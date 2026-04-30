#!/usr/bin/env python3
"""
Batch 5 — `botanical_ingredients.json` (all 459 entries).

Per clinician guidance: botanicals are ACTIVES, not excipients. The
botanical_ingredients.json file is the active-side ingredient-identification
reference (root/herb/fruit/leaf/seed/bark/mushroom plant-part categories) —
none of those are functional roles in the FDA 21 CFR 170.3(o) sense.

V1 disposition: bulk-assign `functional_roles=[]` to all 459 entries. The
rare per-product formulation-context cases (turmeric as colorant, vanilla as
flavoring, etc.) are handled at the product-blob level via the
other_ingredients.json mapping when the ingredient appears as an inactive.

Rationale documented in research.md. Idempotent.
"""

import argparse, json, sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[3]
DATA_PATH = SCRIPTS_DIR / "data" / "botanical_ingredients.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    with open(DATA_PATH) as f:
        data = json.load(f)
    arr = data["botanical_ingredients"]

    changes = 0
    for e in arr:
        if e.get("functional_roles") != []:
            e["functional_roles"] = []
            changes += 1

    if not changes:
        print(f"Batch 5 already applied — no-op. (botanical_ingredients: {len(arr)})")
        return 0

    print(f"Batch 5 assigning functional_roles=[] to {changes}/{len(arr)} botanical entries")
    print("Rationale: botanicals are actives, not excipients. Per-product")
    print("formulation-context roles (turmeric-as-colorant) are handled via")
    print("other_ingredients.json mappings when applicable.")

    if args.dry_run:
        print(f"\n[dry-run] would write {DATA_PATH}")
        return 0

    data["_metadata"]["last_updated"] = "2026-04-30"
    with open(DATA_PATH, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"\nWrote {DATA_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
