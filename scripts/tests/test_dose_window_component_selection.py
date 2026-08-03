"""A genuine zero dose-window credit must never be replaced by the fallback.

``generic_dose.score_dose`` selected its window component with

    round(window_credit or no_reference_credit, 4)

Python's ``or`` treats a real, evaluated ``0.0`` as absent. That zero is not
absent — it is the strongest statement the window proxy makes: every nutrient
resolved to at least 150% of its upper limit, or to no adequacy at all. Falling
through to the 16-point "dose disclosed, no reference available" credit would
hand an over-limit product most of the dose window.

The expression is safe today only by coincidence: the no-reference credit is
computed behind a guard that cannot fire when the window did evaluate, so both
sides are zero together. That coincidence is one edit away from becoming an
overdose-credit bug, and nothing currently pins it.

The selection is a decision about which signal applies, so it is tested as one.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scoring_v4.modules.generic_dose import _select_window_component


def test_evaluated_window_is_used_even_when_it_is_zero():
    """The bug this guards: a real 0.0 must not fall through to the fallback."""
    assert _select_window_component(
        window_credit=0.0,
        no_reference_credit=16.0,
        no_rda_reference=False,
    ) == 0.0


def test_evaluated_window_is_used_when_positive():
    assert _select_window_component(
        window_credit=22.0,
        no_reference_credit=16.0,
        no_rda_reference=False,
    ) == 22.0


def test_fallback_is_used_only_when_there_is_no_reference():
    assert _select_window_component(
        window_credit=0.0,
        no_reference_credit=16.0,
        no_rda_reference=True,
    ) == 16.0


def test_no_reference_and_no_fallback_credit_is_zero():
    assert _select_window_component(
        window_credit=0.0,
        no_reference_credit=0.0,
        no_rda_reference=True,
    ) == 0.0
