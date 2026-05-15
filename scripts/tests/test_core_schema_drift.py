#!/usr/bin/env python3
"""
Schema-drift gate for products_core.

Three sources of truth must agree on the products_core column set:

  1. CORE_COLUMN_COUNT  — build_final_db.py constant (line ~4899)
  2. PRODUCTS_CORE_COLUMNS — test_build_final_db.py list
  3. SCHEMA_SQL CREATE TABLE products_core — the actual SQLite schema

If any one drifts, INSERT row tuples land in the wrong columns silently
until the runtime length-check at insert time fires. That check is
correct but only runs during a full build. This test fails at unit-test
time, before the build, by executing SCHEMA_SQL in an in-memory SQLite
and reading PRAGMA table_info.
"""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from build_final_db import CORE_COLUMN_COUNT, SCHEMA_SQL  # noqa: E402

# Reuse the canonical column list maintained alongside the row-builder.
from test_build_final_db import PRODUCTS_CORE_COLUMNS  # noqa: E402


def _pragma_columns() -> list[str]:
    """Return products_core column names in declaration order."""
    conn = sqlite3.connect(":memory:")
    try:
        conn.executescript(SCHEMA_SQL)
        rows = conn.execute("PRAGMA table_info(products_core)").fetchall()
    finally:
        conn.close()
    # PRAGMA table_info: (cid, name, type, notnull, dflt_value, pk)
    rows.sort(key=lambda r: r[0])
    return [r[1] for r in rows]


def test_core_column_count_matches_schema_sql():
    """CORE_COLUMN_COUNT must match the actual SCHEMA_SQL table definition."""
    pragma_cols = _pragma_columns()
    assert len(pragma_cols) == CORE_COLUMN_COUNT, (
        f"CORE_COLUMN_COUNT={CORE_COLUMN_COUNT} but SCHEMA_SQL declares "
        f"{len(pragma_cols)} columns. Update CORE_COLUMN_COUNT in "
        f"build_final_db.py and the row tuple in build_core_row()."
    )


def test_products_core_columns_list_matches_schema_sql():
    """PRODUCTS_CORE_COLUMNS list must match SCHEMA_SQL column names + order.

    Order matters: build_core_row() returns a positional tuple. If the
    list reorders without the tuple reordering, row_as_dict() will map
    values to the wrong columns silently.
    """
    pragma_cols = _pragma_columns()
    test_cols = list(PRODUCTS_CORE_COLUMNS)

    extra_in_test = set(test_cols) - set(pragma_cols)
    extra_in_schema = set(pragma_cols) - set(test_cols)
    assert not extra_in_test, (
        f"PRODUCTS_CORE_COLUMNS has columns not in SCHEMA_SQL: {sorted(extra_in_test)}"
    )
    assert not extra_in_schema, (
        f"SCHEMA_SQL has columns not in PRODUCTS_CORE_COLUMNS: {sorted(extra_in_schema)}"
    )
    assert test_cols == pragma_cols, (
        "PRODUCTS_CORE_COLUMNS order does not match SCHEMA_SQL declaration "
        "order. First divergence: "
        + next(
            f"index {i}: test={t!r} schema={s!r}"
            for i, (t, s) in enumerate(zip(test_cols, pragma_cols))
            if t != s
        )
    )


def test_pragma_count_matches_products_core_columns_length():
    """Triangulation: all three sources agree on column count."""
    pragma_cols = _pragma_columns()
    assert (
        len(pragma_cols)
        == len(PRODUCTS_CORE_COLUMNS)
        == CORE_COLUMN_COUNT
    ), (
        f"Column count mismatch: PRAGMA={len(pragma_cols)}, "
        f"PRODUCTS_CORE_COLUMNS={len(PRODUCTS_CORE_COLUMNS)}, "
        f"CORE_COLUMN_COUNT={CORE_COLUMN_COUNT}"
    )
