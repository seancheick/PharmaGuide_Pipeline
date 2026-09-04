"""Each curation correction pins what its live source actually establishes."""
import json
from pathlib import Path

import pytest

from db_integrity_sanity_check import check_clinically_relevant_strains
from probiotic_measurements import clinical_strain_research_scope


def entries():
    path = Path(__file__).resolve().parents[1] / "data/clinically_relevant_strains.json"
    return {e["id"]: e for e in json.loads(path.read_text())["clinically_relevant_strains"]}


def test_lgg_primary_source_specificity_is_not_lost():
    entry = entries()["STRAIN_LGG"]
    assert entry["cfu_thresholds"]["evidence"]["pmid"] == "26756877"
    assert clinical_strain_research_scope(entry) == {
        "evidence_scope": "strain_specific", "human_evidence": True}
    assert "applicability" not in entry  # pediatric AAD != adult general-use dose


def test_lgg_secondary_review_is_not_rendered_as_proven_benefit():
    entry = entries()["STRAIN_LGG"]
    secondary = entry["cfu_thresholds"]["secondary_indications"][0]
    assert secondary["pmid"] == "33295643"
    assert secondary["effect_direction"] == "uncertain"
    assert "duration reduction" not in secondary["name"]
    assert "1000" not in entry["notable_studies"]
    assert entry["evidence_review"]["search_coverage"] == "partial"
    assert entry["evidence_review"]["clinical_signoff_changed"] is False


def test_bb12_unverified_source_is_held_without_an_unapproved_pmid_swap():
    entry = entries()["STRAIN_LACTIS_BB12"]
    thresholds = entry["cfu_thresholds"]
    assert thresholds["evidence"]["pmid"] is None
    assert "38271203" not in json.dumps(entry)
    assert thresholds["dr_pham_signoff"] is False
    assert thresholds["evidence"]["type"] == "unverified_reference"
    assert entry["evidence_level"] == "unreviewed"
    assert entry["key_benefits"] == []
    assert "applicability" not in entry  # two tested doses are not a continuous range


def test_bi07_cannot_use_a_different_species_laboratory_paper():
    entry = entries()["STRAIN_LACTIS_BI07"]
    thresholds = entry["cfu_thresholds"]
    assert thresholds["dr_pham_signoff"] is False
    assert thresholds["evidence"]["pmid"] is None
    assert "17408927" not in json.dumps(entry)
    assert thresholds["evidence"]["clinical_validation"]["q3_human_clinical"] == "NO"
    assert entry["evidence_level"] == "unreviewed"
    assert entry["key_benefits"] == []
    assert clinical_strain_research_scope(entry)["evidence_scope"] == "scope_unresolved"


def test_hn019_rct_quality_is_not_a_positive_effect_direction():
    entry = entries()["STRAIN_LACTIS_HN019"]
    evidence = entry["cfu_thresholds"]["evidence"]
    assert evidence["pmid"] == "39356506"
    assert evidence["effect_direction"] == "null"
    assert "primary" in evidence["interpretation"]
    assert "10–20B" not in entry["cfu_thresholds"]["notes"]
    secondary = entry["cfu_thresholds"]["secondary_indications"][0]
    assert secondary["effect_direction"] == "null"
    assert "reduction" not in secondary["name"]


def test_unreviewed_strain_evidence_is_not_forced_into_low_strength():
    findings = []
    check_clinically_relevant_strains(findings, {
        "clinically_relevant_strains": [entries()["STRAIN_LACTIS_BB12"]],
    }, "clinically_relevant_strains.json")
    assert findings == []


@pytest.mark.parametrize("identity", ["STRAIN_LACTIS_BB12", "STRAIN_LACTIS_BI07"])
def test_unreviewed_support_does_not_fall_back_to_weak(identity):
    from enrich_supplements_v3 import _derive_clinical_support_level

    assert _derive_clinical_support_level(entries()[identity]) is None


@pytest.mark.parametrize("mutation", ["approved", "benefits"])
def test_unreviewed_strain_cannot_claim_approved_benefits(mutation):
    entry = entries()["STRAIN_LACTIS_BB12"]
    if mutation == "approved":
        entry["cfu_thresholds"]["dr_pham_signoff"] = True
    else:
        entry["key_benefits"] = ["Unreviewed benefit claim"]
    findings = []
    check_clinically_relevant_strains(findings, {
        "clinically_relevant_strains": [entry],
    }, "clinically_relevant_strains.json")
    assert any(f.severity == "error" and f.issue == "unreviewed_evidence_claim" for f in findings)
