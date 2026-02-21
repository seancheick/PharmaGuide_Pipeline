#!/usr/bin/env python3
"""Check for Phosphorus and Vitamin C cross-parent mismatches in Softgels."""
import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))


def load_sample(directory, max_products=5000):
    """Load up to max_products from a batch directory."""
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
        if len(products) >= max_products:
            break
    return products


def main():
    clean = load_sample("output_Softgels/cleaned", max_products=10000)
    enriched = load_sample("output_Softgels_enriched/enriched", max_products=10000)

    # Find products where clean label says "Phosphorus" but enriched maps to non-phosphorus
    print("=== Phosphorus mismatch check ===")
    phosphorus_issues = []
    for pid, c in clean.items():
        e = enriched.get(pid)
        if not e:
            continue
        for ing in c.get("activeIngredients", []):
            label_name = ing.get("name", "")
            std_name = ing.get("standardName", "")
            if (label_name.lower() == "phosphorus"
                    or std_name.lower() == "phosphorus"):
                # Find the enriched match
                iqd = e.get("ingredient_quality_data", {})
                for e_ing in iqd.get("ingredients_scorable", []):
                    e_name = e_ing.get("name", "")
                    if (e_name.lower() == label_name.lower()
                            or e_name.lower() == "phosphorus"):
                        cid = e_ing.get("canonical_id", "")
                        form = e_ing.get("matched_form", "")
                        if cid != "phosphorus":
                            phosphorus_issues.append({
                                "id": pid,
                                "product": e.get("fullName", "?")[:50],
                                "label_name": label_name,
                                "canonical_id": cid,
                                "form": form,
                            })
                        break

    print(f"Products with Phosphorus label → non-phosphorus canonical: {len(phosphorus_issues)}")
    for iss in phosphorus_issues[:10]:
        print(f"  ID={iss['id']} | {iss['product']}")
        print(f"    label='{iss['label_name']}' → canonical={iss['canonical_id']!r}, "
              f"form={iss['form']!r}")

    # Find Vitamin C → wrong parent
    print("\n=== Vitamin C mismatch check ===")
    vitc_issues = []
    for pid, c in clean.items():
        e = enriched.get(pid)
        if not e:
            continue
        for ing in c.get("activeIngredients", []):
            label_name = ing.get("name", "")
            std_name = ing.get("standardName", "")
            if ("vitamin c" in label_name.lower()
                    or std_name.lower() in ("vitamin c", "ascorbic acid")):
                iqd = e.get("ingredient_quality_data", {})
                for e_ing in iqd.get("ingredients_scorable", []):
                    e_name = e_ing.get("name", "").lower()
                    if e_name == label_name.lower() or "vitamin c" in e_name or "ascorbic" in e_name:
                        cid = e_ing.get("canonical_id", "")
                        form = e_ing.get("matched_form", "")
                        if cid != "vitamin_c":
                            vitc_issues.append({
                                "id": pid,
                                "product": e.get("fullName", "?")[:50],
                                "label_name": label_name,
                                "canonical_id": cid,
                                "form": form,
                            })
                        break

    print(f"Products with 'Vitamin C' label → non-vitamin_c canonical: {len(vitc_issues)}")
    for iss in vitc_issues[:10]:
        print(f"  ID={iss['id']} | {iss['product']}")
        print(f"    label='{iss['label_name']}' → canonical={iss['canonical_id']!r}, "
              f"form={iss['form']!r}")


if __name__ == "__main__":
    main()
