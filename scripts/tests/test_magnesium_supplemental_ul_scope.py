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
    assert not any("exceeds" in warning for warning in adequacy["warnings"])
    assert any("food" in warning for warning in adequacy["warnings"])
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


@pytest.mark.parametrize("forms,protein_g", [
    (("Magnesium Oxide",), 60.0),  # food matrix, but the label attributes the amount
    ((), None),  # tablet: no food matrix, so the declared magnesium is added
])
def test_evidently_supplemental_magnesium_keeps_confirmed_exceedance(enricher, forms, protein_g):
    out = _assess(enricher, _magnesium(540, forms), protein_g=protein_g)
    assert out["analyzed_ingredients"][0]["skip_ul_check"] is False
    assert [flag.pct_ul for flag in _confirmed(out)] == [pytest.approx(540 / 350 * 100)]
    assert not get_actionable_ul_review_signals(out)
