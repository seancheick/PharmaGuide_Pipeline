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


def test_algal_source_oil_above_nested_epa_dha_mass_is_parent_total(
    enricher: SupplementEnricherV3,
) -> None:
    parent = _active_row(
        name="life's OMEGA",
        raw_source_text="life's OMEGA",
        standardName="Algae Oil",
        canonical_id="algae_oil",
        cleaner_match_method=None,
        quantity=1400.0,
        forms=[
            {
                "name": "Algal Oil Concentrate",
                "category": "fat",
                "ingredientGroup": "Algal Oil",
                "uniiCode": None,
            }
        ],
        ingredientGroup="Algal Oil",
    )
    dha = _active_row(
        name="Docosahexaenoic Acid",
        raw_source_text="Docosahexaenoic Acid",
        standardName="DHA (Docosahexaenoic Acid)",
        canonical_id="dha",
        quantity=420.0,
        forms=[],
        isNestedIngredient=True,
        parentBlend="Total Omega-3 Fatty Acids",
    )
    epa = _active_row(
        name="Eicosapentaenoic Acid",
        raw_source_text="Eicosapentaenoic Acid",
        standardName="EPA (Eicosapentaenoic Acid)",
        canonical_id="epa",
        quantity=210.0,
        forms=[],
        isNestedIngredient=True,
        parentBlend="Total Omega-3 Fatty Acids",
    )

    result = enricher._collect_ingredient_quality_data(
        {
            "id": "326301",
            "fullName": "Vegan Omega + D3",
            "activeIngredients": [parent, dha, epa],
            "inactiveIngredients": [],
        }
    )

    assert result["unmapped_scorable_count"] == 0
    row = next(
        item
        for item in result["ingredients_scorable"]
        if item["name"] == "life's OMEGA"
    )
    assert row["canonical_id"] == "algae_oil"
    assert row["is_parent_total"] is True


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


@pytest.mark.parametrize(
    ("name", "group", "canonical_id", "standard_name", "expected_canonical"),
    [
        ("Corn Silk", "Corn", "corn_silk", "Corn Silk", "corn_silk"),
        (
            "Sicilian Blood Orange fruit and peel extract",
            "Sweet Orange",
            "blood_orange_extract",
            "Blood Orange Extract",
            "blood_orange_extract",
        ),
        (
            "Phenylethylamine Hydrochloride",
            "Phenethylamine (PEA)",
            "phenylethylamine",
            "Phenylethylamine",
            "phenylethylamine",
        ),
        (
            "Bovine Bile concentrate",
            "Bovine (not specified)",
            "bile_extract",
            "Bile Extract",
            "bile_extract",
        ),
        (
            "Purple Corn extract",
            "Corn",
            "purple_corn_extract",
            "Purple Corn Extract",
            "purple_corn_extract",
        ),
        (
            "NutraFlora scFOS",
            "Fructo-Oligosaccharides (FOS)",
            "prebiotics",
            "Prebiotics",
            "prebiotics",
        ),
        (
            "Beta-1,3-1,6-D-Glucan",
            "Beta-Glucans",
            "brewers_yeast",
            "Brewer's Yeast",
            "beta_glucan",
        ),
        (
            "Algal Docosahexaenoic Acid",
            "DHA",
            "algae_oil",
            "Algae Oil",
            "dha",
        ),
        (
            "Nicotinamide Adenine Dinucleotide",
            "Nicotinamide Adenine Dinucleotide",
            "nadh",
            "NADH",
            "nad",
        ),
    ],
)
def test_reviewed_same_identity_alias_beats_broader_source_group(
    enricher: SupplementEnricherV3,
    name: str,
    group: str,
    canonical_id: str,
    standard_name: str,
    expected_canonical: str,
) -> None:
    forms = (
        [
            {
                "name": "Schizochytrium sp. Oil",
                "category": "other",
                "ingredientGroup": "Schizochytrium",
                "uniiCode": None,
            }
        ]
        if expected_canonical == "dha"
        else []
    )
    row = _active_row(
        name=name,
        raw_source_text=name,
        standardName=standard_name,
        canonical_id=canonical_id,
        cleaner_match_method=None,
        quantity=100.0,
        ingredientGroup=group,
        forms=forms,
        raw_taxonomy={
            "category": "botanical",
            "ingredientGroup": group,
            "forms": forms,
        },
    )
    result = enricher._collect_ingredient_quality_data(
        {
            "id": f"reviewed-alias-{expected_canonical}",
            "fullName": name,
            "activeIngredients": [row],
            "inactiveIngredients": [],
        }
    )

    assert result["unmapped_scorable_count"] == 0
    assert len(result["ingredients_scorable"]) == 1
    mapped = result["ingredients_scorable"][0]
    assert mapped["canonical_id"] == expected_canonical
    assert mapped["scoreable_identity"] is True
    if expected_canonical == "dha":
        assert mapped["form_id"] == "algal triglyceride"


