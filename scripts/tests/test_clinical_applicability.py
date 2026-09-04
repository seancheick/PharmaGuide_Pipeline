"""Evidence identity is necessary but not sufficient for clinical credit."""

from copy import deepcopy
import json

import pytest

from clinical_applicability import (
    assess_clinical_applicability,
    filter_clinical_matches,
    reviewed_entries,
)
from scoring_v4.modules.generic_evidence import resolved_clinical_matches, score_evidence


def zinc_product(form="zinc bisglycinate", amount=2.4, dosage_form="capsule"):
    row = {"name": f"Zinc (as {form})", "standard_name": "Zinc",
           "canonical_id": "zinc", "mapped": True, "quantity": amount,
           "unit": "mg", "raw_source_path": "ingredientRows[0]",
           "forms": [{"name": form}]}
    return {"form_factor_canonical": dosage_form,
            "ingredient_quality_data": {"ingredients_scorable": [row]},
            "evidence_data": {"clinical_matches": [{
                "id": "INGR_ZINC_PICOLINATE", "standard_name": "Zinc Picolinate",
                "ingredient": row["name"], "matched_canonical_ids": ["zinc"],
                "matched_source_row_refs": ["ingredientRows[0]"],
                "study_type": "systematic_review_meta", "evidence_level": "ingredient-human",
                "effect_direction": "positive_strong", "total_enrollment": 575,
            }]}}


@pytest.mark.parametrize("form,amount,dosage_form", [
    ("zinc bisglycinate", 2.4, "capsule"),
    ("zinc acetate", 80, "capsule"),
    ("zinc picolinate", 80, "lozenge"),
    ("zinc acetate", 2.4, "lozenge"),
])
def test_cold_lozenge_research_cannot_credit_unmatched_form_dose_delivery(form, amount, dosage_form):
    product = zinc_product(form, amount, dosage_form)
    matches, _ = resolved_clinical_matches(product)
    assert not any(m["id"] == "INGR_ZINC_PICOLINATE" for m in matches)
    assert score_evidence(product)["metadata"]["matched_entries"] == 0


def test_explicit_studied_zinc_lozenge_still_receives_evidence():
    matches, _ = resolved_clinical_matches(zinc_product("zinc acetate", 80, "lozenge"))
    assert len(matches) == 1
    assert matches[0]["applicability_assessment"]["status"] == "applicable"


def test_caller_cannot_override_curated_applicability_in_stale_match():
    product = zinc_product()
    product["evidence_data"]["clinical_matches"][0]["applicability"] = {"scope": "unrestricted"}
    assert resolved_clinical_matches(product)[0] == []


def test_formula_context_reference_is_not_an_individual_vitamin_trial():
    product = zinc_product()
    product["evidence_data"]["clinical_matches"] = [{
        "id": "INGR_VITAMIN_A_BETA_CAROTENE", "standard_name": "Vitamin A / Beta-Carotene",
        "ingredient": "Vitamin A (as retinyl palmitate)", "study_type": "systematic_review_meta",
        "evidence_level": "ingredient-human", "effect_direction": "positive_strong",
    }]
    assert resolved_clinical_matches(product)[0] == []


def test_primary_floor_requires_known_studied_dose_not_unknown_unit():
    row = {"name": "KSM-66", "standard_name": "KSM-66", "canonical_id": "ashwagandha",
           "mapped": True, "bio_score": 12, "quantity": 600, "unit": "mg"}
    product = {"ingredient_quality_data": {"ingredients_scorable": [row]},
               "evidence_data": {"clinical_matches": [{
                   "id": "BRAND_KSM66", "standard_name": "KSM-66", "ingredient": "KSM-66",
                   "study_type": "rct_multiple", "evidence_level": "branded-rct",
                   "effect_direction": "positive_strong", "dose_unit": "unknown",
                   "min_clinical_dose": 250,
               }]}}
    # Unknown/incompatible dose evidence may not earn a clinically-dosed floor.
    assert score_evidence(product, apply_primary_floor=True)["metadata"]["primary_evidence_floor"] == 0


def scoped_entry(policy: object) -> dict:
    return {
        "id": "TEST_SCOPED_ENTRY",
        "ingredient": "Zinc (as zinc acetate)",
        "matched_source_row_refs": ["ingredientRows[0]"],
        "applicability": policy,
    }


