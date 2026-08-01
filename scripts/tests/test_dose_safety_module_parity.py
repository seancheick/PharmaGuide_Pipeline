"""One enriched contract must produce one dose-safety answer in every module.

``generic_dose``, ``multi_prenatal_dose`` and ``b_complex`` each read
``rda_ul_data.safety_flags`` and each reached a different conclusion:

  * a flag with a missing ``pct_ul`` was penalized by generic (the P0-2
    fail-safe) and silently skipped by the other two;
  * a folate parent-total plus its own form breakdown was de-duplicated by
    multi/prenatal and charged twice by the other two.

A prenatal and a B-complex containing the identical folate declaration should
not receive different dose penalties because of which rubric happened to score
them. These fixtures pin that parity.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scoring_v4.modules.b_complex import _b7_dose_safety as b_complex_b7
from scoring_v4.modules.generic_dose import _penalty_b7_dose_safety as generic_b7
from scoring_v4.modules.multi_prenatal_dose import _penalty_b7_dose_safety as multi_b7

SCORERS = [
    pytest.param(generic_b7, id="generic"),
    pytest.param(multi_b7, id="multi_or_prenatal"),
    pytest.param(b_complex_b7, id="b_complex"),
]


def _prod(flags):
    return {"rda_ul_data": {"safety_flags": flags}}


_FOLATE_PARENT_PLUS_FORMS = {
    "nutrient": "Folate",
    "canonical_id": "vitamin_b9_folate",
    "pct_ul": 425.0,
    "ul_gate_eligible": True,
    "aggregation": "canonical_sum",
    "contributing_rows": [
        {"ingredient": "Folate", "amount": 1700.0},
        {"ingredient": "L-5-MTHF", "amount": 1000.0},
        {"ingredient": "Folic Acid", "amount": 700.0},
    ],
}


@pytest.mark.parametrize("scorer", SCORERS)
def test_missing_pct_ul_penalizes_in_every_module(scorer):
    """An emitted flag is an over-UL signal. A missing magnitude must never be
    read as "under the limit" by any rubric."""
    assert scorer(_prod([{"nutrient": "Vitamin A"}])) > 0
    assert scorer(_prod([{"nutrient": "Vitamin A", "pct_ul": None}])) > 0


@pytest.mark.parametrize("scorer", SCORERS)
def test_folate_parent_total_plus_forms_is_one_exposure_in_every_module(scorer):
    """A declared total itemised into its own forms is one logical exposure."""
    assert scorer(_prod([_FOLATE_PARENT_PLUS_FORMS])) == 0


@pytest.mark.parametrize("scorer", SCORERS)
def test_confirmed_over_threshold_penalizes_in_every_module(scorer):
    assert scorer(_prod([{"nutrient": "Vitamin A", "pct_ul": 200.0, "ul_gate_eligible": True}])) > 0


@pytest.mark.parametrize("scorer", SCORERS)
def test_below_threshold_never_penalizes(scorer):
    assert scorer(_prod([{"nutrient": "Vitamin A", "pct_ul": 120.0, "ul_gate_eligible": True}])) == 0


@pytest.mark.parametrize("scorer", SCORERS)
def test_no_flags_never_penalizes(scorer):
    assert scorer(_prod([])) == 0


@pytest.mark.parametrize("scorer", SCORERS)
def test_unparseable_magnitude_never_deducts(scorer):
    """A magnitude that cannot be parsed is an engineering defect. It must be
    surfaced rather than converted into a silent dose deduction."""
    assert scorer(_prod([{"nutrient": "Vitamin A", "pct_ul": "n/a"}])) == 0


def test_identical_product_scores_identically_across_all_three_modules():
    product = _prod([
        _FOLATE_PARENT_PLUS_FORMS,
        {"nutrient": "Vitamin A", "pct_ul": 210.0, "ul_gate_eligible": True},
        {"nutrient": "Zinc"},
    ])
    results = {scorer.values[0](product) for scorer in SCORERS}
    assert len(results) == 1, f"modules disagree on one contract: {results}"
