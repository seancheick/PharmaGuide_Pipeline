"""Fresh-run output ownership regressions (review finding C8)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from batch_processor import BatchProcessor


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
