"""One display severity for an over-UL flag: critical at 200%, otherwise warning.

Export projects that word (high / moderate). It does not keep a second copy
of the 200% comparison. 100% confirmed exceedance, the 150% score deduction,
and the gate's 200% signal name stay separate.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from build_final_db import (
    build_top_warnings,
    derive_v4_tradeoffs,
    ul_flag_display_severity,
    ul_flag_warning_severity,
)
from enrich_supplements_v3 import SupplementEnricherV3
from rda_ul_calculator import ul_display_severity
from scoring_v4.dose_safety import _CONFIRMED_UL_EXCEEDANCE_PCT, evaluate_dose_safety
from scoring_v4.gate_safety import evaluate_safety_gate
from scoring_v4.quality_score_config import block as quality_block


@pytest.fixture(scope="module")
def enricher() -> SupplementEnricherV3:
    return SupplementEnricherV3()


def _zinc(mg: float) -> dict:
    return {
        "name": "Zinc",
        "standardName": "Zinc",
        "canonical_id": "zinc",
        "canonical_source_db": "ingredient_quality_map",
        "quantity": mg,
        "unit": "mg",
        "dailyValue": 1818.0,
    }


def _flags(enricher, rows):
    product = {"activeIngredients": rows, "inactiveIngredients": []}
    result = enricher._collect_rda_ul_data(
        product, min_servings_per_day=1, max_servings_per_day=1
    )
    return [
        flag for flag in result["safety_flags"]
        if "zinc" in (flag.get("nutrient") or "").lower()
        or flag.get("canonical_id") == "zinc"
    ]


@pytest.mark.parametrize("pct,word", [(199.9, "warning"), (200, "critical"), (200.0, "critical"), (250, "critical"), (None, "warning"), ("high", "warning")])
def test_display_severity_threshold(pct, word):
    assert ul_display_severity(pct) == word


def test_per_row_flag_uses_the_shared_severity(enricher):
    below = _flags(enricher, [_zinc(79)])
    exact = _flags(enricher, [_zinc(80)])
    above = _flags(enricher, [_zinc(100)])
    assert len(below) == 1 and below[0].get("aggregation") is None
    assert below[0]["pct_ul"] == pytest.approx(197.5)
    assert below[0]["severity"] == "warning"
    assert exact[0]["pct_ul"] == pytest.approx(200)
    assert exact[0]["severity"] == "critical"
    assert above[0]["severity"] == "critical"
    assert above[0]["severity"] == ul_display_severity(above[0]["pct_ul"])


def test_aggregated_same_canonical_flag_uses_the_shared_severity(enricher):
    below = _flags(enricher, [_zinc(39), _zinc(39)])
    exact = _flags(enricher, [_zinc(40), _zinc(40)])
    above = _flags(enricher, [_zinc(50), _zinc(50)])
    for flags, word in ((below, "warning"), (exact, "critical"), (above, "critical")):
        aggregated = [flag for flag in flags if flag.get("aggregation") == "canonical_sum"]
        per_row = [flag for flag in flags if flag.get("aggregation") != "canonical_sum"]
        assert len(aggregated) == 1, flags
        assert per_row == []
        assert aggregated[0]["severity"] == word
        assert aggregated[0]["severity"] == ul_display_severity(aggregated[0]["pct_ul"])
    assert exact[0]["pct_ul"] == pytest.approx(200)


def _project(flag):
    enriched = {"rda_ul_data": {"safety_flags": [flag]}}
    _, penalties = derive_v4_tradeoffs({}, enriched)
    warnings = build_top_warnings(enriched)
    dose = [item for item in warnings if item.get("type") == "dose_safety"]
    b7 = [item for item in penalties if item.get("id") == "B7"]
    return b7, dose


def test_export_corrects_a_stale_stored_severity_from_the_canonical_percentage():
    # A valid-looking but stale word cannot contradict the canonical exposure.
    flag = {
        "nutrient": "Zinc",
        "pct_ul": 250,
        "amount": 100,
        "ul": 40,
        "severity": "warning",
        "ul_gate_eligible": True,
    }
    b7, dose = _project(flag)
    assert b7[0]["severity"] == "critical"
    assert dose[0]["severity"] == "high"
    assert "250% of UL" in dose[0]["title"]

    critical = {**flag, "pct_ul": 200, "severity": "critical"}
    b7, dose = _project(critical)
    assert b7[0]["severity"] == "critical"
    assert dose[0]["severity"] == "high"


def test_missing_or_invalid_severity_uses_the_same_owner():
    missing = {"nutrient": "Zinc", "pct_ul": 250, "ul_gate_eligible": True}
    invalid = {"nutrient": "Zinc", "pct_ul": 199, "severity": "high", "ul_gate_eligible": True}
    assert ul_flag_display_severity(missing) == "critical"
    assert ul_flag_warning_severity(missing) == "high"
    assert ul_flag_display_severity(invalid) == "warning"
    assert ul_flag_warning_severity(invalid) == "moderate"
    b7, dose = _project(missing)
    assert b7[0]["severity"] == "critical"
    assert dose[0]["severity"] == "high"
    b7, dose = _project(invalid)
    assert b7[0]["severity"] == "warning"
    assert dose[0]["severity"] == "moderate"


def test_stored_severity_is_used_only_when_percentage_is_unavailable():
    critical = {"nutrient": "Zinc", "severity": "critical", "ul_gate_eligible": True}
    warning = {"nutrient": "Zinc", "severity": "warning", "ul_gate_eligible": True}
    assert ul_flag_display_severity(critical) == "critical"
    assert ul_flag_warning_severity(critical) == "high"
    assert ul_flag_display_severity(warning) == "warning"
    assert ul_flag_warning_severity(warning) == "moderate"


def test_other_ul_thresholds_are_unchanged():
    assert _CONFIRMED_UL_EXCEEDANCE_PCT == 100.0
    policy = quality_block("dose_safety_policy", "ul_pct_threshold")
    assert policy["ul_pct_threshold"] == 150.0
    scored = evaluate_dose_safety(
        {"rda_ul_data": {"safety_flags": [
            {"nutrient": "Zinc", "pct_ul": 149, "ul_gate_eligible": True},
            {"nutrient": "Zinc", "pct_ul": 150, "ul_gate_eligible": True},
        ]}},
        threshold=policy["ul_pct_threshold"],
        per_flag_penalty=policy["per_flag_penalty"],
        cap=policy["cap"],
    )
    assert [flag.penalized for flag in scored.flags] == [False, True]
    below = evaluate_safety_gate({"rda_ul_data": {"safety_flags": [
        {"nutrient": "Zinc", "pct_ul": 199, "ul_gate_eligible": True},
    ]}})
    twice = evaluate_safety_gate({"rda_ul_data": {"safety_flags": [
        {"nutrient": "Zinc", "pct_ul": 200, "ul_gate_eligible": True},
    ]}})
    assert below.verdict == "CAUTION"
    assert "DOSE_OVER_UL_CAUTION" in below.safety_signals
    assert "DOSE_OVER_UL_CRITICAL" not in below.safety_signals
    assert twice.verdict == "CAUTION"
    assert "DOSE_OVER_UL_CRITICAL" in twice.safety_signals
