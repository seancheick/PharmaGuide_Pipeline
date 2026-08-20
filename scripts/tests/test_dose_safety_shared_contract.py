"""One shared dose-safety (B7) evaluator, consumed identically by every module.

The P0-2 fail-safe — "a safety_flag is emitted only for an over-UL row, so a
missing ``pct_ul`` must never read as under-UL" — was implemented in
``generic_dose`` and pinned by ``test_b7_pct_ul_none_failsafe.py``, but it was
never propagated. ``multi_prenatal_dose`` and ``b_complex`` still do
``_as_float(flag.get("pct_ul"), 0.0) or 0.0`` and silently skip the penalty.
The folate parent-total de-duplication has the mirror-image problem: it lives
only in ``multi_prenatal_dose``, so the same logical exposure is charged twice
in ``b_complex`` and ``generic``.

Three modules interpreting one enriched contract three different ways is the
defect. This module pins ONE evaluator that all three consume, and the typed
state contract that keeps "confirmed over the limit" separable from "we could
not resolve the exposure".
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scoring_v4.dose_safety import (
    CONFIRMED_OVER_THRESHOLD,
    CONVERSION_FAILED,
    MATERIAL_BUT_UNRESOLVED,
    NONE,
    NOT_APPLICABLE,
    evaluate_dose_safety,
)

THRESHOLD = 150.0
PER_FLAG = 2.0
CAP = 3.0


def _evaluate(flags):
    return evaluate_dose_safety(
        {"rda_ul_data": {"safety_flags": flags}},
        threshold=THRESHOLD,
        per_flag_penalty=PER_FLAG,
        cap=CAP,
    )


def _states(result):
    return [flag.state for flag in result.flags]


# ── the typed states ──────────────────────────────────────────────────────


def test_no_safety_flags_produces_no_penalty_and_no_flags():
    result = _evaluate([])
    assert result.penalty == 0.0
    assert result.flags == []


def test_flag_over_threshold_is_confirmed_and_penalized():
    result = _evaluate([{"nutrient": "Vitamin A", "pct_ul": 160.0, "ul_gate_eligible": True}])
    assert _states(result) == [CONFIRMED_OVER_THRESHOLD]
    assert result.penalty == PER_FLAG


def test_flag_over_ul_below_penalty_threshold_is_confirmed_and_not_penalized():
    result = _evaluate([{"nutrient": "Vitamin A", "pct_ul": 120.0, "ul_gate_eligible": True}])
    assert _states(result) == [CONFIRMED_OVER_THRESHOLD]
    assert result.flags[0].penalized is False
    assert result.penalty == 0.0


def test_missing_pct_ul_is_unresolved_review_only_not_a_deduction():
    """An incomplete comparison must not read as under-UL or as a confirmed
    exceedance. The gate routes it to review; B7 cannot deduct an unproven fact."""
    result = _evaluate([{"nutrient": "Vitamin A"}])
    assert _states(result) == [MATERIAL_BUT_UNRESOLVED]
    assert result.penalty == 0.0

    explicit_none = _evaluate([{"nutrient": "Vitamin A", "pct_ul": None}])
    assert _states(explicit_none) == [MATERIAL_BUT_UNRESOLVED]
    assert explicit_none.penalty == 0.0


def test_gate_ineligible_flag_is_unresolved_not_confirmed():
    """The enricher marks compound-mass and no-anchor rows ineligible for the
    UL verdict gate. The state routes to review without an over-limit deduction."""
    result = _evaluate([{
        "nutrient": "Vitamin B3 (Niacin)",
        "pct_ul": 2400.0,
        "ul_gate_eligible": False,
        "ul_gate_ineligible_reason": "compound_mass_not_elemental",
    }])
    assert _states(result) == [MATERIAL_BUT_UNRESOLVED]
    assert result.flags[0].reason == "compound_mass_not_elemental"
    assert result.penalty == 0.0


def test_non_numeric_pct_ul_is_a_conversion_failure_and_never_deducts():
    """An unparseable magnitude is an engineering defect, not a dose finding.
    It must be surfaced for the release gate instead of silently deducting."""
    result = _evaluate([{"nutrient": "Vitamin A", "pct_ul": "not-a-number"}])
    assert _states(result) == [CONVERSION_FAILED]
    assert result.penalty == 0.0
    assert result.conversion_failures == 1


def test_non_finite_or_boolean_pct_ul_is_a_conversion_failure():
    """NaN/Infinity and booleans are accepted by ``float()`` but are not
    clinically meaningful percentages. They must fail the same contract as an
    unparseable string rather than becoming confirmed or under-threshold."""
    for raw in (float("nan"), float("inf"), float("-inf"), True, False):
        result = _evaluate([{"nutrient": "Vitamin A", "pct_ul": raw}])
        assert _states(result) == [CONVERSION_FAILED]
        assert result.penalty == 0.0
        assert result.conversion_failures == 1


def test_negative_pct_ul_is_a_conversion_failure():
    result = _evaluate([{"nutrient": "Vitamin A", "pct_ul": -1.0}])

    assert _states(result) == [CONVERSION_FAILED]
    assert result.penalty == 0.0
    assert result.conversion_failures == 1


def test_penalty_is_capped():
    flags = [
        {"nutrient": f"N{i}", "pct_ul": 200.0, "ul_gate_eligible": True}
        for i in range(5)
    ]
    assert _evaluate(flags).penalty == CAP


def test_malformed_flag_entries_are_contained():
    result = _evaluate(["not-a-dict", None, {"nutrient": "A", "pct_ul": 200.0, "ul_gate_eligible": True}])
    assert _states(result) == [CONFIRMED_OVER_THRESHOLD]
    assert result.penalty == PER_FLAG


# ── logical-exposure de-duplication ───────────────────────────────────────

_FOLATE_DUPLICATE = {
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


def test_folate_parent_total_plus_form_breakdown_is_one_exposure():
    """A declared total plus its own disclosed form breakdown is one logical
    exposure, not two. It must not be charged twice."""
    result = _evaluate([_FOLATE_DUPLICATE])
    assert _states(result) == [NOT_APPLICABLE]
    assert result.penalty == 0.0
    assert result.flags[0].reason == "folate_parent_total_plus_form_breakdown_duplicate"


def test_genuinely_distinct_folate_exposures_are_not_collapsed():
    """Rows that do not reconcile to the parent total are separate exposures
    and must still be penalized. Guards against over-de-duplication."""
    distinct = dict(_FOLATE_DUPLICATE)
    distinct["contributing_rows"] = [
        {"ingredient": "Folate", "amount": 400.0},
        {"ingredient": "L-5-MTHF", "amount": 1000.0},
        {"ingredient": "Folic Acid", "amount": 700.0},
    ]
    result = _evaluate([distinct])
    assert _states(result) == [CONFIRMED_OVER_THRESHOLD]
    assert result.penalty == PER_FLAG


def test_parent_row_that_is_not_an_aggregate_is_not_collapsed():
    not_aggregated = dict(_FOLATE_DUPLICATE)
    not_aggregated["aggregation"] = "single_row"
    result = _evaluate([not_aggregated])
    assert _states(result) == [CONFIRMED_OVER_THRESHOLD]
    assert result.penalty == PER_FLAG


def test_non_folate_nutrient_is_not_de_duplicated():
    """De-duplication is scoped to the folate parent/form pattern. Widening it
    to every nutrient is a separate, validated change."""
    other = dict(_FOLATE_DUPLICATE)
    other["nutrient"] = "Vitamin A"
    other["canonical_id"] = "vitamin_a"
    result = _evaluate([other])
    assert _states(result) == [CONFIRMED_OVER_THRESHOLD]
    assert result.penalty == PER_FLAG


def test_ignored_flags_carry_audit_detail():
    result = _evaluate([_FOLATE_DUPLICATE])
    assert result.ignored_flags == [{
        "nutrient": "Folate",
        "canonical_id": "vitamin_b9_folate",
        "pct_ul": 425.0,
        "reason": "folate_parent_total_plus_form_breakdown_duplicate",
    }]


def test_audit_metadata_preserves_unresolved_state_and_reason():
    result = _evaluate([{
        "nutrient": "Vitamin B3 (Niacin)",
        "pct_ul": 2400.0,
        "ul_gate_eligible": False,
        "ul_gate_ineligible_reason": "compound_mass_not_elemental",
    }])

    assert result.audit_metadata() == {
        "state_counts": {MATERIAL_BUT_UNRESOLVED: 1},
        "conversion_failures": 0,
        "flags": [{
            "state": MATERIAL_BUT_UNRESOLVED,
            "nutrient": "Vitamin B3 (Niacin)",
            "canonical_id": None,
            "pct_ul": 2400.0,
            "reason": "compound_mass_not_elemental",
            "penalized": False,
        }],
    }
