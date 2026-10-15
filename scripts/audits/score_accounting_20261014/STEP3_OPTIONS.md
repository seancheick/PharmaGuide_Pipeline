# V4.1 Step 3 — corrected measurements and implementation recommendation

October 14, 2026. **Measurement work only. No production score/config/data changes, catalog rebuild, merge or release.** This report supersedes the original B3 recommendation and earlier diagnostic figures; Git history retains them.

## Decision

Recommend the **source-based ownership option**, measured as `R:canonical_N11.4_sixth_all`. Keep the six pillar weights, existing statuses and Verification unknown at 6/15. Implement the existing owners consistently, remove duplicate charges/credits, and make unfinished required assessments explicit. Do not implement original B3.

11.4/20 is an explicit operational neutral for a genuinely absent applicable Dose benchmark, not earned adequacy or a clinical probability. The exact neutral and the proposed 10/20 confirmed-UL ceiling are product-policy choices for Sean. Neither a near-zero mean nor preservation of a tier boundary justifies them. Prefer 11.4 over 10 here because removing unsupported ownership charges need not also lower the established no-benchmark allowance; the graded curve and confirmed-excess ceiling address the demonstrated ordering problems directly. This is a recommendation, not approval of new policy.

Owner: `quality_score.py::assemble_quality_score` and the existing dimension owners; `generic_helpers.bio_score_of` / `parent_relative_form_quality` own form ratings, `rda_ul_data.adequacy_results` and botanical/collagen/probiotic adapters own benchmarks, `exposure.py::row_exposure` owns daily exposure, and `scored_artifact.py::_quality_assessment_status` owns completion. Evidence: ownership matrix concepts `quality_score_v4_contract` and IQM form/delivery ownership, GLOSSARY Adequacy/Safety exposure, owner replay and frozen-label probes below. Will NOT create: a second scorer, public status, reference registry or downstream app score calculation.

## Measurement correction after Claude's review

The previous **1,033 incomplete-assessment figure is withdrawn**. The old helper tested positive dose usability, not missing disclosure. Independent reproduction of Claude's exclusive bins gives **184 zero/placeholder, 227 positive quantity with an unrecognized unit, and 151 NP/no-amount products**. The 184 group contains 178 literal source zeros, four source-form placeholders, and two independent missing captures; calling all 184 printed zeros was imprecise.

| Original flagged group | Products | Still unresolved after source/unit checks | Cleared |
|---|---:|---:|---:|
| Zero or zero placeholder |184|2|182|
| Positive quantity, unit not accepted by old helper |227|11|216|
| NP/no amount |151|55|96|
| Total |562|68|494|

The probe now accepts an explicitly selected zero source quantity (including declared zero percent), distinguishes synthetic zero from a printed zero, and uses the existing nutrient converter for mg NE/U and other activity-unit spellings. It respects cleaner-owned source eligibility and same-reference ancestor declarations. It does not lend an unrelated blend total to an undosed nutrient. Existing positive quantities already accepted by the production owner are retained; this is not a new form-confidence policy. Unresolved conversions stay separate from undisclosed amounts: four positive quantities printed with NP units are unit gaps, not absent numbers. The final 68 comprise **57 missing quantities and 11 unresolved unit/quantity cases**. Source facts and all per-product classifications are retained in `claude_counts.json`, `probe_correction.json`, and the frozen enriched probe inputs.

The full completion union reconciles independently to **540 products: 155 existing partial plus 385 additional proposed partial assessments**. The reason counts overlap and must not be added as exclusive bins:

| Reason | Products carrying reason |
|---|---:|
| Existing partial assessment |155|
| Known botanical/collagen benchmark, required amount unavailable |72|
| Unassessed probiotic mass/label-presence fallback |112|
| Unknown sugar total |84|
| Unresolved benchmark identity/context |52|
| Missing required nutrient quantity |57|
| Unresolved nutrient unit/quantity |11|

Their sum is543; the deduplicated union is540. The same independent reason reconstruction reproduces the former1033 exactly, including the112 probiotic fallback cases missing from Claude's reconstruction. The corrected three-option assembler reports540 for each option. Clearing494 nutrient false flags removes493 products from the overall partial union because one also has another reason.

The sugar count also needs precision: all84 have unknown total sugar in the canonical nutrition summary;82 carry0 g in the dietary display object and two retain nonzero values from other source context. Product213411 is explicitly marked Sugar-Free despite an NP sugar amount. The unknown-total issue is real, but it is incorrect to claim all84 are marked Sugar-Free or all84 carry0 g.

Regression evidence: printed zero, synthetic zero, mg NE, U, zero percent, same-nutrient source child, unrelated blend parent, and truly absent quantity cases pass; the printed-zero assertion failed before the repair. Twelve transform-order cases plus the real prenatal reference/choline regression pass. All77 raw hiding cases were rerun after the final probe repair, with zero eligible gains or receipt failures. All58 enriched-input SHA256s are unchanged. This correction changes private completion projections only: totals, provisional tiers and the three score-option distributions remain identical.

