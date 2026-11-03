# First Evidence review batch: report for Sean

Nothing is published. No clinician approval is claimed, and no record earns Evidence credit.

## Result

I read the literature for 5 of the top 10 ingredients. The other 5 are held on sources or a clinician decision, so I did not touch them. One review finishes rows, three are recorded and finish nothing, and one is not applied.

Measured on 1,285 products that contain a batch ingredient, plus 150 controls, from frozen raw labels through clean, enrich and the scored artifact, comparing base data with this PR's data:

| | This PR |
|---|---|
| Partial to complete | 40, all from methionine |
| Held to scored | 0 |
| Complete to partial | 0 |
| Quality score, tier, Dose or Evidence points moved | 0 |
| Safety status moved | 0 |
| Controls changed | 0 of 150 |

The 40 by tier: Needs improvement 37, Good 1, Very good 1, Poor 1. They already carried these scores and tiers. On 192 products the Evidence result state changes with no change in points, for example `clinical_review_not_covered` to `applicability_unestablished` (88). I did not review how each state reads to a consumer.

| Ingredient | Result | Rows in the Evidence-only set |
|---|---|---|
| methionine | Reviewed null. Closes through the existing owner | 173 close |
| turmeric | Applicability unestablished | 192 stay open |
| ginkgo | Applicability unestablished | 108 stay open |
| collagen | Applicability unestablished | 143 stay open, and 59 stay held by the signed record |
| fiber | Read, not applied | 57 stay open as they were |

The order in `review_order.csv` predicted 61 products for methionine; 40 finished in the replay. I did not trace the other 21. The prediction for a review that finishes nothing is simply wrong, so read the route column as a prediction, not a result.

## What was wrong in the first version of this PR

- **Three tests failed in CI and I had not run them.** After a late status change I ran a focused set that left out their files.
  - All four non-null records broke the literature contract: `applicability_unestablished` requires a null record effect. Their effects are now null, and the study-level findings stay on each study.
  - Product 59635 went from held to a public score of 60.9. See Question 2. Neither test's expected values changed.
- **"142 finished, 0 score moves" was wrong.** That number came from the unsigned scopes, and the release check ran only on products whose readiness flipped, which missed 59635. It now runs on all 1,435.
- **My unsigned scopes closed rows.** Fiber, ginkgo and collagen carried preparation scopes I wrote. Rows outside them closed as if a reviewer had concluded something. I removed all three. This withdraws my own closure and restores the existing hold; it does not decide Question 1.
- **The ginkgo scope excluded `powder`,** so "Ginkgo Biloba Extract Powder (24% Flavone Glycosides)" and EGb 761 extract powder read as crude leaf powder. No blocked label in the catalog had that wording, but the rule was wrong. Any future scope must not reject standardized extract powder.
- **The 329-product what-if is withdrawn.** It finished 329 products, cut Dose from 11.4 to 0 on 5 (278548 and 329958 to 329961) and moved 278548 from Needs improvement to Poor. "0 once handled" was never measured, and it used the same flawed selection. Nothing replaces it; treat the effect of a yes on Question 1 as unmeasured.
- **Stale text.** Four `research.md` status lines were out of date, and collagen's population still named a retired muscle trial. Both are fixed.
- **Trace numbers.** The table, the 152-product difference, the fully assessed count and 278416 all came from probing the wrong view of the product. `traces.md` has the corrected figures and the cause.

Two papers remain retired because their corrections are unread: 19017911 (GEM, JAMA erratum) and 31919527 (corrigendum 33301004), following the flaxseed precedent.

## Questions for you

The suggested answers below come from Codex's audit. They are recommendations for you to weigh, and I implemented none of them.

**Question 1: may an agent review finish rows at no credit, and under what policy?** Today one route does: a reviewed null with studies closes through the existing owner, which is how methionine finishes 40 products. A review with positive or mixed findings cannot, because `_assess_legacy_signed_scope` needs a signed scope. So a null finding finishes and a positive one waits. Codex suggests agent review only under an approved source-verified policy. If you want that, methionine should wait too: revert its one record and this PR finishes nothing. Allowing positive and mixed reviews to close needs a code change, and Dose must be protected first, as the withdrawn what-if showed.

**Question 2: should a row with an unsigned review count as finished on a probiotic product?** `compose_product_resolution_state` treats `research_present_applicability_unestablished` as complete. Generic products still stop at their row ledger. The probiotic branch of the release gate reads only the module's result, so moving fiber off its generated record would finish 59635, 241707 and 276704. On 59635 the fiber row is a 0 g line on the label. I left fiber out of the data to keep today's behavior, and the review is in `spec.py` and `research.md` ready to apply. Codex suggests no automatic completion from outside-scope rows, which points the same way. Your answer decides whether fiber goes in, and whether the gate needs tightening before any later review of a non-strain row on a probiotic label.

**Question 3: how should trace food powders and single amino acids be handled?** Blocked rows: broccoli 269, pumpkin 133, acai 132, culinary matrix 205, l_isoleucine 239, l_valine 226, l_tryptophan 67, l_threonine 49, l_histidine 58, l_phenylalanine 84. I withdraw my earlier recommendation, because I did not collect each row's role, dose or claim. Codex suggests classifying by actual role, dose and claim, and that needs those data first. I changed nothing here. Methionine is also an essential amino acid, so a ruling here may also apply to it.

**Question 4: clinician items, per record.** For each of l_carnitine, elderberry, tmg_betaine, phytosterols, taurine and grape seed: supply the unread papers listed in `traces.md`, or give a per-record ruling on what happens without them. Codex suggests the same. Collagen needs one field: read the Am J Med 2025 paper for `collagen_skin_funding_40324552`, or authorize re-encoding it as a rejected source.

## Remaining work (rough estimate)

Of 5,797 ordinary products with blocked rows (omega 141 and probiotic 244 counted apart), predicted closure if each route's rows really closed, from row reasons, not replayed:

| Route | Ingredients | Products closable by this route alone |
|---|---|---|
| Agent review | 341 | 2,218 |
| Clinician | 71 | 1,571 |
| Applicability decision (reviewed, cannot close) | 69 | 617 |
| Policy or identity | 43 | 212 |
| All four together | 524 | 5,765 |

This batch says to discount the agent figure heavily. Of the five reviews, one finished rows, and only because its finding was null. At that rate, 341 ingredients at 5 per long session is about 70 sessions and closes about 70 ingredients. 2,047 single-ingredient products sit behind those reviews, so at 1 in 5, and the 40 of 61 yield methionine showed, that is on the order of 270 products. It is a rough extrapolation from one batch. More review before Questions 1 and 2 are answered mostly produces records that stay open.

## Not done

- The replay covers products containing a batch ingredient, not the whole catalog, and the corpus was selected before the view correction.
- 232321 and the 21 methionine products that did not finish are not traced.
- `origin/main` is merged in. Its 23 new commits are release and signing work and touch no file this batch changed, so I did not rerun the replay on it.
