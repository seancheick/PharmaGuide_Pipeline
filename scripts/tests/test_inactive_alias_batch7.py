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


def test_batch7_generic_buckets_do_not_steal_specific_colors_and_gums() -> None:
    expected = {
        "annatto": "Annatto Extract",
        "anthocyanins": "Anthocyanin",
        "beet juice powder": "Beet Juice Color",
        "beet powder": "Beetroot Powder",
        "carrot juice concentrate": "Carrot Juice (Color)",
        "cellulose, plant": "Plant-Derived Cellulose",
        "e412": "Guar Gum",
        "e414": "Acacia Gum",
        "e415": "Xanthan Gum",
    }

    for raw_label, expected_standard_name in expected.items():
        assert _resolved_standard_name(raw_label) == expected_standard_name
