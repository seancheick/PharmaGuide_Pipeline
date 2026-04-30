#!/usr/bin/env python3
"""
Phase 4c — other_ingredients.json category canonicalization (241 → ~30).

Per CLINICIAN_REVIEW.md Section 2B + the deterministic categorize.py
mapper outcomes from Phase 3 batch_04.

Canonical category mapping derived from action type:
  - assign action  → primary functional_role (first in the list)
  - retire action  → "label_descriptor"
  - move_to_actives → "active_pending_relocation"
  - manual_review  → "manual_review"

Net effect: 241 distinct values collapse to a small canonical set
matching the 32-role vocab + 3 transitional buckets. Internal hygiene
cleanup — no Flutter impact (Flutter reads functional_roles[], not
category, on inactive_ingredients[] rows).

Idempotent.
"""

import argparse, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from categorize import categorize, load_vocab_ids  # noqa: E402

SCRIPTS_DIR = Path(__file__).resolve().parents[3]
DATA_PATH = SCRIPTS_DIR / "data" / "other_ingredients.json"

# Special non-vocab transitional category values
RETIRE_CATEGORY = "label_descriptor"
MOVE_TO_ACTIVES_CATEGORY = "active_pending_relocation"
MANUAL_REVIEW_CATEGORY = "manual_review"

ALL_CANONICAL_VALUES_SUFFIX = {
    RETIRE_CATEGORY,
    MOVE_TO_ACTIVES_CATEGORY,
    MANUAL_REVIEW_CATEGORY,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    vocab = load_vocab_ids()
    with open(DATA_PATH) as f:
        data = json.load(f)
    arr = data["other_ingredients"]

    changes = []
    for e in arr:
        eid = e.get("id", "")
        cur = e.get("category", "")
        action, roles, _ = categorize(e, vocab)

        if action == "retire":
            new = RETIRE_CATEGORY
        elif action == "move_to_actives":
            new = MOVE_TO_ACTIVES_CATEGORY
        elif action == "manual_review":
            new = MANUAL_REVIEW_CATEGORY
        elif action == "assign" and roles:
            new = roles[0]
        else:
            # action == "assign" with empty roles (shouldn't happen post Phase 3
            # since empty-list categories were moved to RETIRE) — fallback
            new = MANUAL_REVIEW_CATEGORY

        # Per-id overrides matching batch_04 backfill — keep category in sync
        # with the per-id functional_roles override
        ID_OVERRIDES = {
            "NHA_AGAR":                    "gelling_agent",
            "NHA_CARROT_EXTRACT_COLOR":    "colorant_natural",
            "NHA_FDC_BLUE_1":              "colorant_artificial",
            "NHA_FDC_YELLOW_10":           "colorant_artificial",
            "PII_NATURAL_COLORING":        "colorant_natural",
            "PII_SIENNA_COLOR":            "colorant_natural",
            "NHA_TOMATO_COLOR":            "colorant_natural",
            "PII_ARABINOSE":               "sweetener_natural",
            "NHA_PALATINOSE":              "sweetener_natural",
            "NHA_GLYCOLIPIDS":             MANUAL_REVIEW_CATEGORY,
        }
        if eid in ID_OVERRIDES:
            new = ID_OVERRIDES[eid]

        if new != cur:
            changes.append((eid, cur, new))
            e["category"] = new

    # Validate post-rename: every category is either a vocab role ID or
    # one of the transitional values
    invalid = []
    for e in arr:
        cat = e.get("category", "")
        if cat not in vocab and cat not in ALL_CANONICAL_VALUES_SUFFIX:
            invalid.append((e.get("id"), cat))
    if invalid:
        print(f"FATAL: {len(invalid)} non-canonical categories: {invalid[:10]}",
              file=sys.stderr)
        return 2

    if not changes:
        print("Phase 4c already applied — no-op.")
        return 0

    from collections import Counter
    summary = Counter(new for _, _, new in changes)
    print(f"Phase 4c renaming category on {len(changes)} entries:")
    print(f"\nNew category distribution (post-rename):")
    new_dist = Counter(e.get("category") for e in arr)
    for c, n in new_dist.most_common():
        print(f"  {n:3d}  {c}")
    print(f"\nDistinct categories: {len(new_dist)} (was 241)")

    if args.dry_run:
        print(f"\n[dry-run] would write {DATA_PATH}")
        return 0

    data["_metadata"]["last_updated"] = "2026-04-30"
    if data["_metadata"].get("schema_version") == "5.2.0":
        data["_metadata"]["schema_version"] = "5.3.0"
    if "field_contract_changes" not in data["_metadata"]:
        data["_metadata"]["field_contract_changes"] = {}
    data["_metadata"]["field_contract_changes"]["v5.3.0"] = (
        "2026-04-30 Phase 4c — category canonicalization. Renamed 241 → ~30 "
        "values per CLINICIAN_REVIEW.md Section 2B. Each category now equals "
        "either a functional_roles vocab ID or a transitional bucket "
        "(label_descriptor / active_pending_relocation / manual_review). "
        "No Flutter impact — Flutter reads functional_roles[], not category."
    )

    with open(DATA_PATH, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"\nWrote {DATA_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
