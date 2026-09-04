"""Keep clinical preparation evidence tied to its original source label row."""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING

import pytest

from clinical_applicability import (
    assess_clinical_applicability,
    filter_clinical_matches,
    reviewed_entries,
)
from scoring_v4.modules.generic_evidence import resolved_clinical_matches

if TYPE_CHECKING:
    from enrich_supplements_v3 import SupplementEnricherV3


@pytest.fixture(scope="module")
def enricher() -> SupplementEnricherV3:
    from enrich_supplements_v3 import SupplementEnricherV3

    return SupplementEnricherV3()


def _source_product(name: str, *, forms: list[dict] | None = None) -> dict:
    """Retain the source and identity fields used by the real cleaned rows."""
    row = {
        "name": name,
        "raw_source_text": name,
        "raw_source_path": "ingredientRows[0]",
        "standardName": "Green Tea Extract",
        "canonical_id": "green_tea_extract",
        "canonical_source_db": "ingredient_quality_map",
        "ingredientGroup": "Green Tea",
        "raw_category": "botanical",
        "quantity": 15.0,
        "unit": "mg",
        "dose_class": "therapeutic_mass",
        "source_section": "active",
        "cleaner_row_role": "active_scorable",
        "score_eligible_by_cleaner": True,
        "forms": deepcopy(forms or []),
        "nestedIngredients": [],
        "isNestedIngredient": False,
        "parentBlend": None,
    }
    row["raw_taxonomy"] = {
        "category": "botanical", "ingredientGroup": "Green Tea",
        "forms": deepcopy(row["forms"]), "isNestedIngredient": False,
    }
    return {
        "id": "green-tea-source-scope",
        "fullName": name,
        "activeIngredients": [row],
        "inactiveIngredients": [],
        "servingSizes": [{
            "order": 1, "minQuantity": 1.0, "maxQuantity": 1.0,
            "unit": "Capsule(s)", "minDailyServings": 1,
            "maxDailyServings": 1,
        }],
    }


def _replayed_match(product: dict) -> dict:
    """Reproduce a stored generic match that predates the reviewed scope."""
    row = product["activeIngredients"][0]
    return {
        "id": "INGR_GREEN_TEA", "standard_name": "Green Tea Extract",
        "ingredient": row["name"],
        "matched_source_row_refs": [row["raw_source_path"]],
        "matched_canonical_ids": [row["canonical_id"]],
        "evidence_level": "ingredient-human", "study_type": "systematic_review_meta",
        "effect_direction": "positive_weak", "total_enrollment": 1210,
        "applicability": {"scope": "ingredient"},
        "applicability_assessment": {"status": "applicable"},
    }


@pytest.mark.parametrize("label", [
    "Epigallocatechin Gallate", "Epigallocatechin-3-Gallate",
])
def test_spelled_out_egcg_reaches_the_existing_catechin_evidence(enricher, label):
    # DSLD 328410: the explicit EGCG owner, not its green-tea source form,
    # establishes the same chemical identity as the already-authored EGCG alias.
    source = _source_product(label, forms=[{
        "name": "Green Tea leaf extract", "category": "botanical",
        "ingredientGroup": "Green Tea",
    }])
    source["id"] = "328410"
    row = source["activeIngredients"][0]
    row.update(
        quantity=300.0, canonical_id="egcg",
        standardName="EGCG (Epigallocatechin Gallate)",
        ingredientGroup="EGCG", raw_source_path="ingredientRows[1]",
        raw_category="non-nutrient/non-botanical",
    )
    row["raw_taxonomy"].update(category="non-nutrient/non-botanical", ingredientGroup="EGCG")
    product, issues = enricher.enrich_product(deepcopy(source))
    assert product.get("enrichment_status") != "validation_failed", issues
    matches = [m for m in resolved_clinical_matches(product)[0] if m["id"] == "INGR_GREEN_TEA"]
    assert len(matches) == 1
    assert matches[0]["matched_source_row_refs"] == ["ingredientRows[1]"]
    assert product["activeIngredients"][0]["quantity"] == 300.0


