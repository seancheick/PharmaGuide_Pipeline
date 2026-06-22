"""Anti-regression guards for botanical-identity separations.

These lock CURRENT-CORRECT behavior verified 2026-06-22: none of these plain
botanical labels currently collapse onto an isolated marker or a neighbouring
plant's IQM identity. Each assertion guards against a *specific* documented
mis-mapping risk, NOT against the label being recognized at all — so adding a
legitimate identity-only botanical entry later (e.g. ``Plantago major`` for
plantain) keeps these green; only a marker/neighbor collapse turns them red.

Risks guarded (from the unmapped-actives review):
  - Plantain leaf/whole-herb  must NOT become IQM ``aucubin`` (isolated marker).
  - Passion fruit             must NOT become ``passionflower`` or ``vitexin``.
  - Perilla aerial part       must NOT become ``perilla_oil``.
  - Black rice                must NOT become ``anthocyanins``.
Plus a promotion guard: a plant-part label alone (without the cleaner's
``active_misfiled_in_inactive`` flag) must not be promoted into scoring.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from enhanced_normalizer import EnhancedDSLDNormalizer
from enrich_supplements_v3 import SupplementEnricherV3


@pytest.fixture(scope="module")
def normalizer():
    return EnhancedDSLDNormalizer()


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3()


@pytest.mark.parametrize(
    "label,forbidden",
    [
        ("Plantain leaf extract", "aucubin"),
        ("Plantain Whole Herb Extract", "aucubin"),
        ("Passion Fruit Extract", "passionflower"),
        ("Passion Fruit Extract", "vitexin"),
        ("Passion Fruit Extract", "isovitexin"),
        # label carries no "oil"; any collapse onto a perilla *oil* form introduces it
        ("Perilla Aerial Part Extract", "oil"),
        ("Perilla aerial part", "oil"),
        ("Black Rice extract", "anthocyanin"),
        ("Black Rice Extract", "anthocyanin"),
    ],
)
def test_botanical_label_does_not_collapse_to_marker_or_neighbor(normalizer, label, forbidden):
    standard_name, _mapped, _ = normalizer._enhanced_ingredient_mapping(label, [])
    assert forbidden not in str(standard_name).lower(), (
        f"{label!r} resolved to {standard_name!r} which contains forbidden "
        f"identity token {forbidden!r}"
    )


def test_plant_part_text_alone_does_not_promote_to_scorable(enricher):
    """Rule D product-type rescue requires the cleaner to have flagged the row as
    an active misfiled into inactives. A bare plant-part label (no such flag)
    must never be promoted into scoring on the strength of the word 'leaf' alone.
    """
    quality_map = enricher.databases["ingredient_quality_map"]
    botanicals_db = enricher.databases["standardized_botanicals"]
    ingredient = {"name": "Plantain leaf extract", "quantity": 100, "unit": "mg"}
    assert (
        enricher._should_promote_to_scorable(ingredient, quality_map, botanicals_db, 0)
        is None
    )
