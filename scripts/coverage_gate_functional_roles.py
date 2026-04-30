#!/usr/bin/env python3
"""
Phase 5 — Functional Roles Coverage Gate

Verifies that every entry across `harmful_additives.json`,
`other_ingredients.json`, and `botanical_ingredients.json` either:
  (a) has at least one role from the locked 32-ID vocab, OR
  (b) is in an architectural exclusion class (contaminants,
      label-descriptors, move-to-actives, V1.1-deferred, botanicals).

Architectural exclusions (allowlisted, intentional `[]`):

  harmful_additives.json:
    - category == "contaminant"       (unintended impurities, not ingredients)
    - category == "mineral_compound"  (Phase 4c → actives migration)
    - category == "nutrient_synthetic"(Phase 4c → actives)
    - category == "stimulant_laxative"(Phase 4c → actives)
    - id in V1_1_DEFERRED_HA          (caramel class, Candurin per-product, etc.)

  other_ingredients.json:
    - is_label_descriptor: true       (Phase 4a flag — label noise)
    - is_active_only: true            (Phase 4a flag — move-to-actives)
    - id in MANUAL_REVIEW_ALLOWLIST   (1 entry: NHA_GLYCOLIPIDS)

  botanical_ingredients.json:
    - All entries (architectural — botanicals are actives, not excipients)

Exit codes:
  0 — all required entries have roles; release allowed
  1 — one or more required entries are empty; release blocked
  2 — vocab file or data files unloadable

Usage:
  python3 scripts/coverage_gate_functional_roles.py
  python3 scripts/coverage_gate_functional_roles.py --verbose
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
DATA = SCRIPTS_DIR / "data"
VOCAB_PATH = DATA / "functional_roles_vocab.json"
HA_PATH = DATA / "harmful_additives.json"
OI_PATH = DATA / "other_ingredients.json"
BOT_PATH = DATA / "botanical_ingredients.json"


# ---------------------------------------------------------------------------
# Architectural allowlists — must stay tightly curated; adding entries here
# requires a clinician-signed rationale (see CLINICIAN_REVIEW.md).
# ---------------------------------------------------------------------------

# harmful_additives — V1.1 attribute-required disambiguation + Phase 4c moves
V1_1_DEFERRED_HA = {
    "ADD_CARAMEL_COLOR",   # needs attributes.caramel_class i-iv (4-MEI Prop 65)
    "ADD_CANDURIN_SILVER", # per-product source verification (multi-formulation brand)
    "ADD_TIME_SORB",       # per-product source verification (sustained-release brand)
}

HA_PHASE_4C_CATEGORIES = {
    "mineral_compound",     # Cupric Sulfate
    "nutrient_synthetic",   # Synthetic B Vitamins, Synthetic Vitamins
    "stimulant_laxative",   # Senna
}

# other_ingredients — single manual_review entry that defies categorization
MANUAL_REVIEW_ALLOWLIST = {
    "NHA_GLYCOLIPIDS",     # bioactive structural lipids; clinician judgement deferred
}


def _is_excluded_harmful(entry: dict) -> tuple[bool, str]:
    cat = entry.get("category", "")
    if cat == "contaminant":
        return True, "contaminant — unintended impurity"
    if cat in HA_PHASE_4C_CATEGORIES:
        return True, f"Phase 4c actives migration ({cat})"
    if entry.get("id") in V1_1_DEFERRED_HA:
        return True, "V1.1 attribute-layer disambiguation required"
    return False, ""


def _is_excluded_other(entry: dict) -> tuple[bool, str]:
    if entry.get("is_label_descriptor"):
        return True, "is_label_descriptor=true (label noise)"
    if entry.get("is_active_only"):
        return True, "is_active_only=true (move-to-actives)"
    if entry.get("id") in MANUAL_REVIEW_ALLOWLIST:
        return True, "manual_review allowlist (clinician judgement)"
    return False, ""


def _is_excluded_botanical(entry: dict) -> tuple[bool, str]:
    # All botanicals architecturally excluded
    return True, "botanical_ingredients architectural exclusion (actives)"


# ---------------------------------------------------------------------------
# Gate
# ---------------------------------------------------------------------------


def run_gate(verbose: bool = False) -> int:
    try:
        with open(VOCAB_PATH) as f:
            vocab_ids = {r["id"] for r in json.load(f)["functional_roles"]}
    except Exception as e:
        print(f"FATAL: vocab unloadable: {e}", file=sys.stderr)
        return 2

    files_violations: list[dict] = []
    files_summary: list[dict] = []

    for path, key, exclude_fn, label in [
        (HA_PATH,  "harmful_additives",    _is_excluded_harmful,   "harmful_additives"),
        (OI_PATH,  "other_ingredients",    _is_excluded_other,     "other_ingredients"),
        (BOT_PATH, "botanical_ingredients", _is_excluded_botanical, "botanical_ingredients"),
    ]:
        try:
            with open(path) as f:
                arr = json.load(f)[key]
        except Exception as e:
            print(f"FATAL: {label} unloadable: {e}", file=sys.stderr)
            return 2

        required_count = 0
        populated_count = 0
        excluded_count = 0
        violations = []
        invalid_roles = []

        for entry in arr:
            excluded, reason = exclude_fn(entry)
            roles = entry.get("functional_roles", [])

            # Always validate role IDs against vocab — never allow drift
            for r in roles:
                if r not in vocab_ids:
                    invalid_roles.append((entry.get("id"), r))

            if excluded:
                excluded_count += 1
                if roles and label != "botanical_ingredients":
                    # Excluded entries SHOULDN'T have roles (except botanicals
                    # which are silently excluded but allow per-product roles)
                    pass  # informational only
                continue

            required_count += 1
            if roles:
                populated_count += 1
            else:
                violations.append({
                    "id": entry.get("id"),
                    "standard_name": entry.get("standard_name"),
                    "category": entry.get("category"),
                    "file": label,
                })

        files_summary.append({
            "file": label,
            "total": len(arr),
            "required": required_count,
            "populated": populated_count,
            "excluded": excluded_count,
            "missing": len(violations),
            "invalid_role_ids": len(invalid_roles),
        })
        files_violations.extend(violations)
        if invalid_roles:
            files_violations.extend(
                {"id": eid, "file": label, "kind": "invalid_role_id", "value": r}
                for eid, r in invalid_roles
            )

    # ---- Report ----
    print("=" * 64)
    print("Functional Roles Coverage Gate (Phase 5)")
    print("=" * 64)
    print(f"{'File':<32} {'Total':>6} {'Reqd':>6} {'OK':>6} {'Excl':>6} {'Miss':>6}")
    for s in files_summary:
        flag = "✗" if (s["missing"] or s["invalid_role_ids"]) else "✓"
        print(f"{flag} {s['file']:<30} {s['total']:>6} {s['required']:>6} "
              f"{s['populated']:>6} {s['excluded']:>6} {s['missing']:>6}")

    total_reqd = sum(s["required"] for s in files_summary)
    total_pop = sum(s["populated"] for s in files_summary)
    total_miss = sum(s["missing"] for s in files_summary)
    total_invalid = sum(s["invalid_role_ids"] for s in files_summary)

    pct = (100.0 * total_pop / total_reqd) if total_reqd else 100.0
    print(f"\nRequired entries populated: {total_pop} / {total_reqd} ({pct:.1f}%)")
    print(f"Invalid role-ID drift: {total_invalid}")

    if total_miss == 0 and total_invalid == 0:
        print("\n✓ GATE PASS — all required entries populated; vocab clean")
        return 0

    if verbose and files_violations:
        print(f"\n--- {len(files_violations)} violation(s) ---")
        for v in files_violations[:50]:
            print(f"  {v}")
        if len(files_violations) > 50:
            print(f"  ... and {len(files_violations)-50} more")

    print(f"\n✗ GATE BLOCKED — {total_miss} missing role(s), {total_invalid} invalid role-id(s)")
    return 1


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--verbose", "-v", action="store_true",
                    help="Print all violations")
    args = ap.parse_args()
    return run_gate(verbose=args.verbose)


if __name__ == "__main__":
    sys.exit(main())
