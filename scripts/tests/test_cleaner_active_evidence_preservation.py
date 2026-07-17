import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from enhanced_normalizer import EnhancedDSLDNormalizer  # noqa: E402


def _clean(raw):
    return EnhancedDSLDNormalizer().normalize_product(raw)


def _active_names(cleaned):
    return {
        str(row.get("name") or row.get("raw_source_text") or "").lower()
        for row in cleaned.get("activeIngredients") or []
    }


def _active_canonicals(cleaned):
    return {
        str(row.get("canonical_id") or "").lower()
        for row in cleaned.get("activeIngredients") or []
    }


def test_active_proprietary_blend_forms_are_preserved_as_scoreable_actives():
    raw = {
        "id": "fixture-botanical-blend-forms",
        "fullName": "Fem-Mend Synergistic Blend",
        "ingredientRows": [
            {
                "name": "Proprietary Blend",
                "ingredientGroup": "Proprietary Blend (Herb/Botanical)",
                "category": "blend",
                "quantity": [{"quantity": 860, "unit": "mg"}],
                "forms": [
                    {"name": "Ginger", "ingredientGroup": "Ginger"},
                    {"name": "Goldenseal", "ingredientGroup": "Goldenseal"},
                    {"name": "Red Raspberry", "ingredientGroup": "Red Raspberry"},
                ],
            }
        ],
        "otheringredients": {"ingredients": [{"name": "Gelatin"}]},
    }

    cleaned = _clean(raw)

    names = _active_names(cleaned)
    assert "ginger" in names
    assert "goldenseal" in names
    assert all(
        row.get("score_eligible_by_cleaner") is True
        for row in cleaned["activeIngredients"]
    )


def test_active_probiotic_blend_forms_are_preserved_as_scoreable_actives():
    raw = {
        "id": "fixture-probiotic-blend-forms",
        "fullName": "Extra Strength Probiotic 15 mg",
        "ingredientRows": [
            {
                "name": "Proprietary Probiotic Blend",
                "ingredientGroup": "Bifidobacterium (mixed)",
                "category": "bacteria",
                "quantity": [{"quantity": 15, "unit": "mg"}],
                "forms": [
                    {"name": "Bifidobacterium longum"},
                    {"name": "Lactobacillus acidophilus"},
                ],
            }
        ],
        "otheringredients": {"ingredients": [{"name": "Gelatin"}]},
    }

    cleaned = _clean(raw)

    names = _active_names(cleaned)
    assert "bifidobacterium longum" in names
    assert "lactobacillus acidophilus" in names


def test_nested_dsld_blend_header_is_not_promoted_to_scoreable_active():
    raw = {
        "id": "fixture-nested-dsld-blend",
        "fullName": "Nested Blend Product",
        "ingredientRows": [
            {
                "name": "Thermogenic Activator",
                "ingredientGroup": "Blend",
                "category": "blend",
                "quantity": [{"quantity": 0, "unit": "Not Present"}],
                "nestedRows": [
                    {
                        "name": "Caffeine Anhydrous",
                        "ingredientGroup": "Caffeine",
                        "quantity": [{"quantity": 200, "unit": "mg"}],
                    }
                ],
            }
        ],
        "otheringredients": {"ingredients": []},
    }

    cleaned = _clean(raw)

    header = next(
        row
        for row in cleaned["activeIngredients"]
        if row.get("raw_source_text") == "Thermogenic Activator"
    )
    child = next(
        row
        for row in cleaned["activeIngredients"]
        if row.get("raw_source_text") == "Caffeine Anhydrous"
    )
    assert header["cleaner_row_role"] == "blend_header_total"
    assert header["score_eligible_by_cleaner"] is False
    assert header["dose_class"] == "blend_total_weight"
    assert child["score_eligible_by_cleaner"] is True


