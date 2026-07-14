"""One malformed active row cannot erase unrelated RDA/UL evidence (H6)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from enrich_supplements_v3 import SupplementEnricherV3


@pytest.fixture(scope="module")
def enricher() -> SupplementEnricherV3:
    return SupplementEnricherV3()


def test_malformed_active_row_does_not_discard_valid_rda_result(enricher) -> None:
    product = {
        "activeIngredients": [
            {
                "name": "Vitamin C",
                "standardName": "Vitamin C",
                "canonical_id": "vitamin_c",
                "quantity": 90,
                "unit": "mg",
                "dailyValue": 100,
            },
            "malformed row",
        ],
        "inactiveIngredients": [],
    }

    result = enricher._collect_rda_ul_data(
        product,
        min_servings_per_day=1,
        max_servings_per_day=1,
    )

    assert result["count"] == 1
    assert result["adequacy_results"][0]["nutrient"] == "Vitamin C"
    assert result["adequacy_results"][0]["amount"] == pytest.approx(90)
