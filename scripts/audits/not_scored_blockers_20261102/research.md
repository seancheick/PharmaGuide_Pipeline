# Not-scored blockers, 2026.11.02 build: receipts

Verified 2026-11-02. Label means the printed NIH DSLD label PDF (`https://api.ods.od.nih.gov/dsld/s3/pdf/<id>.pdf`), read directly. DSLD record means the raw staged JSON for that id. Agent review only: nothing here is clinician or Sean sign-off.

**Rule applied.** A named form with no established quality takes the parent's authored unspecified form, which is the floor. That follows existing entries such as Chromium Citrate and Manganese Fumarate under their unspecified forms. Every form entry is a parent-scoped `source_form_aliases` value, so it cannot create an identity on another row. No `bio_score` was invented. The one new form is corn silk's floor, which equals the value the unknown-form rule already derived (6).

## Forms read (`ingredient_quality_map.json`)

| Label text | Parent → form | Bio | Evidence and limit |
|---|---|---|---|
| Zychrome Chromium Dinicocysteinate; Chromium Dinicocysteinate | chromium → unspecified | 5 | DSLD 188790, 246350, 246370. `Zychrome` is already an alias of this form. Not found in PubChem or GSRS by that name, so identity rests on the label and the floor makes no quality claim. |
| Chromium GlycoProtein Matrix | chromium → unspecified | 5 | DSLD 231826, 62816. A branded matrix, no compound identifier. Floor. |
| Safflower | cla → cla 80% | 11 | Label 295001 prints "Conjugated Linoleic Acid (from Safflower oil)". The map already files `cla safflower oil` under this form. The label prints no 80%: that is the existing form's name, not a new claim. |
| Taraxacum mongolicum Root Extract | dandelion → dandelion root | 6 | DSLD 306204. GSRS: TARAXACUM MONGOLICUM WHOLE, UNII 4E8QL88U6H. A different species from the map's T. officinale. All dandelion forms hold 6, so no quality moves. No clinical data transfers. |
| Prunus avium Fruit Extract, Powder | dark_sweet_cherry → powder | 6 | DSLD 294296. GSRS: SWEET CHERRY, UNII 93T4562ZI3. `prunus avium extract` is already on this form. |
| Citrus Bioflavonoid Complex | diosmin → unspecified | 7 | DSLD 241290: "95% Diosmin, in a Citrus Bioflavonoid Complex, with Hesperidin". The complex is the carrier, not a diosmin form. |
| Omega-9 | flaxseed → flaxseed oil | 10 | DSLD 312832, 294583 note "source of omega-9". A marker on a row already named Flaxseed Oil. |
| Ginkgo-Phosphatidylserine Phytosome | ginkgo → unspecified | 6 | DSLD 287389 (Virtiva). Floor. Does not infer pure ginkgo or phosphatidylserine content, as the existing correction note requires. |
| Asian Ginseng Root Extract, Fermented | ginseng → fermented red ginseng | 12 | DSLD 328465, row GS15-4. The map already files GS15-4 under this form. |
| L-Arginine, OT2 | l_arginine → l-arginine base | 10 | DSLD 47590, 27808, 28993, 29066. DSLD UNII 94ZLA3W45F is arginine, on both the row and the form. OT2 is an unexplained brand token. |
| Manganese Bisglycinate Sulfate Chelate | manganese → unspecified | 3 | DSLD 66513. Not the map's bisglycinate. Floor. |
| Wild Green Oat Aerial Parts Extract | oat_straw → unspecified | 5 | DSLD 328434, row Neuravena. `neuravena` and `wild green oat extract` are already on this form. |
| Phosphorus Oxide | phosphorus → unspecified | 7 | DSLD 214676, 214952. Floor. |
| Plantago Asiatica | psyllium → unspecified | 8 | DSLD 312947, grouped by DSLD under Psyllium fiber. GSRS: PLANTAGO ASIATICA WHOLE, UNII 5F5728J5E8. A different species from P. ovata husk, so it takes no husk credit. |
| Ganoderma lucidum Mushroom Fruiting Body Extract | reishi → fruiting body | 9 | DSLD 328649. Same species and part as the existing alias. |
| Ganoderma lucidum spore, shell-broken | reishi → unspecified | 8 | DSLD 328649. Floor; no spore form exists. |
| Silicon Hydrolyzed Vegetable Protein | silica → unspecified | 7 | DSLD 27203. Floor. |
| Mixed Carotenoids; Mixed Carotenoids from African Oil Palm Fruit Extract | vitamin_a → beta-carotene from mixed carotenoids | 7 | DSLD 293269, 328127, 328639, each also naming Beta-Carotene. Keeps the row provitamin, so no preformed vitamin A or UL reading changes. Confirmed in replay. |
| Calcium Pantothenate Glycinate Amino Acid Chelate | calcium → calcium pantothenate (as calcium source) | 10 | Label 220021 prints "Calcium (as ascorbate, carbonate, pantothenate glycinate amino acid chelate)". Ambiguous between two forms, so it takes the lower one. |
| Magnesium Oxide Chelate | magnesium → unspecified | 1 | Label 256962 prints "Magnesium (as magnesium oxide & magnesium oxide chelate) 25 mg". Not a known compound. Floor. |
| Zea mays, Powder; Corn Silk, Powder | corn_silk → new `corn silk (unspecified)` | 6 | NIH labels print Cornsilk (Zea mays) Powder (pinned in `test_identity_label_named_over_group`). The matcher correctly refuses extract credit for a printed powder, and corn silk had no other form, so the existing alias could never be read. The new form holds the floor the rule already derived. |

