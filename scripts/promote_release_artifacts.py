#!/usr/bin/env python3
"""Atomically promote gated catalog candidates with rollback.

The snapshot builder writes and validates sibling candidate directories first.
This module is the only step allowed to replace the live ``dist`` and
``final_db_output`` directories.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path
from typing import Optional

from dataset_paths import brand_dataset_root
from audits.run_verification_gate import (
    RELEASE_SOURCE_INPUTS, _input_binding, _sha256, _canonical_sha256, _write_receipt,
)


# Test harness edits require new CI and release checks, but cannot change the
# catalog bytes that snapshot assembly produces. Source-gate receipts retain
# their broader input set; only the catalog build receipt excludes these paths.
CATALOG_NONPRODUCER_PATHS = (
    'scripts/test.sh',
    'scripts/tests/*',
    'scripts/test_profiles.py',
    'scripts/test_lock.py',
    'scripts/test_shard_plan.py',
    'scripts/ci_skip_guard.py',
)


def _raw_label_fingerprint(raw_root: Path) -> dict:
    """Content of every raw DSLD label the snapshot's raw-to-final gate reads."""
    if not raw_root.is_dir():
        return {'root': str(raw_root), 'missing': True}
    return {'root': str(raw_root), 'labels': [
        (str(path.relative_to(raw_root)), _sha256(path)) for path in sorted(raw_root.rglob('*.json'))]}


def catalog_input_binding(repo: Path) -> str:
    """Bind assembly to content, runtime and configuration, never mtimes.

    Includes the raw DSLD labels: a catalog gated against other raw labels is
    not current, so the raw-to-final comparison reruns (ADR-0005).
    """
    return _canonical_sha256({
        'inputs': _input_binding(repo.resolve(), ['catalog-assembly'], (
            *RELEASE_SOURCE_INPUTS,
            'scripts/products/*_scored/scored/*.json',
            'manual_labels/**/*.json',
        ), exclude_paths=CATALOG_NONPRODUCER_PATHS),
        'raw_labels': _raw_label_fingerprint(brand_dataset_root()),
    })


def require_catalog_inputs(repo: Path, expected: str) -> None:
    if catalog_input_binding(repo) != expected:
        raise ValueError('Catalog inputs changed during this release; no promotion/publication allowed')


def catalog_receipt_path(repo: Path) -> Path:
    return repo / 'scripts/reports/release-gates/catalog-assembly.json'


def _catalog_outputs(repo: Path) -> dict:
    outputs = {}
    for directory in ('dist', 'final_db_output'):
        root = repo / 'scripts' / directory
        for required in ('pharmaguide_core.db', 'export_manifest.json'):
            if not (root / required).is_file():
                raise FileNotFoundError(root / required)
        # Images/interactions have their own owners and release gates. Include
        # every catalog-owned artifact, including additions and deletions.
        for pattern in ('pharmaguide_core.db', 'export_manifest.json',
                        'detail_index.json', 'detail_blobs/**/*',
                        'export_audit_report.json', 'RELEASE_NOTES.md'):
            for path in sorted(root.glob(pattern)):
                if path.is_file():
                    outputs[str(path.relative_to(repo))] = _sha256(path)
    return outputs


def record_catalog_build(repo: Path, expected: str) -> None:
    require_catalog_inputs(repo, expected)
    outputs = _catalog_outputs(repo)
    require_catalog_inputs(repo, expected)
    _write_receipt(catalog_receipt_path(repo), {
        'input_binding': expected, 'outputs': outputs,
    })


def catalog_build_is_current(repo: Path) -> bool:
    try:
        receipt = json.loads(catalog_receipt_path(repo).read_text())
        seal = receipt.pop('receipt_sha256')
        return (seal == _canonical_sha256(receipt)
                and receipt['input_binding'] == catalog_input_binding(repo)
                and receipt['outputs'] == _catalog_outputs(repo))
    except (OSError, ValueError, KeyError, TypeError):
        return False


