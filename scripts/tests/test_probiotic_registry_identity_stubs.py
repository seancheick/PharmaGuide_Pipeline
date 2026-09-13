"""Registry identities added for label resolution carry no evidence or approval.

2026-09-13: the registry grew from 49 to 100+ identities so that a printed
strain designation resolves to "exact strain, not yet reviewed" instead of
falling through to species-only. Every such stub must say how the designation
was verified, must carry no clinician sign-off, no evidence block and no
contexts, and must never present as affirmative research.
"""
import json
from pathlib import Path

import pytest

from constants import DATA_DIR
from enrich_supplements_v3 import _probiotic_research_presentation
from probiotic_measurements import label_strain_identity_resolution
from studied_formulas import clinical_strain_identity_matches

VERIFICATION_STATUSES = {
    "designation_verified",                  # PubMed title/abstract names designation + species
    "designation_found_species_unconfirmed",  # designation found; species token not in abstract
    "label_only_no_literature_hit",          # printed on labels only
}
GUIDELINE_STATUSES = {"recommended", "conditionally_recommended", "insufficient_evidence",
                      "not_recommended", "conflicting_guidance", "not_addressed"}


def _entries():
    payload = json.loads((Path(DATA_DIR) / "clinically_relevant_strains.json").read_text())
    return payload["clinically_relevant_strains"]


def _stubs():
    return [e for e in _entries() if isinstance(e.get("identity_verification"), dict)]


def test_registry_has_grown_past_the_v1_universe():
    assert len(_stubs()) >= 50


@pytest.mark.parametrize("entry", _stubs(), ids=lambda e: e["id"])
def test_stub_identity_is_honest_about_what_it_knows(entry):
    verification = entry["identity_verification"]
    assert verification["status"] in VERIFICATION_STATUSES
    if verification["status"] == "label_only_no_literature_hit":
        assert verification["source_pmids"] == []
    else:
        assert verification["source_pmids"], "a literature-verified designation must cite its PMIDs"
    assert entry["evidence_level"] == "unreviewed"
    assert entry["cfu_thresholds"]["dr_pham_signoff"] is False
    assert entry["cfu_thresholds"]["evidence"] is None
    assert entry["cfu_thresholds"]["tiers_cfu_per_day"] is None
    assert entry["study_contexts"] == []
    assert entry["key_benefits"] == []
    presented = _probiotic_research_presentation(entry)
    assert presented["research_match_status"] == "pending_review"
    assert presented["human_evidence"] is False


@pytest.mark.parametrize("entry", _stubs(), ids=lambda e: e["id"])
def test_stub_resolves_its_own_name_as_unreviewed_exact_strain(entry):
    registry = {entry["id"]: entry}
    out = label_strain_identity_resolution(entry["standard_name"], entry["id"], registry)
    assert out["resolution"] == "exact_strain_unreviewed"
    assert clinical_strain_identity_matches(entry["standard_name"], entry)


def test_no_alias_is_shared_between_two_identities():
    import re
    owner = {}
    for entry in _entries():
        for name in [entry["standard_name"], *entry.get("aliases", [])]:
            key = re.sub(r"[^a-z0-9]+", "", name.lower())
            assert owner.setdefault(key, entry["id"]) == entry["id"], (name, owner[key], entry["id"])


def test_guideline_status_vocabulary_is_closed_when_present():
    for entry in _entries():
        if "guideline_status" in entry:
            assert entry["guideline_status"] in GUIDELINE_STATUSES, entry["id"]
