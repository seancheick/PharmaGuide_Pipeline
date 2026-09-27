from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from enhanced_normalizer import EnhancedDSLDNormalizer
from functional_grouping_handler import FunctionalGroupingHandler


def test_functional_group_split_respects_parenthesized_commas() -> None:
    handler = FunctionalGroupingHandler()

    result = handler.process_ingredient_for_cleaning(
        "Natural Colors: Citrus Oils (Orange, Lemon), Beet Root"
    )

    assert result["ingredients"] == [
        "Citrus Oils (Orange, Lemon)",
        "Beet Root",
    ]


@pytest.mark.parametrize("parallel_threshold", [1, 100])
def test_cleaner_uses_same_functional_group_path_for_every_list_size(
    parallel_threshold: int,
) -> None:
    normalizer = EnhancedDSLDNormalizer()
    normalizer._parallel_threshold = parallel_threshold
    raw = {
        "ingredients": [
            {"name": "Natural Colors: Citrus Oils (Orange, Lemon), Beet Root", "order": 1},
            {"name": "Cellulose", "order": 2},
        ]
    }

    names = [
        row["name"]
        for row in normalizer._process_other_ingredients_enhanced(raw)
    ]

    assert names == ["Citrus Oils (Orange, Lemon)", "Beet Root", "Cellulose"]


@pytest.mark.parametrize('name', ['Proprietary Blend', 'Proprietary Protein Blend'])
def test_skipped_inactive_blend_preserves_disclosed_source_forms(name):
    normalizer = EnhancedDSLDNormalizer()
    raw = {'ingredients': [{
        'name': name, 'raw_source_path': 'otheringredients.ingredients[0]',
        'category': 'protein', 'ingredientGroup': 'Whey Protein',
        'forms': [{'name': 'Whey Protein Isolate', 'category': 'protein',
                   'ingredientGroup': 'Whey Protein'}],
    }]}
    rows = normalizer._process_other_ingredients_enhanced(raw)
    assert [row['name'] for row in rows] == ['Whey Protein Isolate']
    assert rows[0]['raw_source_path'] == 'otheringredients.ingredients[0].forms[0]'
