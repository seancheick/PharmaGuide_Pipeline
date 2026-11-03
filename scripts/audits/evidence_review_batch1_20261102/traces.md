# Traces behind the review order

All counts come from the unpublished 2026.11.02 scored and enriched artifacts in the main checkout, re-resolved with code at `0bd492188` and base literature data, through `score_eligible_identity_view`, the same view the scorer reads. Nothing here was published. The two sections on what the row and gate tables mean for this batch use the replay in `report.md`.

## Which rows actually block

The artifact labels 9,065 rows `no_reviewed_evidence_assessment`. Re-running the resolver gives the real reason for each row: 11,175 rows on 5,993 of the 6,289 Evidence-only products. The other 296 have no blocked row at all (see below).

| Rows | Resolver reason | What it means |
|---|---|---|
| 3,461 | `unverified_generated_record_cannot_complete_evidence` | The record was never reviewed |
| 2,102 | `clinical_sources_ineligible` | A curated record is held on a source or clinician decision |
| 1,698 | `literature_applicability_unestablished` | Reviewed, but the review does not establish applicability |
| 1,094 | `probiotic_species_or_stub_applicability_unestablished` | Probiotic species or stub row |
| 789 | `botanical_therapeutic_reference_unverified_studies` | Botanical route with no reviewed studies |
| 748 | `clinical_source_contexts_missing` | Curated record has no approved contexts |
| 295 | `invalid_applicability_contract` | Scope present but not signed |
| 269 | `crude_vegetable_powder_cannot_inherit_purified_extract_trials` | Hard-coded broccoli rule |
| 205 | `culinary_matrix_review_cannot_complete_extract` | Culinary review on an extract row |
| 155 | `active_identity_requires_literature_search` | No record yet |
| 133 | `crude_seed_powder_cannot_inherit_purified_oil_trials` | Hard-coded pumpkin rule |
| 131 | `reviewed_human_clinical_evidence_matched` | Resolves on current code |
| 55 | `label_claim_unclassified` | Label claim has no class |
| 35 | `trace_mineral_authority_established` | Resolves on current code |
| 2 | `identity_material_unresolved` | Identity not settled |
| 2 | `clinical_outcome_not_qualified` | Outcome not qualified |
| 1 | `probiotic_strain_reviewed_no_qualifying_human_evidence` | Resolves on current code |

The table sums to 11,175. So 2,600 rows (1,698 + 295 + 269 + 205 + 133) were not waiting on research. They were waiting on a rule about what a finished review may close. Sean's November 3 decisions give that rule; `report.md` says how it is applied.

The first version of this file reported 11,318 rows, listed only 11,222 of them, and said the probe disagreed with the artifact on 152 products. All of that came from one mistake: the probe resolved the raw enriched product instead of the scoring view, which added rows the scorer never reads (beetroot on 256991, apple fruit on 328104). Through the scoring view, the probe matches the artifact on all 6,289 products (0 mismatches).

## Why `clinical_sources_ineligible` records fail

These records are held on purpose. None is a data error an agent can fix. Each one's October 28 ruling or hold needs a paper we cannot read, or a decision only a clinician can make. I checked OpenAlex and Europe PMC on 2026-11-03: six of the seven papers are closed. PMID 24287284 is hybrid access but returned 403, and I did not try to get around that.

| Record | Unlocks (rank) | What holds it |
|---|---|---|
| `INGR_L_CARNITINE` | 162 (1) | 32154768 and 32359762 unread (closed). 32958033 is finished as non-credit |
| `INGR_ELDERBERRY` | 124 (3) | 30670267 unread (closed). 33827515 is finished as non-credit |
| `PRECLIN_BETAINE_ANHYDROUS` | 82 (6) | Ruling asks for outcome-scoped lower-body strength from 39514262 (closed, not in the record). 30064450 and 37409757 are approved as non-credit |
| `INGR_PLANT_STEROLS` | 64 (8) | Ruling reopened capsule and tablet LDL. 24144075 is closed, 24287284 returned 403. 19109655 is a food-matrix non-credit |
| `INGR_TAURINE` | 63 (9) | No contexts at all. 32871172 and 41275513 are closed |
| `INGR_GRAPE_SEED_EXTRACT` | 58 (11) | 34798267 unread (closed). 33671310 is null on its primary outcome, approved as non-credit |
| `INGR_COLLAGEN_PEPTIDES` | part of collagen (2) | Ruling says complete as no-credit for skin. One field blocks it: signed context `collagen_skin_funding_40324552` has `included_study_pmids: "extraction_pending"` |

