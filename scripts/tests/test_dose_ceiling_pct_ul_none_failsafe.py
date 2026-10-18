"""A missing/None ``pct_ul`` must fail clean assessment without false scoring.

The old fallback treated a missing magnitude as under-UL. The typed contract
routes that uncertainty to CAUTION/review and sets no Dose ceiling until an
exceedance is actually established (Dose V4.1 §2.4).
"""

from __future__ import annotations

from scoring_v4.dose_safety import CONFIRMED_OVER_THRESHOLD, MATERIAL_BUT_UNRESOLVED, evaluate_dose_safety


def _result(flags):
    return evaluate_dose_safety({"rda_ul_data": {"safety_flags": flags}})


def test_flag_with_missing_pct_ul_sets_no_unproven_ceiling():
    for flag in ({"nutrient": "X"}, {"nutrient": "X", "pct_ul": None}):
        result = _result([flag])
        assert result.flags[0].state == MATERIAL_BUT_UNRESOLVED
        assert result.dose_ceiling() is None


def test_real_over_ul_flag_sets_a_ceiling():
    assert _result([{"nutrient": "X", "pct_ul": 200, "ul_gate_eligible": True}]).dose_ceiling()["cap_public"] == 0


def test_no_flags_no_ceiling():
    assert _result([]).dose_ceiling() is None


def test_confirmed_over_ul_below_150_is_typed_and_caps_at_10():
    result = _result([{"nutrient": "Zinc", "pct_ul": 125, "ul_gate_eligible": True}])
    assert result.flags[0].state == CONFIRMED_OVER_THRESHOLD
    assert result.dose_ceiling()["cap_public"] == 10
