from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import promote_release_artifacts as promotion  # noqa: E402


@pytest.fixture(autouse=True)
def _hermetic_raw_root(tmp_path, monkeypatch):
    # The catalog binding hashes raw DSLD labels; never read the operator's corpus.
    monkeypatch.setenv('PHARMAGUIDE_DATASET_ROOT', str(tmp_path / 'no-raw-root'))


def _dir(path: Path, marker: str) -> Path:
    path.mkdir()
    (path / "marker.txt").write_text(marker)
    return path


def test_promotes_both_candidates_and_removes_backups(tmp_path: Path) -> None:
    live_dist = _dir(tmp_path / "dist", "old-dist")
    live_final = _dir(tmp_path / "final", "old-final")
    candidate_dist = _dir(tmp_path / ".dist-candidate", "new-dist")
    candidate_final = _dir(tmp_path / ".final-candidate", "new-final")

    promotion.promote_release_artifacts(
        candidate_dist=candidate_dist,
        candidate_final=candidate_final,
        live_dist=live_dist,
        live_final=live_final,
    )

    assert (live_dist / "marker.txt").read_text() == "new-dist"
    assert (live_final / "marker.txt").read_text() == "new-final"
    assert not candidate_dist.exists()
    assert not candidate_final.exists()
    assert not (tmp_path / ".dist.release-backup").exists()
    assert not (tmp_path / ".final.release-backup").exists()


def test_second_promotion_failure_restores_both_live_directories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    live_dist = _dir(tmp_path / "dist", "old-dist")
    live_final = _dir(tmp_path / "final", "old-final")
    candidate_dist = _dir(tmp_path / ".dist-candidate", "new-dist")
    candidate_final = _dir(tmp_path / ".final-candidate", "new-final")
    real_replace = os.replace

    def fail_final_candidate(source, destination):
        if Path(source) == candidate_final:
            raise OSError("injected final promotion failure")
        return real_replace(source, destination)

    monkeypatch.setattr(promotion.os, "replace", fail_final_candidate)

    with pytest.raises(OSError, match="injected final promotion failure"):
        promotion.promote_release_artifacts(
            candidate_dist=candidate_dist,
            candidate_final=candidate_final,
            live_dist=live_dist,
            live_final=live_final,
        )

    assert (live_dist / "marker.txt").read_text() == "old-dist"
    assert (live_final / "marker.txt").read_text() == "old-final"


def _assembly(repo):
    for relative in ('scripts/products/a_enriched/enriched/one.json',
                     'scripts/products/a_scored/scored/one.json',
                     'scripts/dist/pharmaguide_core.db',
                     'scripts/dist/export_manifest.json',
                     'scripts/final_db_output/pharmaguide_core.db',
                     'scripts/final_db_output/export_manifest.json'):
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{}')
    return promotion.catalog_input_binding(repo)


def test_catalog_receipt_uses_content_and_binds_outputs(tmp_path):
    binding = _assembly(tmp_path)
    promotion.record_catalog_build(tmp_path, binding)
    assert promotion.catalog_build_is_current(tmp_path)
    source = tmp_path / 'scripts/products/a_scored/scored/one.json'
    os.utime(source, None)
    assert promotion.catalog_build_is_current(tmp_path)
    source.write_text('{"score": 90}')
    assert not promotion.catalog_build_is_current(tmp_path)
    with pytest.raises(ValueError, match='inputs changed'):
        promotion.record_catalog_build(tmp_path, binding)


def test_catalog_receipt_rejects_missing_or_modified_artifact(tmp_path):
    binding = _assembly(tmp_path)
    promotion.record_catalog_build(tmp_path, binding)
    db = tmp_path / 'scripts/dist/pharmaguide_core.db'
    db.write_text('modified')
    assert not promotion.catalog_build_is_current(tmp_path)
    db.unlink()
    assert not promotion.catalog_build_is_current(tmp_path)


def test_catalog_receipt_requires_both_mirrors_and_seal(tmp_path):
    binding = _assembly(tmp_path)
    promotion.record_catalog_build(tmp_path, binding)
    receipt = promotion.catalog_receipt_path(tmp_path)
    receipt.write_text(receipt.read_text().replace('input_binding', 'forged_binding'))
    assert not promotion.catalog_build_is_current(tmp_path)
    (tmp_path / 'scripts/final_db_output/export_manifest.json').unlink()
    with pytest.raises(FileNotFoundError):
        promotion.record_catalog_build(tmp_path, binding)


