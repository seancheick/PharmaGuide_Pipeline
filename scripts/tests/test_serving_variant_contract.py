"""Serving ranges have one explicit adequacy/safety interpretation (H5)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from enrich_supplements_v3 import SupplementEnricherV3
from rda_ul_calculator import RDAULCalculator


def test_canonical_serving_coerces_numeric_strings_before_comparison() -> None:
    enricher = SupplementEnricherV3.__new__(SupplementEnricherV3)

    selected = enricher._select_canonical_serving(
        [{"quantity": "1"}, {"quantity": "2"}],
        [],
    )

    assert selected == {"quantity": "2"}


def test_adult_neutral_profile_uses_conservative_sourced_reference() -> None:
    result = RDAULCalculator().compute_nutrient_adequacy(
        nutrient="Vitamin C",
        amount=90,
        unit="mg",
        age_group="19-30",
        sex="adult_neutral",
    )

    assert result.sex_group == "Adult neutral"
    assert result.rda_ai == 90  # max of sourced adult male/female references
    assert result.pct_rda == pytest.approx(100)


@pytest.fixture(scope="module")
def enricher() -> SupplementEnricherV3:
    return SupplementEnricherV3()


def test_adequacy_uses_minimum_and_ul_safety_uses_maximum(enricher) -> None:
    product = {
        "activeIngredients": [
            {
                "name": "Vitamin C",
                "standardName": "Vitamin C",
                "canonical_id": "vitamin_c",
                "quantity": 1000,
                "unit": "mg",
                "dailyValue": 1111,
            }
        ],
        "inactiveIngredients": [],
    }

    result = enricher._collect_rda_ul_data(
        product,
        min_servings_per_day=1,
        max_servings_per_day=3,
    )
    row = result["adequacy_results"][0]

    assert row["amount"] == pytest.approx(1000)
    assert row["adequacy_exposure"]["per_day"] == pytest.approx(1000)
    assert row["safety_exposure"]["per_day"] == pytest.approx(3000)
    assert row["over_ul"] is True
    assert result["safety_flags"][0]["amount"] == pytest.approx(3000)
    assert row["data_by_group"]
    assert result["reference_profile"]["id"] == "adult_neutral_compatibility"


def test_precaution_ceiling_is_not_parsed_as_recommended_dose(enricher) -> None:
    parsed = enricher._parse_dosage_from_directions(
        "Do not exceed 6 tablets in 24 hours. Take 2 tablets daily."
    )

    assert parsed == {"min": 2, "max": 2}


def test_precaution_without_recommended_dose_returns_none(enricher) -> None:
    parsed = enricher._parse_dosage_from_directions(
        "Do not exceed 6 tablets in 24 hours."
    )

    assert parsed is None


@pytest.mark.parametrize(
    "directions",
    [
        "Take 2 tablets daily, do not exceed 6 tablets in 24 hours.",
        "Do not exceed 6 tablets in 24 hours, take 2 tablets daily.",
    ],
)
def test_comma_joined_precaution_preserves_recommended_dose(
    enricher, directions
) -> None:
    parsed = enricher._parse_dosage_from_directions(directions)

    assert parsed == {"min": 2, "max": 2}


@pytest.mark.parametrize(
    "name,matched_form,unit,expected_reason",
    [
        ("Methylfolate", "5-MTHF", "mcg", "non_folic_acid_folate_ul_basis"),
        ("Food Folate", "food folate", "mcg", "non_folic_acid_folate_ul_basis"),
        ("Folate", "standard", "mcg DFE", "unknown_folate_form_lineage"),
    ],
)
def test_non_folic_acid_folate_retains_adequacy_but_suppresses_ul(
    enricher, name, matched_form, unit, expected_reason
) -> None:
    result = enricher._collect_rda_ul_data({
        "activeIngredients": [{
            "name": name,
            "standardName": "Folate",
            "canonical_id": "vitamin_b9_folate",
            "matched_form": matched_form,
            "quantity": 1200,
            "unit": unit,
            "dailyValue": 300,
        }],
        "inactiveIngredients": [],
    })
    row = result["adequacy_results"][0]

    assert row["rda_ai"] is not None
    assert row["ul"] is None
    assert row["pct_ul"] is None
    assert row["over_ul"] is False
    assert row["skip_ul_reason"] == expected_reason
    assert result["has_over_ul"] is False
    if expected_reason == "non_folic_acid_folate_ul_basis":
        assert result["ul_review_flags"] == []


def test_identified_folic_acid_still_uses_synthetic_ul_basis(enricher) -> None:
    result = enricher._collect_rda_ul_data({
        "activeIngredients": [{
            "name": "Folic Acid",
            "standardName": "Folate",
            "canonical_id": "vitamin_b9_folate",
            "matched_form": "folic acid",
            "quantity": 1100,
            "unit": "mcg",
            "dailyValue": 275,
        }],
        "inactiveIngredients": [],
    })
    row = result["adequacy_results"][0]

    assert row["skip_ul_check"] is False
    assert row["over_ul"] is True
    assert result["has_over_ul"] is True


@pytest.mark.parametrize(
    "unit,daily_value,expected_screening_amount,expected_basis",
    [
        ("mcg", 425, 1000, "dfe_inferred_from_daily_value"),
        ("mcg DFE", 425, 1000, "label_declared_dfe"),
        ("mcg", None, 1700, "bare_mass_worst_case"),
    ],
)
def test_unknown_folate_at_possible_synthetic_ul_emits_review_not_over_ul(
    enricher, unit, daily_value, expected_screening_amount, expected_basis
) -> None:
    quantity = 1700
    result = enricher._collect_rda_ul_data({
        "activeIngredients": [{
            "name": "Folate",
            "standardName": "Folate",
            "canonical_id": "vitamin_b9_folate",
            "matched_form": "standard",
            "quantity": quantity,
            "unit": unit,
            "dailyValue": daily_value,
        }],
        "inactiveIngredients": [],
    })
    row = result["adequacy_results"][0]

    assert row["ul_assessment_status"] == "indeterminate"
    assert row["ul_status"] == "indeterminate_unknown_folate_form_lineage"
    assert row["over_ul"] is False
    assert row["potential_ul_concern"] is True
    assert result["has_over_ul"] is False
    assert result["ul_review_flags"] == [{
        "nutrient": "Folate",
        "assessment_status": "indeterminate",
        "reason": "unknown_folate_form_lineage",
        "screening_amount": pytest.approx(expected_screening_amount),
        "screening_unit": "mcg folic acid",
        "screening_ul": pytest.approx(1000),
        "potential_pct_ul": pytest.approx(expected_screening_amount / 10),
        "screening_basis": expected_basis,
        "review_required": True,
    }]


def test_unknown_folate_below_possible_synthetic_ul_is_indeterminate_without_review(
    enricher,
) -> None:
    result = enricher._collect_rda_ul_data({
        "activeIngredients": [{
            "name": "Folate",
            "standardName": "Folate",
            "canonical_id": "vitamin_b9_folate",
            "matched_form": "standard",
            "quantity": 400,
            "unit": "mcg DFE",
            "dailyValue": 100,
        }],
        "inactiveIngredients": [],
    })
    row = result["adequacy_results"][0]

    assert row["ul_assessment_status"] == "indeterminate"
    assert row["potential_ul_concern"] is False
    assert result["ul_review_flags"] == []


def test_unknown_folate_without_declared_dfe_does_not_guess_adequacy(enricher) -> None:
    result = enricher._collect_rda_ul_data({
        "activeIngredients": [{
            "name": "Folate",
            "standardName": "Folate",
            "canonical_id": "vitamin_b9_folate",
            "matched_form": "standard",
            "quantity": 1700,
            "unit": "mcg",
            "dailyValue": None,
        }],
        "inactiveIngredients": [],
    })
    row = result["adequacy_results"][0]

    assert row["rda_ai"] is None
    assert row["pct_rda"] is None
    assert row["adequacy_band"] == "unknown"
    assert row["scoring_eligible"] is False


def test_unknown_folate_dfe_inference_uses_per_serving_dv_before_daily_range(
    enricher,
) -> None:
    result = enricher._collect_rda_ul_data(
        {
            "activeIngredients": [{
                "name": "Folate",
                "standardName": "Folate",
                "canonical_id": "vitamin_b9_folate",
                "matched_form": "standard",
                "quantity": 850,
                "unit": "mcg",
                "dailyValue": 212.5,
            }],
            "inactiveIngredients": [],
        },
        min_servings_per_day=1,
        max_servings_per_day=2,
    )

    flag = result["ul_review_flags"][0]
    assert flag["screening_basis"] == "dfe_inferred_from_daily_value"
    assert flag["screening_amount"] == pytest.approx(1000)
    assert flag["potential_pct_ul"] == pytest.approx(100)
