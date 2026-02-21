#!/usr/bin/env python3
"""Check why Vitamin E gets is_excipient=True in enriched output."""
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
    clean = load_all("output_Gummies/cleaned")
    enriched = load_all("output_Gummies_enriched/enriched")

    # Find standardName of Vitamin E in clean
    print("=== Vitamin E standardName in clean ===")
    seen_std = set()
    for pid, c in list(clean.items())[:500]:
        for ing in c.get("activeIngredients", []):
            name_lower = ing.get("name", "").lower()
            if "vitamin e" in name_lower or "tocopherol" in name_lower:
                std_name = ing.get("standardName", "")
                if std_name not in seen_std:
                    seen_std.add(std_name)
                    print(f"  '{ing.get('name')}' -> standardName='{std_name}'")
                    # Check enriched
                    e = enriched.get(pid, {})
                    iqd = e.get("ingredient_quality_data", {})
                    for e_ing in iqd.get("ingredients_scorable", []):
                        cid = e_ing.get("canonical_id", "")
                        e_name = e_ing.get("name", "").lower()
                        if "vitamin_e" in cid or "tocopherol" in e_name:
                            print(f"    enriched: canonical={cid!r}, "
                                  f"is_excipient={e_ing.get('is_excipient')}, "
                                  f"never_promote={e_ing.get('never_promote_reason')!r}, "
                                  f"score={e_ing.get('ingredient_quality_score')!r}")
                            break
                break

    # Check turmeric specifically
    print("\n=== Turmeric standardName in clean ===")
    seen_std2 = set()
    for pid, c in list(clean.items())[:2000]:
        for ing in c.get("activeIngredients", []):
            name_lower = ing.get("name", "").lower()
            if "turmeric" in name_lower or "curcumin" in name_lower:
                std_name = ing.get("standardName", "")
                key = (std_name, ing.get("name", ""))
                if key not in seen_std2:
                    seen_std2.add(key)
                    print(f"  '{ing.get('name')[:50]}' -> standardName='{std_name}'")
                    # Check enriched
                    e = enriched.get(pid, {})
                    iqd = e.get("ingredient_quality_data", {})
                    for e_ing in iqd.get("ingredients_scorable", []) + iqd.get("ingredients_skipped", []):
                        cid = e_ing.get("canonical_id", "")
                        if "turmeric" in cid or "curcumin" in cid:
                            print(f"    enriched: canonical={cid!r}, "
                                  f"is_excipient={e_ing.get('is_excipient')}, "
                                  f"score={e_ing.get('ingredient_quality_score')!r}")
                            break
                if len(seen_std2) >= 5:
                    break
        if len(seen_std2) >= 5:
            break

    # What does is_excipient=True actually mean for scoring?
    print("\n=== is_excipient=True - impact on score ===")
    print("Are these items in scorable or skipped?")
    in_scorable_with_score = 0
    in_scorable_no_score = 0
    for pid, e in enriched.items():
        iqd = e.get("ingredient_quality_data", {})
        for ing in iqd.get("ingredients_scorable", []):
            if ing.get("is_excipient", False):
                score = ing.get("ingredient_quality_score")
                if score is not None:
                    in_scorable_with_score += 1
                else:
                    in_scorable_no_score += 1
    print(f"  in scorable with score: {in_scorable_with_score}")
    print(f"  in scorable with score=None: {in_scorable_no_score}")

    # How does score_supplements.py handle is_excipient?
    print("\n=== Searching score_supplements.py for is_excipient ===")
    score_path = os.path.join(BASE, "score_supplements.py")
    if os.path.exists(score_path):
        with open(score_path, encoding="utf-8") as f:
            lines = f.readlines()
        for i, line in enumerate(lines):
            if "is_excipient" in line or "excipient" in line.lower():
                print(f"  line {i+1}: {line.rstrip()}")
    else:
        print("  score_supplements.py not found")


if __name__ == "__main__":
    main()
