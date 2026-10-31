#!/usr/bin/env python3
"""Run one verification command and emit an exit-code/log-bound receipt.

The receipt is written by the same process that observes the child exit code.
Candidate reports consume these receipts instead of trusting hand-authored
``exit_code`` fields.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Sequence


RECEIPT_SCHEMA_VERSION = "1.0.0"

REUSABLE_RELEASE_GATES = frozenset({
    'cleaner/IQD row contract',
    'enrichment/IQD source-of-truth contract', 'clinical drift contract',
    'RDA/UL emitted-reference stamp parity',
})

# Read-only source/corpus gates share these inputs across snapshot and release.
# Generated reports, live catalogs and audit caches are deliberately outside
# this set. Artifact/live/mutating gates never opt into this reuse policy.
RELEASE_SOURCE_INPUTS = (
    '.env', 'scripts/**/*.py', 'scripts/**/*.sh',
    'requirements*.txt', '.python-version',
    'scripts/data/*.json', 'scripts/data/curated*/*.json', 'scripts/config/**/*.json',
    'scripts/contracts/*.json', 'scripts/scoring_v4/config/*.json',
    'scripts/tests/**/*.json',
    'scripts/products/*_enriched/enriched/*.json',
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def _canonical_sha256(payload: dict) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _write_receipt(path: Path, payload: dict) -> None:
    body = dict(payload)
    body["receipt_sha256"] = _canonical_sha256(body)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(body, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def run_gate(
    *,
    name: str,
    command: Sequence[str],
    log_path: Path,
    receipt_path: Path,
    cwd: Path,
    input_globs: Sequence[str] = (),
    max_age_seconds: float = 86400,
) -> int:
    """Serialize receipt writers; reuse is opt-in for bound read-only checks."""
    receipt_path = Path(receipt_path).resolve()
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    with receipt_path.with_suffix(receipt_path.suffix + '.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return _run_gate(name=name, command=command, log_path=log_path,
                         receipt_path=receipt_path, cwd=cwd,
                         input_globs=input_globs, max_age_seconds=max_age_seconds)


# Only variables the pipeline, release scripts and interpreter actually read
# bind a result. The whole shell environment once did: release_full.sh exports
# PYTHONUNBUFFERED=1 and the corpus runner exports PHARMAGUIDE_DATASET_ROOT, so a
# catalog built by the standalone snapshot was never "current" for the release
# that followed, and every full run assembled the catalog twice (2026-10-31).
BOUND_ENVIRONMENT_PREFIXES = ('PG_', 'PHARMAGUIDE_', 'SUPABASE_', 'FLUTTER_', 'SKIP_')
BOUND_ENVIRONMENT_NAMES = frozenset({
    'PATH', 'PYTHON', 'PYTHONPATH', 'PYTHONHASHSEED', 'PYTHONSAFEPATH',
    'VIRTUAL_ENV', 'PYENV_VERSION', 'HOME',
    'UMLS_API_KEY', 'PUBMED_API_KEY', 'PUBMED_TOOL', 'PUBMED_EMAIL',
    'NCBI_API_KEY', 'NCBI_TOOL', 'NCBI_EMAIL', 'USDA_API_KEY', 'FDC_API_KEY',
    'OPENFDA_API_KEY', 'COMPTOX_API_KEY', 'VALYU_API_KEY',
    'WADA_LAST_UPDATED', 'ALLOW_CURATED_CONFLICTS', 'ENRICH_DEBUG_AMBIGUITY',
    'SAFETY_ALERT_DISPATCH_SECRET', 'KEY_NAME', 'SUPABASE_DRY_RUN',
})
# Bookkeeping the shell or a tool call sets per process; never configuration.
UNBOUND_ENVIRONMENT_NAMES = frozenset({
    'PG_RELEASE_LOCK_TOKEN', 'PG_RELEASE_LOCK_WRAPPED', 'PYTHONUNBUFFERED',
    'PHARMAGUIDE_DATASET_ROOT',
})


def _bound_environment(environ) -> dict:
    bound = {
        key: value for key, value in environ.items()
        if key not in UNBOUND_ENVIRONMENT_NAMES
        and (key in BOUND_ENVIRONMENT_NAMES or key.startswith(BOUND_ENVIRONMENT_PREFIXES))
    }
    # The dataset root binds by its resolved path, so exporting the default
    # value equals leaving it unset. The resolver is the existing owner in
    # scripts/dataset_paths.py; a copy of this runner without it binds the raw
    # override only.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    try:
        from dataset_paths import brand_dataset_root
    except ImportError:
        brand_dataset_root = None
    finally:
        sys.path.pop(0)
    if brand_dataset_root is not None:
        root = brand_dataset_root(environ=environ)
    elif environ.get('PHARMAGUIDE_DATASET_ROOT'):
        root = Path(environ['PHARMAGUIDE_DATASET_ROOT'])
    else:
        root = None
    if root is not None:
        bound['PHARMAGUIDE_DATASET_ROOT'] = str(root.expanduser().resolve())
    return bound


def _input_binding(
    cwd: Path, command: Sequence[str], patterns: Sequence[str],
    *, exclude_paths: Sequence[str] = (),
) -> str:
    # Never persist credentials or environment values. The fingerprint binds
    # effective configuration, not shell bookkeeping or the per-run lock token.
    environment = _bound_environment(os.environ)
    files = {}
    # This cache lives for one content pass only. Never carry hashes across
    # the before/after verification boundary or a later publication check.
    digests = {}
    for pattern in patterns:
        entries = []
        for path in sorted(cwd.glob(pattern)):
            if path.is_file():
                relative = str(path.relative_to(cwd))
                if any(fnmatchcase(relative, excluded) for excluded in exclude_paths):
                    continue
                if path not in digests:
                    digests[path] = _sha256(path)
                entries.append((relative, digests[path]))
        files[pattern] = entries
    executable = shutil.which(str(command[0]))
    return _canonical_sha256({
        'files': files, 'environment': environment, 'python': sys.version,
        'packages': sorted((dist.metadata['Name'], dist.version)
                           for dist in importlib.metadata.distributions()),
        'executable': (executable, _sha256(Path(executable))) if executable else None,
        'cwd': str(cwd), 'command': list(command),
    })


def _can_reuse(receipt_path: Path, log_path: Path, *, name: str,
               binding: str, max_age_seconds: float) -> bool:
    try:
        receipt = json.loads(receipt_path.read_text())
        seal = receipt.pop('receipt_sha256')
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(receipt['completed_at'])).total_seconds()
        return (seal == _canonical_sha256(receipt) and receipt['exit_code'] == 0
                and receipt['gate_name'] == name and receipt.get('input_binding') == binding
                and receipt['log'] == str(log_path) and receipt['log_sha256'] == _sha256(log_path)
                and 0 <= age < max_age_seconds)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return False


def _run_gate(*, name: str, command: Sequence[str], log_path: Path,
              receipt_path: Path, cwd: Path, input_globs: Sequence[str],
              max_age_seconds: float) -> int:
    """Run ``command`` and return its actual exit code after writing a receipt."""
    if not name.strip():
        raise ValueError("gate name must not be empty")
    if not command:
        raise ValueError("verification command must not be empty")

    cwd = Path(cwd).resolve()
    log_path = Path(log_path).resolve()
    receipt_path = Path(receipt_path).resolve()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    binding_started = time.monotonic()
    binding = _input_binding(cwd, command, input_globs) if input_globs else None
    binding_duration = time.monotonic() - binding_started
    if binding and _can_reuse(receipt_path, log_path, name=name, binding=binding,
                             max_age_seconds=max_age_seconds):
        print(f'REUSED: {name} — verified unchanged inputs and successful log '
              f'| input binding {binding_duration:.3f}s', flush=True)
        return 0
    started_at = _utc_now()
    started_monotonic = time.monotonic()
    exit_code = 125
    # Invalidate an older success BEFORE launching: killed or incomplete
    # attempts must never leave a previous receipt looking like this success.
    _write_receipt(receipt_path, {'gate_name': name, 'exit_code': 125,
                                 'started_at': started_at, 'completed_at': None})

    with log_path.open("wb") as log_handle:
        process = subprocess.Popen(
            [str(part) for part in command],
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        assert process.stdout is not None
        try:
            for chunk in iter(lambda: process.stdout.read1(64 * 1024), b""):
                log_handle.write(chunk)
                log_handle.flush()
                sys.stdout.buffer.write(chunk)
                sys.stdout.buffer.flush()
            exit_code = process.wait()
        except KeyboardInterrupt:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            exit_code = 130
        finally:
            process.stdout.close()

    if binding:
        binding_started = time.monotonic()
        final_binding = _input_binding(cwd, command, input_globs)
        binding_duration += time.monotonic() - binding_started
        if final_binding != binding:
            print(f'FAILED: {name} — inputs changed during verification', file=sys.stderr)
            exit_code = exit_code or 125

    payload = {
        "receipt_schema_version": RECEIPT_SCHEMA_VERSION,
        "gate_name": name,
        "command": [str(part) for part in command],
        "cwd": str(cwd),
        "started_at": started_at,
        "completed_at": _utc_now(),
        "duration_seconds": round(time.monotonic() - started_monotonic, 3),
        "exit_code": exit_code,
        "log": str(log_path),
        "log_sha256": _sha256(log_path),
        "input_binding": binding,
        "input_binding_duration_seconds": round(binding_duration, 6),
        "log_bytes": log_path.stat().st_size,
    }
    _write_receipt(receipt_path, payload)
    print(f'FINISHED: {name} | exit {exit_code} | {payload["duration_seconds"]:.3f}s', flush=True)
    return exit_code


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--log", type=Path)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--receipt-dir", type=Path,
                        help='Keep per-gate logs and receipts in this existing report directory')
    parser.add_argument("--cwd", default=Path.cwd(), type=Path)
    parser.add_argument("--input-glob", action='append', default=[],
                        help='Bind and reuse a read-only check against these content globs')
    parser.add_argument("--max-age-seconds", type=float, default=86400)
    parser.add_argument("--release-check", action='store_true',
                        help='Apply the shared read-only release-gate reuse policy')
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = list(args.command)
    if command and command[0] == "--":
        command.pop(0)
    if args.receipt_dir:
        key = hashlib.sha256(args.name.encode()).hexdigest()[:20]
        args.log = args.receipt_dir / f'{key}.log'
        args.receipt = args.receipt_dir / f'{key}.json'
    if not args.log or not args.receipt:
        parser.error('supply --receipt-dir or both --log and --receipt')
    return run_gate(
        name=args.name,
        command=command,
        log_path=args.log,
        receipt_path=args.receipt,
        cwd=args.cwd,
        input_globs=[*args.input_glob, *(RELEASE_SOURCE_INPUTS
                     if args.release_check and args.name in REUSABLE_RELEASE_GATES else ())],
        max_age_seconds=args.max_age_seconds,
    )


if __name__ == "__main__":
    raise SystemExit(main())
