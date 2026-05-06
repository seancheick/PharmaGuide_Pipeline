#!/usr/bin/env python3
"""Unit tests for scripts/tools/migrate_to_profile_gate.py.

Exercises the deterministic mapping table from the v6.0 ADR. No clinical
judgment in the migration — every test is a pure structural assertion.
"""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest


# Load the migrate_to_profile_gate module dynamically (it lives in scripts/tools/, not on path)
_TOOLS_PATH = Path(__file__).resolve().parents[1] / "tools" / "migrate_to_profile_gate.py"
_spec = importlib.util.spec_from_file_location("migrate_to_profile_gate", _TOOLS_PATH)
_mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]
migrate_rules = _mod.migrate_rules


# --- Deterministic mapping unit tests ---


def test_diabetes_condition_rule_gets_condition_gate():
    rule = {
        "subject_ref": {"db": "ingredient_quality_map", "canonical_id": "x"},
        "condition_rules": [{"condition_id": "diabetes", "severity": "caution"}],
        "drug_class_rules": [],
        "dose_thresholds": [],
    }
    data = {"interaction_rules": [rule]}
    out, _ = migrate_rules(data)
    g = out["interaction_rules"][0]["condition_rules"][0]["profile_gate"]
    assert g["gate_type"] == "condition"
    assert g["requires"]["conditions_any"] == ["diabetes"]
    assert g["requires"]["drug_classes_any"] == []
    assert g["requires"]["profile_flags_any"] == []
    assert g["dose"] is None


def test_pregnancy_condition_rule_gets_profile_flag_gate():
    rule = {
        "subject_ref": {"db": "ingredient_quality_map", "canonical_id": "x"},
        "condition_rules": [{"condition_id": "pregnancy", "severity": "avoid"}],
        "drug_class_rules": [],
        "dose_thresholds": [],
    }
    data = {"interaction_rules": [rule]}
    out, _ = migrate_rules(data)
    g = out["interaction_rules"][0]["condition_rules"][0]["profile_gate"]
    assert g["gate_type"] == "profile_flag"
    assert set(g["requires"]["profile_flags_any"]) == {"pregnant", "trying_to_conceive"}
    assert g["requires"]["conditions_any"] == []


def test_lactation_condition_rule_gets_profile_flag_gate():
    rule = {
        "subject_ref": {"db": "ingredient_quality_map", "canonical_id": "x"},
        "condition_rules": [{"condition_id": "lactation", "severity": "monitor"}],
        "drug_class_rules": [],
        "dose_thresholds": [],
    }
    data = {"interaction_rules": [rule]}
    out, _ = migrate_rules(data)
    g = out["interaction_rules"][0]["condition_rules"][0]["profile_gate"]
    assert g["gate_type"] == "profile_flag"
    assert g["requires"]["profile_flags_any"] == ["breastfeeding"]


def test_ttc_condition_rule_gets_profile_flag_gate():
    rule = {
        "subject_ref": {"db": "ingredient_quality_map", "canonical_id": "x"},
        "condition_rules": [{"condition_id": "ttc", "severity": "monitor"}],
        "drug_class_rules": [],
        "dose_thresholds": [],
    }
    data = {"interaction_rules": [rule]}
    out, _ = migrate_rules(data)
    g = out["interaction_rules"][0]["condition_rules"][0]["profile_gate"]
    assert g["gate_type"] == "profile_flag"
    assert g["requires"]["profile_flags_any"] == ["trying_to_conceive"]


def test_surgery_scheduled_condition_rule_gets_profile_flag_gate():
    rule = {
        "subject_ref": {"db": "ingredient_quality_map", "canonical_id": "x"},
        "condition_rules": [{"condition_id": "surgery_scheduled", "severity": "avoid"}],
        "drug_class_rules": [],
        "dose_thresholds": [],
    }
    data = {"interaction_rules": [rule]}
    out, _ = migrate_rules(data)
    g = out["interaction_rules"][0]["condition_rules"][0]["profile_gate"]
    assert g["gate_type"] == "profile_flag"
    assert g["requires"]["profile_flags_any"] == ["surgery_scheduled"]


