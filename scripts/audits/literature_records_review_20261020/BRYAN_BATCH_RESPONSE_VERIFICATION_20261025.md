# Dr. Bryan responses — batches 1–8, independent verification

October 25, 2026. **Batch 1's supported decisions and remaining holds are approved by Sean. Batches 2–8 are reviewed below; no blanket scoring approval or rebuilt-product closure is recorded.** Attribution to Dr. Bryan comes from Sean. Receipt date is not an invented date of the original scientific review.

Owner Check: existing `clinical_review_holds.csv` and `benchmark_review_backlog.csv` are the execution reports; `clinical_applicability.py::assess_clinical_source_review` and `probiotic_measurements.py::context_accepted_for_scoring` remain runtime owners. Evidence: current owners, request sections, exact response keys and primary API/full-text sources inspected. Will NOT create another clinical authority, scorer, completion registry, grade, dose curve or approval timestamp.

This is documentation/report work only. No curated runtime clinical facts, eligibility flags, source contexts, scores or public fields changed. Frozen register fields and closure states remain intact. Source facts checked below are not automatically product-level clearances.

## Batch 1 — approval recorded; source-access gaps reduced

Sean approved accepting the narrow supported findings, preserving negative trials, preparation boundaries and unresolved holds. The request's first three priority subjects match this response. Neumentix and 299v are priority questions, not permission to approve generic A103 probiotics. B445 brewed spearmint tea remains separate from Neumentix cognition; B365 remains preparation-specific.

Eleven cited PMID records were retrieved in one live PubMed request with no cache hits. All four missing exact NIH label records and PDFs were retrieved; every PDF was visually inspected independently:

