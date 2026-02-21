#!/usr/bin/env python3
"""Investigate Thorne manufacturer matching anomaly."""
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


def main():
    clean = load_all("output_Thorne/cleaned")
    enriched = load_all("output_Thorne_enriched/enriched")

    # Find Thorne products with is_trusted=False
    trusted_true = 0
    trusted_false_brands = {}
    fuzzy_to_throne = 0

    for pid, e in enriched.items():
        mfr_data = e.get("manufacturer_data", {})
        top_mfr = mfr_data.get("top_manufacturer", {})
        found = top_mfr.get("found", False)
        is_trusted = e.get("is_trusted_manufacturer", False)
        match_type = top_mfr.get("match_type", "")
        mfr_id = top_mfr.get("manufacturer_id", "")

        if is_trusted:
            trusted_true += 1
        elif found and not is_trusted:
            # Get brand from clean
            c = clean.get(pid, {})
            contacts = c.get("contacts", [])
            brand = c.get("brandName", "")
            mfr_name = ""
            for contact in contacts:
                if contact.get("type") == "manufacturer":
                    mfr_name = contact.get("company", "")
                    break
            brand_key = f"brand={brand!r}, mfr={mfr_name!r}"
            trusted_false_brands[brand_key] = trusted_false_brands.get(brand_key, 0) + 1
            if "THRONE" in mfr_id:
                fuzzy_to_throne += 1

    print(f"is_trusted_manufacturer=True: {trusted_true}")
    print(f"is_trusted_manufacturer=False (found=True): {sum(trusted_false_brands.values())}")
    print(f"  of which match to MANUF_THRONE: {fuzzy_to_throne}")
    print()
    print("Brands/manufacturers that get found=True, is_trusted=False:")
    for brand_key, count in sorted(trusted_false_brands.items(), key=lambda x: -x[1])[:15]:
        print(f"  {count:4d}  {brand_key}")

    # Check if MANUF_THRONE is in top_manufacturers trusted list
    print("\n=== top_manufacturers_data.json check ===")
    with open(os.path.join(BASE, "data", "top_manufacturers_data.json"), encoding="utf-8") as f:
        content = f.read()
    if "MANUF_THRONE" in content:
        print("MANUF_THRONE exists in top_manufacturers_data.json")
    if "MANUF_THORNE" in content:
        print("MANUF_THORNE exists in top_manufacturers_data.json")
    else:
        print("MANUF_THORNE does NOT exist (only MANUF_THRONE with typo)")

    # Check how the code decides is_trusted
    # Look for the trust gate logic in enrich_supplements_v3.py
    print("\n=== is_trusted_manufacturer logic ===")
    with open(os.path.join(BASE, "enrich_supplements_v3.py"), encoding="utf-8") as f:
        lines = f.readlines()
    for i, line in enumerate(lines):
        if "is_trusted_manufacturer" in line or "trusted_manufacturer" in line:
            if "def " in line or "=" in line or "return" in line:
                print(f"  line {i+1}: {line.rstrip()}")


if __name__ == "__main__":
    main()
