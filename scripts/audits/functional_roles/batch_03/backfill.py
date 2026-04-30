#!/usr/bin/env python3
"""Batch 3 — harmful_additives.json entries 81-115 (final). Idempotent."""
import argparse, json, sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[3]
DATA_PATH = SCRIPTS_DIR / "data" / "harmful_additives.json"
VOCAB_PATH = SCRIPTS_DIR / "data" / "functional_roles_vocab.json"

ASSIGNMENTS = {
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
DEFERRED_EMPTY = {"ADD_TIN", "ADD_SYNTHETIC_B_VITAMINS", "ADD_SYNTHETIC_VITAMINS", "ADD_TIME_SORB"}


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
        print(f"FATAL: missing: {missing}", file=sys.stderr); return 2
    if len(in_scope) != 35:
        print(f"FATAL: must cover 35; got {len(in_scope)}", file=sys.stderr); return 2

    changes = []
    for eid, exp in ASSIGNMENTS.items():
        if by_id[eid].get("functional_roles") != exp:
            changes.append((eid, by_id[eid].get("functional_roles"), exp))
            by_id[eid]["functional_roles"] = exp
    for eid in DEFERRED_EMPTY:
        if by_id[eid].get("functional_roles") != []:
            changes.append((eid, by_id[eid].get("functional_roles"), []))
            by_id[eid]["functional_roles"] = []

    if not changes:
        print("Batch 3 already applied — no-op."); return 0
    print(f"Batch 3 applying {len(changes)} change(s):")
    for eid, b, a in changes:
        print(f"  {eid:42} {b!r} -> {a!r}")
    if args.dry_run:
        print("[dry-run]"); return 0
    data["_metadata"]["last_updated"] = "2026-04-30"
    with open(DATA_PATH, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False); f.write("\n")
    print(f"Wrote {DATA_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
