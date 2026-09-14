#!/usr/bin/env python3
"""Read-only Wave 2 projection. Nothing is written to the corpus or snapshots.

Evidence today vs. a what-if where every Wave 2 context is clinician_approved
as authored (doses left exactly as recorded). Shows how many scored probiotics
would gain dose applicability and why the rest would not. Wave 2 adds no
identity stubs, so there is no formulation section (see wave1_projection.py).

    python3 scripts/audits/probiotic_curation_queue_2026_09_13/wave2_projection.py
"""
from __future__ import annotations
import collections, glob, json, sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))
import studied_formulas  # noqa: E402
from scoring_v4.modules.probiotic_evidence import score_evidence  # noqa: E402

WAVE_2 = {"STRAIN_COAGULANS_IS2", "STRAIN_COAGULANS_MTCC5856", "STRAIN_ACIDOPHILUS_DDS1",
          "STRAIN_PLANTARUM_299V", "STRAIN_ACIDOPHILUS_LA5", "STRAIN_LACTIS_BB12",
          "STRAIN_HELVETICUS_R0052", "STRAIN_LONGUM_R0175", "STRAIN_RHAMNOSUS_GR1",
          "STRAIN_FERMENTUM_RC14", "STRAIN_COAGULANS_GBI30", "STRAIN_BREVE_M16V",
          "STRAIN_PLANTARUM_LP01"}

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

if not products:
    # The enriched/scored corpus is not part of the repository. Refuse to write
    # product-level zeros that would read as "no product carries a Wave 2
    # identity"; record honestly that the projection was not computable here.
    n_authored = sum(1 for e in studied_formulas._clinical_strain_registry().values()
                     for c in e.get("study_contexts", []) if c.get("authored_on") == "2026-09-14")
    report = {"_metadata": {"built": "2026-09-14", "read_only": True, "corpus_present": False,
                            "scored_probiotics": 0, "wave2_contexts_authored": n_authored},
              "A_evidence": None,
              "note": ("scripts/products/output_*_{enriched,scored} not present in this checkout; "
                       "re-run this script in a checkout that has the corpus to compute the "
                       "evidence what-if (wave1_projection.json was built against 548 scored probiotics).")}
    (OUT / "wave2_projection.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps(report, indent=1)); sys.exit(0)

real = studied_formulas._clinical_strain_registry()
whatif = deepcopy(real)
approved_ids = []
for cid, entry in whatif.items():
    for c in entry.get("study_contexts", []):
        if c.get("authored_on") == "2026-09-14":
            c["review_status"] = "clinician_approved"; approved_ids.append(c["context_id"])

rows = []
reasons = collections.Counter(); per_identity = collections.defaultdict(lambda: {"products": 0, "applicable": 0, "delta": 0.0})
for p in products:
    ids = {r.get("clinical_id") for r in (p["probiotic_data"].get("clinical_strains") or []) if isinstance(r, dict)}
    if not ids & WAVE_2:
        continue
    studied_formulas._clinical_strain_registry = lambda: real
    e0 = score_evidence(p)
    studied_formulas._clinical_strain_registry = lambda: whatif
    e1 = score_evidence(p)
    a1 = studied_formulas.assess_probiotic_evidence(p)
    applicable = [s for s in a1["strain_assessments"] if s["status"] == "strain_dose_applicable"]
    for s in a1["strain_assessments"]:
        if s.get("clinical_id") in WAVE_2:
            for c in s["study_contexts"]:
                if c.get("review_status") == "clinician_approved" and c.get("status") == "source_context_recorded":
                    reasons[c.get("applicability_reason")] += 1
    for cid in ids & WAVE_2:
        per_identity[cid]["products"] += 1
        per_identity[cid]["applicable"] += any(s.get("clinical_id") == cid for s in applicable)
        per_identity[cid]["delta"] += e1["score"] - e0["score"]
    rows.append({"dsld_id": p.get("dsld_id"), "brand": p.get("brand_name"), "name": p.get("product_name"),
                 "evidence_today": e0["score"], "evidence_if_approved": e1["score"],
                 "applicable_strains": [s["clinical_id"] for s in applicable]})
studied_formulas._clinical_strain_registry = lambda: real
deltas = [r["evidence_if_approved"] - r["evidence_today"] for r in rows]

report = {
    "_metadata": {"built": "2026-09-14", "read_only": True, "scored_probiotics": len(products),
                  "wave2_contexts_authored": len(approved_ids)},
    "A_evidence": {
        "products_carrying_wave2_identity": len(rows),
        "products_changed_today": 0,  # every Wave 2 context is pending; pending never scores
        "products_gaining_applicability_if_approved": sum(1 for r in rows if r["applicable_strains"]),
        "evidence_delta_if_approved": {"mean": round(sum(deltas) / len(deltas), 3) if deltas else 0,
                                       "max": max(deltas) if deltas else 0,
                                       "n_positive": sum(1 for d in deltas if d > 0)},
        "why_approved_contexts_do_not_apply": dict(reasons.most_common()),
        "per_identity": {k: {**v, "delta": round(v["delta"], 2)} for k, v in sorted(per_identity.items())},
        "gainers": sorted([r for r in rows if r["applicable_strains"]], key=lambda r: -(r["evidence_if_approved"] - r["evidence_today"]))[:25],
    },
}
(OUT / "wave2_projection.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")
print(json.dumps({k: v for k, v in report["A_evidence"].items() if k != "gainers"}, indent=1))
print("gainers:", [(r["brand"], (r["name"] or "")[:40], r["evidence_today"], r["evidence_if_approved"], r["applicable_strains"]) for r in report["A_evidence"]["gainers"][:10]])
