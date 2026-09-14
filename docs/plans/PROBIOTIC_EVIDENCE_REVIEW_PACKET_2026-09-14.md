# Probiotic evidence review packet

> Generated from `scripts/data/clinically_relevant_strains.json` on 2026-09-14.
> This packet is a research handoff. Reviewers supply source-backed recommendations; the registry and pipeline remain the source of truth.
> The engineering owner verifies each recommendation against the cited source and the frozen schema, then applies the final registry status. Reviewers do not edit statuses or the registry.
> Automated source check: [PubMed verification report](EVIDENCE_API_VERIFICATION_2026-09-14.json) — 182/182 citation references matched; 0 mismatches.
> Batch-1 structural patch: `scripts/audits/probiotic_curation_queue_2026_09_13/batch1_disposition_2026-09-14.json` (snapshot-bound; statuses unchanged).

## Where we are

The source records and citations have already been assembled. The decisions below have not yet been written into the registry, so no evidence change is shipped from this packet by itself.

- **Pending review:** 125
- **Recorded approved:** 0
- **Recorded rejected:** 0
- **Other registry states:** 0
- **Contexts shown in this packet:** 125
**Owning identities represented:** 21

## What is already done

- Source links and citation identifiers were checked before this packet was generated.
- Each context already has an identity scope, population, condition, dose fields, outcomes, and limitations where available.
- Clean → Enrich → Score is the production pipeline. Review decisions only change which evidence contexts are eligible; they do not bypass cleaning, enrichment, scoring, or release checks.
- Unresolved values remain unresolved. The system never fills a missing dose, turns a combination result into single-strain evidence, or treats a ranking as a direct treatment effect.

## What the reviewer needs to do

For each context, compare the record with the linked PubMed entry and full text when needed. Return only the context ID, one recommendation, and a short rationale. Do not edit the registry or assign a final status; the engineering owner performs that verification and change.

Record exactly one decision (these are deliberately different):
- **Approve as written** — the record is an accurate source summary. This does *not* mean the result was positive, and it does not make an unresolved dose eligible for scoring.
- **Approve with correction** — the source is usable, but specify the exact field-level correction (for example, a missing strain component or full-text dose) before it can be applied.
- **Reject** — the source/context should not be used, even after correction; give the reason and identify a replacement if one exists.
- **Needs source clarification** — keep pending because full text, an underlying trial, or a dose/form detail must be checked first.

A null or negative outcome may still be approved as an accurate record; it will never create a positive evidence bonus. Combination evidence remains combination evidence. A context with an unresolved dose may be approved as a source summary, but it remains ineligible for exact-dose applicability until the dose is resolved.

Return the context ID, recommendation, and rationale. For a correction, include an exact before/after field value, the source PMID, and the source location. The engineering owner verifies the recommendation, records the source snapshot, and applies the final status with the existing review provenance.

## Schema to use (do not invent fields)

The registry is authoritative. Put corrections only in these existing paths:
- **Dose:** `dose.dose_status`, `dose.dose_basis`, `dose.values`, `dose.unit`, `dose.dosage_forms`, `dose.duration_days`, `dose.duration_as_printed`, `dose.duration_basis`, `dose.administration_frequency`, `dose.component_doses`, and `dose.source_provenance`.
- **Evidence:** `evidence_role`.
- **Components:** `component_registration_status`.
- **Eligibility:** `scoring_eligible` at the context level only.
- **Outcomes:** `outcomes[].name`, `hierarchy`, `kind`, `direction`, and `outcome_role`.

Use only the existing vocabulary:
- `dose_status`: `verified`, `source_not_reported`, `extraction_pending`, `conflicting_source_values`, `combination_total_only`.
- `dose_basis`: `per_strain_daily`, `combination_total_daily`, `nominal_assigned_arm`, `measured_viability`, `single_challenge`, `not_applicable`.
- `duration_basis`: `fixed_protocol`, `tied_to_cotherapy`, `participant_specific`, `endpoint_followup_only`, `not_recorded`, `extraction_pending`.
- `evidence_role`: `direct_rct`, `network_meta_analysis`, `systematic_review`, `meta_analysis`, `guideline`, `companion_analysis`, `observational_study`, `mechanistic_study`.
- `outcome kind`: `patient_important`, `surrogate`, `evidence_ranking`; `outcome_role`: `direct_between_group_effect`, `network_ranking`, `within_group_change`, `surrogate`, `post_hoc_subgroup`, `companion_reported_context`.
- `component_registration_status`: `fully_registered`, `unregistered_components_present`, `identity_uncertain`.

Do not create variants such as `studied_dose.*`, `network_node_estimate`, `systematic_review_guideline`, `recoverable_manual`, `daily_use_comparable`, or outcome-level eligibility flags. If the source does not support a value, leave it pending or source-not-reported.

## What happens after the decisions

1. The engineering owner verifies the recommendation against the cited source, the exact context ID, and the named source snapshot.
2. The owner applies the final status and any corrections only after schema/source validation; rejected or unresolved contexts remain excluded.
3. The normal Clean → Enrich → Score pipeline runs. Only verified, eligible evidence contributes to scoring; rankings, class-level results, companion reports, and unresolved doses stay bounded.
4. Release checks compare the generated catalog with the prior release, then the approved build is shipped to the app.

---

## STRAIN_ACIDOPHILUS_DDS1

### 1. `dds1_ibs_network_meta_37686889`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 37686889](https://pubmed.ncbi.nlm.nih.gov/37686889/)
- **Identity scope:** exact_strain; components=['STRAIN_ACIDOPHILUS_DDS1']
- **Evidence role:** network_meta_analysis; component_registration_status=fully_registered; schema=1.1.0
- **Condition / purpose:** irritable_bowel_syndrome / treatment
- **Population:** Adults with IBS in a 2023 outcome-specific network meta-analysis; age_group=adult
- **Studied dose:** status=source_not_reported; basis=not_applicable; values=unresolved; unit=CFU; forms=unresolved; duration_days=not recorded; duration_basis=not_recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=ibs_severity_score_ranking; hierarchy=unresolved; kind=evidence_ranking; direction=unresolved; outcome_role=network_ranking
- **Limitations:**
  - DDS-1 ranked first for IBS-SSS improvement (SUCRA 92.9%), an indirect ranking resting on the single DDS-1 IBS RCT already recorded (PMID 32019158); shares its trial family.
- **Rationale / notes:**

### 2. `dds1_ibs_three_arm_32019158`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 32019158](https://pubmed.ncbi.nlm.nih.gov/32019158/)
- **Identity scope:** exact_strain; components=['STRAIN_ACIDOPHILUS_DDS1']
- **Evidence role:** direct_rct; component_registration_status=fully_registered; schema=1.1.0
- **Condition / purpose:** irritable_bowel_syndrome / treatment
- **Population:** 330 adults with IBS randomized across placebo, DDS-1 and UABla-12 solo arms; age_group=adult
- **Studied dose:** status=verified; basis=per_strain_daily; values=10000000000.0; unit=CFU; forms=capsule; duration_days=42; duration_basis=fixed_protocol; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=abdominal_pain_severity_nrs; hierarchy=primary; kind=patient_important; direction=positive; outcome_role=not recorded
- name=ibs_severity_score; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- **Limitations:**
  - Manufacturer-run (UAS Labs); the daily CFU dose is printed with a stripped exponent in the retrieved abstract and is recorded as unresolved.
  - Only the DDS-1 solo arm is recorded here; the UABla-12 solo arm remains future curation under its own identity.
- **Rationale / notes:**

### 3. `dds1_lactose_intolerance_crossover_27207411`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 27207411](https://pubmed.ncbi.nlm.nih.gov/27207411/)
- **Identity scope:** exact_strain; components=['STRAIN_ACIDOPHILUS_DDS1']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** lactose_intolerance / challenge
- **Population:** Adults with lactose intolerance; crossover with 4-week arms, washout, and a 6-hour lactose challenge; age_group=adult
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=28; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=challenge_diarrhea_score; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- name=abdominal_cramping; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- name=vomiting; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- name=overall_symptom_score; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- **Limitations:**
  - Dose not stated in the abstract; industry authorship (Nebraska Cultures); sample size not stated in the abstract.
- **Rationale / notes:**

### 4. `dds1_lactose_intolerance_sr_36308983`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 36308983](https://pubmed.ncbi.nlm.nih.gov/36308983/)
- **Identity scope:** exact_strain; components=['STRAIN_ACIDOPHILUS_DDS1']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** lactose_intolerance / treatment
- **Population:** Adults with lactose intolerance in a systematic review of probiotic trials; age_group=adult
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=not recorded; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=lactose_intolerance_symptoms; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- **Limitations:**
  - LOW certainty; no pooling was possible; the review's DDS-1 evidence is the crossover trial already recorded (PMID 27207411), so this shares its trial family.
- **Rationale / notes:**

### 5. `dds1_night_shift_stress_markers_33584665`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 33584665](https://pubmed.ncbi.nlm.nih.gov/33584665/)
- **Identity scope:** exact_strain; components=['STRAIN_ACIDOPHILUS_DDS1']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** anticipatory_stress_markers_night_shift / physiology
- **Population:** Night-shift workers, DDS-1 solo arm (29 per arm), 14 days; age_group=adult
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=14; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=pre_shift_anticipatory_stress_markers; hierarchy=unresolved; kind=surrogate; direction=positive; outcome_role=not recorded
- name=stress_marker_night_shift_interactions; hierarchy=unresolved; kind=surrogate; direction=null; outcome_role=not recorded
- **Limitations:**
  - Serum stress markers are surrogates; pre-shift moderation without interaction effects across the night shift makes the record mixed.
  - Only the DDS-1 solo arm of a multi-arm trial is recorded here; total trial size not captured.
- **Rationale / notes:**

### 6. `dds1_uabla12_fos_atopic_dermatitis_20642296`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 20642296](https://pubmed.ncbi.nlm.nih.gov/20642296/)
- **Identity scope:** combination; components=['STRAIN_ACIDOPHILUS_DDS1', 'STRAIN_LACTIS_UABla12']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** pediatric_atopic_dermatitis / treatment
- **Population:** 90 children 1-3 years with moderate-to-severe atopic dermatitis; age_group=child
- **Studied dose:** status=not recorded; basis=discrete_daily_arms; values=10000000000.0; unit=CFU; forms=unresolved; duration_days=56; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=fructooligosaccharide
- **Outcomes:**
- name=scorad_percentage_decrease; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- name=topical_corticosteroid_use; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- **Limitations:**
  - Synbiotic with fructooligosaccharide; 5 x 10^9 CFU twice daily (1 x 10^10/day) is the combination total.
  - SCORAD reported as percentage decrease (33.7% vs 19.4%).
- **Rationale / notes:**

### 7. `dds1_uabla12_fos_pediatric_ari_26463725`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 26463725](https://pubmed.ncbi.nlm.nih.gov/26463725/)
- **Identity scope:** combination; components=['STRAIN_ACIDOPHILUS_DDS1', 'STRAIN_LACTIS_UABla12']
- **Evidence role:** direct_rct; component_registration_status=fully_registered; schema=1.1.0
- **Condition / purpose:** pediatric_acute_respiratory_infections / prevention
- **Population:** 315 children randomized (225 analyzed) with household exposure to acute respiratory infection; age_group=child
- **Studied dose:** status=combination_total_only; basis=combination_total_daily; values=5000000000.0; unit=CFU; forms=unresolved; duration_days=14; duration_basis=fixed_protocol; frequency=not recorded; component_doses=unresolved; co-therapies=fructooligosaccharide
- **Outcomes:**
- name=ari_incidence; hierarchy=primary; kind=patient_important; direction=null; outcome_role=not recorded
- name=symptom_resolution_time; hierarchy=secondary; kind=patient_important; direction=positive; outcome_role=not recorded
- name=ari_severity; hierarchy=secondary; kind=patient_important; direction=positive; outcome_role=not recorded
- **Limitations:**
  - Primary incidence endpoint null (57% vs 65%, p=0.261); only resolution time and severity differed.
  - Synbiotic with fructooligosaccharide; 5 x 10^9 CFU/day is the combination total.
- **Rationale / notes:**

### 8. `dds1_uabla12_pediatric_constipation_36071965`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 36071965](https://pubmed.ncbi.nlm.nih.gov/36071965/)
- **Identity scope:** combination; components=['STRAIN_ACIDOPHILUS_DDS1', 'STRAIN_LACTIS_UABla12']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** pediatric_functional_constipation / treatment
- **Population:** 92 children with functional constipation, chewable tablet; age_group=child
- **Studied dose:** status=not recorded; basis=discrete_daily_arms; values=5000000000.0; unit=CFU; forms=chewable tablet; duration_days=28; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=stool_frequency_normalization_time; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- **Limitations:**
  - Single-blind; industry involvement (Sirio/Chr. Hansen).
  - 5 x 10^9 CFU/day is the two-strain combination total, never an individual dose.
- **Rationale / notes:**

## STRAIN_ACIDOPHILUS_LA5

### 9. `la5_bb12_aad_incidence_24772726`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 24772726](https://pubmed.ncbi.nlm.nih.gov/24772726/)
- **Identity scope:** combination; components=['STRAIN_ACIDOPHILUS_LA5', 'STRAIN_LACTIS_BB12']
- **Evidence role:** direct_rct; component_registration_status=fully_registered; schema=1.1.0
- **Condition / purpose:** antibiotic_associated_diarrhea / prevention
- **Population:** Adults on cefadroxil or amoxicillin in a multicentric trial; 14 days of LA-5 + BB-12; age_group=adult
- **Studied dose:** status=source_not_reported; basis=not_applicable; values=unresolved; unit=CFU; forms=unresolved; duration_days=14; duration_basis=fixed_protocol; frequency=not recorded; component_doses=unresolved; co-therapies=cefadroxil or amoxicillin
- **Outcomes:**
- name=aad_incidence; hierarchy=primary; kind=patient_important; direction=null; outcome_role=not recorded
- name=diarrhea_duration; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- name=severe_diarrhea_subgroup; hierarchy=post_hoc; kind=patient_important; direction=positive; outcome_role=not recorded
- **Limitations:**
  - Primary incidence endpoint null (10.8% vs 15.6%, p=0.19); duration (2 vs 4 days) and a severe-diarrhea subgroup differed.
  - Sample size not captured from the abstract.
- **Rationale / notes:**

### 10. `la5_bb12_hpylori_yogurt_aad_21871144`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 21871144](https://pubmed.ncbi.nlm.nih.gov/21871144/)
- **Identity scope:** combination; components=['STRAIN_ACIDOPHILUS_LA5', 'STRAIN_LACTIS_BB12']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** antibiotic_associated_diarrhea_h_pylori_eradication / prevention
- **Population:** 88 Helicobacter pylori-infected adults in a three-arm fruit-yogurt trial spanning an eradication week; age_group=adult
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=fruit yogurt; duration_days=56; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=Helicobacter pylori eradication therapy
- **Outcomes:**
- name=aad_days; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- name=h_pylori_urease_activity; hierarchy=unresolved; kind=surrogate; direction=null; outcome_role=not recorded
- **Limitations:**
  - AAD days 4 vs 10 vs 10 across arms; urease activity fell in ALL milk arms, so that change is not attributable to the probiotic.
  - Food matrix; dose not stated in the abstract.
- **Rationale / notes:**

### 11. `la5_bb12_lc01_yogurt_aad_30439760`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 30439760](https://pubmed.ncbi.nlm.nih.gov/30439760/)
- **Identity scope:** combination; components=['STRAIN_ACIDOPHILUS_LA5', 'STRAIN_LACTIS_BB12']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** antibiotic_associated_diarrhea / prevention
- **Population:** 314 hospitalized adults on antibiotics receiving a yogurt with LA-5, BB-12 and LC-01; age_group=adult
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=yogurt; duration_days=not recorded; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=antibiotic therapy
- **Outcomes:**
- name=aad_incidence; hierarchy=unresolved; kind=patient_important; direction=null; outcome_role=not recorded
- **Limitations:**
  - Null result (23.0% vs 17.6%).
  - The studied product was a THREE-strain yogurt; the third strain L. casei LC-01 has no registry identity, so this record understates the formulation. A two-strain product matching these components was not what was tested.
- **Rationale / notes:**

### 12. `la5_bb12_nonconstipated_ibs_41255078`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 41255078](https://pubmed.ncbi.nlm.nih.gov/41255078/)
- **Identity scope:** combination; components=['STRAIN_ACIDOPHILUS_LA5', 'STRAIN_LACTIS_BB12']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** irritable_bowel_syndrome / treatment
- **Population:** 200 adults with non-constipated IBS, 84 days; age_group=adult
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=84; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=ibs_gis_response; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- name=ibs_severity_abdominal_pain; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- name=abdominal_distension; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- name=quality_of_life; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- **Limitations:**
  - Combination evidence; nothing here attributes the effect to either strain alone; dose not stated in the abstract.
