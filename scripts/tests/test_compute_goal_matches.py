#!/usr/bin/env python3
"""Behavior tests for ``compute_goal_matches()`` in ``scripts/build_final_db.py``.

These tests pin the v6.0.0 matching algorithm:
  * required_clusters gate (any-present)
  * blocked_by_clusters gate (any-present → disqualify)
  * normalized score = matched_weight / max_weight
  * threshold gate via min_match_score
  * deduplication of product clusters
  * confidence = average matched score across matched goals
"""

import sys
from pathlib import Path

import pytest

# Make scripts/ importable so we can hit build_final_db's helpers directly.
SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from build_final_db import compute_goal_matches  # noqa: E402


def _enriched(clusters):
    return {"synergy_detail": {"clusters_matched": list(clusters)}}


# ---------- Empty / degenerate inputs ----------


def test_empty_clusters_returns_empty_match():
    result = compute_goal_matches(_enriched([]))
    assert result == {"goal_matches": [], "goal_match_confidence": 0.0}


def test_missing_synergy_detail_returns_empty_match():
    result = compute_goal_matches({})
    assert result == {"goal_matches": [], "goal_match_confidence": 0.0}


def test_clusters_with_no_overlap_returns_empty_match():
    # urinary_tract_health is a real cluster but isn't weighted by any of the 18 goals.
    result = compute_goal_matches(_enriched(["urinary_tract_health"]))
    assert result["goal_matches"] == []
    assert result["goal_match_confidence"] == 0.0


# ---------- required_clusters gate ----------


def test_required_clusters_gate_blocks_when_no_required_present():
    """GOAL_REDUCE_STRESS_ANXIETY requires stress_resilience OR mood_balance.
    A product with adrenal_support alone (in cluster_weights but not required)
    must not match — even if score would otherwise pass."""
    # adrenal_support has weight 0.9 in stress goal; total weight ~5.0; score ~0.18 anyway,
    # so we need a stronger combo to isolate the required gate. Use the closest cluster set
    # that hits high score WITHOUT touching either required cluster:
    # adrenal_support (0.9) + magnesium (0.7) + sleep (0.6) + mood_gut (0.5) + probiotic (0.4)
    # = 3.1 / 5.0 = 0.62 (above 0.5) — but neither required is hit.
    result = compute_goal_matches(_enriched([
        "adrenal_support", "magnesium_nervous_system", "sleep_stack",
        "mood_gut_axis_probiotic_blend", "probiotic_and_gut_health",
    ]))
    assert "GOAL_REDUCE_STRESS_ANXIETY" not in result["goal_matches"]


def test_required_clusters_gate_passes_when_at_least_one_required_present():
    """SLEEP_QUALITY requires sleep_stack only. Presence + good score → match."""
    result = compute_goal_matches(_enriched([
        "sleep_stack", "magnesium_nervous_system", "stress_resilience",
    ]))
    assert "GOAL_SLEEP_QUALITY" in result["goal_matches"]


# ---------- blocked_by_clusters gate ----------


def test_blocked_clusters_disqualify_even_with_high_score():
    """SLEEP_QUALITY blocks pre_workout_energy. A product hitting sleep_stack +
    magnesium would otherwise easily match (score ~0.56), but pre_workout_energy
    must override that."""
    result = compute_goal_matches(_enriched([
        "sleep_stack", "magnesium_nervous_system", "pre_workout_energy",
    ]))
    assert "GOAL_SLEEP_QUALITY" not in result["goal_matches"]


def test_blocked_clusters_apply_independently_per_goal():
    """A product with sleep_stack + pre_workout_energy: blocked from SLEEP, but
    pre_workout_energy is required for INCREASE_ENERGY (not blocked there)."""
    result = compute_goal_matches(_enriched([
        "energy_mitochondria", "pre_workout_energy", "sleep_stack",
    ]))
    # SLEEP blocks on pre_workout_energy → excluded
    assert "GOAL_SLEEP_QUALITY" not in result["goal_matches"]
    # INCREASE_ENERGY blocks on sleep_stack → also excluded
    assert "GOAL_INCREASE_ENERGY" not in result["goal_matches"]


