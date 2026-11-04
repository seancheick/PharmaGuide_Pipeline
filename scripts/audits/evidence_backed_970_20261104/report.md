# Evidence review of the 74 ingredients behind 970 labels

Agent review (Claude), November 4, 2026. No clinician approval is claimed or written. Nothing is published.

## Result

| Ingredient | Labels | Stored | As read | Recommendation | Packet |
|---|---:|---|---|---|---|
| l_lysine | 49 | positive_weak | Null at review level; older trials conflict | No credit | `packet/INGR_L_LYSINE.json` |
| l_tyrosine, free form | 34 | positive_weak | Mixed; acute task effects, null for endurance | Held: 3 doses behind closed full text | `packet/INGR_L_TYROSINE.json` |
| l_tyrosine, N-acetyl | 11 (37 reached) | positive_weak | No oral efficacy trial found | **True rejection, in this PR** | `records.py` |
| pomegranate | 44 | positive_weak | Mixed; juice-led, I² above 90% | Held: extract subgroup unreadable | `packet/INGR_POMEGRANATE.json` |
| nattokinase | 41 | positive_moderate | Mixed, blood pressure only | Held: fibrinolytic-unit dose can't be stored | `packet/INGR_NATTOKINASE.json` |
| mct_oil | 40 | positive_weak | Weak, weight when replacing other fat | Held: 13 trials not extracted | `packet/INGR_MCT_OIL.json` |

Label counts come from the census, not row counts. The 74 come to 74, covering 970 labels; 7 labels carry two of them, so `the74.csv` sums to 977.

No context in these packets is marked eligible. Reading did not produce a top-5 context I would recommend for credit as it stands.

Packets use the patch shape of `held_source_closure_20261028`. These ingredients have no backed record yet, and that apply path expects one, so each `record_updates` carries the whole record body and applying one starts from `{"id": record_id}`. That path also leaves pending contexts out of the data. `check_packet.py` tests this in memory; nothing is written. In memory, each record's only source-review errors are the unsigned reviews (`review.approval_required`, `clinical_source_rejection_incomplete`) plus the gaps each hold names (`dose.source_review_incomplete`, `included_studies.review_incomplete`).

## True rejection

`INGR_N_ACETYL_L_TYROSINE` rejects every label it reaches with `clinical_form_excluded`. It has no study contexts and earns nothing.

- **Evidence:** PubMed title and abstract search: 225 records, 42 in a human-use or supplement context read as excerpts. None is an oral efficacy trial of N-acetyl-L-tyrosine alone. The human reports are intravenous or parenteral (PMIDs 2507878, 14621123, 7705801), with a large share excreted unchanged; two pre-workout blends contain 300 mg (PMIDs 28096758, 28096757).
- **What `null` means here:** no affirmative finding exists for this preparation. It does not say the preparation was tested and failed; the rationale states that.
- **My reading of the instruction:** "don't ship no-context records" meant credit-bearing records that drop labels to partial. This one earns nothing and finishes labels. If that reading is wrong, this record comes out.

## Measurement

Raw label through clean, enrich and the scored artifact, by name, base against candidate. 70 labels: the 37 the record reaches and 33 free-tyrosine controls. Holds 241290 and 294296 measured separately.

| | Main | #354 tree (92308be30) |
|---|---|---|
| Score, tier, Evidence or Dose moved | 0 | 0 |
| Safety status moved | 0 | 0 |
| Partial to complete | 0 | 11 |
| Now show Sean's sentence | not on main | 11 |
| Stay partial for other rows | 19 of 70, unchanged | 17 of 37 reached, unchanged |
| Controls changed | 0 of 33 | 0 of 33 |
| 241290, 294296 changed | 0 | not run |

The driver is the row reason: on the 37, each N-acetyl row now reads `clinical_form_excluded` rather than matching nothing. `nat_labels.csv` lists all 37. C1 to C13 are held rows in the blockers lane. A record can only change labels it reaches, and nothing moved on the 37 it reaches.

**On #354, all 33 free-tyrosine controls read "Clinical evidence review pending" and sit at partial.** That is #354's own behavior, and it will apply across the 970 until each ingredient has an answer.

## Stop list: the existing fields can't express these

1. **Nattokinase dose.** Every positive trial reports fibrinolytic units. `DOSE_MEASUREMENT_UNITS` has mass, AFU, CFU and spores. A context can't verify this dose, so it can't be eligible. A new unit is a schema change, so I stopped here.
2. **Coconut products that print an MCT row.** 251539, 327918, 259503, 212876, 53872, 239047. The row reads as MCT or caprylic acid, and only the product title says coconut. PMID 28689741 reports coconut oil isn't equivalent to MCT oil for satiety. No field reads the title.
3. **Purpose limit on a label with no claim.** Tyrosine's evidence is acute demand and MCT's is replacing other fat. A label with no claim reads `absent`, which is creditable, so no field limits credit to that purpose.
4. **Pomegranate flower rows.** 232129, 232132, 60602, 232748, 74011, 328442 pair a flower extract of unstated amount with Pomella. The flower evidence read is mostly animal, but the row can't be separated from the extract.

## For Dr. Pham (no record written)

- **Nattokinase and clotting:** prolonged closure time and aPTT against placebo after 8 weeks (PMID 31070609); aPTT prolonged after one dose, within normal range (PMID 26109079). `RULE_IQM_NATTOKINASE_BLEEDING` already covers anticoagulants and antiplatelets at `avoid`. Question for her: does the clotting-time finding change anything beyond that? The rule isn't edited here.
- **Stored ratings:** nattokinase `positive_moderate` and pomegranate `positive_weak` stay on her list.
- **Nattokinase and metabolic markers:** total cholesterol and glucose higher in the meta-analysis (PMID 39076715).
- **N-acetyl-L-tyrosine:** a liver-failure case on a fat burner containing it among other ingredients; the authors found no prior report for those substances (PMID 32192741). No attribution can be drawn.
- **Eligibility:** each packet ends in one question for her.

## Corrections to stored claims

- Nattokinase's `positive_moderate` rests on one trial of coagulation markers in 12 healthy young men.
- The pomegranate note that the extract subgroup's diastolic result wasn't significant can't be verified from what's open.
- Deijen 1999's stored `positive_strong` compares a protein drink with a carbohydrate drink, so it isn't tyrosine alone against placebo.
- Pomegranate 40218993's blood pressure result is secondary; its primary outcome is IL-6.

## What was read, and what wasn't

- Abstracts through PubMed for all 48 receipts, unless a receipt says otherwise.
- Named full text passages only for 40218993, 36548401 and 39076715.
- Not read: the Cochrane review's full text (Europe PMC failed), so its lysine trials aren't extracted. Most tyrosine, pomegranate and MCT full texts aren't open.
- PMID 24287284's PDF stays unread after a fetch was refused.
- Pomegranate 10 powder labels: no powder trial read yet.
- The search for each top-5 ingredient isn't a systematic review.

## Lysine, closed in this PR

