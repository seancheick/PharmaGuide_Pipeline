# Branded preparation and blend integrity — bounded correction

Assessment completeness remains independent of quality. A patent or trade name does not establish disclosure, clinical applicability, efficacy, purity or finished-batch testing. No clinical approvals, scoring weights or public product fields changed.

## Scope and owners

Frozen denominator: 15,437 saved products. All 165 priority records across 163 products were inspected against exact raw rows; 23 additional controls produce a 186-label Clean → Enrich → Score diagnostic replay, not a corpus regeneration. Baseline: pipeline `d4d94999321e16c8419fd60c70b89ed0f6b2a7e4`.

Owner: `scripts/enhanced_normalizer.py::_citrus_bioflavonoid_source_identity` / `_is_dsld_active_blend_total_row` and `scripts/enrich_supplements_v3.py::SupplementEnricherV3._collect_proprietary_data` — evidence: physical source-row traces, canonical preparation resolution and raw replay.
Owner: `scripts/scoring_input_contract.py::dose_disclosure_status` / `disclosed_source_amount` and `scripts/proprietary_blend_detector.py::_analyze_disclosure` — evidence: canonical quantity/activity and detector callers.
Owner: existing B5 and complete-disclosure readers; `scripts/build_final_db.py::build_detail_blob`; Flutter `label_confidence_helpers.dart`, section and connected caller — evidence: owner/consumer tests and exported detail metadata.
Will NOT create: patent exemptions, a classifier/registry/scorer, guessed constituent doses, clinical approvals, or new public product fields.

## Confirmed causes and correction

- Reconcile detector and cleaner against the same individually quantified, canonically identified material. Natural constituents and nutrient source salts do not automatically become separately formulated actives.
- Recognize the exact saved PrimaVie shilajit and UC-II label names through existing IQM forms. Assess those materials rather than skipping them as generic headers. Preserve original source provenance.
- Keep an explicit nutrient declaration distinct from structural header hints, without converting a preparation amount into an elemental amount. The exact citrus-bioflavonoid material uses its existing identity/source owner: disclosed mass, explicit citrus botanical provenance and no additional/member blend structure. Real-label controls 213448/201803 and added-active, missing-amount, negated-source and name-conflict guards cover these cases.
- Restore detector member lists only from physical source links, and only when every direct child in the physical inventory remains available. The unchanged missing-descendant canary caught an incomplete subset being mistaken for a sole ingredient; its fail-first reproduction now passes without weakening the assertion. Recognize structural blend headers even when a weaker boolean is false. Keep real TamaFlex, myrosinase, protease, amino-acid, protein and probiotic member limitations.
- Reuse the normalizer's typed enzyme-activity units as disclosure, without converting activity to mass or inventing adequacy. Deduplicate matching physical owners; preserve conflicting totals.
- Do not borrow a named ingredient's amount as the total of a different mixture mentioned in its notes (307567/321953).
- Flutter consumes existing disclosure levels: full disclosure does not create a blend warning or Partial tier; partial, missing composition and unverified metadata receive different explanations. Independent coverage and assessment limitations remain visible. The app does not recalculate scores.

## Measured results

The final stable 186-label replay is bound to runtime candidate `379e538eaddee5f6956c06f26b4adb24a81b432e`; all 443 source-file hashes still match. Printed source names, quantities, units and activity values are unchanged. Clean identity changes are limited to 16 saved PrimaVie rows: generic blend identity becomes shilajit. All 186 release-assessment decisions and clinical blockers remain unchanged. No nonempty warning, recall, ban or contraindication field was removed.

Among 165 candidate records, 63 erroneous record-level deductions disappear: 60 quantified nutrient/preparation/matrix records, two activity groups, and one duplicate outer owner whose genuine inner protease limitation remains. Another 59 charges decrease but remain positive; 29 increase and 14 are unchanged after corrected totals/ownership. Six initial correction candidates already had no B5 charge and remain `not_scored`. This is not 165 false penalties or 63 new clinical clearances.

