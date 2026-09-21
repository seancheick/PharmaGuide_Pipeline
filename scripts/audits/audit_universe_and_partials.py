#!/usr/bin/env python3
"""Audit actual production evidence universe vs historical 664 queue and isolate the 227 partials."""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List

_SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from scoring_input_contract import get_assessable_evidence_ingredients
from scoring_v4.scored_artifact import build_scored_artifact
import evidence_resolver as er

TERMINAL_DISPOSITIONS = {
    er.EvidenceDisposition.RESOLVED_BY_AUTHORITY.value,
    er.EvidenceDisposition.RESOLVED_BY_REVIEWED_CLINICAL_EVIDENCE.value,
    er.EvidenceDisposition.RESEARCH_PRESENT_APPLICABILITY_UNESTABLISHED.value,
    er.EvidenceDisposition.REVIEWED_NULL_UNFAVORABLE.value,
    er.EvidenceDisposition.NO_QUALIFYING_HUMAN_EVIDENCE.value,
    er.EvidenceDisposition.NOT_EFFICACY_RELEVANT.value,
}


def main():
    # Load queue.json
    queue_file = _SCRIPTS_DIR / "audits" / "evidence_expansion_2026_09" / "queue.json"
    q_data = json.loads(queue_file.read_text(encoding="utf-8")).get("queue", [])
    historical_664_cids = {str(x["canonical_id"]).lower() for x in q_data if x.get("gap_rank", 9999) <= 664}
    all_queue_cids = {str(x["canonical_id"]).lower(): x.get("gap_rank") for x in q_data}

    enriched_files = sorted(Path("scripts/products").glob("output_*_enriched/enriched/enriched_*.json"))
    scored_files = sorted(Path("scripts/products").glob("output_*_scored/scored/scored_*.json"))

    baseline_by_id: Dict[str, Dict[str, Any]] = {}
    for sf in scored_files:
        data = json.loads(sf.read_text(encoding="utf-8"))
        prods = data if isinstance(data, list) else data.get("products", [])
        for p in prods:
            did = str(p.get("dsld_id") or "").strip()
            if did:
                baseline_by_id[did] = p

    all_prods: List[Dict[str, Any]] = []
    for ef in enriched_files:
        data = json.loads(ef.read_text(encoding="utf-8"))
        prods = data if isinstance(data, list) else data.get("products", [])
        all_prods.extend(prods)

    active_products = defaultdict(set)
    active_rows = Counter()
    active_names = defaultdict(Counter)

    for p in all_prods:
        did = str(p.get("dsld_id") or "").strip()
        assessable = get_assessable_evidence_ingredients(p)
        for ing in assessable:
            cid = str(ing.get("canonical_id") or "").strip().lower()
            if not cid:
                continue
            active_products[cid].add(did)
            active_rows[cid] += 1
            name = str(ing.get("ingredient_name") or ing.get("name") or "").strip()
            if name:
                active_names[cid][name] += 1

    distinct_actives = sorted(active_products.keys())

    non_terminal_data = {}
    terminal_data = {}
    for cid in distinct_actives:
        top_name = active_names[cid].most_common(1)[0][0] if active_names[cid] else cid
        res = er.resolve_evidence_for_canonical(cid, name=top_name, cleaner_row_role="active_scorable")
        
        # Determine why it was not in historical 664
        reason = "not_in_queue"
        if cid in historical_664_cids:
            reason = "in_664_queue_but_unresolved"
        elif cid in all_queue_cids:
            reason = f"in_queue_rank_gt_664 (rank={all_queue_cids[cid]})"

        info = {
            "canonical_id": cid,
            "top_name": top_name,
            "product_count": len(active_products[cid]),
            "row_count": active_rows[cid],
            "disposition": res.disposition,
            "matched_owners": res.matched_owners,
            "queue_reason": reason,
        }
        if res.disposition not in TERMINAL_DISPOSITIONS:
            non_terminal_data[cid] = info
        else:
            terminal_data[cid] = info

    print(f"Total distinct assessable canonical actives: {len(distinct_actives)}")
    print(f"Terminal count: {len(terminal_data)}")
    print(f"Non-terminal count: {len(non_terminal_data)}")

    # Isolate the 227 scorable partial products
    partial_227 = []
    for p in all_prods:
        did = str(p.get("dsld_id") or "").strip()
        if not did or did not in baseline_by_id:
            continue
        base_p = baseline_by_id[did]
        if base_p.get("quality_score_status") in {"not_scored", "suppressed_safety"}:
            continue
        prop_p = build_scored_artifact(p)
        if prop_p.get("quality_assessment_status") == "partial":
            partial_227.append((did, p, prop_p))

    print(f"Production-scored partial products count: {len(partial_227)}")

    partial_actives_counter = Counter()
    partial_product_actives = defaultdict(list)
    for did, raw_p, prop_p in partial_227:
        res = er.resolve_product_evidence(raw_p)
        for r in res.resolutions:
            if r.disposition not in TERMINAL_DISPOSITIONS:
                partial_actives_counter[r.canonical_id] += 1
                partial_product_actives[did].append(r.canonical_id)

    print(f"Unique unresolved actives across the {len(partial_227)} partial products: {len(partial_actives_counter)}")
    
    # Save full breakdown
    report = {
        "total_catalog": len(all_prods),
        "total_distinct_assessable_actives": len(distinct_actives),
        "terminal_actives_count": len(terminal_data),
        "non_terminal_actives_count": len(non_terminal_data),
        "production_partial_products_count": len(partial_227),
        "partial_product_ids": [did for did, _, _ in partial_227],
        "unique_unresolved_actives_in_partials": len(partial_actives_counter),
        "unresolved_actives_ranked_in_partials": [
            {
                "canonical_id": cid,
                "partial_reach": cnt,
                "catalog_reach": non_terminal_data.get(cid, {}).get("product_count"),
                "top_name": non_terminal_data.get(cid, {}).get("top_name"),
                "disposition": non_terminal_data.get(cid, {}).get("disposition"),
                "queue_reason": non_terminal_data.get(cid, {}).get("queue_reason"),
            }
            for cid, cnt in partial_actives_counter.most_common()
        ],
        "all_non_terminal_actives": list(non_terminal_data.values()),
    }

    out_file = Path("reports/production_evidence_universe_gap.json")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Report written to {out_file}")

    print("\n--- TOP 30 UNRESOLVED ACTIVES IN PARTIAL PRODUCTS ---")
    for row in report["unresolved_actives_ranked_in_partials"][:30]:
        print(f"  {row['canonical_id']} ({row['top_name']}): reach={row['partial_reach']} (total {row['catalog_reach']}), disp={row['disposition']}, queue={row['queue_reason']}")


if __name__ == "__main__":
    main()
