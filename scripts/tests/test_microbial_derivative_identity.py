"""Source preparations must not inherit live-organism identity from taxonomy."""

from __future__ import annotations

from copy import deepcopy

import pytest

from identity_integrity import normalize_label_display, resolve_identity
from scoring_input_contract import _has_probiotic_identity_text, get_scoring_ingredients
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


def test_fermented_rice_preparation_is_not_an_organism_identity(enricher) -> None:
    """The shared cleaned label boundary on DSLD 311956/330490/330491."""
    row = {
        **_yeast_extract_row(), "name": "Red Yeast Rice extract",
        "raw_source_text": "Red Yeast Rice extract", "quantity": 600.0,
        "standardName": "Red Yeast Rice", "ingredientGroup": "Red Yeast Rice",
        "canonical_id": "red_yeast_rice", "canonical_source_db": "botanical_ingredients",
        "forms": [{"name": "Monascus purpureus Extract", "ingredientGroup": "Red Yeast"}],
    }
    registry = enricher._current_canonical_identity_registry()
    assert registry.resolve_verified_preferred(row["raw_source_text"]) == (
        "red_yeast_rice", "botanical_ingredients",
    )
    decision = resolve_identity(
        row, row["canonical_id"],
        enricher._identity_candidate_resolver(
            enricher.databases["ingredient_quality_map"], row["canonical_id"],
        ),
        canonical_registry=registry,
    )

    assert decision.disposition == "clean"
    assert decision.canonical_id == "red_yeast_rice"
    assert decision.source_label_name == "Red Yeast Rice extract"
    assert decision.source_label_form == "Monascus purpureus Extract"
    assert enricher._collect_probiotic_data({"activeIngredients": [row]}) == {
        "is_probiotic_product": False,
    }


@pytest.mark.parametrize("literal", ["Brewer's Yeast", "Brewers' yeast"])
def test_exact_whole_yeast_alias_cannot_validate_its_extract(enricher, literal: str) -> None:
    row = {
        **_yeast_extract_row(), "name": literal, "raw_source_text": literal,
        "ingredientGroup": literal, "forms": [{"name": "extract"}],
    }
    registry = enricher._current_canonical_identity_registry()
    assert registry.resolve_verified_preferred(literal) == (
        "brewers_yeast", "ingredient_quality_map",
    )
    decision = resolve_identity(
        row, "brewers_yeast",
        enricher._identity_candidate_resolver(
            enricher.databases["ingredient_quality_map"], "brewers_yeast",
        ),
        canonical_registry=registry,
    )

    assert decision.disposition == "identity_conflict"
    assert decision.canonical_id is None
    assert decision.source_label_name == literal
    assert decision.source_label_form == "extract"


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


@pytest.mark.parametrize("literal,canonical,source_db,form", [
    ("EpiCor", "epicor", "standardized_botanicals",
     "Saccharomyces cerevisiae, Dry, Fermentate"),
    ("EpiCor dried Yeast Fermentate", "NHA_YEAST_FERMENTATE_DRIED",
     "other_ingredients", None),
])
@pytest.mark.parametrize("intermediate", ["yeast_fermentate", None])
def test_exact_preparation_identity_repairs_intermediate_quality_parent(
    enricher, literal: str, canonical: str, source_db: str, form: str | None,
    intermediate: str | None,
) -> None:
    """Actual EpiCor labels enter IQD with a generic quality-parent match."""
    row = {
        **_yeast_extract_row(), "name": literal, "raw_source_text": literal,
        "canonical_id": canonical, "canonical_source_db": source_db,
        "standardName": "EpiCor" if canonical == "epicor" else "Yeast Fermentate (Dried)",
        "ingredientGroup": "Saccharomyces cerevisiae",
        "forms": [{"name": form}] if form else [],
    }
    registry = enricher._current_canonical_identity_registry()
    assert registry.resolve_verified_preferred(literal) == (canonical, source_db)
    decision = resolve_identity(
        row, intermediate,
        enricher._identity_candidate_resolver(
            enricher.databases["ingredient_quality_map"], intermediate,
        ),
        canonical_registry=registry,
    )

    assert decision.disposition == "repaired"
    assert decision.canonical_id == canonical
    assert decision.source_label_name == literal
    assert decision.source_label_form == form
    quality_row = enricher._collect_ingredient_quality_data(
        {"activeIngredients": [row]},
    )["ingredients"][0]
    assert quality_row["canonical_id"] == canonical
    assert quality_row["identity_disposition"] in {"clean", "repaired"}
    assert quality_row["source_label_name"] == literal
    assert quality_row["source_label_form"] == form


