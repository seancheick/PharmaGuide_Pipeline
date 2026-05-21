"""SP-2.8 v3 _resolve_percentile_category taxonomy-first migration.

Before this commit: the scorer derived percentile_category from
`product.get("percentile_category")` first, then from
`supplement_type.category` / `subtype` / `type`. The taxonomy classifier's
`supplement_taxonomy.percentile_category` was ignored even when present.

After this commit: prefers `supplement_taxonomy.percentile_category`,
which aligns the scorer with build_final_db and the taxonomy classifier
itself. Legacy paths remain as fallback for old enriched batches.

The source string for taxonomy-derived categories is `taxonomy_v2` so
audit consumers can see which signal won.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from score_supplements import SupplementScorer


@pytest.fixture(scope="module")
def scorer() -> SupplementScorer:
    return SupplementScorer()


def test_taxonomy_percentile_category_wins(scorer):
    """When taxonomy is present, its percentile_category is canonical."""
    product = {
        "supplement_taxonomy": {
            "primary_type": "omega_3",
            "percentile_category": "fish_oil",
            "classification_confidence": 0.95,
            "classification_reasons": ["omega-3: ids=['epa', 'dha'], name_match=True"],
        },
        # Legacy field deliberately disagrees — taxonomy must win.
        "percentile_category": "general_supplement",
    }
    key, label, source, confidence, signals = scorer._resolve_percentile_category(product, {})
    assert key == "fish_oil"
    assert label == "Fish Oil"
    assert source == "taxonomy_v2"
    assert confidence == 0.95
    assert "omega-3" in signals[0]


def test_taxonomy_multivitamin(scorer):
    product = {
        "supplement_taxonomy": {
            "primary_type": "multivitamin",
            "percentile_category": "multivitamin",
            "classification_confidence": 0.9,
            "classification_reasons": ["multivitamin: 11 vitamins, 5 minerals"],
        },
    }
    key, label, source, _, _ = scorer._resolve_percentile_category(product, {})
    assert key == "multivitamin"
    assert source == "taxonomy_v2"


def test_taxonomy_probiotic(scorer):
    product = {
        "supplement_taxonomy": {
            "primary_type": "probiotic",
            "percentile_category": "probiotic",
            "classification_confidence": 0.85,
            "classification_reasons": [],
        },
    }
    key, _, source, _, _ = scorer._resolve_percentile_category(product, {})
    assert key == "probiotic"
    assert source == "taxonomy_v2"


def test_no_taxonomy_falls_back_to_explicit_field(scorer):
    """Old batch — taxonomy absent. Use explicit percentile_category."""
    product = {
        "percentile_category": "single_vitamin",
        "percentile_category_label": "Single Vitamin",
        "percentile_category_source": "explicit",
        "percentile_category_confidence": 0.8,
    }
    key, label, source, confidence, _ = scorer._resolve_percentile_category(product, {})
    assert key == "single_vitamin"
    assert label == "Single Vitamin"
    assert source == "explicit"
    assert confidence == 0.8


def test_no_taxonomy_falls_back_to_supplement_type(scorer):
    """Old batch with no taxonomy AND no explicit category — derives from
    legacy supplement_type."""
    product = {
        "supplement_type": {"type": "multivitamin"},
    }
    key, _, _, _, _ = scorer._resolve_percentile_category(product, {})
    assert key == "multivitamin"


def test_taxonomy_with_empty_percentile_category_falls_through(scorer):
    """If taxonomy is present but percentile_category is empty, fall
    through to legacy paths instead of using an empty category."""
    product = {
        "supplement_taxonomy": {
            "primary_type": "general_supplement",
            "percentile_category": "",
            "classification_confidence": 0.0,
        },
        "percentile_category": "single_vitamin",
    }
    key, _, source, _, _ = scorer._resolve_percentile_category(product, {})
    # Should NOT be taxonomy_v2 because taxonomy's category was empty
    assert source != "taxonomy_v2"
    assert key == "single_vitamin"


def test_taxonomy_general_supplement_is_valid(scorer):
    """`general_supplement` from taxonomy is a real classification, not a
    missing-data signal. Should still win over legacy fields."""
    product = {
        "supplement_taxonomy": {
            "primary_type": "general_supplement",
            "percentile_category": "general_supplement",
            "classification_confidence": 0.3,
        },
        # Even if legacy says something else
        "percentile_category": "herbal_blend",
    }
    key, _, source, _, _ = scorer._resolve_percentile_category(product, {})
    assert key == "general_supplement"
    assert source == "taxonomy_v2"
