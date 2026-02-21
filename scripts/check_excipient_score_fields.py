#!/usr/bin/env python3
"""Check all fields of excipient=True ingredients to understand score impact."""
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
    enriched = load_all("output_Gummies_enriched/enriched")

    print("=== Sample excipient=True Vitamin E ingredient fields ===")
    shown = 0
    for pid, e in enriched.items():
        if shown >= 3:
            break
        iqd = e.get("ingredient_quality_data", {})
        for ing in iqd.get("ingredients_scorable", []):
            if ing.get("is_excipient") and "vitamin_e" in ing.get("canonical_id", ""):
                print(f"\nProduct {pid}: {e.get('fullName','?')[:50]}")
                for k, v in ing.items():
                    if v is not None and v != "" and v != [] and v != {}:
                        print(f"  {k}: {v!r}")
                shown += 1
                break

    print("\n=== Sample excipient=True Turmeric ingredient fields ===")
    shown = 0
    for pid, e in enriched.items():
        if shown >= 2:
            break
        iqd = e.get("ingredient_quality_data", {})
        for ing in iqd.get("ingredients_scorable", []):
            if ing.get("is_excipient") and "turmeric" in ing.get("canonical_id", ""):
                print(f"\nProduct {pid}: {e.get('fullName','?')[:50]}")
                for k, v in ing.items():
                    if v is not None and v != "" and v != [] and v != {}:
                        print(f"  {k}: {v!r}")
                shown += 1
                break

    # Check what 'score' field (not ingredient_quality_score) is for excipient items
    print("\n=== 'score' field values for excipient=True items ===")
    score_values = {}
    for pid, e in enriched.items():
        iqd = e.get("ingredient_quality_data", {})
        for ing in iqd.get("ingredients_scorable", []):
            if ing.get("is_excipient"):
                score = ing.get("score")
                mapped = ing.get("mapped", False)
                key = f"score={score!r}, mapped={mapped}"
                score_values[key] = score_values.get(key, 0) + 1
    for k, v in sorted(score_values.items(), key=lambda x: -x[1])[:10]:
        print(f"  {k}: {v} occurrences")


if __name__ == "__main__":
    main()
