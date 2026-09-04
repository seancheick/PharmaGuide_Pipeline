"""Commercial nonviable mixture identity is not live strain or constituent mass."""

from __future__ import annotations

from copy import deepcopy

import pytest

from scoring_input_contract import get_scoring_ingredients


@pytest.fixture(scope="module")
def enricher():
    from enrich_supplements_v3 import SupplementEnricherV3

    return SupplementEnricherV3()


def _preparation_row() -> dict:
    return {
        "name": "Immuno-LP20", "raw_source_text": "Immuno-LP20",
        "standardName": "Lactobacillus plantarum", "canonical_id": "lactobacillus_plantarum",
        "canonical_source_db": "ingredient_quality_map",
        "ingredientGroup": "Lactobacillus plantarum", "raw_source_path": "ingredientRows[3]",
        "quantity": 50.0, "unit": "mg", "ingredientId": 269875,
        "forms": [{"name": "Lactobacillus plantarum L-137", "prefix": "tyndallized",
                   "ingredientId": 124789, "category": "bacteria",
                   "ingredientGroup": "Lactobacillus plantarum", "percent": None}],
        "source_section": "active", "cleaner_row_role": "active_scorable",
        "score_eligible_by_cleaner": True,
    }


def test_immuno_lp20_resolves_the_commercial_mixture_only(enricher) -> None:
    registry = enricher._current_canonical_identity_registry()
    owner = ("NHA_IMMUNO_LP20", "other_ingredients")
    assert registry.resolve_verified_preferred("Immuno-LP20") == owner
    for different in ("HK L-137", "Lactobacillus plantarum L-137", "Lactobacillus plantarum", "dextrin"):
        assert registry.resolve_preferred(different) != owner
    entry = next(row for row in enricher.databases["other_ingredients"]["other_ingredients"]
                 if row["id"] == owner[0])
    assert entry["external_ids"] == {}
    assert not {"bio_score", "score", "cfu", "clinical_studies"}.intersection(entry)


@pytest.mark.parametrize("processing", ["tyndallized", "heat-killed", "heat-treated"])
def test_immuno_lp20_keeps_50_mg_without_inventing_constituent_or_cfu(enricher, processing: str) -> None:
    source = _preparation_row()
    source["forms"][0]["prefix"] = processing
    product, issues = enricher.enrich_product({
        "id": "immuno-lp20-label", "fullName": "Immune preparation",
        "activeIngredients": [deepcopy(source)], "inactiveIngredients": [],
    })
    assert product, issues
    row = product["ingredient_quality_data"]["ingredients"][0]
    assert row["canonical_id"] == "NHA_IMMUNO_LP20"
    assert row["source_label_name"] == "Immuno-LP20"
    assert row["label_display_form"] == f"{processing} Lactobacillus plantarum L-137"
    scoring = get_scoring_ingredients(product, strict=True)
    assert scoring.unmapped_count == 0
    assert scoring.mapped_coverage == 1.0
    assert len(scoring.rows) == 1
    assert scoring.rows[0]["canonical_id"] == "nha_immuno_lp20"
    assert scoring.rows[0]["quantity"] == 50.0
    assert scoring.rows[0]["unit"] == "mg"
    assert scoring.rows[0]["raw_source_path"] == "ingredientRows[3]"
    assert product["activeIngredients"][0]["forms"] == source["forms"]
    assert product["probiotic_data"] == {"is_probiotic_product": False}
    assert product["evidence_data"]["clinical_matches"] == []


def test_preparation_does_not_erase_an_independent_live_probiotic(enricher) -> None:
    live = {"name": "Bacillus coagulans", "ingredientGroup": "Bacillus coagulans",
            "canonical_id": "bacillus_coagulans", "category": "probiotic",
            "raw_source_path": "ingredientRows[2].nestedRows[0]",
            "quantity": 1_000_000_000, "unit": "CFU", "forms": []}
    result = enricher._collect_probiotic_data({"activeIngredients": [_preparation_row(), live]})
    assert result["is_probiotic_product"] is True
    assert result["total_strain_count"] == 1
    assert result["total_cfu"] == 1_000_000_000
    assert result["probiotic_blends"][0]["strains"] == ["Bacillus coagulans"]


@pytest.mark.parametrize("taxonomy", ["TBD", None])
@pytest.mark.parametrize("processing", ["tyndallized", "heat-killed", "heat-treated"])
def test_literal_preparation_and_own_form_do_not_require_resolved_taxonomy(
    enricher, taxonomy: str | None, processing: str,
) -> None:
    # Doctor's Best 82408 prints the same 50 mg preparation as Garden 241325,
    # but DSLD supplies TBD instead of an organism in ingredientGroup.
    source = _preparation_row()
    source["ingredientGroup"] = taxonomy
    source["forms"][0]["prefix"] = processing
    source["raw_taxonomy"] = {"ingredientGroup": taxonomy, "forms": deepcopy(source["forms"])}
    product, issues = enricher.enrich_product({
        "id": "immuno-unresolved-taxonomy", "fullName": "Daily Immune Complex",
        "activeIngredients": [deepcopy(source)], "inactiveIngredients": [],
    })
    assert product, issues
    quality = product["ingredient_quality_data"]["ingredients"][0]
    assert quality["canonical_id"] == "NHA_IMMUNO_LP20"
    assert quality["identity_disposition"] == "repaired"
    scoring = get_scoring_ingredients(product, strict=True)
    assert scoring.mapped_coverage == 1.0
    assert scoring.unmapped_count == 0
    assert [(row["quantity"], row["unit"]) for row in scoring.rows] == [(50.0, "mg")]
    assert product["activeIngredients"][0]["forms"] == source["forms"]
    assert product["probiotic_data"] == {"is_probiotic_product": False}


@pytest.mark.parametrize("taxonomy", ["TBD", None])
def test_unknown_preparation_still_conflicts_without_resolved_taxonomy(
    enricher, taxonomy: str | None,
) -> None:
    source = _preparation_row()
    source.update(name="Unverified immune preparation", raw_source_text="Unverified immune preparation",
                  ingredientGroup=taxonomy)
    product, _ = enricher.enrich_product({
        "id": "unknown-preparation", "fullName": "Unknown preparation",
        "activeIngredients": [source], "inactiveIngredients": [],
    })
    assert product["ingredient_quality_data"]["ingredients"][0]["identity_disposition"] == "identity_conflict"
    scoring = get_scoring_ingredients(product, strict=True)
    assert scoring.rows == []
    assert scoring.unmapped_count == 1
