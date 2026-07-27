"""Section 4 — oral-contraceptive depletion claims fail closed on scope."""

import json
from pathlib import Path


DATA = Path(__file__).resolve().parent.parent / "data" / "medication_depletions.json"


def _entries():
    return {item["id"]: item for item in json.loads(DATA.read_text())["depletions"]}


def test_section4_claims_are_not_promoted_through_broad_hormonal_class():
    entries = _entries()
    expected = {
        "DEP_OCP_VITAMINB12": "rejected",
        "DEP_OCP_MAGNESIUM": "needs_revision",
        "DEP_OCP_ZINC": "needs_revision",
        "DEP_OCP_VITAMINC": "rejected",
        "DEP_OCP_VITAMINE": "rejected",
    }
    for entry_id, status in expected.items():
        entry = entries[entry_id]
        assert entry["citation_review_status"] == status
        assert entry["drug_ref"]["id"] == "class:oral_contraceptives"
        assert entry["citation_review_status"] != "verified"


def test_ghost_citation_records_remain_suppressed():
    entries = _entries()
    for entry_id in ("DEP_OCP_MAGNESIUM", "DEP_OCP_ZINC"):
        note = entries[entry_id]["citation_review_note"].lower()
        assert "ghost" in note or "unrelated" in note
        assert entries[entry_id]["citation_review_status"] == "needs_revision"
