from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent))

from enhanced_normalizer import EnhancedDSLDNormalizer
from enrich_supplements_v3 import _resolve_cli_paths


def test_proprietary_disclosure_retains_every_blend_and_uses_clear_unknown_copy() -> None:
    normalizer = EnhancedDSLDNormalizer()
    blends = [
        {
            "name": "Botanical Blend",
            "quantity": 500,
            "unit": "mg",
            "proprietaryBlend": True,
            "nestedIngredients": [
                {"name": "Turmeric", "quantityProvided": False, "unit": "NP"},
                {"name": "Ginger", "quantityProvided": False, "unit": "NP"},
            ],
        },
        {
            "name": "Enzyme Blend",
            "quantity": 0,
            "unit": "NP",
            "proprietaryBlend": True,
            "nestedIngredients": [
                {"name": "Protease", "quantityProvided": True, "unit": "mg"},
            ],
        },
    ]

    disclosure = normalizer._build_proprietary_blend_disclosure(blends)

    assert disclosure["blendCount"] == 2
    assert [blend["name"] for blend in disclosure["blends"]] == [
        "Botanical Blend",
        "Enzyme Blend",
    ]
    assert disclosure["blends"][0]["individualAmounts"] == "Not disclosed"
    assert disclosure["blends"][1]["totalAmount"] == "Not disclosed"


def test_enricher_cli_overrides_are_independent() -> None:
    config = {"paths": {"input_directory": "configured-in", "output_directory": "configured-out"}}

    assert _resolve_cli_paths(
        SimpleNamespace(input_dir="chosen-in", output_dir=None), config
    ) == ("chosen-in", "configured-out")
    assert _resolve_cli_paths(
        SimpleNamespace(input_dir=None, output_dir="chosen-out"), config
    ) == ("configured-in", "chosen-out")
