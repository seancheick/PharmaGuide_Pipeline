#!/usr/bin/env python3
"""Canonical inactive-ingredient contract regression tests.

Same architectural pattern as the active-ingredient contract: pipeline
emits explicit display + routing fields on every inactive so Flutter
renders them directly without local inference.

  display_label        user-visible name (canonical, prettified)
  display_role_label   user-visible role ('Anti-caking agent', etc.)
                       or None when no excipient role is known
  severity_status      'critical' | 'suppress' | 'informational' | 'n/a'

The triggering use case: Thorne Basic Prenatal (DSLD 328830) carries
Silicon Dioxide (low-severity excipient) and Hypromellose (vegetarian
capsule shell). Flutter was showing silicon dioxide in Review-Before-Use
because severity routing was implicit; the canonical contract bakes the
decision into severity_status='suppress' so the RBU filter is trivial.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from build_final_db import (
    _compute_inactive_role_label,
    _compute_inactive_severity_status,
    _compute_is_safety_concern,
    build_detail_blob,
)


# -- _compute_inactive_role_label -------------------------------------------

@pytest.mark.parametrize("ingredient, expected", [
    ({"additive_type": "anti_caking_agent"}, "Anti-caking agent"),
    ({"additive_type": "capsule_coating"}, "Capsule coating"),
    ({"category": "capsule_shell"}, "Capsule shell"),
    ({"additive_type": "lubricant"}, "Lubricant"),
    ({"additive_type": "filler"}, "Filler"),
    ({"additive_type": "colorant"}, "Colorant"),
    ({"additive_type": "preservative"}, "Preservative"),
    ({"additive_type": "lecithin"}, "Lecithin (emulsifier)"),
    # additive_type takes precedence over category when both present.
    ({"additive_type": "anti_caking_agent", "category": "capsule_shell"}, "Anti-caking agent"),
])
def test_role_label_curated_mapping(ingredient, expected):
    assert _compute_inactive_role_label(ingredient, {}) == expected


def test_role_label_falls_back_to_other_ref():
    """When the ingredient itself has no role hints, use the
    other_ingredients reference data."""
    assert _compute_inactive_role_label({}, {"additive_type": "lubricant"}) == "Lubricant"


def test_role_label_uncurated_value_falls_back_to_titlecase():
    """Vocabulary entries we haven't curated yet still produce a clean
    label rather than leaking snake_case to Flutter."""
    assert _compute_inactive_role_label({"additive_type": "novel_excipient_x"}, {}) == "Novel excipient x"


def test_role_label_returns_none_when_no_role_known():
    """Bare amino acid like 'Leucine' has no excipient role — Flutter
    should suppress the role chip entirely rather than guess one."""
    assert _compute_inactive_role_label({}, {}) is None


# -- _compute_inactive_severity_status --------------------------------------

@pytest.mark.parametrize("is_additive, is_harmful, severity, expected", [
    # Hazardous excipients always show.
    (True, True, "high", "critical"),
    (True, True, "moderate", "critical"),
    (True, True, "critical", "critical"),
    # Low-severity excipients suppress (Tradeoffs only, hidden from RBU).
    (True, True, "low", "suppress"),
    (False, True, "low", "suppress"),
    # Flagged but no severity — informational.
    (True, True, "", "informational"),
    (True, True, None, "informational"),
    # Non-harmful inactives — n/a (just render in Other Ingredients).
    (True, False, None, "n/a"),
    (False, False, None, "n/a"),
])
def test_severity_status_routing(is_additive, is_harmful, severity, expected):
    assert _compute_inactive_severity_status(is_additive, is_harmful, severity) == expected


# -- _compute_is_safety_concern ---------------------------------------------
# is_harmful records DB provenance (in harmful_additives.json); the
# semantic safety flag must NOT light up for low-severity excipients
# tracked for transparency. This test pins that semantic.

@pytest.mark.parametrize("is_harmful, severity, expected", [
    (True, "high", True),
    (True, "moderate", True),
    (True, "critical", True),
    # Silicon dioxide / MCC / calcium laurate — listed in harmful DB
    # but severity=low because they're tracked excipients, not risks.
    (True, "low", False),
    (True, "", False),
    (True, None, False),
    (False, None, False),
])
def test_is_safety_concern_only_true_for_real_hazards(is_harmful, severity, expected):
    assert _compute_is_safety_concern(is_harmful, severity) is expected


# -- Integration: blob carries the new contract fields ----------------------

def _enriched_with_thorne_inactives():
    """Reproduce two real inactives from Thorne Basic Prenatal:
      - Silicon Dioxide (low-severity excipient -> suppress)
      - Hypromellose (vegetarian capsule shell -> n/a)
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
        # Inactives mirror the harmful_additives entry by name so the
        # severity look-up wires up.
        "harmful_additives": [
            {
                "ingredient": "Silicon Dioxide",
                "raw_source_text": "Silicon Dioxide",
                "additive_name": "Silicon Dioxide (E551)",
                "severity_level": "low",
                "category": "flow_agent_anticaking",
            }
        ],
        "allergen_hits": [],
        "interaction_profile": {"ingredient_alerts": []},
        "dietary_sensitivity_data": {"warnings": []},
        "activeIngredients": [],
        "ingredient_quality_data": {"ingredients": []},
        "dosage_normalization": {"normalized_ingredients": []},
        "inactiveIngredients": [
            {
                "name": "Silicon Dioxide",
                "raw_source_text": "Silicon Dioxide",
                "standardName": "Silicon Dioxide (E551)",
                "category": "flow_agent_anticaking",
                "additive_type": "anti_caking_agent",
                "isAdditive": True,
            },
            {
                "name": "Hypromellose",
                "raw_source_text": "Hypromellose",
                "standardName": "Hydroxypropyl Methylcellulose",
                "category": "capsule_shell",
                "additive_type": "capsule_coating",
                "isAdditive": True,
            },
        ],
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