Also held: `INGR_OMEGA3` (omega nutrition path, in the Evidence calibration work), `INGR_GLYCINE`, `SAME` and `SPIRULINA` (record-level `scoring_eligible: false`, no contexts), `INGR_CINNAMON_EXTRACT` (Khan 2003 expression of concern), `PRECLIN_PQQ` (correction hold), and `INGR_AMLA` and `PRECLIN_AKG` (reference-only, contexts missing).

## Why fully assessed products stay blocked

The brief counted 272. With current code it is 296: fiber_digestive 105, generic 94, probiotic 94, sports 3. I earlier counted 298 including 3 multi products and called those drift. That was the same probe mistake: 204732, 241347 and 241349 have real blocked rows (alfalfa, broccoli, cabbage extract, pumpkin), so they are not in this group.

**Generic, sports and fiber (202 products).** The artifact marks module-scoped product-level rows `not_applicable` / `module_scoped_product_projection`, so every visible row looks assessed. `evaluate_release_assessment` then re-resolves those same rows with `resolve_product_evidence(owner_scoped=True, module=...)` and adds `evidence_assessment_incomplete`. The ledger and the release gate disagree about what counts. Split, read the way the gate reads it (the raw enriched product, see below): unreviewed row only 107, unreviewed plus pending applicability 30, pending only 65, neither 0. An earlier version said 89, 47, 65 and 1 because it read the scoring view. Live probes: 278554 and 47339 both stop on a fiber row with `unverified_generated_record_cannot_complete_evidence`. The pending list is led by bromelain 24, prebiotics 13, collagen 8, pancreatin 7, triphala 6, phytosterols 6, elderberry 5, sytrinol 4.

**232321 (VenoFlow, Life Extension, partial, 44.9, Poor) is not a methionine case and has nothing to do with this batch.** The earlier "neither" was a probe artifact. `scored_artifact.py` passes the raw enriched product to the release gate, while the scorer and the row ledger use `score_eligible_identity_view`. The raw view has a `pine_bark_extract` Pycnogenol row with `unverified_generated_record_cannot_complete_evidence`, which the scoring view drops. Its nattokinase row resolves. So it is a real hold on an unreviewed active, reached through a view disagreement. I reported the disagreement to a9, which owns the completion rule.

**Probiotic (94).** 70 have `probiotic_evidence_assessment_incomplete` (180210 and 60467: strain status `strain_context_not_applicable`, so no reviewed conclusion). 20 carry the contributing context `is2_adult_ibs_multicenter_31434935`, 4 carry `p299v_ibs_rome3_22912552`.

**278416.** It is not in this group either. I reported it as unresolved because the old probe saw no blocked row. Through the scoring view it has four: alfalfa and cabbage extract (`unverified_generated_record_cannot_complete_evidence`), broccoli and pumpkin (the hard-coded crude-powder rules).

## Methionine

173 products have a methionine row on the Evidence-only list. 40 have no other open row, and all 40 finish. The order's 61 is greedy: it counts a product once every higher rank has closed. Replayed, those 61 are:

| Products | Also needs | Result |
|---|---|---|
| 40 | Nothing | Complete |
| 13 | `tmg_betaine`, held | Partial |
| 6 | `l_carnitine` and `taurine`, held | Partial |
| 2 | 27810 and 31064 | Partial |

