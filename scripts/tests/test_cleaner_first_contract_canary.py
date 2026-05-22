import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from enhanced_normalizer import EnhancedDSLDNormalizer
from enrich_supplements_v3 import SupplementEnricherV3
from supplement_taxonomy import classify_supplement


def _first_named(rows, name):
    for row in rows:
        if row.get("name") == name or row.get("raw_source_text") == name:
            return row
    raise AssertionError(f"missing row {name!r}; found {[r.get('name') for r in rows]}")


def test_cleaner_contract_for_blend_header_enzyme_and_inactive_rows():
    cleaned = EnhancedDSLDNormalizer().normalize_product({
        "id": "cleaner-contract-test",
        "fullName": "Cleaner Contract Test",
        "brandName": "Contract Brand",
        "offMarket": 0,
        "contacts": [],
        "statements": [],
        "ingredientRows": [
            {
                "name": "Proprietary Blend",
                "category": "blend",
                "ingredientGroup": "Blend (Combination)",
                "order": 1,
                "quantity": [{"quantity": 1150, "unit": "mg"}],
                "nestedRows": [
                    {
                        "name": "Quercetin",
                        "category": "non-nutrient/non-botanical",
                        "ingredientGroup": "Quercetin",
                        "order": 2,
                        "quantity": [{"quantity": 0, "unit": "NP"}],
                    }
                ],
            },
            {
                "name": "Serrapeptase",
                "category": "enzyme",
                "ingredientGroup": "Serrapeptase",
                "order": 3,
                "quantity": [{"quantity": 120000, "unit": "SPU"}],
            },
            {
                "name": "Energy Blend",
                "category": "blend",
                "ingredientGroup": "Blend (Combination)",
                "order": 4,
                "quantity": [{"quantity": 250, "unit": "mg"}],
            },
        ],
        "otheringredients": {
            "ingredients": [
                {"name": "Leucine", "category": "amino acid", "ingredientGroup": "Leucine", "order": 1}
            ]
        },
    })

    blend = _first_named(cleaned["activeIngredients"], "Proprietary Blend")
    assert blend["source_section"] == "active"
    assert blend["raw_source_path"] == "ingredientRows[0]"
    assert blend["cleaner_row_role"] == "blend_header_total"
    assert blend["score_eligible_by_cleaner"] is False
    assert blend["score_exclusion_reason"] == "blend_header_total"
    assert blend["dose_class"] == "blend_total_weight"
    assert blend["hierarchyType"] == "blend_header"
    assert blend["raw_taxonomy"]["category"] == "blend"

    top_level_blend = _first_named(cleaned["activeIngredients"], "Energy Blend")
    assert top_level_blend["cleaner_row_role"] == "blend_header_total"
    assert top_level_blend["score_eligible_by_cleaner"] is False

    enzyme = _first_named(cleaned["activeIngredients"], "Serrapeptase")
    assert enzyme["cleaner_row_role"] == "active_scorable"
    assert enzyme["score_eligible_by_cleaner"] is True
    assert enzyme["dose_class"] == "enzyme_activity"

    inactive = _first_named(cleaned["inactiveIngredients"], "Leucine")
    assert inactive["source_section"] == "inactive"
    assert inactive["raw_source_path"] == "otheringredients.ingredients[0]"
    assert inactive["cleaner_row_role"] == "inactive"
    assert inactive["score_eligible_by_cleaner"] is False


def test_iqd_preserves_contract_and_blocks_default_inactive_rescue():
    product = {
        "fullName": "Inactive Leucine Capsule",
        "activeIngredients": [
            {
                "name": "Vitamin C",
                "standardName": "Vitamin C",
                "quantity": 500,
                "unit": "mg",
                "source_section": "active",
                "raw_source_path": "ingredientRows[0]",
                "cleaner_row_role": "active_scorable",
                "score_eligible_by_cleaner": True,
                "dose_class": "therapeutic_mass",
                "raw_taxonomy": {"category": "vitamin"},
            }
        ],
        "inactiveIngredients": [
            {
                "name": "Leucine",
                "standardName": "L-Leucine",
                "source_section": "inactive",
                "raw_source_path": "otheringredients.ingredients[0]",
                "cleaner_row_role": "inactive",
                "score_eligible_by_cleaner": False,
                "score_exclusion_reason": "inactive",
                "dose_class": "none",
            }
        ],
    }

    iqd = SupplementEnricherV3()._collect_ingredient_quality_data(product)

    assert iqd["promoted_from_inactive"] == []
    assert "Leucine" not in {row["name"] for row in iqd["ingredients_scorable"]}
    assert all(row.get("raw_source_path") for row in iqd["ingredients"])
    assert all("cleaner_row_role" in row for row in iqd["ingredients"])


