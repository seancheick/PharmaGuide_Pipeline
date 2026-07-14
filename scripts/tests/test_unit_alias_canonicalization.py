"""Regression tests for canonical mass-unit aliases (review finding C7)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from unit_converter import UnitConverter


@pytest.fixture(scope="module")
def converter() -> UnitConverter:
    return UnitConverter()


@pytest.mark.parametrize(
    "alias",
    ["mcg", "ug", "µg", "μg", "microgram", "micrograms", "Microgram(s)"],
)
def test_microgram_aliases_share_one_canonical_unit(converter: UnitConverter, alias: str) -> None:
    result = converter.convert_mass(25, alias, "mcg")

    assert result.success is True
    assert result.converted_value == pytest.approx(25)


@pytest.mark.parametrize("alias", ["g", "gram", "grams", "gm", "Gram(s)"])
def test_gram_aliases_convert_to_milligrams(converter: UnitConverter, alias: str) -> None:
    result = converter.convert_mass(2, alias, "mg")

    assert result.success is True
    assert result.converted_value == pytest.approx(2000)


def test_nutrient_conversion_uses_the_same_alias_canonicalizer(
    converter: UnitConverter,
) -> None:
    result = converter.convert_nutrient(
        nutrient="Vitamin B12",
        amount=500,
        from_unit="μg",
        to_unit="mcg",
    )

    assert result.success is True
    assert result.converted_value == pytest.approx(500)
    assert result.converted_unit == "mcg"


def test_parenthetical_milligram_alias_is_canonicalized(converter: UnitConverter) -> None:
    result = converter.convert_mass(2, "Milligram(s)", "mg")

    assert result.success is True
    assert result.converted_value == pytest.approx(2)
