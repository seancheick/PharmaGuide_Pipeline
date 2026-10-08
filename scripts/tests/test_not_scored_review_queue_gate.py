#!/usr/bin/env python3
"""Known labels may ship without scores; missing label identity stays quarantined.

The actual builder, including its defensive sweep, must retain eligible
NOT_SCORED rows while continuing to reject retired NUTRITION_ONLY rows.
"""

import os
import json
from pathlib import Path
import sqlite3

import pytest

import sys
HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, ".."))

from build_final_db import validate_export_contract, build_final_db  # noqa: E402


def test_validate_export_contract_rejects_not_scored():
    """A malformed NOT_SCORED payload without a usable label stays excluded."""
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


def test_missing_label_quarantine_preserves_scorer_assessment_reason():
    enriched = {"dsld_id": "TEST-ROUTE", "product_name": "Claimed Protein"}
    scored = {
        "verdict": "NOT_SCORED",
        "quality_score_status": "not_scored",
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

    assert "review_queue: NOT_SCORED product lacks a verified source-label record." in issues
    assert scored["score_unavailable_reason"] == "blocked_by_completeness_gate"
    assert scored["assessment_readiness"]["route"]["readiness"] == "incomplete"
    assert scored["assessment_readiness"]["evidence"]["readiness"] == "incomplete"


def test_actual_builder_retains_eligible_not_scored_after_defensive_sweep(tmp_path):
    from scripts.tests.test_export_gate import _unscored_known_label_fixture

    enriched, scored = _unscored_known_label_fixture()
    scored["dsld_id"] = enriched["dsld_id"]
    enriched_dir = tmp_path / "enriched"
    scored_dir = tmp_path / "scored"
    output = tmp_path / "output"
    enriched_dir.mkdir()
    scored_dir.mkdir()
    (enriched_dir / "batch.json").write_text(json.dumps([enriched]))
    (scored_dir / "batch.json").write_text(json.dumps([scored]))
    result = build_final_db([str(enriched_dir)], [str(scored_dir)],
                            str(output), str(Path(__file__).resolve().parents[1]))
    assert result["product_count"] == 1
    assert result["error_count"] == 0
    with sqlite3.connect(output / "pharmaguide_core.db") as conn:
        row = conn.execute("SELECT verdict, quality_score_status, quality_score_v4_100, "
                           "quality_tier FROM products_core WHERE dsld_id='31063'").fetchone()
    assert row == ("NOT_SCORED", "not_scored", None, None)
    blob = json.loads((output / "detail_blobs" / "31063.json").read_text())
    assert blob["display_ingredients"][0]["label_display_name"] == "Vitamin C"


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
