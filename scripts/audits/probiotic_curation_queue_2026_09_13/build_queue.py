#!/usr/bin/env python3
"""Clinical curation queue for the native probiotic strain registry (v2, 2026-09-13).

Read-only over scripts/data/clinically_relevant_strains.json and the enriched +
scored brand corpora. For every registry identity (reviewed v1 identities and
the 2026-09-13 label-resolution stubs alike):

  * coverage leverage  — scored probiotic products whose label strings resolve
    to the identity through the production matcher (so stubs added after the
    last enrichment run are counted the same way as v1 identities);
  * evidence impact    — how many of those products sit at Evidence 0 or at the
    "research present, applicability unestablished" plateau (8/20);
  * uncertainty        — no contexts yet (2.0), pending/held contexts (1.5),
    at least one clinician-approved context (1.0);
  * priority           — leverage × evidence_impact_share × uncertainty, plus
    a wave assignment (Wave 1 / 2 fixed by the owner; Wave 3 by priority).

Evidence strength, applicability and review completeness are three separate
columns; "not reviewed" is never written as "no evidence". The label-identity
classification (species-only / unregistered designation / genus-only /
unresolved text) is emitted beside the queue so species names are never turned
into strain identities by accident.

    python3 scripts/audits/probiotic_curation_queue_2026_09_13/build_queue.py
"""
from __future__ import annotations
import collections, glob, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))
from studied_formulas import clinical_strain_identity_matches  # noqa: E402
from probiotic_measurements import label_strain_identity_resolution  # noqa: E402

BUILT = "2026-09-13"
WAVE_1 = ["STRAIN_LGG", "STRAIN_LACTIS_BL04", "STRAIN_ACIDOPHILUS_NCFM", "STRAIN_PARACASEI_LPC37",
          "STRAIN_LONGUM_BB536", "STRAIN_RHAMNOSUS_HN001", "STRAIN_LACTIS_BI07", "STRAIN_LACTIS_HN019",
          "STRAIN_SUBTILIS_DE111", "STRAIN_SACCHAROMYCES"]
WAVE_2 = ["STRAIN_COAGULANS_IS2", "STRAIN_COAGULANS_MTCC5856", "STRAIN_ACIDOPHILUS_DDS1", "STRAIN_LACTIS_BB12",
          "STRAIN_PLANTARUM_299V", "STRAIN_ACIDOPHILUS_LA5", "STRAIN_BREVE_M16V", "STRAIN_HELVETICUS_R0052",
          "STRAIN_PLANTARUM_LP01", "STRAIN_COAGULANS_GBI30", "STRAIN_RHAMNOSUS_GR1", "STRAIN_FERMENTUM_RC14",
          "STRAIN_LONGUM_R0175"]
REVIEW_FIELDS = ["human_vs_nonhuman_source", "studied_doses", "population", "indication_outcome", "duration",
                 "result_direction", "systematic_review_or_guideline_support", "dose_applicability_status",
                 "source_quality", "evidence_strength", "review_completeness", "reviewer_adjudication_status"]
PLATEAU = 8.0  # research_present_applicability_unestablished

reg = json.load(open(ROOT / "scripts/data/clinically_relevant_strains.json"))
entries = {e["id"]: e for e in reg["clinically_relevant_strains"]}
by_id = entries

scored = {}
for f in glob.glob(str(ROOT / "scripts/products/output_*_scored/scored/*.json")):
    for p in json.load(open(f)):
        if p.get("_v4_module") == "probiotic" and p.get("_v4_quality_status") == "scored":
            ev = ((p.get("quality_pillars_v4") or {}).get("evidence") or {}).get("score")
            scored[str(p.get("dsld_id"))] = {"total": p.get("_v4_quality_score_100"), "evidence": ev}

