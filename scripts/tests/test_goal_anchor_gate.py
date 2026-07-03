#!/usr/bin/env python3
"""Goal-correctness: a cluster's GOAL is claimed only when a DEFINING anchor
ingredient is adequately dosed — not when incidental broad cofactors (zinc,
selenium, copper, vitamin E, omega-3...) merely overlap.

Two axes:
  * anchor gate — a curated cluster needs an adequately-dosed *defining* actor
    (lutein for eye, milk thistle for liver, iodine for thyroid...).
  * product-intent (tier-2) — a few broad micronutrients ARE the primary actor
    for a nutrient-defined goal (zinc→immune, vit C/E→antioxidant). They claim
    the goal only when the product is FOCUSED on them (few actives), not when
    they are incidental in a loaded pre-workout or a 95-ingredient multi.

Regression for the P0 bug where a pre-workout containing only trace zinc+selenium
was mapped to eye/immune/liver/thyroid/skin/hormonal goals. Gate lives in
build_final_db._extract_product_cluster_ids (goal-emission only; does not touch
the synergy display or the A5c synergy score). Hermetic.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import build_final_db as b  # noqa: E402


def _cluster(cid, matched):
    """matched = list of (cluster_ingredient, meets_minimum)."""
    return {
        "cluster_id": cid,
        "matched_ingredients": [
            {"cluster_ingredient": ci, "meets_minimum": mm, "min_effective_dose": 15}
            for ci, mm in matched
        ],
    }


def _enriched(clusters, n_actives=8):
    """n_actives defaults to a LOADED product (>focus ceiling) so tier-2
    micronutrients read as incidental unless a test says otherwise."""
    return {
        "activeIngredients": [{"i": i} for i in range(n_actives)],
        "formulation_data": {"synergy_clusters": clusters},
    }


def _detail_cluster(cid, matched, all_adequate=1):
    """Post-build detail-blob shape: id + string matched_ingredients."""
    return {
        "id": cid,
        "matched_ingredients": list(matched),
        "all_adequate": all_adequate,
    }


def _detail_blob(clusters, raw_actives_count=8):
    return {
        "raw_actives_count": raw_actives_count,
        "ingredients": [{"i": i} for i in range(raw_actives_count)],
        "synergy_detail": {"clusters": clusters},
    }


def test_incidental_cofactors_do_not_emit_goal_clusters():
    """The exact pre-workout pathology: trace micronutrients in a LOADED product
    must NOT emit the broad goal clusters."""
    preworkout = _enriched([
        _cluster("eye_health", [("zinc", True)]),                       # zinc alone
        _cluster("immune_defense", [("zinc", True), ("selenium", True)]),
        _cluster("liver_support", [("selenium", True)]),                # selenium alone
        _cluster("thyroid_support", [("selenium", True), ("zinc", True), ("copper", True)]),
        _cluster("hair_skin_nutrition", [("zinc", True), ("copper", True)]),
        _cluster("wound_healing", [("zinc", True), ("vitamin c", True)]),
        _cluster("fertility_female", [("folate", True), ("zinc", True)]),  # folate is prenatal-anchor, NOT fertility-anchor
    ], n_actives=12)
    ids = b._extract_product_cluster_ids(preworkout, enforce_dose_gate=True)
    for bad in ("eye_health", "immune_defense", "liver_support",
                "thyroid_support", "hair_skin_nutrition", "wound_healing",
                "fertility_female"):
        assert bad not in ids, f"{bad} wrongly emitted from incidental cofactors"


def test_real_anchors_still_emit_goal_clusters():
    """No over-correction: a real anchor at dose keeps the goal, at any breadth."""
    real = _enriched([
        _cluster("eye_health", [("lutein", True), ("zinc", True)]),
        _cluster("immune_defense", [("vitamin c", True), ("zinc", True)]),
        _cluster("thyroid_support", [("iodine", True), ("selenium", True)]),
        _cluster("liver_support", [("milk thistle", True)]),
        _cluster("hair_skin_nutrition", [("collagen", True), ("vitamin c", True)]),
        _cluster("fertility_female", [("myo-inositol", True), ("coq10", True)]),
        _cluster("prenatal_pregnancy_support", [("folate", True), ("dha", True)]),
    ], n_actives=20)
    ids = b._extract_product_cluster_ids(real, enforce_dose_gate=True)
    for good in ("eye_health", "immune_defense", "thyroid_support",
                 "liver_support", "hair_skin_nutrition", "fertility_female",
                 "prenatal_pregnancy_support"):
        assert good in ids, f"{good} wrongly filtered despite a real anchor at dose"


def test_focused_micronutrient_products_keep_their_goal():
    """Product-intent: a standalone mineral/vitamin product IS that goal."""
    # "Zinc 30" — 1 active
    assert "immune_defense" in b._extract_product_cluster_ids(
        _enriched([_cluster("immune_defense", [("zinc", True)])], n_actives=1),
        enforce_dose_gate=True)
    # "Vitamin C & E" — 3 actives
    assert "antioxidant_defense" in b._extract_product_cluster_ids(
        _enriched([_cluster("antioxidant_defense", [("vitamin c", True), ("vitamin e", True)])], n_actives=3),
        enforce_dose_gate=True)
    # "Zinc Lozenges" — respiratory
    assert "respiratory_health_lung_support" in b._extract_product_cluster_ids(
        _enriched([_cluster("respiratory_health_lung_support", [("zinc", True)])], n_actives=2),
        enforce_dose_gate=True)


def test_broad_micronutrient_incidental_in_stack_is_dropped():
    """The SAME tier-2 nutrient in a LOADED product does NOT claim the goal."""
    loaded = _enriched([
        _cluster("immune_defense", [("zinc", True)]),
        _cluster("antioxidant_defense", [("vitamin e", True)]),
        _cluster("respiratory_health_lung_support", [("zinc", True)]),
    ], n_actives=9)
    ids = b._extract_product_cluster_ids(loaded, enforce_dose_gate=True)
    for bad in ("immune_defense", "antioxidant_defense", "respiratory_health_lung_support"):
        assert bad not in ids, f"{bad} wrongly kept — tier-2 nutrient was incidental"


def test_tier2_does_not_leak_to_specific_goals():
    """A focused single-nutrient product must NOT pick up a SPECIFIC goal the
    nutrient does not define (Selenium is not a liver-detox actor)."""
    ids = b._extract_product_cluster_ids(
        _enriched([_cluster("liver_support", [("selenium", True)])], n_actives=1),
        enforce_dose_gate=True)
    assert "liver_support" not in ids


def test_anchor_present_but_underdosed_is_filtered():
    """An anchor that is present but below its effective dose must not emit the
    goal (dose gate still applies to anchors)."""
    e = _enriched([_cluster("eye_health", [("lutein", False), ("zinc", True)])])
    assert "eye_health" not in b._extract_product_cluster_ids(e, enforce_dose_gate=True)


def test_uncurated_clusters_keep_legacy_behavior():
    """A cluster not in the anchor map is unchanged — any adequate match counts."""
    e = _enriched([_cluster("sleep_stack", [("magnesium", True)])])
    assert "sleep_stack" in b._extract_product_cluster_ids(e, enforce_dose_gate=True)


def test_presence_only_set_keeps_real_anchor_but_not_cofactor_only_noise():
    """The underdosed surface bypasses dose, not anchor identity.

    A real anchor below dose should be present-but-underdosed; a cofactor-only
    match should disappear entirely instead of moving to partial support.
    """
    cofactor_only = _enriched([_cluster("eye_health", [("zinc", True)])])
    assert "eye_health" not in b._extract_product_cluster_ids(
        cofactor_only,
        enforce_dose_gate=False,
    )

    real_anchor_below_dose = _enriched([
        _cluster("eye_health", [("lutein", False), ("zinc", True)])
    ])
    assert "eye_health" in b._extract_product_cluster_ids(
        real_anchor_below_dose,
        enforce_dose_gate=False,
    )


def test_detail_blob_shape_uses_id_strings_and_raw_active_count():
    """Regression for post-build detail blobs: cluster id lives in `id`, matches
    are strings, and product breadth lives in raw_actives_count/ingredients."""
    blob = _detail_blob([
        _detail_cluster("eye_health", ["Zinc"]),
        _detail_cluster("immune_defense", ["Zinc", "Selenium"]),
        _detail_cluster("liver_support", ["Selenium"]),
        _detail_cluster("hair_skin_nutrition", ["Zinc", "Copper"]),
        _detail_cluster("methylation_support", ["BetaPure", "Choline Bitartrate"]),
    ], raw_actives_count=14)

    ids = b._extract_product_cluster_ids(blob, enforce_dose_gate=True)

    for bad in ("eye_health", "immune_defense", "liver_support", "hair_skin_nutrition"):
        assert bad not in ids
    assert "methylation_support" in ids


def test_detail_blob_focused_zinc_keeps_immune_but_loaded_zinc_does_not():
    focused = _detail_blob([
        _detail_cluster("immune_defense", ["Zinc"]),
    ], raw_actives_count=1)
    loaded = _detail_blob([
        _detail_cluster("immune_defense", ["Zinc"]),
    ], raw_actives_count=9)

    assert "immune_defense" in b._extract_product_cluster_ids(
        focused,
        enforce_dose_gate=True,
    )
    assert "immune_defense" not in b._extract_product_cluster_ids(
        loaded,
        enforce_dose_gate=True,
    )


def test_detail_blob_cofactor_goals_do_not_move_to_underdosed():
    """The original pathology must not survive as partial goal support."""
    blob = _detail_blob([
        _detail_cluster("eye_health", ["Zinc"]),
        _detail_cluster("immune_defense", ["Zinc", "Selenium"]),
        _detail_cluster("liver_support", ["Selenium"]),
        _detail_cluster("hair_skin_nutrition", ["Zinc", "Copper"]),
        _detail_cluster("thyroid_support", ["Selenium", "Zinc", "Copper"]),
    ], raw_actives_count=14)

    result = b.compute_goal_matches(blob)
    noisy_goals = {
        "GOAL_EYE_VISION_HEALTH",
        "GOAL_IMMUNE_SUPPORT",
        "GOAL_LIVER_DETOX",
        "GOAL_SKIN_HAIR_NAILS",
        "GOAL_HORMONAL_BALANCE",
    }

    assert noisy_goals.isdisjoint(result["goal_matches"])
    assert noisy_goals.isdisjoint(result["goal_matches_underdosed"])


def test_detail_blob_real_anchor_below_dose_routes_to_underdosed():
    blob = _detail_blob([
        _detail_cluster("eye_health", ["Lutein", "Zinc"], all_adequate=0),
    ], raw_actives_count=2)

    result = b.compute_goal_matches(blob)
    assert "GOAL_EYE_VISION_HEALTH" not in result["goal_matches"]
    assert "GOAL_EYE_VISION_HEALTH" in result["goal_matches_underdosed"]