@pytest.mark.parametrize(
    ("name", "standard_name", "source_group", "expected_canonical"),
    [
        ("Corn Silk Powder", "Corn Silk", "Corn", "corn_silk"),
        ("Natto extract", "Nattokinase", "Soy", "nattokinase"),
        ("Naringin", "Naringin", "Naringenin", "naringin"),
        ("Soy germ extract", "Isoflavones", "Soy", "isoflavones"),
        (
            "Adenosine 5'-Triphosphate Disodium",
            "ATP (Adenosine Triphosphate)",
            "Adenosine",
            "atp",
        ),
        (
            "Oligomeric proanthocyanidins",
            "OPCs (Oligomeric Proanthocyanidins)",
            "Proanthocyanidins (unspecified)",
            "opc",
        ),
        ("Prebiotic", "Prebiotics", "Fiber (unspecified)", "prebiotics"),
        ("Zeaxanthin", "Zeaxanthin", "Lutein", "zeaxanthin"),
        ("Alpha-Amylase", "Alpha-Amylase", "Amylase", "alpha_amylase"),
        (
            "Epigallocatechin",
            "Epigallocatechin (EGC)",
            "EGCG",
            "epigallocatechin",
        ),
        ("Methyliberine", "Methylliberine", "Caffeine", "methylliberine"),
        (
            "Omega-9 Fatty Acids",
            "Omega-9 Fatty Acids",
            "Omega-9",
            "omega_9_fatty_acids",
        ),
        ("Vitamin K", "Brewer's Yeast", "Vitamin K", "vitamin_k"),
        (
            "fermented Soybean powder",
            "Nattokinase",
            "Soy",
            "nattokinase",
        ),
        ("Touchi extract", "Touchi Extract", "Soy", "touchi_extract"),
        ("Ginsenoside Rg3", "Ginsenoside Rg3", "Ginsenosides", "rg3"),
        (
            "Fermented Goat's Milk Whey",
            "Goat Whey Protein",
            "Whey",
            "goat_whey_protein",
        ),
        (
            "S. thermophilus",
            "Probiotics",
            "Streptococcus Thermophilus",
            "streptococcus_thermophilus",
        ),
    ],
)
def test_exact_reviewed_label_is_not_repaired_to_broader_source_group(
    enricher: SupplementEnricherV3,
    name: str,
    standard_name: str,
    source_group: str,
    expected_canonical: str,
) -> None:
    """Reduced July-16 misses: literal curated identity outranks DSLD grouping."""
    row = _active_row(
        name=name,
        raw_source_text=name,
        standardName=standard_name,
        canonical_id=expected_canonical,
        cleaner_match_method=None,
        quantity=100.0,
        ingredientGroup=source_group,
        forms=[],
        raw_taxonomy={
            "category": "botanical",
            "ingredientGroup": source_group,
            "forms": [],
        },
    )

    result = enricher._collect_ingredient_quality_data(
        {
            "id": f"literal-authority-{expected_canonical}",
            "fullName": name,
            "activeIngredients": [row],
            "inactiveIngredients": [],
        }
    )

    assert result["unmapped_scorable_count"] == 0
    assert len(result["ingredients_scorable"]) == 1
    mapped = result["ingredients_scorable"][0]
    assert mapped["canonical_id"] == expected_canonical
    assert mapped["identity_disposition"] in {"clean", "repaired"}
    assert mapped["scoreable_identity"] is True