@pytest.mark.parametrize("label", ["Epigallocatechin", "Epicatechin Gallate"])
def test_similar_catechin_names_do_not_inherit_the_egcg_alias(enricher, label):
    study = reviewed_entries()["INGR_GREEN_TEA"]
    assert not enricher._clinical_study_match([label], study)


@pytest.mark.parametrize("product_id,name,quantity,source_ref,forms", [
    ("213472", "Green Tea (leaf) extract", 10.0, "ingredientRows[10]", [{
        "name": "Polyphenol", "prefix": "with", "percent": None,
        "category": "blend", "ingredientGroup": "Blend (non-nutrient/non-botanical)",
    }]),
    ("217338", "standardized Green Tea extract", 15.0, "ingredientRows[17]", [{
        "name": "Polyphenols", "prefix": None, "percent": 50,
        "category": "blend", "ingredientGroup": "Blend (non-nutrient/non-botanical)",
    }]),
])
def test_original_extract_rows_reach_existing_evidence(
    enricher: SupplementEnricherV3, product_id: str, name: str,
    quantity: float, source_ref: str, forms: list[dict],
) -> None:
    """The two real source-declared extracts survive broad identity repair."""
    source = _source_product(name, forms=forms)
    source["id"] = product_id
    source["activeIngredients"][0].update(quantity=quantity, raw_source_path=source_ref)
    enriched, issues = enricher.enrich_product(deepcopy(source))
    assert enriched.get("enrichment_status") != "validation_failed", issues

    matches, _ = resolved_clinical_matches(enriched)
    match = next((row for row in matches if row["id"] == "INGR_GREEN_TEA"), None)
    assert match is not None
    assert match["matched_source_row_refs"] == [source_ref]
    active = enriched["activeIngredients"][0]
    assert active["canonical_id"] == "green_tea"
    for field in ("name", "raw_source_text", "forms", "quantity", "raw_source_path"):
        assert active[field] == source["activeIngredients"][0][field]


@pytest.mark.parametrize("name", [
    "Matcha Green Tea, Powder", "organic Green Tea", "Camellia sinensis",
])
def test_replayed_generic_match_does_not_credit_unproven_preparation(name: str) -> None:
    product = _source_product(name)
    product["evidence_data"] = {"clinical_matches": [_replayed_match(product)]}
    before = deepcopy(product)

    assert resolved_clinical_matches(product)[0] == []
    accepted, rejected = filter_clinical_matches(
        product, product["evidence_data"]["clinical_matches"],
    )
    assert accepted == []
    assert rejected[0]["reason_code"] == "clinical_form_mismatch"
    assert product == before


@pytest.mark.parametrize("stale_surface", [
    "derived_form", "generated_name", "generated_forms", "iqd_duplicate",
    "missing_source_label", "excluded_source_owner",
])
def test_original_source_owner_cannot_be_overruled_by_derived_preparation(
    stale_surface: str,
) -> None:
    product = _source_product("Matcha Green Tea, Powder")
    active = product["activeIngredients"][0]
    if stale_surface == "derived_form":
        active.update(matched_form="Green Tea Extract", form_id="green tea extract (unspecified)")
    elif stale_surface == "generated_name":
        active["name"] = "Green Tea Extract"
    elif stale_surface == "generated_forms":
        active["forms"] = [{"name": "Green Tea Extract"}]
    elif stale_surface == "missing_source_label":
        active.update(name="Green Tea Extract", raw_source_text=None)
    elif stale_surface == "excluded_source_owner":
        active.update(name="Green Tea Extract", raw_source_text="Green Tea Extract",
                      score_eligible_by_cleaner=False)
    if stale_surface in {"iqd_duplicate", "excluded_source_owner"}:
        generated = deepcopy(active)
        generated.update(name="Green Tea Extract", matched_form="Green Tea Extract",
                         score_eligible_by_cleaner=True)
        product["ingredient_quality_data"] = {"ingredients_scorable": [generated]}
    product["evidence_data"] = {"clinical_matches": [_replayed_match(product)]}
    before = deepcopy(product)

    assert resolved_clinical_matches(product)[0] == []
    assert product == before


