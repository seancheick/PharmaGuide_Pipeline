"""Candidate D omega standard: one exposure owner and one form-quality owner."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


def _product(
    *,
    epa: float = 600.0,
    dha: float = 400.0,
    minimum: float = 1.0,
    maximum: float = 1.0,
    name: str = "Omega-3",
) -> dict:
    return {
        "product_name": name,
        "servingSizes": [{
            "minDailyServings": minimum,
            "maxDailyServings": maximum,
        }],
        "ingredient_quality_data": {
            "ingredients_scorable": [
                {
                    "name": "EPA",
                    "canonical_id": "epa",
                    "quantity": epa,
                    "unit": "mg",
                },
                {
                    "name": "DHA",
                    "canonical_id": "dha",
                    "quantity": dha,
                    "unit": "mg",
                },
            ],
        },
    }


def test_evidence_amount_is_owned_only_by_dose() -> None:
    from scoring_v4.modules.omega_evidence import score_evidence

    crossing = score_evidence(_product(epa=1200, dha=300, minimum=1, maximum=2))
    exact = score_evidence(_product(epa=1600, dha=400, minimum=1, maximum=1))

    assert crossing["score"] == pytest.approx(10.4)
    assert crossing["metadata"]["per_day_epa_dha_min_mg"] == 1500.0
    assert crossing["metadata"]["per_day_epa_dha_max_mg"] == 3000.0
    assert crossing["metadata"]["applicability_qualified"] is True
    assert exact["score"] == pytest.approx(10.4)
    assert exact["metadata"]["evidence_standard"] == "omega_reviewed_weak"


def test_evidence_keeps_reviewed_weak_record_below_one_gram() -> None:
    from scoring_v4.modules.omega_evidence import score_evidence

    payload = score_evidence(_product(epa=300, dha=200))

    assert payload["score"] == 10.4
    assert payload["metadata"]["evidence_standard"] == "omega_reviewed_weak"
    assert payload["metadata"]["disclosed_epa_dha_clinical_floor_awarded"] is False
    assert payload["metadata"]["applicability_qualified"] is True
    assert payload["metadata"]["evidence_result_state"] == "evaluated_applicable"


def test_evidence_does_not_use_the_reviewed_trial_amount_as_a_threshold() -> None:
    from scoring_v4.modules.omega_evidence import score_evidence

    below_reviewed_range = score_evidence(_product(epa=200, dha=175))
    at_reviewed_range = score_evidence(_product(epa=200, dha=176))

    assert below_reviewed_range["score"] == 10.4
    assert below_reviewed_range["metadata"]["evidence_standard"] == "omega_reviewed_weak"
    assert below_reviewed_range["metadata"]["applicability_qualified"] is True
    assert at_reviewed_range["score"] == 10.4
    assert at_reviewed_range["metadata"]["evidence_standard"] == "omega_reviewed_weak"


def test_prenatal_intake_authority_is_not_preterm_outcome_credit() -> None:
    from scoring_v4.modules.omega_evidence import score_evidence

    payload = score_evidence(
        _product(epa=0, dha=200, name="Prenatal DHA")
    )

    assert payload["score"] == 11.1
    assert payload["metadata"]["evidence_standard"] == "prenatal_dha_intake_authority"
    assert payload["metadata"]["prenatal_outcome_credit_awarded"] is False
    assert payload["metadata"]["evidence_result_state"] == "evaluated_authority"


def test_explicit_adult_triglyceride_lowering_purpose_owns_strong_evidence() -> None:
    from scoring_v4.modules.omega_evidence import score_evidence

    product = _product(epa=150, dha=100, name="Adult Omega-3 Triglyceride Support")
    product["statements"] = [{
        "type": "Formula re: Contains",
        "notes": "EPA and DHA help lower triglyceride levels.",
    }]
    payload = score_evidence(product)

    assert payload["score"] == 20.0
    assert payload["metadata"]["evidence_standard"] == "triglyceride_strong"


def test_triglyceride_form_wording_is_not_a_lowering_purpose() -> None:
    from scoring_v4.modules.omega_evidence import score_evidence

    payload = score_evidence(
        _product(epa=150, dha=100, name="Natural Triglyceride Form Omega-3")
    )

    assert payload["score"] == 10.4
    assert payload["metadata"]["evidence_standard"] == "omega_reviewed_weak"


@pytest.mark.parametrize("claim", [
    "This product does not lower triglycerides.",
    "This product doesn't lower triglycerides.",
    "No evidence shows that EPA and DHA reduce triglycerides.",
    "Not intended to reduce triglyceride levels.",
    "Triglyceride lowering is not supported by evidence.",
])
def test_negated_triglyceride_claim_does_not_create_strong_evidence(claim: str) -> None:
    from scoring_v4.modules.omega_evidence import score_evidence

    product = _product(epa=150, dha=100, name="Adult Omega-3")
    product["statements"] = [{"notes": claim}]

    payload = score_evidence(product)

    assert payload["score"] == pytest.approx(10.4)
    assert payload["metadata"]["evidence_standard"] == "omega_reviewed_weak"


@pytest.mark.parametrize("name", ["Children's Omega-3", "Baby Omega-3 Drops"])
def test_child_and_baby_products_do_not_borrow_adult_evidence(name: str) -> None:
    from scoring_v4.modules.omega_evidence import score_evidence

    payload = score_evidence(_product(epa=300, dha=200, name=name))

    assert payload["score"] == 0.0
    assert payload["metadata"]["applicability_qualified"] is False
    assert payload["metadata"]["evidence_result_state"] == "applicability_unestablished"


def test_dha_only_non_prenatal_product_does_not_borrow_epa_dha_evidence() -> None:
    from scoring_v4.modules.omega_evidence import score_evidence

    payload = score_evidence(_product(epa=0, dha=500, name="Vegetarian DHA"))

    assert payload["score"] == 0.0
    assert payload["metadata"]["applicability_qualified"] is False
    assert payload["metadata"]["evidence_result_state"] == "identity_material_unresolved"


def test_epa_only_product_does_not_borrow_combined_epa_dha_evidence() -> None:
    from scoring_v4.modules.omega_evidence import score_evidence

    payload = score_evidence(_product(epa=500, dha=0, name="EPA Concentrate"))

    assert payload["score"] == 0.0
    assert payload["metadata"]["applicability_qualified"] is False
    assert payload["metadata"]["evidence_result_state"] == "identity_material_unresolved"


@pytest.mark.parametrize("name", ["Pro-Resolving Mediator Formula", "SPM Active Omega"])
def test_specialized_omega_delivery_does_not_borrow_ordinary_fish_oil_evidence(name: str) -> None:
    from scoring_v4.modules.omega_evidence import score_evidence

    payload = score_evidence(_product(epa=300, dha=200, name=name))

    assert payload["score"] == 0.0
    assert payload["metadata"]["applicability_qualified"] is False
    assert payload["metadata"]["applicability_reason"] == "held_specialized_preparation"
    assert payload["metadata"]["evidence_result_state"] == "applicability_unestablished"


def test_mixed_purpose_product_does_not_borrow_omega_only_evidence() -> None:
    from scoring_v4.modules.omega_evidence import score_evidence

    product = _product(epa=300, dha=200, name="Omega-3 + Lutein Eye Formula")
    product["ingredient_quality_data"]["ingredients_scorable"].append({
        "name": "Lutein",
        "canonical_id": "lutein",
        "quantity": 10,
        "unit": "mg",
    })
    payload = score_evidence(product)

    assert payload["score"] == 0.0
    assert payload["metadata"]["applicability_qualified"] is False
    assert payload["metadata"]["applicability_reason"] == "held_mixed_purpose_ownership"
    assert payload["metadata"]["evidence_result_state"] == "applicability_unestablished"


def test_held_omega_evidence_public_copy_does_not_claim_applicable_research() -> None:
    from scoring_v4.modules.omega_evidence import score_evidence
    from scoring_v4.quality_score import _config, _pillar_evidence

    dimension = score_evidence(_product(epa=500, dha=0, name="EPA Concentrate"))
    pillar = _pillar_evidence(dimension, 20.0, "omega", _config())

    assert pillar["score"] == 0.0
    assert pillar["evidence_result_state"] == "identity_material_unresolved"
    assert pillar["display_state"] == "not_yet_reviewed"
    assert pillar["reason"] == (
        "Active ingredient identity or material form requires further scientific "
        "clarification before evidence can be assessed."
    )
    assert "Limited human evidence" not in pillar["reason"]


def test_unknown_frequency_records_default_without_inventing_a_range() -> None:
    from scoring_v4.modules.omega_evidence import score_evidence

    product = _product(epa=1600, dha=400)
    product.pop("servingSizes")
    payload = score_evidence(product)

    assert payload["score"] == 10.4
    assert payload["metadata"]["servings_defaulted"] is True
    assert payload["metadata"]["applicability_qualified"] is True


def test_dose_scores_minimum_and_retains_directed_interval() -> None:
    from scoring_v4.modules.omega_dose import score_dose

    payload = score_dose(_product(epa=900, dha=300, minimum=1, maximum=2))

    assert payload["metadata"]["per_day_min_mg"] == 1200.0
    assert payload["metadata"]["per_day_max_mg"] == 2400.0
    assert payload["metadata"]["interval_crosses_band"] is True
    assert payload["score"] == pytest.approx(16.8)


def test_omega_registry_keeps_clinical_facts_not_scoring_magnitudes():
    from evidence_resolver import _load_backed_studies
    record = next(r for r in _load_backed_studies() if r["id"] == "INGR_OMEGA3")
    for standard in record["purpose_evidence"]:
        assert "pillar_score" not in standard
        assert "graduated_from_daily_epa_dha_mg" not in standard


def test_omega_points_are_read_from_shared_scoring_config(monkeypatch):
    from copy import deepcopy
    from scoring_v4 import quality_score_config
    from scoring_v4.modules.omega_evidence import score_evidence
    original = quality_score_config.block

    def configured(name, sentinel):
        result = deepcopy(original(name, sentinel))
        if name == "evidence_magnitudes":
            result["omega"].setdefault("purpose_standards", {}).setdefault(
                "omega_reviewed_weak", {})["pillar_score"] = 7.0
        return result

    monkeypatch.setattr(quality_score_config, "block", configured)
    assert score_evidence(_product(epa=300, dha=200))["score"] == 7.0
