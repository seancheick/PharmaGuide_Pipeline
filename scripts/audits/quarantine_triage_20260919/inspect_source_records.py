#!/usr/bin/env python3
"""Read-only: dump the original (cleaned-lane) DSLD record for given product ids.

Prints activeIngredients/ingredientRows with quantities, plus labelText, so
pipeline rows can be compared against what DSLD actually carries — the check
the clinical sign-off review asked for ("dig deeper, check what's there").
"""
import glob
import json
import sys

WANTED = set(sys.argv[1:] or ["75188", "243713"])

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
        print(f"===== {rid} — {r.get('brandName','')} {r.get('fullName','')} ({path.split('/')[2]})")
        rows = r.get("ingredientRows") or []
        if not rows:
            rows = r.get("activeIngredients") or []
        for row in rows:
            print(f"  [{row.get('sourceSection', row.get('source_section', '?'))}] "
                  f"{row.get('name','?')} | qty={row.get('quantity')} {row.get('unit','')} | "
                  f"rowRole={row.get('rowRole', row.get('cleaner_row_role','?'))}")
        lt = r.get("labelText")
        if lt:
            print("  --- labelText shape:", type(lt).__name__)
            if isinstance(lt, dict):
                for k, v in lt.items():
                    txt = v if isinstance(v, str) else json.dumps(v)
                    for line in txt.splitlines():
                        if any(t in line.lower() for t in ["omega", "protein", "blend", "mg", "mcg"]):
                            print(f"    [{k}]", line.strip()[:160])
            else:
                for line in str(lt).splitlines():
                    if any(t in line.lower() for t in ["omega", "protein", "blend", "mg", "mcg"]):
                        print("    ", line.strip()[:160])
        WANTED.discard(rid)
        if not WANTED:
            sys.exit(0)
print("NOT FOUND:", sorted(WANTED))
