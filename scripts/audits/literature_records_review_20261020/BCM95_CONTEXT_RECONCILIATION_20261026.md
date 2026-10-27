# BCM-95 source-context reconciliation — October 26, 2026

Owner: `scripts/data/backed_clinical_studies.json::BRAND_BCM95`, consumed by `clinical_applicability.py::assess_clinical_source_review` and the existing ingredient-context schema. Evidence: exact retained entry/reference census, returned A003 response and both original full bodies. Will NOT create another approval registry, efficacy grade, dose curve or product-equivalence rule.

## Applied scope

Both retained references now have separate native `study_contexts`. Their source union equals the record's entire two-reference set; no one-context shortcut is used. Sean attests that Dr. Pham signed the explicit returned decisions and supplied October 26, 2026 as the approval date. `clinical_review.reviewed_at` records the genuine date only; no clock time is inferred. The existing approval owner handles date precision. This does not fill blank A responses or approve twelve retail label editions.

| Source | Preparation / tested exposure | Accepted bounded conclusion | Retained limits |
|---|---|---|---|
| [30975196](https://pubmed.ncbi.nlm.nih.gov/30975196/), [full paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC6460672/) | BCM-95/Curcugreen curcuminoid–turmeric-essential-oil complex, 500 mg three times daily for 28 days | Qualified active-comparator observation in symptomatic knee OA; pain-change difference versus diclofenac was not significant | Open-label subjective outcomes, no placebo, retrospective registration, short duration, capsules supplied by Arjuna; no general drug equivalence or long-term safety claim |
| [33516238](https://pubmed.ncbi.nlm.nih.gov/33516238/), [full paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC7847013/) | The specified complex, 500 mg twice daily for six weeks | Authors' non-inferiority report under their chosen margins; baseline-adjusted WOMAC pain and CRP differences were null; TNF-alpha was a separate surrogate | Unblinded after allocation; 193 randomized, 144 completed; margin derivation/supplementary randomized-subject analysis/original registry history remain outside stronger acceptance; no placebo superiority or universal equivalence |

The 2019 paper's abstract and returned response call 139 randomized, but its full Results reports 149 enrolled and 139 completed/analyzed. The record now states the full-results counts, retains the discrepancy in context limitations, and keeps `total_enrollment=null`. No pooled unique enrollment is invented.

The dose values count complete branded complex, not isolated curcumin. The existing `tier_1` and scoring weights are unchanged. The descriptive effect direction is corrected from `positive_strong` to `mixed` under the scoped source decisions. Its existing consumer multiplier can change points; integrated real-product replay measures the actual effect. These limited active-comparator contexts must not be read as independently validating a broad positive efficacy grade; qualification and exact-label applicability remain separately governed.

## Source receipts and access

Original returned batch4 SHA256: `566d7b9f302090b9885309d535666bc4bcf409328525bb6d767d31ab848594d4`.

Retained original XML bodies were read again and match the earlier retrieval receipt:

- PMC6460672: `1a253b1dd3e4159845508c3fb87883fe18ffdcc61ff41649963097fd0c3bfeee`.
- PMC7847013: `f624b09b1cf5bad0c8d82607906f484d848542e7188b5f20126eb37f3715e9cf`.

Local originals: `.claude/state/bryan_batches_4_5_20261025/`; receipt `fulltext_receipt.json`. New web opening on October 26 encountered PMC's browser challenge, so this reconciliation reuses content-verified original full bodies instead of claiming a new full-text download. The exact regimen, trial design, population, primary endpoint, comparator, attrition and stated limitations were inspected per source.

## Verification and closure

Two added regression tests failed first because the canonical record had zero contexts. They cover both source dependencies, distinct regimens, complex-mass basis, corrected enrollment wording, date-only attributable scope, and preserved comparative/product limitations. Both contexts passed the existing source-authoring validator before applying the signed approval.

No corpus run, export, app update, publication or overall scientific clearance is claimed. Passing source-context review resolves the missing-context dependency only. Retail-product matching and any independent readiness holds remain; integration owns bounded affected/control measurements and final qualification.

Focused verification: `scripts/test.sh fast scripts/tests/test_bcm95_returned_contexts.py scripts/tests/test_clinical_evidence_schema_ingredient.py scripts/tests/test_clinical_applicability.py` — 223 passed in 13.78 seconds. Exact data-batch check: one changed entry (`backed_clinical_studies/BRAND_BCM95`), zero problems. `git diff --check` passed.

Direct current-owner result: `assess_clinical_source_review(BRAND_BCM95)` changes from `clinical_source_contexts_missing` to complete with both context IDs. This removes one missing source-context dependency shared by twelve current products (181881, 182713, 209156, 209949, 211219, 231687, 60405, 60682, 62076, 63661, 63705, 74706) when re-evaluated. Their stored rebuilt artifacts have not been rewritten. `assess_clinical_applicability({}, record)` still returns `not_curated/no_reviewed_scope_constraints`; no product is claimed fully ready from this source-only change.

Final rationale/register reconciliation: the old October23 attribution-screen disclaimer is explicitly historical; it no longer falsely says no attributable scoped approval exists. The retained `tier_1` classification is expressly provisional and is not validated by these comparative-null/non-inferiority contexts. Only the BCM95 row of the existing clinical register records its source-context pass, actual signed date and residual product/grade scope. No global phase is checked off. The new rationale regression failed first; all five returned-context tests pass after cleanup.

The stale Magtein owner regression now checks both approved isolated trial families, correction pairing and whole-formula exclusion; it no longer expects a missing-context hold after migration. Direction regression failed first at positive_strong versus mixed. All six focused context/source-role checks pass after the source-direction correction. No scoring weight or numerical grade was invented.
