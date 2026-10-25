# Independent verification of the signed A/C responses

October 25, 2026. **Source checks completed for the returned 14-product response; blanket scientific clearance and rebuilt-output closure are not established.**

Sean confirmed that Dr. Pham signed these bounded responses. That attribution is accepted as Sean's attestation. It does not expand the decisions actually written in the responses, supply missing assessments, or authorize invented approval dates. The earlier A-response report describes the attribution available at that earlier checkpoint; this report supersedes its statement that no attribution was available.

**Checkpoint scope:** this report covers the initial signed A/C reply. Later source checks and returned decisions are recorded in the [current batches1–7 verification](BRYAN_BATCH_RESPONSE_VERIFICATION_20261025.md); its resolved access/timing findings supersede earlier open retrieval questions here. Frozen original denominators remain unchanged.

## What was independently verified

- All **14 returned C labels** retrieved successfully from the live NIH DSLD API, with their **14 exact label PDFs** downloaded and visually inspected. The API and label images were compared individually; similar flavor editions were not treated as interchangeable.
- **Seven PubMed identifiers** retrieved in one live request, with no cache hits: 40567408, 39252819, 22909270, 40918053, 37976892, 35917215 and 34415830. The correction links 40567408 → 39252819 and 35917215 → 34415830 were verified. A valid correction link does not establish the contents of a corrected numerical table.
- The previous verified Magtein correction-body and historical magnesium-source findings were retained. The new A response explicitly acknowledges those corrections and explicitly does **not** finish the remaining A assessments.
- The unsupported 2020–2026-only restriction is withdrawn. It is not adopted as an inclusion policy.

[API/PDF hashes, retrieval date and PubMed request receipt](signed_source_receipts_20261025.json). Public primary-source URLs are included below and in the receipt. Original responses and exact downloaded source bodies are retained locally with checksums; private attachment links and API credentials are not published.

## Individual product dispositions

“Verified” below means the stated source facts were checked. It does not mean every assessment dimension is complete.

