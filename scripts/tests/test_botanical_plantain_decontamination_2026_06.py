"""Plantain (Plantago major) must not be conflated with banana (Musa × paradisiaca).

The botanical_ingredients.json 'plantain' entry IS common plantain, the medicinal
herb — verified live 2026-06-22: CUI C0032094 = "Plantago major", correct UNII
W2469WNO6U = "PLANTAGO MAJOR WHOLE". It had been contaminated with banana fields:
aliases 'musa paradisiaca'/'cooking banana', category 'fruit', and banana's
UNII I4U55R240N ("Musa × paradisiaca whole") + matching GSRS substance_name.

These lock the decontamination: banana out, Plantago major in, label coverage
added so 'Plantain leaf/whole herb extract' resolves to the herb identity.
"""
import json
import os

import pytest

BOT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "botanical_ingredients.json")


@pytest.fixture(scope="module")
def plantain():
    with open(BOT_PATH, encoding="utf-8") as fh:
        data = json.load(fh)
    for entry in data["botanical_ingredients"]:
        if entry.get("id") == "plantain":
            return entry
    pytest.fail("plantain entry not found in botanical_ingredients.json")


def test_plantain_aliases_have_no_banana(plantain):
    al = {a.lower() for a in plantain.get("aliases", [])}
    assert "musa paradisiaca" not in al, "banana alias must be removed from Plantago major"
    assert "cooking banana" not in al, "banana alias must be removed from Plantago major"


def test_plantain_identity_preserved_and_labels_covered(plantain):
    al = {a.lower() for a in plantain.get("aliases", [])}
    assert plantain["latin_name"] == "Plantago major"
    assert plantain["cui"] == "C0032094"          # verified "Plantago major"
    # the real unmapped labels now resolve to this herb identity
    assert "plantain leaf extract" in al
    assert "plantain whole herb extract" in al


def test_plantain_identifiers_are_plantago_not_banana(plantain):
    assert plantain["external_ids"]["unii"] == "W2469WNO6U"   # PLANTAGO MAJOR WHOLE
    assert plantain["external_ids"]["unii"] != "I4U55R240N"   # NOT Musa × paradisiaca
    assert plantain["gsrs"]["substance_name"] == "PLANTAGO MAJOR WHOLE"
    assert plantain.get("category") == "herb"
