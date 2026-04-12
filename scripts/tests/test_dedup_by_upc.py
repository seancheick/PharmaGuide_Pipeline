#!/usr/bin/env python3
"""
Tests for UPC-level deduplication in build_final_db.

DSLD registers the same physical product multiple times (different years,
formulation revisions) under distinct dsld_ids but the same UPC barcode.
dedup_by_upc keeps the best row per UPC group and deletes the rest.
"""

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from build_final_db import dedup_by_upc

# Minimal schema — only the columns dedup_by_upc reads/writes.
_MINI_SCHEMA = """
CREATE TABLE products_core (
    dsld_id          TEXT PRIMARY KEY,
    product_name     TEXT NOT NULL,
    brand_name       TEXT,
    upc_sku          TEXT,
    product_status   TEXT,
    score_quality_80 REAL
);
"""


def _make_db(rows):
    """Create an in-memory DB with the given rows.

    Each row is (dsld_id, product_name, brand_name, upc_sku,
                 product_status, score_quality_80).
    Returns (connection, detail_index_dict).
    """
    conn = sqlite3.connect(":memory:")
    conn.executescript(_MINI_SCHEMA)
    c = conn.cursor()
    for row in rows:
        c.execute(
            "INSERT INTO products_core "
            "(dsld_id, product_name, brand_name, upc_sku, "
            " product_status, score_quality_80) "
            "VALUES (?,?,?,?,?,?)",
            row,
        )
    conn.commit()
    # Build a detail_index keyed by dsld_id (mirrors real build flow)
    detail_index = {str(row[0]): {"blob_sha256": f"sha_{row[0]}"} for row in rows}
    return conn, detail_index


def _remaining_ids(conn):
    """Return sorted list of dsld_ids still in products_core."""
    rows = conn.execute(
        "SELECT dsld_id FROM products_core ORDER BY dsld_id"
    ).fetchall()
    return [r[0] for r in rows]


# ── Core behaviour ──────────────────────────────────────────────


