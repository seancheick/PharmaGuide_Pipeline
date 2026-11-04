# Evidence review of the 74 ingredients behind 970 labels: top-5 batch

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

- **Nattokinase and clotting:** prolonged closure time and aPTT against placebo after 8 weeks (PMID 31070609); aPTT prolonged after one dose, within normal range (PMID 26109079). Worth a safety look, separate from Evidence.
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
- Not counted: how many of the 970 carry the projection row that blocks #354's sentence.
- The search for each top-5 ingredient isn't a systematic review.

## Option for lysine, not in this PR

`literature_evidence_records.json` stores lysine as `positive_weak`, while its own `applicability_decision` says the 2015 review found no evidence of efficacy. Setting `effect_direction` to `null` uses the existing no-credit path that methionine took in #340, with no clinician gate and no new record.

Probed on scratch copies, all 49 labels:

| | Main | #354 tree |
|---|---|---|
| Score, tier, Evidence or Dose moved | 0 | 0 |
| Safety status moved | 0 | 0 |
| Partial to complete | 0 (already complete) | 49 |
| Sentence | "We reviewed the human research and it did not establish a clear benefit for these ingredients." | same |

That isn't Sean's sentence, and it shouldn't be: this is a purpose lysine was studied for, and the review found no efficacy, so preparation isn't the reason. The same one-field change is available to any ingredient whose reading comes out null. The other four top-5 ingredients read mixed or weak, so it doesn't apply to them.
