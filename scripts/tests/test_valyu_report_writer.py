import os
import sys
from pathlib import Path
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api_audit.valyu_report_types import normalize_signal_row
from api_audit.valyu_report_writer import build_report_paths, render_summary, write_reports


def test_normalize_signal_row_enforces_review_only_flags():
    row = normalize_signal_row(
        {
            "domain": "clinical_refresh",
            "entity_name": "Meriva Curcumin Phytosome",
            "signal_type": "possible_upgrade",
        }
    )

    assert row["requires_human_review"] is True
    assert row["auto_apply_allowed"] is False
    assert row["signal_type"] == "possible_upgrade"
    assert row["candidate_sources"] == []
    assert row["candidate_references"] == []
    assert row["supporting_summary"] == ""


def test_build_report_paths_creates_expected_filenames(tmp_path):
    paths = build_report_paths(timestamp="20260410T120000Z", output_dir=tmp_path)

    assert paths["raw_search_report"].name == "20260410T120000Z-raw-search-report.json"
    assert paths["review_queue"].name == "20260410T120000Z-review-queue.json"
    assert paths["summary"].name == "20260410T120000Z-summary.md"


def test_write_reports_writes_json_and_summary(tmp_path):
    metadata = {
        "timestamp": "2026-04-10T12:00:00Z",
        "mode": "clinical-refresh",
        "targets_scanned": 2,
    }
    raw_report = {"metadata": metadata, "raw_results": [{"target": "a"}]}
    review_rows = [
        normalize_signal_row(
            {
                "domain": "clinical_refresh",
                "entity_name": "Meriva Curcumin Phytosome",
                "signal_type": "possible_upgrade",
                "signal_strength": "high",
                "reason": "Recent review found",
            }
        )
    ]

    paths = write_reports(metadata, raw_report, review_rows, timestamp="20260410T120000Z", output_dir=tmp_path)

    raw_saved = json.loads(paths["raw_search_report"].read_text())
    queue_saved = json.loads(paths["review_queue"].read_text())
    summary_saved = paths["summary"].read_text()

    assert raw_saved["metadata"]["mode"] == "clinical-refresh"
    assert queue_saved[0]["entity_name"] == "Meriva Curcumin Phytosome"
    assert "Highest-Priority Findings" in summary_saved
    assert "Meriva Curcumin Phytosome" in summary_saved


def test_render_summary_orders_higher_strength_first():
    metadata = {
        "timestamp": "2026-04-10T12:00:00Z",
        "mode": "all",
        "targets_scanned": 2,
    }
    rows = [
        normalize_signal_row(
            {
                "domain": "clinical_refresh",
                "entity_name": "Lower",
                "signal_type": "possible_upgrade",
                "signal_strength": "low",
                "reason": "later",
            }
        ),
        normalize_signal_row(
            {
                "domain": "clinical_refresh",
                "entity_name": "Higher",
                "signal_type": "possible_upgrade",
                "signal_strength": "high",
                "reason": "first",
            }
        ),
    ]

    summary = render_summary(metadata, rows)
    assert summary.index("Higher") < summary.index("Lower")
