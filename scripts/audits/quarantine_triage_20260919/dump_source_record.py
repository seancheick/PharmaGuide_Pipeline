#!/usr/bin/env python3
"""Read-only: dump ALL structured content of a cleaned-lane DSLD record."""
import glob
import json
import sys

WANTED = set(sys.argv[1:] or ["75188"])

def show_rows(rows, label):
    if not rows:
        return
    print(f"  --- {label} ({len(rows)}) ---")
    for row in rows:
        if isinstance(row, dict):
            name = row.get("name") or row.get("ingredientName") or "?"
            print(f"    {name} | qty={row.get('quantity')} {row.get('unit','')} | "
                  f"dailyValue={row.get('dailyValue', row.get('dv',''))}")

for path in glob.glob("scripts/products/output_*/cleaned/cleaned_batch_*.json"):
    try:
        data = json.load(open(path, encoding="utf-8"))
    except Exception:
        continue
    recs = data if isinstance(data, list) else data.get("products", [])
    for r in recs:
        rid = str(r.get("id"))
        if rid not in WANTED:
            continue
        print(f"===== {rid} — {r.get('brandName','')} {r.get('fullName','')}")
        for key in sorted(r.keys()):
            v = r[key]
            if key in ("labelText",) and isinstance(v, dict):
                for k2, v2 in v.items():
                    txt = v2 if isinstance(v2, str) else json.dumps(v2)
                    if any(t in txt.lower() for t in ["omega-3", "omega 3", "300 mg", "epa", "dha"]):
                        print(f"  labelText[{k2}] mentions omega/300/EPA/DHA:")
                        for line in txt.splitlines():
                            if any(t in line.lower() for t in ["omega", "epa", "dha", "300"]):
                                print("     ", line.strip()[:180])
            elif isinstance(v, list) and v and isinstance(v[0], dict) and any(
                    k in str(v[0].keys()) for k in ("name", "ingredientName")):
                show_rows(v, key)
        WANTED.discard(rid)
        if not WANTED:
            sys.exit(0)
print("NOT FOUND:", sorted(WANTED))
