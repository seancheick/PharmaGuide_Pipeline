"""Plain-botanical identity recognition for the BulkSupplements unmapped triage.

These are identity-only botanicals (recognized, NOT IQM-scored). Moves them from
'unmapped active' to 'recognized'. All CUIs UMLS-verified live 2026-06-22.

Coverage added to existing entries: perilla_leaf (aerial part), tremella_fuciformis
(fruiting body). New entries created: dragon fruit, mulberry mistletoe, purslane,
galla chinensis, black rice, arnica, cassia seed.

cassia_seed is a verify-before-assume catch: the existing 'cassia' entries are
Cinnamomum cassia (cinnamon) and Cassia nomame — NEITHER is the cassia seed
(Senna/Cassia obtusifolia), so it needs its own entry.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from enhanced_normalizer import EnhancedDSLDNormalizer

BOT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "botanical_ingredients.json")


@pytest.fixture(scope="module")
def normalizer():
    return EnhancedDSLDNormalizer()


@pytest.fixture(scope="module")
def botanicals():
    with open(BOT_PATH, encoding="utf-8") as fh:
        data = json.load(fh)
    return {e["id"]: e for e in data["botanical_ingredients"]}


@pytest.mark.parametrize(
    "label,expected_sn",
    [
        ("Perilla Aerial Part Extract", "perilla"),
        ("Tremella Fruiting Body Extract", "tremella"),
        ("Tremella Mushroom Fruiting Body Extract", "tremella"),
        ("Dragon fruit extract", "dragon fruit"),
        ("Mulberry Mistletoe extract", "mulberry mistletoe"),
        ("Mulberry Mistletoe Leaf, Stem Extract", "mulberry mistletoe"),
        ("Portulaca oleracea Whole Herb Extract", "purslane"),
        ("Portulaca oleracea extract", "purslane"),
        ("Galla chinensis extract", "galla chinensis"),
        ("Black Rice extract", "black rice"),
        ("Arnica Flower Extract", "arnica"),
        ("Cassia Seed Extract", "cassia seed"),
    ],
)
def test_plain_botanical_now_recognized(normalizer, label, expected_sn):
    standard_name, mapped, _ = normalizer._enhanced_ingredient_mapping(label, [])
    assert mapped is True, f"{label!r} should now be recognized, got unmapped"
    assert expected_sn in str(standard_name).lower()


@pytest.mark.parametrize(
    "entry_id,cui,latin",
    [
        ("dragon_fruit", "C1202122", "Hylocereus undatus"),
        ("mulberry_mistletoe", "C1463005", "Taxillus chinensis"),
        ("purslane", "C0330346", "Portulaca oleracea"),
        ("galla_chinensis", "C1677349", "Rhus chinensis"),
        ("black_rice", "C0086740", "Oryza sativa"),
        ("arnica", "C0331307", "Arnica montana"),
        ("cassia_seed", "C1900008", "Senna obtusifolia"),
    ],
)
def test_new_botanical_has_verified_cui(botanicals, entry_id, cui, latin):
    e = botanicals[entry_id]
    assert e["cui"] == cui          # UMLS-verified 2026-06-22
    assert e["latin_name"] == latin


def test_cassia_seed_is_distinct_from_cinnamon(botanicals):
    assert botanicals["cassia_seed"]["latin_name"] == "Senna obtusifolia"
    assert botanicals["cassia_seed"]["latin_name"] != "Cinnamomum cassia"