def test_active_omega_rollup_compound_forms_split_to_epa_and_dha():
    raw = {
        "id": "fixture-omega-compound-forms",
        "fullName": "High Potency EPA & DHA",
        "ingredientRows": [
            {
                "name": "Total Omega-3 Fatty Acids",
                "ingredientGroup": "Omega-3 Fatty Acid",
                "category": "fatty-acid",
                "quantity": [{"quantity": 1065, "unit": "mg"}],
                "forms": [
                    {"name": "Total DHA, EPA"},
                    {"name": "Other Omega-3 Fatty Acids"},
                ],
            }
        ],
        "otheringredients": {
            "ingredients": [{"name": "Fish Body Oil"}, {"name": "Gelatin"}]
        },
    }

    cleaned = _clean(raw)

    names = _active_names(cleaned)
    canonicals = _active_canonicals(cleaned)
    assert "dha" in names or "dha" in canonicals
    assert "epa" in names or "epa" in canonicals
    assert "other omega-3 fatty acids" not in names


def test_other_fatty_acids_is_a_composition_rollup_not_an_active():
    raw = {
        "id": "fixture-other-fatty-acids-rollup",
        "fullName": "Organic Flaxseed Oil",
        "ingredientRows": [
            {
                "name": "Organic Flaxseed Oil",
                "ingredientGroup": "Flaxseed",
                "category": "botanical",
                "quantity": [{"quantity": 1000, "unit": "mg"}],
                "nestedRows": [
                    {
                        "name": "Other Fatty Acids",
                        "ingredientGroup": "Fatty acids",
                        "category": "fatty acid",
                        "quantity": [{"quantity": 50, "unit": "mg"}],
                    }
                ],
            }
        ],
        "otheringredients": {"ingredients": []},
    }

    cleaned = _clean(raw)

    active_names = _active_names(cleaned)
    assert "other fatty acids" not in active_names
    assert any(
        row.get("display_type") == "nutrition_fact"
        and str(row.get("raw_source_text") or row.get("name") or "").lower()
        == "other fatty acids"
        for row in cleaned.get("display_ingredients", [])
    )


def test_total_carotenoids_is_a_rollup_not_a_second_active():
    raw = {
        "id": "fixture-total-carotenoids-rollup",
        "fullName": "Mixed Carotenoid Formula",
        "ingredientRows": [
            {
                "name": "Total Carotenoids",
                "ingredientGroup": "carotenoids",
                "category": "non-nutrient/non-botanical",
                "quantity": [{"quantity": 10, "unit": "mg"}],
            }
        ],
        "otheringredients": {"ingredients": []},
    }

    cleaned = _clean(raw)

    assert "total carotenoids" not in _active_names(cleaned)
    assert any(
        row.get("display_type") == "nutrition_fact"
        for row in cleaned.get("display_ingredients", [])
    )


def test_active_omega_nested_compound_forms_split_to_epa_and_dha():
    raw = {
        "id": "fixture-omega-nested-compound-forms",
        "fullName": "Fish Oil Omega-3s",
        "ingredientRows": [
            {
                "name": "Total Omega-3s",
                "ingredientGroup": "Omega-3",
                "category": "fatty acid",
                "quantity": [{"quantity": 533, "unit": "mg"}],
                "nestedRows": [
                    {
                        "name": "Total DHA, EPA",
                        "ingredientGroup": "Blend",
                        "quantity": [{"quantity": 500, "unit": "mg"}],
                        "forms": [
                            {"name": "Docosahexaenoic Acid"},
                            {"name": "Eicosapentaenoic Acid"},
                        ],
                    },
                    {
                        "name": "Other Omega-3s",
                        "ingredientGroup": "Omega-3",
                        "quantity": [{"quantity": 33, "unit": "mg"}],
                    },
                ],
            }
        ],
        "otheringredients": {"ingredients": [{"name": "Fish Oil"}]},
    }

    cleaned = _clean(raw)

    canonicals = _active_canonicals(cleaned)
    assert "dha" in canonicals
    assert "epa" in canonicals


