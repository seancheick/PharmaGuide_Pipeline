#!/usr/bin/env python3
"""Regression guards for interaction-rule data-integrity issues found in review.

These checks intentionally stay structural and hermetic. Clinical content is
still source-reviewed separately, but these failure modes should never re-enter
the data file unnoticed.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path


DATA = Path(__file__).resolve().parents[1] / "data"
RULES = json.loads((DATA / "ingredient_interaction_rules.json").read_text())[
    "interaction_rules"
]

SEVERITY_RANK = {
    "informational": 1,
    "monitor": 2,
    "caution": 3,
    "avoid": 4,
    "contraindicated": 5,
}


def _targets(rule: dict) -> set[tuple[str, str]]:
    out = set()
    for item in rule.get("condition_rules") or []:
        out.add(("condition", item.get("condition_id")))
    for item in rule.get("drug_class_rules") or []:
        out.add(("drug_class", item.get("drug_class_id")))
    for item in rule.get("dose_thresholds") or []:
        out.add((item.get("scope"), item.get("target_id")))
    return {x for x in out if x[1]}


def test_non_form_scoped_duplicate_canonicals_do_not_overlap_targets():
    """Two unscoped rows for one canonical_id must not own the same target.

    Form-scoped variants are allowed; overlapping unscoped rows double-fire and
    can ship conflicting thresholds/copy.
    """
    by_canonical = defaultdict(list)
    for rule in RULES:
        canonical_id = (rule.get("subject_ref") or {}).get("canonical_id")
        if canonical_id and not rule.get("form_scope"):
            by_canonical[canonical_id].append((rule["id"], _targets(rule)))

    overlaps = []
    for canonical_id, entries in by_canonical.items():
        for i, (left_id, left_targets) in enumerate(entries):
            for right_id, right_targets in entries[i + 1 :]:
                overlap = left_targets & right_targets
                if overlap:
                    overlaps.append((canonical_id, left_id, right_id, sorted(overlap)))

    assert not overlaps, f"overlapping unscoped canonical rules: {overlaps}"


def test_pregnancy_condition_rules_do_not_conflict_with_pregnancy_lactation_no_data():
    contradictions = []
    for rule in RULES:
        pregnancy_lactation = rule.get("pregnancy_lactation") or {}
        if pregnancy_lactation.get("pregnancy_category") != "no_data":
            continue
        for item in rule.get("condition_rules") or []:
            if item.get("condition_id") == "pregnancy":
                contradictions.append(rule["id"])

    assert not contradictions, (
        "condition_rules[pregnancy] cannot coexist with "
        f"pregnancy_lactation.pregnancy_category=no_data: {contradictions}"
    )


def test_dose_thresholds_do_not_lower_matching_baseline_severity():
    downgrades = []
    for rule in RULES:
        baseline = {}
        for item in rule.get("condition_rules") or []:
            baseline[("condition", item.get("condition_id"))] = item.get("severity")
        for item in rule.get("drug_class_rules") or []:
            baseline[("drug_class", item.get("drug_class_id"))] = item.get("severity")

        for threshold in rule.get("dose_thresholds") or []:
            key = (threshold.get("scope"), threshold.get("target_id"))
            if key not in baseline:
                continue
            base = baseline[key]
            met = threshold.get("severity_if_met")
            if SEVERITY_RANK.get(met, 0) < SEVERITY_RANK.get(base, 0):
                downgrades.append((rule["id"], key, base, met))

    assert not downgrades, f"dose thresholds lower baseline severity: {downgrades}"


def test_vitamin_k_rules_target_vitamin_k_antagonists_not_all_anticoagulants():
    vitamin_k_rules = [
        r
        for r in RULES
        if (r.get("subject_ref") or {}).get("canonical_id") == "vitamin_k"
    ]
    assert vitamin_k_rules

    broad_rules = []
    for vitamin_k in vitamin_k_rules:
        drug_class_ids = {
            item.get("drug_class_id") for item in vitamin_k.get("drug_class_rules") or []
        }
        if "anticoagulants" in drug_class_ids:
            broad_rules.append(vitamin_k["id"])

    assert not broad_rules
    assert any(
        "vitamin_k_antagonists"
        in {
            item.get("drug_class_id")
            for item in vitamin_k.get("drug_class_rules") or []
        }
        for vitamin_k in vitamin_k_rules
    )


def test_probiotic_severe_infection_rule_is_not_autoimmune_gated():
    probiotics = next(
        r
        for r in RULES
        if r.get("id") == "RULE_IQM_PROBIOTICS_IMMUNOCOMPROMISED"
    )
    condition_ids = {
        item.get("condition_id") for item in probiotics.get("condition_rules") or []
    }
    assert "immunocompromised" in condition_ids
    assert "autoimmune" not in condition_ids
