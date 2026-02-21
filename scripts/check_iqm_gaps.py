#!/usr/bin/env python3
"""Check IQM for missing aliases and form gaps found in Thorne audit."""
import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))
IQM_PATH = os.path.join(BASE, "data", "ingredient_quality_map.json")


def main():
    with open(IQM_PATH, encoding="utf-8") as f:
        iqm = json.load(f)

    # 1. Check folate forms and aliases
    print("=== folate parent forms ===")
    folate = iqm.get("folate", {})
    for form_key, form in folate.get("forms", {}).items():
        aliases = form.get("aliases", [])
        print(f"  {form_key!r}")
        if aliases:
            print(f"    aliases: {aliases[:10]}")

    # 2. Search for 5-mthf / methylfolate / L-5-Methyltetrahydrofolic Acid
    print("\n=== searching for 5-mthf / methylfolate across all parents ===")
    for parent_key, parent in iqm.items():
        for form_key, form in parent.get("forms", {}).items():
            aliases = form.get("aliases", [])
            all_names = [form_key] + aliases
            for n in all_names:
                if ("5-mthf" in n.lower()
                        or "methyltetrahydro" in n.lower()
                        or "methylfolate" in n.lower()):
                    print(f"  {parent_key}/{form_key} | matching alias: {n!r}")
                    break

    # 3. Search for riboflavin-5-phosphate / FMN
    print("\n=== searching for riboflavin-5'-phosphate / FMN ===")
    for parent_key, parent in iqm.items():
        for form_key, form in parent.get("forms", {}).items():
            aliases = form.get("aliases", [])
            all_names = [form_key] + aliases
            for n in all_names:
                if ("riboflavin" in n.lower()
                        and ("phosphate" in n.lower()
                             or "fmn" in n.lower()
                             or "sodium" in n.lower())):
                    print(f"  {parent_key}/{form_key} | matching alias: {n!r}")
                    break

    # 4. Check what Thorne products actually have as L-5-MTHF
    print("\n=== Thorne enriched: how does 5-MTHF map? ===")
    thorne_dir = os.path.join(BASE, "output_Thorne_enriched", "enriched")
    if os.path.isdir(thorne_dir):
        for fname in sorted(os.listdir(thorne_dir))[:2]:
            if not fname.endswith(".json"):
                continue
            with open(os.path.join(thorne_dir, fname), encoding="utf-8") as f:
                data = json.load(f)
            products = data if isinstance(data, list) else [data]
            for prod in products:
                iqd = prod.get("ingredient_quality_data", {})
                for ing in iqd.get("ingredients_scorable", []) + iqd.get("ingredients_skipped", []):
                    name = ing.get("name", "")
                    if ("methyltetrahydro" in name.lower()
                            or "5-mthf" in name.lower()
                            or "methylfolate" in name.lower()):
                        print(f"  ID={prod.get('id')} | name={name!r}")
                        print(f"    canonical={ing.get('canonical_id')!r}, "
                              f"form={ing.get('matched_form')!r}, "
                              f"score={ing.get('score')!r}")
                        print(f"    skip_reason={ing.get('skip_reason')!r}, "
                              f"decision={ing.get('decision_reason')!r}")

    # 5. Check riboflavin-5-phosphate in Thorne
    print("\n=== Thorne enriched: how does Riboflavin 5-Phosphate map? ===")
    if os.path.isdir(thorne_dir):
        shown = set()
        for fname in sorted(os.listdir(thorne_dir)):
            if not fname.endswith(".json"):
                continue
            with open(os.path.join(thorne_dir, fname), encoding="utf-8") as f:
                data = json.load(f)
            products = data if isinstance(data, list) else [data]
            for prod in products:
                iqd = prod.get("ingredient_quality_data", {})
                for ing in iqd.get("ingredients_scorable", []) + iqd.get("ingredients_skipped", []):
                    name = ing.get("name", "")
                    if "riboflavin" in name.lower() and "phosphate" in name.lower():
                        key = ing.get("canonical_id", "") + "|" + ing.get("matched_form", "")
                        if key not in shown:
                            shown.add(key)
                            print(f"  ID={prod.get('id')} | name={name!r}")
                            print(f"    canonical={ing.get('canonical_id')!r}, "
                                  f"form={ing.get('matched_form')!r}, "
                                  f"score={ing.get('score')!r}")


if __name__ == "__main__":
    main()
