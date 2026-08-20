"""Select scalar route thresholds from reviewed, observed corpus boundaries.

This module deliberately does not infer labels.  Callers supply a reviewed
boolean for every row; the selector then applies the routing policy's fixed
lexicographic objective:

1. fewest false-positive specialized routes;
2. highest specialized-route recall;
3. fewest predicates;
4. widest distance from the nearest rejected observed value.
"""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence


class ThresholdSelectionError(ValueError):
    """Reviewed threshold input is incomplete or not reproducible."""


def _reviewed_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    value_field: str,
    expected_field: str,
) -> list[tuple[str, float, bool]]:
    reviewed: list[tuple[str, float, bool]] = []
    for index, row in enumerate(rows):
        row_id = str(row.get("id") or row.get("dsld_id") or index)
        expected = row.get(expected_field)
        if not isinstance(expected, bool):
            raise ThresholdSelectionError(
                f"{row_id}: {expected_field} must be a reviewed boolean"
            )
        try:
            value = float(row.get(value_field))
        except (TypeError, ValueError):
            value = math.nan
        if not math.isfinite(value):
            raise ThresholdSelectionError(
                f"{row_id}: {value_field} must be a finite numeric value"
            )
        reviewed.append((row_id, value, expected))
    if not reviewed:
        raise ThresholdSelectionError("at least one reviewed row is required")
    return reviewed


def _metrics(
    rows: Sequence[tuple[str, float, bool]],
    threshold: float,
    *,
    predicate_count: int,
) -> dict[str, int | float]:
    false_positives = 0
    true_positives = 0
    false_negatives = 0
    true_negatives = 0
    for _, value, expected in rows:
        predicted = value >= threshold
        if predicted and expected:
            true_positives += 1
        elif predicted:
            false_positives += 1
        elif expected:
            false_negatives += 1
        else:
            true_negatives += 1
    positives = true_positives + false_negatives
    lower_values = [value for _, value, _ in rows if value < threshold]
    separation = (
        round(threshold - max(lower_values), 6)
        if lower_values
        else 0.0
    )
    return {
        "false_positives": false_positives,
        "true_positives": true_positives,
        "false_negatives": false_negatives,
        "true_negatives": true_negatives,
        "recall": round(true_positives / positives, 6) if positives else 1.0,
        "predicate_count": predicate_count,
        "separation": separation,
    }


def select_gte_threshold(
    rows: Sequence[Mapping[str, Any]],
    *,
    value_field: str,
    expected_field: str = "expected_specialized",
    predicate_count: int = 1,
) -> dict[str, Any]:
    """Return the selected ``value >= threshold`` observed boundary and audit.

    A boundary just above the largest observation is included so the policy can
    choose no specialized routes when every observed boundary would create a
    false positive.  This makes the zero-false-positive priority explicit rather
    than silently accepting a dirty cutoff.
    """
    if predicate_count < 1:
        raise ThresholdSelectionError("predicate_count must be positive")
    reviewed = _reviewed_rows(
        rows,
        value_field=value_field,
        expected_field=expected_field,
    )
    observed = sorted({value for _, value, _ in reviewed})
    thresholds = [*observed, math.nextafter(observed[-1], math.inf)]
    candidates: list[dict[str, Any]] = []
    for threshold in thresholds:
        metrics = _metrics(
            reviewed,
            threshold,
            predicate_count=predicate_count,
        )
        candidates.append({"threshold": threshold, **metrics})

    selected = min(
        candidates,
        key=lambda row: (
            row["false_positives"],
            -row["recall"],
            row["predicate_count"],
            -row["separation"],
            row["threshold"],
        ),
    )
    selected_metrics = {
        key: selected[key]
        for key in (
            "false_positives",
            "true_positives",
            "false_negatives",
            "true_negatives",
            "recall",
            "predicate_count",
            "separation",
        )
    }
    return {
        "selection_policy": [
            "fewest_false_positive_specialized_routes",
            "highest_recall",
            "fewest_predicates",
            "widest_observed_separation",
        ],
        "value_field": value_field,
        "expected_field": expected_field,
        "reviewed_row_count": len(reviewed),
        "selected_threshold": selected["threshold"],
        "selected_metrics": selected_metrics,
        "candidates": candidates,
    }
