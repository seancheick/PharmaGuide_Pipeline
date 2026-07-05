"""
P1-6 regression — input-validation failures must count toward the success-rate
denominator.

Files that fail ``validate_input_file`` (malformed JSON, missing ``id``, no
ingredient data) are appended to ``errors`` and ``continue``d BEFORE
``processed_files.append`` — so they never enter ``processed`` and never enter
the ``success_rate = cleaned / total_processed`` denominator. Result: 1,000
inputs with 100 malformed can clean 900/900 = "100% success" and exit 0 while
10% of the catalog was silently dropped. The min_success_rate gate that exists
to catch exactly this can never fire.

Fix: process_batch reports ``input_validation_failures`` in its summary, and the
final summary counts them into the attempted-files denominator.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.dirname(__file__))

from batch_processor import BatchProcessor
from test_batch_processor_regressions import _make_config


def _cfg(tmp_path):
    cfg = _make_config(tmp_path)
    cfg["validation"]["check_input_integrity"] = True
    return cfg


def test_process_batch_counts_input_validation_failures(tmp_path, monkeypatch):
    processor = BatchProcessor(_cfg(tmp_path))
    monkeypatch.setattr(processor, "_write_quarantine_file", lambda *a, **kw: None)

    bad1 = tmp_path / "bad1.json"
    bad1.write_text('{"ingredientRows": []}', encoding="utf-8")  # missing required 'id'
    bad2 = tmp_path / "bad2.json"
    bad2.write_text("not valid json", encoding="utf-8")          # malformed JSON

    result = processor.process_batch(0, [bad1, bad2])

    assert result["summary"].get("input_validation_failures") == 2, (
        f"input-validation failures not counted in batch summary: {result['summary']}"
    )
    assert result["summary"]["processed"] == 0


def test_final_summary_counts_validation_failures_in_denominator(tmp_path):
    processor = BatchProcessor(_cfg(tmp_path))
    batch_results = [
        {
            "summary": {
                "processed": 9,
                "cleaned": 9,
                "needs_review": 0,
                "incomplete": 0,
                "errors": 1,
                "input_validation_failures": 1,
            }
        }
    ]
    summary = processor._generate_final_summary(batch_results, 1.0)

    # 9 cleaned of 10 attempted (9 processed + 1 validation failure) = 90%, not 100%.
    assert summary["total_files"] == 10, (
        f"validation failures excluded from total_files: {summary['total_files']}"
    )
    assert summary["success_rate"] == 90.0, (
        f"success_rate ignores validation failures: {summary['success_rate']}"
    )