def require_catalog_disk_space(repo: Path, destination: Path) -> None:
    # Existing mirrors must coexist with their replacements until atomic
    # promotion succeeds. Include source bytes and 1 GiB working headroom.
    roots = [repo / 'scripts' / name for name in ('dist', 'final_db_output')]
    sizes = sum(path.stat().st_size for root in roots if root.exists()
                for path in root.rglob('*') if path.is_file())
    source_bytes = sum(path.stat().st_size for pattern in (
        'scripts/products/*_enriched/enriched/*.json',
        'scripts/products/*_scored/scored/*.json',
    ) for path in repo.glob(pattern) if path.is_file())
    required = sizes + source_bytes + 1024 ** 3
    free = shutil.disk_usage(destination).free
    if free < required:
        raise OSError(f'Insufficient free disk for catalog candidates: {free} available, '
                      f'{required} estimated bytes required. No build started.')


def _remove_directory(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)


def _require_atomic_sibling(candidate: Path, live: Path) -> None:
    if candidate.parent.resolve() != live.parent.resolve():
        raise ValueError(
            f"candidate {candidate} must be a sibling of {live} so promotion "
            "uses an atomic same-filesystem rename"
        )


def promote_release_artifacts(
    *,
    candidate_dist: Path,
    candidate_final: Path,
    live_dist: Path,
    live_final: Path,
) -> None:
    """Rename both gated candidates into place, restoring both on failure."""
    candidate_dist = candidate_dist.resolve()
    candidate_final = candidate_final.resolve()
    live_dist = live_dist.resolve()
    live_final = live_final.resolve()

    for candidate in (candidate_dist, candidate_final):
        if not candidate.is_dir():
            raise FileNotFoundError(f"release candidate directory missing: {candidate}")
    _require_atomic_sibling(candidate_dist, live_dist)
    _require_atomic_sibling(candidate_final, live_final)

    backup_dist = live_dist.with_name(f".{live_dist.name}.release-backup")
    backup_final = live_final.with_name(f".{live_final.name}.release-backup")
    _remove_directory(backup_dist)
    _remove_directory(backup_final)

    dist_promoted = False
    final_promoted = False
    try:
        if live_dist.exists():
            os.replace(live_dist, backup_dist)
        os.replace(candidate_dist, live_dist)
        dist_promoted = True

        if live_final.exists():
            os.replace(live_final, backup_final)
        os.replace(candidate_final, live_final)
        final_promoted = True
    except Exception:
        # Reverse the partial transaction. Moving a promoted directory back to
        # its candidate name preserves it for diagnosis while the last known
        # good live directories are restored.
        if final_promoted and live_final.exists():
            os.replace(live_final, candidate_final)
        if backup_final.exists():
            os.replace(backup_final, live_final)
        if dist_promoted and live_dist.exists():
            os.replace(live_dist, candidate_dist)
        if backup_dist.exists():
            os.replace(backup_dist, live_dist)
        raise

    _remove_directory(backup_dist)
    _remove_directory(backup_final)


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Promote fully gated catalog candidates into live paths."
    )
    parser.add_argument("--dist-candidate")
    parser.add_argument("--final-candidate")
    parser.add_argument("--dist-dir", default="scripts/dist")
    parser.add_argument("--final-dir", default="scripts/final_db_output")
    parser.add_argument('--repo-root', type=Path, default=Path(__file__).resolve().parents[1])
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument('--catalog-input-binding', action='store_true')
    actions.add_argument('--catalog-current', action='store_true')
    actions.add_argument('--check-input-binding')
    actions.add_argument('--record-catalog')
    actions.add_argument('--check-disk', type=Path)
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)
    if args.catalog_input_binding:
        print(catalog_input_binding(args.repo_root))
        return 0
    if args.catalog_current:
        return 0 if catalog_build_is_current(args.repo_root) else 1
    if args.check_input_binding:
        require_catalog_inputs(args.repo_root, args.check_input_binding)
        return 0
    if args.record_catalog:
        record_catalog_build(args.repo_root, args.record_catalog)
        return 0
    if args.check_disk:
        require_catalog_disk_space(args.repo_root, args.check_disk)
        return 0
    if not args.dist_candidate or not args.final_candidate:
        raise SystemExit('--dist-candidate and --final-candidate are required for promotion')
    promote_release_artifacts(
        candidate_dist=Path(args.dist_candidate),
        candidate_final=Path(args.final_candidate),
        live_dist=Path(args.dist_dir),
        live_final=Path(args.final_dir),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
