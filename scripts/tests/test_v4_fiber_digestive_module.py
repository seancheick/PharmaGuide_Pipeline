"""Fiber/digestive v4 module calibration tests.

The fiber category should not be scored as a generic capsule. A well-labeled
psyllium/acacia fiber should be able to score strongly, while underdosed gummies
or stimulant-laxative blends should remain low.
"""

from __future__ import annotations

import pytest

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from score_supplements_v4 import score_product_v4  # noqa: E402
from scoring_v4.modules.fiber_digestive import score_fiber_digestive  # noqa: E402
from scoring_v4.modules.fiber_digestive_dose import score_dose  # noqa: E402


def _row(
    canonical_id: str,
    quantity: float,
    unit: str = "Gram(s)",
    *,
    name: str | None = None,
    category: str = "fiber",
    bio_score: float = 12.0,
    proprietary: bool = False,
) -> dict:
    label = name or canonical_id.replace("_", " ").title()
    return {
        "name": label,
        "standard_name": label,
        "canonical_id": canonical_id,
        "quantity": quantity,
        "unit": unit,
        "unit_normalized": unit.lower(),
        "category": category,
        "bio_score": bio_score,
        "matched_form": label.lower(),
        "raw_source_text": label,
        "mapped": True,
        "mapped_identity": True,
        "scoreable_identity": True,
        "score_eligible_by_cleaner": True,
        "role_classification": "active_scorable",
        "cleaner_row_role": "active_scorable",
        "source_section": "active",
        "is_proprietary_blend": proprietary,
        "is_parent_total": False,
    }


def _match(
    *,
    ingredient: str = "Psyllium",
    canonical_id: str = "psyllium",
    study_type: str = "rct_multiple",
    evidence_level: str = "ingredient-human",
) -> dict:
    return {
        "id": f"INGR_{canonical_id.upper()}",
        "ingredient": ingredient,
        "standard_name": ingredient,
        "canonical_id": canonical_id,
        "study_type": study_type,
        "evidence_level": evidence_level,
        "effect_direction": "positive_strong",
        "total_enrollment": 500,
    }


def _fiber_product(
    rows: list[dict],
    *,
    name: str = "PharmaGuide Benchmark Psyllium Fiber",
    dietary_fiber_g: float | None = 8.0,
    sugar: dict | None = None,
    sweeteners: dict | None = None,
    additives: list[dict] | None = None,
    matches: list[dict] | None = None,
) -> dict:
    return {
        "servingSizes": [{"quantity": 1, "unit": "scoop", "minDailyServings": 1, "maxDailyServings": 1}],
        "id": 910001,
        "dsld_id": "910001",
        "fullName": name,
        "product_name": name,
        "brandName": "PharmaGuide Benchmark",
        "primary_type": "fiber_digestive",
        "supplement_taxonomy": {
            "primary_type": "fiber_digestive",
            "percentile_category": "fiber_digestive",
        },
        "form_factor": "powder",
        "form_factor_canonical": "powder",
        "status": "active",
        "ingredient_quality_data": {
            "ingredients_scorable": rows,
            "ingredients": rows,
        },
        "nutrition_summary": {
            "dietary_fiber_g": dietary_fiber_g,
            "dietary_fiber_source": {"amount": dietary_fiber_g, "unit": "g", "raw_source_path": "ingredientRows[0]",
                                     "quantityVariants": [{"quantity": dietary_fiber_g, "unit": "g", "operator": "="}]},
            "total_sugars_g": 0.0 if sugar is None else sugar.get("amount_g"),
        },
        "nutrition_detail": {
            "dietary_fiber_g": dietary_fiber_g,
            "dietary_fiber_source": {"amount": dietary_fiber_g, "unit": "g", "raw_source_path": "ingredientRows[0]",
                                     "quantityVariants": [{"quantity": dietary_fiber_g, "unit": "g", "operator": "="}]},
            "total_sugars_g": 0.0 if sugar is None else sugar.get("amount_g"),
        },
        "dietary_sensitivity_data": {
            "sugar": sugar
            or {
                "amount_g": 0.0,
                "level": "sugar_free",
                "contains_sugar": False,
                "has_added_sugar": False,
                "sugar_sources": [],
            },
            "sweeteners": sweeteners
            or {
                "artificial": [],
                "high_glycemic": [],
                "sugar_alcohols": [],
                "safer_alternatives": [],
            },
        },
        "contaminant_data": {
            "harmful_additives": {
                "found": bool(additives),
                "additives": additives or [],
            },
            "banned_substances": {"found": False, "substances": []},
        },
        "proprietary_blends": [],
        "proprietary_data": {"blends": [], "total_active_ingredients": len(rows)},
        "evidence_data": {"clinical_matches": matches or [_match()]},
    }