- **Rationale / notes:**

### 13. `la5_bb12_primal_preterm_mdro_39102225`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 39102225](https://pubmed.ncbi.nlm.nih.gov/39102225/)
- **Identity scope:** combination; components=['STRAIN_ACIDOPHILUS_LA5', 'STRAIN_LACTIS_BB12']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** multidrug_resistant_organism_colonization_preterm / prevention
- **Population:** 618 preterm infants 28-32 weeks in the PRIMAL phase 3 trial; age_group=infant
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=not recorded; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=mdro_colonization; hierarchy=primary; kind=surrogate; direction=null; outcome_role=not recorded
- name=gut_eubiosis_score; hierarchy=secondary; kind=surrogate; direction=positive; outcome_role=not recorded
- **Limitations:**
  - Primary MDRO-colonization endpoint null; eubiosis is a microbiota surrogate.
  - The studied product also contained an unnamed B. longum subsp. infantis component with no registry identity; this record understates the formulation.
  - Hospital neonatal population; not a consumer supplement indication; dose not stated in the abstract.
- **Rationale / notes:**

### 14. `lgg_la5_bb12_hospital_aad_17356555`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 17356555](https://pubmed.ncbi.nlm.nih.gov/17356555/)
- **Identity scope:** combination; components=['STRAIN_LGG', 'STRAIN_ACIDOPHILUS_LA5', 'STRAIN_LACTIS_BB12']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** antibiotic_associated_diarrhea / prevention
- **Population:** 87 hospitalized adults on antibiotics receiving a fermented milk with LGG, La-5 and Bb-12 for 14 days; age_group=adult
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=fermented milk; duration_days=14; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=antibiotic therapy
- **Outcomes:**
- name=aad_incidence; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- **Limitations:**
  - Three-strain fermented milk (5.9% vs 27.6%); food matrix; nothing attributes the effect to a single strain.
- **Rationale / notes:**

### 15. `lgg_la5_bb12_pediatric_aad_25588782`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 25588782](https://pubmed.ncbi.nlm.nih.gov/25588782/)
- **Identity scope:** combination; components=['STRAIN_LGG', 'STRAIN_ACIDOPHILUS_LA5', 'STRAIN_LACTIS_BB12']
- **Evidence role:** direct_rct; component_registration_status=fully_registered; schema=1.1.0
- **Condition / purpose:** pediatric_antibiotic_associated_diarrhea / prevention
- **Population:** 70 children 1-12 years on antibiotics receiving 200 g/day of a yogurt with LGG, Bb-12 and La-5; age_group=child
- **Studied dose:** status=source_not_reported; basis=not_applicable; values=unresolved; unit=CFU; forms=yogurt 200 g/day; duration_days=not recorded; duration_basis=tied_to_cotherapy; frequency=not recorded; component_doses=unresolved; co-therapies=antibiotic therapy
- **Outcomes:**
- name=severe_diarrhea_episodes; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- **Limitations:**
  - Severe diarrhea 0 vs 6 episodes (p=0.025) in a small yogurt trial; three-strain food matrix.
- **Rationale / notes:**

### 16. `lgg_la5_bb12_propact_offspring_ad_41748464`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 41748464](https://pubmed.ncbi.nlm.nih.gov/41748464/)
- **Identity scope:** combination; components=['STRAIN_LGG', 'STRAIN_ACIDOPHILUS_LA5', 'STRAIN_LACTIS_BB12']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** childhood_atopic_dermatitis / prevention
- **Population:** Offspring of 415 pregnant women in the ProPACT trial of maternal LGG, La-5 and Bb-12 supplementation; age_group=infant
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=not recorded; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=offspring_atopic_dermatitis; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- **Limitations:**
  - Authored from a longitudinal T-cell immunology companion whose abstract restates the parent trial's atopic-dermatitis reduction; the parent outcome paper was not read this wave.
  - Maternal supplementation with offspring outcomes; dose not stated in the abstract.
- **Rationale / notes:**

## STRAIN_ACIDOPHILUS_NCFM

### 17. `bi07_lpc37_ncfm_bl04_omega3_elderly_inflammation_36235651`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 36235651](https://pubmed.ncbi.nlm.nih.gov/36235651/)
- **Identity scope:** combination; components=['STRAIN_LACTIS_BI07', 'STRAIN_PARACASEI_LPC37', 'STRAIN_ACIDOPHILUS_NCFM', 'STRAIN_LACTIS_BL04']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** chronic_low_grade_inflammation / treatment
- **Population:** 76 community-dwelling elderly (median 71 y) with chronic low-grade inflammation; dual supplement with omega-3; age_group=adult
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=56; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=omega-3 supplement
- **Outcomes:**
- name=hs_crp; hierarchy=primary; kind=surrogate; direction=null; outcome_role=not recorded
- name=il_10; hierarchy=secondary; kind=surrogate; direction=positive; outcome_role=not recorded
- name=valeric_acid; hierarchy=secondary; kind=surrogate; direction=positive; outcome_role=not recorded
- **Limitations:**
  - Proof-of-concept; primary hs-CRP not different; probiotic effect cannot be separated from omega-3 co-supplementation.
  - GSK Consumer Healthcare co-author; doses not stated.
- **Rationale / notes:**

### 18. `ncfm_adult_ibs_28082816`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 28082816](https://pubmed.ncbi.nlm.nih.gov/28082816/)
- **Identity scope:** exact_strain; components=['STRAIN_ACIDOPHILUS_NCFM']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** irritable_bowel_syndrome / treatment
- **Population:** Adults aged 18–65 with Rome III IBS; 391 randomized, 340 completed; age_group=adult
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=capsule; duration_days=84; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=ibs_symptom_severity_score; hierarchy=primary; kind=patient_important; direction=null; outcome_role=not recorded
- name=abdominal_pain_moderate_severe_subgroup; hierarchy=post_hoc; kind=patient_important; direction=positive; outcome_role=not recorded
- **Limitations:**
  - Nominal once-daily arms are 1 billion and 10 billion CFU, not an efficacy interval
  - Reported low-dose capsule viability exceeds 9.8 billion CFU, conflicting with the nominal 1-billion arm; automated dose comparison remains unresolved
  - Primary IBS-SSS and overall secondary outcomes did not differ from placebo
  - Pain signal comes from a post hoc subgroup, not the primary endpoint
  - Industry supplied study product and participated in the study
- **Rationale / notes:**

### 19. `ncfm_bi07_post_rygb_food_addiction_35766604`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 35766604](https://pubmed.ncbi.nlm.nih.gov/35766604/)
- **Identity scope:** combination; components=['STRAIN_ACIDOPHILUS_NCFM', 'STRAIN_LACTIS_BI07']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** post_bariatric_binge_eating_and_food_addiction / treatment
- **Population:** 101 adults after Roux-en-Y gastric bypass; 90 days from postoperative day 7; outcomes at 90 days and 1 year; age_group=adult
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=90; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=food_addiction_symptoms_1_year; hierarchy=primary; kind=patient_important; direction=positive; outcome_role=not recorded
- name=binge_eating_score_1_year; hierarchy=primary; kind=patient_important; direction=positive; outcome_role=not recorded
- name=food_addiction_and_binge_eating_90_days; hierarchy=secondary; kind=patient_important; direction=null; outcome_role=not recorded
- **Limitations:**
  - Both groups improved at 90 days; the between-group difference appeared only at 1 year (p=0.037 and p=0.030).
  - Same Curitiba RYGB cohort as PMIDs 33443719 and 35987956; one trial family, not three confirmations. Dose not stated.
- **Rationale / notes:**

### 20. `ncfm_bi07_post_rygb_nutritional_metabolic_33443719`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 33443719](https://pubmed.ncbi.nlm.nih.gov/33443719/), [PMID 35987956](https://pubmed.ncbi.nlm.nih.gov/35987956/)
- **Identity scope:** combination; components=['STRAIN_ACIDOPHILUS_NCFM', 'STRAIN_LACTIS_BI07']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** post_bariatric_nutritional_and_metabolic_markers / treatment
- **Population:** Adults after Roux-en-Y gastric bypass; 3 months of FloraVantage or placebo from day 7; age_group=adult
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=90; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=serum_25_oh_vitamin_d; hierarchy=secondary; kind=surrogate; direction=unresolved; outcome_role=not recorded
- name=triglycerides; hierarchy=secondary; kind=surrogate; direction=unresolved; outcome_role=not recorded
- name=plasma_tmao_and_beta_hydroxybutyrate; hierarchy=secondary; kind=surrogate; direction=positive; outcome_role=not recorded
- **Limitations:**
  - Vitamin D and triglyceride changes were significant within the probiotic group only; between-group tests are not reported in the abstract.
  - Metabolomic differences (PMID 35987956) are surrogate outcomes from the same cohort.
- **Rationale / notes:**

### 21. `ncfm_child_cold_flu_symptoms_19651563`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 19651563](https://pubmed.ncbi.nlm.nih.gov/19651563/)
- **Identity scope:** exact_strain; components=['STRAIN_ACIDOPHILUS_NCFM']
- **Evidence role:** direct_rct; component_registration_status=fully_registered; schema=1.1.0
- **Condition / purpose:** cold_and_flu_like_symptoms / prevention
- **Population:** Children aged 3–5; NCFM-only arm of a 326-participant three-arm trial; age_group=child
- **Studied dose:** status=source_not_reported; basis=not_applicable; values=unresolved; unit=CFU; forms=unresolved; duration_days=182 (as_printed=6 months); duration_basis=fixed_protocol; frequency=twice_daily; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=fever_and_cough_incidence_and_duration; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- name=rhinorrhea_incidence_single_strain_arm; hierarchy=unresolved; kind=patient_important; direction=null; outcome_role=not recorded
- **Limitations:**
  - Twice-daily administration for six months; exact CFU, dosage form and prespecified endpoint hierarchy were not verified in the accessible abstract
  - Study also includes a distinct NCFM plus Bi-07 arm; its results are not allocated to NCFM alone
  - Reported symptoms do not establish laboratory-confirmed infection prevention or adult digestive benefit
- **Rationale / notes:**

### 22. `ncfm_hn001_lpc37_hn019_caloric_restriction_obese_men_39842252`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 39842252](https://pubmed.ncbi.nlm.nih.gov/39842252/)
- **Identity scope:** combination; components=['STRAIN_ACIDOPHILUS_NCFM', 'STRAIN_RHAMNOSUS_HN001', 'STRAIN_PARACASEI_LPC37', 'STRAIN_LACTIS_HN019']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** obesity_body_composition_under_caloric_restriction / treatment
- **Population:** Men 25-44 y with obesity (BMI 30-39.9) under 30% caloric restriction; 25 analyzed per protocol of 33 randomized; age_group=adult
- **Studied dose:** status=not recorded; basis=discrete_daily_arms; values=8000000000.0; unit=CFU; forms=unresolved; duration_days=84; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=body_weight_change; hierarchy=primary; kind=patient_important; direction=null; outcome_role=not recorded
- name=body_fat_change; hierarchy=primary; kind=patient_important; direction=null; outcome_role=not recorded
- **Limitations:**
  - 8 billion CFU/day is the four-strain total (2 x 10^9 each); no between-group differences in weight or fat loss.
  - Per-protocol analysis of a small sample.
- **Rationale / notes:**

### 23. `ncfm_infant_colic_41998618`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 41998618](https://pubmed.ncbi.nlm.nih.gov/41998618/)
- **Identity scope:** exact_strain; components=['STRAIN_ACIDOPHILUS_NCFM']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** infantile_colic / treatment
- **Population:** 60 infants with colic, Brazil; five drops daily; age_group=infant
- **Studied dose:** status=not recorded; basis=discrete_daily_arms; values=1000000000.0; unit=CFU; forms=drops; duration_days=28; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=responder_rate_day_28; hierarchy=primary; kind=patient_important; direction=null; outcome_role=not recorded
- name=responder_rate_day_14; hierarchy=secondary; kind=patient_important; direction=positive; outcome_role=not recorded
- name=daily_fussing_and_crying_time; hierarchy=secondary; kind=patient_important; direction=null; outcome_role=not recorded
- name=fecal_calprotectin; hierarchy=secondary; kind=surrogate; direction=null; outcome_role=not recorded
- **Limitations:**
  - Primary endpoint not met (p=0.240); the day-14 responder signal was attenuated after correction for multiple comparisons.
  - Retrospectively registered.
- **Rationale / notes:**

### 24. `ncfm_lpc37_bl04_bi07_bb02_chemotherapy_diarrhea_41379184`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 41379184](https://pubmed.ncbi.nlm.nih.gov/41379184/)
- **Identity scope:** combination; components=['STRAIN_ACIDOPHILUS_NCFM', 'STRAIN_PARACASEI_LPC37', 'STRAIN_LACTIS_BL04', 'STRAIN_LACTIS_BI07', 'STRAIN_BIFIDUM_BB02']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** chemotherapy_induced_diarrhea / prevention
- **Population:** 28 gastrointestinal cancer patients starting fluoropyrimidine/oxaliplatin/irinotecan chemotherapy; age_group=adult
- **Studied dose:** status=not recorded; basis=discrete_daily_arms; values=20000000000.0; unit=CFU; forms=unresolved; duration_days=90; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=grade_2_3_diarrhea; hierarchy=primary; kind=patient_important; direction=null; outcome_role=not recorded
- name=overall_diarrhea_incidence; hierarchy=secondary; kind=patient_important; direction=null; outcome_role=not recorded
- **Limitations:**
  - Very small (n=28); 20 billion CFU/day is the five-strain total, not a per-strain dose.
  - No benefit for grade 2/3 or overall diarrhea.
- **Rationale / notes:**

### 25. `ncfm_lpc37_bl04_bi07_hn019_constipation_bloating_2wk_31131616`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 31131616](https://pubmed.ncbi.nlm.nih.gov/31131616/)
- **Identity scope:** combination; components=['STRAIN_ACIDOPHILUS_NCFM', 'STRAIN_PARACASEI_LPC37', 'STRAIN_LACTIS_BL04', 'STRAIN_LACTIS_BI07', 'STRAIN_LACTIS_HN019']
- **Evidence role:** direct_rct; component_registration_status=fully_registered; schema=1.1.0
- **Condition / purpose:** functional_constipation_with_bloating / treatment
- **Population:** 156 adults with self-reported bloating and Rome III functional constipation; age_group=adult
- **Studied dose:** status=verified; basis=per_strain_daily; values=unresolved; unit=CFU; forms=unresolved; duration_days=14; duration_basis=fixed_protocol; frequency=not recorded; component_doses=STRAIN_ACIDOPHILUS_NCFM=10000000000.0 CFU/day, STRAIN_PARACASEI_LPC37=2500000000.0 CFU/day, STRAIN_LACTIS_BL04=2500000000.0 CFU/day, STRAIN_LACTIS_BI07=2500000000.0 CFU/day, STRAIN_LACTIS_HN019=10000000000.0 CFU/day; co-therapies=none recorded
- **Outcomes:**
- name=bloating; hierarchy=primary; kind=patient_important; direction=null; outcome_role=not recorded
- name=colonic_transit_time; hierarchy=secondary; kind=patient_important; direction=null; outcome_role=not recorded
- name=bowel_movement_frequency; hierarchy=secondary; kind=patient_important; direction=null; outcome_role=not recorded
- name=stool_consistency; hierarchy=secondary; kind=patient_important; direction=null; outcome_role=not recorded
- name=flatulence; hierarchy=post_hoc; kind=patient_important; direction=positive; outcome_role=not recorded
- **Limitations:**
  - Efficacy not shown for the primary outcome or any secondary outcome; placebo performed similarly.
  - Per-strain CFU (NCFM 10^10, Lpc-37/Bl-04/Bi-07 2.5x10^9, HN019 10^10 as printed) not machine-readable in the retrieved abstract; recorded as unresolved.
  - Post hoc flatulence signal only.
- **Rationale / notes:**

