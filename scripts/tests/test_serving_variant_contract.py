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
