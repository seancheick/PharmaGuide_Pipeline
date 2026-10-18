"""Wave 6 sports v4 dose rubric tests."""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scoring_v4.modules.sports_dose import score_dose
from scoring_v4.modules.sports_helpers import (
    dose_g,
    group_bcaa,
    group_eaa,
    pre_workout_goal_cluster_ids,
    primary_sports_identity,
    sports_identity_rows,
    sports_dosed_rows,
    sports_subtype,
)


def _row(
    canonical_id: str,
    quantity: float,
    unit: str,
    *,
    name: str | None = None,
    bio_score: float = 12.0,
) -> dict:
    return {
        "name": name or canonical_id.replace("_", " ").title(),
        "standard_name": name or canonical_id.replace("_", " ").title(),
        "canonical_id": canonical_id,
        "quantity": quantity,
        "unit": unit,
        "bio_score": bio_score,
        "mapped": True,
        "mapped_identity": True,
        "scoreable_identity": True,
        "score_eligible_by_cleaner": True,
        "role_classification": "active_scorable",
        "cleaner_row_role": "active_scorable",
        "dose_class": "therapeutic_mass",
        "source_section": "activeIngredients",
        "raw_source_path": f"activeIngredients[{canonical_id}]",
    }


def _declared_protein_row(grams: float) -> dict:
    return {**_row("protein", grams, "g", name="Protein"),
            "scoring_input_kind": "product_level_evidence", "evidence_type": "sports_primary_dose",
            "reason": "declared_nutrition_protein_mass"}


def _product(*rows: dict, name: str = "Sports Product", primary_type: str = "amino_acid") -> dict:
    return {
        "servingSizes": [{"quantity": 1, "unit": "scoop", "minDailyServings": 1, "maxDailyServings": 1}],
        "fullName": name,
        "product_name": name,
        "primary_type": primary_type,
        "supplement_taxonomy": {"primary_type": primary_type},
        "ingredient_quality_data": {"ingredients_scorable": list(rows)},
    }


def test_dose_g_normalizes_grams_and_milligrams() -> None:
    assert dose_g(_row("creatine_monohydrate", 3, "Gram(s)")) == pytest.approx(3.0)
    assert dose_g(_row("creatine_monohydrate", 5000, "mg")) == pytest.approx(5.0)
    assert dose_g(_row("creatine_monohydrate", 5000000, "mcg")) == pytest.approx(5.0)


def test_sports_rows_filters_incidental_minerals() -> None:
    product = _product(
        _row("calcium", 200, "mg"),
        _row("vitamin_d", 20, "mcg"),
        _row("creatine_monohydrate", 5, "Gram(s)"),
    )

    assert [row["canonical_id"] for row in sports_dosed_rows(product)] == ["creatine_monohydrate"]


def test_sports_identity_rows_preserve_undosed_sports_actives() -> None:
    product = _product(
        {
            **_row("creatine_monohydrate", 0, "Gram(s)"),
            "quantity": None,
            "unit": None,
        },
        _row("calcium", 200, "mg"),
        name="Creatine Monohydrate",
    )

    assert [row["canonical_id"] for row in sports_identity_rows(product)] == ["creatine_monohydrate"]
    assert sports_dosed_rows(product) == []
    assert primary_sports_identity(product) == "creatine"


def test_group_bcaa_totals_ratio_and_components() -> None:
    product = _product(
        _row("l_leucine", 5, "Gram(s)"),
        _row("l_isoleucine", 2.5, "Gram(s)"),
        _row("l_valine", 2.5, "Gram(s)"),
    )

    grouped = group_bcaa(sports_dosed_rows(product))

    assert grouped["complete"] is True
    assert grouped["total_g"] == pytest.approx(10.0)
    assert grouped["ratio"] == pytest.approx((2.0, 1.0, 1.0))


def test_group_eaa_treats_six_to_eight_essential_amino_acids_as_partial() -> None:
    product = _product(
        _row("l_histidine", 500, "mg"),
        _row("l_isoleucine", 500, "mg"),
        _row("l_leucine", 1000, "mg"),
        _row("l_lysine", 500, "mg"),
        _row("l_phenylalanine", 500, "mg"),
        _row("l_threonine", 500, "mg"),
    )

    grouped = group_eaa(sports_dosed_rows(product))

    assert grouped["complete"] is False
    assert grouped["partial"] is True
    assert grouped["count"] == 6
    assert grouped["total_g"] == pytest.approx(3.5)


