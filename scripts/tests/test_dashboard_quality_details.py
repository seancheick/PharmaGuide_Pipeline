import sqlite3
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

from scripts.dashboard.views.quality import build_safety_finding_rows


def test_build_safety_finding_rows_extracts_warning_level_details(tmp_path: Path):
    db_path = tmp_path / "test.db"
    blob_dir = tmp_path / "detail_blobs"
    blob_dir.mkdir()

    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE products_core (
            dsld_id TEXT,
            product_name TEXT,
            brand_name TEXT,
            verdict TEXT,
            score_100_equivalent REAL,
            mapped_coverage REAL,
            has_harmful_additives INTEGER
        )
        """
    )
    conn.execute(
        """
        INSERT INTO products_core (
            dsld_id, product_name, brand_name, verdict, score_100_equivalent, mapped_coverage, has_harmful_additives
        ) VALUES ('15581', 'Restore', 'Thorne', 'SAFE', 48.8, 1.0, 1)
        """
    )
    conn.commit()

    (blob_dir / "15581.json").write_text(
        """
        {
          "warnings": [
            {
              "type": "harmful_additive",
              "severity": "low",
              "title": "Contains Silicon Dioxide (E551)",
              "detail": "Anti-caking additive detail",
              "category": "excipient"
            }
          ]
        }
        """
    )

    rows = build_safety_finding_rows(conn, blob_dir, "has_harmful_additives")

    assert len(rows) == 1
    assert rows[0]["dsld_id"] == "15581"
    assert rows[0]["warning_title"] == "Contains Silicon Dioxide (E551)"
    assert "Anti-caking additive detail" in rows[0]["warning_detail"]

