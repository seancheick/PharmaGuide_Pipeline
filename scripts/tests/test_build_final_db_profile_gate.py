#!/usr/bin/env python3
"""Phase 2 / Step 8 — verify build_final_db emits profile_gate in detail blob.

The catalog DB version bumped 1.5.0 → 1.6.0 to carry profile_gate on every
interaction/drug_interaction warning in detail_blobs. Flutter reads this
blob to render alerts, so missing the gate here = ungated alerts in the
app even though the source rule has the gate.
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from build_final_db import EXPORT_SCHEMA_VERSION, build_detail_blob


def test_export_schema_version_bumped_to_v6_compatible():
    """Schema version must reflect the profile_gate addition."""
    # v1.6.0 indicates profile_gate is now in detail blobs
    assert EXPORT_SCHEMA_VERSION == "1.6.0", (
        f"EXPORT_SCHEMA_VERSION={EXPORT_SCHEMA_VERSION!r}; expected '1.6.0' for v6.0 "
        f"profile_gate passthrough"
    )


def _scored_skeleton(dsld_id: str = "p_pg_test") -> dict:
    """Minimal scored input that build_detail_blob accepts."""
    return {
        "dsld_id": dsld_id,
        "scoring_metadata": {"engine_version": "3.4.0"},
        "scoring": {
            "total_score": 50,
            "max_possible": 80,
            "score_quality_80": 50,
            "score_display_100_equivalent": "62",
            "verdict": "CAUTION",
        },
        "section_scores": {},
    }


def _enriched_with_interaction_alert() -> dict:
    """Enriched product blob with one interaction alert carrying profile_gate."""
    sample_gate = {
        "gate_type": "condition",
        "requires": {"conditions_any": ["diabetes"], "drug_classes_any": [], "profile_flags_any": []},
        "excludes": {"conditions_any": [], "drug_classes_any": [], "profile_flags_any": [],
                     "product_forms_any": [], "nutrient_forms_any": []},
        "dose": None,
    }
    return {
        "dsld_id": "p_pg_test",
        "product_name": "Test Product",
        "brand_name": "TestBrand",
        "ingredient_quality_data": {"ingredients": [], "ingredients_skipped": []},
        "interaction_profile": {
            "condition_summary": {},
            "drug_class_summary": {},
            "ingredient_alerts": [{
                "ingredient_name": "Test Ingredient",
                "subject_ref": {"db": "ingredient_quality_map", "canonical_id": "test"},
                "rule_id": "RULE_TEST_DIABETES",
                "condition_hits": [{
                    "condition_id": "diabetes",
                    "severity": "caution",
                    "evidence_level": "probable",
                    "mechanism": "Test mechanism",
                    "action": "Test action",
                    "sources": [],
                    "alert_headline": "May affect glucose control",
                    "alert_body": "If you have diabetes, talk to your clinician before adding this product and monitor your glucose carefully.",
                    "informational_note": "Test note about glucose effects relevant to people with diabetes.",
                    "profile_gate": sample_gate,
                }],
                "drug_class_hits": [{
                    "drug_class_id": "anticoagulants",
                    "severity": "caution",
                    "evidence_level": "probable",
                    "mechanism": "Test mechanism",
                    "action": "Test action",
                    "sources": [],
                    "alert_headline": "May raise bleeding risk",
                    "alert_body": "If you take a blood thinner, talk to your prescriber before adding this product.",
                    "informational_note": "Test note about bleeding risk relevant to people on anticoagulants.",
                    "profile_gate": {
                        "gate_type": "drug_class",
                        "requires": {"conditions_any": [], "drug_classes_any": ["anticoagulants"], "profile_flags_any": []},
                        "excludes": {"conditions_any": [], "drug_classes_any": [], "profile_flags_any": [],
                                     "product_forms_any": [], "nutrient_forms_any": []},
                        "dose": None,
                    },
                }],
            }],
        },
    }


def test_interaction_warning_carries_profile_gate():
    """Detail blob's warnings list must include profile_gate on interaction warnings."""
    enriched = _enriched_with_interaction_alert()
    blob = build_detail_blob(enriched, _scored_skeleton())
    interaction_warnings = [w for w in blob.get("warnings", []) if w.get("type") == "interaction"]
    assert interaction_warnings, "expected at least one interaction warning"
    for w in interaction_warnings:
        assert "profile_gate" in w, f"interaction warning missing profile_gate: keys={list(w.keys())}"
        assert w["profile_gate"] is not None
        assert w["profile_gate"].get("gate_type") in {"condition", "drug_class", "profile_flag", "combination", "dose", "nutrient_form"}


def test_drug_interaction_warning_carries_profile_gate():
    """Detail blob's drug_interaction warnings must also include profile_gate."""
    enriched = _enriched_with_interaction_alert()
    blob = build_detail_blob(enriched, _scored_skeleton())
    drug_warnings = [w for w in blob.get("warnings", []) if w.get("type") == "drug_interaction"]
    assert drug_warnings, "expected at least one drug_interaction warning"
    for w in drug_warnings:
        assert "profile_gate" in w, f"drug_interaction warning missing profile_gate: keys={list(w.keys())}"
        assert w["profile_gate"] is not None
        assert w["profile_gate"].get("gate_type") == "drug_class"


def test_warning_profile_gate_shape_matches_source():
    """The emitted profile_gate matches the source dict from the enricher."""
    enriched = _enriched_with_interaction_alert()
    source_gate = enriched["interaction_profile"]["ingredient_alerts"][0]["condition_hits"][0]["profile_gate"]
    blob = build_detail_blob(enriched, _scored_skeleton())
    interaction_warnings = [w for w in blob.get("warnings", []) if w.get("type") == "interaction"]
    assert interaction_warnings
    # Compare structural shape
    emitted = interaction_warnings[0]["profile_gate"]
    assert emitted["gate_type"] == source_gate["gate_type"]
    assert emitted["requires"]["conditions_any"] == source_gate["requires"]["conditions_any"]
