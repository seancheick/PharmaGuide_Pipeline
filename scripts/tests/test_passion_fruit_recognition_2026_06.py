"""Passion fruit must not be falsely recognized as passionflower (2026-06).

Found by Codex adversarial review. The enricher's _is_recognized_non_scorable
fuzzy-matched 'Passion Fruit Extract' (Passiflora edulis, the fruit) to
NHA_PASSIONFLOWER_EXTRACT (Passiflora incarnata, the calming herb) because
'passion fruit' ≈ 'passion flower'. The normalizer/IQM path left it unmapped, so
the earlier separation guard (which only tested that path) missed it.

Fix: give passion fruit its own exact identity (botanical_ingredients passion_fruit,
Passiflora edulis, CUI C0553350 verified) so the O(1) exact recognition lookup
preempts the fuzzy passionflower match. Also decontaminate the passionflower entry,
which carried passion fruit's UNII (SY49TH8VUA = "PASSIFLORA EDULIS FLOWER") and
GSRS — corrected to the verified incarnata UNII CLF5YFS11O.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from enrich_supplements_v3 import SupplementEnricherV3

DATA = os.path.join(os.path.dirname(__file__), "..", "data")


def _by_id(filename, *list_keys):
    with open(os.path.join(DATA, filename), encoding="utf-8") as fh:
        d = json.load(fh)
    lst = d if isinstance(d, list) else next(
        (d[k] for k in list_keys if isinstance(d.get(k), list)),
        next((v for v in d.values() if isinstance(v, list)), []),
    )
    return {e["id"]: e for e in lst if isinstance(e, dict) and "id" in e}


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3()


@pytest.fixture(scope="module")
def botanicals():
    return _by_id("botanical_ingredients.json", "botanical_ingredients")


@pytest.fixture(scope="module")
def other_ingredients():
    return _by_id("other_ingredients.json", "other_ingredients", "ingredients")


@pytest.mark.parametrize("label", ["Passion Fruit Extract", "passion fruit extract", "Passion Fruit"])
def test_passion_fruit_not_recognized_as_passionflower(enricher, label):
    r = enricher._is_recognized_non_scorable(label, label)
    assert r is not None, f"{label!r} should be recognized (as passion fruit)"
    assert r.get("matched_entry_id") != "NHA_PASSIONFLOWER_EXTRACT", (
        f"{label!r} falsely matched the passionflower entry: {r}"
    )
    assert "passionflower" not in str(r.get("matched_entry_name", "")).lower()


@pytest.mark.parametrize("label", ["Passionflower Extract", "Passiflora incarnata extract"])
def test_real_passionflower_still_recognized(enricher, label):
    r = enricher._is_recognized_non_scorable(label, label)
    assert r is not None and r.get("matched_entry_id") == "NHA_PASSIONFLOWER_EXTRACT"


def test_passion_fruit_entry_identity(botanicals):
    pf = botanicals["passion_fruit"]
    assert pf["latin_name"] == "Passiflora edulis"
    assert pf["cui"] == "C0553350"          # UMLS-verified plant concept


def test_passionflower_entry_decontaminated(other_ingredients):
    e = other_ingredients["NHA_PASSIONFLOWER_EXTRACT"]
    assert e["external_ids"]["unii"] == "CLF5YFS11O"          # Passiflora incarnata
    assert e["external_ids"]["unii"] != "SY49TH8VUA"          # NOT Passiflora edulis
    assert "EDULIS" not in e["gsrs"]["substance_name"].upper()