hits = collections.defaultdict(dict)            # identity -> {dsld_id: (brand, name, total, evidence)}
label_states = collections.Counter(); label_slots = collections.Counter()
label_rows = collections.defaultdict(lambda: {"products": set(), "examples": set()})
resolution_cache = {}
scored_probiotics = 0
for f in glob.glob(str(ROOT / "scripts/products/output_*_enriched/enriched/*.json")):
    for p in json.load(open(f)):
        pd = p.get("probiotic_data") or {}
        did = str(p.get("dsld_id"))
        if not pd or did not in scored:
            continue
        scored_probiotics += 1
        brand = p.get("brand_name") or p.get("brandName") or ""
        name = p.get("product_name") or p.get("fullName") or ""
        for blend in pd.get("probiotic_blends") or []:
            for s in blend.get("strains") or []:
                label = re.sub(r"\s+", " ", str(s)).strip()
                if not label:
                    continue
                if label not in resolution_cache:
                    cid = next((e["id"] for e in entries.values() if clinical_strain_identity_matches(label, e)), None)
                    resolution_cache[label] = (cid, label_strain_identity_resolution(label, cid, by_id)["resolution"])
                cid, state = resolution_cache[label]
                if cid:
                    hits[cid].setdefault(did, (brand, name, scored[did]["total"], scored[did]["evidence"]))
                label_rows[label]["products"].add(did); label_rows[label]["examples"].add(f"{brand} — {name}"[:90])
                label_rows[label]["state"] = state


def context_summary(e):
    ctxs = e.get("study_contexts") or []
    states = collections.Counter(c.get("review_status") for c in ctxs)
    pmids = sorted({pm for c in ctxs for pm in (c.get("source_pmids") or [])})
    return {"context_count": len(ctxs), "review_states": dict(states), "source_pmids": pmids,
            "approved_contexts": [c["context_id"] for c in ctxs if c.get("review_status") == "clinician_approved"],
            "pending_or_held_contexts": [c.get("context_id") for c in ctxs if c.get("review_status") in
                                         ("source_verified_pending_clinical_review", "adjudication_required")],
            "conditions": sorted({c.get("condition") for c in ctxs if c.get("condition")}),
            "legacy_signoff": (e.get("cfu_thresholds") or {}).get("dr_pham_signoff") is True,
            "legacy_primary_pmid": ((e.get("cfu_thresholds") or {}).get("evidence") or {}).get("pmid"),
            "identity_verification": (e.get("identity_verification") or {}).get("status")}


queue = []
for cid, e in entries.items():
    prods = hits.get(cid, {})
    n = len(prods)
    ev_scores = [v[3] for v in prods.values() if isinstance(v[3], (int, float))]
    stuck = sum(1 for s in ev_scores if s <= PLATEAU)
    impact_share = (stuck / n) if n else 0.0
    summary = context_summary(e)
    if summary["approved_contexts"]:
        uncertainty = 1.0
    elif summary["context_count"]:
        uncertainty = 1.5
    else:
        uncertainty = 2.0
    priority = round(n * (0.25 + impact_share) * uncertainty, 1)
    wave = 1 if cid in WAVE_1 else 2 if cid in WAVE_2 else 3
    rep = sorted(prods.items(), key=lambda kv: -(kv[1][2] or 0))[:3]
    queue.append({
        "identity": cid, "standard_name": e.get("standard_name"), "aliases": e.get("aliases", []),
        "identity_only_stub": "identity_verification" in e,
        "affected_scored_products": n, "affected_brands": len({v[0] for v in prods.values()}),
        "evidence_at_or_below_plateau": stuck, "evidence_impact_share": round(impact_share, 3),
        "mean_evidence_score": round(sum(ev_scores) / len(ev_scores), 2) if ev_scores else None,
        "uncertainty_factor": uncertainty, "priority_score": priority, "wave": wave,
        "representative_products": [{"dsld_id": d, "brand": b, "name": nm, "score": sc, "evidence": ev} for d, (b, nm, sc, ev) in rep],
        "registry": summary,
        "review": {k: "not_reviewed" for k in REVIEW_FIELDS},
    })
queue.sort(key=lambda q: (q["wave"], -q["priority_score"], -q["affected_scored_products"]))
for i, q in enumerate(queue, 1):
    q["rank"] = i

