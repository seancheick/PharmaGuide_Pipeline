"""
Sprint D2.5 regression tests — whole-food + uncommon plant routing.

Context: ~300 silently-mapped rows in the deep accuracy audit were
whole-food powders, uncommon species, and animal/plant protein
isolates that had no canonical in any reference DB. Fix: added
aliases to existing botanical entries (oat_generic, blueberry,
brussels_sprout, kelp_powder, tart_cherry_fruit, dark_sweet_cherry)
plus new entries (tamarind, green_bean, lima_bean, ecklonia_radiata,
ecklonia_kurome, alaria_esculenta) and three protein-isolate entries
in other_ingredients (beef / chicken / chickpea).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from enhanced_normalizer import EnhancedDSLDNormalizer

DATA_DIR = Path(__file__).parent.parent / "data"


@pytest.fixture(scope="module")
def normalizer() -> EnhancedDSLDNormalizer:
    return EnhancedDSLDNormalizer()


class TestWholeFoodRouting:
    """Every audit-surfaced silent row now resolves to some canonical."""

    @pytest.mark.parametrize("raw,expected_source_dbs", [
        ("Swedish Oats Beta-Glucans",       {"botanical_ingredients", "standardized_botanicals"}),
        ("Blueberry juice powder",          {"botanical_ingredients"}),
        ("organic tamarind juice powder",   {"botanical_ingredients"}),
        ("Tamarind juice powder",           {"botanical_ingredients"}),
        ("Ecklonia radiata",                {"botanical_ingredients"}),
        ("Ecklonia kurome",                 {"botanical_ingredients"}),
        ("Alaria esculenta",                {"botanical_ingredients"}),
        ("Brussels",                        {"botanical_ingredients"}),
        ("Green Bean powder",               {"botanical_ingredients"}),
        ("Lima Bean powder",                {"botanical_ingredients"}),
        ("Cherry puree powder",             {"botanical_ingredients"}),
        ("Beef Protein isolate",            {"other_ingredients"}),
        ("Chicken Protein Isolate",         {"other_ingredients"}),
        ("Chickpea Protein",                {"other_ingredients"}),
    ])
    def test_silent_row_now_resolves(self, normalizer, raw, expected_source_dbs) -> None:
        r = normalizer._resolve_canonical_identity(raw, raw_name=raw)
        assert r is not None and r[0] is not None, f"{raw!r} did not resolve"
        assert r[1] in expected_source_dbs, (
            f"{raw!r} resolved to source_db={r[1]!r}; expected one of {expected_source_dbs}"
        )


class TestNewBotanicalEntriesExist:
    """Guard the new botanical entries from accidental deletion."""

    @pytest.mark.parametrize("entry_id", [
        "tamarind",
        "green_bean",
        "lima_bean",
        "ecklonia_radiata",
        "ecklonia_kurome",
        "alaria_esculenta",
    ])
    def test_entry_in_botanicals(self, entry_id) -> None:
        data = json.loads((DATA_DIR / "botanical_ingredients.json").read_text())
        found = False
        for section, items in data.items():
            if section.startswith("_") or not isinstance(items, list):
                continue
            if any(isinstance(e, dict) and e.get("id") == entry_id for e in items):
                found = True
                break
        assert found, f"Sprint D2.5 botanical entry {entry_id!r} missing — regression"


class TestProteinIsolateEntriesExist:
    """Guard the new protein-isolate entries in other_ingredients."""

    @pytest.mark.parametrize("entry_id", [
        "NHA_BEEF_PROTEIN_ISOLATE",
        "NHA_CHICKEN_PROTEIN_ISOLATE",
        "NHA_CHICKPEA_PROTEIN",
    ])
    def test_protein_entry_exists(self, entry_id) -> None:
        data = json.loads((DATA_DIR / "other_ingredients.json").read_text())
        found = any(
            isinstance(e, dict) and e.get("id") == entry_id
            for e in data.get("other_ingredients", [])
        )
        assert found, f"Sprint D2.5 protein entry {entry_id!r} missing — regression"
