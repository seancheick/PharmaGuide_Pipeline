"""The magnesium UL covers supplemental magnesium only, never food magnesium.

ODS/FNB set the adult magnesium UL at 350 mg for magnesium from supplements
and medications; magnesium naturally present in food is outside it. A
food-matrix label (a Facts panel declaring protein) that prints a bare
"Magnesium 540 mg" total, with no form attributing that amount, reports food
and added magnesium together (BSN/GNC Re-Built Mass XP 244288: whey, grains and
cocoa plus 2.5 g Creatine MagnaPower). Its supplemental share is not stated,
so the comparison is indeterminate and routes to review; it is neither a
confirmed exceedance nor cleared. Labels whose magnesium is evidently
supplemental (a declared form, or no food matrix) keep their findings.
"""
import json
from pathlib import Path

import pytest

from enrich_supplements_v3 import SupplementEnricherV3
from rda_ul_calculator import get_actionable_ul_review_signals
from scoring_v4.dose_safety import CONFIRMED_OVER_THRESHOLD, evaluate_dose_safety


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3()


def _magnesium(quantity, forms=()):
    return {
        "name": "Magnesium", "standardName": "Magnesium", "raw_source_text": "Magnesium",
        "canonical_id": "magnesium", "canonical_source_db": "ingredient_quality_map",
        "quantity": quantity, "unit": "mg", "dailyValue": round(quantity / 4.2),
        "forms": [{"name": name} for name in forms],
    }


def _assess(enricher, row, protein_g=60.0, servings=1):
    product = {"activeIngredients": [row], "inactiveIngredients": [], "statements": []}
    if protein_g is not None:
        product["nutritionalInfo"] = {"protein": {"amount": protein_g, "unit": "Gram(s)"}}
    return enricher._collect_rda_ul_data(
        product, min_servings_per_day=servings, max_servings_per_day=servings)


def _confirmed(out):
    return [flag for flag in evaluate_dose_safety({"rda_ul_data": out}).flags
            if flag.state == CONFIRMED_OVER_THRESHOLD]


def test_food_matrix_total_without_supplemental_share_is_indeterminate_review(enricher):
    out = _assess(enricher, _magnesium(540))
    row = out["analyzed_ingredients"][0]
    assert row["skip_ul_reason"] == "supplemental_magnesium_fraction_unknown"
    assert row["ul_assessment_status"] == "indeterminate"
    assert row["ul_gate_eligible"] is True  # still a valid nutrient amount
    adequacy = out["adequacy_results"][0]
    assert adequacy["pct_rda"] == pytest.approx(135.0)
    assert adequacy["pct_ul"] is None and adequacy["over_ul"] is False
    assert not out["safety_flags"] and not _confirmed(out)
    # Uncertainty, not a confirmed excess; the total is never called supplemental.
    assert adequacy["warnings"] == [
        "The 350 mg magnesium upper limit applies to supplemental magnesium only. This "
        "label's magnesium total may include magnesium from food ingredients and does not "
        "state the supplemental amount, so supplemental magnesium could exceed that limit; "
        "this is not confirmed."]
    review = [flag for flag in out["ul_review_flags"] if flag["nutrient"] == "Magnesium"]
    assert review and review[0]["review_required"] is True
    assert review[0]["potential_pct_ul"] == pytest.approx(540 / 350 * 100)
    assert get_actionable_ul_review_signals(out) == ["MAGNESIUM_UL_SOURCE_REVIEW"]


def test_daily_total_uses_maximum_directed_servings(enricher):
    out = _assess(enricher, _magnesium(200), servings=2)
    assert out["analyzed_ingredients"][0]["ul_assessment_status"] == "indeterminate"
    assert get_actionable_ul_review_signals(out) == ["MAGNESIUM_UL_SOURCE_REVIEW"]


def test_total_within_ul_is_assessed_normally(enricher):
    # Supplemental magnesium cannot exceed a total that is itself within the UL.
    out = _assess(enricher, _magnesium(300))
    row = out["analyzed_ingredients"][0]
    assert row["skip_ul_check"] is False
    assert out["adequacy_results"][0]["pct_ul"] == pytest.approx(300 / 350 * 100)
    assert not out["ul_review_flags"]


@pytest.mark.parametrize("change", [
    {"forms": [{"name": "Magnesium Oxide"}]},
    {"raw_source_text": "Magnesium (as Magnesium Oxide)"},
    {"name": "Magnesium Citrate", "raw_source_text": "Magnesium Citrate"},
])
def test_named_source_on_a_food_matrix_does_not_partition_the_total(enricher, change):
    # The Facts amount is the total nutrient: naming the added source does not
    # make the whole declared total supplemental on a food-matrix product.
    row = _magnesium(540)
    row.update(change)
    out = _assess(enricher, row)
    assert out["analyzed_ingredients"][0]["skip_ul_reason"] == "supplemental_magnesium_fraction_unknown"
    assert not _confirmed(out)
    assert get_actionable_ul_review_signals(out) == ["MAGNESIUM_UL_SOURCE_REVIEW"]


