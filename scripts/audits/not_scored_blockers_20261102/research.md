# Not-scored blockers, 2026.11.02 build: receipts

Verified 2026-11-02. Label means the printed NIH DSLD label PDF (`https://api.ods.od.nih.gov/dsld/s3/pdf/<id>.pdf`), read directly. DSLD record means the raw staged JSON for that id. Agent review only: nothing here is clinician or Sean sign-off.

**Rule applied.** An entry stays only where the printed words identify a form the map already holds, and no earlier review note or test holds that row. Every entry is parent-scoped, so it cannot create a new identity on another row. A floor read where the chemistry or plant part is not established is not ours to add: `phase2_form_curation_20260929/README.md` held `phosphorus oxide` for exactly that reason. Those rows are decision C13.

## Forms read (`ingredient_quality_map.json`)

| Label text | Parent → form | Bio | Evidence and limit |
|---|---|---|---|
| Omega-9 | flaxseed → flaxseed oil | 10 | DSLD 312832, 294583 note "source of omega-9". A marker on a row already named Flaxseed Oil. |
| Asian Ginseng Root Extract, Fermented | ginseng → fermented red ginseng | 12 | DSLD 328465, row GS15-4. The map already files GS15-4 under this form. |
| Ganoderma lucidum Mushroom Fruiting Body Extract | reishi → fruiting body | 9 | DSLD 328649. Same species and part as the existing alias. |
| Mixed Carotenoids; Mixed Carotenoids from African Oil Palm Fruit Extract | vitamin_a → beta-carotene from mixed carotenoids | 7 | DSLD 293269, 328127, 328639, each also naming Beta-Carotene. Keeps the row provitamin, so no preformed vitamin A or UL reading changes. Confirmed in replay. |

## Removed after label review, November 3

These three aliases were in this PR and are gone. The earlier entries here over-read the labels: `cla 80%` holds a `cla safflower oil` alias, but the 295001 label prints no 80%, and a settled species does not settle a preparation. The rows are held.

| Label row | Alias removed | Why |
|---|---|---|
| Safflower, 295001 | `safflower` on `cla 80%` | The label prints safflower as the source, not 80%. Temporary hold; a qualified correction follows on a separate branch. |
| Prunus avium Fruit Extract, Powder, 294296 | `prunus avium fruit extract, powder` on `dark sweet cherry powder` | Sean: "Species identification is settled; preparation assessment is not." |
| Citrus Bioflavonoid Complex, 241290 | `citrus bioflavonoid complex` on `diosmin (unspecified)` | Sean: "The current mapping does not justify its score." That form is what `unknown_form_quality` returns for a form a label does not disclose, and this label discloses one. |

## Identity conflicts, one pair at a time

| Label row | Resolves to | Evidence |
|---|---|---|
| Oregano Flower, Leaf Oil (328006) | oregano → oil of oregano | DSLD group `oregano`, forms Oregano Leaf Oil and Oregano Flower Oil. DSLD's UNII 7D0CGR40U1 was not found in GSRS, so it was not used. |
| organic Chamomile (flower) extract (285637, 232887) | chamomile → chamomile extract | DSLD group Chamomile. The map already reads `chamomile flower extract`. |
| Organic freeze-dried banana powder (28963) | other_ingredients `NHA_MISC_JUICE_CONCENTRATES` | That entry already holds `organic Banana powder`. |

## Withdrawn after checking

- **N-Acetyl-L-Cystine (78327).** Label prints this spelling at 15 mg. PubChem has that as a real compound (CID 12049111), distinct from N-acetylcysteine (CID 12035), while DSLD groups the row under N-Acetyl Cysteine. Choosing either invents an identity. Held for Sean.
- **Advanced Hair Complex on Biotin (336100).** Label shows it is a marketing name for a biotin, arginine and silicon matrix. `test_identity_label_named_over_group` pins this product held since 2026-10-23, so the pin stands. Held for Sean.
- **Zero-%DV parser change (212411, 212398, 214221).** These panels print "0%" with no amount, and the rows read as active doses, which looked like a falsy-zero bug beside the nonzero `daily_value_no_amount` branch. Extending that branch was tried and withdrawn. `identity.interaction.label_row_establishes_presence` treats that role as present, while a printed 0% reads as absent (Sean, 2026-09-26, register Q23), so it would have flipped presence on about 80 labels. It also finished none of them: replay moved 212411 and 212398 to `identity_assessment_incomplete` and left 214221 `not_scored` with no named blocker. The labels have no dosed active, so they stay held as a real label limit.

