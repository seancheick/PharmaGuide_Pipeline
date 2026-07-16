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


def test_dosed_omega3_parent_total_is_mapped_but_not_double_scored(
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
    epa = _active_row(
        name="Eicosapentaenoic Acid",
        raw_source_text="Eicosapentaenoic Acid",
        standardName="EPA (Eicosapentaenoic Acid)",
        canonical_id="epa",
        cleaner_match_method="unii_exact_match",
        quantity=325.0,
        uniiCode="AAN7QOV9EA",
        forms=[],
        isNestedIngredient=True,
        parentBlend="Omega-3 Fatty Acids",
        raw_source_path="ingredientRows[3].nestedRows[0]",
        raw_taxonomy={
            "category": "fatty acid",
            "ingredientGroup": "EPA (Eicosapentaenoic Acid)",
            "uniiCode": "AAN7QOV9EA",
            "forms": [],
            "parentBlend": "Omega-3 Fatty Acids",
            "isNestedIngredient": True,
        },
    )
    dha = _active_row(
        name="Docosahexaenoic Acid",
        raw_source_text="Docosahexaenoic Acid",
        standardName="DHA (Docosahexaenoic Acid)",
        canonical_id="dha",
        cleaner_match_method="unii_exact_match",
        quantity=175.0,
        uniiCode="ZAD9OKH9JC",
        forms=[],
        isNestedIngredient=True,
        parentBlend="Omega-3 Fatty Acids",
        raw_source_path="ingredientRows[3].nestedRows[1]",
        raw_taxonomy={
            "category": "fatty acid",
            "ingredientGroup": "DHA (Docosahexaenoic Acid)",
            "uniiCode": "ZAD9OKH9JC",
            "forms": [],
            "parentBlend": "Omega-3 Fatty Acids",
            "isNestedIngredient": True,
        },
    )
    result = enricher._collect_ingredient_quality_data(
        {
            "id": "18180",
            "fullName": "Advanced Eye Health",
            "activeIngredients": [omega, epa, dha],
            "inactiveIngredients": [],
        }
    )

    rows = result["ingredients_scorable"]
    assert len(rows) == 3
    row = next(item for item in rows if item["name"] == "Omega-3 Fatty Acids")
    assert row["canonical_id"] == "fish_oil"
    assert row["form_id"] == "fish oil (unspecified)"
    assert row["is_blend_header"] is False
    assert row["is_parent_total"] is True
    assert row["has_dose"] is True
    assert result["unmapped_scorable_count"] == 0


def test_generic_omega3_without_children_uses_unspecified_form(
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
        raw_source_path="ingredientRows[0]",
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
            "id": "generic-omega-3",
            "fullName": "Generic Omega-3",
            "activeIngredients": [omega],
            "inactiveIngredients": [],
        }
    )

    assert result["unmapped_scorable_count"] == 0
    assert len(result["ingredients_scorable"]) == 1
    row = result["ingredients_scorable"][0]
    assert row["canonical_id"] == "fish_oil"
    assert row["form_id"] == "fish oil (unspecified)"
    assert row["is_parent_total"] is False
    assert "eicosatrienoic" not in str(row["matched_form"]).lower()


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


