"""Interaction subjects present on a product's active label rows (cleaner/display id) for which the
pipeline emitted no warning from that subject's rule. Read-only.
argv: RECORDS_DIR INTERACTION_DB OUT_JSON"""
import collections, gzip, json, re, sqlite3, sys
from pathlib import Path

RECORDS, DB, OUT = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
con = sqlite3.connect(DB)
rule_of = collections.defaultdict(set)
for cid, rid in con.execute("select canonical_id, rule_id from profile_warning_rules"):
    rule_of[cid].add(rid)
pair_subjects = {r[0] for r in con.execute("select agent1_canonical_id from interactions union select agent2_canonical_id from interactions") if r[0]}


def norm(v):
    raw = str(v or "").strip().lower().replace("&", " and ").replace("'", "").replace("’", "")
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", raw)).strip("_") or None


missed = collections.Counter(); products = collections.defaultdict(set); reasons = collections.Counter()
examples = collections.defaultdict(list); covered = collections.Counter()
for p in sorted(RECORDS.glob("*.json.gz")):
    s = json.load(gzip.open(p, "rt"))
    blob, enr = s.get("blob") or {}, s.get("enriched") or {}
    if not blob:
        continue
    pid = p.name[:-8]
    fired = {w.get("source_rule_id") for w in (blob.get("warnings") or []) + (blob.get("warnings_profile_gated") or []) if isinstance(w, dict)}
    iqd = {r.get("raw_source_path"): r for r in (enr.get("ingredient_quality_data") or {}).get("ingredients") or [] if isinstance(r, dict)}
    for row in blob.get("display_ingredients") or []:
        if not isinstance(row, dict) or str(row.get("source_section") or "").lower() not in ("active", "activeingredients"):
            continue
        if str(row.get("display_disposition") or "").lower() == "other_ingredient":
            continue
        cid = norm(row.get("canonical_id"))
        if cid not in rule_of:
            continue
        if rule_of[cid] & fired:
            covered[cid] += 1
            continue
        e = iqd.get(row.get("raw_source_path")) or {}
        reason = e.get("identity_decision_reason") or ("enricher_same_id" if norm(e.get("canonical_id")) == cid else f"enricher_id={e.get('canonical_id')}")
        missed[cid] += 1; products[cid].add(pid); reasons[(cid, reason, row.get("display_disposition"))] += 1
        if len(examples[cid]) < 4:
            examples[cid].append({"id": pid, "name": blob.get("product_name"), "path": row.get("raw_source_path"),
                                  "row": row.get("display_label") or row.get("name"), "disposition": row.get("display_disposition"),
                                  "enricher_reason": reason, "qty": row.get("quantity"), "unit": row.get("unit")})
print("subject rows covered by a fired rule:", sum(covered.values()))
print("subject rows with NO warning from their rule:", sum(missed.values()), "in", len({x for v in products.values() for x in v}), "products")
for cid, n in missed.most_common(30):
    print(f"  {n:4d} rows {len(products[cid]):4d} products  {cid}")
print("by (subject, enricher reason, disposition):")
for k, n in reasons.most_common(40):
    print(f"  {n:4d} {k}")
json.dump({"missed": missed, "products": {k: sorted(v) for k, v in products.items()}, "reasons": [[list(k), n] for k, n in reasons.items()], "examples": examples}, open(OUT, "w"), indent=1, default=str)
