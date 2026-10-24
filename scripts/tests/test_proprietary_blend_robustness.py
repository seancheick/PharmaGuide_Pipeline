"""Regression tests for proprietary-blend dedupe and parsing (finding C10)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from proprietary_blend_detector import ProprietaryBlendDetector


def _partial_blend() -> dict:
    return {
        "name": "Digestive Enzyme Blend",
        "amount": 500,
        "unit": "mg",
        "ingredients": ["Amylase", "Protease"],
    }


def test_same_blend_projected_in_two_sections_is_penalized_once() -> None:
    detector = ProprietaryBlendDetector()
    blend = _partial_blend()

    result = detector.analyze_product({
        "activeIngredients": [blend],
        "otherIngredients": [dict(blend)],
    })

    assert len(result.blends_detected) == 1
    assert result.total_penalty_applicable == -5


def test_comma_formatted_embedded_amount_is_parsed_without_crashing() -> None:
    detector = ProprietaryBlendDetector()

    result = detector.analyze_product({
        "activeIngredients": [{
            "name": "Digestive Enzyme Blend",
            "amount": 500,
            "unit": "mg",
            "ingredients": ["Amylase 1,000 mg"],
        }]
    })

    detected = result.blends_detected[0]
    assert detected.ingredients_with_amounts[0]["amount"] == 1000.0
    assert detected.disclosure_level == "full"


def test_normalized_nested_disclosure_and_parent_quantity_are_read():
    detector = ProprietaryBlendDetector()
    [blend] = detector.analyze_product({'activeIngredients': [{
        'name': 'Proprietary Blend', 'quantity': 500, 'unit': 'mg',
        'nestedIngredients': [{'name': 'Collagen', 'quantity': 300, 'unit': 'mg'},
                              {'name': 'Hyaluronic Acid', 'quantity': 50, 'unit': 'mg'}],
    }]}).blends_detected
    assert blend.blend_total_amount == 500
    assert blend.disclosure_level == 'full'
    assert [r['amount'] for r in blend.ingredients_with_amounts] == [300, 50]


def test_typed_activity_is_disclosure_without_borrowing_the_parent_mass():
    detector = ProprietaryBlendDetector()
    [blend] = detector.analyze_product({'activeIngredients': [{
        'name': 'Digestive Enzyme Blend', 'quantity': 350, 'unit': 'mg',
        'nestedIngredients': [{'name': 'Protease', 'quantity': 0, 'unit': 'NP',
                               'activity_quantity': 75000, 'activity_unit': 'HUT'}],
    }]}).blends_detected
    assert blend.disclosure_level == 'full'
    assert blend.ingredients_with_amounts == [{'name': 'Protease', 'amount': 75000, 'unit': 'HUT'}]


def test_unknown_child_mass_does_not_become_full_disclosure():
    detector = ProprietaryBlendDetector()
    [blend] = detector.analyze_product({'activeIngredients': [{
        'name': 'Proprietary Blend', 'amount': 500, 'unit': 'mg',
        'ingredients': [{'name': 'One', 'quantity': -5, 'unit': 'mg'},
                        {'name': 'Two', 'quantity': float('nan'), 'unit': 'mg'}],
    }]}).blends_detected
    assert blend.disclosure_level == 'partial'
    assert blend.ingredients_with_amounts == []
