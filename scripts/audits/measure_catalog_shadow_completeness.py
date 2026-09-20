#!/usr/bin/env python3
"""Measure full catalog product evidence completeness in shadow mode across all 15,421 products."""

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import evidence_resolver as er

def main():
    enriched_files = sorted(Path("scripts/products").glob("output_*_enriched/enriched/enriched_*.json"))
    print(f"Loading {len(enriched_files)} enriched product files...")

    total_products = 0
    complete_products = 0
    partial_products = 0

    partial_by_reason = Counter()
    partial_products_by_cid = defaultdict(list)
    partial_examples = []

    for fpath in enriched_files:
        try:
            data = json.loads(fpath.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"Error reading {fpath}: {e}")
            continue

        products = data if isinstance(data, list) else data.get("products", [])
        for prod in products:
            total_products += 1
            res = er.resolve_product_evidence(prod)

            if res.is_assessment_complete:
                complete_products += 1
            else:
                partial_products += 1
                for b in res.unresolved_blockers:
                    partial_by_reason[b] += 1
                # Find which active ingredients blocked it
                blocked_cids = []
                for ing_res in res.resolutions:
                    if not ing_res.matched_owners or ing_res.disposition == er.EvidenceDisposition.IDENTITY_INSUFFICIENT.value:
                        blocked_cids.append(ing_res.canonical_id)
                        partial_products_by_cid[ing_res.canonical_id].append(prod.get("dsld_id"))
                if len(partial_examples) < 10:
                    partial_examples.append({
                        "dsld_id": prod.get("dsld_id"),
                        "name": prod.get("name") or prod.get("product_name"),
                        "blocked_cids": blocked_cids,
                        "overall_disposition": res.overall_disposition,
                    })

    pct_complete = (complete_products / total_products * 100.0) if total_products else 0.0

    print("=" * 70)
    print("RESOLVER-SHADOW CATALOG EVIDENCE COMPLETENESS REPORT")
    print("=" * 70)
    print(f"Total Products Evaluated: {total_products}")
    print(f"Complete Assessments:    {complete_products} ({pct_complete:.2f}%)")
    print(f"Partial Products:         {partial_products} ({100.0 - pct_complete:.2f}%)")
    print("\nPartial Blockers Breakdown:")
    for reason, cnt in partial_by_reason.most_common():
        print(f"  {reason:<45}: {cnt}")

    print(f"\nRemaining Partial Blocking Canonical Actives ({len(partial_products_by_cid)}):")
    for cid, pids in sorted(partial_products_by_cid.items(), key=lambda x: -len(x[1])):
        print(f"  {cid:<40}: {len(pids)} products")

    output_report = {
        "total_products": total_products,
        "complete_products": complete_products,
        "partial_products": partial_products,
        "percentage_complete": round(pct_complete, 2),
        "partial_by_reason": dict(partial_by_reason),
        "partial_by_cid": {cid: len(pids) for cid, pids in partial_products_by_cid.items()},
    }
    out_path = Path("scripts/reports/phase4_final_sweep_completeness.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output_report, indent=2), encoding="utf-8")
    print(f"\nSaved report to {out_path}")

if __name__ == "__main__":
    main()
