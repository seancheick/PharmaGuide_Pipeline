"""Integrity holds must survive both evidence resolution and public scoring."""
import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import evidence_resolver as er
from scoring_v4.modules.generic_evidence import score_evidence
from scoring_v4.scored_artifact import build_scored_artifact


def _entry(refs, **extra):
    return {"id": "INGR_AUDIT_MATERIAL", "standard_name": "Audit Material",
            "study_type": "rct_single", "evidence_level": "ingredient-human",
            "effect_direction": "positive_strong", "total_enrollment": 100,
            "references_structured": refs, **extra}


def _product(entry):
    rows = [{"name": "Audit Material", "standard_name": "Audit Material",
             "canonical_id": "audit_material", "mapped": True, "quantity": 100,
             "unit": "mg", "bio_score": 10}]
    return {"status": "active", "form_factor": "capsule",
            "supplement_type": {"type": "single_nutrient"},
            "ingredient_quality_data": {"ingredients": rows, "ingredients_scorable": rows},
            "evidence_data": {"clinical_matches": [entry]}}


@pytest.mark.parametrize("ref", [
    {"pmid": "41573009", "retracted": True},
    {"pmid": "41573009", "expression_of_concern": True},
    {"pmid": "41573009", "scoring_eligible": False},
])
def test_held_source_cannot_award_raw_points_or_public_primary_floor(ref):
    entry = _entry([ref])
    assert score_evidence(_product(entry), apply_primary_floor=True)["score"] == 0
    assert build_scored_artifact(_product(entry))["quality_pillars_v4"]["evidence"]["score"] == 0
    control = _product(_entry([{"pmid": "28661438", "retracted": False}]))
    assert score_evidence(control, apply_primary_floor=True)["score"] > 0


def test_mixed_record_retains_independently_eligible_source():
    entry = _entry([{"pmid": "41573009", "retracted": True},
                    {"pmid": "28661438", "retracted": False}])
    assert score_evidence(_product(entry), apply_primary_floor=True)["score"] > 0


@pytest.mark.parametrize("entry", [
    _entry([{"pmid": "41573009", "retracted": True}]),
    _entry([{"pmid": "28661438"}], study_type="reference"),
    _entry([{"pmid": "28661438"}], scoring_eligible=False),
])
def test_no_eligible_backed_record_does_not_resolve_as_reviewed_benefit(monkeypatch, entry):
    monkeypatch.setattr(er, "_backed_studies_index", lambda: {"audit_material": [copy.deepcopy(entry)]})
    result = er.resolve_evidence_for_canonical("audit_material", name="Audit Material")
    assert result.points_eligible is False
    assert result.applicability_status != "applicable_reviewed_trials"