def test_group_eaa_requires_all_nine_for_full_completeness() -> None:
    product = _product(
        _row("l_histidine", 500, "mg"),
        _row("l_isoleucine", 500, "mg"),
        _row("l_leucine", 1000, "mg"),
        _row("l_lysine", 500, "mg"),
        _row("methionine", 500, "mg"),
        _row("l_phenylalanine", 500, "mg"),
        _row("l_threonine", 500, "mg"),
        _row("l_tryptophan", 500, "mg"),
        _row("l_valine", 500, "mg"),
    )

    grouped = group_eaa(sports_dosed_rows(product))

    assert grouped["complete"] is True
    assert grouped["partial"] is False
    assert grouped["count"] == 9
    assert grouped["total_g"] == pytest.approx(5.0)


def test_primary_identity_prefers_creatine_single() -> None:
    product = _product(_row("creatine_monohydrate", 3, "Gram(s)"), name="Creatine Monohydrate")

    assert primary_sports_identity(product) == "creatine"


def test_sports_subtype_detects_creatine() -> None:
    product = _product(_row("creatine_monohydrate", 5, "Gram(s)"), name="Creatine Monohydrate")

    assert sports_subtype(product) == "creatine"


def test_no_sports_category_can_cap_the_public_score() -> None:
    """The public score is the literal six-pillar sum (locked 2026-09-21).

    Sports subtypes remain an informational annotation; opacity, stimulant risk
    and evidence breadth are already owned by Transparency, Safety and Evidence.
    """
    import scoring_v4.modules.sports_helpers as helpers

    assert not hasattr(helpers, "sports_public_quality_cap")


def test_sports_subtype_detects_transparent_preworkout() -> None:
    product = _product(
        _row("beta-alanine", 3200, "mg"),
        _row("l_citrulline", 6000, "mg", name="Citrulline Malate"),
        _row("betaine_anhydrous", 2500, "mg"),
        _row("caffeine", 150, "mg", name="Caffeine Anhydrous"),
        name="Vector Pre-Workout Tested",
        primary_type="pre_workout",
    )

    assert sports_subtype(product) == "pre_workout"


def test_opaque_stimulant_preworkout_is_classified_as_stimulant() -> None:
    product = {
        "fullName": "MegaPump Pre-Workout",
        "product_name": "MegaPump Pre-Workout",
        "primary_type": "pre_workout",
        "supplement_taxonomy": {"primary_type": "pre_workout"},
        "ingredient_quality_data": {"ingredients_scorable": []},
        "proprietary_blends": [{"name": "Stimulant Blend", "disclosure_level": "none"}],
    }

    assert sports_subtype(product) == "stimulant_fat_burner"


def test_preworkout_goal_clusters_require_dosed_anchors_for_supported_goals() -> None:
    adequate = _product(
        _row("beta-alanine", 3200, "mg"),
        _row("l_citrulline", 6000, "mg", name="Citrulline Malate"),
        _row("caffeine", 150, "mg"),
        name="Vector Pre-Workout Tested",
        primary_type="pre_workout",
    )
    underdosed = _product(
        _row("beta-alanine", 800, "mg"),
        _row("l_citrulline", 1000, "mg", name="Citrulline Malate"),
        _row("caffeine", 50, "mg"),
        name="Vector Pre-Workout Tested",
        primary_type="pre_workout",
    )

    assert pre_workout_goal_cluster_ids(adequate, enforce_dose_gate=True) == {
        "pre_workout_energy",
        "pre_post_workout",
        "muscle_building_recovery",
    }
    assert pre_workout_goal_cluster_ids(underdosed, enforce_dose_gate=True) == set()
    assert pre_workout_goal_cluster_ids(underdosed, enforce_dose_gate=False) == {
        "pre_workout_energy",
        "pre_post_workout",
        "muscle_building_recovery",
    }


def test_creatine_three_grams_scores_primary_dose_max() -> None:
    payload = score_dose(_product(_row("creatine_monohydrate", 3, "Gram(s)"), name="Creatine Monohydrate"))

    # V4.1 Step 4: a single-active completion bonus is retired; the primary
    # dose is the whole assessment (sports Dose reference 20).
    assert payload["score"] == pytest.approx(20.0)
    assert payload["components"]["sports_primary_active_dose"] == pytest.approx(20.0)
    assert "sports_focused_single_completion" not in payload["components"]
    assert payload["metadata"]["primary_identity"] == "creatine"
    assert payload["metadata"]["dose_basis"] == "creatine_contribution_policy"


