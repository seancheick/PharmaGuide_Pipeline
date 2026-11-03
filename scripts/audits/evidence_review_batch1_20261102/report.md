# First Evidence review batch: report for Sean

Nothing is published. No clinician approval is claimed, and no record earns Evidence credit. This applies your November 3 decisions; it does not ask you to approve the result, and it does not authorize a whole-catalog build.

## Result

200 products go from partial to complete. No score, tier, Dose points, Evidence points or safety status moves on any product.

I replayed 2,063 products from frozen raw labels through clean, enrich and the scored artifact, comparing base data with this PR's data. That covers all but 2 of the 1,923 products with a batch ingredient anywhere in their enriched data, plus controls. The first replay had missed 630 of them, mostly fiber rows, so I added 628 and read the other 2 through their stored enriched files, because they are user submissions with no raw label.

| | This PR |
|---|---|
| Partial to complete | 200 (199 replayed, 1 user submission) |
| Held to scored | 0 |
| Complete to partial | 0 |
| Quality score, tier, Dose or Evidence points moved | 0 |
| Safety status moved | 0 |
| Controls changed | 0 of 150 |

The 200 by tier: Needs improvement 155, Good 23, Poor 16, Very good 6. They already carried these scores and tiers. On 192 products the Evidence result state changes with no change in points.

| Record | Finish | Reviewed preparation, no credit | Outside the review (preparation or label purpose) | Mixed rows |
|---|---|---|---|---|
| turmeric | 66 | 47 | 14 | 5 |
| collagen | 66 | 54 | 9 | 3 |
| methionine | 40 | 40 (reviewed null) | 0 | 0 |
| ginkgo | 28 | 19 | 8 | 1 |
| fiber | 0 | Read, not applied | | |

The collagen line includes the user submission. `products_complete.csv` names each product, its record and its conclusion. `products_held.csv` names every replayed product that stays incomplete and the open rows behind it.

## How each decision is applied

**1. A documented review may close an ordinary assessment.** Turmeric, ginkgo and collagen now state once, on the record, the preparation, purpose, population, sources and scope (`documented_review_scope`), and every label reuses it. The sources must be cited papers whose live record and abstract were checked. The record says Claude did the review. Nothing names an agent as a clinician.

| The label | The row | Example |
|---|---|---|
| Declares a preparation inside the scope | Finishes at no credit | "Collagen, Hydrolyzed", 312932 |
| Declares a preparation outside it | Finishes as outside the review | "Ginkgo biloba, Powder", 329958 |
| Declares a purpose the sources do not cover | Finishes as outside the review | 74547 |
| Declares no preparation, or an unclassified claim | Stays open | "Turmeric", or 278548 |

The last line is the one that matters: an unresolved match is not renamed a conclusion.

**2. No module shortcut.** Fiber stays out of the data, and 59635, 241707 and 276704 stay held. The reason is in `traces.md`: the probiotic branch of the release gate reads the module result rather than the rows. The same gap already lets 98 of 279 complete probiotic products through with an open non-strain row. Closing it is a change to the shared completion rule, so a9 has the count and the product IDs.

**3. Trace powders and amino acids use the existing rules.** No new rule and no blanket call on powders.
- 2,012 of the 3,256 open rows on these products are `adjunct`. All 389 products with an adjunct row inherit it from a material blend, and on 317 of them every open row is adjunct. So the existing inheritance rule is what asks a supporting broccoli or pumpkin row for an answer, not a missing trial. Owner selection also decides Evidence points, so I did not change it here. a9 has the count.
- l_isoleucine and l_valine are primary on 200 rows each, so they are not supporting rows. None is a DRI essential nutrient, so they take the ordinary documented review, one preparation and purpose at a time.

**4. The holds stay.** Nothing changed on carnitine, elderberry, betaine, phytosterols, taurine or grape seed, and the signed collagen record stays held on its unresolved extraction (60 products). Unread papers are not recorded as negative or complete. PMID 24287284 stays unread: its publisher returned 403 and I did not try to get around that.

## Dose