def test_unrelated_theanine_row_does_not_exclude_a_source_owned_extract() -> None:
    product = _source_product("Green Tea Extract")
    generated = deepcopy(product["activeIngredients"][0])
    generated.update(name="L-Theanine", canonical_id="l_theanine",
                     forms=[{"name": "L-Theanine"}])
    product["ingredient_quality_data"] = {"ingredients_scorable": [generated]}
    sibling = deepcopy(generated)
    sibling.update(raw_source_path="ingredientRows[1]", raw_source_text="L-Theanine")
    product["activeIngredients"].append(sibling)
    product["evidence_data"] = {"clinical_matches": [_replayed_match(product)]}
    accepted, _ = resolved_clinical_matches(product)
    assert accepted[0]["matched_source_row_refs"] == ["ingredientRows[0]"]


@pytest.mark.parametrize("references", [["missing"], ["ingredientRows[0]"]])
def test_missing_or_powder_source_cannot_borrow_a_sibling_extract(references: list[str]) -> None:
    product = _source_product("Matcha Green Tea, Powder")
    sibling = deepcopy(_source_product("Green Tea Extract")["activeIngredients"][0])
    sibling["raw_source_path"] = "ingredientRows[1]"
    product["activeIngredients"].append(sibling)
    match = _replayed_match(product)
    match["matched_source_row_refs"] = references
    product["evidence_data"] = {"clinical_matches": [match]}
    assert resolved_clinical_matches(product)[0] == []


def test_legacy_iqd_only_label_proof_remains_usable() -> None:
    product = _source_product("Green Tea Extract")
    match = _replayed_match(product)
    product["ingredient_quality_data"] = {"ingredients_scorable": product.pop("activeIngredients")}
    product["evidence_data"] = {"clinical_matches": [match]}
    assert resolved_clinical_matches(product)[0][0]["id"] == "INGR_GREEN_TEA"


def test_refless_generated_extract_cannot_replace_original_powder() -> None:
    product = _source_product("Matcha Green Tea, Powder")
    generated = _source_product("Green Tea Extract")["activeIngredients"][0]
    generated.pop("raw_source_path")
    product["ingredient_quality_data"] = {"ingredients_scorable": [generated]}
    match = _replayed_match(product)
    match.update(ingredient="Green Tea Extract", matched_source_row_refs=[])
    product["evidence_data"] = {"clinical_matches": [match]}
    before = deepcopy(product)

    assert resolved_clinical_matches(product)[0] == []
    assert product == before


@pytest.mark.parametrize("owner_kind", ["original", "iqd_only"])
@pytest.mark.parametrize("source_ref", [None, "", "   ", 42])
def test_source_required_legacy_fallback_needs_a_valid_owner_reference(
    owner_kind: str, source_ref: object,
) -> None:
    product = _source_product("Green Tea Extract")
    match = _replayed_match(product)
    match["matched_source_row_refs"] = []
    owner = product["activeIngredients"][0]
    if source_ref is None:
        owner.pop("raw_source_path")
    else:
        owner["raw_source_path"] = source_ref
    if owner_kind == "iqd_only":
        product["ingredient_quality_data"] = {"ingredients_scorable": product.pop("activeIngredients")}
    product["evidence_data"] = {"clinical_matches": [match]}
    before = deepcopy(product)
    assert resolved_clinical_matches(product)[0] == []
    assert product == before


