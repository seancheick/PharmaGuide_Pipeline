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


def _enriched_dosed(clusters_with_doses):
    """Primary-path enrichment with per-cluster dose adequacy.

    ``clusters_with_doses`` maps cluster_id -> meets_minimum (bool). Emits the
    ``formulation_data.synergy_clusters[*].matched_ingredients[].meets_minimum``
    shape the dose gate reads, so we can exercise the
    supported-vs-present-but-underdosed split.
    """
    return {
        "formulation_data": {
            "synergy_clusters": [
                {
                    "cluster_id": cid,
                    "matched_ingredients": [
                        {"name": "magnesium", "meets_minimum": meets},
                    ],
                }
                for cid, meets in clusters_with_doses.items()
            ]
        }
    }


def _creatine_enriched(
    *,
    quantity: float = 5,
    unit: str = "Gram(s)",
    canonical_id: str = "creatine_monohydrate",
    name: str = "Creatine Monohydrate",
    bio_score: float = 14,
):
    return {
        "ingredient_quality_data": {
            "ingredients_scorable": [
                {
                    "name": name,
                    "standard_name": name,
                    "canonical_id": canonical_id,
                    "quantity": quantity,
                    "unit": unit,
                    "bio_score": bio_score,
                    "mapped": True,
                    "scoreable_identity": True,
                    "cleaner_row_role": "active_scorable",
                }
            ]
        }
    }


def _protein_enriched(
    *,
    quantity: float = 25,
    unit: str = "Gram(s)",
    canonical_id: str = "whey_protein",
    name: str = "Whey Protein Isolate",
    bio_score: float = 12,
):
    return {
        "ingredient_quality_data": {
            "ingredients_scorable": [
                {
                    "name": name,
                    "standard_name": name,
                    "canonical_id": canonical_id,
                    "quantity": quantity,
                    "unit": unit,
                    "bio_score": bio_score,
                    "mapped": True,
                    "scoreable_identity": True,
                    "cleaner_row_role": "active_scorable",
                }
            ]
        }
    }


def _fiber_enriched(
    *,
    quantity: float = 5,
    unit: str = "Gram(s)",
    canonical_id: str = "psyllium",
    name: str = "Psyllium Husk",
):
    return {
        "product_name": "Daily Psyllium Fiber",
        "supplement_taxonomy": {"primary_type": "fiber_digestive"},
        "ingredient_quality_data": {
            "ingredients_scorable": [
                {
                    "name": name,
                    "standard_name": name,
                    "canonical_id": canonical_id,
                    "quantity": quantity,
                    "unit": unit,
                    "mapped": True,
                    "scoreable_identity": True,
                    "cleaner_row_role": "active_scorable",
                }
            ]
        },
    }


def _sleep_active_enriched(
    *,
    canonical_id: str = "5_htp",
    name: str = "5-HTP",
    quantity: float = 100,
    unit: str = "mg",
):
    return {
        "supplement_taxonomy": {"primary_type": "sleep_support"},
        "ingredient_quality_data": {
            "ingredients_scorable": [
                {
                    "name": name,
                    "standard_name": name,
                    "canonical_id": canonical_id,
                    "quantity": quantity,
                    "unit": unit,
                    "bio_score": 12,
                    "mapped": True,
                    "scoreable_identity": True,
                    "cleaner_row_role": "active_scorable",
                }
            ]
        },
    }


def _joint_active_enriched(
    *,
    canonical_id: str = "glucosamine",
    name: str = "Glucosamine Sulfate",
    quantity: float = 1500,
    unit: str = "mg",
):
    return {
        "supplement_taxonomy": {"primary_type": "joint_support"},
        "ingredient_quality_data": {
            "ingredients_scorable": [
                {
                    "name": name,
                    "standard_name": name,
                    "canonical_id": canonical_id,
                    "quantity": quantity,
                    "unit": unit,
                    "bio_score": 11,
                    "mapped": True,
                    "scoreable_identity": True,
                    "cleaner_row_role": "active_scorable",
                }
            ]
        },
    }


