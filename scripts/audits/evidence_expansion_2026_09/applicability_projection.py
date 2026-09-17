#!/usr/bin/env python3
"""Read-only before/after projection for the applicability-owner repair.

Loads the committed (pre-repair) ``clinical_applicability`` alongside the working
copy and runs BOTH over every enricher-owned clinical match in the corpus, so the
difference is measured rather than argued. Nothing is written to scripts/data,
scripts/products or scripts/dist, and no score is computed or moved.

    python3 scripts/audits/evidence_expansion_2026_09/applicability_projection.py \
        --baseline-ref HEAD --out <report.json>
"""
from __future__ import annotations

import argparse
import collections
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))


def load_baseline(ref: str):
    """Import the committed version of the owner under its own module name."""
    source = subprocess.run(["git", "show", f"{ref}:scripts/clinical_applicability.py"],
                            cwd=ROOT, capture_output=True, text=True, check=True).stdout
    tmp = Path(tempfile.mkdtemp()) / "clinical_applicability_baseline.py"
    tmp.write_text(source)
    spec = importlib.util.spec_from_file_location("clinical_applicability_baseline", tmp)
    module = importlib.util.module_from_spec(spec)
    sys.modules["clinical_applicability_baseline"] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-ref", default="HEAD")
    parser.add_argument("--out", type=Path, default=OUT / "applicability_projection.json")
    parser.add_argument("--limit-brands", type=int, default=0)
    args = parser.parse_args()

    import clinical_applicability as after
    before = load_baseline(args.baseline_ref)
    # The baseline copy lives outside scripts/, so point it at the one registry loader
    # both versions must read. Same data, same cache, no second source of truth.
    before.reviewed_entries = after.reviewed_entries

    changes: list[dict] = []
    transitions = collections.Counter()
    by_entry = collections.Counter()
    by_reason_after = collections.Counter()
    products_seen = matches_seen = 0
    products_changed: set[str] = set()

    import glob
    scored_dirs = sorted(glob.glob(str(ROOT / "scripts/products/output_*_enriched")))
    if args.limit_brands:
        scored_dirs = scored_dirs[:args.limit_brands]
    for brand_dir in scored_dirs:
        brand = Path(brand_dir).name.removeprefix("output_").removesuffix("_enriched")
        for path in sorted(glob.glob(f"{brand_dir}/enriched/*.json")):
            for product in json.load(open(path)):
                products_seen += 1
                matches = [m for m in (product.get("evidence_data") or {}).get("clinical_matches") or []
                           if isinstance(m, dict)]
                for match in matches:
                    matches_seen += 1
                    old = before.assess_clinical_applicability(product, match)
                    new = after.assess_clinical_applicability(product, match)
                    if (old.get("status"), old.get("reason_code")) == (new.get("status"), new.get("reason_code")):
                        continue
                    entry_id = str(match.get("id") or match.get("study_id"))
                    dsld_id = str(product.get("dsld_id"))
                    products_changed.add(dsld_id)
                    transitions[f"{old.get('status')}:{old.get('reason_code')} -> "
                                f"{new.get('status')}:{new.get('reason_code')}"] += 1
                    by_entry[entry_id] += 1
                    by_reason_after[str(new.get("reason_code"))] += 1
                    if len(changes) < 4000:
                        changes.append({
                            "dsld_id": dsld_id, "brand": brand,
                            "product_name": product.get("product_name"),
                            "entry_id": entry_id,
                            "before": {k: old.get(k) for k in ("status", "reason_code")},
                            "after": {k: new.get(k) for k in ("status", "reason_code", "source_row_ref")}})
        print(f"{brand}: products={products_seen} matches={matches_seen} changed={len(products_changed)}",
              file=sys.stderr, flush=True)

    gained = sum(count for key, count in transitions.items() if "-> applicable" in key)
    lost = sum(count for key, count in transitions.items()
               if key.startswith("applicable:") and "-> applicable" not in key)
    payload = {"_metadata": {
        "baseline_ref": args.baseline_ref,
        "products_evaluated": products_seen, "clinical_matches_evaluated": matches_seen,
        "products_with_a_changed_result": len(products_changed),
        "match_results_changed": sum(transitions.values()),
        "match_results_newly_applicable": gained,
        "match_results_no_longer_applicable": lost,
        "note": "Applicability decisions only. No score was computed or moved; no production data written."},
        "transitions": dict(transitions.most_common()),
        "by_evidence_record": dict(by_entry.most_common()),
        "reason_codes_after": dict(by_reason_after.most_common()),
        "changes": changes}
    args.out.write_text(json.dumps(payload, indent=1))
    print(json.dumps(payload["_metadata"], indent=1))
    print(json.dumps(payload["transitions"], indent=1)[:2000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
