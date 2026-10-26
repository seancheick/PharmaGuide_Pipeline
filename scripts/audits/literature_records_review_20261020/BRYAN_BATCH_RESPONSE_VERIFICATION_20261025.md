# Dr. Bryan responses — batches 1–9, independent verification

**Current status, October26:** the remaining18C/47D source-correction batch is implemented, verified and merged. [Final qualification](#final-qualification-and-integration--october-26-2026) records exact CI/integration. The active [remaining list](#one-remaining-list-before-final-delivery) separates required scientific decisions from rebuilt-corpus/app verification. Earlier pending-source lists below are historical and superseded. No publication or full corpus run occurred.

October 25, 2026. **Batch 1's supported decisions and remaining holds are approved by Sean. Batches 2–9 are reviewed below; no blanket scoring approval or rebuilt-product closure is recorded.** Attribution to Dr. Bryan comes from Sean. Receipt date is not an invented date of the original scientific review.

Owner Check: existing `clinical_review_holds.csv` and `benchmark_review_backlog.csv` are the execution reports; `clinical_applicability.py::assess_clinical_source_review` and `probiotic_measurements.py::context_accepted_for_scoring` remain runtime owners. Evidence: current owners, request sections, exact response keys and primary API/full-text sources inspected. Will NOT create another clinical authority, scorer, completion registry, grade, dose curve or approval timestamp.

The original review sections were documentation/report work only. Later runtime implementation checkpoints are identified separately below; source dispositions alone do not establish rebuilt closure. Frozen register fields and closure states remain intact. Source facts checked below are not automatically product-level clearances.


## October 26 returned-source access closeout

The engineering checkpoint remains closed. A bounded reconciliation recovered two specifically reported source-access dependencies; it does not approve the other A/B/C/D decisions or regenerate products.

| Item | Independently established | Remaining boundary |
|---|---|---|
| D011 / STRAIN_LACTIS_HN019 | The [April 15 author response](https://jamanetwork.com/journals/jamanetworkopen/fullarticle/2831509) is readable, separately from correction PMID40327349. Its access gap is closed. The canonical context now records the methodological qualifications rather than saying the comment is unavailable. | Protocol/supplement appraisal and exact combination applicability remain separate; no individual-strain inference or new approval. |
| D139 / BANNED_ADD_SYNTHETIC_ESTROGENS | The [official 150-page statement](https://endocrinenews.endocrine.org/wp-content/uploads/EDC-2-Scientific-Statement-2.pdf) is retrieved. Page E8 specifically discusses prenatal DES exposure and subsequent human outcomes; this is relevant context, not a wrong-topic citation merely because the title omits the ingredient. | Selected-section inspection, not full scientific closure. Do not generalize DES findings to every alias/exposure, or use this scientific statement as a legal-status authority. Existing warning remains unchanged. |

Owner: existing strain context limitations and existing review report/request. Evidence: live primary sources above, source hashes in `.claude/state/review_dependency_closeout_20261026/`, fail-first HN019 regression. Will NOT create another authority, approval, grade, benchmark or registry.

The missing return was recovered after Sean supplied its exact Library link: **PharmaGuide evidence review — expanded Batch 12**, reported version 4, updated October 25. Original Markdown downloaded through the authenticated Library to `Downloads/evidence_review_marked.md`; unchanged retained copy and parsed inventory are in the private closeout receipt directory. SHA256: `e88d3a6ac687d2b82d7095b98b74bacd193898063f3aa39ea38a42ffea6422fb`. Independently enumerated the original worksheet sections: 171 unique C001–C171 rows and 146 unique D001–D146 rows, all 317 response cells populated, no missing/duplicate IDs. This closes the missing-document dependency. The reviewer explicitly identifies the work as ChatGPT-assisted source research/arithmetic, not expanded clinical acceptance. Individual source dispositions have now been compared to current canonical owners; 317 populated cells do not establish 317 implemented or rebuilt-closed assessments. The earlier `evidence_review.pdf` remains the original unanswered request. The historical missing-file statements below are superseded.

### Recovered return: current-owner comparison

All 171 C-label responses were read against the current retained raw records and correction owner. The private per-ID receipt retains each response, exact raw path/hash, current correction fields, source URLs and next action. Disjoint accounting: 38 existing exact-product corrections/containments, 17 prior shared-owner or source dispositions, 98 documented label/applicability limitations, and **18 remaining source-difference or owner-probe cases**. Three of those 18 also have an earlier correction for a different issue; 41 current correction entries therefore occur across the whole sample. None of these counts is a rebuilt-completion count.

Remaining C IDs: C014, C020, C021, C024, C026, C027, C032, C033, C034, C040, C079, C091, C094, C116, C143, C147, C167, C168. Shared work: daily-frequency disclosure, plant-part/preparation text, mixed grape skin/seed representation, EAA hierarchy, literal chemical naming, two barcode records and a zero-sodium unit. Twenty bounded Clean probes and two selected Enrich probes establish current owner behavior; newly reported image discrepancies still need independent exact-image verification before edits. In particular, C168/330882 retains a mixed skin/seed row while its public-form representation selects seed; no positive grade on that mixed row was demonstrated. Do not call the older shared repair closure of this exact case.

The D response comparison covers all 146 rows. Disjoint accounting: 97 existing containments/narrow contexts retained; one implemented access-note correction (D011); one source-access closure with separate appraisal (D139); eight IQM source/endpoint items; 19 standardized-preparation source/rationale items; 17 safety-source corrections or reference clarifications; and three policy/applicability decisions. The last four groups total 47 action items, not 47 independent literature reviews or approvals. The private `d_reconciliation.json` preserves every returned response and its disposition. In detail: D001–D010 retain existing exclusions; D011 has the source-access correction above; D012 retains its intentional historical rejection and D013 remains an identity crosswalk, not isolated-strain efficacy. The middle 112 rows and final 21 safety rows were compared individually against current owners. Already corrected Niagen, devil's-claw and SunActive attribution must not be reopened merely because the return describes an older baseline.

| Remaining source work | Existing owner and boundary |
|---|---|
| D017, D020, D031, D035, D057, D062–D064 | IQM source/endpoint wording: intestinal disappearance versus systemic absorption; tested ketone preparation; isolated resveratrol versus red-wine extract; fenugreek preparation versus isolated diosgenin; ALA tracer versus whole oil; source metadata; Caco-2 versus human cascara absorption; rat platelets versus case report. Unsupported numerical absorption values require a separate measured behavioral correction, not replacement estimates. |
| D092, D105–D118, D120–D123 | Existing standardized-botanical source lists still contain inconsistent attributions. Explicitly retain rejected provenance, source type and preparation limits. D114 also has unsupported affirmative rationale. Existing hold/eligibility ownership remains separate. |
| D124–D138, D143–D144 | Existing additive/banned-record source metadata and explanations need scope corrections: mixture versus isolated dye, animal versus human study, compound versus class, bioaccessibility versus absorption, and multi-brand/multi-compound outbreak attribution. Some rows need only a narrow reference clarification. These are proposed corrections pending primary-source inspection and targeted validation, not changed safety policy. Preserve risk-matched warnings and do not silently change clinical-risk tags. |
| D099, D145, D146 | FloraGLO award threshold, omega-3/niacin dose/ingredient eligibility and knotweed marker threshold are not established by the returned source. Resolve through existing policy/applicability owners; no invented cutoff or replacement dose. |

D135's full review is accessible at https://pmc.ncbi.nlm.nih.gov/articles/PMC10922848/ according to the independently gathered receipt. Its source-class estimates concern bioaccessibility, not measured sodium-hexametaphosphate absorption; source access alone cannot close compound-specific applicability. Required warning and numerical changes must be verified at the canonical owner before implementation is claimed.

This comparison closes the missing-document and per-ID inventory gaps. It does not close the remaining source corrections, A/B applicability decisions, benchmark policy, rebuilt assessments or app delivery. The full returned file remains private; the digest and scoped accounting preserve reproducibility without publishing the entire supplied document.

## October 26 reconciliation against the completed corpus

The operator's scored corpus at `bbaf3a7d` contains 15,437 products; 10,509 have at least one release-completeness blocker and 4,928 pass. This is a frozen observed result, not a claim that the current source candidate has been rebuilt. The source-attribution correction and later source-note correction below retain their genuine holds.

Owner: `clinical_applicability.py::assess_clinical_source_review` and the existing clinical/benchmark CSV registers — evidence: every current contributing dependency joined to canonical `reviewed_entries`, all 155 register rows checked, every 3,238 botanical-blocked product traced through the existing botanical/purpose owner. Will NOT create: another review authority, blanket approval, new clinical registry or replacement benchmark.

### Counts describe different units

| Unit | Reconciled finding |
|---|---|
| Returned A items | 148 individually enumerated in the original response: 147 curated records plus generated collagen. The response expressly leaves source/preparation assessments incomplete; the follow-up withdraws age-only exclusions. |
| Existing clinical register | 155 rows: the 147 A-linked records plus eight additional historical records. Frozen IDs/counts remain unchanged. |
| Current contributing-source IDs | 147 raw IDs, collapsing to 146 canonical records after the generated collagen pointer resolves to INGR_COLLAGEN_PEPTIDES. These affect 5,972 distinct products, with overlap between records. |
| Register rows outside that blocker set | Nine: INGR_BENFOTIAMINE, INGR_BIFIDOBACTERIUM_BIFIDUM, INGR_GLYCINE, INGR_MOLYBDENUM, INGR_PROPOLIS, INGR_SAME, INGR_SLIPPERY_ELM, INGR_VITAMIN_E and PRECLIN_BETAINE_HCL. Their historical review rows alone do not create a publication blocker. Other product-level gates remain independent. |
| Botanical benchmark groups | All 3,238 affected products map to 374 canonical subject groups: 366 already in the frozen 506-row backlog and eight newly observed subjects. The 140 remaining frozen subjects have no current botanical benchmark block. Each group's exact preparations still matter; these are not 374 independent literature reviews. |
| Additional material-evidence work | The existing readiness rows identify 463 canonical subjects across 3,515 products with at least one not-yet-evaluated ingredient; this overlaps the other blocker families and is not added to their totals. |
| C-label / D-citation responses | The latest returned summary (`f32df139-89c6-41d8-b910-1cb4811949fa`) reports all 171 C and 146 D cells populated and describes remaining limitations. That earlier missing-document state is superseded by the recovered Markdown and independent 171/146 inventory above; populated responses are not completed assessments. Source dispositions do not by themselves close the A/B applicability work. |

The eight current-only botanical subjects are american_ginseng, cinnamon, gentian, green_bell_pepper, green_cabbage, joint_comfort_proprietary_blend, nha_cranberry_extract and raspberry_unspecified. They are appended to the existing benchmark register with frozen count zero; no historical row or count was replaced.

### What was actually supplied, and what was not applied

The 147 linked A rows now acknowledge Sean's attestation that Dr. Pham signed the bounded responses. Older cells saying attribution was absent were stale. This correction recognizes the supplied signature without expanding its scope or inventing its date. Later Bryan responses are linked separately for the eight affected existing records, with source-access questions already resolved removed from their current action text.

Every current canonical clinical record lacks `study_contexts`: 210/210 at historical `e7e1c4a`, failure baseline `bbaf3a7d`, and the inspected current source. Thus this structure gap predates the latest enhancement. It does not prove that no human review happened. The original A response and follow-up explicitly retain substantive preparation/regimen/outcome gaps; the richer later batches close some facts but also name particular residual questions. The CSV now carries each returned row's original disposition, exact remaining question, response provenance, and current affected product IDs. Age-only restrictions are marked withdrawn. A146/A147 block-retrieval omissions are marked already recovered.

The approval validator `probiotic_measurements.py::clinical_review_provenance_valid` requires an attributable reviewer, an actual timezone-qualified review timestamp and scope `identity_dose_outcome_applicability`. That is an existing runtime requirement. A receipt/download time cannot substitute for the original approval time. More importantly, a signature on a response that expressly leaves a source question unanswered cannot fill that substantive field. Requests must name the missing scope or provenance; do not request a blanket repeat of already signed work.

### Confirmed unapplied Magtein source facts corrected

`BRAND_MAGTEIN` still called correction PMID40567408 unverified even though its full official body had already been inspected. The source note also omitted the vitamin B6 co-active in the MagteinPS methods. Live PubMed confirmed all three identifiers (36558392,39252819,40567408), and official PMC bodies were rechecked on October26. The existing record and reference notes now reflect the available correction and full-formula identity. Clinical applicability, numerical grades and holds remain unchanged. Sources: [correction](https://pmc.ncbi.nlm.nih.gov/articles/PMC12190206/), [formula methods](https://pmc.ncbi.nlm.nih.gov/articles/PMC9786204/).

The owner regression failed first, then passed. `test_clinical_source_integrity_eligibility.py` plus `test_clinical_applicability.py`: 290 passed. `data_batch.py check ... --since HEAD --expect backed_clinical_studies/BRAND_MAGTEIN` reported one expected changed record and no unexpected entries. Citation-diff tools selected zero new identifiers/rules; that result is not represented as source verification. The independent live API/full-body checks above supply the source evidence. Fourteen real enriched-product Score replays (all eleven current Magtein contributors plus three controls) preserve every compared score, pillar, status, safety field and readiness result. No corpus run, export or app delivery is claimed.

### Structured-context migration boundary

A controlled synthetic probe demonstrates that `assess_clinical_source_review` currently validates supplied contexts without establishing coverage of every source listed on the record: one approved synthetic context plus a second unrepresented reference still returns complete. This is a coverage question, not evidence that every historical reference contributes. A single partial real context was therefore not inserted as though it represented a whole multi-source record. Before migration, establish the actual contributing-source set and cover its required decisions through the existing owner; exclude correction notices and unused references for their documented reasons. Do not introduce a universal all-historical-citations approval rule.

The narrower source-attribution defect is now fixed at `assess_clinical_source_review`: every supplied context source must belong to the canonical record, and at least one must remain eligible under the existing `clinical_record_sources_eligible` owner. An excluded correction notice may accompany an eligible trial as provenance but cannot supply affirmative support alone. Malformed reference containers fail closed with a recorded error rather than crashing or silently discarding data. Seven attribution cases and ten malformed-container cases failed before their fixes; the twenty-case regression/control slice passes. The earlier 443-case owner/consumer slice passed before the container hardening. All 210 real canonical records retain the exact missing-context result, so no assessment is newly cleared. Complete contributing-reference coverage remains the separate migration boundary above; this fix does not invent that mapping.

### Evidence and remaining closure

Private evidence retained in `.claude/state/rebuilt_assessment_audit_20261026/`: `dependency_reconciliation.json` attributes all 3,238 botanical cases and material-evidence subjects; `findings.json` retains all blocked IDs; `contributing_source_groups.csv` retains the contributing-record join; `magtein_live_pubmed.xml` (SHA256 `669fff299b01ddbb011b5369c8390ffd52000d9f3d1de3f7d47f93ccc5046166`), frozen Magtein replay inputs and before/after summaries, and `context_coverage_probe.json`. All original 155 clinical and 506 benchmark frozen IDs/counts were compared to HEAD and are unchanged.

This reconciliation closes the known attribution-metadata error and the unapplied Magtein facts. It does not close all scientific assessments. Remaining work is precisely scoped in the existing registers: complete source-specific applicability decisions where the responses retain questions, apply the remaining supported decisions from the recovered C/D cells without requesting duplicate reviews, verify necessary multi-source coverage, and select regeneration from the final fingerprints. Full-corpus/export/native-app proof remains the integration owner's responsibility.

## Batch 11 source corrections and later-report intake — October 25

**Implemented, bounded-verified and integrated; scientific and rebuilt closure remain separate.** Baseline `585d19f7ff50bf54a94eeb9d95996c6bfe74235a`; isolated branch `codex/batch11-source-corrections`. The new summary attachment is an intake report, not proof that all its later findings exist in current runtime or that the full171C/146D review is closed. It is pinned to older `ebc792e8`; previously integrated batches must not be counted as newly unfixed.

Owner: `enhanced_normalizer.py::_apply_label_corrections/_process_serving_sizes`, existing product-label corrections, IQM absorption fields, and canonical clinical/botanical registries — evidence: exact source image/API receipts, ten source-content bindings, named regressions and18 frozen raw Clean→Enrich→Score→blob replays. Will NOT create another normalizer, registry, scorer, approval, public field or clinical policy.

| Exact source / record | Implemented disposition |
|---|---|
|270233 NADH|20mg reduced NADH disodium-salt source replaces erroneous2mg/disodium-phosphate transcription; no invented identifier or ENADA equivalence.|
|62816 iodine|Image-bound25mcg correction with25–50mcg/day preserved. Baseline already numerically corrected by existing generic owner; this is explicit source provenance.|
|231826 InSea2|125mg belongs to named preparation; heading remains unquantified. No invented species/polyphenol allocation.|
|315691 potassium iodide|130mg compound per two tablets; preserve emergency/age/duration/consultation restrictions, no nutritional benchmark.|
|252842/254473/254474/254475 citrate|1/3tbsp annotation,3g and600mg elemental sodium unchanged.|
|269689 magnesium|Two-scoop Facts basis,0.5–1 Facts servings/day yields200–400mg/day. Fractional daily counts survive cleaning.|
|287389 Virtiva|Restore literal ginkgo-leaf/sunflower-phospholipid composition. Original BRT6 V2 prints5%ginkgoflavonglucosides and12%PS: nominal6mg/14.4mg within120mg complex. Latest summary's6% is rejected. No component allocation or preparation approval; remains not_scored.|
|Niagen/unspecified NR, three devil's-claw forms|Remove unsupported human absolute absorption percentages/ranges using existing unknown/null convention; preserve all bio_score values. Correct Trammell attribution to27721479 and qualify Loew11372004 marker PK. EMA report supports traditional use, not claimed well-established efficacy.|
|Theracurmin|46randomized/40analyzed body distinction; no new enrollment aggregate, grade or approval. Main-paper access resolved, remaining appraisal/product correspondence held.|
|SunActive|Bare wrong-topic19674817 explicitly marked rejected provenance; bonus remains excluded.|

Fail-first evidence: original source nodes8failed/2passed; fractional count failed separately; later Virtiva composition failed; seven IQM regressions failed before the corresponding changes. Final named owner/data slice352passed; additional magnesium safety-ceiling assertion passes. A self-review also reproduced and fixed non-finite daily-count leakage introduced by the fractional helper (two failing cases before repair); final32-node defect file passes. All10label,2IQM,1clinical and1botanical entry sets pass `data_batch.py check` without extra changes.

Live changed-entry verifier:27721479/11372004 match;19674817 still correctly mismatches SunActive. Existing unchanged citation backlog identifies that rejected reference. Baseline-aware result:0new mismatches/0unresolved,1known mismatch. This is not approval of SunActive efficacy or a claim that every citation in the corpus passes.

Eighteen frozen raw replays: NADH270233 becomes scored76.1 after its false identity limitation resolves. Three initial controls188790/25501/66513 unchanged; all six later scored artifacts are semantically identical (Niagen182475/182477, devil's-claw213485/251548/210639, Virtiva287389). No product safety-status change or observed lost clinical warning. Magnesium269689 changes minimum dose400→200mg, minimum UL exceedance becomes false, and dose treatment becomes deduction2 instead of cap10; maximum400mg, over-UL flag and caution remain. NADH exposure2→20mg is an intentional source correction. These changes must not be summarized as every safety-related field unchanged.

Independent fresh-context read-only review found no production defect and requested the added magnesium ceiling/caution assertions. Local passes546/24declared opt-in skips (skip guard green). First isolated local attempt failed missing-artifact skip guard; existing preserved paths were exposed,100affected checks passed, then the combined local checkpoint passed. CI40228636370 failed two historical numerical expectations (B32/B34), reproduced as2failures; exact reviewed-unknown expectations were corrected without changing runtime data back to fabricated fractions.79affected tests pass. Replacement whole-fast CI and integration remain pending; no full corpus, app import or publication. Original receipt baseline/candidate hashes and full records are retained in `.claude/state/bryan_batch_11_20261025/` in the primary checkout; current derived deltas in the isolated handoff directory.

### What the latest summary does not close

- Later exact-label findings312832,330191,330664,328649,43662,277705,312947,285637,268493 and other63-case entries require per-entry current-owner/source verification and implementation as applicable. Known totals must remain usable; unknown fractions must not be invented.
- D031/D035, remaining additive study-type/substance/mixture explanations, D144 attribution and omega3/niacin eligibility/floors require their actual owner correction and consumer measurements. No automatic replacement dose threshold or new eligibility field is authorized.
- D011/D139 source-access completion is reported externally; retain appraisal boundaries until source bodies/receipts are independently inspected. D135 quantitative context and corrected PQQTable4 remain unavailable here.
- All genuine manufacturer unit/activity conflicts, archived preparation correspondence and specifically required approval holds remain explicit. Populated response cells are not equivalent to scientific or rebuilt closure.
- The complete marked171C/146D report was located via its Library link but could not be retrieved through the unauthenticated browser. This pasted summary does not contain the full case rows or63hashed receipt pairs; their reconciliation is not certified.

## Runtime correction batch — implemented October 25

**Current status:** confirmed engineering findings from batches6–9 are now implemented in the existing owners. Earlier “not fixed” statements below describe the review-only checkpoints, not the current candidate. Full-corpus/rebuilt closure remains separate.

Owner Check: `enhanced_normalizer.py::_apply_label_corrections/_process_quantity` and the existing product-label correction file own reviewed source repairs; its private `_apply_reviewed_serving_basis` extends that same mechanism. `serving_frequency.py` still owns cadence; corrected source metadata feeds it. `enrich_supplements_v3.py::_collect_rda_ul_data` owns vitamin activity/allocation decisions. `build_final_db.py::_fold_general_serving_variants` supplies the existing `serving_note`, already read by Flutter. `backed_clinical_studies/INGR_DIGESTIVE_ENZYMES` retains the clinical record. Evidence: matrix/glossary, callers, app reader and raw/source/output traces inspected. Will NOT create another registry, scorer, parser, approval, public field, source allocation or numerical policy.

| Correction | Implementation and bounded result |
|---|---|
| RAW275412 | Corrected exact-label daily source metadata from3–3 to3–9; per-capsule activities/blend amounts/CFU qualification retained. |
| Two-Per-Day328753 | Shared two-capsule basis corrected across27 top-level active rows and their quantity-bearing children; values preserved. Vitamin A now1,500mcgRAE/day, D50mcg/day, E67mg/day, Mg100mg/day, Zn25mg/day. Unknown acetate fraction remains unknown; existing conservative UL bounds may establish within-limit status without claiming an exact fraction. |
| Eight Bulk editions66984/69584/69613/243776/243812/243815/308692/315322 | Individually reviewed maps identify powder/water versus milk columns across panel rows, including nested rows. No runtime minimum-amount inference. Both alternatives retained; export supplies their existing serving notes. 243815 restores1–2/day. |
| Related transcriptions | Exact panels support iodine150mcg and sodium mg on69584/69613; water E30IU/Mg140mg/Zn15mg on243776; thiamin mg and1.505/1.615g ATP complex on315322;1.505g water ATP on308692;243812 milk sugars46g;243815 milk manganese2.6mg;69613 milk inositol200mg versus water250mg. These are image-supported API corrections, unlike the genuine manufacturer unit conflicts retained in batch8. |
| Named vitamin A sources | 67030 UI→IU and beta-carotene/palmitate; Bulk printed natural beta-carotene;328639 palm fruit mixed carotenoids plus beta-carotene. Legacy aggregate IU/preparation uncertainty retained; modern activity remains usable independently of preformed shares. Selecting powder never invents analytical zero retinol. |
| Poolzyme | Canonical notes and notable-study description now name Poolzyme Multi and200mg at lunch/dinner. Existing source-context review still incomplete; no efficacy approval or dose curve added. |

Every reviewed serving repair is bound to SHA-256 of its source panel, serving rows and statements. Changed content fails closed for renewed verification. The original API records are frozen; working pre-correction quantities are preserved, all serving alternatives remain, and repairs do not mutate caller inputs. Unknown selected quantities cannot fall through into a different milk preparation. Ordinary untouched IDs bypass this repair with a constant-time registry lookup.

**Verification:** fail-first regressions reproduced the defect classes, then targeted fixes passed. Combined owner/export/data slice:789 passed in60.98s. Additional export-note and clinical-hold checks:3 passed. Full18-case frozen raw replay completed through Clean/Enrich/Score/detail blob:12 affected records changed; six controls have identical cleaned/enriched/scored/blob hashes. All18 product safety statuses unchanged. Previously scored18299070.2,RAW27541266.2 and895884.1 unchanged.328753 and67030 become scoreable at80.4/62.0 through resolved source defects; evidence readiness was already complete before these repairs, not newly approved by this batch. Other unresolved products remain held. No full corpus run or real app render is claimed.

Data landed check:12 exact label entries and one clinical-description entry,0 unexpected/missing changes. No citation IDs changed: citation-diff tools selected0 citations/rules, which is not a new content-verification pass. Retained source receipts remain applicable, and the original Poolzyme methods/name/timing were independently rechecked again. Read-only fresh-context reviewer found no actionable defect; limits were no live re-fetch, broad suite or app render by that reviewer.

**Checkpoint passed:** local546passed/24declaredopt-in skips and [whole-fast CI40221374564](https://github.com/seancheick/PharmaGuide_Pipeline/actions/runs/40221374564) green on exact runtime source `a7c203160`. No pipeline rerun, import, release or public product publication. Remaining scientific approvals, manufacturer clarifications, corrected PQQ table/other source dependencies and rebuilt corpus/app verification are not bypassed.

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

## Batch 9 — vitamin E and the remaining vitamin A questions

All 14 exact NIH API records and archived PDFs were retrieved and each PDF was rendered and independently inspected on October 25. Sources, hashes, returned response and read-only owner probes are retained in `.claude/state/bryan_batch_9_20261025/`. The response correctly distinguishes source-data contradictions from untested software behavior. We additionally exercised current Clean, Enrich and scored-artifact owners for these 14 isolated inputs; this is diagnostic replay, not a full corpus run, candidate rebuild, app check or claim about current published artifacts.

Owner Check: `enhanced_normalizer.py::_process_quantity` and `serving_frequency.py::select_canonical_serving/resolve_facts_panel_serving_basis/resolve_daily_serving_range` own selected column, basis and cadence; product-specific reviewed corrections use the existing `product_label_corrections.json` mechanism. `rda_ul_data` owns adequacy/UL results. Evidence: raw quantity arrays, current selected Clean variants, Enrich adequacy and scored-artifact probes inspected. Will NOT create a second exposure calculator, scorer, clinical authority, source registry or guessed preformed fraction. This commit updates review reports only; reproduced runtime defects below remain unimplemented.

### Source decisions, individually reconciled

| Item / exact label | Independently verified source conclusion | Current-owner result and remaining boundary |
|---|---|---|
| C004 / [8958](https://api.ods.od.nih.gov/dsld/s3/pdf/8958.pdf) | d-alpha-tocopherol in ingredients; 800 IU/softgel, one or two daily. 536–1,072 mg/day using natural-form conversion. Do not allocate additional mixed-tocopherol masses. | Already implemented: correction restores the form, Enrich returns maximum 1,072 mg/day, UL 1,000 mg, over-UL 72 mg, scored safety caution. Existing production/export regression passed. No new efficacy approval or warning removal. |
| C036 / [66984](https://api.ods.od.nih.gov/dsld/s3/pdf/66984.pdf) | Natural beta-carotene named; water/powder 5,000 IU, milk-prepared 6,390 IU per two scoops/360 g; one or two daily. | Selects 5,000 IU currently. Source description still generic unspecified. Preserve unresolved legacy RAE conversion/source allocation, not a blanket unknown-source claim. |
| C037 / [67030](https://api.ods.od.nih.gov/dsld/s3/pdf/67030.pdf) | Original prints 5,000 IU; names beta-carotene and vitamin A palmitate, with cultured-source footnote. One complete pack daily; multivitamin portion is two light-green caplets. | Clean retains API UI and unspecified form. Image supports correcting transcription and recognizing named classes; exact source shares/conversion remain unresolved. Other pack components must retain their separate bases. |
| C038 / [69584](https://api.ods.od.nih.gov/dsld/s3/pdf/69584.pdf) | Natural beta-carotene; powder 5,000 IU vs milk 6,390 IU per two heaping scoops/360 g, one or two daily. | Clean currently selects milk value 6,390. Preparation-column correction needed; legacy conversion/allocation limitation remains. |
| C039 / [69613](https://api.ods.od.nih.gov/dsld/s3/pdf/69613.pdf) | Same type of declarations independently checked on Double Chocolate edition: powder 5,000 IU vs milk 6,390 IU, one or two daily. | Clean selects 6,390; source-column correction needed, no borrowed normalized RAE or fraction. |
| C057 / [243776](https://api.ods.od.nih.gov/dsld/s3/pdf/243776.pdf) | Vanilla Ice Cream separately confirms powder 5,000 IU vs milk 6,390 IU, two heaping scoops/360 g, one or two daily; natural beta-carotene named. | Clean selects 6,390. Keep exact edition and conversion/allocation limits. |
| C058 / [243812](https://api.ods.od.nih.gov/dsld/s3/pdf/243812.pdf) | Modern powder declaration 3,000 mcg vitamin A, milk 3,417 mcg; two heaping scoops/360 g, one or two daily. Natural beta-carotene in blend. Powder activity 3,000–6,000 mcg RAE/day. | Total activity already usable by Enrich, but Clean selects 3,417. Preformed fraction correctly remains unknown; fix column, not an invented fraction or DV-derived amount. |
| C059 / [243815](https://api.ods.od.nih.gov/dsld/s3/pdf/243815.pdf) | Independently confirms 3,000 mcg powder vs 3,417 milk and one or two daily. Preserve 334% printed DV without reverse calculation. | Clean selects 3,417 and cadence falls back to one daily because structured counts are null. Both require existing-owner correction. |
| C103 / [293269](https://api.ods.od.nih.gov/dsld/s3/pdf/293269.pdf) | Beta-carotene as mixed carotenoids; 700 mcg vitamin A per one-softgel daily serving. | Current total activity 700 mcg RAE/day is usable. Source category is recognized; no other carotenoid masses, efficacy or laboratory-zero-retinol inference. |
| C117 / [308692](https://api.ods.od.nih.gov/dsld/s3/pdf/308692.pdf) | Explicit powder 1,500 mcg RAE vs milk 1,708; six scoops/360 g, one or two daily. Natural beta-carotene in blend. | Clean selects 1,708; Enrich uses that known activity, so powder source selection needs correction. Actual powder range is 1,500–3,000 mcg RAE/day; unknown preformed share remains separate. |
| C146 / [315322](https://api.ods.od.nih.gov/dsld/s3/pdf/315322.pdf) | Own image confirms explicit 1,500 mcg RAE powder / 1,708 milk; six scoops/360 g, one or two daily. | Current selection is correct at 1,500, with Enrich range 1,500–3,000. Named added-source explanation still needs reconciliation; exact preformed share not established. |
| C151 / [328127](https://api.ods.od.nih.gov/dsld/s3/pdf/328127.pdf) | Beta-carotene from mixed carotenoids; 450 mcg per three capsules twice daily = 900 mcg RAE/day. | Current cadence and total are correct. Retain pregnancy/nursing/trying-to-conceive exclusion and glucose-monitoring instructions. No blood-sugar benefit approval follows. |
| C154 / [328639](https://api.ods.od.nih.gov/dsld/s3/pdf/328639.pdf) | African oil palm fruit mixed carotenoids plus beta-carotene; activity footnote defines RAE; 900 mcg/day per three capsules. Food Complex 1,400 mg is separate. | Current total 900 mcg RAE/day usable; conservative worst-case preformed bound is not an exact retinol allocation. Source explanation should retain printed palm/beta-carotene identity without guessed shares/standardization. |
| C156 / [328753](https://api.ods.od.nih.gov/dsld/s3/pdf/328753.pdf) | Archived 09/2024 / M22272F04 / L02317E: 1,500 mcg RAE per TWO capsules; two capsules/day divided with meals. Beta-carotene/acetate proportions not declared. | API assigns the panel to one capsule, two servings/day. Current owner replay indeed produces 3,000 mcg RAE/day. All 27 top-level raw active rows carry that one-capsule basis, so correction must reconcile the shared serving structure and verify all nutrients, not arbitrarily halve vitamin A alone. |

### Confirmed engineering findings, not yet fixed

1. **Serving basis — 328753:** full owner replay doubles vitamin A to 3,000 mcg RAE/day. Review all 27 panel rows against the two-capsule basis; preserve original amounts and unknown acetate activity fraction.
2. **Alternative preparation columns — six labels:** 69584/69613/243776 select 6,390 instead of 5,000 IU; 243812/243815 select 3,417 instead of 3,000 mcg; 308692 selects 1,708 instead of 1,500 mcg RAE. Selected physical mass alone cannot disambiguate equal-mass water/milk columns. Preserve all original variants and reviewed preparation provenance; do not sum alternatives, subtract milk estimates, or use minimum-amount heuristics. 66984 and 315322 currently select the correct A column and are controls. This is not yet a full nutrient-by-nutrient column correction.
3. **Missing cadence — 243815:** current result is one serving/day; printed directions establish one or two. Correct through serving owner with the RAW 275412 cadence finding already recorded.
4. **Source explanation/transcription:** 67030 UI-to-IU is image-supported; recognition of its named source classes and the disclosed natural beta-carotene in the specified Bulk rows needs owner qualification. Legacy RAE/preformed allocation remains unresolved. Current modern activity totals are already assessable; do not rebuild a second conversion policy or incorrectly claim they all fail conversion.

These require fail-first regressions, affected-label/control measurements, applicable local checks and combined behavioral CI before merge of runtime corrections. No new runtime correction is claimed by this report. The existing vitamin E regression `scripts/test.sh fast scripts/tests/test_product_label_corrections.py::test_signed_source_vitamin_e_uses_printed_natural_form_and_resolves_conversion` passed (1 test, 2.37 seconds); it covers dose range, caution and exported form/dose, not whole-corpus or real app rendering.

### Scientific limits retained

[NIH vitamin E](https://ods.od.nih.gov/factsheets/VitaminE-HealthProfessional/) supports the natural-form 0.67 mg/IU conversion, adult 1,000 mg/day supplemental alpha-tocopherol UL and anticoagulant/antiplatelet bleeding concern. A 1,072 mg maximum exceeds that UL; it does not predict harm in an individual or establish extra mixed-tocopherol amounts.

[FDA conversion guidance](https://www.fda.gov/media/129863/download), Table 1/footnotes and vitamin A conversion section, supports modern vitamin A mcg declarations as activity and distinguishes purified supplemental carotenoids in oil from food-source preparations. [21 CFR 101.9](https://www.ecfr.gov/current/title-21/chapter-I/subchapter-B/part-101/subpart-A/section-101.9) and [NIH vitamin A](https://ods.od.nih.gov/factsheets/VitaminA-HealthProfessional/) support retaining total activity separately from preformed exposure. Unknown preformed share does not erase a declared total. No all-preformed, 50/50, analytical-zero, or DV-derived allocation is accepted; legacy aggregate IU totals retain their specific preparation/conversion limitation. Review provenance, clinical holds and efficacy exclusions remain unchanged.

**Closure scope:** fourteen returned source dispositions reconciled, including already-correct controls and reproduced defects. No whole-product closure, runtime repair, newly approved evidence credit, corpus rebuild, app parity or release is asserted. Current owner probes are diagnostics, not verification of the existing shipped corpus. Earlier engineering findings remain open alongside the four classes above.

## Closure and next actions

- **Recorded:** Sean's batch1 approval of supported sub-decisions, subject to the stated holds; first-batch exact-label facts above; available API/full-text source facts for batches2/3; the newer Magtein correction and retrospective COLLinstant registration.
- **Not repeated:** already completed source retrieval/correction work. None of these access gaps should be sent back as if the sources were still unobtainable.
- **Batches4/5 additions:** source/access facts above and D043–D046 triage are recorded; retain the TGA avoid precaution and all stated preparation/applicability holds. No automatic acceptance of the proposed weaker warning.
- **Batches6/7 additions:** exact-label/source facts above are checked; RAW daily-range and canonical Poolzyme description corrections remain engineering work for the combined implementation batch, not extra scientific sign-offs.
- **Still needed:** applicable trial/preparation/product decisions and authentic review provenance through existing owners; unavailable full texts/tables only where still unavailable; PQQ corrected Table4; trial overlap/forest-input reconciliation; Magtein11-product and collagen24-product correspondence; generated A148 behavior; eventual rebuilt-corpus and app verification.
- **Not done:** runtime context migration, new scoring eligibility, changed weights/grades/benchmarks, full pipeline, publication, or scientifically/rebuilt-closed status for A011/A135/A059/A148/A003/A029/B433/A063/A090.

Audit receipt hashes and exact retrieval outcomes are retained locally in `.claude/state/bryan_review_20261025/receipt.json`, with source bodies in the batch folders, with the batches 4/5 supplement in `.claude/state/bryan_batches_4_5_20261025/receipt.json`. Batches6/7 source receipts are retained in `.claude/state/bryan_batches_6_7_20261025/`. The existing hold register records receipt/verification progress without changing frozen counts, production eligibility or closure fields.


### Combined checkpoint correction — October25

CI40220219109 on3b198e871 failed with three enumerated classes: one over-broad legacy-IU condition, four stale phase3 metadata pins, and five hierarchy rejection-message pins. The IU condition now limits the new source-preparation uncertainty to alternative preparation columns or the explicit cultured-vitamin/mineral context; ordinary mixed beta/retinyl behavior and its4500mcgRAE regression are preserved. The original beta-carotene UNII on243812/243815 is retained (live NIH source content names Beta-Carotene for01YAE03M7J). Strict metadata expectations were updated only for those two newly reviewed records, and all changed RAW hierarchy inputs still must raise; they now reject earlier at the SHA binding. No weakened safety exception or numerical policy change.

Targeted combined files:212passed46.54s; remaining affected owner/guard slice126passed9.97s. Reviewer inspected just this delta and found no actionable issue. Fresh18-case qualified replay and local validation in progress; one combined whole-fast retry follows the finished corrections. Previous failed CI is not reported as passing. Ten actual staged serving-repair inputs were independently checked and all source bindings match. No full pipeline/app import/publication.


### Final runtime qualification — October25

**Implemented and qualified for main integration:** exact runtime source `a7c203160cce07b00f0cb3f2fec57490ed70b046` passed [whole-fast CI40221374564](https://github.com/seancheick/PharmaGuide_Pipeline/actions/runs/40221374564), all4shards, including strict declared-skip guards. Final local rung:546passed/24declaredopt-in skips in135.96s. Targeted correction/consumer checks and fresh-context delta review passed as recorded above. First checkpoint40220219109 failed and was corrected; it is not counted as a pass.

Latest bounded artifacts are `qualified_candidate.jsonl`, `qualified_candidate.jsonl.records/`, `qualified_delta.json` and `qualified_movement_summary.json` under `.claude/state/verified_runtime_batch_20261025/`, beside frozen raw manifest/baseline and source receipts.18products,12affected and6hash-identical controls; all18safety states unchanged. All10actual staged serving-repair sources match their content bindings. Superseded intermediate captures removed. The final integration receipt changes documentation only; runtime source is identical to the green candidate.

Confirmed engineering corrections in this batch are no longer deferred. Genuine clinical/source/manufacturer limitations remain held; no whole-corpus/rebuilt closure, real Flutter rendering, pipeline rerun, app import or release is claimed. Remaining external/source decisions and post-rebuild corpus/app verification stay on the existing register.


## Batch 10 — elemental magnesium, Zychrome and incomplete daily frequency

October 25: independently retrieved all five exact live NIH API records and original PDFs, and visually inspected every panel. Sources and SHA receipts: `.claude/state/bryan_batch_10_20261025/source/receipts.json`. The original returned response remains unchanged outside the repository. A source disposition is not rebuilt-product closure.

Owner Check: `enhanced_normalizer.py::_process_serving_sizes`, `serving_frequency.py::resolve_daily_serving_range` / `resolve_facts_panel_serving_basis`, enrichment's existing serving/RDA owners, `clinical_applicability.py::assess_clinical_applicability` and `build_final_db.py::generate_dosing_summary`. Evidence: matrix, existing contracts/callers and five-label production seam replay. Will NOT create a new registry, numerical form grade, approval, public field or daily maximum.

| Item | Independently verified disposition | Runtime and remaining boundary |
|---|---|---|
| C013 /25501 |200 mg elemental from2000 mg chelate per2tablets;2tablets twice daily=400mg/day. |Already correct; magnesium350mg supplemental UL comparison and50mg excess retained. The mixed-ligand form review remains held; no generic bisglycinate credit. |
| C041 /188790 |One packet contains200mcg chromium; explicit50%Zychrome=100mcg elemental contribution, not preparation mass. |200mcg/packet and50%form declaration already survive cleaning; no sevenfold multiplier or proprietary-blend flag. No Zychrome clinical match contributes evidence. Exact preparation numerical assessment remains held; no invented grade or ligand masses. |
| C042 /203385 |200mg magnesium from1112mg buffered preparation per3capsules daily.855mg carnitine fumarate yields500mg carnitine. |Elemental magnesium already200mg/day; source material is a non-distinct duplicate for UL, not added exposure. Exact archived internal composition/form grading remains unresolved; current product composition cannot establish the archived ratio. |
| C149 /322515 |200mg elemental from2000mg chelate per2tablets twice daily=400mg/day. |Already correct; source4000mg/day not added as magnesium.350mg supplemental UL warning retained; named preparation hold retained. |
| C150 /323080 |40mg magnesium per10.4g scoop; no finite daily scoop maximum. Exact pregnancy consultation and California warning preserved. |Reproduced and fixed a shared defect: cleaner filled the absent endpoint with1; frequency owner then treated it as declared and export printed daily cadence. Preserve the partial source range, mark the numeric assessment basis estimated, expose uncertainty through existing exposure provenance, reject unestablished daily clinical dose qualification, and export See product label. No three-scoop interpretation, chelate mass or new efficacy grade. |

Both original chromium papers were read in full through official PMC HTML (`PMC4077620`, PMID22674882; `PMC5043078`, PMID27687012), after the full-text XML endpoint failed. Both studied400mcg elemental chromium/day. The latter reanalyzes43metformin-only participants from the former trial; it is not independent replication. Its glucose comparison versus placebo is p=.10, with exploratory/sponsor limitations. These findings do not establish glucose-control or weight-management benefit for this packet's100mcg Zychrome contribution. Primary full texts: https://pmc.ncbi.nlm.nih.gov/articles/PMC4077620/?pdf=1 and https://pmc.ncbi.nlm.nih.gov/articles/PMC5043078/?pdf=1 . Identity/allocation confirmation is not efficacy approval. No curated clinical record, scoring weight or approval changed.

Fail-first: partial daily range and exported cadence regressions failed on the original owner; exact Catalyte source regression also reproduced cleaner endpoint fabrication. Existing173920fixture says adults may take one scoop **one or more times per day**: its adult Facts basis stays20g, while its obsolete finite-daily assertion is corrected to uncertainty. Numeric assessment fallback is retained for existing policy; it is not a verified maximum or personal recommendation.

Bounded five-label frozen raw comparison against clean main e7e1c4aab:25501/188790/203385/322515 have identical normalized hashes across cleaned/enriched/scored/blob layers.323080 changes cleaned/enriched/blob only; scored hash remains identical. All five remain not_scored, all safety states unchanged. This checks source-to-export behavior, not actual Flutter rendering or a rebuilt corpus. Evidence retained under `.claude/state/bryan_batch_10_20261025/`. Qualification/integration status follows the LEDGER; no full pipeline or release.


### Batch 10 combined checkpoint correction

Whole-fast40223229927 on1367471e75c8071222d31b1728b017d963e13d29 failed4assertions in one fixture class: three hypothetical cranberry daily-goal cases and one hypothetical Ashwagandha daily-evidence case omitted a declared daily regimen. Two CI shards passed; the failed run is not a green checkpoint. The production guard remains unchanged. Synthetic positive/underdose fixtures now explicitly declare one daily serving; new consumer regressions require unknown or partial frequency to produce neither a supported nor an underdosed urinary goal. No clinical record, actual product regimen, score, warning or gate was loosened.

Local546passed/24declaredoptinskips315.10s with strictskipguard; runtime source unchanged by the fixture correction, so that receipt remains applicable.557original combined owner/export tests passed. Targeted failed-class/owner/real-label slice passed (see retained terminal/CI receipts); final whole-fast retry pending before main integration. Fresh-context review previously found no actionable runtime issue. No full pipeline/app import/release.


### Batch 10 — additional reproduced interaction consumer defect

Owner: `supplement_type_utils.py::mark_compound_duplicate_rows` and `enrich_supplements_v3.py::_collect_interaction_profile` — evidence: exact203385/322515 raw-to-export probes, existing RDA duplicate decisions and existing `_interaction_row_key`. Will NOT create a second exposure classifier, registry, clinical rule, public field or source allocation.

The RDA dose totals were correct, but a further consumer check reproduced a separate error: interaction rules also evaluated1112mg buffered source as1112mg elemental magnesium beside its actual200mg, and2000mg chelate twice/day as4000mg magnesium beside actual400mg. Two fail-first exact-label assertions failed with those false amounts. Reuse the existing duplicate owner via an optional process-local owner map and existing source/row identity seams; same nutrient rule is evaluated on its declared parent. Unique source-specific rules retain amount-unknown/review protection, and distinct banned/other safety subjects retain their own warnings and quantities. No warning policy changed.

Independent delta review found an introduced repeated-path ambiguity in an initial join. A regression reproduced the lost scoped warning; the corrected join uses existing path+label+canonical keys, unique candidates and a no-self-owner guard. Reviewer independently reran the reproducer and confirmed amount_unknown/review survives; no remaining actionable finding. Initial new synthetic setup/key-name mistakes were fixed without counting them as production fail-first evidence.

Validation:116nearby interaction/owner tests passed66.39s before the join correction;4repeated-path/scoped/distinct-hazard cases passed0.80s after correction;54final owner/real-label/source-amount tests passed5.69s. Final frozen five-label full-layer replay supersedes the earlier frequency-only result:203385/322515 interactions/export corrected,323080partial-frequency correction;25501/188790 remain hash-identical across all layers. Every scored hash and top-level safety status remains identical, all5products stillnot_scored. Real400mg/day magnesium warnings remain; false source-mass duplicate alerts are removed. Full evidence and all changed paths retained in final_qualified_candidate/records,final_qualified_delta,final_qualified_movement_summary.

Whole-fast40223229927 failed4synthetic regimen assertions (fixed as above). The frequency-only retry40224249527 is superseded by this final output-changing correction and is not qualification for the new source. Final local/combined CI pending before main merge; no full pipeline, app import or release.


### Batch 10 final qualification — October 25

Completed runtime source `91221cba9023305e84212be2b53111ba53841655` passed [whole-fast CI40225009285](https://github.com/seancheick/PharmaGuide_Pipeline/actions/runs/40225009285), all4shards, including declared-skip guards. Final local:546passed/24declaredoptinskips160.74s, strictskipguardpassed. Final source-amount owner checks54passed5.69s; repeated-path/scoped/distinct-hazard matrix4passed0.80s; gold interaction benchmark56passed2.07s. Earlier557owner/export,271fixture/owner and116nearby safety checks are recorded above, not added into a misleading unique test total. Independent initial/delta reviews complete; the introduced repeated-path finding was reproduced, corrected and independently re-probed before this qualification. FirstCI40223229927 failed4synthetic fixture assumptions;40224249527 was superseded/cancelled and does not count as a pass.

Final five-label capture source fingerprints exactly match the committed runtime (final_committed_binding.json). All5scored hashes/top-level safety states remain unchanged and all5remainnot_scored.25501/188790are full-layer controls;203385/322515have corrected interaction consumers/export;323080has corrected partial-frequency provenance/export. All condition and drug-class warning target sets remain present for both interaction corrections (final_safety_target_parity.json). Real400mg/day magnesium warnings remain; no1112/4000mg source material is treated as elemental magnesium. Required scientific holds, source quantities, original statements and numerical scoring policy remain intact.

Authoritative retained receipts: `.claude/state/bryan_batch_10_20261025/` source bodies/hash receipts,frozenmanifest,baselinecapture,final_qualified_candidate/meta/records,final_qualified_delta,final_qualified_movement_summary,final_committed_binding,final_safety_target_parity,final_local.log,final_ci_watch.log. Superseded reproducible archive and duplicate intermediate capture removed after hash equivalence checks; unique source inputs retained. This final receipt changes documentation only relative to the green source. Main integration is authorized; no duplicate CI wait is required for identical runtime plus this receipt.

Source findings are verified and confirmed engineering corrections are implemented/qualified. This is not scientific approval of unresolved preparation grades, whole-corpus rebuilt closure or actual Flutter rendering. No full pipeline, app import or release ran. Those existing downstream/source-review gates remain explicit.

### Later exact-label receipt collection

Nine additional exact NIH API/PDF pairs are independently gathered and visually inspected by receipt agents:312832,330191,330664,328649,43662,277705,312947,285637,268493. Their unchanged originals, hashes, individual findings and image paths are retained under the existing Batch11 receipt root in `batch12_sources_a/` and `batch12_sources_b/`. These are source hypotheses pending main-model inspection and implementation, not closed products. Two existing-owner limitations are identified: source-bound statement replacement and reviewed cross-parent movement of nested rows. Preserve source conflicts and all safety warnings; do not invent missing component amounts or make modern editions repair archived ones.

## Batch11 final integration qualification — October25

PR248 merged at `3506351fcb3c6232282486dac420f34e5b8d4108`; ancestry of exact tested head `3efb50764e78f950c9e5f2e9f2752a40d9b3c883` verified in origin/main. Rebased on the separately qualified product-detail merge `d107824976c8070c0482ef58768bf80d4e62babb`; the sole rebase conflict was additive ledger text and both records were preserved. Dirty primary-checkout copies were not imported, staged or removed.

Whole-fast CI40233428775 passes all four shards and all four declared-skip guards. Combined named source/normalizer/export tests343passed79.08s; combined local546passed/24declared opt-in skips139.60s with skipguard green. Earlier CI40228636370 failed historical numerical expectations; it is not qualification. Earlier missing-artifact local checkpoint is also not a pass.

The full18-label frozen raw replay was rerun against the merged product-detail source and this rebased candidate. Every candidate scored artifact hash, score and status matches its previously reviewed candidate. Intentional source corrections and safety-related exposure/ceiling movements are described above. No scoring weight, clinical approval, full corpus, catalog import or release was added. Existing18-record comparison receipts and immutable source inputs remain retained; integration captures are in the active source-review worktree's ignored `batch11_integration` directory.

All nine later label images were also independently inspected by the integrator after receipt gathering. Their source findings are confirmed; they remain a separate unimplemented correction batch, requiring the existing statement/hierarchy owners and full consumer checks. No unknown mixture allocations, modern-to-archived substitutions or clinical clearances follow. The full marked171C/146D report remains unretrieved, and additional source/applicability/citation/eligibility decisions remain open. This qualification closes this engineering integration only.

## Batch12 — all nine exact-label corrections implemented, October25

Owner: `enhanced_normalizer.py::_apply_reviewed_serving_basis/_apply_label_corrections`, existing product-label registry, and IQM cranberry fallback explanation — evidence: nine exact API/PDF image receipts independently inspected, frozen12raw replay, fail-first owner/export regressions. Will NOT create another registry, scorer, policy, public field, source amount, species equivalence or approval. Baseline `cc6a56b57ad0950f470031aa79c641622f6fd6cf`; branch `codex/batch12-nine-label-corrections`. This supersedes earlier unimplemented status for these nine engineering cases only.

| Exact label | Implemented correction and retained boundary |
|---|---|
|312832|Two softgels/day and2400mg total oil statements; each800mg oil retained. Other editions untouched; no fatty-acid allocation.|
|330191|Whole oyster extract10:1,500mg replaces false shell identity; wrong shell-form identifier cleared without replacement. Shellfish warning retained.|
|330664|Vaccinium macrocarpon fruit powder5g replacesV.oxycoccus form; actual front200versusFacts20servings conflict retained. Generic fallback copy no longer denies disclosed fruit; no PAC amount invented and grade4 retained.|
|328649|Shell-broken Reishi spores150mg separate from980mgfruit-body extract. No standardization/clinical transfer or polysaccharide→beta-glucan substitution.|
|43662|Three original fruit rows move from Reishi200mg to fruit blend140mg, keeping immutable source paths and unknown individual amounts.|
|277705|35mg is phytocannabinoids AND terpenes, including25mgCBD within334mgextract. Descriptor stays excluded from independent scoring. Existing blocked/suppressed safety status and restrictions retained.|
|312947|ArchivedV002servings2→120; P.asiatica and1400mg/two capsules retained. Husk is explicitly annotated without borrowing the genericP.ovata preparation. Its pre-existing identity/preparation hold remains.|
|285637|Generic4+target metadata replaced with the actual6+under-adult-supervision direction; original statements/other groups remain. No pediatric efficacy approval.|
|268493|9gMCT/acacia mixture total retained as an excluded blend header with two unquantified original source constituents, not9gpureMCT. False tree-nut-free/facility additions removed; coconut and printed cross-contact warnings retained.|

The existing receipt owner now permits only specifically bound `servingsPerContainer`/`targetGroups` changes and same-membership/type statement corrections. Source hash still covers ingredient rows, servings and statements; additional original metadata is equality-bound independently. Existing hierarchy handling supports explicit source-parent/quantity-bound nested/form-row movement and rejects final graph cycles before mutation. Caller raw input remains unchanged.

Fail-first:19initial regressions failed for the source cases/bindings; diagnostic psyllium alias promotion was separately reproduced and rejected rather than granting P.ovata credit; cranberry consumer contradiction also failed before repair. Final correction-owner slice359passed81.26s; added exporter regression passes. Independent review reran24owner cases and found no blocking defect; the additional wording-only change was reviewed separately with no finding. The local behavioral checkpoint passed546tests/24declaredopt-in skips157.57s with skipguard green. The later cranberry wording change has named consumer coverage and numerical-equivalence verification; no broad rerun is required solely for that display clarification.

Exactly9product-label entries and1IQMparent explanation changed, with landed checks clean. Changed-citation/rule inventories select0newPMIDs/0rules: this is no new clinical-evidence claim or scientific approval. All original API/PDF bodies, hashes and image receipts remain in the existing Batch11 source-packet directories. Batch12 immutable12raw manifest/baseline/qualified captures are retained in `.claude/state/bryan_batch12_20261025/` in the primary checkout.

The bounded comparison covers9affected labels plus3full-layer unchanged controls188790/25501/66513. Oyster calculates53.9with0Evidence, cranberry58.1andGoldenMilk28.6with0Evidence; these are provisional calculations under existing policies, not release approval. Oyster/cranberry unfinished source reviews remain represented in existing release assessment receipts. Psyllium remainsnot_scored, CBDremainssuppressed_safety. No product safety-status change or observed lost warning-rule membership. Final explanation-only parity and exact-head CI/integration qualification are recorded in the follow-up. No full pipeline, app import or release.

### Batch12 final qualification and integration — October25

All nine engineering corrections are integrated through PR249 at `406cd6ff8f9d2f740b073954a5ccbd12d2f44507`. Exact head `10098f1a06895881dac080e1a02057c49f3e85b2` passed whole-fastCI40239901450:all4shards/all4declared-skip guards green; ancestry verified in fetched origin/main. No extra clinical authority, grade, weight or public contract changed.

Final committed12-label captures prove all12scored hashes unchanged by the additional cranberry wording clarification. Three controls188790/25501/66513 have identical Clean/Enrich/Score/blob hashes versus baseline; all12product safety statuses remain unchanged. Core consumer probe verifies archived psyllium120servings/Take2capsulesdaily and oil2softgelsdaily. Psyllium identity/preparation and existing Oyster/cranberry release-review holds remain; CBD staysblocked. Scores that now calculate are provisional under existing assessment policy, not scientific/release clearance.

359combinedowner/consumer checks plus the additional named exporter regression pass; independent full-diff and wording-only reviews report no blocking finding. Local546/24declaredopt-in skips+guardgreen passes; subsequent display-only wording has named export coverage and complete12-record numerical/status parity. No repeated broad checkpoint was required solely for that wording. The exact final source passed the whole-fast checkpoint above.

Retained evidence: primary `.claude/state/bryan_batch12_20261025/frozen/manifest.json`,baseline_sha,baselinecapture/fullrecords,`final_committed_candidate.jsonl`/meta/fullrecords,`final_movement_summary.json`,source receipt originals/hashes andCIwatchlog. Intermediate captures are diagnostic, especially the rejected psyllium alias promotion; they must not be used for qualification. This documentation follow-up changes no executable/reference source. No full pipeline, catalog/import, real-app source refresh or release occurred. Broader clinical/citation/benchmark and final corpus/app qualification remain separate.


## October 26 — returned 18 C / 47 D implementation and qualification

This supersedes the earlier pending-source-work list above. All 65 items have an individually checked disposition and the supported corrections are implemented in the current candidate. This closes the bounded engineering/source-correction work, **not** all scientific approvals or rebuilt-corpus assessments. C143 required no edit. Original 15,437-product snapshot and all existing holds remain intact. No full corpus, catalog import, cloud write or publication performed.

Owner: `enhanced_normalizer.py::_apply_label_corrections`, `serving_frequency.py::resolve_daily_serving_range`, existing Enrich botanical/source/evidence owners, `build_final_db.py::_verified_corrected_source_label`, canonical IQM/standardized/safety/synergy/marker records, and Flutter `product_canonical_ids.dart::markerCanonicalIdsFromDetailBlob`. Evidence: exact-label image/API receipts, per-D content receipts, fail-first owner/export regressions and paired frozen-raw artifacts. Will NOT create: another scorer, identity authority, review registry, approval, grade, benchmark or release orchestrator. Sean explicitly approved only the two existing-owner Boolean eligibility extensions, with safety and factual-composition preservation.

### Each C-label disposition

Every source below is the exact NIH label edition, independently compared with the retained raw API record. Corrections are bound to source content and fail closed on changed panels/statements. A documented missing daily limit remains a manufacturer limitation, not an invented daily regimen.

| Case | Exact label | Implemented or confirmed disposition |
|---|---|---|
| C014 | [25583](https://api.ods.od.nih.gov/dsld/s3/pdf/25583.pdf) | No numeric daily maximum; distinguish one-serving fallback from label directions. |
| C020 | [29049](https://api.ods.od.nih.gov/dsld/s3/pdf/29049.pdf) | Same completed label limitation; no invented bar count. |
| C021 | [29054](https://api.ods.od.nih.gov/dsld/s3/pdf/29054.pdf) | Same completed label limitation; no invented bar count. |
| C024 | [33361](https://api.ods.od.nih.gov/dsld/s3/pdf/33361.pdf) | Restore exact 17β diol label spelling and existing banned alias; retain BLOCKED and warnings. |
| C026 | [43662](https://api.ods.od.nih.gov/dsld/s3/pdf/43662.pdf) | Restore printed beet Root and preserve existing fruit hierarchy; daily maximum remains undisclosed. |
| C027 | [43947](https://api.ods.od.nih.gov/dsld/s3/pdf/43947.pdf) | Restore printed beet Root; no numeric daily maximum. |
| C032 | [63330](https://api.ods.od.nih.gov/dsld/s3/pdf/63330.pdf) | Restore printed beet Root; no numeric daily maximum. |
| C033 | [63463](https://api.ods.od.nih.gov/dsld/s3/pdf/63463.pdf) | Restore printed beet Root; no numeric daily maximum. |
| C034 | [63475](https://api.ods.od.nih.gov/dsld/s3/pdf/63475.pdf) | Restore printed beet Root; no numeric daily maximum. |
| C040 | [78327](https://api.ods.od.nih.gov/dsld/s3/pdf/78327.pdf) | No numeric daily maximum; retain previously reviewed iodine correction. |
| C079 | [254413](https://api.ods.od.nih.gov/dsld/s3/pdf/254413.pdf) | Correct exact SKU X001FYWVWV; container mass is not a serving. Professional-use caution retained. |
| C091 | [259374](https://api.ods.od.nih.gov/dsld/s3/pdf/259374.pdf) | Restore hemp seed, 30 g, and 1.7 g EFA note; no CBD or whole-plant efficacy inference. |
| C094 | [268493](https://api.ods.od.nih.gov/dsld/s3/pdf/268493.pdf) | No numeric daily maximum; retain reviewed MCT/allergen corrections. |
| C116 | [306350](https://api.ods.od.nih.gov/dsld/s3/pdf/306350.pdf) | Restore zero sodium unit to mg through nutrition ledger, not just the active-row path. |
| C143 | [312713](https://api.ods.od.nih.gov/dsld/s3/pdf/312713.pdf) | Already correct control: corn silk powder 6.25 mg and separate Uva-Ursi 3:1. No data change. |
| C147 | [315586](https://api.ods.od.nih.gov/dsld/s3/pdf/315586.pdf) | Restore ten printed plant parts; Wood Betony is a name, not wood tissue. Blend children remain undosed. |
| C167 | [330806](https://api.ods.od.nih.gov/dsld/s3/pdf/330806.pdf) | Restore 10 g EAA parent → undosed blend → nine undosed children, including exported geometry. No component allocation. |
| C168 | [330882](https://api.ods.od.nih.gov/dsld/s3/pdf/330882.pdf) | Keep 210 mg combined grape seed/skin under broad grape identity through export; separate 125 mg seed remains seed. No constituent dose invented. |

### Each D-citation disposition

Rejected citations remain identified as rejected provenance, not affirmative efficacy evidence. A verified abstract establishes only its content; it is not a completed applicability approval. No scoring weights, `bio_score`, severity grades or legal statuses changed. Perilla and cascara unsupported human-absorption fractions were replaced by the existing unknown/null representation.

| Case | Verified source | Applied disposition and remaining boundary |
|---|---|---|
| D017 | [Source](https://pubmed.ncbi.nlm.nih.gov/7491892/) | Batch 12 source decision: PMID 7491892 is cross-topic quercetin history in sea-buckthorn notes, not sea-buckthorn support. Its attribution of 1–5% systemic rutin availability is not established: the study measured intake minus ileostomy excretion, not absolute systemic bioavailability. Correct that numerical description without transferring quercetin results to sea buckthorn. |
| D020 | [Source](https://pubmed.ncbi.nlm.nih.gov/29163194/) | Batch 12 source decision: PMID 29163194 concerns exogenous ketone drinks and appears as cross-topic history under inositol. Keep it out of direct inositol support. The tested salts contained a substantial L-beta-hydroxybutyrate fraction, but this check does not endorse the note’s blanket characterization of that isomer as inactive or generalize the tested mixture to all salts. |
| D031 | [Source](https://pubmed.ncbi.nlm.nih.gov/26889234/) | Batch 12 source decision: PMID 26889234 supports pharmacokinetics of a studied 500 mg trans-resveratrol tablet. It does not establish whole red-wine-extract bioavailability, proanthocyanidin absorption or an exact commercial extract match. Retain only explicitly component-specific background; qualify the affirmative note rather than treating its number as a red-wine-extract result. |
| D035 | [Source](https://pubmed.ncbi.nlm.nih.gov/21116018/) | Batch 12 source decision: PMID 21116018 tested 500 mg/day of an Indus Biotech fenugreek preparation standardized for Grecunin, not 500 mg isolated diosgenin. Original full-paper methods now verified. Correct the direct diosgenin attribution; no component dose, generic fenugreek match, replacement benchmark or clinical approval is established. |
| D057 | [Source](https://pubmed.ncbi.nlm.nih.gov/12323085/) | Batch 12 source decision: PMID 12323085 can support narrowly described ALA-metabolism context: a tracer study in six young men. It does not establish perilla-product bioequivalence, whole-oil absolute absorption, a form grade or absence of conversion in every population. Retain only that bounded physiological explanation. Unsupported absorption0.8/range0.7–0.85 removed to unknown/null; bio_score unchanged. |
| D062 | [Source](https://pubmed.ncbi.nlm.nih.gov/16205659/) | Batch 12 source decision: Keep non-supporting/content hold: the exact Europe PMC DOI maps to an obesity-congress Foreword, but its body was not received. Update the source-identity receipt without claiming full review or supplying sage/Cognivia efficacy credit. |
| D063 | [Source](https://pubmed.ncbi.nlm.nih.gov/22982073/) | Batch 12 source decision: Restrict to emodin Caco-2 metabolism/efflux context. It does not support cascara/cascaroside hydrolysis or the form’s 0.30 absorption fraction; preparation-specific evidence and the quantitative basis remain unresolved. Preserve existing safety/regulatory wording. Both cascara forms now unknown/null for unsupported human absolute absorption; bio_score and warnings unchanged. |
| D064 | [Source](https://pubmed.ncbi.nlm.nih.gov/6528310/) | Batch 12 source decision: Keep only preclinical capsaicin antiplatelet context and existing theoretical-interaction cautions. Classify this PMID as an in-vitro rat-platelet experiment, not case_report; do not infer an oral cayenne dose or clinical interaction magnitude. |
| D092 | [Source](https://pubmed.ncbi.nlm.nih.gov/24013626/) | Batch 12 source decision: Keep excluded and bonus held: this is bacterial RNA research. Qualify the residual bare sources[0] URL as rejected provenance; retain exact NeuroFactor composition/outcome review and separately owned IQM evidence. |
| D099 | [Source](https://pubmed.ncbi.nlm.nih.gov/23644932/) | Batch 12 source decision: retain the narrow AREDS2 supplier link, not the title-screen mismatch. Original methods name DSM-supplied lutein/zeaxanthin; Kemin identifies FloraGLO. The primary add-on result was nonsignificant (HR 0.90; P=.12); subgroup/substitution findings remain separate. This PMID does not validate a universal >5% grade, brand-only bonus or general efficacy. Preparation grade and any award remain separate owner decisions. Existing bonus_eligible=false / requires_verification holds applied pending qualifying preparation-specific support. |
| D105 | [Source](https://pubmed.ncbi.nlm.nih.gov/18689548/) | Batch 12 source decision: original abstract is a serum-hepcidin assay study, not life’sDHA research. Its unqualified URL remains in sources[0], although this preparation is already requires_verification and bonus_eligible=false. Mark the citation inapplicable while preserving the existing hold and algal-DHA identity; no replacement or efficacy credit is supplied. |
| D106 | [Source](https://pubmed.ncbi.nlm.nih.gov/18689548/) | Batch 12 source decision: original abstract is a hepcidin-assay study, not sea-buckthorn seed-oil evidence. Notes/rationale already recognize the mismatch; sources[1] still presents the raw URL. Reconcile that presentation and preserve the unresolved 30% combined-fatty-acid floor and seed-versus-fruit distinction. No new efficacy or threshold approval. |
| D107 | [Source](https://pubmed.ncbi.nlm.nih.gov/28494836/) | Batch 12 source decision: original abstract concerns silica-induced lung toxicity in rats, not Lutemax 2020. The raw citation is in sources[0], but the preparation is already requires_verification and bonus_eligible=false. Record the source as inapplicable; retain existing preparation/specification questions without an invented replacement. |
| D108 | [Source](https://pubmed.ncbi.nlm.nih.gov/29144655/) | Batch 12 source decision: PMID 29144655 exists as an IQWiG dulaglutide PubmedBookArticle; its abstract concerns diabetes-treatment assessment, not Lutemax. Correct any not-found interpretation and reject its carotenoid attribution. The pinned backlog already records this distinction, and the preparation’s existing verification hold remains. |
| D109 | [Source](https://pubmed.ncbi.nlm.nih.gov/27535533/) | Batch 12 source decision: original abstract is the ExAC human exome-variation study, not MicroActive melatonin evidence. Qualify the raw sources[0] citation as inapplicable. The pinned preparation is already requires_verification with bonus_eligible=false; no release-profile, pharmacokinetic or sleep claim is established. |
| D110 | [Source](https://pubmed.ncbi.nlm.nih.gov/15211420/) | Batch 12 source decision: PubMed author/title/journal/indexing identify Cameron’s nursing-ethics article, not the attributed Schneider/Rubben nettle BPH trial. No abstract is available and publisher full text was unavailable, so no full-content review is claimed. Notes already reject the PMID, while sources[1] retains the false attribution; reconcile that inconsistency and retain the part-specific 1% floor question. |
| D111 | [Source](https://pubmed.ncbi.nlm.nih.gov/15050362/) | Batch 12 source decision: original abstract concerns neutron-activated spoons and cobalt-60, not OptiBerry. Its raw sources[0] citation is inapplicable. The preparation is already requires_verification and bonus_eligible=false; preserve that status and the separate composition/standardization review. |
| D112 | [Source](https://pubmed.ncbi.nlm.nih.gov/16219800/) | Batch 12 source decision: original abstract concerns stem-cell transplantation for HLH, not OptiBerry. Its raw sources[1] citation is inapplicable. Preserve the preparation’s existing requires_verification/bonus_eligible=false status; this check supplies no replacement citation or component-level clinical credit. |
| D113 | [Source](https://pubmed.ncbi.nlm.nih.gov/27013539/) | Batch 12 source decision: original abstract concerns cardiac-amyloidosis prognosis, not Pacran or urinary-tract outcomes. Mark raw sources[1] inapplicable. The pinned preparation is already requires_verification and bonus_eligible=false; retain its existing standardization and preparation-applicability questions. |
| D114 | [Source](https://pubmed.ncbi.nlm.nih.gov/22260513/) | Batch 12 source decision: full original NO-performance review and both study tables checked; the grape-seed/arginine combinations do not establish Pycnogenol. This PMID does not substantiate the record’s 65–75% procyanidin specification or broad clinical-claim list. The pinned entry remains bonus_eligible=true with affirmative rationale, so qualify this source through the existing owner; do not infer a score change or reject legitimate brand identity. Existing bonus_eligible=false / requires_verification holds applied pending qualifying preparation-specific support. |
| D115 | [Source](https://pubmed.ncbi.nlm.nih.gov/20429767/) | Batch 12 source decision: original abstract describes breast plasmacytoma, not sea-buckthorn fruit/pulp oil. Notes already recognize the mismatch, but sources[0] remains a raw URL. Reconcile citation presentation and preserve the unresolved 3% palmitoleic-acid floor; do not transfer seed-oil evidence or approve a generic benefit. |
| D116 | [Source](https://pubmed.ncbi.nlm.nih.gov/24787677/) | Batch 12 source decision: original abstract measures plyometric-exercise intensity, not sea-buckthorn oil. The pinned notes/rationale already reject the PMID; sources[1] still shows its raw URL. Keep the unresolved fruit/pulp-oil 3% floor and preparation distinction while correcting citation presentation. |
| D117 | [Source](https://pubmed.ncbi.nlm.nih.gov/19883366/) | Batch 12 source decision: original abstract is a bone-modeling/remodeling review, not evidence for sea-buckthorn seed-oil composition or the 30% ALA-plus-LA floor. Notes already identify the mismatch; sources[0] remains unqualified. Reconcile that presentation and retain the existing floor/specification question. |
| D118 | [Source](https://pubmed.ncbi.nlm.nih.gov/24345046/) | Batch 12 source decision: original abstract reviews peanut resveratrol, not Sharp-PS Green. Mark raw sources[0] inapplicable. The pinned preparation is already requires_verification and bonus_eligible=false; its exact phospholipid source, composition and clinical applicability are not resolved by this paper. |
| D120 | [Source](https://pubmed.ncbi.nlm.nih.gov/18046594/) | Batch 12 source decision: original abstract compares dietary carbohydrate/fat restriction, not Thermosil or orthosilicic acid. Mark raw sources[0] inapplicable. Preserve the existing requires_verification/bonus_eligible=false status; no brand equivalence, silicon specification or clinical claim is approved. |
| D121 | [Source](https://pubmed.ncbi.nlm.nih.gov/22972503/) | Batch 12 source decision: original abstract measures αB-crystallin in breast-tumor tissue, not turkey-tail/PSK/PSP therapy. Notes already reject the PMID, while sources[0] remains a raw URL. Reconcile source presentation, retain whole-mushroom versus fraction limits and the unresolved 30% floor, and preserve oncology cautions. |
| D122 | [Source](https://pubmed.ncbi.nlm.nih.gov/31935893/) | Batch 12 source decision: original abstract concerns wearable-sensor feature selection, not Turmipure Gold. Mark raw sources[0] inapplicable. The pinned preparation is already requires_verification and bonus_eligible=false; no curcuminoid profile, bioavailability advantage or clinical credit follows. |
| D123 | [Source](https://pubmed.ncbi.nlm.nih.gov/19185917/) | Batch 12 source decision: original abstract analyzes myelodysplastic-syndrome treatments, not Uniflex. Mark raw sources[0] inapplicable. Preserve existing requires_verification/bonus_eligible=false status; the separate UC-II link does not establish an Uniflex=UC-II identity bridge in this review. |
| D145 | [Source](https://pubmed.ncbi.nlm.nih.gov/25932792/) | Approved relationship hold: omega3_niacin_lipid scoring_eligible=false; suppress cluster qualification, preserve separate ingredients/safety. Numeric v4 synergy premiums were already retired; no bonus-removal claim. |
| D146 | [Source](https://pubmed.ncbi.nlm.nih.gov/34410415/) | Approved knotweed→marker relationship hold; preserve percentages, known/unknown amounts and safety exposures. Eligible marker study cannot override hold; independent eligible sources remain eligible in either row order. |
| D124 | [Source](https://pubmed.ncbi.nlm.nih.gov/17825405/) | Blue1 was not tested; McCann is a mixture RCT, not an ingredient systematic review. |
| D125 | [Source](https://pubmed.ncbi.nlm.nih.gov/17825405/) | Blue2 was not tested; retain independently sourced hypersensitivity warnings. |
| D126 | [Source](https://pubmed.ncbi.nlm.nih.gov/17825405/) | Red40 was in mixture B; no isolated additive attribution. |
| D127 | [Source](https://doi.org/10.2903/j.efsa.2008.754) | Combined animal endpoints and total aluminium exposure/TWI; no human food-exposure Alzheimer conclusion. |
| D128 | [Source](https://doi.org/10.2903/j.efsa.2010.1461) | No EFSA n6:n3 ratio-harm conclusion; remove unsupported corn-oil inflammation inference. |
| D129 | [Source](https://ntp.niehs.nih.gov/publications/reports/tr/tr535) | 4-MEI mouse lung tumors, non-neoplastic rat liver lesions; no invented liver/thyroid tumor conclusion. |
| D130 | [Source](https://doi.org/10.2903/j.efsa.2015.4288) | Carmine-specific evidence cannot identify an undisclosed color; unknown identity stays explicit. |
| D131 | [Source](https://pubmed.ncbi.nlm.nih.gov/25731162/) | CMC/P80 mouse experiment is background, not direct E475 evidence. |
| D132 | [Source](https://pubmed.ncbi.nlm.nih.gov/25731162/) | Same E475 record: preserve regulatory/safety limits while removing unsupported class causal claim. |
| D133 | [Source](https://pubmed.ncbi.nlm.nih.gov/25731162/) | CMC/P80 evidence does not establish E471/soy monoglyceride effects. |
| D134 | [Source](https://doi.org/10.2903/j.efsa.2018.5083) | 2018 assessment concerns 3-MCPD; distinguish prior glycidyl assessment and unmeasured product contamination. |
| D135 | [Source](https://pmc.ncbi.nlm.nih.gov/articles/PMC10922848/) | Phosphate percentages are bioaccessibility, not absorption; preserve renal-risk context and elemental-P basis. |
| D136 | [Source](https://doi.org/10.2903/j.efsa.2019.5674) | Group phosphate ADI concerns elemental P/total exposure and excludes impaired renal function; no blanket safe claim. |
| D137 | [Source](https://pubmed.ncbi.nlm.nih.gov/22529856/) | Folate study measures biomarkers in reproductive-age women, not direct clinical harm. |
| D138 | [Source](https://pubmed.ncbi.nlm.nih.gov/17825405/) | Yellow5 was mixture A; retain applicable labeling and hypersensitivity warnings. |
| D143 | [Source](https://pubmed.ncbi.nlm.nih.gov/40047835/) | Phenylpiracetam review:11 articles/549 patients, asthenia200mg/day one month; no invented sponsor-region claim or warning removal. |
| D144 | [Source](https://www.cdc.gov/mmwr/volumes/75/wr/mm7513a2.htm) | CDC totals span brands and substances; not Amanita-only causation. Critical warning and stop/consult instruction retained. |

### Verification and measured boundaries

- Fail-first tests cover source-bound transcription, daily-default provenance, zero-nutrition display units, exact banned aliases, nested geometry, mixed plant parts and approved eligibility consumers. Independent review caught and reproduced seven corrected-label export failures and held-marker deduplication suppressing an eligible source; both classes were fixed and rechecked. Export retains exact registry/original/corrected-text verification and unresolved-identity restrictions.
- Final named owner/consumer slice: **575 passed**. App: four regressions failed before the fix; **12 owner tests passed**, analyzer clean, independent caller review found no blockers. App research routing honors explicit false; source identities, factual quantities and safety routing remain unchanged. Ordinary native app rendering/new-catalog delivery is not claimed.
- Paired frozen-raw replay: **36 products, all Clean/Enrich/Score/blob calls completed**, zero errors, same immutable source manifest and unchanged capture fingerprints. Seven controls are byte-equivalent after volatile-field normalization. Ten daily-label limitations retain the one-serving calculation fallback but mark it defaulted. Product330882 changes from suppressed/unscored to provisional53.3 after broad grape identity is preserved; its dose and contributing-evidence blockers remain and prevent publication. All other overall scores and all product safety states are unchanged. This is bounded proof, not full-corpus closure.
- The earlier Wobenzym321405 fixture74.3/complete was already stale on main. Independent baseline and candidate captures of identical raw input have identical hashes at all four layers and produce71.2/partial. Selectively refresh only that fixture and record the existing-baseline cause; no new clinical inference or safety/amount change.
- All seven data files pass exact expected-entry `data_batch.py check`; no unexpected entries or count defects. Citation-content screen:22 matches/59 heuristic mismatches,0 unresolved.58 mismatches are existing backlog; one new heuristic mismatch is the explicitly rejected sage Foreword DOI, whose publisher/repository metadata was independently verified. **The automated screen is not green** and does not count as clinical approval; source-specific review supplies the bounded factual disposition. D062 full body remains unavailable and cannot supply efficacy credit. Interaction-citation diff:0 changed rules; no unrelated rule claim.
- Required local and whole-fast CI qualification/integration results are recorded in the existing LEDGER. Pending is not green. Private source hashes, full receipts and comparison artifacts are retained under `.claude/state/returned_batch_completion_20261026/`; original returned Markdown remains unchanged.

### One remaining list before final delivery

1. **Qualifying scoped decisions:** existing clinical/benchmark registers remain authoritative. Retain unresolved preparation, regimen, population and outcome decisions, authentic approval requirements, and specific manufacturer limitations. This correction batch does not sign all146 contributing records or374 preparation subjects. No request to repeat already accepted bounded decisions.
2. **Specific restoration/source boundaries:** omega3/niacin relationship and knotweed→marker credit require qualifying scoped support before restoration; FloraGLO and Pycnogenol qualification remains held. D062 publisher metadata is verified but full-body efficacy is not. Missing PQQ corrected Table4 and unresolved manufacturer/preparation facts remain limitations, not invented answers. Completed negative findings can remain excluded permanently.
3. **One necessary rebuilt candidate:** Clean fingerprints change in this batch, so Enrich-only or Score-only cannot deliver it. After integration and readiness inspection, operator runs the existing compute-only Clean→Enrich→Score command; no publish flag. A compute pass does not clear scientific holds or authorize publication.
4. **After that run:** verify every rebuilt assessment/dependency and warning, amounts/identities/held states, exports, original20 examples, then actual ordinary Flutter import/rendering and remaining release gates. Do not call old bundled/installed data proof of these source fixes.


### Combined CI failure reconciliation

Initial whole-fast40407509860 failed11 assertions across four shards and did not qualify integration. Reproduced every failure class locally: stale FloraGLO/Pycnogenol bonus eligibility; stale Perilla/Cascara numerical absorption pins and exact unknown inventory; stale sage access wording; synthetic hemp panel conflicting with the new content-bound correction; safety-copy length and semicolon constraints. Existing tests now explicitly pin the source-supported holds/unknowns/metadata and use the exact hemp panel. No safety validator or source guard was relaxed. Shortened Amanita/Yellow5 copy and replaced three semicolons with periods while retaining poisoning, hypersensitivity, mixture-evidence limits and stop/consult action. Full rationale remains in canonical reference/reason fields. Combined failure-class slice281passed. Additional identity consumers328passed.

Final36-label recapture after copy formatting completed successfully; all scores, pillar payloads and statuses are identical to the previous qualified replay. Prior33canaries passed; only supported copy formatting changed afterward. App full CI40405374984 passed in18m24s, protectedPR154 mergedf4d28c4d; docs-onlyPR155/CI40408485521 passed lightweight checks and mergedaea9eadc. Appmain alignedclean, completedbranches removed. Pipeline final local refresh and combined exact CI retry pending; no full corpus or publication.


Final wording check reproduced a related display defect: qualitative printed instructions were described as no daily directions. Existing dose explanation owners now say no daily amount, retaining the one-serving default and upper-limit warning.59owner/real-label tests pass;268493 remains28.6 with identical pillar scores/status, identity/amounts/safety unchanged. Independent review confirms display-only. All33rawcanaries pass again. Refreshed local checkpoint546passed/24declaredskips with strictguard. CI40409705304 was cancelled early as superseded, never counted green. Final combined candidate requires a fresh exact-source whole-fast checkpoint.


### Protected-merge review follow-through

Candidate dd6058191570b4aaa5ade28a3939f2a79b97585e passed all four full shards, skip guards and Merge readiness in CI40410067131. Normal protected merge still correctly refused two unresolved review conversations; no bypass used. One exposed an existing43662 display-geometry defect: actual label/correction owner places three fruit rows under the140mg fruit blend at ingredientRows[5], but display source overlay restored their old Reishi parent[3]. The review suggestion to retain parent[3] was not accepted blindly. Exact source and existing reviewed move were checked.

Fail-first regression reproduced wrong display parent. Existing43662 hierarchy provenance is now retained separately from its added beet identity correction, and the existing hierarchy owner marks the former parent affected so its stale child list is rebuilt. Immutable source paths and all quantities remain unchanged.141owner/integration tests pass; independent review reran the new regression and found no blockers. Three frozen labels replay Clean/Enrich/Score/blob successfully with unchanged scores/statuses; both cleaner and blob now show the correct fruit parent[5]. The handoff points directly to the active remaining-work section, and the single forwardable request now carries completed source work instead of requesting it again. Fresh exact-candidate CI is required for this output-changing follow-up; prior green evidence is retained but not represented as covering the later fix.


### Concurrent-main integration

Hierarchy candidate d826eaec77110eea99b3456287c7c1e2a6501624 passed all four full shards/skip guards and Merge readiness in CI40412535170; both verified review threads are resolved. While it ran, independent submission-identifier PR259 merged to main da80f7481. Strict protection correctly requires an up-to-date combined candidate. Preserved that work via clean merge9437ab5b0; no overwrite or bypass. Shared export diff only routes normalize_upc through the canonical formatted-GTIN/checksum owner. Combined exact-label/importer/GTIN/ownership slice261passed. Appmain remainsaea9eadc. User-authorized coordination with the other active chat requested a temporary main integration lane to avoid further concurrent checkpoint restarts. Combined local and exact whole-fast CI are required; earlier green source is not presented as proof of this composition.


## Final qualification and integration — October 26, 2026

The full18C/47D bounded correction batch is qualified and integrated. Exact combined candidate `e9734f756b5724baabc48c4b2e093398032420c8` passed all four whole-fast shards, every declared-skip guard, Validation scope and Merge readiness in [CI40414536231](https://github.com/seancheick/PharmaGuide_Pipeline/actions/runs/40414536231). Normal protected [PR258](https://github.com/seancheick/PharmaGuide_Pipeline/pull/258) merged at `31b3e7878a915e2a96dad37cc60d779bed32f029`; fetched ancestor check confirms the tested source is on origin/main. Concurrent identifier work from PR259 is preserved in that composition. Both corrected review conversations are resolved. No administrator bypass or force push. Completed local/remote source branch removed; primary checkout aligned with main.

Final combined local checkpoint:546passed/24declaredskips with strict skip guard. Combined owner/importer/export slice261passed; hierarchy141passed;33rawcanaries passed. Full36-label paired replay plus scoped final copy/hierarchy captures preserve the measured results and safety states described above. Real exported knotweed hold remains false while its declared75mg marker exposure survives. App candidatea8aa15ff passed full CI40405374984 and integrated through PR154; appmain source is unchanged by documentation-only PR155. Ordinary rebuilt-catalog delivery and native app rendering remain unverified.

No full corpus, export/import campaign, cloud data write or publication was performed. Six untracked user submissions and local supabase work were preserved. Source corrections are implemented, measured, reviewed and integrated; they are not marked rebuilt-closed. Required scientific approvals and exact source/preparation gaps remain in the existing registers and the active remaining list. In particular, the documented citation heuristic mismatch is not represented as an automated pass or scientific clearance.

Read-only startup and producer/app compatibility checks pass. Actual stage fingerprints select Clean as earliest required stage (114stale manifests before rebuilding). Operator command from the primary checkout:

```bash
source scripts/python_env.sh
PYTHON="$PG_PYTHON" bash batch_run_all_datasets.sh --pipeline-only
```

This computes Clean→Enrich→Score and stops. Publication remains separately gated by source-bound assessment completeness. Next proof is the rebuilt full-corpus invariant, identities/amounts/warnings/held states, exports and ordinary Flutter delivery including the original20examples. No further source edit is planned for this batch.
