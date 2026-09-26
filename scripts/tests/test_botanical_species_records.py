"""Botanical records describe the species and part their identifiers name.

``vitex`` serves the Airborne "Vitex trifolia" rows and Man Jing Zi, the fruit
of V. trifolia (Viticis Fructus; PMID 37810114, 37282876), yet claimed Vitex
agnus-castus and carried V. negundo aliases. Chaste tree (V. agnus-castus) is
``chaste_tree`` and five-leaf chastetree (V. negundo) is ``nirgundi``, so one
species resolved to two records by spelling: "Vitex negundo" to ``nirgundi``,
"organic Vitex negundo" to ``vitex``.

``milk_thistle`` notes called it the whole herb, but its UNII U946SH95EE is
registered as SILYBUM MARIANUM SEED (openFDA /other/unii, 2026-09-26).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

FIXTURES = Path(__file__).parent / "fixtures"


def _records() -> dict:
    data = json.loads((SCRIPTS / "data" / "botanical_ingredients.json").read_text())
    return {row["id"]: row for row in data["botanical_ingredients"]}


@pytest.fixture(scope="module")
def normalizer():
    from enhanced_normalizer import EnhancedDSLDNormalizer

    return EnhancedDSLDNormalizer()


def _vitex_rows(cleaned: dict) -> dict:
    found = {}

    def walk(rows):
        for row in rows or []:
            if "vitex" in str(row.get("name")).lower():
                found[row["name"]] = row.get("canonical_id")
            walk(row.get("nestedRows") or row.get("nested_ingredients"))

    walk((cleaned.get("activeIngredients") or []) + (cleaned.get("inactiveIngredients") or []))
    return found


@pytest.mark.parametrize(
    "pid,expected",
    [
        # Garden of Life Vitamin Code Perfect Weight
        (67354, {"organic Vitex negundo": "nirgundi"}),
        # Airborne Kids Mixed Berry
        (64228, {"Vitex trifolia": "vitex"}),
    ],
)
def test_vitex_labels_resolve_to_their_species_record(normalizer, pid, expected):
    raw = json.loads((FIXTURES / f"vitex_species_{pid}_raw.json").read_text())
    assert _vitex_rows(normalizer.normalize_product(raw)) == expected


def test_each_vitex_record_names_one_species():
    records = _records()
    species = {"chaste_tree": "agnus-castus", "vitex": "trifolia", "nirgundi": "negundo"}
    for record_id, epithet in species.items():
        record = records[record_id]
        assert record["latin_name"].lower() == f"vitex {epithet}", record_id
        others = [other for other in species.values() if other != epithet]
        for text in [record["notes"]] + record["aliases"]:
            named = [other for other in others if f"vitex {other}" in text.lower()]
            assert not named or record_id == "vitex" and text == record["notes"], (record_id, text)


def test_vitex_does_not_carry_the_agnus_castus_cui():
    """C0752339 is Vitex agnus castus (NCIt C72243 UMLS_CUI, checked
    2026-09-26); no V. trifolia concept exists there, so vitex carries none."""
    records = _records()
    assert records["chaste_tree"]["cui"] == "C0752339"
    assert records["vitex"]["cui"] is None


def test_milk_thistle_notes_match_its_seed_unii():
    record = _records()["milk_thistle"]
    assert record["external_ids"]["unii"] == "U946SH95EE"
    assert "whole herb" not in record["notes"].lower()
    assert "seed" in record["notes"].lower()