The review does not move Dose. The 11.4 points on 278548 and 329958 to 329961 are the existing neutral value for a disclosed dose with no applicable benchmark (`no_benchmark_neutral`, `pharmaguide_policy`, reason "Dose disclosed, but adequacy cannot be determined"). The review adds no benchmark, so those points are still supported, and they are not being preserved to protect a tier.

The earlier drop to 0 was a real coupling. `_completed_botanical_reference` and `_botanical_benchmark` read a record's `applicability`, so writing an Evidence scope into that key narrowed turmeric's Dose reference, and changing the status hid the exact-preparation ginkgo owners. The owner fix is a separate key that Dose does not read, with the record status left as it was. The 5 products keep 11.4 in the replay. 329958 to 329961 are now complete at 54.4 (Poor); 278548 stays partial at 55.4 on its unclassified claim.

## Who stays held

1,098 of the 2,063 replayed products stay incomplete. Evidence blocks 1,086 of them, some alongside another blocker. The other 12 stop only on Dose or identity.

| Open rows | Products | Why |
|---|---|---|
| A batch record's row | 414 | See below |
| Only other ingredients' rows | 668 | Not reviewed in this batch, or held on their own record |
| No individual row | 16 | 11 stop on Dose or identity, 5 on the probiotic gate. 59635 is one of the 5 |

Products with an open batch row (a product can appear in more than one line):

| Row | Products | Why it is open |
|---|---|---|
| fiber | 179 | Review not applied |
| turmeric | 75 | Mostly no preparation declared ("Turmeric", "organic Turmeric") |
| ginkgo | 65 | Mostly an unstandardized "Ginkgo biloba leaf extract", which the review does not settle |
| collagen, signed record | 60 | The unresolved extraction |
| collagen, literature record | 47 | Mostly no preparation declared ("Collagen", "Marine Collagen", "Gelatin") |

14 of the open turmeric, ginkgo and collagen products name a preparation inside the review and still stay open. The one I traced (278548) has an unclassified label claim. I did not trace the other 13, and they are conservative either way.

## Methionine and 232321

Every methionine case is accounted for in `traces.md`. 40 finish, 19 also need a held betaine, carnitine or taurine row, and 27810 and 31064 stay partial on a whey row where the resolver and the ledger disagree. 232321 is not a methionine case: it holds on an unreviewed Pycnogenol row that the release gate sees and the scoring view drops.

## Corrections to earlier versions

- **Workload estimates are removed.** The session and product projections extrapolated from one batch and were unsupported. The `unlocks` column in `review_order.csv` is greedy and assumes every higher rank has closed, so read it as an order, not a forecast. Its route names now say `documented_scope` and `held_source_or_ruling`.
- **The 142-product figure and the 329-product what-if stay withdrawn.** The 40-product result was correct for the rule then in force and is superseded by this one.
- **The first replay did not cover every product with a batch ingredient.** The 628 added products changed nothing.
- Earlier corrections: the literature contract failures, the ginkgo `powder` exclusion and the 11,318-row table are all fixed, and `traces.md` has the correct figures. Papers 19017911 and 31919527 stay retired because their corrections are unread.

## For a9

- The probiotic branch reads the module result (98 complete products with an open non-strain row).
- The release gate reads the raw enriched product while the scorer and ledger read the scoring view (232321).
- The resolver and ledger disagree on some matched rows (27810, 31064; 266 such rows in `products_held.csv`).
- Material-blend members inherit the purpose tier (389 products).
- A finished no-credit row and an open row show the same sentence: "Available research has not established a match to this product's assessed ingredients and use." #338 owns that distinction.
- `get_evidence_subject_rows` keeps one row per ingredient in a blend. On 46707 the gate reads the root powder and records "outside the review", while the 95% extract would be inside. It finishes at no credit either way, but the recorded reason describes only the first row.

## Not done

- No whole-catalog build. The replay covers the products with a batch ingredient and the controls.
- Fiber is not applied, and the other held records are not reopened.
- This branch is not merged with a9's work. That branch changes `assessment_readiness.py` and `scored_artifact.py`, including a new capture-gap condition on completion that could hold some of these products. Both branches edit `test_blend_identities_have_a_finished_review.py`. Whichever lands second must reconcile that test and rerun this replay.