def test_creatine_without_dose_preserves_identity_diagnostic() -> None:
    row = {
        **_row("creatine_monohydrate", 0, "Gram(s)"),
        "quantity": None,
        "unit": None,
    }
    payload = score_dose(_product(row, name="Creatine Monohydrate"))

    assert payload["score"] is None
    assert payload["metadata"]["assessment_status"] == "incomplete"
    assert payload["metadata"]["primary_identity"] == "creatine"
    assert payload["metadata"]["dose_basis"] == "creatine_no_dose"
    assert payload["metadata"]["not_evaluable_reason"] == "creatine_no_dose"


def test_creatine_five_grams_scores_primary_dose_max() -> None:
    payload = score_dose(_product(_row("creatine_monohydrate", 5000, "mg"), name="Creatine Monohydrate"))

    assert payload["components"]["sports_primary_active_dose"] == pytest.approx(20.0)
    assert payload["score"] == pytest.approx(20.0)


def test_creatine_hmb_stack_scores_the_same_as_its_primary_active() -> None:
    payload = score_dose(
        _product(
            _row("creatine_monohydrate", 5, "Gram(s)"),
            _row("hmb", 3, "Gram(s)", name="HMB-Ca"),
            name="Creatine HMB",
        )
    )

    assert payload["components"]["sports_primary_active_dose"] == pytest.approx(20.0)
    assert "sports_focused_single_completion" not in payload["components"]
    # No stack-support presence credit either: adding HMB adds no points.
    assert "sports_stack_support" not in payload["components"]
    assert payload["score"] == pytest.approx(20.0)


def test_creatine_above_ten_grams_plateaus() -> None:
    # Dose V4.1 D3: exceeding a studied range is not a reduction.
    payload = score_dose(_product(_row("creatine_monohydrate", 12, "Gram(s)"), name="Creatine Monohydrate"))

    assert payload["components"]["sports_primary_active_dose"] == pytest.approx(20.0)
    assert payload["metadata"]["dose_basis"] == "creatine_contribution_policy"


def test_whey_twenty_two_grams_uses_protein_serving_not_minerals() -> None:
    payload = score_dose(
        _product(
            _row("calcium", 25, "mg"),
            _row("iron", 1, "mg"),
            _row("whey_protein", 30, "Gram(s)", name="Whey Protein Isolate"),
            _declared_protein_row(22.5),
            name="Whey Protein Isolate",
            primary_type="protein_powder",
        )
    )

    assert payload["components"]["sports_primary_active_dose"] == pytest.approx(20.0)
    assert payload["metadata"]["primary_identity"] == "protein"
    assert payload["metadata"]["dose_basis"] == "protein_contribution_policy"


def test_casein_five_grams_uses_actual_protein_contribution() -> None:
    payload = score_dose(
        _product(
            _row("casein", 6, "Gram(s)", name="Micellar Casein"),
            _declared_protein_row(5),
            name="Micellar Casein Protein",
            primary_type="protein_powder",
        )
    )

    assert payload["components"]["sports_primary_active_dose"] == pytest.approx(5.0)
    assert payload["metadata"]["primary_identity"] == "protein"
    assert payload["metadata"]["dose_basis"] == "protein_contribution_policy"


def test_beta_alanine_three_point_two_grams_scores_below_max_band() -> None:
    payload = score_dose(_product(_row("beta-alanine", 3200, "mg"), name="Beta-Alanine"))

    assert payload["components"]["sports_primary_active_dose"] == pytest.approx(16.0)
    assert payload["metadata"]["primary_identity"] == "beta_alanine"


def test_hmb_three_grams_scores_primary_dose_max() -> None:
    payload = score_dose(_product(_row("hmb", 3, "Gram(s)", name="HMB-Ca"), name="HMB"))

    assert payload["components"]["sports_primary_active_dose"] == pytest.approx(20.0)
    assert "sports_focused_single_completion" not in payload["components"]
    assert payload["score"] == pytest.approx(20.0)
    assert payload["metadata"]["primary_identity"] == "hmb"
    assert payload["metadata"]["dose_basis"] == "hmb_contribution_policy"


def test_hmb_one_point_five_to_three_grams_scores_partial() -> None:
    payload = score_dose(_product(_row("hmb", 1500, "mg", name="HMB-Ca"), name="HMB"))

    assert payload["components"]["sports_primary_active_dose"] == pytest.approx(10.0)
    assert payload["metadata"]["dose_basis"] == "hmb_contribution_policy"