`l_lysine` now has `effect_direction: null`, the no-credit path methionine took in #340. The rationale names the positive trials (PMIDs 3115841, 6435961), a null trial (PMID 6419679) and the Cochrane sentence "We failed to find any evidence of efficacy for lysine" (PMID 26252373). It reads as conflicting evidence with no clear benefit, and it's marked agent review, not clinician reviewed.

## Batch 2: next 12 ingredients, plus lysine

| Ingredient | Labels | Stored | Result | Field |
|---|---:|---|---|---|
| l_lysine | 49 | positive_weak | **Closed:** conflicting, no clear benefit | literature `null` |
| l_leucine | 36 | positive_weak | **Closed:** conflicting, no clear benefit | literature `null` |
| lecithin | 33 | positive_weak | **Closed:** conflicting, no clear benefit | literature `null` |
| siberian_ginseng | 27 | positive_weak | **Closed:** conflicting, no clear benefit | literature `null` |
| d_ribose | 26 | positive_weak | **Closed:** exercise mostly null; cardiac positives in patients at far higher amounts | literature `null` |
| cayenne_pepper | 26 | positive_weak | **Closed:** no qualifying study for these labels | `no_qualifying_human_evidence` |
| gotu_kola | 22 | positive_moderate | **Closed:** no qualifying study for these labels | `no_qualifying_human_evidence` |
| feverfew | 20 | positive_moderate | **Closed:** no qualifying study for these labels | `no_qualifying_human_evidence` |
| butterbur, whole herb extract | 6 of 25 | positive_strong | **Closed:** root extract trials only | rejection `INGR_BUTTERBUR_WHOLE_HERB` |
| l_ornithine, L-aspartate | 8 of 20 | positive_moderate | **Closed:** cirrhosis trials only | rejection `INGR_L_ORNITHINE_L_ASPARTATE` |
| apple_cider_vinegar | 39 | positive_weak | Pending: capsule RCT in PCOS (42215584) | packet |
| blueberry | 24 | positive_weak | Pending: 100 mg extract trial, WBE111 (29882843) | packet |
| lions_mane | 21 | positive_moderate | Pending: 3 g/day tablet trial (18844328) | packet |
| butterbur, the rest | 19 of 25 | positive_strong | Pending: Petadolex RCTs (15623680, 14752215); liver items | packet |
| l_ornithine, the rest | 12 of 20 | positive_moderate | Pending: stress and fatigue trials; results table of 19083482 unread | packet |

### The three ways a review closes

No field here is new, and none gives credit.

1. **Literature `null`:** an abstract says directly there's no benefit, and a positive trial exists. The rationale names both sides. The label reads "We reviewed the human research and it did not establish a clear benefit for these ingredients."
2. **`no_qualifying_human_evidence`:** the review finished and no study meets rule 2 for what these labels print. The owner's rule is that this result carries no studies, so `applicability_decision` names each one and why it falls short; the packet keeps the full reading. The label reads "We reviewed the research but found no qualifying human clinical evidence of benefit applicable to this product." 152 records already use this result.
3. **Backed rejection:** one preparation differs from what was studied, and the ingredient's other preparations stay open. The label shows Sean's sentence on #354.

An ingredient with a study that meets rule 2 for a preparation its labels print stays pending for Sean's ruling. Its packet holds the question.

`applicability_status: applicability_unestablished` and a reference-only record do not finish a label: probed on cayenne, both left all 26 at partial on #354.

### Measurement

Raw label through clean, enrich and the scored artifact, by name, base against candidate, on the 253 labels these closures reach.

| | Main (aa65ec72d) | #354 (72e2e22ed) |
|---|---:|---:|
| Score, tier, Evidence or Dose moved | 0 | 0 |
| Safety status moved | 0 | 0 |
| Partial to complete | 0 | 244 |
| Stay partial for other rows | 2, unchanged | 9 |
| Reason text changed | 225 | 246 |

A literature record reaches every label carrying that ingredient, not only the 970. All 991 labels carrying one of the eight corrected ingredients, measured on main: 0 score, tier, Evidence, Dose, status or safety moves, and 258 display reasons changed. On those labels, `qa` and `sa` didn't move.

Older tests pinned the stored text, so the changes are deliberate:

- `test_clinical_registry_evidence_corrections.py` and `test_literature_records_review_20261020.py`: the rationales keep the true sentences they pin, on leucine's and lysine's thresholds and cayenne's 2 mg.
- `test_evidence_resolver.py::test_bcaa_sports_amino_dose_applicability_not_points`: leucine now closes as `reviewed_null_unfavorable` at both doses, with no points.
- `test_evidence_result_state.py::test_product_level_owner_is_not_nothing_to_assess`: soya lecithin now reads `evaluated_null`, still not "nothing to assess".

### Projection rows

62 of the 970 labels carry `module_scoped_product_projection` (64 rows, all `product_level_evidence`), which blocks #354's sentence: Natto Extract 13, Lactase 11, Nattokinase 7, Alaska Blueberry 5, NSK-SD Nattokinase 4, Cayenne Pepper 3, Kudzu 2, Protein 2 and others. Scored on stored enrichment on #354. a9-finish's fix covers rows with their own rejection.

### What would settle the held ingredients

- **l_tyrosine, free form:** daily doses in PMIDs 25598314, 24433977 and 29980424.
- **pomegranate:** the extract subgroup of PMID 38410857.
- **nattokinase:** a stored unit for fibrinolytic units, a schema change. Stopped.
- **mct_oil:** the 13 trials in PMID 25636220.
- **l_ornithine:** the results table of PMID 19083482.

### Batch 2 limits

- Abstracts only, unless a receipt says otherwise. Each no-qualifying rationale says so, and says it doesn't state a preparation was tested and failed.
- Lecithin: 6 labels print sunflower lecithin, and no trial of it was found. The dementia quote doesn't test them; the rationale says no sunflower trial was found.
- Whole-herb butterbur: titles scanned across 97 and 30 records, not every abstract opened; the record says so.
- Gotu kola: two labels print a triterpene percentage (306227 at 10%, 219195 at 6% glycosides). Neither prints the total triterpenic fraction tested.
- These searches aren't systematic reviews.

### For Dr. Pham, batch 2 (no record written)

Each entry is a question from the read, not a finding in a record. Sources are in `clinician_items` in `decisions/<ingredient>.json`.

- **Butterbur and liver:** PMIDs 31083451, 39853578.
- **Cayenne, gut symptoms and dropouts:** PMIDs 21573941, 33291700.
- **Lion's mane:** PMIDs 32581767, 40959699.
- **Feverfew:** PMID 34434419.
- **Apple cider vinegar:** PMIDs 15983536, 39238884, 23373303. PMID 41010525 pools a trial since retracted (PMID 38966098).
- **D-ribose:** PMIDs 24272966, 36551203, 8815168.
- **Siberian ginseng:** PMIDs 15190050, 15207399, 11798012, 24683218.
- **Lecithin, adverse effects:** PMID 12917896.
- **Ornithine:** PMIDs 40323503, 20717126, and whether LOLA liver data belongs on a supplement label at all.