def test_clean_psyllium_fiber_routes_to_dedicated_module_and_scores_strong() -> None:
    product = _fiber_product([_row("psyllium", 8.0, name="Psyllium Husk")])

    out = score_product_v4(product)

    assert out["v4_module"] == "fiber_digestive"
    assert out["v4_breakdown"]["module"]["module"] == "fiber_digestive"
    assert out["quality_pillars_v4"]["dose"]["score"] == 11.4
    dose = out["v4_breakdown"]["module"]["dimensions"]["dose"]
    assert dose["metadata"]["method"] == "fiber_effective_dose_v1"
    assert dose["components"]["fiber_effective_dose"] == 12.54


def test_under_dosed_fiber_gummy_stays_low_despite_category_membership() -> None:
    product = _fiber_product(
        [_row("fiber", 0.8, name="Soluble Corn Fiber")],
        name="Fiber Candy Gummies",
        dietary_fiber_g=0.8,
        sugar={
            "amount_g": 6.0,
            "level": "high",
            "contains_sugar": True,
            "has_added_sugar": True,
            "sugar_sources": ["glucose syrup"],
        },
        sweeteners={
            "artificial": ["sucralose"],
            "high_glycemic": ["glucose syrup"],
            "sugar_alcohols": ["maltitol"],
            "safer_alternatives": [],
        },
        additives=[
            {
                "additive_id": "ADD_RED_40",
                "severity_level": "moderate",
                "source_section": "inactive",
            }
        ],
        matches=[],
    )

    result = score_fiber_digestive(product)
    breakdown = result.to_breakdown()

    assert breakdown["dimensions"]["dose"]["score"] == 12.54
    assert breakdown["dimensions"]["formulation"]["score"] < 30.0
    assert "fiber_gummy_delivery_penalty" not in breakdown["dimensions"]["formulation"]["penalties"]


def test_stimulant_laxative_cleanse_earns_only_its_fiber_source_quality() -> None:
    product = _fiber_product(
        [
            _row("psyllium", 2.0, name="Psyllium Husk"),
            _row("senna", 20.0, "mg", name="Senna Leaf", category="herb", bio_score=6),
            _row("cascara_sagrada", 20.0, "mg", name="Cascara Sagrada", category="herb", bio_score=6),
        ],
        name="Fiber Cleanse Detox",
        dietary_fiber_g=2.0,
        matches=[],
    )

    result = score_fiber_digestive(product)
    formulation = result.to_breakdown()["dimensions"]["formulation"]

    # V4.1 Step 4: senna (watchlist) and cascara (high risk) are charged once
    # by their banned_recalled owner through the formula-checks pillar and the
    # product safety status; Formulation no longer re-charges them by name, and
    # the stimulant herbs add no fiber quality.
    assert "fiber_stimulant_laxative_penalty" not in formulation["penalties"]
    assert "fiber_cleanse_detox_penalty" not in formulation["penalties"]
    assert set(formulation["components"]) == {"fiber_source_quality"}
    psyllium_only = score_fiber_digestive(_fiber_product(
        [_row("psyllium", 2.0, name="Psyllium Husk")],
        name="Fiber Cleanse Detox", dietary_fiber_g=2.0, matches=[],
    )).to_breakdown()["dimensions"]["formulation"]
    assert formulation["components"] == psyllium_only["components"]
    assert formulation["metadata"]["fiber_profile_applied"] is True


def test_fiber_dose_prefers_label_fiber_grams_over_active_mass_noise() -> None:
    product = _fiber_product(
        [
            _row("psyllium", 500.0, "mg", name="Psyllium Husk"),
            _row("natural_flavor", 2.0, "mg", name="Natural Flavor", category="other", bio_score=0),
        ],
        dietary_fiber_g=7.0,
    )

    dose = score_dose(product)

    assert dose["score"] == 12.54
    assert dose["metadata"]["fiber_dose_source"] == "nutrition_facts"
    assert dose["metadata"]["fiber_grams_per_serving"] == 7.0


