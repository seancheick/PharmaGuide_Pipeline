#!/usr/bin/env python3
"""Cause census of the products withheld between two full-artifact replay baselines.

Reads the two replay projections (one JSON line per product) and the kept per-product stage
records beside them (``<baseline>.records/<id>.json.gz``, written by
scripts/audits/quality_redesign/replay.py::keep_records) and classifies every product whose
status moved scored -> not_scored by the Dose owner's own fields. No production module is
imported; every number in REPORT.md comes from this script.

    $PG_PYTHON scripts/audits/dose_hold_census_20261019/census.py \
        --old /Users/seancheick/pg_quality/full_artifact_baseline_20261018/baseline_5fb2be1ca.jsonl \
        --new /Users/seancheick/pg_quality/corpus_20261019_post167/baseline_951a05415_unpinned.jsonl
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
GAP = "pediatric_reference_gap"


def rows(path):
    with open(path) as fh:
        for line in fh:
            yield json.loads(line)


def record(path, pid):
    with gzip.open(Path(str(path) + ".records") / f"{pid}.json.gz", "rt", encoding="utf-8") as fh:
        return json.load(fh)


def tier(total):
    return "85+" if total >= 85 else "70-84" if total >= 70 else "55-69" if total >= 55 else "<55"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--old", required=True)
    ap.add_argument("--new", required=True)
    args = ap.parse_args()
    old = {r["id"]: r for r in rows(args.old)}
    new = {r["id"]: r for r in rows(args.new)}
    assert set(old) == set(new), "baselines must cover the same products"
    out = {"old": args.old, "new": args.new, "products": len(new)}
    out["status_old"] = dict(collections.Counter(r["status"] for r in old.values()))
    out["status_new"] = dict(collections.Counter(r["status"] for r in new.values()))
    out["transitions"] = {f"{old[i]['status']}->{new[i]['status']}": n for (i, n) in
                          collections.Counter(i for i in new if old[i]["status"] != new[i]["status"]).items()}
    out["transitions"] = dict(collections.Counter(f"{old[i]['status']}->{new[i]['status']}" for i in new
                                                  if old[i]["status"] != new[i]["status"]))
    flipped = sorted(i for i in new if old[i]["status"] == "scored" and new[i]["status"] == "not_scored")
    out["flipped"] = len(flipped)

    buckets = collections.defaultdict(list)
    gap_rows = collections.Counter()
    gap_units = collections.Counter()
    gap_members = collections.Counter()
    gap_payload = collections.Counter()
    target_groups = collections.Counter()
    impact_tier = collections.Counter()
    impact_route = collections.Counter()
    impact_brand = collections.Counter()
    old_totals = []
    drivers = {}
    for pid in flipped:
        rec = record(args.new, pid)
        enriched, scored, cleaned = rec["enriched"], rec["scored"], rec["cleaned"]
        readiness = scored["assessment_readiness"]
        dose = readiness.get("dose") or {}
        assessments = [a for a in (enriched.get("rda_ul_data") or {}).get("dose_assessments") or [] if isinstance(a, dict)]
        gaps = [a for a in assessments if a.get("reason_code") == GAP]
        if gaps:
            bucket = "pediatric_reference_gap"
            adequacy = {a.get("canonical_id"): a for a in (enriched.get("rda_ul_data") or {}).get("adequacy_results") or [] if isinstance(a, dict)}
            for a in gaps:
                gap_rows[a.get("canonical_id")] += 1
                gap_units[a.get("source_unit")] += 1
                pop = (adequacy.get(a.get("canonical_id")) or {}).get("ul_population") or {}
                gap_members[tuple(pop.get("members") or [])] += 1
                gap_payload[str(pop.get("reference_gap"))] += 1
            for group in cleaned.get("targetGroups") or []:
                target_groups[group] += 1
            total = old[pid]["total"]
            old_totals.append(total)
            impact_tier[tier(total)] += 1
            impact_route[new[pid]["route"]] += 1
            impact_brand[enriched.get("brandName") or enriched.get("brand_name")] += 1
            if len(drivers) < 3:
                a = gaps[0]
                drivers[pid] = {"name": cleaned.get("fullName"), "targetGroups": cleaned.get("targetGroups"),
                                "driver_row": {k: a.get(k) for k in ("source_path", "ingredient", "source_value", "source_unit", "ul_value", "ul_assessment_status", "readiness", "reason_code")},
                                "ul_population": (adequacy.get(a.get("canonical_id")) or {}).get("ul_population"),
                                "old_total": old[pid]["total"], "old_dose_readiness": (record(args.old, pid)["scored"].get("assessment_readiness") or {}).get("dose", {}).get("readiness")}
        else:
            reason = dose.get("reason_code") or (dose.get("measurements") or [{}])[0].get("reason_code") if dose.get("readiness") == "incomplete" else None
            unavailable = readiness.get("unavailable_reasons") or []
            bucket = reason or (unavailable[0] if unavailable else "unknown")
        buckets[bucket].append(pid)

    out["buckets"] = {k: {"count": len(v), "ids": v if len(v) <= 10 else v[:10] + ["..."]} for k, v in buckets.items()}
    out["gap"] = {
        "rows": sum(gap_rows.values()),
        "rows_by_nutrient": gap_rows.most_common(25),
        "rows_by_unit": gap_units.most_common(),
        "ul_population_members": [(list(k), n) for k, n in gap_members.most_common()],
        "reference_gap_payload": gap_payload.most_common(),
        "target_groups": target_groups.most_common(12),
        "old_total_median": statistics.median(old_totals) if old_totals else None,
        "old_total_range": [min(old_totals), max(old_totals)] if old_totals else None,
        "old_tier": dict(impact_tier),
        "route": dict(impact_route),
        "brands": impact_brand.most_common(10),
        "drivers": drivers,
    }

    # Whole-corpus context: products with a gap row that still scored, and scored products whose
    # Dose receipt is incomplete (the sports protein case).
    scored_with_gap = collections.Counter()
    scored_with_gap_examples = []
    incomplete_receipt = collections.Counter()
    incomplete_receipt_examples = []
    child_tag_products = collections.Counter()
    for pid, row in new.items():
        rec = record(args.new, pid)
        enriched, scored, cleaned = rec["enriched"], rec["scored"], rec["cleaned"]
        groups = cleaned.get("targetGroups") or []
        childish = any(any(w in str(g).lower() for w in ("child", "infant", "boys", "girls")) for g in groups)
        if childish:
            child_tag_products[row["status"]] += 1
        assessments = [a for a in (enriched.get("rda_ul_data") or {}).get("dose_assessments") or [] if isinstance(a, dict)]
        gaps = [a for a in assessments if a.get("reason_code") == GAP]
        if gaps and row["status"] == "scored":
            evidence_rows = {a.get("source_row_ref"): a for a in (scored["assessment_readiness"].get("evidence") or {}).get("ingredient_assessments") or []}
            material_in_evidence = any((evidence_rows.get(a.get("source_path")) or {}).get("material") for a in gaps)
            scored_with_gap[(scored.get("_v4_module"), "gap row evidence-material" if material_in_evidence else "gap row not evidence-material")] += 1
            if len(scored_with_gap_examples) < 4:
                scored_with_gap_examples.append((pid, cleaned.get("fullName"), [(a.get("ingredient"), a.get("source_value"), a.get("source_unit")) for a in gaps][:3]))
        if row["status"] == "scored":
            dose_pillar = (scored.get("quality_pillars_v4") or {}).get("dose") or {}
            receipt = ((dose_pillar.get("explanation") or {}).get("dose_receipt") or {})
            if receipt.get("assessment_status") == "incomplete":
                incomplete_receipt[(row["route"], dose_pillar.get("score"), tuple(c.get("assessment") for c in receipt.get("contributions") or []))] += 1
                if len(incomplete_receipt_examples) < 6:
                    incomplete_receipt_examples.append((pid, cleaned.get("fullName"), old[pid]["total"], row["total"],
                                                        (scored["assessment_readiness"].get("dose") or {}).get("readiness")))
    out["context"] = {
        "child_tag_products_by_status": dict(child_tag_products),
        "scored_with_gap_rows": [(list(k), n) for k, n in scored_with_gap.most_common()],
        "scored_with_gap_examples": scored_with_gap_examples,
        "scored_with_incomplete_dose_receipt": [(list(k), n) for k, n in incomplete_receipt.most_common()],
        "scored_with_incomplete_dose_receipt_examples": incomplete_receipt_examples,
    }
    (HERE / "census.json").write_text(json.dumps(out, indent=1, default=str) + "\n")
    print(json.dumps({k: out[k] for k in ("products", "status_old", "status_new", "transitions", "flipped")}, indent=1))
    print("buckets:", {k: v["count"] for k, v in out["buckets"].items()})
    print("gap rows:", out["gap"]["rows"], "units:", out["gap"]["rows_by_unit"], "members:", out["gap"]["ul_population_members"])
    print("payload:", out["gap"]["reference_gap_payload"])
    print("target groups:", out["gap"]["target_groups"][:6])
    print("old tier:", out["gap"]["old_tier"], "route:", out["gap"]["route"], "median old total:", out["gap"]["old_total_median"])
    print("context:", json.dumps(out["context"], indent=1, default=str)[:3000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
