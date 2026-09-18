#!/usr/bin/env python3
"""Read-only projection: what changes if a null direction earns no affirmative credit.

Runs the PRODUCTION scorer (``score_supplements_v4.score_product_v4``) twice over every
product that matches one of the null-direction records — once as shipped, once with the
null multiplier set to 0 in both modules that read it — and reports the difference.

Nothing is implemented. The config and the registry are untouched; the multiplier is
patched in memory for the duration of the run only.

    python3 scripts/audits/evidence_expansion_2026_09/null_direction_projection.py --slim <slim.jsonl>
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))

NULL_RECORDS = ("INGR_VITAMIN_B12", "INGR_SAW_PALMETTO", "PRECLIN_DIM", "INGR_BORON")


def evidence_of(result: dict) -> float | None:
    pillars = result.get("quality_pillars_v4") or {}
    value = (pillars.get("evidence") or {}).get("score")
    return float(value) if isinstance(value, (int, float)) else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slim", required=True, type=Path)
    args = parser.parse_args()

    from score_supplements_v4 import score_product_v4
    from scoring_v4.modules import generic_evidence, probiotic_evidence

    targets: dict[str, dict] = {}
    for line in args.slim.open():
        product = json.loads(line)
        hits = [m["id"] for m in product["accepted_matches"] if m["id"] in NULL_RECORDS]
        if hits:
            targets[product["dsld_id"]] = {"brand_dir": product["brand_dir"], "records": hits,
                                           "brand": product["brand_name"], "name": product["product_name"],
                                           "module": product["module"], "shipped_evidence": product["evidence"]}
    print(f"products matching a null record: {len(targets)}", file=sys.stderr)

    rows = []
    by_brand = collections.defaultdict(list)
    for dsld_id, meta in targets.items():
        by_brand[meta["brand_dir"]].append(dsld_id)

    for brand_dir, ids in sorted(by_brand.items()):
        wanted = set(ids)
        for path in sorted(glob.glob(str(ROOT / f"scripts/products/output_{brand_dir}_enriched/enriched/*.json"))):
            for enriched in json.load(open(path)):
                dsld_id = str(enriched.get("dsld_id"))
                if dsld_id not in wanted:
                    continue
                meta = targets[dsld_id]
                baseline = score_product_v4(json.loads(json.dumps(enriched)))
                saved = (generic_evidence.EFFECT_DIRECTION_MULTIPLIERS["null"],
                         probiotic_evidence.EFFECT_DIRECTION_MULTIPLIERS["null"])
                generic_evidence.EFFECT_DIRECTION_MULTIPLIERS["null"] = 0.0
                probiotic_evidence.EFFECT_DIRECTION_MULTIPLIERS["null"] = 0.0
                try:
                    candidate = score_product_v4(json.loads(json.dumps(enriched)))
                finally:
                    (generic_evidence.EFFECT_DIRECTION_MULTIPLIERS["null"],
                     probiotic_evidence.EFFECT_DIRECTION_MULTIPLIERS["null"]) = saved
                before_ev, after_ev = evidence_of(baseline), evidence_of(candidate)
                before_total = baseline.get("quality_score_v4_100")
                after_total = candidate.get("quality_score_v4_100")
                rows.append({
                    "dsld_id": dsld_id, "brand": meta["brand"], "product_name": meta["name"],
                    "module": meta["module"], "null_records": meta["records"],
                    "evidence_before": before_ev, "evidence_after": after_ev,
                    "evidence_delta": None if None in (before_ev, after_ev) else round(after_ev - before_ev, 2),
                    "total_before": before_total, "total_after": after_total,
                    "total_delta": None if None in (before_total, after_total) else round(
                        after_total - before_total, 2)})
        print(f"{brand_dir}: scored {len(rows)}", file=sys.stderr, flush=True)

    changed = [r for r in rows if r["evidence_delta"] not in (None, 0)]
    per_record = collections.Counter()
    for row in changed:
        for record in row["null_records"]:
            per_record[record] += 1
    deltas = [r["evidence_delta"] for r in changed if r["evidence_delta"] is not None]
    total_deltas = [r["total_delta"] for r in changed if r["total_delta"] is not None]
    by_module = collections.Counter(r["module"] for r in changed)

    payload = {"_metadata": {
        "products_matching_a_null_record": len(targets),
        "products_scored": len(rows),
        "products_with_an_evidence_change": len(changed),
        "mean_evidence_delta": round(sum(deltas) / len(deltas), 3) if deltas else 0,
        "largest_evidence_drop": min(deltas) if deltas else 0,
        "mean_total_score_delta": round(sum(total_deltas) / len(total_deltas), 3) if total_deltas else 0,
        "largest_total_drop": min(total_deltas) if total_deltas else 0,
        "changed_by_module": dict(by_module),
        "changed_by_record": dict(per_record),
        "candidate": "null direction contributes 0 affirmative efficacy credit (current: 0.25)",
        "note": "Read-only. Config and registry untouched; the multiplier was patched in memory only."},
        "largest_movers": sorted(changed, key=lambda r: r["evidence_delta"] or 0)[:30],
        "products": rows}
    (OUT / "null_direction_projection.json").write_text(json.dumps(payload, indent=1))
    print(json.dumps(payload["_metadata"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
