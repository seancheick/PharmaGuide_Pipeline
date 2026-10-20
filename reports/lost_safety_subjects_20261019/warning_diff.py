"""Per-product interaction warning diff between two replay --full --blob record dirs. Read-only.

Lists, for every product, the profile rules (blob warnings source_rule_id) and the
(rule, target, severity) hits of enriched interaction_profile.ingredient_alerts that were
added or removed, with the label row each hit came from.
argv: BASE_RECORDS CAND_RECORDS OUT_JSON
"""
import gzip, json, sys
from pathlib import Path

BASE, CAND, OUT = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]


def load(path):
    s = json.load(gzip.open(path, "rt"))
    blob, enr = s.get("blob") or {}, s.get("enriched") or {}
    rules = sorted({w.get("source_rule_id") for w in (blob.get("warnings") or []) + (blob.get("warnings_profile_gated") or [])
                    if isinstance(w, dict) and w.get("source_rule_id")})
    hits = set()
    for a in (enr.get("interaction_profile") or {}).get("ingredient_alerts") or []:
        for key, field in (("condition_hits", "condition_id"), ("drug_class_hits", "drug_class_id")):
            for h in a.get(key) or []:
                hits.add((a.get("rule_id"), h.get(field), h.get("severity"), a.get("ingredient_name")))
    return {"name": blob.get("product_name"), "rules": rules, "hits": hits, "score": (s.get("scored") or {}).get("quality_score_v4_100"),
            "safety": blob.get("product_safety_status")}


out, totals = [], {"products": 0, "changed": 0, "rules_added": 0, "rules_removed": 0, "score_changed": 0, "safety_changed": 0}
for p in sorted(BASE.glob("*.json.gz")):
    q = CAND / p.name
    if not q.exists():
        continue
    a, b = load(p), load(q)
    totals["products"] += 1
    added, removed = sorted(set(b["rules"]) - set(a["rules"])), sorted(set(a["rules"]) - set(b["rules"]))
    hits_added = sorted(b["hits"] - a["hits"], key=str)
    hits_removed = sorted(a["hits"] - b["hits"], key=str)
    if not (added or removed or hits_added or hits_removed or a["score"] != b["score"] or a["safety"] != b["safety"]):
        continue
    totals["changed"] += 1
    totals["rules_added"] += len(added); totals["rules_removed"] += len(removed)
    totals["score_changed"] += a["score"] != b["score"]; totals["safety_changed"] += a["safety"] != b["safety"]
    out.append({"id": p.name[:-8], "name": a["name"], "rules_added": added, "rules_removed": removed,
                "hits_added": hits_added, "hits_removed": hits_removed,
                "score": [a["score"], b["score"]], "safety": [a["safety"], b["safety"]]})
print(json.dumps(totals))
for r in out:
    print(r["id"], (r["name"] or "")[:40], "+", r["rules_added"], "-", r["rules_removed"],
          "hits +%d -%d" % (len(r["hits_added"]), len(r["hits_removed"])), "score", r["score"], "safety", r["safety"])
json.dump({"totals": totals, "products": out}, open(OUT, "w"), indent=1, default=list)
