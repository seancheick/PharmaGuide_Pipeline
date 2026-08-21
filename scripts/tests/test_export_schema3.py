"""Prepared schema-3 export cleanup and warning-equivalence contract."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from export_schema import (  # noqa: E402
    project_detail_blob,
    resolve_warning_rule_refs,
)


RULE = {
    "id": "RULE_TEST_MAGNESIUM_DIABETES",
    "subject_ref": {
        "db": "ingredient_quality_map",
        "canonical_id": "magnesium",
    },
    "condition_rules": [
        {
            "condition_id": "diabetes",
            "severity": "caution",
            "evidence_level": "probable",
            "mechanism": "Magnesium may affect glucose control.",
            "action": "Monitor glucose with your clinician.",
            "sources": ["https://ods.od.nih.gov/factsheets/Magnesium-HealthProfessional/"],
            "alert_headline": "May affect glucose control",
            "alert_body": "If you have diabetes, discuss magnesium use with your clinician.",
            "informational_note": "Magnesium and glucose control may be relevant for diabetes.",
            "profile_gate": {
                "gate_type": "condition",
                "requires": {
                    "conditions_any": ["diabetes"],
                    "drug_classes_any": [],
                    "profile_flags_any": [],
                },
                "excludes": {
                    "conditions_any": [],
                    "drug_classes_any": [],
                    "profile_flags_any": [],
                    "product_forms_any": [],
                    "nutrient_forms_any": [],
                },
                "dose": None,
            },
            "direction": "harmful",
            "materiality": "presence",
        }
    ],
    "drug_class_rules": [],
    "dose_thresholds": [],
    "pregnancy_lactation": {},
}


FULL_INTERACTION_WARNING = {
    "type": "interaction",
    "severity": "caution",
    "severity_contextual": "informational",
    "display_mode_default": "suppress",
    "title": "Magnesium / diabetes",
    "detail": "Magnesium may affect glucose control.",
    "action": "Monitor glucose with your clinician.",
    "alert_headline": "May affect glucose control",
    "alert_body": "If you have diabetes, discuss magnesium use with your clinician.",
    "informational_note": "Magnesium and glucose control may be relevant for diabetes.",
    "condition_ids": ["diabetes"],
    "drug_class_ids": [],
    "ingredient_name": "Magnesium",
    "ingredient_canonical_id": "magnesium",
    "evidence_level": "probable",
    "sources": ["https://ods.od.nih.gov/factsheets/Magnesium-HealthProfessional/"],
    "dose_threshold_evaluation": None,
    "dose_decision": {
        "clinical_severity": "caution",
        "evaluation_status": "evaluated",
        "consumer_disposition": "review",
    },
    "direction": "harmful",
    "materiality": "presence",
    "min_effective_dose": None,
    "dose_floor_status": None,
    "source": "interaction_rules",
    "source_rule_id": "RULE_TEST_MAGNESIUM_DIABETES",
    "profile_gate": RULE["condition_rules"][0]["profile_gate"],
}


PREGNANCY_WARNING = {
    "type": "interaction",
    "severity": "no_data",
    "severity_contextual": "no_data",
    "display_mode_default": "suppress",
    "title": "Magnesium / pregnancy",
    "detail": "",
    "action": "Discuss magnesium use during pregnancy with your clinician.",
    "alert_headline": "Pregnancy guidance",
    "alert_body": "Review magnesium use with your prenatal care team.",
    "informational_note": "Pregnancy-specific guidance applies.",
    "condition_ids": ["pregnancy"],
    "drug_class_ids": [],
    "ingredient_name": "Magnesium",
    "ingredient_canonical_id": "magnesium",
    "evidence_level": "no_data",
    "sources": [],
    "dose_threshold_evaluation": None,
    "dose_decision": None,
    "direction": "unknown",
    "materiality": "presence",
    "min_effective_dose": None,
    "dose_floor_status": None,
    "source": "interaction_rules",
    "source_rule_id": "RULE_TEST_MAGNESIUM_DIABETES",
    "profile_gate": None,
    "source_producers": ["interaction_rules"],
}


def _schema2_blob() -> dict:
    return {
        "blob_version": 1,
        "ingredients": [
            {
                "canonical_id": "magnesium",
                "safety_hits": [{"rule_id": RULE["id"], "payload": "large"}],
            }
        ],
        "warnings": [
            FULL_INTERACTION_WARNING,
            {
                "type": "banned_substance",
                "severity": "critical",
                "title": "Banned substance",
                "detail": "Authoritative safety copy remains display-ready.",
                "display_mode_default": "critical",
            },
        ],
        "warnings_profile_gated": [
            {
                "type": "banned_substance",
                "severity": "critical",
                "title": "Banned substance",
                "detail": "Authoritative safety copy remains display-ready.",
                "display_mode_default": "critical",
            }
        ],
        "section_breakdown": {"ingredient_quality": {"score": 10}},
        "row_ledger": [
            {
                "row_ref": "ingredientRows[0]",
                "source_role": "score_active",
                "score_eligible": True,
                "mapping_disposition": "mapped_score_active",
                "reason_code": "MAPPED_CANONICAL_IDENTITY",
                "final_destination": "ingredients",
            }
        ],
        "row_ledger_summary": {
            "source_row_count": 1,
            "mapped_coverage": 1.0,
        },
        "rda_ul_data": {
            "ingredients_with_rda": [{"canonical_id": "magnesium"}],
            "adequacy_results": [{"canonical_id": "magnesium"}],
            "analyzed_ingredients": [
                {
                    "canonical_id": "magnesium",
                    "normalized_amount": 100,
                    "normalized_unit": "mg",
                    "data_by_group": [{"group": "adults", "rda": 420}],
                }
            ],
            "safety_flags": [],
        },
        "non_gmo_audit": {"diagnostic": True},
        "omega3_audit": {"diagnostic": True},
        "proprietary_blend_audit": {"diagnostic": True},
        "proprietary_blend": True,
        "proprietary_blend_detail": {
            "has_proprietary_blends": True,
            "blends": [{"name": "Test Blend"}],
        },
        "supplement_type_audit": {"diagnostic": True},
        "audit": {"diagnostic": True},
        "product_status_detail": {"type": "discontinued"},
        "product_status": {"type": "discontinued"},
        "synergy_detail": {
            "clusters": [{"cluster_id": "sleep_stack", "id": "sleep_stack"}]
        },
    }


def test_schema_24_projection_is_byte_stable() -> None:
    source = _schema2_blob()
    projected = project_detail_blob(source, export_schema_version="2.4.0")

    assert projected is source
    assert json.dumps(projected, sort_keys=True) == json.dumps(source, sort_keys=True)


def test_schema_3_removes_only_redundant_consumer_payloads() -> None:
    projected = project_detail_blob(_schema2_blob(), export_schema_version="3.0.0")

    assert projected["blob_version"] == 3
    assert "section_breakdown" not in projected
    assert "warnings_profile_gated" not in projected
    assert "product_status" not in projected
    assert "row_ledger" not in projected
    assert "row_ledger_summary" not in projected
    assert projected["product_status_detail"]["type"] == "discontinued"
    assert projected["synergy_detail"]["clusters"] == [
        {"cluster_id": "sleep_stack"}
    ]
    assert projected["has_opaque_proprietary_blend"] is True
    assert "proprietary_blend" not in projected
    assert projected["proprietary_blend_detail"] == {
        "has_any_proprietary_blend": True,
        "blends": [{"name": "Test Blend"}],
    }
    assert "safety_hits" not in projected["ingredients"][0]
    assert "ingredients_with_rda" not in projected["rda_ul_data"]
    assert "adequacy_results" not in projected["rda_ul_data"]
    assert "data_by_group" not in projected["rda_ul_data"]["analyzed_ingredients"][0]
    for diagnostic in (
        "non_gmo_audit",
        "omega3_audit",
        "proprietary_blend_audit",
        "supplement_type_audit",
        "audit",
    ):
        assert diagnostic not in projected


def test_schema_3_warning_refs_rehydrate_byte_equivalent_interaction_copy() -> None:
    source = _schema2_blob()
    projected = project_detail_blob(source, export_schema_version="3.0.0")

    assert projected["warnings"] == [source["warnings"][1]]
    assert len(projected["warning_rule_refs"]) == 1
    assert "detail" not in projected["warning_rule_refs"][0]
    assert "alert_body" not in projected["warning_rule_refs"][0]

    resolved = resolve_warning_rule_refs(
        projected["warning_rule_refs"],
        rules_by_id={RULE["id"]: RULE},
    )
    assert resolved == [FULL_INTERACTION_WARNING]


def test_schema_3_rehydrates_pregnancy_warning_and_dedup_provenance() -> None:
    rule = json.loads(json.dumps(RULE))
    rule["condition_rules"].append(
        {
            "condition_id": "pregnancy",
            "severity": "caution",
            "evidence_level": "established",
            "mechanism": "Different explicit pregnancy rule copy.",
            "action": "Use the explicit condition action.",
            "sources": ["https://example.com/explicit"],
            "alert_headline": "Explicit condition copy",
            "alert_body": "This must not replace the selected aggregate copy.",
            "informational_note": None,
            "direction": "harmful",
            "materiality": "presence",
        }
    )
    rule["pregnancy_lactation"] = {
        "pregnancy_category": "no_data",
        "lactation_category": "no_data",
        "evidence_level": "no_data",
        "notes": "Discuss magnesium use during pregnancy with your clinician.",
        "alert_headline": "Pregnancy guidance",
        "alert_body": "Review magnesium use with your prenatal care team.",
        "informational_note": "Pregnancy-specific guidance applies.",
        "direction": "unknown",
        "materiality": "presence",
    }
    blob = _schema2_blob()
    blob["warnings"] = [PREGNANCY_WARNING]

    projected = project_detail_blob(blob, export_schema_version="3.0.0")
    resolved = resolve_warning_rule_refs(
        projected["warning_rule_refs"],
        rules_by_id={rule["id"]: rule},
    )

    assert resolved == [PREGNANCY_WARNING]


def test_schema_3_rejects_interaction_warning_without_stable_rule_id() -> None:
    blob = _schema2_blob()
    blob["warnings"][0].pop("source_rule_id")

    try:
        project_detail_blob(blob, export_schema_version="3.0.0")
    except ValueError as exc:
        assert "stable source_rule_id" in str(exc)
    else:  # pragma: no cover - assertion branch
        raise AssertionError("schema 3 must not delete warning prose without a rule id")
