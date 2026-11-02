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

from audits.run_verification_gate import (
    RELEASE_SOURCE_INPUTS, SCORING_AUDIT_CORPUS_INPUTS, _input_binding, _sha256,
    _canonical_sha256, _write_receipt,
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


def catalog_input_binding(repo: Path) -> str:
    """Bind catalog production separately from the checks run against its bytes."""
    from pipeline_freshness import _imported_modules
    repo = repo.resolve()
    scripts = repo / 'scripts'
    pending = [scripts / name for name in ('build_final_db.py', 'release_catalog_artifact.py')]
    producers = set()
    while pending:
        path = pending.pop()
        if path not in producers:
            producers.add(path)
            if path.is_file():
                pending.extend(_imported_modules(scripts, path) - producers)
    inputs = tuple(str(p.relative_to(repo)) for p in sorted(producers))
    return _input_binding(repo, ['catalog-assembly'], (
        *inputs, '.env', 'requirements*.txt', '.python-version',
        'scripts/data/*.json', 'scripts/data/curated*/*.json',
        'scripts/config/**/*.json', 'scripts/contracts/*.json',
        'scripts/scoring_v4/config/*.json',
        'scripts/products/*_enriched/enriched/*.json', *SCORING_AUDIT_CORPUS_INPUTS,
    ), portable_python=True)


def catalog_validation_binding(repo: Path) -> str:
    """Gate implementation changes require revalidation, never blind promotion."""
    return _input_binding(repo.resolve(), ['catalog-validation'], (
        *RELEASE_SOURCE_INPUTS, *SCORING_AUDIT_CORPUS_INPUTS,
    ), exclude_paths=CATALOG_NONPRODUCER_PATHS, portable_python=True)


def _construction_outputs(root: Path) -> dict:
    for required in ('pharmaguide_core.db', 'export_manifest.json'):
        if not (root / required).is_file():
            raise FileNotFoundError(root / required)
    return {str(p.relative_to(root)): _sha256(p) for p in sorted(root.rglob('*'))
            if p.is_file() and p.name != '.construction-receipt.json'}


def record_catalog_construction(repo: Path, root: Path, expected: str) -> None:
    require_catalog_inputs(repo, expected)
    outputs = _construction_outputs(root)
    require_catalog_inputs(repo, expected)
    _write_receipt(root / '.construction-receipt.json',
                   {'input_binding': expected, 'outputs': outputs})


def catalog_construction_is_current(repo: Path, root: Path) -> bool:
    from release_catalog_artifact import check_release_freshness, DEFAULT_MAX_AGE_HOURS, ReleaseValidationError
    try:
        manifest = json.loads((root / 'export_manifest.json').read_text())
        check_release_freshness(manifest=manifest, max_age_hours=DEFAULT_MAX_AGE_HOURS, allow_stale=False)
        receipt = json.loads((root / '.construction-receipt.json').read_text())
        seal = receipt.pop('receipt_sha256')
        return (seal == _canonical_sha256(receipt)
                and receipt['input_binding'] == catalog_input_binding(repo)
                and receipt['outputs'] == _construction_outputs(root))
    except (OSError, ValueError, KeyError, TypeError, AttributeError, ReleaseValidationError):
        return False


def restore_catalog_construction(repo: Path, root: Path, destination: Path) -> None:
    if not catalog_construction_is_current(repo, root):
        raise ValueError('Construction is incomplete, changed or stale; cannot reuse')
    shutil.copytree(root, destination, ignore=shutil.ignore_patterns('.construction-receipt.json'))
    if _construction_outputs(root) != _construction_outputs(destination):
        raise ValueError('Construction changed while copying; no promotion allowed')


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
        'input_binding': expected, 'validation_binding': catalog_validation_binding(repo), 'outputs': outputs,
    })


def catalog_build_is_current(repo: Path) -> bool:
    try:
        receipt = json.loads(catalog_receipt_path(repo).read_text())
        seal = receipt.pop('receipt_sha256')
        return (seal == _canonical_sha256(receipt)
                and receipt['input_binding'] == catalog_input_binding(repo)
                and receipt.get('validation_binding') == catalog_validation_binding(repo)
                and receipt['outputs'] == _catalog_outputs(repo))
    except (OSError, ValueError, KeyError, TypeError):
        return False


