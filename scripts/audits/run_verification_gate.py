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
import threading
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

# Read-only source/corpus gates that also read scored artifacts and stage
# manifests bind those too. The scoring completeness preflight took ~17 min on
# every snapshot (2026-10-31) although nothing it reads had changed between runs.
# The raw DSLD labels live outside the repository; this input names their
# content fingerprint (raw_label_fingerprint) in place of a repository glob.
RAW_DSLD_LABELS = '<raw DSLD labels>'

# The scoring audit joins scored, enriched and cleaned (*.json, *.jsonl) stage
# files, every stage manifest and the raw labels the clean manifest fingerprints.
SCORING_AUDIT_CORPUS_INPUTS = (
    'scripts/products/*_scored/scored/*.json',
    'scripts/products/*/cleaned/*.json',
    'scripts/products/*/cleaned/*.jsonl',
    'scripts/products/*/*/.stage_manifest.json',
    'manual_labels/**/*.json', 'manual_labels/**/*.jsonl',
    RAW_DSLD_LABELS,
)

RELEASE_GATE_EXTRA_INPUTS = {
    'scoring assessment completeness preflight': SCORING_AUDIT_CORPUS_INPUTS,
    'scoring assessment readiness': SCORING_AUDIT_CORPUS_INPUTS,
    'active identity integrity': SCORING_AUDIT_CORPUS_INPUTS,
    'raw-to-final line integrity': SCORING_AUDIT_CORPUS_INPUTS,
    'detail-blob field completeness': SCORING_AUDIT_CORPUS_INPUTS,
    'clinical evidence match reachability': SCORING_AUDIT_CORPUS_INPUTS,
}


def release_gate_input_globs(name: str) -> tuple:
    """Content globs the shared release-gate reuse policy binds for ``name``."""
    if name in RELEASE_GATE_EXTRA_INPUTS:
        return (*RELEASE_SOURCE_INPUTS, *RELEASE_GATE_EXTRA_INPUTS[name])
    if name in REUSABLE_RELEASE_GATES:
        return tuple(RELEASE_SOURCE_INPUTS)
    return ()

# Read-only source/corpus gates share these inputs across snapshot and release.
# Generated reports, live catalogs and audit caches are deliberately outside
# this set. Artifact/live/mutating gates never opt into this reuse policy.
# A quiet child used to look identical to a hung release. The runner prints
# STARTING immediately, FINGERPRINT while it hashes, and STILL RUNNING on this
# interval while the child produces no output. An explicit test value is not
# clamped; only the environment default is kept at or above five seconds.
FINGERPRINT_PROGRESS_SECONDS = 15.0
DEFAULT_HEARTBEAT_SECONDS = 30.0


def _heartbeat_interval(explicit: float | None) -> float:
    if explicit is not None:
        return explicit
    raw = os.environ.get('PG_GATE_HEARTBEAT_SECONDS')
    if not raw:
        return DEFAULT_HEARTBEAT_SECONDS
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_HEARTBEAT_SECONDS
    return max(5.0, value)


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


def runtime_identity() -> dict:
    """Shared runtime provenance for stage manifests and verification receipts."""
    try:
        fuzz = importlib.import_module('rapidfuzz.fuzz')
        implementation = sys.modules.get(fuzz.ratio.__module__)
        origin = getattr(implementation, '__file__', None)
        rapidfuzz = {'available': True, 'implementation': fuzz.ratio.__module__,
                    'content_sha256': _sha256(Path(origin)) if origin else None}
    except (ImportError, OSError):
        rapidfuzz = {'available': False}
    executable = Path(sys.executable).resolve()
    return {'python': sys.version,
            'executable': (str(executable), _sha256(executable)),
            'packages': sorted((dist.metadata['Name'], dist.version)
                               for dist in importlib.metadata.distributions()),
            'rapidfuzz': rapidfuzz}


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
    artifact_dir: Path | None = None,
    output_paths: Sequence[Path] = (),
    portable_python: bool = False,
    heartbeat_seconds: float | None = None,
) -> int:
    """Serialize receipt writers; reuse is opt-in for bound read-only checks."""
    receipt_path = Path(receipt_path).resolve()
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    with receipt_path.with_suffix(receipt_path.suffix + '.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return _run_gate(name=name, command=command, log_path=log_path,
                         receipt_path=receipt_path, cwd=cwd,
                         input_globs=input_globs, max_age_seconds=max_age_seconds,
                         artifact_dir=artifact_dir, output_paths=output_paths,
                         portable_python=portable_python,
                         heartbeat_seconds=heartbeat_seconds)


