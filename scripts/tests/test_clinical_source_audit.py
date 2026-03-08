import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from audit_clinical_sources import audit_entries


def test_audit_flags_uncited_and_contradictory_entries():
    report = audit_entries(
        [
            {
                "id": "ENTRY_UNCITED",
                "notes": "Strong human evidence.",
                "notable_studies": "Large trial reported benefit.",
                "evidence_level": "ingredient-human",
                "study_type": "rct_multiple",
                "published_studies": ["RCT"],
            },
            {
                "id": "ENTRY_CONTRADICTORY",
                "notes": "No standalone RCTs were identified.",
                "notable_studies": "Combination products only.",
                "evidence_level": "ingredient-human",
                "study_type": "rct_single",
                "published_studies": ["RCT"],
            },
            {
                "id": "ENTRY_CITED",
                "notes": "Supported by NIH ODS and randomized evidence.",
                "notable_studies": "PMID 12345678 reported benefit.",
                "evidence_level": "ingredient-human",
                "study_type": "rct_single",
                "published_studies": ["RCT"],
            },
        ]
    )

    assert "ENTRY_UNCITED" in report["entries_without_explicit_source_text"]
    assert "ENTRY_CITED" not in report["entries_without_explicit_source_text"]
    contradiction_ids = {item["id"] for item in report["entries_with_possible_contradictions"]}
    assert "ENTRY_CONTRADICTORY" in contradiction_ids
