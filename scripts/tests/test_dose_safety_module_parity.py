"""One enriched contract must produce one dose-safety answer in every module.

``generic_dose``, ``multi_prenatal_dose`` and ``b_complex`` each read
``rda_ul_data.safety_flags`` and each reached a different conclusion:

  * a flag with a missing ``pct_ul`` was historically interpreted differently
    across modules; it is now review-only everywhere;
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

from scoring_v4.dose_safety import evaluate_dose_safety
from scoring_v4.modules.b_complex import _score_dose as score_b_complex_dose
from scoring_v4.modules.generic_dose import score_dose as score_generic_dose
from scoring_v4.modules.multi_prenatal_dose import score_dose as score_multi_dose
from scoring_v4.quality_score_config import block as _cfg_block

_POLICY = _cfg_block("dose_safety_policy", "ul_pct_threshold")


def _live_b7(product):
    # Production evaluates B7 once (score_supplements_v4) and applies it to
    # every module; per-module B7 wrappers no longer exist to disagree.
    return evaluate_dose_safety(
        product,
        threshold=float(_POLICY["ul_pct_threshold"]),
        per_flag_penalty=float(_POLICY["per_flag_penalty"]),
        cap=float(_POLICY["cap"]),
    ).penalty


SCORERS = [pytest.param(_live_b7, id="shared_b7")]


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
def test_missing_pct_ul_is_review_only_in_every_module(scorer):
    """A missing magnitude cannot justify an over-limit deduction."""
    assert scorer(_prod([{"nutrient": "Vitamin A"}])) == 0
    assert scorer(_prod([{"nutrient": "Vitamin A", "pct_ul": None}])) == 0


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


@pytest.mark.parametrize(
    "scorer",
    [
        pytest.param(score_generic_dose, id="generic"),
        pytest.param(score_multi_dose, id="multi_or_prenatal"),
        pytest.param(score_b_complex_dose, id="b_complex"),
    ],
)
def test_unresolved_state_is_emitted_in_every_module_audit_metadata(scorer):
    product = _prod([{
        "nutrient": "Vitamin B3 (Niacin)",
        "pct_ul": 2400.0,
        "ul_gate_eligible": False,
        "ul_gate_ineligible_reason": "compound_mass_not_elemental",
    }])

    metadata = scorer(product)["metadata"]["B7_safety_evaluation"]
    assert metadata["state_counts"] == {"material_but_unresolved": 1}
    assert metadata["flags"][0]["reason"] == "compound_mass_not_elemental"
