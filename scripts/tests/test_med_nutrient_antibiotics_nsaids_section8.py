"""Section 8 — avoid broad antibiotic/NSAID nutrient alerts without matched scope."""

import json
from pathlib import Path


DATA = Path(__file__).resolve().parent.parent / "data" / "medication_depletions.json"


def test_section8_claims_fail_closed_or_remain_narrow_scope_backlog():
    entries = {item["id"]: item for item in json.loads(DATA.read_text())["depletions"]}
    expected = {
        "DEP_NSAIDS_FOLATE": "rejected",
        "DEP_NSAIDS_IRON": "needs_revision",
        "DEP_NSAIDS_VITAMINC": "rejected",
        "DEP_ANTIBIOTICS_BVITAMINS": "rejected",
        "DEP_ANTIBIOTICS_VITAMINK": "needs_revision",
    }
    assert {entry_id: entries[entry_id].get("citation_review_status") for entry_id in expected} == expected
    for entry_id in expected:
        entry = entries[entry_id]
        assert entry["citation_review_status"] != "verified"
        assert entry["recommendation"] == "Do not supplement solely because of this medication or condition."