The recommended sixth-pillar option deliberately caps the combined additive/high-risk quality consequence at10 points. A high-risk ingredient can consume that whole budget, leaving no additional numerical loss for additives; structured concerns and warnings are separate and must remain visible. The Formulation-additive alternative retains more cumulative quality deductions (mean+0.02 versus+0.57). Choose the sixth-pillar model for one consistent formula-check budget, not to raise averages. The new confirmed-UL Dose ceiling10 is likewise a proposed policy, not a bug fix.

**Step4 is ready for Sean's policy decision and bounded implementation once approved.** There is no remaining measurement blocker in this pass. Approval must explicitly include the owner/cap choices and the proposed eligible-assessment hiding rule: an unknown assessment may not acquire a definitive tier/rank, even if provisional arithmetic rises. The original plan's literal scalar-monotonicity assertion is not claimed satisfied. Production changes and the rebuild remain on hold.

## Corrected option comparison

All 15,123 stored scored products were assembled for each option, with **zero arithmetic/receipt exceptions and zero unexplained movements on untouched products**.

| Complete option | Totals moved | Mean delta /100 | Provisional tier changes | Incomplete assessments |
|---|---:|---:|---:|---:|
| One owner; additives in Formulation; Dose neutral 11.4 | 11,318 | +0.02 | 2,429 | 540 |
| Same; Dose neutral 10 | 11,274 | -0.48 | 2,561 | 540 |
| Recommended: additives in sixth; Dose neutral 11.4 | 12,661 | +0.57 | 2,747 | 540 |

These are provisional mathematical tiers, including incomplete assessments, **not a count of publishable tier changes**. Completion is a private eligibility projection using existing complete/partial semantics. It is not yet implemented in the scored-artifact owner or app. Numeric projections retain provisional arithmetic for inspection; incomplete judgments must not be presented/ranked as final.

Recommended option: median delta 0.2, 5th–95th percentile -4.1 to +6.5. Route means: b_complex -2.24, fiber_digestive -1.16, generic +0.31, multi_or_prenatal +1.69, omega +0.83, probiotic -2.00, sports +3.43. Route means diagnose redistribution; they are not fairness targets. Verification mean movement is zero.

## Proposed owner/config decisions

| Concern | One numerical owner and required behavior |
|---|---|
| Additives, sugar and supported high-risk/watchlist findings | Sixth pillar, total deduction bounded by its existing 10 points; remove Formulation B0/B1 and sixth-pillar mirrors. Include existing low-severity quality signals, rather than silently deleting their effects. Their explanation remains a quality consideration, not an invented clinical warning. Only confirmed high-risk matches affect quality; preserve unresolved findings and warnings. |
| Dose safety | Dose alone: remove repeated B7 subtraction and the B-complex withdrawn `moderate_dose_fit` credit. Confirmed >100% applicable UL caps Dose at 10/20 without raising an already lower score. Findings/status/warnings remain separate. This proposed ceiling is not a clinical safe/unsafe boundary. |
| Disclosure and opacity | Transparency alone: remove label-presence credits from other pillars and the sports opacity penalty. Do not withhold the disclosure bonus a second time solely because a blend opacity penalty exists. Replace generic free identity base with credit conditional on resolved active identity. Printed quantity/strain names alone cannot establish adequacy/form quality. |
| Benchmark absence versus missing information | Neutral 11.4 only when the applicable benchmark is absent. An established benchmark with a missing amount does not receive neutral credit; leave the required assessment incomplete. Unresolved benchmark identity is also incomplete. Do not strip every botanical blend of its score merely because amounts are hidden. |
| Assessed botanical/collagen doses | Use shared daily minimum for adequacy and maximum for excess. Retain within/near/above band shape; grade below-range credit by fraction of the lower bound, instead of one flat severe-underdose credit. No new clinical benchmark is invented. |
| Probiotic Dose | Use the existing strain, aggregate-CFU eligibility and guarantee/viability owners; assessed strain credit cannot fall below the owner-derived eligible aggregate floor. Preserve native AFU assessment. Remove pure mass/CFU-label-presence fallback credit; incomplete if the required viable-dose assessment remains unperformed. |
| Form quality | Canonical IQM rating, including probiotics; no second reward for naming a strain. Explicit unrated Formulation neutral 12/20 before deductions. Remove known-low panel averaging floors; keep owner-derived parent-relative ratings and original panel weights. Botanical recognized identity becomes the same neutral treatment, not earned form quality. |
| Category purpose | Keep expected nutrient/core-panel denominators and source-backed composition criteria. Retire ingredient-count/focus/base bonuses and duplicate B-complex panel-presence awards. Choline participates once in prenatal critical coverage; retain original DHA complement allocation. |
| Evidence and branded traits | Gate probiotic certainty/replication on applicability; remove branded-study credit duplicated in Formulation. Retain evidence eligibility and the existing clinical source owners. |
| Missing nutrient or sugar amount | Preserve unknown source quantities; never coerce them to assessed zero/sugar-free. Extend existing completion owner, using existing nutrition/source-label and nutrient-reference facts. The private probe covers missing benchmarked vitamin/mineral label rows, not all optional blend ingredients. |

