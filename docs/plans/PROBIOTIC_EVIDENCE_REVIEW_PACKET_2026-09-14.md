# Probiotic evidence review packet

> Generated from `scripts/data/clinically_relevant_strains.json` on 2026-09-14.
> This packet is a research handoff. Reviewers supply source-backed recommendations; the registry and pipeline remain the source of truth.
> The engineering owner verifies each recommendation against the cited source and the frozen schema, then applies the final registry status. Reviewers do not edit statuses or the registry.
> Automated source check: [PubMed verification report](EVIDENCE_API_VERIFICATION_2026-09-14.json) — 182/182 citation references matched; 0 mismatches.
> Batch-1 structural patch: `scripts/audits/probiotic_curation_queue_2026_09_13/batch1_disposition_2026-09-14.json` (snapshot-bound; statuses unchanged).

## Where we are

The source records and citations have already been assembled. The decisions below have not yet been written into the registry, so no evidence change is shipped from this packet by itself.

- **Pending review:** 0
- **Recorded approved:** 123
- **Recorded rejected:** 0
- **Other registry states:** 2
- **Contexts shown in this packet:** 0
**Owning identities represented:** 0

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

