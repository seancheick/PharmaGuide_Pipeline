"""Section 7 — diabetes/metabolic claims must not turn disease association into drug depletion."""

import json
from pathlib import Path


DATA = Path(__file__).resolve().parent.parent / "data" / "medication_depletions.json"


def test_section7_claims_fail_closed_when_evidence_is_not_a_consumer_depletion_claim():
    entries = {item["id"]: item for item in json.loads(DATA.read_text())["depletions"]}
    expected = {
        "DEP_METFORMIN_FOLATE": "needs_revision",
        "DEP_DIABETESMEDS_MAGNESIUM": "rejected",
        "DEP_INSULINS_MAGNESIUM": "rejected",
    }
    assert {entry_id: entries[entry_id].get("citation_review_status") for entry_id in expected} == expected
    for entry_id in expected:
        entry = entries[entry_id]
        assert entry["citation_review_status"] != "verified"
        assert entry["recommendation"] == "Do not supplement solely because of this medication or condition."
