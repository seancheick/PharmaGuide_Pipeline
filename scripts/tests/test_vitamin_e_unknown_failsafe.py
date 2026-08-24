"""
Review follow-up — unknown-form Vitamin E must fail toward safety, not the lower
synthetic factor.

`_detect_vitamin_e_form` defaulted an undetected form to SYNTHETIC (0.45 mg/IU).
At high IU that under-states the mg (natural is 0.67 mg/IU), so an over-UL dose
could be hidden. Mirror vitamin A: an undetected E form resolves to
`vitamin_e_unknown` (conversions:null → flag_for_review), and the enricher skips
the UL check (not evaluable) rather than converting at the synthetic factor.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from enrich_supplements_v3 import SupplementEnricherV3


@pytest.fixture(scope="module")
def enricher() -> SupplementEnricherV3:
    return SupplementEnricherV3()


def test_vitamin_e_unknown_form_is_ul_skipped_not_synthetic(enricher):
    # Bare "Vitamin E 1500 IU" — no natural/synthetic token.
    product = {
        "activeIngredients": [
            {"name": "Vitamin E", "standardName": "Vitamin E", "canonical_id": "vitamin_e",
             "canonical_source_db": "ingredient_quality_map",
             "quantity": 1500, "unit": "IU", "dailyValue": None},
        ],
        "inactiveIngredients": [],
    }
    result = enricher._collect_rda_ul_data(product, min_servings_per_day=1, max_servings_per_day=1)
    rows = [a for a in result["adequacy_results"] if "vitamin e" in (a.get("nutrient") or "").lower()]
    assert rows, "expected a Vitamin E adequacy row"
    assert rows[0].get("skip_ul_check") is True, (
        "unknown-form Vitamin E must skip the UL check, not convert at the synthetic factor"
    )
    assert rows[0].get("skip_ul_reason") == "unknown_vitamin_form"


def test_low_unknown_form_vitamin_e_uses_natural_form_upper_bound(enricher):
    product = {
        "activeIngredients": [
            {
                "name": "Vitamin E",
                "standardName": "Vitamin E",
                "canonical_id": "vitamin_e",
                "canonical_source_db": "ingredient_quality_map",
                "quantity": 75,
                "unit": "IU",
                "dailyValue": None,
            },
        ],
        "inactiveIngredients": [],
    }
    result = enricher._collect_rda_ul_data(
        product,
        min_servings_per_day=1,
        max_servings_per_day=1,
    )
    row = result["adequacy_results"][0]
    assessment = result["dose_assessments"][0]

    assert row["skip_ul_reason"] == "worst_case_natural_vitamin_e_within_ul"
    assert row["ul"] == pytest.approx(1000)
    assert row["pct_ul"] == pytest.approx(5.025)
    assert row["pct_rda"] is None
    assert row["scoring_eligible"] is False
    assert assessment["normalized_value"] == pytest.approx(50.25)
    assert assessment["normalized_unit"] == "mg"
    assert assessment["ul_assessment_status"] == "assessed_within_limit"
    assert assessment["readiness"] == "complete"


def test_single_mixed_tocopherol_mass_is_an_alpha_tocopherol_upper_bound(
    enricher,
):
    product = {
        "activeIngredients": [
            {
                "name": "Mixed Tocotrienols/Tocopherols",
                "standardName": "Vitamin E",
                "canonical_id": "vitamin_e",
                "canonical_source_db": "ingredient_quality_map",
                "quantity": 60,
                "unit": "mg",
                "dailyValue": None,
            },
        ],
        "inactiveIngredients": [],
    }
    result = enricher._collect_rda_ul_data(product)
    row = result["adequacy_results"][0]
    assessment = result["dose_assessments"][0]

    assert row["skip_ul_reason"] == "worst_case_vitamin_e_mass_within_ul"
    assert row["pct_rda"] is None
    assert row["scoring_eligible"] is False
    assert assessment["normalized_value"] == pytest.approx(60)
    assert assessment["normalized_unit"] == "mg"
    assert assessment["readiness"] == "complete"


def test_vitex_name_does_not_trigger_vitamin_e_readiness(enricher):
    product = {
        "activeIngredients": [
            {
                "name": "organic Vitex negundo",
                "standardName": "organic Vitex negundo",
                "canonical_id": "vitex",
                "canonical_source_db": "ingredient_quality_map",
                "quantity": 4,
                "unit": "mg",
                "dailyValue": None,
            },
        ],
        "inactiveIngredients": [],
    }
    result = enricher._collect_rda_ul_data(product)
    assessment = result["dose_assessments"][0]

    assert assessment["ul_assessment_status"] == "no_ul_applicable"
    assert assessment["readiness"] == "not_applicable"


@pytest.mark.parametrize(
    ("amounts", "expected_readiness"),
    [
        ([120, 30, 16, 4, 1], "complete"),
        ([600, 500], "incomplete"),
    ],
)
def test_multiple_vitamin_e_family_masses_use_aggregate_upper_bound(
    enricher,
    amounts,
    expected_readiness,
):
    rows = [
        {
            "name": name,
            "standardName": "Vitamin E",
            "canonical_id": "vitamin_e",
            "canonical_source_db": "ingredient_quality_map",
            "quantity": amount,
            "unit": "mg",
            "dailyValue": None,
        }
        for name, amount in zip(
            [
                "D-Gamma-Tocopherol",
                "Tocotrienols",
                "D-Gamma-Tocotrienol",
                "D-Delta-Tocotrienol",
                "D-Beta-Tocotrienol",
            ],
            amounts,
        )
    ]
    result = enricher._collect_rda_ul_data(
        {"activeIngredients": rows, "inactiveIngredients": []}
    )
    assessments = result["dose_assessments"]
    assert all(row["readiness"] == expected_readiness for row in assessments)
    if expected_readiness == "complete":
        assert all(
            row["reason_code"] == "worst_case_vitamin_e_mass_within_ul"
            for row in assessments
        )


def test_nested_vitamin_e_breakdown_is_not_double_counted(enricher):
    rows = [
        {
            "name": "Complete 8 Vitamin E",
            "standardName": "Vitamin E",
            "canonical_id": "vitamin_e",
            "canonical_source_db": "ingredient_quality_map",
            "quantity": 400,
            "unit": "IU",
            "raw_source_path": "ingredientRows[0]",
        },
        {
            "name": "Tocopherol",
            "standardName": "Vitamin E",
            "canonical_id": "vitamin_e",
            "canonical_source_db": "ingredient_quality_map",
            "quantity": 441,
            "unit": "mg",
            "raw_source_path": "ingredientRows[0].nestedRows[0]",
        },
        {
            "name": "D-Alpha-Tocopherol",
            "standardName": "Vitamin E",
            "canonical_id": "vitamin_e",
            "canonical_source_db": "ingredient_quality_map",
            "quantity": 269,
            "unit": "mg",
            "raw_source_path": "ingredientRows[0].nestedRows[0].nestedRows[0]",
        },
        {
            "name": "D-Gamma-Tocopherol",
            "standardName": "Vitamin E",
            "canonical_id": "vitamin_e",
            "canonical_source_db": "ingredient_quality_map",
            "quantity": 120,
            "unit": "mg",
            "raw_source_path": "ingredientRows[0].nestedRows[0].nestedRows[1]",
        },
        {
            "name": "D-Delta-Tocopherol",
            "standardName": "Vitamin E",
            "canonical_id": "vitamin_e",
            "canonical_source_db": "ingredient_quality_map",
            "quantity": 48,
            "unit": "mg",
            "raw_source_path": "ingredientRows[0].nestedRows[0].nestedRows[2]",
        },
        {
            "name": "D-Beta-Tocopherol",
            "standardName": "Vitamin E",
            "canonical_id": "vitamin_e",
            "canonical_source_db": "ingredient_quality_map",
            "quantity": 4,
            "unit": "mg",
            "raw_source_path": "ingredientRows[0].nestedRows[0].nestedRows[3]",
        },
        {
            "name": "Tocotrienols",
            "standardName": "Vitamin E",
            "canonical_id": "vitamin_e",
            "canonical_source_db": "ingredient_quality_map",
            "quantity": 30,
            "unit": "mg",
            "raw_source_path": "ingredientRows[0].nestedRows[1]",
        },
        {
            "name": "D-Gamma-Tocotrienol",
            "standardName": "Vitamin E",
            "canonical_id": "vitamin_e",
            "canonical_source_db": "ingredient_quality_map",
            "quantity": 16,
            "unit": "mg",
            "raw_source_path": "ingredientRows[0].nestedRows[1].nestedRows[0]",
        },
        {
            "name": "D-Alpha-Tocotrienol",
            "standardName": "Vitamin E",
            "canonical_id": "vitamin_e",
            "canonical_source_db": "ingredient_quality_map",
            "quantity": 9,
            "unit": "mg",
            "raw_source_path": "ingredientRows[0].nestedRows[1].nestedRows[1]",
        },
        {
            "name": "D-Delta-Tocotrienol",
            "standardName": "Vitamin E",
            "canonical_id": "vitamin_e",
            "canonical_source_db": "ingredient_quality_map",
            "quantity": 4,
            "unit": "mg",
            "raw_source_path": "ingredientRows[0].nestedRows[1].nestedRows[2]",
        },
        {
            "name": "D-Beta-Tocotrienol",
            "standardName": "Vitamin E",
            "canonical_id": "vitamin_e",
            "canonical_source_db": "ingredient_quality_map",
            "quantity": 1,
            "unit": "mg",
            "raw_source_path": "ingredientRows[0].nestedRows[1].nestedRows[3]",
        },
    ]
    result = enricher._collect_rda_ul_data(
        {"activeIngredients": rows, "inactiveIngredients": []}
    )
    unresolved = [
        row for row in result["dose_assessments"]
        if row["readiness"] == "incomplete"
    ]
    assert unresolved == []


def test_natural_vitamin_e_still_converts(enricher):
    # A named natural form must still convert (regression guard — fix only touches
    # the unknown default).
    product = {
        "activeIngredients": [
            {"name": "Vitamin E (d-alpha-tocopherol)", "standardName": "Vitamin E",
             "canonical_id": "vitamin_e", "canonical_source_db": "ingredient_quality_map",
             "quantity": 30, "unit": "IU", "dailyValue": 100.0},
        ],
        "inactiveIngredients": [],
    }
    result = enricher._collect_rda_ul_data(product, min_servings_per_day=1, max_servings_per_day=1)
    rows = [a for a in result["adequacy_results"] if "vitamin e" in (a.get("nutrient") or "").lower()]
    assert rows, "expected a Vitamin E adequacy row"
    assert rows[0].get("skip_ul_check") is not True, "named natural form must still be evaluated"


def test_bare_vitamin_e_mg_is_label_declared_alpha_tocopherol(enricher):
    """Current Supplement Facts mg Vitamin E is already alpha-tocopherol."""
    product = {
        "activeIngredients": [
            {
                "name": "Vitamin E",
                "standardName": "Vitamin E",
                "canonical_id": "vitamin_e",
                "canonical_source_db": "ingredient_quality_map",
                "raw_source_path": "ingredientRows[0]",
                "quantity": 15,
                "unit": "mg",
                "dailyValue": 100.0,
            },
        ],
        "inactiveIngredients": [],
        "assessment_readiness_contract_version": "1.0.0",
    }

    result = enricher._collect_rda_ul_data(
        product,
        min_servings_per_day=1,
        max_servings_per_day=1,
    )
    row = result["adequacy_results"][0]
    assessment = result["dose_assessments"][0]

    assert row["skip_ul_check"] is False
    assert assessment["normalized_unit"] == "mg"
    assert assessment["ul_assessment_status"] == "assessed_within_limit"
    assert assessment["readiness"] == "complete"
