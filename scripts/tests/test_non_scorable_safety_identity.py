"""US-unlawful supplement identities retain identity but never enter IQM scoring (H9)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from enrich_supplements_v3 import SupplementEnricherV3


@pytest.fixture(scope="module")
def enricher() -> SupplementEnricherV3:
    return SupplementEnricherV3()


def _row(
    name: str,
    canonical_id: str | None = None,
    *,
    canonical_source_db: str | None = None,
) -> dict:
    row = {
        "name": name,
        "raw_source_text": name,
        "standardName": name,
        "quantity": 25,
        "unit": "mg",
        "score_eligible_by_cleaner": True,
    }
    if canonical_id is not None:
        row["canonical_id"] = canonical_id
    if canonical_source_db is not None:
        row["canonical_source_db"] = canonical_source_db
    return row


def test_cbd_identity_is_retained_but_not_scorable(enricher) -> None:
    result = enricher._collect_ingredient_quality_data({
        "activeIngredients": [_row("CBD (Cannabidiol)")],
        "inactiveIngredients": [],
    })

    assert result["ingredients_scorable"] == []
    skipped = result["ingredients_recognized_non_scorable"][0]
    assert skipped["canonical_id"] is None
    assert skipped["canonical_source_db"] == "unmapped"
    assert skipped["scoreable_identity"] is False
    assert skipped["recognized_entry_id"] == "BANNED_CBD_US"
    assert skipped["safety_identity_id"] == "BANNED_CBD_US"
    assert skipped["identity_decision_reason"] == "safety_recognition_without_primary_identity"


def test_hemp_seed_oil_negative_term_is_not_treated_as_cbd(enricher) -> None:
    result = enricher._collect_ingredient_quality_data({
        "activeIngredients": [_row(
            "Hemp Seed Oil",
            "hemp_seed_oil",
            canonical_source_db="ingredient_quality_map",
        )],
        "inactiveIngredients": [],
    })

    assert result["ingredients_scorable"]
    assert result["ingredients_scorable"][0]["canonical_id"] == "hemp_seed_oil"
    assert result["ingredients_scorable"][0]["canonical_source_db"] == "ingredient_quality_map"
