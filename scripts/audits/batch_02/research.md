# Med–Nutrient Content Audit — Batch 02

Started 2026-07-23 (after batch 01 merged: pipeline 320ad0df / app 5638b54).
Same discipline + the LOCKED RULE from batch 01: **`verified` requires EVERY
user-visible field (relationship, mechanism, clinical_impact, recommendation,
consumer copy) to be defensible AND a real cited source to support the specific
claim** — not just the relationship. Placeholder sources (generic NIH ODS nutrient
sheet / vague "PubMed — <topic>") and over-prescriptive copy ⇒ needs_revision.

Marks status only; fixes are the tracked follow-up. `verified` shows; `needs_revision`/`rejected` suppressed by the B1.2 publication rule.

## The 10 entries + preliminary read (to be confirmed by the 3 verifiers)

| id | drug → nutrient | type | prelim read |
|---|---|---|---|
| DEP_OCP_VITAMINB6 | oral contraceptives → B6 | depletion | **needs_revision?** mechanism is OLD high-estrogen pills; modern low-dose evidence weaker; source = NIH ODS placeholder |
| DEP_OCP_FOLATE | oral contraceptives → folate | depletion | **needs_revision?** modern low-dose OCP folate effect small/inconsistent; NIH ODS placeholder; pre-pregnancy advice ≠ depletion claim |
| DEP_ANTICOAGULANTS_VITAMINK | warfarin → vitamin K | functional_antagonism | **verified?** VKORC1 mechanism ✓, correctly typed, copy is CORRECT ("don't supplement, keep intake consistent"); Hirsh Chest 2001 — confirm |
| DEP_METHOTREXATE_FOLATE | methotrexate → folate | functional_antagonism | **needs_revision?** relationship + clinician-directed copy sound, but source = vague "PubMed —" placeholder (needs Shea/Cochrane 2013) |
| DEP_ISONIAZID_VITAMINB6 | isoniazid → B6 | depletion | **verified?** classic; DailyMed INH label real; but one source is a vague "PubMed —" placeholder to firm |
| DEP_SSRIS_SODIUM | SSRIs → sodium | monitoring_stability | **needs_revision?** SIADH/hyponatremia real + correctly typed, but source = NIH ODS Sodium placeholder (doesn't cover SSRI-SIADH) |
| DEP_ORLISTAT_VITAMIND | orlistat → vitamin D | depletion | **verified?** fat-soluble malabsorption; DailyMed XENICAL label recommends A/D/E/K 2h apart — confirm |
| DEP_CHOLESTYRAMINE_VITAMINK | cholestyramine → vitamin K | depletion | **verified?** bile-acid sequestrant; DailyMed label covers fat-soluble/K — confirm |
| DEP_SULFASALAZINE_FOLATE | sulfasalazine → folate | depletion | **verified?** established folate malabsorption; DailyMed label — confirm |
| DEP_COLCHICINE_VITAMINB12 | colchicine → B12 | depletion (evidence=probable) | **borderline;** evidence=probable is honest, copy conditional; indirect citation (B12 label lists colchicine) — firm to a real colchicine-B12 study |

## Verifier verdicts (filled on subagent return)

- Verifier A (OCP + antifolate: OCP-B6, OCP-folate, MTX-folate): _pending_
- Verifier B (warfarin-K, SSRI-sodium, INH-B6): **DONE, no ghosts.**
  - **DEP_ANTICOAGULANTS_VITAMINK → verified.** VKORC1 mechanism ✓, functional_antagonism correct, copy correct ("don't supplement; keep intake CONSISTENT" — guideline-endorsed). Hirsh *Chest* 2001 **PMID 11157640** real. Non-blocking: the bone/vascular (osteocalcin/matrix-Gla) clause in clinical_impact isn't in Hirsh — add a citation or keep the hedge.
  - **DEP_SSRIS_SODIUM → verified-after-source-fix.** Relationship + `monitoring_stability` type + copy all sound (dilutional, not depletion — self-corrects). ONLY defect: sole source = NIH ODS Sodium PLACEHOLDER (doesn't cover SSRI-SIADH). Fix: replace with De Picker et al. *Psychosomatics* 2014 **PMID 25262043** (+optional Fabian **PMID 16896026**). → verify once source firmed.
  - **DEP_ISONIAZID_VITAMINB6 → verified-after-label-fix.** Classic; mechanism (hydrazone + pyridoxal-kinase inhibition) ✓; copy appropriate; DailyMed INH label real + recommends pyridoxine. The "vague PubMed" placeholder ALREADY points to a REAL on-topic PMID **21477422** (van der Watt IJTLD 2011) — only the label TEXT is weak. Fix: relabel to the full citation (no new PMID). → verify.
- Verifier C (orlistat-D, cholestyramine-K, sulfasalazine-folate, colchicine-B12): **DONE — all 4 verified; no ghosts/placeholders; DailyMed labels fetched + confirmed to genuinely address each interaction.**
  - **DEP_ORLISTAT_VITAMIND → verified (clean).** Copy near-verbatim from the XENICAL label (A/D/E/K multivitamin ≥2h apart). No action.
  - **DEP_CHOLESTYRAMINE_VITAMINK → verified (clean).** DailyMed label covers fat-soluble malabsorption + hypoprothrombinemia. Optional: mention bleeding risk in clinical_impact (label is stronger than the entry's tone).
  - **DEP_SULFASALAZINE_FOLATE → verified (clean).** Label covers folate absorption/metabolism inhibition + megaloblastic anemia + NTD. Optional primary strengtheners: Reisenauer/Halsted **PMID 6113848**, **6104945**.
  - **DEP_COLCHICINE_VITAMINB12 → verified.** evidence=`probable` is HONEST+correct (normal B12 at standard prophylactic doses — Ehrenfeld 1982; effect is dose-dependent/reversible). Copy conditional. Indirect citation (cyanocobalamin label lists colchicine) is factually true + acceptable. Recommend UPGRADE to primary: Webb *NEJM* 1968 **PMID 5677718** (+ Race 5416781, Stopa 759260, Ehrenfeld 6284460 support dose-dependence).

## Status assignment (final — every PMID content-verified via PubMed eutils; no ghosts this batch)

- Verifier A (OCP + antifolate): **DONE.**
  - **DEP_METHOTREXATE_FOLATE → verified.** functional_antagonism correct; clinician-directed copy correct (RA supplementation vs oncology folinic rescue). The vague label's URL already resolves to a REAL on-topic paper (Morgan 1997 **PMID 18020507**) → not a placeholder. Fix (hygiene): relabel + add Cochrane **PMID 23728635** (primary).
  - **DEP_OCP_VITAMINB6 → needs_revision.** Placeholder source (NIH ODS B6 sheet has ZERO OCP content — fetched + confirmed). Signal is weak ("may", Wilson/Bailey 2011 **PMID 21967158**), so evidence=established + severity=significant overstate; mechanism presents 1970s view as fact; mood-symptom claim weak. **SAFETY: recommendation 25–50 mg B6 = 2–4× the EFSA UL (12 mg/day, PMID 37207271) — a therapeutic/neuropathy-risk dose, not repletion.** Fixes: source→21967158, downgrade evidence, cut B6 dose to multivitamin level (deferred with the reframe).
  - **DEP_OCP_FOLATE → needs_revision.** Placeholder source that the real literature CONTRADICTS (Wilson/Bailey 2011: "data do not support a conclusion that currently used OCs negatively impact folate status"). Depletion framing is really repackaged preconception advice; consumer copy + 400 mcg rec are fine, the STRUCTURED fields (evidence/severity/mechanism/clinical_impact) overstate. Fix: reframe + source→21967158 (deferred).

**verified (8):** DEP_ANTICOAGULANTS_VITAMINK, DEP_ORLISTAT_VITAMIND, DEP_CHOLESTYRAMINE_VITAMINK, DEP_SULFASALAZINE_FOLATE, DEP_COLCHICINE_VITAMINB12, DEP_METHOTREXATE_FOLATE, DEP_ISONIAZID_VITAMINB6, DEP_SSRIS_SODIUM.
**needs_revision (2):** DEP_OCP_VITAMINB6, DEP_OCP_FOLATE.
**rejected (0).**

APPLIED source firm-ups on the verified entries: SSRI placeholder (NIH ODS Sodium) → De Picker 2014 **PMID 25262043**; isoniazid vague label → van der Watt 2011 (**PMID 21477422** kept); MTX vague label → Morgan 1997 + Cochrane **PMID 23728635**; colchicine + Webb 1968 **PMID 5677718** (kept DailyMed as secondary). **DEFERRED FOLLOW-UP (batch_02_fixes):** the OCP reframe (evidence downgrade, source→21967158, cut OCP-B6 dose below the EFSA UL, reframe OCP-folate around preconception). All PMIDs used = content-verified: 11157640, 25262043, 21477422, 18020507, 23728635, 5677718, 21967158. Total corpus now: verified 9, needs_revision 12, unverified 59.
