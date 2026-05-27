"""Wave 8 critical-only interaction batch regressions."""

from __future__ import annotations

import json
from pathlib import Path


DATA = Path(__file__).resolve().parents[1] / "data"


def _load(name: str) -> dict:
    return json.loads((DATA / name).read_text())


def test_critical_batch_has_no_minor_or_monitor_entries() -> None:
    payload = _load("curated_interactions/batch_critical_2026_05.json")
    entries = payload["interactions"]

    assert len(entries) == 10
    assert payload["_metadata"]["total_entries"] == len(entries)
    assert {e["severity"] for e in entries} <= {"Major", "Moderate"}
    assert not [
        e["id"]
        for e in entries
        if str(e.get("severity", "")).lower() in {"minor", "monitor"}
    ]


def test_critical_batch_uses_only_narrow_new_classes() -> None:
    payload = _load("curated_interactions/batch_critical_2026_05.json")
    class_ids = {
        e["agent1_id"]
        for e in payload["interactions"]
        if str(e.get("agent1_id", "")).startswith("class:")
    }

    assert class_ids == {
        "class:doacs",
        "class:fluoroquinolones",
        "class:potassium_sparing_diuretics",
        "class:tetracycline_antibiotics",
    }

    drug_classes = _load("drug_classes.json")["classes"]
    for class_id in class_ids:
        members = drug_classes[class_id]["member_rxcuis"]
        assert members, f"{class_id} must expand to verified RxCUIs"


def test_wave8_rule_only_classes_are_in_all_profile_gate_vocabs() -> None:
    expected = {
        "doacs",
        "fluoroquinolones",
        "potassium_sparing_diuretics",
        "tetracycline_antibiotics",
        "beta_blockers",
    }
    vocab_ids = {d["id"] for d in _load("drug_class_vocab.json")["drug_classes"]}
    taxonomy_ids = {
        d["id"] for d in _load("clinical_risk_taxonomy.json")["drug_classes"]
    }

    assert expected <= vocab_ids
    assert expected <= taxonomy_ids


def test_profile_rules_use_narrow_wave8_drug_classes() -> None:
    rules = _load("ingredient_interaction_rules.json")["interaction_rules"]
    by_subject = {
        rule["subject_ref"]["canonical_id"]: rule
        for rule in rules
        if rule.get("subject_ref", {}).get("db") == "ingredient_quality_map"
    }

    assert any(
        r.get("drug_class_id") == "doacs" and r.get("severity") == "avoid"
        for r in by_subject["st_johns_wort"]["drug_class_rules"]
    )
    assert any(
        r.get("drug_class_id") == "potassium_sparing_diuretics"
        and r.get("severity") == "avoid"
        for r in by_subject["potassium"]["drug_class_rules"]
    )
    assert any(
        r.get("drug_class_id") == "beta_blockers" and r.get("severity") == "avoid"
        for r in by_subject["green_tea_extract"]["drug_class_rules"]
    )
    for mineral in ("calcium", "iron", "magnesium", "zinc"):
        assert any(
            r.get("drug_class_id") == "fluoroquinolones"
            and r.get("severity") == "caution"
            for r in by_subject[mineral]["drug_class_rules"]
        )


def test_biotin_lab_warning_is_diagnostic_interference_not_drug_interaction() -> None:
    rules = _load("ingredient_interaction_rules.json")["interaction_rules"]
    biotin = next(
        r
        for r in rules
        if r.get("subject_ref", {}).get("canonical_id") == "vitamin_b7_biotin"
    )

    diagnostic_conditions = {
        r["condition_id"]
        for r in biotin["condition_rules"]
        if r.get("warning_type") == "diagnostic_interference"
    }
    assert {"thyroid_disorder", "heart_disease"} <= diagnostic_conditions
    assert any(
        t.get("target_id") == "heart_disease"
        and t.get("comparator") == ">="
        and t.get("value") == 5
        and t.get("unit") == "mg"
        and t.get("severity_if_met") == "avoid"
        for t in biotin["dose_thresholds"]
    )