@pytest.mark.parametrize(
    ("name", "standard_name", "initial_canonical", "group", "forms", "expected"),
    [
        (
            "Tri-MG(TM)",
            "Magnesium",
            "magnesium",
            "Betaine",
            [{"name": "Betaine Anhydrous", "ingredientGroup": "Betaine Anhydrous"}],
            "tmg_betaine",
        ),
        (
            "Micronized alpha-Ketoglutarate",
            "Creatine Monohydrate",
            "creatine_monohydrate",
            "Alpha-Ketoglutarate",
            [],
            "alpha_ketoglutarate",
        ),
        (
            "Delphinol",
            "Delphinidin",
            "delphinidin",
            "Maqui",
            [],
            "maqui_berry",
        ),
        (
            "Ox Bile extract",
            "Digestive Enzymes",
            "digestive_enzymes",
            "Bile",
            [],
            "bile_extract",
        ),
        (
            "Elantria",
            "Algae Oil",
            "algae_oil",
            "Fish Oil",
            [],
            "algae_oil",
        ),
    ],
)
def test_reviewed_literal_corrects_stale_or_broader_cleaner_identity(
    enricher: SupplementEnricherV3,
    name: str,
    standard_name: str,
    initial_canonical: str,
    group: str,
    forms: list[dict],
    expected: str,
) -> None:
    row = _active_row(
        name=name,
        raw_source_text=name,
        standardName=standard_name,
        canonical_id=initial_canonical,
        canonical_source_db="ingredient_quality_map",
        cleaner_match_method=None,
        quantity=100.0,
        ingredientGroup=group,
        forms=forms,
        raw_taxonomy={
            "category": "non-nutrient/non-botanical",
            "ingredientGroup": group,
            "forms": forms,
        },
    )

    result = enricher._collect_ingredient_quality_data(
        {
            "id": f"reviewed-correction-{expected}",
            "fullName": name,
            "activeIngredients": [row],
            "inactiveIngredients": [],
        }
    )

    assert result["unmapped_scorable_count"] == 0
    assert [item["canonical_id"] for item in result["ingredients_scorable"]] == [
        expected
    ]


def test_percent_probiotic_child_keeps_reviewed_strain_identity(
    enricher: SupplementEnricherV3,
) -> None:
    row = _active_row(
        name="S. thermophilus",
        raw_source_text="S. thermophilus",
        standardName="Probiotics",
        canonical_id="probiotics",
        cleaner_match_method=None,
        quantity=10.0,
        unit="%",
        ingredientGroup="Streptococcus Thermophilus",
        forms=[],
        parentBlend="Probiotic Complex Blend",
        parentBlendMass=4_000_000_000,
        parentBlendUnit="Organism(s)",
        isNestedIngredient=True,
        raw_taxonomy={
            "category": "bacteria",
            "ingredientGroup": "Streptococcus Thermophilus",
            "forms": [],
            "parentBlend": "Probiotic Complex Blend",
            "isNestedIngredient": True,
            "quantityVariants": [{"quantity": 10.0, "unit": "%"}],
        },
    )

    result = enricher._collect_ingredient_quality_data(
        {
            "id": "799",
            "fullName": "Probiotic Complex 4",
            "activeIngredients": [row],
            "inactiveIngredients": [],
        }
    )

    assert result["unmapped_scorable_count"] == 0
    assert [item["canonical_id"] for item in result["ingredients_scorable"]] == [
        "streptococcus_thermophilus"
    ]


@pytest.mark.parametrize(
    (
        "name",
        "source_group",
        "marker_canonical",
        "expected_source_canonical",
        "expected_source_db",
    ),
    [
        ("Silexan", "English Lavender", "linalool", "lavender", "botanical_ingredients"),
        (
            "Artichoke Leaf, Stem Extract",
            "Artichoke",
            "cynarin",
            "globe_artichoke",
            "botanical_ingredients",
        ),
        (
            "Shark Cartilage",
            "Cartilage",
            "chondroitin",
            "OI_SHARK_CARTILAGE",
            "other_ingredients",
        ),
        (
            "Clovinol Clove Flower Bud Extract",
            "Clove",
            "eugenol",
            "cloves",
            "botanical_ingredients",
        ),
    ],
)
def test_source_extract_alias_does_not_become_marker_identity(
    enricher: SupplementEnricherV3,
    name: str,
    source_group: str,
    marker_canonical: str,
    expected_source_canonical: str,
    expected_source_db: str,
) -> None:
    row = _active_row(
        name=name,
        raw_source_text=name,
        standardName=name,
        canonical_id=marker_canonical,
        cleaner_match_method=None,
        quantity=100.0,
        ingredientGroup=source_group,
        forms=[],
        raw_taxonomy={
            "category": "botanical",
            "ingredientGroup": source_group,
            "forms": [],
        },
    )
    result = enricher._collect_ingredient_quality_data(
        {
            "id": f"source-marker-{marker_canonical}",
            "fullName": name,
            "activeIngredients": [row],
            "inactiveIngredients": [],
        }
    )

    assert all(
        item.get("canonical_id") != marker_canonical
        for item in result["ingredients_scorable"]
    )
    assert result["unmapped_scorable_count"] == 0
    recognized = result["ingredients_recognized_non_scorable"]
    assert len(recognized) == 1
    assert recognized[0]["canonical_id"] == expected_source_canonical
    assert recognized[0]["canonical_source_db"] == expected_source_db
    assert recognized[0]["mapped_identity"] is True
    assert recognized[0]["scoreable_identity"] is False
    assert recognized[0]["role_classification"] == "recognized_non_scorable"


