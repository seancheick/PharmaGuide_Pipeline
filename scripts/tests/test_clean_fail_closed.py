"""Clean-stage side outputs and reference loading fail closed.

2026-10-19: a quarantine or unmapped-report write failure only logged a
warning, the unmapped report fell back to a different schema, and a missing or
corrupt non-critical reference file (label corrections, context routing
overrides, other_ingredients...) became an empty table, all with the stage
still marked complete.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import enhanced_normalizer
from batch_processor import BatchProcessor, ProcessingResult, StructuredError
from enhanced_normalizer import EnhancedDSLDNormalizer, EnhancedIngredientMatcher


def _make_config(tmp_path):
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


def _block_directory(path):
    """Replace a directory with a file so any write inside it fails."""
    path.rmdir()
    path.write_text("not a directory", encoding="utf-8")


def test_quarantine_write_failure_is_recorded(tmp_path):
    processor = BatchProcessor(_make_config(tmp_path))
    _block_directory(processor.output_dir / "errors")

    processor._write_quarantine_file(
        "123.json",
        StructuredError(
            file_path="123.json", exception_type="ProcessingError",
            message="boom", stage="clean", traceback=None,
        ),
    )

    assert processor.report_write_failures == [
        str(processor.output_dir / "errors" / "123_error.json")
    ]


def test_validation_quarantine_open_failure_is_recorded(tmp_path, monkeypatch):
    processor = BatchProcessor(_make_config(tmp_path))
    real_open = open

    def failing_open(path, *args, **kwargs):
        if str(path).endswith("_validation.json"):
            raise OSError("disk full")
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr("builtins.open", failing_open)
    processor._write_validation_quarantine(
        ProcessingResult(
            success=True, status="needs_review", data={"id": 7},
            file_path="7.json", validation_errors=["bad"],
        )
    )

    assert processor.report_write_failures == [
        str(processor.output_dir / "quarantine" / "7_validation.json")
    ]


def test_unmapped_report_failure_is_recorded_without_a_fallback_file(tmp_path, monkeypatch):
    processor = BatchProcessor(_make_config(tmp_path))
    processor.global_unmapped.update({"Mystery Root": 2})

    def fail(self, processed_count_override=None):
        raise OSError("disk full")

    monkeypatch.setattr(EnhancedDSLDNormalizer, "process_and_save_unmapped_tracking", fail)
    processor._save_unmapped_ingredients(processed_count_override=1)

    assert processor.report_write_failures == [str(processor.output_dir / "unmapped")]
    assert not (processor.output_dir / "unmapped" / "unmapped_ingredients.json").exists()


def test_report_write_failure_marks_the_stage_incomplete(tmp_path, monkeypatch):
    processor = BatchProcessor(_make_config(tmp_path))
    raw = tmp_path / "001.json"
    raw.write_text(json.dumps({"id": 1}), encoding="utf-8")

    def fake_process_batch(batch_num, batch_files, output_batch_num=None):
        processor.report_write_failures.append("errors/001_error.json")
        return {
            "summary": {
                "processed": 1, "cleaned": 1, "needs_review": 0,
                "incomplete": 0, "errors": 0, "output_write_failures": 0,
            },
            "errors": [],
            "unmapped_count": 0,
            "processed_files": [str(raw)],
            "write_success": True,
        }

    manifests = []
    monkeypatch.setattr(processor, "process_batch", fake_process_batch)
    monkeypatch.setattr(processor, "_save_unmapped_ingredients", lambda *a, **kw: None)
    monkeypatch.setattr(processor, "_generate_processing_report", lambda summary, results: None)
    monkeypatch.setattr(processor, "_generate_detailed_review_report", lambda: None)
    monkeypatch.setattr(processor, "_write_stage_manifest", lambda summary: manifests.append(summary))

    summary = processor.process_all_files([raw], resume=False)

    assert summary["processing_complete"] is False
    assert summary["report_write_failures"] == 1
    assert manifests[0]["processing_complete"] is False


def test_clean_run_without_report_failures_stays_complete(tmp_path, monkeypatch):
    processor = BatchProcessor(_make_config(tmp_path))
    raw = tmp_path / "001.json"
    raw.write_text(json.dumps({"id": 1}), encoding="utf-8")
    monkeypatch.setattr(processor, "process_batch", lambda batch_num, batch_files, output_batch_num=None: {
        "summary": {
            "processed": 1, "cleaned": 1, "needs_review": 0,
            "incomplete": 0, "errors": 0, "output_write_failures": 0,
        },
        "errors": [], "unmapped_count": 0,
        "processed_files": [str(raw)], "write_success": True,
    })
    monkeypatch.setattr(processor, "_save_unmapped_ingredients", lambda *a, **kw: None)
    monkeypatch.setattr(processor, "_generate_processing_report", lambda summary, results: None)
    monkeypatch.setattr(processor, "_generate_detailed_review_report", lambda: None)
    monkeypatch.setattr(processor, "_write_stage_manifest", lambda summary: None)

    summary = processor.process_all_files([raw], resume=False)

    assert summary["processing_complete"] is True
    assert "report_write_failures" not in summary


@pytest.mark.parametrize("constant", [
    "PRODUCT_CONTEXT_CANONICAL_OVERRIDES",
    "PRODUCT_LABEL_CORRECTIONS",
    "OTHER_INGREDIENTS",
])
@pytest.mark.parametrize("content", [None, "{not json"])
def test_unloadable_reference_file_stops_the_cleaner(tmp_path, monkeypatch, constant, content):
    path = tmp_path / getattr(enhanced_normalizer, constant).name
    if content is not None:
        path.write_text(content, encoding="utf-8")
    monkeypatch.setattr(enhanced_normalizer, constant, path)

    with pytest.raises(RuntimeError, match="Failed to load reference file"):
        EnhancedDSLDNormalizer()


def test_unconvertible_field_raises_instead_of_blanking():
    class Unprintable:
        def __str__(self):
            raise ValueError("no text form")

    with pytest.raises(ValueError, match="no text form"):
        EnhancedIngredientMatcher().validate_input(Unprintable(), "ingredient_name")