def test_quatrefolic_nested_composition_rows_do_not_enter_scorable_iqd():
    product = {
        "fullName": "Fully Active B Complex with Quatrefolic",
        "activeIngredients": [
            {
                "name": "Quatrefolic",
                "standardName": "Vitamin B9 (Folate)",
                "quantity": 400,
                "unit": "mcg",
                "source_section": "active",
                "raw_source_path": "ingredientRows[0]",
                "cleaner_row_role": "active_scorable",
                "score_eligible_by_cleaner": True,
                "dose_class": "therapeutic_mass",
            },
            {
                "name": "(6S)-5-Methyltetrahydrofolic Acid, Glucosamine Salt",
                "standardName": "Vitamin B9 (Folate)",
                "quantity": 0,
                "unit": "NP",
                "source_section": "active",
                "raw_source_path": "ingredientRows[0].nestedRows[0]",
                "cleaner_row_role": "active_scorable",
                "score_eligible_by_cleaner": True,
                "dose_class": "zero_or_np",
                "isNestedIngredient": True,
                "parentBlend": "Quatrefolic",
                "parentBlendMass": 400,
                "parentBlendUnit": "mcg",
            },
            {
                "name": "(6S)-5-Methyltetrahydrofolic Acid",
                "standardName": "Vitamin B9 (Folate)",
                "quantity": 0,
                "unit": "NP",
                "source_section": "active",
                "raw_source_path": "ingredientRows[0].nestedRows[0].nestedRows[0]",
                "cleaner_row_role": "active_scorable",
                "score_eligible_by_cleaner": True,
                "dose_class": "zero_or_np",
                "isNestedIngredient": True,
                "parentBlend": "(6S)-5-Methyltetrahydrofolic Acid, Glucosamine Salt",
            },
        ],
    }

    iqd = SupplementEnricherV3()._collect_ingredient_quality_data(product)

    scorable_names = {row["name"] for row in iqd["ingredients_scorable"]}
    assert "Quatrefolic" in scorable_names
    assert "(6S)-5-Methyltetrahydrofolic Acid, Glucosamine Salt" not in scorable_names
    assert "(6S)-5-Methyltetrahydrofolic Acid" not in scorable_names

    skipped_names = {row["name"] for row in iqd["ingredients_skipped"]}
    assert "(6S)-5-Methyltetrahydrofolic Acid, Glucosamine Salt" in skipped_names
    assert "(6S)-5-Methyltetrahydrofolic Acid" in skipped_names


def test_generic_supplemental_chromium_does_not_match_hexavalent_chromium():
    hits = SupplementEnricherV3()._check_banned_substances(
        [{"name": "Chromium", "standardName": "Chromium", "canonical_id": "chromium"}]
    )
    assert "HM_CHROMIUM_HEXAVALENT" not in {
        row.get("banned_id") for row in hits.get("substances", [])
    }


def test_generic_chromium_with_bad_standard_name_does_not_match_hexavalent_chromium():
    hits = SupplementEnricherV3()._check_banned_substances(
        [
            {
                "name": "Chromium",
                "raw_source_text": "Chromium",
                "standardName": "Chromium (VI) — Hexavalent Chromium",
                "canonical_id": "chromium",
                "raw_taxonomy": {"category": "mineral", "ingredientGroup": "Chromium"},
            }
        ]
    )
    assert "HM_CHROMIUM_HEXAVALENT" not in {
        row.get("banned_id") for row in hits.get("substances", [])
    }


def test_explicit_hexavalent_chromium_still_matches_contaminant_gate():
    hits = SupplementEnricherV3()._check_banned_substances(
        [{"name": "Hexavalent Chromium", "standardName": "Chromium VI"}]
    )
    assert "HM_CHROMIUM_HEXAVALENT" in {
        row.get("banned_id") for row in hits.get("substances", [])
    }