def test_botanical_marker_demotion_replaces_stale_identity_conflict(
    enricher: SupplementEnricherV3,
) -> None:
    """Reduced GNC row: source lineage is mapped, but never marker-scored."""
    row = _active_row(
        name="Cinnamon bark powder",
        raw_source_text="Cinnamon bark powder",
        standardName="Cinnamon",
        canonical_id="cinnamon",
        canonical_source_db="ingredient_quality_map",
        cleaner_match_method=None,
        quantity=500.0,
        ingredientGroup="Cinnamomum burmanii",
        forms=[],
        raw_taxonomy={
            "category": "botanical",
            "ingredientGroup": "Cinnamomum burmanii",
            "forms": [],
        },
    )

    result = enricher._collect_ingredient_quality_data(
        {
            "id": "gnc-cinnamon-marker-lineage",
            "fullName": "Cinnamon",
            "activeIngredients": [row],
            "inactiveIngredients": [],
        }
    )

    assert result["ingredients_scorable"] == []
    recognized = result["ingredients_recognized_non_scorable"]
    assert len(recognized) == 1
    assert recognized[0]["canonical_id"] == "cinnamon_bark"
    assert recognized[0]["identity_disposition"] == "taxonomy_only"
    assert recognized[0]["identity_decision_reason"] == (
        "botanical_marker_is_secondary_metadata"
    )
    assert recognized[0]["scoreable_identity"] is False


def test_iqm_source_parent_is_not_replaced_by_structured_marker_form(
    enricher: SupplementEnricherV3,
) -> None:
    """A standardized marker decorates the source; it is not the active identity."""
    row = _active_row(
        name="Phase 2 Carb Controller White Kidney Bean extract",
        raw_source_text="Phase 2 Carb Controller White Kidney Bean extract",
        standardName="Common Bean Extract",
        canonical_id="common_bean_extract",
        canonical_source_db="ingredient_quality_map",
        cleaner_match_method=None,
        quantity=1.0,
        unit="Gram(s)",
        ingredientGroup="Bean",
        forms=[
            {
                "name": "Alpha-Amylase",
                "prefix": "standardized for",
                "category": "enzyme",
                "ingredientGroup": "Amylase",
                "uniiCode": "0",
            }
        ],
        raw_taxonomy={
            "category": "botanical",
            "ingredientGroup": "Bean",
            "forms": [
                {
                    "name": "Alpha-Amylase",
                    "prefix": "standardized for",
                    "category": "enzyme",
                    "ingredientGroup": "Amylase",
                    "uniiCode": "0",
                }
            ],
        },
    )

    result = enricher._collect_ingredient_quality_data(
        {
            "id": "213183",
            "fullName": "White Kidney Bean 1,000 mg",
            "activeIngredients": [row],
            "inactiveIngredients": [],
        }
    )

    assert result["unmapped_scorable_count"] == 0
    assert len(result["ingredients_scorable"]) == 1
    scored = result["ingredients_scorable"][0]
    assert scored["canonical_id"] == "common_bean_extract"
    assert scored["identity_disposition"] in {"clean", "repaired"}
    assert scored["scoreable_identity"] is True