# ---------- min_match_score (normalized) gate ----------


def test_single_required_cluster_at_full_coverage_passes_via_score_required():
    """Score formula is max(score_full, score_required).

    SLEEP_QUALITY required=['sleep_stack']. A product hitting only sleep_stack
    has matched_required_weight = 1.0, max_required_weight = 1.0 → score_required
    = 1.0. This rewards single-purpose supplements and makes the
    single-ingredient-override pipeline visible at the goal layer."""
    result = compute_goal_matches(_enriched(["sleep_stack"]))
    # sleep_stack alone covers the only required cluster fully.
    assert "GOAL_SLEEP_QUALITY" in result["goal_matches"]
    # confidence is the max of (1.0/3.4 = 0.29) and (1.0/1.0 = 1.0) = 1.0
    assert result["goal_match_confidence"] == 1.0


def test_partial_required_coverage_uses_required_ratio():
    """LIVER_DETOX requires both liver_support and detox_pathway with weights
    1.0 each. Hitting only liver_support → score_required = 1.0/2.0 = 0.5 →
    exactly meets threshold 0.5. score_full = 1.0/3.7 = 0.27 below threshold.
    max(0.27, 0.5) = 0.5 → MATCH (corrected single-purpose semantics)."""
    result = compute_goal_matches(_enriched(["liver_support"]))
    assert "GOAL_LIVER_DETOX" in result["goal_matches"]


def test_zero_required_overlap_excludes_goal():
    """Even with score-max, no required cluster present means goal cannot
    fire (gate 2 short-circuits before the score is computed)."""
    # GOAL_LIVER_DETOX required = [liver_support, detox_pathway]. Provide
    # neither — only contributing cluster_weights via gut_barrier (0.5).
    result = compute_goal_matches(_enriched(["gut_barrier"]))
    assert "GOAL_LIVER_DETOX" not in result["goal_matches"]


def test_high_threshold_single_required_still_passes_when_fully_covered():
    """PRENATAL has min_match_score=0.7. Hitting only prenatal_pregnancy_support:
       score_required = 1.0/1.0 = 1.0 ≥ 0.7 → MATCH.
    A DHA-only or folate-only single-ingredient supplement reaches PRENATAL
    via this path — exactly the behavior the single-ingredient override
    on the cluster needs at the goal layer."""
    result = compute_goal_matches(_enriched(["prenatal_pregnancy_support"]))
    assert "GOAL_PRENATAL_PREGNANCY" in result["goal_matches"]
    assert result["goal_match_confidence"] == 1.0


# ---------- deduplication ----------


def test_duplicate_clusters_are_deduplicated():
    """Repeating sleep_stack 5 times must not inflate the score above 1.0
    nor count as multiple matches at the cluster level."""
    result_one = compute_goal_matches(_enriched(["sleep_stack"]))
    result_five = compute_goal_matches(_enriched(["sleep_stack"] * 5))
    # Identical results regardless of duplication
    assert result_one == result_five
    # Score capped at 1.0
    assert result_five["goal_match_confidence"] <= 1.0


# ---------- confidence aggregation ----------


def test_confidence_is_average_of_matched_scores_rounded_to_two_decimals():
    """fat_metabolism + blood_sugar covers BOTH WEIGHT_MGMT required clusters
    with total required-weight = 1.9 → score_required = 1.0 (full coverage).
    BLOOD_SUGAR required=blood_sugar only → score_required = 1.0.
    Both match. Confidence is average of matched scores."""
    result = compute_goal_matches(_enriched([
        "fat_metabolism", "blood_sugar_regulation",
    ]))
    assert "GOAL_WEIGHT_MANAGEMENT" in result["goal_matches"]
    assert "GOAL_BLOOD_SUGAR_SUPPORT" in result["goal_matches"]
    # Both matched at score 1.0 → average 1.0
    assert result["goal_match_confidence"] == 1.0