## Released by mistake in `47a3ea25d`, put back in `f0f7e406c`

CI on `47a3ea25d` failed on 7 pinned labels. Checking every alias against the ledger and earlier audits then found more. These rows were held on purpose, the first batch of this PR released them, and 27 labels that it had scored are `not_scored` again. No test pin is changed any more.

| Row | Where the hold is recorded | Labels | Code |
|---|---|---|---|
| Plantago asiatica on Psyllium | LEDGER D21; 312947's correction says the repair must not remove this hold; `test_batch12_label_source_corrections` | 312947 | C9 |
| Taraxacum mongolicum on Dandelion | LEDGER D21 | 306204 | C9 |
| Wild Green Oat Aerial Parts on Oat Straw | LEDGER D21; `test_a_different_species_under_the_row_parent_stays_held_for_review` pins a near spelling, which is how the alias got past it | 328434 | C9 |
| Phosphorus Oxide | `phase2_form_curation_20260929/README.md`: chemically ambiguous, PubChem has no exact compound | 214676, 214952 | C10 |
| L-Arginine, OT2 | Same README and LEDGER Q32: token whose chemistry is not established | 47590, 29066; also 27808, 28993, already held on caffeine dose and evidence | C10 |
| Chromium GlycoProtein Matrix | Same README and Q32 | 231826, 62816 | C10 |
| Zychrome / Chromium Dinicocysteinate | Same README and Q32; `test_dinicocysteinate_never_inherits_polynicotinate_form` | 188790, 246350, 246370 | C10 |
| FoodState Farm Fresh Beet Root | `test_reviewed_literal_correction_exports_without_assigning_quality_identity`, returned review `acf3edb0f`, 2026-10-26 | 43662, 43947, 63330, 63463, 63475 | C11 |
| Organic Hemp Powder (seed) | Same test and review; correction text "No CBD/whole-plant evidence transfer" | 259374 | C11 |
| Corn Silk, Powder | `test_a_named_corn_silk_powder_cannot_claim_extract_form_credit`, `6d7d535d0`; the first batch also authored a new form with a bio score | 312640, 312713, 330886 | C12 |
| Magnesium Oxide Chelate; Manganese Bisglycinate Sulfate Chelate; Silicon Hydrolyzed Vegetable Protein | No hold recorded, but no established compound: same reasoning as phosphorus oxide | 256962; 66513; 27203 | C13 |
| Ginkgo-Phosphatidylserine Phytosome | 287389's correction forbids inferring pure ginkgo or phosphatidylserine, and the row scores under ginkgo | 287389 | C13 |
| Shell-broken Reishi spore | The map has no spore form, and 328649's correction says extract standards do not apply to spores | 328649 | C13 |
| Calcium Pantothenate Glycinate Amino Acid Chelate | The printed term reads as two forms, and choosing the lower one is still a choice | 220021 | C13 |

**Why the first check missed this.** It searched for identifiers and DSLD groups, not for earlier decisions on the same row, and the owner test set left out the two files holding the pins.

## Replay

Frozen raw labels through Clean, Enrich and Score, on main `0bd492188` and on `f0f7e406c`, with `scripts/audits/quality_redesign/replay.py`.

- 152 labels: all 152 `not_scored` on main, reproducing the build. `per_product.md` lists the 135 in the identity and dose groups, and 12 of those moved to scored at that commit. After the three aliases above were removed, 9 of the 135 score. That count is measured label by label from raw labels through `build_scored_artifact`, and each label is listed in `per_product.md`. The other 17 are outside this sort: 15 Cascara (229932, 251528, 252441, 253399, 253403, 253404, 311301, 311302, 311303, 311304, 327907, 330523, 330524, 330525, 332909) and 2 with no identity or dose blocker (222918, 315691). All 17 are `not_scored` on main and on this branch, with score, verdict and safety status unchanged. The 11 evidence-group labels were not replayed.
- 121 controls, chosen because they carry the same forms and names or read zero-%DV rows: no status or score changed. Only 232887 (CBD+ Sleep) differs: its chamomile row now resolves, its reasons change, and it stays `suppressed_safety`.
- Safety fields compared across the 152: `product_safety_status`, `safety_verdict`, `dose_safety_evaluation`, safety review records, harmful additives and allergens. None changed.
- `interaction_profile` changed on 2. 328465 changes only `form_context` text. 285637 gains `RULE_INGREDIENT_CHAMOMILE` because its chamomile row now resolves: bleeding disorders, anticoagulants, antiplatelets and NSAIDs.
- The 86 labels on PR #335's earlier list, on main and on this branch: no status, score, verdict or safety status changed.

