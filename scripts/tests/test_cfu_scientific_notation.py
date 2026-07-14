"""Scientific-notation CFU labels use the canonical row-local CFU parser."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from enrich_supplements_v3 import SupplementEnricherV3


@pytest.fixture(scope="module")
def enricher() -> SupplementEnricherV3:
    return SupplementEnricherV3()


@pytest.mark.parametrize(
    "text,expected_count",
    [
        ("Provides 5 × 10^9 CFU through expiration", 5_000_000_000),
        ("Contains 5x10⁹ CFUs", 5_000_000_000),
        ("2.5e9 colony forming units", 2_500_000_000),
        ("Provides 1.5 billion CFU", 1_500_000_000),
        ("Provides 1.5 B CFU", 1_500_000_000),
        ("Provides 500 million CFUs", 500_000_000),
    ],
)
def test_scientific_notation_cfu_is_parsed_with_row_provenance(
    enricher, text, expected_count
) -> None:
    result = enricher._extract_cfu(
        text,
        ingredient={"name": "Lactobacillus rhamnosus GG", "notes": text},
        source_path="activeIngredients[0]",
        evidence_scope="row_level",
    )

    assert result["has_cfu"] is True
    assert result["cfu_count"] == pytest.approx(expected_count)
    assert result["billion_count"] == pytest.approx(expected_count / 1e9)
    assert result["source"] == "activeIngredients.notes"
    assert result["raw_source_path"] == "activeIngredients[0]"
    assert result["evidence_scope"] == "row_level"


def test_scientific_notation_without_cfu_unit_is_not_borrowed(enricher) -> None:
    result = enricher._extract_cfu(
        "Vitamin D3 provides 5 × 10^3 IU",
        ingredient={"name": "Lactobacillus rhamnosus GG"},
        source_path="activeIngredients[0]",
        evidence_scope="row_level",
    )

    assert result["has_cfu"] is False
    assert result["cfu_count"] == 0


@pytest.mark.parametrize("text", ["1e999 CFU", "5 × 10^-3 CFU"])
def test_out_of_range_scientific_cfu_is_contained(enricher, text) -> None:
    result = enricher._extract_cfu(
        text,
        ingredient={"name": "Lactobacillus rhamnosus GG"},
        source_path="activeIngredients[0]",
        evidence_scope="row_level",
    )

    assert result["has_cfu"] is False
    assert result["cfu_count"] == 0
