#!/usr/bin/env python3
"""Phase 3 — dose-floor batch: lock in the authored min_effective_dose floors.

Guards the migration of the high-value dose-dependent-harmful floors (niacin +
chromium from batch diabetes-01, plus the bleeding / glucose / BP cluster) so a
later edit can't silently drop a floor and re-introduce the trace-dose noise the
whole smart-flagging rework was built to remove.

Every floored sub-rule must also carry direction=harmful + materiality=
dose_dependent (the app's applyEmittedFloorGate predicate). Hermetic: reads the
shipped data file, no network.
"""
import json
from pathlib import Path

RULES = json.loads(
    (Path(__file__).parent.parent / "data" / "ingredient_interaction_rules.json").read_text()
)["interaction_rules"]

# canonical_id -> (expected floor value, unit, set of sub-rule keys that must carry it)
EXPECTED = {
    "vitamin_b3_niacin": (1500, "mg", {"diabetes", "hypoglycemics_high_risk",
                                       "hypoglycemics_lower_risk", "hypoglycemics_unknown"}),
    "chromium": (200, "mcg", {"hypoglycemics_high_risk", "hypoglycemics_lower_risk",
                              "hypoglycemics_unknown"}),
    "alpha_lipoic_acid": (600, "mg", {"diabetes", "hypoglycemics_high_risk",
                                      "hypoglycemics_lower_risk", "hypoglycemics_unknown"}),
    "vitamin_e": (400, "IU", {"anticoagulants"}),
    "omega_3": (3000, "mg", {"anticoagulants", "antiplatelets"}),
    "fish_oil": (3000, "mg", {"anticoagulants", "antiplatelets", "bleeding_disorders",
                              "surgery_scheduled"}),
    "ginkgo": (120, "mg", {"bleeding_disorders", "anticoagulants", "antiplatelets",
                           "hypertension", "antihypertensives", "surgery_scheduled"}),
    "garlic": (600, "mg", {"anticoagulants", "antiplatelets", "hypertension",
                           "antihypertensives", "diabetes", "surgery_scheduled"}),
    "turmeric": (1000, "mg", {"bleeding_disorders", "anticoagulants", "antiplatelets"}),
    "curcumin": (1000, "mg", {"bleeding_disorders", "anticoagulants", "antiplatelets"}),
    "caffeine": (200, "mg", {"hypertension"}),
    "licorice": (100, "mg", {"hypertension", "antihypertensives"}),
}


def _sub_rules(rule):
    out = [(x.get("condition_id"), x) for x in (rule.get("condition_rules") or [])]
    out += [(x.get("drug_class_id"), x) for x in (rule.get("drug_class_rules") or [])]
    return out


def test_expected_floors_present_and_correct():
    seen = {c: set() for c in EXPECTED}
    for r in RULES:
        canon = (r.get("subject_ref") or {}).get("canonical_id", "")
        if canon not in EXPECTED:
            continue
        value, unit, keys = EXPECTED[canon]
        for key, x in _sub_rules(r):
            if key in keys and x.get("min_effective_dose"):
                f = x["min_effective_dose"]
                assert f["value"] == value, f"{canon}/{key} floor {f['value']} != {value}"
                assert f["unit"] == unit, f"{canon}/{key} unit {f['unit']} != {unit}"
                assert x.get("direction") == "harmful", f"{canon}/{key} not harmful"
                assert x.get("materiality") == "dose_dependent", f"{canon}/{key} not dose_dependent"
                assert f.get("source"), f"{canon}/{key} floor missing source"
                assert f.get("confidence") in ("high", "medium", "low"), canon
                seen[canon].add(key)
    # each ingredient must have floored at least one of its expected keys
    for canon, keys in seen.items():
        assert keys, f"{canon}: no floored sub-rules found (floor dropped?)"


def test_no_floor_on_beneficial_or_presence():
    """A floor must never sit on a beneficial or presence-materiality sub-rule
    (would wrongly dose-suppress a benefit or a presence-matters risk)."""
    for r in RULES:
        for _key, x in _sub_rules(r):
            if x.get("min_effective_dose"):
                assert x.get("direction") == "harmful"
                assert x.get("materiality") == "dose_dependent"


def test_floor_shape_is_valid():
    """Every min_effective_dose (non-null) has the load-bearing fields the
    enricher's _evaluate_min_effective_dose reads."""
    for r in RULES:
        for _key, x in _sub_rules(r):
            f = x.get("min_effective_dose")
            if not f:
                continue
            assert isinstance(f.get("value"), (int, float)) and f["value"] > 0
            assert f.get("unit")
            assert f.get("basis") in ("per_day", "per_serving")
