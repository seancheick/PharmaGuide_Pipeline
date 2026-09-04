"""Source preparations must not inherit live-organism identity from taxonomy."""

from __future__ import annotations

from copy import deepcopy

import pytest

from identity_integrity import normalize_label_display, resolve_identity
from scoring_input_contract import _has_probiotic_identity_text
from supplement_taxonomy import _row_has_probiotic_identity


def _yeast_extract_row() -> dict:
    """Minimal cleaned label boundary from Jarrow DSLD 264610, not a remap."""
    return {
        "name": "Saccharomyces cerevisiae extract",
        "raw_source_text": "Saccharomyces cerevisiae extract",
        "raw_source_path": "ingredientRows[0]",
        "standardName": "Brewer's Yeast",
        "canonical_id": "brewers_yeast",
        "canonical_source_db": "ingredient_quality_map",
        "ingredientGroup": "Saccharomyces boulardii ",
        "quantity": 250.0,
        "unit": "mg",
        "dose_class": "therapeutic_mass",
        "source_section": "active",
        "cleaner_row_role": "active_scorable",
        "score_eligible_by_cleaner": True,
        "forms": [{
            "prefix": "providing at least",
            "name": "long, branched Beta 1,3/Beta 1,6 Glucans",
            "percent": 75,
            "category": "fiber",
            "ingredientGroup": "Beta Glucans",
        }],
    }


@pytest.fixture(scope="module")
def enricher():
    from enrich_supplements_v3 import SupplementEnricherV3

    return SupplementEnricherV3()


def _organism_resolver(value: str) -> str | None:
    return {
        "saccharomyces cerevisiae": "brewers_yeast",
        "saccharomyces boulardii": "saccharomyces_boulardii",
    }.get(normalize_label_display(value).casefold())


def test_extract_literal_blocks_taxonomy_repair_and_preserves_label() -> None:
    row = _yeast_extract_row()
    decision = resolve_identity(
        row, "brewers_yeast", _organism_resolver, taxonomy_coherent=True,
    )

    assert decision.disposition == "identity_conflict"
    assert decision.canonical_id is None
    assert decision.scoreable_identity is False
    assert decision.source_label_name == row["raw_source_text"]
    assert decision.label_display_name == row["raw_source_text"]
    assert decision.source_label_form == (
        "providing at least long, branched Beta 1,3/Beta 1,6 Glucans"
    )


def test_real_extract_boundary_is_quarantined_without_probiotic_route(enricher) -> None:
    from scoring_v4.scored_artifact import build_scored_artifact

    product = {
        "id": "label-boundary-fixture",
        "fullName": "Beta Glucan",
        "activeIngredients": [_yeast_extract_row()],
        "inactiveIngredients": [],
    }
    product["ingredient_quality_data"] = enricher._collect_ingredient_quality_data(product)
    product["probiotic_data"] = enricher._collect_probiotic_data(product)
    enricher.apply_taxonomy_projection(product)

    iqd = product["ingredient_quality_data"]
    assert not iqd["ingredients_scorable"]
    assert iqd["ingredients_skipped"][0]["identity_disposition"] == "identity_conflict"
    assert iqd["ingredients_skipped"][0]["canonical_id"] is None
    assert product["activeIngredients"][0]["name"] == "Saccharomyces cerevisiae extract"
    assert product["probiotic_data"] == {"is_probiotic_product": False}
    assert product["primary_type"] != "probiotic"
    artifact = build_scored_artifact(product)
    assert artifact["_v4_module"] != "probiotic"
    assert artifact["quality_score_status"] == "not_scored"


