#!/usr/bin/env python3
"""Batch diabetes-01 — min_effective_dose floor emission + fail-open.

Covers the Phase-2/3 pipeline half of the smart-flagging rework:
  * enricher `_evaluate_min_effective_dose` returns below / at_or_above and
    FAILS OPEN (None) on missing/unconvertible dose or absent floor — the
    load-bearing safety contract (never suppress on missing evidence).
  * build_final_db carries `direction` / `materiality` / `min_effective_dose`
    / `dose_floor_status` from the interaction hit onto the emitted blob
    warning so the app can gate on it.

Hermetic: no network, no live pipeline run.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from enrich_supplements_v3 import SupplementEnricherV3 as SupplementEnricher
from build_final_db import build_detail_blob

FLOOR = {"value": 1500, "unit": "mg", "basis": "per_day"}
RULES = json.loads(
    (Path(__file__).parent.parent / "data" / "ingredient_interaction_rules.json").read_text()
)["interaction_rules"]


# --------------------------------------------------------------------------
# _evaluate_min_effective_dose — the fail-open floor comparison
# --------------------------------------------------------------------------

def test_floor_below_at_and_above():
    e = SupplementEnricher()
    assert e._evaluate_min_effective_dose(
        FLOOR, {"quantity": 20, "unit": "mg", "raw_source_text": "Niacin"}, 1.0
    ) == "below"
    assert e._evaluate_min_effective_dose(
        FLOOR, {"quantity": 2000, "unit": "mg", "raw_source_text": "Niacin"}, 1.0
    ) == "at_or_above"
    # per_day basis multiplies by servings: 800 mg x 2/day = 1600 mg >= 1500
    assert e._evaluate_min_effective_dose(
        FLOOR, {"quantity": 800, "unit": "mg", "raw_source_text": "Niacin"}, 2.0
    ) == "at_or_above"


def test_floor_fails_open_on_missing_or_absent():
    e = SupplementEnricher()
    # missing/zero dose -> None (fires), never suppress on missing evidence
    assert e._evaluate_min_effective_dose(FLOOR, {"unit": "mg"}, 1.0) is None
    assert e._evaluate_min_effective_dose(FLOOR, {"quantity": 0, "unit": "mg"}, 1.0) is None
    assert e._evaluate_min_effective_dose(FLOOR, {"quantity": 20, "unit": None}, 1.0) is None
    # absent / malformed floor -> None
    assert e._evaluate_min_effective_dose(None, {"quantity": 20, "unit": "mg"}, 1.0) is None
    assert e._evaluate_min_effective_dose({}, {"quantity": 20, "unit": "mg"}, 1.0) is None
    assert e._evaluate_min_effective_dose(
        {"unit": "mg"}, {"quantity": 20, "unit": "mg"}, 1.0
    ) is None


def _condition_floor(canonical_id, condition_id):
    for rule in RULES:
        if (rule.get("subject_ref") or {}).get("canonical_id") != canonical_id:
            continue
        for condition_rule in rule.get("condition_rules") or []:
            if condition_rule.get("condition_id") == condition_id:
                return condition_rule.get("min_effective_dose")
    return None


def test_thyroid_mineral_floors_restore_retired_app_boundaries():
    """Selenium/iodine thyroid gates moved out of Flutter and into the emitted
    pipeline floor contract. Below-floor warnings suppress; missing dose still
    fails open in the generic floor tests above.
    """
    e = SupplementEnricher()
    iodine_floor = _condition_floor("iodine", "thyroid_disorder")
    selenium_floor = _condition_floor("selenium", "thyroid_disorder")

    assert e._evaluate_min_effective_dose(
        iodine_floor, {"quantity": 149, "unit": "mcg", "raw_source_text": "Iodine"}, 1.0
    ) == "below"
    assert e._evaluate_min_effective_dose(
        iodine_floor, {"quantity": 150, "unit": "mcg", "raw_source_text": "Iodine"}, 1.0
    ) == "at_or_above"
    assert e._evaluate_min_effective_dose(
        selenium_floor, {"quantity": 399, "unit": "mcg", "raw_source_text": "Selenium"}, 1.0
    ) == "below"
    assert e._evaluate_min_effective_dose(
        selenium_floor, {"quantity": 400, "unit": "mcg", "raw_source_text": "Selenium"}, 1.0
    ) == "at_or_above"


FLOOR_NICOTINIC = {
    "value": 1500, "unit": "mg", "basis": "per_day",
    "form_scope": ["nicotinic acid"],
}


def _ing(qty, form="nicotinic acid", unit="mg", form_id=None):
    # Real pipeline rows carry a form_id. A LABEL-CONFIRMED form has a
    # non-"unspecified" id; an inferred/fallback form (generic "Vitamin B3")
    # gets a '<parent>_unspecified' id. Default derives a confirmed id from the
    # form name so the confirmed-form cases exercise the mismatch path; pass an
    # explicit form_id to model an inferred form.
    resolved_form_id = form_id if form_id is not None else form.replace(" ", "_")
    return {
        "quantity": qty,
        "unit": unit,
        "raw_source_text": "Niacin",
        "matched_form": form,
        "form_id": resolved_form_id,
    }


def test_form_scope_only_matching_form_gets_floor():
    """G1: the nicotinic-acid floor must NOT fire on confirmed other forms.

    A confirmed nonmatching form (niacinamide) is a form mismatch, not an
    unknown. Unknown and missing form still fail open (the warning fires).
    """
    e = SupplementEnricher()
    assert e._evaluate_min_effective_dose(FLOOR_NICOTINIC, _ing(20, "nicotinic acid"), 1.0) == "below"
    assert e._evaluate_min_effective_dose(FLOOR_NICOTINIC, _ing(2000, "nicotinic acid"), 1.0) == "at_or_above"
    assert e._evaluate_min_effective_dose(FLOOR_NICOTINIC, _ing(20, "niacinamide"), 1.0) == "form_mismatch"
    assert e._evaluate_min_effective_dose(FLOOR_NICOTINIC, _ing(20, ""), 1.0) is None
    assert e._evaluate_min_effective_dose(FLOOR_NICOTINIC, {"quantity": 20, "unit": "mg"}, 1.0) is None


def test_form_scope_inferred_form_fails_open():
    """G1/F2: an INFERRED (unconfirmed) form must NOT suppress the floor.

    A generic "Vitamin B3" label with no "(as ...)" resolves to a fallback
    matched_form and a '<parent>_unspecified' form_id. Because generic B3 could
    BE nicotinic acid, gating on the inferred form (form_mismatch → suppress)
    would hide a genuine flush/hepatotoxicity warning. The floor must fail open
    until the form is label-confirmed. Mirrors the matcher's own confirmation
    test (`form_id and 'unspecified' not in form_id`).
    """
    e = SupplementEnricher()
    # matched_form populated but form_id is the unspecified fallback → not confirmed
    assert e._evaluate_min_effective_dose(
        FLOOR_NICOTINIC, _ing(20, "niacin", form_id="niacin_unspecified"), 1.0
    ) is None
    # matched_form populated but form_id missing entirely → not confirmed
    assert e._evaluate_min_effective_dose(
        FLOOR_NICOTINIC, _ing(20, "niacin", form_id=""), 1.0
    ) is None


def test_unknown_basis_fails_open():
    # A `basis` typo (e.g. "daily" instead of "per_day") must NOT silently drop
    # the per-day multiplier and under-count the dose -> fail open (adversarial
    # audit D2). Even a large dose returns None (fires) under a bad basis.
    e = SupplementEnricher()
    typo = {"value": 1500, "unit": "mg", "basis": "daily", "form_scope": ["nicotinic acid"]}
    assert e._evaluate_min_effective_dose(typo, _ing(20), 1.0) is None
    assert e._evaluate_min_effective_dose(typo, _ing(9999), 1.0) is None


# --------------------------------------------------------------------------
# build_final_db emission of the new axes onto the blob warning
# --------------------------------------------------------------------------

def _enriched_with_niacin_alert(dose_floor_status):
    return {
        "dsld_id": "TEST_DIAB01",
        "product_name": "Test Multivitamin",
        "brandName": "Test Brand",
        "upcSku": "0", "imageUrl": "", "status": "active",
        "form_factor": "capsule",
        "supplement_type": {"type": "specialty"},
        "enrichment_version": "3.1.0",
        "is_certified_organic": False, "is_trusted_manufacturer": False,
        "manufacturing_region": "USA", "named_cert_programs": [],
        "has_full_disclosure": True, "compliance_data": {},
        "probiotic_data": {"is_probiotic_product": False},
        "contaminant_data": {"banned_substances": {"substances": []}},
        "harmful_additives": [], "allergen_hits": [],
        "interaction_profile": {
            "ingredient_alerts": [
                {
                    "ingredient_name": "Niacin",
                    "standard_name": "Niacin",
                    "condition_hits": [
                        {
                            "condition_id": "diabetes",
                            "severity": "caution",
                            "evidence_level": "established",
                            "mechanism": "Pharmacologic-dose niacin raises glucose.",
                            "action": "Monitor glucose.",
                            "sources": [
                                "https://ods.od.nih.gov/factsheets/Niacin-HealthProfessional/"
                            ],
                            "alert_headline": "High-dose niacin may raise blood sugar",
                            "alert_body": "High-dose niacin can raise blood sugar.",
                            "informational_note": "Niacin affects blood sugar.",
                            "warning_type": "interaction",
                            "direction": "harmful",
                            "materiality": "dose_dependent",
                            "min_effective_dose": FLOOR,
                            "dose_floor_status": dose_floor_status,
                            "profile_gate": {"gate_type": "condition"},
                        }
                    ],
                    "drug_class_hits": [],
                }
            ]
        },
        "dietary_sensitivity_data": {"warnings": []},
        "activeIngredients": [],
        "ingredient_quality_data": {"ingredients": []},
        "dosage_normalization": {"normalized_ingredients": []},
        "inactiveIngredients": [], "certification_data": {},
        "proprietary_data": {"has_proprietary_blends": False, "blends": []},
        "serving_basis": {
            "basis_count": 1, "basis_unit": "capsule",
            "min_servings_per_day": 1, "max_servings_per_day": 1,
        },
        "manufacturer_data": {"violations": {}},
        "evidence_data": {"match_count": 0, "clinical_matches": [], "unsubstantiated_claims": []},
        "rda_ul_data": {"collection_enabled": True, "analyzed_ingredients": [], "adequacy_results": []},
    }


def _scored():
    return {
        "score_80": 50.0, "display": "50/80", "display_100": "62/100",
        "score_100_equivalent": 62.0, "grade": "Fair", "verdict": "SAFE",
        "safety_verdict": "SAFE", "mapped_coverage": 1.0,
        "badges": [], "flags": [], "section_scores": {}, "summary": {},
        "supp_type": "specialty", "unmapped_actives": [], "breakdown": {},
    }


def _niacin_warning(blob):
    # condition_id is nulled in the full warnings[] list (the app matches via
    # profile_gate); the title retains the condition, so match on that.
    for w in blob.get("warnings", []):
        if w.get("ingredient_name") == "Niacin" and "diabetes" in str(w.get("title", "")).lower():
            return w
    return None


def test_blob_carries_direction_materiality_and_floor():
    blob = build_detail_blob(_enriched_with_niacin_alert("below"), _scored())
    w = _niacin_warning(blob)
    assert w is not None, "niacin/diabetes warning must be emitted"
    assert w["direction"] == "harmful"
    assert w["materiality"] == "dose_dependent"
    assert w["dose_floor_status"] == "below"
    assert (w.get("min_effective_dose") or {}).get("value") == 1500


def test_blob_floor_status_above_passes_through():
    blob = build_detail_blob(_enriched_with_niacin_alert("at_or_above"), _scored())
    w = _niacin_warning(blob)
    assert w is not None
    assert w["dose_floor_status"] == "at_or_above"


def test_blob_floor_status_none_when_unknown():
    """Fail-open: unknown dose -> dose_floor_status None -> app fires."""
    blob = build_detail_blob(_enriched_with_niacin_alert(None), _scored())
    w = _niacin_warning(blob)
    assert w is not None
    assert w["dose_floor_status"] is None


# --------------------------------------------------------------------------
# Diabetes-gated added-sugar flag (presence-matters, harmful, score-neutral)
# --------------------------------------------------------------------------

def _enriched_with_sugar(has_added_sugar=False, level="low"):
    e = _enriched_with_niacin_alert(None)
    e["interaction_profile"] = {"ingredient_alerts": []}
    e["dietary_sensitivity_data"] = {
        "warnings": [],
        "sugar": {"has_added_sugar": has_added_sugar, "amount_g": 6, "level": level},
    }
    return e


def _sugar_warning(blob):
    return next(
        (w for w in blob.get("warnings", [])
         if w.get("type") == "dietary" and w.get("direction") == "harmful"
         and "diabetes" in (w.get("condition_ids") or [])),
        None,
    )


def test_added_sugar_emits_diabetes_presence_flag():
    blob = build_detail_blob(_enriched_with_sugar(has_added_sugar=True), _scored())
    w = _sugar_warning(blob)
    assert w is not None
    assert w["title"] == "Added sugar"  # has_added_sugar=True -> correctly "Added"
    assert w["condition_ids"] == ["diabetes"]
    assert w["direction"] == "harmful"
    assert w["materiality"] == "presence"
    # presence-matters carries no floor -> never dose-suppressed
    assert w.get("dose_floor_status") is None
    # suppressed by default -> hidden until a diabetes profile match promotes it
    assert _sugar_warning({"warnings": blob.get("warnings_profile_gated", [])}) is None


def test_no_added_sugar_no_flag():
    blob = build_detail_blob(_enriched_with_sugar(has_added_sugar=False, level="low"), _scored())
    assert _sugar_warning(blob) is None


def test_total_sugar_labeled_sugar_not_added():
    # has_added_sugar False but total sugar level moderate -> still fires (total
    # sugar matters for a diabetic) BUT must be titled "Sugar", not "Added sugar"
    # (D5 mislabel fix from the adversarial audit).
    blob = build_detail_blob(
        _enriched_with_sugar(has_added_sugar=False, level="moderate"), _scored()
    )
    w = _sugar_warning(blob)
    assert w is not None
    assert w["title"] == "Sugar"
    assert "added" not in (w.get("detail") or "").lower()
