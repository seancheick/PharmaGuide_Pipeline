"""Section 9 — direct label effects stay active; broad specialty classes fail closed."""

import json
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data" / "medication_depletions.json"

def test_section9_specialized_therapy_dispositions_are_scope_matched():
    entries = {entry["id"]: entry for entry in json.loads(DATA.read_text())["depletions"]}
    for entry_id in (
        "DEP_ORLISTAT_VITAMINA", "DEP_ORLISTAT_VITAMIND", "DEP_ORLISTAT_VITAMINE", "DEP_ORLISTAT_VITAMINK",
        "DEP_CHOLESTYRAMINE_VITAMINA", "DEP_CHOLESTYRAMINE_VITAMIND", "DEP_CHOLESTYRAMINE_VITAMINE", "DEP_CHOLESTYRAMINE_VITAMINK",
    ):
        assert entries[entry_id]["citation_review_status"] == "verified"
    for entry_id in (
        "DEP_IMMUNOSUPPRESSANTS_MAGNESIUM", "DEP_IMMUNOSUPPRESSANTS_VITAMIND",
        "DEP_HIVPI_VITAMIND", "DEP_HIVPI_ZINC",
    ):
        assert entries[entry_id]["citation_review_status"] == "needs_revision"
        assert entries[entry_id]["recommendation"] == "Do not supplement solely because of this medication or condition."