def test_drug_class_rule_gets_drug_class_gate():
    rule = {
        "subject_ref": {"db": "ingredient_quality_map", "canonical_id": "x"},
        "condition_rules": [],
        "drug_class_rules": [{"drug_class_id": "anticoagulants", "severity": "caution"}],
        "dose_thresholds": [],
    }
    data = {"interaction_rules": [rule]}
    out, _ = migrate_rules(data)
    g = out["interaction_rules"][0]["drug_class_rules"][0]["profile_gate"]
    assert g["gate_type"] == "drug_class"
    assert g["requires"]["drug_classes_any"] == ["anticoagulants"]
    assert g["requires"]["conditions_any"] == []
    assert g["requires"]["profile_flags_any"] == []


def test_dose_threshold_with_condition_scope_gets_combination_gate():
    rule = {
        "subject_ref": {"db": "ingredient_quality_map", "canonical_id": "x"},
        "condition_rules": [],
        "drug_class_rules": [],
        "dose_thresholds": [{
            "scope": "condition", "target_id": "diabetes",
            "basis": "per_day", "comparator": ">=", "value": 1500, "unit": "mg",
            "severity_if_met": "avoid", "severity_if_not_met": "caution",
        }],
    }
    data = {"interaction_rules": [rule]}
    out, _ = migrate_rules(data)
    g = out["interaction_rules"][0]["dose_thresholds"][0]["profile_gate"]
    assert g["gate_type"] == "combination"
    assert g["requires"]["conditions_any"] == ["diabetes"]
    assert g["dose"]["value"] == 1500
    assert g["dose"]["severity_if_met"] == "avoid"


def test_dose_threshold_with_drug_class_scope_gets_combination_gate():
    rule = {
        "subject_ref": {"db": "ingredient_quality_map", "canonical_id": "x"},
        "condition_rules": [], "drug_class_rules": [],
        "dose_thresholds": [{
            "scope": "drug_class", "target_id": "anticoagulants",
            "basis": "per_day", "comparator": ">", "value": 1200, "unit": "mg",
            "severity_if_met": "avoid", "severity_if_not_met": "monitor",
        }],
    }
    out, _ = migrate_rules({"interaction_rules": [rule]})
    g = out["interaction_rules"][0]["dose_thresholds"][0]["profile_gate"]
    assert g["gate_type"] == "combination"
    assert g["requires"]["drug_classes_any"] == ["anticoagulants"]


def test_dose_threshold_with_pregnancy_scope_uses_profile_flag_target():
    """Condition-scoped dose thresholds whose target_id is itself a profile_flag
    (e.g., pregnancy → caffeine 200mg) get profile_flags_any populated, not
    conditions_any."""
    rule = {
        "subject_ref": {"db": "ingredient_quality_map", "canonical_id": "x"},
        "condition_rules": [], "drug_class_rules": [],
        "dose_thresholds": [{
            "scope": "condition", "target_id": "pregnancy",
            "basis": "per_day", "comparator": ">", "value": 200, "unit": "mg",
            "severity_if_met": "caution", "severity_if_not_met": "monitor",
        }],
    }
    out, _ = migrate_rules({"interaction_rules": [rule]})
    g = out["interaction_rules"][0]["dose_thresholds"][0]["profile_gate"]
    assert g["gate_type"] == "combination"
    assert g["requires"]["conditions_any"] == []
    assert set(g["requires"]["profile_flags_any"]) == {"pregnant", "trying_to_conceive"}


