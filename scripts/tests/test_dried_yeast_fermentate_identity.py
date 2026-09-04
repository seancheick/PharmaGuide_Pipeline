"""One exact generic preparation owner; no borrowed brand or live-yeast credit."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scoring_input_contract import get_scoring_ingredients


@pytest.fixture(scope="module")
def enricher():
    from enrich_supplements_v3 import SupplementEnricherV3

    return SupplementEnricherV3()


@pytest.mark.parametrize("literal", [
    "dried Yeast Fermentate", "yeast fermentate, dried", "yeast fermentate dried",
])
def test_generic_dried_label_keeps_one_preparation_owner(enricher, literal: str) -> None:
    registry = enricher._current_canonical_identity_registry()
    assert registry.resolve_verified_preferred(literal) == (
        "NHA_YEAST_FERMENTATE_DRIED", "other_ingredients",
    )
    row = {
        "name": literal, "raw_source_text": literal,
        "raw_source_path": "ingredientRows[11]", "standardName": "Yeast Fermentate",
        "canonical_id": "yeast_fermentate", "canonical_source_db": "ingredient_quality_map",
        "ingredientGroup": "Saccharomyces cerevisiae", "quantity": 500.0, "unit": "mg",
        "forms": [], "source_section": "active", "cleaner_row_role": "active_scorable",
        "score_eligible_by_cleaner": True, "ingredientId": 151706,
    }
    product, issues = enricher.enrich_product({
        "id": "airborne-generic-fermentate", "fullName": "Beta-Immune Booster",
        "activeIngredients": [row], "inactiveIngredients": [],
    })
    assert product, issues
    quality_row = product["ingredient_quality_data"]["ingredients"][0]
    assert quality_row["canonical_id"] == "NHA_YEAST_FERMENTATE_DRIED"
    assert quality_row["source_label_name"] == literal
    scoring = get_scoring_ingredients(product, strict=True)
    assert scoring.unmapped_count == 0
    assert scoring.mapped_coverage == 1.0
    assert len(scoring.rows) == 1
    source = scoring.rows[0]
    assert source["canonical_id"] == "nha_yeast_fermentate_dried"
    assert source["name"] == literal
    assert source["quantity"] == 500.0
    assert source["unit"] == "mg"
    assert source["raw_source_path"] == "ingredientRows[11]"
    assert row["forms"] == []
    assert product["probiotic_data"] == {"is_probiotic_product": False}
    assert product["evidence_data"]["clinical_matches"] == []
    assert not any(item.get("botanical_id") == "epicor" for item in
                   product["formulation_data"]["standardized_botanicals"])


def test_generic_fermentate_does_not_cite_spirulina_or_claim_branded_efficacy() -> None:
    data = json.loads((Path(__file__).parents[1] / "data/ingredient_quality_map.json").read_text())
    form = data["yeast_fermentate"]["forms"]["yeast fermentate (unspecified)"]
    assert "19298191" not in json.dumps(data["yeast_fermentate"])
    assert "reduced cold/flu" not in form["notes"]
    assert form["bio_score"] == 5
    assert form["score"] == 8