| Exact label | Verified source fact | Closed / still open |
|---|---|---|
| [232839 Focus Tea](https://api.ods.od.nih.gov/dsld/s3/pdf/232839.pdf) | Neumentix K110-42,900 mg per stick pack, aerial spearmint extract standardized to24% total phenolics and14.5% rosmarinic acid; mixed into hot water. | Identity, markers and amount per pack verified. Printed directions do not explicitly state a daily frequency. Trial capsules versus hot-water delivery, population/outcome applicability and immediate-focus claim remain distinct questions. |
| [19067 Nature Made 299v](https://api.ods.od.nih.gov/dsld/s3/pdf/19067.pdf) | Label declares 299v, 10 billion CFU per capsule, one capsule daily. | Exact strain/dose/directions disclosure verified, not laboratory potency verification. Preserve positive and negative IBS trials at matching daily exposure; no universal efficacy threshold. |
| [328014 Pepogest](https://api.ods.od.nih.gov/dsld/s3/pdf/328014.pdf) | Aerial peppermint oil 0.2 mL per softgel; explicit enteric coating; one softgel three times daily 30–60 minutes before food. | Historical-edition regimen verified:0.6 mL/day. Exact trial-product correspondence and full trial/review details remain; no mass conversion. |
| [213826 Stomach Soothe](https://api.ods.od.nih.gov/dsld/s3/pdf/213826.pdf) | Aerial peppermint oil 0.2 mL per softgel; three times daily; upset-stomach/nausea positioning. | Identity and volume regimen verified. The inspected image does not explicitly claim enteric coating. Do not infer delivery from excipients or borrow Pepogest/IBS efficacy. |

Both peppermint labels explicitly retain stop-if-heartburn and pregnancy/nursing/medication consultation instructions. Source transcription is not a new safety-policy decision.

The negative299v trial25194614 and peppermint trial34319275 were independently checked by content, not merely resolved by identifier. Their negative findings remain. The commercial Pepogest assignment for34319275 still requires verifying the underlying full-text/preparation table. No first-batch subject is falsely described as having no human literature.

## Batch 2 — appropriate boundaries, one confirmed correction

Seven PMID records retrieved in one live API request with no cache hits. Full-text API copies retrieved for 39252819, 41601871, 36558392 and 38908296. The40567408 correction body was inspected directly on official PMC; a failed additional API retrieval does not undo that successful body verification.

| Item / context | Independent disposition |
|---|---|
| A011 original sleep39252819 +40567408 | Original methods identify1 g/day preparation, about75 mg elemental magnesium, for 21 days. Table2 confirms the reported important null interactions. The correction concerns retrospective registration and commercial disclosures, not a new efficacy cohort. Retain narrow mixed findings. |
| A011 cognition41601871 | The current publisher original confirms2 g/day preparation,145 mg elemental/day, six weeks; the primary composite and subjective/ objective outcome distinctions require their stated limits. **The response's one-tailed-method statement is outdated; see correction below.** |
| A011 MagteinPS36558392 | Full-text composition confirms four capsules/day:1,600 mg Magtein,200 mg phosphatidylserine,48 mg vitaminC,320 IU vitaminD3 and16 mg vitaminB6. Whole-formula context only; no isolated-component attribution. |
| A011 products | All11 listed NIH API editions retrieved. This closes retrieval failure only; exact PDFs, compound/elemental ownership, daily directions and co-active matching are not claimed complete. The raw299037 crossed hierarchy already has an existing exact-source correction and regression; do not undo it by trusting raw API values alone. |
| A135 standalone34415830 +35917215 | Correction relationship confirmed. Corrected Table4 content remains unavailable from the prior bounded publisher attempts; do not activate a corrected efficacy benchmark or call the unresolved study negative. |
| A135 combination38908296 | Full methods confirm20 mg PQQ and80 mg elemental magnesium as daily totals, administered twice daily for six weeks. Primary between-group BDNF interaction is not significant. No standalone PQQ or universal cognitive-benefit transfer. |

### Required correction to A011-3

[Official publisher correction, October 15, 2026](https://www.frontiersin.org/journals/nutrition/articles/10.3389/fnut.2026.2010644/full), DOI10.3389/fnut.2026.2010644, says all analyses used **two-tailed tests** and the earlier one-tailed wording was erroneous. It states that reported results are unchanged. The current publisher original is amended; the independently retrieved PMC XML still contains the old wording. Preserve this source-version distinction. Do not double p-values or retain a one-tailed penalty on the basis of the stale copy. Other study limitations remain.

## Batch 3 — defensible restrictions; additional gaps independently resolved

Four PMID records retrieved in one live API request with no cache hits. Complete XML bodies retrieved for37432180,37717022 and39839727. The40324552 abstract is independently verified; its full methods and supplement are not claimed reviewed.

| Item / context | Independent disposition |
|---|---|
| A059 skin37432180 | A favorable synthesis does not establish an interchangeable preparation or universal efficacy dose. Keep preparation/co-active and bias limitations. |
| A059 skin40324552 | Abstract confirms23 trials / 1,474 participants and the funding/quality sensitivity. Accept rejection of an unqualified overall-benefit interpretation; do not claim full-text appraisal or that all products are ineffective. |
| A059 knee37717022 | Full Table1 really identifies Trč's comparator as1.5 g/day glucosamine sulfate. Text nevertheless labels the pooled contrast placebo-controlled. The post-hoc section repeats several outcomes from that same cohort. The response identifies a real issue; do not present the pooled estimate as uncontested placebo superiority or independent replications. Original-trial and forest-input reconciliation remain. |
| A059 COLLinstant39839727 | Full methods confirm10 g collagen plus80 mg calcium ascorbate per sachet; placebo lacks those nutrients. Thus the active arm is not collagen monotherapy. Methods, results, funding and registry are now accessible; see below. Whole-formula acceptance and exact product correspondence remain unfinished. |
| A148 generated collagen | Shared provenance from A059 is appropriate as an intended dependency. It does not create another trial or propagate blanket efficacy. Generated-owner behavior and all 24 named product editions remain to be verified against applicable decisions and eventual rebuilt outputs. |

### COLLinstant access gaps now have concrete answers

The [complete original paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC11745964/) reports120 randomized participants and120 completers, no reported adverse events, and funding from Nutraresearch and Viscofan. Those are the paper's reports, not independent proof of complete ascertainment or comprehensive safety. Preserve the stated calcium-ascorbate amount without inventing its vitaminC-equivalent mass.

The live [NCT05149053 registry API](https://clinicaltrials.gov/api/v2/studies/NCT05149053) matches this hydrolyzed-collagen knee-pain study. It records study startJune 1, 2020; completionMarch 12, 2021; first submissionNovember 5, 2021; first postingDecember 8, 2021. Registration is therefore retrospective. The current listed primary outcomes are six-month pain and functional limitation; these entries do not demonstrate prospective endpoint registration. A prospective trial design and prospective registration are different assertions.

### New methodological paper

The [September 28, 2026 publisher article](https://onlinelibrary.wiley.com/doi/10.1111/jocd.71208), DOI10.1111/jocd.71208, exists and directly challenges earlier skin syntheses, including Pu et al. It supplies a supporting-data/code archive. It is not a retraction, correction notice or new randomized cohort. Its technical conclusions have not been independently reproduced here; retain it for appraisal rather than treating it as proof that every collagen product is ineffective.

## Batch 4 — enhanced curcumin, with a safety-wording correction

Scope: A003 `BRAND_BCM95`, A029 `BRAND_THERACURMIN`, and the proposed turmeric safety language. The five cited PMIDs resolve by live API to the stated studies. Complete XML bodies were retrieved for 30975196, 33516238, 25308211 and 35494290 and the material methods/results were checked. For 29246725, the abstract is checked; the publisher full-paper request returned HTTP 403, so the full appraisal remains held.

| Context | Independent disposition |
|---|---|
| BCM-95/diclofenac — 30975196 | Active-comparator, open-label study; preserve the tested whole-complex regimen and comparative observations. Absence of a significant difference is not established equivalence or placebo superiority. |
| BCM-95/paracetamol — 33516238 | Methods specify 500 mg complex twice daily; results confirm 193 randomized and 144 completers. Unblinding, attrition and non-inferiority margin/supplement questions remain. Do not turn the authors' active-comparator claim into general drug equivalence. |
| Theracurmin OA — 25308211 | Methods confirm 180 mg/day curcumin delivered by six capsules in two administrations. One-sided testing and the restricted low-baseline-pain analysis need their limits; no unqualified overall pain/function superiority. |
| Theracurmin memory — 29246725 | Abstract supports a small, outcome-specific 18-month study, not dementia prevention or immediate-focus claims. Retain full-paper/supplement/registry appraisal hold. |
| Theracurmin postoperative — 35494290 | Separate surgical cohort, not memory-trial follow-up. Retain null clinical symptom results separately from selected arthroscopic surrogate findings. |

The 12 BCM-95 and 4 Theracurmin saved editions were not independently label-matched in this batch. No study regimen is converted into a universal range or interchangeable formulation-mass reference.

**Correction needed in the submitted warning:** the [TGA advisory](https://www.tga.gov.au/safety/safety-monitoring-and-information/safety-alerts/medicines-containing-turmeric-or-curcumin-risk-liver-injury) advises people with current or previous liver problems to avoid medicinal turmeric/curcumin products. The proposed consultation-only sentence softens that precaution and is not accepted as a replacement. Preserve immediate stopping and medical advice for suspected liver-injury symptoms. The advisory does not establish brand-specific comparative risk; its dietary-food distinction also remains. No runtime warning was rewritten by this report.

## Batch 5 — PrimaVie/shilajit and B433

The three cited PMIDs were independently retrieved in the same live eight-record request used for batches4/5. The hormone trial 26395129 was checked against the accessible full publisher article; the strength trial 30728074 has a retrieved complete XML body.35933897 is checked at abstract level only; its material equivalence, methods and bone-health application remain held.

| Source | Independent disposition |
|---|---|
| PrimaVie — 26395129 | Publisher methods identify the named purified material and 500 mg/day regimen;96 randomized / 75 completed. Preserve preliminary hormone-biomarker observations and attrition/commercial limitations. No demonstrated symptomatic, fertility, muscle-growth or longevity benefit follows. |
| PrimaVie — 30728074 | Results distinguish the full sample from median-split subgroups. The full-sample high-versus-low-dose contrast is not a general placebo-superiority finding; placebo-separated fatigue findings were in the stronger subgroup. No tendon-healing or recovery efficacy transfer. |
| Shilajit — 35933897 | A separate 48-week osteopenia/BMD study, not a fracture-prevention trial or automatically matched to these retail preparations. Full-paper qualification remains open. |

### Four exact B433 labels independently checked

All four live NIH API records and PDFs were retrieved. Each PDF was visually inspected on its own; the two prior access failures are resolved.

| Exact edition | Confirmed printed facts and disposition |
|---|---|
| [272454](https://api.ods.od.nih.gov/dsld/s3/pdf/272454.pdf) | Names PrimaVie and 500 mg shilajit per three-tablet daily serving, alongside other active preparations. It is a disclosed individual preparation within a multi-active product, not an inferred proprietary-blend allocation. The finished formula is not the single-material trial intervention. |
| [323708](https://api.ods.od.nih.gov/dsld/s3/pdf/323708.pdf) | Nutricost: 1,000 mg extract per two capsules/day; 20:1 and 20% fulvic-acid label claims; separate calcium 30 mg and iron 3 mg. Does not name PrimaVie. Printed third-party-testing language is not an independently inspected test report. |
| [315120](https://api.ods.od.nih.gov/dsld/s3/pdf/315120.pdf) | Double Wood: 1,000 mg shilajit extract per two-capsule daily serving, 10:1, 20% fulvic acid; no PrimaVie name. Exact edition's identity/amount/directions access question closed; no automatic PrimaVie equivalence. |
| [315696](https://api.ods.od.nih.gov/dsld/s3/pdf/315696.pdf) | Independently inspected Double Wood edition: same printed 1,000 mg/two-capsule daily serving, 10:1, 20% fulvic acid; no PrimaVie name. Verified independently rather than copied from 315120. No automatic PrimaVie equivalence. |

A separately named and quantified material can be assessed as one disclosed preparation without inventing internal constituent doses or awarding efficacy because it is patented. The response supplies a no-general-shilajit-threshold decision; no numeric curve is created. Preparation correspondence, applicable benefit and actual contaminant testing remain separate questions. No universal safe intake is inferred.

### D043–D046 source-use triage

PMID26395129 concerns shilajit, not black-seed oil, tuna oil, manuka honey or krill oil. Current IQM occurrences within those four subjects are in repeated historical audit notes that identify a shilajit/PK mismatch; they are not affirmative ingredient-specific efficacy references. Record the rejection of such transfer and preserve the history. These four citation flags are triaged; they do not create new publication holds, replacement approvals or reasons to delete the valid shilajit source. No entire ingredient or product assessment is closed by this triage.

## Batch 6 — RAW Enzyme, A063 and Mineral2O

The exact 275412 and 182990 NIH API records and PDFs were retrieved and visually checked. These access questions are resolved; they are not manufacturer nondisclosure.

- **RAW 275412:** one-capsule Facts basis; RAW enzyme group 620 mg, separate probiotic group 31 mg, total cultures 500millionCFU. The printed CFU qualification is **at time of blending**. Named cultures are Bacillus coagulans and Saccharomyces boulardii, without separate strain identifiers or organism-specific CFU allocations. Enzyme activity declarations remain activity units, not inferred enzyme masses. Directions say one capsule three times daily with meals, with gradual increase up to nine capsules/day.
- **Mineral2O 182990:** one scoop/day, about 1.8 g. Printed calcium 50 mg, magnesium 150 mg, chloride 245 mg, sodium 6 mg, potassium 50 mg and trace-mineral complex 700 mg must keep their own identities/bases. Typical constituent ranges on this exact panel are boron0.7–0.9 mg, iodine0.1–3.9 mcg, iron2.5–45.6 mcg, lithium1.0–1.2 mg, silicon5.7–12.3 mcg, vanadium0.4–2.7 mcg and zinc2.2–114.8 mcg. They are not exact batch assays. Do not substitute the45 mg-potassium brochure, collapse the matrix to elemental magnesium, add overlapping material masses, or replace ranges with midpoints.

### A063 source correction and remaining holds

The [author-uploaded original paper](https://www.researchgate.net/publication/375746407_Efficacy_of_digestive_enzyme_supplementation_in_functional_dyspepsia_A_monocentric_randomized_double-blind_placebo-controlled_clinical_trial), DOI10.1016/j.biopha.2023.115858, explicitly identifies **Poolzyme Multi**,200 mg per capsule at lunch and dinner. This resolves the prior named-preparation/timing questions; the worklist is corrected. The material is not RAW Enzymes and does not establish generic enzyme-mass equivalence.

The [documented registry API](https://www.isrctn.com/api/trial/67691215/format/who) returns registrationJune28,2023 and actual enrolmentJune16,2023. Prospective registration is not established. Paper ethics references differ between sections; the registry supplies another reference. These may describe different approval stages: clarification is required, not an allegation of absent approval. Outcome-table and seven-product applicability review remain open.

**Implementation boundary:** `backed_clinical_studies.json` still describes the preparation as unbranded in`INGR_DIGESTIVE_ENZYMES.notes/notable_studies`. That is a confirmed pending canonical-description correction, not a completed runtime repair. Keep source eligibility held; apply the correction with the combined owner/test/verification batch before the next candidate build.

### Separate reproduced engineering issue

A read-only probe of `EnhancedDSLDNormalizer.normalize_product` plus `serving_frequency.resolve_daily_serving_range` on275412 returns3–3 capsules/day, following API metadata, despite the exact label allowing gradual increase up to 9. This source/regimen discrepancy remains **open for the existing serving owner**, not for Dr.Bryan and not claimed fixed. No full pipeline or product artifacts were generated by the probe. Retain it as a pre-build engineering blocker alongside the canonical Poolzyme description correction.

## Batch 7 — biotinate, Lustriva and magnesium preparations

Live PubMed retrieval confirms34000342,40918053 and22909270, alongside37976892 from batch6. The [2019 magnesium-biotinate conference abstract](https://pmc.ncbi.nlm.nih.gov/articles/PMC6574044/) was read on official PMC: its open-label single-dose absorption findings do not establish comparative efficacy or a chronic human dose.34000342 is toxicology, not a human efficacy/safe-dose trial.

The [original Lustriva report](https://www.longdom.org/open-access/a-randomized-doubleblind-evaluation-of-a-novel-biotin-and-silicon-ingredient-complex-on-the-hair-and-skin-of-healthy-women-61185.html) identifies an exploratory combination trial and its high-dose composition. Its component-specific attribution, protocol/prespecification and exact product correspondence require the stated limits; no universal160 mg benchmark or finished-product component allocation follows.

### Exact label decisions independently checked

Twelve new API/PDF editions across batches6/7 were retrieved and visually inspected.25501 reuses the independently verified same-day API/PDF receipt from the earlier signed-response batch; its failed retrieval by the reviewer does not reopen that source fact.

| Item / edition | Verified facts and remaining boundary |
|---|---|
| C111 / 299744 | Biotin 10,000 mcg from magnesium biotinate; named Lustriva 160 mg with declared 10 mg silicon; one capsule daily with a meal. Combination identity resolved; individual compound masses/effects not inferred. |
| C170 / 336100 | Biotin 10,000 mcg from Advanced Hair Complex 160 mg, with declared 10 mg silicon and Lustriva trademark attribution; one capsule/day. Do not turn160 mg into biotin or magnesium. |
| C097 / 270235 |105 mg elemental magnesium from 1,050 mg lysinate–glycinate chelate per two-capsule daily serving. |
| C112 / 302674 |200 mg elemental from 2,000 mg lysinate–glycinate chelate per two tablets, twice daily:400 mg elemental/day. |
| C149 / 322515 | Same independently checked200 mg/two-tablet basis and twice-daily directions:400 mg/day; Albion/lysinate–glycinate identity printed. |
| C150 / 323080 |40 mg magnesium per scoop from Albion/TRAACS lysinate–glycinate in an electrolyte formula. Do not infer isolated-form efficacy or a fixed daily frequency beyond the printed directions. |
| C090 / 256962 |25 mg total magnesium from oxide **and** oxide chelate per two-tablet daily serving. Source proportions are not disclosed; the total is not unknown. |
| C013 / 25501 | Prior same-day exact source confirms200 mg elemental per two tablets twice daily:400 mg/day. Mixed glycinate/lysinate is not plain bisglycinate. |
| C042 / 203385 |200 mg magnesium from 1,112 mg **buffered magnesium bisglycinate chelate**, per three-capsule daily serving; other active ingredients remain separate. The buffer's composition/proportions are not disclosed; do not assume its identity. |
| C095 / 269689 |400 mg magnesium from 4,000 mg lysinate–glycinate chelate per two scoops (~8g). Directions start with one scoop and gradually increase to two daily:200–400 mg/day, not a fixed400 mg minimum. |
| C113 / 302675 |200 mg magnesium from 2,000 mg lysinate–glycinate chelate per one scoop (~2g), twice daily:400 mg/day. This edition is not the same scoop/direction basis as269689. |

The 2019 [magnesium bioavailability paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC6683096/) was retrieved via the full-text API. Table1 lists Doctor's Best as J for laboratory testing; human phases test A/Ultractive and O/B-magnum. It does not establish a human sixfold-absorption claim for the listed Doctor's Best editions.

The40918053 full-text API copy confirms the narrow four-week bisglycinate sleep context,250 mg elemental/day and the small primary ISI finding. It does not become lysinate–glycinate, buffered-form, anxiety or universal-dose evidence.22909270 remains a separate pregnancy/cramp context, not sleep evidence; its full-paper API attempt failed, so its full appraisal is not claimed complete.

### Safety boundaries retained

The [FDA biotin warning](https://www.fda.gov/medical-devices/in-vitro-diagnostics/biotin-interference-troponin-lab-tests-assays-subject-biotin-interference) supports the assay-interference concern, including falsely low troponin.299744 prints an eight-hour interval; that manufacturer statement is not a guarantee for every assay or patient. Do not promise a universal interruption interval.

[NIH ODS](https://ods.od.nih.gov/factsheets/Magnesium-HealthProfessional/) confirms the adult350 mg supplemental/medication magnesium UL, excluding food magnesium. The 400 mg/day regimens above exceed it; that is not automatically a toxicity diagnosis. Preserve kidney-function and medication-absorption precautions. No warning is cleared and no human safety ceiling is derived from animal toxicology.

## Batch 8 — molybdenum and vitamin unit conflicts

October 25: all nine exact NIH API records and PDFs retrieved successfully. Each live PDF is byte-identical to the saved final-completion-campaign PDF; each saved rendering was independently inspected. Retrieval and visual confirmation are separate: 27807 remains unreadable for the specific unit. Source bodies, SHA-256 hashes and the unchanged returned response are retained in `.claude/state/bryan_batch_8_20261025/`.

Owner Check: existing C-product request/report owns returned dispositions; `enhanced_normalizer.py` and `enrich_supplements_v3.py` retain label-conflict handling, and `dose_assessment.py` retains dose assessment semantics. Evidence: exact C rows and `rg label_unit_conflict scripts` inspected. Will NOT create a replacement dose, approval authority, new status or source-correction registry. This batch changes reports only, not those runtime owners.

| Item / exact edition | Independent result | Disposition and remaining action |
|---|---|---|
| C001 / [801](https://api.ods.od.nih.gov/dsld/s3/pdf/801.pdf) | Printed molybdenum 75 mg as sodium molybdate, 100% DV; two level scoops (34 g) daily. Di-arginine malate and whey protein concentrate appear in the arginine source description. | Confirm the printed conflict; no mg-to-mcg substitution or DV-derived amount. Manufacturer clarification must identify this edition/formula. Arginine preparation/component applicability remains separate. |
| C002 / [802](https://api.ods.od.nih.gov/dsld/s3/pdf/802.pdf) | Independently printed 75 mg molybdenum, 100% DV; two level scoops (34 g) daily. | Same conflict class established on its own source. No corrected exposure or whole-product clearance. |
| C023 / [31063](https://api.ods.od.nih.gov/dsld/s3/pdf/31063.pdf) | Independently printed 75 mg molybdenum, 100% DV; two level scoops (34 g) daily. Arginine source also names di-arginine malate and whey protein concentrate. | Preserve conflict and separate preparation applicability; obtain edition-specific clarification. |
| C016 / [27807](https://api.ods.od.nih.gov/dsld/s3/pdf/27807.pdf) | Live API repeats 75 mg, but the exact image remains too blurred for independent unit confirmation. | Preserve existing conflict finding and image-confirmation hold. Require a legible exact original or edition-specific clarification; another flavor cannot substitute. |
| C052 / [231334](https://api.ods.od.nih.gov/dsld/s3/pdf/231334.pdf) | Printed vitamin A 6,000 mcg DFE, 100% beta-carotene, 667% DV; two tablets daily. | Identity is disclosed; activity/quantity basis is defective. Do not substitute RAE, IU or beta-carotene mass, or reverse-engineer from DV. |
| C053 / [231335](https://api.ods.od.nih.gov/dsld/s3/pdf/231335.pdf) | Same declarations independently confirmed on this exact edition. | Require intended quantity and activity-versus-mass basis tied to this edition. |
| C093 / [263865](https://api.ods.od.nih.gov/dsld/s3/pdf/263865.pdf) | Same declarations independently confirmed on this exact edition. | Preserve unresolved activity; no automatic corrected exposure. |
| C050 / [223563](https://api.ods.od.nih.gov/dsld/s3/pdf/223563.pdf) | Exact PDF independently confirms vitamin A “900 RAE mg” from beta-carotene, 60% DV; vitamin D3 100 mg, 660% DV; two tablets daily. API represents A as 900 mg RAE. | The returned response's access gap is now resolved. Actual intended amounts remain unresolved; require manufacturer clarification, not an assumed microgram correction. |
| C051 / [223572](https://api.ods.od.nih.gov/dsld/s3/pdf/223572.pdf) | Exact PDF independently confirms vitamin A “900 RAE mg” from beta-carotene, 60% DV; vitamin D3 50 mg, 330% DV; two tablets daily. API represents A as 900 mg RAE. | Independently resolved source access, not exposure. Preserve the unit conflict and obtain this edition's intended quantity/basis. |

The proposed limitation explanations are supported: preserve what the label says while explaining that actual exposure cannot reliably be determined. None proves laboratory-measured excessive contents, establishes a benefit rejection, or completes the entire product assessment. The manufacturer clarification is an exposure-resolution dependency; it is not a request for Dr. Bryan to guess a corrected unit.

[NIH molybdenum guidance](https://ods.od.nih.gov/factsheets/Molybdenum-HealthProfessional/) lists an adult UL of 2,000 mcg/day. Conditional arithmetic is correct: the printed 75 mg equals 75,000 mcg, or 37.5 times that UL; this is not a measured product exposure. [Folate guidance](https://ods.od.nih.gov/factsheets/Folate-HealthProfessional/) defines DFE for folate, while [vitamin A guidance](https://ods.od.nih.gov/factsheets/VitaminA-HealthProfessional/) uses RAE. Do not convert the defective vitamin-A DFE declarations or apply a preformed-retinol toxicity calculation to beta-carotene. Preserve the separate high-dose supplemental beta-carotene concerns in smokers and asbestos-exposed populations; these labels do not establish their beta-carotene exposure.

[NIH vitamin D guidance](https://ods.od.nih.gov/factsheets/VitaminD-HealthProfessional/) confirms 1 mcg = 40 IU and the adult 100 mcg/day UL, including pregnancy/lactation. Literal 50/100 mg would be 50,000/100,000 mcg; this conditional comparison explains why silent correction is unacceptable. It does not confirm actual contents or a toxicity diagnosis.

**Closure:** nine returned C dispositions recorded; eight exact printed-conflict observations independently confirmed, one image-specific verification hold retained. The two previously unavailable prenatal/postnatal PDFs are now verified. Frozen findings, counts, product identities, source eligibility, approval/closure states and all runtime data remain unchanged. No manufacturer clarification, corrected dose, corpus rebuild or app verification is claimed. The two engineering blockers from batches 6/7 remain open.

## Closure and next actions

- **Recorded:** Sean's batch1 approval of supported sub-decisions, subject to the stated holds; first-batch exact-label facts above; available API/full-text source facts for batches2/3; the newer Magtein correction and retrospective COLLinstant registration.
- **Not repeated:** already completed source retrieval/correction work. None of these access gaps should be sent back as if the sources were still unobtainable.
- **Batches4/5 additions:** source/access facts above and D043–D046 triage are recorded; retain the TGA avoid precaution and all stated preparation/applicability holds. No automatic acceptance of the proposed weaker warning.
- **Batches6/7 additions:** exact-label/source facts above are checked; RAW daily-range and canonical Poolzyme description corrections remain engineering work for the combined implementation batch, not extra scientific sign-offs.
- **Still needed:** applicable trial/preparation/product decisions and authentic review provenance through existing owners; unavailable full texts/tables only where still unavailable; PQQ corrected Table4; trial overlap/forest-input reconciliation; Magtein11-product and collagen24-product correspondence; generated A148 behavior; eventual rebuilt-corpus and app verification.
- **Not done:** runtime context migration, new scoring eligibility, changed weights/grades/benchmarks, full pipeline, publication, or scientifically/rebuilt-closed status for A011/A135/A059/A148/A003/A029/B433/A063/A090.

Audit receipt hashes and exact retrieval outcomes are retained locally in `.claude/state/bryan_review_20261025/receipt.json`, with source bodies in the batch folders, with the batches 4/5 supplement in `.claude/state/bryan_batches_4_5_20261025/receipt.json`. Batches6/7 source receipts are retained in `.claude/state/bryan_batches_6_7_20261025/`. The existing hold register records receipt/verification progress without changing frozen counts, production eligibility or closure fields.
