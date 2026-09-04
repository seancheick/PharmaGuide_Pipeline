"""Report-only rubric sensitivity. Never imported by production or writes a catalog.

Independent ablations keep existing public denominators. They are not complete
replacement rubrics, clinically calibrated numbers, or release artifacts.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
import json
from multiprocessing import get_context
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
from audits.scoring_applicability_2026_09_03 import audit_corpus as replay
from probiotic_measurements import declared_total_cfu

VARIANTS = ("form_no_size_diversity", "identity_fraction", "flat_total_disclosure",
            "dose_without_disclosure", "combined_form_transparency")
CONTROLS = replay.REVIEW_TARGET_IDS | {"79324"}


def alter_dimensions(dimensions, pdata, variant):
    if variant not in ("baseline", *VARIANTS):
        raise ValueError(f"Unknown sensitivity variant: {variant}")
    dims = deepcopy(dimensions)
    if variant == "combined_form_transparency":
        for child in VARIANTS[:3]:
            dims = alter_dimensions(dims, pdata, child)
        return dims
    changed = set()
    if variant == "form_no_size_diversity":
        for key in ("cfu_amount", "studied_formula_potency", "named_species_diversity"):
            dims["formulation"]["components"].pop(key, None)
        changed.add("formulation")
    elif variant == "identity_fraction":
        form = dims["formulation"]
        if "identified_strain_codes" in form["components"]:
            meta = form.get("metadata") or {}
            count, total = meta.get("identified_strain_count", 0), meta.get("total_strain_count", 0)
            form["components"]["identified_strain_codes"] = 8 * min(1, count / total) if total else 0
        # Exact formula set identity already earns 8; no special size exemption.
        changed.add("formulation")
    elif variant == "flat_total_disclosure":
        comp = dims["transparency"]["components"]
        if "aggregate_cfu_disclosure_proxy" in comp:
            target = 4 if declared_total_cfu(pdata) > 0 else 0
            comp["aggregate_cfu_disclosure_proxy"] = max(0, target - comp.get("per_strain_cfu_on_label", 0))
        if "aggregate_native_afu_disclosure" in comp:
            formula = dims["transparency"].get("metadata", {}).get("studied_formula_assessment", {})
            target = 4 if formula.get("status") == "assessed_studied_formula" else 0
            comp["aggregate_native_afu_disclosure"] = max(0, target - comp.get("per_strain_cfu_on_label", 0))
        changed.add("transparency")
    elif variant == "dose_without_disclosure":
        dose = dims["dose"]
        dose["components"].pop("per_strain_cfu_disclosure", None)
        if dose.get("metadata", {}).get("cfu_adequacy_basis") in {
            "aggregate_cfu_disclosed_only", "direct_strain_mass_no_cfu_floor"}:
            dose["components"]["cfu_adequacy"] = 0
        changed.add("dose")
    for key in changed:
        dim = dims[key]
        raw = sum(dim["components"].values()) - sum(abs(v) for v in dim.get("penalties", {}).values())
        dim["score"] = round(max(0, min(dim["max"], raw)), 4)
    return dims


def shadow_scores(record, variant):
    """Use the production public pillar adapters; preserve all untouched pillars."""
    from scoring_v4 import quality_score as quality
    detail, base = record["candidate_detail"], record["candidate"]
    state = {"status": base["status"], "baseline_verdict": base.get("verdict"),
             "baseline_tier": base.get("tier")}
    if base["status"] != "scored":
        return {**state, "score": None, "pillars": base["pillars"]}
    module = detail["_v4_module_breakdown"]
    dims = alter_dimensions(module["dimensions"], detail["probiotic_data"], variant)
    cfg = quality._config()
    pillars = dict(base["pillars"])
    for name, adapter in (("formulation", quality._pillar_formulation), ("dose", quality._pillar_dose)):
        pillars[name] = adapter(dims[name], cfg["pillars"][name]["weight"], "probiotic", cfg)["score"]
    pillars["transparency"] = quality._pillar_from_dim(
        "transparency", dims["transparency"], cfg["pillars"]["transparency"]["weight"], "transparency")["score"]
    total = max(0, min(100, round(sum(pillars.values()), 1)))
    cap = quality._public_quality_cap(module)
    if cap:
        total = min(total, cap["cap"])
    return {**state, "score": total, "pillars": pillars}


def impact(rows, variant):
    pairs = [(r["baseline"]["score"], r["shadows"][variant]["score"]) for r in rows if r["baseline"]["score"] is not None]
    deltas = [round(b-a, 1) for a, b in pairs]
    reversals = sum((a-c) * (b-d) < 0 for index, (a, b) in enumerate(pairs) for c, d in pairs[index+1:])
    return {"population_count": len(rows), "scored_count": len(pairs),
            "excluded_unscored_count": len(rows) - len(pairs), "scored_pair_count": len(pairs) * (len(pairs)-1) // 2,
            "changed": sum(x != 0 for x in deltas), "increased": sum(x > 0 for x in deltas),
            "decreased": sum(x < 0 for x in deltas), "mean_delta": round(sum(deltas)/len(deltas), 3) if deltas else None,
            "min_delta": min(deltas, default=None), "max_delta": max(deltas, default=None),
            "strict_pairwise_rank_reversals": reversals}


def audit_record(record):
    detail = record["candidate_detail"]
    return {"id": record["id"], "name": record["name"], "brand": record["brand"],
            "baseline": record["candidate"], "fully_reenriched": record["full_reenrichment"],
            "dimensions": (detail["_v4_module_breakdown"] or {}).get("dimensions", {}),
            "native_evidence_assessment": detail["native_evidence_assessment"],
            "shadows": {v: shadow_scores(record, v) for v in VARIANTS}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--baseline-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Report already exists; use a fresh path")
    inputs = args.input_root.resolve()
    files = {stage: replay.select_stage_files((inputs / "scripts/products").glob(pattern), stage, require_manifest=True)
             for stage, pattern in (("enrich", "output_*_enriched/enriched"), ("score", "output_*_scored/scored"), ("clean", "output_*/cleaned"))}
    hashes = {str(p.relative_to(inputs)): replay.sha(p) for paths in files.values() for p in paths}
    original = {}
    for path in files["score"]:
        for row in json.loads(path.read_text()):
            pid = replay.product_id(row)
            if pid in original:
                raise ValueError(f"Duplicate scored input: {pid}")
            original[pid] = replay.summary(row)
    baseline, digest = replay.load_baseline_report(args.baseline_report, original, hashes)
    targets = {pid for pid, row in baseline.items() if row["module"] == "probiotic"}
    if not CONTROLS <= targets:
        raise ValueError("Mandatory control absent from probiotic corpus")
    previous = json.loads(args.baseline_report.read_text())
    selected = set(previous["full_reenrichment_ids"])
    code = replay.implementation_hashes(ROOT)
    if code != previous["candidate_code_hashes"]:
        raise ValueError("Production implementation differs from the approved audit baseline")
    audit_files = [Path(__file__), ROOT / "scripts/audits/scoring_applicability_2026_09_03/audit_corpus.py", ROOT / "scripts/stage_manifest.py"]
    audit_hashes = {str(p): replay.sha(p) for p in audit_files}
    result, counts, priority = [], Counter(), defaultdict(set)
    start = time.monotonic()
    with ProcessPoolExecutor(max_workers=2, mp_context=get_context("spawn"), initializer=replay.init_worker,
                             initargs=(str(ROOT), str(inputs))) as pool:
        tasks = [(str(p), selected, targets) for p in files["enrich"]]
        for batch in pool.map(replay.process_file, tasks):
            for record in batch:
                pid, detail = record["id"], record["candidate_detail"]
                if record["candidate"] != baseline[pid]:
                    raise ValueError(f"Replay does not match current candidate: {pid}")
                replayed = shadow_scores(record, "baseline")
                if any(replayed[k] != baseline[pid][k] for k in ("score", "pillars", "status")):
                    raise ValueError(f"Public adapter baseline mismatch: {pid}")
                for strain in detail["probiotic_data"].get("clinical_strains", []):
                    if strain.get("clinical_id"):
                        priority[strain["clinical_id"]].add(pid)
                counts[record["candidate"]["status"]] += 1
                result.append(audit_record(record))
            if batch:
                print(f"Replayed {len(result)}/{len(targets)} probiotic labels", flush=True)
    if len(result) != len(targets) or {r["id"] for r in result} != targets:
        raise ValueError("Duplicate or missing probiotic input")
    if (code != replay.implementation_hashes(ROOT) or any(replay.sha(inputs / p) != h for p, h in hashes.items())
            or any(replay.sha(p) != h for p, h in audit_hashes.items())):
        raise ValueError("Inputs or implementation changed during audit")
    _, final_digest = replay.load_baseline_report(args.baseline_report, original, hashes)
    if final_digest != digest:
        raise ValueError("Baseline changed during audit")
    report = {"kind": "report_only_probiotic_rubric_sensitivity", "complete": True,
        "production_changes": False, "clinically_validated": False, "baseline_report": str(args.baseline_report),
        "baseline_sha256": digest, "implementation_hashes": code, "audit_hashes": audit_hashes, "input_hashes": hashes,
        "population_definition": "All current authenticated candidate rows routed probiotic; no blob replay",
        "count": len(result), "statuses": dict(counts), "errors": [], "baseline_disagreements": [],
        "fully_reenriched": sum(r["fully_reenriched"] for r in result), "elapsed_seconds": round(time.monotonic()-start, 1),
        "note": "Ablations keep denominators; no point redistribution, verdict recomputation, indication approval or superiority claim.",
        "impact": {v: impact(result, v) for v in VARIANTS},
        "review_priority": [{"clinical_id": k, "product_count": len(v), "product_ids": sorted(v)}
                            for k, v in sorted(priority.items(), key=lambda kv: (-len(kv[1]), kv[0]))],
        "controls": [r for r in result if r["id"] in CONTROLS], "products": sorted(result, key=lambda r: r["id"])}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as handle:
        json.dump(replay.json_safe(report), handle, indent=2, allow_nan=False)
        handle.write("\n")
    print(json.dumps({k: report[k] for k in ("complete", "count", "statuses", "elapsed_seconds", "impact")}))


if __name__ == "__main__":
    main()
