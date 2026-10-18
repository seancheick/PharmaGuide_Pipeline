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


def test_aggregate_formula_above_its_highest_studied_dose_plateaus():
    entries = {entry["id"]: entry for entry in json.loads(DATA_PATH.read_text())["backed_clinical_studies"]}
    match = dict(entries["INGR_BRANCHED_CHAIN_AMINO_ACIDS"])
    match.update({"matched_term": "Branched Chain Amino Acids", "ingredient": "Branched Chain Amino Acids"})
    payload = score_dose(_scoring_product(
        [_active("l_leucine", 45000), _active("l_isoleucine", 22500), _active("l_valine", 22500)], match))
    assert payload["metadata"]["aggregate_dose_band"] == "above_highest_studied_dose"
    assert payload["components"]["supplemental_window_proxy"] == 22.0


def _immune(zinc_mg, servings=1):
    from test_daily_serving_multiplier_guard import _row
    rows = [_row("Zinc", "zinc", zinc_mg, "mg"), _row("Vitamin C", "vitamin_c", 500, "mg")]
    return {"primary_type": "immune_support",
            "ingredient_quality_data": {"ingredients_scorable": rows, "ingredients": rows},
            "servingSizes": [{"minDailyServings": 1, "maxDailyServings": servings}]}


def test_immune_zinc_at_its_ul_is_not_zeroed_a_second_time():
    from scoring_v4.modules.immune_support import score_immune_support_dose
    over = score_immune_support_dose(_immune(50))
    within = score_immune_support_dose(_immune(20))
    assert over["metadata"]["high_zinc"] is True
    # Range credit is adequacy only (above the 25 mg band high it keeps the
    # existing half credit); the UL is the ceiling's alone.
    assert over["components"]["zinc_daily_range"] == 1.5
    assert over["components"]["daily_use_discipline"] == within["components"]["daily_use_discipline"]


@pytest.mark.parametrize("ingredient,band", [
    (_botanical_ingredient(quantity=0, unit="", isNestedIngredient=True), "primary_no_dose"),
    (_botanical_ingredient(quantity=500, scoring_input_kind="product_level_evidence",
                           evidence_type="blend_anchor_mass"), "blend_total_only"),
])
def test_hidden_botanical_amount_with_a_studied_range_takes_the_neutral(ingredient, band):
    out = score_botanical_dose(_botanical_product(ingredient=ingredient))
    assert out["band"] == band and out["metadata"]["benchmark"] == "present"
    assert out["score"] == pytest.approx(unbenchmarked_dose_credit())
