"""Botanical identity-only alias batch (2026-06 unmapped triage).

Unmapped DSLD label forms whose botanical identity ALREADY exists in
botanical_ingredients.json — the bare name matched but the full label form
(genus only, or "organic ... Mushroom mycelium powder") did not. Added the
missing label aliases so they recognize as non-scorable botanical identity.

The collision check prevented duplicate entries: Lonicera (Lonicera japonica =
japanese_honeysuckle), Vijayasar (Pterocarpus marsupium = indian_kino_tree),
Enokitake, and Himematsutake were all already present — this is alias-only.

Deferred (NOT aliased): bare "Tropical Almond" is ambiguous in DSLD. Current
labels use it inside Triphala contexts for Terminalia chebula/myrobalan, while
the common name can also mean Terminalia catappa. Keep it unmapped until a
context-specific routing decision is reviewed.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from enrich_supplements_v3 import SupplementEnricherV3


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3()


@pytest.mark.parametrize(
    "label,expected_id",
    [
        ("Lonicera", "japanese_honeysuckle"),
        ("Vijayasar", "indian_kino_tree"),
        ("organic Enokitake Mushroom", "enokitake"),
        ("organic Himematsutake Mushroom mycelium powder", "himematsutake"),
        ("Biolut(TM) Marigold Extract", "marigold"),  # branded marigold lutein extract -> marigold botanical (dose-aware)
        ("Chinese Vitex", "nirgundi"),                # Vitex negundo, alias to existing Nirgundi (same CUI C1643782)
        ("Red Currant Fruit Extract", "red_currant"),         # new: Ribes rubrum (C1201367)
        ("Muira Puama", "muira_puama"),
        ("Ellirose Hibiscus extract", "hibiscus_extract"),
        ("Excelery", "celery"),
        ("Barley extract", "barley_unspecified"),
        ("Barley powder", "barley_unspecified"),
        ("Wheat Germ Oil", "wheat_germ_oil"),
        ("Oat Fiber", "oat_generic"),
    ],
)
def test_botanical_label_recognized_as_identity(enricher, label, expected_id):
    r = enricher._is_recognized_non_scorable(label, label)
    assert r is not None and r.get("matched_entry_id") == expected_id, (
        f"{label!r} should recognize as {expected_id!r} (non-scorable botanical); got {r}"
    )


def test_tropical_almond_stays_unmapped_until_context_review(enricher):
    r = enricher._is_recognized_non_scorable("Tropical Almond", "Tropical Almond")
    assert r is None, (
        "Bare Tropical Almond should not be globally mapped: DSLD uses it in "
        "Triphala/Chebulic Myrobalan context, while the common name may also "
        "refer to Terminalia catappa."
    )


def test_muira_puama_bark_has_a_distinct_standard_name():
    path = os.path.join(
        os.path.dirname(__file__), "..", "data", "botanical_ingredients.json"
    )
    with open(path, encoding="utf-8") as handle:
        entries = json.load(handle)["botanical_ingredients"]

    names = {
        entry["id"]: entry["standard_name"]
        for entry in entries
        if entry.get("id") in {"muira_puama", "muira_puama_bark"}
    }
    assert names == {
        "muira_puama": "Muira Puama",
        "muira_puama_bark": "Muira Puama Bark",
    }