## The dose group has no group (a)

No dose-blocked label had a curated or parser gap to fix. 25 of the 61 (20 no-reference, 5 whey) are exact editions Sean approved as `NOT_SCORED` on 2026-10-30 in `quality_score.json::suppression.held_assessment_labels`. Their blocking rows in `per_product.md` match the rows bound there. 27808 and 28993 had their arginine form fixed but stay held on caffeine dose and evidence.

## Decisions for Sean

| Code | Question | Products |
|---|---|---|
| C1 | Magnesium lysinate/glycinate and buffered bisglycinate. The note on `magnesium glycinate` (commit `c6487cea4`, 2026-10-13, calibration approved by Sean) says these are not aliases of that exact form, and no other form names them. `magnesium lysinate` alone is already on amino acid chelate (bio 11). Score these there, or stay held? | 269689, 270235, 302674, 302675, 322515, 323080, 25501, 203385 |
| C2 | Named salts with no form under the parent: L-Ornithine AKG, L-Glutamine AKG, PepZin GI on L-Carnosine, Di-Arginine Malate. Add a form at the floor, or hold? | 59067, 59086, 302699, 801, 31063 (the last two are also held on Molybdenum "75 mg") |
| C3 | N-Acetyl-L-Cystine at 15 mg: a label typo for NAC, or the literal compound? PubChem has both, DSLD groups it as NAC. | 78327 |
| C4 | Blend members written as forms, so a member reads as a form of the parent. TripleFlex: "Chondroitin Complex" 290 mg (`ingredientRows[4]`), DSLD forms Chondroitin Sulfate and White Willow Bark Extract, members disclosed, amounts not. Score the complex, or hold? | 12144 here; 855, 12300, 19598, 271115 from PR #335 |
| C5 | Advanced Hair Complex on Biotin: a marketing name for a matrix, pinned held since 2026-10-23. Stay held? | 336100 |
| C6 | Magnesium biotinate: recognized form with no bio score. Author one, or stay held? | 299744 |
| C7 | Marine Collagen: panel prints Protein 10 g, and the collagen sits in Other Ingredients. Read it as the collagen dose, or stay held? | 306350 |
| C8 | No completed dose reference (`dose_benchmark_identity_unresolved`). Sean approved these as exact-edition holds on 2026-10-30. Keep holding, or commission approved neutral records? Sibling session `start-evidence-review-wi` may overlap. | Horsetail: 251616, 327984, 252704, 254795, 254796, 254797, 312024, 312025, 312026, 312027, 331202. Others: 231921, 232035, 269718, 328831, 232921, 232928, 220046, 80302, 295107 |

**C9 to C13 are decided.** Sean answered "Yes, hold all 29" on November 3, 2026. C13 rests on `unknown_form_quality`: a named form the map does not recognize stays unmapped for curation and is not routed to the floor.

| Code | Question | Products |
|---|---|---|
| C9 | Different species or plant part from the map's parent, left held on purpose in LEDGER D21. Keep holding, or give each its own form? | Plantago asiatica 312947; Taraxacum mongolicum 306204; wild green oat aerial parts 328434 |
| C10 | Terms whose chemistry was not established in form curation. Keep holding, or commission an identity check? | Phosphorus Oxide 214676, 214952; OT2 47590, 29066, 27808, 28993; Chromium GlycoProtein Matrix 231826, 62816; Zychrome/Dinicocysteinate 188790, 246350, 246370 |
| C11 | The October 26 review exports these without a quality identity, and its stated limits are no nitrate allocation and no CBD or whole-plant transfer. Was withholding the score itself intended, or may they score with those limits kept? | Beet root 43662, 43947, 63330, 63463, 63475; hemp 259374 |
| C12 | Corn silk powder: the only form is an extract, and a printed powder cannot take its credit. Author a powder form, or keep holding? | 312640, 312713, 330886 |
| C13 | Named forms with no established compound or part. May a named form score at the parent's floor, or does it stay held? | 256962, 66513, 27203, 287389, 328649, 220021 |