def _preworkout_enriched(*, adequate: bool = True):
    multiplier = 1.0 if adequate else 0.25
    return {
        "product_name": "Vector Pre-Workout Tested",
        "fullName": "Vector Pre-Workout Tested",
        "supplement_taxonomy": {"primary_type": "pre_workout"},
        "ingredient_quality_data": {
            "ingredients_scorable": [
                {
                    "name": "Beta-Alanine",
                    "standard_name": "Beta-Alanine",
                    "canonical_id": "beta-alanine",
                    "quantity": 3200 * multiplier,
                    "unit": "mg",
                    "mapped": True,
                    "scoreable_identity": True,
                    "cleaner_row_role": "active_scorable",
                },
                {
                    "name": "Citrulline Malate",
                    "standard_name": "Citrulline Malate",
                    "canonical_id": "l_citrulline",
                    "quantity": 6000 * multiplier,
                    "unit": "mg",
                    "mapped": True,
                    "scoreable_identity": True,
                    "cleaner_row_role": "active_scorable",
                },
                {
                    "name": "Caffeine Anhydrous",
                    "standard_name": "Caffeine Anhydrous",
                    "canonical_id": "caffeine",
                    "quantity": 150 * multiplier,
                    "unit": "mg",
                    "mapped": True,
                    "scoreable_identity": True,
                    "cleaner_row_role": "active_scorable",
                },
            ]
        },
        # Regression shape from the sports audit: trace nutrients/adapted
        # clusters can over-promote a pre-workout to broad wellness goals.
        # Once the direct pre-workout clusters are added, goal-level
        # blocked_by rules should suppress these broad goals.
        "synergy_detail": {
            "clusters_matched": [
                "fat_metabolism",
                "immune_defense",
                "hair_skin_nutrition",
                "liver_support",
                "hormone_balance_men",
                "eye_health",
            ]
        },
    }


# ---------- Empty / degenerate inputs ----------


def test_empty_clusters_returns_empty_match():
    result = compute_goal_matches(_enriched([]))
    assert result == {
        "goal_matches": [],
        "goal_match_confidence": 0.0,
        "goal_matches_underdosed": [],
    }


def test_missing_synergy_detail_returns_empty_match():
    result = compute_goal_matches({})
    assert result == {
        "goal_matches": [],
        "goal_match_confidence": 0.0,
        "goal_matches_underdosed": [],
    }


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


def test_skin_hair_nails_matches_collagen_synthesis_support():
    """Collagen synthesis support is a direct skin/hair/nails lane.

    A clean collagen product commonly carries this cluster without the broader
    beauty-stack clusters, so it must qualify the goal by itself.
    """
    result = compute_goal_matches(_enriched(["collagen_synthesis_support"]))

    assert "GOAL_SKIN_HAIR_NAILS" in result["goal_matches"]


def test_skin_hair_nails_does_not_match_wound_healing_alone():
    """Wound-healing formulas are adjacent, not a standalone beauty-goal match."""
    result = compute_goal_matches(_enriched(["wound_healing"]))

    assert "GOAL_SKIN_HAIR_NAILS" not in result["goal_matches"]


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


def test_prenatal_required_cluster_passes_when_product_is_prenatal_positioned():
    """PRENATAL still has a high threshold, but the cluster must first survive
    the product-level prenatal gate. A product explicitly positioned as prenatal
    with prenatal anchors can claim the goal; a plain B-complex cannot."""
    result = compute_goal_matches({
        "product_name": "Prenatal Multi + DHA",
        "activeIngredients": [{"i": i} for i in range(10)],
        "supplement_taxonomy": {"primary_type": "multivitamin"},
        "formulation_data": {
            "synergy_clusters": [
                {
                    "cluster_id": "prenatal_pregnancy_support",
                    "matched_ingredients": [
                        {"cluster_ingredient": "folate", "meets_minimum": True},
                        {"cluster_ingredient": "choline", "meets_minimum": True},
                        {"cluster_ingredient": "dha", "meets_minimum": True},
                    ],
                }
            ]
        },
    })
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
    # Hit fat_metabolism + blood_sugar + thyroid + energy + recovery = 1.0+0.9+0.7+0.5+0.4 = 3.5
    #   → 3.5/4.1 = 0.854, no blocked → MATCH
    # BLOOD_SUGAR_SUPPORT: req blood_sugar, weights 1.0+0.6+0.5+0.5+0.4+0.4 = 3.4
    # Hit blood_sugar + energy + thyroid + fat_metabolism = 1.0+0.6+0.5+0.5 = 2.6
    #   → 2.6/3.4 = 0.765, no blocked → MATCH
    result = compute_goal_matches(_enriched([
        "fat_metabolism", "blood_sugar_regulation", "thyroid_support",
        "energy_mitochondria", "recovery_support",
    ]))
    assert "GOAL_WEIGHT_MANAGEMENT" in result["goal_matches"]
    assert "GOAL_BLOOD_SUGAR_SUPPORT" in result["goal_matches"]
    # Confidence is average of all matched scores
    assert 0.0 < result["goal_match_confidence"] <= 1.0


