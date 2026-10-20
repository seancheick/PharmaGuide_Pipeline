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



def test_undecylenic_reference_cannot_resolve_oral_human_efficacy():
    import json
    from clinical_applicability import assess_clinical_applicability
    from scoring_v4.modules.generic_evidence import _is_verified_ingredient_human_entry
    data = json.loads((Path(__file__).resolve().parents[1] / "data" / "backed_clinical_studies.json").read_text())
    entry = next(r for r in data["backed_clinical_studies"] if r["id"] == "ING_UNDECYLENIC_ACID")
    assert entry["study_type"] == "reference"
    assert entry["evidence_level"] == "reference"
    assert entry["effect_direction"] == "positive_strong"  # descriptive preclinical effect retained
    assert entry["total_enrollment"] is None
    assert entry["registry_completed_trials_count"] is None
    assert entry["endpoint_relevance_tags"] == []
    assert entry["published_studies"] == ["10991877"]
    assert not er.clinical_record_sources_eligible(entry)
    assert not _is_verified_ingredient_human_entry(entry)
    resolution = er.resolve_evidence_for_canonical("undecylenic_acid", name="Undecylenic Acid")
    assert resolution.points_eligible is False
    assert resolution.blocking_reasons == ["clinical_sources_ineligible"]
    row = {"name": "Undecylenic Acid", "canonical_id": "undecylenic_acid", "quantity": 250, "unit": "mg", "raw_source_path": "ingredientRows[0]"}
    product = {"form_factor_canonical": "capsule", "activeIngredients": [row], "ingredient_quality_data": {"ingredients": [row], "ingredients_scorable": [row]}}
    stale = {**entry, "evidence_level": "ingredient-human", "total_enrollment": 20, "registry_completed_trials_count": 7}
    assert assess_clinical_applicability(product, stale, assess_amount=False)["reason_code"] == "reference_only_clinical_record"


@pytest.mark.parametrize("metadata", [
    {"evidence_level": "preclinical", "study_type": "animal_study"},
    {"evidence_level": "product-human", "study_type": "in_vitro"},
])
def test_brand_identifier_never_overrides_explicit_nonhuman_sources(metadata):
    from scoring_v4.modules.generic_evidence import _is_verified_product_level_entry
    entry = _entry([{"pmid": "22556508"}], id="BRAND_AUDIT_MATERIAL", **metadata)
    assert not _is_verified_product_level_entry(entry)
    control = _entry([{"pmid": "28661438"}], id="BRAND_AUDIT_MATERIAL", evidence_level="product-human")
    assert _is_verified_product_level_entry(control)


def test_backed_records_do_not_transfer_generic_or_combination_or_protocol_results():
    import json
    data = json.loads((Path(__file__).resolve().parents[1] / "data" / "backed_clinical_studies.json").read_text())
    records = {r["id"]: r for r in data["backed_clinical_studies"]}
    for key in ["BRAND_ZYLOFRESH", "PRECLIN_AKG", "PRECLIN_APIGENIN", "PRECLIN_LUTEOLIN"]:
        entry = records[key]
        assert entry["evidence_level"] == "reference"
        assert entry["total_enrollment"] is None
        assert entry["effect_direction"] == "positive_weak"
        assert not er.clinical_record_sources_eligible(entry)
    assert records["BRAND_ZYLOFRESH"]["study_type"] == "reference"
    assert records["PRECLIN_AKG"]["study_type"] == "reference"
    assert records["PRECLIN_APIGENIN"]["published_studies"] == ["19593179"]
    assert records["PRECLIN_LUTEOLIN"]["published_studies"] == ["35450527"]
    fisetin = records["PRECLIN_FISETIN"]
    assert fisetin["study_type"] == "observational"
    assert fisetin["total_enrollment"] == 10
    assert fisetin["registry_completed_trials_count"] is None
    assert fisetin["effect_direction"] == "mixed"
    assert fisetin["published_studies"] == ["39269340"]
    assert "uncontrolled" in fisetin["notable_studies"]


@pytest.mark.parametrize("key,expected", [
    ("BRAND_ZYLOFRESH", ["Rabbit lipid outcomes with generic Medicago sativa seed extract"]),
    ("PRECLIN_AKG", ["Protocol and recruitment feasibility; efficacy outcomes not reported"]),
    ("PRECLIN_APIGENIN", ["Generalized anxiety symptoms with chamomile extract"]),
    ("PRECLIN_LUTEOLIN", ["Olfactory function with PEA-luteolin plus olfactory training"]),
])
def test_reference_endpoints_describe_the_cited_intervention(key, expected):
    import json
    data = json.loads((Path(__file__).resolve().parents[1] / "data" / "backed_clinical_studies.json").read_text())
    entry = next(r for r in data["backed_clinical_studies"] if r["id"] == key)
    assert entry["key_endpoints"] == expected
