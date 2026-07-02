#!/usr/bin/env python3
"""Role-aware stack coverage export contract."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from build_final_db import build_detail_blob
from test_build_final_db import make_enriched, make_scored


def _ingredient(
    name,
    canonical_id,
    quantity,
    unit,
    *,
    standard_name=None,
    category="vitamins",
    normalized_amount=None,
    normalized_unit=None,
):
    standard_name = standard_name or name
    return {
        "active": {
            "name": name,
            "standardName": standard_name,
            "normalized_key": canonical_id,
            "raw_source_text": name,
            "forms": [],
            "quantity": quantity,
            "unit": unit,
            "canonical_id": canonical_id,
        },
        "iqm": {
            "raw_source_text": name,
            "name": name,
            "standard_name": standard_name,
            "canonical_id": canonical_id,
            "parent_key": canonical_id,
            "category": category,
            "bio_score": 12,
            "natural": False,
            "score": 12.0,
            "mapped": True,
            "notes": "",
            "matched_form": "",
            "matched_forms": [],
            "extracted_forms": [],
            "safety_hits": [],
        },
        "normalized": {
            "original_name": name,
            "normalized_amount": normalized_amount if normalized_amount is not None else quantity,
            "normalized_unit": normalized_unit or unit,
        },
    }


def _product(name, ingredients, *, target_groups=None, primary_type="multivitamin"):
    enriched = make_enriched()
    enriched["product_name"] = name
    enriched["targetGroups"] = target_groups or []
    enriched["supplement_taxonomy"] = {
        "primary_type": primary_type,
        "secondary_type": None,
        "classification_confidence": 0.9,
        "classification_reasons": [],
    }
    enriched["activeIngredients"] = [row["active"] for row in ingredients]
    enriched["ingredient_quality_data"]["ingredients"] = [row["iqm"] for row in ingredients]
    enriched["dosage_normalization"] = {
        "normalized_ingredients": [row["normalized"] for row in ingredients]
    }
    enriched["rda_ul_data"] = {
        "collection_enabled": True,
        "ingredients_with_rda": len(ingredients),
        "analyzed_ingredients": len(ingredients),
        "count": len(ingredients),
        "adequacy_results": [],
        "conversion_evidence": [],
        "safety_flags": [],
        "has_over_ul": False,
    }
    return enriched


def _core_prenatal_ingredients():
    return [
        _ingredient("Folate", "folate", 600, "mcg DFE"),
        _ingredient("Iron", "iron", 27, "mg", category="minerals"),
        _ingredient("Iodine", "iodine", 220, "mcg", category="minerals"),
        _ingredient("Vitamin D3", "vitamin_d", 15, "mcg", standard_name="Vitamin D"),
        _ingredient("Vitamin B12", "vitamin_b12_cobalamin", 2.6, "mcg"),
        _ingredient("Vitamin A", "vitamin_a", 770, "mcg RAE"),
    ]


def test_prenatal_core_without_dha_or_choline_exports_prenatal_base():
    enriched = _product("Essential Prenatal Multi", _core_prenatal_ingredients())

    blob = build_detail_blob(enriched, make_scored())

    assert blob["product_role"] == "prenatal_base"
    assert blob["completeness_claim_mismatch"] is False
    assert blob["prenatal_coverage"]["summary"]["missing"] == ["choline", "dha"]
    assert blob["prenatal_coverage"]["scoring_impact"] == "none"


def test_complete_prenatal_requires_core_plus_dha_and_choline():
    ingredients = _core_prenatal_ingredients() + [
        _ingredient("Choline", "choline", 450, "mg"),
        _ingredient("DHA", "dha", 200, "mg", category="fatty_acids"),
    ]
    enriched = _product("Complete Prenatal Multi", ingredients)

    blob = build_detail_blob(enriched, make_scored())

    assert blob["product_role"] == "prenatal_complete"
    assert blob["completeness_claim_mismatch"] is False
    assert "dha" in blob["prenatal_coverage"]["summary"]["covered"]
    assert "choline" in blob["prenatal_coverage"]["summary"]["covered"]


def test_complete_claim_without_dha_or_choline_exports_mismatch():
    enriched = _product("Complete Prenatal", _core_prenatal_ingredients())

    blob = build_detail_blob(enriched, make_scored())

    assert blob["product_role"] == "prenatal_base"
    assert blob["completeness_claim_mismatch"] is True


def test_prenatal_dha_companion_does_not_need_full_multi_panel():
    enriched = _product(
        "Prenatal DHA",
        [_ingredient("DHA", "dha", 250, "mg", category="fatty_acids")],
        primary_type="omega_3",
    )

    blob = build_detail_blob(enriched, make_scored())

    assert blob["product_role"] == "prenatal_dha_companion"
    assert blob["prenatal_coverage"]["summary"]["covered"] == ["dha"]


def test_dha_anchor_does_not_match_ashwagandha_substring():
    enriched = _product(
        "Prenatal Support",
        [_ingredient("Ashwagandha", "ashwagandha", 300, "mg", category="botanicals")],
        primary_type="herbal_botanical",
    )

    blob = build_detail_blob(enriched, make_scored())

    assert blob["product_role"] == "prenatal_support"
    assert "dha" not in blob["product_role_evidence"]["present_prenatal_anchors"]
    assert "prenatal_coverage" not in blob


def test_pregnancy_negation_target_group_is_not_prenatal_positioning():
    enriched = _product(
        "Digestive Balance",
        [_ingredient("Ginger", "ginger", 100, "mg", category="botanicals")],
        target_groups=["Women (not pregnant or lactating)"],
        primary_type="herbal_botanical",
    )

    blob = build_detail_blob(enriched, make_scored())

    assert blob["product_role"] == "targeted_gap_filler"
    assert blob["product_role_evidence"]["prenatal_positioned"] is False