def test_fiber_canonical_identity_has_one_declaration() -> None:
    """Routing and the fiber scorer read one fiber canonical set.

    route_features and fiber_digestive_helpers each kept an identical literal
    copy, so a canonical added to one would route a product to fiber_digestive
    without the fiber scorer recognising its rows, or the reverse. route_features
    owns it: fiber_digestive_helpers reaches scoring_input_contract through
    generic_helpers, and scoring_input_contract imports route_features, so the
    leaf module is the only owner both sides can import.
    """
    from scoring_v4 import route_features
    from scoring_v4.modules import fiber_digestive_formulation, fiber_digestive_helpers

    assert fiber_digestive_helpers.FIBER_CANONICALS is route_features.FIBER_CANONICALS
    assert route_features.MATERIAL_FIBER_CANONICALS <= route_features.FIBER_CANONICALS
    source = Path(fiber_digestive_formulation.__file__).read_text(encoding="utf-8")
    assert '{"", "fiber"}' not in source, "use fiber_digestive_helpers.COMPATIBLE_GUAR_CANONICALS"


def test_phage_title_cannot_create_a_fiber_dose():
    from scoring_v4.modules.fiber_digestive_dose import score_dose
    from scoring_v4.modules.generic_dose import score_dose as generic_dose
    product={"product_name":"Prebiotic +","primary_type":"digestive",
             "ingredient_quality_data":{"ingredients_scorable":[{"name":"PreforPro","canonical_id":"bacteriophages","quantity":15,"unit":"mg","mapped":True}]}}
    result=score_dose(product)
    assert result==generic_dose(product)
    assert "fiber_grams_daily_benchmark" not in result.get("metadata",{})


def test_incidental_nutrition_fiber_does_not_replace_digestive_ingredient_dose():
    from scoring_v4.modules.fiber_digestive_dose import score_dose
    from scoring_v4.modules.generic_dose import score_dose as generic_dose
    product = {"fullName": "Digestive Enzymes", "nutrition_summary": {"dietary_fiber_g": 1}, "activeIngredients": [{"name": "Protease", "canonical_id": "protease", "quantity": 1000, "unit": "HUT"}]}
    assert score_dose(product) == generic_dose(product)


@pytest.mark.parametrize('grams', [.25,1,3,5,7,15])
def test_reviewed_general_fiber_amount_is_not_a_clinical_dose_curve(grams):
    from scoring_v4.modules.fiber_digestive_dose import _fiber_effective_dose_points
    from scoring_v4.modules.generic_helpers import unbenchmarked_dose_credit
    assert _fiber_effective_dose_points(grams) == unbenchmarked_dose_credit()



@pytest.mark.parametrize("facts_amount", [None,8.0])
def test_missing_fiber_capture_is_not_a_completed_zero_or_neutral(facts_amount):
    from scoring_v4.scored_artifact import build_scored_artifact
    product=_fiber_product([_row("psyllium", None, name="Psyllium Husk")], dietary_fiber_g=facts_amount)
    artifact=build_scored_artifact(product)
    if facts_amount is None:
        assert artifact["quality_assessment_status"] == "partial" or artifact["quality_score_status"] == "not_scored"
    else:
        # A valid Nutrition Facts total owns aggregate fiber independently of
        # an unquantified ingredient source. Never discard that declaration.
        # This synthetic Dose fixture lacks independent completed source reviews.
        assert artifact["quality_assessment_status"] == "partial"
        assert artifact["assessment_readiness"]["release_assessment"]["is_complete"] is False
        assert artifact["quality_pillars_v4"]["dose"]["score"] == 11.4


def _fiber_with_named_vitamin(*, fiber_rows=None, vitamin_amount=1000, named=True, assessed=True):
    product = _fiber_product(
        (fiber_rows if fiber_rows is not None else [_row("psyllium", 8)])
        + [_row("vitamin_c", vitamin_amount, "mg", name="Vitamin C", category="vitamin")],
        name="Psyllium + Vitamin C" if named else "Psyllium Fiber",
    )
    product["rda_ul_data"] = {"adequacy_results": [{
        "nutrient": "Vitamin C", "canonical_id": "vitamin_c", "amount": 1000,
        "unit": "mg", "pct_rda": 1000 / 90 * 100, "rda_ai": 90, "scoring_eligible": True,
    }] if assessed else [], "safety_flags": []}
    return product


@pytest.mark.parametrize("fibers", [[_row("psyllium", 8)],
                                    [_row("psyllium", 4), _row("acacia", 4)],
                                    [_row("psyllium", None)]])