# Only variables the pipeline, release scripts and interpreter actually read
# bind a result. The whole shell environment once did: release_full.sh exports
# PYTHONUNBUFFERED=1 and the corpus runner exports PHARMAGUIDE_DATASET_ROOT, so a
# catalog built by the standalone snapshot was never "current" for the release
# that followed, and every full run assembled the catalog twice (2026-10-31).
# PYTHON* covers the interpreter selector and every interpreter behaviour
# switch (PYTHONPATH, PYTHONOPTIMIZE, PYTHONWARNINGS, PYTHONUTF8 ...); LC_*,
# LANG and TZ set default text encoding and local time.
BOUND_ENVIRONMENT_PREFIXES = ('PG_', 'PHARMAGUIDE_', 'SUPABASE_', 'FLUTTER_', 'SKIP_',
                              'PYTHON', 'LC_')
BOUND_ENVIRONMENT_NAMES = frozenset({
    'PATH', 'LANG', 'TZ', 'VIRTUAL_ENV', 'PYENV_VERSION', 'HOME',
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


def _dataset_root(environ) -> Path | None:
    # The resolver is the existing owner in scripts/dataset_paths.py; a copy of
    # this runner without it reads the raw override only.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    try:
        from dataset_paths import brand_dataset_root
    except ImportError:
        brand_dataset_root = None
    finally:
        sys.path.pop(0)
    if brand_dataset_root is not None:
        return brand_dataset_root(environ=environ).expanduser().resolve()
    if environ.get('PHARMAGUIDE_DATASET_ROOT'):
        return Path(environ['PHARMAGUIDE_DATASET_ROOT']).expanduser().resolve()
    return None


def raw_label_fingerprint(raw_root: Path | None, on_file=None) -> dict:
    """Content of every raw DSLD label the raw-to-final and scoring audits read."""
    if raw_root is None or not raw_root.is_dir():
        return {'root': str(raw_root), 'missing': True}
    labels = []
    paths = sorted({
        path for pattern in ('*.json', '*.jsonl')
        for path in raw_root.rglob(pattern) if path.is_file()
    })
    for path in paths:
        labels.append((str(path.relative_to(raw_root)), _sha256(path)))
        if on_file is not None:
            on_file(path)
    return {'root': str(raw_root), 'labels': labels}


def _bound_environment(environ) -> dict:
    bound = {
        key: value for key, value in environ.items()
        if key not in UNBOUND_ENVIRONMENT_NAMES
        and (key in BOUND_ENVIRONMENT_NAMES or key.startswith(BOUND_ENVIRONMENT_PREFIXES))
    }
    # The dataset root binds by its resolved path, so exporting the default
    # value equals leaving it unset.
    root = _dataset_root(environ)
    if root is not None:
        bound['PHARMAGUIDE_DATASET_ROOT'] = str(root)
    return bound


def _fingerprint_progress(label: str, started: float, progress: dict) -> None:
    if not label:
        return
    now = time.monotonic()
    if now < progress['next']:
        return
    print(
        f'FINGERPRINT: {label} | {progress["seen"]} files | {now - started:.0f}s',
        file=sys.stderr, flush=True,
    )
    progress['next'] = now + FINGERPRINT_PROGRESS_SECONDS


def _input_binding(
    cwd: Path, command: Sequence[str], patterns: Sequence[str],
    *, exclude_paths: Sequence[str] = (), portable_python: bool = False,
    artifact_dir: Path | None = None, output_paths: Sequence[Path] = (),
    label: str = '',
) -> str:
    # Never persist credentials or environment values. The fingerprint binds
    # effective configuration, not shell bookkeeping or the per-run lock token.
    environment = _bound_environment(os.environ)
    if portable_python:
        for key in ('PATH', 'PYTHON', 'PG_PYTHON', 'VIRTUAL_ENV', 'PYENV_VERSION'):
            environment.pop(key, None)
    files = {}
    # This cache lives for one content pass only. Never carry hashes across
    # the before/after verification boundary or a later publication check.
    digests = {}
    started = time.monotonic()
    progress = {'seen': 0, 'next': started + FINGERPRINT_PROGRESS_SECONDS}

    def saw_file() -> None:
        progress['seen'] += 1
        _fingerprint_progress(label, started, progress)

    for pattern in patterns:
        if pattern == RAW_DSLD_LABELS:
            files[pattern] = raw_label_fingerprint(_dataset_root(os.environ), on_file=lambda _path: saw_file())
            continue
        entries = []
        for path in sorted(cwd.glob(pattern)):
            if path.is_file():
                relative = str(path.relative_to(cwd))
                if any(fnmatchcase(relative, excluded) for excluded in exclude_paths):
                    continue
                if path not in digests:
                    digests[path] = _sha256(path)
                entries.append((relative, digests[path]))
                saw_file()
        files[pattern] = entries
    executable = shutil.which(str(command[0]))
    normalized = list(command)
    artifact = None
    if artifact_dir is not None:
        root = artifact_dir.resolve()
        artifact = {}
        for pattern in ('pharmaguide_core.db', 'export_manifest.json', 'detail_index.json',
                        'export_audit_report.json', 'detail_blobs/**/*.json'):
            hashed = []
            for path in sorted(root.glob(pattern)):
                if path.is_file() and path.resolve() not in {item.resolve() for item in output_paths}:
                    hashed.append((str(path.relative_to(root)), _sha256(path)))
                    saw_file()
            artifact[pattern] = hashed
        if not (root / 'pharmaguide_core.db').is_file() or not (root / 'export_manifest.json').is_file():
            raise ValueError(f'Missing candidate core/manifest: {root}')
        normalized = [arg.replace(str(root), '<catalog>') for arg in normalized]
    # Relative/absolute spellings inside the same checkout are equivalent.
    normalized = [arg.replace(str(cwd.resolve()) + '/', '') for arg in normalized]
    return _canonical_sha256({
        'files': files, 'environment': environment, 'runtime': runtime_identity(),
        'executable': (executable, _sha256(Path(executable))) if executable else None,
        'cwd': str(cwd), 'command': normalized, 'artifact': artifact,
    })


def _can_reuse(receipt_path: Path, log_path: Path, *, name: str,
               binding: str, max_age_seconds: float, output_paths: Sequence[Path] = ()) -> bool:
    try:
        receipt = json.loads(receipt_path.read_text())
        seal = receipt.pop('receipt_sha256')
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(receipt['completed_at'])).total_seconds()
        return (seal == _canonical_sha256(receipt) and receipt['exit_code'] == 0
                and receipt['gate_name'] == name and receipt.get('input_binding') == binding
                and receipt['log'] == str(log_path) and receipt['log_sha256'] == _sha256(log_path)
                and receipt.get('output_hashes', {}) == _output_hashes(output_paths)
                and 0 <= age < max_age_seconds)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return False


def _output_hashes(paths: Sequence[Path]) -> dict:
    return {str(index): _sha256(Path(path)) for index, path in enumerate(paths)}


def _log_tail(path: Path, lines: int = 12, max_bytes: int = 16384) -> str:
    try:
        size = path.stat().st_size
        with path.open('rb') as handle:
            handle.seek(max(0, size - max_bytes))
            text = handle.read().decode('utf-8', errors='replace')
    except OSError:
        return ''
    return '\n'.join(text.splitlines()[-lines:])


def _run_gate(*, name: str, command: Sequence[str], log_path: Path,
              receipt_path: Path, cwd: Path, input_globs: Sequence[str],
              max_age_seconds: float, artifact_dir: Path | None = None,
              output_paths: Sequence[Path] = (), portable_python: bool = False,
                        heartbeat_seconds: float | None = None) -> int:
    """Run ``command`` and return its actual exit code after writing a receipt."""
    if not name.strip():
        raise ValueError("gate name must not be empty")
    if not command:
        raise ValueError("verification command must not be empty")

    print(f'STARTING: {name}', flush=True)
    cwd = Path(cwd).resolve()
    log_path = Path(log_path).resolve()
    receipt_path = Path(receipt_path).resolve()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    invocation_started = time.monotonic()
    binding_started = invocation_started
    binding_options = dict(artifact_dir=artifact_dir, output_paths=output_paths,
                           portable_python=portable_python, label=name)
    binding = _input_binding(cwd, command, input_globs, **binding_options) if input_globs else None
    binding_duration = time.monotonic() - binding_started
    if binding and _can_reuse(receipt_path, log_path, name=name, binding=binding,
                             max_age_seconds=max_age_seconds, output_paths=output_paths):
        receipt = json.loads(receipt_path.read_text())
        receipt.pop('receipt_sha256', None)
        receipt['last_invocation'] = {
            'outcome': 'reused', 'reason': 'unchanged content and successful sealed log',
            'checked_at': _utc_now(), 'duration_seconds': round(binding_duration, 6),
        }
        _write_receipt(receipt_path, receipt)
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

    stop_heartbeat = threading.Event()
    last_output = time.monotonic()
    last_line = ''
    heartbeat = _heartbeat_interval(heartbeat_seconds)

    def beat() -> None:
        while not stop_heartbeat.wait(heartbeat):
            quiet = time.monotonic() - last_output
            elapsed = time.monotonic() - invocation_started
            shown = last_line or '(no output yet)'
            print(
                f'STILL RUNNING: {name} | elapsed {elapsed:.0f}s | quiet for {quiet:.0f}s | last line: {shown}',
                flush=True,
            )

    with log_path.open("wb") as log_handle:
        process = subprocess.Popen(
            [str(part) for part in command],
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        assert process.stdout is not None
        heartbeat_thread = None
        if heartbeat > 0:
            heartbeat_thread = threading.Thread(target=beat, name='gate-heartbeat', daemon=True)
            heartbeat_thread.start()
        pending = b''
        try:
            for chunk in iter(lambda: process.stdout.read1(64 * 1024), b""):
                log_handle.write(chunk)
                log_handle.flush()
                sys.stdout.buffer.write(chunk)
                sys.stdout.buffer.flush()
                last_output = time.monotonic()
                pending = (pending + chunk)[-4096:]
                lines = [
                    line for line in pending.decode('utf-8', errors='replace').splitlines()
                    if line.strip()
                ]
                if lines:
                    last_line = lines[-1][:240]
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
            stop_heartbeat.set()
            if heartbeat_thread is not None:
                heartbeat_thread.join(timeout=2)

    if binding:
        binding_started = time.monotonic()
        final_binding = _input_binding(cwd, command, input_globs, **binding_options)
        binding_duration += time.monotonic() - binding_started
        if final_binding != binding:
            print(f'FAILED: {name} — inputs changed during verification', file=sys.stderr, flush=True)
            exit_code = exit_code or 125

    try:
        output_hashes = _output_hashes(output_paths) if exit_code == 0 else {}
    except OSError:
        output_hashes = {}
        exit_code = 125
    if exit_code != 0:
        elapsed = time.monotonic() - invocation_started
        print(
            f'FAILED: {name} | exit {exit_code} | elapsed {elapsed:.0f}s\n{_log_tail(log_path)}',
            file=sys.stderr, flush=True,
        )
    payload = {
        "output_hashes": output_hashes,
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
        "last_invocation": {
            "outcome": "executed", "reason": "no reusable success for current inputs",
            "duration_seconds": round(time.monotonic() - invocation_started, 6),
        },
    }
    _write_receipt(receipt_path, payload)
    print(f'FINISHED: {name} | exit {exit_code} | {payload["duration_seconds"]:.3f}s', flush=True)
    return exit_code


def release_gate_options(name: str, command: Sequence[str], cwd: Path, release_check: bool = True):
    if not command:
        raise ValueError('A verification command is required')
    artifact_dir = None
    output_paths = []
    artifact_names = {'scoring assessment readiness', 'active identity integrity',
                      'raw-to-final line integrity', 'detail-blob field completeness'}
    def option(flag):
        return (cwd / command[command.index(flag) + 1]).resolve() if flag in command else None
    if release_check and name in artifact_names:
        artifact_dir = option('--dist-dir') or option('--export-dir') or option('--build-dir')
        if artifact_dir is None:
            raise ValueError(f'{name} requires a candidate directory')
    if release_check and release_gate_input_globs(name):
        output = option('--out') or option('--output')
        if output is not None:
            output_paths.append(output)
    # Only explicitly registered direct Python checks have known tool resolution.
    portable = bool(release_check and release_gate_input_globs(name)
                    and Path(command[0]).resolve() == Path(sys.executable).resolve())
    return artifact_dir, output_paths, portable


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
    artifact_dir, output_paths, portable = release_gate_options(args.name, command, Path(args.cwd), args.release_check)
    return run_gate(
        artifact_dir=artifact_dir, output_paths=output_paths, portable_python=portable,
        name=args.name,
        command=command,
        log_path=args.log,
        receipt_path=args.receipt,
        cwd=args.cwd,
        input_globs=[*args.input_glob,
                     *(release_gate_input_globs(args.name) if args.release_check else ())],
        max_age_seconds=args.max_age_seconds,
    )


if __name__ == "__main__":
    raise SystemExit(main())
