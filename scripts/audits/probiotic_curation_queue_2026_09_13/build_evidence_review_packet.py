"""Build the reviewer handoff packet from the canonical probiotic registry."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
REGISTRY = ROOT / "scripts/data/clinically_relevant_strains.json"
OUTPUT = ROOT / "docs/plans/PROBIOTIC_EVIDENCE_REVIEW_PACKET_2026-09-14.md"


def _bullet(value: object) -> str:
    return str(value) if value not in (None, "", [], {}) else "not recorded"


def _dose(dose: dict[str, object]) -> str:
    values = ", ".join(str(v) for v in dose.get("values", [])) or "unresolved"
    forms = ", ".join(str(v) for v in dose.get("dosage_forms", [])) or "unresolved"
    therapies = ", ".join(str(v) for v in dose.get("co_therapies", [])) or "none recorded"
    component_doses = dose.get("component_doses") or []
    component_text = "unresolved"
    if isinstance(component_doses, list) and component_doses:
        component_text = ", ".join(
            f"{item.get('component')}={item.get('dose_cfu_per_day')} CFU/day"
            for item in component_doses
            if isinstance(item, dict)
        ) or "unresolved"
    as_printed = dose.get("duration_as_printed")
    duration_text = f"duration_days={_bullet(dose.get('duration_days'))}"
    if isinstance(as_printed, dict):
        duration_text += (
            f" (as_printed={_bullet(as_printed.get('value'))} "
            f"{_bullet(as_printed.get('unit'))})"
        )
    return "; ".join(
        [
            f"status={_bullet(dose.get('dose_status'))}",
            f"basis={_bullet(dose.get('dose_basis') or dose.get('basis'))}",
            f"values={values}",
            f"unit={_bullet(dose.get('unit'))}",
            f"forms={forms}",
            duration_text,
            f"duration_basis={_bullet(dose.get('duration_basis'))}",
            f"frequency={_bullet(dose.get('administration_frequency'))}",
            f"component_doses={component_text}",
            f"co-therapies={therapies}",
        ]
    )


def _outcomes(outcomes: list[dict[str, object]]) -> str:
    if not outcomes:
        return "- Not recorded"
    lines = []
    for outcome in outcomes:
        lines.append(
            "- "
            + "; ".join(
                [
                    f"name={_bullet(outcome.get('name'))}",
                    f"hierarchy={_bullet(outcome.get('hierarchy'))}",
                    f"kind={_bullet(outcome.get('kind'))}",
                    f"direction={_bullet(outcome.get('direction'))}",
                    f"outcome_role={_bullet(outcome.get('outcome_role'))}",
                ]
            )
        )
    return "\n".join(lines)


def build() -> None:
    registry = json.loads(REGISTRY.read_text())
    entries = registry["clinically_relevant_strains"]
    all_contexts = [
        context
        for entry in entries
        for context in entry.get("study_contexts", [])
    ]
    contexts = [
        (entry, context)
        for entry in entries
        for context in entry.get("study_contexts", [])
        if context.get("review_status") == "source_verified_pending_clinical_review"
    ]
    contexts.sort(key=lambda pair: (pair[0].get("id", ""), pair[1].get("context_id", "")))

    status_counts: dict[str, int] = {}
    for context in all_contexts:
        status = context.get("review_status") or "not recorded"
        status_counts[status] = status_counts.get(status, 0) + 1
    pending_count = status_counts.get("source_verified_pending_clinical_review", 0)
    approved_count = sum(
        count
        for status, count in status_counts.items()
        if status in {"clinician_approved", "approved"}
    )
    rejected_count = sum(
        count
        for status, count in status_counts.items()
        if status in {"rejected", "review_rejected"}
    )
    other_count = len(all_contexts) - pending_count - approved_count - rejected_count

    lines = [
        "# Probiotic evidence review packet",
        "",
        "> Generated from `scripts/data/clinically_relevant_strains.json` on 2026-09-14.",
        "> This packet is a research handoff. Reviewers supply source-backed recommendations; the registry and pipeline remain the source of truth.",
        "> The engineering owner verifies each recommendation against the cited source and the frozen schema, then applies the final registry status. Reviewers do not edit statuses or the registry.",
        "> Automated source check: [PubMed verification report](EVIDENCE_API_VERIFICATION_2026-09-14.json) — 182/182 citation references matched; 0 mismatches.",
        "> Batch-1 structural patch: `scripts/audits/probiotic_curation_queue_2026_09_13/batch1_disposition_2026-09-14.json` (snapshot-bound; statuses unchanged).",
        "",
        "## Where we are",
        "",
        "The source records and citations have already been assembled. The decisions below have not yet been written into the registry, so no evidence change is shipped from this packet by itself.",
        "",
        f"- **Pending review:** {pending_count}",
        f"- **Recorded approved:** {approved_count}",
        f"- **Recorded rejected:** {rejected_count}",
        f"- **Other registry states:** {other_count}",
        f"- **Contexts shown in this packet:** {len(contexts)}",
        f"**Owning identities represented:** {len({entry.get('id') for entry, _ in contexts})}",
        "",
        "## What is already done",
        "",
        "- Source links and citation identifiers were checked before this packet was generated.",
        "- Each context already has an identity scope, population, condition, dose fields, outcomes, and limitations where available.",
        "- Clean → Enrich → Score is the production pipeline. Review decisions only change which evidence contexts are eligible; they do not bypass cleaning, enrichment, scoring, or release checks.",
        "- Unresolved values remain unresolved. The system never fills a missing dose, turns a combination result into single-strain evidence, or treats a ranking as a direct treatment effect.",
        "",
        "## What the reviewer needs to do",
        "",
        "For each context, compare the record with the linked PubMed entry and full text when needed. Return only the context ID, one recommendation, and a short rationale. Do not edit the registry or assign a final status; the engineering owner performs that verification and change.",
        "",
        "Record exactly one decision (these are deliberately different):",
        "- **Approve as written** — the record is an accurate source summary. This does *not* mean the result was positive, and it does not make an unresolved dose eligible for scoring.",
        "- **Approve with correction** — the source is usable, but specify the exact field-level correction (for example, a missing strain component or full-text dose) before it can be applied.",
        "- **Reject** — the source/context should not be used, even after correction; give the reason and identify a replacement if one exists.",
        "- **Needs source clarification** — keep pending because full text, an underlying trial, or a dose/form detail must be checked first.",
        "",
        "A null or negative outcome may still be approved as an accurate record; it will never create a positive evidence bonus. Combination evidence remains combination evidence. A context with an unresolved dose may be approved as a source summary, but it remains ineligible for exact-dose applicability until the dose is resolved.",
        "",
        "Return the context ID, recommendation, and rationale. For a correction, include an exact before/after field value, the source PMID, and the source location. The engineering owner verifies the recommendation, records the source snapshot, and applies the final status with the existing review provenance.",
        "",
        "## Schema to use (do not invent fields)",
        "",
        "The registry is authoritative. Put corrections only in these existing paths:",
        "- **Dose:** `dose.dose_status`, `dose.dose_basis`, `dose.values`, `dose.unit`, `dose.dosage_forms`, `dose.duration_days`, `dose.duration_as_printed`, `dose.duration_basis`, `dose.administration_frequency`, `dose.component_doses`, and `dose.source_provenance`.",
        "- **Evidence:** `evidence_role`.",
        "- **Components:** `component_registration_status`.",
        "- **Eligibility:** `scoring_eligible` at the context level only.",
        "- **Outcomes:** `outcomes[].name`, `hierarchy`, `kind`, `direction`, and `outcome_role`.",
        "",
        "Use only the existing vocabulary:",
        "- `dose_status`: `verified`, `source_not_reported`, `extraction_pending`, `conflicting_source_values`, `combination_total_only`.",
        "- `dose_basis`: `per_strain_daily`, `combination_total_daily`, `nominal_assigned_arm`, `measured_viability`, `single_challenge`, `not_applicable`.",
        "- `duration_basis`: `fixed_protocol`, `tied_to_cotherapy`, `participant_specific`, `endpoint_followup_only`, `not_recorded`, `extraction_pending`.",
        "- `evidence_role`: `direct_rct`, `network_meta_analysis`, `systematic_review`, `meta_analysis`, `guideline`, `companion_analysis`, `observational_study`, `mechanistic_study`.",
        "- `outcome kind`: `patient_important`, `surrogate`, `evidence_ranking`; `outcome_role`: `direct_between_group_effect`, `network_ranking`, `within_group_change`, `surrogate`, `post_hoc_subgroup`, `companion_reported_context`.",
        "- `component_registration_status`: `fully_registered`, `unregistered_components_present`, `identity_uncertain`.",
        "",
        "Do not create variants such as `studied_dose.*`, `network_node_estimate`, `systematic_review_guideline`, `recoverable_manual`, `daily_use_comparable`, or outcome-level eligibility flags. If the source does not support a value, leave it pending or source-not-reported.",
        "",
        "## What happens after the decisions",
        "",
        "1. The engineering owner verifies the recommendation against the cited source, the exact context ID, and the named source snapshot.",
        "2. The owner applies the final status and any corrections only after schema/source validation; rejected or unresolved contexts remain excluded.",
        "3. The normal Clean → Enrich → Score pipeline runs. Only verified, eligible evidence contributes to scoring; rankings, class-level results, companion reports, and unresolved doses stay bounded.",
        "4. Release checks compare the generated catalog with the prior release, then the approved build is shipped to the app.",
        "",
        "---",
        "",
    ]

    current_identity = None
    for index, (entry, context) in enumerate(contexts, start=1):
        identity = entry.get("id", "unknown")
        if identity != current_identity:
            current_identity = identity
            lines.extend([f"## {identity}", ""])

        pmids = context.get("source_pmids", [])
        links = ", ".join(
            f"[PMID {pmid}](https://pubmed.ncbi.nlm.nih.gov/{pmid}/)" for pmid in pmids
        ) or "No PMID recorded"
        population = context.get("population", {})
        limitations = context.get("limitations", [])
        limitation_lines = (
            [f"  - {limitation}" for limitation in limitations]
            if limitations
            else ["  - Not recorded"]
        )
        lines.extend(
            [
                f"### {index}. `{context.get('context_id', 'unknown')}`",
                "",
                f"- **Decision:** ☐ Approve as written  ☐ Approve with correction  ☐ Reject  ☐ Needs source clarification",
                f"- **Source:** {links}",
                f"- **Identity scope:** {_bullet(context.get('identity_scope'))}; components={_bullet(context.get('components'))}",
                f"- **Evidence role:** {_bullet(context.get('evidence_role'))}; component_registration_status={_bullet(context.get('component_registration_status'))}; schema={_bullet(context.get('context_schema_version'))}",
                f"- **Condition / purpose:** {_bullet(context.get('condition'))} / {_bullet(context.get('purpose'))}",
                f"- **Population:** {_bullet(population.get('description'))}; age_group={_bullet(population.get('age_group'))}",
                f"- **Studied dose:** {_dose(context.get('dose', {}))}",
                "- **Outcomes:**",
                _outcomes(context.get("outcomes", [])),
                "- **Limitations:**",
                *limitation_lines,
                "- **Rationale / notes:**",
                "",
            ]
        )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(lines) + "\n")
    print(f"Wrote {len(contexts)} contexts to {OUTPUT}")


if __name__ == "__main__":
    build()
