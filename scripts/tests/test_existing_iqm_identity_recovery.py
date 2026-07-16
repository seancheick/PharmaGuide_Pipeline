"""Regression coverage for existing IQM identities rejected during enrichment.

These fixtures are reduced from manifest-owned July 16 corpus rows.  They
exercise the ingredient-quality contract boundary rather than the private
text matcher: a cleaner-approved, dose-bearing active with verified structured
identity must either reach ``ingredients_scorable`` under the correct IQM
parent or fail closed for a named clinical reason.
"""

from __future__ import annotations

import pytest

from enrich_supplements_v3 import SupplementEnricherV3


@pytest.fixture(scope="module")
def enricher() -> SupplementEnricherV3:
    return SupplementEnricherV3()


def _active_row(**overrides):
    row = {
        "name": "AlphaSize",
        "raw_source_text": "AlphaSize",
        "standardName": "Alpha GPC",
        "canonical_id": "alpha_gpc",
        "canonical_source_db": "ingredient_quality_map",
        "cleaner_match_method": "unii_form_exact_match",
        "quantity": 300.0,
        "unit": "mg",
        "forms": [
            {
                "name": "Alpha-Glycerylphosphorylcholine",
                "category": "non-nutrient/non-botanical",
                "ingredientGroup": "Alpha-GPC",
                "uniiCode": "60M22SGW66",
            }
        ],
        "cleaner_row_role": "active_scorable",
        "score_eligible_by_cleaner": True,
        "score_exclusion_reason": None,
        "source_section": "active",
        "raw_source_path": "ingredientRows[1]",
        "dose_class": "therapeutic_mass",
        "raw_taxonomy": {
            "category": "non-nutrient/non-botanical",
            "ingredientGroup": "Alpha-GPC",
            "forms": [
                {
                    "name": "Alpha-Glycerylphosphorylcholine",
                    "category": "non-nutrient/non-botanical",
                    "ingredientGroup": "Alpha-GPC",
                    "uniiCode": "60M22SGW66",
                }
            ],
        },
    }
    row.update(overrides)
    return row


def test_structured_alpha_gpc_parent_is_not_downgraded_to_generic_choline(
    enricher: SupplementEnricherV3,
) -> None:
    result = enricher._collect_ingredient_quality_data(
        {
            "id": "302695",
            "fullName": "Natural Brain Enhancers",
            "activeIngredients": [_active_row()],
            "inactiveIngredients": [],
        }
    )

    assert len(result["ingredients_scorable"]) == 1
    row = result["ingredients_scorable"][0]
    assert row["canonical_id"] == "alpha_gpc"
    assert row["scoreable_identity"] is True
    assert row["role_classification"] == "active_scorable"


def test_dosed_exact_unii_omega3_row_is_active_not_a_blend_header(
    enricher: SupplementEnricherV3,
) -> None:
    omega = _active_row(
        name="Omega-3 Fatty Acids",
        raw_source_text="Omega-3 Fatty Acids",
        standardName="Minor Omega-3 Fatty Acids & SPM Precursors",
        canonical_id="omega_3",
        cleaner_match_method="unii_exact_match",
        quantity=500.0,
        forms=[],
        raw_source_path="ingredientRows[3]",
        raw_taxonomy={
            "category": "fatty acid",
            "ingredientGroup": "Omega-3",
            "uniiCode": "71M78END5S",
            "forms": [],
        },
        uniiCode="71M78END5S",
    )
    result = enricher._collect_ingredient_quality_data(
        {
            "id": "18180",
            "fullName": "Advanced Eye Health",
            "activeIngredients": [omega],
            "inactiveIngredients": [],
        }
    )

    assert len(result["ingredients_scorable"]) == 1
    row = result["ingredients_scorable"][0]
    assert row["canonical_id"] == "omega_3"
    assert row["is_blend_header"] is False
    assert row["has_dose"] is True


def test_nutrient_parent_identity_survives_multiple_source_form_uniis(
    enricher: SupplementEnricherV3,
) -> None:
    forms = [
        {
            "name": "Calcium Phosphate",
            "category": "mineral",
            "ingredientGroup": "Calcium",
            "uniiCode": "97Z1WI3NDX",
        },
        {
            "name": "Potassium Phosphate",
            "prefix": "as",
            "category": "mineral",
            "ingredientGroup": "Potassium",
            "uniiCode": "B7862WZ632",
        },
        {
            "name": "Sodium Phosphate",
            "category": "other",
            "ingredientGroup": "Sodium Phosphate",
            "uniiCode": None,
        },
    ]
    phosphorus = _active_row(
        name="Phosphorus",
        raw_source_text="Phosphorus",
        standardName="Calcium",
        canonical_id="calcium",
        cleaner_match_method="unii_form_exact_match",
        quantity=38.0,
        forms=forms,
        raw_source_path="ingredientRows[11]",
        raw_taxonomy={
            "category": "mineral",
            "ingredientGroup": "Phosphorus",
            "uniiCode": None,
            "forms": forms,
        },
    )
    result = enricher._collect_ingredient_quality_data(
        {
            "id": "239602",
            "fullName": "Vitamin C 1000 mg Orange Flavored Fizzy Drink",
            "activeIngredients": [phosphorus],
            "inactiveIngredients": [],
        }
    )

    assert len(result["ingredients_scorable"]) == 1
    row = result["ingredients_scorable"][0]
    assert row["canonical_id"] == "phosphorus"
    assert row["scoreable_identity"] is True
    assert row["role_classification"] == "active_scorable"