There are 131 numeric total movements, with no quality-status changes. Only Transparency (131) and Formulation (17) move; Dose, Evidence, Verification and Safety pillar values do not change. For 231852, Transparency 12→15 but Formulation 20→15.8 because shilajit is now assessed instead of skipped: total 79→77.8. BioCell 246073 moves 79→82, DigeZyme 277667 moves 49.9→55.9 and Glutalytic 302668 moves 44.9→53.9 through corrected disclosure. Boron 213448 and citrus 201803 controls retain 58.4/82.8 respectively. Branding never guarantees a score increase.

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

- **275412 RAW Enzyme:** exact physical label now verifies composition; hierarchy, native activities and duplicated CFU ownership are corrected. Genuine individual-dose limitations remain. See [source follow-up](research.md).
- **182990 Trace Mineral:** the natural 700 mg source matrix now uses its existing source-descriptor owner, with separately declared minerals and ranges preserved. Clinical/benchmark holds remain. See [source follow-up](research.md).
- Existing clinical backlog remains in [CLINICAL_REVIEW_HANDOFF](../literature_records_review_20261020/CLINICAL_REVIEW_HANDOFF.md): 147 conditional clinical contexts plus generated collagen binding/context; 506 benchmark subjects are shared scientific questions, not 506 automatic clinician holds. Do not fabricate sign-off. The older 174/238 identity-dose diagnostic is not an updated count from this separate blend batch.
- No whole-corpus pipeline, catalog publication, production app import or release occurred. After scientific decisions are stable, inspect current stage fingerprints and perform one necessary combined regeneration, then validate the corpus invariant, catalog and real consumer. No old artifact is restamped to imply this source has run.

Qualification and measured movements are in `validation.json`; per-entry outcomes in `candidate_review.csv`. The existing LEDGER remains the execution register. Implemented, source-screened and bounded-verified are distinct from scientifically approved and release-validated.

## Simulator display verification

[Simulator screenshot](blend-display-simulator.png) shows the actual corrected label-confidence component with bounded exported disclosure metadata: 231852 has two disclosed 200 mg materials and no false warning; 219249 retains Partial/component-amount wording. Nine unchanged production display files were hash-bound into an isolated native preview host. The ordinary app host's OCR plugin excludes the available simulator architecture, so this component preview deliberately excludes that unrelated plugin. Connected-screen wiring is separately tested. This is not a production catalog import, whole-app runtime acceptance or release qualification.

Final read-only stage-fingerprint inspection finds 38 stale Clean, 38 Enrich and 38 Score manifests. The earliest required stage is **Clean**; no manifests were restamped and no stage was run. Keep the next combined regeneration deferred until authorized and the planned scientific decisions are stable. Final local checks on `379e538e` pass 546 tests / 24 declared optional-service skips with the skip guard passing.

## Final source qualification

Runtime candidate `379e538eaddee5f6956c06f26b4adb24a81b432e` passes [whole-fast CI 40064982337](https://github.com/seancheick/PharmaGuide_Pipeline/actions/runs/40064982337): **23,748 passed / 192 declared skips**, all four groups and skip guards green. Named owner/consumer tests: 465 passed. Final local: 546 passed / 24 declared optional-service skips, skip guard green. Flutter: 4013 tests and clean analysis; its subsequent connector integration changes no checked Dart/platform/package source. Independent source review clears the final missing-descendant guard.

Pipeline runtime commits: `63ad40e71`, `f3b8169d3`, `379e538e`. App fix: `9b8f0d25`, integrated through `8c5ab48a` with the concurrent connector work preserved. Report-only follow-up does not change the qualified runtime, fixtures or configuration. Main containment/cleanup is recorded in the final handoff.

CI 40063277118 was cancelled and is not qualification. CI 40063751192 failed the missing-descendant canary and is not qualification. The unchanged assertion was reproduced and repaired through the physical inventory owner; the final replacement checkpoint above is the passing result. No failed, interrupted or cancelled receipt is restamped as passing.
