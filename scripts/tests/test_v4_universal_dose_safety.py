"""Universal typed dose-safety policy and fail-closed scoring contract."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from scoring_v4.dose_safety import (  # noqa: E402
    CONFIRMED_OVER_THRESHOLD,
    MATERIAL_BUT_UNRESOLVED,
    evaluate_dose_safety,
)
from scoring_v4.gate_safety import evaluate_safety_gate  # noqa: E402
from scoring_v4.modules.generic import (  # noqa: E402
    GenericModuleResult,
    _assemble_score,
    _empty_dimensions,
)
from scoring_v4.scored_artifact import build_scored_artifact  # noqa: E402
from score_supplements_v4 import apply_universal_dose_safety  # noqa: E402


def _evaluate(flag: dict):
    return evaluate_dose_safety(
        {"rda_ul_data": {"safety_flags": [flag]}},
        threshold=150.0,
        per_flag_penalty=2.0,
        cap=3.0,
    )


def _module_result(*, dose_score: float = 12.0) -> GenericModuleResult:
    result = GenericModuleResult(dimensions=_empty_dimensions())
    for dimension in result.dimensions.values():
        dimension.score = 0.0
    result.dimensions["dose"].score = dose_score
    result.manufacturer_trust.score = 0.0
    result.manufacturer_violations.score = 0.0
    _assemble_score(result)
    return result


def test_unresolved_material_exposure_is_review_only_not_a_deduction() -> None:
    result = _evaluate(
        {
            "nutrient": "Magnesium Hydroxide",
            "pct_ul": 571.0,
            "ul_gate_eligible": False,
            "ul_gate_ineligible_reason": "compound_mass_not_elemental",
        }
    )

    assert result.penalty == 0.0
    assert result.flags[0].state == MATERIAL_BUT_UNRESOLVED
    assert result.flags[0].penalized is False


def test_safety_gate_consumes_typed_unresolved_state_without_exceedance_copy() -> None:
    product = {
        "rda_ul_data": {
            "safety_flags": [
                {
                    "nutrient": "Magnesium Hydroxide",
                    "pct_ul": 571.0,
                    "ul_gate_eligible": False,
                    "ul_gate_ineligible_reason": "compound_mass_not_elemental",
                }
            ]
        }
    }
    typed = _evaluate(product["rda_ul_data"]["safety_flags"][0])

    gate = evaluate_safety_gate(product, dose_safety=typed)

    assert gate.verdict == "CAUTION"
    assert gate.needs_review is True
    assert "DOSE_SAFETY_UNRESOLVED_REVIEW" in gate.safety_signals
    assert not any(signal.startswith("DOSE_OVER_UL") for signal in gate.safety_signals)


def test_universal_adapter_applies_confirmed_b7_once_to_uncovered_module() -> None:
    typed = _evaluate(
        {
            "nutrient": "Zinc",
            "pct_ul": 200.0,
            "ul_gate_eligible": True,
        }
    )
    module_result = _module_result()

    apply_universal_dose_safety(module_result, typed)

    dose = module_result.dimensions["dose"]
    assert typed.flags[0].state == CONFIRMED_OVER_THRESHOLD
    assert dose.score == 10.0
    assert dose.penalties["B7_dose_safety"] == -2.0
    assert dose.metadata["B7_safety_evaluation"] == typed.audit_metadata()
    assert module_result.raw_score_100 == 10.0


def test_universal_adapter_does_not_double_existing_b7_penalty() -> None:
    typed = _evaluate(
        {
            "nutrient": "Zinc",
            "pct_ul": 200.0,
            "ul_gate_eligible": True,
        }
    )
    module_result = _module_result(dose_score=10.0)
    module_result.dimensions["dose"].penalties["B7_dose_safety"] = -2.0

    apply_universal_dose_safety(module_result, typed)

    assert module_result.dimensions["dose"].score == 10.0
    assert module_result.raw_score_100 == 10.0


@pytest.mark.parametrize("bad_value", [True, -1, "not-a-number", float("nan")])
def test_direct_stage3_entry_point_fails_closed_on_bad_ul_magnitude(
    bad_value: object,
) -> None:
    product = {
        "dsld_id": "bad-b7",
        "rda_ul_data": {
            "safety_flags": [
                {
                    "nutrient": "Zinc",
                    "pct_ul": bad_value,
                    "ul_gate_eligible": True,
                }
            ]
        },
    }

    with pytest.raises(ValueError, match="dose-safety contract"):
        build_scored_artifact(product)
