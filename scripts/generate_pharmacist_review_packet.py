#!/usr/bin/env python3
"""Generate the bounded B1 pharmacist review packet from the shipped artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


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
    status = (
        "AI clinical-content review complete"
        if signed
        else "clinical reviewer sign-off requested"
    )

    lines = [
        "# B1 pharmacist review packet",
        "",
        f"Status: **{status}**",
        "",
        (
            f"Scope: **{len(active)} consumer-visible records** after "
            f"**{len(reviewed)} reviewed records**. "
            f"The {excluded} suppressed/rejected records are intentionally "
            "not consumer-facing."
        ),
        "",
        (
            f"Artifact: schema `{_clean(metadata.get('schema_version'))}`, "
            f"content version `{_clean(metadata.get('content_version'))}`, "
            f"content hash `{_clean(metadata.get('content_hash'))}`."
        ),
        "",
        "## Review focus",
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
        "Verified records:",
        "",
        f"![Verified medication-nutrient presentation]({verified_screenshot})",
        "",
        "Unavailable analysis (explicitly not an all-clear):",
        "",
        f"![Unavailable medication-nutrient presentation]({unavailable_screenshot})",
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
                f"- Mechanism: {_clean(row.get('mechanism'))}",
                f"- Clinical impact: {_clean(row.get('clinical_impact'))}",
                f"- Recommendation: {_clean(row.get('recommendation'))}",
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
            ]
        )

    if signed:
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
                (
                    "- Licensed pharmacist sign-off: "
                    "**not represented by this packet**"
                ),
                (
                    "- Scope statement: This is a documented AI "
                    "clinical-content audit and controlled-beta sign-off; it "
                    "does not claim professional licensure."
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