@pytest.mark.parametrize("forms,serving_sizes,protein_g", [
    ((), None, None),  # no food matrix: the declared magnesium is added
    (("Magnesium Oxide",), [{"minQuantity": 2, "maxQuantity": 2, "unit": "Tablet(s)"}], 1.0),
    ((), [{"minQuantity": 1, "maxQuantity": 1, "unit": "Capsule(s)"}], 1.0),
])
def test_evidently_supplemental_magnesium_keeps_confirmed_exceedance(
        enricher, forms, serving_sizes, protein_g):
    # A tablet or capsule declaring a gram of protein is not a food matrix.
    product = {"activeIngredients": [_magnesium(540, forms)], "inactiveIngredients": [],
               "statements": []}
    if serving_sizes:
        product["servingSizes"] = serving_sizes
    if protein_g is not None:
        product["nutritionalInfo"] = {"protein": {"amount": protein_g, "unit": "Gram(s)"}}
    out = enricher._collect_rda_ul_data(product, min_servings_per_day=1, max_servings_per_day=1)
    assert out["analyzed_ingredients"][0]["skip_ul_check"] is False
    assert [flag.pct_ul for flag in _confirmed(out)] == [pytest.approx(540 / 350 * 100)]
    assert not get_actionable_ul_review_signals(out)


def _food_serving(enricher, quantity, serving):
    product = {"activeIngredients": [_magnesium(quantity, ("Magnesium Amino Acid Chelate",))],
               "inactiveIngredients": [], "statements": [], "servingSizes": [serving],
               "nutritionalInfo": {"protein": {"amount": 5.0, "unit": "Gram(s)"}}}
    return enricher._collect_rda_ul_data(product, min_servings_per_day=1, max_servings_per_day=1)


@pytest.mark.parametrize("label_id", ["273824", "321360"])
def test_unproven_food_partition_stays_unresolved_even_in_small_serving(enricher, label_id):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from scoring_v4.scored_artifact import build_scored_artifact

    raw = json.loads((Path(__file__).parent / "fixtures" / f"magnesium_food_{label_id}_raw.json").read_text())
    enriched, _ = enricher.enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    out = enriched["rda_ul_data"]
    assert not [flag for flag in _confirmed(out) if flag.nutrient == "Magnesium"]
    assert not [flag for flag in out["safety_flags"] if flag["nutrient"] == "Magnesium"]
    row = next(row for row in out["analyzed_ingredients"] if row["canonical_id"] == "magnesium")
    assert row["ul_assessment_status"] == "indeterminate"
    assert row["skip_ul_reason"] == "supplemental_magnesium_fraction_unknown"
    assert "MAGNESIUM_UL_SOURCE_REVIEW" in get_actionable_ul_review_signals(out)
    artifact = build_scored_artifact(enriched)
    assert "MAGNESIUM_UL_SOURCE_REVIEW" in str(artifact)
    assert "includes at least 590" not in str(artifact)


@pytest.mark.parametrize("serving", [
    {"minQuantity": 255, "maxQuantity": 255, "unit": "Gram(s)"},  # food could hold it all
    {"minQuantity": 2, "maxQuantity": 2, "unit": "Scoop(s)"},  # no mass to bound food
])
def test_unbounded_food_share_stays_unresolved(enricher, serving):
    out = _food_serving(enricher, 800, serving)
    assert not _confirmed(out)
    assert get_actionable_ul_review_signals(out) == ["MAGNESIUM_UL_SOURCE_REVIEW"]


@pytest.mark.parametrize("physical_state,serving", [
    ("Capsule", {"minQuantity": 1, "maxQuantity": 1, "unit": "Serving(s)"}),
    ("Tablet or Pill", None),
    (None, {"minQuantity": 2, "maxQuantity": 2, "unit": "Chewable Tablet(s)"}),
])
def test_dosage_form_from_physical_state_or_serving_is_not_a_food_matrix(
        enricher, physical_state, serving):
    product = {"activeIngredients": [_magnesium(540, ("Magnesium Oxide",))],
               "inactiveIngredients": [], "statements": [],
               "nutritionalInfo": {"protein": {"amount": 1.0, "unit": "Gram(s)"}}}
    if physical_state:
        product["physicalState"] = {"langualCodeDescription": physical_state}
    if serving:
        product["servingSizes"] = [serving]
    out = enricher._collect_rda_ul_data(product, min_servings_per_day=1, max_servings_per_day=1)
    assert [flag.pct_ul for flag in _confirmed(out)] == [pytest.approx(540 / 350 * 100)]


@pytest.mark.parametrize("quantities,protein,review,confirmed", [
    ([200, 200], 5, True, False),
    ([100, 200], 5, False, False),
    ([200, 200], None, False, True),
])
def test_summed_distinct_magnesium_rows_use_same_source_scope(
        enricher, quantities, protein, review, confirmed):
    rows = [_magnesium(amount) for amount in quantities]
    for index, row in enumerate(rows):
        row["name"] = row["raw_source_text"] = f"Magnesium source {index + 1}"
    product = {"activeIngredients": rows, "inactiveIngredients": [], "statements": []}
    if protein:
        product["nutritionalInfo"] = {"protein": {"amount": protein, "unit": "Gram(s)"}}
    out = enricher._collect_rda_ul_data(product, min_servings_per_day=1, max_servings_per_day=1)
    assert bool(_confirmed(out)) is confirmed
    assert ("MAGNESIUM_UL_SOURCE_REVIEW" in get_actionable_ul_review_signals(out)) is review
    if review:
        flag = next(flag for flag in out["ul_review_flags"] if flag["nutrient"] == "Magnesium")
        assert flag["assessment_status"] == "indeterminate"
        assert flag["screening_amount"] == sum(quantities)