@pytest.mark.parametrize("literal", [
    "EpiCor-style yeast fermentate", "Unverified Yeast Fermentate",
])
def test_brand_word_in_normalized_name_or_form_is_not_exact_source_proof(
    enricher, literal: str,
) -> None:
    row = {
        **_yeast_extract_row(), "raw_source_text": literal, "name": "EpiCor",
        "ingredientGroup": "Saccharomyces cerevisiae",
        "forms": [{"name": "EpiCor"}],
    }
    registry = enricher._current_canonical_identity_registry()
    assert registry.resolve_verified_preferred(literal) is None
    decision = resolve_identity(
        row, None,
        enricher._identity_candidate_resolver(enricher.databases["ingredient_quality_map"]),
        canonical_registry=registry,
    )

    assert decision.disposition == "identity_conflict"
    assert decision.canonical_id is None
    assert decision.source_label_name == literal


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


def _fermentate_source_row() -> dict:
    """Required 500 mg active printed on Airborne DSLD 178352."""
    return {
        **_yeast_extract_row(), "name": "dried Yeast Fermentate",
        "raw_source_text": "dried Yeast Fermentate", "raw_source_path": "ingredientRows[11]",
        "standardName": "Yeast Fermentate", "canonical_id": "yeast_fermentate",
        "ingredientGroup": "Saccharomyces cerevisiae", "quantity": 500.0, "forms": [],
    }


def _valid_vitamin_row() -> dict:
    return {
        **_fermentate_source_row(), "name": "Vitamin C", "raw_source_text": "Vitamin C",
        "raw_source_path": "ingredientRows[3]", "standardName": "Vitamin C",
        "ingredientGroup": "Vitamin C", "canonical_id": "vitamin_c",
        "identity_disposition": "clean", "scoreable_identity": True,
        "role_classification": "active_scorable", "mapped": True,
    }


def test_required_conflict_blocks_product_readiness_and_root_score(enricher) -> None:
    from scoring_v4.scored_artifact import build_scored_artifact

    product, issues = enricher.enrich_product({
        "id": "airborne-real-label-boundary", "fullName": "Beta-Immune Booster Zesty Orange",
        "brandName": "Airborne", "activeIngredients": [
            _valid_vitamin_row(), _fermentate_source_row(),
        ], "inactiveIngredients": [],
    })
    assert product, issues
    scoring = get_scoring_ingredients(product, strict=True)
    assert scoring.unmapped_count == 1
    assert scoring.mapped_coverage < 1.0
    assert not any(row["raw_source_path"] == "ingredientRows[11]" for row in scoring.rows)
    artifact = build_scored_artifact(product)
    assert artifact["assessment_readiness"]["identity"]["readiness"] == "incomplete"
    assert artifact["assessment_readiness"]["is_live_ready"] is False
    assert artifact["quality_score_status"] == "not_scored"
    assert artifact["quality_score_v4_100"] is None
    assert artifact["verdict"] == "NOT_SCORED"


@pytest.mark.parametrize("collection", [
    "activeIngredients", "ingredients", "ingredients_skipped", "ingredients_scorable",
])
@pytest.mark.parametrize("scoreable_identity", [False, True])
@pytest.mark.parametrize("canonical", [None, "yeast_fermentate"])
@pytest.mark.parametrize("strict", [False, True])
def test_required_conflict_is_counted_across_every_rejection_guard(
    collection: str, scoreable_identity: bool, canonical: str | None, strict: bool,
) -> None:
    valid = _valid_vitamin_row()
    conflict = {
        **_fermentate_source_row(), "canonical_id": canonical,
        "identity_disposition": "identity_conflict", "scoreable_identity": scoreable_identity,
        "role_classification": "active_scorable", "score_exclusion_reason": "quality_map_match",
    }
    product = {
        "assessment_readiness_contract_version": "1.0.0", "activeIngredients": [],
        "ingredient_quality_data": {"ingredients_scorable": [valid],
                                    "ingredients_skipped": [], "ingredients": [valid]},
    }
    owner = product if collection == "activeIngredients" else product["ingredient_quality_data"]
    owner[collection].append(conflict)
    result = get_scoring_ingredients(product, strict=strict)

    assert result.mapped_count == 1
    assert result.unmapped_count == 1
    assert result.mapped_coverage == 0.5
    assert [row["canonical_id"] for row in result.rows] == ["vitamin_c"]
    assert any(row.row["raw_source_path"] == "ingredientRows[11]" for row in result.rejected_rows)
    assert not any(row.row.get("scoring_input_kind") == "recovered_active_identity"
                   for row in result.rejected_rows)


