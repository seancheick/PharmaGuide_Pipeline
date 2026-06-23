"""Plant-part disambiguation guardrail (2026-06, Codex "broad plant-part" item).

A plant-part word must not collapse a label onto the wrong botanical identity.
Concrete verified case: 'plantain' is a homonym — Plantago major (a LEAF herb)
vs Musa x paradisiaca (the cooking-banana FRUIT). The enricher's recognition
fuzzy path was collapsing 'Plantain Fruit Extract' onto the Plantago herb.

Fix: give the banana/cooking-plantain its own exact identity (cooking_plantain,
Musa x paradisiaca, CUI C1039591 / UNII I4U55R240N — both live-verified) so the
O(1) exact recognition lookup preempts the fuzzy Plantago match.

KNOWN BROADER LIMITATION — deliberately NOT fixed here (recognition-DISPLAY only,
no scoring impact; needs corpus-validated design): the variant-stripping fallback
can still mis-recognize other cross-part labels (e.g. 'Apple Seed Extract' ->
apple puree, 'Cherry Bark Extract' -> cherry flavor, 'Rhubarb Leaf Extract' ->
rhubarb). A general plant-part-aware guard must NOT reject legit 'Ashwagandha
Root' / 'Pumpkin Seed' where the part is the standard one — so it is a scoped
follow-up, not a rushed edit into the recognition core.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from enrich_supplements_v3 import SupplementEnricherV3

BOT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "botanical_ingredients.json")


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3()


@pytest.fixture(scope="module")
def botanicals():
    with open(BOT_PATH, encoding="utf-8") as fh:
        data = json.load(fh)
    return {e["id"]: e for e in data["botanical_ingredients"]}


@pytest.mark.parametrize(
    "label",
    [
        "Plantain Fruit Extract",
        "Plantain Fruit",
        "Cooking Plantain",
        "Green Plantain Powder",
        "Plantain Flour",
        "Plantain Banana Extract",
    ],
)
def test_banana_plantain_not_recognized_as_plantago(enricher, label):
    r = enricher._is_recognized_non_scorable(label, label)
    assert r is not None, f"{label!r} should be recognized (as cooking plantain/banana)"
    assert r.get("matched_entry_id") == "cooking_plantain", (
        f"{label!r} should resolve to the Musa banana identity, got {r}"
    )
    assert r.get("matched_entry_id") != "plantain"   # NOT the Plantago herb


@pytest.mark.parametrize("label", ["Plantain Leaf Extract", "Plantain Whole Herb Extract"])
def test_herb_plantain_still_recognized_as_plantago(enricher, label):
    r = enricher._is_recognized_non_scorable(label, label)
    assert r is not None and r.get("matched_entry_id") == "plantain"


def test_cooking_plantain_entry_identity(botanicals):
    cp = botanicals["cooking_plantain"]
    assert cp["latin_name"] == "Musa x paradisiaca"
    assert cp["cui"] == "C1039591"                      # UMLS-verified Musa x paradisiaca
    assert cp["external_ids"]["unii"] == "I4U55R240N"   # GSRS-verified banana UNII


# ── cross-part disambiguation: the plant-part word must select the right identity ──
@pytest.mark.parametrize(
    "label,expected_id",
    [
        ("Cherry Bark Extract", "wild_cherry_bark"),      # was cherry FLAVOR
        ("Wild Cherry Bark Extract", "wild_cherry_bark"),
        ("Grape Leaf Extract", "grape_leaf"),             # was plain GRAPE
        ("Red Vine Leaf Extract", "grape_leaf"),
        ("Apple Seed Extract", "apple_seed"),             # was apple PUREE
        ("Rhubarb Leaf Extract", "rhubarb_leaf"),         # was rhubarb (root)
        ("Tomato Leaf Extract", "tomato_leaf"),           # was tomato (fruit)
    ],
)
def test_cross_part_label_resolves_to_correct_part(enricher, label, expected_id):
    r = enricher._is_recognized_non_scorable(label, label)
    assert r is not None and r.get("matched_entry_id") == expected_id, (
        f"{label!r} should resolve to {expected_id!r}, got {r}"
    )


def test_whole_plant_labels_not_falsely_rejected(enricher):
    """The additive disambiguation must NOT break legit whole-plant / standard-part
    labels — the reason we used identities instead of a recognition-core guard."""
    for label, expect in [
        ("Ashwagandha Root Extract", "ashwagandha"),
        ("Pumpkin Seed Extract", "pumpkin"),
        ("Grape Seed Extract", "grape_seed"),
        ("Rhubarb Root Extract", "rhubarb"),
    ]:
        r = enricher._is_recognized_non_scorable(label, label)
        assert r is not None and r.get("matched_entry_id") == expect, (
            f"{label!r} regressed to {r}"
        )


@pytest.mark.parametrize(
    "entry_id,cui,latin",
    [
        ("wild_cherry_bark", "C0330655", "Prunus serotina"),
        ("grape_leaf", "C0682492", "Vitis vinifera"),
        ("apple_seed", "C0330653", "Malus domestica"),
        ("rhubarb_leaf", "C1066370", "Rheum officinale"),
        ("tomato_leaf", "C1140676", "Solanum lycopersicum"),
    ],
)
def test_disambiguation_entries_verified_cui(botanicals, entry_id, cui, latin):
    e = botanicals[entry_id]
    assert e["cui"] == cui          # UMLS-verified 2026-06-22
    assert e["latin_name"] == latin
