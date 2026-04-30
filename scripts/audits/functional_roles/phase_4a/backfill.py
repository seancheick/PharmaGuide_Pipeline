#!/usr/bin/env python3
"""
Phase 4a — flag retire + move-to-actives entries in other_ingredients.json.

Drives off the deterministic categorize.py mapper (same source of truth as
batch_04). Adds two boolean flags to entries based on their category-class:

  - is_label_descriptor: true  → retire-class (label noise; should not
    render in Flutter inactive_ingredients[] chips)
  - is_active_only: true       → move-to-actives class (will physically
    relocate to active-ingredient pipeline in V1.1; meanwhile suppress
    from inactive_ingredients[] rendering)

These are ADDITIVE flags — the underlying entries stay in the data file
for ingredient resolution by the cleaner/enricher. Only Flutter blob
rendering is suppressed.

Phase 4b (next): category canonicalization (rename 241 → ~30 values).
Phase 4c (deferred): physical removal of additive_type field — requires
migrating ADDITIVE_TYPES_SKIP_SCORING to FUNCTIONAL_ROLES equivalent.

Idempotent.
"""

import argparse, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from categorize import categorize, load_vocab_ids  # noqa: E402

SCRIPTS_DIR = Path(__file__).resolve().parents[3]
DATA_PATH = SCRIPTS_DIR / "data" / "other_ingredients.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    vocab = load_vocab_ids()
    with open(DATA_PATH) as f:
        data = json.load(f)
    arr = data["other_ingredients"]

    changes = {"label_descriptor": 0, "active_only": 0, "cleared": 0}
    for e in arr:
        action, _, _ = categorize(e, vocab)
        # Determine target flag state
        target_label = (action == "retire")
        target_active = (action == "move_to_actives")

        cur_label = bool(e.get("is_label_descriptor", False))
        cur_active = bool(e.get("is_active_only", False))

        if target_label != cur_label:
            if target_label:
                e["is_label_descriptor"] = True
                changes["label_descriptor"] += 1
            else:
                e.pop("is_label_descriptor", None)
                changes["cleared"] += 1

        if target_active != cur_active:
            if target_active:
                e["is_active_only"] = True
                changes["active_only"] += 1
            else:
                e.pop("is_active_only", None)
                changes["cleared"] += 1

    total = sum(changes.values())
    if total == 0:
        print("Phase 4a already applied — no-op.")
        return 0

    print(f"Phase 4a applying flags to other_ingredients.json:")
    print(f"  is_label_descriptor=true: {changes['label_descriptor']} entries")
    print(f"  is_active_only=true:      {changes['active_only']} entries")
    if changes['cleared']:
        print(f"  cleared (re-categorized): {changes['cleared']} entries")

    if args.dry_run:
        print(f"\n[dry-run] would write {DATA_PATH}")
        return 0

    data["_metadata"]["last_updated"] = "2026-04-30"
    # Bump schema_version to record the flag addition
    if data["_metadata"]["schema_version"] == "5.1.0":
        data["_metadata"]["schema_version"] = "5.2.0"
        # Note: vocab + integrity gate are unchanged; this is purely additive
        if "field_contract_additions" not in data["_metadata"]:
            data["_metadata"]["field_contract_additions"] = {}
        data["_metadata"]["field_contract_additions"]["v5.2.0"] = {
            "is_label_descriptor": "Phase 4a flag (2026-04-30): true on label-noise entries (marketing_descriptor / phytochemical_marker / source_descriptor / etc.). Suppressed from Flutter inactive_ingredients[] blob.",
            "is_active_only": "Phase 4a flag (2026-04-30): true on entries that will relocate to the active-ingredient pipeline in V1.1 (botanical_extract, glandular_tissue, branded complexes, amino_acid_derivative, phytocannabinoids, marine extracts). Suppressed from inactive_ingredients[].",
        }

    with open(DATA_PATH, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"\nWrote {DATA_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