On 27810 and 31064 the methionine row closes. Both stay partial on an unrelated `whey_protein` row: the resolver matches it to reviewed evidence, but the row ledger still says `not_yet_evaluated`. That disagreement predates this batch. I did not change it and reported it to a9.

The other 112 products have further open rows, led by l_isoleucine 60, l_valine 50, l_phenylalanine 45, l_histidine 41 and l_threonine 38.

## Why the fiber review is not in the data

A record moved from unverified to `applicability_unestablished` stops being a gap: `compose_product_resolution_state` treats that disposition as complete. Generic products still stop at their row ledger. The probiotic branch of `evaluate_release_assessment` reads only the module's `evidence_result_state`, so the fiber record alone finishes 3 probiotic products: 59635, 241707 and 276704. On 59635 the fiber row is a 0 g line on the label, and an approved hold (`test_held_assessment_publication.py`) would have become a public score of 60.9, Needs improvement. Sean's decision keeps these holds and rejects a module shortcut, so fiber stays out until that branch reads rows the way the generic one does.

That branch is a wider gap than fiber. Of 547 probiotic products, 279 are complete, and 98 of those have an open non-strain row (207050, 218190, 218199, 246009, 250619 among them). 68 of the 268 partial products have one too. Closing it would move those 98 to partial, so it is a change to the shared completion rule and I reported it to a9 rather than making it here.

## One row per ingredient in a blend

`get_evidence_subject_rows` keeps the first disclosed row of each identity from an undosed blend, so the gate reads one row where the label names two preparations. Among the products that finish, this affects 4:

- 46707 (Member's Mark) lists turmeric root powder and a 95% standardized extract. The gate reads the powder and records "outside the review". The extract, read alone, is inside the review. Both finish at no credit, so completion holds, but the recorded reason describes only the first row.
- 268562, 268575 and 326268 (Sports Research) list bovine and fish hydrolyzed collagen peptides, the same preparation class, so the reason holds for both.

## Why supporting rows block

Of 3,256 not-yet-evaluated rows on trace powder and amino acid products, 2,012 are `adjunct`, 649 primary, 320 claim-prominent and 275 major. `_evidence_owner_selection` passes the purpose tier of a material blend to its members, because an undosed member's share is unknown. All 389 products that have an adjunct row got it this way, and on 317 of them every open row is adjunct. So the rule that makes a supporting broccoli or pumpkin row need an answer is the existing inheritance rule, not a missing trial. Owner selection also decides Evidence points, so changing it is not a no-credit change. I reported the count to a9 and changed nothing.

Amino acids are mostly not supporting rows. l_isoleucine and l_valine are primary on 200 rows each, because they are what the product is. None is in `DRI_ESSENTIAL_NUTRIENTS`, so the nutrition-authority route does not apply. They take the ordinary documented review.

## Oddities for later

- The `fiber` canonical holds galactomannan and konjac glucomannan rows, and identical hydrolyzed collagen labels take two routes ("Collagen, Hydrolyzed" through the botanical path, "hydrolyzed Collagen" through the held backed record).
- `ginkgo`, `ginkgo_biloba`, `ginkgo_biloba_leaf` and `ginkgo_leaf_powder` are separate literature records for one botanical. The last two have different owners and purposes (Dose against Evidence), but the split is easy to trip over: see the Dose section of `report.md`.
- A finished no-credit row and an open one show the same Evidence sentence: "Available research has not established a match to this product's assessed ingredients and use." That is existing copy and this batch does not change it, but it reads oddly on a label the review does cover (312932). #338 owns the distinction between the two.
- `_metadata.verified_records_count` and `verified_studies_count` in `literature_evidence_records.json` already disagree with the file (809 against 783 authoritative records, 280 against 308 studies). The test comment says they record the last full verifier run, so this batch leaves them alone.
- PubMed turned up a turmeric liver-injury case series (32656820). The safety data already covers this signal: `RULE_IQM_TURMERIC_LIVER` and `RULE_INGREDIENT_CURCUMIN` in `ingredient_interaction_rules.json`, plus the `turmeric` CAERS entry. This batch changes none of them.
