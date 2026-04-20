#!/usr/bin/env python3
"""
Sprint D2.1 retro-fix — apply the cleaner contract (mapped ⇒ canonical_id)
to existing cleaned_*.json files in place so the brand-wide regression
test (``test_no_silently_mapped_rows.py``) passes without waiting for
D5.1 to re-run the full cleaner.

This is a one-time maintenance helper. The code-level fix in
``enhanced_normalizer.py`` already prevents new silently-mapped rows
from being written — this script retroactively cleans stale cleaned
output that was produced by pre-D2.1 runs.

For every active/inactive ingredient row with ``mapped=True`` and
``canonical_id=None``:
  - sets ``mapped=False``
  - sets ``canonical_source_db="unmapped"``

Never modifies rows that already satisfy the contract. Idempotent.

Usage:
    python3 scripts/tests/apply_d2_1_contract_retro.py [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PRODUCTS_ROOT = REPO_ROOT / "scripts" / "products"


def fixup_ingredient(ing: dict) -> bool:
    """Return True if a modification was made."""
    if not isinstance(ing, dict):
        return False
    mapped = ing.get("mapped")
    canonical_id = ing.get("canonical_id")
    if mapped and canonical_id is None:
        ing["mapped"] = False
        ing["canonical_source_db"] = "unmapped"
        return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not PRODUCTS_ROOT.exists():
        print(f"No {PRODUCTS_ROOT}; nothing to fix.")
        return 0

    total_rows_fixed = 0
    files_touched = 0
    brands_touched = set()

    for brand_dir in sorted(PRODUCTS_ROOT.glob("output_*")):
        if "_enriched" in brand_dir.name or "_scored" in brand_dir.name:
            continue
        cleaned = brand_dir / "cleaned"
        if not cleaned.exists():
            continue
        brand = brand_dir.name.replace("output_", "")

        for batch in sorted(cleaned.glob("cleaned_*.json")):
            try:
                data = json.loads(batch.read_text())
            except json.JSONDecodeError:
                continue
            if not isinstance(data, list):
                continue

            file_rows_fixed = 0
            for product in data:
                if not isinstance(product, dict):
                    continue
                for section in ("activeIngredients", "inactiveIngredients"):
                    for ing in product.get(section, []) or []:
                        if fixup_ingredient(ing):
                            file_rows_fixed += 1

            if file_rows_fixed:
                total_rows_fixed += file_rows_fixed
                files_touched += 1
                brands_touched.add(brand)
                if not args.dry_run:
                    batch.write_text(json.dumps(data, indent=2) + "\n")
                    print(f"  [{brand}] {batch.name}: fixed {file_rows_fixed} rows")
                else:
                    print(f"  [{brand}] {batch.name}: would fix {file_rows_fixed} rows (dry-run)")

    print()
    print(f"Summary: {total_rows_fixed} rows across {files_touched} files in "
          f"{len(brands_touched)} brands.")
    if args.dry_run:
        print("(dry-run; no files written)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