@pytest.mark.parametrize("name,form", [
    ("Saccharomyces cerevisiae extract", None),
    ("Lactobacillus acidophilus lysate", None),
    ("yeast hydrolysate", None),
    ("L. acidophilus lysate", None),
    ("B. lactis heat-inactivated", None),
    ("Saccharomyces cerevisiae", "cell wall fragments"),
    ("Saccharomyces cerevisiae", "extract"),
    ("Saccharomyces boulardii", "heat-inactivated"),
    ("Saccharomyces boulardii", "heat-killed cells"),
    ("Saccharomyces cerevisiae", "long, branched Beta 1,3/Beta 1,6 Glucans"),
])
@pytest.mark.parametrize("raw_forms", [False, True])
def test_derivative_evidence_is_shared_across_identity_consumers(
    enricher, name: str, form: str | None, raw_forms: bool,
) -> None:
    row = {**_yeast_extract_row(), "name": name, "raw_source_text": name,
           "category": "probiotic", "forms": [{"name": form}] if form else []}
    if raw_forms:
        row["raw_taxonomy"] = {"forms": row.pop("forms")}

    assert _row_has_probiotic_identity(row) is False
    assert _has_probiotic_identity_text(row) is False
    assert enricher._has_probiotic_identity_text(row) is False
    assert enricher._collect_probiotic_data({"activeIngredients": [row]}) == {
        "is_probiotic_product": False,
    }


@pytest.mark.parametrize("name,canonical", [
    ("Saccharomyces boulardii", "saccharomyces_boulardii"),
    ("Saccharomyces cerevisiae", "brewers_yeast"),
])
@pytest.mark.parametrize("unrelated_form", ["rice bran extract", "whey hydrolysate"])
def test_live_yeast_owned_dose_survives_unrelated_extracts(
    enricher, name: str, canonical: str, unrelated_form: str,
) -> None:
    live = {
        "name": name, "raw_source_text": name, "ingredientGroup": name,
        "canonical_id": canonical, "category": "probiotic",
        "raw_source_path": "ingredientRows[0]", "quantity": 5_000_000_000,
        "unit": "CFU", "forms": [{"name": unrelated_form}],
    }
    decision = resolve_identity(live, canonical, _organism_resolver)
    assert decision.disposition == "clean"
    assert decision.canonical_id == canonical
    assert _row_has_probiotic_identity(live) is True
    assert _has_probiotic_identity_text(live) is True
    assert enricher._has_probiotic_identity_text(live) is True
    result = enricher._collect_probiotic_data({
        "activeIngredients": [live], "inactiveIngredients": [_yeast_extract_row()],
    })
    assert result["is_probiotic_product"] is True
    assert result["total_strain_count"] == 1
    assert result["total_cfu"] == 5_000_000_000


@pytest.mark.parametrize("forms", [False, True])
def test_nonlive_blend_component_is_not_counted_as_a_strain(enricher, forms: bool) -> None:
    extract = _yeast_extract_row()
    extract["raw_source_path"] = "ingredientRows[0].nestedRows[0]"
    owner = {
        "name": "Probiotic Blend", "raw_source_path": "ingredientRows[0]",
        "cleaner_row_role": "blend_header_total", "quantity": 5_000_000_000,
        "unit": "CFU", "forms" if forms else "nestedIngredients": [extract],
    }
    assert enricher._collect_probiotic_data({"activeIngredients": [owner]}) == {
        "is_probiotic_product": False,
    }

    mixed = deepcopy(owner)
    mixed["forms" if forms else "nestedIngredients"].append({
        "name": "Saccharomyces boulardii", "category": "probiotic",
        "raw_source_path": "ingredientRows[0].nestedRows[1]",
    })
    result = enricher._collect_probiotic_data({"activeIngredients": [mixed]})
    assert result["is_probiotic_product"] is True
    assert result["total_strain_count"] == 1
    assert result["probiotic_blends"][0]["strains"] == ["Saccharomyces boulardii"]
    assert result["strain_allocation_owner_refs"] == []
    assert all(row["cfu_per_day"] is None for row in result["clinical_strains"])


@pytest.mark.parametrize("normalized_name", ["Saccharomyces cerevisiae extract", "Beta Glucan"])
def test_guessed_preparation_from_candidate_resolver_is_not_literal_proof(
    enricher, normalized_name: str,
) -> None:
    row = {**_yeast_extract_row(), "name": normalized_name,
           "ingredientGroup": "Saccharomyces cerevisiae"}

    def broad_resolver(value: str) -> str:
        if normalize_label_display(value).casefold() == "saccharomyces cerevisiae":
            return "brewers_yeast"
        return "beta_glucan"

    decision = resolve_identity(
        row, "beta_glucan", broad_resolver,
        canonical_registry=enricher._current_canonical_identity_registry(),
    )
    assert decision.disposition == "identity_conflict"
    assert decision.canonical_id is None
    assert decision.scoreable_identity is False


