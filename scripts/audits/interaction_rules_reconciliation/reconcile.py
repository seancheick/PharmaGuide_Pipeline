#!/usr/bin/env python3
"""Reconciliation audit — the delete-gate for condition_thresholds.dart.

Maps every dose-suppression (`aboveDose`) entry in the app's hand-authored
`condition_thresholds.dart` to a pipeline rule in `ingredient_interaction_rules.json`,
classifying each as:
  COVERED  — a pipeline condition_rule owns (canonical_id, condition_id).
  RETIRED  — deliberately not migrated (verified: the app over-warns). OK to drop.
  MISSING  — app-only suppression with no pipeline rule. BLOCKS the table delete.

Exit non-zero if any MISSING remain. When this passes (0 MISSING), every clinically
retained app suppression is represented in the pipeline, so `condition_thresholds.dart`
can be deleted after a rebuild confirms end-to-end emission.

Usage: python3 reconcile.py [--app-table PATH]
"""
import argparse
import json
import re
import sys
from pathlib import Path

RULES = Path(__file__).resolve().parents[2] / "data" / "ingredient_interaction_rules.json"
DEFAULT_APP_TABLE = Path("/Users/seancheick/PharmaGuide ai/lib/services/warnings/condition_thresholds.dart")

# app-table ingredient key -> pipeline canonical_id(s). A value may be a SET when
# the app's single key maps to a family of pipeline canonicals (omega-3 fractions).
CANONICAL = {
    "vitamin_b6": "vitamin_b6_pyridoxine",
    "retinol": "vitamin_a",           # preformed form of vitamin_a
    "niacin": "vitamin_b3_niacin",
    "vanadium": "vanadyl_sulfate",
    "omega_3": {"omega_3", "fish_oil", "epa", "dha"},
    "fish_oil": {"fish_oil", "omega_3", "epa", "dha"},
}

# (canonical_id, condition_id) deliberately RETIRED — verified the app over-warns.
RETIRED = {
    ("vitamin_d", "kidney_disease"),
    ("zinc", "kidney_disease"),
}


def app_suppressions(path):
    """Extract (condition_id, ingredient_key) for every aboveDose entry."""
    src = path.read_text()
    out = []
    cur = None
    for line in src.splitlines():
        hc = re.match(r"^  '([a-z_]+)':\s*\{\s*$", line)
        if hc:
            cur = hc.group(1)
            continue
        he = re.match(r"^\s*'([a-z0-9_]+)':\s*ConditionThreshold\.aboveDose\b", line)
        if he and cur:
            out.append((cur, he.group(1)))
    return out


def rule_coverage():
    """(canonical_id, condition_id) pairs owned by a pipeline rule — via a
    condition_rule OR a condition-scoped dose_threshold (both reach the app)."""
    rules = json.loads(RULES.read_text())["interaction_rules"]
    cov = set()
    for r in rules:
        cid = (r.get("subject_ref") or {}).get("canonical_id")
        if not cid:
            continue
        for cr in r.get("condition_rules") or []:
            if cr.get("condition_id"):
                cov.add((cid, cr["condition_id"]))
        for dt in r.get("dose_thresholds") or []:
            if dt.get("scope") == "condition" and dt.get("target_id"):
                cov.add((cid, dt["target_id"]))
    return cov


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--app-table", type=Path, default=DEFAULT_APP_TABLE)
    args = ap.parse_args()

    if not args.app_table.exists():
        print(f"app table not found: {args.app_table}")
        sys.exit(2)

    cov = rule_coverage()
    covered, retired, missing = [], [], []
    for cond, ing in app_suppressions(args.app_table):
        canon = CANONICAL.get(ing, ing)
        canons = canon if isinstance(canon, set) else {canon}
        if any((c, cond) in RETIRED for c in canons):
            retired.append((cond, ing))
        elif any((c, cond) in cov for c in canons):
            covered.append((cond, ing))
        else:
            missing.append((cond, ing, sorted(canons)))

    print(f"app aboveDose suppressions: {len(covered) + len(retired) + len(missing)}")
    print(f"  COVERED by pipeline rule : {len(covered)}")
    print(f"  RETIRED (drop app entry) : {len(retired)}  {sorted(set((c, i) for c, i in retired))}")
    print(f"  MISSING (app-only, BLOCKS): {len(missing)}")
    for cond, ing, canon in missing:
        print(f"      {cond} / {ing}  (looked up canonical '{canon}')")

    if missing:
        print("\nGATE: RED — condition_thresholds.dart is NOT deletable (app-only suppressions remain).")
        sys.exit(1)
    print("\nGATE: GREEN — every retained app suppression is owned by a pipeline rule.")
    print("Delete condition_thresholds.dart only after a rebuild confirms end-to-end emission.")


if __name__ == "__main__":
    main()
