#!/usr/bin/env python3
"""T7A regression test — below_clinical_dose flag on analyzed_ingredients.

Sprint task T7A (docs/sprints/product_detail_page_sprint.md):
  Pipeline emits per-ingredient `below_clinical_dose: true` flag on the
  analyzed_ingredients / adequacy_results rows when the scorer's
  SUB_CLINICAL_DOSE_DETECTED guard fires for that canonical ingredient.

  Drives Flutter's "Low dose" chip on the ingredient row. Distinct from
  the product-level SUB_CLINICAL_DOSE_DETECTED flag (which fires on any
  occurrence) — the per-ingredient flag identifies WHICH ingredient is
  low so Flutter can target the right row.

Test plumbing: build_final_db consumes scored output. We exercise the
chain by feeding a synthetic scored dict that includes
breakdown.C.sub_clinical_canonicals and verifying analyzed_ingredients
+ adequacy_results in the resulting blob carry below_clinical_dose
correctly.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from build_final_db import build_detail_blob


def _enriched_with_rda_data():
    """Minimal enriched product with two RDA-tracked ingredients —
    one canonical_id matches the scorer's sub-clinical set, the other
    doesn't."""
    return {
        "dsld_id": "TEST_T7A",
        "product_name": "Test Product",
        "brandName": "Test Brand",
        "upcSku": "0",
        "imageUrl": "",
        "status": "active",
        "form_factor": "capsule",
        "supplement_type": {"type": "specialty"},
        "enrichment_version": "3.1.0",
        "is_certified_organic": False,
        "is_trusted_manufacturer": False,
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
        "activeIngredients": [],
        "ingredient_quality_data": {"ingredients": []},
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
            "collection_enabled": True,
            "ingredients_with_rda": 2,
            "analyzed_ingredients": [
                {"canonical_id": "vitamin_c", "ingredient_name": "Vitamin C"},
                {"canonical_id": "magnesium", "ingredient_name": "Magnesium"},
            ],
            "count": 2,
            "adequacy_results": [
                {"canonical_id": "vitamin_c", "ingredient_name": "Vitamin C",
                 "daily_amount": 50, "daily_amount_unit": "mg",
                 "adequacy_band": "below_rda"},
                {"canonical_id": "magnesium", "ingredient_name": "Magnesium",
                 "daily_amount": 400, "daily_amount_unit": "mg",
                 "adequacy_band": "adequate"},
            ],
            "conversion_evidence": [],
            "safety_flags": [],
            "has_over_ul": False,
        },
    }


def _scored_with_sub_clinical(canonicals):
    return {
        "score_80": 50.0, "display": "50/80", "display_100": "62/100",
        "score_100_equivalent": 62.0, "grade": "Fair", "verdict": "SAFE",
        "safety_verdict": "SAFE", "mapped_coverage": 1.0,
        "badges": [], "flags": ["SUB_CLINICAL_DOSE_DETECTED"] if canonicals else [],
        "section_scores": {},
        "summary": {},
        "supp_type": "specialty",
        "unmapped_actives": [],
        "breakdown": {
            "C": {
                "score": 5.0,
                "max": 20.0,
                "ingredient_points": {},
                "matched_entries": 1,
                "top_n_applied": 1,
                "depth_bonus": 0.0,
                "sub_clinical_canonicals": canonicals,
            },
        },
    }


def test_below_clinical_dose_marks_matching_canonical_only():
    """Vitamin C below clinical dose → flagged True on the V-C row.
    Magnesium not in the sub-clinical set → flagged False."""
    enriched = _enriched_with_rda_data()
    scored = _scored_with_sub_clinical(["vitamin_c"])
    blob = build_detail_blob(enriched, scored)

    rda = blob.get("rda_ul_data", {})
    by_canon = {row.get("canonical_id"): row for row in rda.get("adequacy_results", [])}
    assert by_canon["vitamin_c"]["below_clinical_dose"] is True
    assert by_canon["magnesium"]["below_clinical_dose"] is False

    analyzed = {row.get("canonical_id"): row for row in rda.get("analyzed_ingredients") or []}
    assert analyzed["vitamin_c"]["below_clinical_dose"] is True
    assert analyzed["magnesium"]["below_clinical_dose"] is False


def test_below_clinical_dose_false_when_no_sub_clinical_canonicals():
    """Empty sub-clinical set → every row gets False (explicit, not
    missing — Flutter can rely on the field being present)."""
    enriched = _enriched_with_rda_data()
    scored = _scored_with_sub_clinical([])
    blob = build_detail_blob(enriched, scored)

    for row in blob.get("rda_ul_data", {}).get("adequacy_results", []):
        assert row["below_clinical_dose"] is False


def test_below_clinical_dose_handles_multiple_canonicals():
    """Both ingredients triggered the guard → both marked True."""
    enriched = _enriched_with_rda_data()
    scored = _scored_with_sub_clinical(["vitamin_c", "magnesium"])
    blob = build_detail_blob(enriched, scored)

    for row in blob.get("rda_ul_data", {}).get("adequacy_results", []):
        assert row["below_clinical_dose"] is True
