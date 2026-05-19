"""Tests for the scored-output delta report utility."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from api_audit.score_delta_report import build_delta_rows, write_reports  # noqa: E402


def _write_batch(path: Path, products: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(products) + "\n", encoding="utf-8")


def test_build_delta_rows_reads_scored_batches_and_extracts_b4a(tmp_path: Path) -> None:
    before = tmp_path / "before" / "scored"
    after = tmp_path / "after" / "scored"
    _write_batch(
        before / "batch.json",
        [
            {
                "dsld_id": "1",
                "brand_name": "Brand",
                "product_name": "Product A",
                "score_100_equivalent": 70.0,
                "breakdown": {"B": {"B4a": 5.0}},
            },
            {
                "dsld_id": "2",
                "brand_name": "Brand",
                "product_name": "Removed Product",
                "score_100_equivalent": 60.0,
                "breakdown": {"B": {"B4a": 0.0}},
            },
        ],
    )
    _write_batch(
        after / "batch.json",
        [
            {
                "dsld_id": "1",
                "brand_name": "Brand",
                "product_name": "Product A",
                "score_100_equivalent": 72.5,
                "breakdown": {"B": {"B4a": 8.0}},
            },
            {
                "dsld_id": "3",
                "brand_name": "Brand",
                "product_name": "Added Product",
                "score_100_equivalent": 55.0,
                "breakdown": {"B": {"B4a": 2.0}},
            },
        ],
    )

    rows = build_delta_rows(before, after)
    by_id = {row["dsld_id"]: row for row in rows}

    assert by_id["1"]["score_delta"] == 2.5
    assert by_id["1"]["b4a_delta"] == 3.0
    assert by_id["2"]["status"] == "removed"
    assert by_id["3"]["status"] == "added"


def test_build_delta_rows_reads_final_export_detail_blobs(tmp_path: Path) -> None:
    before = tmp_path / "before" / "detail_blobs"
    after = tmp_path / "after" / "detail_blobs"
    before.mkdir(parents=True)
    after.mkdir(parents=True)
    (before / "10.json").write_text(
        json.dumps(
            {
                "dsld_id": "10",
                "brand_name": "Brand",
                "product_name": "Blob Product",
                "score_display_100_equivalent": 80.0,
                "section_breakdown": {"safety_purity": {"sub": {"B4a": 10.0}}},
            }
        ),
        encoding="utf-8",
    )
    (after / "10.json").write_text(
        json.dumps(
            {
                "dsld_id": "10",
                "brand_name": "Brand",
                "product_name": "Blob Product",
                "score_display_100_equivalent": 78.0,
                "section_breakdown": {"safety_purity": {"sub": {"B4a": 8.0}}},
            }
        ),
        encoding="utf-8",
    )

    rows = build_delta_rows(tmp_path / "before", tmp_path / "after")

    assert rows[0]["dsld_id"] == "10"
    assert rows[0]["score_delta"] == -2.0
    assert rows[0]["b4a_delta"] == -2.0


def test_write_reports_emits_json_csv_and_markdown(tmp_path: Path) -> None:
    rows = [
        {
            "dsld_id": "1",
            "status": "changed",
            "brand": "Brand",
            "product": "Product",
            "score_before": 70.0,
            "score_after": 72.0,
            "score_delta": 2.0,
            "b4a_before": 5.0,
            "b4a_after": 8.0,
            "b4a_delta": 3.0,
        }
    ]

    paths = write_reports(rows, tmp_path, "unit_delta")

    assert paths["json"].exists()
    assert paths["csv"].exists()
    assert paths["md"].exists()
    assert "Product" in paths["md"].read_text(encoding="utf-8")
