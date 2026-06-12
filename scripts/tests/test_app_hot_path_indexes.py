"""App hot-path index contract — catalog & interaction DDL must ship the
expression indexes the Flutter app queries through.

The Flutter app (lib/data/database/core_database.dart and
interaction_database.dart, `_ensureAppIndexes`) creates these indexes at
first open as a fallback, but every shipped artifact should already carry
them so first-open cost is zero and the expressions never drift.

The expression strings below are CONTRACT: they must stay char-identical
to the SQL the app executes, or SQLite will not match index to query.
"""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import build_final_db
import build_interaction_db


UPC_NORMALIZE_EXPR = (
    "REPLACE(REPLACE(REPLACE(REPLACE(upc_sku, ' ', ''), '-', ''), "
    "'.', ''), '/', '')"
)


def _apply_core_schema(conn):
    conn.executescript(build_final_db.SCHEMA_SQL)
    conn.executescript(build_final_db.CORE_INDEX_SQL)


def _index_names(conn, table):
    return {
        row[1]
        for row in conn.execute(f"PRAGMA index_list({table})").fetchall()
    }


def test_core_ddl_ships_upc_normalized_and_cat_score_indexes():
    conn = sqlite3.connect(":memory:")
    _apply_core_schema(conn)
    names = _index_names(conn, "products_core")
    assert "idx_core_upc_normalized" in names
    assert "idx_core_cat_score" in names


def test_upc_normalized_index_serves_app_query_plan():
    conn = sqlite3.connect(":memory:")
    _apply_core_schema(conn)
    plan = conn.execute(
        "EXPLAIN QUERY PLAN SELECT dsld_id FROM products_core "
        f"WHERE {UPC_NORMALIZE_EXPR} = ?",
        ("012345678905",),
    ).fetchall()
    detail = " ".join(str(row[3]) for row in plan)
    assert "idx_core_upc_normalized" in detail, detail


def test_cat_score_partial_index_serves_alternatives_query_plan():
    conn = sqlite3.connect(":memory:")
    _apply_core_schema(conn)
    # Literal status predicate — matches the app's inlined CustomExpression
    # so SQLite can prove the partial-index WHERE clause.
    plan = conn.execute(
        "EXPLAIN QUERY PLAN SELECT dsld_id FROM products_core "
        "WHERE primary_category = ? AND quality_score_v4_100 > 50 "
        "AND quality_score_status = 'scored' "
        "ORDER BY quality_score_v4_100 DESC LIMIT 20",
        ("multivitamin",),
    ).fetchall()
    detail = " ".join(str(row[3]) for row in plan)
    assert "idx_core_cat_score" in detail, detail


def test_interaction_ddl_ships_lower_expression_indexes():
    conn = sqlite3.connect(":memory:")
    conn.executescript(build_interaction_db.SCHEMA_SQL)
    int_names = _index_names(conn, "interactions")
    rp_names = _index_names(conn, "research_pairs")
    assert {"idx_int_a1_canon_lower", "idx_int_a2_canon_lower"} <= int_names
    assert {"idx_rp_canon_a_lower", "idx_rp_canon_b_lower"} <= rp_names


def test_interaction_lower_index_serves_app_query_plan():
    conn = sqlite3.connect(":memory:")
    conn.executescript(build_interaction_db.SCHEMA_SQL)
    plan = conn.execute(
        "EXPLAIN QUERY PLAN SELECT id FROM interactions "
        "WHERE lower(agent1_canonical_id) = ? "
        "OR lower(agent2_canonical_id) = ?",
        ("st_johns_wort", "st_johns_wort"),
    ).fetchall()
    detail = " ".join(str(row[3]) for row in plan)
    assert "idx_int_a1_canon_lower" in detail, detail
    assert "idx_int_a2_canon_lower" in detail, detail
