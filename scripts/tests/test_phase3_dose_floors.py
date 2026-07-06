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
    # glucose batch
    "berberine_supplement": (500, "mg", {"diabetes", "hypoglycemics_high_risk"}),
    "gymnema_sylvestre": (400, "mg", {"diabetes"}),
    "fenugreek": (500, "mg", {"diabetes"}),
    "bitter_melon": (600, "mg", {"diabetes"}),
    "white_mulberry": (125, "mg", {"diabetes"}),
    "psyllium": (3000, "mg", {"hypoglycemics_high_risk"}),
    # bleeding batch
    "feverfew": (100, "mg", {"bleeding_disorders", "anticoagulants"}),
    "quercetin": (150, "mg", {"anticoagulants"}),
    "saw_palmetto": (320, "mg", {"anticoagulants"}),
    "glucosamine": (1500, "mg", {"anticoagulants"}),
    "white_willow_bark": (120, "mg", {"bleeding_disorders"}),
    # BP batch
    "hawthorn": (160, "mg", {"hypertension"}),
    "l_arginine": (4000, "mg", {"antihypertensives"}),
    "black_seed_oil": (2000, "mg", {"diabetes", "hypertension"}),
    "st_johns_wort": (900, "mg", {"antihypertensives"}),
    # vitamin D high-dose-only
    "vitamin_d": (10000, "IU", {"anticoagulants"}),
    # thyroid mineral dose gates moved from the retired Flutter threshold table
    # into emitted pipeline floors.
    "iodine": (150, "mcg", {"thyroid_disorder"}),
    "selenium": (400, "mcg", {"thyroid_disorder"}),
}

# (canonical, sub-rule) that MUST be beneficial (routed to support, never floored)
# NB: (inositol, diabetes) was beneficial in the Phase-3 batch but was retagged
# `neutral` after an adversarial clinical review (2026-07-02): inositol's glucose
# benefit for diabetics is weakly evidenced (PCOS extrapolation) and it has no
# hypoglycemics drug backstop, so a green "supports glucose control" bullet could
# mask additive hypoglycemia. Its copy already carries the additive-lowering
# caution, which the neutral (good-to-know) surface preserves.
BENEFICIAL_EXPECTED = {
    ("magnesium", "hypertension"), ("magnesium", "diabetes"),
    ("vitamin_d", "diabetes"), ("inositol", "ttc"),
    ("chromium", "diabetes"),
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


def test_beneficial_ingredients_reclassified_not_floored():
    """Beneficial nutrients (magnesium/inositol/vitamin-D for their conditions)
    must be direction=beneficial and carry NO floor — flooring them as harmful
    would re-introduce the benefit-as-warning false positive."""
    found = set()
    for r in RULES:
        canon = (r.get("subject_ref") or {}).get("canonical_id", "")
        for key, x in _sub_rules(r):
            if (canon, key) in BENEFICIAL_EXPECTED:
                assert x.get("direction") == "beneficial", f"{canon}/{key} not beneficial"
                assert not x.get("min_effective_dose"), f"{canon}/{key} beneficial rule wrongly floored"
                found.add((canon, key))
    assert found == BENEFICIAL_EXPECTED, f"missing beneficial reclassifications: {BENEFICIAL_EXPECTED - found}"


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
