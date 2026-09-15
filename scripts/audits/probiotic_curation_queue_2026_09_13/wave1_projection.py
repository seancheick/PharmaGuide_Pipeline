#!/usr/bin/env python3
"""Read-only Wave 1 projection. Nothing is written to the corpus or snapshots.

A. The historical 2026-09-13 approval hypothesis replayed against the loaded
   registry and corpus (doses left exactly as recorded). This does not assume
   that the original Wave 1 contexts remain pending today.
B. The former count-only Formulation projection is superseded by the current
   source-owned scorer. Use the frozen production replay for numeric results.
Reports print to stdout; writing a new report requires --output PATH.

    python3 scripts/audits/probiotic_curation_queue_2026_09_13/wave1_projection.py
"""
from __future__ import annotations
import argparse, collections, glob, json, sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
import studied_formulas  # noqa: E402
from scoring_v4.modules.probiotic_evidence import score_evidence  # noqa: E402

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output", type=Path, help="Write a new report to this explicit path.")
args = parser.parse_args()

WAVE_1 = {"STRAIN_LGG", "STRAIN_LACTIS_BL04", "STRAIN_ACIDOPHILUS_NCFM", "STRAIN_PARACASEI_LPC37",
          "STRAIN_LONGUM_BB536", "STRAIN_RHAMNOSUS_HN001", "STRAIN_LACTIS_BI07", "STRAIN_LACTIS_HN019",
          "STRAIN_SUBTILIS_DE111", "STRAIN_SACCHAROMYCES"}

scored = {}
for f in glob.glob(str(ROOT / "scripts/products/output_*_scored/scored/*.json")):
    for p in json.load(open(f)):
        if p.get("_v4_module") == "probiotic" and p.get("_v4_quality_status") == "scored":
            scored[str(p.get("dsld_id"))] = p
products = []
for f in glob.glob(str(ROOT / "scripts/products/output_*_enriched/enriched/*.json")):
    for p in json.load(open(f)):
        if str(p.get("dsld_id")) in scored and p.get("probiotic_data"):
            products.append(p)

registry_loader = studied_formulas._clinical_strain_registry
real = registry_loader()
whatif = deepcopy(real)
approved_ids = []
for cid in WAVE_1:
    for c in whatif[cid].get("study_contexts", []):
        if c.get("authored_on") == "2026-09-13":
            c["review_status"] = "clinician_approved"
            # Ephemeral what-if provenance; this copied registry is never persisted.
            c["clinical_review"] = {
                "reviewer": "hypothetical_wave1_projection",
                "reviewed_at": "2026-09-13T00:00:00Z",
                "scope": "identity_dose_outcome_applicability",
            }
            approved_ids.append(c["context_id"])

# ---- A. evidence today vs what-if approval --------------------------------
rows = []
reasons = collections.Counter(); per_identity = collections.defaultdict(lambda: {"products": 0, "applicable": 0, "delta": 0.0})
for p in products:
    ids = {r.get("clinical_id") for r in (p["probiotic_data"].get("clinical_strains") or []) if isinstance(r, dict)}
    if not ids & WAVE_1:
        continue
    studied_formulas._clinical_strain_registry = lambda: real
    e0 = score_evidence(p)
    studied_formulas._clinical_strain_registry = lambda: whatif
    e1 = score_evidence(p)
    a1 = studied_formulas.assess_probiotic_evidence(p)
    applicable = [s for s in a1["strain_assessments"] if s["status"] == "strain_dose_applicable"]
    for s in a1["strain_assessments"]:
        if s.get("clinical_id") in WAVE_1:
            for c in s["study_contexts"]:
                if c.get("review_status") == "clinician_approved" and c.get("status") == "source_context_recorded":
                    reasons[c.get("applicability_reason")] += 1
    for cid in ids & WAVE_1:
        per_identity[cid]["products"] += 1
        per_identity[cid]["applicable"] += any(s.get("clinical_id") == cid for s in applicable)
        per_identity[cid]["delta"] += e1["score"] - e0["score"]
    rows.append({"dsld_id": p.get("dsld_id"), "brand": p.get("brand_name"), "name": p.get("product_name"),
                 "evidence_today": e0["score"], "evidence_if_approved": e1["score"],
                 "applicable_strains": [s["clinical_id"] for s in applicable]})
studied_formulas._clinical_strain_registry = registry_loader
deltas = [r["evidence_if_approved"] - r["evidence_today"] for r in rows]

report = {
    "_metadata": {"built": datetime.now(timezone.utc).isoformat(), "hypothesis_authored_on": "2026-09-13",
                  "read_only": True, "scored_probiotics": len(products),
                  "wave1_contexts_authored": len(approved_ids)},
    "A_evidence": {
        "status": "historical_approval_hypothesis",
        "note": "Historical approval hypothesis evaluated against the registry and corpus loaded for this run; approval status is not assumed to remain pending.",
        "products_carrying_wave1_identity": len(rows),
        "products_with_applicability_under_hypothesis": sum(1 for r in rows if r["applicable_strains"]),
        "evidence_delta_if_approved": {"mean": round(sum(deltas) / len(deltas), 3) if deltas else 0,
                                       "max": max(deltas) if deltas else 0,
                                       "n_positive": sum(1 for d in deltas if d > 0)},
        "why_approved_contexts_do_not_apply": dict(reasons.most_common()),
        "per_identity": {k: {**v, "delta": round(v["delta"], 2)} for k, v in sorted(per_identity.items())},
        "applicable_examples": sorted([r for r in rows if r["applicable_strains"]], key=lambda r: -(r["evidence_if_approved"] - r["evidence_today"]))[:25],
    },
    "B_formulation_stubs": {
        "status": "superseded",
        "note": "Superseded by the source-owned current scorer; use the existing frozen production replay for numeric Formulation comparisons.",
        "replacement": "scripts/audits/scoring_boundary_audit_2026_09_15/replay.py",
    },
}
if args.output:
    args.output.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")
print(json.dumps({k: v for k, v in report["A_evidence"].items() if k != "applicable_examples"}, indent=1))
print(json.dumps(report["B_formulation_stubs"], indent=1))
print("applicable examples:", [(r["brand"], r["name"][:40], r["evidence_today"], r["evidence_if_approved"], r["applicable_strains"]) for r in report["A_evidence"]["applicable_examples"][:10]])
