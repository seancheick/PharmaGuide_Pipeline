#!/usr/bin/env python3
"""Render WAVE2_REPORT.md from the registry, queue and projection JSON (no hand-copied counts)."""
import collections, json
from pathlib import Path
OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
reg = json.load(open(ROOT / "scripts/data/clinically_relevant_strains.json"))
entries = {e["id"]: e for e in reg["clinically_relevant_strains"]}
proj = json.load(open(OUT / "wave2_projection.json"))
queue = json.load(open(OUT / "queue.json"))
W2 = ["STRAIN_COAGULANS_IS2", "STRAIN_COAGULANS_MTCC5856", "STRAIN_ACIDOPHILUS_DDS1", "STRAIN_PLANTARUM_299V",
      "STRAIN_ACIDOPHILUS_LA5", "STRAIN_LACTIS_BB12", "STRAIN_BREVE_M16V", "STRAIN_HELVETICUS_R0052",
      "STRAIN_PLANTARUM_LP01", "STRAIN_COAGULANS_GBI30", "STRAIN_RHAMNOSUS_GR1", "STRAIN_FERMENTUM_RC14",
      "STRAIN_LONGUM_R0175"]
new = [(cid, c) for cid, e in entries.items() for c in e.get("study_contexts", []) if c.get("authored_on") == "2026-09-14"]
joined = collections.Counter(comp for _, c in new for comp in c["components"])
directions = collections.Counter(o["direction"] for _, c in new for o in c["outcomes"] if o["hierarchy"] == "primary")
all_directions = collections.Counter(o["direction"] for _, c in new for o in c["outcomes"])
kinds = collections.Counter(o["kind"] for _, c in new for o in c["outcomes"])
designs = collections.Counter(c.get("study_design") for _, c in new)
tiers = collections.Counter(c.get("source_tier") for _, c in new)
families = collections.Counter(c["trial_family"] for _, c in new)
pmids = {p for _, c in new for p in c["source_pmids"]}
with_dose = sum(1 for _, c in new if c["dose"]["basis"] == "discrete_daily_arms")
combos = sum(1 for _, c in new if c["identity_scope"] == "combination")
qrows = {q["identity"]: q for q in queue["queue"]}
L = ["# Wave 2 clinical curation report — 2026-09-14", "",
     "Read-only. The corpus was not re-enriched or re-scored; contract snapshots are untouched.",
     "No identity stubs were added: the DDS-1 combination partner already exists as `STRAIN_LACTIS_UABla12`,",
     "and trials whose partner strains have no registry identity stay reviewed-not-recorded (wave2_read_log.md).", "",
     "## What was curated", "",
     f"- Contexts authored: {len(new)} across {len({cid for cid, _ in new})} owning identities, citing {len(pmids)} PubMed records read title/abstract on 2026-09-14 (full read log: wave2_read_log.md).",
     f"- Combination contexts: {combos} (joined to every component through `components`; never individual applicability). RC-14, R0175, UABla-12, CRL-431 and LGG join only through combinations.",
     f"- Contexts with a machine-readable studied daily dose: {with_dose}; the rest are `unresolved` because the retrieved abstract did not state it or lost the exponent.",
     f"- Publication families: {len(families)} (`trial_family`), so papers from one cohort cannot count twice.",
     f"- Primary-outcome directions: {dict(directions)}; all-outcome directions: {dict(all_directions)}; outcome kinds: {dict(kinds)}.",
     f"- Designs: {dict(designs)}; source tiers: {dict(tiers)}.",
     "- Every context is `source_verified_pending_clinical_review`. Nothing scores until a clinician sets `clinician_approved`.", "",
     "| identity | products (scored) | contexts total | authored Wave 2 | joined via combinations | mean Evidence today |", "|---|---:|---:|---:|---:|---:|"]
for cid in W2:
    e = entries[cid]; q = qrows[cid]
    L.append(f"| {cid} | {q['affected_scored_products']} | {len(e.get('study_contexts', []))} | {sum(1 for c, _ in new if c == cid)} | {joined.get(cid, 0)} | {q['mean_evidence_score']} |")
L += ["", "## Scoring effect", ""]
if proj.get("A_evidence"):
    A = proj["A_evidence"]
    L += [f"- Products carrying a Wave 2 identity: {A['products_carrying_wave2_identity']}. Products whose score changes today: {A['products_changed_today']}.",
          f"- If a clinician approved every Wave 2 context exactly as authored: products gaining dose applicability = {A['products_gaining_applicability_if_approved']}; mean Evidence delta = {A['evidence_delta_if_approved']['mean']}.",
          "- Why approved contexts still would not apply (context-product pairs):", ""]
    for reason, n in A["why_approved_contexts_do_not_apply"].items():
        L.append(f"  - `{reason}`: {n}")
else:
    L += ["- Nothing changes today: every Wave 2 context is pending and pending never scores.",
          f"- The product-level what-if was NOT computable in this checkout ({proj['note']})",
          "- Owner action: run `wave2_projection.py` then re-run this builder in the corpus checkout to fill this section."]
L += ["", "## Null, negative and conflicting evidence kept", ""]
for cid, c in new:
    flagged = [o for o in c["outcomes"] if o["direction"] in ("null", "negative", "mixed")]
    if flagged:
        L.append(f"- {cid}: `{c['context_id']}` — {', '.join(o['name'] + ':' + o['direction'] for o in flagged)} (PMIDs {', '.join(c['source_pmids'])})")
L += ["", "## Schema limitations met", "",
      "- Abstract text from the PubMed API strips superscript exponents; doses such as `4 x 10^9` can arrive as `4 x 10`. Full-text reads are required before any dose can be approved.",
      "- Combination totals (for example DDS-1 + UABla-12 at 5 x 10^9 CFU/day) are recorded on the combination context only and never become an individual-strain dose.",
      "- Two recorded combination trials used a product with one extra non-registry strain (LC-01; an unnamed B. longum subsp. infantis). Both are nulls, recorded with the formulation named in limitations for the clinician to weigh.",
      "- Meta-analyses have no single dose or sample size; `hierarchy: unresolved` is used for strain-level rankings inside class-level pooled analyses, and endpoint hierarchies the abstract did not state are `unresolved` rather than guessed.", "",
      "## Remaining", "",
      f"- Unreviewed identities after Wave 2: {sum(1 for q in queue['queue'] if entries[q['identity']].get('study_contexts') is None or not entries[q['identity']].get('study_contexts'))} of {len(queue['queue'])}.",
      "- Wave 3 (the rest, including the 56 label-resolution stubs) remains queued in QUEUE.md; LP01's controlled evidence base is largely non-registry multi-strain formulations (see wave2_read_log.md).",
      "- Owner decisions: (a) full-text dose resolution for contexts with `unresolved` doses; (b) the dose-window applicability policy; (c) whether the UABla-12 solo arm of PMID 32019158 and the classic BB-12 colic/daycare trials get their own curation pass."]
(OUT / "WAVE2_REPORT.md").write_text("\n".join(L) + "\n")
print("\n".join(L[:16]))
