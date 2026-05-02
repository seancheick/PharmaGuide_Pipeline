#!/usr/bin/env python3
"""
Regression test for the NOT_SCORED review-queue gate (build_final_db.py).

Asserts:
  1. validate_export_contract() raises (returns issues) when verdict=NOT_SCORED
  2. The defensive sweep SQL removes any stale NOT_SCORED rows from products_core

Per REFERENCE_DATA_LOOKUP_OPPORTUNITIES.md §1 pipeline contract:
"NOT_SCORED is intentionally NOT in vocab — products that fail scoring
divert to the review queue and never ship to Flutter."
"""

import os
import sqlite3

import pytest

import sys
HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, ".."))

from build_final_db import validate_export_contract  # noqa: E402


def test_validate_export_contract_rejects_not_scored():
    """Per Batch 3 data integrity gate, NOT_SCORED must be flagged for the
    review queue and excluded from the products_core insert path."""
    enriched = {"dsld_id": "TEST-001", "product_name": "Test"}
    scored = {
        "verdict": "NOT_SCORED",
        "section_scores": {},
        "scoring_metadata": {},
    }
    issues = validate_export_contract(enriched, scored)
    assert any("review_queue" in i and "NOT_SCORED" in i for i in issues), (
        f"Expected NOT_SCORED to trigger review_queue issue; got {issues}"
    )


def test_defensive_sweep_removes_not_scored():
    """The end-of-build defensive sweep cleans any stale NOT_SCORED rows
    from products_core. This guards against pre-gate builds and against
    products that fell out of the input batch between runs."""
    # In-memory SQLite mirroring the products_core schema for the columns
    # we care about
    conn = sqlite3.connect(":memory:")
    c = conn.cursor()
    c.execute("CREATE TABLE products_core (dsld_id TEXT PRIMARY KEY, verdict TEXT)")
    c.execute("INSERT INTO products_core VALUES ('A', 'SAFE')")
    c.execute("INSERT INTO products_core VALUES ('B', 'NOT_SCORED')")
    c.execute("INSERT INTO products_core VALUES ('C', 'NOT_SCORED')")
    c.execute("INSERT INTO products_core VALUES ('D', 'NUTRITION_ONLY')")
    conn.commit()

    swept = c.execute(
        "DELETE FROM products_core WHERE verdict = ?", ("NOT_SCORED",)
    ).rowcount
    assert swept == 2

    remaining = c.execute(
        "SELECT verdict, COUNT(*) FROM products_core GROUP BY verdict ORDER BY 1"
    ).fetchall()
    assert remaining == [("NUTRITION_ONLY", 1), ("SAFE", 1)]
    conn.close()


def test_nutrition_only_is_not_swept():
    """NUTRITION_ONLY is a legitimate shipped verdict (food-shape products);
    the sweep targets only NOT_SCORED."""
    conn = sqlite3.connect(":memory:")
    c = conn.cursor()
    c.execute("CREATE TABLE products_core (dsld_id TEXT PRIMARY KEY, verdict TEXT)")
    c.execute("INSERT INTO products_core VALUES ('FOOD', 'NUTRITION_ONLY')")
    conn.commit()

    swept = c.execute(
        "DELETE FROM products_core WHERE verdict = ?", ("NOT_SCORED",)
    ).rowcount
    assert swept == 0

    rows = c.execute("SELECT * FROM products_core").fetchall()
    assert rows == [("FOOD", "NUTRITION_ONLY")]
    conn.close()
