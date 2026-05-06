#!/usr/bin/env python3
"""Reference Python implementation of the v6.0 profile_gate evaluator + validator.

This module is the source-of-truth for `profile_gate` semantics defined in
scripts/INTERACTION_RULE_SCHEMA_V6_ADR.md. The Flutter (Dart) implementation
MUST produce the same boolean / severity output for every case in
scripts/data/profile_gate_test_cases.json — the shared evaluator fixture.

Two surfaces:

1. validate_profile_gate(gate, *, taxonomy)
   Structural + vocabulary check. Returns list[str] of errors.

2. evaluate_profile_gate(gate, user_profile, product_context)
   Returns EvaluationResult(fires: bool, severity: str | None).

Semantics (locked by ADR):
  - requires: AND across populated keys, OR within each list.
  - excludes: OR — any match suppresses the rule.
  - dose: optional; modifies severity after gate matches via
    severity_if_met / severity_if_not_met. Does NOT change fires=True/False.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


# --- Locked vocabulary (mirrors ADR §"Decisions locked") ---

ALLOWED_GATE_TYPES = {"condition", "drug_class", "profile_flag", "dose", "nutrient_form", "combination"}

# Per-gate-type strict requires-key allowance.
# combination is the only multi-key gate; everything else is single-axis.
GATE_TYPE_REQUIRED_KEY = {
    "condition":     "conditions_any",
    "drug_class":    "drug_classes_any",
    "profile_flag":  "profile_flags_any",
}


# --- Validator ---


def validate_profile_gate(
    gate: Any,
    *,
    taxonomy: Optional[dict[str, Any]] = None,
    form_vocab: Optional[dict[str, Any]] = None,
) -> list[str]:
    """Return list of error strings; empty list = clean.

    taxonomy: parsed clinical_risk_taxonomy.json (for condition / drug_class /
              profile_flag / product_form ID checks)
    form_vocab: parsed form_keywords_vocab.json (for nutrient_form ID checks)
    """
    errors: list[str] = []

    if not isinstance(gate, dict):
        return [f"profile_gate must be a dict, got {type(gate).__name__}"]

    gt = gate.get("gate_type")
    if gt not in ALLOWED_GATE_TYPES:
        errors.append(f"gate_type {gt!r} not in {sorted(ALLOWED_GATE_TYPES)}")

    req = gate.get("requires") or {}
    exc = gate.get("excludes") or {}

    for k in ("conditions_any", "drug_classes_any", "profile_flags_any"):
        if k not in req:
            errors.append(f"requires missing key {k!r}")
        else:
            for v in req[k] or []:
                if not isinstance(v, str) or not v.strip():
                    errors.append(f"requires.{k} contains empty/non-string id {v!r}")

    for k in ("conditions_any", "drug_classes_any", "profile_flags_any",
              "product_forms_any", "nutrient_forms_any"):
        if k not in exc:
            errors.append(f"excludes missing key {k!r}")
        else:
            for v in exc[k] or []:
                if not isinstance(v, str) or not v.strip():
                    errors.append(f"excludes.{k} contains empty/non-string id {v!r}")

    # Per-gate-type strict-key validation
    if gt in GATE_TYPE_REQUIRED_KEY:
        required_key = GATE_TYPE_REQUIRED_KEY[gt]
        # The required key must be populated
        if not (req.get(required_key) or []):
            errors.append(f"gate_type={gt!r} requires non-empty requires.{required_key}")
        # No OTHER key may be populated (single-axis enforcement)
        for k in ("conditions_any", "drug_classes_any", "profile_flags_any"):
            if k != required_key and (req.get(k) or []):
                errors.append(
                    f"gate_type={gt!r} must only populate requires.{required_key}; "
                    f"found requires.{k}={req.get(k)!r} (use gate_type='combination' for multi-axis)"
                )
    elif gt == "combination":
        populated = sum(1 for k in ("conditions_any", "drug_classes_any", "profile_flags_any") if req.get(k))
        # combination = "more than one concern": either (a) ≥2 requires axes, OR
        # (b) exactly 1 requires axis combined with a dose threshold (the dose
        # check is the second axis). The ADR's migration table maps
        # dose_thresholds[scope=condition/drug_class/profile_flag] → combination
        # with one requires key + a dose block; that's a valid combination.
        has_dose = isinstance(gate.get("dose"), dict)
        if populated < 2 and not has_dose:
            errors.append(
                f"gate_type='combination' needs ≥2 populated requires keys OR a dose block; "
                f"got requires_populated={populated} dose={'present' if has_dose else 'absent'}"
            )
    elif gt == "dose":
        if not gate.get("dose"):
            errors.append("gate_type='dose' requires non-null dose block")

    # Cross-vocabulary check
    if taxonomy:
        valid_conditions = {c["id"] for c in taxonomy.get("conditions", []) if isinstance(c, dict)}
        valid_drug_classes = {c["id"] for c in taxonomy.get("drug_classes", []) if isinstance(c, dict)}
        valid_flags = {c["id"] for c in taxonomy.get("profile_flags", []) if isinstance(c, dict)}
        valid_product_forms = {c["id"] for c in taxonomy.get("product_forms", []) if isinstance(c, dict)}

        for v in (req.get("conditions_any") or []) + (exc.get("conditions_any") or []):
            if v and v not in valid_conditions:
                errors.append(f"unknown condition_id {v!r} (not in taxonomy.conditions)")
        for v in (req.get("drug_classes_any") or []) + (exc.get("drug_classes_any") or []):
            if v and v not in valid_drug_classes:
                errors.append(f"unknown drug_class_id {v!r} (not in taxonomy.drug_classes)")
        for v in (req.get("profile_flags_any") or []) + (exc.get("profile_flags_any") or []):
            if v and v not in valid_flags:
                errors.append(f"unknown profile_flag {v!r} (not in taxonomy.profile_flags)")
        for v in (exc.get("product_forms_any") or []):
            if v and v not in valid_product_forms:
                errors.append(f"unknown product_form {v!r} (not in taxonomy.product_forms)")

    if form_vocab:
        valid_nutrient_forms = set(_collect_form_vocab_ids(form_vocab))
        for v in (exc.get("nutrient_forms_any") or []):
            if v and v not in valid_nutrient_forms:
                errors.append(f"unknown nutrient_form {v!r} (not in form_keywords_vocab)")

    return errors


def _collect_form_vocab_ids(form_vocab: dict[str, Any]) -> set[str]:
    """Walk form_keywords_vocab.json shape to collect every form id we recognize.

    The vocab file is structured as `categories[].name` plus a `forms[].id`-like
    layout in some versions. We accept any string under category->forms->id, and
    also accept the lowercased category name as an id (for top-level forms like
    'beta_carotene' vs 'mixed_carotenoids' which may live at category root).
    """
    ids: set[str] = set()
    cats = form_vocab.get("categories") or form_vocab.get("form_keywords") or []
    if isinstance(cats, dict):
        cats = list(cats.values())
    for cat in cats:
        if isinstance(cat, dict):
            for f in cat.get("forms", []) or []:
                if isinstance(f, dict) and isinstance(f.get("id"), str):
                    ids.add(f["id"])
                elif isinstance(f, str):
                    ids.add(f)
    # Fallback: also accept commonly-cited explicit ids that may be top-level
    for default in ("beta_carotene", "mixed_carotenoids", "retinol",
                    "retinyl_palmitate", "retinyl_acetate"):
        ids.add(default)
    return ids


# --- Evaluator ---


@dataclass
class EvaluationResult:
    """Result of evaluating a profile_gate against a user profile + product."""
    fires: bool
    severity: Optional[str] = None
    reason: str = ""


def evaluate_profile_gate(
    gate: dict[str, Any],
    user_profile: dict[str, Any],
    product_context: dict[str, Any],
    *,
    base_severity: Optional[str] = None,
) -> EvaluationResult:
    """Evaluate whether the gate fires for this user + product, and at what severity.

    user_profile keys: conditions, drug_classes, profile_flags  (each list[str])
    product_context keys: product_form (str|None), nutrient_form (str|None),
                          dose_per_day (number|None), dose_unit (str|None)
    base_severity: the sub-rule's static severity field; passed in so the dose
                   block can override it.

    Returns EvaluationResult(fires, severity, reason).
    """
    requires = gate.get("requires") or {}
    excludes = gate.get("excludes") or {}

    user_conditions   = set(user_profile.get("conditions", []) or [])
    user_drug_classes = set(user_profile.get("drug_classes", []) or [])
    user_flags        = set(user_profile.get("profile_flags", []) or [])

    # requires: AND across populated keys, OR within each list.
    require_pairs = [
        ("conditions_any",    user_conditions),
        ("drug_classes_any",  user_drug_classes),
        ("profile_flags_any", user_flags),
    ]
    for key, user_set in require_pairs:
        req_list = requires.get(key) or []
        if req_list and not (set(req_list) & user_set):
            return EvaluationResult(
                fires=False,
                severity=None,
                reason=f"requires.{key} not satisfied: needs any of {req_list}, user has {sorted(user_set)}",
            )

    # excludes: OR — any match suppresses.
    for key, user_set in require_pairs:
        exc_list = excludes.get(key) or []
        if exc_list and (set(exc_list) & user_set):
            return EvaluationResult(
                fires=False,
                severity=None,
                reason=f"excludes.{key} suppressed: matched {sorted(set(exc_list) & user_set)}",
            )

    product_form = product_context.get("product_form")
    if product_form and product_form in (excludes.get("product_forms_any") or []):
        return EvaluationResult(
            fires=False,
            severity=None,
            reason=f"excludes.product_forms_any suppressed: product_form={product_form!r}",
        )

    nutrient_form = product_context.get("nutrient_form")
    if nutrient_form and nutrient_form in (excludes.get("nutrient_forms_any") or []):
        return EvaluationResult(
            fires=False,
            severity=None,
            reason=f"excludes.nutrient_forms_any suppressed: nutrient_form={nutrient_form!r}",
        )

    # Gate matched. Compute severity.
    severity = base_severity
    dose = gate.get("dose")
    if isinstance(dose, dict):
        sev = _resolve_dose_severity(dose, product_context)
        if sev is not None:
            severity = sev

    return EvaluationResult(fires=True, severity=severity, reason="all gate predicates satisfied")


def _resolve_dose_severity(dose: dict[str, Any], product_context: dict[str, Any]) -> Optional[str]:
    """Apply the gate's dose block: if comparator(value) is met, use severity_if_met
    else severity_if_not_met. Returns None if the dose can't be evaluated.
    """
    comparator = dose.get("comparator")
    threshold  = dose.get("value")
    user_dose  = product_context.get("dose_per_day")
    if user_dose is None or threshold is None or comparator is None:
        return dose.get("severity_if_not_met")

    try:
        u = float(user_dose)
        t = float(threshold)
    except (TypeError, ValueError):
        return dose.get("severity_if_not_met")

    met = {
        ">":  u >  t,
        ">=": u >= t,
        "<":  u <  t,
        "<=": u <= t,
        "==": u == t,
    }.get(comparator)
    if met is None:
        return dose.get("severity_if_not_met")
    return dose.get("severity_if_met") if met else dose.get("severity_if_not_met")
