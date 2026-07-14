from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from enhanced_normalizer import EnhancedDSLDNormalizer


def _row(name: str, amount: float, unit: str) -> dict:
    return {"name": name, "quantity": amount, "unit": unit}


def test_panel_fats_and_cholesterol_are_retained_in_nutritional_info() -> None:
    normalizer = EnhancedDSLDNormalizer()

    info = normalizer._extract_nutritional_info([
        _row("Total Fat", 5, "g"),
        _row("Saturated Fat", 2, "g"),
        _row("Trans Fat", 0, "g"),
        _row("Cholesterol", 15, "mg"),
    ])

    assert info["totalFat"] == {"amount": 5.0, "unit": "g"}
    assert info["saturatedFat"] == {"amount": 2.0, "unit": "g"}
    assert info["transFat"] == {"amount": 0.0, "unit": "g"}
    assert info["cholesterol"] == {"amount": 15.0, "unit": "mg"}