| Returned item / label | Independently established | Disposition |
|---|---|---|
| C001 / [801](https://api.ods.od.nih.gov/dsld/s3/pdf/801.pdf) | Molybdenum is printed as 75 mg and 100% Daily Value, a real conflict. Arginine total is disclosed without a component split. | Retain source-quantity hold; do not silently change mg to mcg. |
| C002 / [802](https://api.ods.od.nih.gov/dsld/s3/pdf/802.pdf) | Same molybdenum unit/Daily Value conflict on its own label. | Retain hold; no inferred replacement amount. |
| C003 / [855](https://api.ods.od.nih.gov/dsld/s3/pdf/855.pdf) | Label and API disclose 60% carvacrol, 3.2 mg. The response's “standardization unavailable” is incorrect. The 60 mg blend includes olive oil and oregano oil. | Check off marker disclosure; oregano-oil amount remains undisclosed. Do not derive an oil amount from the percentage. |
| C004 / [8958](https://api.ods.od.nih.gov/dsld/s3/pdf/8958.pdf) | Printed d-alpha tocopherol; front says natural. API active-row forms omit it, but API other-ingredient text also identifies d-alpha. 800 IU per softgel, 1–2 daily. | Repair exact-source form through existing correction owner. Natural conversion gives 536–1,072 mg/day; retain the real upper-limit warning. |
| C005 / [12144](https://api.ods.od.nih.gov/dsld/s3/pdf/12144.pdf) | Glucosamine HCl 1,500 mg; a 290 mg chondroitin/white-willow complex; hyaluronic acid 10 mg per two softgels. | Preserve mixed preparation and undisclosed component amounts. No component-dose or form-grade invention. |
| C006 / [12300](https://api.ods.od.nih.gov/dsld/s3/pdf/12300.pdf) | 860 mg whole blend per two capsules, taken twice daily: 1,720 mg/day whole blend. | Whole-blend regimen verified; individual herb quantities remain undisclosed. |
| C011 / [18538](https://api.ods.od.nih.gov/dsld/s3/pdf/18538.pdf) | Front and API explicitly disclose 3 g micronized arginine. Creatine matrix includes other constituents. | Check off arginine disclosure; do not infer creatine quantity by subtraction. |
| C012 / [19598](https://api.ods.od.nih.gov/dsld/s3/pdf/19598.pdf) | Trisynex is a subrecord of a Physio-Burn bundle with multiple Facts panels. | Do not equate the silver-capsule subrecord with the complete pack, infer pack mapping, or import a named preparation not printed on this source. |
| C013 / [25501](https://api.ods.od.nih.gov/dsld/s3/pdf/25501.pdf) | Two tablets contain 200 mg elemental magnesium from 2,000 mg glycinate/lysinate chelate; twice daily gives 400 mg elemental/day. | Elemental basis verified; mixed-chelate qualification remains separate. Do not call it pure bisglycinate or invent ligand doses. |
| C015 / [27203](https://api.ods.od.nih.gov/dsld/s3/pdf/27203.pdf) | Silica 1 mg from silicon hydrolyzed vegetable protein. | Preserve exact identity; no unsupported elemental conversion. |
| C016 / [27807](https://api.ods.od.nih.gov/dsld/s3/pdf/27807.pdf) | API repeats 75 mg molybdenum; available exact image remains too blurred for independent unit confirmation. | Explicitly retain source-confirmation hold. Repeated API data is not independent image confirmation. |
| C017 / [27808](https://api.ods.od.nih.gov/dsld/s3/pdf/27808.pdf) | Lemon Tea prints arginine 500/1,000 mg at one/two scoops; API first column says 100. Guarana caffeine is 50/100 mg; API child names say 150/300 and the second value says 300. | Correct this exact edition only. Reconcile alternative serving columns; total caffeine becomes 200–400 mg/day, not the erroneous 700. Other identity/evidence holds remain. |
| C018 / [28963](https://api.ods.od.nih.gov/dsld/s3/pdf/28963.pdf) | Organic freeze-dried banana powder, 100 mg per quarter teaspoon. | Food-powder identity verified; no applicable form grade established. Do not borrow a flavor/color catch-all or an extract grade. |
| C019 / [28993](https://api.ods.od.nih.gov/dsld/s3/pdf/28993.pdf) | Fruit Blast really prints guarana caffeine 150/300 mg. Its four component annotations total 300 mg/scoop while the printed total says 200 mg/scoop. | Genuine label conflict. Preserve all printed numbers, qualify exposure as unresolved, and block completed dose assessment. Never borrow Lemon Tea's 50/100 mg correction. |

The natural vitamin E conversion and adult 1,000 mg supplemental upper limit were checked against the [NIH ODS vitamin E reference](https://ods.od.nih.gov/factsheets/VitaminE-HealthProfessional/). A quality score is not a recommendation to use that regimen.

## Implementation and closure evidence

Owner Check:

- Owner: `enhanced_normalizer.py::_apply_label_corrections` — exact source/path/forms/quantity fences and the existing curated correction file. The unresolved qualifier extends the existing quantity operator; it creates no new public field or assessment authority.
- Owner: `enhanced_normalizer.py::_merge_alternate_serving_rows` — amount-prefixed leaf names were preventing alternative columns from merging. Merge only sibling leaves whose names agree with their own quantities and ingredient group, with matching category/UNII/unit and distinct complete serving contexts. Cross-carrier matching is unchanged.
- Owner: `serving_frequency.py::resolve_facts_panel_serving_basis` — preserve an explicit same-audience one-to-two-scoop range when both exact bases are present in the same source column. Pediatric/adult, AM/PM and incomplete-context controls remain.
- Owner: `assessment_readiness.py::_dose_readiness`, reusing `scoring_v4.exposure::quantity_is_unresolved` — an existing completed typed assessment cannot waive a conflicting source quantity.
- Evidence: ownership matrix/glossary and callers inspected; exact API/PDF comparison, fail-first tests and raw-label replay. Will NOT create another scorer, registry, matcher, clinical authority, score weight or fabricated benchmark.

Implemented source entries: 8958, 27808 and 28993. Fail-first coverage reproduced the natural-form and arginine defects, alternative-column double counting, discarded minimum regimen, incorrect exact exposure and a readiness waiver. Source-snapshot mismatch, different editions, conflicting forms/UNIIs, independent carriers and audience/panel controls protect the repairs.

The frozen 19-label diagnostic contains the 14 returned labels plus five retained controls. It is **not** a full pipeline or corpus rebuild. The initial comparison changes source/enriched/blob records for only 8958, 27808 and 28993. Three existing molybdenum holds (801, 802, 27807) receive a clearer readiness reason; their amounts, safety and not-scored status remain unchanged. The other thirteen records remain identical. No clinical record was newly approved and no discretionary Evidence grade was invented; the vitamin E assessment uses the existing nutrition-authority policy. Natural vitamin E changes from not-scored to 84.1 with a real caution; both pre-workouts remain not-scored. Fruit Blast retains caution and gains an explicit unresolved dose hold. Lemon Tea's false general caffeine-excess caution disappears at the verified maximum 400 mg; its existing profile-specific interaction rules remain present.

Verification so far: 262 owner/source/readiness tests passed; 230 serving/safety/consumer tests passed; the final six range/source controls passed. These are named slices, with overlapping coverage, not an asserted unique total. The final 19-label replay completes without errors and its stage hashes match the earlier measured candidate after the stronger audience/order guards. Data-batch validation reports exactly three changed entries and zero problems. Bounded independent technical review found no concrete blocker. Local validation passed **546 tests / 24 declared optional skips** in137.81seconds. [Whole-fast CI40210617064](https://github.com/seancheick/PharmaGuide_Pipeline/actions/runs/40210617064) passed on source candidate `129e291c85437c6a36e48eb7b917e95e1d79d568`: **23,868 passed / 192 declared skips**, all four groups and skip guards green. The final follow-up changes only documentation/receipts; all443 runtime/data source hashes still match the qualified candidate. A passing diagnostic or source fix is **implemented and bounded-verified**, not rebuilt-closed.

## One remaining-work list

1. **A assessments:** 147 curated records plus generated collagen still need complete source-specific applicability decisions where missing: preparation/delivery, dose/regimen, population, outcome, limitations and exact product correspondence. The returned acknowledgment supplies no blanket scoring acceptance. Record actual acceptance/rejection only for completed scopes; retain required approval holds.
2. **B benchmarks:** the existing 506-subject register remains open. Source identity and known label limitations can be checked off individually; neither creates an evidence-based dose curve or form grade. Negative/inapplicable findings are valid resolutions when supported and recorded.
3. **C products:** 14 of the original 171 have returned decisions and independent source checks in this report; **157 have no returned decision**. The 14 still have the specific unresolved items listed above, including source contradictions and preparation qualifications. This is not 14 complete product clearances.
4. **PQQ:** PubMed confirms the correction relationship, but corrected Table 4 remains unread. Both publisher full-text/PDF requests returned 403; the connected literature API refused access for this account. This is a residual content-verification limitation, not a pass. Obtain the actual corrected table before clearing its numerical assessment. A063 capsule timing was subsequently resolved from the original methods (lunch and dinner); its remaining qualification and implementation items are recorded in the [current batches1–7 report](BRYAN_BATCH_RESPONSE_VERIFICATION_20261025.md).
5. **Final verification:** after the remaining output-changing decisions are integrated, choose the earliest required stage from actual fingerprints, run the single authorized rebuild, verify every published assessment and the original app examples, and close only the backlog items demonstrated in those rebuilt outputs. **Do not run that final rebuild or publish on the strength of this report.**

No full pipeline, app import, release or product publication was performed in this batch. No clinical sign-off, evidence grade, component amount or benchmark was manufactured to close a row.
