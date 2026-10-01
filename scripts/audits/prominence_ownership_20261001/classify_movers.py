"""Classify every changed product between two verified replay captures.

usage: formal_classify.py <checkout> base.jsonl cand.jsonl out.json out.md
"""
import json, sys, collections
sys.path.insert(0, sys.argv[1] + "/scripts")
sys.path.insert(0, sys.argv[1] + "/scripts/audits/quality_redesign")
import replay
from scoring_v4.quality_score import _tier, shipped_whole_score

base = {r["id"]: r for r in replay.read_rows(sys.argv[2])}
cand = {r["id"]: r for r in replay.read_rows(sys.argv[3])}
assert base.keys() == cand.keys(), "id sets differ"
for k in base:
    assert base[k]["input_sha256"] == cand[k]["input_sha256"], k


def ev(r):
    dims = (((r.get("reasons") or {}).get("module") or {}).get("dimensions") or {})
    e = dims.get("evidence") or {}
    md = e.get("metadata") or {}
    return e, (md.get("generic_evidence_metadata") or md)


def tier(r):
    return _tier(shipped_whole_score(r["total"])) if r.get("total") is not None else None


def pill(r, p):
    return ((r.get("pillars") or {}).get(p) or {}).get("score")


def rec_set(md):
    out = set()
    for m in md.get("recovered_matches") or []:
        if isinstance(m, dict):
            out.add((m.get("id") or m.get("entry_id"), json.dumps(m.get("matched_source_row_refs") or m.get("source_row_refs"), sort_keys=True)))
        else:
            out.add((str(m), ""))
    return out


def diff_paths(a, b, path=""):
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in sorted(set(a) | set(b)):
            out += diff_paths(a.get(k), b.get(k), f"{path}.{k}" if path else k)
        return out
    return [] if a == b else [path]


rows, counts = [], collections.Counter()
for k in sorted(base, key=lambda x: (len(x), x)):
    b, c = base[k], cand[k]
    if b == c:
        counts["identical"] += 1
        continue
    be, bmd = ev(b)
    ce, cmd = ev(c)
    causes = []
    if (bmd.get("primary_evidence_floor"), bmd.get("primary_evidence_floor_canonical")) != (cmd.get("primary_evidence_floor"), cmd.get("primary_evidence_floor_canonical")):
        causes.append("floor")
    if (bmd.get("nutrition_authority_canonical"), bmd.get("nutrition_authority_floor_applied")) != (cmd.get("nutrition_authority_canonical"), cmd.get("nutrition_authority_floor_applied")):
        causes.append("authority")
    if rec_set(bmd) != rec_set(cmd):
        causes.append("recovery")
    if sorted(bmd.get("evidence_owner_canonicals") or []) != sorted(cmd.get("evidence_owner_canonicals") or []):
        causes.append("owners")
    if bmd.get("matched_entries") != cmd.get("matched_entries"):
        causes.append("matched_entries")
    paths = diff_paths(b, c)
    other = sorted({".".join(p.split(".")[:3]) for p in paths
                    if not p.startswith("reasons.module.dimensions.evidence")
                    and not p.startswith("pillars.evidence")
                    and p not in ("total",) and not p.startswith("reasons.module.score_100")
                    and not p.startswith("reasons.module.raw_score_100")})
    pmoves = {p: [pill(b, p), pill(c, p)] for p in replay.PILLARS if pill(b, p) != pill(c, p)}
    item = {
        "id": k, "name": b.get("name"), "route": b.get("route"), "status": [b.get("status"), c.get("status")],
        "total": [b.get("total"), c.get("total")], "tier": [tier(b), tier(c)], "pillars": pmoves,
        "floor": [[bmd.get("primary_evidence_floor"), bmd.get("primary_evidence_floor_canonical")],
                  [cmd.get("primary_evidence_floor"), cmd.get("primary_evidence_floor_canonical")]],
        "authority": [bmd.get("nutrition_authority_canonical"), cmd.get("nutrition_authority_canonical")],
        "recovered_removed": sorted(map(list, rec_set(bmd) - rec_set(cmd))),
        "recovered_added": sorted(map(list, rec_set(cmd) - rec_set(bmd))),
        "owners_removed": sorted(set(bmd.get("evidence_owner_canonicals") or []) - set(cmd.get("evidence_owner_canonicals") or [])),
        "owners_added": sorted(set(cmd.get("evidence_owner_canonicals") or []) - set(bmd.get("evidence_owner_canonicals") or [])),
        "causes": causes, "non_evidence_paths": other[:12], "n_paths": len(paths),
    }
    rows.append(item)
    counts["changed"] += 1
    if b.get("total") != c.get("total"):
        counts["total_moved"] += 1
        counts["up" if (c.get("total") or 0) > (b.get("total") or 0) else "down"] += 1
    if tier(b) != tier(c):
        counts[f"tier {tier(b)} -> {tier(c)}"] += 1
    for f in ("status", "route"):
        if b.get(f) != c.get(f):
            counts[f + "_change"] += 1
    for p in pmoves:
        counts["pillar_" + p] += 1
    counts["cause:" + ("+".join(causes) or "metadata_only")] += 1
    if other:
        counts["has_non_evidence_paths"] += 1

summary = {"products": len(base), **dict(sorted(counts.items()))}
json.dump({"summary": summary, "changed": rows}, open(sys.argv[4], "w"), indent=1, default=str)

with open(sys.argv[5], "w") as fh:
    fh.write("| id | product | total | tier | Evidence | floor (value, canonical) | authority | recovery -/+ | owners -/+ | cause |\n|---|---|---|---|---|---|---|---|---|---|\n")
    for r in rows:
        e = r["pillars"].get("evidence") or ["=", "="]
        fl = r["floor"]
        fls = "=" if fl[0] == fl[1] else f"{fl[0][0]} {fl[0][1]} → {fl[1][0]} {fl[1][1]}"
        au = "=" if r["authority"][0] == r["authority"][1] else f"{r['authority'][0]} → {r['authority'][1]}"
        rec = f"-{[x[0] for x in r['recovered_removed']]} +{[x[0] for x in r['recovered_added']]}" if (r["recovered_removed"] or r["recovered_added"]) else "="
        ow = f"-{r['owners_removed']} +{r['owners_added']}" if (r["owners_removed"] or r["owners_added"]) else "="
        tot = "=" if r["total"][0] == r["total"][1] else f"{r['total'][0]} → {r['total'][1]}"
        ti = "=" if r["tier"][0] == r["tier"][1] else f"{r['tier'][0]} → {r['tier'][1]}"
        ev_s = "=" if e[0] == e[1] else f"{e[0]} → {e[1]}"
        name = str(r["name"]).replace("|", "/")
        cause = "+".join(r["causes"]) or ("metadata: " + ", ".join(r["non_evidence_paths"][:3]))
        fh.write(f"| {r['id']} | {name} | {tot} | {ti} | {ev_s} | {fls} | {au} | {rec} | {ow} | {cause} |\n")
print(json.dumps(summary, indent=1))
