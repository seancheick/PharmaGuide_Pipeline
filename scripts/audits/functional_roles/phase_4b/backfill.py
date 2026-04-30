#!/usr/bin/env python3
"""
Phase 4b — harmful_additives.json category canonicalization.

Per CLINICIAN_REVIEW.md Section 2A: collapse 21 distinct category values
to 12 canonical safety-taxonomy values. The granular functional info now
lives in `functional_roles[]` (Phase 3 backfill); `category` is reduced
to a coarse safety bucket.

Canonical 12 values per clinician:
  excipient, preservative, emulsifier, colorant_artificial,
  colorant_natural, sweetener_artificial, sweetener_natural,
  sweetener_sugar_alcohol, filler, contaminant, processing_aid, phosphate

Renames applied (22 entries):
  artificial_color (1)         → colorant_artificial
  fat_oil (5)                  → excipient   (carrier_oil role in functional_roles[])
  flavor (4)                   → excipient   (flavor_natural/artificial/enhancer in functional_roles[])
  preservative_antioxidant (4) → preservative (antioxidant role in functional_roles[])
  sweetener (8)                → sweetener_natural (all are natural-source)

V1 transitional holdouts (Phase 4c migration targets, not renamed yet):
  mineral_compound (1)   — Cupric Sulfate moves to actives Phase 4c
  nutrient_synthetic (2) — Synthetic B Vitamins / Synthetic Vitamins move to actives
  stimulant_laxative (1) — Senna moves to actives

Idempotent. No scoring impact (functional_roles is the structural dimension).
"""

import argparse, json, sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[3]
DATA_PATH = SCRIPTS_DIR / "data" / "harmful_additives.json"

CATEGORY_RENAME = {
    "artificial_color":         "colorant_artificial",
    "fat_oil":                  "excipient",
    "flavor":                   "excipient",
    "preservative_antioxidant": "preservative",
    "sweetener":                "sweetener_natural",
}

# Per-id overrides — clinician Section 2A: colorant (2) "REVIEW PER ENTRY,
# no category-level defaulting".
ID_CATEGORY_OVERRIDES = {
    "ADD_IRON_OXIDE":      "colorant_natural",   # mineral source, FDA 21 CFR 73.200
    "ADD_CANDURIN_SILVER": "excipient",          # brand covers multiple formulations;
                                                  # per-product verification deferred to V1.1
}

CANONICAL_VALUES = {
    "excipient", "preservative", "emulsifier",
    "colorant_artificial", "colorant_natural",
    "sweetener_artificial", "sweetener_natural", "sweetener_sugar_alcohol",
    "filler", "contaminant", "processing_aid", "phosphate",
    # V1 transitional (Phase 4c migration targets)
    "mineral_compound", "nutrient_synthetic", "stimulant_laxative",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    with open(DATA_PATH) as f:
        data = json.load(f)
    arr = data["harmful_additives"]

    changes = []
    for e in arr:
        eid = e.get("id", "")
        cur = e.get("category", "")
        # Per-id override takes precedence over category-level rename
        if eid in ID_CATEGORY_OVERRIDES:
            new = ID_CATEGORY_OVERRIDES[eid]
            if new != cur:
                changes.append((eid, cur, new))
                e["category"] = new
        elif cur in CATEGORY_RENAME:
            new = CATEGORY_RENAME[cur]
            changes.append((eid, cur, new))
            e["category"] = new

    # Validate post-rename: every entry's category in CANONICAL_VALUES
    invalid = []
    for e in arr:
        if e.get("category") not in CANONICAL_VALUES:
            invalid.append((e.get("id"), e.get("category")))
    if invalid:
        print(f"FATAL: {len(invalid)} entries have non-canonical category after "
              f"rename: {invalid[:10]}", file=sys.stderr)
        return 2

    if not changes:
        print("Phase 4b already applied — no-op.")
        return 0

    print(f"Phase 4b applying {len(changes)} category renames:")
    by_old = {}
    for eid, old, new in changes:
        by_old.setdefault(old, []).append(new)
    for old, news in sorted(by_old.items()):
        from collections import Counter
        c = Counter(news)
        for new, n in c.most_common():
            print(f"  {old:30} → {new:30} ({n})")

    if args.dry_run:
        print(f"\n[dry-run] would write {DATA_PATH}")
        return 0

    data["_metadata"]["last_updated"] = "2026-04-30"
    if data["_metadata"].get("schema_version") == "5.2.0":
        data["_metadata"]["schema_version"] = "5.3.0"
    if "field_contract_changes" not in data["_metadata"]:
        data["_metadata"]["field_contract_changes"] = {}
    data["_metadata"]["field_contract_changes"]["v5.3.0"] = (
        "2026-04-30 Phase 4b — category canonicalization. Renamed 21 → 12 "
        "canonical safety values per CLINICIAN_REVIEW.md Section 2A. Granular "
        "functional info now lives in functional_roles[]. Renames: "
        "artificial_color→colorant_artificial; fat_oil→excipient; flavor→"
        "excipient; preservative_antioxidant→preservative; sweetener→"
        "sweetener_natural. Transitional holdouts (Phase 4c): mineral_compound, "
        "nutrient_synthetic, stimulant_laxative."
    )

    with open(DATA_PATH, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"\nWrote {DATA_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
