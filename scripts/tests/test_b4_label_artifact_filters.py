"""B4: structural label-artifact filters in the cleaner skip-list.

The May 22 2026 pipeline run surfaced multiple unmapped inactives
that are not actual ingredients but food-matrix descriptors,
packaging artifacts, or section headers:

  - 'Coloring' (×3) — too vague; specific colors map separately
  - 'Chocolate Cookie Crumbs' (×2), '...Pieces' (×2),
    'Chocolate Chips' (×1) — textural confection descriptors
  - 'Vanilla Micro Cookie Gems' (×1) — same
  - 'Peanut/Yogurt/Chocolate Flavored Coating' (×3 combined)
  - 'Vegetable Concentrate' (×1) — too vague; specific veggies map separately
  - 'Certified Organic Fruit Chew Base Blend' (×4),
    'Certified Organic Real Food Vitamin Blend' (×3+) — section headers
  - 'Other Ingredients, Redberry:' (×1) — parser leak of section header

Adding these to EXCLUDED_LABEL_PHRASES makes the cleaner skip them
instead of emitting them as unmapped — they're not ingredients in
the cleaning-pipeline sense.
"""
from __future__ import annotations

import sys
import os
from typing import Set

import pytest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(_ROOT, "scripts"))

from constants import EXCLUDED_LABEL_PHRASES  # type: ignore


B4_NEW_FILTERS = [
    "coloring",
    "chocolate cookie crumbs",
    "chocolate cookie pieces",
    "chocolate chips",
    "vanilla micro cookie gems",
    "peanut flavored coating",
    "yogurt flavored coating",
    "chocolate flavored coating",
    "chocolate flavoured coating",
    "vegetable concentrate",
    "certified organic fruit chew base blend",
    "certified organic real food vitamin blend",
    "certified organic real food vitamin blend:",
    "other ingredients, redberry:",
]


@pytest.mark.parametrize("phrase", B4_NEW_FILTERS)
def test_phrase_in_excluded_label_phrases(phrase):
    """Each B4 filter must be present in EXCLUDED_LABEL_PHRASES so
    the cleaner skips it rather than emitting as unmapped."""
    assert phrase in EXCLUDED_LABEL_PHRASES, (
        f"B4 filter {phrase!r} missing from EXCLUDED_LABEL_PHRASES"
    )


def test_real_ingredients_NOT_filtered():
    """Safety boundary: the B4 additions must NOT shadow real
    ingredient names. Common real ingredients should NOT be in
    the skip list."""
    SAFE_REAL_INGREDIENTS = (
        "vitamin c", "calcium carbonate", "spirulina", "cocoa",
        "vitamin d3", "omega-3", "ginger", "turmeric",
        "magnesium glycinate", "zinc", "iron",
    )
    for ingredient in SAFE_REAL_INGREDIENTS:
        assert ingredient not in EXCLUDED_LABEL_PHRASES, (
            f"REGRESSION: '{ingredient}' is a real ingredient — must "
            f"NOT be in EXCLUDED_LABEL_PHRASES"
        )


def test_pre_existing_filters_preserved():
    """Pre-existing filter entries must remain — additions are
    additive only."""
    PRE_EXISTING = (
        "other ingredients", "inactive ingredients", "active ingredients",
        "less than 2% of", "may contain", "contains",
    )
    for phrase in PRE_EXISTING:
        assert phrase in EXCLUDED_LABEL_PHRASES, (
            f"Pre-existing filter {phrase!r} was lost"
        )
