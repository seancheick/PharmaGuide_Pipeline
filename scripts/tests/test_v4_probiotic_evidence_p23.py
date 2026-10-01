"""Approved probiotic family certainty, product applicability and confirmation."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))



def _match(
    *,
    id: str = "STRAIN_LGG_EVIDENCE",
    ingredient: str = "Lactobacillus rhamnosus GG",
    standard_name: str = "Lactobacillus rhamnosus GG",
    study_type: str = "clinical_strain",
    evidence_level: str = "strain-clinical",
    effect_direction: str = "positive_strong",
    total_enrollment: int | None = None,
    published_studies_count: int | None = None,
    **extra,
) -> dict:
    row = {
        "id": id,
        "ingredient": ingredient,
        "standard_name": standard_name,
        "study_name": standard_name,
        "study_type": study_type,
        "evidence_level": evidence_level,
        "effect_direction": effect_direction,
    }
    if total_enrollment is not None:
        row["total_enrollment"] = total_enrollment
    if published_studies_count is not None:
        row["published_studies_count"] = published_studies_count
    row.update(extra)
    return row


def _clinical_strain(
    strain: str = "Lactobacillus rhamnosus GG",
    indication: str = "prevention of antibiotic-associated diarrhea",
) -> dict:
    return {
        "strain": strain,
        "clinical_id": {
            "Lactobacillus rhamnosus GG": "STRAIN_LGG",
            "Lactobacillus rhamnosus HN001": "STRAIN_RHAMNOSUS_HN001",
        }[strain],
        "clinical_support_level": "high",
        "indication_primary": indication,
    }


def _product(
    *,
    product_name: str = "Daily Digestive Probiotic",
    brand_name: str = "Example Probiotics",
    matches: list[dict] | None = None,
    clinical_strains: list[dict] | None = None,
) -> dict:
    strains = [_clinical_strain()] if clinical_strains is None else clinical_strains
    return {
        "status": "active",
        "form_factor": "capsule",
        "product_name": product_name,
        "brand_name": brand_name,
        "supplement_type": {"type": "probiotic"},
        "activeIngredients": [{"name": row["strain"], "raw_source_path": f"ingredientRows[{i}]"}
                              for i, row in enumerate(strains)],
        "ingredient_quality_data": {
            "total_active": 1,
            "ingredients_scorable": [
                {
                    "name": "Lactobacillus rhamnosus GG",
                    "standard_name": "Lactobacillus rhamnosus GG",
                    "canonical_id": "lactobacillus_rhamnosus_gg",
                    "mapped": True,
                    "has_dose": True,
                }
            ],
        },
        "evidence_data": {
            "clinical_matches": [_match()] if matches is None else matches,
        },
        "probiotic_data": {
            "is_probiotic": True,
            "is_probiotic_product": True,
            "total_strain_count": 1,
            "clinical_strain_count": 1,
            "clinical_strains": strains,
        },
    }


def _infant_product():
    return _product(product_name="Infant Colic Digestive Probiotic", matches=[],
        clinical_strains=[{"strain": "Bifidobacterium lactis BB-12", "clinical_id": "STRAIN_LACTIS_BB12"}])


def test_undosed_strain_receives_reviewed_family_credit_without_dose_points():
    from scoring_v4.modules.probiotic_evidence import score_evidence
    payload = score_evidence(_product())
    assert payload["max"] == 20
    assert payload["components"] == {"evidence_family_certainty": 6.6667,
        "product_applicability": 3.0, "independent_replication_consistency": 0.0}
    assert payload["score"] == 9.6667
    assert "dose_applicability" not in payload["components"]
    assert payload["metadata"]["claim_alignment"]["level"] == "direct"


def test_native_family_scores_without_generic_matches_for_its_population():
    from scoring_v4.modules.probiotic_evidence import score_evidence
    product = _infant_product()
    product["probiotic_data"]["clinical_strains"][0]["clinical_support_level"] = "invented"
    payload = score_evidence(product)
    assert payload["score"] == 18
    assert payload["components"] == {"evidence_family_certainty": 10.0,
        "product_applicability": 6.0, "independent_replication_consistency": 2.0}
    assert "native_context" in payload["metadata"]["notes"]
    product["product_name"] = "Adult Digestive Probiotic"
    assert score_evidence(product)["score"] == 0


def test_more_strains_do_not_manufacture_independent_confirmation():
    from scoring_v4.modules.probiotic_evidence import score_evidence
    product = _infant_product()
    before = score_evidence(product)
    extra = _clinical_strain(strain="Lactobacillus rhamnosus HN001")
    product["activeIngredients"].append({"name": extra["strain"], "raw_source_path": "ingredientRows[1]"})
    product["probiotic_data"]["clinical_strains"].append(extra)
    after = score_evidence(product)
    assert after["components"] == before["components"]
    assert after["metadata"]["clinical_strain_count"] == 2


def test_generic_strain_matches_require_verified_native_identity():
    from scoring_v4.modules.probiotic_evidence import score_evidence
    payload = score_evidence(_product(clinical_strains=[]))
    assert payload["score"] == 0
    assert payload["components"]["product_applicability"] == 0
    assert payload["metadata"]["uncredited_strain_match_ids"] == ["STRAIN_LGG_EVIDENCE"]


def test_prenatal_positioning_does_not_borrow_infant_or_secondary_mood_efficacy(monkeypatch):
    from copy import deepcopy
    import studied_formulas
    from scoring_v4.modules.probiotic_evidence import score_evidence
    registry = deepcopy(studied_formulas._clinical_strain_registry())
    registry["STRAIN_RHAMNOSUS_HN001"]["cfu_thresholds"]["indication_primary"] = "atopic eczema prevention in infants"
    monkeypatch.setattr(studied_formulas, "_clinical_strain_registry", lambda: registry)
    product = _product(product_name="Once Daily Prenatal", matches=[],
        clinical_strains=[_clinical_strain(strain="Lactobacillus rhamnosus HN001")])
    payload = score_evidence(product)
    assert payload["metadata"]["indication_relevance_level"] == "partial"
    assert "infant" in payload["metadata"]["matched_relevance_categories"]
    assert payload["score"] == 0  # Label/category proximity does not create a primary trial.


def test_generic_positioning_limits_applicability_without_changing_certainty():
    from scoring_v4.modules.probiotic_evidence import score_evidence
    direct = score_evidence(_product())
    broad = score_evidence(_product(product_name="Daily Probiotic 50 Billion"))
    assert broad["components"]["evidence_family_certainty"] == direct["components"]["evidence_family_certainty"]
    assert broad["components"]["product_applicability"] == 1.5
    assert broad["metadata"]["indication_relevance_level"] == "broad"


def test_structured_positioning_changes_applicability_only():
    from scoring_v4.modules.probiotic_evidence import score_evidence
    product = _product(product_name="FloraSport 20B")
    before = score_evidence(product)
    product["statements"] = [{"type": "Formulation re: Other", "notes": "GI Support\nImmune Support"}]
    after = score_evidence(product)
    assert after["metadata"]["product_positioning_categories"] == ["digestive", "immune"]
    assert after["metadata"]["indication_relevance_level"] == "direct"
    assert after["components"]["evidence_family_certainty"] == before["components"]["evidence_family_certainty"]
    assert after["components"]["independent_replication_consistency"] == before["components"]["independent_replication_consistency"]
    assert after["components"]["product_applicability"] == 3


def test_precautions_do_not_create_product_positioning():
    from scoring_v4.modules.probiotic_evidence import score_evidence
    product = _product(product_name="Daily Probiotic")
    before = score_evidence(product)
    product["statements"] = [{"type": "Precautions re: Pregnant or Nursing or Prescription Medications",
                              "notes": "If pregnant, consult your doctor."}]
    after = score_evidence(product)
    assert after["components"] == before["components"]
    assert after["metadata"]["claim_alignment"] == before["metadata"]["claim_alignment"]


def test_unrelated_positioning_receives_no_product_applicability():
    from scoring_v4.modules.probiotic_evidence import score_evidence
    payload = score_evidence(_product(product_name="Women's Vaginal Probiotic"))
    assert payload["metadata"]["indication_relevance_level"] == "none"
    assert payload["components"]["product_applicability"] == 0


@pytest.mark.parametrize("direction,certainty,total", [("negative",0,0), ("null",0,0), ("mixed",4,7)])
def test_independent_record_direction_is_not_replaced_by_strain_support(direction, certainty, total):
    from scoring_v4.modules.probiotic_evidence import score_evidence
    payload = score_evidence(_product(matches=[_match(effect_direction=direction)]))
    assert payload["components"]["evidence_family_certainty"] == certainty
    assert payload["score"] == total
    assert payload["metadata"]["companion_points"] == 0
    if direction == "negative":
        assert payload["metadata"]["evidence_result_state"] == "evaluated_unfavorable"
    if direction == "null":
        assert payload["metadata"]["evidence_result_state"] == "evaluated_null"


def test_score_probiotic_wires_approved_evidence_dimension():
    from scoring_v4.modules.probiotic import score_probiotic
    result = score_probiotic(_infant_product()).to_breakdown()
    assert result["dimensions"]["evidence"]["score"] == 18
    assert result["dimensions"]["evidence"]["metadata"]["phase"] == "P2.3_probiotic_evidence"
    assert result["phase"].startswith("P2.")


def test_final_blob_probiotic_detail_alias_has_the_same_evidence():
    from scoring_v4.modules.probiotic_evidence import score_evidence
    product = _product()
    before = score_evidence(product)
    product["probiotic_detail"] = product.pop("probiotic_data")
    assert score_evidence(product)["components"] == before["components"]


def test_probiotic_evidence_malformed_input_fails_closed():
    from scoring_v4.modules.probiotic_evidence import score_evidence
    for product in (None, {}, {"evidence_data": None,"probiotic_data": None},42,"oops"):
        payload = score_evidence(product)
        assert payload["score"] == 0
        assert payload["max"] == 20
        assert all(value == 0 for value in payload["components"].values())


def test_reviewed_generic_null_is_a_result_not_an_applicability_gap():
    from scoring_v4.modules.probiotic_evidence import score_evidence
    product = _product(matches=[_match(study_type='rct_single',
                        evidence_level='ingredient-human', effect_direction='null')],
                       clinical_strains=[])
    payload = score_evidence(product)
    assert payload['score'] == 0
    assert payload['metadata']['evidence_result_state'] == 'evaluated_null'


def test_inactivated_bb12_cannot_inherit_live_strain_research():
    from studied_formulas import _clinical_strain_registry
    from scoring_v4.modules.probiotic_evidence import score_evidence
    ref = _clinical_strain_registry()['STRAIN_LACTIS_BB12']
    product = {'product_name': 'Infant Probiotic Colic Digestive', 'form_factor': 'capsule',
               'activeIngredients': [{'name': ref['standard_name'], 'raw_source_path': 'ingredientRows[0]'}],
               'evidence_data': {'clinical_matches': []},
               'probiotic_data': {'clinical_strains': [{'strain': ref['standard_name'],
                    'clinical_id': ref['id'], 'source_row_ref': 'ingredientRows[0]'}]}}
    assert score_evidence(product)['score'] == 18
    product['probiotic_data']['clinical_strains'][0]['is_inactivated'] = True
    assert score_evidence(product)['score'] == 0


def test_evidence_match_join_does_not_reject_an_amount_only_mismatch():
    from studied_formulas import strain_assessments_for_match
    assessment = {"strain_assessments": [{
        "clinical_id": "STRAIN_LGG", "research_accepted": True,
        "status": "strain_dose_incompatible",
    }]}
    assert strain_assessments_for_match({"id": "STRAIN_LGG"}, assessment)
    assessment["strain_assessments"][0]["status"] = "strain_context_mismatch"
    assert not strain_assessments_for_match({"id": "STRAIN_LGG"}, assessment)


from scoring_v4.modules import probiotic_evidence

def _consistency_context(family: str, direction: str = "positive", design: str = "rct"):
    return ("STRAIN_TEST", {
        "condition": "digestive_condition", "trial_family": family,
        "study_design": design,
        "outcomes": [{"hierarchy": "primary", "kind": "patient_important",
                      "direction": direction}],
    })

def test_graded_consistency_requires_exceptional_replication_for_full_credit():
    two = probiotic_evidence._consistency_from_contexts([
        _consistency_context("trial_a"), _consistency_context("trial_b"),
    ])
    three = probiotic_evidence._consistency_from_contexts([
        _consistency_context("trial_a"), _consistency_context("trial_b"),
        _consistency_context("trial_c"),
    ])
    assert two["credit"] == 0.5
    assert three["credit"] == 1.0

@pytest.mark.parametrize("direction", ["null", "negative", "mixed"])
def test_material_conflict_suppresses_consistency_credit(direction):
    result = probiotic_evidence._consistency_from_contexts([
        _consistency_context("positive_a"), _consistency_context("positive_b"),
        _consistency_context("conflict", direction),
    ])
    assert result["credit"] == 0.0
    assert result["has_material_conflict"] is True

def test_null_family_without_positive_same_condition_is_not_material_conflict():
    result = probiotic_evidence._consistency_from_contexts([
        _consistency_context("null_only", "null"),
    ])

    assert result["credit"] == 0.0
    assert result["has_material_conflict"] is False

def test_null_family_for_different_condition_does_not_conflict_with_positive_family():
    positive = _consistency_context("positive", "positive")
    null = _consistency_context("null", "null")
    null[1]["condition"] = "different_condition"
    result = probiotic_evidence._consistency_from_contexts([positive, null])

    assert result["credit"] == 0.0
    assert result["has_material_conflict"] is False

def test_pooled_family_does_not_stack_with_constituent_trials():
    result = probiotic_evidence._consistency_from_contexts([
        _consistency_context("trial_a"), _consistency_context("trial_b"),
        _consistency_context("pooled", design="meta_analysis"),
    ])
    assert result["credit"] == 0.0
    assert result["conditions"][0]["pooled_family_ids"] == ["pooled"]

@pytest.mark.parametrize("study_type,native_design", [
    ("rct_single", "rct"), ("rct_multiple", "rct"),
    ("systematic_review_meta", "meta_analysis"),
    ("observational", "observational"),
])
@pytest.mark.parametrize("level", ["product-human", "ingredient-human", "branded-rct", "strain-clinical"])
def test_equivalent_family_design_has_source_path_parity(study_type, native_design, level):
    entry = {"study_type": study_type, "evidence_level": level,
             "effect_direction": "positive_strong"}
    context = {"study_design": native_design,
               "outcomes": [{"hierarchy": "primary", "kind": "patient_important",
                             "direction": "positive"}]}
    assert probiotic_evidence._single_generic_family_certainty(entry) == (
        probiotic_evidence._single_native_family_certainty(context, probiotic_evidence._EM)
    )

@pytest.mark.parametrize("effect", ["positive_strong", "positive_weak", "mixed", "null", "negative"])
def test_explicit_effect_facts_use_same_family_scale(effect):
    generic = {"study_type": "rct_single", "evidence_level": "product-human",
               "effect_direction": effect}
    native = {"study_design": "rct", "effect_direction": effect,
              "outcomes": [{"hierarchy": "primary", "kind": "patient_important",
                            "direction": "positive"}]}
    assert probiotic_evidence._single_generic_family_certainty(generic) == (
        probiotic_evidence._single_native_family_certainty(native, probiotic_evidence._EM)
    )

def test_unknown_design_is_not_promoted_to_randomized_evidence():
    clinical = {"study_type": "clinical_strain", "evidence_level": "strain-clinical",
                "effect_direction": "positive_strong"}
    assert probiotic_evidence._single_generic_family_certainty(clinical) < 1.0
    assert probiotic_evidence._single_generic_family_certainty({**clinical, "study_type": "unknown"}) == 0
    assert probiotic_evidence._single_generic_family_certainty({**clinical, "evidence_level": "preclinical"}) == 0

@pytest.mark.parametrize("other_direction", ["null", "negative", "mixed"])
def test_same_family_mixed_primary_outcomes_have_source_parity(other_direction):
    generic = {"study_type": "rct_single", "evidence_level": "product-human",
               "effect_direction": "mixed"}
    native = {"study_design": "rct", "outcomes": [
        {"hierarchy": "primary", "kind": "patient_important", "direction": "positive"},
        {"hierarchy": "primary", "kind": "patient_important", "direction": other_direction},
    ]}
    assert probiotic_evidence._single_native_family_certainty(native, probiotic_evidence._EM) == (
        probiotic_evidence._single_generic_family_certainty(generic)
    )


def test_native_evidence_state_is_independent_of_owned_label_amount():
    from test_probiotic_applicability_rubric import strain_product
    results = [probiotic_evidence.score_evidence(strain_product(dose=amount))
               for amount in (None, 1e6, 1e9, 1e10, 1e12)]
    assert all(result["components"] == results[0]["components"] for result in results)
    assert all(result["metadata"]["evidence_result_state"] == results[0]["metadata"]["evidence_result_state"]
               for result in results)
