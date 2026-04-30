#!/usr/bin/env python3
"""
Batch 1 backfill — `harmful_additives.json` entries 1-40 (alphabetical by id).

Idempotent applier. Re-runs are no-ops once the data file matches the
clinician-locked assignments (it diffs first; only writes when needed).

Source of truth: scripts/audits/functional_roles/batch_01/research.md
Clinician sign-off: scripts/audits/functional_roles/CLINICIAN_REVIEW.md (2026-04-30)

Validation gates:
  - Every assigned role must be in functional_roles_vocab.json v1.0.0 (32 IDs)
  - Contaminants and Phase 4 / V1.1-deferred entries stay []
  - Test test_b01_functional_roles_integrity.py must pass after run

Usage:
    python3 scripts/audits/functional_roles/batch_01/backfill.py
    python3 scripts/audits/functional_roles/batch_01/backfill.py --dry-run
"""

import argparse
import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[3]  # scripts/
DATA_PATH = SCRIPTS_DIR / "data" / "harmful_additives.json"
VOCAB_PATH = SCRIPTS_DIR / "data" / "functional_roles_vocab.json"


# ---------------------------------------------------------------------------
# Clinician-locked assignments — keep in sync with
# scripts/tests/test_b01_functional_roles_integrity.py
# ---------------------------------------------------------------------------

ASSIGNMENTS = {
    # Sweeteners — artificial
    "ADD_ACESULFAME_K":               ["sweetener_artificial"],
    "ADD_ADVANTAME":                  ["sweetener_artificial"],
    "ADD_ASPARTAME":                  ["sweetener_artificial"],
    # Sweeteners — natural / nutritive
    "ADD_CANE_SUGAR":                 ["sweetener_natural"],
    "ADD_CANE_MOLASSES":              ["sweetener_natural", "flavor_natural", "colorant_natural"],
    "ADD_DEXTROSE":                   ["sweetener_natural"],
    "ADD_FRUCTOSE":                   ["sweetener_natural"],
    "ADD_HFCS":                       ["sweetener_natural"],
    "ADD_D_MANNOSE":                  ["sweetener_natural"],
    # Sugar alcohol
    "ADD_ERYTHRITOL":                 ["sweetener_sugar_alcohol"],
    # Colorants — artificial
    "ADD_BLUE1":                      ["colorant_artificial"],
    "ADD_BLUE2":                      ["colorant_artificial"],
    "ADD_GREEN3":                     ["colorant_artificial"],
    "ADD_ALUMINUM_LAKE_GENERIC":      ["colorant_artificial"],
    # Colorants — natural
    "ADD_CARMINE_RED":                ["colorant_natural"],
    # Preservatives + antioxidants
    "ADD_BHA":                        ["preservative", "antioxidant"],
    "ADD_BHT":                        ["preservative", "antioxidant"],
    "ADD_CALCIUM_DISODIUM_EDTA":      ["preservative", "antioxidant"],
    "ADD_DISODIUM_EDTA":              ["preservative", "antioxidant"],
    # Emulsifiers / multi-role hydrocolloids
    "ADD_CARBOXYMETHYLCELLULOSE":     ["emulsifier", "thickener", "stabilizer"],
    "ADD_CARRAGEENAN":                ["emulsifier", "thickener", "gelling_agent", "stabilizer"],
    "ADD_FATTY_ACID_POLYGLYCEROL_ESTERS": ["emulsifier", "surfactant"],
    # Carrier oils (fat_oil → carrier_oil per clinician)
    "ADD_CANOLA_OIL":                 ["carrier_oil"],
    "ADD_CORN_OIL":                   ["carrier_oil"],
    # Disintegrants
    "ADD_CROSCARMELLOSE_SODIUM":      ["disintegrant"],
    "ADD_CROSPOVIDONE":               ["disintegrant"],
    # Lubricants / flow agents
    "ADD_CALCIUM_LAURATE":            ["lubricant"],
    "ADD_CALCIUM_CITRATE_LAURATE":    ["lubricant"],
    "ADD_CALCIUM_SILICATE":           ["anti_caking_agent", "glidant"],
    "ADD_CALCIUM_ALUMINUM_PHOSPHATE": ["processing_aid", "anti_caking_agent"],
    # Fillers
    "ADD_CASSAVA_DEXTRIN":            ["filler"],
    "ADD_CORN_SYRUP_SOLIDS":          ["filler", "sweetener_natural"],
    # Flavorings
    "ADD_ARTIFICIAL_FLAVORS":         ["flavor_artificial"],
}

# Entries that must stay [] — contaminants + V1.1-deferred + Phase-4-deferred.
# These are explicitly assigned [] (not just left missing) so re-runs of this
# backfill don't accidentally overwrite an entry's existing roles with [].
DEFERRED_EMPTY = {
    "ADD_ACRYLAMIDE",
    "ADD_ANTIMONY",
    "ADD_BISPHENOL_F",
    "ADD_BISPHENOL_S",
    "ADD_CARAMEL_COLOR",
    "ADD_CANDURIN_SILVER",
    "ADD_CUPRIC_SULFATE",
}


def _load_vocab_ids() -> set:
    with open(VOCAB_PATH, encoding="utf-8") as f:
        return {r["id"] for r in json.load(f)["functional_roles"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview the diff without writing the data file.",
    )
    args = parser.parse_args()

    vocab_ids = _load_vocab_ids()
    # Validate all proposed roles are in vocab BEFORE touching data
    bad = []
    for eid, roles in ASSIGNMENTS.items():
        for r in roles:
            if r not in vocab_ids:
                bad.append((eid, r))
    if bad:
        print(f"FATAL: {len(bad)} role IDs are not in vocab v1.0.0: {bad}", file=sys.stderr)
        return 2

    with open(DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)

    by_id = {e["id"]: e for e in data["harmful_additives"]}

    # Confirm every batch entry exists
    in_scope = set(ASSIGNMENTS) | DEFERRED_EMPTY
    missing = in_scope - set(by_id)
    if missing:
        print(f"FATAL: batch 1 entries missing from data file: {missing}", file=sys.stderr)
        return 2
    if len(in_scope) != 40:
        print(f"FATAL: batch 1 must cover exactly 40 entries; got {len(in_scope)}", file=sys.stderr)
        return 2

    changes = []
    for eid, expected in ASSIGNMENTS.items():
        cur = by_id[eid].get("functional_roles", None)
        if cur != expected:
            changes.append((eid, cur, expected))
            by_id[eid]["functional_roles"] = expected

    for eid in DEFERRED_EMPTY:
        cur = by_id[eid].get("functional_roles", None)
        if cur != []:
            changes.append((eid, cur, []))
            by_id[eid]["functional_roles"] = []

    if not changes:
        print("Batch 1 already applied — no changes needed (idempotent re-run).")
        return 0

    print(f"Batch 1 applying {len(changes)} change(s):")
    for eid, before, after in changes[:60]:
        print(f"  {eid:36} {before!r} -> {after!r}")

    if args.dry_run:
        print(f"\n[dry-run] would write {DATA_PATH}")
        return 0

    # Bump _metadata.last_updated to today
    data["_metadata"]["last_updated"] = "2026-04-30"

    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"\nWrote {DATA_PATH}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
