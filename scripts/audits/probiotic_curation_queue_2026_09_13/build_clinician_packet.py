"""Build a single clinician-review packet from the canonical probiotic registry."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
REGISTRY = ROOT / "scripts/data/clinically_relevant_strains.json"
OUTPUT = ROOT / "docs/plans/CLINICIAN_REVIEW_PACKET_2026-09-14.md"


def _bullet(value: object) -> str:
    return str(value) if value not in (None, "", [], {}) else "not recorded"


def _dose(dose: dict[str, object]) -> str:
    values = ", ".join(str(v) for v in dose.get("values", [])) or "unresolved"
    forms = ", ".join(str(v) for v in dose.get("dosage_forms", [])) or "unresolved"
    therapies = ", ".join(str(v) for v in dose.get("co_therapies", [])) or "none recorded"
    return (
        f"basis={_bullet(dose.get('basis'))}; values={values}; "
        f"unit={_bullet(dose.get('unit'))}; forms={forms}; "
        f"duration_days={_bullet(dose.get('duration_days'))}; co-therapies={therapies}"
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
                ]
            )
        )
    return "\n".join(lines)


def build() -> None:
    registry = json.loads(REGISTRY.read_text())
    entries = registry["clinically_relevant_strains"]
    contexts = [
        (entry, context)
        for entry in entries
        for context in entry.get("study_contexts", [])
        if context.get("review_status") == "source_verified_pending_clinical_review"
    ]
    contexts.sort(key=lambda pair: (pair[0].get("id", ""), pair[1].get("context_id", "")))

    lines = [
        "# Clinician review packet — probiotic evidence contexts",
        "",
        "> Generated from `scripts/data/clinically_relevant_strains.json` on 2026-09-14.",
        "> This packet is a review aid, not an approval. Every item remains pending until an attributable clinician records approve/reject and rationale in the canonical registry workflow.",
        "",
        f"**Pending contexts:** {len(contexts)}  ",
        f"**Owning identities represented:** {len({entry.get('id') for entry, _ in contexts})}",
        "",
        "## Instructions for the clinician",
        "",
        "For each context, verify the exact strain/identity scope, population, condition, tested dose and form, outcomes, and limitations against the linked PubMed record and full text when needed. Do not infer a missing dose or convert a combination result into single-strain evidence.",
        "",
        "Record exactly one decision (these are deliberately different):",
        "- **Approve as written** — the record is an accurate source summary. This does *not* mean the result was positive, and it does not make an unresolved dose eligible for scoring.",
        "- **Approve with correction** — the source is usable, but specify the exact field-level correction (for example, a missing strain component or full-text dose) before it can be applied.",
        "- **Reject** — the source/context should not be used, even after correction; give the reason and identify a replacement if one exists.",
        "- **Needs source clarification** — keep pending because full text, an underlying trial, or a dose/form detail must be checked first.",
        "",
        "A null or negative outcome may still be approved as an accurate record; it will never create a positive evidence bonus. Combination evidence remains combination evidence. A context with an unresolved dose may be approved as a source summary, but it remains ineligible for exact-dose applicability until the dose is resolved.",
        "",
        "The reviewer should return the context ID, decision, reviewer name/credentials, date, whether full text was checked, and rationale. For a correction, include an exact before/after field value. The registry remains unchanged until that attributable decision is entered.",
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
                f"- **Condition / purpose:** {_bullet(context.get('condition'))} / {_bullet(context.get('purpose'))}",
                f"- **Population:** {_bullet(population.get('description'))}; age_group={_bullet(population.get('age_group'))}",
                f"- **Studied dose:** {_dose(context.get('dose', {}))}",
                "- **Outcomes:**",
                _outcomes(context.get("outcomes", [])),
                "- **Limitations:**",
                *limitation_lines,
                "- **Reviewer / credentials:**",
                "- **Decision date:**",
                "- **Rationale / notes:**",
                "",
            ]
        )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(lines) + "\n")
    print(f"Wrote {len(contexts)} contexts to {OUTPUT}")


if __name__ == "__main__":
    build()
