"""A missing/None ``pct_ul`` must fail clean assessment without false scoring.

The old fallback treated a missing magnitude as under-UL. The typed contract now
routes that uncertainty to CAUTION/review while withholding the numeric B7
deduction until an exceedance is actually established.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scoring_v4.modules.generic_dose import _penalty_b7_dose_safety


def _prod(flags):
    return {"rda_ul_data": {"safety_flags": flags}}


def test_flag_with_missing_pct_ul_does_not_apply_unproven_penalty():
    assert _penalty_b7_dose_safety(_prod([{"nutrient": "X"}])) == 0
    assert _penalty_b7_dose_safety(_prod([{"nutrient": "X", "pct_ul": None}])) == 0


def test_real_over_ul_flag_penalizes():
    assert _penalty_b7_dose_safety(_prod([
        {"nutrient": "X", "pct_ul": 200, "ul_gate_eligible": True}
    ])) > 0


def test_no_flags_no_penalty():
    assert _penalty_b7_dose_safety(_prod([])) == 0


def test_flag_below_threshold_not_penalized():
    # A real over-UL flag below the 150% B7 threshold is not a B7 penalty
    # (by design) — the fail-safe only applies to missing/None magnitudes.
    assert _penalty_b7_dose_safety(_prod([{"nutrient": "X", "pct_ul": 120}])) == 0
