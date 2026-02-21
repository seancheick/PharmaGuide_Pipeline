#!/usr/bin/env python3
"""Examine Phosphorus → calcium mismatch in enriched data to find fix point."""
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
    target_ids = {
        "230344", "26095", "266011", "267690", "273672",
        "274576", "31755", "34881", "35391",
    }
    clean = load_all("output_Softgels/cleaned")
    enriched = load_all("output_Softgels_enriched/enriched")

    for pid in sorted(target_ids):
        c = clean.get(pid)
        e = enriched.get(pid)
        if not c or not e:
            continue

        # Find the phosphorus active ingredient in clean
        for ing in c.get("activeIngredients", []):
            name = ing.get("name", "")
            std = ing.get("standardName", "")
            if "phosphor" in name.lower() or "phosphor" in std.lower():
                print(f"\nID={pid} | {c.get('fullName','?')[:45]}")
                print(f"  clean: name={name!r}, standardName={std!r}")
                print(f"  forms in clean: {ing.get('forms', [])}")

                # Find corresponding enriched entry
                iqd = e.get("ingredient_quality_data", {})
                for e_ing in iqd.get("ingredients_scorable", []):
                    if (e_ing.get("name", "").lower() == name.lower()
                            or "phosphor" in e_ing.get("name", "").lower()):
                        print(f"  enriched: canonical={e_ing.get('canonical_id')!r}, "
                              f"form={e_ing.get('matched_form')!r}, "
                              f"score={e_ing.get('score')!r}")
                        print(f"    match_tier={e_ing.get('match_tier')!r}, "
                              f"form_extraction_used={e_ing.get('form_extraction_used')!r}")
                        print(f"    extracted_forms={e_ing.get('extracted_forms')!r}")
                        break
                break

    # Also examine the IQM phosphorus parent to see if calcium phosphate is there
    print("\n=== IQM phosphorus parent ===")
    iqm = json.load(open(os.path.join(BASE, "data", "ingredient_quality_map.json"),
                         encoding="utf-8"))
    phos = iqm.get("phosphorus", {})
    for form_key, form in phos.get("forms", {}).items():
        aliases = form.get("aliases", [])
        print(f"  form: {form_key!r}")
        if aliases:
            print(f"    aliases: {aliases[:8]}")

    print("\n=== IQM calcium parent - phosphate forms ===")
    calcium = iqm.get("calcium", {})
    for form_key, form in calcium.get("forms", {}).items():
        if "phosphate" in form_key.lower():
            aliases = form.get("aliases", [])
            print(f"  form: {form_key!r}, aliases: {aliases[:5]}")


if __name__ == "__main__":
    main()
