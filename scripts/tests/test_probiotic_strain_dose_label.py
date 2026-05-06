#!/usr/bin/env python3
"""Probiotic blend-member dose label override (UX fix #4 from dev audit).

When a probiotic strain appears as a proprietary-blend member without
an individual dose, the generic "Amount not disclosed" copy implies
the manufacturer hid information. For probiotics that's typically not
the case — per-strain CFU is rarely listed even on transparent labels,
and the product-level total appears on ProbioticDetailSection.

Pipeline now overrides the wording to "Per-strain dose not listed"
when the active row is a probiotic blend member of a probiotic product.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from build_final_db import _compute_display_dose_label, build_detail_blob


# -- Direct function tests ---------------------------------------------------

def test_blend_member_default_wording():
    """Non-probiotic blend member keeps the generic copy."""
    label = _compute_display_dose_label(
        {"quantity": 0, "unit": "NP", "is_in_proprietary_blend": True},
    )
    assert label == "Amount not disclosed"


def test_blend_member_probiotic_wording():
    """Probiotic blend member gets the per-strain copy."""
    label = _compute_display_dose_label(
        {"quantity": 0, "unit": "NP", "is_in_proprietary_blend": True},
        is_probiotic_strain=True,
    )
    assert label == "Per-strain dose not listed"


def test_disclosed_dose_unaffected_by_probiotic_flag():
    """When a strain HAS an individual dose, render it verbatim — the
    probiotic flag must not override Class 1."""
    label = _compute_display_dose_label(
        {"quantity": 5_000_000_000, "unit": "CFU", "is_in_proprietary_blend": True},
        is_probiotic_strain=True,
    )
    assert label == "5 billion CFU"


def test_truly_missing_dose_not_overridden():
    """No quantity, not a blend member → em-dash regardless of flag."""
    assert _compute_display_dose_label({}, is_probiotic_strain=True) == "—"


# -- Integration through build_detail_blob ----------------------------------

def _enriched_with_probiotic_blend():
    return {
        "dsld_id": "TEST_PROBIOTIC",
        "product_name": "Test Probiotic 25 Billion",
        "brandName": "Test Brand",
        "upcSku": "0",
        "imageUrl": "",
        "status": "active",
        "form_factor": "capsule",
        "supplement_type": {"type": "probiotic"},
        "enrichment_version": "3.1.0",
        "is_certified_organic": False,
        "is_trusted_manufacturer": False,
        "manufacturing_region": "USA",
        "named_cert_programs": [],
        "has_full_disclosure": False,
        "compliance_data": {},
        "probiotic_data": {
            "is_probiotic_product": True,
            "has_cfu": True,
            "total_cfu": 25_000_000_000,
            "total_billion_count": 25.0,
            "total_strain_count": 2,
            "probiotic_blends": [
                {
                    "name": "Lactobacillus acidophilus",
                    "strains": ["Lactobacillus acidophilus"],
                    "strain_count": 1,
                },
                {
                    "name": "Bifidobacterium lactis",
                    "strains": ["Bifidobacterium lactis"],
                    "strain_count": 1,
                },
            ],
            "clinical_strains": [],
        },
        "contaminant_data": {"banned_substances": {"substances": []}},
        "harmful_additives": [],
        "allergen_hits": [],
        "interaction_profile": {"ingredient_alerts": []},
        "dietary_sensitivity_data": {"warnings": []},
        "activeIngredients": [
            {
                "name": "Lactobacillus acidophilus",
                "standardName": "Lactobacillus acidophilus",
                "normalized_key": "lactobacillus_acidophilus",
                "raw_source_text": "Lactobacillus acidophilus",
                "forms": [],
                "quantity": 0,
                "unit": "NP",
                "is_in_proprietary_blend": True,
            },
            # Sanity row: a non-probiotic blend member should keep the
            # generic wording even in a probiotic product.
            {
                "name": "Vitamin C",
                "standardName": "Vitamin C",
                "normalized_key": "vitamin_c",
                "raw_source_text": "Vitamin C",
                "forms": [],
                "quantity": 0,
                "unit": "NP",
                "is_in_proprietary_blend": True,
            },
        ],
        "ingredient_quality_data": {"ingredients": []},
        "dosage_normalization": {"normalized_ingredients": []},
        "inactiveIngredients": [],
        "certification_data": {},
        "proprietary_data": {"has_proprietary_blends": True, "blends": []},
        "serving_basis": {
            "basis_count": 1, "basis_unit": "capsule",
            "min_servings_per_day": 1, "max_servings_per_day": 1,
        },
        "manufacturer_data": {"violations": {}},
        "evidence_data": {"match_count": 0, "clinical_matches": [], "unsubstantiated_claims": []},
        "rda_ul_data": {
            "collection_enabled": False,
            "ingredients_with_rda": 0,
            "analyzed_ingredients": [], "count": 0,
            "adequacy_results": [], "conversion_evidence": [],
            "safety_flags": [], "has_over_ul": False,
        },
    }


def _scored_minimal():
    return {
        "score_80": 50.0, "display": "50/80", "display_100": "62/100",
        "score_100_equivalent": 62.0, "grade": "Fair", "verdict": "SAFE",
        "safety_verdict": "SAFE", "mapped_coverage": 1.0,
        "badges": [], "flags": [], "section_scores": {}, "summary": {},
        "supp_type": "probiotic", "unmapped_actives": [],
    }


def _find(blob, raw):
    for ing in blob.get("ingredients", []):
        if ing.get("raw_source_text") == raw:
            return ing
    raise AssertionError(f"Ingredient {raw!r} not found")


def test_probiotic_strain_blob_uses_per_strain_copy():
    blob = build_detail_blob(_enriched_with_probiotic_blend(), _scored_minimal())
    strain = _find(blob, "Lactobacillus acidophilus")
    assert strain["display_dose_label"] == "Per-strain dose not listed"
    assert strain["dose_status"] == "not_disclosed_blend"


def test_non_probiotic_blend_member_keeps_generic_copy():
    """Vitamin C in the same probiotic product is a regular blend member,
    not a probiotic strain — gets the default 'Amount not disclosed'."""
    blob = build_detail_blob(_enriched_with_probiotic_blend(), _scored_minimal())
    vit_c = _find(blob, "Vitamin C")
    assert vit_c["display_dose_label"] == "Amount not disclosed"
