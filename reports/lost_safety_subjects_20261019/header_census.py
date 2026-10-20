"""Every blend-header row that carries a specific identity, with its declared forms and children,
and whether that identity has an interaction rule. Read-only. argv: RECORDS_DIR RULES_JSON OUT_JSON"""
import collections, gzip, json, sys
from pathlib import Path

RECORDS, RULES, OUT = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
ruled = {(r.get("subject_ref") or {}).get("canonical_id") for r in json.load(open(RULES))["interaction_rules"]}
groups = collections.defaultdict(list)
for p in sorted(RECORDS.glob("*.json.gz")):
    iqd = (json.load(gzip.open(p, "rt")).get("enriched") or {}).get("ingredient_quality_data") or {}
    rows = (iqd.get("ingredients") or []) + (iqd.get("ingredients_skipped") or [])
    seen = set()
    for r in rows:
        cid = str(r.get("canonical_id") or "")
        path = r.get("raw_source_path") or ""
        if path in seen or r.get("skip_reason") != "blend_header_total_weight_only" or not cid or cid.upper().startswith("BLEND_"):
            continue
        seen.add(path)
        kids = sorted({str(k.get("canonical_id")) for k in rows if str(k.get("raw_source_path") or "").startswith(path + ".")})
        forms = [f.get("name") for f in (r.get("raw_taxonomy") or {}).get("forms") or []]
        groups[(cid, r.get("raw_source_text"), r.get("identity_disposition"))].append(
            {"id": p.name[:-8], "qty": r.get("quantity"), "unit": r.get("unit"), "forms": forms, "children": kids})
out = []
for (cid, label, disp), items in sorted(groups.items(), key=lambda kv: -len(kv[1])):
    out.append({"canonical_id": cid, "label": label, "disposition": disp, "has_rule": cid in ruled,
                "products": len(items), "example": items[0]})
print(len(out), "header identity groups;", sum(o["products"] for o in out), "rows;",
      sum(o["products"] for o in out if o["has_rule"]), "rows whose identity has a rule")
for o in out:
    if o["has_rule"]:
        e = o["example"]
        print(f'{o["products"]:3d} {o["canonical_id"]:22} {o["disposition"]:13} {o["label"]!r:45} forms={e["forms"][:4]} kids={e["children"][:5]} {e["id"]}')
json.dump(out, open(OUT, "w"), indent=1)
