"""Fresh-run output ownership regressions (review finding C8)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from batch_processor import BatchProcessor
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
