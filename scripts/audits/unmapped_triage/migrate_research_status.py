#!/usr/bin/env python3
"""Schema migration — add research_status field to data entries.

Per clinician decision 2026-05-01: 'stub' was too vague. Replace with
research_status: unverified / partially_verified / validated.

Mapping (from existing review_status):
- stub          → unverified  (legacy "minimal scoring data" state)
- draft         → unverified
- pending       → unverified
- provisional   → partially_verified  (some review applied)
- needs_review  → unverified  (explicitly waiting on clinician)
- reviewed      → partially_verified
- verified      → validated  (legacy alias for validated)
- validated     → validated

This script is idempotent — running twice produces the same result.
The original review_status field is PRESERVED (not removed) for backward
compatibility; both fields coexist during migration.

Usage:
    python3 scripts/audits/unmapped_triage/migrate_research_status.py --dry-run
    python3 scripts/audits/unmapped_triage/migrate_research_status.py --apply
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent / "data"

REVIEW_TO_RESEARCH = {
    "stub": "unverified",
    "draft": "unverified",
    "pending": "unverified",
    "needs_review": "unverified",
    "provisional": "partially_verified",
    "reviewed": "partially_verified",
    "verified": "validated",
    "validated": "validated",
}


def migrate_entry(entry: dict) -> bool:
    """Add research_status if missing. Return True if changed."""
    if not isinstance(entry, dict):
        return False
    dq = entry.get("data_quality")
    if not isinstance(dq, dict):
        return False
    if "research_status" in dq:
        return False  # already migrated
    rs = dq.get("review_status")
    if rs is None:
        return False
    research = REVIEW_TO_RESEARCH.get(rs)
    if research is None:
        return False
    dq["research_status"] = research
    return True


def migrate_file(path: Path, list_key: str | None, apply: bool) -> dict:
    if not path.exists():
        return {"file": path.name, "missing": True}
    data = json.loads(path.read_text())
    changes = 0
    if list_key:
        for e in data.get(list_key, []):
            if migrate_entry(e):
                changes += 1
    else:
        # IQM top-level
        for k, v in data.items():
            if k.startswith("_"):
                continue
            if migrate_entry(v):
                changes += 1
    if apply and changes:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    return {"file": path.name, "changes": changes}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true",
                   help="Write changes (default: dry-run)")
    args = p.parse_args()

    targets = [
        ("ingredient_quality_map.json", None),
        ("botanical_ingredients.json", "botanical_ingredients"),
        ("standardized_botanicals.json", "standardized_botanicals"),
        ("other_ingredients.json", "other_ingredients"),
        ("harmful_additives.json", "harmful_additives"),
        ("banned_recalled_ingredients.json", "ingredients"),
    ]

    print(f"\n{'APPLY' if args.apply else 'DRY RUN'} — adding research_status to entries with review_status\n")
    total = 0
    for fname, key in targets:
        result = migrate_file(ROOT / fname, key, args.apply)
        if result.get("missing"):
            print(f"  SKIP {fname} — file not found")
            continue
        ch = result["changes"]
        total += ch
        print(f"  {fname}: {ch} entries migrated")
    print(f"\nTotal: {total} entries migrated to research_status")
    if not args.apply:
        print("\n(Re-run with --apply to write changes.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
