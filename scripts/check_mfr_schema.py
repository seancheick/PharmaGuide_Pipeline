#!/usr/bin/env python3
"""Check manufacturer_data.top_manufacturer.found vs is_trusted_manufacturer consistency."""
import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))


def load_all(directory):
    products = {}
    dirpath = os.path.join(BASE, directory)
    if not os.path.isdir(dirpath):
        return products
    for fname in sorted(os.listdir(dirpath)):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(dirpath, fname), encoding="utf-8") as f:
            data = json.load(f)
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


def check_batch(name, edir):
    enriched = load_all(edir)
    schema_inconsistent = []
    for pid, e in enriched.items():
        mfr_data = e.get("manufacturer_data", {})
        top_mfr = mfr_data.get("top_manufacturer", {})
        found = top_mfr.get("found", False)
        is_trusted = e.get("is_trusted_manufacturer")
        if is_trusted is None:
            is_trusted = mfr_data.get("is_trusted_manufacturer", False)
        match_type = top_mfr.get("match_type", "")
        if found and not is_trusted:
            schema_inconsistent.append({
                "id": pid,
                "product_name": e.get("fullName") or e.get("product_name") or "?",
                "found": found,
                "is_trusted": is_trusted,
                "match_type": match_type,
                "mfr_id": top_mfr.get("manufacturer_id"),
                "mfr_name": top_mfr.get("name") or top_mfr.get("standard_name"),
                "match_confidence": top_mfr.get("match_confidence"),
            })
    total = len(enriched)
    print(f"\n{name}: found=True but is_trusted=False: "
          f"{len(schema_inconsistent)}/{total} products")
    for c in schema_inconsistent[:3]:
        print(f"  ID={c['id']} | {c['product_name'][:45]}")
        print(f"    found={c['found']}, is_trusted={c['is_trusted']}, "
              f"match_type={c['match_type']}, mfr={c['mfr_id']}, "
              f"conf={c['match_confidence']}")


for batch_name, edir in [
    ("Gummies",        "output_Gummies_enriched/enriched"),
    ("Softgels",       "output_Softgels_enriched/enriched"),
    ("Thorne",         "output_Thorne_enriched/enriched"),
    ("Lozenges",       "output_Lozenges_enriched/enriched"),
    ("Nordic-Naturals","output_Nordic-Naturals_enriched/enriched"),
    ("Olly",           "output_Olly_enriched/enriched"),
]:
    check_batch(batch_name, edir)
