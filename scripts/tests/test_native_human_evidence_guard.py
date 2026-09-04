"""Native support labels cannot substitute for reviewed human evidence."""

from copy import deepcopy

import pytest

import studied_formulas
from clinical_applicability import reviewed_entries
from scoring_v4.modules.generic_evidence import score_evidence as score_generic_evidence
from scoring_v4.modules.probiotic_evidence import score_evidence
from scoring_v4.quality_score import _pillar_evidence
from scoring_v4.quality_score_config import config
from test_probiotic_applicability_rubric import strain_product


@pytest.mark.parametrize("clinical_id,name,pmid", [
    ("STRAIN_ACIDOPHILUS_NCFM", "Lactobacillus acidophilus NCFM", "24717228"),
    ("STRAIN_LACTIS_BL04", "Bifidobacterium lactis Bl-04", "38665561"),
])
def test_nonhuman_native_reference_does_not_earn_human_clinical_credit(clinical_id, name, pmid):
    result = score_evidence(strain_product(clinical_id=clinical_id, name=name))
    metadata = result["metadata"]
    assessment = metadata["evidence_assessment"]["strain_assessments"][0]
    assert assessment["research_accepted"] is True  # Identity/review is a separate decision.
    assert assessment["human_evidence"] is False
    assert pmid in assessment["source_pmids"]
    assert metadata["generic_evidence_score"] == 0
    assert result["score"] == 0
    assert metadata["native_clinical_strain_evidence_rows"] == []
    # The historical anchor is nonhuman, but newly verified human contexts
    # exist and await clinical review; zero credit is not absence of research.
    assert metadata["evidence_result_state"] == "native_research_review_incomplete"
    uncredited = metadata["uncredited_native_strain_evidence_rows"]
    assert len(uncredited) == 1
    assert uncredited[0]["clinical_id"] == clinical_id
    assert uncredited[0]["source_pmids"] == assessment["scoring_source_pmids"]
    assert uncredited[0]["reason_code"] == "human_clinical_evidence_unestablished"


def test_native_nonhuman_reference_cannot_supply_dose_applicability_points(monkeypatch):
    registry = deepcopy(studied_formulas._clinical_strain_registry())
    # A synthetic scope contract proves that dose compatibility cannot override
    # the source's existing nonhuman classification. This is not a data correction.
    registry["STRAIN_ACIDOPHILUS_NCFM"]["applicability"] = {
        "dose_unit": "CFU", "minimum_daily_dose": 1e9, "maximum_daily_dose": 2e10,
        "dosage_forms": ["capsule"], "target_population": "adult",
        "studied_population": "Synthetic adult test population",
        "supported_outcomes": ["digestive"], "source_pmids": ["24717228"],
    }
    monkeypatch.setattr(studied_formulas, "_clinical_strain_registry", lambda: registry)
    result = score_evidence(strain_product(
        dose=1e10, clinical_id="STRAIN_ACIDOPHILUS_NCFM", name="Lactobacillus acidophilus NCFM"))
    assessment = result["metadata"]["evidence_assessment"]["strain_assessments"][0]
    assert assessment["dose_applicable"] is False
    assert assessment["human_evidence"] is False
    assert result["components"] == {"strain_clinical_evidence": 0, "dose_applicability": 0}


@pytest.mark.parametrize("native_source", ["nonhuman", "unreviewed"])
def test_native_source_gap_does_not_silence_independent_backbone_match(monkeypatch, native_source):
    registry = deepcopy(studied_formulas._clinical_strain_registry())
    # Change only the native source fixture. The existing backbone match stays
    # independent and is evaluated through the actual production match boundary.
    registry["STRAIN_LGG"]["cfu_thresholds"]["evidence"] = (
        {"type": "animal_model", "clinical_validation": {
            "q1_strain_explicit": "YES", "q3_human_clinical": "NO"}}
        if native_source == "nonhuman" else {"type": "unreviewed_reference"}
    )
    monkeypatch.setattr(studied_formulas, "_clinical_strain_registry", lambda: registry)
    product = strain_product()
    product["evidence_data"] = {"clinical_matches": [deepcopy(reviewed_entries()["STRAIN_LGG"])]}
    generic_score = score_generic_evidence(product)["score"]
    assert generic_score > 0
    result = score_evidence(product)
    assert result["metadata"]["evidence_assessment"]["strain_assessments"][0]["human_evidence"] is False
    assert result["metadata"]["uncredited_strain_match_ids"] == []
    assert result["metadata"]["native_clinical_strain_evidence_score"] == 0
    assert result["score"] == generic_score


@pytest.mark.parametrize("effect", ["positive_weak", "mixed", "null", "negative"])
def test_nonhuman_native_fallback_cannot_overrule_independent_match_effect(effect):
    # Synthetic accepted matches exercise direction without creating new sources.
    from test_v4_probiotic_evidence_p23 import _match

    product = strain_product(clinical_id="STRAIN_ACIDOPHILUS_NCFM",
                             name="Lactobacillus acidophilus NCFM")
    product["evidence_data"] = {"clinical_matches": [_match(
        id="STRAIN_ACIDOPHILUS_NCFM", ingredient="Lactobacillus acidophilus NCFM",
        standard_name="Lactobacillus acidophilus NCFM", effect_direction=effect)]}
    result = score_evidence(product)
    assert result["metadata"]["native_clinical_strain_evidence_score"] == 0
    assert result["score"] == score_generic_evidence(product)["score"]
    if effect == "negative":
        assert result["metadata"]["evidence_result_state"] == "evaluated_unfavorable"


@pytest.mark.parametrize("direction,multiplier", [("null", .25), ("mixed", .6), ("negative", 0)])
def test_native_primary_effect_direction_is_not_defaulted_to_positive(monkeypatch, direction, multiplier):
    registry = deepcopy(studied_formulas._clinical_strain_registry())
    registry["STRAIN_LGG"]["cfu_thresholds"]["evidence"]["effect_direction"] = direction
    monkeypatch.setattr(studied_formulas, "_clinical_strain_registry", lambda: registry)
    result = score_evidence(strain_product())
    assert result["score"] == 8 * multiplier
    assert result["metadata"]["native_clinical_strain_evidence_rows"][0]["effect_direction"] == direction
    if direction == "negative":
        assert result["metadata"]["evidence_result_state"] == "evaluated_unfavorable"


def test_nonhuman_zero_is_not_presented_as_evidence_of_no_benefit():
    result = score_evidence(strain_product(clinical_id="STRAIN_ACIDOPHILUS_NCFM",
                                          name="Lactobacillus acidophilus NCFM"))
    reason = _pillar_evidence(result, 20, "probiotic", config())["reason"]
    assert "human clinical" in reason
    assert "incomplete" in reason


@pytest.mark.parametrize("clinical_id,name", [
    ("STRAIN_LACTIS_BB12", "Bifidobacterium lactis BB-12"),
    ("STRAIN_LACTIS_BI07", "Bifidobacterium lactis Bi-07"),
])
def test_native_source_hold_is_a_review_gap_not_a_negative_result(clinical_id, name):
    result = score_evidence(strain_product(clinical_id=clinical_id, name=name))
    assert result["score"] == 0
    assert result["metadata"]["evidence_result_state"] == "native_research_review_incomplete"
    reason = _pillar_evidence(result, 20, "probiotic", config())["reason"]
    assert "review is incomplete" in reason
    assert "no conclusion" in reason