## Batch 3: the rest of the 74, and the 21 read so far

Agent review, abstracts mainly, November 4, 2026. No credit, no clinician approval. Every quote was checked live against PubMed before applying. Label counts are the ones each read reported.

### The 74

- **Closed, conflicting with no clear benefit (13):** aloe_vera (15), arjuna (2), borage_seed_oil (16), caralluma (14), cayenne_pepper (26), cocoa (9), feverfew (20), gotu_kola (22), guarana (6), hawthorn (20), hibiscus_extract (13), nicotinamide_riboside (7), theobromine (19).
- **Closed, no qualifying study for these labels (28):** african_mango (9), agmatine (14), algae_oil (1), apple_cider_vinegar (39), atp (2), blood_orange_extract (3), broccoli_sprout (1), chlorophyll (12), coleus_forskohlii_root (5), diamine_oxidase (1), fucoidan (2), jujube (12), l_serine (16), licorice (2), lions_mane (21), nopal (1), oat_straw (3), oregano (18), phosphatidic_acid (1), picrorhiza (1), puerarin (14), pygeum (11), red_clover (11), rose_hips (10), rosemary (13), tudca (16), turkey_rhubarb_root (7), turkey_tail (5).
- **Pending, packet for Sean's ruling:** ashwagandha_root (2), blueberry (24), butterbur (25), citrus_bergamot (5), colostrum (8), dgl_deglycyrrhizinated_licorice (7), diosmin (3), english_ivy (4), globe_artichoke (13), horse_chestnut_seed (9), l_ornithine (20), lactase (11), larch_arabinogalactan (5), mastic_gum (3), olive_fruit (4), olive_leaf_powder (1), siberian_rhubarb (1), white_willow_bark (9).
- **Held, a paper would settle it:** butchers_broom_root (4), capsaicin (1), lumbrokinase (2), maqui_berry (1). See below.

### The 21

- **Closed, conflicting with no clear benefit (4):** alpha_linolenic_acid (10), cla (76), lycopene (23), zeaxanthin (32).
- **Closed, no qualifying study for these labels (2):** goldenseal (28), l_glutamine (81).
- **Pending, packet for Sean's ruling:** collagen (48), gamma_linolenic_acid (11), glutathione (35), green_coffee_bean (22), milk_basic_protein (1), turmeric (39).
- **Not touched:** ginkgo. On main its November 3 review finishes declared preparations through `documented_review_scope`. On #354 it does not: see "Ginkgo, turmeric and collagen on #354" below. `test_undeclared_preparation_stays_open` keeps undeclared rows open either way, and the read found on-target null trials (20040554, 22959217).

### Ingredients on the no qualifying route

The sentence on these labels is the existing "We reviewed the research but found no qualifying human clinical evidence of benefit applicable to this product." It says less than Sean's preparation sentence, so this list is what a change of wording would touch:

african_mango, agmatine, algae_oil, apple_cider_vinegar, atp, blood_orange_extract, broccoli_sprout, chlorophyll, coleus_forskohlii_root, diamine_oxidase, fucoidan, goldenseal, jujube, l_glutamine, l_serine, licorice, lions_mane, nopal, oat_straw, oregano, phosphatidic_acid, picrorhiza, puerarin, pygeum, red_clover, rose_hips, rosemary, tudca, turkey_rhubarb_root, turkey_tail.

### Moved between routes

- **cayenne_pepper, gotu_kola, feverfew** moved from no qualifying to conflicting, because each has a plainly on-target null trial (24267043; 28878245 and 41383475; 12230594 and 23195074). Their stored studies are back on the record.
- **theobromine** was read as no qualifying and is conflicting here, because 28971099 tested 500 mg/day alone and was null on HDL cholesterol.
- **zeaxanthin** was read as no qualifying and is conflicting here: AREDS2 was null on its primary and the one zeaxanthin-alone trial found no visual benefit. This also keeps the corrected AREDS2 rows.
- **goldenseal** was read as a rejection. A literature record already exists, so it closes through that record with no new backed entry.

### Moved out of pending on my read, for you to overrule

The reading agents parked these because a study met the design test. Each is reversible by deleting one entry from `literature_corrections.json`.

- **Null trial on target or close, so conflicting:** hawthorn (SPICE, HERB CHF), hibiscus_extract (40334927 at 1000 mg/day), nicotinamide_riboside (42478598, 42848371), cla (37671495 high quality subgroup, 21593349), aloe_vera (32314514), borage_seed_oil (14670885), alpha_linolenic_acid (20929341).
- **The only qualifying trial is a purpose or population the labels don't print, so no qualifying:** jujube, l_serine, agmatine, chlorophyll, tudca, pygeum, l_glutamine, apple_cider_vinegar, rosemary, rose_hips. lions_mane and turkey_rhubarb_root were here and went back to pending: see "Amount is not a ground" in Batch 4.

### Older pins this moved

Study rows leave a record on the no qualifying route, because the owner refuses rows there (`verify_semantic_applicability.py`). Where an October pin read such a row, `_study` in `test_literature_records_review_20261020.py` now asserts the decision names that PMID and skips the figure. Figures live on in git. Disposition pins moved with the review, and no points move: alpha_linolenic_acid, zeaxanthin, lycopene, pygeum, nicotinamide_riboside, and the batch lists in `test_evidence_resolver.py`.

### Id drift, not fixed in this PR

Labels counted from census fix2 rows on main.

| Ingredient | Ids | Labels |
|---|---|---:|
| Artichoke | `artichoke` / `globe_artichoke` | 41 / 38 |
| Butcher's broom | `butcher_s_broom` / `butchers_broom_root` | 10 / 12 |
| Olive leaf | `olive_leaf` / `olive_leaf_powder` | 80 / 2 |
| Olive | `olive_fruit` / `olive_fruit_extract` | 25 / 42 |

Three of the 4 `olive_fruit` labels read are named Olive Leaf Extract. Both ids of a pair hold their own literature record, so one review doesn't reach the other's labels.

### What would settle these

- **activated_charcoal:** the dose in 16739360, behind German full text.
- **royal_jelly:** the primary outcome in the full text of 31470366.
- **butchers_broom_root:** the mg dose in 12040966.
- **lumbrokinase:** the capsule amount in 24229674.
- **maqui_berry:** a named primary outcome in 31193920.
- **capsaicin:** a named primary outcome in 32578488.

### For Dr. Pham, batch 3 (no record written)

