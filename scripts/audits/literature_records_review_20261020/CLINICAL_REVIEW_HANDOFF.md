# Final pre-rebuild completion campaign — October 24, 2026

## Decision

**Pre-rebuild GO: BLOCKED. Post-rebuild release readiness: BLOCKED / not exercised.**
The verified engineering/source correction batch is implemented. Scientific qualification is
not finished. Do not run the pipeline yet as a production-candidate rebuild; no full corpus run,
export, manifest restamp, catalog activation or publication was performed. No scoring weights,
clinical policy, approval authority or public product fields changed.

## Owners and qualification

Owner: `scripts/evidence_resolver.py::resolve_evidence_for_row` — evidence: fail-first empty
machine-verification receipts falsely completed Evidence despite no source review.
Owner: `scripts/enhanced_normalizer.py::_apply_label_corrections` and its display builder —
evidence: exact NIH label PDFs, source-form fences, cache and public-copy regressions.
Owner: `scripts/identity_integrity.py::resolve_identity` / existing canonical registry —
evidence: literal Corn Silk Powder versus source-form Zea mays with conflicting-identity controls.
Owner: existing backed/literature registries, `clinical_applicability::assess_clinical_source_review`
and `probiotic_measurements::context_accepted_for_scoring` — evidence: per-source review packets,
existing context errors and actual saved product dependencies.
Will NOT create another scorer, identity matcher, registry, completion authority or approval.

## One remaining-work list

1. **Clinical: 147 eligible curated records + generated collagen remain open.**
   The existing [clinical hold register](clinical_review_holds.csv) gives exact record IDs,
   frozen/current product dependencies, source URLs, content-screening status, per-paper access
   and outstanding obligations. The 147 cover 6,309 record-product dependencies across 5,961 distinct saved products; generated collagen has
   24 saved dependencies, with overlap possible. All 147 current source-owner completion checks
   fail for missing contexts. This requires scientific synthesis as well as authentic approval;
   it is not merely a signature queue. No approval was created. Five source-ineligible records
   and three unused historical records remain separately identified among the 155 union rows;
   unused history does not block publication.
2. **Benchmarks: all 506 subjects / 4,259 frozen rows / 3,118 products remain open.**
   [Benchmark register](benchmark_review_backlog.csv) preserves every subject and assigns the
   actual existing literature owner: 125 subjects have study rows, 225 have no study rows,
   156 lack an exact/alias literature owner. Review preparation, regimen, population and purpose,
   then establish a defensible reference decision through the existing owner. Five narrow
   no-general-curve proposals (aloe vera, flaxseed, green tea leaf, lignans, pygeum) were not
   approved or activated. Benchmark absence alone is not a clinician hold.
3. **Identity/dose:** all 15,437 frozen IDs reconcile exactly; all 288 retained snapshot checksums
   pass. The saved pre-campaign corpus has 135 identity-incomplete and 51 dose-incomplete products,
   10 overlapping (176 union); the old 238-label sample covers 174 of these. One additional
   public label is 241681, corrected in this batch; the other is private intake and remains only
   in local receipts. These are saved old-source counts, not a rebuilt candidate assessment.
   Preserve unresolved printed-unit conflicts, unspecified vitamin forms/fractions, preparation
   gaps and genuinely undisclosed amounts. NIH PDFs confirm several apparent bad units are
   actually printed; do not guess corrections. Fish-oil/omega totals, collagen/protein totals
   and the coconut/acacia MCT matrix cannot supply invented constituent doses.
4. **Final integration/rebuild checks:** after scientific owner decisions are complete, inspect
   actual Clean/Enrich/Score fingerprints and use the documented pipeline-only command from
   main. Then verify every rebuilt assessment, all positive Evidence dependencies, original
   20 labels, app explanations and banned/recalled discoverability. Targeted replay does not
   close a whole-corpus invariant. Release/publication still needs separate authorization.

## Source review completed, with limits

