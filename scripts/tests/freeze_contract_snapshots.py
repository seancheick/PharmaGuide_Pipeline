#!/usr/bin/env python3
"""
Phase 0 — Scoring-snapshot fixture freezer.

Reads the manifest at ``scripts/tests/fixtures/contract_snapshots/_manifest.json``,
extracts the listed products from the current scored output under
``scripts/products/output_<brand>_scored/scored/*.json``, and writes one
``<dsld_id>.json`` fixture per product containing only the fields enumerated
in the manifest's ``frozen_fields`` whitelist.

Invoked by hand when a scoring change has been reviewed and the new
baselines should replace the old ones. The matching test
(``scripts/tests/test_scoring_snapshot_v1.py``) compares the current
scored output against these fixtures on every test run — any drift in
frozen fields fails the test.

Usage:
    python3 scripts/tests/freeze_contract_snapshots.py          # freeze all
    python3 scripts/tests/freeze_contract_snapshots.py 16037    # freeze one by dsld_id
    python3 scripts/tests/freeze_contract_snapshots.py --dry-run

Exit codes:
    0 — success, all products frozen
    1 — manifest missing, product missing, or scored output missing
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = REPO_ROOT / "scripts" / "tests" / "fixtures" / "contract_snapshots" / "_manifest.json"
FIXTURE_DIR = MANIFEST.parent
PRODUCTS_ROOT = REPO_ROOT / "scripts" / "products"


def load_manifest() -> Dict[str, Any]:
    if not MANIFEST.exists():
        sys.exit(f"ERROR: manifest not found at {MANIFEST}")
    return json.loads(MANIFEST.read_text())


def load_scored_batches(brand_source: str) -> List[Dict[str, Any]]:
    """Load all scored batches for a given brand_source folder name."""
    scored_root = PRODUCTS_ROOT / f"output_{brand_source}_scored" / "scored"
    if not scored_root.exists():
        return []
    products: List[Dict[str, Any]] = []
    for batch in sorted(scored_root.glob("*.json")):
        try:
            data = json.loads(batch.read_text())
        except json.JSONDecodeError:
            continue
        if isinstance(data, list):
            products.extend(data)
    return products


def find_product(
    dsld_id: int, brand_source: str
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Return (product, source_path) or (None, None)."""
    products = load_scored_batches(brand_source)
    for p in products:
        if str(p.get("dsld_id")) == str(dsld_id):
            return p, f"output_{brand_source}_scored/scored"
    return None, None


def freeze_fields(product: Dict[str, Any], whitelist: List[str]) -> Dict[str, Any]:
    """Return a dict containing only the whitelisted keys from product."""
    frozen: Dict[str, Any] = {}
    for k in whitelist:
        if k in product:
            frozen[k] = product[k]
    return frozen


def freeze_one(
    entry: Dict[str, Any], whitelist: List[str], dry_run: bool
) -> Tuple[bool, str]:
    dsld_id = entry["dsld_id"]
    brand_source = entry["brand_source"]
    label = entry.get("label", "")

    product, source = find_product(dsld_id, brand_source)
    if product is None:
        return False, f"[{dsld_id:>7}] MISSING from {brand_source} scored output"

    frozen = freeze_fields(product, whitelist)
    fixture_path = FIXTURE_DIR / f"{dsld_id}.json"

    if dry_run:
        return True, f"[{dsld_id:>7}] {label[:50]:50s} -> would write {fixture_path.name} (score_80={frozen.get('score_80')})"

    fixture_path.write_text(json.dumps(frozen, indent=2, sort_keys=True) + "\n")
    return True, f"[{dsld_id:>7}] {label[:50]:50s} -> wrote {fixture_path.name} (score_80={frozen.get('score_80')})"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dsld_id", nargs="?", type=int, help="Freeze a single product by dsld_id (default: freeze all)")
    parser.add_argument("--dry-run", action="store_true", help="Report what would be written without touching disk")
    args = parser.parse_args()

    manifest = load_manifest()
    whitelist = manifest["fixture_schema"]["frozen_fields"]
    products = manifest["products"]

    if args.dsld_id is not None:
        products = [p for p in products if p["dsld_id"] == args.dsld_id]
        if not products:
            sys.exit(f"ERROR: dsld_id {args.dsld_id} not in manifest")

    ok_count = 0
    fail_count = 0
    lines: List[str] = []
    for entry in products:
        success, line = freeze_one(entry, whitelist, args.dry_run)
        lines.append(line)
        if success:
            ok_count += 1
        else:
            fail_count += 1

    print("\n".join(lines))
    print()
    print(f"Frozen: {ok_count}  Failed: {fail_count}  Total: {len(products)}")
    if args.dry_run:
        print("(dry-run; no files written)")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