Rebase references to retained attainable components, rather than applying unrelated marginal changes. Final shadow references include Formulation botanical12, collagen8, multi12, B-complex8, probiotic15, protein15, fiber12; Dose ordinary sports20, complete EAA/BCAA22, fiber22, B-complex18, adult multi20, prenatal21, probiotic15. Other existing references remain. Formula configuration and metadata must express the same reference; check receipts at the public pillar boundary.

## What was corrected and verified

- **Benchmark census:** all 15,123 scored IDs join exactly one enriched input; zero missing/duplicate IDs or owner errors. Among 1,422 hidden botanical/collagen assessments: 72 have an applicable benchmark, 1,331 have no applicable registry benchmark, and 19 have unresolved identity/context. The last 19 receive no neutral uplift and remain explicitly unresolved, not silently counted as assessed. All 34 mixed fallback-window cases now use the actual Dose owner rather than a hand-written average.
- **Owner reproduction:** 529 probiotic Dose component sets and 2,484 generic fallback-window component sets reproduce their stored baseline exactly. Probiotic floors include the actual guarantee multipliers and live-strain eligibility. Form quality uses the canonical IQM owner. Collagen daily exposure and botanical maximum-use comparison follow the existing GLOSSARY contract in the shadow.
- **Reference accounting:** the isolated disclosure transform now derives its own references, rather than assuming the other transforms ran. It affects 7,391 products, mean −1.25, with 2,090 provisional tier changes; the original −0.41 marginal claim was conflated. Complete-option transforms order removal before profile rescaling, keep prenatal reference/choline logic after breadth retirement, and prevent graded reassessment from restoring a removed neutral/hidden fallback. Twelve targeted botanical/collagen ordering cases plus a real prenatal reference/choline case pass.
- **Frozen real labels:** 41 complete-quantity-removal cases pass through Clean → Enrich → Score and become not-scored. Another 36 source-preserving partial mutations retain other quantities or actual parent totals. Across these 77 cases, the corrected recommended shadow has **zero increases in a completed/eligible assessment and zero receipt failures**. This is a bounded counterfactual test, not universal proof. All 77 cases were rerun after the corrected zero/unit/source-row probe; no prior eligibility results were reused.
- **Real bugs retained for Step 4:** product173803 (Men’s Multi 40+ Organic Berry) rises 76.5→83.8 under current production when nested sugar/fiber amounts are removed, while still complete: missing sugar becomes zero and penalties disappear. Product12031 (Energy And Metabolism) gains 0.1 in the revised shadow when Vitamin A’s amount is hidden because the strict active set excludes the unquantified row. The proposed completion checks make both incomplete; their provisional arithmetic is still reported. These are not claimed fixed in production.

The hiding acceptance criterion is **no higher completed, eligible judgment after information is removed**, not that every provisional scalar must decrease. An unknown hazard cannot honestly be assigned a made-up worst-case penalty. Keep the unknown visible and prevent a definitive tier/rank. Safety findings that are no longer assessable must remain unknown, never become a positive reassurance.

## Evidence, scope and limits

Private, durable receipts: primary checkout `reports/step3_review_20261014/` — `verified_options.py`, `owner_facts.json`, `graded_owner.py`, `final_verified_options.json`, `raw_hiding.json`, `raw_partial_hiding.json`, `raw_policy_acceptance.py/json`, and checksum manifest. The original private harness is retained separately. All 58 enriched input SHA256s were rechecked unchanged. Result summaries enumerate arithmetic errors and unresolved cases explicitly.

This is a full **stored scored-corpus policy projection**, not a new production full-corpus replay. Inputs remain stored config1.23 artifacts with current1.24 source owners. Suppressed69/not-scored234 products are inventoried but excluded from numerical option averages. The source delivery-context defect (acid-resistant strain claims versus actual delivery systems) remains a required Step4 repair; its final impact is not qualified by these projections. Final source implementation, source-specific completeness tests, catalog parity and app rendering must be checked on the completed candidate. We do not claim all clinical source records were re-audited or that these tier thresholds are calibrated.

## Next authorized boundary

Step3 measurement corrections are complete, with the 19 unresolved records and source defects explicitly bounded. **Recommend the owner/config proposal above for Sean’s decision.** Keep production changes and rebuild on hold now. Once Sean approves the policy, Step4 is one bounded implementation batch: extend the existing owners; repair delivery context, missing-quantity provenance/completion and daily exposure; move magnitudes into config; remove proven dead entries; validate affected products and controls plus receipts/eligibility. Then use the required owner/consumer tests, local rung and one green exact-candidate CI checkpoint. Review tiers separately; do not tune the mean or preserve old product scores as a target. A later single pipeline run starts from verified stage fingerprints and requires the separate rebuild/release authorization.
