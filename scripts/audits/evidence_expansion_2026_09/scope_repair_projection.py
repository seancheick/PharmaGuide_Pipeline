#!/usr/bin/env python3
"""Read-only projection for the legacy scope repairs (2026-09-18).

Scores every product that carries one of the repaired records twice with the
PRODUCTION scorer (``score_supplements_v4.score_product_v4``):

  * baseline  — the committed registry, product blob untouched;
  * candidate — the working-tree registry, with each affected product's embedded
    ``evidence_data.clinical_matches`` rebuilt from the repaired record exactly
    as ``enrich_supplements_v3`` would rebuild it on the next enrichment run.

Rebuilding the embedded payload is what makes this faithful: the scorer reads
the match copy baked into the enriched product, while the applicability policy
is read live from the registry. Patching only one of the two would understate or
overstate the repair.

Nothing is written back. No config, no scoring rule and no product file changes.

    python3 scripts/audits/evidence_expansion_2026_09/scope_repair_projection.py \
        --slim <slim.jsonl> --baseline <baseline backed_clinical_studies.json>
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

LIVE_REGISTRY = ROOT / "scripts/data/backed_clinical_studies.json"

# Mirrors enrich_supplements_v3.py's clinical-match payload: the registry-owned
# keys it stamps on every match. Anything absent from the repaired record is
# removed from the match, because the next enrichment run would not write it.
REGISTRY_BASE_KEYS = ("evidence_level", "study_type", "score_contribution",
                      "health_goals_supported", "key_endpoints")
REGISTRY_OPTIONAL_KEYS = (
    "applicability", "min_clinical_dose", "max_studied_clinical_dose", "max_clinical_dose",
    "max_studied_dose", "dose_unit", "typical_effective_dose", "dose_range", "base_points",
    "multiplier", "computed_score", "effect_direction", "effect_direction_rationale",
    "effect_direction_confidence", "total_enrollment", "published_studies",
    "published_studies_count", "published_rct_count", "published_meta_review_count",
    "registry_completed_trials_count", "primary_outcome", "endpoint_relevance_tags",
    "evidence_group_id", "aggregate_canonical_ids", "notes", "notable_studies",
    "references_structured")


def ui_evidence_scope(evidence_level) -> str:
    level = str(evidence_level or "").strip().lower()
    if level == "product-human":
        return "product"
    if level == "branded-rct":
        return "branded_ingredient"
    if level in {"ingredient-human", "strain-clinical"}:
        return "ingredient"
    return "indirect"


def load_registry(path: Path) -> dict:
    payload = json.loads(path.read_text())
    return {entry["id"]: entry for entry in payload["backed_clinical_studies"]}


def repaint_match(match: dict, entry: dict) -> dict:
    """Rebuild one embedded clinical match from its registry record."""
    fresh = dict(match)
    for key in REGISTRY_BASE_KEYS:
        fresh[key] = entry.get(key, [] if key in ("health_goals_supported", "key_endpoints") else None)
    fresh["ui_evidence_scope"] = ui_evidence_scope(entry.get("evidence_level"))
    for key in REGISTRY_OPTIONAL_KEYS:
        if entry.get(key) is not None:
            fresh[key] = entry[key]
        else:
            fresh.pop(key, None)
    return fresh


def evidence_of(result: dict):
    pillars = result.get("quality_pillars_v4") or {}
    value = (pillars.get("evidence") or {}).get("score")
    return float(value) if isinstance(value, (int, float)) else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slim", required=True, type=Path)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--out", default="scope_repair_projection.json")
    args = parser.parse_args()

    baseline_registry = load_registry(args.baseline)
    live_registry = load_registry(LIVE_REGISTRY)
    changed_ids = sorted(
        entry_id for entry_id in set(baseline_registry) | set(live_registry)
        if baseline_registry.get(entry_id) != live_registry.get(entry_id))
    if not changed_ids:
        print("no registry record differs from the baseline; nothing to project", file=sys.stderr)
        return 1
    print(f"repaired records: {', '.join(changed_ids)}", file=sys.stderr)

    import clinical_applicability
    from score_supplements_v4 import score_product_v4

    targets: dict[str, dict] = {}
    for line in args.slim.open():
        product = json.loads(line)
        hits = [m["id"] for m in product["accepted_matches"] if m["id"] in changed_ids]
        if hits:
            targets[product["dsld_id"]] = {"brand_dir": product["brand_dir"], "records": hits,
                                           "brand": product["brand_name"], "name": product["product_name"],
                                           "module": product["module"]}
    print(f"products carrying a repaired record: {len(targets)}", file=sys.stderr)

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

                clinical_applicability.reviewed_entries = lambda r=baseline_registry: r
                baseline = score_product_v4(json.loads(json.dumps(enriched)))

                candidate_blob = json.loads(json.dumps(enriched))
                matches = ((candidate_blob.get("evidence_data") or {}).get("clinical_matches") or [])
                for index, match in enumerate(matches):
                    entry = live_registry.get(match.get("id") or match.get("study_id"))
                    if entry is not None and (match.get("id") or match.get("study_id")) in changed_ids:
                        matches[index] = repaint_match(match, entry)
                clinical_applicability.reviewed_entries = lambda r=live_registry: r
                candidate = score_product_v4(candidate_blob)

                before_ev, after_ev = evidence_of(baseline), evidence_of(candidate)
                before_total = baseline.get("quality_score_v4_100")
                after_total = candidate.get("quality_score_v4_100")
                rows.append({
                    "dsld_id": dsld_id, "brand": meta["brand"], "product_name": meta["name"],
                    "module": meta["module"], "repaired_records": meta["records"],
                    "evidence_before": before_ev, "evidence_after": after_ev,
                    "evidence_delta": None if None in (before_ev, after_ev) else round(after_ev - before_ev, 2),
                    "total_before": before_total, "total_after": after_total,
                    "total_delta": None if None in (before_total, after_total) else round(
                        after_total - before_total, 2)})
        print(f"{brand_dir}: scored {len(rows)}", file=sys.stderr, flush=True)

    changed = [r for r in rows if r["evidence_delta"] not in (None, 0)]
    per_record = collections.Counter()
    for row in changed:
        for record in row["repaired_records"]:
            per_record[record] += 1
    deltas = [r["evidence_delta"] for r in changed if r["evidence_delta"] is not None]
    ups = [d for d in deltas if d > 0]
    downs = [d for d in deltas if d < 0]
    payload = {"_metadata": {
        "repaired_records": changed_ids,
        "products_carrying_a_repaired_record": len(targets),
        "products_scored": len(rows),
        "products_with_an_evidence_change": len(changed),
        "products_up": len(ups), "products_down": len(downs),
        "mean_evidence_delta": round(sum(deltas) / len(deltas), 3) if deltas else 0,
        "largest_evidence_rise": max(deltas) if deltas else 0,
        "largest_evidence_drop": min(deltas) if deltas else 0,
        "changed_by_module": dict(collections.Counter(r["module"] for r in changed)),
        "changed_by_record": dict(per_record),
        "note": "Read-only. Registry read from the working tree; enriched products patched in memory only."},
        "largest_drops": sorted(changed, key=lambda r: r["evidence_delta"] or 0)[:25],
        "largest_rises": sorted(changed, key=lambda r: -(r["evidence_delta"] or 0))[:25],
        "products": rows}
    (OUT / args.out).write_text(json.dumps(payload, indent=1))
    print(json.dumps(payload["_metadata"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