# ---------- Round-trip / contract ----------


def test_returns_only_documented_keys():
    result = compute_goal_matches(_enriched(["sleep_stack", "magnesium_nervous_system"]))
    assert set(result.keys()) == {
        "goal_matches",
        "goal_match_confidence",
        "goal_matches_underdosed",
    }


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


# ---------- goal_matches_underdosed (present-but-underdosed split) ----------
#
# A goal whose only qualifying clusters fail the dose gate (present but below
# the goal-specific effective dose) must NOT claim full support. It routes to
# the additive ``goal_matches_underdosed`` list instead — the pipeline source
# of truth for the app's "Partially supported" bucket. ``goal_matches`` keeps
# its exact prior meaning (dose-adequate support only).


def test_underdosed_cluster_routes_goal_to_underdosed_not_supported():
    """Screenshot scenario: magnesium adequate for sleep_stack (≥100 mg) but
    underdosed for stress_resilience (<200 mg). SLEEP is adequately supported;
    STRESS is present-but-underdosed."""
    result = compute_goal_matches(
        _enriched_dosed(
            {"sleep_stack": True, "stress_resilience": False}
        )
    )
    # Sleep cleared its dose gate → fully supported, never in underdosed.
    assert "GOAL_SLEEP_QUALITY" in result["goal_matches"]
    assert "GOAL_SLEEP_QUALITY" not in result["goal_matches_underdosed"]
    # Stress only qualifies on presence (its cluster failed the dose gate) →
    # present-but-underdosed, never claimed as supported.
    assert "GOAL_REDUCE_STRESS_ANXIETY" in result["goal_matches_underdosed"]
    assert "GOAL_REDUCE_STRESS_ANXIETY" not in result["goal_matches"]


def test_adequate_cluster_keeps_goal_supported_not_underdosed():
    """Same clusters, but magnesium now meets the stress dose: STRESS becomes
    fully supported and the underdosed list does not double-list it."""
    result = compute_goal_matches(
        _enriched_dosed(
            {"sleep_stack": True, "stress_resilience": True}
        )
    )
    assert "GOAL_REDUCE_STRESS_ANXIETY" in result["goal_matches"]
    assert "GOAL_REDUCE_STRESS_ANXIETY" not in result["goal_matches_underdosed"]


def test_underdosed_excludes_anything_already_supported():
    """A goal present in goal_matches is never also in goal_matches_underdosed,
    even when some of its clusters are underdosed (support already proven by an
    adequate cluster)."""
    result = compute_goal_matches(
        _enriched_dosed(
            {"sleep_stack": True, "stress_resilience": False}
        )
    )
    overlap = set(result["goal_matches"]) & set(result["goal_matches_underdosed"])
    assert overlap == set(), f"goal must not be both supported and underdosed: {overlap}"


def test_all_clusters_adequate_yields_empty_underdosed():
    """When every matched cluster clears its dose gate, the underdosed list is
    empty (nothing is present-but-underdosed)."""
    result = compute_goal_matches(
        _enriched_dosed({"sleep_stack": True, "magnesium_nervous_system": True})
    )
    assert result["goal_matches_underdosed"] == []


