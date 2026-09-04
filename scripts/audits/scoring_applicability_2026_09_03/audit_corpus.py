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
from multiprocessing import get_context
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))

REVIEW_TARGET_IDS = {"PG_SUB_35E0BD3374BF494B80FEABE87FC559E7", "299239", "250851",
                     "327965", "307727", "326762"}


def select_stage_files(stage_dirs: Any, stage: str, *, require_manifest: bool) -> list[Path]:
    """Import lazily so spawned workers do not preload the input checkout's code."""
    from stage_manifest import select_stage_files as select
    return select(stage_dirs, stage, require_manifest=require_manifest)


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


def load_baseline_report(path: Path, baseline: dict, input_hashes: dict) -> tuple[dict, str]:
    """Reconstruct authenticated ancestor candidates before applying child deltas.

    Reports omit unchanged non-canaries, so a child is not a standalone overlay
    on shipped artifacts. Every ancestor must prove the same complete corpus.
    """
    ancestors: set[Path] = set()

    def load(current: Path, expected_digest: str | None = None) -> tuple[dict, str]:
        current = current.resolve()
        if current in ancestors:
            raise ValueError(f"Baseline report chain contains a cycle: {current}")
        ancestors.add(current)
        try:
            raw = current.read_bytes()
            report = json.loads(raw)
        except (OSError, ValueError) as exc:
            raise ValueError(f"Baseline report cannot be read: {current}") from exc
        digest = hashlib.sha256(raw).hexdigest()
        if expected_digest is not None and digest != expected_digest:
            raise ValueError(f"Baseline parent report hash mismatch: {current}")
        if (not isinstance(report, dict) or report.get("complete") is not True
                or report.get("product_count") != len(baseline)
                or report.get("baseline_product_count") != len(baseline)
                or report.get("input_hashes") != input_hashes or report.get("errors")):
            raise ValueError("Baseline report is incomplete or does not prove the current input corpus")

        inherited = baseline
        parent = report.get("baseline_report")
        parent_digest = report.get("baseline_report_sha256")
        if parent is not None:
            if (not isinstance(parent, str) or not parent.strip()
                    or not isinstance(parent_digest, str) or not parent_digest):
                raise ValueError("Baseline parent report requires a path and hash")
            parent_path = Path(parent)
            if not parent_path.is_absolute():
                parent_path = current.parent / parent_path
            inherited, _ = load(parent_path, parent_digest)
        elif parent_digest is not None:
            raise ValueError("Baseline parent hash has no report path")

        overlays = {}
        for section in ("changes", "canaries"):
            rows = report.get(section)
            if not isinstance(rows, list):
                raise ValueError(f"Baseline report has invalid {section}")
            for row in rows:
                pid = str(row.get("id")) if isinstance(row, dict) else ""
                candidate = row.get("candidate") if isinstance(row, dict) else None
                if (pid not in baseline or not isinstance(candidate, dict)
                        or set(candidate) != set(summary({}))):
                    raise ValueError(f"Baseline report has invalid candidate: {pid}")
                if pid in overlays and overlays[pid] != candidate:
                    raise ValueError(f"Baseline report has conflicting candidates: {pid}")
                overlays[pid] = candidate
        return {**inherited, **overlays}, digest

    return load(path)


def parse_target_ids(value: str | None) -> set[str] | None:
    """Parse an explicit nonempty target list; None alone means the full corpus."""
    if value is None:
        return None
    targets = {part.strip() for part in value.split(",")}
    if "" in targets:
        raise ValueError("Every target ID must be nonempty")
    return targets


def target_products(rows: list[dict], target_ids: set[str] | None) -> list[dict]:
    """Filter before any enrichment or cleaned-input lookup."""
    return rows if target_ids is None else [row for row in rows if product_id(row) in target_ids]


def merge_reenrichment_ids(selected: set[str], requested: set[str] | None,
                          available: set[str]) -> set[str]:
    """Expand clean replay without reducing the full-corpus scoring denominator."""
    missing = (requested or set()) - available
    if missing:
        raise ValueError(f"Re-enrichment IDs absent from baseline: {', '.join(sorted(missing))}")
    return selected | (requested or set())


def implementation_hashes(implementation_root: Path) -> dict[str, str]:
    """Hash code and reference/config data relative to the implementation used."""
    scripts = implementation_root / "scripts"
    files = (list(scripts.glob("*.py")) + list((scripts / "scoring_v4").rglob("*.py"))
             + list((scripts / "data").rglob("*.json"))
             + list((scripts / "config").rglob("*.json"))
             + list((scripts / "scoring_v4/config").glob("*.json")))
    reachability = scripts / "audits/evidence_match_reachability.py"
    if reachability.is_file():
        files.append(reachability)
    return {str(path.relative_to(implementation_root)): sha(path) for path in sorted(set(files))}


