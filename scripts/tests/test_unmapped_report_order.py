"""Unmapped-report order does not depend on worker history.

2026-10-19: a cleaner worker's unmapped Counter keeps the first-ever insertion
order of every name it saw, so each label's unmapped list came out in an order
set by the labels that worker cleaned before (682 of 15,414 labels differed
between two parallel runs of the same code). The tracker then sorted by count
only, so equal-count names were written in that arrival order.
"""

import json
import os
import sys
from collections import Counter

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from enhanced_normalizer import EnhancedDSLDNormalizer
from unmapped_ingredient_tracker import UnmappedIngredientTracker


@pytest.fixture(scope="module")
def normalizer():
    return EnhancedDSLDNormalizer()


def test_label_delta_lists_names_in_sorted_order(normalizer):
    normalizer.unmapped_ingredients = Counter()
    normalizer.unmapped_details = {}
    for name in ["Zeta Root", "Alpha Leaf", "Mu Bark"]:
        normalizer._record_unmapped_ingredient(name, [], is_active=True)

    delta = normalizer.get_unmapped_delta({})["unmapped"]

    assert [row["name"] for row in delta] == ["Alpha Leaf", "Mu Bark", "Zeta Root"]


def _saved(tmp_path, arrival_order):
    tracker = UnmappedIngredientTracker(tmp_path)
    counts = {name: 2 for name in arrival_order}
    counts["Common Gum"] = 5
    tracker.process_unmapped_ingredients(
        counts,
        {"Zeta Root", "Alpha Leaf"},
        {name: {"is_active": name in {"Zeta Root", "Alpha Leaf"}} for name in counts},
        processed_count_override=1,
    )
    tracker.save_tracking_files()
    return {
        name: list(json.loads((tmp_path / name).read_text())["unmapped_ingredients"])
        for name in ("unmapped_active_ingredients.json", "unmapped_inactive_ingredients.json")
    }


def test_equal_counts_are_written_by_name_whatever_the_arrival_order(tmp_path):
    first = _saved(tmp_path / "a", ["Zeta Root", "Alpha Leaf", "Wax", "Beet Fiber"])
    second = _saved(tmp_path / "b", ["Beet Fiber", "Alpha Leaf", "Wax", "Zeta Root"])

    assert first == second
    assert first["unmapped_active_ingredients.json"] == ["Alpha Leaf", "Zeta Root"]
    assert first["unmapped_inactive_ingredients.json"] == ["Common Gum", "Beet Fiber", "Wax"]
