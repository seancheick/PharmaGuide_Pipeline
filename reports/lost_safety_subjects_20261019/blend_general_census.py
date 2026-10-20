"""Rows whose supplied (cleaner) identity is a specific substance with an interaction rule but whose
enricher identity is BLEND_GENERAL (a "Proprietary Blend" DSLD group repair). Read-only.
argv: RECORDS_DIR RULES_JSON OUT_JSON"""
import collections, gzip, json, sys
from pathlib import Path

RECORDS, RULES, OUT = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
ruled = {(r.get("subject_ref") or {}).get("canonical_id") for r in json.load(open(RULES))["interaction_rules"]}
rows, by_before = [], collections.Counter()
for p in sorted(RECORDS.glob("*.json.gz")):
    s = json.load(gzip.open(p, "rt"))
    iqd = (s.get("enriched") or {}).get("ingredient_quality_data") or {}
    seen = set()
    for r in (iqd.get("ingredients") or []) + (iqd.get("ingredients_skipped") or []):
        before, path = r.get("canonical_id_before"), r.get("raw_source_path")
        if path in seen or r.get("canonical_id") != "BLEND_GENERAL" or not before or str(before).upper().startswith("BLEND_"):
            continue
        seen.add(path)
        rows.append({"id": p.name[:-8], "product": (s.get("blob") or {}).get("product_name"), "path": path,
                     "label": r.get("raw_source_text"), "before": before, "has_rule": before in ruled,
                     "group": (r.get("raw_taxonomy") or {}).get("ingredientGroup"),
                     "forms": [f.get("name") for f in (r.get("raw_taxonomy") or {}).get("forms") or []]})
        by_before[(before, before in ruled)] += 1
print(len(rows), "rows;", sum(r["has_rule"] for r in rows), "with a rule on the supplied identity, in",
      len({r["id"] for r in rows if r["has_rule"]}), "products")
for (b, h), n in by_before.most_common():
    if h:
        print(f"  {n:4d} {b}")
json.dump(rows, open(OUT, "w"), indent=1)
