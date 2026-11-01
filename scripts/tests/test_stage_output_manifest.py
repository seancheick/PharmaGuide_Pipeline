"""Fresh-run output ownership regressions (review finding C8)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from batch_processor import REPO_ROOT, BatchProcessor
from pipeline_freshness import CODE_FINGERPRINT_KEY, stage_input_fingerprints
from stage_manifest import (
    StageManifestError,
    select_stage_input_files,
    write_stage_manifest,
)


def _config(tmp_path: Path) -> dict:
    return {
        "processing": {"batch_size": 10, "max_workers": 1},
        "paths": {
            "output_directory": str(tmp_path / "out"),
            "log_directory": str(tmp_path / "logs"),
        },
        "validation": {"verify_output": False, "check_input_integrity": False},
        "output_format": {},
        "ui": {"show_progress_bar": False},
    }


def test_fresh_run_quarantines_stale_numbered_outputs(tmp_path: Path) -> None:
    processor = BatchProcessor(_config(tmp_path))
    stale_cleaned = processor.output_dir / "cleaned" / "cleaned_batch_99.json"
    stale_review = processor.output_dir / "needs_review" / "needs_review_batch_99.json"
    stale_cleaned.write_text("[]", encoding="utf-8")
    stale_review.write_text("[]", encoding="utf-8")

    moved = processor._prepare_fresh_run_outputs()

    assert not stale_cleaned.exists()
    assert not stale_review.exists()
    assert len(moved) == 2
    assert all(path.exists() for path in moved)
    assert all("stale_outputs" in path.parts for path in moved)


def test_stage_manifest_lists_only_current_materialized_outputs(tmp_path: Path) -> None:
    processor = BatchProcessor(_config(tmp_path))
    current = processor.output_dir / "cleaned" / "cleaned_batch_1.json"
    current.write_text(json.dumps([{"id": "1"}]), encoding="utf-8")

    manifest_path = processor._write_stage_manifest({"processing_complete": True})
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["stage"] == "clean"
    assert manifest["processing_complete"] is True
    assert manifest["owned_files"] == ["cleaned_batch_1.json"]
    assert manifest_path.name == ".stage_manifest.json"
    assert manifest["input_fingerprints"] == stage_input_fingerprints(REPO_ROOT, "clean")


def test_clean_manifest_refuses_inputs_that_changed_during_the_run(
    tmp_path: Path,
) -> None:
    processor = BatchProcessor(_config(tmp_path))
    (processor.output_dir / "cleaned" / "cleaned_batch_1.json").write_text("[]", encoding="utf-8")
    started = processor._clean_stage_inputs()
    processor._stage_inputs = dict(started, **{CODE_FINGERPRINT_KEY: "0" * 64})

    with pytest.raises(StageManifestError, match="changed during the run"):
        processor._write_stage_manifest({"processing_complete": True})

    assert not (processor.output_dir / "cleaned" / ".stage_manifest.json").exists()


def test_resume_checksum_covers_cleaning_code_and_reference_data(
    tmp_path: Path,
) -> None:
    processor = BatchProcessor(_config(tmp_path))
    before = processor._get_config_checksum()

    processor._stage_inputs = dict(processor._clean_stage_inputs(), **{CODE_FINGERPRINT_KEY: "0" * 64})

    assert processor._get_config_checksum() != before


def test_successful_stage_manifest_discards_completed_run_quarantine(
    tmp_path: Path,
) -> None:
    stage_dir = tmp_path / "enriched"
    stage_dir.mkdir()
    current = stage_dir / "enriched_batch_1.json"
    current.write_text(json.dumps([{"id": "current"}]), encoding="utf-8")
    stale = (
        stage_dir
        / "quarantine"
        / "stale_outputs"
        / "20260806T000000000000Z"
        / "enriched_batch_1.json"
    )
    stale.parent.mkdir(parents=True)
    stale.write_text(json.dumps([{"id": "previous"}]), encoding="utf-8")

    write_stage_manifest(stage_dir, "enrich", [current])

    assert current.exists()
    assert not (stage_dir / "quarantine" / "stale_outputs").exists()


def test_successful_clean_manifest_discards_parent_run_quarantine(
    tmp_path: Path,
) -> None:
    processor = BatchProcessor(_config(tmp_path))
    current = processor.output_dir / "cleaned" / "cleaned_batch_1.json"
    current.write_text(json.dumps([{"id": "current"}]), encoding="utf-8")
    stale = (
        processor.output_dir
        / "quarantine"
        / "stale_outputs"
        / "20260806T000000000000Z"
        / "cleaned"
        / "cleaned_batch_1.json"
    )
    stale.parent.mkdir(parents=True)
    stale.write_text(json.dumps([{"id": "previous"}]), encoding="utf-8")

    processor._write_stage_manifest({"processing_complete": True})

    assert current.exists()
    assert not (processor.output_dir / "quarantine" / "stale_outputs").exists()


def test_incomplete_stage_manifest_retains_rollback_quarantine(
    tmp_path: Path,
) -> None:
    stage_dir = tmp_path / "scored"
    stage_dir.mkdir()
    current = stage_dir / "scored_batch_1.json"
    current.write_text(json.dumps([{"id": "partial"}]), encoding="utf-8")
    stale = (
        stage_dir
        / "quarantine"
        / "stale_outputs"
        / "20260806T000000000000Z"
        / "scored_batch_1.json"
    )
    stale.parent.mkdir(parents=True)
    stale.write_text(json.dumps([{"id": "previous"}]), encoding="utf-8")

    write_stage_manifest(
        stage_dir,
        "score",
        [current],
        processing_complete=False,
    )

    assert stale.exists()


def test_manifest_is_the_only_authority_for_stage_inputs(tmp_path: Path) -> None:
    stage_dir = tmp_path / "enriched"
    stage_dir.mkdir()
    owned = stage_dir / "enriched_batch_1.json"
    stale = stage_dir / "enriched_batch_99.json"
    owned.write_text(json.dumps([{"id": "1"}]), encoding="utf-8")
    stale.write_text(json.dumps([{"id": "99"}]), encoding="utf-8")
    write_stage_manifest(stage_dir, "enrich", [owned])

    try:
        select_stage_input_files(stage_dir, "enrich", require_manifest=True)
    except StageManifestError as exc:
        assert "unowned" in str(exc).lower()
    else:
        raise AssertionError("stale unowned JSON must not be silently consumed")


def test_manifest_content_hash_is_verified(tmp_path: Path) -> None:
    stage_dir = tmp_path / "enriched"
    stage_dir.mkdir()
    owned = stage_dir / "enriched_batch_1.json"
    owned.write_text(json.dumps([{"id": "1"}]), encoding="utf-8")
    write_stage_manifest(stage_dir, "enrich", [owned])
    owned.write_text(json.dumps([{"id": "changed"}]), encoding="utf-8")

    try:
        select_stage_input_files(stage_dir, "enrich", require_manifest=True)
    except StageManifestError as exc:
        assert "checksum" in str(exc).lower()
    else:
        raise AssertionError("changed content must invalidate stage ownership")


def test_stage_manifest_can_be_correlated_to_pipeline_run(tmp_path: Path) -> None:
    stage_dir = tmp_path / "enriched"
    stage_dir.mkdir()
    owned = stage_dir / "enriched_batch_1.json"
    owned.write_text("[]", encoding="utf-8")

    manifest_path = write_stage_manifest(
        stage_dir, "enrich", [owned], run_id="review-run-1"
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["run_id"] == "review-run-1"


def test_required_manifest_cannot_be_missing(tmp_path: Path) -> None:
    stage_dir = tmp_path / "enriched"
    stage_dir.mkdir()
    (stage_dir / "enriched_batch_1.json").write_text("[]", encoding="utf-8")

    try:
        select_stage_input_files(stage_dir, "enrich", require_manifest=True)
    except StageManifestError as exc:
        assert "missing" in str(exc).lower()
    else:
        raise AssertionError("strict stage input must require a manifest")


def test_clean_manifest_rejects_same_timestamp_raw_content_change(tmp_path):
    import os
    processor = BatchProcessor(_config(tmp_path))
    raw = tmp_path / 'raw.json'
    raw.write_text('{"id":"1"}')
    processor._source_files = (raw,)
    processor._clean_stage_inputs()
    stamp = raw.stat()
    raw.write_text('{"id":"2"}')
    os.utime(raw, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    (processor.output_dir / 'cleaned/cleaned_batch_1.json').write_text('[]')
    with pytest.raises(StageManifestError, match='source content changed'):
        processor._write_stage_manifest({'processing_complete': True})


@pytest.mark.parametrize('change', ['add', 'remove'])
def test_clean_manifest_rejects_raw_inventory_change(tmp_path, change):
    processor = BatchProcessor(_config(tmp_path))
    raw = tmp_path / 'raw'
    raw.mkdir()
    one = raw / '1.json'
    one.write_text('{"id":"1"}')
    processor._source_files = (one,)
    processor._source_directory = raw
    processor._source_inventory = tuple(processor.get_input_files(str(raw)))
    processor._clean_stage_inputs()
    (processor.output_dir / 'cleaned/cleaned_batch_1.json').write_text('[]')
    if change == 'add':
        (raw / '2.json').write_text('{"id":"2"}')
    else:
        one.unlink()
    with pytest.raises(StageManifestError, match='source inventory changed'):
        processor._write_stage_manifest({'processing_complete': True})


def test_clean_subset_binding_does_not_claim_unprocessed_raw_file(tmp_path):
    from pipeline_freshness import DATA_FINGERPRINT_KEY, stage_data_fingerprint
    processor = BatchProcessor(_config(tmp_path))
    raw = tmp_path / 'raw'
    raw.mkdir()
    for name in ('1', '2'):
        (raw / (name + '.json')).write_text(json.dumps({'id': name}))
    processor._source_files = (raw / '1.json',)
    processor._source_directory = raw
    processor._source_inventory = tuple(processor.get_input_files(str(raw)))
    processor._clean_stage_inputs()
    (processor.output_dir / 'cleaned/cleaned_batch_1.json').write_text('[]')
    path = processor._write_stage_manifest({'processing_complete': True})
    binding = json.loads(path.read_text())['input_fingerprints'][DATA_FINGERPRINT_KEY]
    assert binding == stage_data_fingerprint([raw / '1.json'])
    assert binding != stage_data_fingerprint(processor.get_input_files(str(raw)))


def test_resume_stage_requires_output_and_input_content_proof(tmp_path, monkeypatch):
    import pipeline_freshness as freshness
    from stage_manifest import write_stage_manifest
    raw = tmp_path / 'raw'
    raw.mkdir()
    source = raw / 'label.json'
    source.write_text('{"id": 1}')
    output = tmp_path / 'cleaned'
    output.mkdir()
    product = output / 'cleaned_batch_1.json'
    product.write_text('[{"id": 1}]')
    stamps = {freshness.REFERENCE_FINGERPRINT_KEY: 'a' * 64,
              freshness.CODE_FINGERPRINT_KEY: 'b' * 64}
    monkeypatch.setattr(freshness, 'stage_input_fingerprints', lambda *args: stamps)
    write_stage_manifest(output, 'clean', [product], input_fingerprints={
        **stamps, freshness.DATA_FINGERPRINT_KEY: freshness.stage_data_fingerprint([source])})
    assert freshness.reusable_stage_issue(tmp_path, output, 'clean', raw) is None
    source.write_text('{"id": 2}')
    assert 'input' in freshness.reusable_stage_issue(tmp_path, output, 'clean', raw)
    source.write_text('{"id": 1}')
    product.write_text('[]')
    assert freshness.reusable_stage_issue(tmp_path, output, 'clean', raw)


def test_resume_plan_rebuilds_from_first_invalid_stage(tmp_path, monkeypatch):
    import pipeline_freshness as freshness
    seen = []
    def issue(repo, directory, stage, inputs):
        seen.append(stage)
        return 'changed input' if stage == 'enrich' else None
    monkeypatch.setattr(freshness, 'reusable_stage_issue', issue)
    stages, reason = freshness.dataset_resume_plan(tmp_path, tmp_path / 'raw', tmp_path / 'output_Brand')
    assert stages == ['enrich', 'score']
    assert reason == 'changed input'
    assert seen == ['clean', 'enrich']
    monkeypatch.setattr(freshness, 'reusable_stage_issue', lambda *args: None)
    assert freshness.dataset_resume_plan(tmp_path, tmp_path / 'raw', tmp_path / 'output_Brand')[0] == []


@pytest.mark.parametrize('change', ['missing', 'incomplete', 'extra_output', 'code', 'reference', 'added_raw', 'deleted_raw'])
def test_resume_rejects_unproven_stage(tmp_path, monkeypatch, change):
    import pipeline_freshness as freshness
    from stage_manifest import write_stage_manifest
    raw = tmp_path / 'raw'
    raw.mkdir()
    source = raw / 'one.json'
    source.write_text('{}')
    output = tmp_path / 'cleaned'
    output.mkdir()
    product = output / 'cleaned_batch_1.json'
    product.write_text('[{}]')
    stamps = {freshness.REFERENCE_FINGERPRINT_KEY: 'a' * 64,
              freshness.CODE_FINGERPRINT_KEY: 'b' * 64}
    monkeypatch.setattr(freshness, 'stage_input_fingerprints', lambda *args: stamps)
    manifest = write_stage_manifest(output, 'clean', [product], input_fingerprints={
        **stamps, freshness.DATA_FINGERPRINT_KEY: freshness.stage_data_fingerprint([source])})
    if change == 'missing':
        manifest.unlink()
    elif change == 'incomplete':
        data = json.loads(manifest.read_text())
        data['processing_complete'] = False
        manifest.write_text(json.dumps(data))
    elif change == 'extra_output':
        (output / 'unexpected.json').write_text('[]')
    elif change in ('code', 'reference'):
        key = freshness.CODE_FINGERPRINT_KEY if change == 'code' else freshness.REFERENCE_FINGERPRINT_KEY
        stamps[key] = 'c' * 64
    elif change == 'added_raw':
        (raw / 'two.json').write_text('{}')
    else:
        source.unlink()
    assert freshness.reusable_stage_issue(tmp_path, output, 'clean', raw)


def test_batch_source_fingerprint_ignores_docs_but_detects_runtime_edits(tmp_path):
    import pipeline_freshness as freshness
    (tmp_path / 'scripts/data').mkdir(parents=True)
    runtime = tmp_path / 'scripts/worker.py'
    runtime.write_text('VALUE = 1\n')
    first = freshness.batch_source_fingerprint(tmp_path)
    (tmp_path / 'README.md').write_text('documentation')
    (tmp_path / 'scripts/tests').mkdir()
    (tmp_path / 'scripts/tests/test_probe.py').write_text('assert True\n')
    assert freshness.batch_source_fingerprint(tmp_path) == first
    runtime.write_text('VALUE = 2\n')
    assert freshness.batch_source_fingerprint(tmp_path) != first


def test_verified_output_digests_can_bind_upstream_without_second_read(tmp_path, monkeypatch):
    import pipeline_freshness as freshness
    from stage_manifest import write_stage_manifest, select_stage_input_files
    output = tmp_path / 'cleaned'
    output.mkdir()
    product = output / 'cleaned_batch_1.json'
    product.write_text('[{}]')
    write_stage_manifest(output, 'clean', [product])
    expected = freshness.stage_data_fingerprint([product])
    hashes = {}
    files = select_stage_input_files(output, 'clean', require_manifest=True, content_hashes=hashes)
    def unexpected_read(path):
        raise AssertionError('verified file bytes were read twice')
    monkeypatch.setattr(freshness, '_bytes_digest', unexpected_read)
    assert freshness.stage_data_fingerprint(files, content_hashes=hashes) == expected


def test_resume_invalidates_only_the_changed_brand(tmp_path, monkeypatch):
    import pipeline_freshness as freshness
    from stage_manifest import write_stage_manifest
    stamps = {freshness.REFERENCE_FINGERPRINT_KEY: 'a' * 64,
              freshness.CODE_FINGERPRINT_KEY: 'b' * 64}
    monkeypatch.setattr(freshness, 'stage_input_fingerprints', lambda *args: stamps)
    for brand in ['A', 'B']:
        raw = tmp_path / brand
        raw.mkdir()
        (raw / 'one.json').write_text('{}')
        prefix = tmp_path / ('output_' + brand)
        upstream = raw
        for stage, directory in [('clean', prefix / 'cleaned'),
                                 ('enrich', Path(str(prefix) + '_enriched') / 'enriched'),
                                 ('score', Path(str(prefix) + '_scored') / 'scored')]:
            directory.mkdir(parents=True)
            product = directory / 'batch.json'
            product.write_text('[{}]')
            write_stage_manifest(directory, stage, [product], input_fingerprints={
                **stamps, freshness.DATA_FINGERPRINT_KEY: freshness.stage_data_fingerprint(freshness.stage_data_files(upstream))})
            upstream = directory
        assert freshness.dataset_resume_plan(tmp_path, raw, prefix)[0] == []
    (tmp_path / 'A/one.json').write_text('{"changed":true}')
    assert freshness.dataset_resume_plan(tmp_path, tmp_path / 'A', tmp_path / 'output_A')[0] == ['clean', 'enrich', 'score']
    assert freshness.dataset_resume_plan(tmp_path, tmp_path / 'B', tmp_path / 'output_B')[0] == []


def test_stale_source_selects_rebuild_without_reading_large_outputs(tmp_path, monkeypatch):
    import pipeline_freshness as freshness
    import stage_manifest
    output = tmp_path / 'cleaned'
    output.mkdir()
    product = output / 'batch.json'
    product.write_text('[{}]')
    stage_manifest.write_stage_manifest(output, 'clean', [product], input_fingerprints={
        freshness.REFERENCE_FINGERPRINT_KEY: 'a' * 64,
        freshness.CODE_FINGERPRINT_KEY: 'b' * 64})
    monkeypatch.setattr(freshness, 'stage_input_fingerprints', lambda *args: {
        freshness.REFERENCE_FINGERPRINT_KEY: 'c' * 64,
        freshness.CODE_FINGERPRINT_KEY: 'b' * 64})
    def no_output_read(path):
        raise AssertionError('stale outputs should not be read before choosing rebuild')
    monkeypatch.setattr(stage_manifest, '_sha256', no_output_read)
    assert 'reference_data' in freshness.reusable_stage_issue(tmp_path, output, 'clean', tmp_path)


def test_source_freeze_binds_external_environment_symlink_without_exposing_values(tmp_path):
    import pipeline_freshness as freshness
    root = tmp_path / 'repo'
    (root / 'scripts/data').mkdir(parents=True)
    env = tmp_path / 'private.env'
    env.write_text('SECRET=first\n')
    (root / '.env').symlink_to(env)
    first = freshness.batch_source_fingerprint(root)
    env.write_text('SECRET=second\n')
    assert freshness.batch_source_fingerprint(root) != first
    assert len(first) == 64
