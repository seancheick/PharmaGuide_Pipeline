"""Fail-closed policy tests for the v4 penalty registry."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from scoring_v4.modules.generic import (  # noqa: E402
    GenericModuleResult,
    _assemble_score,
    _empty_dimensions,
)
from scoring_v4.penalty_registry import (  # noqa: E402
    apply_penalty_registry,
    mirrored_penalty_magnitude,
)


def _result() -> GenericModuleResult:
    result = GenericModuleResult(dimensions=_empty_dimensions())
    for dimension in result.dimensions.values():
        dimension.score = 10.0
    result.manufacturer_trust.score = 0.0
    result.manufacturer_violations.score = 0.0
    _assemble_score(result)
    return result


def test_unknown_penalty_fails_closed() -> None:
    result = _result()
    result.dimensions["formulation"].penalties["B9_mystery"] = -1.0

    with pytest.raises(RuntimeError, match="unregistered v4 penalty"):
        apply_penalty_registry(result)


def test_omega_lowercase_penalty_alias_normalizes_to_one_schema() -> None:
    result = _result()
    result.dimensions["transparency"].penalties[
        "b6_marketing_claims"
    ] = -5.0

    changed = apply_penalty_registry(result)

    assert changed is False
    assert result.dimensions["transparency"].penalties == {
        "B6_marketing_claims": -5.0
    }


def test_immune_high_zinc_penalty_moves_from_formulation_to_dose() -> None:
    result = _result()
    result.dimensions["formulation"].penalties[
        "B7_immune_high_zinc_daily_use"
    ] = -2.0

    changed = apply_penalty_registry(result)
    if changed:
        _assemble_score(result)

    assert "B7_immune_high_zinc_daily_use" not in (
        result.dimensions["formulation"].penalties
    )
    assert result.dimensions["formulation"].score == 12.0
    assert result.dimensions["dose"].score == 8.0
    assert result.dimensions["dose"].penalties[
        "B7_immune_high_zinc_daily_use"
    ] == -2.0
    assert result.metadata["penalty_relocations"] == [
        {
            "penalty": "B7_immune_high_zinc_daily_use",
            "from": "formulation",
            "to": "dose",
            "magnitude": 2.0,
        }
    ]


def test_consumer_mirror_is_registry_driven_across_dimensions() -> None:
    result = _result()
    result.dimensions["formulation"].penalties["B1_dietary_sugar"] = -2.5
    result.dimensions["dose"].penalties["B7_dose_safety"] = -2.0
    result.dimensions["transparency"].penalties["B6_marketing_claims"] = -5.0
    apply_penalty_registry(result)
    breakdown = result.to_breakdown()

    assert mirrored_penalty_magnitude(
        breakdown, "formula_quality_checks"
    ) == 2.5
    assert mirrored_penalty_magnitude(breakdown, "dose_limit") == 2.0
