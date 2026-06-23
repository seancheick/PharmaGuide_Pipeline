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