### 26. `ncfm_lpc37_bl04_bi07_mdr_colonization_antibiotics_33763399`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 33763399](https://pubmed.ncbi.nlm.nih.gov/33763399/)
- **Identity scope:** combination; components=['STRAIN_ACIDOPHILUS_NCFM', 'STRAIN_PARACASEI_LPC37', 'STRAIN_LACTIS_BL04', 'STRAIN_LACTIS_BI07']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** multidrug_resistant_gut_colonization_during_antibiotics / prevention
- **Population:** 120 hospitalized patients (mean age 78) treated 10 days with amoxicillin-clavulanate; 30-day study product; age_group=adult
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=30; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=amoxicillin-clavulanate 10 days
- **Outcomes:**
- name=pseudomonas_colonization; hierarchy=unresolved; kind=surrogate; direction=positive; outcome_role=not recorded
- name=ampc_producing_enterobacteria_colonization; hierarchy=unresolved; kind=surrogate; direction=positive; outcome_role=not recorded
- name=esbl_infection_over_2_years; hierarchy=secondary; kind=patient_important; direction=positive; outcome_role=not recorded
- **Limitations:**
  - Combination product (Bactiol duo); colonization on selective culture is a microbiological surrogate; the S. boulardii arm showed no significant change.
  - Doses per strain not stated; industry (Metagenics) co-authors.
- **Rationale / notes:**

## STRAIN_BREVE_M16V

### 27. `m16v_neonatal_jaundice_adjunct_41994268`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 41994268](https://pubmed.ncbi.nlm.nih.gov/41994268/)
- **Identity scope:** exact_strain; components=['STRAIN_BREVE_M16V']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** neonatal_jaundice_phototherapy_adjunct / treatment
- **Population:** 79 neonates with jaundice under phototherapy in a four-arm trial (control / M-16V / Bb-12 / M-16V + Bb-12), 30 days; age_group=infant
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=30; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=phototherapy
- **Outcomes:**
- name=defecation_frequency; hierarchy=unresolved; kind=surrogate; direction=positive; outcome_role=not recorded
- name=transcutaneous_bilirubin_decline; hierarchy=unresolved; kind=surrogate; direction=positive; outcome_role=not recorded
- name=hospital_stay_duration; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- **Limitations:**
  - About 20 infants per arm; the Bb-12 arm's neurodevelopment-domain signals are not recorded under this identity.
  - Industry-adjacent authorship (Diprobio); dose not stated in the abstract.
- **Rationale / notes:**

### 28. `m16v_simpro_five_year_followup_41515257`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 41515257](https://pubmed.ncbi.nlm.nih.gov/41515257/)
- **Identity scope:** exact_strain; components=['STRAIN_BREVE_M16V']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** extremely_preterm_five_year_outcomes / prevention
- **Population:** Extremely preterm infants below 28 weeks from the SiMPro trial followed to five years; age_group=infant
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=not recorded; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=neurodevelopment_5_years; hierarchy=unresolved; kind=patient_important; direction=null; outcome_role=not recorded
- name=growth_5_years; hierarchy=unresolved; kind=patient_important; direction=null; outcome_role=not recorded
- name=blood_pressure_5_years; hierarchy=unresolved; kind=surrogate; direction=null; outcome_role=not recorded
- name=atopy_5_years; hierarchy=unresolved; kind=patient_important; direction=null; outcome_role=not recorded
- **Limitations:**
  - Comparative single- vs triple-strain design without placebo: 'null' here means the arms were comparable, not that M-16V lacks effect versus no treatment.
  - Hospital neonatal population; dose and follow-up sample size not captured from the abstract.
- **Rationale / notes:**

### 29. `m16v_synbiotic_formula_csection_39915586`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 39915586](https://pubmed.ncbi.nlm.nih.gov/39915586/)
- **Identity scope:** exact_strain; components=['STRAIN_BREVE_M16V']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** gut_microbiota_after_cesarean_birth / physiology
- **Population:** 284 healthy cesarean-born infants randomized to a synbiotic formula with M-16V and scGOS/lcFOS versus a prebiotic-only formula; age_group=infant
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=infant formula; duration_days=not recorded; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=scGOS/lcFOS prebiotic blend
- **Outcomes:**
- name=bifidobacterial_restoration; hierarchy=unresolved; kind=surrogate; direction=positive; outcome_role=not recorded
- **Limitations:**
  - Microbiota restoration is a surrogate; formula matrix with prebiotic co-therapy; sponsor-run (Danone).
- **Rationale / notes:**

## STRAIN_COAGULANS_GBI30

### 30. `bc30_functional_gi_complaints_40707016`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 40707016](https://pubmed.ncbi.nlm.nih.gov/40707016/)
- **Identity scope:** exact_strain; components=['STRAIN_COAGULANS_GBI30']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** functional_gastrointestinal_complaints / treatment
- **Population:** 111 healthy adults with functional gastrointestinal complaints; age_group=adult
- **Studied dose:** status=not recorded; basis=discrete_daily_arms; values=1000000000.0; unit=CFU; forms=unresolved; duration_days=28; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=stool_frequency; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- name=stool_consistency; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- name=constipation_proportion; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- **Limitations:**
  - Sponsor-run (Kerry); endpoint hierarchy not stated in the abstract.
- **Rationale / notes:**

### 31. `bc30_geriatric_indigestion_enzymes_32318476`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 32318476](https://pubmed.ncbi.nlm.nih.gov/32318476/)
- **Identity scope:** exact_strain; components=['STRAIN_COAGULANS_GBI30']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** functional_indigestion_elderly / treatment
- **Population:** Elderly adults with functional indigestion; open-label, BC30 co-formulated with digestive enzymes, 5 days; age_group=adult
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=5; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=digestive enzymes (co-formulated)
- **Outcomes:**
- name=dyspepsia_severity; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- **Limitations:**
  - Open label; attribution confounded by the co-formulated digestive enzymes; five-day duration.
- **Rationale / notes:**

### 32. `bc30_synbiotic_pasta_cardiometabolic_31162597`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 31162597](https://pubmed.ncbi.nlm.nih.gov/31162597/)
- **Identity scope:** exact_strain; components=['STRAIN_COAGULANS_GBI30']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** inflammation_and_lipid_markers / physiology
- **Population:** 41 adults consuming a whole-grain pasta with BC30 and barley beta-glucans for 12 weeks; age_group=adult
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=whole-grain pasta; duration_days=84; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=barley beta-glucans
- **Outcomes:**
- name=hs_crp; hierarchy=primary; kind=surrogate; direction=null; outcome_role=not recorded
- name=lipid_profile; hierarchy=primary; kind=surrogate; direction=null; outcome_role=not recorded
- name=subgroup_signals; hierarchy=post_hoc; kind=surrogate; direction=positive; outcome_role=not recorded
- **Limitations:**
  - Primary hs-CRP and lipid endpoints null overall; only subgroups moved.
  - Food matrix and beta-glucan co-therapy confound any strain attribution; single-blind.
- **Rationale / notes:**

## STRAIN_COAGULANS_IS2

### 33. `is2_adult_ibs_multicenter_31434935`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 31434935](https://pubmed.ncbi.nlm.nih.gov/31434935/)
- **Identity scope:** exact_strain; components=['STRAIN_COAGULANS_IS2']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** irritable_bowel_syndrome / treatment
- **Population:** 136 adults with Rome III IBS randomized (153 enrolled), multicenter, India; age_group=adult
- **Studied dose:** status=not recorded; basis=discrete_daily_arms; values=2000000000.0; unit=CFU; forms=unresolved; duration_days=56; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=abdominal_pain_and_discomfort; hierarchy=primary; kind=patient_important; direction=positive; outcome_role=not recorded
- name=complete_spontaneous_bowel_movements; hierarchy=primary; kind=patient_important; direction=positive; outcome_role=not recorded
- name=serum_cytokines; hierarchy=unresolved; kind=surrogate; direction=null; outcome_role=not recorded
- **Limitations:**
  - Manufacturer authorship (Unique Biotech); serum cytokines did not change alongside the symptom improvements.
- **Rationale / notes:**

### 34. `is2_chronic_constipation_meta_36372047`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 36372047](https://pubmed.ncbi.nlm.nih.gov/36372047/)
- **Identity scope:** exact_strain; components=['STRAIN_COAGULANS_IS2']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** chronic_constipation / treatment
- **Population:** Adults with chronic constipation in 30 probiotic RCTs; strain-level subgroups reported; age_group=adult
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=not recorded; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=constipation_response_probiotics_class; hierarchy=primary; kind=patient_important; direction=positive; outcome_role=not recorded
- name=stool_frequency_is2_subgroup; hierarchy=unresolved; kind=patient_important; direction=null; outcome_role=not recorded
- **Limitations:**
  - The class-level benefit is not IS-2 evidence: the IS-2 subgroup was NOT significant for stool frequency (species-level B. lactis was).
  - Pooled trials overlap the IS-2 constipation RCT contexts already recorded; not an independent confirmation.
- **Rationale / notes:**

### 35. `is2_constipation_lactulose_cotherapy_34599466`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 34599466](https://pubmed.ncbi.nlm.nih.gov/34599466/)
- **Identity scope:** exact_strain; components=['STRAIN_COAGULANS_IS2']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** functional_constipation / treatment
- **Population:** 150 adults with functional constipation randomized to IS-2 plus lactulose, lactulose alone, or placebo; age_group=adult
- **Studied dose:** status=not recorded; basis=discrete_daily_arms; values=2000000000.0; unit=spores; forms=unresolved; duration_days=28; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=lactulose 10 g/day
- **Outcomes:**
- name=stool_frequency_vs_lactulose; hierarchy=unresolved; kind=patient_important; direction=mixed; outcome_role=not recorded
- name=stool_consistency; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- name=incomplete_evacuation; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- name=abdominal_pain; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- **Limitations:**
  - The stool-frequency advantage over lactulose alone was transient and not significant at end of trial.
  - Every active arm contained lactulose; nothing here is monotherapy evidence.
- **Rationale / notes:**

### 36. `is2_functional_constipation_30911991`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 30911991](https://pubmed.ncbi.nlm.nih.gov/30911991/)
- **Identity scope:** exact_strain; components=['STRAIN_COAGULANS_IS2']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** functional_constipation / treatment
- **Population:** 100 adults with functional constipation, India; age_group=adult
- **Studied dose:** status=not recorded; basis=discrete_daily_arms; values=2000000000.0; unit=CFU; forms=unresolved; duration_days=28; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=spontaneous_bowel_movements_3_or_more_per_week; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- **Limitations:**
  - Manufacturer-affiliated authors; endpoint hierarchy not stated in the abstract.
- **Rationale / notes:**

### 37. `is2_ibs_strain_level_metas_41682832`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 41682832](https://pubmed.ncbi.nlm.nih.gov/41682832/), [PMID 37686889](https://pubmed.ncbi.nlm.nih.gov/37686889/)
- **Identity scope:** exact_strain; components=['STRAIN_COAGULANS_IS2']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** irritable_bowel_syndrome / treatment
- **Population:** Adults with IBS: a 2026 strain-specific meta-analysis and a 2023 outcome-specific network meta-analysis; age_group=adult
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=not recorded; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=ibs_symptom_efficacy_strain_level; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- name=abdominal_pain_ranking; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- **Limitations:**
  - Both analyses pool the same underlying IS-2 trials already recorded (PMIDs 31434935, 29695183); two meta-analyses of one evidence base count once.
  - Rankings are indirect strain-level comparisons, not pooled IS-2 effect sizes with certainty grades.
- **Rationale / notes:**

### 38. `is2_infrequent_bowel_movements_40456531`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 40456531](https://pubmed.ncbi.nlm.nih.gov/40456531/)
- **Identity scope:** exact_strain; components=['STRAIN_COAGULANS_IS2']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** infrequent_bowel_movements / treatment
- **Population:** 144 healthy adults with infrequent bowel movements (3-7 complete spontaneous BMs/week); age_group=adult
- **Studied dose:** status=not recorded; basis=discrete_daily_arms; values=2000000000.0; unit=CFU; forms=unresolved; duration_days=28; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=bowel_movement_frequency; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- name=stool_consistency; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- name=gastrointestinal_symptoms; hierarchy=unresolved; kind=patient_important; direction=null; outcome_role=not recorded
- name=quality_of_life; hierarchy=unresolved; kind=patient_important; direction=null; outcome_role=not recorded
- name=gut_microbiota_composition; hierarchy=unresolved; kind=surrogate; direction=null; outcome_role=not recorded
- **Limitations:**
  - Sponsor-run (PepsiCo/Nutrasource); frequency effect modest (p=0.037) in a healthy population; symptoms, QoL and microbiota unchanged.
- **Rationale / notes:**

### 39. `is2_moderate_covid19_adjunct_39866999`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 39866999](https://pubmed.ncbi.nlm.nih.gov/39866999/)
- **Identity scope:** exact_strain; components=['STRAIN_COAGULANS_IS2']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** moderate_covid19_adjunctive_care / treatment
- **Population:** 56 adults with moderate COVID-19 on standard treatment; three arms (B. coagulans UBBC-07, IS-2, placebo); age_group=adult
- **Studied dose:** status=not recorded; basis=discrete_daily_arms; values=4000000000.0; unit=spores; forms=unresolved; duration_days=14; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=standard COVID-19 treatment
- **Outcomes:**
- name=serum_ferritin; hierarchy=unresolved; kind=surrogate; direction=positive; outcome_role=not recorded
- name=d_dimer; hierarchy=unresolved; kind=surrogate; direction=positive; outcome_role=not recorded
- name=crp_ldh_il6; hierarchy=unresolved; kind=surrogate; direction=null; outcome_role=not recorded
- **Limitations:**
  - Small three-arm trial (about 19 per arm) with inflammatory-marker surrogates only; ferritin fell in both probiotic arms, D-dimer only in the IS-2 arm.
  - The UBBC-07 arm is a different, non-registry strain; published in Cureus.
  - 2 x 10^9 spores twice daily (4 x 10^9/day).
- **Rationale / notes:**

### 40. `is2_pediatric_ibs_chewable_29695183`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 29695183](https://pubmed.ncbi.nlm.nih.gov/29695183/)
- **Identity scope:** exact_strain; components=['STRAIN_COAGULANS_IS2']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** pediatric_irritable_bowel_syndrome / treatment
- **Population:** 141 children 4-12 years with IBS, chewable tablet once daily; age_group=child
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=chewable tablet; duration_days=56; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=abdominal_pain_intensity; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- **Limitations:**
  - Daily CFU dose not machine-readable in the retrieved abstract; manufacturer-affiliated authors.
  - Endpoint hierarchy not stated in the abstract.
- **Rationale / notes:**

### 41. `is2_whey_protein_strength_35249118`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 35249118](https://pubmed.ncbi.nlm.nih.gov/35249118/)
- **Identity scope:** exact_strain; components=['STRAIN_COAGULANS_IS2']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** protein_absorption_and_muscle_performance / physiology
- **Population:** Resistance-trained males co-supplementing whey protein for 60 days; age_group=adult
- **Studied dose:** status=not recorded; basis=discrete_daily_arms; values=2000000000.0; unit=CFU; forms=unresolved; duration_days=60; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=whey protein 20 g/day
- **Outcomes:**
- name=plasma_bcaa_absorption; hierarchy=unresolved; kind=surrogate; direction=positive; outcome_role=not recorded
- name=leg_press_strength; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- name=vertical_jump; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- **Limitations:**
  - Surrogate-heavy; industry co-authors; performance findings from a small trained-athlete sample.
- **Rationale / notes:**

## STRAIN_COAGULANS_MTCC5856

### 42. `mtcc5856_functional_gas_bloating_36862903`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 36862903](https://pubmed.ncbi.nlm.nih.gov/36862903/)
- **Identity scope:** exact_strain; components=['STRAIN_COAGULANS_MTCC5856']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** functional_gas_and_bloating / treatment
- **Population:** 70 adults with functional gas and bloating (66 completed); age_group=adult
- **Studied dose:** status=not recorded; basis=discrete_daily_arms; values=2000000000.0; unit=spores; forms=unresolved; duration_days=28; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=gsrs_indigestion_score; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- name=patient_global_assessment; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- **Limitations:**
  - Manufacturer-run; four-week duration; endpoint hierarchy not stated in the abstract.
- **Rationale / notes:**

### 43. `mtcc5856_healthy_microbiome_37335737`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 37335737](https://pubmed.ncbi.nlm.nih.gov/37335737/)
- **Identity scope:** exact_strain; components=['STRAIN_COAGULANS_MTCC5856']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** gut_microbiome_composition / physiology
- **Population:** 30 healthy adults; microbiome and safety study; age_group=adult
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=28; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=gut_microbiome_composition; hierarchy=unresolved; kind=surrogate; direction=null; outcome_role=not recorded
- **Limitations:**
  - Gut microbiome composition essentially unchanged; the abstract states 2 x 10^9 CFU per capsule without capsules/day, so the daily dose is unresolved.
- **Rationale / notes:**

