"""Missing review metadata is uncertainty, not a species-level conclusion."""
from copy import deepcopy

import pytest

import studied_formulas
from enrich_supplements_v3 import _probiotic_research_presentation
from probiotic_measurements import clinical_strain_research_scope
from scoring_v4.modules.probiotic_evidence import score_evidence
from scoring_v4.quality_score import _pillar_evidence
from scoring_v4.quality_score_config import config
from test_probiotic_applicability_rubric import strain_product


@pytest.mark.parametrize("entry", [{}, {"cfu_thresholds": {"evidence": {"type": "clinical_guideline"}}}])
def test_missing_specificity_remains_unresolved(entry):
    assert clinical_strain_research_scope(entry)["evidence_scope"] == "scope_unresolved"


def test_explicit_nonstrain_research_remains_species_general():
    entry = {"cfu_thresholds": {"evidence": {"clinical_validation": {"q1_strain_explicit": "NO"}}}}
    assert clinical_strain_research_scope(entry)["evidence_scope"] == "species_general"


def test_unknown_scope_does_not_display_an_affirmative_species_badge():
    entry = {"cfu_thresholds": {"dr_pham_signoff": True, "evidence": {"type": "clinical_guideline"}}}
    result = _probiotic_research_presentation(entry)
    assert result["review_status"] == "clinician_verified"
    assert result["research_match_status"] == "scope_unresolved"


def test_unknown_scope_preserves_contextual_credit_without_inventing_specificity(monkeypatch):
    registry = deepcopy(studied_formulas._clinical_strain_registry())
    evidence = registry["STRAIN_LGG"]["cfu_thresholds"]["evidence"]
    evidence.pop("clinical_validation", None)
    evidence["type"] = "clinical_guideline"
    monkeypatch.setattr(studied_formulas, "_clinical_strain_registry", lambda: registry)
    product = strain_product(dose=1e10)
    product["probiotic_data"]["clinical_strains"][0].update(
        _probiotic_research_presentation(registry["STRAIN_LGG"]))
    result = score_evidence(product)
    row = result["metadata"]["evidence_assessment"]["strain_assessments"][0]
    assert row["research_accepted"] is True
    assert row["evidence_scope"] == "scope_unresolved"
    assert row["dose_applicable"] is False
    assert result["score"] == 8
    reason = _pillar_evidence(result, 20, "probiotic", config())["reason"]
    assert "specificity" in reason
    assert "incomplete" in reason
    assert "species-level" not in reason


@pytest.mark.parametrize("status", ["pending_review", "rejected", "none"])
def test_unresolved_scope_cannot_bypass_an_explicit_review_hold(status):
    product = strain_product()
    product["probiotic_data"]["clinical_strains"][0]["review_status"] = status
    if status == "none":
        product["probiotic_data"]["clinical_strains"][0]["research_match_status"] = status
    assert score_evidence(product)["score"] == 0


def test_caller_unknown_scope_cannot_downgrade_a_reviewed_scope(monkeypatch):
    registry = deepcopy(studied_formulas._clinical_strain_registry())
    registry["STRAIN_LGG"]["cfu_thresholds"]["evidence"]["clinical_validation"] = {
        "q1_strain_explicit": "YES", "q3_human_clinical": "YES"}
    monkeypatch.setattr(studied_formulas, "_clinical_strain_registry", lambda: registry)
    product = strain_product()
    product["probiotic_data"]["clinical_strains"][0]["research_match_status"] = "scope_unresolved"
    row = studied_formulas.assess_probiotic_evidence(product)["strain_assessments"][0]
    assert row["evidence_scope"] == "strain_specific"
    assert row["research_accepted"] is False
