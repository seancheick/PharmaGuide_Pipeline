#!/usr/bin/env python3
"""Render WAVE1_REPORT.md from the registry, queue and projection JSON (no hand-copied counts)."""
import collections, json
from pathlib import Path
OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
reg = json.load(open(ROOT / "scripts/data/clinically_relevant_strains.json"))
entries = {e["id"]: e for e in reg["clinically_relevant_strains"]}
proj = json.load(open(OUT / "wave1_projection.json"))
queue = json.load(open(OUT / "queue.json"))
W1 = ["STRAIN_LGG", "STRAIN_LACTIS_BL04", "STRAIN_ACIDOPHILUS_NCFM", "STRAIN_PARACASEI_LPC37", "STRAIN_LONGUM_BB536",
      "STRAIN_RHAMNOSUS_HN001", "STRAIN_LACTIS_BI07", "STRAIN_LACTIS_HN019", "STRAIN_SUBTILIS_DE111", "STRAIN_SACCHAROMYCES"]
new = [(cid, c) for cid, e in entries.items() for c in e.get("study_contexts", []) if c.get("authored_on") == "2026-09-13"]
joined = collections.Counter(comp for _, c in new for comp in c["components"])
directions = collections.Counter(o["direction"] for _, c in new for o in c["outcomes"] if o["hierarchy"] == "primary")
kinds = collections.Counter(o["kind"] for _, c in new for o in c["outcomes"])
designs = collections.Counter(c.get("study_design") for _, c in new)
tiers = collections.Counter(c.get("source_tier") for _, c in new)
families = collections.Counter(c["trial_family"] for _, c in new)
pmids = {p for _, c in new for p in c["source_pmids"]}
with_dose = sum(1 for _, c in new if c["dose"]["basis"] == "discrete_daily_arms")
combos = sum(1 for _, c in new if c["identity_scope"] == "combination")
A, B = proj["A_evidence"], proj["B_formulation_stubs"]
qrows = {q["identity"]: q for q in queue["queue"]}
L = ["# Wave 1 clinical curation report — 2026-09-13", "",
     "Read-only. The corpus was not re-enriched or re-scored; contract snapshots are untouched.", "",
     "## What was curated", "",
     f"- Contexts authored: {len(new)} across {len({cid for cid, _ in new})} owning identities, citing {len(pmids)} PubMed records read title/abstract on 2026-09-13.",
     f"- Combination contexts: {combos} (joined to every component through `components`; never individual applicability).",
     f"- Contexts with a machine-readable studied daily dose: {with_dose}; the rest are `unresolved` because the retrieved abstract did not state it or lost the exponent.",
     f"- Publication families: {len(families)} (`trial_family`), so papers from one cohort cannot count twice.",
     f"- Primary-outcome directions: {dict(directions)}; outcome kinds: {dict(kinds)}.",
     f"- Designs: {dict(designs)}; source tiers: {dict(tiers)}.",
     "- Every context is `source_verified_pending_clinical_review`. Nothing scores until a clinician sets `clinician_approved`.", "",
     "| identity | products (scored) | contexts total | authored Wave 1 | joined via combinations | mean Evidence today |", "|---|---:|---:|---:|---:|---:|"]
for cid in W1:
    e = entries[cid]; q = qrows[cid]
    L.append(f"| {cid} | {q['affected_scored_products']} | {len(e.get('study_contexts', []))} | {sum(1 for c, _ in new if c == cid)} | {joined.get(cid, 0)} | {q['mean_evidence_score']} |")
L += ["", "## Scoring effect", "",
      f"- Products carrying a Wave 1 identity: {A['products_carrying_wave1_identity']}. Products whose score changes today: {A['products_changed_today']}.",
      f"- If a clinician approved every Wave 1 context exactly as authored: products gaining dose applicability = {A['products_gaining_applicability_if_approved']}; mean Evidence delta = {A['evidence_delta_if_approved']['mean']}.",
      "- Why approved contexts still would not apply (context-product pairs):", ""]
for reason, n in A["why_approved_contexts_do_not_apply"].items():
    L.append(f"  - `{reason}`: {n}")
L += ["", "Reading: the bridge is correct and strict. It needs (1) studied daily doses resolved from full texts (abstracts lost the exponents for most DuPont/IFF and Morinaga trials), and (2) a clinician-approved policy for how close a label dose must be to a tested arm (today: exact equality with one arm). Combination and species-level contexts are recorded as research but can never become single-strain applicability by design.", "",
      "## Formulation effect of the new identities (approximation)", "",
      f"- Scored probiotics whose identity-code credit would change once the stubs are live in enrichment: {B['products_with_identity_credit_change']} of {proj['_metadata']['scored_probiotics']}.",
      f"- Raw component delta distribution (of 8 points): {B['raw_delta_distribution']}.",
      f"- Approximate shipped formulation-pillar mean delta for those products: {B['approx_shipped_pillar_delta_mean']} (reference {proj['_metadata']['formulation_reference']}).",
      f"- {B['note']}", "",
      "## Null, negative and conflicting evidence kept", ""]
for cid, c in new:
    prim = [o for o in c["outcomes"] if o["hierarchy"] == "primary"]
    if any(o["direction"] in ("null", "negative", "mixed") for o in prim):
        L.append(f"- {cid}: `{c['context_id']}` — primary {', '.join(o['name'] + ':' + o['direction'] for o in prim)} (PMIDs {', '.join(c['source_pmids'])})")
L += ["", "## Schema limitations met", "",
      "- Abstract text from the PubMed API strips italics, which removes genus/species tokens and superscript exponents; doses such as `1 x 10^10` arrive as `1 x 10`. Full-text reads are required before any dose can be approved.",
      "- Mass-dosed organisms (S. boulardii, 250-1000 mg/day) cannot be expressed in the CFU-only dose block; recorded as `unresolved` with the mass in limitations.",
      "- Studies of a strain plus a non-registry strain (for example BB536 + MCC1274, HN001 + LE16) cannot be authored as combinations; B. lactis 420 was added as an identity for that reason. MCC1274, LE16 and B. lactis DN-173 010 remain candidates.",
      "- Meta-analyses have no single dose or sample size; `hierarchy: unresolved` is used for strain-level rankings inside class-level pooled analyses.", "",
      "## Remaining", "",
      f"- Unreviewed identities after Wave 1: {sum(1 for q in queue['queue'] if q['registry']['context_count'] == 0)} of {len(queue['queue'])}.",
      "- Wave 2 (13 identities) and Wave 3 (the rest, including the 56 label-resolution stubs) are queued in QUEUE.md.",
      "- Owner decisions: (a) full-text dose resolution for the Wave 1 contexts with `unresolved` doses; (b) the dose-window policy for applicability; (c) whether to run the curation sprint before or after the single full re-score."]
(OUT / "WAVE1_REPORT.md").write_text("\n".join(L) + "\n")
print("\n".join(L[:14]))
