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


def test_no_ul_nutrient_caps_adequacy_at_high_without_claiming_safety() -> None:
    result = RDAULCalculator().compute_nutrient_adequacy(
        nutrient="Vitamin B12",
        amount=24,
        unit="mcg",
        age_group="19-30",
        sex="adult_neutral",
    )

    assert result.ul is None
    assert result.ul_status == "not_determined"
    assert result.pct_rda == pytest.approx(1000)
    assert result.adequacy_band == "high"
    assert result.point_recommendation == 2
    assert result.over_ul is False
    assert any("not a safety conclusion" in note.lower() for note in result.notes)


def test_established_ul_nutrient_remains_excessive_when_over_ul() -> None:
    result = RDAULCalculator().compute_nutrient_adequacy(
        nutrient="Vitamin C",
        amount=3000,
        unit="mg",
        age_group="19-30",
        sex="adult_neutral",
    )

    assert result.ul_status == "established"
    assert result.over_ul is True
    assert result.adequacy_band == "excessive"
    assert result.point_recommendation == 0


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


def test_non_precaution_commas_preserve_recommended_dose(enricher) -> None:
    parsed = enricher._parse_dosage_from_directions(
        "Take 2 capsules daily, preferably with food, or as directed."
    )

    assert parsed == {"min": 2, "max": 2}