def require_catalog_disk_space(repo: Path, destination: Path) -> None:
    # Existing mirrors must coexist with their replacements until atomic
    # promotion succeeds. The immutable construction coexists with both
    # replacement mirrors. Existing retained copies already reduce free space.
    roots = [repo / 'scripts' / name for name in ('dist', 'final_db_output')]
    sizes = sum(path.stat().st_size for root in roots if root.exists()
                for path in root.rglob('*') if path.is_file())
    source_bytes = sum(path.stat().st_size for pattern in (
        'scripts/products/*_enriched/enriched/*.json',
        'scripts/products/*_scored/scored/*.json',
    ) for path in repo.glob(pattern) if path.is_file())
    final_size = sum(path.stat().st_size for path in roots[1].rglob('*') if path.is_file())
    required = sizes + source_bytes + max(final_size, source_bytes) + 1024 ** 3
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


def describe_release_plan(repo: Path) -> None:
    """Read-only recovery plan from the same owners execution uses."""
    from dataset_paths import brand_dataset_root
    from pipeline_freshness import dataset_resume_plan
    from audits.run_verification_gate import (
        release_gate_input_globs, release_gate_options, _can_reuse,
    )
    repo = repo.resolve()
    raw = brand_dataset_root()
    datasets = [(p.name, p) for p in sorted(raw.iterdir()) if p.is_dir()] if raw.is_dir() else []
    submissions = repo / 'manual_labels/product_submissions'
    if submissions.is_dir():
        datasets.append(('Product_Submissions', submissions))
    for name, root in datasets:
        try:
            stages, reason = dataset_resume_plan(repo, root, repo / f'scripts/products/output_{name}')
        except (OSError, ValueError) as exc:
            stages, reason = ['clean', 'enrich', 'score'], str(exc)
        action = 'rebuild ' + ','.join(stages) if stages else 'reuse all stages'
        print(f'Producer {name}: {action} — {reason}', flush=True)
    binding = catalog_input_binding(repo)
    root = repo / f'scripts/.catalog-construction.{binding[:20]}'
    print('Catalog construction: ' + ('reuse verified bytes' if catalog_construction_is_current(repo, root)
                                      else 'build required'), flush=True)
    for path in sorted((repo / 'scripts/reports/release-gates').glob('*.json')):
        try:
            receipt = json.loads(path.read_text())
            name, command = receipt['gate_name'], receipt['command']
            patterns = release_gate_input_globs(name)
            if not patterns:
                continue
            artifact, outputs, portable = release_gate_options(name, command, repo)
            current = _input_binding(repo, command, patterns, artifact_dir=artifact,
                                     output_paths=outputs, portable_python=portable)
            reusable = _can_reuse(path, Path(receipt['log']), name=name, binding=current,
                                 max_age_seconds=86400, output_paths=outputs)
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            continue
        print(f'Gate {name}: ' + ('verified reusable' if reusable else 'execute; receipt not current'), flush=True)
    print('Missing or incomplete gate evidence: execute; never inferred from an old pass.')
    print('Publication and live comparisons: always execute')
    print('Next: bash batch_run_all_datasets.sh --resume')


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
    actions.add_argument('--preflight-plan', action='store_true')
    actions.add_argument('--catalog-current', action='store_true')
    actions.add_argument('--construction-current', type=Path)
    actions.add_argument('--record-construction', type=Path)
    actions.add_argument('--restore-construction', type=Path)
    actions.add_argument('--validation-input-binding', action='store_true')
    actions.add_argument('--check-validation-binding')
    parser.add_argument('--binding')
    actions.add_argument('--check-input-binding')
    actions.add_argument('--record-catalog')
    actions.add_argument('--check-disk', type=Path)
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)
    if args.preflight_plan:
        describe_release_plan(args.repo_root)
        return 0
    if args.validation_input_binding:
        print(catalog_validation_binding(args.repo_root))
        return 0
    if args.check_validation_binding:
        if catalog_validation_binding(args.repo_root) != args.check_validation_binding:
            raise ValueError('Validation source changed during this snapshot; no promotion allowed')
        return 0
    if args.construction_current:
        return 0 if catalog_construction_is_current(args.repo_root, args.construction_current) else 1
    if args.record_construction:
        if not args.binding:
            raise ValueError('--record-construction requires --binding')
        record_catalog_construction(args.repo_root, args.record_construction, args.binding)
        return 0
    if args.restore_construction:
        if not args.final_candidate:
            raise ValueError('--restore-construction requires --final-candidate')
        restore_catalog_construction(args.repo_root, args.restore_construction, Path(args.final_candidate))
        return 0
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
