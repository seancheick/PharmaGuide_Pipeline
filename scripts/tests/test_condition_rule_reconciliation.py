#!/usr/bin/env python3
"""Reconciliation coverage gate: the pipeline (ingredient_interaction_rules.json)
must be the single source of truth for every condition suppression the app's
hand-authored `condition_thresholds.dart` fallback still owns.

These 7 (canonical_id, condition_id) pairs are the app-table suppressions the
freshly-built catalog does NOT yet emit (verified by the reconciliation audit
2026-07-04). Each must become an authored pipeline condition_rule with a
content-verified source before `condition_thresholds.dart` can be deleted.

TEST-FIRST: this fails until the rules are authored. It asserts STRUCTURE
(the pair exists + carries direction/materiality); the clinical CONTENT
(materiality/floor/source correctness) is gated separately by
verify_interaction_rules_citations.py and the dose-floor tests.

Do NOT weaken this test to make it pass — author the rule instead. If clinical
review concludes a pair should NOT warn at all, remove it here WITH the sourced
rationale in the commit, not silently.
"""
import json
from pathlib import Path

import pytest

RULES_PATH = Path(__file__).resolve().parents[1] / "data" / "ingredient_interaction_rules.json"

# (canonical_id, condition_id) — the app-only suppressions the pipeline must own.
# retinol folds into vitamin_a (form of the same nutrient); pregnancy/retinol is
# already covered by the existing vitamin_a/pregnancy rule (form-gating is a
# refinement, not a coverage gap).
RECONCILIATION_TARGETS = [
    ("vitamin_e", "bleeding_disorders"),
    ("vitamin_e", "surgery_scheduled"),  # sibling gap surfaced by the audit
    ("garlic", "bleeding_disorders"),
    ("vitamin_a", "ttc"),
    ("caffeine", "ttc"),
    ("vitamin_b6_pyridoxine", "seizure_disorder"),
]

# RETIRED (2026-07-04, user-confirmed) — the app table warns here but verified
# clinical evidence says NOT to. These are removed from the coverage targets:
# the correct fix is to DROP the app-table entry, not author a pipeline rule.
#   ("vitamin_d", "kidney_disease")  — nutritional D3 is neutral-to-beneficial in
#     CKD; hypercalcemia hazard belongs to prescription active analogs (calcitriol
#     /paricalcitol), not D3 supplements. 4,000 IU is the UL, not a CKD-harm floor.
#     (NIH ODS Vitamin D; NKF CKD-MBD; Frontiers 2025; RCT PMID 28088187.)
#   ("zinc", "kidney_disease")  — CKD/dialysis patients are typically zinc-DEFICIENT
#     and dosed 45-100 mg/day therapeutically; 40 mg is a general copper-antagonism
#     UL, not a renal hazard. No kidney-specific zinc floor exists.
#     (NIH ODS Zinc; Nutrients 2025 PMC12252395.)
RETIRED_APP_ENTRIES = [
    ("vitamin_d", "kidney_disease"),
    ("zinc", "kidney_disease"),
]


def _condition_coverage():
    """Map canonical_id -> {condition_id -> condition_rule dict}."""
    rules = json.loads(RULES_PATH.read_text())["interaction_rules"]
    cov = {}
    for r in rules:
        cid = (r.get("subject_ref") or {}).get("canonical_id")
        if not cid:
            continue
        by_cond = cov.setdefault(cid, {})
        for cr in r.get("condition_rules") or []:
            cond = cr.get("condition_id")
            if cond:
                by_cond[cond] = cr
    return cov


@pytest.mark.parametrize("canonical_id,condition_id", RECONCILIATION_TARGETS)
def test_pipeline_covers_app_table_suppression(canonical_id, condition_id):
    cov = _condition_coverage()
    rule = cov.get(canonical_id, {}).get(condition_id)
    assert rule is not None, (
        f"{canonical_id}/{condition_id}: no pipeline condition_rule — app-only "
        f"suppression still lives in condition_thresholds.dart. Author it in "
        f"ingredient_interaction_rules.json with a content-verified source."
    )
    # Structural contract: authored rules must carry the routing axes + a source.
    assert rule.get("direction") in {"harmful", "beneficial", "neutral", "unknown"}, \
        f"{canonical_id}/{condition_id}: missing/invalid direction"
    assert rule.get("materiality") in {"presence", "dose_dependent", "unknown"}, \
        f"{canonical_id}/{condition_id}: missing/invalid materiality"
    assert rule.get("sources"), \
        f"{canonical_id}/{condition_id}: no sources — every clinical claim needs a verifiable source"
    if rule.get("materiality") == "dose_dependent":
        med = rule.get("min_effective_dose") or {}
        assert med.get("value") and med.get("unit") and med.get("source"), \
            f"{canonical_id}/{condition_id}: dose_dependent rule needs min_effective_dose{{value,unit,source}}"
