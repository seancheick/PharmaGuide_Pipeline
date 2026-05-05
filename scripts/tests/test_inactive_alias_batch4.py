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


def test_batch4_specific_entries_keep_exact_owner() -> None:
    expected = {
        "l-arabinose": "L-Arabinose",
        "mono and diglycerides": "Mono and Diglycerides",
        "sunfiber": "Sunfiber",
        "vegetable lubricant": "Vegetable Lubricant",
        "vegetable magnesium silicate": "Vegetable Magnesium Silicate",
        "vitamin u": "Vitamin U",
    }

    for raw_label, expected_standard_name in expected.items():
        assert _resolved_standard_name(raw_label) == expected_standard_name
