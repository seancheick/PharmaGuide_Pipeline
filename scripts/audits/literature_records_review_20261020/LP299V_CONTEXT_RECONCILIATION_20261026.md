# 299v signed source-context reconciliation — October 26, 2026

Owner: `scripts/data/clinically_relevant_strains.json::STRAIN_PLANTARUM_299V`, consumed by `studied_formulas.py::assess_probiotic_evidence`, `probiotic_measurements.py::derived_context_evidence` and the existing probiotic scorer. Evidence: native record/context census, signed returned batch1 and live PubMed API records. Will NOT create another strain registry, scoring policy, numerical efficacy threshold or generalized IBS-to-digestive-health rule.

## Exact source changes

- **22912552:** updated the existing positive context's review provenance to Dr. Pham's explicit signed source decision dated2026-10-26, as attested by Sean. Preserved the existing exact DSM9843 strain,10billionCFU/day capsule,28days, RomeIII IBS population, positive primary abdominal-pain frequency finding and study limitations. Historical delegated source authoring remains distinguishable from this new attributable approval.
- **25194614:** added the missing independent negative matching-dose context. The live primary abstract states two capsules each5×10^9CFU, daily for eight weeks in RomeII IBS. The10billionCFU/day total and56day duration are explicit arithmetic with provenance. Between-group abdominal-pain relief(p=.800) and IBS quality-of-life(p=.687) were null. The review accepts the negative trial as such; within-group improvement is not efficacy.
- **12452404:** retained the signed rejection of affirmative symptom-benefit use as a separate excluded context. The live abstract reports12patients, no symptom/overall-fermentation difference, and a breath-hydrogen finding after lactulose. The original methods are still needed for precise CFU, delivery and crossover timing. Those fields remain unresolved rather than copying the other trials' amounts. `review_status=rejected_source` and `scoring_eligible=false` prevent affirmative use while preserving the actual findings and source history.

All other299v contexts and the historical industry CFU tier fields remain intact. No10billionCFU efficacy minimum, optimum, safety ceiling or continuous clinical-dose curve is created. The accepted positive and null trials use different trial families and remain separate.

## Source verification

The live PubMed API retrieved all three exact records in one XML request on October26. Its content confirms the positive trial identity, the negative trial's full stated capsule arithmetic/duration and null comparisons, and the Sen abstract's symptom/fermentation findings and missing dose details. Exact source URLs:

- [22912552](https://pubmed.ncbi.nlm.nih.gov/22912552/)
- [25194614](https://pubmed.ncbi.nlm.nih.gov/25194614/)
- [12452404](https://pubmed.ncbi.nlm.nih.gov/12452404/)

The signed return supplies the bounded decisions. This task did not newly retrieve25194614full text; dose and null results are explicitly reported in the primary abstract. Missing Sen methods remain a precise source limitation, not a finding that dose is zero or that no human research exists.

Local live XML receipt: `.claude/state/clinical_context_migration_20261026/299v_pubmed.xml`. Original returned batch1: `.claude/state/bryan_review_20261025/batch1.txt`. Existing exact19067API/PDF evidence remains under `.claude/state/bryan_first_batch_20261025/`.

## Measured owner behavior and product boundary

Before adding the negative trial, the existing native derived summary was `positive_weak`; with the signed matching-dose null trial present, the same owner derives **`mixed`**, strength **medium**, one positive and one null primary-outcome trial family. No new strength grade is invented.

19067's saved label describes digestive balance and a healthy digestive system, not treatment of IBS. Its exact strain and10billionCFU/day disclosure are known, but that alone cannot transfer IBS treatment findings to generic digestive health. The existing native scorer remains **Evidence0 / research_present_applicability_unestablished** for this broad positioning. Existing exact-condition-claim controls remain distinct; no claim is inserted into the product to obtain credit.

The current release-completeness owner still treats this state as incomplete. This migration therefore does not claim19067release-ready. Whether a documented rejected claim-to-study transfer can constitute a completed inapplicable assessment is a separate existing-owner semantics question requiring a concrete reproduction and scoped resolution; this source batch does not quietly waive it.

## Verification

Two fail-first regressions reproduced missing25194614and12452404contexts. The three new native tests plus existing probiotic applicability/rubric tests pass: **61passed**. They enforce matching-dose positive/null trials, authentic approval scope, no invented Sen dose/delivery, derived mixed summary, and zero generic-purpose Evidence. All three updated/new contexts pass the existing frozen and native validators. Integration owns the combined real-label replay, consumer checks and CI; no full corpus, export, publication or app update occurred in this subtask.

Independent review precision correction:25194614reports two capsules daily but does not specify within-day timing. The context now records that literal source limitation instead of `once_daily`;10billionCFU/day arithmetic remains valid. The abstract does not establish concomitant therapies: an explicit limitation clarifies that the empty co_therapies list means none extracted, not proven absence. The regression asserting distinct schedules/limitations failed first before correction.