def test_fallback_path_without_dose_data_has_empty_underdosed():
    """Legacy fallback inputs (clusters_matched, no dose data) pass the gate
    leniently, so adequate == present and nothing is underdosed — preserving
    the prior contract for existing callers."""
    result = compute_goal_matches(_enriched(["sleep_stack"]))
    assert "GOAL_SLEEP_QUALITY" in result["goal_matches"]
    assert result["goal_matches_underdosed"] == []


def test_probiotic_product_directly_matches_digestive_health_when_dosed():
    """A well-disclosed probiotic should not need a precomputed synergy cluster
    to reach the digestive-health goal surface."""
    result = compute_goal_matches(
        {
            "probiotic_data": {
                "is_probiotic_product": True,
                "total_billion_count": 10.0,
                "total_strain_count": 3,
                "clinical_strain_count": 1,
            }
        }
    )

    assert "GOAL_DIGESTIVE_HEALTH" in result["goal_matches"]
    assert "GOAL_DIGESTIVE_HEALTH" not in result["goal_matches_underdosed"]


def test_low_cfu_probiotic_routes_digestive_health_to_underdosed():
    result = compute_goal_matches(
        {
            "probiotic_data": {
                "is_probiotic_product": True,
                "total_billion_count": 0.5,
                "total_strain_count": 3,
            }
        }
    )

    assert "GOAL_DIGESTIVE_HEALTH" not in result["goal_matches"]
    assert "GOAL_DIGESTIVE_HEALTH" in result["goal_matches_underdosed"]


def test_dosed_fiber_directly_matches_digestive_health():
    result = compute_goal_matches(_fiber_enriched(quantity=5, unit="Gram(s)"))

    assert "GOAL_DIGESTIVE_HEALTH" in result["goal_matches"]
    assert "GOAL_DIGESTIVE_HEALTH" not in result["goal_matches_underdosed"]


def test_low_dose_fiber_routes_digestive_health_to_underdosed():
    result = compute_goal_matches(_fiber_enriched(quantity=1, unit="Gram(s)"))

    assert "GOAL_DIGESTIVE_HEALTH" not in result["goal_matches"]
    assert "GOAL_DIGESTIVE_HEALTH" in result["goal_matches_underdosed"]


def test_nutrition_facts_fiber_directly_matches_digestive_health_when_contextual():
    result = compute_goal_matches(
        {
            "product_name": "Clear Mixing Fiber",
            "nutrition_detail": {"dietary_fiber_g": 5},
            "ingredient_quality_data": {"ingredients_scorable": []},
        }
    )

    assert "GOAL_DIGESTIVE_HEALTH" in result["goal_matches"]
    assert "GOAL_DIGESTIVE_HEALTH" not in result["goal_matches_underdosed"]


def test_dosed_creatine_monohydrate_directly_matches_muscle_recovery():
    """Creatine monohydrate is a focused single-ingredient sports product.
    It should not depend on a precomputed synergy cluster to reach the
    recovery goal surface."""
    result = compute_goal_matches(_creatine_enriched(quantity=5, unit="Gram(s)"))

    assert "GOAL_MUSCLE_GROWTH_RECOVERY" in result["goal_matches"]
    assert "GOAL_MUSCLE_GROWTH_RECOVERY" not in result["goal_matches_underdosed"]


def test_low_dose_creatine_routes_muscle_recovery_to_underdosed():
    result = compute_goal_matches(_creatine_enriched(quantity=1890, unit="mg"))

    assert "GOAL_MUSCLE_GROWTH_RECOVERY" not in result["goal_matches"]
    assert "GOAL_MUSCLE_GROWTH_RECOVERY" in result["goal_matches_underdosed"]


def test_creatine_ethyl_ester_does_not_get_supported_recovery_goal():
    result = compute_goal_matches(
        _creatine_enriched(
            quantity=5,
            unit="Gram(s)",
            name="Creatine Ethyl Ester",
            bio_score=4,
        )
    )

    assert "GOAL_MUSCLE_GROWTH_RECOVERY" not in result["goal_matches"]
    assert "GOAL_MUSCLE_GROWTH_RECOVERY" in result["goal_matches_underdosed"]


