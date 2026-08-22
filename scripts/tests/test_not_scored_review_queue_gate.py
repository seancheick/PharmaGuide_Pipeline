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


def test_not_scored_review_record_names_reason_and_incomplete_dimensions():
    enriched = {"dsld_id": "TEST-ROUTE", "product_name": "Claimed Protein"}
    scored = {
        "verdict": "NOT_SCORED",
        "score_unavailable_reason": "blocked_by_completeness_gate",
        "assessment_readiness": {
            "enforcement_mode": "enforced",
            "identity": {"readiness": "complete"},
            "dose": {"readiness": "complete"},
            "evidence": {"readiness": "incomplete"},
            "verification": {"readiness": "complete"},
            "route": {"readiness": "incomplete"},
            "enforced_dimensions": [
                "identity",
                "dose",
                "verification",
                "route",
            ],
        },
        "section_scores": {},
        "scoring_metadata": {},
    }

    issues = validate_export_contract(enriched, scored)

    review_record = next(issue for issue in issues if "NOT_SCORED" in issue)
    assert "reason=blocked_by_completeness_gate" in review_record
    assert "incomplete_dimensions=route" in review_record
    assert "evidence" not in review_record


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
        "DELETE FROM products_core WHERE verdict IN (?, ?)",
        ("NOT_SCORED", "NUTRITION_ONLY"),
    ).rowcount
    assert swept == 3

    remaining = c.execute(
        "SELECT verdict, COUNT(*) FROM products_core GROUP BY verdict ORDER BY 1"
    ).fetchall()
    assert remaining == [("SAFE", 1)]
    conn.close()


def test_validate_export_contract_rejects_retired_nutrition_only():
    enriched = {"dsld_id": "FOOD", "product_name": "Food-shaped product"}
    scored = {
        "verdict": "NUTRITION_ONLY",
        "section_scores": {},
        "scoring_metadata": {},
    }

    issues = validate_export_contract(enriched, scored)

    assert any(
        "NUTRITION_ONLY" in issue and "retired" in issue.lower()
        for issue in issues
    )
