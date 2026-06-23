"""Botanical identity-only alias batch (2026-06 unmapped triage).

Unmapped DSLD label forms whose botanical identity ALREADY exists in
botanical_ingredients.json — the bare name matched but the full label form
(genus only, or "organic ... Mushroom mycelium powder") did not. Added the
missing label aliases so they recognize as non-scorable botanical identity.

The collision check prevented duplicate entries: Lonicera (Lonicera japonica =
japanese_honeysuckle), Vijayasar (Pterocarpus marsupium = indian_kino_tree),
Enokitake, and Himematsutake were all already present — this is alias-only.

Deferred (NOT aliased): "Chinese Vitex" is Vitex negundo/rotundifolia, a
different species from chaste_tree (V. agnus-castus) — no cross-species alias.
"Red Currant Fruit Extract" is genuinely new and needs a verified CUI entry.
"""
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
        ("Tropical Almond", "tropical_almond"),               # new: Terminalia catappa (C0971878)
    ],
)
def test_botanical_label_recognized_as_identity(enricher, label, expected_id):
    r = enricher._is_recognized_non_scorable(label, label)
    assert r is not None and r.get("matched_entry_id") == expected_id, (
        f"{label!r} should recognize as {expected_id!r} (non-scorable botanical); got {r}"
    )
