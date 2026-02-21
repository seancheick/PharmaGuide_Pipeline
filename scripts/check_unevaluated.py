#!/usr/bin/env python3
"""Check unevaluated_records==0 invariant across all enriched batches."""
import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))

BATCHES = [
    ("Gummies",         "output_Gummies_enriched/enriched"),
    ("Lozenges",        "output_Lozenges_enriched/enriched"),
    ("Nordic-Naturals", "output_Nordic-Naturals_enriched/enriched"),
    ("Olly",            "output_Olly_enriched/enriched"),
    ("Softgels",        "output_Softgels_enriched/enriched"),
    ("Thorne",          "output_Thorne_enriched/enriched"),
    ("tmp_focus",       "tmp_focus_enriched/enriched"),
]


def load_all(directory):
    products = {}
    if not os.path.isdir(directory):
        return products
    for fname in sorted(os.listdir(directory)):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(directory, fname), encoding="utf-8") as f:
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


for name, edir in BATCHES:
    enriched = load_all(os.path.join(BASE, edir))
    violations = []
    for pid, e in enriched.items():
        iqd = e.get("ingredient_quality_data", {})
        unevaluated = iqd.get("unevaluated_records", 0)
        promoted = iqd.get("promoted_from_inactive", [])
        n_promoted = len(promoted) if isinstance(promoted, list) else promoted
        total_active = iqd.get("total_active", 0)
        if unevaluated != 0:
            product_name = e.get("fullName") or e.get("product_name") or "?"
            violations.append((pid, product_name, unevaluated, total_active, n_promoted))
    total = len(enriched)
    ok = total - len(violations)
    status = "PASS" if not violations else "FAIL"
    print(f"{name}: {status} | {ok}/{total} products unevaluated=0  (violations: {len(violations)})")
    for v in violations[:5]:
        print(f"  ID={v[0]} | {v[1][:50]} | unevaluated={v[2]}, total_active={v[3]}, promoted={v[4]}")