def test_source_required_legacy_fallback_cannot_guess_from_canonical_alone() -> None:
    product = _source_product("Green Tea Extract")
    match = _replayed_match(product)
    match.update(ingredient="Unlinked preparation", matched_source_row_refs=[])
    product["evidence_data"] = {"clinical_matches": [match]}
    assert resolved_clinical_matches(product)[0] == []


@pytest.mark.parametrize("generated_ref", [None, "   ", "ingredientRows[99]", "missing"])
@pytest.mark.parametrize("match_link", ["absent", "empty", "forged"])
def test_generated_source_reference_cannot_displace_any_original_owner(
    generated_ref: str | None, match_link: str,
) -> None:
    product = _source_product("Matcha Green Tea, Powder")
    generated = _source_product("Green Tea Extract")["activeIngredients"][0]
    if generated_ref is None:
        generated.pop("raw_source_path")
    else:
        generated["raw_source_path"] = generated_ref
    product["ingredient_quality_data"] = {"ingredients_scorable": [generated]}
    match = _replayed_match(product)
    match["ingredient"] = "Green Tea Extract"
    if match_link == "absent":
        match.pop("matched_source_row_refs")
    else:
        match["matched_source_row_refs"] = [] if match_link == "empty" else [generated_ref]
    product["evidence_data"] = {"clinical_matches": [match]}
    before = deepcopy(product)
    assert resolved_clinical_matches(product)[0] == []
    assert product == before


@pytest.mark.parametrize("owner_kind", ["original", "iqd_only"])
@pytest.mark.parametrize("match_link", ["absent", "empty"])
def test_exact_legacy_fallback_keeps_a_genuinely_referenced_source_owner(
    owner_kind: str, match_link: str,
) -> None:
    product = _source_product("Green Tea Extract")
    match = _replayed_match(product)
    if match_link == "absent":
        match.pop("matched_source_row_refs")
    else:
        match["matched_source_row_refs"] = []
    if owner_kind == "iqd_only":
        product["ingredient_quality_data"] = {"ingredients_scorable": product.pop("activeIngredients")}
    product["evidence_data"] = {"clinical_matches": [match]}
    before = deepcopy(product)
    accepted, _ = resolved_clinical_matches(product)
    assert accepted[0]["matched_source_row_refs"] == ["ingredientRows[0]"]
    assert accepted[0]["applicability_assessment"]["source_row_ref"] == "ingredientRows[0]"
    assert product == before


@pytest.mark.parametrize("name", [
    "Green Tea (Camellia sinensis) extract",
    "Green Tea (Camellia sinensis) (leaf) extract",
    "Green Tea leaves extract",
    "Green Tea decaffeinated extract",
])
def test_source_declared_extract_spelling_variants_remain_applicable(name: str) -> None:
    """Preserve exact extract spellings found in the current clinical corpus."""
    product = _source_product(name)
    product["evidence_data"] = {"clinical_matches": [_replayed_match(product)]}
    before = deepcopy(product)
    accepted, _ = resolved_clinical_matches(product)
    assert len(accepted) == 1
    assert accepted[0]["applicability_assessment"]["source_row_ref"] == "ingredientRows[0]"
    assert product == before


@pytest.mark.parametrize("name", ["Greenselect", "Green Tea Phytosome"])
def test_verified_extract_preparation_name_can_establish_source_scope(name: str) -> None:
    product = _source_product(name)
    product["evidence_data"] = {"clinical_matches": [_replayed_match(product)]}
    accepted, _ = resolved_clinical_matches(product)
    assert len(accepted) == 1
    assert accepted[0]["applicability_assessment"]["source_row_ref"] == "ingredientRows[0]"


def test_caffeine_primary_cannot_borrow_extract_evidence_from_its_source_form() -> None:
    product = _source_product("Caffeine", forms=[{"name": "Green Tea Extract"}])
    product["activeIngredients"][0].update(canonical_id="caffeine", standardName="Caffeine")
    product["evidence_data"] = {"clinical_matches": [_replayed_match(product)]}
    accepted, rejected = filter_clinical_matches(product, product["evidence_data"]["clinical_matches"])
    assert accepted == []
    assert rejected[0]["reason_code"] == "clinical_identity_excluded"


