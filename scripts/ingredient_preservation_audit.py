#!/usr/bin/env python3
"""
Ingredient Preservation Audit
Verifies all activeIngredients from clean are accounted for in enriched output.
Files are batch JSONs (each file is a list of products).
Reports any discrepancies and lists skipped ingredients.
"""

import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))

BATCHES = [
    ("Gummies",          "output_Gummies/cleaned",           "output_Gummies_enriched/enriched"),
    ("Lozenges",         "output_Lozenges/cleaned",          "output_Lozenges_enriched/enriched"),
    ("Nordic-Naturals",  "output_Nordic-Naturals/cleaned",   "output_Nordic-Naturals_enriched/enriched"),
    ("Olly",             "output_Olly/cleaned",              "output_Olly_enriched/enriched"),
    ("Softgels",         "output_Softgels/cleaned",          "output_Softgels_enriched/enriched"),
    ("Thorne",           "output_Thorne/cleaned",            "output_Thorne_enriched/enriched"),
    ("tmp_focus",        "tmp_focus_cleaned",                "tmp_focus_enriched/enriched"),
]


def load_all_products(directory):
    """Load all products from a directory of batch JSON files (each file = list of products)."""
    products = {}
    if not os.path.isdir(directory):
        return products
    for fname in sorted(os.listdir(directory)):
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(directory, fname)
        try:
            data = json.load(open(fpath))
        except Exception as e:
            print(f"  [ERROR] Could not load {fname}: {e}")
            continue
        if isinstance(data, list):
            for item in data:
                pid = str(item.get("id", ""))
                if pid:
                    products[pid] = item
        elif isinstance(data, dict):
            pid = str(data.get("id", ""))
            if pid:
                products[pid] = data
    return products


def audit_batch(batch_name, clean_dir, enriched_dir):
    clean_path = os.path.join(BASE, clean_dir)
    enriched_path = os.path.join(BASE, enriched_dir)

    clean_products = load_all_products(clean_path)
    enriched_products = load_all_products(enriched_path)

    print(f"\n{'='*70}")
    print(f"BATCH: {batch_name}")
    print(f"  Clean products:    {len(clean_products)}  ({clean_dir})")
    print(f"  Enriched products: {len(enriched_products)}  ({enriched_dir})")

    if not clean_products:
        print("  [SKIP] No clean products found")
        return

    # Find products missing from enriched
    missing_ids = set(clean_products.keys()) - set(enriched_products.keys())
    if missing_ids:
        print(f"\n  *** {len(missing_ids)} PRODUCT(S) NOT ENRICHED ***")
        for pid in sorted(missing_ids, key=lambda x: int(x) if x.isdigit() else x)[:20]:
            item = clean_products[pid]
            name = item.get("fullName") or item.get("product_name") or "?"
            print(f"    - ID={pid}  {name[:60]}")
        if len(missing_ids) > 20:
            print(f"    ... and {len(missing_ids)-20} more")

    # Ingredient preservation check (only products present in both)
    common_ids = sorted(
        set(clean_products.keys()) & set(enriched_products.keys()),
        key=lambda x: int(x) if x.isdigit() else x
    )

    ok_count = 0
    issues = []
    skipped_details = []

    for pid in common_ids:
        cdata = clean_products[pid]
        edata = enriched_products[pid]

        active_clean = cdata.get("activeIngredients", [])
        n_active = len(active_clean)

        iqd = edata.get("ingredient_quality_data", {})
        scorable = iqd.get("ingredients_scorable", [])
        skipped = iqd.get("ingredients_skipped", [])
        n_scorable = len(scorable)
        n_skipped = len(skipped)
        n_total_iqd = n_scorable + n_skipped

        name = cdata.get("fullName") or cdata.get("product_name") or "?"

        if n_active == n_total_iqd:
            ok_count += 1
        else:
            diff = n_active - n_total_iqd
            issues.append({
                "id": pid,
                "name": name,
                "clean_active": n_active,
                "iqd_scorable": n_scorable,
                "iqd_skipped": n_skipped,
                "iqd_total": n_total_iqd,
                "diff": diff,
            })

        # Collect skipped ingredient details
        if n_skipped > 0:
            skip_names = []
            for ing in skipped:
                if isinstance(ing, dict):
                    ing_name = (ing.get("ingredient_name") or ing.get("name")
                                or ing.get("raw_name") or str(ing))
                    reason = ing.get("skip_reason") or ing.get("reason") or "?"
                    skip_names.append(f"{ing_name} [{reason}]")
                else:
                    skip_names.append(str(ing))
            skipped_details.append({
                "id": pid,
                "name": name,
                "skipped": skip_names,
            })

    print(f"\n  Ingredient Preservation (activeIngredients == scorable+skipped):")
    print(f"    OK: {ok_count}/{len(common_ids)}")

    if issues:
        print(f"\n  *** DISCREPANCIES ({len(issues)}) ***")
        for iss in issues:
            print(f"    ID={iss['id']} | {iss['name'][:55]}")
            print(f"      clean_active={iss['clean_active']}  "
                  f"iqd_scorable={iss['iqd_scorable']}  "
                  f"iqd_skipped={iss['iqd_skipped']}  "
                  f"total={iss['iqd_total']}  DIFF={iss['diff']}")
    else:
        if common_ids:
            print(f"    All {len(common_ids)} products: full ingredient preservation confirmed.")

    if skipped_details:
        print(f"\n  Skipped (recognized_non_scorable) — {len(skipped_details)} product(s):")
        for sd in skipped_details:
            print(f"    ID={sd['id']} | {sd['name'][:55]}")
            for s in sd["skipped"]:
                print(f"      - {s}")


def main():
    print("INGREDIENT PRESERVATION AUDIT")
    print("Checks: clean activeIngredients == enriched (scorable + skipped)")
    for batch_name, clean_dir, enriched_dir in BATCHES:
        audit_batch(batch_name, clean_dir, enriched_dir)
    print(f"\n{'='*70}")
    print("AUDIT COMPLETE")


if __name__ == "__main__":
    main()