def test_dosed_complete_protein_directly_matches_muscle_recovery():
    result = compute_goal_matches(_protein_enriched(quantity=25, unit="Gram(s)"))

    assert "GOAL_MUSCLE_GROWTH_RECOVERY" in result["goal_matches"]
    assert "GOAL_MUSCLE_GROWTH_RECOVERY" not in result["goal_matches_underdosed"]


def test_low_dose_protein_routes_muscle_recovery_to_underdosed():
    result = compute_goal_matches(_protein_enriched(quantity=10, unit="Gram(s)"))

    assert "GOAL_MUSCLE_GROWTH_RECOVERY" not in result["goal_matches"]
    assert "GOAL_MUSCLE_GROWTH_RECOVERY" in result["goal_matches_underdosed"]


def test_collagen_does_not_inherit_complete_protein_muscle_goal():
    result = compute_goal_matches(
        _protein_enriched(
            quantity=20,
            unit="Gram(s)",
            canonical_id="protein",
            name="Hydrolyzed Collagen Peptides",
        )
    )

    assert "GOAL_MUSCLE_GROWTH_RECOVERY" not in result["goal_matches"]
    assert "GOAL_MUSCLE_GROWTH_RECOVERY" not in result["goal_matches_underdosed"]


def test_dosed_5htp_sleep_support_directly_matches_sleep_quality():
    result = compute_goal_matches(_sleep_active_enriched(quantity=100))

    assert "GOAL_SLEEP_QUALITY" in result["goal_matches"]
    assert "GOAL_SLEEP_QUALITY" not in result["goal_matches_underdosed"]


def test_low_dose_5htp_routes_sleep_quality_to_underdosed():
    result = compute_goal_matches(_sleep_active_enriched(quantity=25))

    assert "GOAL_SLEEP_QUALITY" not in result["goal_matches"]
    assert "GOAL_SLEEP_QUALITY" in result["goal_matches_underdosed"]


def test_dosed_joint_active_directly_matches_joint_bone_mobility():
    result = compute_goal_matches(_joint_active_enriched(quantity=1500))

    assert "GOAL_JOINT_BONE_MOBILITY" in result["goal_matches"]
    assert "GOAL_JOINT_BONE_MOBILITY" not in result["goal_matches_underdosed"]


def test_low_dose_joint_active_routes_joint_goal_to_underdosed():
    result = compute_goal_matches(
        _joint_active_enriched(
            canonical_id="hyaluronic_acid",
            name="Hyaluronic Acid",
            quantity=10,
        )
    )

    assert "GOAL_JOINT_BONE_MOBILITY" not in result["goal_matches"]
    assert "GOAL_JOINT_BONE_MOBILITY" in result["goal_matches_underdosed"]


def test_dosed_preworkout_matches_training_and_energy_without_broad_goal_spam():
    result = compute_goal_matches(_preworkout_enriched(adequate=True))

    assert "GOAL_INCREASE_ENERGY" in result["goal_matches"]
    assert "GOAL_MUSCLE_GROWTH_RECOVERY" in result["goal_matches"]
    for noisy_goal in {
        "GOAL_WEIGHT_MANAGEMENT",
        "GOAL_IMMUNE_SUPPORT",
        "GOAL_SKIN_HAIR_NAILS",
        "GOAL_LIVER_DETOX",
        "GOAL_HORMONAL_BALANCE",
        "GOAL_EYE_VISION_HEALTH",
    }:
        assert noisy_goal not in result["goal_matches"]


def test_low_dose_preworkout_routes_training_and_energy_to_underdosed():
    result = compute_goal_matches(_preworkout_enriched(adequate=False))

    assert "GOAL_INCREASE_ENERGY" not in result["goal_matches"]
    assert "GOAL_MUSCLE_GROWTH_RECOVERY" not in result["goal_matches"]
    assert "GOAL_INCREASE_ENERGY" in result["goal_matches_underdosed"]
    assert "GOAL_MUSCLE_GROWTH_RECOVERY" in result["goal_matches_underdosed"]