def test_title_matching_otheringredient_oil_rescues_active_identity_when_panel_is_empty():
    raw = {
        "id": "fixture-flax-otheringredient-active",
        "fullName": "Flax Seed Oil 1000 mg",
        "ingredientRows": [
            {"name": "Calories", "quantity": [{"quantity": 10, "unit": "kcal"}]},
            {"name": "Total Fat", "quantity": [{"quantity": 1, "unit": "g"}]},
        ],
        "otheringredients": {
            "ingredients": [
                {"name": "Flaxseed Oil"},
                {"name": "Gelatin"},
                {"name": "Glycerin"},
            ]
        },
    }

    cleaned = _clean(raw)

    canonicals = _active_canonicals(cleaned)
    names = _active_names(cleaned)
    assert "flaxseed" in canonicals or "flaxseed oil" in names
    rescued = cleaned["activeIngredients"][0]
    assert rescued.get("rescued_from_otheringredients_active_identity") is True
    assert rescued.get("score_eligible_by_cleaner") is True


def test_rescued_otheringredient_active_does_not_count_as_raw_inactive():
    raw = {
        "id": "fixture-coconut-oil-otheringredient-active",
        "fullName": "Coconut Oil",
        "ingredientRows": [
            {"name": "Calories", "quantity": [{"quantity": 120, "unit": "Calorie(s)"}]},
            {"name": "Total Fat", "quantity": [{"quantity": 14, "unit": "g"}]},
        ],
        "otheringredients": {
            "ingredients": [
                {
                    "name": "organic, unrefined, cold-pressed, extra virgin Coconut Oil",
                    "category": "fat",
                    "ingredientGroup": "coconut oil",
                }
            ]
        },
    }

    cleaned = _clean(raw)

    assert cleaned.get("inactiveIngredients") == []
    assert cleaned.get("raw_inactives_count") == 0
    rescued = cleaned["activeIngredients"][0]
    assert rescued.get("rescued_from_otheringredients_active_identity") is True
    assert "coconut" in str(rescued.get("name") or "").lower()


def test_otheringredients_probiotic_wrapper_rescues_named_strain_forms():
    raw = {
        "id": "fixture-otheringredients-probiotic-forms",
        "fullName": "FLORASSIST Oral Hygeine",
        "ingredientRows": [
            {"name": "Calories", "quantity": [{"quantity": 5, "unit": "Calorie(s)"}]},
            {"name": "Protein", "quantity": [{"quantity": 0, "unit": "g"}]},
        ],
        "otheringredients": {
            "ingredients": [
                {"name": "Xylitol"},
                {
                    "name": "Probiotics",
                    "forms": [{"name": "BLIS M18"}, {"name": "GanedenBC30"}],
                },
                {"name": "Maltodextrin"},
            ]
        },
    }

    cleaned = _clean(raw)

    canonicals = _active_canonicals(cleaned)
    names = _active_names(cleaned)
    assert "streptococcus_salivarius" in canonicals
    assert "bacillus_coagulans" in canonicals
    assert "probiotics" not in names
    assert all(
        row.get("rescued_from_otheringredients_active_identity") is True
        for row in cleaned["activeIngredients"]
    )


def test_dha_title_does_not_synthesize_missing_omega_identity_from_sunflower_oil():
    raw = {
        "id": "fixture-dha-title-only",
        "fullName": "DHA",
        "ingredientRows": [
            {
                "name": "Dextrose",
                "quantity": [{"quantity": 200, "unit": "mg"}],
                "forms": [{"name": "Glucose"}],
            }
        ],
        "otheringredients": {
            "ingredients": [
                {"name": "High Oleic Sunflower Oil"},
                {"name": "Sunflower Lecithin"},
                {"name": "Gelatin Capsule"},
            ]
        },
    }

    cleaned = _clean(raw)

    names = _active_names(cleaned)
    canonicals = _active_canonicals(cleaned)
    assert "dha" not in names
    assert "epa" not in names
    assert "fish_oil" not in canonicals
    assert all(
        row.get("rescued_from_otheringredients_active_identity") is not True
        for row in cleaned.get("activeIngredients") or []
    )