def test_pregnancy_lactation_block_gets_union_gate():
    rule = {
        "subject_ref": {"db": "ingredient_quality_map", "canonical_id": "x"},
        "condition_rules": [], "drug_class_rules": [], "dose_thresholds": [],
        "pregnancy_lactation": {
            "pregnancy_category": "avoid",
            "lactation_category": "monitor",
            "evidence_level": "probable",
        },
    }
    out, _ = migrate_rules({"interaction_rules": [rule]})
    g = out["interaction_rules"][0]["pregnancy_lactation"]["profile_gate"]
    assert g["gate_type"] == "profile_flag"
    assert set(g["requires"]["profile_flags_any"]) == {"pregnant", "trying_to_conceive", "breastfeeding"}


def test_pregnancy_lactation_no_data_block_skipped():
    """When both categories are no_data the block should not get a gate."""
    rule = {
        "subject_ref": {"db": "ingredient_quality_map", "canonical_id": "x"},
        "condition_rules": [], "drug_class_rules": [], "dose_thresholds": [],
        "pregnancy_lactation": {
            "pregnancy_category": "no_data",
            "lactation_category": "no_data",
            "evidence_level": "no_data",
        },
    }
    out, _ = migrate_rules({"interaction_rules": [rule]})
    pl = out["interaction_rules"][0]["pregnancy_lactation"]
    assert "profile_gate" not in pl


# --- Idempotency / structural integrity ---


def test_migration_is_idempotent():
    rule = {
        "subject_ref": {"db": "ingredient_quality_map", "canonical_id": "x"},
        "condition_rules": [{"condition_id": "diabetes", "severity": "caution"}],
        "drug_class_rules": [{"drug_class_id": "anticoagulants", "severity": "caution"}],
        "dose_thresholds": [],
    }
    data = {"interaction_rules": [rule]}
    out1, c1 = migrate_rules(copy.deepcopy(data))
    out2, c2 = migrate_rules(copy.deepcopy(out1))
    assert c2["condition_rules"] == 0
    assert c2["drug_class_rules"] == 0
    assert out1 == out2


def test_existing_profile_gate_not_overwritten():
    """If a sub-rule already has profile_gate (e.g., hand-authored), don't overwrite."""
    custom_gate = {"gate_type": "combination", "requires": {"conditions_any": ["x"]}}
    rule = {
        "subject_ref": {"db": "ingredient_quality_map", "canonical_id": "x"},
        "condition_rules": [{
            "condition_id": "diabetes",
            "severity": "caution",
            "profile_gate": custom_gate,
        }],
        "drug_class_rules": [], "dose_thresholds": [],
    }
    out, _ = migrate_rules({"interaction_rules": [rule]})
    assert out["interaction_rules"][0]["condition_rules"][0]["profile_gate"] is custom_gate


def test_full_file_migration_counts_match_expectation():
    """Run the migration on the live file and assert it touches every rule."""
    live = json.loads(
        (Path(__file__).resolve().parents[1] / "data" / "ingredient_interaction_rules.json").read_text()
    )
    _, counts = migrate_rules(copy.deepcopy(live))
    assert counts["rules_visited"] == 145
    # Migration must add at least one gate of each kind across 145 rules
    assert counts["condition_rules"] > 0
    assert counts["drug_class_rules"] > 0
    assert counts["dose_thresholds"] > 0
    assert counts["pregnancy_lactation_blocks"] > 0


def test_excludes_block_starts_empty():
    """ADR §"Decisions locked": excludes is populated only by hand in Step 5."""
    rule = {
        "subject_ref": {"db": "ingredient_quality_map", "canonical_id": "x"},
        "condition_rules": [{"condition_id": "diabetes", "severity": "caution"}],
        "drug_class_rules": [], "dose_thresholds": [],
    }
    out, _ = migrate_rules({"interaction_rules": [rule]})
    g = out["interaction_rules"][0]["condition_rules"][0]["profile_gate"]
    for k, v in g["excludes"].items():
        assert v == [], f"excludes.{k} must be empty post-migration; got {v!r}"
