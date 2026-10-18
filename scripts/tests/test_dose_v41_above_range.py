"""Dose V4.1 §2.2-2.4 applied to the remaining excess paths.

* The highest studied dose establishes no upper limit: above it, adequacy
  plateaus (generic clinical and aggregate-formula benchmarks).
* An exposure is reduced once, by the product-level ceiling: immune support no
  longer zeroes zinc or vitamin D at their adult ULs (40 mg, 100 mcg).
* A hidden botanical amount takes the shared neutral even when a studied range
  exists; Transparency keeps the disclosure consequence."""
import json

import pytest

from test_bcaa_clinical_evidence_contract import DATA_PATH, _active, _scoring_product
from test_v4_botanical_profile import _botanical_ingredient, _botanical_product
from scoring_v4.modules.generic_dose import score_dose
from scoring_v4.modules.botanical_profile import score_botanical_dose
from scoring_v4.modules.generic_helpers import unbenchmarked_dose_credit


def test_aggregate_formula_regimens_do_not_infer_a_general_dose_window():
    entries = {entry["id"]: entry for entry in json.loads(DATA_PATH.read_text())["backed_clinical_studies"]}
    match = dict(entries["INGR_BRANCHED_CHAIN_AMINO_ACIDS"])
    match.update({"matched_term": "Branched Chain Amino Acids", "ingredient": "Branched Chain Amino Acids"})
    payload = score_dose(_scoring_product(
        [_active("l_leucine", 45000), _active("l_isoleucine", 22500), _active("l_valine", 22500)], match))
    assert "aggregate_dose_band" not in payload["metadata"]
    assert payload["components"]["supplemental_window_proxy"] == unbenchmarked_dose_credit()


def _immune(zinc_mg, servings=1):
    from test_daily_serving_multiplier_guard import _row
    rows = [_row("Zinc", "zinc", zinc_mg, "mg"), _row("Vitamin C", "vitamin_c", 500, "mg")]
    return {"primary_type": "immune_support",
            "ingredient_quality_data": {"ingredients_scorable": rows, "ingredients": rows},
            "rda_ul_data": {"adequacy_results": [
                {"nutrient": "Zinc", "canonical_id": "zinc", "pct_rda": zinc_mg / 11 * 100},
                {"nutrient": "Vitamin C", "canonical_id": "vitamin_c", "pct_rda": 500 / 90 * 100},
            ]},
            "servingSizes": [{"minDailyServings": 1, "maxDailyServings": servings}]}


def test_immune_zinc_at_its_ul_is_not_zeroed_a_second_time():
    from scoring_v4.modules.immune_support import score_immune_support_dose
    over = score_immune_support_dose(_immune(50))
    within = score_immune_support_dose(_immune(20))
    assert over["metadata"]["high_zinc"] is True
    # Nutritional adequacy plateaus; the UL is the ceiling's alone.
    assert over["components"]["zinc_daily_range"] == 3.0
    assert over["components"]["daily_use_discipline"] == within["components"]["daily_use_discipline"]


@pytest.mark.parametrize("active,name,unit,amount,ul", [
    ("zinc", "Zinc", "mg", 50.0, 40.0),
    ("vitamin_d3", "Vitamin D3", "mcg", 125.0, 100.0),
])
@pytest.mark.parametrize("vitamin_c_mg,expected", [(5.0, 10.0), (500.0, 10.0)])
def test_immune_purpose_excess_is_reduced_only_by_final_ceiling(
    active, name, unit, amount, ul, vitamin_c_mg, expected,
):
    from test_daily_serving_multiplier_guard import _row
    from scoring_v4.modules.immune_support import score_immune_purpose_dose
    from scoring_v4.scored_artifact import build_scored_artifact

    rows = [_row(name, active, amount, unit), _row("Vitamin C", "vitamin_c", vitamin_c_mg, "mg")]
    product = {
        "product_name": f"{name} and Vitamin C Immune Support",
        "primary_type": "immune_support",
        "ingredient_quality_data": {"ingredients_scorable": rows, "ingredients": rows},
        "servingSizes": [{"minDailyServings": 1, "maxDailyServings": 1}],
        "rda_ul_data": {"adequacy_results": [
            {"nutrient": name, "canonical_id": active, "pct_rda": 500, "scoring_eligible": True},
            {"nutrient": "Vitamin C", "canonical_id": "vitamin_c", "pct_rda": vitamin_c_mg / 90 * 100, "scoring_eligible": True},
        ], "safety_flags": [{
            "nutrient": name, "canonical_id": active, "pct_ul": amount / ul * 100,
            "ul": ul, "unit": unit, "ul_gate_eligible": True,
        }]},
    }
    # A confirmed UL exceedance must not reduce individual adequacy before aggregation.
    assert score_immune_purpose_dose(product, rows[0])["score"] == 22.0
    artifact = build_scored_artifact(product)
    assert artifact["quality_score_status"] == "scored"
    dose = artifact["quality_pillars_v4"]["dose"]
    assert dose["score"] == expected
    receipt = dose["explanation"]["dose_receipt"]
    assert receipt["upper_reference"]["pct_ul"] == 125.0
    assert receipt["adequacy_before_safety"] == (11.4 if vitamin_c_mg == 5 else 20.0)
    assert receipt["reconciles"] is True


