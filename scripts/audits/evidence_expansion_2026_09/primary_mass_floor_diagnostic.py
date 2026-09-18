#!/usr/bin/env python3
"""Who reaches Evidence through the primary-mass floor, and how much they get (read-only).

The calibration question this exists to answer, raised by the amla canary:

    should a positive_weak systematic-review record be able to take ~66% of the
    public Evidence pillar simply by being the mass-dominant active?

It measures; it changes nothing. No constant here is touched: not the 14.0 floor,
not the 0.85 direction weight, not the archetype reference, not the 20-point scale.

Per product that receives a floor, it reports the direction and study type that
anchored it, the raw floor value, the archetype and its reference maximum, the
rescaled public Evidence value, whether the pipeline also contributed, and where
that lands in the corpus-wide Evidence distribution.

    python3 scripts/audits/evidence_expansion_2026_09/primary_mass_floor_diagnostic.py --slim <slim.jsonl>
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slim", required=True, type=Path)
    parser.add_argument("--out", default="primary_mass_floor_diagnostic.json")
    args = parser.parse_args()

    from scoring_v4.modules import generic_evidence as ge
    import clinical_applicability as ca

    registry = ca.reviewed_entries()
    by_brand = collections.defaultdict(list)
    shipped_evidence = []
    for line in args.slim.open():
        product = json.loads(line)
        shipped_evidence.append(product.get("evidence") or 0.0)
        by_brand[product["brand_dir"]].append(product["dsld_id"])

    corpus = sorted(shipped_evidence)

    def percentile_of(value: float) -> float:
        below = sum(1 for v in corpus if v < value)
        return round(100 * below / len(corpus), 1) if corpus else 0.0

    rows = []
    for brand_dir in sorted(by_brand):
        wanted = set(by_brand[brand_dir])
        for path in sorted(glob.glob(str(ROOT / f"scripts/products/output_{brand_dir}_enriched/enriched/*.json"))):
            for enriched in json.load(open(path)):
                dsld_id = str(enriched.get("dsld_id"))
                if dsld_id not in wanted:
                    continue
                payload = ge.score_evidence(json.loads(json.dumps(enriched)), apply_primary_floor=True)
                components = payload.get("components") or {}
                floor = components.get("primary_evidence_floor")
                if not floor:
                    continue
                metadata = payload.get("metadata") or {}
                canonical = metadata.get("primary_evidence_floor_canonical") or metadata.get(
                    "primary_evidence_floor_ingredient")
                entry = next((registry[eid] for eid in registry
                              if ge._canonical_text(registry[eid].get("standard_name", "")) ==
                              ge._canonical_text(canonical or "")), None)
                pipeline = components.get("clinical_evidence_pipeline") or 0.0
                reference = components.get("reference")
                rows.append({
                    "dsld_id": dsld_id, "brand_dir": brand_dir,
                    "floor_anchor_canonical": canonical,
                    "direction": (entry or {}).get("effect_direction"),
                    "study_type": (entry or {}).get("study_type"),
                    "evidence_level": (entry or {}).get("evidence_level"),
                    "raw_floor": round(float(floor), 3),
                    "pipeline_also_contributed": round(float(pipeline), 3),
                    "raw_evidence_used": components.get("raw_evidence"),
                    "archetype": components.get("archetype"),
                    "archetype_reference_max": reference,
                    "public_evidence": payload.get("score"),
                    "public_evidence_percentile": percentile_of(payload.get("score") or 0.0),
                    "share_of_pillar_pct": round(100 * (payload.get("score") or 0) / 20, 1),
                })
        print(f"{brand_dir}: {len(rows)} floored so far", file=sys.stderr, flush=True)

    by_direction = collections.Counter(r["direction"] for r in rows)
    by_study = collections.Counter(r["study_type"] for r in rows)
    weak = [r for r in rows if r["direction"] == "positive_weak"]
    payload = {"_metadata": {
        "question": "Should a positive_weak systematic-review record reach ~66% of the public Evidence "
                    "pillar through the primary-mass floor plus the archetype rescale?",
        "measured_only": "No constant was changed: not the 14.0/11.0 floors, not the direction weights, "
                         "not the archetype references, not the 20-point scale.",
        "products_scored": len(corpus),
        "products_receiving_a_primary_mass_floor": len(rows),
        "by_direction": dict(by_direction), "by_study_type": dict(by_study),
        "positive_weak_products": len(weak),
        "positive_weak_median_public_evidence": round(statistics.median(
            [r["public_evidence"] for r in weak]), 2) if weak else None,
        "positive_weak_median_share_of_pillar_pct": round(statistics.median(
            [r["share_of_pillar_pct"] for r in weak]), 1) if weak else None,
        "median_public_evidence_all_floored": round(statistics.median(
            [r["public_evidence"] for r in rows]), 2) if rows else None,
        "floored_products_where_pipeline_added_nothing": sum(
            1 for r in rows if not r["pipeline_also_contributed"]),
    }, "products": rows}
    (OUT / args.out).write_text(json.dumps(payload, indent=1))
    print(json.dumps(payload["_metadata"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
