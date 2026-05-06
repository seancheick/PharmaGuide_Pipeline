#!/usr/bin/env python3
"""Contract tests for v6.0 profile_gate validator + evaluator.

Three concerns:
  1. Validator structural rules per ADR §"Strict per-gate-type validator"
  2. Evaluator semantics — runs the shared fixture
     (scripts/data/profile_gate_test_cases.json) which Dart MUST also pass.
  3. Live rule file invariants — every gate in
     scripts/data/ingredient_interaction_rules.json passes validation.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


# Load the evaluator module dynamically (it lives in scripts/, not on path).
# Register in sys.modules BEFORE exec so @dataclass can resolve cls.__module__.
_EVAL_PATH = Path(__file__).resolve().parents[1] / "profile_gate_evaluator.py"
_spec = importlib.util.spec_from_file_location("profile_gate_evaluator", _EVAL_PATH)
_mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
sys.modules["profile_gate_evaluator"] = _mod
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]
validate_profile_gate = _mod.validate_profile_gate
evaluate_profile_gate = _mod.evaluate_profile_gate


DATA_DIR = Path(__file__).resolve().parents[1] / "data"


@pytest.fixture(scope="module")
def taxonomy():
    with (DATA_DIR / "clinical_risk_taxonomy.json").open() as f:
        return json.load(f)


@pytest.fixture(scope="module")
def form_vocab():
    p = DATA_DIR / "form_keywords_vocab.json"
    if not p.exists():
        return {}
    with p.open() as f:
        return json.load(f)


@pytest.fixture(scope="module")
def fixture_cases():
    with (DATA_DIR / "profile_gate_test_cases.json").open() as f:
        return json.load(f)["test_cases"]


@pytest.fixture(scope="module")
def live_rules():
    with (DATA_DIR / "ingredient_interaction_rules.json").open() as f:
        return json.load(f)["interaction_rules"]


def _empty_excludes():
    return {"conditions_any": [], "drug_classes_any": [], "profile_flags_any": [],
            "product_forms_any": [], "nutrient_forms_any": []}


def _gate(gate_type, requires=None, excludes=None, dose=None):
    return {
        "gate_type": gate_type,
        "requires": requires or {"conditions_any": [], "drug_classes_any": [], "profile_flags_any": []},
        "excludes": excludes or _empty_excludes(),
        "dose": dose,
    }


# --- Validator structural tests ---


def test_validator_clean_condition_gate_passes():
    g = _gate("condition", requires={"conditions_any": ["diabetes"], "drug_classes_any": [], "profile_flags_any": []})
    assert validate_profile_gate(g) == []


def test_validator_unknown_gate_type_fails():
    g = _gate("bogus", requires={"conditions_any": ["x"], "drug_classes_any": [], "profile_flags_any": []})
    errors = validate_profile_gate(g)
    assert any("gate_type" in e for e in errors)


def test_validator_condition_gate_with_drug_class_key_fails():
    """gate_type=condition must NOT also populate drug_classes_any."""
    g = _gate("condition", requires={"conditions_any": ["diabetes"], "drug_classes_any": ["anticoagulants"], "profile_flags_any": []})
    errors = validate_profile_gate(g)
    assert any("must only populate requires.conditions_any" in e for e in errors)


def test_validator_drug_class_gate_with_condition_key_fails():
    g = _gate("drug_class", requires={"conditions_any": ["diabetes"], "drug_classes_any": ["anticoagulants"], "profile_flags_any": []})
    errors = validate_profile_gate(g)
    assert any("must only populate requires.drug_classes_any" in e for e in errors)


def test_validator_profile_flag_gate_with_condition_key_fails():
    g = _gate("profile_flag", requires={"conditions_any": ["x"], "drug_classes_any": [], "profile_flags_any": ["pregnant"]})
    errors = validate_profile_gate(g)
    assert any("must only populate requires.profile_flags_any" in e for e in errors)


def test_validator_combination_with_one_key_warns():
    """combination gate needs ≥2 populated requires keys."""
    g = _gate("combination", requires={"conditions_any": ["diabetes"], "drug_classes_any": [], "profile_flags_any": []})
    errors = validate_profile_gate(g)
    assert any("≥2 populated" in e for e in errors)


def test_validator_dose_gate_without_dose_fails():
    g = _gate("dose")
    errors = validate_profile_gate(g)
    assert any("non-null dose block" in e for e in errors)


def test_validator_empty_id_in_requires_fails():
    g = _gate("condition", requires={"conditions_any": [""], "drug_classes_any": [], "profile_flags_any": []})
    errors = validate_profile_gate(g)
    assert any("empty/non-string id" in e for e in errors)


def test_validator_required_gate_keys_must_be_populated():
    g = _gate("condition")  # all requires empty
    errors = validate_profile_gate(g)
    assert any("non-empty requires.conditions_any" in e for e in errors)


def test_validator_taxonomy_check_unknown_condition(taxonomy):
    g = _gate("condition", requires={"conditions_any": ["not_a_condition"], "drug_classes_any": [], "profile_flags_any": []})
    errors = validate_profile_gate(g, taxonomy=taxonomy)
    assert any("not in taxonomy.conditions" in e for e in errors)


def test_validator_taxonomy_check_unknown_profile_flag(taxonomy):
    g = _gate("profile_flag", requires={"conditions_any": [], "drug_classes_any": [], "profile_flags_any": ["bogus_flag"]})
    errors = validate_profile_gate(g, taxonomy=taxonomy)
    assert any("not in taxonomy.profile_flags" in e for e in errors)


def test_validator_taxonomy_check_unknown_product_form(taxonomy):
    g = _gate(
        "profile_flag",
        requires={"conditions_any": [], "drug_classes_any": [], "profile_flags_any": ["pregnant"]},
        excludes={**_empty_excludes(), "product_forms_any": ["not_a_form"]},
    )
    errors = validate_profile_gate(g, taxonomy=taxonomy)
    assert any("not in taxonomy.product_forms" in e for e in errors)


# --- Shared evaluator fixture (Dart MUST pass these too) ---


def test_shared_fixture_loads():
    with (DATA_DIR / "profile_gate_test_cases.json").open() as f:
        data = json.load(f)
    assert data["_metadata"]["evaluator_contract_version"] == "6.0"
    assert len(data["test_cases"]) >= 18


def test_shared_fixture_every_case_evaluates_correctly(fixture_cases):
    failures = []
    for case in fixture_cases:
        result = evaluate_profile_gate(
            case["gate"],
            case["user_profile"],
            case["product_context"],
            base_severity=case.get("base_severity"),
        )
        exp = case["expected"]
        if result.fires != exp["fires"]:
            failures.append(
                f"[{case['name']}] expected fires={exp['fires']} got {result.fires} (reason: {result.reason})"
            )
        if exp["fires"] and result.severity != exp["severity"]:
            failures.append(
                f"[{case['name']}] expected severity={exp['severity']!r} got {result.severity!r}"
            )
    assert not failures, "\n  - ".join([f"{len(failures)} fixture mismatch(es):"] + failures)


# --- Live rule file invariants ---


def test_live_file_every_gate_passes_validator(live_rules, taxonomy, form_vocab):
    failures: list[str] = []
    for rule in live_rules:
        rule_id = rule.get("id", "?")

        def check(sub: dict, path: str) -> None:
            gate = sub.get("profile_gate")
            if gate is None:
                # only required if the sub-rule is post-migration; report missing
                failures.append(f"{rule_id}/{path}: missing profile_gate")
                return
            errors = validate_profile_gate(gate, taxonomy=taxonomy, form_vocab=form_vocab or None)
            for e in errors:
                failures.append(f"{rule_id}/{path}: {e}")

        for i, cr in enumerate(rule.get("condition_rules") or []):
            if isinstance(cr, dict):
                check(cr, f"condition_rules[{i}]")
        for i, dr in enumerate(rule.get("drug_class_rules") or []):
            if isinstance(dr, dict):
                check(dr, f"drug_class_rules[{i}]")
        for i, dt in enumerate(rule.get("dose_thresholds") or []):
            if isinstance(dt, dict):
                check(dt, f"dose_thresholds[{i}]")
        pl = rule.get("pregnancy_lactation")
        if isinstance(pl, dict) and pl:
            preg = (pl.get("pregnancy_category") or "").strip().lower()
            lact = (pl.get("lactation_category") or "").strip().lower()
            if preg not in {"no_data", ""} or lact not in {"no_data", ""}:
                check(pl, "pregnancy_lactation")

    assert not failures, (
        f"\n{len(failures)} validator failure(s) in live rule file:\n  - "
        + "\n  - ".join(failures[:30])
        + (f"\n  ... and {len(failures) - 30} more" if len(failures) > 30 else "")
    )


def test_live_file_no_combination_gate_with_only_one_axis(live_rules):
    """Catch any rule that should be a single-axis gate but is mistakenly
    typed as combination."""
    suspicious = []
    for rule in live_rules:
        rule_id = rule.get("id", "?")
        for bucket in ("condition_rules", "drug_class_rules", "dose_thresholds"):
            for i, sub in enumerate(rule.get(bucket) or []):
                if not isinstance(sub, dict):
                    continue
                gate = sub.get("profile_gate") or {}
                if gate.get("gate_type") != "combination":
                    continue
                req = gate.get("requires") or {}
                populated = sum(1 for k in ("conditions_any", "drug_classes_any", "profile_flags_any")
                                if req.get(k))
                if populated < 2:
                    # Allow combination + dose (single-axis-with-dose is valid)
                    if not gate.get("dose"):
                        suspicious.append(f"{rule_id}/{bucket}[{i}]")
    assert not suspicious, f"combination gate with <2 axes and no dose: {suspicious}"
