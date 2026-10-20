"""Rows a candidate newly identifies (base canonical_id None -> candidate id), with the product's
score and rule changes. Read-only over two replay --full --blob record dirs.
argv: BASE_RECORDS CAND_RECORDS OUT_JSON"""
import collections, gzip, json, sys
from pathlib import Path

BASE, CAND, OUT = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]


def load(p):
    s = json.load(gzip.open(p, "rt"))
    iqd = (s.get("enriched") or {}).get("ingredient_quality_data") or {}
    rows = {}
    for r in (iqd.get("ingredients") or []) + (iqd.get("ingredients_skipped") or []):
        rows.setdefault(r.get("raw_source_path"), r)
    blob = s.get("blob") or {}
    rules = {w.get("source_rule_id") for w in (blob.get("warnings") or []) + (blob.get("warnings_profile_gated") or [])
             if isinstance(w, dict) and w.get("source_rule_id")}
    sc = s.get("scored") or {}
    pillars = {k: (v.get("score") if isinstance(v, dict) else v) for k, v in (sc.get("quality_pillars_v4") or {}).items()}
    return rows, rules, sc.get("quality_score_v4_100"), pillars, blob.get("product_name"), blob.get("product_safety_status")


groups, products = collections.defaultdict(list), []
for p in sorted(BASE.glob("*.json.gz")):
    q = CAND / p.name
    if not q.exists():
        continue
    (br, brules, bs, bp, name, bsafe), (cr, crules, cs, cp, _, csafe) = load(p), load(q)
    new = []
    for path, row in cr.items():
        before = br.get(path) or {}
        if row.get("canonical_id") and not before.get("canonical_id"):
            header = row.get("skip_reason") == "blend_header_total_weight_only"
            new.append({"path": path, "label": row.get("raw_source_text"), "id": row.get("canonical_id"),
                        "header": header, "standardName": row.get("standard_name")})
            groups[(header, row.get("raw_source_text"), row.get("canonical_id"))].append(p.name[:-8])
    if new or bs != cs or brules != crules or bsafe != csafe:
        products.append({"id": p.name[:-8], "name": name, "new_ids": new, "score": [bs, cs],
                         "pillars_changed": {k: [bp.get(k), cp.get(k)] for k in set(bp) | set(cp) if bp.get(k) != cp.get(k)},
                         "rules_added": sorted(crules - brules), "rules_removed": sorted(brules - crules), "safety": [bsafe, csafe]})
moved = [x for x in products if x["score"][0] != x["score"][1]]
print(f"products {len(products)} with a change; {sum(bool(x['new_ids']) for x in products)} with new identities; "
      f"{len(moved)} score moves; rules +{sum(len(x['rules_added']) for x in products)} -{sum(len(x['rules_removed']) for x in products)}; "
      f"safety changes {sum(x['safety'][0] != x['safety'][1] for x in products)}")
print("pillars moved:", collections.Counter(k for x in moved for k in x["pillars_changed"]))
for (header, label, cid), ids in sorted(groups.items(), key=lambda kv: -len(kv[1])):
    print(f"{len(ids):4d} {'HEADER' if header else 'row   '} {label!r:45} -> {cid}")
json.dump({"products": products, "groups": [[list(k), v] for k, v in groups.items()]}, open(OUT, "w"), indent=1)