@pytest.mark.parametrize("policy", [
    {}, [], False, "ingredient",
    {"scope": []},
    {"scope": "ingredient", "dosage_forms": "lozenge"},
    {"scope": "ingredient", "dosage_forms": 42},
    {"scope": "ingredient", "required_form_terms": "zinc acetate"},
    {"scope": "ingredient", "required_form_terms": [None]},
    {"scope": "ingredient", "supported_outcomes": "common_cold_duration"},
    {"scope": "ingredient", "studied_population": ["adults"]},
    {"scope": "ingredient", "dose_unit": "mg", "minimum_daily_dose": "unknown"},
    {"scope": "ingredient", "dose_unit": "mg", "minimum_daily_dose": float("nan")},
    {"scope": "ingredient", "dose_unit": "mg", "minimum_daily_dose": True},
    {"scope": "ingredient", "dose_unit": "mg", "minimum_daily_dose": -80},
    {"scope": "ingredient", "dose_unit": "mg", "maximum_daily_dose": None},
    {"scope": "ingredient", "dose_unit": "mg", "maximum_daily_dose": float("inf")},
    {"scope": "ingredient", "dose_unit": "mg", "minimum_daily_dose": 207,
     "maximum_daily_dose": 80},
    {"scope": "ingredient", "minimum_daily_dose": 80},
    {"scope": "ingredient", "dose_unit": ["mg"]},
])
def test_malformed_scope_contract_fails_closed_without_crashing(policy: object) -> None:
    decision = assess_clinical_applicability(
        zinc_product("zinc acetate", 80, "lozenge"), scoped_entry(policy)
    )
    assert decision == {
        "status": "unresolved", "reason_code": "invalid_applicability_contract"
    }


@pytest.mark.parametrize("name,forms", [
    ("Zinc (as acetate)", [{"name": "acetate"}]),
    ("Zinc", [{"name": "acetate"}]),
    ("Zinc (as gluconate)", None),
])
def test_parent_and_source_form_on_same_row_can_match(name: str, forms: object) -> None:
    product = zinc_product("zinc acetate", 80, "lozenge")
    row = product["ingredient_quality_data"]["ingredients_scorable"][0]
    row.update(name=name, forms=forms)
    matches, _ = resolved_clinical_matches(product)
    assert len(matches) == 1
    assert matches[0]["applicability_assessment"]["source_row_ref"] == "ingredientRows[0]"


@pytest.mark.parametrize("unmatched_form,unmatched_dose", [
    ("zinc acetate", 2.4), ("zinc bisglycinate", 80),
])
def test_exact_source_reference_cannot_borrow_other_rows_form_or_dose(
    unmatched_form: str, unmatched_dose: float
) -> None:
    product = zinc_product(unmatched_form, unmatched_dose, "lozenge")
    other_row = deepcopy(zinc_product("zinc acetate", 80, "lozenge")[
        "ingredient_quality_data"]["ingredients_scorable"][0])
    other_row["raw_source_path"] = "ingredientRows[1]"
    product["ingredient_quality_data"]["ingredients_scorable"].append(other_row)
    assert resolved_clinical_matches(product)[0] == []


def test_accepted_scope_retains_only_the_source_row_that_satisfied_constraints() -> None:
    product = zinc_product("zinc acetate", 80, "lozenge")
    rejected_row = deepcopy(product["ingredient_quality_data"]["ingredients_scorable"][0])
    rejected_row.update(name="Zinc bisglycinate", quantity=600, forms=[],
                        raw_source_path="ingredientRows[1]")
    product["ingredient_quality_data"]["ingredients_scorable"].append(rejected_row)
    original = product["evidence_data"]["clinical_matches"][0]
    original["matched_source_row_refs"] = ["ingredientRows[0]", "ingredientRows[1]"]
    matches, _ = resolved_clinical_matches(product)
    assert matches[0]["matched_source_row_refs"] == ["ingredientRows[0]"]
    assert original["matched_source_row_refs"] == ["ingredientRows[0]", "ingredientRows[1]"]


def test_missing_exact_source_reference_does_not_fall_back_to_name_or_canonical() -> None:
    product = zinc_product("zinc acetate", 80, "lozenge")
    product["evidence_data"]["clinical_matches"][0]["matched_source_row_refs"] = ["missing"]
    assert resolved_clinical_matches(product)[0] == []


@pytest.mark.parametrize("references", ["ingredientRows[0]", {"ingredientRows[0]": True},
                                       ["ingredientRows[0]", []], 42])
def test_malformed_source_reference_contract_fails_closed(references: object) -> None:
    product = zinc_product("zinc acetate", 80, "lozenge")
    entry = product["evidence_data"]["clinical_matches"][0]
    entry["matched_source_row_refs"] = references
    assert assess_clinical_applicability(product, entry)["status"] != "applicable"


@pytest.mark.parametrize("role_fields", [
    {"source_section": "inactive"},
    {"source": "inactiveIngredients"},
    {"cleaner_row_role": "source_descriptor"},
    {"role_classification": "inactive"},
    {"score_eligible_by_cleaner": False},
    {"dose_class": "source_material_mass"},
])
@pytest.mark.parametrize("use_reference", [False, True])
def test_non_exposure_rows_cannot_supply_clinical_dose(
    role_fields: dict, use_reference: bool
) -> None:
    product = zinc_product("zinc acetate", 80, "lozenge")
    row = product["ingredient_quality_data"]["ingredients_scorable"][0]
    row.update(role_fields)
    if not use_reference:
        product["evidence_data"]["clinical_matches"][0].pop("matched_source_row_refs")
    assert resolved_clinical_matches(product)[0] == []