def test_preworkout_ignores_tiny_accessory_creatine_when_beta_alanine_is_better_anchor() -> None:
    payload = score_dose(
        _product(
            _row("beta-alanine", 3200, "mg"),
            _row("creatine_monohydrate", 100, "mg"),
            _row("l_leucine", 3000, "mg"),
            _row("l_isoleucine", 1000, "mg"),
            _row("l_valine", 1000, "mg"),
            name="RapidDrive Pre-Workout Amino Complex",
        )
    )

    # The BCAA preparation contributes one completed neutral vote; the tiny
    # creatine accessory remains excluded.
    assert payload["components"]["sports_primary_active_dose"] == pytest.approx((16 + 11.4) / 2, abs=.0001)
    assert [c["ingredient"] for c in payload["metadata"]["dose_contributions"]] == ["beta_alanine", "bcaa"]
    assert payload["metadata"]["primary_identity"] == "beta_alanine"
    assert payload["metadata"]["dose_basis"] == "beta_alanine_contribution_policy"


def test_citrulline_malate_six_grams_is_completed_neutral() -> None:
    payload = score_dose(_product(_row("l_citrulline", 6000, "mg", name="L-Citrulline Malate"), name="Citrulline Malate"))

    assert payload["components"]["sports_primary_active_dose"] == pytest.approx(11.4)
    assert payload["metadata"]["primary_identity"] == "citrulline"
    assert payload["metadata"]["dose_basis"] == "citrulline_completed_no_general_benchmark"


def test_focused_citrulline_studied_regimen_is_completed_neutral() -> None:
    payload = score_dose(
        _product(
            _row("l_citrulline", 8000, "mg", name="L-Citrulline Malate"),
            name="Citrulline Malate",
        )
    )

    assert payload["components"]["sports_primary_active_dose"] == pytest.approx(11.4)
    assert "sports_focused_single_completion" not in payload["components"]
    assert payload["score"] == pytest.approx(11.4)


def test_bcaa_2_1_1_ratio_remains_descriptive() -> None:
    payload = score_dose(
        _product(
            _row("l_leucine", 5, "Gram(s)"),
            _row("l_isoleucine", 2.5, "Gram(s)"),
            _row("l_valine", 2.5, "Gram(s)"),
            name="Precision BCAA",
        )
    )

    assert payload["components"]["sports_primary_active_dose"] == pytest.approx(11.4)
    assert "sports_focused_single_completion" not in payload["components"]
    assert "sports_ratio_or_completeness" not in payload["components"]
    # Composition remains descriptive and adds no Dose points.
    assert payload["score"] == pytest.approx(11.4)
    assert payload["metadata"]["primary_identity"] == "bcaa"


def test_eaa_partial_profile_remains_completed_neutral_without_composition_bonus() -> None:
    payload = score_dose(
        _product(
            _row("l_histidine", 1500, "mg"),
            _row("l_isoleucine", 1500, "mg"),
            _row("l_leucine", 1500, "mg"),
            _row("l_lysine", 1500, "mg"),
            _row("l_phenylalanine", 1500, "mg"),
            _row("l_threonine", 1500, "mg"),
            name="Essential Amino Acids",
        )
    )

    assert payload["components"]["sports_primary_active_dose"] == pytest.approx(11.4)
    assert "sports_ratio_or_completeness" not in payload["components"]
    assert payload["metadata"]["primary_identity"] == "eaa"
    assert payload["metadata"]["dose_basis"] == "eaa_completed_no_general_benchmark"


def test_eaa_all_nine_with_eight_grams_is_completed_neutral() -> None:
    payload = score_dose(
        _product(
            _row("l_histidine", 900, "mg"),
            _row("l_isoleucine", 900, "mg"),
            _row("l_leucine", 1600, "mg"),
            _row("l_lysine", 900, "mg"),
            _row("methionine", 900, "mg"),
            _row("l_phenylalanine", 900, "mg"),
            _row("l_threonine", 900, "mg"),
            _row("l_tryptophan", 900, "mg"),
            _row("l_valine", 900, "mg"),
            name="Essential Amino Acids",
        )
    )

    assert payload["components"]["sports_primary_active_dose"] == pytest.approx(11.4)
    assert "sports_focused_single_completion" not in payload["components"]
    assert "sports_ratio_or_completeness" not in payload["components"]
    assert payload["score"] == pytest.approx(11.4)
    assert payload["metadata"]["primary_identity"] == "eaa"


def test_explicit_complete_eaa_aggregate_scores_one_combined_dose() -> None:
    aggregate = {
        **_row("essential_amino_acids", 10, "g", name="Essential Amino Acids"),
        "scoring_input_kind": "product_level_evidence",
        "evidence_type": "sports_primary_dose",
        "verified_child_canonicals": [
            "l_histidine",
            "l_isoleucine",
            "l_leucine",
            "l_lysine",
            "methionine",
            "l_phenylalanine",
            "l_threonine",
            "l_tryptophan",
            "l_valine",
        ],
    }

    payload = score_dose(_product(aggregate, name="EAA"))

    assert payload["components"]["sports_primary_active_dose"] == pytest.approx(11.4)
    assert "sports_ratio_or_completeness" not in payload["components"]
    assert payload["metadata"]["primary_identity"] == "eaa"
    assert payload["metadata"]["dose_basis"] == "eaa_completed_no_general_benchmark"


