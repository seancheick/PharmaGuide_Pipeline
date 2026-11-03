# First Evidence review batch: report for Sean

Nothing is published. No clinician approval is claimed, and no record earns Evidence credit.

## Result

Reviews are finished for 5 of the top 10 ingredients. The other 5 are held on sources or a clinician decision, so I did not touch them. Measured on the 1,435 products that contain a batch ingredient, plus 150 controls, by replay from frozen raw labels:

| | This PR | If you approve Question 1 (what-if, not in this PR) |
|---|---|---|
| Partial to complete | 142 | 329 |
| Quality score moves | 0 | 0 once the Dose issue below is handled |
| Tier moves | 0 | 0 once the Dose issue below is handled |
| Safety status moves | 0 | 0 |
| Controls changed | 0 of 150 | 0 of 150 |

The 142 unlocked products by tier: Needs improvement 90, Poor 32, Good 13, Very good 7. Partial products already carried these tiers. Completion changes the status and the Evidence wording, not the number. The prediction for these five was far higher (methionine alone 61 and the full top 10 about 960), so read the route column in `review_order.csv` as a prediction.

| Ingredient | Result | Rows |
|---|---|---|
| methionine | Reviewed null. Closes | 174 rows close |
| ginkgo | Mixed. Scope covers declared standardization | 73 close as outside scope, 37 wait |
| collagen | Mixed. Scope covers hydrolyzed and peptides | 55 close as outside scope, 89 wait, 59 stay held by the signed record |
| fiber | Mixed. Scope covers named fibers | 72 close as outside scope, 31 wait |
| turmeric | Positive-weak. No scope | 196 wait |

## Corrections made along the way

- My first records used `applicable_reviewed_trials` while saying the trials did not transfer. That would have finished whole-turmeric rows, so I replaced it.
- That status and a turmeric scope also cut Dose from 11.4 to 0 on 5 products. The corrected records restore them, and the replay shows 0 moves.
- Two papers have corrections I could not read: 19017911 (GEM, JAMA erratum) and 31919527 (corrigendum 33301004). Following the flaxseed precedent, I retired them from the records and noted why.

## Questions for you

**Question 1: may an agent-reviewed literature record close in-scope rows at no credit?** Today it cannot. A preparation scope on a literature record always returns `invalid_applicability_contract`, because `_assess_legacy_signed_scope` needs a signed scope. Outside-scope rows do close, through `completed_scope_reasons`, so the rows the trials did test wait while the rows they did not test finish. Saying yes needs a small code change, and Dose must be protected as described above. I recommend yes, because it matches Dr. Pham's rule that a completed negative closes the research task without authorizing credit.

**Question 2: should outside-scope rows stay closed?** These are labels like "Fiber", "Collagen" and undeclared ginkgo extract. They now close through an existing owner, on a scope I wrote and no clinician signed. Consumers read: "Available research has not established a match to this product's assessed ingredients and use." I left this in because the existing owner allows it. To undo it, remove the `applicability` key from a record.

**Question 3: do trace food powders and single amino acids need individual review?** Blocked rows: broccoli 265, pumpkin 129, acai 132, culinary matrix 211, l_isoleucine 239, l_valine 226, l_tryptophan 67, l_threonine 49, l_histidine 58, l_phenylalanine 84. Options: a class disposition through the existing `not_efficacy_relevant` food-matrix path, a non-material role rule, nutrition authority for essential amino acids, or keep individual review. I recommend the food-matrix path for powders and a clinician ruling for amino acids. I changed nothing here. I did not collect label doses or roles for these rows, so check those before deciding. Methionine is also an essential amino acid, so a ruling could replace its review, and the current wording ("did not establish a clear benefit") should be read with that in mind.

**Question 4: clinician items, with papers.** Supply the PDFs listed in `traces.md`, or rule that an unread stronger meta-analysis stays an optional stronger claim, so each record closes as completed no-credit and reopens later. Yes or no for each: l_carnitine, elderberry, tmg_betaine, phytosterols, taurine, grape seed. Collagen needs one field: read the Am J Med 2025 paper for `collagen_skin_funding_40324552`, or authorize re-encoding it as a rejected source.

## Remaining work (rough estimate)

Predicted products closable from the 5,991 with blocked rows, from row reasons in `traces.md`, not replayed: policy decisions alone 1,017, agent review alone 2,110 (352 ingredients), clinician alone 1,566, all three 5,503, adding probiotics 5,662. Those figures assume a review closes its rows, and this batch shows that it often does not: only 1 of 5 reviews closed its in-scope rows. Without a yes on Question 1, more review mostly produces held records. With a yes, 352 ingredients at this depth (5 per long session, including verification and replay) is roughly 70 sessions, and the first 100 in the order carry most of the gain. Decide the questions before funding more review.

## Not done

- Replay covers products containing a batch ingredient, not the whole catalog.
- Not traced: why the probe and artifact differ on 152 products, and why 278416 stays blocked.
- `origin/main` moved during this work. I did not merge it or rerun the replay on it.