class TestDedupByUpc:
    """dedup_by_upc keeps the best row per UPC group."""

    def test_active_beats_discontinued(self):
        """Active product wins over discontinued even with lower score."""
        conn, idx = _make_db([
            ("100", "Vitamin D", "Thorne", "123456", "discontinued", 50.0),
            ("200", "Vitamin D", "Thorne", "123456", "active", 45.0),
        ])
        result = dedup_by_upc(conn, idx)
        assert _remaining_ids(conn) == ["200"]
        assert result["duplicates_removed"] == 1
        assert result["upc_groups_deduped"] == 1
        assert "100" not in idx
        assert "200" in idx

    def test_higher_score_wins_same_status(self):
        """When both are active, the higher score wins."""
        conn, idx = _make_db([
            ("100", "5-MTHF", "Thorne", "693749", "active", 46.0),
            ("200", "5-MTHF", "Thorne", "693749", "active", 48.0),
        ])
        dedup_by_upc(conn, idx)
        assert _remaining_ids(conn) == ["200"]
        assert "100" not in idx

    def test_newest_dsld_id_breaks_tie(self):
        """When status and score are identical, highest dsld_id wins."""
        conn, idx = _make_db([
            ("100", "5-MTHF", "Thorne", "693749", "active", 46.0),
            ("200", "5-MTHF", "Thorne", "693749", "active", 46.0),
            ("300", "5-MTHF", "Thorne", "693749", "active", 46.0),
        ])
        result = dedup_by_upc(conn, idx)
        assert _remaining_ids(conn) == ["300"]
        assert result["duplicates_removed"] == 2
        assert "100" not in idx
        assert "200" not in idx
        assert "300" in idx

    def test_spaces_in_upc_normalised(self):
        """UPCs stored with spaces (DSLD format) are treated as same barcode."""
        conn, idx = _make_db([
            ("100", "Mag", "Thorne", "6 93749 12901 1", "active", 48.0),
            ("200", "Mag", "Thorne", "693749129011", "discontinued", 40.0),
        ])
        dedup_by_upc(conn, idx)
        assert _remaining_ids(conn) == ["100"]

    def test_no_dupes_means_no_changes(self):
        """All unique UPCs — nothing deleted."""
        conn, idx = _make_db([
            ("100", "A", "X", "111", "active", 50.0),
            ("200", "B", "Y", "222", "active", 45.0),
            ("300", "C", "Z", "333", "active", 40.0),
        ])
        result = dedup_by_upc(conn, idx)
        assert _remaining_ids(conn) == ["100", "200", "300"]
        assert result["duplicates_removed"] == 0
        assert result["upc_groups_deduped"] == 0
        assert len(idx) == 3

    def test_null_upc_not_deduped(self):
        """Products with NULL UPC are never grouped together."""
        conn, idx = _make_db([
            ("100", "A", "X", None, "active", 50.0),
            ("200", "B", "Y", None, "active", 45.0),
        ])
        result = dedup_by_upc(conn, idx)
        assert _remaining_ids(conn) == ["100", "200"]
        assert result["duplicates_removed"] == 0

    def test_empty_upc_not_deduped(self):
        """Products with empty-string UPC are never grouped."""
        conn, idx = _make_db([
            ("100", "A", "X", "", "active", 50.0),
            ("200", "B", "Y", "", "active", 45.0),
            ("300", "C", "Z", "  ", "active", 40.0),
        ])
        result = dedup_by_upc(conn, idx)
        assert _remaining_ids(conn) == ["100", "200", "300"]
        assert result["duplicates_removed"] == 0

    def test_multiple_upc_groups(self):
        """Dedup works across independent UPC groups simultaneously."""
        conn, idx = _make_db([
            # Group 1: UPC 111
            ("100", "A", "X", "111", "active", 50.0),
            ("101", "A", "X", "111", "discontinued", 48.0),
            # Group 2: UPC 222
            ("200", "B", "Y", "222", "discontinued", 45.0),
            ("201", "B", "Y", "222", "active", 40.0),
            # Unique: UPC 333
            ("300", "C", "Z", "333", "active", 60.0),
        ])
        result = dedup_by_upc(conn, idx)
        remaining = _remaining_ids(conn)
        assert "100" in remaining   # group 1 winner: active + highest score
        assert "201" in remaining   # group 2 winner: active beats higher-score discontinued
        assert "300" in remaining   # unique — untouched
        assert len(remaining) == 3
        assert result["duplicates_removed"] == 2
        assert result["upc_groups_deduped"] == 2

    def test_seven_dupes_like_real_thorne(self):
        """Simulates the real Thorne 5-MTHF case: 7 entries, same UPC."""
        conn, idx = _make_db([
            ("15707",  "5-MTHF 1 mg", "Thorne Research", "693749129011", "discontinued", 48.0),
            ("35431",  "5-MTHF 1 mg", "Thorne Research", "693749129011", "discontinued", 47.0),
            ("63783",  "5-MTHF 1 mg", "Thorne Research", "693749129011", "discontinued", 48.0),
            ("181732", "5-MTHF 1 mg", "Thorne",          "6 93749 12901 1", "discontinued", 47.6),
            ("181733", "5-MTHF 1 mg", "Thorne",          "6 93749 12901 1", "discontinued", 47.6),
            ("284181", "5-MTHF 1 mg", "Thorne",          "6 93749 12901 1", "active", 46.0),
            ("337850", "5-MTHF 1 mg", "Thorne",          "6 93749 12901 1", "active", 46.0),
        ])
        result = dedup_by_upc(conn, idx)
        remaining = _remaining_ids(conn)

        # Exactly one survivor
        assert len(remaining) == 1
        # Active entries outrank discontinued, tie-break by dsld_id → "337850" wins
        assert remaining[0] == "337850"
        assert result["duplicates_removed"] == 6
        assert result["upc_groups_deduped"] == 1
        # detail_index only keeps the winner
        assert len(idx) == 1
        assert "337850" in idx

    def test_detail_index_stays_in_sync(self):
        """detail_index entries for deleted rows are removed."""
        conn, idx = _make_db([
            ("A", "P", "B", "999", "active", 50.0),
            ("B", "P", "B", "999", "active", 40.0),
            ("C", "P", "B", "999", "discontinued", 60.0),
        ])
        dedup_by_upc(conn, idx)
        assert set(idx.keys()) == {"A"}
        assert _remaining_ids(conn) == ["A"]

    def test_null_score_treated_as_zero(self):
        """Products with NULL score_quality_80 don't crash the sort."""
        conn, idx = _make_db([
            ("100", "A", "X", "111", "active", None),
            ("200", "A", "X", "111", "active", 40.0),
        ])
        dedup_by_upc(conn, idx)
        # 200 wins because COALESCE(NULL,0) < 40
        assert _remaining_ids(conn) == ["200"]
