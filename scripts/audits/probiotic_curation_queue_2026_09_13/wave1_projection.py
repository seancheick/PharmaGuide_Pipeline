#!/usr/bin/env python3
"""Read-only Wave 1 projection. Nothing is written to the corpus or snapshots.

A. Evidence today vs. a what-if where every Wave 1 context is clinician_approved
   as authored (doses left exactly as recorded). Shows how many scored
   probiotics would gain dose applicability and why the rest would not.
B. Formulation: identity-code credit if the 2026-09-13 stub identities were
   live in enrichment (label strings matched through the production matcher).

    python3 scripts/audits/probiotic_curation_queue_2026_09_13/wave1_projection.py
"""
from __future__ import annotations
import collections, glob, json, sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))
import studied_formulas  # noqa: E402
from studied_formulas import clinical_strain_identity_matches  # noqa: E402
from scoring_v4.modules.probiotic_evidence import score_evidence  # noqa: E402
from scoring_v4.modules.probiotic_formulation import _score_identified_strain_codes  # noqa: E402

WAVE_1 = {"STRAIN_LGG", "STRAIN_LACTIS_BL04", "STRAIN_ACIDOPHILUS_NCFM", "STRAIN_PARACASEI_LPC37",
          "STRAIN_LONGUM_BB536", "STRAIN_RHAMNOSUS_HN001", "STRAIN_LACTIS_BI07", "STRAIN_LACTIS_HN019",
          "STRAIN_SUBTILIS_DE111", "STRAIN_SACCHAROMYCES"}
cfg = json.load(open(ROOT / "scripts/scoring_v4/config/quality_score.json"))
_form_block = next((v for v in cfg.values() if isinstance(v, dict) and str(v.get("_doc", "")).startswith("PR4")), {})
form_ref = (_form_block.get("archetype_reference") or {}).get("probiotic")

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

real = studied_formulas._clinical_strain_registry()
whatif = deepcopy(real)
approved_ids = []
for cid in WAVE_1:
    for c in whatif[cid].get("study_contexts", []):
        if c.get("authored_on") == "2026-09-13":
            c["review_status"] = "clinician_approved"; approved_ids.append(c["context_id"])

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
studied_formulas._clinical_strain_registry = lambda: real
deltas = [r["evidence_if_approved"] - r["evidence_today"] for r in rows]

# ---- B. identity-code credit from the new stubs -------------------------
stubs = [e for e in real.values() if isinstance(e.get("identity_verification"), dict)]
form_rows = []
for p in products:
    pd = p["probiotic_data"]
    old_ids = {r.get("clinical_id") for r in (pd.get("clinical_strains") or [])
               if isinstance(r, dict) and r.get("clinical_id") and not r.get("is_blocked")}
    new_ids = set(old_ids)
    for blend in pd.get("probiotic_blends") or []:
        for s in blend.get("strains") or []:
            hit = next((e["id"] for e in stubs if clinical_strain_identity_matches(str(s), e)), None)
            if hit:
                new_ids.add(hit)
    raw_delta = _score_identified_strain_codes(len(new_ids)) - _score_identified_strain_codes(len(old_ids))
    if raw_delta:
        form_rows.append({"dsld_id": p.get("dsld_id"), "brand": p.get("brand_name"), "name": p.get("product_name"),
                          "identities_before": len(old_ids), "identities_after": len(new_ids), "raw_formulation_delta": raw_delta})
pillar_scale = (20.0 / form_ref) if form_ref else None

report = {
    "_metadata": {"built": "2026-09-13", "read_only": True, "scored_probiotics": len(products),
                  "wave1_contexts_authored": len(approved_ids), "formulation_reference": form_ref},
    "A_evidence": {
        "products_carrying_wave1_identity": len(rows),
        "products_changed_today": 0,  # every Wave 1 context is pending; pending never scores
        "products_gaining_applicability_if_approved": sum(1 for r in rows if r["applicable_strains"]),
        "evidence_delta_if_approved": {"mean": round(sum(deltas) / len(deltas), 3) if deltas else 0,
                                       "max": max(deltas) if deltas else 0,
                                       "n_positive": sum(1 for d in deltas if d > 0)},
        "why_approved_contexts_do_not_apply": dict(reasons.most_common()),
        "per_identity": {k: {**v, "delta": round(v["delta"], 2)} for k, v in sorted(per_identity.items())},
        "gainers": sorted([r for r in rows if r["applicable_strains"]], key=lambda r: -(r["evidence_if_approved"] - r["evidence_today"]))[:25],
    },
    "B_formulation_stubs": {
        "products_with_identity_credit_change": len(form_rows),
        "raw_delta_distribution": dict(collections.Counter(r["raw_formulation_delta"] for r in form_rows)),
        "approx_shipped_pillar_delta_mean": round(sum(r["raw_formulation_delta"] for r in form_rows) / len(form_rows) * pillar_scale, 2) if form_rows and pillar_scale else None,
        "examples": sorted(form_rows, key=lambda r: -r["raw_formulation_delta"])[:15],
        "note": "Approximation: identity ownership in scoring also requires the label row proof (source_row_ref); real numbers come from a re-enrichment.",
    },
}
(OUT / "wave1_projection.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")
print(json.dumps({k: v for k, v in report["A_evidence"].items() if k != "gainers"}, indent=1))
print(json.dumps({k: v for k, v in report["B_formulation_stubs"].items() if k != "examples"}, indent=1))
print("gainers:", [(r["brand"], r["name"][:40], r["evidence_today"], r["evidence_if_approved"], r["applicable_strains"]) for r in report["A_evidence"]["gainers"][:10]])