def _scored_minimal():
    return {
        "score_80": 50.0, "display": "50/80", "display_100": "62/100",
        "score_100_equivalent": 62.0, "grade": "Fair", "verdict": "SAFE",
        "safety_verdict": "SAFE", "mapped_coverage": 1.0,
        "badges": [], "flags": [],
        "section_scores": {}, "score_breakdown": {},
        "summary": {}, "supp_type": "multivitamin", "unmapped_actives": [],
    }


def _find_inactive(blob, name):
    for ing in blob.get("inactive_ingredients", []):
        if ing.get("name") == name:
            return ing
    raise AssertionError(f"Inactive {name!r} not found")


def test_silicon_dioxide_suppresses_to_tradeoffs_only():
    """Silicon Dioxide must carry severity_status='suppress' so
    Flutter's Review-Before-Use filter can drop it without inference.
    Crucially, is_safety_concern is False even though it's listed in
    harmful_additives.json — it's tracked for transparency, not
    because it's a risk."""
    blob = build_detail_blob(_enriched_with_thorne_inactives(), _scored_minimal())
    sio2 = _find_inactive(blob, "Silicon Dioxide")
    assert sio2["display_label"] == "Silicon Dioxide (E551)"
    assert sio2["display_role_label"] == "Anti-caking agent"
    assert sio2["severity_status"] == "suppress"
    assert sio2["harmful_severity"] == "low"
    # Semantic safety flag — silicon dioxide is NOT a safety concern.
    assert sio2["is_safety_concern"] is False
    # Legacy `is_harmful` removed in v1.5.x deprecation cleanup.
    assert "is_harmful" not in sio2


def test_hypromellose_renders_as_neutral_excipient():
    """Vegetarian capsule shell — not a safety concern, should render
    in Other Ingredients only (severity_status='n/a')."""
    blob = build_detail_blob(_enriched_with_thorne_inactives(), _scored_minimal())
    hpmc = _find_inactive(blob, "Hypromellose")
    assert hpmc["display_label"] == "Hydroxypropyl Methylcellulose"
    assert hpmc["display_role_label"] == "Capsule coating"
    assert hpmc["severity_status"] == "n/a"
    assert hpmc["is_safety_concern"] is False
    assert "is_harmful" not in hpmc
