"""Regression tests for explicit color-name boundaries (review finding C1)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from enhanced_normalizer import EnhancedDSLDNormalizer


@pytest.fixture(scope="module")
def normalizer() -> EnhancedDSLDNormalizer:
    return EnhancedDSLDNormalizer()


def test_amaranth_plant_descriptor_is_not_an_artificial_color(
    normalizer: EnhancedDSLDNormalizer,
) -> None:
    standard_name, _mapped, _forms = normalizer._enhanced_ingredient_mapping(
        "Amaranth Sprout Powder", []
    )

    assert standard_name != "artificial colors"


@pytest.mark.parametrize("label", ["Amaranth Dye", "Amaranth Colorant", "E123 Amaranth"])
def test_qualified_amaranth_dye_labels_remain_artificial_colors(
    normalizer: EnhancedDSLDNormalizer,
    label: str,
) -> None:
    standard_name, mapped, _forms = normalizer._enhanced_ingredient_mapping(label, [])

    assert standard_name == "artificial colors"
    assert mapped is True