@pytest.mark.parametrize("quantity,unit", [(500.0, "mg"), (None, "NP")])
@pytest.mark.parametrize("null_ownership", [False, True])
@pytest.mark.parametrize("strict", [False, True])
def test_partial_conflict_uses_source_ownership_without_inventing_identity(
    quantity: float | None, unit: str, null_ownership: bool, strict: bool,
) -> None:
    valid = _valid_vitamin_row()
    source = {**_fermentate_source_row(), "quantity": quantity, "unit": unit}
    conflict = {"raw_source_path": source["raw_source_path"], "canonical_id": None,
                "identity_disposition": "identity_conflict", "scoreable_identity": False}
    if null_ownership:
        conflict.update(source_section=None, cleaner_row_role=None, score_eligible_by_cleaner=None)
    result = get_scoring_ingredients({
        "assessment_readiness_contract_version": "1.0.0", "activeIngredients": [source],
        "ingredient_quality_data": {"ingredients_scorable": [valid], "ingredients": [conflict]},
    }, strict=strict)
    assert result.unmapped_count == 1
    assert result.mapped_coverage == 0.5
    assert result.rejected_rows[0].row["canonical_id"] is None
    assert result.rejected_rows[0].row["quantity"] == quantity
    assert source["canonical_id"] == "yeast_fermentate"


@pytest.mark.parametrize("strict", [False, True])
def test_duplicate_conflict_owns_coverage_over_a_stale_scorable_copy(strict: bool) -> None:
    valid = _valid_vitamin_row()
    stale = {**_fermentate_source_row(), "identity_disposition": "clean",
             "scoreable_identity": True, "role_classification": "active_scorable"}
    conflict = {**stale, "canonical_id": None, "identity_disposition": "identity_conflict",
                "scoreable_identity": False}
    result = get_scoring_ingredients({
        "assessment_readiness_contract_version": "1.0.0", "activeIngredients": [stale],
        "ingredient_quality_data": {"ingredients_scorable": [valid, stale],
                                    "ingredients_skipped": [conflict], "ingredients": [valid, conflict]},
    }, strict=strict)
    assert result.mapped_count == 1
    assert result.unmapped_count == 1
    assert result.mapped_coverage == 0.5
    assert len(result.rejected_rows) == 1
    assert [row["canonical_id"] for row in result.rows] == ["vitamin_c"]


@pytest.mark.parametrize("strict", [False, True])
@pytest.mark.parametrize("required_child", [False, True])
def test_nested_conflict_uses_only_its_own_required_source_ownership(
    strict: bool, required_child: bool,
) -> None:
    valid = _valid_vitamin_row()
    child = {**_fermentate_source_row(), "raw_source_path": "ingredientRows[0].nestedRows[0]",
             "score_eligible_by_cleaner": required_child}
    conflict = {"raw_source_path": child["raw_source_path"], "canonical_id": None,
                "identity_disposition": "identity_conflict", "scoreable_identity": False}
    result = get_scoring_ingredients({
        "assessment_readiness_contract_version": "1.0.0",
        "activeIngredients": [{"name": "Immune Blend", "raw_source_path": "ingredientRows[0]",
                               "cleaner_row_role": "blend_header_total", "score_eligible_by_cleaner": False,
                               "nestedIngredients": [child]}],
        "ingredient_quality_data": {"ingredients_scorable": [valid], "ingredients": [conflict]},
    }, strict=strict)
    assert result.unmapped_count == int(required_child)
    assert result.mapped_coverage == (0.5 if required_child else 1.0)
    assert [row["canonical_id"] for row in result.rows] == ["vitamin_c"]


def test_legacy_shape_does_not_make_an_established_conflict_scoreable() -> None:
    result = get_scoring_ingredients({"ingredient_quality_data": {
        "ingredients_scorable": [{"name": "Yeast Fermentate",
            "canonical_id": "yeast_fermentate", "identity_disposition": "identity_conflict",
            "scoreable_identity": True}],
    }}, strict=False)
    assert result.rows == []
    assert result.rejected_rows[0].reason == "identity_disposition_not_scoreable:identity_conflict"


@pytest.mark.parametrize("excluded", [
    {"source_section": "inactive"},
    {"score_eligible_by_cleaner": False},
    {"cleaner_row_role": "blend_header_total"},
    {"cleaner_row_role": "nested_display_only"},
    {"cleaner_row_role": "nutrition_rollup"},
    {"is_blend_header": True},
    {"blend_total_weight_only": True},
    {"is_excipient": True},
    {"role_classification": "recognized_non_scorable",
     "score_exclusion_reason": "recognized_non_scorable"},
])
def test_intentionally_excluded_conflict_is_not_a_required_active(excluded: dict) -> None:
    valid = _valid_vitamin_row()
    conflict = {**_fermentate_source_row(), "canonical_id": None,
                "identity_disposition": "identity_conflict", "scoreable_identity": False,
                "role_classification": "active_scorable", **excluded}
    result = get_scoring_ingredients({
        "assessment_readiness_contract_version": "1.0.0",
        "ingredient_quality_data": {"ingredients_scorable": [valid],
                                    "ingredients_skipped": [conflict], "ingredients": [valid, conflict]},
    }, strict=True)
    assert result.unmapped_count == 0
    assert result.mapped_coverage == 1.0


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
