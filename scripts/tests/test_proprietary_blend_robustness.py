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