def json_safe(value: Any) -> Any:
    """Retain nested report data, converting set-valued diagnostics to arrays."""
    return json.loads(json.dumps(value, allow_nan=False, default=lambda item:
        sorted(item, key=str) if isinstance(item, (set, frozenset)) else str(item)))


def strain_summary(product):
    return [{k: row.get(k) for k in ("strain", "clinical_id", "research_match_status", "review_status", "source_row_ref", "label_name")}
            for row in (product.get("probiotic_data") or {}).get("clinical_strains", [])]


def init_worker(implementation_root: str | Path = ROOT,
                input_root: str | Path | None = None) -> None:
    """Keep source inputs separate from the implementation in spawned workers."""
    global ENRICHER, ROOT
    if input_root is not None:
        ROOT = Path(input_root).resolve()
    implementation_root = Path(implementation_root).resolve()
    sys.path.insert(0, str(implementation_root / "scripts"))
    logging.disable(logging.CRITICAL)
    import enrich_supplements_v3
    if not Path(enrich_supplements_v3.__file__).resolve().is_relative_to(implementation_root):
        raise RuntimeError("Worker imported enrichment outside the selected implementation root")
    ENRICHER = enrich_supplements_v3.SupplementEnricherV3()


def process_file(args):
    path, selected, target_ids = args
    path = Path(path)
    products = target_products(json.loads(path.read_text()), target_ids)
    if not products:
        return []
    from scoring_v4.scored_artifact import build_scored_artifact
    import studied_formulas
    from audits.evidence_match_reachability import recompute_evidence
    assess_studied_formula = studied_formulas.assess_studied_formula
    brand_root = path.parent.parent.name.removesuffix("_enriched")
    cleaned_dir = ROOT / "scripts/products" / brand_root / "cleaned"
    cleaned, clean_sources = {}, {}
    needed = {product_id(p) for p in products} & selected
    if needed:
        for file in select_stage_files([cleaned_dir], "clean", require_manifest=True):
            for row in target_products(json.loads(file.read_text()), needed):
                pid = product_id(row)
                if pid in cleaned:
                    raise RuntimeError(f"Duplicate selected clean source: {pid}")
                cleaned[pid], clean_sources[pid] = row, str(file.relative_to(ROOT))
    result = []
    for p in products:
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
            p["proprietary_data"] = ENRICHER._collect_proprietary_data(p)
            p["proprietary_blends"] = p["proprietary_data"].get("blends", [])
            if p["probiotic_data"].get("afu_measurements"):
                p["probiotic_data"]["studied_formula_assessment"] = assess_studied_formula(p)
            p["evidence_data"] = recompute_evidence(ENRICHER, p)
        score = build_scored_artifact(p)
        after_evidence = [m.get("id") for m in p["evidence_data"].get("clinical_matches", [])]
        record = {"id": pid, "name": p.get("fullName"), "brand": p.get("brandName"),
                       "candidate": summary(score), "full_reenrichment": pid in selected,
                       "evidence_before": before_evidence, "evidence_after": after_evidence,
                       "strains_before": before_strains, "strains_after": strain_summary(p),
                       "rejected_evidence": p["evidence_data"].get("rejected_clinical_matches", []),
                       "cert_before": before_certs if before_certs != p.get("verified_cert_programs") else None,
                       "cert_after": p.get("verified_cert_programs") if before_certs != p.get("verified_cert_programs") else None,
                       "formula": assess_studied_formula(p) if pid.startswith("PG_SUB_") else None,
                       "readiness": score.get("assessment_readiness"),
                       "source_inputs": {"enriched": str(path.relative_to(ROOT)), "cleaned": clean_sources.get(pid)}}
        if pid in REVIEW_TARGET_IDS or target_ids is not None:
            assess_native = getattr(studied_formulas, "assess_probiotic_evidence", None)
            record["candidate_detail"] = {
                "quality_pillars_v4": score.get("quality_pillars_v4"),
                "_v4_module_breakdown": score.get("_v4_module_breakdown"),
                "cert_records_before": before_certs,
                "cert_records_after": p.get("verified_cert_programs") or [],
                "certification_data": p.get("certification_data"),
                "probiotic_data": p.get("probiotic_data") or p.get("probiotic_detail"),
                "evidence_data": p.get("evidence_data"),
                "native_evidence_assessment": assess_native(p) if callable(assess_native) else None,
                "assessment_readiness": score.get("assessment_readiness"),
            }
        result.append(json_safe(record))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--baseline-report", type=Path, help="Complete prior report for the identical input corpus")
    parser.add_argument("--target-ids", type=parse_target_ids, help="Comma-separated IDs; process only these products")
    parser.add_argument("--reenrich-ids", type=parse_target_ids,
                        help="Additional IDs to fully re-enrich; retain the whole scoring corpus")
    parser.add_argument("--input-root", type=Path, default=ROOT,
                        help="Checkout containing the manifest-owned source product inputs")
    parser.add_argument("--implementation-root", type=Path, default=ROOT,
                        help="Implementation/code/data checkout, independent of source product inputs")
    args = parser.parse_args()
    if not 1 <= args.workers <= 2:
        parser.error("Use one or two bounded workers")
    implementation_root = args.implementation_root.resolve()
    input_root = args.input_root.resolve()
    if not (implementation_root / "scripts/enrich_supplements_v3.py").is_file():
        parser.error("Implementation root does not contain scripts/enrich_supplements_v3.py")
    if not (input_root / "scripts/products").is_dir():
        parser.error("Input root does not contain scripts/products")
    if args.output.exists():
        parser.error("Output must be a new path; existing reports must not be replaced")
    enriched_files = select_stage_files((input_root / "scripts/products").glob("output_*_enriched/enriched"), "enrich", require_manifest=True)
    scored_files = select_stage_files((input_root / "scripts/products").glob("output_*_scored/scored"), "score", require_manifest=True)
    cleaned_files = select_stage_files((input_root / "scripts/products").glob("output_*/cleaned"), "clean", require_manifest=True)
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
    selected |= REVIEW_TARGET_IDS
    selected &= set(baseline)
    try:
        selected = merge_reenrichment_ids(selected, args.reenrich_ids, set(baseline))
    except ValueError as exc:
        parser.error(str(exc))
    sources = {str(p.relative_to(input_root)): sha(p) for p in enriched_files + scored_files + cleaned_files}
    baseline_digest = None
    source_baseline = baseline
    if args.baseline_report:
        baseline, baseline_digest = load_baseline_report(args.baseline_report, baseline, sources)
    full_baseline_count = len(baseline)
    if args.target_ids is not None:
        missing = args.target_ids - set(baseline)
        if missing:
            parser.error(f"Target IDs absent from baseline: {', '.join(sorted(missing))}")
        baseline = {pid: baseline[pid] for pid in sorted(args.target_ids)}
        selected = set(args.target_ids)
    code = implementation_hashes(implementation_root)
    runner_hashes = {str(p.resolve()): sha(p) for p in (Path(__file__), ROOT / "scripts/stage_manifest.py")}
    report = {"kind": "read_only_enriched_corpus_impact_audit", "complete": False,
              "baseline_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=input_root, text=True).strip(),
              "input_hashes": sources, "candidate_code_hashes": code,
              "input_root": str(input_root), "implementation_root": str(implementation_root),
              "audit_runner_hashes": runner_hashes,
              "baseline_report": str(args.baseline_report.resolve()) if args.baseline_report else None,
              "baseline_report_sha256": baseline_digest,
              "selection_policy": "explicit target IDs only" if args.target_ids is not None else
                  "lowest SHA256(20260903:id) per brand/module plus every submission, reviewed canaries and explicit extra clean-replay IDs",
              "extra_reenrichment_ids": sorted(args.reenrich_ids or []),
              "recomputed_lanes": ["certification", "probiotic", "proprietary_blend_provenance", "evidence", "scoring"],
              "target_ids": sorted(args.target_ids) if args.target_ids is not None else None,
              "full_baseline_product_count": full_baseline_count,
              "full_reenrichment_ids": sorted(selected), "baseline_product_count": len(baseline),
              "changes": [], "canaries": [], "errors": []}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation also rejects a collision after the preflight check.
    with args.output.open("x") as handle:
        handle.write(json.dumps(report, indent=2)+"\n")
    start, seen = time.monotonic(), set()
    transitions = Counter()
    rejected = Counter()
    with ProcessPoolExecutor(max_workers=args.workers, initializer=init_worker, mp_context=get_context("spawn"),
                             initargs=(str(implementation_root), str(input_root))) as pool:
        tasks = [(str(f), selected, args.target_ids) for f in enriched_files]
        for index, batch in enumerate(pool.map(process_file, tasks), 1):
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
    for name, digest in sources.items():
        if sha(input_root / name) != digest:
            raise RuntimeError(f"Source changed during audit: {name}")
    for name, digest in code.items():
        if sha(implementation_root / name) != digest:
            raise RuntimeError(f"Implementation changed during audit: {name}")
    for name, digest in runner_hashes.items():
        if sha(name) != digest:
            raise RuntimeError(f"Audit runner changed during audit: {name}")
    if args.baseline_report:
        # The immediate report can stay unchanged while a transitive ancestor
        # is replaced. Revalidate every link before declaring the replay complete.
        _, latest_digest = load_baseline_report(args.baseline_report, source_baseline, sources)
        if latest_digest != baseline_digest:
            raise RuntimeError("Baseline report changed during audit")
    report.update(complete=True, product_count=len(seen), elapsed_seconds=round(time.monotonic()-start, 1),
                  status_transitions={f"{a}->{b}": n for (a,b),n in transitions.items()},
                  rejected_evidence_reasons=dict(rejected))
    args.output.write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps({k:report[k] for k in ("complete", "product_count", "elapsed_seconds", "status_transitions")}))


if __name__ == "__main__":
    main()