def test_source_term_on_unrelated_row_does_not_complete_parent_form() -> None:
    product = zinc_product("zinc bisglycinate", 80, "lozenge")
    product["ingredient_quality_data"]["ingredients_scorable"].append({
        "name": "Sodium acetate", "canonical_id": "sodium", "quantity": 80,
        "unit": "mg", "forms": [{"name": "acetate"}],
        "raw_source_path": "ingredientRows[1]",
    })
    assert resolved_clinical_matches(product)[0] == []


def test_unreviewed_legacy_match_remains_accepted_without_claiming_review() -> None:
    entry = {"id": "TEST_UNREVIEWED", "ingredient": "Legacy ingredient"}
    assert assess_clinical_applicability({}, entry)["status"] == "not_curated"
    assert filter_clinical_matches({}, [entry]) == ([entry], [])


def test_zinc_reference_contains_only_verified_cold_lozenge_scope() -> None:
    entry = reviewed_entries()["INGR_ZINC_PICOLINATE"]
    assert entry["applicability"]["minimum_daily_dose"] == 80
    assert entry["applicability"]["maximum_daily_dose"] == 207
    assert entry["total_enrollment"] == 575
    assert "registry_completed_trials_count" not in entry
    assert "unii" not in entry.get("external_ids", {})
    assert entry["endpoint_relevance_tags"] == ["common_cold_duration"]
    # Coarse vocabulary labels are categorization, not a broadened claim.
    assert entry["primary_outcome"] == "Immune Support"
    assert entry["health_goals_supported"] == ["Immune Support"]
    assert entry["applicability"]["supported_outcomes"] == ["common_cold_duration"]
    assert "not prevention" in entry["applicability"]["studied_population"]
    assert "does not establish prevention" in entry["notes"]
    text = json.dumps(entry).lower()
    for stale in ("immune function", "cardiovascular", "glycemic_control", "digestive_health"):
        assert stale not in text
    assert {ref["pmid"] for ref in entry["references_structured"]} == {
        "25888289", "27378206", "28515951"
    }


def test_vitamin_a_references_remain_combination_context_not_individual_benefits() -> None:
    entry = reviewed_entries()["INGR_VITAMIN_A_BETA_CAROTENE"]
    assert entry["applicability"]["scope"] == "formula_context_only"
    assert entry["evidence_level"] == "reference"
    assert entry["study_type"] == "reference"
    assert entry["endpoint_relevance_tags"] == ["amd_progression_combination_context"]
    assert entry["primary_outcome"] == "Eye & Vision"
    assert entry["health_goals_supported"] == ["Eye & Vision"]
    text = json.dumps(entry).lower()
    for stale in ("visual function support", "immune function support", "oxidative stress support",
                  "stress_mood", "correction of deficiency"):
        assert stale not in text
    assert {ref["pmid"] for ref in entry["references_structured"]} == {
        "23644932", "35653117", "37702300"
    }


def test_seed_formula_effect_confidence_uses_the_clinical_registry_vocabulary() -> None:
    assert reviewed_entries()["FORMULA_SEED_DS01"]["effect_direction_confidence"] == "medium"


@pytest.mark.parametrize("amount,accepted", [(75, False), (80, True), (207, True), (208, False)])
def test_zinc_cold_scope_uses_observed_dose_envelope(amount: float, accepted: bool) -> None:
    assert bool(resolved_clinical_matches(zinc_product("zinc acetate", amount, "lozenge"))[0]) is accepted


def test_zinc_scope_resolves_directed_daily_dose() -> None:
    product = zinc_product("zinc acetate", 10, "lozenge")
    product["serving_basis"] = {
        "min_servings_per_day": 8, "max_servings_per_day": 8,
        "servings_per_day_source": "directions",
    }
    assert len(resolved_clinical_matches(product)[0]) == 1


@pytest.fixture(scope="module")
def enricher():
    from enrich_supplements_v3 import SupplementEnricherV3

    return SupplementEnricherV3()


@pytest.mark.parametrize("name,forms,amount,accepted", [
    ("Zinc (as acetate)", [{"name": "acetate"}], 80, True),
    ("Zinc (as bisglycinate)", [{"name": "bisglycinate"}], 80, False),
    ("Zinc (as acetate)", [{"name": "acetate"}], 2.4, False),
])
def test_enrichment_collector_applies_shared_zinc_scope(
    enricher, name: str, forms: list, amount: float, accepted: bool
) -> None:
    product = zinc_product("zinc acetate", amount, "lozenge")
    row = product["ingredient_quality_data"]["ingredients_scorable"][0]
    row.update(name=name, standardName="Zinc", forms=forms)
    product["activeIngredients"] = [deepcopy(row)]
    product["fullName"] = "Clinical applicability test lozenges"
    evidence = enricher._collect_evidence_data(product, product["ingredient_quality_data"])
    matches = [match for match in evidence["clinical_matches"]
               if match["id"] == "INGR_ZINC_PICOLINATE"]
    assert bool(matches) is accepted
    if not accepted:
        assert any(match["id"] == "INGR_ZINC_PICOLINATE"
                   for match in evidence["rejected_clinical_matches"])
