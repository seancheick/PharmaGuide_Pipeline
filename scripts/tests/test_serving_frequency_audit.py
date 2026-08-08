"""Contracts for the keyed serving-frequency before/after audit."""

from __future__ import annotations

import sys
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from audits.serving_frequency_audit import _threshold_key  # noqa: E402


THRESHOLD = {
    "basis": "per_day",
    "comparator": ">",
    "threshold_value": 200.0,
    "threshold_unit": "mg",
}


def test_threshold_key_distinguishes_separate_label_rows() -> None:
    """Two same-canonical rows must not overwrite different evaluations."""
    first = _threshold_key(
        "82369",
        "RULE_INGREDIENT_CAFFEINE",
        "caffeine",
        "pregnancy",
        THRESHOLD,
        ingredient_row_id="ingredientRows[1].nestedRows[0]",
    )
    second = _threshold_key(
        "82369",
        "RULE_INGREDIENT_CAFFEINE",
        "caffeine",
        "pregnancy",
        THRESHOLD,
        ingredient_row_id="ingredientRows[2]",
    )

    assert first != second


def test_threshold_key_is_stable_when_rule_arrays_reorder() -> None:
    """The key uses semantic rule terms, never a list index."""
    kwargs = {
        "dsld_id": "82369",
        "rule_id": "RULE_INGREDIENT_CAFFEINE",
        "ingredient": "caffeine",
        "condition": "pregnancy",
        "threshold": dict(THRESHOLD),
        "ingredient_row_id": "ingredientRows[2]",
    }

    assert _threshold_key(**kwargs) == _threshold_key(**kwargs)
