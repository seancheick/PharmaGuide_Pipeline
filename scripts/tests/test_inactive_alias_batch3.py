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


def test_batch3_specific_inactive_alias_owners() -> None:
    expected = {
        "beetroot powder": "Beetroot Powder",
        "blackstrap molasses": "Blackstrap Molasses",
        "calcium chloride": "Calcium Chloride",
        "glyceryl monooleate": "Glyceryl Monooleate",
        "microcrystalline cellulose": "Microcrystalline Cellulose",
        "modified starch": "Modified Starch",
        "sodium carboxymethylcellulose": "Sodium Carboxymethylcellulose",
    }

    for raw_label, expected_standard_name in expected.items():
        assert _resolved_standard_name(raw_label) == expected_standard_name


def test_batch3_common_cellulose_aliases_stay_on_mcc() -> None:
    assert _resolved_standard_name("cellulose powder") == "Microcrystalline Cellulose"
    assert _resolved_standard_name("MCC") == "Microcrystalline Cellulose"
