# Branded preparation and blend integrity — bounded correction

Assessment completeness remains independent of quality. A patent or trade name does not establish disclosure, clinical applicability, efficacy, purity or finished-batch testing. No clinical approvals, scoring weights or public product fields changed.

## Scope and owners

Frozen denominator: 15,437 saved products. All 165 priority records across 163 products were inspected against exact raw rows; 23 additional controls produce a 186-label Clean → Enrich → Score diagnostic replay, not a corpus regeneration. Baseline: pipeline `d4d94999321e16c8419fd60c70b89ed0f6b2a7e4`.

Owner: `scripts/enrich_supplements_v3.py::SupplementEnricherV3._collect_proprietary_data` — evidence: physical source-row traces, canonical preparation resolution and raw replay.
Owner: `scripts/scoring_input_contract.py::dose_disclosure_status` / `disclosed_source_amount` and `scripts/proprietary_blend_detector.py::_analyze_disclosure` — evidence: canonical quantity/activity and detector callers.
Owner: existing B5 and complete-disclosure readers; `scripts/build_final_db.py::build_detail_blob`; Flutter `label_confidence_helpers.dart`, section and connected caller — evidence: owner/consumer tests and exported detail metadata.
Will NOT create: patent exemptions, a classifier/registry/scorer, guessed constituent doses, clinical approvals, or new public product fields.

## Confirmed causes and correction

- Reconcile detector and cleaner against the same individually quantified, canonically identified material. Natural constituents and nutrient source salts do not automatically become separately formulated actives.
- Recognize the exact saved PrimaVie shilajit and UC-II label names through existing IQM forms. Assess those materials rather than skipping them as generic headers. Preserve original source provenance.
- Restore detector member lists only from physical source links; recognize structural blend headers even when a weaker boolean is false. Keep real TamaFlex, myrosinase, protease, amino-acid, protein and probiotic member limitations.
- Reuse the normalizer's typed enzyme-activity units as disclosure, without converting activity to mass or inventing adequacy. Deduplicate matching physical owners; preserve conflicting totals.
- Do not borrow a named ingredient's amount as the total of a different mixture mentioned in its notes (307567/321953).
- Flutter consumes existing disclosure levels: full disclosure does not create a blend warning or Partial tier; partial, missing composition and unverified metadata receive different explanations. Independent coverage and assessment limitations remain visible. The app does not recalculate scores.

## Source verification

Every candidate's exact raw row and SHA-256 are recorded in `candidate_review.csv`. The register distinguishes original source-screening disposition from measured current behavior. Source screening and passing replay are not clinical approval or rebuilt-corpus closure.

Primary preparation sources:

- [Life Extension current label](https://www.lifeextension.com/vitamins-supplements/item01431/super-ubiquinol-coq10-with-enhanced-mitochondrial-support): ubiquinol 200 mg and shilajit complex 200 mg. Current generic wording does not independently establish PrimaVie; the saved edition explicitly supplies that name.
- [Jarrow label](https://jarrow.com/products/shilajit-fulvic-acid-complex-250-mg-60-veggie-caps): PrimaVie material/trademark and 250 mg preparation; its fulvic-acid-complex declaration is not assumed analytically identical to every trial specification.
- [BioCell manufacturer](https://www.biocellcollagen.com/): a naturally occurring chicken-cartilage matrix; five exact saved labels separately quantify its listed constituents.
- [UC-II manufacturer identity](https://www.capsugel.com.cn/news/lonza-acquired-new-claim-food-function-claims-japan-uc-ii-undenatured-type-ii-collagen): undenatured type-II collagen preparation, not automatic disclosure of other joint-formula actives. An inaccessible historical PDF was not counted as verification.
- [PrimaVie exercise trial](https://pubmed.ncbi.nlm.nih.gov/30728074/): preparation/dose/population/outcome limitations remain independent. No clinical grade, approval or benchmark was added from this research.

The existing live IQM citation verifier reports 12 matching bindings and zero mismatches for changed entries. Exact data-batch checks cover two IQM entries and one blend-concern entry. PMID identity/content verification does not confer clinical sign-off.

## Saved-output census

`full_census.json` groups all 2,839 flagged products / 5,796 saved blend records across 38 manifest-owned filesets. All content hashes matched. It records 145 repeated physical owners, 460 omitted known parent amounts, 272 omitted source-child inventories (129 fully quantified), 949 records without recorded children, and 358 records without a physical row binding. These are overlapping structural diagnostics, not newly counted clinical holds or 5,796 completed scientific reviews. Empty children never establish full disclosure. Frozen full/partial/none counts describe old artifacts, not corrected publication.

## Remaining work and release boundary

- **275412 RAW Enzyme:** raw flat grouping does not prove physical composition; preserve its limitation pending a source label establishing membership.
- **182990 Trace Mineral:** preparation/constituent ranges do not establish an exact usable profile or component quantities; retain the existing preparation/benchmark hold.
- Existing clinical backlog remains in [CLINICAL_REVIEW_HANDOFF](../literature_records_review_20261020/CLINICAL_REVIEW_HANDOFF.md): 147 conditional clinical contexts plus generated collagen binding/context; 506 benchmark subjects are shared scientific questions, not 506 automatic clinician holds. Do not fabricate sign-off. The older 174/238 identity-dose diagnostic is not an updated count from this separate blend batch.
- No whole-corpus pipeline, catalog publication, production app import or release occurred. After scientific decisions are stable, inspect current stage fingerprints and perform one necessary combined regeneration, then validate the corpus invariant, catalog and real consumer. No old artifact is restamped to imply this source has run.

Qualification and measured movements are in `validation.json`; per-entry outcomes in `candidate_review.csv`. The existing LEDGER remains the execution register. Implemented, source-screened and bounded-verified are distinct from scientifically approved and release-validated.
