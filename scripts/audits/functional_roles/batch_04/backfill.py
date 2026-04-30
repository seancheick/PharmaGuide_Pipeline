#!/usr/bin/env python3
"""
Batch 4 — `other_ingredients.json` mega-backfill (all 673 entries).

Drives off the deterministic `categorize.py` mapper which encodes the
clinician-locked Section 2B mapping table (CLINICIAN_REVIEW.md). Per
the user's fast-forward directive, this consolidates the original
17-batch plan into a single auditable batch — the per-entry rationale
trail is preserved in the categorize.py DIRECT_MAP / RETIRE / MOVE
sets.

Idempotent. Re-runs are no-ops once applied.

Outcomes per entry:
  - assign         → roles assigned per direct map / decomposition
  - retire         → assigned [] (label noise / descriptor)
  - move_to_actives → assigned [] (Phase 4 cleanup will physically relocate)
  - manual_review  → [] for now, with explicit per-id overrides for known cases
"""

import argparse, json, sys
from pathlib import Path

# Add categorize module path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from categorize import categorize, load_vocab_ids  # noqa: E402

SCRIPTS_DIR = Path(__file__).resolve().parents[3]
DATA_PATH = SCRIPTS_DIR / "data" / "other_ingredients.json"


# Per-id manual overrides for the 9 manual_review entries (resolved by
# inspection of the standard_name; clinician spot-check items in research.md).
ID_OVERRIDES = {
    # Colorants — per clinician Section 2A, no category-level defaulting;
    # resolved here by ingredient name (FDA color additive listing).
    "NHA_CARROT_EXTRACT_COLOR":   ["colorant_natural"],
    "NHA_FDC_BLUE_1":             ["colorant_artificial"],
    "NHA_FDC_YELLOW_10":          ["colorant_artificial"],
    "PII_NATURAL_COLORING":       ["colorant_natural"],
    "PII_SIENNA_COLOR":           ["colorant_natural"],
    "NHA_TOMATO_COLOR":           ["colorant_natural"],
    # Sweeteners — both natural pentose/disaccharide sugars
    "PII_ARABINOSE":              ["sweetener_natural"],
    "NHA_PALATINOSE":             ["sweetener_natural"],
    # Glycolipids — bioactive structural lipids; move to actives
    "NHA_GLYCOLIPIDS":            None,   # None signals "leave [] (move-to-actives)"
    # Per-id name-based override: Agar's gelling function is iconic and not
    # captured by the thickener_stabilizer category. Clinician table 3B locked.
    "NHA_AGAR":                   ["gelling_agent", "thickener", "stabilizer"],
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    vocab = load_vocab_ids()

    with open(DATA_PATH) as f:
        data = json.load(f)
    arr = data["other_ingredients"]

    counts = {"assign": 0, "retire": 0, "move_to_actives": 0, "manual_review": 0,
              "override_assign": 0, "no_change": 0}
    changes = []

    for e in arr:
        eid = e.get("id", "")
        # Per-id override takes precedence
        if eid in ID_OVERRIDES:
            override = ID_OVERRIDES[eid]
            target_roles = override if override is not None else []
            if override is not None:
                counts["override_assign"] += 1
            else:
                counts["manual_review"] += 1
            cur = e.get("functional_roles")
            if cur != target_roles:
                changes.append((eid, cur, target_roles, "override"))
                e["functional_roles"] = target_roles
            else:
                counts["no_change"] += 1
            continue

        action, roles, why = categorize(e, vocab)
        counts[action] += 1
        # Validate vocab membership of any assigned roles
        for r in roles:
            if r not in vocab:
                print(f"FATAL: {eid} got role {r!r} not in vocab", file=sys.stderr)
                return 2
        cur = e.get("functional_roles")
        if cur != roles:
            changes.append((eid, cur, roles, why))
            e["functional_roles"] = roles
        else:
            counts["no_change"] += 1

    if not changes:
        print("Batch 4 already applied — no-op."); return 0

    print(f"Batch 4 disposition over {len(arr)} entries:")
    for k in ("assign", "override_assign", "retire", "move_to_actives", "manual_review", "no_change"):
        print(f"  {k:20} {counts[k]:4d}")

    print(f"\nApplying {len(changes)} change(s)...")
    if args.verbose:
        for eid, before, after, why in changes[:30]:
            print(f"  {eid:42} {before!r} -> {after!r} ({why})")
        if len(changes) > 30:
            print(f"  ... and {len(changes)-30} more")

    if args.dry_run:
        print(f"[dry-run] would write {DATA_PATH}"); return 0

    data["_metadata"]["last_updated"] = "2026-04-30"
    with open(DATA_PATH, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False); f.write("\n")
    print(f"\nWrote {DATA_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