def test_caffeine_constituent_does_not_exclude_the_extract_primary() -> None:
    product = _source_product("Green Tea Extract", forms=[{"name": "Caffeine"}])
    product["evidence_data"] = {"clinical_matches": [_replayed_match(product)]}
    assert resolved_clinical_matches(product)[0][0]["id"] == "INGR_GREEN_TEA"


def test_original_without_reference_still_prevents_generated_source_substitution() -> None:
    product = _source_product("Matcha Green Tea, Powder")
    match = _replayed_match(product)
    product["activeIngredients"][0].pop("raw_source_path")
    generated = _source_product("Green Tea Extract")["activeIngredients"][0]
    product["ingredient_quality_data"] = {"ingredients_scorable": [generated]}
    match["ingredient"] = "Green Tea Extract"
    product["evidence_data"] = {"clinical_matches": [match]}
    assert resolved_clinical_matches(product)[0] == []


@pytest.mark.parametrize("legacy_surface", ["generated_row", "canonical_fallback"])
def test_reference_hardening_does_not_change_default_policies(legacy_surface: str) -> None:
    product = _source_product("Green Tea Extract")
    entry = _replayed_match(product)
    entry.update(id="TEST_DEFAULT_REFERENCE_POLICY", matched_source_row_refs=[],
                 applicability={"scope": "ingredient", "required_form_terms": ["green tea extract"]})
    if legacy_surface == "generated_row":
        generated = deepcopy(product["activeIngredients"][0])
        generated.pop("raw_source_path")
        product["ingredient_quality_data"] = {"ingredients_scorable": [generated]}
        product["activeIngredients"][0].update(
            name="Matcha Green Tea, Powder", raw_source_text="Matcha Green Tea, Powder",
        )
    else:
        entry["ingredient"] = "Legacy name without an exact match"
    assert assess_clinical_applicability(product, entry)["status"] == "applicable"


@pytest.mark.parametrize("field,value", [
    ("require_source_label_form", "true"),
    ("require_source_label_form", 1),
    ("require_source_label_form", None),
    ("require_source_label_form", []),
    ("required_form_terms", []),
    ("excluded_canonical_ids", "l_theanine"),
    ("excluded_canonical_ids", None),
    ("excluded_canonical_ids", [None]),
    ("excluded_canonical_ids", [""]),
    ("excluded_canonical_ids", ["_"]),
    ("excluded_form_terms", "theanine"),
    ("excluded_form_terms", None),
    ("excluded_form_terms", [False]),
    ("excluded_form_terms", [[]]),
    ("excluded_form_terms", [" "]),
    ("excluded_form_terms", ["-"]),
])
def test_malformed_new_scope_constraints_fail_closed(field: str, value: object) -> None:
    product = _source_product("Green Tea Extract")
    entry = _replayed_match(product)
    entry["id"] = "TEST_PREPARATION_SCOPE"
    entry["applicability"] = deepcopy(reviewed_entries()["INGR_GREEN_TEA"]["applicability"])
    entry["applicability"][field] = value
    assert assess_clinical_applicability(product, entry) == {
        "status": "unresolved", "reason_code": "invalid_applicability_contract",
    }


def test_source_only_constraint_does_not_change_other_records_default_behavior() -> None:
    product = _source_product("Matcha Green Tea, Powder")
    product["activeIngredients"][0]["matched_form"] = "Green Tea Extract"
    entry = _replayed_match(product)
    entry.update(id="TEST_LEGACY_FORM_SCOPE", applicability={
        "scope": "ingredient", "required_form_terms": ["green tea extract"],
    })
    assert assess_clinical_applicability(product, entry)["status"] == "applicable"