def test_alternate_taxonomy_cannot_replace_unverified_preparation() -> None:
    row = {**_yeast_extract_row(), "name": "Yeast Fermentate",
           "raw_source_text": "Yeast Fermentate",
           "alternateNames": ["Saccharomyces cerevisiae"], "forms": []}
    row.pop("ingredientGroup")

    def resolver(value: str) -> str | None:
        return {"yeast fermentate": "yeast_fermentate",
                "saccharomyces cerevisiae": "brewers_yeast"}.get(
            normalize_label_display(value).casefold()
        )

    decision = resolve_identity(row, "yeast_fermentate", resolver)
    assert decision.disposition == "identity_conflict"
    assert decision.canonical_id is None


@pytest.mark.parametrize("literal", [
    "Yeast Fermentate", "Saccharomyces cerevisiae fermentate", "yeast hydrolysate",
])
@pytest.mark.parametrize("alternate_only", [False, True])
def test_existing_exact_preparation_keeps_its_identity_over_source_taxonomy(
    enricher, literal: str, alternate_only: bool,
) -> None:
    row = {
        **_yeast_extract_row(), "name": literal,
        "raw_source_text": literal, "standardName": "Yeast Fermentate",
        "canonical_id": "yeast_fermentate", "ingredientGroup": "Saccharomyces cerevisiae",
        "forms": [],
    }
    if alternate_only:
        row["alternateNames"] = [row.pop("ingredientGroup")]
    result = enricher._collect_ingredient_quality_data({"activeIngredients": [row]})
    assert len(result["ingredients_scorable"]) == 1
    assert result["ingredients_scorable"][0]["canonical_id"] == "yeast_fermentate"
    assert result["ingredients_scorable"][0]["source_label_name"] == literal


@pytest.mark.parametrize("alternate_only", [False, True])
def test_ambiguous_preparation_alias_does_not_override_source_taxonomy(
    enricher, alternate_only: bool,
) -> None:
    literal = "dried yeast fermentate"
    registry = enricher._current_canonical_identity_registry()
    assert registry.resolve_verified_preferred(literal) is None
    row = {
        **_yeast_extract_row(), "name": literal, "raw_source_text": literal,
        "standardName": "Yeast Fermentate", "canonical_id": "yeast_fermentate",
        "ingredientGroup": "Saccharomyces cerevisiae", "forms": [],
    }
    if alternate_only:
        row["alternateNames"] = [row.pop("ingredientGroup")]

    result = enricher._collect_ingredient_quality_data({"activeIngredients": [row]})
    assert result["ingredients_scorable"] == []
    assert result["ingredients_skipped"][0]["identity_disposition"] == "identity_conflict"
    assert result["ingredients_skipped"][0]["canonical_id"] is None
    assert result["ingredients_skipped"][0]["source_label_name"] == literal


def test_real_source_owned_cerevisiae_active_culture_dose_is_retained(enricher) -> None:
    # One source row from GNC 206322, retaining its printed NP quantity and
    # own culture statement rather than assigning product/blend totals.
    name = "Saccharomyces cerevisiae subsp. boulardii (CNCM-I-1079)"
    row = {
        "name": name, "raw_source_text": name, "standardName": "Brewer's Yeast",
        "ingredientGroup": "Saccharomyces cerevisiae", "canonical_id": "brewers_yeast",
        "quantity": 0.0, "unit": "NP", "raw_source_path": "ingredientRows[7]",
        "harvestMethod": "1 billion active cultures",
        "notes": name + " Genus: Saccharomyces Species: cerevisiae "
                 "SubSpecies: boulardii Note: 1 billion active cultures ",
    }
    result = enricher._collect_probiotic_data({"activeIngredients": [row]})
    assert result["is_probiotic_product"] is True
    assert result["total_cfu"] == 1_000_000_000
    assert result["probiotic_blends"][0]["cfu_data"]["raw_source_path"] == "ingredientRows[7]"
    assert result["probiotic_blends"][0]["strains"] == [name]
