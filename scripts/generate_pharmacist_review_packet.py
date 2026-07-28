#!/usr/bin/env python3
"""Generate the bounded B1 pharmacist review packet from the shipped artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


# The complete set of record fields the Flutter card renders to consumers,
# in display order, paired with the on-screen label the user actually sees
# (`pg_depletion_card.dart`). This is the SINGLE source of truth for "what a
# reviewer is being asked to approve":
#   * the packet renders every one of these, so approval covers the whole card;
#   * `test_generate_pharmacist_review_packet.py` asserts none escapes the packet;
#   * `test_b1_clinical_signoff.py` asserts every one is inside the ledger's
#     clinical fingerprint, so none can change without re-review.
# Added 2026-07-27 after `food_sources_short` reached users while being absent
# from all three review surfaces (fingerprint, packet, and reviewer golden).
# NOTE: `monitoring_note` is deliberately NOT here — no Dart code reads it.
CONSUMER_VISIBLE_FIELDS: tuple[tuple[str, str], ...] = (
    ("alert_headline", "Headline"),
    ("alert_body", "Body"),
    ("monitoring_tip_short", "Monitoring tip"),
    ("clinical_impact", "What can happen"),
    ("food_sources_short", "From food"),
    ("mechanism", "Why"),
    ("recommendation", "Clinical guidance"),
)

CONSUMER_VISIBLE_FIELD_NAMES = frozenset(
    name for name, _ in CONSUMER_VISIBLE_FIELDS
)

APP_UNAVAILABLE_TITLE = "Check unavailable"
APP_UNAVAILABLE_BODY = (
    "We couldn't load the medication & nutrient checks right now. "
    "This is not an all-clear — please try again later."
)
CLINICIAN_UNAVAILABLE_STATUS = "Unavailable"
CLINICIAN_UNAVAILABLE_BODY = (
    "Medication-nutrient analysis was unavailable when this report was "
    "generated. This is not evidence that no interactions exist - the "
    "check could not run."
)
CLINICIAN_PARTIAL_STATUS = "Partial - fallback artifact"
CLINICIAN_PARTIAL_BODY = (
    "Partial medication-nutrient analysis: a fallback reference artifact "
    "was used. Review these notes in that context."
)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def _link(source: dict[str, Any]) -> str:
    label = _clean(source.get("label")) or _clean(source.get("source_type"))
    url = _clean(source.get("url"))
    return f"[{label}]({url})" if url else label


def build_packet(
    artifact: dict[str, Any],
    *,
    ledger: dict[str, Any] | None = None,
    verified_screenshot: str,
    unavailable_screenshot: str,
) -> str:
    metadata = artifact.get("_metadata", {})
    rows = artifact.get("depletions", [])
    by_id = {row.get("id"): row for row in rows}
    if ledger is None:
        reviewed = [
            row
            for row in rows
            if row.get("citation_review_status") == "verified"
        ]
        review_records = {
            row["id"]: {
                "disposition": "pending",
                "note": "Clinical reviewer disposition requested.",
            }
            for row in reviewed
        }
        ledger_metadata: dict[str, Any] = {}
    else:
        review_records = ledger.get("records", {})
        missing = sorted(set(review_records) - set(by_id))
        if missing:
            raise ValueError(
                "Sign-off ledger references records missing from artifact: "
                + ", ".join(missing)
            )
        reviewed = [by_id[record_id] for record_id in review_records]
        ledger_metadata = ledger.get("_metadata", {})

    reviewed = sorted(
        reviewed,
        key=lambda row: (
            _clean(row.get("drug_ref", {}).get("display_name")).lower(),
            _clean(row.get("depleted_nutrient", {}).get("standard_name")).lower(),
        ),
    )
    active = [
        row
        for row in rows
        if row.get("citation_review_status") == "verified"
    ]
    excluded = len(rows) - len(active)
    signed = ledger is not None
    licensed_signoff = bool(
        signed and ledger_metadata.get("licensed_pharmacist_signoff")
    )
    status = (
        "licensed pharmacist clinical review complete"
        if licensed_signoff
        else (
            "AI clinical-content review complete"
            if signed
            else "clinical reviewer sign-off requested"
        )
    )

    packet_title = _clean(
        ledger_metadata.get("packet_title")
        if signed
        else "B1 pharmacist review packet"
    ) or "B1 pharmacist review packet"
    packet_status = _clean(
        ledger_metadata.get("packet_status") if signed else status
    ) or status
    packet_scope_override = _clean(
        ledger_metadata.get("packet_scope") if signed else ""
    )
    if packet_scope_override:
        packet_scope_line = f"Scope: **{packet_scope_override}**"
    else:
        packet_scope_line = (
            f"Scope: **{len(active)} consumer-visible records** after "
            f"**{len(reviewed)} reviewed records**. "
            f"The {excluded} suppressed/rejected records are intentionally "
            "not consumer-facing."
        )

    lines = [
        f"# {packet_title}",
        "",
        f"Status: **{packet_status}**",
        "",
        packet_scope_line,
        "",
        (
            f"Artifact: schema `{_clean(metadata.get('schema_version'))}`, "
            f"content version `{_clean(metadata.get('content_version'))}`, "
            f"content hash `{_clean(metadata.get('content_hash'))}`."
        ),
        "",
        "## Review focus",
        "",
        (
            "**Approval covers the full card copy shown to the user — all "
            "seven consumer-visible fields reproduced under each record "
            "below, not only mechanism, clinical impact, and "
            "recommendation.** Every line printed under \"Consumer-visible "
            "card copy\" is text a user can read in the app."
        ),
        "",
        "- Confirm the medication scope and nutrient relationship are clinically accurate.",
        "- Confirm the mechanism and clinical impact are supported by the linked evidence.",
        "- Confirm recommendations are calm, actionable, and do not imply universal supplementation.",
        "- Confirm monitoring and supplement-interaction records are not presented as measured deficiency.",
        (
            "- Dispositions are limited to `approved`, "
            "`approved_with_wording_change`, `requires_evidence_revision`, "
            "or `remove_from_release`."
        ),
        "",
        "## App presentation",
        "",
        "**These images are layout-regression artifacts, not clinical-review "
        "evidence.** They are Flutter golden files: text renders as filled "
        "boxes because no font is registered in the test binding, and the "
        "verified card is captured in its collapsed state, so the expanded "
        "detail copy does not appear. Review the card copy from the "
        "per-record text below, which is the authoritative source. Do not "
        "base an approval on these screenshots.",
        "",
        "Verified records (layout only):",
        "",
        f"![Verified medication-nutrient layout]({verified_screenshot})",
        "",
        "Unavailable analysis, explicitly not an all-clear (layout only):",
        "",
        f"![Unavailable medication-nutrient layout]({unavailable_screenshot})",
        "",
        "### Exact unavailable and partial-state copy",
        "",
        "App unavailable card:",
        "",
        f"- Title: {APP_UNAVAILABLE_TITLE}",
        f"- Body: {APP_UNAVAILABLE_BODY}",
        "",
        "Clinician report unavailable state:",
        "",
        f"- Status: {CLINICIAN_UNAVAILABLE_STATUS}",
        f"- Body: {CLINICIAN_UNAVAILABLE_BODY}",
        "",
        "Clinician report partial state:",
        "",
        f"- Status: {CLINICIAN_PARTIAL_STATUS}",
        f"- Body: {CLINICIAN_PARTIAL_BODY}",
        "",
        "## Review disposition index",
        "",
        "| Record | Medication / class | Nutrient | Relationship | Disposition | Consumer-visible |",
        "|---|---|---|---|---|---|",
    ]

    for row in reviewed:
        drug = row["drug_ref"]
        nutrient = row["depleted_nutrient"]
        review = review_records[row["id"]]
        visible = (
            "yes" if row.get("citation_review_status") == "verified" else "no"
        )
        lines.append(
            (
                "| `{id}` | {drug} (`{drug_id}`) | {nutrient} | "
                "`{relationship}` | `{disposition}` | {visible} |"
            ).format(
                id=_clean(row.get("id")),
                drug=_clean(drug.get("display_name")).replace("|", "\\|"),
                drug_id=_clean(drug.get("id")),
                nutrient=_clean(nutrient.get("standard_name")).replace("|", "\\|"),
                relationship=_clean(row.get("depletion_type")),
                disposition=_clean(review.get("disposition")),
                visible=visible,
            )
        )

    lines.extend(["", "## Record details", ""])
    for index, row in enumerate(reviewed, start=1):
        drug = row["drug_ref"]
        nutrient = row["depleted_nutrient"]
        sources = "; ".join(_link(source) for source in row.get("sources", []))
        review = review_records[row["id"]]
        drug_id = _clean(drug.get("id"))
        typed_drug_id = (
            drug_id
            if drug_id.startswith(f"{_clean(drug.get('type'))}:")
            else f"{_clean(drug.get('type'))}:{drug_id}"
        )
        lines.extend(
            [
                f"### {index}. `{_clean(row.get('id'))}`",
                "",
                f"- Medication / class: {_clean(drug.get('display_name'))} "
                f"(`{typed_drug_id}`)",
                f"- Nutrient: {_clean(nutrient.get('standard_name'))} "
                f"(`{_clean(nutrient.get('canonical_id'))}`)",
                f"- Relationship: `{_clean(row.get('depletion_type'))}`; "
                f"severity `{_clean(row.get('severity'))}`; "
                f"onset `{_clean(row.get('onset_timeline'))}`",
                "",
                "Consumer-visible card copy (every line below is shown to the "
                "user — approval covers all of it):",
                "",
            ]
        )
        for field, label in CONSUMER_VISIBLE_FIELDS:
            value = _clean(row.get(field))
            lines.append(
                f"- {label} (`{field}`): {value if value else '_(not set)_'}"
            )
        lines.extend(
            [
                "",
                f"- Evidence: {sources}",
                "",
                (
                    "Reviewer disposition: "
                    f"**`{_clean(review.get('disposition'))}`**"
                ),
                f"Review note: {_clean(review.get('note'))}",
                (
                    "Consumer-visible after review: "
                    + (
                        "**yes**"
                        if row.get("citation_review_status") == "verified"
                        else "**no**"
                    )
                ),
                "",
                "Reviewer comment (Approved / Approved with wording change / "
                "Requires evidence revision / Remove from release, plus any "
                "required change): _______________________________________",
                "",
            ]
        )

    if signed:
        pharmacist_status = (
            "**confirmed**"
            if licensed_signoff
            else "**not represented by this packet**"
        )
        scope_statement = (
            "This packet records licensed-pharmacist approval of the bounded "
            "controlled-beta corpus."
            if licensed_signoff
            else (
                "This packet requests licensed-pharmacist review of the "
                "documented evidence audit; it does not record release "
                "approval or claim professional licensure."
            )
        )
        provenance_lines: list[str] = []
        evidence_auditor = _clean(ledger_metadata.get("supporting_reviewer"))
        if evidence_auditor:
            provenance_lines.append(
                "- Evidence auditor: "
                f"`{evidence_auditor}` "
                f"({_clean(ledger_metadata.get('supporting_reviewer_type'))})"
            )
        approver_organization = _clean(
            ledger_metadata.get("licensed_clinical_approver_organization")
        )
        if approver_organization:
            provenance_lines.append(
                "- Licensed clinical approver organization: "
                f"`{approver_organization}`"
            )
        lines.extend(
            [
                "## Sign-off",
                "",
                (
                    "- Reviewer: "
                    f"`{_clean(ledger_metadata.get('reviewer'))}` "
                    f"({_clean(ledger_metadata.get('reviewer_type'))})"
                ),
                f"- Review date: `{_clean(ledger_metadata.get('reviewed_at'))}`",
                (
                    "- Release disposition: "
                    f"`{_clean(ledger_metadata.get('release_disposition'))}`"
                ),
                *provenance_lines,
                (
                    "- Licensed pharmacist sign-off: "
                    f"{pharmacist_status}"
                ),
                (
                    f"- Scope statement: {scope_statement}"
                ),
                "",
            ]
        )
    else:
        lines.extend(
            [
                "## Sign-off",
                "",
                "- Reviewer name / credentials:",
                "- Review date:",
                "- Approved records:",
                "- Records requiring revision:",
                "- Notes:",
                "",
            ]
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--artifact",
        type=Path,
        default=Path("scripts/data/medication_depletions.json"),
    )
    parser.add_argument("--ledger", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verified-screenshot", required=True)
    parser.add_argument("--unavailable-screenshot", required=True)
    args = parser.parse_args()

    artifact = json.loads(args.artifact.read_text(encoding="utf-8"))
    ledger = (
        json.loads(args.ledger.read_text(encoding="utf-8"))
        if args.ledger
        else None
    )
    packet = build_packet(
        artifact,
        ledger=ledger,
        verified_screenshot=args.verified_screenshot,
        unavailable_screenshot=args.unavailable_screenshot,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(packet, encoding="utf-8")
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
