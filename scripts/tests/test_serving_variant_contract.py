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
    "name,matched_form,unit,expected_reason",
    [
        ("Methylfolate", "5-MTHF", "mcg", "non_folic_acid_folate_ul_basis"),
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