@pytest.mark.parametrize(
    ("row", "expected_canonical"),
    [
        (
            _active_row(
                name="Palmitic Acid Monoethanolamide",
                raw_source_text="Palmitic Acid Monoethanolamide",
                standardName="Palmitoylethanolamide",
                canonical_id="palmitoylethanolamide",
                cleaner_match_method="unii_exact_match",
                quantity=25.0,
                forms=[],
                ingredientGroup="Palmitic Acid",
                uniiCode="6R8T1UDM3V",
                raw_taxonomy={
                    "category": "fatty acid",
                    "ingredientGroup": "Palmitic Acid",
                    "uniiCode": "6R8T1UDM3V",
                    "forms": [],
                },
            ),
            "palmitoylethanolamide",
        ),
        (
            _active_row(
                name="Natto Extract",
                raw_source_text="Natto Extract",
                standardName="Nattokinase",
                canonical_id="nattokinase",
                cleaner_match_method="unii_form_exact_match",
                quantity=110.0,
                ingredientGroup="Soy",
                forms=[
                    {
                        "name": "Nattokinase",
                        "category": "enzyme",
                        "ingredientGroup": "Nattokinase",
                        "uniiCode": "H81695M5OP",
                    }
                ],
                raw_taxonomy={
                    "category": "botanical",
                    "ingredientGroup": "Soy",
                    "uniiCode": None,
                    "forms": [
                        {
                            "name": "Nattokinase",
                            "category": "enzyme",
                            "ingredientGroup": "Nattokinase",
                            "uniiCode": "H81695M5OP",
                        }
                    ],
                },
                dose_class="enzyme_activity",
                activity_quantity=20_000.0,
                activity_unit="FU",
            ),
            "nattokinase",
        ),
    ],
)
def test_coherent_exact_unii_identity_beats_broader_structured_group(
    enricher: SupplementEnricherV3,
    row: dict,
    expected_canonical: str,
) -> None:
    result = enricher._collect_ingredient_quality_data(
        {
            "id": f"unii-{expected_canonical}",
            "fullName": row["name"],
            "activeIngredients": [row],
            "inactiveIngredients": [],
        }
    )

    assert len(result["ingredients_scorable"]) == 1
    mapped = result["ingredients_scorable"][0]
    assert mapped["canonical_id"] == expected_canonical
    assert mapped["scoreable_identity"] is True