def test_catalog_freeze_detects_new_source_and_runtime_changes(tmp_path, monkeypatch):
    binding = _assembly(tmp_path)
    promotion.require_catalog_inputs(tmp_path, binding)
    monkeypatch.setenv('PG_ASSEMBLY_TEST', 'changed')
    with pytest.raises(ValueError, match='inputs changed'):
        promotion.require_catalog_inputs(tmp_path, binding)


def test_disk_headroom_fails_before_assembly(tmp_path, monkeypatch):
    _assembly(tmp_path)
    monkeypatch.setattr(promotion.shutil, 'disk_usage', lambda _: type('Disk', (), {'free': 1})())
    with pytest.raises(OSError, match='free disk'):
        promotion.require_catalog_disk_space(tmp_path, tmp_path)


@pytest.mark.parametrize('relative', [
    'scripts/data/banned_recalled_ingredients.json',
    'scripts/data/ingredient_quality_map.json',
    'scripts/data/harmful_additives.json',
    'scripts/data/other_ingredients.json',
    'scripts/data/absorption_enhancers.json',
    'scripts/data/rda_optimal_uls.json',
    'scripts/scoring_v4/pillar_explanations.py',
    'scripts/build_final_db.py',
    'scripts/audit_raw_to_final.py',
    'scripts/rebuild_dashboard_snapshot.sh',
])
def test_catalog_receipt_invalidates_on_safety_formulation_and_exporter_changes(tmp_path, relative):
    binding = _assembly(tmp_path)
    promotion.record_catalog_build(tmp_path, binding)
    changed = tmp_path / relative
    changed.parent.mkdir(parents=True, exist_ok=True)
    changed.write_text('# new source')
    assert not promotion.catalog_build_is_current(tmp_path)
    with pytest.raises(ValueError, match='inputs changed'):
        promotion.require_catalog_inputs(tmp_path, binding)


def test_catalog_receipt_binds_the_raw_labels_the_line_gate_compared(tmp_path, monkeypatch):
    # A catalog gated against one set of raw DSLD labels is not current for
    # another: the raw-to-final comparison must rerun (ADR-0005).
    raw = tmp_path / 'raw'
    (raw / 'Olly').mkdir(parents=True)
    label = raw / 'Olly' / '1.json'
    label.write_text('{"fullName": "A"}')
    monkeypatch.setenv('PHARMAGUIDE_DATASET_ROOT', str(raw))
    repo = tmp_path / 'repo'
    binding = _assembly(repo)
    promotion.record_catalog_build(repo, binding)
    assert promotion.catalog_build_is_current(repo)
    os.utime(label, None)
    assert promotion.catalog_build_is_current(repo)
    label.write_text('{"fullName": "B"}')
    assert not promotion.catalog_build_is_current(repo)
    label.write_text('{"fullName": "A"}')
    assert promotion.catalog_build_is_current(repo)
    (raw / 'Olly' / '2.json').write_text('{}')
    assert not promotion.catalog_build_is_current(repo)
    (raw / 'Olly' / '2.json').unlink()
    assert promotion.catalog_build_is_current(repo)
    monkeypatch.setenv('PHARMAGUIDE_DATASET_ROOT', str(tmp_path / 'absent'))
    assert not promotion.catalog_build_is_current(repo)


@pytest.mark.parametrize('relative', [
    'scripts/test.sh',
    'scripts/tests/test_release_gate.py',
    'scripts/tests/fixtures/release_case.json',
    'scripts/test_profiles.py',
    'scripts/test_lock.py',
    'scripts/test_shard_plan.py',
    'scripts/ci_skip_guard.py',
])
def test_catalog_receipt_ignores_test_only_changes(tmp_path, relative):
    binding = _assembly(tmp_path)
    promotion.record_catalog_build(tmp_path, binding)
    path = tmp_path / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('test infrastructure changed')
    assert promotion.catalog_build_is_current(tmp_path)
    promotion.require_catalog_inputs(tmp_path, binding)
