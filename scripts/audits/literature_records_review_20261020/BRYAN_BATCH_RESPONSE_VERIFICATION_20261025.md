# Dr. Bryan responses — batches 1–5, independent verification

October 25, 2026. **Batch 1's supported decisions and remaining holds are approved by Sean. Batches 2–5 are reviewed below; no blanket scoring approval or rebuilt-product closure is recorded.** Attribution to Dr. Bryan comes from Sean. Receipt date is not an invented date of the original scientific review.

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

## Closure and next actions

- **Recorded:** Sean's batch1 approval of supported sub-decisions, subject to the stated holds; first-batch exact-label facts above; available API/full-text source facts for batches2/3; the newer Magtein correction and retrospective COLLinstant registration.
- **Not repeated:** already completed source retrieval/correction work. None of these access gaps should be sent back as if the sources were still unobtainable.
- **Batches4/5 additions:** source/access facts above and D043–D046 triage are recorded; retain the TGA avoid precaution and all stated preparation/applicability holds. No automatic acceptance of the proposed weaker warning.
- **Still needed:** applicable trial/preparation/product decisions and authentic review provenance through existing owners; unavailable full texts/tables only where still unavailable; PQQ corrected Table4; trial overlap/forest-input reconciliation; Magtein11-product and collagen24-product correspondence; generated A148 behavior; eventual rebuilt-corpus and app verification.
- **Not done:** runtime context migration, new scoring eligibility, changed weights/grades/benchmarks, full pipeline, publication, or scientifically/rebuilt-closed status for A011/A135/A059/A148/A003/A029/B433.

Audit receipt hashes and exact retrieval outcomes are retained locally in `.claude/state/bryan_review_20261025/receipt.json`, with source bodies in the batch folders, with the batches 4/5 supplement in `.claude/state/bryan_batches_4_5_20261025/receipt.json`. The existing hold register records receipt/verification progress without changing frozen counts, production eligibility or closure fields.
