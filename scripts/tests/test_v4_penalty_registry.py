"""Fail-closed policy tests for the v4 penalty registry."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from scoring_v4.modules.generic import (  # noqa: E402
    ModuleResult,
    _assemble_score,
    _empty_dimensions,
)
from scoring_v4.penalty_registry import apply_penalty_registry  # noqa: E402


def _result() -> ModuleResult:
    result = ModuleResult(dimensions=_empty_dimensions())
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


@pytest.mark.parametrize("key", ["B0_moderate_watchlist", "B1_dietary_sugar", "B1_harmful_additives"])
def test_formula_check_findings_cannot_reenter_a_dimension(key) -> None:
    """V4.1 Step 4: the formula-checks pillar owns these findings once."""
    result = _result()
    result.dimensions["formulation"].penalties[key] = -2.5

    with pytest.raises(RuntimeError, match="unregistered v4 penalty"):
        apply_penalty_registry(result)