## Identity conflicts, one pair at a time

| Label row | Resolves to | Evidence |
|---|---|---|
| Oregano Flower, Leaf Oil (328006) | oregano → oil of oregano | DSLD group `oregano`, forms Oregano Leaf Oil and Oregano Flower Oil. DSLD's UNII 7D0CGR40U1 was not found in GSRS, so it was not used. |
| organic Chamomile (flower) extract (285637, 232887) | chamomile → chamomile extract | DSLD group Chamomile. The map already reads `chamomile flower extract`. |
| FoodState farm fresh Beet Root (63330, 63463, 63475); FoodState(R) Farm Fresh Beet Root (43662, 43947) | botanical `beet_root` | DSLD group Beet, printed root. The reviewed correction text names no nitrate amount, so it does not reach `dietary_nitrate`. |
| Organic freeze-dried banana powder (28963) | other_ingredients `NHA_MISC_JUICE_CONCENTRATES` | That entry already holds `organic Banana powder`. |
| Organic Hemp Powder (seed) (259374) | new botanical `hemp_seed_powder` | GSRS: CANNABIS SATIVA SEED, UNII QE567Z26NG, RxCUI 1429926. Distinct from hemp seed oil and hemp protein. The notes forbid cannabinoid or whole-plant evidence transfer. UMLS returned no hemp-seed CUI, so `cui` stays null. |

## Withdrawn after checking

- **N-Acetyl-L-Cystine (78327).** Label prints this spelling at 15 mg. PubChem has that as a real compound (CID 12049111), distinct from N-acetylcysteine (CID 12035), while DSLD groups the row under N-Acetyl Cysteine. Choosing either invents an identity. Held for Sean.
- **Advanced Hair Complex on Biotin (336100).** Label shows it is a marketing name for a biotin, arginine and silicon matrix. `test_identity_label_named_over_group` pins this product held since 2026-10-23, so the pin stands. Held for Sean.
- **Zero-%DV parser change (212411, 212398, 214221).** These panels print "0%" with no amount, and the rows read as active doses, which looked like a falsy-zero bug beside the nonzero `daily_value_no_amount` branch. Extending that branch was tried and withdrawn. `identity.interaction.label_row_establishes_presence` treats that role as present, while a printed 0% reads as absent (Sean, 2026-09-26, register Q23), so it would have flipped presence on about 80 labels. It also finished none of them: replay moved 212411 and 212398 to `identity_assessment_incomplete` and left 214221 `not_scored` with no named blocker. The labels have no dosed active, so they stay held as a real label limit.

## Two pinned tests changed

Both pins said the row stays held because no form could be read. Each test's named purpose still holds: the row takes no credit from a higher form.

- `test_dinicocysteinate_never_inherits_polynicotinate_form` now asserts `form_id == "chromium (unspecified)"`, a bio below polynicotinate and no `unmapped_forms`. It was `unmapped_forms == [chemical]`. Affects 188790, 246350, 246370.
- `test_a_named_corn_silk_powder_cannot_claim_extract_form_credit` now asserts `form_id == "corn silk (unspecified)"`, bio 6 below the extract and no `unmapped_forms`. It was held as `FORM_DISCLOSED_UNMAPPED`. Affects 312640, 312713, 330886.

Sean can veto either: reverting that alias and that pin puts those products back on hold, and nothing else depends on them.

## Replay

Frozen raw labels through Clean, Enrich and Score, on main `0bd492188` and on this branch, with `scripts/audits/quality_redesign/replay.py`.

- 152 affected labels: all 152 `not_scored` on main, reproducing the build. 39 moved to scored. The rest stay held. See `per_product.md`.
- 121 controls, chosen because they carry the same forms and names or read zero-%DV rows: no status or score changed. Only 232887 (CBD+ Sleep) differs: its chamomile row now resolves, its reasons change, and it stays `suppressed_safety`.
- Safety fields compared across the 152: `product_safety_status`, `safety_verdict`, `dose_safety_evaluation`, safety review records, harmful additives and allergens. None changed.
- `interaction_profile` changed on 6. 231826, 246350, 62816, 287389 and 328465 change only `form_context` text, with no change to hits, severity or disposition. 285637 gains `RULE_INGREDIENT_CHAMOMILE` because its chamomile row now resolves: bleeding disorders, anticoagulants, antiplatelets and NSAIDs. That alert is correct for a product that prints chamomile, and it was missing before only because the row was unresolved.

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

**One policy for Sean to confirm.** A named form with no published quality evidence scores at the parent's floor instead of staying held. That is the existing unknown-form rule and has precedents, but it moves 39 labels from no score to a score, so it is his to veto.
