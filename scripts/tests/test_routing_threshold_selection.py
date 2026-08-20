"""Deterministic, reviewed scalar-threshold selection for routing."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


def test_selector_chooses_first_zero_false_positive_b_boundary() -> None:
    from audits.routing_threshold_selection import select_gte_threshold

    reviewed = [
        {"id": "stress-b", "value": 0.615385, "expected_specialized": True},
        {"id": "b-with-c", "value": 0.625, "expected_specialized": True},
        {"id": "super-b", "value": 0.8, "expected_specialized": True},
        {"id": "partial-b", "value": 0.6, "expected_specialized": False},
        {"id": "broad-multi", "value": 0.571429, "expected_specialized": False},
    ]

    result = select_gte_threshold(reviewed, value_field="value")

    assert result["selected_threshold"] == 0.615385
    assert result["selected_metrics"] == {
        "false_positives": 0,
        "true_positives": 3,
        "false_negatives": 0,
        "true_negatives": 2,
        "recall": 1.0,
        "predicate_count": 1,
        "separation": 0.015385,
    }
    assert [row["threshold"] for row in result["candidates"]] == sorted(
        row["threshold"] for row in result["candidates"]
    )


def test_selector_prefers_zero_false_positives_before_recall() -> None:
    from audits.routing_threshold_selection import select_gte_threshold

    reviewed = [
        {"id": "clean-high", "share": 1.0, "expected_specialized": True},
        {"id": "ambiguous-mid", "share": 0.8, "expected_specialized": True},
        {"id": "contrary-mid", "share": 0.8, "expected_specialized": False},
    ]

    result = select_gte_threshold(reviewed, value_field="share")

    assert result["selected_threshold"] == 1.0
    assert result["selected_metrics"]["false_positives"] == 0
    assert result["selected_metrics"]["true_positives"] == 1


def test_selector_rejects_unreviewed_or_non_numeric_rows() -> None:
    import pytest

    from audits.routing_threshold_selection import ThresholdSelectionError
    from audits.routing_threshold_selection import select_gte_threshold

    with pytest.raises(ThresholdSelectionError, match="expected_specialized"):
        select_gte_threshold([{"id": "missing-review", "value": 1.0}], value_field="value")
    with pytest.raises(ThresholdSelectionError, match="finite numeric"):
        select_gte_threshold(
            [{"id": "bad", "value": "unknown", "expected_specialized": True}],
            value_field="value",
        )
