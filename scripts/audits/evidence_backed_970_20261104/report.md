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
