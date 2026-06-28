#!/usr/bin/env python3
"""Underdosed sole-primary synergy emission (present-but-underdosed 3-state).

A single primary ingredient that matches a cluster but sits BELOW its effective
dose used to be dropped entirely by ``_collect_synergy_data`` (the
single-ingredient override required ``meets_minimum``). That made the goal show
as "Unaddressed" when the ingredient was in fact present — e.g. a magnesium-only
product at 150 mg vanished from the stress goal (effective dose 200 mg).

New behavior: a sole primary ingredient at >= 50% of its effective dose is
emitted as a present-but-underdosed cluster (``underdosed_single: True``,
matched ingredient ``meets_minimum: False``). Downstream:
  * goal matching routes it to ``goal_matches_underdosed`` (presence set keeps
    it; the dose-adequate set excludes it because meets_minimum is False);
  * the A5c synergy BONUS ignores it (match_count < 2);
  * the synergy DISPLAY filters it out (it is not a real synergy).

A trace dose (< 50% of the minimum) is still dropped — 17 mg of magnesium in a
multivitamin must not claim to "partially support" sleep.

These tests pin the enricher contract using stress_resilience (magnesium
effective dose 200 mg), which is independent of the sleep_stack recalibration.
"""

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from enrich_supplements_v3 import SupplementEnricherV3  # noqa: E402
from build_final_db import build_detail_blob  # noqa: E402


@pytest.fixture(scope="module")
def enricher():
    # Module-scoped: booting the enricher loads all reference databases.
    return SupplementEnricherV3()


def _magnesium_only(qty_mg):
    """Minimal product whose sole active is elemental magnesium at qty_mg.

    Generic name (no nutrient+dose pattern) so the name-synthesis fallback
    does not inject extra virtual ingredients.
    """
    return {
        "name": "Test Single Active Product",
        "activeIngredients": [
            {
                "name": "Magnesium Glycinate",
                "standardName": "Magnesium",
                "quantity": qty_mg,
                "unit": "mg",
            }
        ],
    }


def _cluster(clusters, cluster_id):
    return next((c for c in clusters if c.get("cluster_id") == cluster_id), None)


def test_underdosed_sole_primary_is_emitted_as_underdosed_single(enricher):
    """150 mg magnesium (>=50% of the 200 mg stress dose, but below it) is
    emitted as present-but-underdosed rather than dropped."""
    clusters = enricher._collect_synergy_data(_magnesium_only(150))
    stress = _cluster(clusters, "stress_resilience")
    assert stress is not None, "underdosed sole-primary cluster must be emitted"
    assert stress.get("underdosed_single") is True
    # The matched magnesium row reports the honest (failing) dose check.
    mag = next(
        m for m in stress["matched_ingredients"]
        if "magnesium" in str(m.get("cluster_ingredient", "")).lower()
    )
    assert mag["meets_minimum"] is False
    # Not an adequate solo match.
    assert stress.get("single_ingredient_match") is False


def test_trace_sole_primary_is_still_dropped(enricher):
    """80 mg magnesium (<50% of the 200 mg stress dose) is trace — dropped, so
    the goal stays Unaddressed (no 'partially supported' noise)."""
    clusters = enricher._collect_synergy_data(_magnesium_only(80))
    assert _cluster(clusters, "stress_resilience") is None


def test_adequate_sole_primary_unchanged(enricher):
    """250 mg magnesium (>= the 200 mg stress dose) stays a normal adequate
    solo match: single_ingredient_match True, underdosed_single False."""
    clusters = enricher._collect_synergy_data(_magnesium_only(250))
    stress = _cluster(clusters, "stress_resilience")
    assert stress is not None
    assert stress.get("single_ingredient_match") is True
    assert stress.get("underdosed_single") in (False, None)
    mag = next(
        m for m in stress["matched_ingredients"]
        if "magnesium" in str(m.get("cluster_ingredient", "")).lower()
    )
    assert mag["meets_minimum"] is True


def test_underdosed_single_does_not_earn_synergy_bonus(enricher):
    """An underdosed single-ingredient cluster (match_count 1) must never set
    synergy_cluster_qualified — the A5c bonus requires >= 2 matched."""
    clusters = enricher._collect_synergy_data(_magnesium_only(150))
    enriched = {
        "formulation_data": {"synergy_clusters": clusters},
        "contaminant_data": {},
    }
    enricher._project_scoring_fields(enriched)
    assert enriched["synergy_cluster_qualified"] is False


def test_underdosed_single_cluster_hidden_from_synergy_display():
    """The user-facing synergy_detail must not list an underdosed_single cluster
    — it is a goal-coverage signal, not a real synergy to show off."""
    enriched = {
        "formulation_data": {
            "synergy_clusters": [
                {
                    "cluster_id": "stress_resilience",
                    "cluster_name": "Stress Resilience",
                    "evidence_tier": 2,
                    "matched_ingredients": [
                        {"ingredient": "Ashwagandha", "meets_minimum": True},
                        {"ingredient": "L-Theanine", "meets_minimum": True},
                    ],
                    "match_count": 2,
                    "underdosed_single": False,
                },
                {
                    "cluster_id": "sleep_stack",
                    "cluster_name": "Sleep Stack",
                    "evidence_tier": 3,
                    "matched_ingredients": [
                        {"ingredient": "Magnesium", "meets_minimum": False},
                    ],
                    "match_count": 1,
                    "underdosed_single": True,
                },
            ]
        }
    }
    blob = build_detail_blob(enriched, {})
    detail = blob.get("synergy_detail") or {}
    ids = [c.get("id") for c in detail.get("clusters", [])]
    assert "stress_resilience" in ids, "real synergy must still display"
    assert "sleep_stack" not in ids, "underdosed_single must be suppressed from display"
