#!/usr/bin/env python3
"""Canonical active-ingredient contract regression tests.

The pipeline emits four explicit fields on every active ingredient so
Flutter never has to infer whether a form or dose is disclosed:

  display_form_label   user-visible form, or None when unknown
  form_status          'known' | 'unknown'
  form_match_status    'mapped' | 'unmapped' | 'n/a'
  dose_status          'disclosed' | 'not_disclosed_blend' | 'missing'

The triggering bug: Thorne Basic Prenatal (DSLD 328830) emitted
forms: [] for Vitamin A Palmitate even though matched_form was
'retinyl palmitate'. Flutter showed no form helper line because it
read ingredient['form'] (empty) instead of the enricher's match.
The bridge in build_final_db falls back to matched_form when the
cleaner missed the inline form, so display_form_label is populated.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from build_final_db import (
    _compute_dose_status,
    _compute_form_contract,
    _is_placeholder_form,
    _prettify_matched_form,
    build_detail_blob,
)


# -- _is_placeholder_form -----------------------------------------------------

def test_placeholder_form_recognizes_empty_and_sentinels():
    assert _is_placeholder_form("")
    assert _is_placeholder_form("standard")
    assert _is_placeholder_form("Standard")
    assert _is_placeholder_form("unspecified")
    assert _is_placeholder_form("vitamin a (unspecified)")
    assert _is_placeholder_form("retinol (unmapped)")


def test_placeholder_form_lets_real_forms_through():
    assert not _is_placeholder_form("retinyl palmitate")
    assert not _is_placeholder_form("methylcobalamin")
    assert not _is_placeholder_form("magnesium glycinate")


# -- _prettify_matched_form ---------------------------------------------------

def test_prettify_strips_parent_prefix():
    assert _prettify_matched_form("vitamin a palmitate") == "Palmitate"
    assert _prettify_matched_form("vitamin b12 methylcobalamin") == "Methylcobalamin"


def test_prettify_preserves_alphanumeric_tokens():
    # Tokens carrying digits stay upper so they remain recognizable.
    assert _prettify_matched_form("vitamin d d3") == "D3"
    assert _prettify_matched_form("mk-7") == "MK-7"
    assert _prettify_matched_form("menaquinone-7") == "Menaquinone-7"


def test_prettify_capitalizes_multi_word_forms():
    assert _prettify_matched_form("retinyl palmitate") == "Retinyl Palmitate"
    assert _prettify_matched_form("magnesium bisglycinate chelate") == (
        "Magnesium Bisglycinate Chelate"
    )


# -- _compute_form_contract ---------------------------------------------------

def test_form_contract_uses_cleaner_forms_when_present():
    ing = {"forms": [{"name": "Palmitate"}]}
    m = {"matched_form": "retinyl palmitate"}
    out = _compute_form_contract(ing, m)
    assert out == {
        "display_form_label": "Palmitate",
        "form_status": "known",
        "form_match_status": "mapped",
    }


def test_form_contract_bridges_to_matched_form_when_cleaner_empty():
    """The Thorne Basic Prenatal regression — cleaner missed inline
    form on 'Vitamin A Palmitate' so forms=[]; enricher caught it."""
    ing = {"forms": [], "name": "Vitamin A Palmitate"}
    m = {"matched_form": "retinyl palmitate"}
    out = _compute_form_contract(ing, m)
    assert out == {
        "display_form_label": "Retinyl Palmitate",
        "form_status": "known",
        "form_match_status": "mapped",
    }


def test_form_contract_unknown_when_label_has_no_form_and_match_is_placeholder():
    """The other Thorne Basic Prenatal row — 'Vitamin A' alone, no form
    on label, IQM fell back to the parent canonical."""
    ing = {"forms": [], "name": "Vitamin A"}
    m = {"matched_form": "vitamin a (unspecified)"}
    out = _compute_form_contract(ing, m)
    assert out == {
        "display_form_label": None,
        "form_status": "unknown",
        "form_match_status": "n/a",
    }


def test_form_contract_label_form_with_no_iqm_match_is_unmapped():
    ing = {"forms": [{"name": "Mixed Carotenoids"}]}
    m = {"matched_form": ""}
    out = _compute_form_contract(ing, m)
    assert out == {
        "display_form_label": "Mixed Carotenoids",
        "form_status": "known",
        "form_match_status": "unmapped",
    }


def test_form_contract_falls_back_to_ingredient_matched_form_field():
    # Older enricher paths put matched_form on the ingredient directly
    # rather than via the ingredient_quality_data lookup.
    ing = {"forms": [], "matched_form": "methylcobalamin"}
    m = {}
    out = _compute_form_contract(ing, m)
    assert out["form_status"] == "known"
    assert out["form_match_status"] == "mapped"
    assert out["display_form_label"] == "Methylcobalamin"


# -- _compute_dose_status -----------------------------------------------------

def test_dose_status_disclosed_when_quantity_and_unit_present():
    assert _compute_dose_status({"quantity": 1.05, "unit": "mg"}) == "disclosed"
    assert _compute_dose_status({"quantity": 600, "unit": "mcg"}) == "disclosed"


def test_dose_status_not_disclosed_blend_for_blend_member_without_dose():
    assert _compute_dose_status({
        "quantity": 0, "unit": "NP", "is_in_proprietary_blend": True,
    }) == "not_disclosed_blend"
    assert _compute_dose_status({
        "quantity": None, "unit": "", "isNestedIngredient": True,
    }) == "not_disclosed_blend"


def test_dose_status_missing_when_no_dose_and_not_blend():
    assert _compute_dose_status({"quantity": 0, "unit": "NP"}) == "missing"
    assert _compute_dose_status({}) == "missing"


# -- Integration: blob carries the new contract fields -----------------------

def _minimal_enriched_with_thorne_vitamin_a():
    """Reproduce the two rows from Thorne Basic Prenatal blob 328830:
      Row 1: 'Vitamin A' alone, forms=[], matched_form='vitamin a (unspecified)'
      Row 2: 'Vitamin A Palmitate', forms=[], matched_form='retinyl palmitate'
    """
    return {
        "dsld_id": "328830",
        "product_name": "Basic Prenatal",
        "brandName": "Thorne",
        "upcSku": "0",
        "imageUrl": "",
        "status": "active",
        "form_factor": "capsule",
        "supplement_type": {"type": "multivitamin"},
        "enrichment_version": "3.1.0",
        "is_certified_organic": False,
        "is_trusted_manufacturer": True,
        "manufacturing_region": "USA",
        "named_cert_programs": [],
        "has_full_disclosure": True,
        "compliance_data": {},
        "probiotic_data": {"is_probiotic_product": False},
        "contaminant_data": {"banned_substances": {"substances": []}},
        "harmful_additives": [],
        "allergen_hits": [],
        "interaction_profile": {"ingredient_alerts": []},
        "dietary_sensitivity_data": {"warnings": []},
        "activeIngredients": [
            {
                "name": "Vitamin A",
                "standardName": "Vitamin A",
                "normalized_key": "vitamin_a",
                "raw_source_text": "Vitamin A",
                "forms": [],
                "quantity": 1.05,
                "unit": "mg",
            },
            {
                "name": "Vitamin A Palmitate",
                "standardName": "Vitamin A",
                "normalized_key": "vitamin_a_palmitate",
                "raw_source_text": "Vitamin A Palmitate",
                "forms": [],
                "quantity": 600,
                "unit": "mcg",
            },
        ],
        "ingredient_quality_data": {
            "ingredients": [
                {
                    "raw_source_text": "Vitamin A",
                    "name": "Vitamin A",
                    "standard_name": "Vitamin A",
                    "parent_key": "vitamin_a",
                    "form": "vitamin a (unspecified)",
                    "category": "vitamins",
                    "bio_score": 5,
                    "natural": False,
                    "score": 5.0,
                    "mapped": True,
                    "matched_form": "vitamin a (unspecified)",
                    "matched_forms": [],
                    "extracted_forms": [],
                    "safety_hits": [],
                },
                {
                    "raw_source_text": "Vitamin A Palmitate",
                    "name": "Vitamin A Palmitate",
                    "standard_name": "Vitamin A",
                    "parent_key": "vitamin_a_palmitate",
                    "form": "retinyl palmitate",
                    "category": "vitamins",
                    "bio_score": 14,
                    "natural": False,
                    "score": 14.0,
                    "mapped": True,
                    "matched_form": "retinyl palmitate",
                    "matched_forms": [],
                    "extracted_forms": [],
                    "safety_hits": [],
                },
            ]
        },
        "dosage_normalization": {"normalized_ingredients": []},
        "inactiveIngredients": [],
        "certification_data": {},
        "proprietary_data": {"has_proprietary_blends": False, "blends": []},
        "serving_basis": {
            "basis_count": 1, "basis_unit": "capsule",
            "min_servings_per_day": 1, "max_servings_per_day": 1,
        },
        "manufacturer_data": {"violations": {}},
        "evidence_data": {"match_count": 0, "clinical_matches": [], "unsubstantiated_claims": []},
        "rda_ul_data": {
            "collection_enabled": True, "ingredients_with_rda": 0,
            "analyzed_ingredients": 0, "count": 0,
            "adequacy_results": [], "conversion_evidence": [],
            "safety_flags": [], "has_over_ul": False,
        },
    }


def _minimal_scored():
    return {
        "score_80": 50.0, "display": "50/80", "display_100": "62/100",
        "score_100_equivalent": 62.0, "grade": "Fair", "verdict": "SAFE",
        "safety_verdict": "SAFE", "mapped_coverage": 1.0,
        "badges": [], "flags": [],
        "section_scores": {},
        "score_breakdown": {},
        "summary": {},
        "supp_type": "multivitamin",
        "unmapped_actives": [],
    }


def _find_active(blob, raw):
    for ing in blob.get("ingredients", []):
        if ing.get("raw_source_text") == raw and ing.get("role") == "active":
            return ing
    raise AssertionError(f"Active ingredient {raw!r} not found in blob")


def test_thorne_vitamin_a_palmitate_bridges_form_when_cleaner_missed_it():
    """End-to-end: Vitamin A Palmitate with forms=[] gets a populated
    display_form_label sourced from matched_form. Without the bridge,
    Flutter sees an empty form helper line."""
    blob = build_detail_blob(
        _minimal_enriched_with_thorne_vitamin_a(), _minimal_scored()
    )
    palmitate = _find_active(blob, "Vitamin A Palmitate")
    assert palmitate["display_form_label"] == "Retinyl Palmitate"
    assert palmitate["form_status"] == "known"
    assert palmitate["form_match_status"] == "mapped"
    assert palmitate["dose_status"] == "disclosed"
    # Legacy `form` field deleted in v1.5.x deprecation cleanup.
    assert "form" not in palmitate


def test_thorne_vitamin_a_unspecified_emits_explicit_unknown():
    """The 'Vitamin A' row with no form on label and IQM fallback to the
    parent canonical must surface as form_status='unknown', not as a
    silently empty string."""
    blob = build_detail_blob(
        _minimal_enriched_with_thorne_vitamin_a(), _minimal_scored()
    )
    vit_a = _find_active(blob, "Vitamin A")
    assert vit_a["display_form_label"] is None
    assert vit_a["form_status"] == "unknown"
    assert vit_a["form_match_status"] == "n/a"
    assert vit_a["dose_status"] == "disclosed"
