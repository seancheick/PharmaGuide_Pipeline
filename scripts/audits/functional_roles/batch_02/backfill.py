#!/usr/bin/env python3
"""Batch 2 — harmful_additives.json entries 41-80. Idempotent."""
import argparse, json, sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[3]
DATA_PATH = SCRIPTS_DIR / "data" / "harmful_additives.json"
VOCAB_PATH = SCRIPTS_DIR / "data" / "functional_roles_vocab.json"

ASSIGNMENTS = {
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
DEFERRED_EMPTY = {"ADD_NICKEL", "ADD_SENNA"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    with open(VOCAB_PATH) as f:
        vocab = {r["id"] for r in json.load(f)["functional_roles"]}
    bad = [(e, r) for e, rr in ASSIGNMENTS.items() for r in rr if r not in vocab]
    if bad:
        print(f"FATAL: roles not in vocab: {bad}", file=sys.stderr); return 2

    with open(DATA_PATH) as f:
        data = json.load(f)
    by_id = {e["id"]: e for e in data["harmful_additives"]}

    in_scope = set(ASSIGNMENTS) | DEFERRED_EMPTY
    missing = in_scope - set(by_id)
    if missing:
        print(f"FATAL: entries missing: {missing}", file=sys.stderr); return 2
    if len(in_scope) != 40:
        print(f"FATAL: must cover 40 entries; got {len(in_scope)}", file=sys.stderr); return 2

    changes = []
    for eid, expected in ASSIGNMENTS.items():
        if by_id[eid].get("functional_roles") != expected:
            changes.append((eid, by_id[eid].get("functional_roles"), expected))
            by_id[eid]["functional_roles"] = expected
    for eid in DEFERRED_EMPTY:
        if by_id[eid].get("functional_roles") != []:
            changes.append((eid, by_id[eid].get("functional_roles"), []))
            by_id[eid]["functional_roles"] = []

    if not changes:
        print("Batch 2 already applied — no-op."); return 0

    print(f"Batch 2 applying {len(changes)} change(s):")
    for eid, before, after in changes:
        print(f"  {eid:42} {before!r} -> {after!r}")
    if args.dry_run:
        print(f"[dry-run] would write {DATA_PATH}"); return 0

    data["_metadata"]["last_updated"] = "2026-04-30"
    with open(DATA_PATH, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False); f.write("\n")
    print(f"Wrote {DATA_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
