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


def test_evidence_uses_minimum_directed_exposure_for_full_applicability() -> None:
    from scoring_v4.modules.omega_evidence import score_evidence

    crossing = score_evidence(_product(epa=1200, dha=300, minimum=1, maximum=2))
    exact = score_evidence(_product(epa=1600, dha=400, minimum=1, maximum=1))

    assert crossing["score"] == pytest.approx(15.2)
    assert crossing["metadata"]["per_day_epa_dha_min_mg"] == 1500.0
    assert crossing["metadata"]["per_day_epa_dha_max_mg"] == 3000.0
    assert crossing["metadata"]["applicability_qualified"] is True
    assert exact["score"] == 20.0
    assert exact["metadata"]["evidence_standard"] == "triglyceride_strong"


def test_evidence_keeps_reviewed_weak_record_below_one_gram() -> None:
    from scoring_v4.modules.omega_evidence import score_evidence

    payload = score_evidence(_product(epa=300, dha=200))

    assert payload["score"] == 10.4
    assert payload["metadata"]["evidence_standard"] == "omega_reviewed_weak"
    assert payload["metadata"]["disclosed_epa_dha_clinical_floor_awarded"] is False
    assert payload["metadata"]["applicability_qualified"] is True


def test_evidence_requires_the_reviewed_weak_record_minimum_exposure() -> None:
    from scoring_v4.modules.omega_evidence import score_evidence

    below_reviewed_range = score_evidence(_product(epa=200, dha=175))
    at_reviewed_range = score_evidence(_product(epa=200, dha=176))

    assert below_reviewed_range["score"] == 0.0
    assert below_reviewed_range["metadata"]["evidence_standard"] is None
    assert below_reviewed_range["metadata"]["applicability_qualified"] is False
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


def test_unknown_frequency_records_default_without_inventing_a_range() -> None:
    from scoring_v4.modules.omega_evidence import score_evidence

    product = _product(epa=1600, dha=400)
    product.pop("servingSizes")
    payload = score_evidence(product)

    assert payload["score"] == 20.0
    assert payload["metadata"]["servings_defaulted"] is True
    assert payload["metadata"]["applicability_qualified"] is True


def test_dose_scores_directed_interval_not_midpoint_dose() -> None:
    from scoring_v4.modules.omega_dose import score_dose

    payload = score_dose(_product(epa=900, dha=300, minimum=1, maximum=2))

    assert payload["metadata"]["per_day_min_mg"] == 1200.0
    assert payload["metadata"]["per_day_max_mg"] == 2400.0
    assert payload["metadata"]["interval_crosses_band"] is True
    assert payload["score"] == pytest.approx(18.4)
