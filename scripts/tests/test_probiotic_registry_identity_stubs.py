"""Registry identities added for label resolution are honest about what they know.

2026-09-13: the registry grew from 49 to 100+ identities so that a printed
strain designation resolves to "exact strain, not yet reviewed" instead of
falling through to species-only. Every such stub must say how the designation
was verified, must carry no clinician sign-off and must never present as
clinician-verified research.

2026-09-22 (closure D1): the stubs were literature-reviewed to a terminal
state. Each identity-verified entry is now in exactly one honest state:
unreviewed (no review, no contexts), reviewed with no qualifying human
evidence (a finished zero), or reviewed with single-strain contexts that own
its evidence. None of them carries a legacy evidence summary.
"""
import json
from pathlib import Path

import pytest

from constants import DATA_DIR
from enrich_supplements_v3 import _probiotic_research_presentation
from probiotic_measurements import (
    derived_context_evidence, effective_strain_evidence, label_strain_identity_resolution,
    strain_literature_review_concluded,
)
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
    assert entry["cfu_thresholds"]["dr_pham_signoff"] is False
    assert entry["cfu_thresholds"]["evidence"] is None
    presented = _probiotic_research_presentation(entry)
    assert presented["review_status"] != "clinician_verified"
    review = entry.get("literature_review")
    if review is None:
        assert entry["evidence_level"] == "unreviewed"
        assert entry["study_contexts"] == [] and entry["key_benefits"] == []
        assert entry["cfu_thresholds"]["tiers_cfu_per_day"] is None
        assert presented["review_status"] == presented["research_match_status"] == "pending_review"
        assert presented["human_evidence"] is False
    elif review["conclusion"] == "no_qualifying_human_evidence":
        assert strain_literature_review_concluded(entry)
        assert entry["evidence_level"] == "none" and entry["key_benefits"] == []
        assert effective_strain_evidence(entry) is None
        assert presented["review_status"] == "literature_reviewed_no_qualifying_evidence"
        assert presented["research_match_status"] == "no_qualifying_human_evidence"
        assert presented["human_evidence"] is False
    else:
        assert review["conclusion"] == "exact_strain_contexts_recorded"
        derived = derived_context_evidence(entry)
        assert derived is not None and effective_strain_evidence(entry) == derived
        assert entry["evidence_level"] == {"strong": "high", "medium": "moderate", "weak": "low"}[
            derived["evidence_strength"]]
        assert presented["review_status"] == "clinician_context_approved"
        assert presented["human_evidence"] is True


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