- **activated_charcoal:** 12516788: 75 g superactivated charcoal slurry in healthy volunteers: constipation or abdominal fullness 12/24, nausea 5/24, vomiting 2/24 versus 0 on control.
- **activated_charcoal:** 11139541: 5 g four times daily on three cycle days in 11 oral contraceptive users, 3 h after the pill and at least 12 h before the next: no ovulation.
- **activated_charcoal:** 41547464: adverse events similar across arms at 4.5 g and 7.2 g with febuxostat, 348 patients.
- **african_mango:** 23419021: adverse events in the included trials were headache and sleep difficulty.
- **african_mango:** 36364907: full text reports side effects of nausea (6 cases), constipation (1) and thirst (1), described as not severe.
- **agmatine:** 20447305: at 3.560 g/day in the open-label phase, three participants had mild-to-moderate diarrhea and mild nausea that stopped when treatment stopped. No treatment-related adverse events were noted in the randomized phase. Longest human exposure in these abstracts is 2 months (32102167).
- **aloe_vera:** 27347994: authors state limited evidence exists about the safety of aloe vera.
- **apple_cider_vinegar:** 41010525: the pooled weight result lists Abou-Khalil 2024 (38966098), retracted per 41789013; the review doesn't mention a retraction and that trial isn't in the passage naming high risk-of-bias trials.
- **apple_cider_vinegar:** 15983536: esophageal injury reported with ACV tablets; eight tablet products varied in pH, acid content and label claims, and the authors doubt ACV was in fact an ingredient.
- **apple_cider_vinegar:** 39238884: case report, acute pancreatitis in an 84-year-old possibly linked to a weight-loss supplement containing ACV. One case, causality not established.
- **apple_cider_vinegar:** 23373303: case report, erosive tooth wear in a 15-year-old from a daily glass of liquid ACV.
- **ashwagandha_root:** 41368179: this safety analysis reviewed case studies reporting liver toxicity and notes many involved supplements with both leaves and roots; read to the first 900 characters only.
- **ashwagandha_root:** 41943502: no significant changes in liver function tests in 1002 adults on 600 mg/day root extract for 8 weeks.
- **atp:** 22510240: single 5000 mg doses of oral ATP raised uric acid about 50% over placebo in 8 healthy volunteers when released in the proximal small intestine or by naso-duodenal tube; blood ATP did not rise. Far above these labels' 150 mg.
- **blood_orange_extract:** 35276783: all safety markers of liver toxicity were within the normal range over 6 months in both groups; abstract only.
- **borage_seed_oil:** 23633319: oral borage and evening primrose oil have mild, transient, mainly gastrointestinal adverse effects, and long-term use is not examined. The cited thrombosis and warfarin-bleeding reports concern evening primrose oil, not borage oil.
- **broccoli_sprout:** 39929977: gastro-intestinal side effects with broccoli sprout extract, no severe adverse events.
- **broccoli_sprout:** 30735751: beverage for 84 days in 45 women did not affect thyroid-stimulating hormone, free thyroxine, thyroglobulin or thyroid autoimmunity; the abstract notes broccoli sprout products have been suspected of thyroidal toxicity.
- **butchers_broom_root:** 12040966: of 48 adverse events across both groups, 22 were in the ruscus group and one was considered related to the study medication (unlikely); no pregnancy, bleeding, liver or interaction data in the abstract.
- **butterbur:** 31083451: Spontaneous reports of herbal induced liver injury with Petadolex. Causality for 48 cases: 3 likely, 13 possible, 8 unlikely, 24 unclassifiable or unclassified. Nine severe (ALT 3 to 153-fold, AST 2 to 104-fold ULN), average onset 103 days, dose range 50 to 225 mg/day for the mild group. Cases resolved after withdrawal, though two patients required liver transplantation. 22 reported hepatotoxic co-medications. Authors call cases rare, idiosyncratic and frequently confounded. No incidence can be read from this.
- **butterbur:** 39853578: 2025 headache review states butterbur preparations have strong evidence for efficacy and concern for hepatotoxicity, and refers readers to NCCIH.
- **butterbur:** NCCIH butterbur page (https://www.nccih.nih.gov/health/butterbur, last updated November 2024, not a PMID): AAN recommended butterbur in 2012 (22529203), then stopped in 2015 because of serious safety concerns. Raw plant contains pyrrolizidine alkaloids; only PA-free products should be considered. Rare liver injury is reported with products said to be PA-free.
- **butterbur:** 35585841: narrative review reporting on Petadolex: no relevant abnormal liver function in its RCTs, and bile duct hyperplasia in rats at 45 to 90-fold of the maximal clinical dose. Counter-evidence from authors reporting their own data; it doesn't address the spontaneous reports in its abstract.
- **butterbur:** 12864764: 2003 report concludes the extract is safe, with no numbers in the abstract. It predates 31083451.
- **butterbur:** 37394426: rats only: two oily PA-free butterbur products raised CYP2B expression above 10-fold with liver enlargement, and one powdery product had no significant effect. Shows products differ; no human finding. Possible CYP interaction question, not established in humans by this paper.
- **butterbur:** 15623680, 14752215, 17659990: mild gastrointestinal events or good tolerability only; none of these abstracts reports liver tests, so they neither support nor refute liver risk.
- **butterbur:** What I read doesn't establish causation or a rate. It also doesn't show whether the 22 non-Petadolex labels are PA-free.
- **caralluma:** 34758791: most common side effects reported were constipation, diarrhoea, nausea and rashes, reported by few studies.
- **cayenne_pepper:** 21573941: in the IBS trial, 6 red pepper patients dropped out for abdominal pain against 2 placebo dropouts, and 8 patients had pills reduced because of abdominal pain at the start.
- **cayenne_pepper:** 33291700: a single 2 g chili capsule dose in non-erosive reflux patients gave more severe abdominal burning (p<0.05) and a trend to more severe heartburn (p=0.06) than placebo.
- **citrus_bergamot:** 39682955: full text reports liver and kidney markers unchanged and the product well tolerated over 4 months.
- **citrus_bergamot:** 37732063 and 37312672 report lower GGT or liver enzymes on bergamot extract; these are efficacy readouts in their abstracts, not safety findings, and are noted here only so they aren't read as harm.
- **cla:** 42112190: EFSA panel statement says safety of Clarinol and Tonalin TG 80 was established for the proposed uses and doses for up to six months, not established beyond six months, and not established in type-2 diabetic subjects.
- **cla:** 36270407: pooled RCTs found no ALT or AST change.
- **cla:** 32560516: 3 g/day, abstract reports liver safety on 13C-methacetin breath test and enzymes.
- **cla:** 21990002: adverse events included constipation, diarrhea and soft stools.
- **cla:** 36048508: adverse-event risk ratio 1.32 (95% CI 0.94-1.84) with exercise.
- **cocoa:** 22895979: gastrointestinal complaints and distaste of the product were reported by 5% of the active cocoa group and 1% of controls.
- **coffeeberry:** 37299382: 100 mg coffeeberry increased mental fatigue and decreased sustained attention accuracy at 60 minutes; authors caution given the number of outcomes.
- **coleus_forskohlii_root:** 42847203: systematic review says adverse effects were generally mild and infrequent, and asks for long-term trials on safety.
- **coleus_forskohlii_root:** 20515580: one forskolin-treated patient had a mild asthma attack in 2 months; none on beclomethasone. Forskolin replaced an inhaled controller in this comparison.
- **d_beta_hydroxybutyrate_bhb:** 29338584: gastrointestinal symptoms in 13 of 19 participants at 0.38 g/kg twice before exercise.
- **d_beta_hydroxybutyrate_bhb:** 28750585: time-trial power about 7% lower after 0.3 g/kg ketone salts (-16 W, p = 0.029); a performance harm rather than a safety event, flagged for the wording of any claim.
- **d_ribose:** 24272966: dose-related falls in serum glucose up to 26.3 mg/dL (30.3% of baseline) in the first 60 minutes at 2.5 to 10 g, with an insulin response, in 12 healthy subjects. Relevant to anyone on glucose-lowering drugs.
- **d_ribose:** 36551203: narrative review warns of glycation capacity and predicted cytotoxicity of free ribose. Theoretical in the abstract, no clinical data given.
- **d_ribose:** 8815168: five McArdle's patients on 60 g/day reported disliking it; no harm stated in the abstract.
- **dgl_deglycyrrhizinated_licorice:** 21747893 and 39929150: the same brand is specified with glycyrrhizin at 0.5% w/w or less in the first and at 3.0% w/w or less in the second; 39929150 names glycyrrhizin as causing electrolyte imbalance, hypertension and water retention. The stored record carries only the 0.5% figure.
- **diosmin:** 33141449: phlebotonics as a class probably increase adverse events slightly compared with placebo (RR 1.14, moderate certainty); gastrointestinal most frequent; only short-term safety data.
- **diosmin:** 32348101: diosmin 600 mg added to rivaroxaban and compression over 12 months, no difference in recurrent DVT or adverse events; open-label, 90 patients.
- **english_ivy:** Labels 327886 and 212385 carry an infant tag in the label data and an 86 mg row. The trials used for the question were in adults. 12725580 covers children with asthma, with little placebo data. Whether an infant tag is acceptable on these two labels is for a clinician.
- **english_ivy:** 33523253: no serious adverse effects reported across ivy leaf studies, and the review concludes the preparations are safe for acute cough while rating risk of bias high.
- **english_ivy:** 36414647: adverse event rates comparable to placebo; no safety signals observed.
- **feverfew:** 34434419: case report of a 36-year-old on 800 mg feverfew three times daily with vaginal bleeding and altered coagulation tests, Naranjo 'probable'; the report advises caution with surgery, coagulant disorders or antithrombotics.
- **feverfew:** 22435410: review raises possible concern with long-term dosing from COX-2 inhibition in coronary disease patients.
- **feverfew:** 25892430: gastrointestinal complaints and mouth ulcers were the most common adverse events.
- **fucoidan:** 36307493: creatinine fell significantly at weeks 12 and 24 in the fucoidan group, in asthma patients on regular treatment; abstract gives no explanation. No bleeding data in the abstracts read.
- **fucoidan:** 42806726: fucoidan consistently well tolerated, no serious adverse events, across five studies; abstract doesn't address anticoagulant interaction.
- **gamma_linolenic_acid:** 21328257: adverse events GLA 20% versus placebo 3%, not statistically different (relative risk 4.24, 95% CI 0.78 to 22.99).
- **gamma_linolenic_acid:** 23633319: evening primrose and borage oil had the same mild transient adverse effects as placebo, mainly gastrointestinal per the part of the abstract read.
- **ginkgo:** 41641880: in subjective cognitive complaints, a three-month study found the risk of adverse events may be higher with ginkgo than placebo.
- **ginkgo:** 36383762: low-certainty evidence of little to no difference in bleeding or seizures (4 studies, 1154 participants).
- **ginkgo:** 22959217: stroke 65 vs 60 and other haemorrhagic or cardiovascular events did not differ between groups over 5 years.
- **globe_artichoke:** 41274796: transaminases, particularly AST, increased in the extract group of 40 bariatric candidates with obesity and steatotic liver disease; the authors note this differs from prior studies. Pooled analyses (35763310, 41270328) and 29520889 report ALT and AST falling, so these conflict.
- **glutathione:** 42683004: EFSA panel concludes S-acetyl glutathione is safe at 300 mg/day for adults, excluding pregnant and lactating women, with lower limits for adolescents; notes perchlorate in the novel food below the TDI.
- **glutathione:** 39444151: review says IV glutathione is contraindicated due to lack of efficacy and side effects, and describes minimal versus substantial adverse effects for topical versus oral.
- **glutathione:** 41897500: no significant changes in ALT, AST, ALP or creatinine after 30 days at 600 mg/day of a micellar product, single arm.
- **glutathione:** 30895708: some nonserious adverse events reported.
- **goldenseal:** 17495878: midazolam AUC 107.9 to 175.3 ng x h/ml after 14 days of goldenseal in 16 healthy volunteers; the authors warn of significant interactions with CYP3A substrates.
- **goldenseal:** 15900287: about 40% inhibition of CYP2D6 in a 28-day supplementation study of 12 healthy volunteers.
- **goldenseal:** 33174626: midazolam AUC GMR 1.43 and metformin AUC GMR 0.77 in 16 healthy volunteers; authors note possible unfavorable effects on glucose control.
- **goldenseal:** 39943692: in type 2 diabetes aggregate metformin AUC ratio 0.93, within the no-effect range, but about 20% lower at 500 to 750 mg metformin.
- **goldenseal:** 17079360: digoxin Cmax up 14% at 3210 mg daily goldenseal; no other significant digoxin parameter.
- **goldenseal:** 32683037: narrative review reports possible neurotoxic, hepatotoxic and phototoxic activities of goldenseal extract and its alkaloids.
- **goldenseal:** 21372858: NTP 2-year feed studies: clear evidence of carcinogenic activity of goldenseal root powder in male and female F344/N rats, some evidence in male B6C3F1 mice, none in female mice. Animal data, listed for the clinician; 21 of these labels print powder or plain goldenseal rows at 250 mg to 1 g.
- **guarana:** 42646867: guarana 300 mg raised mean exercise heart rate and slowed early heart rate recovery in 32 soccer players.
- **guarana:** 37898479 and 38931247: 500 mg of guarana contained 130 mg caffeine, and the labels here print up to 1000 mg with no caffeine amount.
- **guarana:** 27322597: guarana 50 mg twice daily during chemoradiotherapy: significantly worse quality of life after the second chemotherapy cycle, worse weight loss after treatment and more analgesic use than placebo; authors propose it is not beneficial for this population.
- **hawthorn:** 18490196: retrospective analysis of HERB CHF reports higher early heart failure progression on WS 1442 (3.9 times, p = 0.035; adjusted 6.4, p = 0.011) and greater risk at LVEF of 35% or less (3.2, p = 0.02); overall progression 46.6% versus 43.3%, p = 0.86.
- **hawthorn:** 19789403: significantly more adverse events on hawthorn (p = 0.02), most non-cardiac.
- **hawthorn:** 18254076: one trial reported deaths, three on active and one on control, without further detail.
- **hawthorn:** 19019730: adverse events comparable; authors call WS 1442 safe with optimal heart failure medication.
- **hawthorn:** 12817526: 8 healthy volunteers, no significant change in digoxin pharmacokinetics with WS 1442 450 mg twice daily.
- **hawthorn:** 16762125: no herb-drug interaction found in type 2 diabetes patients on medication (79 patients).
- **hibiscus_extract:** 23333908: review notes possible adverse hepatic effects at high doses and evidence of a diuretic action.
- **hibiscus_extract:** 39870328: minor, clinically insignificant AST increase; authors say long-term and therapeutic dosing safety needs careful monitoring.
- **hibiscus_extract:** 38952776 and 42011348: extract used with valsartan; blood pressure lowering alongside antihypertensive drugs, with 42011348 reporting greater kidney and lipid effects and lesser blood pressure and glucose effects than the hydrochlorothiazide control. Worth a look at the interaction lane.
- **horse_chestnut_seed:** 11747472: in the full text of the early disease trial, nausea, heartburn or fullness occurred in 4 patients (4%) on extract and 2 patients (2%) on compression.
- **horse_chestnut_seed:** 23152216: adverse events were usually mild and infrequent; the abstract gives no pregnancy, bleeding, liver or drug interaction data, and raw seed toxicity was not reviewed here.
- **l_glutamine:** 32992440: acute GI symptoms were dose-dependent at 0.9 g/kg fat-free mass, most rated mild, in 14 healthy men.
- **l_ornithine:** 40323503: safety review of 22 healthy-subject studies estimated a no observed adverse effect level of 12,000 mg/person/day as HCl; gastrointestinal disorders were the main adverse events.
- **l_ornithine:** 20717126: plasma ammonia was higher after exhausting exercise with 0.1 g/kg HCl than with placebo.
- **l_ornithine:** 8 labels print 3 g L-ornithine L-aspartate, whose trials are in cirrhosis (29762873, 38403493, 9625322): whether a label should reach people with liver disease without a physician is a clinician question.
- **l_serine:** 28527102: phase I in 20 ALS patients, 0.5 to 15 g twice daily: two withdrew for gastrointestinal side effects; three deaths, which the authors call about the expected number.
- **l_serine:** 34201370: healthy men, graded 3 to 12 g/day over 4-week periods: no treatment-related adverse events; authors set a NOAEL of 12 g/day.
- **l_serine:** 30626650: no serious adverse effects related to L-serine at 400 mg/kg/day in HSAN1.
- **larch_arabinogalactan:** 20796315: no serious adverse events reported in 72 days; mild events were listed for the placebo group and the rest of that passage wasn't read.
- **lecithin:** 12917896: the only statistically significant result was in favour of placebo for adverse events, in one trial, which the authors call likely spurious.
- **licorice:** 28660884: pooled trials of products with at least 100 mg glycyrrhizic acid daily raised systolic and diastolic blood pressure and lowered plasma potassium, renin activity and aldosterone; the abstract opens by noting case reports of severe adverse events including deaths after chronic ingestion. These labels print no glycyrrhizin content.
- **licorice:** 39519602: interventions with glycyrrhizic acid as the main component raised blood pressure; flavonoid-dominated ones had no significant effect.
- **licorice:** 29433679: licorice consumption raised diastolic blood pressure in pooled trials; the authors say hypertensive patients should avoid it.
- **linoleic_acid:** 23386268: replacing saturated fat with linoleic acid raised all-cause (HR 1.62), cardiovascular and coronary mortality in 458 men after a coronary event.
- **linoleic_acid:** 27071971: 22% higher risk of death for each 30 mg/dL cholesterol reduction in covariate adjusted Cox regression models.
- **linoleic_acid:** 21118617: n-6 specific diets, RR 1.13 (95% CI 0.84 to 1.53) for non-fatal MI plus CHD death; authors say advice to raise n-6 may increase risk of CHD and death.
- **linoleic_acid:** 33933722 and 40058591 used 15 to 20 g/d linoleic acid from safflower oil; 40058591 reports a relative systolic pressure difference favouring n-3 over n-6 (-1.81% vs 2.61%, P = 0.003). Read to the cut only.
- **lions_mane:** 32581767: four subjects dropped out of the study due to abdominal discomfort, nausea and skin rash.
- **lions_mane:** 40959699: the review lists stomach discomfort, headache and allergic reactions as potential side effects.
- **lumbrokinase:** 40933244: no significant increase in GI bleeding as pooled, OR 1.42, 95% CI 0.55 to 3.67.
- **lumbrokinase:** 27011386: no significant difference in hemostasis parameters and no hemorrhagic symptoms in 20 healthy adults on DLBS1033 490 mg three times daily for 14 days.
- **lumbrokinase:** 29093246: lumbrokinase was given together with low molecular heparin and warfarin in pulmonary embolism patients; the abstract calls this safe with no bleeding numbers in it.
- **mastic_gum:** 42885189: Chios mastic at 1500 and 2800 mg/day well tolerated over 3 months in well-controlled hypertension.
- **mastic_gum:** 30450689: fibrinogen fell and iron rose in the mastiha arm at 2.8 g/day; no bleeding or interaction data in the abstract.
- **milk_basic_protein:** 17482742: products containing MBP are labelled as containing milk because MBP has not been shown free of milk allergens.
- **nicotinamide_riboside:** 42848371: nicotinamide riboside 1000 mg/day for 52 weeks in early Parkinson disease: MDS-UPDRS worsened versus placebo, difference 2.72 points, P = .02; non-motor symptoms worse, P = .009. Serious adverse events 8.3% versus 14.1% on placebo.
- **nicotinamide_riboside:** 37994989: walking speed improved on placebo but not nicotinamide riboside at 1 g/day; the authors read the placebo change as a practice effect.
- **nopal:** 32935904: nopal fiber at 30 g per day induced more loose stools.
- **nopal:** Label itself, not a study: the label prints a California Proposition 65 warning for chemicals including lead.
- **oat_straw:** 23221935: resting blood pressure did not alter; dose and duration were well tolerated in older adults. No pregnancy, bleeding, liver or interaction data in the abstracts read.
- **olive_fruit:** 40990594: extract was added in people already treated for hypertension and lowered 24-hour systolic pressure; the abstract reports no significant adverse events. Additive effect with blood pressure medicine is worth a clinician's look; the abstract doesn't address it.
- **olive_fruit:** 39818111: well tolerated, no severe or serious adverse events over 24 weeks in a pilot of 31.
- **olive_fruit:** Canonical mapping: three products named Olive Leaf Extract sit under olive_fruit, and no label row read prints fruit. A leaf identity may belong elsewhere; I changed nothing.
- **olive_fruit:** 33868820: reports its 1000 mg/day comparison as versus placebo with -11.5 and -13.7 mmHg, the same figures 21036583 reports for olive leaf extract and captopril. The comparator in that review looks mislabeled, so read it with that in mind.
- **olive_leaf_powder:** 38287654: in the meta-analysis, fasting glycemia in studies using a low dose of olive leaf extract showed a significant result favoring the control group.
- **omega_6_fatty_acids:** 23386268: substituting linoleic acid for saturated fat raised all-cause (HR 1.62), cardiovascular and coronary mortality in 458 men after a coronary event.
- **omega_6_fatty_acids:** 21118617: n-6 specific diets, RR 1.13 (95% CI 0.84 to 1.53) for non-fatal MI plus CHD death; authors say advice to raise n-6 may increase risk of CHD and death.
- **puerarin:** 29409850: Pueraria mirifica review reports serum C-reactive protein doubled, with adverse events (mastodynia, vaginal spotting, dizziness) at similar rates across groups; one label (216948) prints P. mirifica and is positioned for women. Estrogenic botanical, worth a look at the pregnancy and hormone-sensitive lanes.
- **pygeum:** 1702916: gastrointestinal side effects in 5 patients on extract, 3 of whom stopped treatment.
- **red_clover:** 31975316: premenopausal women with ER-positive breast cancer on tamoxifen, Promensil Forte 80 mg for 24 months; endometrial thickness stayed constant, breast density fell in both groups, and serum effects on cell lines did not differ. No between-group benefit on menopausal score (p = 0.69).
- **rosemary:** 21877951: the 6,000 mg single dose significantly impaired speed of memory (P<.01), with other deleterious cognitive effects that were less consistent, in adults with mean age 75.
- **royal_jelly:** 41071287: systematic overview of bee product pharmacovigilance reports severe asthma attacks after royal jelly consumption; allergic responses were most prevalent among atopic individuals.
- **royal_jelly:** 38717683: review notes 10-hydroxy-2-decenoic acid can attach to estrogen receptors, calls data on royal jelly in cancer controversial, and says clinical studies are needed to confirm a safe dose in breast cancer; its dose findings are preclinical.
- **siberian_ginseng:** 15190050: Siberian ginseng 3 g raised 90-min and 120-min glucose and glucose AUC in an OGTT in 12 healthy people (p<0.05), relevant to glucose control.
- **siberian_ginseng:** 15207399: in 20 digitalized hypertensive older adults, no significant difference in digitalemia or blood pressure control over 8 weeks; small, not proof of no digoxin interaction.
- **siberian_ginseng:** 11798012: testosterone:cortisol ratio fell 28.7% in endurance athletes on 8 mL/day ES, with a non-significant cortisol rise.
- **siberian_ginseng:** 24683218: adjunct to lithium in 76 adolescents with bipolar disorder, nausea, rash and diarrhea reported; no placebo arm.
- **siberian_rhubarb:** 19161045: fourteen adverse events in total, 11 by 5 women on ERr 731 and 3 by 3 women on placebo; the abstract does not name them.
- **siberian_rhubarb:** 16894335: no differences in gynecological findings including endometrial biopsies, bleeding, weight, blood pressure, pulse and laboratory safety parameters.
- **theobromine:** 23420115: within-subjects study of 80 healthy participants; limited subjective effects at 250 mg, negative mood effects at higher doses (500 and 1000 mg tested), dose-dependent heart rate increase.
- **theobromine:** 20823377: theobromine-enriched cocoa (979 mg) raised 24-hour ambulatory systolic pressure by 3.2 mmHg versus placebo (P<0.01) in 42 adults; central systolic was lower at 2 hours.
- **theobromine:** 28645636: 500 mg/day raised hsCRP (1.2 mg/L, P = 0.017) and postprandial glucose, insulin and FFA in 44 adults.
- **tudca:** 8674405: diarrhea was the only side effect in 24 PBC patients at 500 to 1500 mg/day.
- **tudca:** 37842553: 7 of 86 ALS patients (8.1%) stopped TUDCA for side effects, mainly mild gastrointestinal; 2 adverse events required hospital access and resolved.
- **tudca:** 40236400: transient dyspepsia was the most common side effect in an open-label UC study.
- **turkey_rhubarb_root:** 36499011: open full text says the number of subjects complaining of diarrhea or loose stools increased significantly in the 25 mg rhein-equivalent group; abstract calls 30 days safe even at the higher dose.
- **turkey_tail:** 36445793: authors could not tell whether adverse events were due to the chemotherapy or to the extract itself; evidence on adverse events was very low certainty.
- **turkey_tail:** 36995535: most mushroom supplement studies reported adverse effects of grade 2 or lower, mainly nausea, vomiting, diarrhea and muscle pain; this review pools 12 mushroom preparations and isn't specific to Coriolus versicolor.
- **turmeric:** 32656820: acute hepatitis in 7 Tuscan cases linked to high-bioavailability, high-dose curcumin or curcuminoid formulations, with 23 published cases, most with another medication. Reaches Meriva 248670, CurcuWIN 243618 and 243134, and piperine-paired 182824 and 184133 if those formulations count as high bioavailability; that mapping is mine and not in the abstract.
- **turmeric:** 31351488: more product-linked adverse events at the high dose of bio-optimized extract than placebo (p = 0.012).
- **turmeric:** 41053771: one withdrawal for gastrointestinal side effects at 170 mg/day curcumin.
- **uva_ursi_leaf:** 34111592: pyelonephritis in 8 women on uva ursi versus 2 on fosfomycin (mean difference 2.8, 95% CI 0.2 to 5.9, p 0.067); authors conclude 'more safety concerns than fosfomycin'.
- **uva_ursi_leaf:** 30685500: no safety concerns and no upper tract infection episodes recorded, which contrasts with 34111592.
- **uva_ursi_leaf:** 12162475: healthy volunteers excreted 64.8 to 66.7% of the arbutin dose as hydroquinone equivalents in urine. Pharmacokinetic only, no efficacy; relevant to hydroquinone exposure questions held by the safety owner.
- **white_willow_bark:** 10936472: one patient suffered a severe allergic reaction, perhaps to the extract.
- **white_willow_bark:** 11345689: at 240 mg salicin/day, maximal platelet aggregation differed from placebo with arachidonic acid (p = 0.04) and ADP (p = 0.01), to a far lesser extent than acetylsalicylate; the authors ask whether this matters in patients with impaired thrombocyte function.
- **yerba_mate_leaf:** 41244043: adverse events included mucosal irritation, insomnia, tachycardia, angina, headache and gastrointestinal discomfort.
- **yerba_mate_leaf:** 34173816: an Ilex paraguariensis infusion decreased iron absorption in hereditary hemochromatosis patients, from the title only; abstract not read in full.
- **yerba_mate_leaf:** 29117073: resting plasma adrenaline rose with yerba mate (P = 0.002); these labels are multi-stimulant energy formulas.
- **zeaxanthin:** 28079755: one patient developed a reversible crystalline maculopathy on 20 mg/day zeaxanthin, resolved several months after stopping.
- **zeaxanthin:** 35653117: AREDS2 long-term follow-up; beta carotene nearly doubled lung cancer risk, with no significant increase with lutein/zeaxanthin.
- **zeaxanthin:** 24638908: no differences in adverse events by treatment group.
- **zeaxanthin:** 36247822: no serious adverse events in the glaucoma trial.

## Batch 4: the last of the 21

Agent review, abstracts only, November 4, 2026. No credit, no clinician approval. All 23 quotes and study rows were checked live against PubMed before applying.

### Closed

- **Conflicting or null:** d_beta_hydroxybutyrate_bhb (19 labels, 29451991), gamma_linolenic_acid (11, 23633319), uva_ursi_leaf (11, 30685500), linoleic_acid (6, 23386268), omega_6_fatty_acids (4, 30488422), coffeeberry (1, 37299382).
- **No qualifying study:** lignans (9, 19352068 is a methods sentence, quoted for the sesamin dose), yerba_mate_leaf (3, 41244043), coffee_fruit (1, 23312069).

The no-qualifying list across all batches is the `NO_QUALIFYING` set in `test_evidence_backed_970_20261104.py`, read from `literature_corrections.json`.

### Moved out of pending on my read, for you to overrule

The reading agent routed gamma_linolenic_acid to a packet. It closes as conflicting, the same way borage_seed_oil did: Cochrane finds oral borage and evening primrose oils lack effect on eczema (23633319), Cochrane also finds moderate evidence of some benefit in rheumatoid arthritis with no doses in the abstract (21328257), and another review says the evidence does not support their use in rheumatoid arthritis (21652584). Delete its entry from `literature_corrections.json` to reverse this.

### Stayed pending

- **green_coffee_bean (22):** all three meta-analyses favor it on some weight measure (32507437, 20871849, 31398662), though 20871849 says every trial was of poor quality. The one null trial is in obese breast cancer survivors (36134465). That isn't a conflict I can state as plainly as the others. This batch also corrects its packet, which described 31398662 as a null pooled result. It reports a significant BMI reduction, no significant overall weight change, and authors who support use.
- **milk_basic_protein (1):** four small trials at the label's 40 mg report BMD gains against one larger null trial (19296044). Full text of 17048062 and 16133638 would settle whether BMD was a declared primary outcome.
- **glutathione (35), collagen (48), turmeric (39):** agent reads kept these pending, with their packets.

### Ginkgo, turmeric and collagen on #354

These three carry `documented_review_scope`. A row that declares a reviewed preparation, such as "24% flavone glycosides" on 239062 and 213097, resolves to `resolved_by_reviewed_clinical_evidence` with reason `literature_reviewed_human_clinical_evidence` and no points.

- **On main:** that row reads `evaluated_limited_or_negative`, so 239062 is complete with Evidence 0. `test_documented_review_finishes_a_declared_preparation_at_no_credit` pins this.
- **On #354:** `_resolved_evidence_assessment` maps that reason to `not_yet_evaluated`, so 239062 is partial with blocker `evidence_assessment_incomplete`. #354 renames the pin to `test_documented_positive_review_waits_for_its_scoring_path`.

Ginkgo's stored `effect_direction` is `None`, and its text describes null prevention trials, so "positive" doesn't describe it. This is code on #354, not data, so this PR doesn't change it. No data route closes declared rows and keeps undeclared rows open: the null route would close `Ginkgo Biloba` and `Ginkgo Biloba Leaf Extract`, which `test_undeclared_preparation_stays_open` keeps open. 16 ginkgo labels stay in the pending count until this is decided.

### Amount is not a ground

Dose owns adequacy, and Evidence isn't withheld for a lower amount. A purpose or population the label doesn't print is a valid ground. I sorted all 33 no-qualifying closures by what each would rest on with the amount taken out.

- **Back to pending, trial in the packet for the credit ruling:**
  - lions_mane (21 labels). 18844328 met the standard for a printed preparation, and the closure rested mainly on 500-1000 mg against 3 g/day.
  - turkey_rhubarb_root (7 labels). 36499011 tested the root extract these labels print, and the closure rested mainly on its dose being stated in anthraquinones.
- **Stand, with the amount removed from the stated ground:**
  - On purpose or population: l_serine, agmatine, tudca, l_glutamine, apple_cider_vinegar, rose_hips, jujube.
  - On a missing primary outcome or a mixed pool: pygeum.
  - Text trimmed of amount comparisons, grounds unchanged: african_mango, blood_orange_extract, oat_straw, red_clover, nopal, yerba_mate_leaf.
- **Closest calls, for you to overrule:**
  - atp. These labels print the tested Peak ATP at 150 mg against 400 mg in the trials. It stands only because no abstract read names a primary outcome.
  - yerba_mate_leaf. Its labels carry the tested endurance and metabolic purposes. It stands for the same reason.
  - rosemary. 41312013 names a primary outcome in healthy adults. It stands because these labels show no marker content and no stress claim.

### For Dr. Pham, batch 4 (no record written)

- **uva_ursi_leaf:** 34111592 reports pyelonephritis in 8 women on uva ursi versus 2 on fosfomycin (p 0.067), and its authors conclude more safety concerns than fosfomycin. 30685500 recorded no upper tract infections. 12162475 is pharmacokinetic and bears on hydroquinone exposure.
- **d_beta_hydroxybutyrate_bhb:** 29338584 reports gastrointestinal symptoms in 13 of 19 participants at 0.38 g/kg. 28750585 reports time-trial power about 7% lower.
- **linoleic_acid, omega_6_fatty_acids:** 23386268 reports higher all-cause mortality (HR 1.62) when linoleic acid replaced saturated fat after a coronary event. 21118617 reports RR 1.13 for n-6 specific diets.
- **coffeeberry:** 37299382 reports more mental fatigue and lower sustained-attention accuracy at 100 mg, which its authors say to read with caution.
- **yerba_mate_leaf:** 41244043 lists mucosal irritation, insomnia, tachycardia, angina, headache and gastrointestinal discomfort. 29117073 reports a rise in resting plasma adrenaline, and these labels are multi-stimulant formulas. The cancer association papers 29909900, 38689010 and 29490609 were not read.
- **gamma_linolenic_acid:** 21328257 reports adverse events at 20% versus 3%, not statistically different.
- **milk_basic_protein:** 17482742 says MBP products are labelled as containing milk.
- **ginkgo:** the 41641880 abstract prints MD -0.06 with a 95% CI of -1.00 to -0.20, which doesn't contain the MD, on global clinical status in dementia.
- **lycopene:** the stored rows include a rat study (36422550) and a narrative review (27840359), and Lyc-O-Mato labels 1832, 224633 and 63244 print a tomato complex while 31035474 tested synthetic lycopene.

### Limits

- linoleic_acid and omega_6_fatty_acids close on cardiovascular outcomes. Some labels also carry joint or skin purposes, and no on-target oral trial for those was found in what was read.
- An agent reported label 78153 as carrying `neurofactor`. The census row reads `coffeeberry`, so this record does reach it. The `coffeeberry`, `coffee_fruit` and `neurofactor` ids describe nearly the same material and may be worth merging.
- 12 BHB labels show Evidence above 0 through mineral rows, 7 at 15.6 and 5 at 11.1, and 4 GLA labels show 10.4 through other rows. None of that comes from these rows, and it wasn't traced.
