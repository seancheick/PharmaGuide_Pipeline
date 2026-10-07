"""Standardized botanicals match the identity the cleaner already resolved.

2026-09-16 silent-empty audit: "Amla Extract (40% Tannins)" (DSLD 253714)
shipped formulation_data.standardized_botanicals=[] because the collector
re-matched the raw row name ("Amla extract") against its own alias list while
the cleaner had already resolved the row to canonical_id "amla" — the same id
the standardized_botanicals entry uses. All 69 ids shared by
standardized_botanicals.json and ingredient_quality_map.json were checked to
name the same substance.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from enrich_supplements_v3 import SupplementEnricherV3


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3()


def _amla_product(canonical_id="amla", canonical_source_db="ingredient_quality_map"):
    return {
        "id": "253714",
        "fullName": "Amla Extract (40% Tannins)",
        "activeIngredients": [{
            "name": "Amla extract",
            "standardName": "Amla (Phyllanthus emblica)",
            "raw_source_text": "Amla extract",
            "canonical_id": canonical_id,
            "canonical_source_db": canonical_source_db,
            "raw_category": "botanical",
            "cleaner_row_role": "active_scorable",
            "score_eligible_by_cleaner": True,
            "quantity": 1000,
            "unit": "mg",
            "raw_source_path": "ingredientRows[0]",
            "notes": "",
        }],
        "inactiveIngredients": [],
        "statements": [],
    }


def test_resolved_identity_finds_the_standardized_botanical(enricher):
    found = enricher._collect_standardized_botanicals(_amla_product())
    assert [row["botanical_id"] for row in found] == ["amla"]
    assert found[0]["percentage_found"] == 40
    assert found[0]["meets_threshold"] is True


def test_identity_from_another_catalog_is_not_trusted(enricher):
    product = _amla_product(canonical_source_db="other_ingredients")
    assert enricher._collect_standardized_botanicals(product) == []


@pytest.mark.parametrize("notes", [
    "standardized to 5% ocimum bioactive complex",
    "standardized to 5% unspecified compounds",
    "standardized to 5% unrelated marker",
])
def test_unmatched_marker_percentage_cannot_satisfy_authored_marker_threshold(enricher, notes):
    product = {"activeIngredients": [{
        "name": "Holixer", "standardName": "Holy Basil", "notes": notes,
        "canonical_id": "holy_basil", "canonical_source_db": "ingredient_quality_map",
        "quantity": 250, "unit": "mg",
    }]}
    found = enricher._collect_standardized_botanicals(product)
    assert len(found) == 1
    assert found[0]["percentage_found"] == 0
    assert found[0]["meets_threshold"] is False


def test_explicit_authored_marker_percentage_retains_credit(enricher):
    product = {"activeIngredients": [{
        "name": "Holy Basil Extract", "notes": "standardized to 2.5% ursolic acid",
        "canonical_id": "holy_basil", "canonical_source_db": "ingredient_quality_map",
    }]}
    found = enricher._collect_standardized_botanicals(product)
    assert found[0]["percentage_found"] == 2.5
    assert found[0]["meets_threshold"] is True