def test_branded_green_coffee_source_is_not_replaced_by_chlorogenic_marker(
    enricher: SupplementEnricherV3,
) -> None:
    row = _active_row(
        name="CoffeeGenic Green Coffee extract",
        raw_source_text="CoffeeGenic Green Coffee extract",
        standardName="Green Coffee Bean",
        canonical_id="green_coffee_bean",
        canonical_source_db="standardized_botanicals",
        cleaner_match_method=None,
        branded_token_extracted="CoffeeGenic",
        quantity=400.0,
        ingredientGroup="Green Coffee",
        forms=[
            {
                "name": "Chlorogenic Acids",
                "prefix": "std. to",
                "percent": 50,
                "category": "non-nutrient/non-botanical",
                "ingredientGroup": "chlorogenic acid",
            }
        ],
        raw_taxonomy={
            "category": "botanical",
            "ingredientGroup": "Green Coffee",
            "forms": [
                {
                    "name": "Chlorogenic Acids",
                    "prefix": "std. to",
                    "percent": 50,
                    "category": "non-nutrient/non-botanical",
                    "ingredientGroup": "chlorogenic acid",
                }
            ],
        },
    )

    result = enricher._collect_ingredient_quality_data(
        {
            "id": "231908",
            "fullName": "Green Coffee Extract CoffeeGenic 400 mg",
            "activeIngredients": [row],
            "inactiveIngredients": [],
        }
    )

    assert result["unmapped_scorable_count"] == 0
    assert result["ingredients_scorable"] == []
    assert len(result["ingredients_recognized_non_scorable"]) == 1
    recognized = result["ingredients_recognized_non_scorable"][0]
    assert recognized["canonical_id"] == "green_coffee_bean"
    assert recognized["identity_disposition"] == "taxonomy_only"
    assert recognized["scoreable_identity"] is False


def test_stale_botanical_source_recovery_uses_bounded_identity_index(
    enricher: SupplementEnricherV3,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The source-marker guard must never fall into exhaustive recognition.

    This path runs for every IQM candidate. A full non-scorable scan on an
    ordinary miss caused a 3-7x corpus enrichment regression. Stale source
    recovery is intentionally limited to aliases already present in the
    deterministic normalized identity index.
    """

    def fail_full_scan(*_args, **_kwargs):
        raise AssertionError("source recovery invoked exhaustive recognition")

    monkeypatch.setattr(enricher, "_is_recognized_non_scorable", fail_full_scan)

    ordinary_iqm_row = _active_row(
        name="Magnesium",
        raw_source_text="Magnesium",
        standardName="Magnesium",
        canonical_id="magnesium",
        canonical_source_db="ingredient_quality_map",
    )
    assert enricher._botanical_source_identity(ordinary_iqm_row) is None

    stale_pycrinil_row = _active_row(
        name="Pycrinil Artichoke extract",
        raw_source_text="Pycrinil Artichoke extract",
        standardName="Cynarin",
        canonical_id="cynarin",
        canonical_source_db="ingredient_quality_map",
    )
    assert enricher._botanical_source_identity(stale_pycrinil_row) == (
        "globe_artichoke",
        "botanical_ingredients",
    )


def test_static_banned_alias_filter_is_reused(
    enricher: SupplementEnricherV3,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    aliases = [
        "performance-cache-specific-substance",
        "performance-cache extract",
    ]
    calls = 0
    original = enricher._is_low_precision_token_alias

    def counted(alias: str) -> bool:
        nonlocal calls
        calls += 1
        return original(alias)

    monkeypatch.setattr(enricher, "_is_low_precision_token_alias", counted)
    first = enricher._filter_safe_token_aliases("Performance Cache", aliases)
    first_calls = calls
    second = enricher._filter_safe_token_aliases("Performance Cache", aliases)

    assert first == second
    assert first_calls == len(aliases)
    assert calls == first_calls


@pytest.mark.parametrize(
    ("source_id", "marker_id"),
    [
        ("lavender", "linalool"),
        ("globe_artichoke", "cynarin"),
        ("cloves", "eugenol"),
        ("mulberry", "dnj_1_deoxynojirimycin"),
        ("horny_goat_weed", "icariin"),
        ("siberian_rhubarb", "rhaponticin"),
        ("wakame", "fucoidan"),
    ],
)
def test_botanical_source_identity_blocks_any_iqm_cross_parent(
    enricher: SupplementEnricherV3,
    source_id: str,
    marker_id: str,
) -> None:
    ingredient = {
        "canonical_id": source_id,
        "canonical_source_db": "botanical_ingredients",
        "forms": [],
    }

    assert enricher._is_blocked_botanical_source_marker_match(
        ingredient,
        {"canonical_id": marker_id},
    ) is True
    assert enricher._is_blocked_botanical_source_marker_match(
        ingredient,
        {"canonical_id": source_id},
    ) is False
