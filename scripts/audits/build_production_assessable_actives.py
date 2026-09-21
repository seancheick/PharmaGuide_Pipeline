#!/usr/bin/env python3
"""Derive and persist the complete production assessable canonical active universe.

Outputs scripts/data/production_assessable_actives.json with:
- canonical_id
- top_names / standard_name
- product_count
- row_count
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from scoring_input_contract import get_assessable_evidence_ingredients

OUTPUT_FILE = _SCRIPTS_DIR / "data" / "production_assessable_actives.json"


def main():
    enriched_files = sorted(Path("scripts/products").glob("output_*_enriched/enriched/enriched_*.json"))
    active_products = defaultdict(set)
    active_rows = Counter()
    active_names = defaultdict(Counter)

    total_prods = 0
    for ef in enriched_files:
        try:
            prods = json.loads(ef.read_text(encoding="utf-8"))
            for p in prods:
                did = str(p.get("dsld_id") or "").strip()
                if not did:
                    continue
                total_prods += 1
                for ing in get_assessable_evidence_ingredients(p):
                    cid = str(ing.get("canonical_id") or "").strip().lower()
                    if not cid:
                        continue
                    active_products[cid].add(did)
                    active_rows[cid] += 1
                    name = str(ing.get("ingredient_name") or ing.get("name") or ing.get("standard_name") or "").strip()
                    if name:
                        active_names[cid][name] += 1
        except Exception as e:
            print(f"Error reading {ef}: {e}")

    actives_list = []
    for cid in sorted(active_products.keys()):
        top_name = active_names[cid].most_common(1)[0][0] if active_names[cid] else cid
        actives_list.append({
            "canonical_id": cid,
            "standard_name": top_name,
            "product_count": len(active_products[cid]),
            "row_count": active_rows[cid],
            "common_names": [n for n, _ in active_names[cid].most_common(5)],
        })

    payload = {
        "_metadata": {
            "description": "Real production distinct assessable canonical actives derived via get_assessable_evidence_ingredients() across catalog",
            "purpose": "Authoritative denominator for production Evidence routing, completed disposition, and product completeness KPIs",
            "schema_version": "5.0.0",
            "last_updated": "2026-09-21",
            "total_entries": len(actives_list),
            "catalog_products_evaluated": total_prods,
        },
        "assessable_actives": actives_list,
    }

    OUTPUT_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(actives_list)} production assessable actives to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
