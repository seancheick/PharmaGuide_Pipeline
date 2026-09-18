#!/usr/bin/env python3
"""Measured catalog impact of the Wave 2 application (read-only).

Two changes land together and are measured together:

  * the scoring owner's null = 0.0 decision, which removes affirmative credit
    from every record whose direction is null (in the pipeline AND the floor);
  * six new reviewed records, of which only two score.

Baseline restores the pre-decision multiplier in memory and removes the new
records' matches; candidate is the working tree. Nothing is written back.

    python3 scripts/audits/evidence_expansion_2026_09/wave2_application_projection.py --slim <slim.jsonl>
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

PRIOR_NULL_MULTIPLIER = 0.25
NEW_RECORDS = {"INGR_WHITE_KIDNEY_BEAN": "common_bean_extract", "INGR_AMLA": "amla",
               "INGR_DEVILS_CLAW": "devils_claw", "INGR_SENNA": "senna",
               "INGR_D_MANNOSE": "d_mannose", "INGR_D_ASPARTIC_ACID": "d_aspartic_acid"}


def evidence_of(result: dict):
    pillars = result.get("quality_pillars_v4") or {}
    value = (pillars.get("evidence") or {}).get("score")
    return float(value) if isinstance(value, (int, float)) else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slim", required=True, type=Path)
    args = parser.parse_args()

    import clinical_applicability
    from score_supplements_v4 import score_product_v4
    from scoring_v4.modules import generic_evidence, probiotic_evidence

    registry = clinical_applicability.reviewed_entries()
    null_records = {eid for eid, entry in registry.items() if entry.get("effect_direction") == "null"}

    targets: dict[str, dict] = {}
    for line in args.slim.open():
        product = json.loads(line)
        accepted = {m["id"] for m in product["accepted_matches"]}
        identities = {row.get("canonical_id") for row in product["rows"]
                      if row.get("role_classification") == "active_scorable"}
        why = sorted((accepted & null_records)
                     | {eid for eid, cid in NEW_RECORDS.items() if cid in identities})
        if why:
            targets[product["dsld_id"]] = {"brand_dir": product["brand_dir"], "why": why,
                                           "brand": product["brand_name"], "name": product["product_name"],
                                           "module": product["module"]}
    print(f"products touched by the Wave 2 application: {len(targets)}", file=sys.stderr)

    # The enricher has not run, so the new records are not in any product's embedded matches.
    # Build the match the enricher WOULD build, from the registry, for the candidate scoring only.
    def new_matches(product):
        out = []
        for row in (product.get("ingredient_quality_data") or {}).get("ingredients") or []:
            if row.get("role_classification") != "active_scorable":
                continue
            canonical = row.get("canonical_id")
            for eid, cid in NEW_RECORDS.items():
                if canonical != cid:
                    continue
                entry = registry[eid]
                match = {k: entry.get(k) for k in
                         ("evidence_level", "study_type", "score_contribution", "health_goals_supported",
                          "key_endpoints", "effect_direction", "total_enrollment", "applicability",
                          "notes", "notable_studies", "references_structured", "primary_outcome")}
                match |= {"id": eid, "study_id": eid, "standard_name": entry["standard_name"],
                          "study_name": entry["standard_name"], "ingredient": row.get("name"),
                          "match_method": "standard_name", "matched_term": entry["standard_name"],
                          "matched_canonical_ids": [canonical],
                          "matched_source_row_refs": [row.get("raw_source_path")] if row.get("raw_source_path") else None}
                out.append({k: v for k, v in match.items() if v is not None})
        return out

    by_brand = collections.defaultdict(set)
    for dsld_id, meta in targets.items():
        by_brand[meta["brand_dir"]].add(dsld_id)

    rows = []
    for brand_dir, ids in sorted(by_brand.items()):
        for path in sorted(glob.glob(str(ROOT / f"scripts/products/output_{brand_dir}_enriched/enriched/*.json"))):
            for enriched in json.load(open(path)):
                dsld_id = str(enriched.get("dsld_id"))
                if dsld_id not in ids:
                    continue
                meta = targets[dsld_id]
                saved = (generic_evidence.EFFECT_DIRECTION_MULTIPLIERS["null"],
                         probiotic_evidence.EFFECT_DIRECTION_MULTIPLIERS["null"])
                generic_evidence.EFFECT_DIRECTION_MULTIPLIERS["null"] = PRIOR_NULL_MULTIPLIER
                probiotic_evidence.EFFECT_DIRECTION_MULTIPLIERS["null"] = PRIOR_NULL_MULTIPLIER
                try:
                    baseline = score_product_v4(json.loads(json.dumps(enriched)))
                finally:
                    (generic_evidence.EFFECT_DIRECTION_MULTIPLIERS["null"],
                     probiotic_evidence.EFFECT_DIRECTION_MULTIPLIERS["null"]) = saved

                candidate_blob = json.loads(json.dumps(enriched))
                evidence = candidate_blob.setdefault("evidence_data", {})
                matches = evidence.setdefault("clinical_matches", [])
                have = {m.get("id") or m.get("study_id") for m in matches}
                matches.extend(m for m in new_matches(candidate_blob) if m["id"] not in have)
                candidate = score_product_v4(candidate_blob)

                before, after = evidence_of(baseline), evidence_of(candidate)
                rows.append({"dsld_id": dsld_id, "brand": meta["brand"], "product_name": meta["name"],
                             "module": meta["module"], "why": meta["why"],
                             "evidence_before": before, "evidence_after": after,
                             "evidence_delta": None if None in (before, after) else round(after - before, 2),
                             "total_before": baseline.get("quality_score_v4_100"),
                             "total_after": candidate.get("quality_score_v4_100")})
        print(f"{brand_dir}: scored {len(rows)}", file=sys.stderr, flush=True)

    changed = [r for r in rows if r["evidence_delta"] not in (None, 0)]
    ups = [r for r in changed if r["evidence_delta"] > 0]
    downs = [r for r in changed if r["evidence_delta"] < 0]
    payload = {"_metadata": {
        "products_touched": len(targets), "products_scored": len(rows),
        "products_changed": len(changed), "products_up": len(ups), "products_down": len(downs),
        "mean_delta_changed": round(sum(r["evidence_delta"] for r in changed) / len(changed), 3) if changed else 0,
        "largest_rise": max((r["evidence_delta"] for r in changed), default=0),
        "largest_drop": min((r["evidence_delta"] for r in changed), default=0),
        "changed_by_reason": dict(collections.Counter(w for r in changed for w in r["why"])),
        "note": "Read-only. null restored to 0.25 for the baseline; new records' matches injected for the "
                "candidate exactly as the enricher would build them. Nothing written back."},
        "largest_rises": sorted(ups, key=lambda r: -r["evidence_delta"])[:20],
        "largest_drops": sorted(downs, key=lambda r: r["evidence_delta"])[:20],
        "products": rows}
    (OUT / "wave2_application_projection.json").write_text(json.dumps(payload, indent=1))
    print(json.dumps(payload["_metadata"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
