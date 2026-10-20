"""All score, pillar, rule and safety-status differences between two replay --full --blob record dirs.
argv: BASE_RECORDS CAND_RECORDS"""
import gzip, json, sys
from pathlib import Path
B, C = Path(sys.argv[1]), Path(sys.argv[2])
def load(p):
    s = json.load(gzip.open(p, "rt"))
    blob = s.get("blob") or {}
    rules = {w.get("source_rule_id") for w in (blob.get("warnings") or []) + (blob.get("warnings_profile_gated") or [])
             if isinstance(w, dict) and w.get("source_rule_id")}
    sc = s.get("scored") or {}
    pil = {k: (v.get("score") if isinstance(v, dict) else v) for k, v in (sc.get("quality_pillars_v4") or {}).items()}
    iqd = (s.get("enriched") or {}).get("ingredient_quality_data") or {}
    ids = {(r.get("raw_source_path"), r.get("raw_source_text")): r.get("canonical_id") for r in (iqd.get("ingredients") or []) + (iqd.get("ingredients_skipped") or [])}
    return dict(rules=rules, score=sc.get("quality_score_v4_100"), status=sc.get("quality_score_status"), pil=pil,
                safety=blob.get("product_safety_status"), name=blob.get("product_name"), ids=ids)
n = moves = 0; add = rem = 0; safety = []
for p in sorted(B.glob("*.json.gz")):
    q = C / p.name
    if not q.exists(): print("MISSING", p.name); continue
    n += 1; a, b = load(p), load(q)
    pid = p.name.split(".")[0]
    if a["safety"] != b["safety"]: safety.append((pid, a["safety"], b["safety"]))
    ra, rr = b["rules"] - a["rules"], a["rules"] - b["rules"]; add += len(ra); rem += len(rr)
    idch = [(k[1], a["ids"].get(k), b["ids"].get(k)) for k in set(a["ids"]) | set(b["ids"]) if a["ids"].get(k) != b["ids"].get(k)]
    if (a["score"], a["status"]) != (b["score"], b["status"]):
        moves += 1
        dp = {k: (a["pil"].get(k), b["pil"].get(k)) for k in set(a["pil"]) | set(b["pil"]) if a["pil"].get(k) != b["pil"].get(k)}
        print(f"MOVE\t{pid}\t{(a['name'] or '')[:40]}\t{a['score']}->{b['score']}\t{dp}\t{idch[:4]}")
    if ra or rr: print(f"RULES\t{pid}\t{(a['name'] or '')[:40]}\t+{sorted(ra)}\t-{sorted(rr)}\t{idch[:4]}")
print(f"products {n} score_moves {moves} rules +{add} -{rem} safety_changes {safety}")