@pytest.mark.parametrize(
    "name,matched_form,unit,expected_reason",
    [
        ("Methylfolate", "5-MTHF", "mcg", "non_folic_acid_folate_ul_basis"),
        ("Food Folate", "food folate", "mcg", "non_folic_acid_folate_ul_basis"),
        # Folinic acid / calcium folinate / leucovorin are reduced folates. This
        # pipeline applies the folic-acid UL only to an identified folic-acid
        # contribution; declared mcg DFE remains valid adequacy evidence.
        ("Folinic Acid", "folinic acid", "mcg DFE", "non_folic_acid_folate_ul_basis"),
        ("Calcium Folinate", "calcium folinate", "mcg DFE", "non_folic_acid_folate_ul_basis"),
        ("Leucovorin", "leucovorin", "mcg DFE", "non_folic_acid_folate_ul_basis"),
        (
            "Folate",
            "standard",
            "mcg DFE",
            "worst_case_folic_acid_within_ul",
        ),
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
    if expected_reason == "worst_case_folic_acid_within_ul":
        assert row["ul"] == pytest.approx(1000)
        assert row["pct_ul"] == pytest.approx((1200 / 1.7) / 1000 * 100)
    else:
        assert row["ul"] is None
        assert row["pct_ul"] is None
    assert row["over_ul"] is False
    assert row["skip_ul_reason"] == expected_reason
    assert result["has_over_ul"] is False
    if expected_reason == "non_folic_acid_folate_ul_basis":
        assert result["ul_review_flags"] == []


@pytest.mark.parametrize(
    "name,matched_form",
    [
        ("Folinic Acid", "folinic acid"),
        ("Calcium Folinate", "calcium folinate"),
        ("Leucovorin", "leucovorin"),
    ],
)
@pytest.mark.parametrize("daily_value", [None, 100, 300])
def test_bare_mass_folinic_without_verified_dfe_does_not_score_adequacy(
    enricher, name, matched_form, daily_value
) -> None:
    result = enricher._collect_rda_ul_data({
        "activeIngredients": [{
            "name": name,
            "standardName": "Folate",
            "canonical_id": "vitamin_b9_folate",
            "matched_form": matched_form,
            "quantity": 1200,
            "unit": "mcg",
            "dailyValue": daily_value,
        }],
        "inactiveIngredients": [],
    })
    row = result["adequacy_results"][0]
    conversion = result["conversion_evidence"][0]

    assert conversion["success"] is False
    assert conversion["conversion_rule_id"] == "folate_unknown"
    assert row["rda_ai"] is None
    assert row["pct_rda"] is None
    assert row["adequacy_band"] == "unknown"
    assert row["scoring_eligible"] is False
    assert row["point_recommendation"] == 0
    assert row["ul"] is None
    assert row["pct_ul"] is None
    assert row["over_ul"] is False
    assert row["skip_ul_reason"] == "non_folic_acid_folate_ul_basis"
    assert row["ul_assessment_status"] == "not_applicable"
    assert result["has_over_ul"] is False
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


def test_unknown_folate_below_possible_synthetic_ul_is_conservatively_assessed(
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

    assessment = result["dose_assessments"][0]
    assert row["ul_assessment_status"] == "assessed_within_limit"
    assert row["ul_status"] == "assessed_within_limit_worst_case_folic_acid"
    assert row["skip_ul_reason"] == "worst_case_folic_acid_within_ul"
    assert row["ul"] == pytest.approx(1000)
    assert row["pct_ul"] == pytest.approx((400 / 1.7) / 1000 * 100)
    assert row["potential_ul_concern"] is False
    assert result["ul_review_flags"] == []
    assert assessment["ul_assessment_status"] == "assessed_within_limit"
    assert assessment["readiness"] == "complete"


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


def test_legacy_bare_folate_below_ul_completes_safety_without_adequacy_guess(
    enricher,
) -> None:
    result = enricher._collect_rda_ul_data({
        "activeIngredients": [{
            "name": "Folate",
            "standardName": "Folate",
            "canonical_id": "vitamin_b9_folate",
            "matched_form": "standard",
            "quantity": 400,
            "unit": "mcg",
            "dailyValue": None,
        }],
        "inactiveIngredients": [],
    })
    row = result["adequacy_results"][0]
    assessment = result["dose_assessments"][0]

    assert row["skip_ul_reason"] == "worst_case_folic_acid_within_ul"
    assert row["ul"] == pytest.approx(1000)
    assert row["pct_ul"] == pytest.approx(40)
    assert row["ul_assessment_status"] == "assessed_within_limit"
    assert row["rda_ai"] is None
    assert row["pct_rda"] is None
    assert row["scoring_eligible"] is False
    assert assessment["ul_assessment_status"] == "assessed_within_limit"
    assert assessment["readiness"] == "complete"


def test_folate_row_with_exact_folic_acid_unii_uses_verified_identity(enricher) -> None:
    result = enricher._collect_rda_ul_data(
        {
            "activeIngredients": [
                {
                    "name": "Folate",
                    "raw_source_text": "Folate",
                    "standardName": "Folate (Form Unknown)",
                    "canonical_id": "vitamin_b9_folate",
                    "canonical_source_db": "ingredient_quality_map",
                    "uniiCode": "935E97BOY8",
                    "quantity": 120,
                    "unit": "mcg",
                    "dailyValue": 30,
                }
            ],
            "inactiveIngredients": [],
        },
        min_servings_per_day=1,
        max_servings_per_day=1,
    )

    assessment = result["dose_assessments"][0]
    row = result["analyzed_ingredients"][0]
    assert assessment["conversion_rule_id"] == "folate_folic_acid"
    assert assessment["normalized_value"] == pytest.approx(204)
    assert assessment["normalized_unit"] == "mcg DFE"
    assert assessment["ul_assessment_status"] == "assessed_within_limit"
    assert assessment["readiness"] == "complete"
    assert row["skip_ul_check"] is False


def test_explicit_methylfolate_form_overrides_generic_parent_unii(enricher) -> None:
    result = enricher._collect_rda_ul_data(
        {
            "activeIngredients": [
                {
                    "name": "Folate",
                    "raw_source_text": "Folate",
                    "standardName": "Vitamin B9 (Folate)",
                    "canonical_id": "vitamin_b9_folate",
                    "canonical_source_db": "ingredient_quality_map",
                    "uniiCode": "935E97BOY8",
                    "quantity": 1.7,
                    "unit": "mg DFE",
                    "dailyValue": 425,
                    "raw_source_path": "ingredientRows[0]",
                },
                {
                    "name": "Extrafolate-S",
                    "raw_source_text": "Extrafolate-S",
                    "standardName": "Vitamin B9 (Folate)",
                    "canonical_id": "vitamin_b9_folate",
                    "canonical_source_db": "ingredient_quality_map",
                    "quantity": 1,
                    "unit": "mg",
                    "dailyValue": None,
                    "isNestedIngredient": True,
                    "parentBlend": "Folate",
                    "raw_source_path": "ingredientRows[0].nestedRows[0]",
                    "forms": [
                        {"name": "L-5-Methyltetrahydrofolate"},
                    ],
                },
            ],
            "inactiveIngredients": [],
        },
        min_servings_per_day=1,
        max_servings_per_day=1,
    )

    parent = next(
        row
        for row in result["dose_assessments"]
        if row["ingredient"] == "Folate"
    )
    child = next(
        row
        for row in result["dose_assessments"]
        if row["ingredient"] == "Extrafolate-S"
    )
    assert parent["conversion_rule_id"] == "folate_unknown"
    assert parent["ul_assessment_status"] == "no_ul_applicable"
    assert parent["readiness"] == "not_applicable"
    assert child["conversion_rule_id"] == "folate_methylfolate"
    assert child["ul_assessment_status"] == "not_distinct_exposure"
    assert child["readiness"] == "not_applicable"


@pytest.mark.parametrize(
    "form_name",
    [
        "(6S)-5-Methyltetrahydrofolic Acid",
        "Organic Food Blend",
    ],
)
def test_explicit_non_folic_folate_forms_are_outside_folic_acid_ul(
    enricher,
    form_name,
) -> None:
    result = enricher._collect_rda_ul_data(
        {
            "activeIngredients": [{
                "name": "Folate",
                "raw_source_text": "Folate",
                "standardName": "Vitamin B9 (Folate)",
                "canonical_id": "vitamin_b9_folate",
                "canonical_source_db": "ingredient_quality_map",
                "quantity": 400,
                "unit": "mcg",
                "dailyValue": 100,
                "forms": [{"name": form_name}],
            }],
            "inactiveIngredients": [],
        }
    )
    assessment = result["dose_assessments"][0]
    assert assessment["ul_assessment_status"] == "no_ul_applicable"
    assert assessment["readiness"] == "not_applicable"


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


def test_low_bare_folate_with_daily_value_uses_raw_mass_upper_bound(
    enricher,
) -> None:
    result = enricher._collect_rda_ul_data(
        {
            "activeIngredients": [{
                "name": "Folate",
                "standardName": "Vitamin B9 (Folate)",
                "canonical_id": "vitamin_b9_folate",
                "canonical_source_db": "ingredient_quality_map",
                "quantity": 17,
                "unit": "mcg",
                "dailyValue": 4,
                "forms": [],
            }],
            "inactiveIngredients": [],
        }
    )
    row = result["adequacy_results"][0]
    assessment = result["dose_assessments"][0]
    assert row["skip_ul_reason"] == "worst_case_folic_acid_within_ul"
    assert row["pct_rda"] is None
    assert row["scoring_eligible"] is False
    assert assessment["ul_assessment_status"] == "assessed_within_limit"
    assert assessment["readiness"] == "complete"
    assert row["potential_pct_ul"] == pytest.approx(1.0)
