#!/usr/bin/env python3
"""Fail-close unsupported or over-broad Section 8 depletion claims."""

import json
from pathlib import Path


DATA = Path(__file__).resolve().parents[2] / "data" / "medication_depletions.json"
REVIEWER = "medication_depletion_section_08_antibiotics_nsaids_audit"
DISPOSITIONS = {
    "DEP_NSAIDS_FOLATE": (
        "rejected",
        "Rejected: broad NSAID folate depletion and routine supplementation lack claim-matched clinical evidence.",
    ),
    "DEP_NSAIDS_IRON": (
        "needs_revision",
        "Suppressed: NSAID-associated GI bleeding can cause iron-deficiency anaemia, but this "
        "all-NSAID record lacks a dose, duration, and bleeding-risk scope for a consumer nutrient alert.",
    ),
    "DEP_NSAIDS_VITAMINC": (
        "rejected",
        "Rejected: no claim-matched clinical citation supports routine NSAID or aspirin vitamin-C depletion supplementation.",
    ),
    "DEP_ANTIBIOTICS_BVITAMINS": (
        "rejected",
        "Rejected: microbiome disruption does not establish broad-antibiotic vitamin B12 depletion; "
        "the synthetic non-RxCUI subject is not runtime-mappable.",
    ),
    "DEP_ANTIBIOTICS_VITAMINK": (
        "needs_revision",
        "Suppressed: vitamin-K coagulopathy evidence is limited to narrow high-risk scenarios and "
        "the synthetic non-RxCUI subject is not runtime-mappable.",
    ),
}
NEUTRAL_COPY = {
    "evidence_level": "possible",
    "mechanism": "No consumer depletion mechanism is asserted pending exact supporting evidence.",
    "clinical_impact": "No consumer depletion warning is emitted.",
    "recommendation": "Do not supplement solely because of this medication or condition.",
    "onset_timeline": "not established",
    "monitoring_note": "No medication-specific nutrient monitoring recommendation is emitted.",
    "alert_headline": "No medication-specific depletion alert",
    "alert_body": "This record does not establish a medication-caused nutrient depletion warning.",
    "acknowledgement_note": "No medication-specific nutrient coverage acknowledgement is emitted.",
    "monitoring_tip_short": "Follow the monitoring plan set by your treating clinician.",
    "food_sources_short": "Maintain dietary intake appropriate to your individual needs.",
}


def main() -> None:
    document = json.loads(DATA.read_text())
    entries = {entry["id"]: entry for entry in document["depletions"]}
    for entry_id, (status, note) in DISPOSITIONS.items():
        entry = entries[entry_id]
        entry.update(
            citation_review_status=status,
            citation_review_note=note,
            reviewed_at="2026-07-26",
            reviewer=REVIEWER,
            **NEUTRAL_COPY,
        )
        entry.pop("adequacy_threshold_mcg", None)
        entry.pop("adequacy_threshold_mg", None)
    DATA.write_text(json.dumps(document, indent=2) + "\n")


if __name__ == "__main__":
    main()