def test_multi_goal_match_averages_confidence():
    """Hit a strong cluster set that triggers two distinct goals at different scores."""
    # WEIGHT_MGMT: req fat_metabolism+blood_sugar, weights 1.0+0.9+0.7+0.5+0.6+0.4 = 4.1
    # Hit fat_metabolism + blood_sugar + thyroid + energy + pre_workout = 1.0+0.9+0.7+0.5+0.6 = 3.7
    #   → 3.7/4.1 = 0.902, no blocked → MATCH
    # BLOOD_SUGAR_SUPPORT: req blood_sugar, weights 1.0+0.6+0.5+0.5+0.4+0.4 = 3.4
    # Hit blood_sugar + energy + thyroid + fat_metabolism = 1.0+0.6+0.5+0.5 = 2.6
    #   → 2.6/3.4 = 0.765, no blocked → MATCH
    result = compute_goal_matches(_enriched([
        "fat_metabolism", "blood_sugar_regulation", "thyroid_support",
        "energy_mitochondria", "pre_workout_energy",
    ]))
    assert "GOAL_WEIGHT_MANAGEMENT" in result["goal_matches"]
    assert "GOAL_BLOOD_SUGAR_SUPPORT" in result["goal_matches"]
    # Confidence is average of all matched scores
    assert 0.0 < result["goal_match_confidence"] <= 1.0


# ---------- Round-trip / contract ----------


def test_returns_only_documented_keys():
    result = compute_goal_matches(_enriched(["sleep_stack", "magnesium_nervous_system"]))
    assert set(result.keys()) == {"goal_matches", "goal_match_confidence"}


def test_goal_matches_is_list_and_confidence_is_float():
    result = compute_goal_matches(_enriched(["sleep_stack", "magnesium_nervous_system"]))
    assert isinstance(result["goal_matches"], list)
    assert isinstance(result["goal_match_confidence"], float)


def test_returned_goal_ids_are_canonical_flutter_ids():
    """Sanity: the matcher must never emit a non-canonical goal ID."""
    canonical = {
        "GOAL_SLEEP_QUALITY", "GOAL_REDUCE_STRESS_ANXIETY", "GOAL_INCREASE_ENERGY",
        "GOAL_DIGESTIVE_HEALTH", "GOAL_WEIGHT_MANAGEMENT", "GOAL_CARDIOVASCULAR_HEART_HEALTH",
        "GOAL_HEALTHY_AGING_LONGEVITY", "GOAL_BLOOD_SUGAR_SUPPORT", "GOAL_IMMUNE_SUPPORT",
        "GOAL_FOCUS_MENTAL_CLARITY", "GOAL_MOOD_EMOTIONAL_WELLNESS", "GOAL_MUSCLE_GROWTH_RECOVERY",
        "GOAL_JOINT_BONE_MOBILITY", "GOAL_SKIN_HAIR_NAILS", "GOAL_LIVER_DETOX",
        "GOAL_PRENATAL_PREGNANCY", "GOAL_HORMONAL_BALANCE", "GOAL_EYE_VISION_HEALTH",
    }
    # Try a variety of cluster sets to maximize coverage
    cluster_sets = [
        ["sleep_stack", "magnesium_nervous_system"],
        ["fat_metabolism", "blood_sugar_regulation", "thyroid_support"],
        ["liver_support", "detox_pathway", "antioxidant_defense"],
        ["eye_health", "antioxidant_defense", "omega_3_absorption_enhancement"],
        ["hormone_balance_men", "hormone_balance_women", "thyroid_support",
         "menopause_perimenopause_support"],
    ]
    for cs in cluster_sets:
        result = compute_goal_matches(_enriched(cs))
        for gid in result["goal_matches"]:
            assert gid in canonical, f"Non-canonical goal ID in result: {gid!r}"


# ---------- Cache behavior (sanity) ----------


def test_cache_is_lazily_populated_and_consistent():
    """Two consecutive calls should yield the same result (cache hit on the
    second call)."""
    enriched = _enriched(["sleep_stack", "magnesium_nervous_system"])
    a = compute_goal_matches(enriched)
    b = compute_goal_matches(enriched)
    assert a == b