def test_taxonomy_uses_scorable_rows_not_product_name_only_signals():
    omega_zyme = {
        "fullName": "Garden of Life Omega-Zyme Ultra Enzyme Blend",
        "ingredient_quality_data": {
            "ingredients_scorable": [
                {
                    "name": "Serrapeptase",
                    "canonical_id": "serrapeptase",
                    "category": "enzyme",
                    "quantity": 120000,
                    "unit": "SPU",
                    "score_eligible_by_cleaner": True,
                    "cleaner_row_role": "active_scorable",
                }
            ]
        },
    }
    assert classify_supplement(omega_zyme)["primary_type"] != "omega_3"

    liver_pm = {
        "fullName": "Liver Cleanser PM Packet",
        "ingredient_quality_data": {
            "ingredients_scorable": [
                {
                    "name": "Milk Thistle",
                    "canonical_id": "milk_thistle",
                    "category": "botanical",
                    "quantity": 250,
                    "unit": "mg",
                    "score_eligible_by_cleaner": True,
                    "cleaner_row_role": "active_scorable",
                },
                {
                    "name": "Dandelion Root",
                    "canonical_id": "dandelion",
                    "category": "botanical",
                    "quantity": 100,
                    "unit": "mg",
                    "score_eligible_by_cleaner": True,
                    "cleaner_row_role": "active_scorable",
                },
            ]
        },
    }
    assert classify_supplement(liver_pm)["primary_type"] != "sleep_support"


def test_spu_enzyme_row_is_valid_active_and_excipient_calcium_is_ignored():
    taxonomy = classify_supplement({
        "fullName": "Serrapeptase with Calcium Carrier",
        "ingredient_quality_data": {
            "ingredients_scorable": [
                {
                    "name": "Serrapeptase",
                    "canonical_id": "serrapeptase",
                    "category": "enzyme",
                    "quantity": 120000,
                    "unit": "SPU",
                    "score_eligible_by_cleaner": True,
                    "cleaner_row_role": "active_scorable",
                },
                {
                    "name": "Calcium",
                    "canonical_id": "calcium",
                    "category": "minerals",
                    "quantity": 20,
                    "unit": "mg",
                    "score_eligible_by_cleaner": False,
                    "cleaner_row_role": "excipient",
                },
            ]
        },
    })
    assert taxonomy["quantified_active_count"] == 1
    assert taxonomy["primary_type"] != "single_mineral"


def test_enzyme_activity_in_notes_counts_as_dose_and_blocks_carrier_taxonomy():
    product = {
        "fullName": "Doctor's Best Serrapeptase 120,000 SPU",
        "ingredient_quality_data": {
            "ingredients_scorable": [
                {
                    "name": "Calcium",
                    "canonical_id": "calcium",
                    "category": "minerals",
                    "quantity": 35,
                    "unit": "mg",
                    "score_eligible_by_cleaner": True,
                    "cleaner_row_role": "active_scorable",
                },
                {
                    "name": "Serrapeptase Enzyme",
                    "canonical_id": "digestive_enzymes",
                    "category": "enzymes",
                    "quantity": 0,
                    "unit": "NP",
                    "notes": "enzyme (120,000 SPU - serratiopeptidase activity units)",
                    "score_eligible_by_cleaner": True,
                    "cleaner_row_role": "active_scorable",
                },
            ]
        },
    }

    taxonomy = classify_supplement(product)
    assert taxonomy["quantified_active_count"] == 2
    assert taxonomy["primary_type"] != "single_mineral"


def test_iqd_emits_enzyme_activity_dose_from_raw_notes():
    product = {
        "fullName": "Doctor's Best Serrapeptase 40,000 SPU",
        "activeIngredients": [
            {
                "name": "Serrapeptase Enzyme",
                "standardName": "Digestive Enzymes",
                "quantity": 0,
                "unit": "NP",
                "notes": "enzyme, 40,000 SPU serratiopeptidase activity units",
                "source_section": "active",
                "raw_source_path": "ingredientRows[1]",
                "cleaner_row_role": "active_scorable",
                "score_eligible_by_cleaner": True,
                "dose_class": "zero_or_np",
            }
        ],
    }

    iqd = SupplementEnricherV3()._collect_ingredient_quality_data(product)
    enzyme = _first_named(iqd["ingredients_scorable"], "Serrapeptase Enzyme")
    assert enzyme["has_dose"] is True
    assert enzyme["dose_class"] == "enzyme_activity"
    assert enzyme["activity_quantity"] == 40000
    assert enzyme["activity_unit"] == "SPU"