@pytest.mark.parametrize(
    ("row", "expected_canonical"),
    [
        (
            _active_row(
                name="Calcium",
                raw_source_text="Calcium",
                standardName="Vitamin B5 (Pantothenic Acid)",
                canonical_id="vitamin_b5_pantothenic",
                cleaner_match_method="unii_form_exact_match",
                quantity=75.0,
                ingredientGroup="Calcium",
                forms=[
                    {
                        "name": "Calcium Pantothenate",
                        "category": "mineral",
                        "ingredientGroup": "Calcium",
                        "uniiCode": "568ET80C3D",
                    }
                ],
                raw_taxonomy={
                    "category": "mineral",
                    "ingredientGroup": "Calcium",
                    "forms": [
                        {
                            "name": "Calcium Pantothenate",
                            "category": "mineral",
                            "ingredientGroup": "Calcium",
                            "uniiCode": "568ET80C3D",
                        }
                    ],
                },
            ),
            "calcium",
        ),
        (
            _active_row(
                name="Alpha-Linolenic Acid",
                raw_source_text="Alpha-Linolenic Acid",
                standardName="Minor Omega-3 Fatty Acids & SPM Precursors",
                canonical_id="omega_3",
                cleaner_match_method="unii_form_exact_match",
                quantity=540.0,
                ingredientGroup="Alpha-Linolenic Acid",
                alternateNames=["ALA", "C18:3n-3"],
                forms=[
                    {
                        "name": "Omega-3 Fatty Acids",
                        "category": "fatty acid",
                        "ingredientGroup": "Omega-3",
                        "uniiCode": "71M78END5S",
                    }
                ],
                raw_taxonomy={
                    "category": "fatty acid",
                    "ingredientGroup": "Alpha-Linolenic Acid",
                    "forms": [
                        {
                            "name": "Omega-3 Fatty Acids",
                            "category": "fatty acid",
                            "ingredientGroup": "Omega-3",
                            "uniiCode": "71M78END5S",
                        }
                    ],
                },
            ),
            "alpha_linolenic_acid",
        ),
        (
            _active_row(
                name="Eicosapentaenoic Acid",
                raw_source_text="Eicosapentaenoic Acid",
                standardName="Minor Omega-3 Fatty Acids & SPM Precursors",
                canonical_id="omega_3",
                cleaner_match_method="unii_form_exact_match",
                quantity=180.0,
                ingredientGroup="EPA (Eicosapentaenoic Acid)",
                alternateNames=["EPA"],
                forms=[
                    {
                        "name": "Omega-3 Fatty Acids",
                        "category": "fatty acid",
                        "ingredientGroup": "Omega-3",
                        "uniiCode": "71M78END5S",
                    }
                ],
                raw_taxonomy={
                    "category": "fatty acid",
                    "ingredientGroup": "EPA (Eicosapentaenoic Acid)",
                    "forms": [
                        {
                            "name": "Omega-3 Fatty Acids",
                            "category": "fatty acid",
                            "ingredientGroup": "Omega-3",
                            "uniiCode": "71M78END5S",
                        }
                    ],
                },
            ),
            "epa",
        ),
        (
            _active_row(
                name="DHA",
                raw_source_text="DHA",
                standardName="Minor Omega-3 Fatty Acids & SPM Precursors",
                canonical_id="omega_3",
                cleaner_match_method="unii_form_exact_match",
                quantity=200.0,
                ingredientGroup="DHA (Docosahexaenoic Acid)",
                alternateNames=["Docosahexaenoic Acid"],
                forms=[
                    {
                        "name": "Omega-3 Fatty Acids",
                        "category": "fatty acid",
                        "ingredientGroup": "Omega-3",
                        "uniiCode": "71M78END5S",
                    }
                ],
                raw_taxonomy={
                    "category": "fatty acid",
                    "ingredientGroup": "DHA (Docosahexaenoic Acid)",
                    "forms": [
                        {
                            "name": "Omega-3 Fatty Acids",
                            "category": "fatty acid",
                            "ingredientGroup": "Omega-3",
                            "uniiCode": "71M78END5S",
                        }
                    ],
                },
            ),
            "dha",
        ),
        (
            _active_row(
                name="Saccharomyces boulardii",
                raw_source_text="Saccharomyces boulardii",
                standardName="Brewer's Yeast",
                canonical_id="brewers_yeast",
                cleaner_match_method="unii_exact_match",
                quantity=250.0,
                ingredientGroup="Saccharomyces boulardii",
                uniiCode="978D8U419H",
                forms=[],
                raw_taxonomy={
                    "category": "botanical",
                    "ingredientGroup": "Saccharomyces boulardii",
                    "uniiCode": "978D8U419H",
                    "forms": [],
                },
            ),
            "saccharomyces_boulardii",
        ),
        (
            _active_row(
                name="Proteases",
                raw_source_text="Proteases",
                standardName="Bacillus Subtilis",
                canonical_id="bacillus_subtilis",
                cleaner_match_method="unii_form_exact_match",
                quantity=3500.0,
                unit="HUT",
                dose_class="enzyme_activity",
                ingredientGroup="Proteolytic Enzymes (Proteases)",
                forms=[
                    {
                        "name": "Bacillus subtilis",
                        "category": "bacteria",
                        "ingredientGroup": "Bacillus Subtilis",
                        "uniiCode": "8CF93KW41W",
                    }
                ],
                raw_taxonomy={
                    "category": "enzyme",
                    "ingredientGroup": "Proteolytic Enzymes (Proteases)",
                    "forms": [
                        {
                            "name": "Bacillus subtilis",
                            "category": "bacteria",
                            "ingredientGroup": "Bacillus Subtilis",
                            "uniiCode": "8CF93KW41W",
                        }
                    ],
                },
            ),
            "digestive_enzymes",
        ),
    ],
)
def test_exact_label_identity_beats_source_or_salt_form_identity(
    enricher: SupplementEnricherV3,
    row: dict,
    expected_canonical: str,
) -> None:
    result = enricher._collect_ingredient_quality_data(
        {
            "id": f"label-authority-{expected_canonical}",
            "fullName": row["name"],
            "activeIngredients": [row],
            "inactiveIngredients": [],
        }
    )

    assert result["unmapped_scorable_count"] == 0
    assert len(result["ingredients_scorable"]) == 1
    mapped = result["ingredients_scorable"][0]
    assert mapped["canonical_id"] == expected_canonical
    assert mapped["scoreable_identity"] is True