### 44. `mtcc5856_ibs_d_pilot_26922379`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 26922379](https://pubmed.ncbi.nlm.nih.gov/26922379/)
- **Identity scope:** exact_strain; components=['STRAIN_COAGULANS_MTCC5856']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** irritable_bowel_syndrome_diarrhea_predominant / treatment
- **Population:** 36 adults with diarrhea-predominant IBS at three centres, India; standard care in both arms; age_group=adult
- **Studied dose:** status=not recorded; basis=discrete_daily_arms; values=2000000000.0; unit=CFU; forms=unresolved; duration_days=90; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=standard care
- **Outcomes:**
- name=bloating; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- name=vomiting; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- name=diarrhea; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- name=abdominal_pain; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- name=stool_frequency; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- **Limitations:**
  - Pilot size (n=36); manufacturer-run (Sami/Sabinsa).
- **Rationale / notes:**

### 45. `mtcc5856_ibs_strain_level_metas_41682832`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 41682832](https://pubmed.ncbi.nlm.nih.gov/41682832/), [PMID 37686889](https://pubmed.ncbi.nlm.nih.gov/37686889/)
- **Identity scope:** exact_strain; components=['STRAIN_COAGULANS_MTCC5856']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** irritable_bowel_syndrome / treatment
- **Population:** Adults with IBS: a 2026 strain-specific meta-analysis and a 2023 outcome-specific network meta-analysis; age_group=adult
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=not recorded; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=ibs_quality_of_life; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- name=abdominal_pain_ranking; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- name=ibs_d_stool_form_ranking; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- **Limitations:**
  - Both analyses pool the same underlying MTCC 5856 trials already recorded (PMIDs 26922379, 29997457); two meta-analyses of one evidence base count once.
  - Rankings are indirect strain-level comparisons, not pooled effect sizes with certainty grades.
- **Rationale / notes:**

### 46. `mtcc5856_mdd_with_ibs_29997457`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 29997457](https://pubmed.ncbi.nlm.nih.gov/29997457/)
- **Identity scope:** exact_strain; components=['STRAIN_COAGULANS_MTCC5856']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** major_depression_with_irritable_bowel_syndrome / treatment
- **Population:** 40 adults with major depressive disorder and IBS, India; age_group=adult
- **Studied dose:** status=not recorded; basis=discrete_daily_arms; values=2000000000.0; unit=spores; forms=unresolved; duration_days=90; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=hamilton_depression_score; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- name=madrs_score; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- name=ces_d_score; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- name=ibs_quality_of_life; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- name=serum_myeloperoxidase; hierarchy=unresolved; kind=surrogate; direction=positive; outcome_role=not recorded
- **Limitations:**
  - Pilot size (n=40); manufacturer-run; a single trial carries every mood endpoint.
- **Rationale / notes:**

### 47. `mtcc5856_pediatric_acute_diarrhea_38269290`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 38269290](https://pubmed.ncbi.nlm.nih.gov/38269290/)
- **Identity scope:** exact_strain; components=['STRAIN_COAGULANS_MTCC5856']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** pediatric_acute_gastroenteritis / treatment
- **Population:** 110 children 1-10 years with acute diarrhea; oral rehydration solution and zinc in both arms; age_group=child
- **Studied dose:** status=not recorded; basis=discrete_daily_arms; values=800000000.0; unit=spores; forms=sachet; duration_days=5; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=oral rehydration solution, zinc
- **Outcomes:**
- name=diarrhea_duration; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- name=stool_frequency; hierarchy=unresolved; kind=patient_important; direction=null; outcome_role=not recorded
- **Limitations:**
  - Duration fell (51.3 vs 62.7 h, p=0.011) but stool frequency did not differ.
  - Each sachet contained 4 x 10^8 spores and was taken twice daily (8 x 10^8 spores/day); ORS and zinc were co-therapies.
- **Rationale / notes:**

## STRAIN_HELVETICUS_R0052

### 48. `r0052_r0175_healthy_adults_null_37049546`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 37049546](https://pubmed.ncbi.nlm.nih.gov/37049546/)
- **Identity scope:** combination; components=['STRAIN_HELVETICUS_R0052', 'STRAIN_LONGUM_R0175']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** psychological_wellbeing_healthy_adults / physiology
- **Population:** 135 healthy adults, 4 weeks; age_group=adult
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=28; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=whole_sample_psychological_outcomes; hierarchy=primary; kind=patient_important; direction=null; outcome_role=not recorded
- name=lifestyle_interaction_effects; hierarchy=post_hoc; kind=patient_important; direction=positive; outcome_role=not recorded
- **Limitations:**
  - No significant whole-sample effects; the lifestyle-interaction finding is exploratory.
- **Rationale / notes:**

### 49. `r0052_r0175_mdd_bdnf_secondary_32989186`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 32989186](https://pubmed.ncbi.nlm.nih.gov/32989186/)
- **Identity scope:** combination; components=['STRAIN_HELVETICUS_R0052', 'STRAIN_LONGUM_R0175']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** major_depressive_disorder / treatment
- **Population:** 110 adults with major depressive disorder randomized (78 analyzed), 8 weeks; probiotic vs prebiotic vs placebo; age_group=adult
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=56; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=depressive_symptoms_parent_trial; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- name=serum_bdnf; hierarchy=unresolved; kind=surrogate; direction=positive; outcome_role=not recorded
- **Limitations:**
  - Secondary (BDNF) analysis of the Kazemi cohort; the parent trial's primary outcome paper was not read this wave, and its depression improvement is restated in this abstract.
  - Dose not stated in the retrieved abstract.
- **Rationale / notes:**

### 50. `r0052_r0175_mdd_open_pilot_33658952`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 33658952](https://pubmed.ncbi.nlm.nih.gov/33658952/)
- **Identity scope:** combination; components=['STRAIN_HELVETICUS_R0052', 'STRAIN_LONGUM_R0175']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** major_depressive_disorder / treatment
- **Population:** 10 treatment-naive adults with major depressive disorder; open-label single-arm pilot; age_group=adult
- **Studied dose:** status=not recorded; basis=discrete_daily_arms; values=3000000000.0; unit=CFU; forms=unresolved; duration_days=56; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=affective_symptoms; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- **Limitations:**
  - No control arm; ten participants; hypothesis-generating only.
- **Rationale / notes:**

### 51. `r0052_r0175_psychological_distress_20974015`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 20974015](https://pubmed.ncbi.nlm.nih.gov/20974015/)
- **Identity scope:** combination; components=['STRAIN_HELVETICUS_R0052', 'STRAIN_LONGUM_R0175']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** psychological_distress / treatment
- **Population:** Healthy human volunteers taking the R0052 + R0175 formulation for 30 days (Messaoudi 2011); age_group=adult
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=30; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=hscl90_global_severity; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- name=hospital_anxiety_depression_scale; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- name=urinary_free_cortisol; hierarchy=unresolved; kind=surrogate; direction=positive; outcome_role=not recorded
- **Limitations:**
  - Dose and sample size not stated in the retrieved abstract; the paper's rat arm is not a human context.
- **Rationale / notes:**

## STRAIN_LACTIS_BB12

### 52. `bb12_low_stool_frequency_26382580`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 26382580](https://pubmed.ncbi.nlm.nih.gov/26382580/)
- **Identity scope:** exact_strain; components=['STRAIN_LACTIS_BB12']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** low_stool_frequency / treatment
- **Population:** 1248 generally healthy adults with low stool frequency and abdominal discomfort; age_group=adult
- **Studied dose:** status=not recorded; basis=discrete_daily_arms; values=1000000000, 10000000000; unit=CFU; forms=capsule; duration_days=28; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=defecation_frequency_responder; hierarchy=primary; kind=patient_important; direction=null; outcome_role=not recorded
- name=global_abdominal_relief; hierarchy=primary; kind=patient_important; direction=null; outcome_role=not recorded
- name=tightened_frequency_responder; hierarchy=post_hoc; kind=patient_important; direction=positive; outcome_role=not recorded
- **Limitations:**
  - Original overall frequency-responder OR 1.31 (95% CI .98–1.75); the stronger responder result used a post hoc definition. Average-frequency analyses were favorable.
  - Similar effects at 1B and 10B do not establish benefit at intermediate doses or a dose-response advantage.
  - Not a diagnosed functional-constipation population; industry funded with disclosed relationships.
- **Rationale / notes:**

### 53. `bb12_preterm_inflammation_feeding_39271904`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 39271904](https://pubmed.ncbi.nlm.nih.gov/39271904/)
- **Identity scope:** exact_strain; components=['STRAIN_LACTIS_BB12']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** preterm_inflammation_and_feeding_intolerance / prevention
- **Population:** 71 preterm infants at or below 32 weeks, BB-12 as the sole probiotic; age_group=infant
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=not recorded; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=serum_tlr4_nfkb_il1b_tnfa; hierarchy=unresolved; kind=surrogate; direction=positive; outcome_role=not recorded
- name=feeding_intolerance; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- **Limitations:**
  - Surrogate-heavy inflammatory-marker panel; hospital neonatal population; dose not stated in the abstract.
- **Rationale / notes:**