def test_untyped_eaa_aggregate_cannot_bypass_product_evidence_contract() -> None:
    aggregate = {
        **_row("essential_amino_acids", 10, "g", name="Essential Amino Acids"),
        "verified_child_canonicals": [
            "l_histidine",
            "l_isoleucine",
            "l_leucine",
            "l_lysine",
            "methionine",
            "l_phenylalanine",
            "l_threonine",
            "l_tryptophan",
            "l_valine",
        ],
    }

    payload = score_dose(_product(aggregate, name="EAA"))

    assert payload["components"]["sports_primary_active_dose"] == 0.0
    assert payload["metadata"].get("primary_identity") is None


def test_opaque_preworkout_without_sports_dose_is_not_evaluable_without_a_second_opacity_charge() -> None:
    product = {
        "fullName": "Pre-Workout Elite",
        "product_name": "Pre-Workout Elite",
        "primary_type": "pre_workout",
        "supplement_taxonomy": {"primary_type": "pre_workout"},
        "ingredient_quality_data": {"ingredients_scorable": []},
        "proprietary_blends": [{"name": "Performance Blend", "disclosure_level": "none"}],
    }

    payload = score_dose(product)

    # Transparency B5 owns the opacity; Dose records why it cannot assess the
    # hidden amount and supplies no substitute credit (V4.1 Step 4).
    assert payload["score"] == 0.0
    assert payload["components"]["sports_primary_active_dose"] == 0.0
    assert "opaque_primary_sports_blend" not in payload["penalties"]
    assert payload["metadata"]["not_evaluable_reason"] == "opaque_primary_sports_blend"


@pytest.mark.parametrize("canonical", ["whey_protein", "casein", "pea_protein", "rice_protein"])
def test_protein_ingredient_mass_without_actual_protein_is_incomplete(canonical):
    product = _product(_row(canonical, 30, "g"), name="Protein Powder", primary_type="protein_powder")
    payload = score_dose(product)
    assert payload["score"] is None
    assert payload["metadata"]["assessment_status"] == "incomplete"
    assert payload["metadata"]["reason_code"] == "unresolved_source_quantity"
    assert all(c.get("amount_per_serving") is None for c in payload["metadata"]["dose_contributions"])


def test_actual_protein_projection_takes_precedence_over_ingredient_mass():
    actual = {**_row("protein", 17, "g"), "scoring_input_kind": "product_level_evidence",
              "evidence_type": "sports_primary_dose", "reason": "declared_nutrition_protein_mass"}
    product = _product(_row("whey_protein", 30, "g"), actual,
                       name="Protein Powder", primary_type="protein_powder")
    payload = score_dose(product)
    assert payload["score"] == 17
    contribution = payload["metadata"]["dose_contributions"][0]
    assert contribution["amount_per_serving"] == 17


def test_hidden_protein_blend_remains_neutral_and_missing_protein_is_incomplete():
    missing = {**_row("whey_protein", None, ""), "isNestedIngredient": True}
    hidden = score_dose(_product(missing, name="Protein Powder", primary_type="protein_powder"))
    assert hidden["score"] == 11.4
    assert hidden["metadata"].get("assessment_status") != "incomplete"
    missing.pop("isNestedIngredient")
    unresolved = score_dose(_product(missing, name="Protein Powder", primary_type="protein_powder"))
    assert unresolved["score"] is None
    assert unresolved["metadata"]["assessment_status"] == "incomplete"


def test_unknown_actual_protein_keeps_strict_artifact_preliminary_without_erasing_ingredients():
    from scoring_v4.scored_artifact import build_scored_artifact, unfinished_source_assessment
    from scoring_input_contract import get_scoring_ingredients
    product = _product(_row("whey_protein", 30, "g"), name="Protein Powder", primary_type="protein_powder")
    artifact = build_scored_artifact(product)
    assert get_scoring_ingredients(product, strict=True).rows[0]["quantity"] == 30
    assert artifact["quality_score_status"] == "scored"
    assert artifact["quality_assessment_status"] == "partial"
    assert unfinished_source_assessment(product, artifact["_v4_module_breakdown"]) == "dose_amount_unread"
    assert artifact["_v4_module_breakdown"]["dimensions"]["dose"]["score"] is None
    assert artifact["quality_pillars_v4"]["formulation"]["score"] > 0
