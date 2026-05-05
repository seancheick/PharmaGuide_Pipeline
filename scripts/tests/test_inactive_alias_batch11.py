from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from enhanced_normalizer import EnhancedDSLDNormalizer  # noqa: E402


def _resolved_standard_name(label: str) -> str | None:
    normalizer = EnhancedDSLDNormalizer()
    standard_name, is_other_ingredient, _ = normalizer._map_inactive_name_prefer_other(label)
    assert is_other_ingredient is True
    return standard_name


def test_batch11_exact_owner_trims() -> None:
    expected = {
        "plant-based lubricant": "Vegetable Lubricant",
        "natural vanilla": "Natural Vanilla & Vanilla Extract",
        "spice extracts": "Spices",
        "sodium carboxymethyl starch": "Sodium Starch Glycolate",
        "vegetable magnesium stearate": "Magnesium Stearate",
        "vegetable stearic acid": "Stearic Acid",
        "vegetable wax": "Botanical Wax",
    }

    for raw_label, expected_standard_name in expected.items():
        assert _resolved_standard_name(raw_label) == expected_standard_name
