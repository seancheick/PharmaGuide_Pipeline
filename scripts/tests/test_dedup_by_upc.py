#!/usr/bin/env python3
"""UPC collisions are identity ambiguity, never a score competition."""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from build_final_db import dedup_by_upc


_MINI_SCHEMA = """
CREATE TABLE products_core (
    dsld_id              TEXT PRIMARY KEY,
    product_name         TEXT NOT NULL,
    brand_name           TEXT,
    upc_sku              TEXT,
    product_status       TEXT,
    quality_score_v4_100 REAL,
    score_100_equivalent REAL,
    quality_score_status TEXT
);
"""


def _make_db(rows):
    conn = sqlite3.connect(":memory:")
    conn.executescript(_MINI_SCHEMA)
    for row in rows:
        score = row[5]
        conn.execute(
            "INSERT INTO products_core "
            "(dsld_id, product_name, brand_name, upc_sku, product_status, "
            " quality_score_v4_100, score_100_equivalent, quality_score_status) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (row[0], row[1], row[2], row[3], row[4], score, score, "scored"),
        )
    conn.commit()
    detail_index = {
        str(row[0]): {"blob_sha256": f"sha_{row[0]}"} for row in rows
    }
    return conn, detail_index


def _remaining_ids(conn):
    return [
        row[0]
        for row in conn.execute(
            "SELECT dsld_id FROM products_core ORDER BY dsld_id"
        ).fetchall()
    ]


def test_shared_upc_retains_every_candidate_regardless_of_score_or_status():
    conn, detail_index = _make_db([
        ("scored", "Formula A", "Brand", "012 345", "active", 95.0),
        ("blocked", "Formula B", "Brand", "012345", "active", None),
        ("historic", "Formula C", "Brand", "012345", "discontinued", 40.0),
    ])

    result = dedup_by_upc(conn, detail_index)

    assert _remaining_ids(conn) == ["blocked", "historic", "scored"]
    assert set(detail_index) == {"blocked", "historic", "scored"}
    assert result["duplicates_removed"] == 0
    assert result["upc_groups_deduped"] == 0
    assert result["ambiguous_upc_groups"] == 1
    assert result["ambiguous_product_count"] == 3
    assert result["ambiguous_groups_sample"] == [
        {"upc": "012345", "dsld_ids": ["blocked", "historic", "scored"]}
    ]


def test_no_shared_upcs_reports_no_ambiguity():
    conn, detail_index = _make_db([
        ("100", "A", "Brand", "111", "active", 50.0),
        ("200", "B", "Brand", "222", "active", 45.0),
    ])

    result = dedup_by_upc(conn, detail_index)

    assert _remaining_ids(conn) == ["100", "200"]
    assert result["ambiguous_upc_groups"] == 0
    assert result["ambiguous_product_count"] == 0


def test_missing_and_blank_upcs_are_not_grouped():
    conn, detail_index = _make_db([
        ("100", "A", "Brand", None, "active", 50.0),
        ("200", "B", "Brand", "", "active", 45.0),
        ("300", "C", "Brand", "   ", "active", 40.0),
    ])

    result = dedup_by_upc(conn, detail_index)

    assert _remaining_ids(conn) == ["100", "200", "300"]
    assert result["ambiguous_upc_groups"] == 0


def test_shared_upc_audit_never_reads_quality_columns():
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        "CREATE TABLE products_core ("
        "dsld_id TEXT PRIMARY KEY, upc_sku TEXT);"
    )
    conn.executemany(
        "INSERT INTO products_core VALUES (?, ?)",
        [("100", "999"), ("200", "999")],
    )
    detail_index = {"100": {}, "200": {}}

    result = dedup_by_upc(conn, detail_index)

    assert result["ambiguous_upc_groups"] == 1
    assert _remaining_ids(conn) == ["100", "200"]
