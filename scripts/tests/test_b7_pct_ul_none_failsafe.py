"""
P0-2 — a dose safety_flag with a missing/None ``pct_ul`` must fail SAFE.

``rda_ul_data.safety_flags[]`` are emitted ONLY for over-UL rows. The B7 dose
penalty read ``pct_ul = _as_float(flag.get("pct_ul"), 0.0) or 0.0`` — so a flag
whose ``pct_ul`` is missing/None defaulted to 0.0, fell below the 150% threshold,
and applied NO penalty: "UL unknown" was read as "under UL / safe", the wrong
direction for a clinical product. A present flag is an over-UL signal and must be
penalized even when its magnitude field is absent.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scoring_v4.modules.generic_dose import _penalty_b7_dose_safety


def _prod(flags):
    return {"rda_ul_data": {"safety_flags": flags}}


def test_flag_with_missing_pct_ul_still_penalizes():
    assert _penalty_b7_dose_safety(_prod([{"nutrient": "X"}])) > 0
    assert _penalty_b7_dose_safety(_prod([{"nutrient": "X", "pct_ul": None}])) > 0


def test_real_over_ul_flag_penalizes():
    assert _penalty_b7_dose_safety(_prod([{"nutrient": "X", "pct_ul": 200}])) > 0


def test_no_flags_no_penalty():
    assert _penalty_b7_dose_safety(_prod([])) == 0


def test_flag_below_threshold_not_penalized():
    # A real over-UL flag below the 150% B7 threshold is not a B7 penalty
    # (by design) — the fail-safe only applies to missing/None magnitudes.
    assert _penalty_b7_dose_safety(_prod([{"nutrient": "X", "pct_ul": 120}])) == 0
