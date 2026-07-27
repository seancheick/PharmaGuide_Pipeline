#!/usr/bin/env python3
"""Fail-close Section 4 oral-contraceptive depletion claims.

The medication bridge preserves ingredient RxCUIs but not route/formulation.
Ethinyl-estradiol ingredient membership would match combined oral pills, the
patch, and the vaginal ring alike. Until route-aware identity exists, evidence
about combined oral pills cannot be promoted through the broad hormonal class.
"""

from __future__ import annotations

import json
from pathlib import Path


PATH = Path(__file__).resolve().parents[2] / "data" / "medication_depletions.json"
REVIEWER = "medication_depletion_section_04_scope_audit"
DATE = "2026-07-26"

UPDATES = {
    "DEP_OCP_VITAMINB12": {
        "status": "rejected",
        "evidence_level": "possible",
        "mechanism": "Some combined oral-contraceptive studies report lower measured serum vitamin B12, likely involving carrier-protein changes. Those biomarker findings do not establish reduced absorption or functional vitamin B12 deficiency.",
        "clinical_impact": "No oral-contraceptive vitamin B12 depletion warning is emitted. A low serum result should be interpreted clinically with appropriate confirmatory testing rather than attributed to contraception alone.",
        "recommendation": "Follow ordinary dietary vitamin B12 guidance. Do not start a B12 supplement solely because of hormonal contraceptive use.",
        "citation_review_note": "Rejected: PMID 21967158 reviews serum B12 changes with oral contraceptives, but a biomarker change is not evidence of functional deficiency or a consumer supplementation indication. The current runtime class also includes non-oral hormonal methods, so combined-pill evidence cannot be promoted safely.",
    },
    "DEP_OCP_VITAMINC": {
        "status": "rejected",
        "evidence_level": "possible",
        "mechanism": "Historical oral-pill studies reported concentration differences, but they do not establish clinically meaningful vitamin C deficiency with modern formulations or across all hormonal contraceptive methods.",
        "clinical_impact": "No oral-contraceptive vitamin C depletion warning is emitted.",
        "recommendation": "Follow ordinary dietary vitamin C guidance. Do not supplement solely because of hormonal contraceptive use.",
        "citation_review_note": "Rejected: the inherited textbook claim is not claim-matched primary evidence. PMID 7001015 is an older review, not evidence of clinically meaningful deficiency in modern combined oral contraceptive users; broad hormonal-method scope is also unsupported.",
    },
    "DEP_OCP_VITAMINE": {
        "status": "rejected",
        "evidence_level": "possible",
        "mechanism": "Older literature does not establish that oral contraceptives cause clinically meaningful vitamin E deficiency; an older review found little or no alpha-tocopherol change.",
        "clinical_impact": "No oral-contraceptive vitamin E depletion warning is emitted.",
        "recommendation": "Follow ordinary dietary vitamin E guidance. Do not supplement solely because of hormonal contraceptive use.",
        "citation_review_note": "Rejected: the inherited textbook claim is not claim-matched primary evidence. PMID 7001015 reports little or no alpha-tocopherol effect and does not support a deficiency warning or supplementation recommendation.",
    },
    "DEP_OCP_MAGNESIUM": {
        "status": "needs_revision",
        "evidence_level": "possible",
        "mechanism": "No consumer mechanism is asserted: the inherited PMID is unrelated to oral contraceptives and magnesium.",
        "clinical_impact": "No oral-contraceptive magnesium depletion warning is emitted pending exact supporting evidence.",
        "recommendation": "Do not use hormonal contraceptive use alone as a reason to start magnesium supplementation.",
        "citation_review_note": "Suppressed (needs_revision): PMID 23636014 is a ghost citation and content mismatch unrelated to oral contraceptives and magnesium. Replacement requires exact contraceptive scope, nutrient evidence, mechanism, and consumer recommendation.",
    },
    "DEP_OCP_ZINC": {
        "status": "needs_revision",
        "evidence_level": "possible",
        "mechanism": "No consumer mechanism is asserted: the inherited PMID is unrelated to oral contraceptives and zinc.",
        "clinical_impact": "No oral-contraceptive zinc depletion warning is emitted pending exact supporting evidence.",
        "recommendation": "Do not use hormonal contraceptive use alone as a reason to start zinc supplementation.",
        "citation_review_note": "Suppressed (needs_revision): PMID 23636014 is a ghost citation and content mismatch unrelated to oral contraceptives and zinc. Replacement requires exact contraceptive scope, nutrient evidence, mechanism, and consumer recommendation.",
    },
}


def main() -> None:
    document = json.loads(PATH.read_text())
    entries = {item["id"]: item for item in document["depletions"]}
    for entry_id, update in UPDATES.items():
        entry = entries[entry_id]
        entry.update(
            citation_review_status=update["status"],
            evidence_level=update["evidence_level"],
            mechanism=update["mechanism"],
            clinical_impact=update["clinical_impact"],
            recommendation=update["recommendation"],
            citation_review_note=update["citation_review_note"],
            reviewed_at=DATE,
            reviewer=REVIEWER,
        )
    PATH.write_text(json.dumps(document, indent=2) + "\n")


if __name__ == "__main__":
    main()
