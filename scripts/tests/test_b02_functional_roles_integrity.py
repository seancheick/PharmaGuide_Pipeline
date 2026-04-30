#!/usr/bin/env python3
"""
Batch 2 — `harmful_additives.json` entries 41-80.
Source: scripts/audits/functional_roles/batch_02/research.md
Coverage after batch 2: 71/115 = 62% populated.
"""

import json
from pathlib import Path
import pytest

DATA_PATH = Path(__file__).parent.parent / "data" / "harmful_additives.json"


@pytest.fixture(scope="module")
def by_id():
    with open(DATA_PATH, encoding="utf-8") as f:
        return {e["id"]: e for e in json.load(f)["harmful_additives"]}


EXPECTED_ROLES = {
    "ADD_HYDROGENATED_COCONUT_OIL":         ["carrier_oil"],
    "ADD_HYDROGENATED_STARCH_HYDROLYSATE":  ["sweetener_sugar_alcohol"],
    "ADD_IRON_OXIDE":                       ["colorant_natural"],
    "ADD_ISOMALTOOLIGOSACCHARIDE":          ["sweetener_natural", "prebiotic_fiber"],
    "ADD_MAGNESIUM_CITRATE_LAURATE":        ["lubricant"],
    "ADD_MAGNESIUM_LAURATE":                ["lubricant"],
    "ADD_MAGNESIUM_STEARATE":               ["lubricant", "anti_caking_agent"],
    "ADD_MALTITOL_MALITOL":                 ["sweetener_sugar_alcohol"],
    "ADD_MALTODEXTRIN":                     ["filler"],
    "ADD_MALTOL":                           ["flavor_natural", "flavor_enhancer"],
    "ADD_MALTOTAME":                        ["sweetener_artificial"],
    "ADD_METHYLPARABEN":                    ["preservative"],
    "ADD_MICROCRYSTALLINE_CELLULOSE":       ["filler", "binder"],
    "ADD_MINERAL_OIL":                      ["lubricant", "carrier_oil"],
    "ADD_MODIFIED_STARCH":                  ["filler", "binder", "thickener"],
    "ADD_MSG":                              ["flavor_enhancer"],
    "ADD_NEOTAME":                          ["sweetener_artificial"],
    "ADD_PALM_OIL":                         ["carrier_oil"],
    "ADD_PARTIALLY_HYDROGENATED_CORN_OIL":  ["carrier_oil"],
    "ADD_POLYDEXTROSE":                     ["filler"],
    "ADD_POLYETHYLENE_GLYCOL":              ["solvent", "humectant"],
    "ADD_POLYSORBATE80":                    ["emulsifier", "surfactant"],
    "ADD_POLYSORBATE_20":                   ["emulsifier", "surfactant"],
    "ADD_POLYSORBATE_40":                   ["emulsifier", "surfactant"],
    "ADD_POLYSORBATE_65":                   ["emulsifier", "surfactant"],
    "ADD_POLYVINYLPYRROLIDONE":             ["binder"],
    "ADD_POTASSIUM_BENZOATE":               ["preservative"],
    "ADD_POTASSIUM_HYDROXIDE":              ["ph_regulator", "processing_aid"],
    "ADD_POTASSIUM_NITRATE":                ["preservative"],
    "ADD_POTASSIUM_NITRITE":                ["preservative"],
    "ADD_POTASSIUM_SORBATE":                ["preservative"],
    "ADD_PROPYLENE_GLYCOL":                 ["solvent", "humectant"],
    "ADD_PROPYLPARABEN":                    ["preservative"],
    "ADD_PUREFRUIT_SELECT":                 ["sweetener_natural"],
    "ADD_RED40":                            ["colorant_artificial"],
    "ADD_SACCHARIN":                        ["sweetener_artificial"],
    "ADD_SHELLAC":                          ["coating", "glazing_agent"],
    "ADD_SILICON_DIOXIDE":                  ["anti_caking_agent", "glidant"],
}

DEFERRED_EMPTY = {
    "ADD_NICKEL":  "contaminant",
    "ADD_SENNA":   "Phase 4 move-to-actives (laxative drug)",
}


def test_batch_2_scope_complete(by_id):
    in_scope = set(EXPECTED_ROLES) | set(DEFERRED_EMPTY)
    assert len(in_scope) == 40
    missing = in_scope - set(by_id)
    assert not missing, f"missing: {missing}"


def test_batch_2_assignments(by_id):
    mismatches = [
        (eid, exp, by_id[eid].get("functional_roles"))
        for eid, exp in EXPECTED_ROLES.items()
        if by_id[eid].get("functional_roles") != exp
    ]
    assert not mismatches, f"{len(mismatches)} mismatches: " + "; ".join(
        f"{e}: want {x!r}, got {a!r}" for e, x, a in mismatches[:5]
    )


def test_batch_2_deferred_empty(by_id):
    bad = [(eid, by_id[eid].get("functional_roles"))
           for eid in DEFERRED_EMPTY
           if by_id[eid].get("functional_roles")]
    assert not bad, f"deferred entries should be []: {bad}"


def test_batch_2_coverage(by_id):
    in_scope = set(EXPECTED_ROLES) | set(DEFERRED_EMPTY)
    populated = sum(1 for e in in_scope if by_id[e].get("functional_roles"))
    assert populated == 38, f"want 38/40 populated; got {populated}"
