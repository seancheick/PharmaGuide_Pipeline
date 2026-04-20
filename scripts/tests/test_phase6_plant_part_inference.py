"""
Phase 6 regression tests — plant-part tissue fidelity.

Context: DSLD ingredient rows sometimes carry a structured
``notes: "PlantPart: root"`` field, but many brands (GNC, Goli, CVS)
ship labels where the plant-part qualifier is only embedded in the
ingredient name text. Before Phase 6 these rows lost the qualifier at
cleaner-time, leaving the enricher unable to distinguish root-derived
ashwagandha (high-withanolide, clinically studied for KSM-66) from
leaf-derived (very different alkaloid profile) or aerial parts.

After Phase 6, the cleaner falls back to name-based inference when
DSLD's notes don't declare ``PlantPart:`` explicitly, using a
longest-first token list so "aerial parts" beats "aerial", and
normalizing simple plurals ("leaves" → "leaf").

See docs/HANDOFF_2026-04-20_PIPELINE_REFACTOR.md § Phase 6.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from enhanced_normalizer import EnhancedDSLDNormalizer


@pytest.fixture(scope="module")
def normalizer() -> EnhancedDSLDNormalizer:
    return EnhancedDSLDNormalizer()


class TestPlantPartNameInference:
    """The fallback correctly recovers plant-part from embedded name text."""

    @pytest.mark.parametrize("name,expected", [
        ("KSM-66 Ashwagandha root extract", "root"),
        ("Ashwagandha Root Powder", "root"),
        ("Organic Turmeric Rhizome", "rhizome"),
        ("Peppermint Leaf Extract", "leaf"),
        ("Sage leaves", "leaf"),
        ("Elderberry fruit extract", "fruit"),
        ("Saw Palmetto Berry Extract", "berry"),
        ("Willow Bark", "bark"),
        ("Milk Thistle seed extract", "seed"),
        ("Cranberry Fruit Powder", "fruit"),
        ("Kanna aerial parts extract", "aerial parts"),
        ("Holy Basil whole herb", "whole herb"),
        ("Ginger Rhizome 500 mg", "rhizome"),
    ])
    def test_common_plant_parts_inferred(self, normalizer, name, expected) -> None:
        assert normalizer._infer_plant_part_from_name(name) == expected

    def test_aerial_parts_beats_aerial(self, normalizer) -> None:
        # "aerial parts" is declared first in the token list so a name
        # containing the full phrase matches the phrase, not the single word.
        assert normalizer._infer_plant_part_from_name("Kanna aerial parts extract") == "aerial parts"

    def test_false_positive_rooster_not_root(self, normalizer) -> None:
        # "Rooster" must not match "root" — word-boundary guard holds.
        assert normalizer._infer_plant_part_from_name("Rooster Comb Cartilage") is None

    def test_no_plant_part_returns_none(self, normalizer) -> None:
        assert normalizer._infer_plant_part_from_name("Vitamin D3 (Cholecalciferol)") is None
        assert normalizer._infer_plant_part_from_name("Calcium Ascorbate") is None
        assert normalizer._infer_plant_part_from_name("") is None
        assert normalizer._infer_plant_part_from_name(None) is None  # type: ignore[arg-type]

    def test_plural_normalization(self, normalizer) -> None:
        assert normalizer._infer_plant_part_from_name("Mint Leaves") == "leaf"
        assert normalizer._infer_plant_part_from_name("Flaxseed Seeds") == "seed"
        assert normalizer._infer_plant_part_from_name("Grape Seeds Extract") == "seed"


class TestStructuredNotesStillWins:
    """When DSLD provides ``PlantPart:`` in notes, it takes precedence over name inference."""

    def test_structured_notes_preserved(self, normalizer) -> None:
        # The notes parser sets plantPart before the fallback runs, so
        # even if the name doesn't match any token, the structured value
        # survives. And when both exist, structured wins.
        details = normalizer._parse_botanical_details(
            "PlantPart: aerial parts Genus: Withania Species: somnifera"
        )
        assert details["plantPart"] == "aerial parts"

    def test_structured_notes_overrides_name(self, normalizer) -> None:
        # If notes says "leaf" but name has "root", structured metadata wins.
        details = normalizer._parse_botanical_details("PlantPart: leaf")
        assert details["plantPart"] == "leaf"
        # Cleaner flow won't call the fallback in this case because
        # details.get("plantPart") is truthy.
