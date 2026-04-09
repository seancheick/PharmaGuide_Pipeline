import json
import sys
from pathlib import Path
from unittest.mock import MagicMock


mock_st = MagicMock()


def passthrough(func=None, **kwargs):
    if func is not None:
        return func
    return lambda f: f


mock_st.cache_data = passthrough
mock_st.cache_resource = passthrough
sys.modules["streamlit"] = mock_st

from scripts.dashboard.config import DashboardConfig
from scripts.dashboard.data_loader import load_dashboard_data


def test_loader_prefers_fresh_pipeline_artifacts_over_old_batch_log(tmp_path: Path):
    scan_dir = tmp_path / "scan"
    build_root = tmp_path / "build"
    logs_dir = scan_dir / "logs"
    output_dir = scan_dir / "output_Test"
    reports_dir = output_dir / "reports"
    cleaned_dir = output_dir / "cleaned"

    logs_dir.mkdir(parents=True)
    reports_dir.mkdir(parents=True)
    cleaned_dir.mkdir(parents=True)
    build_root.mkdir(parents=True)

    (build_root / "export_manifest.json").write_text('{"generated_at":"2026-04-09T12:00:00Z","db_version":"test"}')

    (logs_dir / "processing_state.json").write_text(
        json.dumps(
            {
                "started": "2026-04-09T20:10:21Z",
                "last_updated": "2026-04-09T20:11:01Z",
                "processed_files": 10,
                "total_files": 10,
                "errors": [],
                "can_resume": True,
            }
        )
    )
    (logs_dir / "batch_4_log.txt").write_text(
        "\n".join(
            [
                "2026-04-09 11:58:40,287 - INFO - Started: 2026-04-09 11:58:40",
                "2026-04-09 11:58:41,246 - INFO - Ended: 2026-04-09 11:58:41",
                "2026-04-09 11:58:41,246 - INFO - Summary: {'batch_num': 4, 'processed': 215, 'cleaned': 0, 'errors': 215, 'processing_time': 0.9}",
            ]
        )
    )

    (cleaned_dir / "sample.json").write_text("{}")
    (reports_dir / "enrichment_summary_20260409_204815.json").write_text("{}")
    (reports_dir / "scoring_summary_20260409_204822.json").write_text("{}")
    (reports_dir / "processing_summary.txt").write_text(
        "\n".join(
            [
                "Generated: 2026-04-09 16:11:02",
                "Batch Details:",
                "  Batch 4: 215 cleaned, 0 review, 0 incomplete, 0 errors (7.1s)",
            ]
        )
    )

    config = DashboardConfig(scan_dir=scan_dir.resolve(), build_root=build_root.resolve())
    data = load_dashboard_data(config)

    assert data.latest_batch_at is not None
    assert data.latest_batch_at.isoformat() == "2026-04-09T20:11:02+00:00"
    assert data.latest_scored_at is None
    assert data.latest_batch_summary is not None
    assert data.latest_batch_summary["summary"]["errors"] == 215
