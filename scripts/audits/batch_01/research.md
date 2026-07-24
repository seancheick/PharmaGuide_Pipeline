# Med–Nutrient Content Audit — Batch 01

Started 2026-07-23. First prioritized batch (PM-directed). Goal: content-verify each
entry's clinical claim + cited sources against authoritative literature, then mark
each `verified | needs_revision | rejected` in the SOURCE
(`scripts/data/medication_depletions.json`), one at a time, NO bulk-promotion.

Per-entry criteria: drug/class scope · relationship_type · direction · population ·
duration dependency · monitoring rec · comparison amount · consumer copy · source
support for EVERY surfaced claim.

Publication rule (B1.2): `verified` → shown; `needs_revision`/`rejected` → SUPPRESSED
(removed from the monitor); `unverified` → migration display only. So marking a
scope-imprecise entry `needs_revision` is the safe immediate action (stop showing the
imprecise claim); the scope fix is a tracked follow-up.

## The 11 entries + preliminary read (to be confirmed by the 4 verifiers)

| id | drug → nutrient | type | evidence | prelim read |
|---|---|---|---|---|
| DEP_METFORMIN_VITAMINB12 | Metformin → B12 | depletion | established | likely **verified** (landmark de Jager BMJ 2010, Bauman 2000) |
| DEP_ANTACIDS_VITAMINB12 | "PPIs and antacids" → B12 | depletion | established | verify + **scope**: true antacids ≠ PPIs/H2RA (Lam JAMA 2013 is PPI/H2RA) |
| DEP_ANTACIDS_MAGNESIUM | "PPIs and antacids" → Mg | depletion | established | verify + **scope**: FDA 2011 signal is PPI-specific |
| DEP_STATINS_COQ10 | Statins → CoQ10 | depletion | established | **evidence strength**: blood-CoQ10 drop established, but myopathy causation / supplementation benefit are mixed (Banach 2015, Taylor 2015) |
| DEP_DIURETICS_POTASSIUM | "Diuretics" → K | depletion | established | **SCOPE (safety)**: K-sparing diuretics RAISE K → likely **needs_revision** |
| DEP_DIURETICS_MAGNESIUM | "Diuretics" → Mg | depletion | established | **SCOPE**: loop+thiazide, not K-sparing → likely **needs_revision** |
| DEP_CORTICOSTEROIDS_CALCIUM | Corticosteroids → Ca | depletion | established | likely **verified** (GIO textbook) |
| DEP_CORTICOSTEROIDS_VITAMIND | Corticosteroids → vit D | depletion | established | **mechanism**: "induces CYP24A1 → catabolizes 25-OH-D" — verify accuracy (may be overstated vs calcium-malabsorption / VDR antagonism) |
| DEP_ANTICONVULSANTS_VITAMIND | "Anticonvulsants" → vit D | depletion | established | **SCOPE**: enzyme-inducing AEDs only (phenytoin/carbamazepine/phenobarб/primidone); newer AEDs don't → likely **needs_revision** |
| DEP_LEVOTHYROXINE_CALCIUM | Levothyroxine ↔ Ca | supplement_interaction | established | likely **verified** (timing interaction; Singh JAMA 2000) |
| DEP_LEVOTHYROXINE_IRON | Levothyroxine ↔ Fe | supplement_interaction | established | likely **verified** (Campbell Ann Intern Med 1992) |

## Verifier verdicts (filled on subagent return)