def test_fiber_aggregate_and_named_nutrient_each_keep_one_public_purpose_vote(fibers):
    from scoring_v4.scored_artifact import build_scored_artifact

    artifact = build_scored_artifact(_fiber_with_named_vitamin(fiber_rows=fibers))
    # This synthetic Dose fixture lacks independent completed source reviews.
    assert artifact["quality_assessment_status"] == "partial"
    assert artifact["assessment_readiness"]["release_assessment"]["is_complete"] is False
    dose = artifact["quality_pillars_v4"]["dose"]
    assert dose["score"] == 15.7
    receipt = dose["explanation"]["dose_receipt"]
    assert receipt["aggregation"] == "declared_purpose_equal_weight"
    assert len(receipt["contributions"]) == 2
    assert sorted(entry["points"] for entry in receipt["contributions"]) == [11.4, 20]
    assert receipt["reconciles"] is True


def test_incidental_nutrient_does_not_enter_fiber_purpose_average():
    from scoring_v4.scored_artifact import build_scored_artifact

    artifact = build_scored_artifact(_fiber_with_named_vitamin(named=False))
    dose = artifact["quality_pillars_v4"]["dose"]
    assert dose["score"] == 11.4
    assert len(dose["explanation"]["dose_receipt"]["contributions"]) == 1


def test_missing_named_nutrient_amount_cannot_hide_behind_qualified_fiber_facts():
    from scoring_v4.scored_artifact import build_scored_artifact

    artifact = build_scored_artifact(_fiber_with_named_vitamin(vitamin_amount=None, assessed=False))
    assert artifact["quality_assessment_status"] == "partial" or artifact["quality_score_status"] == "not_scored"


@pytest.mark.parametrize("hidden", [False, True])
def test_fiber_keeps_each_declared_unbenchmarked_or_hidden_peer_at_neutral(hidden):
    from scoring_v4.scored_artifact import build_scored_artifact

    peer = _row("l_theanine", None if hidden else 100, "mg", name="L-Theanine", category="amino acid")
    if hidden:
        peer.update(isNestedIngredient=True, parentBlend="Calm Blend", is_proprietary_blend=True)
    product = _fiber_product([_row("psyllium", 8), peer], name="Psyllium + L-Theanine")
    artifact = build_scored_artifact(product)
    if not hidden:
        # This synthetic Dose fixture lacks independent completed source reviews.
        assert artifact["quality_assessment_status"] == "partial"
        assert artifact["assessment_readiness"]["release_assessment"]["is_complete"] is False
    # This compatibility fixture has no typed source-dose collection. Keep its
    # independent readiness result while checking the completed Dose vote.
    module_dose = artifact["_v4_module_breakdown"]["dimensions"]["dose"]
    assert module_dose["metadata"].get("assessment_status") != "incomplete"
    dose = artifact["quality_pillars_v4"]["dose"]
    assert dose["score"] == 11.4
    receipt = dose["explanation"]["dose_receipt"]
    assert len(receipt["contributions"]) == 2
    theanine = next(entry for entry in receipt["contributions"] if entry["ingredient"] == "l_theanine")
    assert theanine["assessment"] == ("hidden_amount_neutral" if hidden else "no_benchmark_neutral")
    assert receipt["reconciles"] is True


def test_fiber_does_not_drop_an_unresolved_declared_group_entry():
    from scoring_v4.scored_artifact import build_scored_artifact

    product = _fiber_product([
        _row("psyllium", 8),
        _row("l_leucine", None, "mg", name="L-Leucine", category="amino acid"),
        _row("l_isoleucine", 1000, "mg", name="L-Isoleucine", category="amino acid"),
        _row("l_valine", 1000, "mg", name="L-Valine", category="amino acid"),
    ], name="Psyllium + BCAA")
    assert score_dose(product)["score"] is None
    artifact = build_scored_artifact(product)
    assert artifact["quality_assessment_status"] == "partial" or artifact["quality_score_status"] == "not_scored"


@pytest.mark.parametrize('unit', ['NP', '', 'scoop'])
def test_fiber_cannot_hide_a_named_peer_with_an_unusable_unit(unit):
    from scoring_v4.scored_artifact import build_scored_artifact
    product = _fiber_with_named_vitamin(assessed=False)
    product['ingredient_quality_data']['ingredients_scorable'][-1].update(unit=unit, unit_normalized=unit.lower())
    artifact = build_scored_artifact(product)
    assert artifact['quality_assessment_status'] == 'partial' or artifact['quality_score_status'] == 'not_scored'
    dose = artifact['_v4_module_breakdown']['dimensions']['dose']
    assert dose['score'] is None
    assert dose['metadata']['reason_code'] == 'unresolved_source_quantity'