The frozen clinical CSV contains 349 structured PMID links and two NCT links, while the same
147 records contain 36 distinct NCT identifiers including excluded/history references. Of 135 benchmark PMIDs,
127 are absent from the 349 clinical PMIDs: 476 unique publication IDs across both initial
worklists. These are publication identifiers, not independent trials. All 135 benchmark sources
were inspected (134 abstracts; one without an abstract). All 119 abstracts from 47 formerly
inventory-only clinical records were read; still-applicable prior bound packets were reused.
77 bounded searches returned 199 candidates, all screened; corrected anchor searches returned
38 screened candidate records, with possible overlap. Search coverage is bounded, not an exhaustive negative literature review.

Of the 349 clinical publications, 181 have PMC identifiers; 157 full-text bodies were retrieved,
24 indexed bodies unavailable, 168 have no PMC identifier. Retrieval is not full-text assessment,
risk-of-bias review or trial-family deduplication. Publisher access is not exhausted. Magtein
correction 40567408 and PQQ corrected Table 4 remain explicit content gaps. The 5-MTHF correction
39083531 changes red-cell to whole-blood folate; current registry has no conflicting numeric RBC
claim. Inositol correction 39208274 adds dataset attribution. No replacement benefit grade follows.

Read-only generic citation audit: 1,539 matches, 146 known baseline mismatches, zero new mismatches
or unresolved transport results. Those 146 are not scientifically closed. Strict backed-source
verification passes its title/content-binding checks; it does not approve clinical use. Clinical
trial audit has no broken IDs/API errors; two design flags concern already-explicit excluded or
nonrandomized sources. Read-only literature screening fetched 29 PMIDs for 16 changed entries;
no title corrections/retractions, but four machine population flags remain in that report.
Primary abstracts confirm human components in 20459662, 38439104, 27164220 and 18355411 (the last
also includes cellular work). Manual disposition is recorded; the machine screen is not called
passing and its provenance was not auto-applied. An earlier generic changed-citation command
covered zero registry entries and is not used as verification of this batch.

## Implemented and measured

Four exact label corrections: 326244 calcium ascorbate; 321393/321394 cracked-wall chlorella;
241681 literal forskolin category. Source-local Corn Silk identity restored for 312640/312713/
330886; preparation Formulation holds remain. Raw source forms are fenced; cached correction
payloads cannot be mutated; superseded API forms cannot leak back into public label copy.
Empty automated no-study stamps no longer imply completed Evidence; genuine bounded negative
reviews remain supported. Eleven backed records and sixteen literature records have factual
source corrections, with no new grades, amounts, benchmarks, approvals or affirmative contexts.

A frozen 350-public-label baseline/candidate replay completes without errors; all 443 runtime
source bindings match. Printed amounts/units and safety decisions unchanged, no nonempty warning
lost, no private marker exported; all 19 suppressed-safety controls retain status. Four labels
recover calculable totals (241681 70.4; 321393/321394 78.5; 326244 78.0), **all still release-blocked**.
43 previously complete release assessments become incomplete; none become complete. These are
bounded measurements, not full-corpus readiness or a claim of clinical accuracy.

Focused owner checkpoint: 1,320 passed plus one obsolete source expectation subsequently corrected
and its named node passed. Final source-owner slices: 381 resolver/literature, 69 label and
139 identity checks passed. Existing Flutter consumers: 119 passed; no app source change or
real rebuilt catalog import. Final local546passed/24declared optional-service skips in139.52s;
skipguard passes. The first local run had three obsolete companion-source completion
expectations; corrected tests require the missing context and preserve nontransfer/point ownership
assertions (12named tests pass). CI40117945440 failed six obsolete source-completion assertions across three portable test files.
All were corrected against actual empty automated stamps, retaining genuine authored-negative
controls and unchanged score/owner/dose assertions;75+18named tests pass. Earlier40117665750
was cancelled/superseded. Neither run is a pass. Final whole-fast rerun and integration pending.

## Single forwardable request

[Sean’s message to Dr. Pham](DR_PHAM_FINAL_REVIEW_REQUEST.md) is the user-requested standalone
communication:148evidence items (147records+generatedcollagen),506dose subjects and171remaining
identity/dose cases from the final238-label sample; all36NCTidentifiers included. Exact source
links, public label editions, correction/access gaps, scoped reply template and closure criteria
are embedded. It contains no private submission IDs and creates no approval. Independent
source-lane coverage review confirms exact147+1and36NCTcoverage. It is a communication artifact
through the existing review handoff owner, not a new assessment registry.