- Verifier A (metformin/PPI absorption): **DONE, no ghost refs (all PMIDs content-verified by title/abstract).**
  - **DEP_METFORMIN_VITAMINB12 → verified.** Citations real: de Jager BMJ 2010 **PMID 20488910**, Bauman Diabetes Care 2000 **PMID 10977010**, NIH ODS B12. Mechanism (Ca-dependent ileal IF–B12) confirmed vs Bauman. Copy fix (not blocking verified): "up to 30% develop deficiency" overstates — 30% is *malabsorption*, frank deficiency ~6–30% by definition/duration; also comparison=500mcg vs rec text "1,000mcg" (pick one).
  - **DEP_ANTACIDS_VITAMINB12 → needs_revision (scope).** Lam JAMA 2013 **PMID 24327038** real, but supports PPIs/**H2RAs**, not simple antacids. Fix: relabel class "PPIs and H2 blockers", drop "antacids". H2RAs stay in scope.
  - **DEP_ANTACIDS_MAGNESIUM → needs_revision (scope + onset).** Danziger Kidney Int 2013 **PMID 23325090** + FDA DSC 2011 real, both **PPI-specific** (Danziger: H2RA null; some antacids are Mg-BASED → raise Mg). Fix: relabel class "PPIs only" (drop antacids + H2RAs); onset months → "years (as early as ~3 months)".
- Verifier B (statin/corticosteroid): **DONE.**
  - **DEP_STATINS_COQ10 → verified.** Blood-CoQ10 depletion established; supplementation-benefit is correctly hedged ("may contribute"/"many clinicians recommend"). Meta-analyses mixed: Banach 2015 **PMID 25440725** (no sig effect) + Taylor 2015 **PMID 25545331** (no muscle-pain reduction). evidence=established OK for the depletion. Optional: note mixed RCT evidence for supplementation.
  - **DEP_CORTICOSTEROIDS_CALCIUM → verified.** GIO firmly established; direct osteoblast suppression correctly included. Minor: amounts (1000–1500 Ca / 800–2000 IU D) run slightly above 2017 ACR (1000–1200 / 600–800, Buckley **PMID 28585373**); PTH clause is the older 2° hyperPTH model. Optional refinements only.
  - **DEP_CORTICOSTEROIDS_VITAMIND → needs_revision.** Mechanism INACCURATE: CYP24A1 is renal/mitochondrial, NOT hepatic (hepatic vit-D catabolism is CYP3A4); glucocorticoid "induction of CYP24A1 lowers serum 25-OH-D" is NOT established; VDR-downregulation data are bone/osteosarcoma (**PMID 1312760**), not intestine. GCs mainly ANTAGONIZE vit-D action; Davidson 2012 meta-analysis: only −0.5 ng/mL vs healthy, no diff vs disease controls (Skversky 2011 **PMID 21956424** = confounded association). Fix: reframe as antagonizing vit-D action; evidence established→**probable**. Recommendation to co-supplement stays valid.
- Verifier C (diuretic/anticonvulsant SCOPE): **DONE — scope bug CONFIRMED against `drug_classes.json` (class:diuretics literally enumerates amiloride/spironolactone/eplerenone/finerenone/triamterene/canrenone).**
  - **DEP_DIURETICS_POTASSIUM → needs_revision.** Loop+thiazide deplete K (Brater NEJM 1998 **PMID 9691107**); K-sparing RAISE K (Roush 2016 **PMID 26556568**) — opposite direction, unsafe to blanket. Fix: scope to loop+thiazide (add `class:loop_diuretics` OR `excludes: class:potassium_sparing_diuretics`); display "Loop & thiazide diuretics". COPY BUG: "Potassium-sparing foods (bananas…)" → "Potassium-rich foods".
  - **DEP_DIURETICS_MAGNESIUM → needs_revision + GHOST.** Loop+thiazide deplete Mg (Ellison 2000 **PMID 10997911**, Dai 1997 **PMID 9083264**); K-sparing are Mg-SPARING (amiloride conserves Mg, Bundy 1995 **PMID 7872368**). Same scope fix. **GHOST CITATION: PMID 3003511** (cited "Altura & Altura, Magnesium 1985") = actually "Aspartate kinases I,II,III from E. coli" (Methods Enzymol 1985) — PubMed-confirmed. Remove + replace with 10997911/9083264.
  - **DEP_ANTICONVULSANTS_VITAMIND → needs_revision.** Effect specific to ENZYME-INDUCING AEDs (phenytoin/carbamazepine/phenobarbital/primidone; Pack 2004 **PMID 15123008**, Arora 2016 **PMID 27843822**, Sourbron 2024 **PMID 39494692**). class:anticonvulsants over-scopes (~40 members incl. levetiracetam/lamotrigine/gabapentin — "scanty/controversial"). Mechanism text overreaches: valproate is an INHIBITOR (bone loss via non-CYP, inconsistent vit-D effect); lamotrigine-as-depleter unsupported → drop. Fix: add `class:enzyme_inducing_anticonvulsants` + re-point; drop lamotrigine/valproate lumping.
- Verifier D (levothyroxine timing): **DONE — GHOST found.**
  - **DEP_LEVOTHYROXINE_CALCIUM → needs_revision + GHOST.** supplement_interaction typing CORRECT (Ca binds levothyroxine; not a Ca depletion). **GHOST: URL is PMID 19174283 = "Treatment of calf diarrhea: oral fluid therapy" (Vet Clin 2009)** under a "Haugen BR" label — PubMed-confirmed. Intended Haugen (**PMID 19942154**) is real but topically weak (TSH-suppressing drugs, no calcium). Replace with Singh JAMA 2000 **PMID 10838651** + Singh Thyroid 2001 **PMID 11716045**. Magnitude "up to 40%" overstated → ~20–30% (acute 83.7→57.9% ≈31%). Demote the reverse bone-turnover claim. 4-h separation correct.
  - **DEP_LEVOTHYROXINE_IRON → needs_revision.** supplement_interaction correct; NIH ODS Iron source valid for the interaction + 4-h advice but does NOT support "30–45%" (unsourced number). Add Campbell 1992 **PMID 1443969** (primary); soften magnitude to "a clinically significant reduction".

## Status assignment (final — all PMIDs content-verified via PubMed eutils; 2 ghosts confirmed)

**verified (3):** DEP_METFORMIN_VITAMINB12, DEP_STATINS_COQ10, DEP_CORTICOSTEROIDS_CALCIUM.
**needs_revision (8):** DEP_ANTACIDS_VITAMINB12, DEP_ANTACIDS_MAGNESIUM, DEP_DIURETICS_POTASSIUM, DEP_DIURETICS_MAGNESIUM, DEP_CORTICOSTEROIDS_VITAMIND, DEP_ANTICONVULSANTS_VITAMIND, DEP_LEVOTHYROXINE_CALCIUM, DEP_LEVOTHYROXINE_IRON.
**rejected (0):** none — every relationship is clinically real; the 8 defects are scope/mechanism/citation, not false claims.

reviewer = `lead_clinician_audit_2026_07` (Claude-assisted, PubMed-content-verified). This batch MARKS status only; the per-entry FIXES above (scope narrowing incl. `drug_classes.json` `class:loop_diuretics` + `class:enzyme_inducing_anticonvulsants`, 2 ghost-ref removals, corticosteroid-D mechanism rewrite, levothyroxine magnitude softening, copy "potassium-rich foods") are the tracked follow-up. needs_revision entries are SUPPRESSED by the B1.2 publication rule until fixed — the safe outcome.
