#!/usr/bin/env python3
"""Clinical curation queue for the native probiotic strain registry.

Read-only over scripts/data/clinically_relevant_strains.json and the enriched
brand corpora. For each registry identity: coverage leverage (how many scored
products carry it), representative products, what the registry already holds
(contexts, PMIDs, review states), and the review fields a clinician fills.
Evidence strength, applicability and review completeness are kept as three
separate columns; "not reviewed" is never written as "no evidence".

    python3 scripts/audits/probiotic_curation_queue_2026_09_13/build_queue.py
"""
from __future__ import annotations
import collections, glob, json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
PRIORITY_FIRST = ["STRAIN_LGG", "STRAIN_LACTIS_BB12", "STRAIN_LACTIS_HN019", "STRAIN_LACTIS_BI07",
                  "STRAIN_SACCHAROMYCES", "STRAIN_PLANTARUM_299V", "STRAIN_ACIDOPHILUS_NCFM", "STRAIN_LACTIS_BL04"]
REVIEW_FIELDS = ["human_vs_nonhuman_source", "studied_doses", "population", "indication_outcome", "duration",
                 "result_direction", "systematic_review_or_guideline_support", "dose_applicability_status",
                 "source_quality", "evidence_strength", "review_completeness", "reviewer_adjudication_status"]

reg = json.load(open(ROOT / "scripts/data/clinically_relevant_strains.json"))
entries = {e["id"]: e for e in reg["clinically_relevant_strains"]}

hits = collections.defaultdict(list)          # registry id -> [(dsld_id, brand, name, score)]
label_only = collections.Counter()            # label strain names with no registry identity
label_examples = collections.defaultdict(set)
scored_total = 0
score_by_id = {}
for f in glob.glob(str(ROOT / "scripts/products/output_*_scored/scored/*.json")):
    for p in json.load(open(f)):
        if p.get("_v4_module") == "probiotic" and p.get("_v4_quality_status") == "scored":
            score_by_id[str(p.get("dsld_id"))] = p.get("_v4_quality_score_100")
for f in glob.glob(str(ROOT / "scripts/products/output_*_enriched/enriched/*.json")):
    for p in json.load(open(f)):
        pd = p.get("probiotic_data") or {}
        if not pd or str(p.get("dsld_id")) not in score_by_id:
            continue
        scored_total += 1
        seen = set()
        for cs in pd.get("clinical_strains") or []:
            cid = (cs or {}).get("clinical_id")
            if cid and cid not in seen:
                seen.add(cid); hits[cid].append((str(p.get("dsld_id")), p.get("brand_name") or p.get("brandName"), p.get("product_name") or p.get("fullName"), score_by_id[str(p.get("dsld_id"))]))
        mapped_names = {str((cs or {}).get("strain") or "").lower() for cs in pd.get("clinical_strains") or []}
        for blend in pd.get("probiotic_blends") or []:
            for s in blend.get("strains") or []:
                name = re.sub(r"\s+", " ", str(s)).strip()
                if name and name.lower() not in mapped_names:
                    label_only[name] += 1; label_examples[name].add(f"{p.get('brand_name') or ''} — {p.get('product_name') or ''}")

def context_summary(e):
    ctxs = e.get("study_contexts") or []
    states = collections.Counter(c.get("review_status") for c in ctxs)
    pmids = sorted({pm for c in ctxs for pm in (c.get("source_pmids") or [])})
    held = [c.get("context_id") for c in ctxs if str(c.get("review_status") or "").endswith("pending_clinical_review") or "held" in str(c.get("review_status") or "")]
    doses = [c.get("dose") for c in ctxs if isinstance(c.get("dose"), dict) and c["dose"].get("values")]
    return {"context_count": len(ctxs), "context_review_states": dict(states), "source_pmids": pmids,
            "unresolved_or_held_contexts": held, "contexts_with_resolved_dose": len(doses),
            "notable_studies": len(e.get("notable_studies") or []), "evidence_level_in_registry": e.get("evidence_level"),
            "evidence_review": e.get("evidence_review")}

queue = []
for cid, e in entries.items():
    prods = sorted(hits.get(cid, []), key=lambda r: -(r[3] or 0))
    queue.append({
        "identity": cid, "standard_name": e.get("standard_name"), "aliases": e.get("aliases") or [],
        "affected_scored_products": len(prods),
        "representative_products": [{"dsld_id": d, "brand": b, "name": n, "score": s} for d, b, n, s in prods[:5]],
        "registry": context_summary(e),
        "priority_first": cid in PRIORITY_FIRST,
        "review": {k: "not_reviewed" for k in REVIEW_FIELDS},
    })
queue.sort(key=lambda q: (not q["priority_first"], -q["affected_scored_products"]))
for rank, q in enumerate(queue, 1):
    q["rank"] = rank

unmapped = [{"label_strain": n, "affected_scored_products": c, "examples": sorted(label_examples[n])[:3]} for n, c in label_only.most_common(40)]
report = {"_metadata": {"built": "2026-09-13", "scored_probiotics": scored_total, "registry_identities": len(entries),
          "rule": "evidence_strength, applicability and review_completeness are independent; not_reviewed is never no_evidence"},
          "queue": queue, "label_strains_without_registry_identity": unmapped}
(OUT / "queue.json").write_text(json.dumps(report, indent=2) + "\n")

lines = ["# Probiotic clinical curation queue — 2026-09-13", "",
         f"Scored probiotics: {scored_total}. Registry identities: {len(entries)}. Coverage leverage = scored products carrying the identity.", "",
         "Three independent columns for every item: evidence strength, applicability to this product/dose/outcome, review completeness. `not_reviewed` is never `no_evidence`.", "",
         "## Top 20 identities by coverage leverage", "", "| rank | identity | products | contexts | PMIDs | pending | representative |", "|---|---|---:|---:|---:|---:|---|"]
for q in sorted(queue, key=lambda q: -q["affected_scored_products"])[:20]:
    r = q["registry"]; rep = q["representative_products"][0] if q["representative_products"] else {}
    lines.append(f"| {q['rank']} | {q['identity']} ({q['standard_name']}) | {q['affected_scored_products']} | {r['context_count']} | {len(r['source_pmids'])} | {len(r['unresolved_or_held_contexts'])} | {rep.get('brand','')} — {str(rep.get('name',''))[:40]} |")
lines += ["", "## Full queue (priority strains first, then by leverage)", "", "| rank | identity | products | contexts | PMIDs | pending | review |", "|---|---|---:|---:|---:|---:|---|"]
for q in queue:
    r = q["registry"]
    lines.append(f"| {q['rank']} | {q['identity']} | {q['affected_scored_products']} | {r['context_count']} | {len(r['source_pmids'])} | {len(r['unresolved_or_held_contexts'])} | not_reviewed |")
lines += ["", "## Label strains carried by products but absent from the registry (candidates for new identities)", "", "| label strain | products | examples |", "|---|---:|---|"]
for u in unmapped[:25]:
    lines.append(f"| {u['label_strain']} | {u['affected_scored_products']} | {'; '.join(u['examples'])[:90]} |")
(OUT / "QUEUE.md").write_text("\n".join(lines) + "\n")
print("scored probiotics:", scored_total, "| identities with any product:", sum(1 for q in queue if q["affected_scored_products"]), "| label strains without identity:", len(label_only))
print("\n".join(lines[8:30]))
print("\nunmapped top 10:", [(u["label_strain"], u["affected_scored_products"]) for u in unmapped[:10]])
