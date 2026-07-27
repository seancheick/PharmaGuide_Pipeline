#!/usr/bin/env python3
"""Fail-close unsupported Section 7 diabetes/metabolic depletion claims."""

import json
from pathlib import Path


DATA = Path(__file__).resolve().parents[2] / "data" / "medication_depletions.json"
REVIEWER = "medication_depletion_section_07_diabetes_metabolic_audit"
DISPOSITIONS = {
    "DEP_METFORMIN_FOLATE": (
        "needs_revision",
        "Suppressed: PMID 20488910 reports no significant adjusted folate effect; "
        "the evidence does not establish folate deficiency or this consumer supplementation claim.",
    ),
    "DEP_DIABETESMEDS_MAGNESIUM": (
        "rejected",
        "Rejected: this is diabetes-associated hypomagnesemia, not evidence that "
        "sulfonylureas or thiazolidinediones deplete magnesium.",
    ),
    "DEP_INSULINS_MAGNESIUM": (
        "rejected",
        "Rejected: PMID 26696633 reviews diabetes-associated hypomagnesemia and "
        "does not establish insulin-caused chronic magnesium depletion.",
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
    "alert_body": "No medication-caused nutrient depletion has been established over time; no consumer warning is emitted.",
    "acknowledgement_note": "No medication-specific nutrient coverage acknowledgement is emitted.",
    "monitoring_tip_short": "Discuss individual monitoring needs with your treating clinician.",
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
