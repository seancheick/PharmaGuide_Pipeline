"""Signed collagen limitations cannot be replaced by a recovery's old grade."""
import json
from pathlib import Path

import pytest

import clinical_applicability as applicability
from clinical_evidence_schema import validate_ingredient_context
from evidence_resolver import clinical_record_sources_eligible
from scoring_v4.modules import generic_evidence as evidence
from tests.test_v4_generic_evidence_p133 import _ingredient, _product


def _record():
    data = json.loads((Path(__file__).resolve().parents[1] / "data" / "backed_clinical_studies.json").read_text())
    return next(row for row in data["backed_clinical_studies"] if row["id"] == "INGR_COLLAGEN_PEPTIDES")


def _collagen(matches=()):
    row = _ingredient(name="Collagen Peptides", canonical_id="collagen", quantity=20, unit="g")
    row.update(raw_source_path="ingredientRows[0]", collagen_subtype="peptides_i_iii")
    return _product(product_name="Collagen Peptides", ingredients=[row], matches=list(matches))


def test_collagen_recovery_requires_a_qualifying_canonical_source(monkeypatch):
    monkeypatch.setattr(evidence, "_verified_ingredient_human_evidence_entries", lambda: ())
    recovered = evidence._recover_contract_evidence_matches(_collagen(), [], owner_scoped=True)
    assert not any(row["id"] == "RECOVERED_COLLAGEN_PEPTIDES_V1" for row in recovered)


@pytest.mark.parametrize("recovered", [False, True])
def test_current_collagen_hold_wins_over_old_positive_match(monkeypatch, recovered):
    owner = {**_record(), "scoring_eligible": False}
    monkeypatch.setattr(applicability, "reviewed_entries", lambda: {owner["id"]: owner})
    monkeypatch.setattr(evidence, "_verified_ingredient_human_evidence_entries", lambda: ())
    stale = {**owner, "scoring_eligible": True, "effect_direction": "positive_strong"}
    if recovered:
        stale.update(id="RECOVERED_COLLAGEN_PEPTIDES_V1", ingredient="collagen",
                     evidence_origin="scoring_contract_recovery",
                     source_data="backed_clinical_studies:INGR_COLLAGEN_PEPTIDES")
    result = evidence.score_evidence(_collagen([stale]), apply_primary_floor=True, owner_scoped=True)
    assert result["score"] == 0


def test_eligible_recovery_copies_source_facts_instead_of_inventing_a_grade_or_dose(monkeypatch):
    owner = {**_record(), "scoring_eligible": True, "effect_direction": "positive_weak",
             "total_enrollment": 73, "health_goals_supported": ["Skin, Hair & Nails"]}
    monkeypatch.setattr(applicability, "reviewed_entries", lambda: {owner["id"]: owner})
    monkeypatch.setattr(evidence, "_verified_ingredient_human_evidence_entries", lambda: (owner,))
    recovered = evidence._recover_contract_evidence_matches(_collagen(), [], owner_scoped=True)
    row = next(row for row in recovered if row["id"] == "RECOVERED_COLLAGEN_PEPTIDES_V1")
    assert row["effect_direction"] == "positive_weak"
    assert row["total_enrollment"] == 73
    assert "min_clinical_dose" not in row and "max_studied_clinical_dose" not in row
    assert row["matched_source_row_refs"] == ["ingredientRows[0]"]


def test_recovered_receipt_keeps_the_canonical_source_review_owner(monkeypatch):
    from tests.test_v4_generic_evidence_p133 import _use_synthetic_eligible_collagen_source

    owner = _use_synthetic_eligible_collagen_source(monkeypatch)
    owner.update(effect_direction="positive_weak", total_enrollment=73)
    seen = []
    def source_review(entry):
        seen.append(entry["id"])
        return {"is_complete": False, "errors": ["synthetic_unfinished_source_review"], "context_ids": []}
    monkeypatch.setattr(applicability, "assess_clinical_source_review", source_review)
    result = evidence.score_evidence(_collagen(), apply_primary_floor=True, owner_scoped=True)
    assert result["score"] > 0
    [receipt] = result["metadata"]["contributing_record_assessments"]
    assert receipt["id"] == "INGR_COLLAGEN_PEPTIDES"
    assert seen == ["INGR_COLLAGEN_PEPTIDES"]
    assert receipt["source_review"] == source_review(owner)
    # The explicitly approved synthetic endpoint isolates receipt ownership;
    # unfinished source-review metadata is retained rather than manufactured.
    assert receipt["source_review"]["is_complete"] is False


def test_signed_collagen_return_retains_all_sources_without_generic_benefit_credit():
    record = _record()
    assert record.get("scoring_eligible") is False
    assert not clinical_record_sources_eligible(record)
    assert record.get("effect_direction") != "positive_strong"
    assert record.get("primary_outcome") != "Healthy Aging/Longevity"
    assert "Healthy Aging/Longevity" not in record["health_goals_supported"]
    assert not {"cardiovascular", "glycemic_control", "muscle_recovery"} & set(record["endpoint_relevance_tags"])
    assert {ref["pmid"] for ref in record["references_structured"]} == {
        "37432180", "40324552", "37717022", "39839727"
    }
    contexts = record.get("study_contexts", [])
    assert len(contexts) == 4
    assert all(context["scoring_eligible"] is False for context in contexts)
    for context in contexts:
        assert validate_ingredient_context(context) == []
        assert context["clinical_review"]["reviewer"] == "Dr. Pham"
        assert context["clinical_review"]["reviewed_at"] == "2026-10-26"
    formula = next(context for context in contexts if context["source_pmids"] == ["39839727"])
    assert formula["identity_scope"] == "combination"
    assert "calcium ascorbate" in " ".join(formula["limitations"]).lower()
    assert formula["dose"]["values"] == [10000]
    assert formula["dose"]["dose_basis"] == "nominal_assigned_arm"
    assert "collagen component" in formula["dose"]["normalization"]["basis"]
    assert formula["dose"]["duration_days"] is None
    assert formula["dose"]["duration_as_printed"] == {"value": 6, "unit": "months"}
    assert "180" not in formula["dose"]["normalization"]["basis"]
