# Evidence expansion — Wave 1 review packet (2026-09-17)

**Status: PENDING. Nothing in this packet has been applied.** No production data was written, no score moved, no scoring rule changed, no catalog rebuild, no release.

Claude authored every context as `source_verified_pending_clinical_review`. Approval is the owner's act. The reviewer string on any approval must say engineering owner — never clinician — unless a clinician signs.

Each PMID below was re-fetched live from PubMed after screening; every quote is a verbatim contiguous span of the live abstract, checked by `validate_wave1_contexts.py` and `verify_shortlist.py`.

## Decision summary

| identity | products | Ev=0 | Ev≤8 | contexts | proposal | scorer class |
|---|---:|---:|---:|---:|---|:--:|
| [Ginkgo](#ginkgo) | 124 | 49 | 57 | 5 | HOLD | B |
| [Isoflavones](#isoflavones) | 57 | 31 | 34 | 4 | HOLD | B |
| [Linoleic Acid](#linoleic-acid) | 73 | 24 | 40 | 4 | RECORD THE REVIEW STATE, CREATE NO SCORING RECORD | B |
| [Tribulus](#tribulus) | 50 | 28 | 33 | 5 | RECORD THE REVIEW STATE (identity state B), CREATE NO SCORING RECORD | B |
| [Horny Goat Weed (Epimedium)](#horny-goat-weed) | 51 | 28 | 28 | 1 | RECORD THE REVIEW STATE (identity state B), CREATE NO SCORING RECORD | B |
| [Gotu Kola](#gotu-kola) | 43 | 25 | 30 | 3 | DO NOT create a scoring record yet | B |
| [D-Ribose](#d-ribose) | 33 | 25 | 27 | 1 | HOLD | B |
| [Butterbur](#butterbur) | 29 | 25 | 26 | 4 | HOLD on safety grounds | A |
| [DHEA (Dehydroepiandrosterone)](#dhea) | 33 | 25 | 25 | 4 | HOLD | B |
| [Dandelion](#dandelion) | 57 | 21 | 27 | 1 | RECORD THE REVIEW STATE (identity state B), CREATE NO SCORING RECORD | B |

Scorer class: **A** = the current generic scorer can apply this evidence safely; **B** = the context is valid but the scorer is too coarse, so the production synthesis is held. This is an audit determination, not a production field.

## Ginkgo

`ginkgo` — 124 products, 29 brands, 140 label rows; Evidence mean 9.49, 49 at zero, 57 at ≤8. Review state today: not_reviewed.

**Label reality.** Measured label median 60 mg/day (p25 40, p75 120); 100 of 140 dosed rows are 'ginkgo (unspecified)' and 42 are 'ginkgo biloba extract (24% flavone glycosides)'. Every positive trial below used the branded standardised extract EGb 761 at 240 mg/day in diagnosed patients.

Measured label exposure: median 60 mg/day (p25 40, p75 120, min 0.12, max 2000) across 140 dosed rows. Source: inventory slim corpus, re-scored 2026-09-17.

**Publications vs trials.** 5 publications, 1 primary cohort (GEM, two publications) plus three reviews over overlapping EGb 761 and healthy-adult trial pools unique trials/cohorts, 0 independent replications. 19017911 and 20040554 are the same 3069-participant GEM cohort. 39895346 re-analyses subgroups of trials expected to sit inside 25114079's pool. Treating these five publications as five sources would badly overstate depth.

### Contexts (all pending)

**`ginkgo_gem_dementia_prevention_19017911`** — PMID 19017911 · rct · direct_rct · funding: independent

- Identity: botanical_preparation — botanical_species: Ginkgo biloba; plant_part: leaf
- Exposure: supplement_dose, route oral, dose 240 mg (verified)
- Population: 3069 community volunteers aged 75 years or older with normal cognition (n = 2587) or mild cognitive impairment (n = 482)
- Outcomes: incident_dementia_and_alzheimer_disease (primary/patient_important) → **null**
  - > Five hundred twenty-three individuals developed dementia (246 receiving placebo and 277 receiving G. biloba)
  - dose > Twice-daily dose of 120-mg extract of G. biloba (n = 1545) or placebo (n = 1524)
- Limitations: (1) The largest and best-powered ginkgo trial (NIH-funded, 6.1-year median follow-up) found no reduction in dementia incidence. (2) Dose was 240 mg/day — four times the measured label median of 60 mg/day. (3) Publishes as two papers with PMID 20040554 from the same GEM cohort; they are one trial, not two.

**`ginkgo_gem_cognitive_decline_20040554`** — PMID 20040554 · rct · companion_analysis · funding: independent

- Identity: botanical_preparation — botanical_species: Ginkgo biloba; plant_part: leaf
- Exposure: supplement_dose, route oral, dose 240 mg (verified)
- Population: 3069 community-dwelling participants aged 72 to 96 years (the GEM cohort)
- Outcomes: rate_of_cognitive_decline_memory_attention_language_executive (primary/patient_important) → **null**
  - > Annual rates of decline in z scores did not differ between G. biloba and placebo groups in any domains
  - dose > Twice-daily dose of 120-mg extract of G. biloba (n = 1545) or identical-appearing placebo (n = 1524)
- Limitations: (1) SAME COHORT as PMID 19017911 (GEM). Counting both as independent evidence would double-count one trial. (2) Null across every cognitive domain at 240 mg/day.

**`ginkgo_healthy_cognition_meta_23001963`** — PMID 23001963 · meta_analysis · meta_analysis · funding: unreported

- Identity: botanical_preparation — botanical_species: Ginkgo biloba; plant_part: leaf
- Exposure: supplement_dose, route oral, dose not resolved mg (source_not_reported)
- Population: Healthy individuals; memory n = 1132, executive function n = 534, attention n = 910
- Outcomes: memory_executive_function_attention (primary/patient_important) → **null**
  - > We report that G. biloba had no ascertainable positive effects on a range of targeted cognitive functions in healthy individuals.
  - > Meta-regressions showed that effect sizes were not related to participant age, duration of the trial, daily dose, total dose or sample size.
- Limitations: (1) This is the population that actually buys ginkgo — healthy adults seeking memory support — and the pooled effect is null across memory, executive function and attention. (2) The meta-regression found no dose relationship, so a higher label dose would not be expected to help either. (3) Included trial PMIDs not listed; overlap with the GEM trial is unresolved.

**`ginkgo_egb761_dementia_meta_25114079`** — PMID 25114079 · meta_analysis · meta_analysis · funding: unreported

- Identity: branded_material — branded_material: EGb 761; botanical_species: Ginkgo biloba; plant_part: leaf; standardization: described by the source only as 'standardized Ginkgo biloba extract EGb761'; the standardisation profile is not stated in the abstract
- Exposure: supplement_dose, route oral, dose 240 mg (verified)
- Population: 2,561 patients with cognitive impairment and dementia across nine trials of 22-26 weeks
- Outcomes: cognition_change_score (primary/patient_important) → **positive**; activities_of_daily_living (primary/patient_important) → **positive**
  - > the weighted mean differences in change scores for cognition were in favor of EGb761 compared to placebo (-2.86, 95%CI -3.18; -2.54)
  - > All these benefits are mainly associated with EGb761 at a dose of 240 mg/day.
  - dose > All these benefits are mainly associated with EGb761 at a dose of 240 mg/day.
- Limitations: (1) Benefit is tied to ONE branded standardised extract (EGb 761) at 240 mg/day in diagnosed patients — not to ginkgo generally. (2) 100 of 140 label rows declare only 'ginkgo (unspecified)'; nothing on those labels establishes EGb 761 equivalence. (3) Treatment of diagnosed cognitive impairment, not memory support in healthy adults (where PMID 23001963 is null). (4) The abstract does not state the standardisation profile, so material equivalence cannot be checked from this source.

**`ginkgo_egb761_mild_dementia_meta_39895346`** — PMID 39895346 · meta_analysis · meta_analysis · funding: industry

- Identity: branded_material — branded_material: EGb 761; botanical_species: Ginkgo biloba; plant_part: leaf; standardization: not stated in the abstract beyond the EGb 761 designation
- Exposure: supplement_dose, route oral, dose 240 mg (verified)
- Population: 782 patients with mild dementia (SKT total scores 9 to 15) pooled from four trials
- Outcomes: cognition_global_assessment_adl_quality_of_life (primary/patient_important) → **positive**
  - > Data of patients with mild dementia (defined as the SKT Short Cognitive Performance Test total scores from 9 to 15) were selected.
  - dose > Treatment with 240 mg EGb 761 daily was significantly superior to placebo in cognition (p = 0.04), global assessment (p = 0.01), activities of daily living (p = 0.01) and quality of life (p = 0.02)
- Limitations: (1) This is a subgroup meta-analysis: patient subgroups were selected out of four trials, so it re-analyses existing EGb 761 trials rather than adding independent replication. (2) Its trials very likely sit inside the pool of PMID 25114079 — membership extraction pending. (3) EGb 761 branded material at 240 mg/day in diagnosed mild dementia. (4) The extract's manufacturer sponsors much of the EGb 761 literature; funding recorded as industry.

### Proposed synthesis (for your decision)

**HOLD — do not create a scoring record**

Ginkgo is the clearest split in Wave 1: null for prevention in the largest independent trial (GEM, n=3069, 240 mg/day, 6.1 years) and null for cognition in healthy adults (meta-analysis, no dose relationship), but positive for the branded EGb 761 extract at 240 mg/day in diagnosed dementia. Labels deliver a median 60 mg/day of mostly unspecified ginkgo to healthy buyers. A single record cannot carry that split, and the scorer cannot express material, dose or population.

<details><summary>if owner approves anyway</summary>

```json
{
 "study_type": "systematic_review_meta",
 "evidence_level": "ingredient-human",
 "effect_direction": "mixed",
 "min_clinical_dose": null,
 "note": "A 'mixed' record would still credit 60 mg unspecified-ginkgo products with EGb 761 dementia-treatment evidence."
}
```
</details>

- Evidence strength: large and high quality, but split by material, dose and population
- Applicability to labels: not applicable at the measured label median; would require EGb 761 identity plus a 240 mg/day dose to even be considered
- Review completeness: bounded search documented in wave1_search_log.json (152 records screened, 79 kept)
- Scorer compatibility: **class B** — Positive evidence is confined to one branded standardised extract (EGb 761) at 240 mg/day in diagnosed dementia patients, while the consumer-relevant meta-analysis in healthy adults is null and the measured label median is 60 mg/day of mostly unspecified ginkgo. The generic scorer has no population gate and no branded-material equivalence test, so a positive record would transfer dementia-treatment evidence to 124 general-population products at a quarter of the studied dose.

### Authoritative guidance (recorded as references, not study contexts)

The frozen context contract requires a PMID and a regulator assessment has none, so these use the shape the registry already has for non-PubMed sources.

**EMA Committee on Herbal Medicinal Products (HMPC)** — Ginkgo folium — EU herbal monograph (EMA/HMPC/321097/2012); public summary EMA/HMPC/324406/2015  
https://www.ema.europa.eu/en/medicines/herbal/ginkgo-folium · retrieved 2026-09-17 · HMPC conclusions section expanded and read on retrieval date

> The HMPC concluded that ginkgo leaf medicines containing the dry extract can be used to improve the age-related cognitive impairment (worsening of mental abilities) and quality of life of adults with mild dementia.
> The HMPC also concluded that, on the basis of their long-standing use, ginkgo leaf medicines containing the powdered leaf can be used for the relief of heaviness in the legs and the sensation of cold hands and feet that may occur with minor circulation problems.
> Ginkgo leaf medicines should only be used in adults. If symptoms of dementia do not improve after 3 months or if symptoms worsen during the treatment, a doctor should be consulted.

*The monograph's well-established-use conclusion is for medicines containing the DRY EXTRACT in adults with mild dementia — the same material-and-population boundary the trials show. The powdered leaf gets only traditional-use status for minor circulation symptoms. 100 of 140 catalog rows declare unspecified ginkgo at a median 60 mg/day to general buyers, so the regulatory context reinforces the hold rather than loosening it.*

### Handoffs to other owners (no clinical interpretation here)

| PMID | role | destination | reason |
|---|---|---|---|
| 18383637 | safety | safety/CAERS owner | Haemorrhage-risk review for ginkgo extracts — bleeding safety belongs to the safety owner. |
| 40198642 | safety | safety/CAERS owner | Bleeding risk and coagulation observational evidence. |
| 11826216 | safety | safety/CAERS owner | Ginkgo safety signal flagged in screening. |
| 17010102 | interaction | ingredient_interaction_rules / curated_interactions owner | Ginkgo drug-interaction study. |
| 32478963 | interaction | ingredient_interaction_rules / curated_interactions owner | Ginkgo drug-interaction study. |
| 23477707 | interaction | ingredient_interaction_rules / curated_interactions owner | Ginkgo drug-interaction study. |
| 30761076 | interaction | ingredient_interaction_rules / curated_interactions owner | Ginkgo drug-interaction study. |
| 27186927 | interaction | ingredient_interaction_rules / curated_interactions owner | Ginkgo drug-interaction study. |

### High-risk queue: anticoagulation_bleeding, perioperative, medication_interactions

Flagged for eventual clinician countersignature; it does not block the owner review above.

**Actions:** approve · approve with correction · reject · hold · request adjudication · request more source review

---

## Isoflavones

`isoflavones` — 57 products, 11 brands, 60 label rows; Evidence mean 6.81, 31 at zero, 34 at ≤8. Review state today: not_reviewed.

**Label reality.** Labels deliver isolated/concentrated isoflavone extracts (soy hypocotyl, soy germ, NovaSoy, red clover); measured median 80 mg/day (p25 36, p75 150). Studied supplement doses overlap this range, which is unusual in Wave 1.

Measured label exposure: median 80 mg/day (p25 35.75, p75 150, min 20, max 750) across 60 dosed rows. Source: inventory slim corpus, re-scored 2026-09-17.

**Publications vs trials.** 4 publications, unresolved — 52 and 63 trial reviews with substantial expected overlap, plus a 62-trial symptom review unique trials/cohorts, at most 1 for BMD (two reviews of overlapping trial sets are not two confirmations) independent replications. Review membership is extraction_pending for all four. Counting these as four independent sources would inflate depth for one largely shared trial pool.

### Contexts (all pending)

**`isoflavones_bmd_meta_31290343`** — PMID 31290343 · meta_analysis · meta_analysis · funding: unreported

- Identity: exact_form — chemical_form: soy isoflavones (aglycone equivalents: genistein, daidzein, glycitein)
- Exposure: supplement_dose, route oral, dose not resolved mg (source_not_reported)
- Population: 52 randomized controlled trials of soy isoflavone consumption; subgroups by weight, duration and location
- Outcomes: lumbar_spine_hip_femoral_neck_bmd (primary/surrogate) → **positive**; bone_turnover_markers (secondary/surrogate) → **mixed**
  - > Consumption of soy isoflavones caused significant improvement in BMD of lumbar spine (mean difference (MD) = 0.76%; 95% CI: 0.09, 1.42%; p = 0.03), hip (MD = 0.22%; 95% CI: 0.02, 0.42%; p = 0.04), and femoral neck (MD = 2.27%; 95% CI: 1.22,…
  - > osteocalcin and bone alkaline phosphatase did not change
- Limitations: (1) Bone mineral density is a surrogate: no fracture outcome is reported. (2) Effect sizes are small (0.22-2.27% mean difference) and were significant mainly in normal-weight subjects and interventions longer than a year. (3) 'Consumption of soy isoflavones' pools supplement and food-matrix exposures; the abstract states no dose, so a label-comparable amount cannot be attached from this record alone. (4) Included trial PMIDs are not listed; overlap with PMID 37875614 (63 trials) is unresolved and the two reviews are NOT independent replications.

**`isoflavones_postmenopausal_bmd_meta_37875614`** — PMID 37875614 · meta_analysis · meta_analysis · funding: unreported

- Identity: exact_form — chemical_form: soy isoflavones (aglycone equivalents: genistein, daidzein, glycitein)
- Exposure: supplement_dose, route oral, dose 50 mg (verified)
- Population: Postmenopausal women; 63 RCTs, isoflavone interventions n = 4,754 versus placebo n = 4,272
- Outcomes: bmd_lumbar_spine_femoral_neck_distal_radius (primary/surrogate) → **positive**
  - > isoflavone interventions significantly improved BMD at the lumbar spine (MD = 0.0175 g/cm2; 95% CI, 0.0088 to 0.0263, P < 0.0001), femoral neck (MD = 0.0172 g/cm2; 95% CI, 0.0046 to 0.0298, P = 0.0073), and distal radius (MD = 0.0138 g/cm2;…
  - dose > the isoflavone intervention was effective for improving BMD when the duration was ≥ 12 months and when the intervention contained genistein of at least 50 mg/day
- Limitations: (1) Population is postmenopausal women only; the generic scorer cannot gate on population, so a positive record would also credit products aimed at men or premenopausal users. (2) The 50 mg/day threshold is GENISTEIN content within the intervention, not total isoflavone content, and labels declare total isoflavones — the two cannot be equated without the product's genistein fraction. (3) Surrogate endpoint (BMD), effect sizes small; benefit required at least 12 months of use. (4) Substantially overlapping trial set with PMID 31290343.

**`isoflavones_menopausal_symptoms_meta_27327802`** — PMID 27327802 · meta_analysis · meta_analysis · funding: unreported

- Identity: exact_form — chemical_form: soy isoflavones (aglycone equivalents: genistein, daidzein, glycitein)
- Exposure: supplement_dose, route oral, dose not resolved mg (source_not_reported)
- Population: 6653 women across 62 randomized clinical trials of plant-based therapies
- Outcomes: daily_hot_flashes (primary/patient_important) → **positive**; vaginal_dryness_score (primary/patient_important) → **positive**; night_sweats (primary/patient_important) → **null**
  - > Individual phytoestrogen interventions such as dietary and supplemental soy isoflavones were associated with improvement in daily hot flashes (pooled mean difference of changes, -0.79 [-1.35 to -0.23])
  - > but not in the number of night sweats (pooled mean difference of changes, -2.14 [95% CI, -5.57 to 1.29])
- Limitations: (1) Effect is modest: about 0.79 fewer hot flashes per day. (2) Night sweats showed no significant reduction — a mixed picture within the same symptom cluster. (3) 74% of included trials had a high risk of bias in three or more domains, and the authors call the evidence suboptimal and heterogeneous. (4) The analysis pools dietary and supplemental soy isoflavones with other phytoestrogens; the isoflavone-specific estimate is the one recorded here. (5) Menopausal population; no dose stated in the abstract.

**`isoflavones_estrogenicity_biomarkers_meta_39433088`** — PMID 39433088 · meta_analysis · meta_analysis · funding: unreported

- Identity: exact_form — chemical_form: soy isoflavones (aglycone equivalents: genistein, daidzein, glycitein)
- Exposure: supplement_dose, route oral, dose 75 mg (verified)
- Population: Postmenopausal women; 40 trials, 52 trial comparisons, n = 3285, median reported dose 75 mg/d over a median of 24 weeks
- Outcomes: estrogenicity_endometrial_thickness_vmi_fsh_estradiol (primary/surrogate) → **null**
  - > Soy isoflavones had no statistically significant effect on any measure of estrogenicity
  - > The certainty of evidence was high to moderate for all outcomes.
  - dose > We included 40 trials (52 trial comparisons, n = 3285) assessing the effect of a median reported dose of 75 mg/d of soy isoflavones in substitution for non-isoflavone controls over a median of 24 wk.
- Limitations: (1) This is a safety/mechanism question (do isoflavones act like estrogen), not an efficacy question; the null result is reassurance about estrogenic risk. (2) Certainty is high to moderate here, in contrast to the symptom literature — do not average the two. (3) Postmenopausal women only.

### Proposed synthesis (for your decision)

**HOLD — do not apply a generic production record (owner decision 2026-09-17)**

Two large meta-analyses (52 and 63 RCTs) find small BMD gains and a 62-trial review finds a modest hot-flash and vaginal-dryness benefit, and the measured label median (80 mg/day) sits inside the studied range — the dose gap that blocks the other Wave 1 identities does not apply here. The blocker is population: every positive result is in peri/postmenopausal women. clinical_applicability.py already carries a studied_population string into its decision (scripts/clinical_applicability.py:241) but never compares it to anything, and the product's target_population is read only by the probiotic lane (studied_formulas.py). So approving this record would credit every isoflavone product, including those marketed to men. Holding the evidence is correct; adding a population gate belongs to the applicability owner, not to this project.

<details><summary>fields if population is ever enforced</summary>

```json
{
 "study_type": "systematic_review_meta",
 "evidence_level": "ingredient-human",
 "effect_direction": "positive_weak",
 "min_clinical_dose": null,
 "dose_note": "No min_clinical_dose: the only stated threshold (genistein >= 50 mg/day) is a fraction of total isoflavones, which labels do not declare."
}
```
</details>

**Decisions needed from you:**
- Population: all positive evidence is in postmenopausal women; the generic scorer has no population gate, so approving this record credits every isoflavone product, including those marketed to men. Accept, or wait for a population mechanism?
- Depth: four reviews over largely overlapping trial pools must not be counted as four independent sources; the record should cite them without claiming replication.

- Evidence strength: moderate volume, small effects, mixed certainty (high-to-moderate for the estrogenicity null; poor for symptom trials)
- Applicability to labels: dose-applicable (median 80 mg/day within studied range); population applicability unresolved
- Review completeness: bounded search documented in wave1_search_log.json (155 records screened, 92 kept)
- Scorer compatibility: **class B** — Evidence is materially population-specific (peri/postmenopausal women) and the generic scorer has no population gate; applying it would transfer menopause evidence to every consumer.

### Handoffs to other owners (no clinical interpretation here)

| PMID | role | destination | reason |
|---|---|---|---|
| 35399656 | interaction | ingredient_interaction_rules / curated_interactions owner | Crossover trial of ~80 mg/day soy isoflavone extract with rosuvastatin pharmacokinetics — a PK interaction question, not efficacy. |
| 35685887 | interaction | ingredient_interaction_rules / curated_interactions owner | Crossover trial of ~80 mg/day soy isoflavone extract with simvastatin pharmacokinetics — PK interaction. |
| 21177797 | safety | safety/CAERS owner | Two-year safety trial of 80-120 mg aglycone-equivalent soy hypocotyl isoflavones; tolerability evidence for the safety lane. |
| 24312387 | safety | safety/CAERS owner | Systematic review touching breast-cancer-related concerns for isoflavones; belongs with the safety/contraindication owner. |

### High-risk queue: hormonal, breast_cancer_history, pregnancy_and_fertility

Flagged for eventual clinician countersignature; it does not block the owner review above.

**Actions:** approve · approve with correction · reject · hold · request adjudication · request more source review

---

## Linoleic Acid

`linoleic_acid` — 73 products, 19 brands, 73 label rows; Evidence mean 7.23, 24 at zero, 40 at ≤8. Review state today: not_reviewed.

**Label reality.** Labels declare linoleic acid as a component of seed/nut oils; measured median 362 mg/day (p25 132, p75 530, max 8,000). Every trial below dosed 7.5-20 g/day or changed whole-diet fat composition — 20-40x the median label amount.

Measured label exposure: median 362.5 mg/day (p25 132, p75 530, min 4, max 8000) across 72 dosed rows. Source: inventory slim corpus, re-scored 2026-09-17.

**Publications vs trials.** 4 publications, 3 unique trials/cohorts, 0 independent replications. One meta-analysis (membership pending) plus three separate trials of different exposures and endpoints. No two studies replicate the same question.

### Contexts (all pending)

**`linoleic_acid_inflammatory_markers_meta_28752873`** — PMID 28752873 · meta_analysis · meta_analysis · funding: unreported

- Identity: exact_form — chemical_form: linoleic acid (18:2 n-6)
- Exposure: dietary_substitution, route oral, dose not resolved mg (source_not_reported)
- Population: 1377 subjects across 30 randomized controlled studies in adults
- Outcomes: c_reactive_protein (primary/surrogate) → **null**; tnf_il6_adiponectin_mcp1 (primary/surrogate) → **null**
  - > No significant effect of higher LA intake was observed for cytokines
  - > the C-reactive protein (CRP) concentration was not significantly affected by increasing LA intake (SMD = 0.09, 95% CI: -0.05 to 0.24)
- Limitations: (1) Exposure is increased dietary LA intake, not a 362 mg capsule; the pooled trials changed diets or used gram-level oils. (2) All endpoints are inflammatory biomarkers, not patient-important outcomes. (3) The one directional signal is a subgroup/meta-regression hint that large intake increases may RAISE CRP — a possible harm signal, not a benefit. (4) Included trial PMIDs not listed in the abstract; overlap with the other LA reviews is unresolved.

**`linoleic_acid_oxidative_dna_damage_rct_12504167`** — PMID 12504167 · rct · direct_rct · funding: unreported

- Identity: exact_form — chemical_form: linoleic acid (18:2 n-6)
- Exposure: supplement_dose, route oral, dose 7500, 15000 mg (verified)
- Population: Thirty healthy volunteers
- Outcomes: oxidative_dna_damage_8_oxodg (primary/surrogate) → **null**
  - > no significant increase in oxidative DNA damage, measured as relative amounts of 7,8-dihydro-8-oxo-2'-deoxyguanosine (8-oxodG) in DNA from peripheral lymphocytes, was observed in both high and intermediate linoleic acid-supplemented groups
  - dose > Thirty volunteers received during 6 weeks either a high dose of linoleic acid (15 g/day), an intermediate dose of linoleic acid (7.5 g/day) or an isocaloric supplement without linoleic acid (15 g palmitic acid/day)
- Limitations: (1) This is a safety/mechanism question (does LA cause oxidative DNA damage), not a benefit question; a null result here is reassurance, not efficacy. (2) Doses of 7.5-15 g/day are 20-40x the measured median label amount. (3) n=30, 6 weeks, surrogate endpoint.

**`linoleic_acid_vs_marine_n3_crossover_40058591`** — PMID 40058591 · crossover_rct · direct_rct · funding: unreported

- Identity: exact_form — chemical_form: linoleic acid (18:2 n-6), delivered as safflower oil
- Exposure: supplement_dose, route oral, dose 15000, 20000 mg (verified)
- Population: Females (n = 16) and males (n = 23) aged 30-70 years with abdominal obesity
- Outcomes: circulating_inflammatory_markers (primary/surrogate) → **null**; systolic_blood_pressure (secondary/surrogate) → **negative**
  - > no differences between n-3 and n-6 were found for any circulatory inflammatory markers
  - > significant differences between treatments in relative change scores were found for systolic blood pressure (n-3 vs. n-6: -1.81% vs. 2.61%, P = 0.003)
  - dose > supplemented with 3-4 g/d EPA/DHA (fish oil) or 15-20 g/d LA (safflower oil) for 7 weeks
- Limitations: (1) Head-to-head against fish oil, not against placebo: 'no difference in inflammatory markers' is not evidence of benefit. (2) The one significant between-treatment difference favours n-3; the LA arm's systolic blood pressure change was in the opposite direction. (3) 15-20 g/day of LA as safflower oil is far above any label serving. (4) Crossover, n=39, surrogate endpoints.

**`linoleic_acid_epa_status_diet_rct_42280457`** — PMID 42280457 · rct · direct_rct · funding: unreported

- Identity: exact_form — chemical_form: linoleic acid (18:2 n-6)
- Exposure: dietary_substitution, route oral, dose not resolved mg (source_not_reported)
- Population: Fifty-two healthy adults completing a 12-week controlled diet intervention
- Outcomes: plasma_epa_status (primary/surrogate) → **negative**
  - > High LA exposure resulted in marked reductions in plasma n-3 eicosapentaenoic acid (EPA) and eicosatetraenoic acid (ETA) concentrations compared with the Low-LA arm
- Limitations: (1) Exposure is percentage of dietary energy, not a supplement dose; it cannot be converted to a label serving without inventing an intake assumption. (2) Finding is a lowering of n-3 status at high LA intake — relevant to omega-6/omega-3 balance messaging, not a benefit claim. (3) Surrogate fatty-acid and oxylipin endpoints only.

### Proposed synthesis (for your decision)

**RECORD THE REVIEW STATE, CREATE NO SCORING RECORD**

A documented bounded search found no human trial of a label-comparable linoleic acid exposure (median 362 mg/day) reporting a patient-important benefit. What exists is gram-level or whole-diet exposure against surrogate endpoints, mostly null, with two unfavourable signals (CRP at high intakes, lowered EPA status). The honest outcome is identity state B — 'reviewed, no qualifying evidence in the documented scope' — which makes Evidence 0 interpretable for 24 products instead of leaving it unexplained.

<details><summary>if owner approves anyway</summary>

```json
{
 "study_type": "systematic_review_meta",
 "evidence_level": "ingredient-human",
 "effect_direction": "null",
 "min_clinical_dose": null,
 "note": "Under the current scorer a null record would ADD points (0.25 multiplier) to products whose evidence showed no benefit \u2014 see GENERIC_EVIDENCE_NULL_DIRECTION_REVIEW.md."
}
```
</details>

- Evidence strength: adequate volume, consistently null on surrogate endpoints at supra-label exposures
- Applicability to labels: not applicable — 20-40x dose gap and dietary-substitution exposures
- Review completeness: bounded search documented in wave1_search_log.json (160 records screened, 23 kept)
- Scorer compatibility: **class B** — Evidence is gram-level supplementation or whole-diet substitution against surrogate endpoints; the scorer has no exposure-basis concept, so dietary-substitution trials would become capsule efficacy at a 20-40x dose gap.

### Handoffs to other owners (no clinical interpretation here)

| PMID | role | destination | reason |
|---|---|---|---|
| 28752873 | safety | safety/CAERS owner | Meta-regression signal that large LA intake increases may raise CRP — a possible harm direction worth the safety lane's attention. |
| 23386268 | safety | safety/CAERS owner | Screening flagged this LA-replacement trial for a safety-relevant result; belongs to the safety owner, not the efficacy record. |
| 27071971 | safety | safety/CAERS owner | Screening flagged a safety-relevant cholesterol-lowering-diet result; safety lane, not efficacy. |

### High-risk queue: cardiovascular

Flagged for eventual clinician countersignature; it does not block the owner review above.

**Actions:** approve · approve with correction · reject · hold · request adjudication · request more source review

---

## Tribulus

`tribulus` — 50 products, 14 brands, 56 label rows; Evidence mean 6.23, 28 at zero, 33 at ≤8. Review state today: not_reviewed.

**Label reality.** Sold for testosterone support and athletic performance. The two primary trials dosed 750-770 mg/day as a sole agent; the syntheses cover 400-750 mg/day for 1-3 months. See label_exposure_measured for what labels actually deliver.

Measured label exposure: median 500 mg/day (p25 250, p75 1000, min 20, max 1500) across 55 dosed rows. Source: inventory slim corpus, re-scored 2026-09-17.

**Publications vs trials.** 5 publications, 2 primary trials plus 3 syntheses over overlapping trial pools unique trials/cohorts, 0 independent replications. The three reviews draw on overlapping small Tribulus trials (10 studies / 483 men in the largest). They are not independent confirmations of each other, and the two primary trials authored earlier are likely inside their pools — membership extraction pending.

### Contexts (all pending)

**`tribulus_idiopathic_infertility_rct_27337519`** — PMID 27337519 · rct · direct_rct · funding: unreported

- Identity: botanical_preparation — botanical_species: Tribulus terrestris; plant_part: not_stated
- Exposure: supplement_dose, route oral, dose 750 mg (verified)
- Population: Thirty randomized male patients complaining of idiopathic infertility
- Outcomes: serum_testosterone_lh_and_semen_parameters (primary/surrogate) → **null**
  - > No statistically significant difference was observed in the levels of testosterone (total and free) and LH and semen parameters (sperm concentration or motility, or abnormal forms) before and after the treatment.
  - > Tribulus terrestris was ineffective in the treatment of idiopathic infertility.
  - dose > They were given Tribulus terrestris (750 mg) in three divided doses for three months.
- Limitations: (1) Before-after comparison in 30 patients; the abstract describes no placebo control group. (2) Directly tests the marketed testosterone claim and finds nothing. (3) Plant part and extract standardisation are not stated.

**`tribulus_crossfit_performance_rct_34836225`** — PMID 34836225 · rct · direct_rct · funding: unreported

- Identity: botanical_preparation — botanical_species: Tribulus terrestris; plant_part: not_stated
- Exposure: supplement_dose, route oral, dose 770 mg (verified)
- Population: 30 healthy CrossFit-trained males
- Outcomes: body_composition_hormonal_response_and_performance (primary/patient_important) → **null**
  - > There were no significant group x time interactions for the outcomes of the study except for testosterone levels and bench press performance (p < 0.05).
  - dose > a total of 30 healthy CrossFit®-trained males were randomly allocated to receive either 770 mg of TT supplementation or a placebo daily for 6 weeks
- Limitations: (1) Single-blind, n=30, 6 weeks. (2) Most outcomes null; the two exceptions (testosterone, bench press) are secondary signals within a null primary picture and must not be reported as 'improves performance'. (3) Co-therapy: all participants were training.

**`tribulus_erectile_function_testosterone_review_40219032`** — PMID 40219032 · systematic_review · systematic_review · funding: unreported

- Identity: botanical_preparation — botanical_species: Tribulus terrestris; plant_part: not_stated
- Exposure: supplement_dose, route oral, dose 400, 750 mg (verified)
- Population: 483 men aged 16-70 across 10 studies: healthy men (5 studies), oligozoospermia, erectile dysfunction, ED with hypogonadism (2), unexplained infertility
- Outcomes: erectile_function (primary/patient_important) → **mixed**; serum_testosterone (primary/surrogate) → **null**
  - > TT supplementation has a low level of evidence regarding its effectiveness in improving erectile function in men with erectile dysfunction, and no robust evidence was found for increasing testosterone levels.
  - > Eight out of ten studies did not report significant changes in androgen profile following TT supplementation
  - dose > TT supplementation at doses of 400 to 750 mg/d for 1 to 3 months improved erectile dysfunction in 3 of the 5 studies that assessed this parameter.
- Limitations: (1) This is the strongest synthesis for the marketed claims and it splits them: a LOW-LEVEL-evidence signal for erectile function in men WITH erectile dysfunction, and no robust evidence for raising testosterone. (2) The review records low methodological quality for 50% of the included studies, and one included study had no control group. (3) The two studies showing a testosterone increase were intra-group changes of low clinical magnitude (60-70 ng/dL) in men with hypogonadism — a clinical population, not general consumers. (4) Dose range 400-750 mg/d for 1-3 months.

**`tribulus_testosterone_booster_review_37697053`** — PMID 37697053 · systematic_review · systematic_review · funding: unreported

- Identity: botanical_preparation — botanical_species: Tribulus terrestris; plant_part: not_stated
- Exposure: supplement_dose, route oral, dose not resolved mg (source_not_reported)
- Population: 52 studies across 27 proposed testosterone boosters in male athletes, men with late-onset hypogonadism, infertile men and healthy men; 4 studies of Tribulus terrestris
- Outcomes: total_testosterone_versus_placebo (primary/surrogate) → **null**
  - > Our findings indicate that most fail to increase total testosterone.
  - > 10 studies of cholecalciferol; 5 zinc/magnesium; 4 Tribulus terrestris and creatine
- Limitations: (1) A cross-ingredient review: Tribulus is one of 27 boosters assessed, contributing 4 studies, and it is not named among the exceptions the review considers effective. (2) No Tribulus-specific pooled estimate or dose is given in the abstract. (3) Directly addresses the marketed testosterone claim at synthesis level.

**`tribulus_sport_health_biomarkers_review_35954909`** — PMID 35954909 · systematic_review · systematic_review · funding: unreported

- Identity: botanical_preparation — botanical_species: Tribulus terrestris; plant_part: not_stated
- Exposure: supplement_dose, route oral, dose not resolved mg (source_not_reported)
- Population: Physically active adult males; 7 studies met inclusion from 340 records
- Outcomes: muscle_damage_markers_and_hormonal_behaviour (primary/surrogate) → **null**
  - > there was no clear evidence of the beneficial effects of TT supplementation on muscle damage markers and hormonal behavior
  - > no TT-induced toxicity was reported
- Limitations: (1) Seven studies only; the review calls for more research. (2) Covers the sports-performance marketing claim at synthesis level and finds no clear benefit. (3) No dose stated in the abstract.

### Proposed synthesis (for your decision)

**RECORD THE REVIEW STATE (identity state B), CREATE NO SCORING RECORD**

Corrected after adding the higher-level syntheses the owner asked for, which changed the conclusion rather than confirming it. 'Null across the board' would have been wrong: the 2025 systematic review reports that 400-750 mg/d improved erectile dysfunction in 3 of 5 studies that measured it — while stating this is a LOW level of evidence, in men with diagnosed erectile dysfunction, with 50% of studies at low methodological quality. For the two claims these products actually market, the syntheses are consistent: no robust testosterone increase (8 of 10 studies showed no androgen change; a cross-booster review finds most fail) and no clear sports-performance benefit. So the honest state is reviewed-with-no-qualifying-evidence for testosterone and performance, with a low-level, population-specific ED signal that the generic scorer cannot gate.

- Evidence strength: two small null primary trials; three syntheses — null for testosterone and performance, low-level positive for erectile dysfunction in diagnosed men
- Applicability to labels: no qualifying evidence for the marketed testosterone or performance claims; the ED signal is confined to a diagnosed population the scorer cannot express
- Review completeness: bounded search documented in wave1_search_log.json, extended 2026-09-17 with a synthesis-level query at owner request (see the tribulus_synthesis_supplement entry)
- Scorer compatibility: **class B** — The only positive signal (erectile function, low level of evidence) is confined to men with diagnosed erectile dysfunction, and the scorer has no population gate; the marketed testosterone and performance claims are null. Sole-agent versus combination also cannot be distinguished, so any record risks importing combination results.

**Actions:** approve · approve with correction · reject · hold · request adjudication · request more source review

---

## Horny Goat Weed (Epimedium)

`horny_goat_weed` — 51 products, 9 brands, 55 label rows; Evidence mean 4.86, 28 at zero, 28 at ≤8. Review state today: not_reviewed.

**Label reality.** Measured label median 50 mg/day (p25 12.5, p75 1,000); sold for libido, erectile function, testosterone and bone health.

Measured label exposure: median 50 mg/day (p25 12.5, p75 1000, min 10, max 1000) across 55 dosed rows. Source: inventory slim corpus, re-scored 2026-09-17.

**Publications vs trials.** 1 publications, 1 unique trials/cohorts, 0 independent replications. One pharmacokinetic trial. No controlled efficacy trial of the marketed indications exists in the documented search scope.

### Contexts (all pending)

**`epimedium_prenylflavonoid_pk_30522143`** — PMID 30522143 · rct · mechanistic_study · funding: unreported

- Identity: botanical_preparation — botanical_species: Epimedium; plant_part: leaf; standardization: defined Epimedium prenylflavonoid extract (icariin, icariside I, icariside II, icaritin, desmethylicaritin)
- Exposure: supplement_dose, route oral, dose 370, 740, 1110 mg (verified)
- Population: 30 healthy male subjects
- Outcomes: prenylflavonoid_metabolite_pharmacokinetics (primary/surrogate) → **unresolved**
  - > Epimedium prenylflavonoid extracts were well tolerated and no adverse effects were observed.
  - > Levels of Epimedium prenylflavonoid metabolites observed in this study were consistent with levels demonstrated to have anti-osteoporotic effects in cellular and animal studies.
  - dose > A single oral dose of 370, 740, or 1110 mg of a standardized Epimedium prenylflavonoid extract was administered to 30 healthy male subjects in a randomized, placebo-controlled trial.
- Limitations: (1) Pharmacokinetics and tolerability only — there is NO efficacy endpoint in this trial. Recorded here as non-efficacy context; its canonical clinical interpretation belongs to the PK/interaction owner. (2) The abstract's bridge to 'anti-osteoporotic effects' is explicitly to cellular and animal studies; that is mechanism, not human efficacy. (3) Single doses in healthy men; nothing about chronic use or the marketed libido/testosterone claims. (4) evidence_role is recorded as mechanistic_study because the frozen contract's EVIDENCE_ROLE vocabulary has no pharmacokinetic value; flagged in CHECKPOINT.md rather than extended for one case.

### Proposed synthesis (for your decision)

**RECORD THE REVIEW STATE (identity state B), CREATE NO SCORING RECORD**

A documented bounded search found no controlled human efficacy trial of Epimedium for libido, erectile function, testosterone or bone health. The only human interventional study is a single-dose pharmacokinetic and tolerability trial. Evidence 0 for these 51 products is correct and should be shown as 'reviewed — no qualifying evidence found', not as 'not yet reviewed'.

- Evidence strength: none for marketed indications
- Applicability to labels: not applicable — no efficacy evidence to apply
- Review completeness: bounded search documented in wave1_search_log.json (11 records screened, 9 kept)
- Scorer compatibility: **class B** — There is nothing for the scorer to consume: no controlled human efficacy evidence exists in the documented scope, so the correct outcome is a review-state change (A -> B), which the current registry has no field for on an identity with no record.

### Handoffs to other owners (no clinical interpretation here)

| PMID | role | destination | reason |
|---|---|---|---|
| 30034348 | safety | safety/CAERS owner | Adverse-event case literature for Epimedium flagged in screening (tachyarrhythmia/hypomania). |
| 38327958 | safety | safety/CAERS owner | Adverse-event case literature flagged in screening. |
| 40546602 | safety | safety/CAERS owner | Adverse-event case literature flagged in screening. |
| 30522143 | pharmacokinetic | PK/interaction owner | Single-dose prenylflavonoid pharmacokinetics and tolerability; the canonical interpretation of this study belongs to the PK owner, not the efficacy record. |

### High-risk queue: cardiovascular, medication_interactions

Flagged for eventual clinician countersignature; it does not block the owner review above.

**Actions:** approve · approve with correction · reject · hold · request adjudication · request more source review

---

## Gotu Kola

`gotu_kola` — 43 products, 9 brands, 44 label rows; Evidence mean 4.7, 25 at zero, 30 at ≤8. Review state today: not_reviewed.

**Label reality.** Labels deliver Centella asiatica herb powder or extract; plant part and extract ratio are usually unstated. See label_exposure_measured for the measured distribution — all dose comparisons below are computed from its median, not from prose.

Measured label exposure: median 60 mg/day (p25 50, p75 364.25, min 10, max 950) across 44 dosed rows. Source: inventory slim corpus, re-scored 2026-09-17.

**Publications vs trials.** 3 publications, 2 unique trials/cohorts, 0 independent replications. Two RCTs of different exposures and outcomes plus one scoping review whose included studies are not yet extracted. Nothing here replicates anything.

### Contexts (all pending)

**`gotu_kola_acute_startle_11106141`** — PMID 11106141 · rct · direct_rct · funding: unreported

- Identity: botanical_preparation — botanical_species: Centella asiatica; plant_part: not_stated; preparation: not_stated (reported only as 'Gotu Kola')
- Exposure: supplement_dose, route oral, dose 12000 mg (verified)
- Population: Healthy adults, 20 per arm
- Outcomes: acoustic_startle_response_amplitude (primary/surrogate) → **positive**; self_rated_mood (secondary/patient_important) → **null**; heart_rate_and_blood_pressure (secondary/surrogate) → **null**
  - > compared with placebo, Gotu Kola significantly attenuated the peak ASR amplitude 30 and 60 minutes after treatment
  - > Gotu Kola had no significant effect on self-rated mood, heart rate, or blood pressure
  - dose > a single 12-g orally administered dose of Gotu Kola (N = 20) or placebo (N = 20)
- Limitations: (1) Single acute 12 g dose. Against the measured label median of 60 mg/day that is ~200x, and ~13x even the measured p75 of 364 mg/day; it establishes nothing about label-range chronic use. (2) Primary endpoint is a physiological startle measure, not a patient-important anxiety outcome; the authors state therapeutic efficacy remains unknown. (3) Plant part, extract ratio and standardization are not stated, so the material cannot be matched to a specific label preparation. (4) n=40, single site, published 2000; no replication in this bounded search scope.

**`gotu_kola_mci_adjunct_36420467`** — PMID 36420467 · rct · direct_rct · funding: unreported

- Identity: botanical_preparation — botanical_species: Centella asiatica; plant_part: not_stated; preparation: Gotu kola extract capsule, 500 mg twice daily
- Exposure: supplement_dose, route oral, dose 1000 mg (verified)
- Population: Older adults with mild cognitive impairment, mean age 74.6 years
- Outcomes: cognitive_function_mmse_digit_span_trail_making (primary/patient_important) → **null**; tnf_alpha (secondary/surrogate) → **positive**
  - > Although supplementing with Gotu kola had no additional effects on cognitive function, it may improve the effects of multicomponent exercise on executive function by decreasing TNF-α levels
  - > The primary outcomes, such as cognitive function, inflammatory markers, and oxidative stress, were measured before and after the 12-week intervention
  - dose > Each participant received one capsule of placebo or 500 mg twice a day of Gotu kola extract
- Limitations: (1) Gotu kola was an ADD-ON to a supervised exercise programme; the isolated contrast is exercise+gotu kola versus exercise, and the cognitive primary showed no additional effect. (2) The positive secondary finding is an inflammatory marker (TNF-α) reported as a correlation, not a patient-important benefit, and must not be presented as cognitive efficacy. (3) 20 participants per arm; blinding of the exercise arms is not described; no MeSH Humans indexing at retrieval (human status confirmed from participant description and design). (4) Extract standardisation and plant part are not stated.

**`gotu_kola_mood_scoping_review_42391143`** — PMID 42391143 · systematic_review · systematic_review · funding: unreported

- Identity: botanical_preparation — botanical_species: Centella asiatica; plant_part: not_stated; preparation: not_stated; review of gotu kola as a Neurotain Plus constituent
- Exposure: supplement_dose, route oral, dose not resolved mg (source_not_reported)
- Population: Mixed human and animal studies; 12 gotu kola studies, three of them human (n = 91)
- Outcomes: mood_disorder_outcomes (unresolved/patient_important) → **unresolved**
  - > substantial methodological heterogeneity in design, population, intervention, and outcome measures indicates that the current evidence base remains insufficient to support quantitative synthesis
- Limitations: (1) Scoping review, not a meta-analysis: it maps the literature and states the evidence base is insufficient for quantitative synthesis. (2) Only three human gotu kola studies totalling 91 participants across the whole literature. (3) The review's subject is a three-constituent product (gotu kola, phosphatidylcholine, taurine); it reports that no study evaluated any combination of these compounds, so it supports neither the combination nor a gotu-kola-alone claim. (4) Included study PMIDs are not listed in the abstract — membership extraction pending, so overlap with the two RCTs above is unresolved.

### Proposed synthesis (for your decision)

**DO NOT create a scoring record yet**

The only positive primary outcome comes from a single acute 12 g challenge — about 200x the measured label median of 60 mg/day — on a surrogate startle endpoint; the one trial inside label range (1,000 mg/day, 12 weeks) was null on its cognitive primary; the 2026 scoping review finds three small human studies in total. Creating a record with effect_direction null or mixed would, under the current generic scorer, raise Evidence above zero for 25 products on the strength of evidence that did not show benefit — see GENERIC_EVIDENCE_NULL_DIRECTION_REVIEW.md.

<details><summary>if owner approves anyway</summary>

```json
{
 "study_type": "rct_single",
 "evidence_level": "ingredient-human",
 "effect_direction": "null",
 "min_clinical_dose": null,
 "note": "No defensible min_clinical_dose: the positive trial's 12 g is not a label exposure."
}
```
</details>

- Evidence strength: sparse; one acute surrogate-endpoint RCT, one null adjunct RCT
- Applicability to labels: unresolved — no trial matches a typical 200-1,000 mg/day label preparation with a patient-important outcome
- Review completeness: bounded search documented in wave1_search_log.json (18 records retrieved, 8 kept)
- Scorer compatibility: **class B** — The only positive primary outcome used a single 12 g challenge and the one label-range trial (1,000 mg/day) was null; catalog median is 60 mg/day. The scorer's dose handling (min_clinical_dose guard) cannot express 'positive only far above any label serving'.

### Handoffs to other owners (no clinical interpretation here)

| PMID | role | destination | reason |
|---|---|---|---|
| 16445150 | safety | safety/CAERS owner | Case report linking gotu kola use to night-eating syndrome; abstract empty in retrieval, needs full text. |
| 21334992 | safety | safety/CAERS owner | Paediatric hepatotoxicity case report; hepatic safety signal for a botanical sold at 200-1,000 mg/day. |

### High-risk queue: hepatic, pediatrics

Flagged for eventual clinician countersignature; it does not block the owner review above.

**Actions:** approve · approve with correction · reject · hold · request adjudication · request more source review

---

## D-Ribose

`d_ribose` — 33 products, 9 brands, 33 label rows; Evidence mean 3.35, 25 at zero, 27 at ≤8. Review state today: not_reviewed.

**Label reality.** Measured label median 1,400 mg/day (p25 1,025, p75 5,000), sold for energy and exercise recovery.

Measured label exposure: median 1400 mg/day (p25 1025, p75 5000, min 1.1, max 5100) across 24 dosed rows. Source: inventory slim corpus, re-scored 2026-09-17.

**Publications vs trials.** 2 publications, 1 unique trials/cohorts, 0 independent replications. 21154353 and 25391139 are successive versions of ONE Cochrane review. Counting both would double-count the same evidence.

### Contexts (all pending)

**`d_ribose_mcardle_cochrane_25391139`** — PMID 25391139 · systematic_review · systematic_review · funding: independent

- Identity: exact_form — chemical_form: D-ribose
- Exposure: supplement_dose, route oral, dose not resolved mg (source_not_reported)
- Population: 13 included studies totalling 85 participants with McArdle disease; largest trial 19 participants
- Outcomes: exercise_endurance_and_fatigability (primary/patient_important) → **null**
  - > There was no benefit with: D-ribose,glucagon, verapamil, vitamin B6, branched chain amino acids, dantrolene sodium, and high-dose creatine.
  - > The included studies involved a total of 85 participants, but the number in each individual trial was small; the largest treatment trial included 19 participants and the smallest study included only one participant.
- Limitations: (1) Cochrane review in a rare metabolic disease population, not general consumers seeking energy support. (2) Explicitly reports no benefit from D-ribose, and notes oral ribose caused diarrhoea and hypoglycaemia-like symptoms — a tolerability signal for the safety owner. (3) Very small included trials (85 participants across 13 studies). (4) This review supersedes the 2004 version (PMID 21154353 is the prior iteration); they are one review lineage, not two independent sources.

### Proposed synthesis (for your decision)

**HOLD — record the review state, create no scoring record**

The best-quality evidence (Cochrane) reports no benefit in the only disease indication studied, with adverse effects, and the exercise-performance literature is small and split. Under the current scorer a null record would manufacture affirmative Evidence points for 33 products, so this must wait for the null-direction decision.

- Evidence strength: null in the best-quality source; small mixed exercise literature
- Applicability to labels: no qualifying positive evidence at label exposures
- Review completeness: bounded search documented in wave1_search_log.json (44 records screened, 24 kept)
- Scorer compatibility: **class B** — The strongest evidence is a null Cochrane review in a rare disease population plus small exercise trials; approving a null record would add Evidence points under the current 0.25 null multiplier.

### Handoffs to other owners (no clinical interpretation here)

| PMID | role | destination | reason |
|---|---|---|---|
| 25391139 | safety | safety/CAERS owner | Cochrane review reports oral ribose caused diarrhoea and hypoglycaemia-like symptoms — tolerability signal. |
| 24272966 | pharmacokinetic | interaction/PK owner | Ribose pharmacokinetics with dose-related serum glucose and insulin changes — PK/glycaemic question, not efficacy. |

### High-risk queue: hypoglycemia_risk

Flagged for eventual clinician countersignature; it does not block the owner review above.

**Actions:** approve · approve with correction · reject · hold · request adjudication · request more source review

---

## Butterbur

`butterbur` — 29 products, 6 brands, 33 label rows; Evidence mean 1.5, 25 at zero, 26 at ≤8. Review state today: not_reviewed.

**Label reality.** Measured label median 150 mg/day (p25 87.5, p75 150, max 150) — the studied effective dose. 5 of 33 dosed rows name the exact studied material ('PA-free butterbur extract (Petadolex)'); the other 28 declare only 'butterbur (unspecified)', where pyrrolizidine-alkaloid content is unknown.

Measured label exposure: median 150 mg/day (p25 87.5, p75 150, min 7.5, max 150) across 33 dosed rows. Source: inventory slim corpus, re-scored 2026-09-17.

**Publications vs trials.** 4 publications, 2 unique trials/cohorts, 1 independent replications. Two placebo-controlled trials (n=60 and n=245/233) are the entire positive base. The systematic review contains both, and the AAN/AHS guideline rests on the same pair. Four publications, two trials.

### Contexts (all pending)

**`butterbur_migraine_prophylaxis_rct_11020030`** — PMID 11020030 · rct · direct_rct · funding: unreported

- Identity: branded_material — branded_material: Petadolex; botanical_species: Petasites hybridus; plant_part: root/rhizome; standardization: special CO2 root/rhizome extract; PA-free grade on current labels
- Exposure: supplement_dose, route oral, dose 100 mg (verified)
- Population: 60 migraine patients after a 4-week run-in phase
- Outcomes: migraine_attack_frequency (primary/patient_important) → **positive**
  - > This reduction in migraine attacks with petadolex was significant (p < 0.05) compared to placebo.
  - > No adverse events were reported.
  - dose > 60 patients received either the special Petasites hybridus extract petadolex or placebo at a dosage of 2 capsules (each capsule contains 25 mg) twice daily over 12 weeks
- Limitations: (1) n=60, published 2000; small. (2) Dose here is 100 mg/day, below the 150 mg/day that the later dose-ranging trial found effective. (3) Branded Petadolex CO2 root extract — not interchangeable with unspecified butterbur.

**`butterbur_migraine_dose_ranging_rct_15623680`** — PMID 15623680 · rct · direct_rct · funding: unreported

- Identity: branded_material — branded_material: Petadolex; botanical_species: Petasites hybridus; plant_part: root/rhizome; standardization: special CO2 root/rhizome extract; PA-free grade on current labels
- Exposure: supplement_dose, route oral, dose 100, 150 mg (verified)
- Population: 245 patients with migraine, ages 18 to 65, with two to six attacks per month
- Outcomes: migraine_attack_frequency_per_month (primary/patient_important) → **mixed**
  - > migraine attack frequency was reduced by 48% for Petasites extract 75 mg bid (p = 0.0012 vs placebo), 36% for Petasites extract 50 mg bid (p = 0.127 vs placebo), and 26% for the placebo group
  - dose > This is a three-arm, parallel-group, randomized trial comparing Petasites extract 75 mg bid, Petasites extract 50 mg bid, or placebo bid in 245 patients with migraine.
- Limitations: (1) Direction is dose-split: 150 mg/day beat placebo, 100 mg/day did NOT (p = 0.127). A record without a dose floor would credit products that deliver the ineffective amount. (2) Per-protocol analysis is the one quoted in the abstract. (3) Standardised special root extract; material equivalence to an unspecified butterbur label is not established.

**`butterbur_migraine_systematic_review_16987643`** — PMID 16987643 · systematic_review · systematic_review · funding: unreported

- Identity: branded_material — branded_material: Petadolex; botanical_species: Petasites hybridus; plant_part: root/rhizome; standardization: special CO2 root/rhizome extract; PA-free grade on current labels
- Exposure: supplement_dose, route oral, dose 100, 150 mg (verified)
- Population: Two trials totalling 293 patients (60 and 233 patients)
- Outcomes: migraine_attack_frequency_and_responder_rate (primary/patient_important) → **positive**
  - > Moderate evidence of effectiveness is, thus, available for a higher than the recommended dose of the proprietary Petasites root extract Petadolex in the prophylaxis of migraine.
  - > Both trials investigated the proprietary Petasites root extract Petadolex.
  - dose > The extract at higher dose (150 mg) showed a greater decreased frequency of migraine attacks and a greater number of responders (improvement>50%) after treatment over 3-4 months than the extract at lower dose (100 mg) and placebo.
- Limitations: (1) The whole positive evidence base is TWO trials (293 patients) — this review contains both contexts above, so it is not a third independent source. (2) Pooling was not carried out because of heterogeneity. (3) The review explicitly calls for further rigorous studies to confirm effectiveness AND safety. (4) Effectiveness is attributed to the proprietary Petadolex extract specifically.

**`butterbur_migraine_guideline_22529203`** — PMID 22529203 · guideline · guideline · funding: independent

- Identity: botanical_preparation — botanical_species: Petasites hybridus; plant_part: root/rhizome; preparation: Petasites (butterbur) as assessed by the AAN/AHS guideline
- Exposure: supplement_dose, route oral, dose not resolved mg (source_not_reported)
- Population: Adults with episodic migraine
- Outcomes: migraine_frequency_and_severity (guideline/patient_important) → **positive**
  - > Petasites (butterbur) is effective for migraine prevention and should be offered to patients with migraine to reduce the frequency and severity of migraine attacks (Level A).
- Limitations: (1) HISTORICAL, NOT CURRENT GUIDANCE: the American Academy of Neurology recommended butterbur for migraine prevention in 2012 and stopped recommending it in 2015 over serious safety concerns (NCCIH, verified 2026-09-17). This context must never be presented as current guideline support. (2) A guideline recommendation summarising the same two trials; authoritative in its time, but not additional evidence. (3) Its literature review window ended May 2009, predating the hepatotoxicity-driven reassessment. (4) The guideline names Petasites generally; the underlying trials used the proprietary extract.

### Live probe against the current architecture

read-only probe calling clinical_applicability.assess_clinical_applicability with a candidate policy (required_form_terms ['petadolex','pa free'], minimum_daily_dose 150 mg) against the real enriched products

- **328579 Migra-Eeze** — not_applicable / clinical_source_row_unresolved — two candidate rows, so no row links
- **61929 Butterbur Extract With Standardized Rosmarinic Acid** — not_applicable / clinical_form_mismatch — linked row is the printed label row; its text is 'purple butterbur co2 extract petasins' and contains neither 'petadolex' nor 'pa free', even though 75 mg x 2 servings = the studied 150 mg/day
- **293376 Petadolex Pro-Active** — not_applicable / clinical_source_row_unresolved — two candidate rows; would otherwise be 50 mg x 3 = 150 mg/day
- **252504 Butterbur Extract (BulkSupplements)** — not_applicable / clinical_form_mismatch — correct outcome for unspecified material

The measured label median of 150 mg/day comes from the UNSPECIFIED-material rows; the products declaring the studied Petadolex material deliver 22.5-75 mg per row and reach 150 mg/day only by serving multiplication. Material scoping is the blocker, and it is not expressible today.

### Proposed synthesis (for your decision)

**HOLD on safety grounds — the applicability blocker is now resolved, the safety question is not**

Two placebo-controlled trials and a systematic review support the proprietary PA-free Petasites root extract at 150 mg/day for migraine prophylaxis, and the 100 mg/day arm failed (p = 0.127). The 2012 AAN/AHS Level A recommendation is HISTORICAL: the Academy stopped recommending butterbur in 2015 over safety concerns, and rare liver injury has been reported even for products labelled PA-free. 'PA-free' is a processing claim, not the studied Petadolex material, so the two must not be equated. A live probe also shows the applicability contract cannot select the studied material at all: it matches printed label text, where 'Petadolex' does not appear. A dose-floor-only record would credit unspecified butterbur at 150 mg — the PA-risk material.

<details><summary>fields if material scoping becomes possible</summary>

```json
{
 "id": "INGR_BUTTERBUR",
 "study_type": "rct_multiple",
 "evidence_level": "ingredient-human",
 "effect_direction": "positive_weak",
 "min_clinical_dose": 150,
 "dose_unit": "mg",
 "applicability": {
  "scope": "ingredient",
  "required_form_terms": [
   "petadolex",
   "pa-free"
  ],
  "dose_unit": "mg",
  "minimum_daily_dose": 150,
  "studied_population": "Adults with episodic migraine (2-6 attacks/month)",
  "supported_outcomes": [
   "migraine prophylaxis"
  ]
 },
 "note": "positive_weak: the entire base is two trials totalling 293 patients and the lower dose failed."
}
```
</details>

**What would unblock it:**
- Let the applicability contract consult the enricher's resolved form identity (form_id / matched_form) for material scoping, with the two-matchers risk handled deliberately — today required_form_terms only sees label text.
- Make _linked_rows resolve multi-row identities instead of returning nothing when more than one canonical row exists (it silently drops Migra-Eeze and Petadolex Pro-Active).
- Then a record with required_form_terms ['petadolex','pa-free'] + minimum_daily_dose 150 mg would credit exactly the intended products.

**Decisions needed from you:**
- Safety owner leads here: unspecified butterbur carries pyrrolizidine-alkaloid hepatotoxicity risk, and NCCIH reports rare liver injury even in products labelled PA-free. No evidence record should make any butterbur product look endorsed before that is settled.
- If material scoping ever becomes possible, scope to the studied Petadolex material specifically — not to the generic 'PA-free' claim.
- Treat the AAN/AHS Level A statement as historical in any consumer-facing copy.

- Evidence strength: guideline-endorsed but thin: two trials, 293 patients, dose-dependent
- Applicability to labels: Now expressible: a record scoped to required_form_terms ['petadolex','pa-free'] with minimum_daily_dose 150 mg credits exactly the 3 products declaring the studied material at the studied dose and refuses the other 26. Verified against real products in wave1_applicability_rerun.json.
- Review completeness: bounded search documented in wave1_search_log.json (58 records screened, 51 kept)
- Scorer compatibility: **class A** — Upgraded from B after the applicability-owner repair (2026-09-17). The owner now reads the form identity enrichment already resolved, and resolves a multi-row identity when the reviewed scope names the material and exactly one row carries it. Re-run against the 29 real butterbur products: 3 become applicable (61929 Petadolex CO2 extract 75 mg x 2 servings; 204072 Petadolex 150 mg; 293376 Petadolex Pro-Active 50 mg x 3 servings), 26 are still refused — 24 on form mismatch (unspecified butterbur), 1 below the 150 mg floor, 1 unresolved. Migra-Eeze (328579) is the canary: its 22.5 mg Petadolex-form petasin row links but falls below the floor, and the 150 mg unspecified row is NOT allowed to lend its amount.

### Authoritative guidance (recorded as references, not study contexts)

The frozen context contract requires a PMID and a regulator assessment has none, so these use the shape the registry already has for non-PubMed sources.

**NCCIH (National Center for Complementary and Integrative Health)** — Butterbur: Usefulness and Safety  
https://www.nccih.nih.gov/health/butterbur · retrieved 2026-09-17 · page read in full on retrieval date

> In 2012, the American Academy of Neurology recommended butterbur for preventing migraines. However, the Academy stopped recommending it in 2015 because of serious concerns about its safety.
> Only butterbur products that have been processed to remove PAs and are labeled or certified as PA-free should be considered for use.
> However, there have been rare cases of liver injury associated with products that were reported to be PA-free.

*Destination: safety owner holds the PA/hepatotoxicity interpretation; recorded here only as evidence context*

### Handoffs to other owners (no clinical interpretation here)

| PMID | role | destination | reason |
|---|---|---|---|
| 12808361 | safety | safety/CAERS owner | Butterbur hepatotoxicity literature — pyrrolizidine-alkaloid liver injury is the defining safety question for this identity. |
| 14584971 | safety | safety/CAERS owner | Butterbur safety/hepatotoxicity record. |
| 23277154 | safety | safety/CAERS owner | Butterbur safety/hepatotoxicity record. |
| 28002518 | safety | safety/CAERS owner | Butterbur safety/hepatotoxicity record. |
| 31631423 | safety | safety/CAERS owner | Butterbur safety/hepatotoxicity record. |
| 30790138 | safety | safety/CAERS owner | Butterbur safety/hepatotoxicity record. |
| 38603736 | efficacy_other_indication | clinical evidence registry owner | Allergic-rhinitis meta-analysis where Petasites is the most-studied plant; very-low-to-low certainty, a separate indication from migraine. |

### High-risk queue: hepatic, pregnancy_and_fertility, withdrawn_guideline_recommendation

Flagged for eventual clinician countersignature; it does not block the owner review above.

**Actions:** approve · approve with correction · reject · hold · request adjudication · request more source review

---

## DHEA (Dehydroepiandrosterone)

`dhea` — 33 products, 12 brands, 33 label rows; Evidence mean 3.45, 25 at zero, 25 at ≤8. Review state today: not_reviewed.

**Label reality.** Labels deliver 5-100 mg/day of DHEA to general adult consumers; the studied populations below are patient groups, not general users.

Measured label exposure: median 25 mg/day (p25 25, p75 50, min 5, max 100) across 33 dosed rows. Source: inventory slim corpus, re-scored 2026-09-17.

**Publications vs trials.** 5 publications, unresolved — four reviews pooling overlapping RCT sets plus one primary RCT unique trials/cohorts, 0 independent replications. 30124161 and 32930419 are successive depression meta-analyses from the same line of work and must not be counted as two independent confirmations. Review membership is extraction_pending, so overlap between the depression, BMD and IVF reviews is unresolved.

### Contexts (all pending)

**`dhea_depressive_symptoms_meta_32930419`** — PMID 32930419 · meta_analysis · meta_analysis · funding: unreported

- Identity: exact_form — chemical_form: dehydroepiandrosterone (DHEA)
- Exposure: supplement_dose, route oral, dose not resolved mg (source_not_reported)
- Population: 853 female and male individuals with depression and/or other clinical conditions in which depressive symptoms are present
- Outcomes: depressive_symptoms (primary/patient_important) → **positive**
  - > In comparison with placebo, DHEA improved depressive symptoms (standardized mean difference [SMD] -0.28, 95% (CI) -0.45 to -0.11, p =.001, 12 studies, 742 individuals
  - > very low quality of evidence
- Limitations: (1) The review itself grades the evidence as very low quality; the pooled effect (SMD -0.28) is small. (2) Populations are people with depression or other clinical conditions, not general consumers taking DHEA for wellbeing. (3) No dose is stated in the abstract, so no studied daily exposure can be attached to a label serving. (4) PMID 30124161 is an earlier depression meta-analysis from the same line of work; the two reviews are not independent replications and their included trials overlap (membership extraction pending).

**`dhea_ivf_diminished_ovarian_reserve_meta_31303658`** — PMID 31303658 · meta_analysis · meta_analysis · funding: unreported

- Identity: exact_form — chemical_form: dehydroepiandrosterone (DHEA)
- Exposure: supplement_dose, route oral, dose not resolved mg (source_not_reported)
- Population: 833 patients with diminished ovarian reserve and/or poor ovarian response undergoing IVF or ICSI
- Outcomes: live_birth_rate (primary/patient_important) → **positive**; clinical_pregnancy_rate (primary/patient_important) → **positive**; miscarriage_rate (secondary/patient_important) → **null**
  - > patients treated with DHEA exhibited increases in the number of retrieved oocytes (mean difference, 0.91; 95% confidence interval [CI], 0.23 - 1.59; p = 0.009), clinical pregnancy rate (relative risk [RR] = 1.27; 95% CI, 1.01 - 1.61; p = 0.…
  - > there was no intergroup difference in the miscarriage rate
- Limitations: (1) Population is a fertility-clinic patient group under medical supervision; this says nothing about general adult use. (2) No dose or duration is stated in the abstract. (3) Included trial PMIDs are not listed in the abstract, so overlap with other DHEA reviews is unresolved.

**`dhea_bone_mineral_density_meta_31237150`** — PMID 31237150 · meta_analysis · meta_analysis · funding: unreported

- Identity: exact_form — chemical_form: dehydroepiandrosterone (DHEA)
- Exposure: supplement_dose, route oral, dose not resolved mg (source_not_reported)
- Population: Healthy older adults in randomized placebo-controlled trials; results reported separately for women and men
- Outcomes: hip_and_trochanter_bone_mineral_density (primary/surrogate) → **mixed**
  - > Hip BMD increased significantly above placebo group in women who took DHEA supplementation (SMD -0.5[-0.95, -0.04], p = .03)
  - > Similar results were not observed in men.
- Limitations: (1) Effect is women-only; men showed no comparable effect, so a single product-level direction would misstate half the population. (2) Bone mineral density is a surrogate endpoint, not a fracture outcome. (3) The review's own conclusion is qualified ('partially increase') and calls for more trials. (4) No dose stated in the abstract.

**`dhea_addisons_replacement_rct_18000094`** — PMID 18000094 · rct · direct_rct · funding: unreported

- Identity: exact_form — chemical_form: dehydroepiandrosterone (DHEA)
- Exposure: supplement_dose, route oral, dose 50 mg (verified)
- Population: 106 subjects (44 males, 62 females) with Addison's disease
- Outcomes: bone_mineral_density (primary/surrogate) → **mixed**; fatigue_cognitive_and_sexual_function (primary/patient_important) → **null**; lean_body_mass (secondary/surrogate) → **positive**
  - > DHEA reversed ongoing loss of bone mineral density at the femoral neck (P < 0.05) but not at other sites
  - > There was no significant benefit of DHEA treatment on fatigue or cognitive or sexual function.
  - dose > we randomized 106 subjects (44 males, 62 females) with Addison's disease to receive either 50 mg daily of micronized DHEA or placebo orally for 12 months
- Limitations: (1) Replacement therapy in patients whose own DHEA synthesis has failed — the opposite of supplementation in people with intact adrenal function. (2) Patient-important endpoints (fatigue, cognition, sexual function) were null; only a site-specific BMD change and lean mass moved. (3) Co-therapy: all participants remained on glucocorticoid and mineralocorticoid replacement.

### Proposed synthesis (for your decision)

**HOLD — do not create a scoring record in Wave 1**

Real meta-analytic human evidence exists, but every positive or mixed finding is population- and indication-specific: IVF patients with diminished ovarian reserve, primary adrenal insufficiency, people with depression or other clinical conditions, and — in healthy older adults — a bone-density signal reported for women with no comparable effect in men. No review states a daily dose. The generic scorer has no population or sex gate, so a positive DHEA record would credit every 25-50 mg consumer product with fertility-clinic, hormone-replacement and sex-specific evidence. It is also a safety-sensitive hormone.

<details><summary>if owner approves anyway</summary>

```json
{
 "study_type": "systematic_review_meta",
 "evidence_level": "ingredient-human",
 "effect_direction": "mixed",
 "min_clinical_dose": null,
 "note": "No defensible min_clinical_dose: the reviews do not state doses; only the Addison's RCT (50 mg) does, in a replacement population."
}
```
</details>

- Evidence strength: moderate in specific patient populations; very low certainty for depressive symptoms per the review's own grading
- Applicability to labels: unresolved — population mismatch is the blocker, not evidence volume
- Review completeness: bounded search documented in wave1_search_log.json (154 records screened, 52 kept)
- Scorer compatibility: **class B** — Positive and mixed results are population- and indication-specific (IVF/diminished ovarian reserve, adrenal insufficiency, clinical depression, and a women-only bone-density signal in healthy older adults), and no review states a dose. With no population or sex gate the record would credit 25 mg consumer products. Hormone-related, so it also routes to the high-risk path.

### Handoffs to other owners (no clinical interpretation here)

| PMID | role | destination | reason |
|---|---|---|---|
| 9951574 | safety | safety/CAERS owner | DHEA safety literature flagged during screening; androgenic effects belong to the safety lane. |
| 32930419 | safety | safety/CAERS owner | Review reports side effects 'commonly related to androgyny' — androgenic tolerability signal for the safety owner. |

### High-risk queue: hormonal, pregnancy_and_fertility, pediatrics_contraindicated

Flagged for eventual clinician countersignature; it does not block the owner review above.

**Actions:** approve · approve with correction · reject · hold · request adjudication · request more source review

---

## Dandelion

`dandelion` — 57 products, 15 brands, 58 label rows; Evidence mean 8.6, 21 at zero, 27 at ≤8. Review state today: not_reviewed.

**Label reality.** Measured label median 100 mg/day (p25 80, p75 200), sold mainly for diuretic, digestive and liver support.

Measured label exposure: median 100 mg/day (p25 80, p75 200, min 10, max 1575) across 59 dosed rows. Source: inventory slim corpus, re-scored 2026-09-17.

**Publications vs trials.** 1 publications, 1 unique trials/cohorts, 0 independent replications. One small single-agent trial. Screening found no large single-ingredient RCT of isolated dandelion for its marketed claims.

### Contexts (all pending)

**`dandelion_acute_diuresis_crossover_42398668`** — PMID 42398668 · crossover_rct · direct_rct · funding: unreported

- Identity: botanical_preparation — botanical_species: Taraxacum officinale; plant_part: root; preparation: commercially available dandelion root powder, four capsules providing about 2.1 g
- Exposure: supplement_dose, route oral, dose 2100 mg (verified)
- Population: Physically active young adults (n = 14; M/F, 12/2; age, 25.5 +/- 4.7 years)
- Outcomes: cumulative_urine_output_4h (primary/surrogate) → **null**
  - > Cumulative urine output was 1,164 ± 244 g in CON and 1,268 ± 213 g in DAND, with the mean difference (95% confidence interval) of 105 (-35 to 244) g (p = .13; g = 0.45)
  - > These results indicate a lack of support for the purported diuretic effect of dandelion.
  - dose > ingested 1 L of still water with (DAND) or without (CON) four capsules providing a total of ∼2.1 g of a commercially available dandelion root powder
- Limitations: (1) n=14, open-label, single acute dose, 4-hour window — small and short. (2) Tests the marketed diuretic claim directly and finds no effect. (3) The 2.1 g dose is roughly 21x the measured label median of 100 mg/day, so label servings are even less likely to act. (4) The authors themselves call for different dosing strategies and sources before definitive conclusions.

### Proposed synthesis (for your decision)

**RECORD THE REVIEW STATE (identity state B), CREATE NO SCORING RECORD**

The only clean single-agent human trial tested the marketed diuretic claim at 21x the label median and found no effect. Evidence 0 for these 57 products is correct and should read 'reviewed — no qualifying evidence found'.

- Evidence strength: one small null trial; no qualifying positive evidence
- Applicability to labels: no qualifying positive evidence to apply
- Review completeness: bounded search documented in wave1_search_log.json (33 records screened, 13 kept)
- Scorer compatibility: **class B** — No qualifying positive evidence exists to represent; the useful output is a review-state change, which the registry cannot express for an identity with no record.

**Actions:** approve · approve with correction · reject · hold · request adjudication · request more source review

---