### 54. `casei431_bb12_dracma_cma_tolerance_39310372`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 39310372](https://pubmed.ncbi.nlm.nih.gov/39310372/)
- **Identity scope:** combination; components=['STRAIN_CASEI_431', 'STRAIN_LACTIS_BB12']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** cow_milk_allergy_tolerance_acquisition / treatment
- **Population:** Infants with cow's milk allergy fed extensively hydrolyzed casein formula with L. casei CRL431 and Bb-12; WAO DRACMA systematic review; age_group=infant
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=not recorded; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=extensively hydrolyzed casein formula
- **Outcomes:**
- name=cow_milk_tolerance_acquisition; hierarchy=guideline; kind=patient_important; direction=positive; outcome_role=not recorded
- name=severe_wheezing; hierarchy=guideline; kind=patient_important; direction=positive; outcome_role=not recorded
- **Limitations:**
  - LOW certainty (tolerance RR 2.47); the formula itself is the delivery vehicle and co-therapy, so this is not supplement evidence.
  - Medical condition (cow's milk allergy) managed under clinical supervision.
- **Rationale / notes:**

### 55. `lgg_bb12_pediatric_ad_prevention_meta_33811784`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 33811784](https://pubmed.ncbi.nlm.nih.gov/33811784/)
- **Identity scope:** combination; components=['STRAIN_LGG', 'STRAIN_LACTIS_BB12']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** childhood_atopic_dermatitis / prevention
- **Population:** 21 RCTs (n=5406) of probiotics for pediatric atopic-dermatitis prevention; network meta-analysis; age_group=infant
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=not recorded; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=atopic_dermatitis_risk_lgg_bb12; hierarchy=primary; kind=patient_important; direction=positive; outcome_role=not recorded
- **Limitations:**
  - The LGG + Bb-12 node estimate (RR 0.50) is graded LOW quality by the reviewers.
  - Pooled trials overlap the ProPACT family context recorded this wave; not an independent confirmation of it.
- **Rationale / notes:**

### 56. `lgg_bb12_preterm_administration_route_37020105`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 37020105](https://pubmed.ncbi.nlm.nih.gov/37020105/)
- **Identity scope:** combination; components=['STRAIN_LGG', 'STRAIN_LACTIS_BB12']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** preterm_gut_microbiota_colonization / physiology
- **Population:** 68 preterm neonates randomized to direct LGG + Bb-12 administration or administration via the lactating mother; age_group=infant
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=not recorded; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=bifidobacterial_colonization_direct_administration; hierarchy=unresolved; kind=surrogate; direction=positive; outcome_role=not recorded
- name=microbiota_change_via_maternal_route; hierarchy=unresolved; kind=surrogate; direction=null; outcome_role=not recorded
- **Limitations:**
  - Route-comparison design without placebo; microbiota composition is a surrogate; dose not stated in the abstract.
- **Rationale / notes:**

## STRAIN_LACTIS_BI07

### 57. `bi07_lactose_challenges_36149331`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 36149331](https://pubmed.ncbi.nlm.nih.gov/36149331/)
- **Identity scope:** exact_strain; components=['STRAIN_LACTIS_BI07']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** lactose_maldigestion / challenge
- **Population:** Adults with lactose intolerance in Booster Alpha and Omega crossover challenges; age_group=adult
- **Studied dose:** status=not recorded; basis=single_challenge; values=2400000000000, 2340000000000; unit=CFU; forms=powder, sachet; duration_days=not recorded; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=25 g lactose with milk in Alpha or water in Omega; one-week washouts
- **Outcomes:**
- name=breath_hydrogen; hierarchy=primary; kind=surrogate; direction=positive; outcome_role=not recorded
- name=gastrointestinal_symptoms; hierarchy=secondary; kind=patient_important; direction=null; outcome_role=not recorded
- name=nausea_omega; hierarchy=secondary; kind=patient_important; direction=negative; outcome_role=not recorded
- **Limitations:**
  - Methods give 2.40T CFU in Alpha and 2.34T in Omega; the abstract rounds to 2T. Not a daily-use dosing interval.
  - Surrogate lactose digestion benefit is not symptom relief. More nausea was reported in Omega; questionnaire and blinding limitations apply.
  - Industry supported; these two challenge experiments are not two independent chronic symptom-efficacy replications.
- **Rationale / notes:**

### 58. `ncfm_bi07_bloating_21436726`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 21436726](https://pubmed.ncbi.nlm.nih.gov/21436726/)
- **Identity scope:** combination; components=['STRAIN_ACIDOPHILUS_NCFM', 'STRAIN_LACTIS_BI07']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** functional_bowel_disorders / treatment
- **Population:** 60 adults with non-constipation functional bowel disorders; age_group=adult
- **Studied dose:** status=not recorded; basis=discrete_daily_arms; values=200000000000; unit=CFU; forms=pill; duration_days=56; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=global_gastrointestinal_relief; hierarchy=primary; kind=patient_important; direction=null; outcome_role=not recorded
- name=treatment_satisfaction; hierarchy=primary; kind=patient_important; direction=null; outcome_role=not recorded
- name=bloating; hierarchy=secondary; kind=patient_important; direction=positive; outcome_role=not recorded
- **Limitations:**
  - 200B total daily is the combination dose. The study states equal amounts in twice-daily 100B pills; this cannot allocate an unspecified product blend or establish either strain alone.
  - Small heterogeneous industry-supported pilot; primary global outcomes negative, bloating a secondary finding.
- **Rationale / notes:**

## STRAIN_LACTIS_BL04

### 59. `bl04_active_adult_respiratory_24268677`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 24268677](https://pubmed.ncbi.nlm.nih.gov/24268677/)
- **Identity scope:** exact_strain; components=['STRAIN_LACTIS_BL04']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** upper_respiratory_illness / prevention
- **Population:** Healthy physically active adults; Bl-04-only arm of a 465-participant three-arm trial; age_group=adult
- **Studied dose:** status=not recorded; basis=discrete_daily_arms; values=2000000000; unit=CFU; forms=drink; duration_days=not recorded; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=upper_respiratory_illness_risk; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- **Limitations:**
  - Bl-04 hazard ratio 0.73, 95% CI 0.55–0.95; this is not a universal 27% benefit for every user
  - Distinct NCFM plus Bi-07 arm was not significantly better than placebo
  - Too few gastrointestinal episodes for a useful analysis
  - Duration and prespecified endpoint hierarchy were not established in the inspected abstract; do not infer adult digestive applicability
- **Rationale / notes:**

### 60. `bl04_cardiovascular_risk_markers_healthy_33161737`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 33161737](https://pubmed.ncbi.nlm.nih.gov/33161737/)
- **Identity scope:** exact_strain; components=['STRAIN_LACTIS_BL04']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** cardiovascular_risk_markers / physiology
- **Population:** Healthy adults 18-65 y (BMI 20-34.9), Bl-04 with or without bacteriophage cocktail arm; age_group=adult
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=28; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=cardiovascular_risk_parameters; hierarchy=primary; kind=surrogate; direction=null; outcome_role=not recorded
- **Limitations:**
  - No significant change in measured CVD parameters with Bl-04 (with or without bacteriophages); the same trial's DE111 arm is recorded separately.
  - Dose not stated in the abstract; largely healthy population.
- **Rationale / notes:**

### 61. `bl04_fermented_milk_urti_haze_adults_34062085`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 34062085](https://pubmed.ncbi.nlm.nih.gov/34062085/)
- **Identity scope:** exact_strain; components=['STRAIN_LACTIS_BL04']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** upper_respiratory_tract_infection / prevention
- **Population:** 136 adults living in a haze-covered area of northern China consuming 250 g yogurt daily; age_group=adult
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=fermented milk; duration_days=84; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=common_cold_incidence; hierarchy=primary; kind=patient_important; direction=positive; outcome_role=not recorded
- name=influenza_like_illness_incidence; hierarchy=secondary; kind=patient_important; direction=positive; outcome_role=not recorded
- name=urti_duration; hierarchy=secondary; kind=patient_important; direction=positive; outcome_role=not recorded
- name=urti_severity; hierarchy=secondary; kind=patient_important; direction=positive; outcome_role=not recorded
- name=interferon_gamma_and_secretory_iga; hierarchy=secondary; kind=surrogate; direction=positive; outcome_role=not recorded
- **Limitations:**
  - Food-matrix delivery (yogurt); CFU dose not stated; single-site industry study (Bright Dairy).
  - Population exposed to air pollution; generalization to supplements is not established.
- **Rationale / notes:**

### 62. `bl04_rhinovirus_challenge_28343401`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 28343401](https://pubmed.ncbi.nlm.nih.gov/28343401/)
- **Identity scope:** exact_strain; components=['STRAIN_LACTIS_BL04']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** experimental_rhinovirus_infection / challenge
- **Population:** Healthy rhinovirus-susceptible adult volunteers; 152 randomized before experimental RV-A39 challenge; age_group=adult
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=sachet, drink; duration_days=33; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=experimental RV-A39 inoculation after 28 days
- **Outcomes:**
- name=nasal_lavage_cxcl8_response; hierarchy=primary; kind=surrogate; direction=positive; outcome_role=not recorded
- name=subjective_cold_symptoms; hierarchy=secondary; kind=patient_important; direction=null; outcome_role=not recorded
- name=infection_rate; hierarchy=secondary; kind=patient_important; direction=null; outcome_role=not recorded
- **Limitations:**
  - Daily sachet supplied a minimum of 2 billion CFU, not an exact verified dose or an unbounded efficacy range
  - Primary inflammatory marker is a surrogate; cold symptoms did not improve
  - Challenge model is not routine community infection prevention
  - Industry sponsored the trial; baseline CXCL8 differed between groups
- **Rationale / notes:**

### 63. `bl04_rhinovirus_challenge_phase2_34927036`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 34927036](https://pubmed.ncbi.nlm.nih.gov/34927036/)
- **Identity scope:** exact_strain; components=['STRAIN_LACTIS_BL04']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** experimental_rhinovirus_infection / challenge
- **Population:** 334 healthy US university-community volunteers randomized (232 analyzed); 28 days of Bl-04 or placebo then RV-A39 challenge; age_group=adult
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=28; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=rhinovirus_associated_illness; hierarchy=primary; kind=patient_important; direction=null; outcome_role=not recorded
- **Limitations:**
  - Illness 56% vs 50% (p=0.34); no effect of oral Bl-04 on rhinovirus-associated illness.
  - This larger phase II trial does not reproduce the earlier positive challenge result already recorded (PMID 28343401).
  - Funded by Danisco/IFF; dose not stated in the abstract.
- **Rationale / notes:**

## STRAIN_LACTIS_HN019

### 64. `hn019_constipation_39356506`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 39356506](https://pubmed.ncbi.nlm.nih.gov/39356506/)
- **Identity scope:** exact_strain; components=['STRAIN_LACTIS_HN019']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** functional_constipation / treatment
- **Population:** 229 adults aged 18–70 with Rome III functional constipation, China; age_group=adult
- **Studied dose:** status=not recorded; basis=measured_viability; values=7000000000, 4690000000; unit=CFU; forms=powder, sachet; duration_days=56; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=complete_spontaneous_bowel_movements; hierarchy=primary; kind=patient_important; direction=null; outcome_role=not recorded
- **Limitations:**
  - 7.0B at first visit and 4.69B at last visit describe measured potency of one once-daily 2-g sachet regimen, not randomized dose arms or an efficacy range.
  - Primary between-group outcome P=.37; null for this outcome does not establish lack of benefit in every context.
  - Industry funded with sponsor involvement in planning, analysis and interpretation.
- **Rationale / notes:**

### 65. `hn019_constipation_40320938`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 40320938](https://pubmed.ncbi.nlm.nih.gov/40320938/)
- **Identity scope:** exact_strain; components=['STRAIN_LACTIS_HN019']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** functional_constipation / treatment
- **Population:** Adults with Rome III functional constipation, four French clinical units; age_group=adult
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=56; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=complete_spontaneous_bowel_movements; hierarchy=primary; kind=patient_important; direction=null; outcome_role=not recorded
- **Limitations:**
  - Primary abstract verified; exact CFU/formulation and full-method limitations not established in this pass.
  - A separate null eight-week constipation trial, not a companion analysis of the China trial; no universal ineffectiveness inference.
- **Rationale / notes:**

### 66. `hn019_elderly_cellular_immunity_meta_28245559`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 28245559](https://pubmed.ncbi.nlm.nih.gov/28245559/)
- **Identity scope:** exact_strain; components=['STRAIN_LACTIS_HN019']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** cellular_immune_function / physiology
- **Population:** Healthy elderly adults in 4 controlled trials; age_group=adult
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=not recorded; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=pmn_phagocytic_capacity; hierarchy=primary; kind=surrogate; direction=positive; outcome_role=not recorded
- name=nk_cell_tumoricidal_activity; hierarchy=primary; kind=surrogate; direction=positive; outcome_role=not recorded
- **Limitations:**
  - Four trials, short follow-up, single strain; surrogate immune assays, no clinical infection outcome.
  - Manufacturer co-authors (DuPont).
- **Rationale / notes:**

### 67. `hn019_functional_constipation_dose_ranging_28d_29227175`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 29227175](https://pubmed.ncbi.nlm.nih.gov/29227175/)
- **Identity scope:** exact_strain; components=['STRAIN_LACTIS_HN019']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** functional_constipation / treatment
- **Population:** 228 adults with Rome III functional constipation; two daily dose arms for 28 days; age_group=adult
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=28; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=colonic_transit_time; hierarchy=primary; kind=patient_important; direction=null; outcome_role=not recorded
- name=pac_sym_pac_qol_bowel_function; hierarchy=secondary; kind=patient_important; direction=null; outcome_role=not recorded
- name=bowel_movement_frequency_low_frequency_subgroup; hierarchy=post_hoc; kind=patient_important; direction=positive; outcome_role=not recorded
- name=straining_low_frequency_subgroup_high_dose; hierarchy=post_hoc; kind=patient_important; direction=positive; outcome_role=not recorded
- **Limitations:**
  - No differences in primary or secondary outcomes; benefit only in a post hoc subgroup with <= 3 bowel movements/week.
  - The two daily doses (1 x 10^9 and 1 x 10^10 as printed) are not machine-readable in the retrieved abstract; left unresolved.
  - Superseded for functional constipation by the larger null trials already recorded (PMIDs 39356506, 40320938).
- **Rationale / notes:**

### 68. `hn019_hn001_functional_constipation_vs_fibers_37078654`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 37078654](https://pubmed.ncbi.nlm.nih.gov/37078654/)
- **Identity scope:** combination; components=['STRAIN_LACTIS_HN019', 'STRAIN_RHAMNOSUS_HN001']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** functional_constipation / treatment
- **Population:** 250 adults with functional constipation randomized across five arms (three fiber formulas, HN019 + HN001, placebo); 242 completed; age_group=adult
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=28; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=oligosaccharides in all active arms
- **Outcomes:**
- name=bowel_movement_frequency; hierarchy=primary; kind=patient_important; direction=null; outcome_role=not recorded
- name=bristol_stool_scale; hierarchy=secondary; kind=patient_important; direction=positive; outcome_role=not recorded
- name=defecation_straining; hierarchy=secondary; kind=patient_important; direction=null; outcome_role=not recorded
- **Limitations:**
  - No time-by-group effect for frequency, stool form or straining; stool-form gains were within-arm and shared with fiber arms.
  - Probiotic arm also contained oligosaccharides; per-strain dose not stated.
- **Rationale / notes:**

### 69. `hn019_intestinal_transit_meta_27275105`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 27275105](https://pubmed.ncbi.nlm.nih.gov/27275105/)
- **Identity scope:** exact_strain; components=['STRAIN_LACTIS_HN019']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** intestinal_transit_time / treatment
- **Population:** Adults in 15 short-term probiotic RCTs measuring intestinal transit time (n=675); HN019 strain subgroup; age_group=adult
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=not recorded; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=intestinal_transit_time_hn019; hierarchy=primary; kind=patient_important; direction=positive; outcome_role=not recorded
- **Limitations:**
  - Pooled SMD 0.67 for HN019 from short-term trials; predates the two large null functional-constipation RCTs (2024, 2025).
  - Authors include the manufacturer (Ouwehand) and an industry-funded consultancy.
- **Rationale / notes:**

### 70. `m16v_hn019_hn001_pediatric_urti_fever_duration_40085083`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 40085083](https://pubmed.ncbi.nlm.nih.gov/40085083/)
- **Identity scope:** combination; components=['STRAIN_BREVE_M16V', 'STRAIN_LACTIS_HN019', 'STRAIN_RHAMNOSUS_HN001']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** upper_respiratory_tract_infection_fever / treatment
- **Population:** 128 children 28 days to 4 years with fever >= 38.5 C and upper respiratory tract infection, pediatric emergency department, Milan; age_group=child
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=oral drops; duration_days=14; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=fever_duration; hierarchy=primary; kind=patient_important; direction=positive; outcome_role=not recorded
- name=adverse_events; hierarchy=secondary; kind=patient_important; direction=null; outcome_role=not recorded
- **Limitations:**
  - Median fever duration 3 vs 5 days (adjusted RR 0.64); 0.5 mL daily of a three-strain mixture, CFU not stated.
  - Combination evidence; nothing here attributes the effect to any single strain.
- **Rationale / notes:**

## STRAIN_LGG

### 71. `lgg_adult_ibs_open_label_vs_diet_25473176`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 25473176](https://pubmed.ncbi.nlm.nih.gov/25473176/)
- **Identity scope:** exact_strain; components=['STRAIN_LGG']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** irritable_bowel_syndrome / treatment
- **Population:** 123 adults with Rome III IBS (median age 37; 73% female), Denmark; age_group=adult
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=42; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=ibs_severity_score_change; hierarchy=primary; kind=patient_important; direction=null; outcome_role=not recorded
- name=ibs_quality_of_life; hierarchy=secondary; kind=patient_important; direction=null; outcome_role=not recorded
- **Limitations:**
  - Unblinded three-arm trial; after adjustment for baseline covariates the LGG vs normal-diet IBS-SSS reduction was not significant (32 points; p=0.20) although the unadjusted comparison was.
  - Dose not stated in the abstract.
- **Rationale / notes:**

### 72. `lgg_covid19_post_exposure_prophylaxis_38103462`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 38103462](https://pubmed.ncbi.nlm.nih.gov/38103462/)
- **Identity scope:** exact_strain; components=['STRAIN_LGG']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** covid19_post_exposure / prevention
- **Population:** 182 US participants with household exposure to a confirmed COVID-19 case within 7 days; age_group=unknown
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=28; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=illness_symptoms_within_28_days; hierarchy=primary; kind=patient_important; direction=positive; outcome_role=not recorded
- name=covid19_diagnosis_incidence; hierarchy=secondary; kind=patient_important; direction=null; outcome_role=not recorded
- name=time_to_covid19_diagnosis; hierarchy=secondary; kind=patient_important; direction=positive; outcome_role=not recorded
- **Limitations:**
  - Symptom incidence 26.4% vs 42.9% (p=0.02); overall COVID-19 diagnosis incidence 8.8% vs 15.4% was not significant (p=0.17).
  - Described by the authors as an initial study; daily CFU dose not given in the abstract.
- **Rationale / notes:**

### 73. `lgg_gi_respiratory_outcomes_meta_40702885`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 40702885](https://pubmed.ncbi.nlm.nih.gov/40702885/)
- **Identity scope:** exact_strain; components=['STRAIN_LGG']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** gastrointestinal_and_respiratory_infections / prevention
- **Population:** 69 RCTs of LGG supplementation; children and adults; effects more consistent in children, adult evidence limited; age_group=mixed
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=not recorded; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=composite_gastrointestinal_outcomes; hierarchy=primary; kind=patient_important; direction=positive; outcome_role=not recorded
- name=diarrhea_risk; hierarchy=secondary; kind=patient_important; direction=positive; outcome_role=not recorded
- name=diarrhea_duration; hierarchy=secondary; kind=patient_important; direction=positive; outcome_role=not recorded
- name=respiratory_infection_risk; hierarchy=primary; kind=patient_important; direction=positive; outcome_role=not recorded
- name=respiratory_symptom_risk; hierarchy=secondary; kind=patient_important; direction=null; outcome_role=not recorded
- name=other_gastrointestinal_symptoms; hierarchy=secondary; kind=patient_important; direction=null; outcome_role=not recorded
- **Limitations:**
  - Pooled RR 0.88 for composite GI outcomes is driven by diarrhea (RR 0.64); prediction intervals crossed the null for most other outcomes.
  - Moderate-to-high heterogeneity; certainty moderate for diarrhea and mostly low elsewhere; adult evidence limited.
  - Industry co-authorship (SIRIO). Pooled trials overlap the pediatric AAD guideline and pediatric pain contexts already recorded; not an independent confirmation of them.
  - No single studied CFU dose can be read from a meta-analysis.
- **Rationale / notes:**

### 74. `lgg_icu_ventilator_pneumonia_prospect_34546300`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 34546300](https://pubmed.ncbi.nlm.nih.gov/34546300/)
- **Identity scope:** exact_strain; components=['STRAIN_LGG']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** ventilator_associated_pneumonia / prevention
- **Population:** 2653 critically ill adults predicted to need mechanical ventilation >= 72 h in 44 ICUs (Canada, USA, Saudi Arabia); age_group=adult
- **Studied dose:** status=not recorded; basis=discrete_daily_arms; values=20000000000.0; unit=CFU; forms=enteral; duration_days=not recorded; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=ventilator_associated_pneumonia; hierarchy=primary; kind=patient_important; direction=null; outcome_role=not recorded
- name=other_icu_acquired_infections; hierarchy=secondary; kind=patient_important; direction=null; outcome_role=not recorded
- name=diarrhea; hierarchy=secondary; kind=patient_important; direction=null; outcome_role=not recorded
- name=mortality; hierarchy=secondary; kind=patient_important; direction=null; outcome_role=not recorded
- name=lgg_isolation_from_sterile_or_predominant_site; hierarchy=secondary; kind=patient_important; direction=negative; outcome_role=not recorded
- **Limitations:**
  - 1 x 10^10 CFU twice daily (2 x 10^10/day) for a median of 9 days in ventilated ICU patients; none of 20 secondary outcomes differed.
  - Harm signal: L. rhamnosus isolated in a sterile site or as the predominant organism in 1.1% vs 0.1% (OR 14.02). Population-specific; not evidence about healthy consumers.
  - Cost-effectiveness companion analysis (PMID 36289153) found probiotics dominated by usual care.
- **Rationale / notes:**

### 75. `lgg_pediatric_aad_guideline_26756877`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 26756877](https://pubmed.ncbi.nlm.nih.gov/26756877/)
- **Identity scope:** exact_strain; components=['STRAIN_LGG']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** antibiotic_associated_diarrhea / prevention
- **Population:** Children at risk of antibiotic-associated diarrhea; age_group=child
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=not recorded; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=Antibiotic course
- **Outcomes:**
- name=antibiotic_associated_diarrhea_incidence; hierarchy=guideline; kind=patient_important; direction=positive; outcome_role=not recorded
- **Limitations:**
  - Moderate-quality evidence and strong pediatric prevention recommendation; not treatment or adult general-use support.
  - Inspected abstract does not establish an exact dose, form or duration; guideline aggregates trials and is not another independent RCT.
- **Rationale / notes:**

### 76. `lgg_pediatric_functional_abdominal_pain_meta_41883407`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 41883407](https://pubmed.ncbi.nlm.nih.gov/41883407/), [PMID 42477222](https://pubmed.ncbi.nlm.nih.gov/42477222/)
- **Identity scope:** exact_strain; components=['STRAIN_LGG']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** functional_abdominal_pain_disorders / treatment
- **Population:** Children 4-18 y with functional abdominal pain disorders; 21 RCTs (n=1807) network meta-analysis and a 21-trial (n=1899) pairwise meta-analysis; age_group=child
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=not recorded; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=global_improvement_probiotics_vs_placebo; hierarchy=primary; kind=patient_important; direction=positive; outcome_role=not recorded
- name=complete_pain_resolution; hierarchy=primary; kind=patient_important; direction=positive; outcome_role=not recorded
- name=lgg_strain_level_ranking; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- **Limitations:**
  - Class-level pooled effects; the LGG-specific finding is an indirect SUCRA ranking, not a pooled LGG estimate.
  - Certainty rated low to moderate; when success was defined by author thresholds response rates did not differ from placebo (PMID 42477222).
  - Overlaps the pediatric pain RCT already recorded (PMID 17229242); two meta-analyses of one evidence base count once.
- **Rationale / notes:**

### 77. `lgg_pediatric_pain_17229242`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 17229242](https://pubmed.ncbi.nlm.nih.gov/17229242/)
- **Identity scope:** exact_strain; components=['STRAIN_LGG']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** functional_abdominal_pain / treatment
- **Population:** 104 children aged 6–16 with Rome II functional abdominal pain disorders; IBS subgroup n=37; age_group=child
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=capsule; duration_days=28; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=pain_free_response; hierarchy=primary; kind=patient_important; direction=mixed; outcome_role=not recorded
- name=pain_severity; hierarchy=secondary; kind=patient_important; direction=null; outcome_role=not recorded
- **Limitations:**
  - Methods and flow diagram describe 3B CFU twice daily; Discussion says 3B daily. Do not select an automated dose until this conflict is resolved.
  - Overall primary outcome P=.08 in Table 2 conflicts with the reported relative-benefit interval excluding one. Authors report benefit, especially the small IBS subgroup; retain the inconsistency and wide intervals.
  - No clear FD/FAP subgroup benefit; university funded, product supplied by manufacturer.
- **Rationale / notes:**

### 78. `lgg_preterm_nec_strain_specific_meta_39060543`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 39060543](https://pubmed.ncbi.nlm.nih.gov/39060543/)
- **Identity scope:** exact_strain; components=['STRAIN_LGG']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** necrotizing_enterocolitis / prevention
- **Population:** Preterm infants in neonatal units; 5 RCTs (n=851) using LGG as the sole probiotic; age_group=infant
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=not recorded; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=nec_stage_2_or_higher; hierarchy=primary; kind=patient_important; direction=positive; outcome_role=not recorded
- name=late_onset_sepsis; hierarchy=secondary; kind=patient_important; direction=null; outcome_role=not recorded
- name=mortality; hierarchy=secondary; kind=patient_important; direction=null; outcome_role=not recorded
- **Limitations:**
  - Hospital neonatal population; not a consumer supplement indication.
  - Observational studies showed no NEC effect; RCT pooled RR 0.50 (95% CI 0.26-0.93).
  - Doses vary across trials and are not stated in the abstract.
- **Rationale / notes:**

### 79. `lgg_seasonal_allergic_rhinitis_chewable_40891819`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 40891819](https://pubmed.ncbi.nlm.nih.gov/40891819/)
- **Identity scope:** exact_strain; components=['STRAIN_LGG']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** seasonal_allergic_rhinitis / treatment
- **Population:** 64 adults with seasonal allergic rhinoconjunctivitis under grass-pollen exposure (33 probiotic, 31 placebo; per-protocol); age_group=adult
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=chewable tablet; duration_days=14; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=allergic_rhinitis_symptom_control; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- name=nasopharyngeal_lgg_detection; hierarchy=secondary; kind=surrogate; direction=positive; outcome_role=not recorded
- name=salivary_il4_and_nasal_il13; hierarchy=secondary; kind=surrogate; direction=positive; outcome_role=not recorded
- **Limitations:**
  - Per-protocol analysis; symptom control reported within the probiotic group after 2 weeks rather than as a between-group primary endpoint.
  - Local (upper-airway) delivery via chewable; dose not stated in the abstract.
- **Rationale / notes:**

## STRAIN_LONGUM_BB536

### 80. `bb536_fermented_milk_gut_environment_39519413`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 39519413](https://pubmed.ncbi.nlm.nih.gov/39519413/)
- **Identity scope:** exact_strain; components=['STRAIN_LONGUM_BB536']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** gut_microbiota_and_metabolites / physiology
- **Population:** Healthy adults, fermented milk with or without BB536 for 17 days; age_group=adult
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=fermented milk; duration_days=17; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=fecal_bifidobacterium_abundance; hierarchy=primary; kind=surrogate; direction=positive; outcome_role=not recorded
- name=tryptophan_and_indole_metabolites; hierarchy=secondary; kind=surrogate; direction=positive; outcome_role=not recorded
- **Limitations:**
  - Surrogate microbiota and metabolite endpoints; no clinical outcome; dose not stated in the abstract.
- **Rationale / notes:**

### 81. `bb536_guar_gum_auto_hsct_pilot_36792187`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 36792187](https://pubmed.ncbi.nlm.nih.gov/36792187/)
- **Identity scope:** exact_strain; components=['STRAIN_LONGUM_BB536']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** chemotherapy_gastrointestinal_toxicity_auto_hsct / prevention
- **Population:** 12 patients with malignant lymphoma undergoing autologous stem-cell transplantation; age_group=adult
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=not recorded; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=guar gum
- **Outcomes:**
- name=total_parenteral_nutrition_duration; hierarchy=primary; kind=patient_important; direction=unresolved; outcome_role=not recorded
- name=grade_3_or_higher_diarrhea_duration; hierarchy=secondary; kind=patient_important; direction=unresolved; outcome_role=not recorded
- **Limitations:**
  - Pilot with 12 patients; medians reported without between-group tests (TPN 15 vs 17.5 days).
  - Synbiotic with guar gum; hospital population.
- **Rationale / notes:**

### 82. `bb536_male_athletes_high_protein_gi_symptoms_42046285`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 42046285](https://pubmed.ncbi.nlm.nih.gov/42046285/)
- **Identity scope:** exact_strain; components=['STRAIN_LONGUM_BB536']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** gastrointestinal_symptoms_on_high_protein_diet / prevention
- **Population:** 60 healthy male athletes (mean 18.6 y) consuming 70 g/day whey protein; age_group=adult
- **Studied dose:** status=not recorded; basis=discrete_daily_arms; values=46000000000.0; unit=CFU; forms=unresolved; duration_days=28; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=whey protein 70 g/day
- **Outcomes:**
- name=gastrointestinal_symptoms; hierarchy=primary; kind=patient_important; direction=null; outcome_role=not recorded
- name=diarrhea_related_score; hierarchy=post_hoc; kind=patient_important; direction=positive; outcome_role=not recorded
- name=odor_related_metabolites; hierarchy=post_hoc; kind=surrogate; direction=positive; outcome_role=not recorded
- **Limitations:**
  - No between-group differences in the full cohort; subgroup and within-group findings are exploratory.
  - 46 billion CFU/day measured at the start of the intervention.
- **Rationale / notes:**

### 83. `bb536_plasmacytoid_dendritic_cell_activation_38201872`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 38201872](https://pubmed.ncbi.nlm.nih.gov/38201872/)
- **Identity scope:** exact_strain; components=['STRAIN_LONGUM_BB536']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** immune_marker_pdc_activation / physiology
- **Population:** 97 healthy adults (49 BB536, 48 placebo), Japan; age_group=adult
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=28; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=cd86_expression_on_peripheral_pdcs; hierarchy=primary; kind=surrogate; direction=positive; outcome_role=not recorded
- **Limitations:**
  - Surrogate immune marker only; daily CFU not machine-readable in the retrieved abstract.
  - Manufacturer-conducted (Morinaga).
- **Rationale / notes:**

### 84. `m63_m16v_bb536_short_term_travel_42533554`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 42533554](https://pubmed.ncbi.nlm.nih.gov/42533554/)
- **Identity scope:** combination; components=['STRAIN_INFANTIS_M63', 'STRAIN_BREVE_M16V', 'STRAIN_LONGUM_BB536']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** travel_related_symptoms_and_microbiota / prevention
- **Population:** 74 healthy adults traveling to Xinjiang for five days; age_group=adult
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=5; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=gut_microbiota_composition_and_function; hierarchy=primary; kind=surrogate; direction=positive; outcome_role=not recorded
- name=irritability; hierarchy=secondary; kind=patient_important; direction=positive; outcome_role=not recorded
- name=fatigue; hierarchy=secondary; kind=patient_important; direction=positive; outcome_role=not recorded
- name=dizziness; hierarchy=secondary; kind=patient_important; direction=positive; outcome_role=not recorded
- **Limitations:**
  - Primary outcomes are microbiota composition; symptom findings are secondary and short (5 days).
  - Daily CFU exponent not machine-readable in the retrieved abstract.
- **Rationale / notes:**

## STRAIN_PARACASEI_LPC37

### 85. `lpc37_chillex_exam_stress_37662485`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 37662485](https://pubmed.ncbi.nlm.nih.gov/37662485/)
- **Identity scope:** exact_strain; components=['STRAIN_PARACASEI_LPC37']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** examination_stress / physiology
- **Population:** 190 healthy university students aged 18–40 facing examinations; age_group=adult
- **Studied dose:** status=not recorded; basis=measured_viability; values=15600000000, 13500000000; unit=CFU; forms=capsule; duration_days=70; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=state_anxiety_at_week_eight; hierarchy=primary; kind=patient_important; direction=null; outcome_role=not recorded
- name=cortisol_awakening_response; hierarchy=secondary; kind=surrogate; direction=null; outcome_role=not recorded
- **Limitations:**
  - One capsule daily for ten weeks; primary assessment at eight weeks. Initial 15.6B and final 13.5B CFU/capsule are site-averaged viability measurements, not dose arms or an efficacy range.
  - Primary state-anxiety comparison P=.446. The first null hierarchical secondary test halted formal testing; later sleep and alertness signals are exploratory, not confirmed benefits.
  - Industry-funded; the expected examination-related anxiety increase did not occur. No broad mood, immune or digestive benefit established.
- **Rationale / notes:**

### 86. `lpc37_sisu_stress_response_33385020`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 33385020](https://pubmed.ncbi.nlm.nih.gov/33385020/)
- **Identity scope:** exact_strain; components=['STRAIN_PARACASEI_LPC37']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** stress_response / physiology
- **Population:** 120 healthy adults aged 18–45, stratified by sex and chronic stress; age_group=adult
- **Studied dose:** status=not recorded; basis=measured_viability; values=17500000000, 16800000000; unit=CFU; forms=capsule; duration_days=35; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=heart_rate_response_to_acute_stress; hierarchy=primary; kind=surrogate; direction=null; outcome_role=not recorded
- name=perceived_stress_per_protocol; hierarchy=secondary; kind=patient_important; direction=positive; outcome_role=not recorded
- **Limitations:**
  - One capsule daily; initial 17.5B and final 16.8B CFU are viability measurements, not separate randomized doses. The stated target was 10B CFU/capsule; no efficacy interval is inferred.
  - Primary result null in ITT and PP; perceived-stress signal is secondary. Chronic-stress subgroups had opposite heart-rate responses, not uniform benefit.
  - Industry involvement; no baseline stress-test comparison. Not digestive or generic immune-efficacy evidence.
- **Rationale / notes:**

## STRAIN_PLANTARUM_299V

### 87. `lp299v_cancer_home_enteral_nutrition_33015813`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 33015813](https://pubmed.ncbi.nlm.nih.gov/33015813/)
- **Identity scope:** exact_strain; components=['STRAIN_PLANTARUM_299V']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** nutritional_status_home_enteral_nutrition / treatment
- **Population:** 35 cancer patients on home enteral nutrition, Poland; age_group=adult
- **Studied dose:** status=not recorded; basis=discrete_daily_arms; values=20000000000.0; unit=CFU; forms=unresolved; duration_days=28; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=serum_albumin; hierarchy=unresolved; kind=surrogate; direction=positive; outcome_role=not recorded
- name=vomiting; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- name=flatulence; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- name=overall_nutritional_status; hierarchy=unresolved; kind=patient_important; direction=null; outcome_role=not recorded
- name=quality_of_life; hierarchy=unresolved; kind=patient_important; direction=null; outcome_role=not recorded
- **Limitations:**
  - Small (n=35); overall nutritional status and between-group quality of life unchanged.
- **Rationale / notes:**

### 88. `lp299v_colon_resection_22434095`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 22434095](https://pubmed.ncbi.nlm.nih.gov/22434095/)
- **Identity scope:** exact_strain; components=['STRAIN_PLANTARUM_299V']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** postoperative_outcomes_colon_resection / prevention
- **Population:** 75 adults undergoing elective colon resection; age_group=adult
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=not recorded; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=enteric_bacterial_load; hierarchy=unresolved; kind=surrogate; direction=null; outcome_role=not recorded
- name=bacterial_translocation; hierarchy=unresolved; kind=surrogate; direction=null; outcome_role=not recorded
- name=postoperative_complications; hierarchy=unresolved; kind=patient_important; direction=null; outcome_role=not recorded
- **Limitations:**
  - All endpoints null; dose not stated in the abstract.
- **Rationale / notes:**

### 89. `lp299v_exam_stress_cortisol_28101105`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 28101105](https://pubmed.ncbi.nlm.nih.gov/28101105/)
- **Identity scope:** exact_strain; components=['STRAIN_PLANTARUM_299V']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** exam_stress_cortisol_response / physiology
- **Population:** 41 university students during exam stress, 14 days; age_group=adult
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=14; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=salivary_cortisol_rise_prevention; hierarchy=unresolved; kind=surrogate; direction=positive; outcome_role=not recorded
- name=salivary_iga; hierarchy=unresolved; kind=surrogate; direction=null; outcome_role=not recorded
- **Limitations:**
  - Salivary cortisol is a stress surrogate; no clinical anxiety or mood endpoint; dose not stated in the abstract.
- **Rationale / notes:**

### 90. `lp299v_female_athletes_iron_32365981`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 32365981](https://pubmed.ncbi.nlm.nih.gov/32365981/)
- **Identity scope:** exact_strain; components=['STRAIN_PLANTARUM_299V']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** iron_deficiency_female_athletes / treatment
- **Population:** 53 iron-deficient female athletes randomized (39 completed) to 20 mg iron with or without 299v for 4-12 weeks; age_group=adult
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=not recorded; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=iron 20 mg/day
- **Outcomes:**
- name=serum_ferritin; hierarchy=unresolved; kind=surrogate; direction=null; outcome_role=not recorded
- name=reticulocyte_hemoglobin; hierarchy=unresolved; kind=surrogate; direction=null; outcome_role=not recorded
- name=poms_vigor; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- name=exercise_performance; hierarchy=unresolved; kind=patient_important; direction=unresolved; outcome_role=not recorded
- **Limitations:**
  - Ferritin (p=0.056) and reticulocyte hemoglobin (p=0.083) missed significance; performance inconclusive; industry involvement (Probi/Nature's Bounty).
  - Variable 4-12 week duration; dose not stated in the abstract.
- **Rationale / notes:**

### 91. `lp299v_ibs_meta_37541528`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 37541528](https://pubmed.ncbi.nlm.nih.gov/37541528/)
- **Identity scope:** exact_strain; components=['STRAIN_PLANTARUM_299V']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** irritable_bowel_syndrome / treatment
- **Population:** Adults with IBS in an 82-RCT (n=10,332) systematic review and meta-analysis; age_group=adult
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=not recorded; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=ibs_global_symptom_improvement; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- **Limitations:**
  - The 299v-specific conclusion is graded LOW certainty by the reviewers; no 299v RCT is separately recorded this wave, so this meta is the strain's IBS record.
- **Rationale / notes:**

### 92. `lp299v_iron_absorption_meta_31816981`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 31816981](https://pubmed.ncbi.nlm.nih.gov/31816981/)
- **Identity scope:** exact_strain; components=['STRAIN_PLANTARUM_299V']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** iron_absorption / physiology
- **Population:** 8 studies (n=950) of 299v and iron absorption or iron status; age_group=adult
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=not recorded; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=iron_absorption; hierarchy=primary; kind=surrogate; direction=positive; outcome_role=not recorded
- name=iron_status_markers; hierarchy=unresolved; kind=surrogate; direction=null; outcome_role=not recorded
- **Limitations:**
  - Absorption (SMD 0.55) is an acute surrogate; the longer iron-status studies were mostly unchanged.
- **Rationale / notes:**

### 93. `lp299v_mdd_ssri_cognition_30388595`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 30388595](https://pubmed.ncbi.nlm.nih.gov/30388595/), [PMID 39271063](https://pubmed.ncbi.nlm.nih.gov/39271063/)
- **Identity scope:** exact_strain; components=['STRAIN_PLANTARUM_299V']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** cognitive_symptoms_in_major_depression / treatment
- **Population:** 79 adults with major depressive disorder randomized (60 analyzed) as SSRI augmentation for 8 weeks, Poland; age_group=adult
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=56; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=SSRI antidepressant
- **Outcomes:**
- name=attention_and_perceptivity_test; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- name=california_verbal_learning_test; hierarchy=unresolved; kind=patient_important; direction=positive; outcome_role=not recorded
- name=plasma_kynurenine; hierarchy=unresolved; kind=surrogate; direction=positive; outcome_role=not recorded
- name=depression_severity_between_groups; hierarchy=unresolved; kind=patient_important; direction=unresolved; outcome_role=not recorded
- **Limitations:**
  - Cognition-scoped record: the abstract does not report a between-group depression-severity improvement.
  - The metabolomics companion (PMID 39271063) is the same cohort; one trial family.
  - Dose not stated in the retrieved abstracts.
- **Rationale / notes:**

### 94. `lp299v_smokers_cardiovascular_markers_12450890`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 12450890](https://pubmed.ncbi.nlm.nih.gov/12450890/)
- **Identity scope:** exact_strain; components=['STRAIN_PLANTARUM_299V']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** cardiovascular_risk_markers_smokers / physiology
- **Population:** 36 smokers consuming 400 mL/day of a 299v rose-hip drink for 6 weeks; age_group=adult
- **Studied dose:** status=not recorded; basis=discrete_daily_arms; values=20000000000.0; unit=CFU; forms=rose-hip drink; duration_days=42; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=systolic_blood_pressure; hierarchy=unresolved; kind=surrogate; direction=positive; outcome_role=not recorded
- name=serum_leptin; hierarchy=unresolved; kind=surrogate; direction=positive; outcome_role=not recorded
- name=fibrinogen; hierarchy=unresolved; kind=surrogate; direction=positive; outcome_role=not recorded
- **Limitations:**
  - Small 2002 trial in a food matrix (400 mL x 5 x 10^7 CFU/mL = 2 x 10^10/day); risk-marker surrogates only.
- **Rationale / notes:**

## STRAIN_PLANTARUM_LP01

### 95. `lp01_bb12_synbiotic_constipation_29949873`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 29949873](https://pubmed.ncbi.nlm.nih.gov/29949873/)
- **Identity scope:** combination; components=['STRAIN_PLANTARUM_LP01', 'STRAIN_LACTIS_BB12']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** functional_constipation / treatment
- **Population:** 85 adults with Rome III functional constipation taking a synbiotic with LP01, BB-12 and prebiotics for 12 weeks; age_group=adult
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=84; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=prebiotic fibers (synbiotic formulation)
- **Outcomes:**
- name=stool_evacuation; hierarchy=unresolved; kind=patient_important; direction=null; outcome_role=not recorded
- name=pac_sym; hierarchy=unresolved; kind=patient_important; direction=null; outcome_role=not recorded
- name=pac_qol; hierarchy=unresolved; kind=patient_important; direction=null; outcome_role=not recorded
- **Limitations:**
  - No endpoint reached significance versus placebo (high placebo response); synbiotic formulation.
  - This null is currently LP01's only registry-recordable RCT: the rest of its trial base uses non-registry partner strains (see wave2_read_log.md).
- **Rationale / notes:**

## STRAIN_RHAMNOSUS_GR1

### 96. `gr1_rc14_bv_metronidazole_adjunct_34295831`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 34295831](https://pubmed.ncbi.nlm.nih.gov/34295831/)
- **Identity scope:** combination; components=['STRAIN_RHAMNOSUS_GR1', 'STRAIN_FERMENTUM_RC14']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** bacterial_vaginosis / treatment
- **Population:** 126 women with bacterial vaginosis on metronidazole, 30 days of oral GR-1 + RC-14; age_group=adult
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=30; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=metronidazole
- **Outcomes:**
- name=bv_cure_rate_30_and_90_days; hierarchy=unresolved; kind=patient_important; direction=null; outcome_role=not recorded
- name=strain_detection_vaginal_fecal; hierarchy=unresolved; kind=surrogate; direction=null; outcome_role=not recorded
- **Limitations:**
  - Cure rates did not differ at 30 or 90 days and the administered species were rarely detected in vaginal or fecal microbiota.
- **Rationale / notes:**

### 97. `gr1_rc14_gbs_colonization_27590374`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 27590374](https://pubmed.ncbi.nlm.nih.gov/27590374/)
- **Identity scope:** combination; components=['STRAIN_RHAMNOSUS_GR1', 'STRAIN_FERMENTUM_RC14']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** group_b_streptococcus_colonization / treatment
- **Population:** 99 group B Streptococcus-positive pregnant women at 35-37 weeks gestation; age_group=adult
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=not recorded; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=gbs_conversion_to_negative; hierarchy=unresolved; kind=surrogate; direction=positive; outcome_role=not recorded
- **Limitations:**
  - Conversion to GBS-negative on admission (42.9% vs 18.0%, p=0.007) is a colonization surrogate, not an infection outcome; dose not stated in the abstract.
- **Rationale / notes:**

### 98. `gr1_rc14_pregnancy_bv_30932317`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 30932317](https://pubmed.ncbi.nlm.nih.gov/30932317/)
- **Identity scope:** combination; components=['STRAIN_RHAMNOSUS_GR1', 'STRAIN_FERMENTUM_RC14']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** bacterial_vaginosis_pregnancy / prevention
- **Population:** 238 pregnant women analyzed, oral supplementation from 9-14 weeks gestation; age_group=adult
- **Studied dose:** status=not recorded; basis=discrete_daily_arms; values=5000000000.0; unit=CFU; forms=unresolved; duration_days=not recorded; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=bacterial_vaginosis_18_20_weeks; hierarchy=unresolved; kind=patient_important; direction=null; outcome_role=not recorded
- name=vaginal_colonization; hierarchy=unresolved; kind=surrogate; direction=null; outcome_role=not recorded
- name=microbiota_composition; hierarchy=unresolved; kind=surrogate; direction=null; outcome_role=not recorded
- **Limitations:**
  - Null throughout; 2.5 x 10^9 CFU of each strain (5 x 10^9/day combination total, never an individual dose).
- **Rationale / notes:**

### 99. `gr1_rc14_pregnancy_colonization_32325794`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 32325794](https://pubmed.ncbi.nlm.nih.gov/32325794/)
- **Identity scope:** combination; components=['STRAIN_RHAMNOSUS_GR1', 'STRAIN_FERMENTUM_RC14']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** vaginal_colonization_pregnancy / physiology
- **Population:** 38 pregnant women at risk for preterm labor; open crossover; age_group=adult
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=not recorded; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=vaginal_colonization_administered_strains; hierarchy=unresolved; kind=surrogate; direction=null; outcome_role=not recorded
- **Limitations:**
  - Open crossover; colonization of the administered strains was rare.
- **Rationale / notes:**

### 100. `gr1_rc14_sci_mdr_colonization_31953482`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 31953482](https://pubmed.ncbi.nlm.nih.gov/31953482/)
- **Identity scope:** combination; components=['STRAIN_RHAMNOSUS_GR1', 'STRAIN_FERMENTUM_RC14']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** multidrug_resistant_gram_negative_colonization / prevention
- **Population:** 207 adults with spinal cord injury in the four-arm ProSCIUTTU trial (including an LGG-BB12 arm); age_group=adult
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=not recorded; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=new_multiresistant_gram_negative_colonization; hierarchy=secondary; kind=surrogate; direction=positive; outcome_role=not recorded
- name=existing_colonization_clearance; hierarchy=secondary; kind=surrogate; direction=null; outcome_role=not recorded
- **Limitations:**
  - Secondary colonization analysis (OR 0.10 for new colonization, no clearing effect); the trial's UTI primary paper was not read this wave.
  - Population-specific (spinal cord injury); colonization is a microbiological surrogate.
- **Rationale / notes:**

## STRAIN_RHAMNOSUS_HN001

### 101. `hn001_b420_pregnancy_child_overweight_36705702`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 36705702](https://pubmed.ncbi.nlm.nih.gov/36705702/)
- **Identity scope:** combination; components=['STRAIN_RHAMNOSUS_HN001', 'STRAIN_LACTIS_B420']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** childhood_overweight / prevention
- **Population:** 330 children of the Turku pregnancy cohort assessed at 24 months; age_group=infant
- **Studied dose:** status=not recorded; basis=discrete_daily_arms; values=20000000000.0; unit=CFU; forms=unresolved; duration_days=not recorded; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=fish oil arm in a 2x2 factorial design
- **Outcomes:**
- name=overweight_odds_24_months; hierarchy=secondary; kind=patient_important; direction=positive; outcome_role=not recorded
- name=body_fat_percentage_24_months; hierarchy=secondary; kind=surrogate; direction=null; outcome_role=not recorded
- **Limitations:**
  - Growth was a secondary outcome of the trial; same cohort as the allergy context, so not an independent trial.
- **Rationale / notes:**

### 102. `hn001_b420_pregnancy_fishoil_child_allergy_37622257`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 37622257](https://pubmed.ncbi.nlm.nih.gov/37622257/), [PMID 37642166](https://pubmed.ncbi.nlm.nih.gov/37642166/)
- **Identity scope:** combination; components=['STRAIN_RHAMNOSUS_HN001', 'STRAIN_LACTIS_B420']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** childhood_allergic_disease / prevention
- **Population:** Children of 439 women with overweight/obesity supplemented from early pregnancy to 6 months postpartum (2x2 factorial with fish oil); outcomes at 12 and 24 months; age_group=infant
- **Studied dose:** status=not recorded; basis=discrete_daily_arms; values=20000000000.0; unit=CFU; forms=unresolved; duration_days=not recorded; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=fish oil arm in a 2x2 factorial design
- **Outcomes:**
- name=physician_diagnosed_food_allergy; hierarchy=primary; kind=patient_important; direction=null; outcome_role=not recorded
- name=atopic_eczema; hierarchy=primary; kind=patient_important; direction=null; outcome_role=not recorded
- name=atopy; hierarchy=primary; kind=patient_important; direction=null; outcome_role=not recorded
- name=recurrent_wheezing_24_months; hierarchy=secondary; kind=patient_important; direction=positive; outcome_role=not recorded
- **Limitations:**
  - Maternal supplementation, infant outcomes; 10^10 CFU each of HN001 and B. lactis 420 (2 x 10^10/day combined).
  - Only recurrent wheezing at 24 months differed (OR 0.39); allergy and atopy endpoints null.
  - Serum fatty-acid secondary analysis (PMID 37642166) is the same cohort.
- **Rationale / notes:**

### 103. `hn001_elderly_brain_function_encapsulation_40976401`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 40976401](https://pubmed.ncbi.nlm.nih.gov/40976401/)
- **Identity scope:** exact_strain; components=['STRAIN_RHAMNOSUS_HN001']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** brain_function_and_cognition_in_elderly / physiology
- **Population:** 87 community-dwelling adults 60-80 y; micro-encapsulated vs non-encapsulated HN001 vs placebo; age_group=adult
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=not recorded; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=resting_state_functional_connectivity; hierarchy=primary; kind=surrogate; direction=unresolved; outcome_role=not recorded
- name=processing_speed; hierarchy=secondary; kind=patient_important; direction=positive; outcome_role=not recorded
- name=short_term_memory; hierarchy=secondary; kind=patient_important; direction=null; outcome_role=not recorded
- name=anxiety_symptoms; hierarchy=secondary; kind=patient_important; direction=null; outcome_role=not recorded
- name=depression_and_perceived_stress; hierarchy=secondary; kind=patient_important; direction=null; outcome_role=not recorded
- name=sleep_quality; hierarchy=secondary; kind=patient_important; direction=null; outcome_role=not recorded
- **Limitations:**
  - The connectivity difference is between the two probiotic formulations, not versus placebo; dose not stated.
  - Most cognitive and mood domains unaffected.
- **Rationale / notes:**

### 104. `hn001_maternal_perinatal_mental_health_sr_41783815`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 41783815](https://pubmed.ncbi.nlm.nih.gov/41783815/)
- **Identity scope:** exact_strain; components=['STRAIN_RHAMNOSUS_HN001']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** perinatal_depression_and_anxiety / prevention
- **Population:** Pregnant and early-postpartum women without a diagnosed mental disorder; 4 RCTs (n=1342) reviewed, HN001 in one; age_group=adult
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=not recorded; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=depressive_symptoms_epds; hierarchy=primary; kind=patient_important; direction=positive; outcome_role=not recorded
- name=anxiety_symptoms_stai6; hierarchy=primary; kind=patient_important; direction=positive; outcome_role=not recorded
- **Limitations:**
  - No pooling; the HN001 finding (EPDS MD -1.2; STAI-6 MD -1.0) rests on a single RCT with moderate risk of bias.
  - Small effect sizes; evidence judged limited by the reviewers.
- **Rationale / notes:**

### 105. `hn001_perceived_stress_happiness_39275252`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 39275252](https://pubmed.ncbi.nlm.nih.gov/39275252/)
- **Identity scope:** exact_strain; components=['STRAIN_RHAMNOSUS_HN001']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** perceived_stress_and_wellbeing / treatment
- **Population:** 120 adults with mild to high perceived stress; age_group=adult
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=28; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=oxford_happiness_questionnaire; hierarchy=primary; kind=patient_important; direction=null; outcome_role=not recorded
- name=perceived_stress_scale; hierarchy=secondary; kind=patient_important; direction=null; outcome_role=not recorded
- name=intervention_by_day_interaction; hierarchy=post_hoc; kind=patient_important; direction=positive; outcome_role=not recorded
- **Limitations:**
  - Primary comparisons not statistically significant; only post hoc interaction and sex subgroups reached significance.
  - Manufacturer-conducted (Fonterra); dose not stated.
- **Rationale / notes:**

### 106. `hn019_hn001_fos_immune_parameters_healthy_adults_37614109`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 37614109](https://pubmed.ncbi.nlm.nih.gov/37614109/)
- **Identity scope:** combination; components=['STRAIN_LACTIS_HN019', 'STRAIN_RHAMNOSUS_HN001']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** immune_parameters_healthy_adults / physiology
- **Population:** 106 healthy adults, China; synbiotic with fructooligosaccharide 500 mg/day; age_group=adult
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=56; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=fructooligosaccharide 500 mg/day
- **Outcomes:**
- name=plasma_c_reactive_protein; hierarchy=primary; kind=surrogate; direction=null; outcome_role=not recorded
- name=interferon_gamma; hierarchy=secondary; kind=surrogate; direction=positive; outcome_role=not recorded
- name=il_10; hierarchy=secondary; kind=surrogate; direction=positive; outcome_role=not recorded
- name=stool_secretory_iga; hierarchy=secondary; kind=surrogate; direction=positive; outcome_role=not recorded
- **Limitations:**
  - Surrogate immune markers in healthy adults; CRP change p=0.088; strain exponents not machine-readable.
- **Rationale / notes:**

## STRAIN_SACCHAROMYCES

### 107. `sb_adult_acute_viral_diarrhea_37400812`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 37400812](https://pubmed.ncbi.nlm.nih.gov/37400812/)
- **Identity scope:** species_general; components=['STRAIN_SACCHAROMYCES']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** acute_viral_diarrhea / treatment
- **Population:** 46 adults with PCR-confirmed viral acute diarrhea, Mexico; 600 mg daily for 8 days; age_group=adult
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=8; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=paracetamol, trimebutine
- **Outcomes:**
- name=symptom_severity; hierarchy=primary; kind=patient_important; direction=null; outcome_role=not recorded
- name=patient_global_impression_of_change_day_4; hierarchy=secondary; kind=patient_important; direction=positive; outcome_role=not recorded
- **Limitations:**
  - Severity unchanged; only the day-4 patient-rated improvement differed (70% vs 26%).
  - Small sample; 600 mg (about 1 x 10^9 per 100 mL as stated), mass dose.
- **Rationale / notes:**

### 108. `sb_cncm_i745_h_pylori_triple_therapy_gistar_37942999`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 37942999](https://pubmed.ncbi.nlm.nih.gov/37942999/)
- **Identity scope:** species_general; components=['STRAIN_SACCHAROMYCES']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** helicobacter_pylori_eradication_adjunct / treatment
- **Population:** 404 adults 40-64 y in the GISTAR cohort on clarithromycin triple therapy for 10 or 14 days; age_group=adult
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=not recorded; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=clarithromycin, amoxicillin, esomeprazole
- **Outcomes:**
- name=eradication_rate_itt; hierarchy=primary; kind=patient_important; direction=mixed; outcome_role=not recorded
- name=eradication_rate_per_protocol; hierarchy=secondary; kind=patient_important; direction=null; outcome_role=not recorded
- name=treatment_adverse_events; hierarchy=secondary; kind=patient_important; direction=null; outcome_role=not recorded
- **Limitations:**
  - Higher ITT eradication only in the 10-day arm (70.8% vs 54.6%); per-protocol and 14-day comparisons null; adverse-event reduction lost significance after multiplicity adjustment.
  - 500 mg CNCM I-745 twice daily (mass dose).
- **Rationale / notes:**

### 109. `sb_cncm_i745_ibs_d_sibo_open_pilot_36630947`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 36630947](https://pubmed.ncbi.nlm.nih.gov/36630947/)
- **Identity scope:** species_general; components=['STRAIN_SACCHAROMYCES']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** ibs_d_with_small_intestinal_bacterial_overgrowth / treatment
- **Population:** 54 adults with diarrhea-predominant IBS and SIBO (48 evaluated), Argentina; 15 days with dietary advice; age_group=adult
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=15; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=dietary advice in both arms
- **Outcomes:**
- name=hydrogen_excretion_reduction; hierarchy=primary; kind=surrogate; direction=unresolved; outcome_role=not recorded
- name=ibs_severity_score; hierarchy=secondary; kind=patient_important; direction=unresolved; outcome_role=not recorded
- name=proportion_with_diarrhea; hierarchy=secondary; kind=patient_important; direction=positive; outcome_role=not recorded
- **Limitations:**
  - Open-label pilot; numerical differences reported without between-group statistics for the main endpoints.
  - Dose not stated in the abstract.
- **Rationale / notes:**

### 110. `sb_cncm_i745_mdr_colonization_antibiotics_33763399`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 33763399](https://pubmed.ncbi.nlm.nih.gov/33763399/)
- **Identity scope:** species_general; components=['STRAIN_SACCHAROMYCES']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** multidrug_resistant_gut_colonization_during_antibiotics / prevention
- **Population:** Hospitalized patients (mean age 78) on amoxicillin-clavulanate; S. boulardii CNCM I-745 arm of a three-arm trial; age_group=adult
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=30; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=amoxicillin-clavulanate 10 days
- **Outcomes:**
- name=pseudomonas_and_ampc_colonization; hierarchy=unresolved; kind=surrogate; direction=null; outcome_role=not recorded
- **Limitations:**
  - No significant colonization changes in the S. boulardii group while the four-strain mixture arm changed; same trial as the NCFM combination context.
  - Dose not stated.
- **Rationale / notes:**

### 111. `sb_cncm_i745_pediatric_acute_gastroenteritis_china_meta_40535538`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 40535538](https://pubmed.ncbi.nlm.nih.gov/40535538/)
- **Identity scope:** species_general; components=['STRAIN_SACCHAROMYCES']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** pediatric_acute_gastroenteritis / treatment
- **Population:** Children with acute gastroenteritis on standard rehydration; 10 RCTs (n=1125) conducted in China; age_group=child
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=not recorded; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=diarrhea_duration; hierarchy=primary; kind=patient_important; direction=positive; outcome_role=not recorded
- name=cure_rate; hierarchy=secondary; kind=patient_important; direction=positive; outcome_role=not recorded
- **Limitations:**
  - All included trials were found only in Chinese databases; consultancy authorship (McFarland Consulting).
  - Duration reduction SMD -1.63 days; doses vary.
- **Rationale / notes:**

### 112. `sb_cncm_i745_ppi_sibo_with_rifaximin_40884341`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 40884341](https://pubmed.ncbi.nlm.nih.gov/40884341/)
- **Identity scope:** species_general; components=['STRAIN_SACCHAROMYCES']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** ppi_associated_small_intestinal_bacterial_overgrowth / treatment
- **Population:** 108 adults with breath-test-confirmed SIBO on long-term proton pump inhibitors; age_group=adult
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=7; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=rifaximin 400 mg twice daily 7 days
- **Outcomes:**
- name=sibo_persistence_breath_test; hierarchy=primary; kind=surrogate; direction=positive; outcome_role=not recorded
- name=diarrhea_resolution; hierarchy=secondary; kind=patient_important; direction=positive; outcome_role=not recorded
- name=symptom_score_7x7; hierarchy=secondary; kind=patient_important; direction=positive; outcome_role=not recorded
- **Limitations:**
  - Open comparative design; SIBO persistence is a breath-test surrogate (41.5% vs 21.8%).
  - 500 mg CNCM I-745 twice daily (mass dose).
- **Rationale / notes:**

### 113. `sb_cncm_i745_vs_b_clausii_pediatric_gastroenteritis_36086703`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 36086703](https://pubmed.ncbi.nlm.nih.gov/36086703/)
- **Identity scope:** species_general; components=['STRAIN_SACCHAROMYCES']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** pediatric_acute_gastroenteritis / treatment
- **Population:** 317 children 6 months to 5 years with mild-moderate acute diarrhea, 8 centers in Argentina; age_group=child
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=5; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=diarrhea_duration; hierarchy=primary; kind=patient_important; direction=positive; outcome_role=not recorded
- **Limitations:**
  - Active-comparator design: 64.6 vs 78.0 h diarrhea duration versus B. clausii, not versus placebo.
  - Dose not stated in the abstract.
- **Rationale / notes:**

### 114. `sb_h_pylori_eradication_adjunct_meta_family`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 40865583](https://pubmed.ncbi.nlm.nih.gov/40865583/), [PMID 41247686](https://pubmed.ncbi.nlm.nih.gov/41247686/), [PMID 40251486](https://pubmed.ncbi.nlm.nih.gov/40251486/), [PMID 40012609](https://pubmed.ncbi.nlm.nih.gov/40012609/)
- **Identity scope:** species_general; components=['STRAIN_SACCHAROMYCES']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** helicobacter_pylori_eradication_adjunct / treatment
- **Population:** Adults with Helicobacter pylori infection receiving bismuth quadruple or triple eradication therapy; four overlapping meta-analyses (10-19 RCTs each, up to 5036 patients); age_group=adult
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=not recorded; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=bismuth quadruple or clarithromycin triple eradication therapy
- **Outcomes:**
- name=eradication_rate; hierarchy=primary; kind=patient_important; direction=positive; outcome_role=not recorded
- name=total_treatment_adverse_events; hierarchy=secondary; kind=patient_important; direction=positive; outcome_role=not recorded
- name=diarrhea_during_eradication; hierarchy=secondary; kind=patient_important; direction=positive; outcome_role=not recorded
- **Limitations:**
  - Four meta-analyses of a largely shared, mostly Chinese RCT base; treated as one evidence family.
  - Modest effect (RR 1.08-1.12 in S. boulardii-specific analyses); dose is mass (500-1000 mg/day), not CFU, so no CFU applicability can be derived.
  - Species-level; strains vary or are unreported across trials.
- **Rationale / notes:**

### 115. `sb_travelers_diarrhea_prevention_meta_38458507`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 38458507](https://pubmed.ncbi.nlm.nih.gov/38458507/)
- **Identity scope:** species_general; components=['STRAIN_SACCHAROMYCES']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** travelers_diarrhea / prevention
- **Population:** Travelers in 10 RCTs of probiotic prophylaxis across genera; age_group=mixed
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=not recorded; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=travelers_diarrhea_incidence; hierarchy=primary; kind=patient_important; direction=positive; outcome_role=not recorded
- **Limitations:**
  - Strain-nonspecific pooled statement that S. boulardii and S. cerevisiae were effective; few trials, mixed genera, no S. boulardii-specific effect size in the abstract.
- **Rationale / notes:**

### 116. `sboulardii_child_aad_prevention_26756877`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 26756877](https://pubmed.ncbi.nlm.nih.gov/26756877/)
- **Identity scope:** species_general; components=['STRAIN_SACCHAROMYCES']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** antibiotic_associated_diarrhea / prevention
- **Population:** Children receiving antibiotics with risk factors for antibiotic-associated diarrhea; age_group=child
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=not recorded; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=antibiotics
- **Outcomes:**
- name=antibiotic_associated_diarrhea_prevention; hierarchy=guideline; kind=patient_important; direction=positive; outcome_role=not recorded
- **Limitations:**
  - Guideline recommendation, not a new independent trial
  - Moderate-quality evidence for prevention in children does not establish adult treatment or general digestive benefit
  - The inspected abstract does not authenticate CNCM I-745 or establish an exact dose
- **Rationale / notes:**

### 117. `sboulardii_elderly_aad_prevention_22472744`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 22472744](https://pubmed.ncbi.nlm.nih.gov/22472744/)
- **Identity scope:** species_general; components=['STRAIN_SACCHAROMYCES']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** antibiotic_associated_diarrhea / prevention
- **Population:** Elderly hospitalized adults receiving antibiotics; mean age 79 years; age_group=adult
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=capsule; duration_days=not recorded; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=antibiotics
- **Outcomes:**
- name=antibiotic_associated_diarrhea_incidence; hierarchy=primary; kind=patient_important; direction=null; outcome_role=not recorded
- **Limitations:**
  - 275 randomized participants; 204 completed follow-up
  - Twice-daily capsules started within 48 hours of antibiotics and continued seven days after withdrawal; no preventive superiority
  - Exact CFU amount and strain code were not verified in the accessible abstract
  - An elderly inpatient null result does not negate pediatric guideline evidence
- **Rationale / notes:**

### 118. `sboulardii_nosocomial_diarrhea_treatment_41675330`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 41675330](https://pubmed.ncbi.nlm.nih.gov/41675330/)
- **Identity scope:** species_general; components=['STRAIN_SACCHAROMYCES']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** non_cdiff_nosocomial_diarrhea / treatment
- **Population:** 72 severely ill hospitalized adults with non-C. difficile nosocomial diarrhea; age_group=adult
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=5; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=standard inpatient care
- **Outcomes:**
- name=stool_weight; hierarchy=primary; kind=patient_important; direction=null; outcome_role=not recorded
- name=stool_frequency_and_consistency; hierarchy=secondary; kind=patient_important; direction=null; outcome_role=not recorded
- **Limitations:**
  - Treatment, not prevention, in a severely ill inpatient population
  - No placebo arm and limited blinding
  - No advantage over standard care in reported stool outcomes
  - Exact dose and strain code remain unresolved from the inspected source
- **Rationale / notes:**

## STRAIN_SUBTILIS_DE111

### 119. `de111_blood_lipids_endothelial_function_33161737`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 33161737](https://pubmed.ncbi.nlm.nih.gov/33161737/)
- **Identity scope:** exact_strain; components=['STRAIN_SUBTILIS_DE111']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** blood_lipids_and_endothelial_function / physiology
- **Population:** Healthy adults 18-65 y (BMI 20-34.9); age_group=adult
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=28; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=total_cholesterol; hierarchy=primary; kind=surrogate; direction=positive; outcome_role=not recorded
- name=non_hdl_cholesterol; hierarchy=primary; kind=surrogate; direction=positive; outcome_role=not recorded
- name=endothelial_function; hierarchy=secondary; kind=surrogate; direction=unresolved; outcome_role=not recorded
- name=ldl_cholesterol; hierarchy=secondary; kind=surrogate; direction=null; outcome_role=not recorded
- **Limitations:**
  - Cholesterol reductions are relative to baseline (-8 mg/dL total; -11 mg/dL non-HDL); endothelial and LDL changes were trends (p=0.05-0.06).
  - Largely healthy population; dose not stated in the abstract.
- **Rationale / notes:**

### 120. `de111_daycare_children_microbiome_33161736`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 33161736](https://pubmed.ncbi.nlm.nih.gov/33161736/)
- **Identity scope:** exact_strain; components=['STRAIN_SUBTILIS_DE111']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** gut_microbiome_composition / physiology
- **Population:** Healthy children 2-6 y attending day care; 8 weeks; age_group=child
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=56; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=overall_microbiome_equilibrium; hierarchy=primary; kind=surrogate; direction=null; outcome_role=not recorded
- name=alpha_diversity; hierarchy=secondary; kind=surrogate; direction=positive; outcome_role=not recorded
- **Limitations:**
  - Microbiome surrogate only; no infection or symptom outcome; dose not stated; manufacturer-authored.
- **Rationale / notes:**

### 121. `de111_female_athletes_offseason_training_33105368`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 33105368](https://pubmed.ncbi.nlm.nih.gov/33105368/)
- **Identity scope:** exact_strain; components=['STRAIN_SUBTILIS_DE111']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** training_adaptation_and_body_composition / physiology
- **Population:** 23 Division I female soccer and volleyball athletes; 10-week offseason resistance training; age_group=adult
- **Studied dose:** status=not recorded; basis=discrete_daily_arms; values=5000000000.0; unit=CFU; forms=unresolved; duration_days=70; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=strength_and_performance; hierarchy=primary; kind=patient_important; direction=null; outcome_role=not recorded
- name=body_fat_percentage; hierarchy=secondary; kind=surrogate; direction=positive; outcome_role=not recorded
- **Limitations:**
  - No performance effect; body-fat interaction in a 23-athlete sample.
  - 5 billion CFU/day with post-workout nutrition.
- **Rationale / notes:**

### 122. `de111_healthy_adults_immune_gi_pilot_33671071`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 33671071](https://pubmed.ncbi.nlm.nih.gov/33671071/)
- **Identity scope:** exact_strain; components=['STRAIN_SUBTILIS_DE111']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** immune_and_gastrointestinal_health_markers / physiology
- **Population:** Healthy adults; 4-week pilot; age_group=adult
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=28; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=ex_vivo_anti_inflammatory_immune_cell_populations; hierarchy=primary; kind=surrogate; direction=positive; outcome_role=not recorded
- name=perceived_gastrointestinal_health; hierarchy=secondary; kind=patient_important; direction=null; outcome_role=not recorded
- name=circulating_and_fecal_inflammation_markers; hierarchy=secondary; kind=surrogate; direction=null; outcome_role=not recorded
- name=plasma_zonulin; hierarchy=secondary; kind=surrogate; direction=null; outcome_role=not recorded
- **Limitations:**
  - Authors state the study may have been underpowered; only an ex vivo LPS-stimulation signal differed.
  - Dose not stated in the abstract.
- **Rationale / notes:**

### 123. `de111_ileostomy_small_intestinal_germination_34408741`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 34408741](https://pubmed.ncbi.nlm.nih.gov/34408741/), [PMID 36790091](https://pubmed.ncbi.nlm.nih.gov/36790091/)
- **Identity scope:** exact_strain; components=['STRAIN_SUBTILIS_DE111']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** small_intestinal_spore_germination / physiology
- **Population:** 11 adults with ileostomy; crossover; age_group=adult
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=not recorded; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=ileal_spore_and_vegetative_cell_recovery; hierarchy=primary; kind=surrogate; direction=positive; outcome_role=not recorded
- name=ileal_metabolite_and_protein_changes; hierarchy=secondary; kind=surrogate; direction=positive; outcome_role=not recorded
- **Limitations:**
  - Germination and survival in ileal effluent is a physiological surrogate; it is not evidence of a clinical benefit.
  - Both publications come from the same 11-participant study (one trial family); dose not stated.
- **Rationale / notes:**

### 124. `de111_male_baseball_immune_hormonal_30049931`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 30049931](https://pubmed.ncbi.nlm.nih.gov/30049931/)
- **Identity scope:** exact_strain; components=['STRAIN_SUBTILIS_DE111']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** immune_and_hormonal_markers_during_training / physiology
- **Population:** 25 Division I male baseball athletes; 12 weeks of offseason training; age_group=adult
- **Studied dose:** status=not recorded; basis=discrete_daily_arms; values=1000000000.0; unit=CFU; forms=unresolved; duration_days=84; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=circulating_tnf_alpha; hierarchy=primary; kind=surrogate; direction=positive; outcome_role=not recorded
- name=body_composition_and_performance; hierarchy=secondary; kind=patient_important; direction=null; outcome_role=not recorded
- name=plasma_zonulin; hierarchy=secondary; kind=surrogate; direction=null; outcome_role=not recorded
- name=salivary_iga_and_igm; hierarchy=secondary; kind=surrogate; direction=null; outcome_role=not recorded
- **Limitations:**
  - Only TNF-alpha differed; a single cytokine in 25 athletes is a surrogate signal.
- **Rationale / notes:**

### 125. `de111_whey_protein_amino_acid_response_33462163`

- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification
- **Source:** [PMID 33462163](https://pubmed.ncbi.nlm.nih.gov/33462163/)
- **Identity scope:** exact_strain; components=['STRAIN_SUBTILIS_DE111']
- **Evidence role:** not recorded; component_registration_status=not recorded; schema=not recorded
- **Condition / purpose:** plasma_amino_acid_response_to_whey / physiology
- **Population:** 22 recreationally active men and women; age_group=adult
- **Studied dose:** status=not recorded; basis=unresolved; values=unresolved; unit=CFU; forms=unresolved; duration_days=28; duration_basis=not recorded; frequency=not recorded; component_doses=unresolved; co-therapies=none recorded
- **Outcomes:**
- name=plasma_amino_acid_auc_after_whey; hierarchy=primary; kind=surrogate; direction=null; outcome_role=not recorded
- **Limitations:**
  - No effect on leucine, BCAA, EAA or total amino acid appearance.
  - PubMed's abstract text prints a malformed 1 x 10-9 CFU exponent; full text is required before recording a tested daily dose.
- **Rationale / notes:**