@pytest.mark.parametrize("active,name,amount_mcg", [
    ("vitamin_d3", "Vitamin D3", 25.0), ("selenium", "Selenium", 55.0),
])
@pytest.mark.parametrize("unit,factor", [("mcg", 1.0), ("mg", 1000.0), ("g", 1000000.0)])
def test_immune_microgram_purposes_keep_equivalent_unit_exposure(active, name, amount_mcg, unit, factor):
    from test_daily_serving_multiplier_guard import _row
    from scoring_v4.modules.immune_support import score_immune_purpose_dose, immune_active_doses
    from scoring_v4.scored_artifact import build_scored_artifact

    def product(quantity, quantity_unit):
        rows = [_row(name, active, quantity, quantity_unit)]
        return {"product_name": f"{name} Immune Support", "primary_type": "immune_support",
                "ingredient_quality_data": {"ingredients_scorable": rows, "ingredients": rows},
                "servingSizes": [{"minDailyServings": 1, "maxDailyServings": 1}]}

    candidate = product(amount_mcg / factor, unit)
    baseline = product(amount_mcg, "mcg")
    candidate_row = candidate["ingredient_quality_data"]["ingredients"][0]
    baseline_row = baseline["ingredient_quality_data"]["ingredients"][0]
    assert immune_active_doses(candidate) == immune_active_doses(baseline)
    assert score_immune_purpose_dose(candidate, candidate_row) == score_immune_purpose_dose(baseline, baseline_row)
    candidate_dose = build_scored_artifact(candidate)["quality_pillars_v4"]["dose"]
    baseline_dose = build_scored_artifact(baseline)["quality_pillars_v4"]["dose"]
    assert candidate_dose["score"] == baseline_dose["score"]


@pytest.mark.parametrize("active,mg", [("vitamin_c", 500.0), ("zinc", 15.0), ("copper", 1.0),
                                      ("beta_glucan", 250.0), ("quercetin", 500.0), ("elderberry", 300.0)])
def test_immune_milligram_purposes_keep_equivalent_units(active, mg):
    from scoring_v4.modules.immune_support import _row_amount
    assert _row_amount({"quantity": mg, "unit": "mg"}, active) == mg
    assert _row_amount({"quantity": mg / 1000.0, "unit": "g"}, active) == mg
    assert _row_amount({"quantity": mg * 1000.0, "unit": "mcg"}, active) == mg


@pytest.mark.parametrize("ingredient,band", [
    (_botanical_ingredient(quantity=0, unit="", isNestedIngredient=True), "primary_no_dose"),
    (_botanical_ingredient(quantity=500, scoring_input_kind="product_level_evidence",
                           evidence_type="blend_anchor_mass"), "blend_total_only"),
])
def test_hidden_botanical_amount_with_a_studied_range_takes_the_neutral(ingredient, band):
    out = score_botanical_dose(_botanical_product(ingredient=ingredient))
    assert out["band"] == band and out["metadata"]["benchmark"] == "absent"
    assert out["score"] == pytest.approx(unbenchmarked_dose_credit())
