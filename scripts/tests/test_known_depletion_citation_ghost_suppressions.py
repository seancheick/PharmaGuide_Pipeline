"""Known real-but-unrelated PMIDs must not remain visible in the app."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


KNOWN_GHOSTS = {
    "DEP_OCP_MAGNESIUM": "23636014",
    "DEP_OCP_ZINC": "23636014",
    "DEP_ANTIPSYCHOTICS_VITAMIND": "25638514",
    "DEP_ANTIPSYCHOTICS_COQ10": "18316143",
    "DEP_STIMULANTS_VITAMINC": "10870150",
    "DEP_HIVPI_VITAMIND": "21694637",
    "DEP_HIVPI_ZINC": "12591569",
    "DEP_IMMUNOSUPPRESSANTS_MAGNESIUM": "16641596",
    "DEP_IMMUNOSUPPRESSANTS_VITAMIND": "19528952",
    "DEP_BENZODIAZEPINES_MELATONIN": "2733455",
    "DEP_BVITAMINS_INTERACTIONS": "2132402",
}


@pytest.fixture(scope="module")
def entries() -> dict[str, dict]:
    source = Path(__file__).resolve().parents[1] / "data" / "medication_depletions.json"
    return {entry["id"]: entry for entry in json.loads(source.read_text())["depletions"]}


def test_every_known_content_mismatch_is_suppressed(entries):
    for entry_id, pmid in KNOWN_GHOSTS.items():
        entry = entries[entry_id]
        assert entry.get("citation_review_status") == "needs_revision", entry_id
        note = (entry.get("citation_review_note") or "").lower()
        assert pmid in note and "content mismatch" in note, entry_id


def test_suppression_does_not_relabel_a_ghost_as_supporting_evidence(entries):
    for entry_id, pmid in KNOWN_GHOSTS.items():
        source = next(
            source for source in entries[entry_id]["sources"] if pmid in source.get("url", "")
        )
        assert "content mismatch" in (source.get("label") or "").lower() or (
            entries[entry_id].get("citation_review_status") == "needs_revision"
        )


def test_betablocker_coq10_source_label_names_the_paper_its_url_points_to(entries):
    """The label named Folkers' 1990 lovastatin paper while the URL is PMID
    12392188, Cocco 2002 "The antihypertensive drug carvedilol inhibits the
    activity of mitochondrial NADH-ubiquinone oxidoreductase" (verified
    2026-09-26). The record stays suppressed."""
    entry = entries["DEP_BETABLOCKERS_COQ10"]
    sources = [s for s in entry["sources"] if "12392188" in s.get("url", "")]
    assert sources
    for source in sources:
        assert "lovastatin" not in source["label"].lower()
        assert "carvedilol" in source["label"].lower()
    assert entry["citation_review_status"] == "needs_revision"
