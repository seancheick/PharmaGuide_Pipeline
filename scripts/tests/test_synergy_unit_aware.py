"""Synergy dose floors compare canonical mass units (H7)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from enrich_supplements_v3 import SupplementEnricherV3


@pytest.fixture(scope="module")
def enricher() -> SupplementEnricherV3:
    instance = SupplementEnricherV3()
    instance.databases["synergy_cluster"] = {
        "synergy_clusters": [
            {
                "id": "melatonin_floor",
                "standard_name": "Melatonin Floor",
                "ingredients": ["melatonin"],
                "canonical_ids": ["melatonin"],
                "min_effective_doses": {"melatonin": 0.5},
                "allow_single_ingredient": True,
                "primary_ingredients": ["melatonin"],
            }
        ]
    }
    return instance


def _product(quantity_mcg: float) -> dict:
    return {
        "name": "Melatonin test",
        "activeIngredients": [
            {
                "name": "Melatonin",
                "standardName": "Melatonin",
                "quantity": quantity_mcg,
                "unit": "mcg",
            }
        ],
    }


def test_500_micrograms_meets_half_milligram_floor(enricher) -> None:
    clusters = enricher._collect_synergy_data(_product(500))
    match = clusters[0]["matched_ingredients"][0]

    assert match["meets_minimum"] is True
    assert match["evaluated_quantity"] == pytest.approx(0.5)
    assert match["evaluated_unit"] == "mg"


def test_300_micrograms_does_not_meet_half_milligram_floor(enricher) -> None:
    clusters = enricher._collect_synergy_data(_product(300))
    assert clusters[0]["matched_ingredients"][0]["meets_minimum"] is False
