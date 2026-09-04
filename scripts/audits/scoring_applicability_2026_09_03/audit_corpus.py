"""Read-only corpus replay. Writes reports only; never replaces pipeline outputs.

Recollect changed producer surfaces from manifest-owned enriched inputs, fully
re-enrich deterministic cross-brand canaries, then use the production v4 scorer.
This is an impact audit, not a replacement for an operational rebuild/release.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import logging
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
from stage_manifest import select_stage_files


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def product_id(row):
    return str(row.get("dsld_id") or row.get("id"))


def summary(row):
    pillars = row.get("quality_pillars_v4") or {}
    return {"score": row.get("quality_score_v4_100"), "status": row.get("quality_score_status"),
            "verdict": row.get("verdict"), "tier": row.get("quality_tier"),
            "module": row.get("_v4_module"), "confidence": row.get("quality_score_confidence"),
            "pillars": {k: v.get("score") for k, v in pillars.items()},
            "reasons": {k: v.get("reason") for k, v in pillars.items()}}


def strain_summary(product):
    return [{k: row.get(k) for k in ("strain", "clinical_id", "research_match_status", "review_status", "source_row_ref", "label_name")}
            for row in (product.get("probiotic_data") or {}).get("clinical_strains", [])]


def init_worker():
    global ENRICHER
    logging.disable(logging.CRITICAL)
    from enrich_supplements_v3 import SupplementEnricherV3
    ENRICHER = SupplementEnricherV3()


def process_file(args):
    path, selected = args
    from scoring_v4.scored_artifact import build_scored_artifact
    from studied_formulas import assess_studied_formula
    from audits.evidence_match_reachability import recompute_evidence
    path = Path(path)
    brand_root = path.parent.parent.name.removesuffix("_enriched")
    cleaned_dir = ROOT / "scripts/products" / brand_root / "cleaned"
    cleaned = {}
    for file in select_stage_files([cleaned_dir], "clean", require_manifest=True):
        for row in json.loads(file.read_text()):
            if product_id(row) in selected:
                cleaned[product_id(row)] = row
    result = []
    for p in json.loads(path.read_text()):
        pid = product_id(p)
        before_certs = p.get("verified_cert_programs") or []
        before_evidence = [m.get("id") for m in (p.get("evidence_data") or {}).get("clinical_matches", [])]
        before_strains = strain_summary(p)
        if pid in selected:
            if pid not in cleaned:
                raise RuntimeError(f"Selected clean source missing: {pid}")
            p, issues = ENRICHER.enrich_product(cleaned[pid])
            if not p:
                raise RuntimeError(f"Canary failed enrichment: {pid}: {issues}")
        else:
            p["certification_data"] = ENRICHER._collect_certification_data(p)
            p["verified_cert_programs"] = p["certification_data"]["verified_cert_programs"]
            p["probiotic_data"] = ENRICHER._collect_probiotic_data(p)
            if p["probiotic_data"].get("afu_measurements"):
                p["probiotic_data"]["studied_formula_assessment"] = assess_studied_formula(p)
            p["evidence_data"] = recompute_evidence(ENRICHER, p)
        score = build_scored_artifact(p)
        after_evidence = [m.get("id") for m in p["evidence_data"].get("clinical_matches", [])]
        result.append({"id": pid, "name": p.get("fullName"), "brand": p.get("brandName"),
                       "candidate": summary(score), "full_reenrichment": pid in selected,
                       "evidence_before": before_evidence, "evidence_after": after_evidence,
                       "strains_before": before_strains, "strains_after": strain_summary(p),
                       "rejected_evidence": p["evidence_data"].get("rejected_clinical_matches", []),
                       "cert_before": before_certs if before_certs != p.get("verified_cert_programs") else None,
                       "cert_after": p.get("verified_cert_programs") if before_certs != p.get("verified_cert_programs") else None,
                       "formula": assess_studied_formula(p) if pid.startswith("PG_SUB_") else None,
                       "readiness": score.get("assessment_readiness") if pid.startswith("PG_SUB_") else None})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    if not 1 <= args.workers <= 2:
        parser.error("Use one or two bounded workers")
    enriched_files = select_stage_files((ROOT / "scripts/products").glob("output_*_enriched/enriched"), "enrich", require_manifest=True)
    scored_files = select_stage_files((ROOT / "scripts/products").glob("output_*_scored/scored"), "score", require_manifest=True)
    cleaned_files = select_stage_files((ROOT / "scripts/products").glob("output_*/cleaned"), "clean", require_manifest=True)
    baseline, buckets = {}, defaultdict(list)
    for f in scored_files:
        for row in json.loads(f.read_text()):
            pid = product_id(row)
            if pid in baseline:
                raise RuntimeError(f"Duplicate baseline product: {pid}")
            baseline[pid] = summary(row)
            buckets[(f.parent.parent.name, row.get("_v4_module"))].append(pid)
    selected = {pid for ids in buckets.values() for pid in sorted(ids, key=lambda x: hashlib.sha256(("20260903:"+x).encode()).digest())[:1]}
    selected |= {pid for pid in baseline if pid.startswith("PG_SUB_")}
    selected |= {"270966", "279714", "313839", "280347", "327416", "335195"}
    selected |= {"252636", "291803", "299239", "333749", "269621", "174659", "222758", "222881", "327965",
                 "307727", "307728", "337852"}
    selected &= set(baseline)
    sources = {str(p.relative_to(ROOT)): sha(p) for p in enriched_files + scored_files + cleaned_files}
    code_files = (list((ROOT / "scripts").glob("*.py"))
                  + list((ROOT / "scripts/scoring_v4").rglob("*.py"))
                  + list((ROOT / "scripts/data").rglob("*.json"))
                  + [ROOT / "scripts/scoring_v4/config/quality_score.json",
                     ROOT / "scripts/audits/evidence_match_reachability.py", Path(__file__)])
    code = {str(p.relative_to(ROOT)): sha(p) for p in code_files}
    report = {"kind": "read_only_enriched_corpus_impact_audit", "complete": False,
              "baseline_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "input_hashes": sources, "candidate_code_hashes": code,
              "selection_policy": "lowest SHA256(20260903:id) per brand/module plus every submission and reviewed certification/native-strain canary",
              "full_reenrichment_ids": sorted(selected), "baseline_product_count": len(baseline),
              "changes": [], "canaries": [], "errors": []}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+"\n")
    start, seen = time.monotonic(), set()
    transitions = Counter()
    rejected = Counter()
    with ProcessPoolExecutor(max_workers=args.workers, initializer=init_worker) as pool:
        for index, batch in enumerate(pool.map(process_file, [(str(f), selected) for f in enriched_files]), 1):
            for row in batch:
                pid = row["id"]
                if pid in seen or pid not in baseline:
                    raise RuntimeError(f"Input identity mismatch: {pid}")
                seen.add(pid)
                row["baseline"] = baseline[pid]
                transitions[(baseline[pid]["status"], row["candidate"]["status"])] += 1
                rejected.update(r["reason_code"] for r in row["rejected_evidence"])
                if (row["candidate"] != baseline[pid] or row["cert_before"] is not None
                        or row["evidence_before"] != row["evidence_after"]
                        or row["strains_before"] != row["strains_after"]):
                    report["changes"].append(row)
                if row["full_reenrichment"]:
                    report["canaries"].append(row)
            print(f"{index}/{len(enriched_files)} files; {len(seen)} products; {len(report['changes'])} changed", flush=True)
    if seen != set(baseline):
        raise RuntimeError("Baseline/candidate product sets differ")
    for name, digest in sources.items() | code.items():
        if sha(ROOT / name) != digest:
            raise RuntimeError(f"Source changed during audit: {name}")
    report.update(complete=True, product_count=len(seen), elapsed_seconds=round(time.monotonic()-start, 1),
                  status_transitions={f"{a}->{b}": n for (a,b),n in transitions.items()},
                  rejected_evidence_reasons=dict(rejected))
    args.output.write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps({k:report[k] for k in ("complete", "product_count", "elapsed_seconds", "status_transitions")}))


if __name__ == "__main__":
    main()