def test_registry_scope_does_not_upgrade_strength_or_invent_dose_cutoffs() -> None:
    entry = reviewed_entries()["INGR_GREEN_TEA"]
    assert entry["effect_direction"] == "positive_weak"
    assert entry["score_contribution"] == "tier_1"
    assert entry["study_type"] == "systematic_review_meta"
    # Preserve this unresolved legacy aggregate; the research note flags it.
    assert entry["total_enrollment"] == 1210
    assert entry["registry_completed_trials_count"] == 144
    policy = entry["applicability"]
    assert policy["source_pmids"] == ["38031409", "19597519"]
    assert set(policy["source_pmids"]) == {ref["pmid"] for ref in entry["references_structured"]}
    assert policy["supported_outcomes"] == [
        "modest_weight_change", "body_composition", "oxidative_stress_markers",
    ]
    for key in ("minimum_daily_dose", "maximum_daily_dose", "dose_unit"):
        assert key not in policy


def test_hemp_source_keeps_its_independent_theanine_evidence(
    enricher: SupplementEnricherV3,
) -> None:
    product = _source_product("organic Green Tea (leaf) extract", forms=[{
        "name": "L-Theanine", "prefix": "standardized to", "percent": 98,
        "category": "non-nutrient/non-botanical", "ingredientGroup": "Theanine",
    }])
    product["id"] = "232933"
    product["activeIngredients"][0]["quantity"] = 51.0
    enriched, _ = enricher.enrich_product(deepcopy(product))
    row = enriched["activeIngredients"][0]
    assert row["canonical_id"] == "green_tea"
    before = deepcopy(enriched)
    enriched["evidence_data"]["clinical_matches"].append(_replayed_match(enriched))
    matches, _ = resolved_clinical_matches(enriched)
    assert {match["id"] for match in matches} == {"INGR_L_THEANINE"}
    assert row == before["activeIngredients"][0]


def test_preparation_on_its_own_source_form_remains_applicable() -> None:
    product = _source_product("Camellia sinensis", forms=[{"name": "Green Tea Extract"}])
    product["evidence_data"] = {"clinical_matches": [_replayed_match(product)]}
    accepted, _ = resolved_clinical_matches(product)
    assert accepted[0]["applicability_assessment"]["source_row_ref"] == "ingredientRows[0]"


@pytest.mark.parametrize("source_kind", ["label", "form", "hemp_98_percent", "canonical"])
def test_theanine_preparation_cannot_replay_generic_green_tea_evidence(
    source_kind: str,
) -> None:
    product = _source_product("Green Tea Extract")
    row = product["activeIngredients"][0]
    row.update(canonical_id="green_tea", canonical_source_db="standardized_botanicals")
    if source_kind == "label":
        row.update(name="Green Tea Extract standardized to L-Theanine",
                   raw_source_text="Green Tea Extract standardized to L-Theanine")
    elif source_kind == "canonical":
        row.update(name="L-Theanine (from Green Tea Extract)",
                   raw_source_text="L-Theanine (from Green Tea Extract)",
                   canonical_id="l_theanine", canonical_source_db="ingredient_quality_map")
    else:
        form = {"name": "L-Theanine", "prefix": "standardized to"}
        if source_kind == "hemp_98_percent":
            row.update(name="organic Green Tea (leaf) extract",
                       raw_source_text="organic Green Tea (leaf) extract", quantity=51.0)
            form["percent"] = 98
        row["forms"] = [form]
        row["raw_taxonomy"]["forms"] = deepcopy(row["forms"])
    product["evidence_data"] = {"clinical_matches": [_replayed_match(product)]}
    before = deepcopy(product)

    assert resolved_clinical_matches(product)[0] == []
    _, rejected = filter_clinical_matches(product, product["evidence_data"]["clinical_matches"])
    assert rejected[0]["reason_code"] == (
        "clinical_identity_excluded" if source_kind == "canonical" else "clinical_form_excluded"
    )
    assert product == before
