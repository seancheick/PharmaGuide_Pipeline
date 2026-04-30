#!/usr/bin/env python3
"""Batch 3 — harmful_additives 81-115 (final). Coverage 89% after batch 3."""

import json
from pathlib import Path
import pytest

DATA_PATH = Path(__file__).parent.parent / "data" / "harmful_additives.json"


@pytest.fixture(scope="module")
def by_id():
    with open(DATA_PATH, encoding="utf-8") as f:
        return {e["id"]: e for e in json.load(f)["harmful_additives"]}


EXPECTED_ROLES = {
    "ADD_SLIMSWEET":                 ["sweetener_natural"],
    "ADD_SODIUM_ALUMINUM_PHOSPHATE": ["ph_regulator", "processing_aid"],
    "ADD_SODIUM_BENZOATE":           ["preservative"],
    "ADD_SODIUM_CASEINATE":          ["emulsifier", "stabilizer"],
    "ADD_SODIUM_COPPER_CHLOROPHYLLIN": ["colorant_natural"],
    "ADD_SODIUM_HEXAMETAPHOSPHATE":  ["emulsifier", "ph_regulator"],
    "ADD_SODIUM_LAURYL_SULFATE":     ["emulsifier", "surfactant"],
    "ADD_SODIUM_METABISULFITE":      ["preservative", "antioxidant"],
    "ADD_SODIUM_NITRATE":            ["preservative"],
    "ADD_SODIUM_NITRITE":            ["preservative"],
    "ADD_SODIUM_SULFITE":            ["preservative", "antioxidant"],
    "ADD_SODIUM_TRIPOLYPHOSPHATE":   ["ph_regulator"],
    "ADD_SORBIC_ACID":               ["preservative"],
    "ADD_SORBITAN_MONOSTEARATE":     ["emulsifier", "surfactant"],
    "ADD_SORBITOL":                  ["sweetener_sugar_alcohol", "humectant"],
    "ADD_SOY_MONOGLYCERIDES":        ["emulsifier"],
    "ADD_STEARIC_ACID":              ["lubricant"],
    "ADD_SUCRALOSE":                 ["sweetener_artificial"],
    "ADD_SUGAR_ALCOHOLS":            ["sweetener_sugar_alcohol"],
    "ADD_SULFUR_DIOXIDE":            ["preservative", "antioxidant"],
    "ADD_SYNTHETIC_ANTIOXIDANTS":    ["preservative", "antioxidant"],
    "ADD_SYRUPS":                    ["sweetener_natural"],
    "ADD_TAPIOCA_FILLER":            ["filler"],
    "ADD_TBHQ":                      ["preservative", "antioxidant"],
    "ADD_TETRASODIUM_DIPHOSPHATE":   ["ph_regulator"],
    "ADD_THAUMATIN":                 ["sweetener_natural"],
    "ADD_UNSPECIFIED_COLORS":        ["colorant_artificial"],
    "ADD_VANILLIN":                  ["flavor_artificial"],
    "ADD_XYLITOL":                   ["sweetener_sugar_alcohol"],
    "ADD_YELLOW5":                   ["colorant_artificial"],
    "ADD_YELLOW6":                   ["colorant_artificial"],
}

DEFERRED_EMPTY = {
    "ADD_TIN":                  "contaminant",
    "ADD_SYNTHETIC_B_VITAMINS": "Phase 4 actives (active-form quality → IQ /25)",
    "ADD_SYNTHETIC_VITAMINS":   "Phase 4 actives",
    "ADD_TIME_SORB":            "V1.1 per-product verification (branded sustained-release excipient)",
}


def test_batch_3_scope_complete(by_id):
    in_scope = set(EXPECTED_ROLES) | set(DEFERRED_EMPTY)
    assert len(in_scope) == 35
    missing = in_scope - set(by_id)
    assert not missing, f"missing: {missing}"


def test_batch_3_assignments(by_id):
    bad = [(eid, exp, by_id[eid].get("functional_roles"))
           for eid, exp in EXPECTED_ROLES.items()
           if by_id[eid].get("functional_roles") != exp]
    assert not bad, f"{len(bad)} mismatches: " + "; ".join(
        f"{e}: want {x!r} got {a!r}" for e, x, a in bad[:5])


def test_batch_3_deferred_empty(by_id):
    bad = [(e, by_id[e].get("functional_roles"))
           for e in DEFERRED_EMPTY
           if by_id[e].get("functional_roles")]
    assert not bad


def test_harmful_additives_total_coverage_after_batch_3(by_id):
    """After batch 3, harmful_additives is at 103/116 populated.
    +1 from ADD_TYRAMINE_RICH_EXTRACT (added 2026-04-30 to support M2
    interaction rule); the new entry carries functional_roles=["preservative"].
    """
    populated = sum(1 for e in by_id.values() if e.get("functional_roles"))
    assert populated == 103, (
        f"expected 103/116 populated after batch 3 + tyramine entry; got {populated}"
    )
