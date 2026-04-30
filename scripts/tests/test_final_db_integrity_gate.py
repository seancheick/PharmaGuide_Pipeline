#!/usr/bin/env python3
"""
Final DB data integrity gate (Batch 3 contract enforcement).

Contract: products in `products_core` must have complete, accurate scoring.
Anything that fails the gate is routed to `excluded_by_gate` (the existing
quarantine bucket) and never reaches Flutter.

What ships (verdict shows in app):
    SAFE, CAUTION, POOR, BLOCKED, UNSAFE, NUTRITION_ONLY

What does NOT ship (gate-quarantined):
    NOT_SCORED          — mapping/dosage gate failure; can't claim accuracy
    score_100=None on a non-blocked verdict — incomplete computation
    breakdown.A/B/C/D missing or non-numeric — partial scoring failure
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from build_final_db import validate_export_contract  # noqa: E402

# Reuse the existing rich fixtures from the test_build_final_db module.
from test_build_final_db import make_enriched, make_scored  # noqa: E402


# ---------------------------------------------------------------------------
# Existing baseline still passes
# ---------------------------------------------------------------------------


def test_complete_safe_product_passes_gate():
    """SAFE product with full A/B/C/D + score_100 passes."""
    issues = validate_export_contract(make_enriched(), make_scored("SAFE"))
    assert issues == [], f"Unexpected issues: {issues}"


def test_complete_caution_product_passes_gate():
    """CAUTION ships — user sees the warning."""
    issues = validate_export_contract(make_enriched(), make_scored("CAUTION"))
    assert issues == [], f"Unexpected issues: {issues}"


def test_complete_blocked_product_passes_gate():
    """BLOCKED ships with the recall reason — user sees stop signal."""
    issues = validate_export_contract(make_enriched(), make_scored("BLOCKED"))
    assert issues == []


def test_complete_unsafe_product_passes_gate():
    """UNSAFE ships with the ban reason."""
    issues = validate_export_contract(make_enriched(), make_scored("UNSAFE"))
    assert issues == []


# ---------------------------------------------------------------------------
# NOT_SCORED must NEVER ship
# ---------------------------------------------------------------------------


def test_not_scored_verdict_is_quarantined():
    """NOT_SCORED is the symptom of a mapping gate failure — never ship.

    The error message must contain a phrase that routes to the
    `excluded_by_gate` bucket via _classify_export_error so the failure
    is reported as a by-design quarantine, not as a catastrophic error.
    """
    scored = make_scored("NOT_SCORED")
    scored["score_100_equivalent"] = None
    scored["quality_score"] = None
    scored["score_80"] = None

    issues = validate_export_contract(make_enriched(), scored)
    assert issues, "NOT_SCORED product must be rejected by the gate"
    assert any("NOT_SCORED" in issue or "review_queue" in issue.lower()
               or "gate" in issue.lower() for issue in issues), (
        f"Gate failure message must signal quarantine, got: {issues}"
    )


def test_null_score_on_safe_verdict_is_quarantined():
    """A SAFE/CAUTION/POOR verdict with score_100=None is incoherent — quarantine."""
    scored = make_scored("SAFE")
    scored["score_100_equivalent"] = None
    issues = validate_export_contract(make_enriched(), scored)
    assert issues, "SAFE verdict with null score_100 must be rejected"
    assert any("score_100_equivalent" in issue or "score" in issue.lower()
               for issue in issues), f"Got: {issues}"


def test_blocked_with_null_score_is_allowed():
    """BLOCKED products legitimately may have None score (substance-blocked)."""
    scored = make_scored("BLOCKED")
    scored["score_100_equivalent"] = None
    scored["quality_score"] = None
    issues = validate_export_contract(make_enriched(), scored)
    # BLOCKED does not need a numeric score — the recall reason is the data
    assert issues == [], (
        f"BLOCKED with null score must be allowed; got: {issues}"
    )


def test_unsafe_with_null_score_is_allowed():
    """UNSAFE products may legitimately have None score (banned substance)."""
    scored = make_scored("UNSAFE")
    scored["score_100_equivalent"] = None
    scored["quality_score"] = None
    issues = validate_export_contract(make_enriched(), scored)
    assert issues == []


# ---------------------------------------------------------------------------
# Missing breakdown sections must NEVER ship
# ---------------------------------------------------------------------------


def test_missing_section_a_is_quarantined():
    """Section A must be a numeric score for non-BLOCKED/UNSAFE verdicts."""
    scored = make_scored("SAFE")
    scored["section_scores"]["A_ingredient_quality"] = {}  # missing score
    issues = validate_export_contract(make_enriched(), scored)
    assert issues, "Missing A section score must be rejected"


def test_non_finite_score_is_quarantined():
    """Inf or NaN scores must never ship."""
    scored = make_scored("SAFE")
    scored["score_100_equivalent"] = float("inf")
    issues = validate_export_contract(make_enriched(), scored)
    assert issues, "Non-finite score must be rejected"


# ---------------------------------------------------------------------------
# Quarantine reason must route through _classify_export_error
# ---------------------------------------------------------------------------


def test_quarantine_message_routes_to_excluded_by_gate_bucket():
    """The new gate's error messages must classify as 'excluded_by_gate'.

    This ensures NOT_SCORED quarantines surface in
    `export_audit_report.json:excluded_by_gate[]` (a non-blocking quarantine
    that doesn't fail the Supabase sync), not in `errors[]` (which would
    block sync as a catastrophic failure).
    """
    from build_final_db import _classify_export_error

    scored = make_scored("NOT_SCORED")
    scored["score_100_equivalent"] = None
    scored["quality_score"] = None

    issues = validate_export_contract(make_enriched(), scored)
    assert issues, "Expected gate failure"
    msg = "; ".join(issues)
    bucket = _classify_export_error(msg)
    assert bucket == "excluded_by_gate", (
        f"Gate failures must route to excluded_by_gate, got bucket={bucket!r} "
        f"for msg={msg!r}"
    )