classification = collections.defaultdict(list)
for label, row in label_rows.items():
    classification[row["state"]].append({"label": label, "affected_scored_products": len(row["products"]),
                                         "examples": sorted(row["examples"])[:3]})
for state in classification:
    classification[state].sort(key=lambda r: -r["affected_scored_products"])
class_totals = {s: {"strings": len(rows), "product_slots": sum(r["affected_scored_products"] for r in rows)}
                for s, rows in classification.items()}

report = {"_metadata": {"built": BUILT, "scored_probiotics": scored_probiotics, "registry_identities": len(entries),
                        "priority_formula": "affected_scored_products x (0.25 + share of those at Evidence <= 8) x uncertainty (2.0 no contexts, 1.5 pending/held, 1.0 approved)",
                        "waves": {"1": WAVE_1, "2": WAVE_2, "3": "remaining identities by priority"},
                        "rule": "evidence_strength, applicability and review_completeness are independent; not_reviewed is never no_evidence; species-only labels never inherit a strain identity"},
          "queue": queue,
          "label_identity_classification": {"totals": class_totals, **classification}}
(OUT / "queue.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")

lines = [f"# Probiotic clinical curation queue — {BUILT} (v2)", "",
         f"Scored probiotics: {scored_probiotics}. Registry identities: {len(entries)} "
         f"({sum(1 for q in queue if q['identity_only_stub'])} identity-only stubs added 2026-09-13).",
         "", f"Priority = {report['_metadata']['priority_formula']}.", "",
         "Three independent columns for every item: evidence strength, applicability to this product/dose/outcome, review completeness. `not_reviewed` is never `no_evidence`.", ""]
for wave in (1, 2, 3):
    rows = [q for q in queue if q["wave"] == wave]
    lines += [f"## Wave {wave} ({len(rows)} identities)", "",
              "| rank | identity | products | brands | Ev<=8 | mean Ev | ctx | approved | pending | priority | representative |",
              "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    for q in rows[:60] if wave == 3 else rows:
        r = q["registry"]; rep = q["representative_products"][0] if q["representative_products"] else {}
        stub = " (stub)" if q["identity_only_stub"] else ""
        lines.append(f"| {q['rank']} | {q['identity']}{stub} | {q['affected_scored_products']} | {q['affected_brands']} | {q['evidence_at_or_below_plateau']} | {q['mean_evidence_score'] if q['mean_evidence_score'] is not None else '—'} | {r['context_count']} | {len(r['approved_contexts'])} | {len(r['pending_or_held_contexts'])} | {q['priority_score']} | {rep.get('brand','')} — {str(rep.get('name',''))[:38]} |")
    lines.append("")
lines += ["## Label identity classification (scored probiotics)", "",
          "| state | strings | product slots |", "|---|---:|---:|"]
for s, t in sorted(class_totals.items(), key=lambda kv: -kv[1]["product_slots"]):
    lines.append(f"| {s} | {t['strings']} | {t['product_slots']} |")
lines += ["", "### Species-only labels (never inherit a strain's research)", "", "| label | products |", "|---|---:|"]
for r in classification.get("species_only", [])[:25]:
    lines.append(f"| {r['label']} | {r['affected_scored_products']} |")
lines += ["", "### Printed designations with no registry identity yet", "", "| label | products | example |", "|---|---:|---|"]
for r in classification.get("strain_designation_unregistered", [])[:30]:
    lines.append(f"| {r['label']} | {r['affected_scored_products']} | {'; '.join(r['examples'])[:80]} |")
(OUT / "QUEUE.md").write_text("\n".join(lines) + "\n")
print(f"queue identities={len(queue)} scored_probiotics={scored_probiotics}")
print("classification:", json.dumps(class_totals))
for q in queue[:12]:
    print(q["rank"], q["wave"], q["identity"], q["affected_scored_products"], q["evidence_at_or_below_plateau"], q["priority_score"])
