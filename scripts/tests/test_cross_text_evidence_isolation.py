"""Ingredient delivery evidence cannot be borrowed from unrelated product text (H7)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from enrich_supplements_v3 import SupplementEnricherV3


@pytest.fixture(scope="module")
def enricher() -> SupplementEnricherV3:
    return SupplementEnricherV3()


def test_marketing_statement_cannot_synthesize_liposomal_delivery(enricher) -> None:
    result = enricher._collect_delivery_data({
        "activeIngredients": [{"name": "Vitamin C", "standardName": "Vitamin C"}],
        "statements": [{"notes": "Learn about liposomal delivery in our research library."}],
        "physicalState": {"langualCodeDescription": "Tablet"},
    })

    assert "liposomal" not in {system["name"] for system in result["systems"]}


def test_row_local_liposomal_label_evidence_is_retained(enricher) -> None:
    result = enricher._collect_delivery_data({
        "activeIngredients": [
            {"name": "Liposomal Vitamin C", "standardName": "Vitamin C"}
        ],
        "physicalState": {"langualCodeDescription": "Liquid"},
    })

    liposomal = next(system for system in result["systems"] if system["name"] == "liposomal")
    assert liposomal["match_source"] == "activeIngredients[0]"
