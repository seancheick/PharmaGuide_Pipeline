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


@pytest.mark.parametrize("ambiguous", [False, True])
def test_applicability_reconciles_only_unique_exact_subject_identity_without_borrowing_amount(monkeypatch, ambiguous):
    from clinical_applicability import _rows
    import scoring_input_contract
    row = {"name": "Omega-3 Fatty Acids", "canonical_id": "omega_3", "quantity": 100,
           "unit": "mg", "raw_source_path": "ingredientRows[0]"}
    subjects = [{**row, "canonical_id": "fish_oil", "quantity": 999}]
    if ambiguous:
        subjects.append({**row, "canonical_id": "alpha_linolenic_acid"})
    monkeypatch.setattr(scoring_input_contract, "get_evidence_subject_rows", lambda product: subjects)
    product = {"activeIngredients": [row], "ingredient_quality_data": {"ingredients": [{**row, "canonical_id": "fish_oil"}]}}
    resolved = list(_rows(product))[0]
    assert resolved["canonical_id"] == ("omega_3" if ambiguous else "fish_oil")
    assert resolved["quantity"] == 100
    assert list(_rows(product, source_only=True))[0] == row


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
])
def test_cold_lozenge_research_cannot_credit_unmatched_form_or_delivery(form, amount, dosage_form):
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


def test_evidence_floor_is_amount_independent_when_dose_benchmark_is_unusable():
    row = {"name": "KSM-66", "standard_name": "KSM-66", "canonical_id": "ashwagandha",
           "mapped": True, "bio_score": 12, "quantity": 600, "unit": "mg"}
    product = {"ingredient_quality_data": {"ingredients_scorable": [row]},
               "evidence_data": {"clinical_matches": [{
                   "id": "BRAND_KSM66", "standard_name": "KSM-66", "ingredient": "KSM-66",
                   "study_type": "rct_multiple", "evidence_level": "branded-rct",
                   "effect_direction": "positive_strong", "dose_unit": "unknown",
                   "min_clinical_dose": 250,
               }]}}
    # Evidence grades the applicable positive research. Dose independently
    # refuses this stale, unitless benchmark.
    assert score_evidence(product, apply_primary_floor=True)["metadata"]["primary_evidence_floor"] > 0
    from dose_assessment import positive_clinical_benchmark
    assert positive_clinical_benchmark(product, row) is None


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
    ("zinc picolinate", 2.4), ("zinc bisglycinate", 80),
])
def test_exact_source_reference_cannot_borrow_other_rows_form(
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
    entry = scoped_entry({"scope":"ingredient", "minimum_daily_dose":80, "dose_unit":"mg"})
    if not use_reference:
        entry.pop("matched_source_row_refs")
    assert assess_clinical_applicability(product, entry)["status"] != "applicable"


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
    assert "minimum_daily_dose" not in entry["applicability"]
    assert "maximum_daily_dose" not in entry["applicability"]
    assert [(r["minimum"], r["maximum"]) for r in entry["studied_regimens"]["regimens"]] == [(80, 92), (192, 207)]
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


@pytest.mark.parametrize("amount,accepted", [(75, True), (80, True), (207, True), (208, True), (None, True)])
def test_zinc_cold_evidence_scope_is_amount_independent(amount: float, accepted: bool) -> None:
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
    ("Zinc (as acetate)", [{"name": "acetate"}], 2.4, True),
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


# ---- Units come from the pipeline's canonical mass-unit function -------------


@pytest.mark.parametrize("unit,unit_normalized,amount", [
    ("Gram(s)", None, 0.08),          # DSLD's printed unit spelling
    ("Gram(s)", "gram(s)", 0.08),     # what the enricher writes to unit_normalized
    ("Milligram(s)", None, 80),
    ("mcg", None, 80000),
])
def test_dose_policy_resolves_every_canonical_mass_unit_spelling(unit, unit_normalized, amount):
    product = zinc_product("zinc acetate", amount, "lozenge")
    row = product["ingredient_quality_data"]["ingredients_scorable"][0]
    row["unit"] = unit
    if unit_normalized is not None:
        row["unit_normalized"] = unit_normalized
    verdict = assess_clinical_applicability(product, product["evidence_data"]["clinical_matches"][0])
    assert verdict["status"] == "applicable", verdict


def test_dose_policy_leaves_non_mass_units_unresolved():
    product = zinc_product("zinc acetate", 80, "lozenge")
    product["ingredient_quality_data"]["ingredients_scorable"][0]["unit"] = "IU"
    verdict = assess_clinical_applicability(product, scoped_entry({"scope":"ingredient", "minimum_daily_dose":80, "dose_unit":"mg"}))
    assert verdict["status"] == "unresolved"
    assert verdict["reason_code"] == "clinical_dose_unresolved"


def test_policy_dose_unit_accepts_canonical_spellings(monkeypatch):
    import clinical_applicability

    entries = deepcopy(reviewed_entries())
    entries["INGR_ZINC_PICOLINATE"]["applicability"]["dose_unit"] = "Milligram(s)"
    monkeypatch.setattr(clinical_applicability, "reviewed_entries", lambda: entries)
    product = zinc_product("zinc acetate", 80, "lozenge")
    product["serving_basis"] = {"min_servings_per_day": 1, "max_servings_per_day": 1}
    verdict = assess_clinical_applicability(product, product["evidence_data"]["clinical_matches"][0])
    assert verdict["status"] == "applicable", verdict


@pytest.mark.parametrize("frequency", [{}, {"minDailyServings": 1, "maxDailyServings": None}])
def test_unknown_daily_frequency_cannot_qualify_a_studied_daily_dose(frequency):
    product = zinc_product("zinc acetate", 80, "lozenge")
    product["servingSizes"] = [{"quantity": 1, "unit": "lozenge", **frequency}]
    verdict = assess_clinical_applicability(product, scoped_entry({
        "scope": "ingredient", "minimum_daily_dose": 80, "dose_unit": "mg"}))
    assert verdict["status"] != "applicable"
    assert verdict["reason_code"] == "clinical_dose_unresolved"


# --- resolved material identity and multi-row ownership (Wave 1 applicability repair) -------------
#
# Both defects were found by probing real butterbur products (61929, 328579, 293376):
# the enricher resolves "PA-free butterbur extract (Petadolex)" on its own projection of a
# label row, and the applicability contract never saw it.

def butterbur_product(*extra_rows, resolved_form="PA-free butterbur extract (Petadolex)"):
    """A product as the pipeline really emits it: the SAME label row in two projections."""
    label_row = {"name": "Purple Butterbur CO2 extract", "canonical_id": "butterbur",
                 "quantity": 75.0, "unit": "mg", "raw_source_path": "ingredientRows[0]"}
    enriched_row = dict(label_row, form_id=resolved_form, matched_form=resolved_form, mapped=True,
                        standard_name="Butterbur")
    return {"form_factor_canonical": "capsule",
            "activeIngredients": [deepcopy(label_row), *[deepcopy(r) for r in extra_rows]],
            "ingredient_quality_data": {"ingredients": [enriched_row, *[deepcopy(r) for r in extra_rows]]},
            "servingSizes": [{"minDailyServings": 2, "maxDailyServings": 2}]}


def butterbur_entry(**policy_overrides):
    policy = {"scope": "ingredient", "required_form_terms": ["petadolex"],
              "dose_unit": "mg", "minimum_daily_dose": 150}
    policy.update(policy_overrides)
    return {"id": "CANDIDATE_BUTTERBUR", "ingredient": "Butterbur",
            "matched_canonical_ids": ["butterbur"], "applicability": policy}


def test_resolved_material_identity_is_visible_to_a_form_scoped_scope():
    # The label prints "Purple Butterbur CO2 extract"; only enrichment resolves Petadolex.
    decision = assess_clinical_applicability(butterbur_product(), butterbur_entry())

    assert decision["status"] == "applicable"
    assert decision["source_row_ref"] == "ingredientRows[0]"


def test_source_required_scope_still_refuses_enrichment_resolved_forms():
    # A source-required scope distrusts enrichment by design; merging must not leak into it.
    decision = assess_clinical_applicability(
        butterbur_product(), butterbur_entry(require_source_label_form=True))

    assert decision["status"] == "unresolved"


def test_unspecified_material_stays_out_even_when_the_dose_matches():
    product = butterbur_product(resolved_form="butterbur (unspecified)")
    product["servingSizes"] = [{"minDailyServings": 2, "maxDailyServings": 2}]

    decision = assess_clinical_applicability(product, butterbur_entry())

    assert decision["status"] == "not_applicable"
    assert decision["reason_code"] == "clinical_form_mismatch"


def test_second_owned_row_no_longer_blocks_a_discriminated_match():
    # 293376 Petadolex Pro-Active carries a second butterbur row ("Petasins"), which
    # previously made the whole identity unresolved.
    second = {"name": "Petasins", "canonical_id": "butterbur", "quantity": 7.5, "unit": "mg",
              "raw_source_path": "ingredientRows[1]", "form_id": "butterbur (unspecified)"}

    decision = assess_clinical_applicability(butterbur_product(second), butterbur_entry())

    assert decision["status"] == "applicable"
    assert decision["source_row_ref"] == "ingredientRows[0]"


def test_two_rows_matching_the_same_scope_remain_unresolved():
    twin = {"name": "Butterbur root extract", "canonical_id": "butterbur", "quantity": 75.0,
            "unit": "mg", "raw_source_path": "ingredientRows[1]",
            "form_id": "PA-free butterbur extract (Petadolex)"}

    decision = assess_clinical_applicability(butterbur_product(twin), butterbur_entry())

    assert decision["status"] == "unresolved"
    assert decision["reason_code"] == "clinical_source_row_unresolved"


def test_multiple_owned_rows_without_a_discriminating_scope_stay_unresolved():
    # No required_form_terms means nothing distinguishes the rows: an unmatched row
    # must never lend its amount to the scope.
    second = {"name": "Petasins", "canonical_id": "butterbur", "quantity": 7.5, "unit": "mg",
              "raw_source_path": "ingredientRows[1]", "form_id": "butterbur (unspecified)"}
    entry = butterbur_entry()
    entry["applicability"].pop("required_form_terms")

    decision = assess_clinical_applicability(butterbur_product(second), entry)

    assert decision["status"] == "unresolved"
    assert decision["reason_code"] == "clinical_source_row_unresolved"


def test_one_source_row_stays_one_logical_row_across_both_projections():
    """Invariant: the label and enriched projections of a row are one row, not two.

    Deduplication must collapse them AND keep what only the enriched copy knows.
    """
    from clinical_applicability import _rows

    rows = list(_rows(butterbur_product()))
    butterbur_rows = [r for r in rows if r.get("canonical_id") == "butterbur"]

    assert len(butterbur_rows) == 1
    assert butterbur_rows[0]["form_id"] == "PA-free butterbur extract (Petadolex)"
    assert butterbur_rows[0]["quantity"] == 75.0


def test_deduplication_never_overwrites_what_the_label_row_already_states():
    """Enrichment fills gaps; it does not replace a value the label row carries."""
    from clinical_applicability import _rows

    product = butterbur_product()
    product["activeIngredients"][0]["form_id"] = "label-declared form"

    row = next(r for r in _rows(product) if r.get("canonical_id") == "butterbur")

    assert row["form_id"] == "label-declared form"


def test_daily_dose_cannot_borrow_an_amount_from_a_different_row():
    """The Migra-Eeze shape (328579): a big unspecified row beside a small studied-material row.

    The studied row is the one that links, and it must fail the floor on its own amount.
    """
    unspecified_bulk = {"name": "Butterbur root extract", "canonical_id": "butterbur",
                        "quantity": 150.0, "unit": "mg", "raw_source_path": "ingredientRows[1]",
                        "form_id": "butterbur (unspecified)"}
    product = butterbur_product(unspecified_bulk, resolved_form="PA-free butterbur extract (Petadolex)")
    product["activeIngredients"][0]["quantity"] = 22.5
    product["ingredient_quality_data"]["ingredients"][0]["quantity"] = 22.5
    product["servingSizes"] = [{"minDailyServings": 1, "maxDailyServings": 1}]

    decision = assess_clinical_applicability(product, butterbur_entry())

    assert decision["status"] == "not_applicable"
    assert decision["reason_code"] == "below_applicable_clinical_dose"


def test_serving_multiplication_uses_only_the_row_that_satisfied_the_scope():
    """50 mg x 3 servings reaches the studied 150 mg/day (293376 Petadolex Pro-Active)."""
    second = {"name": "Petasins", "canonical_id": "butterbur", "quantity": 7.5, "unit": "mg",
              "raw_source_path": "ingredientRows[1]", "form_id": "butterbur (unspecified)"}
    product = butterbur_product(second)
    product["activeIngredients"][0]["quantity"] = 50.0
    product["ingredient_quality_data"]["ingredients"][0]["quantity"] = 50.0
    product["servingSizes"] = [{"minDailyServings": 3, "maxDailyServings": 3}]

    assert assess_clinical_applicability(product, butterbur_entry())["status"] == "applicable"


def test_products_without_enrichment_resolved_forms_are_untouched_by_the_merge():
    """Legacy invariant: a product whose rows carry no resolved form behaves exactly as before."""
    from clinical_applicability import _rows

    product = zinc_product("zinc acetate", 80, "lozenge")
    rows = list(_rows(product))

    assert [dict(r) for r in rows] == product["ingredient_quality_data"]["ingredients_scorable"]


@pytest.mark.parametrize("record_id,name", [
    ("INGR_AMLA", "Amla fruit extract"),
    ("INGR_VITAMIN_B12", "Vitamin B12"),
])
def test_reference_only_registry_cannot_be_revived_by_stale_enriched_credit(record_id, name):
    """A withdrawn clinical credit stays withdrawn even with an older match."""
    from scoring_v4.scored_artifact import build_scored_artifact

    row = {"name": name, "standard_name": name, "canonical_id": "amla" if record_id == "INGR_AMLA" else "vitamin_b12_cobalamin",
           "mapped": True, "quantity": 500, "unit": "mg",
           "raw_source_text": name, "raw_source_path": "ingredientRows[0]"}
    stale = {"id": record_id, "ingredient": name, "standard_name": name,
             "study_type": "rct_multiple", "evidence_level": "ingredient-human",
             "effect_direction": "positive_strong", "total_enrollment": 500,
             "matched_source_row_refs": ["ingredientRows[0]"],
             "applicability": {"scope": "ingredient"}}
    product = {"id": "test_reference_guard", "status": "active",
               "form_factor_canonical": "capsule",
               "ingredient_quality_data": {"ingredients": [row], "ingredients_scorable": [row]},
               "evidence_data": {"clinical_matches": [stale]}}
    assert resolved_clinical_matches(product)[0] == []
    artifact = build_scored_artifact(product)
    assert artifact["_v4_module_breakdown"]["dimensions"]["evidence"]["metadata"].get("matched_entries", 0) == 0
    if record_id == "INGR_VITAMIN_B12":
        evidence = artifact["_v4_module_breakdown"]["dimensions"]["evidence"]
        assert evidence["metadata"]["nutrition_authority_canonical"] == "vitamin_b12_cobalamin"
        assert evidence["metadata"]["nutrition_authority_floor_applied"] is True
        assert evidence["score"] == 10.0


@pytest.mark.parametrize("record_id", [
    "INGR_BIFIDOBACTERIUM_LONGUM", "INGR_LACTOBACILLUS_ACIDOPHILUS",
])
@pytest.mark.parametrize("suffix", ["", " BB536", " 1714", " 35624", " NCFM"])
def test_generic_probiotic_summary_cannot_supply_species_or_sibling_strain_credit(record_id, suffix):
    from scoring_v4.scored_artifact import build_scored_artifact

    entry = reviewed_entries()[record_id]
    name = entry["standard_name"] + suffix
    row = {"name": name, "standard_name": name,
           "canonical_id": "bifidobacterium_longum" if "LONGUM" in record_id else "lactobacillus_acidophilus",
           "mapped": True, "quantity": 100, "unit": "mg",
           "raw_source_text": name, "raw_source_path": "ingredientRows[0]"}
    stale = {**entry, "ingredient": name, "study_type": "rct_multiple",
             "evidence_level": "ingredient-human", "effect_direction": "positive_strong",
             "matched_source_row_refs": ["ingredientRows[0]"],
             "applicability": {"scope": "ingredient"}}
    product = {"id": "test_species_scope", "status": "active",
               "form_factor_canonical": "capsule",
               "ingredient_quality_data": {"ingredients": [row], "ingredients_scorable": [row]},
               "evidence_data": {"clinical_matches": [stale]}}
    assert entry["study_type"] == entry["evidence_level"] == "reference"
    assert resolved_clinical_matches(product)[0] == []
    artifact = build_scored_artifact(product)
    assert artifact["_v4_module_breakdown"]["dimensions"]["evidence"]["metadata"].get("matched_entries", 0) == 0


def test_probiotic_summary_claims_keep_trial_scope_and_endpoint_roles():
    longum = reviewed_entries()["INGR_BIFIDOBACTERIUM_LONGUM"]
    acidophilus = reviewed_entries()["INGR_LACTOBACILLUS_ACIDOPHILUS"]
    assert "RCT" not in longum["published_studies"]
    assert "38341968" not in json.dumps(longum)
    assert "43.4%" in longum["key_endpoints"][0] and "TISS" in longum["key_endpoints"][0]
    for entry in (longum, acidophilus):
        assert "total_enrollment" not in entry
        assert "published_studies_count" not in entry
        assert "registry_completed_trials_count" not in entry
    assert "single-strain evidence from LAPIBSS" not in json.dumps(acidophilus)
    assert "primary" in acidophilus["key_endpoints"][0].lower()
    assert "null" in acidophilus["key_endpoints"][0].lower()
    assert "10 billion" in acidophilus["key_endpoints"][0]
    ref = next(r for r in acidophilus["references_structured"] if r.get("nct_id") == "NCT02103972")
    assert ref["evidence_grade"] == "reference"
    assert "not acidophilus" in ref["note"].lower()


@pytest.mark.parametrize("canonical,name", [("alpha_linolenic_acid", "Alpha-Linolenic Acid"), ("alpha_linolenic_acid", "ALA Omega-3")])
def test_marine_omega_study_does_not_transfer_to_plant_ala(canonical, name):
    from scoring_v4.scored_artifact import build_scored_artifact
    from tests.test_v4_generic_evidence_p133 import _ingredient, _match, _product

    row = _ingredient(name=name, canonical_id=canonical, quantity=1000, unit="mg")
    row["raw_source_path"] = "ingredientRows[0]"
    match = _match(id="INGR_OMEGA3", ingredient=name, standard_name="Omega-3 Fatty Acids",
                   matched_canonical_ids=[canonical], matched_source_row_refs=["ingredientRows[0]"])
    # Stale enriched success must not overrule the reviewed intervention.
    match["applicability"] = {"scope": "ingredient"}
    match["applicability_assessment"] = {"status": "applicable"}
    product = _product(product_name=name, ingredients=[row], matches=[match])
    assert assess_clinical_applicability(product, match)["status"] == "not_applicable"
    artifact = build_scored_artifact(product)
    assert artifact["quality_pillars_v4"]["evidence"]["score"] == 0


@pytest.mark.parametrize("canonical,name", [("epa", "EPA"), ("dha", "DHA")])
def test_marine_omega_identity_controls_remain_applicable(canonical, name):
    product = zinc_product()
    row = product["ingredient_quality_data"]["ingredients_scorable"][0]
    row.update(name=name, standard_name=name, canonical_id=canonical, quantity=1000)
    match = {"id": "INGR_OMEGA3", "ingredient": name, "matched_canonical_ids": [canonical],
             "matched_source_row_refs": ["ingredientRows[0]"]}
    assert assess_clinical_applicability(product, match)["status"] == "applicable"


@pytest.mark.parametrize("reverse", [False, True])
def test_exclusion_only_scope_retains_every_valid_marine_row_independent_of_order(reverse):
    from tests.test_v4_generic_evidence_p133 import _ingredient, _match, _product
    rows = []
    for i, (canonical, name, amount) in enumerate([(
            "epa", "EPA", 100), ("dha", "DHA", 1000),
            ("alpha_linolenic_acid", "Alpha-Linolenic Acid", 1500)]):
        row = _ingredient(name=name, canonical_id=canonical, quantity=amount, unit="mg")
        row["raw_source_path"] = f"ingredientRows[{i}]"
        rows.append(row)
    match = _match(id="INGR_OMEGA3", ingredient="Omega-3 Fatty Acids",
                   standard_name="Omega-3 Fatty Acids",
                   matched_canonical_ids=[r["canonical_id"] for r in rows],
                   matched_source_row_refs=[r["raw_source_path"] for r in rows])
    product = _product(ingredients=rows[::-1] if reverse else rows, matches=[match])
    accepted, rejected = filter_clinical_matches(product, [match])
    assert not rejected
    assert set(accepted[0]["matched_source_row_refs"]) == {"ingredientRows[0]", "ingredientRows[1]"}
    assert set(accepted[0]["matched_canonical_ids"]) == {"epa", "dha"}
def test_spirulina_endpoint_summaries_preserve_population_and_comparator():
    """Disease-specific and within-group results are not general efficacy."""
    import json
    from pathlib import Path
    from data_batch import entries

    data = json.loads((Path(__file__).parents[1] / "data" / "backed_clinical_studies.json").read_text())
    record = entries(data)["backed_clinical_studies/INGR_SPIRULINA"]
    endpoints = record["key_endpoints"]
    hiv = next(text for text in endpoints if "25057105" in text)
    nephrotic = next(text for text in endpoints if "12487756" in text)
    assert "HIV" in hiv and "women" in hiv
    assert "no between-group differences in immunological or virological markers" in hiv
    assert "within-group" in nephrotic and "children" in nephrotic
    assert "medication-only control" in nephrotic
    assert "not placebo-adjusted treatment effects" in nephrotic
    assert "not evidence of general longevity benefit" in record["notes"]


@pytest.mark.parametrize('legacy', [False, True])
def test_amount_independent_applicability_keeps_provider_owned_undosed_member(monkeypatch, legacy):
    import clinical_applicability as ca
    from scoring_input_contract import get_evidence_subject_rows
    row = {'name':'Bromelain', 'raw_source_text':'Bromelain', 'canonical_id':'bromelain',
           'role_classification':'inactive_non_scorable', 'cleaner_row_role':'named_blend_member',
           'source_section':'active', 'raw_source_path':'ingredientRows[0].nestedRows[0]',
           'quantity':0, 'unit':'NP', 'matched_form':'Bromelain'}
    product = {'activeIngredients':[row], 'ingredient_quality_data':{'ingredients':[row], 'ingredients_scorable':[]}}
    assert get_evidence_subject_rows(product)
    entry = {'id':'TEST_UNDOSED', 'ingredient':'Bromelain','matched_source_row_refs':[row['raw_source_path']],
             'matched_canonical_ids':['bromelain'],'study_type':'rct_single'}
    if legacy:entry['exclude_aliases']=['other preparation']
    else:entry['applicability']={'scope':'ingredient', 'required_form_terms':['bromelain'], 'minimum_daily_dose':100, 'dose_unit':'mg'}
    monkeypatch.setattr(ca,'reviewed_entries', lambda: {})
    assert assess_clinical_applicability(product,entry,assess_amount=False)['status'] in {'applicable','not_curated'}
    if not legacy:
        assert assess_clinical_applicability(product,entry,assess_amount=True)['status'] in {'unresolved', 'not_applicable'}
    else:
        assert assess_clinical_applicability(product,entry,assess_amount=True)['status'] == 'not_curated'
    from dose_assessment import positive_clinical_benchmark
    assert positive_clinical_benchmark(product,row) is None


def test_provider_owned_anchor_uses_its_exact_named_child_without_lending_mass(monkeypatch):
    import scoring_input_contract as contract
    import clinical_applicability as ca
    child = {'name': 'Cinnamon Extract', 'canonical_id': 'cinnamon', 'raw_source_path': 'ingredientRows[0].forms[0]',
             'parent_source_path': 'ingredientRows[0]', 'source_section': 'active', 'quantity': 0, 'unit': 'mg'}
    sibling = {**child, 'name': 'Other Extract', 'canonical_id': 'other', 'raw_source_path': 'ingredientRows[0].forms[1]'}
    anchor = {**child, 'raw_source_path': 'ingredientRows[0]', 'quantity': 3200,
              'scoring_input_kind': 'product_level_evidence', 'evidence_scope': 'blend_level'}
    product = {'activeIngredients': [child, sibling], 'ingredient_quality_data': {'ingredients_scorable': [child, sibling]}}
    monkeypatch.setattr(contract, 'get_evidence_subject_rows', lambda _: [anchor, sibling])
    entry = {'ingredient': 'Cinnamon Extract', 'matched_canonical_ids': ['cinnamon'], 'matched_source_row_refs': ['ingredientRows[0]']}
    linked = ca._linked_rows(product, entry, evidence_only=True)
    assert [r['raw_source_path'] for r in linked] == ['ingredientRows[0].forms[0]']
    assert linked[0]['quantity'] == 0
    assert ca._linked_rows(product, entry, evidence_only=False) == []
    entry['matched_canonical_ids'] = ['other']
    assert ca._linked_rows(product, entry, evidence_only=True) == []
    entry['matched_canonical_ids'] = ['cinnamon']
    entry['matched_source_row_refs'] = ['ingredientRows[0]', 'ingredientRows[1]']
    child['parent_source_path'] = 'ingredientRows[1]'
    assert ca._linked_rows(product, entry, evidence_only=True) == []


def test_form_only_review_has_no_exposure_prerequisite(monkeypatch):
    import clinical_applicability as ca
    row = {'name':'Bromelain','raw_source_text':'Bromelain','canonical_id':'bromelain',
           'role_classification':'inactive_non_scorable','cleaner_row_role':'named_blend_member',
           'source_section':'active','raw_source_path':'ingredientRows[0].nestedRows[0]',
           'quantity':0,'unit':'NP','matched_form':'Bromelain'}
    product = {'activeIngredients':[row], 'ingredient_quality_data':{'ingredients':[row],'ingredients_scorable':[]}}
    monkeypatch.setattr(ca,'reviewed_entries', lambda: {})
    entry = {'id':'TEST_FORM_ONLY','ingredient':'Bromelain','matched_source_row_refs':[row['raw_source_path']],
             'applicability':{'scope':'ingredient','required_form_terms':['bromelain']}}
    assert ca.assess_clinical_applicability(product,entry)['status'] == 'applicable'
    entry['applicability'].update(minimum_daily_dose=100,dose_unit='mg')
    assert ca.assess_clinical_applicability(product,entry)['status'] in {'not_applicable','unresolved'}


def test_source_required_anchor_binds_printed_child_before_structural_header(monkeypatch):
    import clinical_applicability as ca
    import scoring_input_contract as contract
    header = {'name':'Organic Botanical Blend','raw_source_text':'Organic Botanical Blend',
              'raw_source_path':'ingredientRows[0]','canonical_id':'structural_blend',
              'quantity':10000,'unit':'mg','score_eligible_by_cleaner':False,'source_section':'active'}
    child = {'name':'Inulin','raw_source_text':'Inulin','canonical_id':'inulin',
             'raw_source_path':'ingredientRows[0].nestedRows[0]',
             'quantity':0,'unit':'NP','source_section':'active','score_eligible_by_cleaner':False}
    anchor = {**child,'raw_source_path':'ingredientRows[0]','quantity':10000,'unit':'mg',
              'scoring_input_kind':'product_level_evidence','evidence_scope':'blend_level',
              'linked_rows':['ingredientRows[0]',child['raw_source_path']]}
    product = {'activeIngredients':[header,child],'ingredient_quality_data':{'ingredients_scorable':[]}}
    monkeypatch.setattr(contract,'get_evidence_subject_rows', lambda _: [anchor])
    monkeypatch.setattr(ca,'reviewed_entries',lambda:{})
    entry = {'id':'TEST_INULIN_ANCHOR','ingredient':'Inulin','matched_canonical_ids':['inulin'],
             'matched_source_row_refs':['ingredientRows[0]'],
             'applicability':{'scope':'ingredient','required_form_terms':['inulin'],'require_source_label_form':True}}
    result=ca.assess_clinical_applicability(product,entry,assess_amount=False)
    assert result['status']=='applicable'
    assert result['source_row_ref']==child['raw_source_path']
    child['raw_source_text']='Different Material';child['name']='Different Material'
    assert ca.assess_clinical_applicability(product,entry,assess_amount=False)['status']=='not_applicable'


@pytest.mark.parametrize("source_name,source_form,eligible", [
    ("Creatine Monohydrate", None, True),
    ("Creatin Monohydrate", None, True),
    ("Creapure", None, True),
    ("Micronized Creatine", "Creatine Monohydrate", True),
    ("Con-Cret", "Creatine Hydrochloride", False),
    ("Creatine", None, False),
    ("Creatine Citrate", None, False),
    ("Creatine Nitrate", None, False),
])
def test_monohydrate_research_requires_its_printed_preparation(source_name, source_form, eligible):
    row = {"name": source_name, "source_label_name": source_name,
           "raw_source_text": source_name, "canonical_id": "creatine_monohydrate",
           "mapped": True, "quantity": 2000, "unit": "mg",
           "raw_source_path": "ingredientRows[0]", "matched_form": "creatine monohydrate",
           "raw_taxonomy": {"forms": [{"name": source_form}] if source_form else []}}
    product = {"fullName": "Creatine", "activeIngredients": [deepcopy(row)],
               "ingredient_quality_data": {"ingredients_scorable": [row]},
               "evidence_data": {"clinical_matches": [{
                   **reviewed_entries()["INGR_CREATINE_MONOHYDRATE"],
                   "matched_canonical_ids": ["creatine_monohydrate"],
                   "matched_source_row_refs": ["ingredientRows[0]"],
               }]}}
    matches, _ = resolved_clinical_matches(product)
    assert bool(matches) is eligible
    if eligible:
        assert matches[0]["matched_source_row_refs"] == ["ingredientRows[0]"]
    else:
        evidence = score_evidence(product)
        assert evidence["metadata"]["matched_entries"] == 0
        assert evidence["metadata"]["primary_evidence_floor"] == 0


@pytest.mark.parametrize("source_form,eligible", [("Creatine Hydrochloride", False), ("Creatine Monohydrate", True)])
def test_raw_triphase_material_keeps_sports_identity_without_borrowing_monohydrate(source_form, eligible):
    from pathlib import Path
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    from scoring_v4.scored_artifact import build_scored_artifact
    raw = json.loads((Path(__file__).parent / "fixtures/triphase_317610_raw.json").read_text())
    if eligible:
        # An explicit monohydrate variant is the form-qualified adverse control.
        row = next(row for row in raw["ingredientRows"] if row["name"] == "Con-Cret")
        row["name"] = source_form
        row["ingredientGroup"] = "Creatine"
        row["forms"][0]["name"] = source_form
    enriched, errors = SupplementEnricherV3().enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    assert not errors
    artifact = build_scored_artifact(deepcopy(enriched))
    assert artifact["_v4_module"] == "sports"
    matches, _ = resolved_clinical_matches(enriched)
    assert any(match["id"] == "INGR_CREATINE_MONOHYDRATE" for match in matches) is eligible
    evidence = artifact["_v4_module_breakdown"]["dimensions"]["evidence"]["metadata"]
    assert ("creatine_monohydrate" in evidence["ingredient_points"]) is eligible
    assert "beta-alanine" in evidence["ingredient_points"]
    if not eligible:
        assert evidence["primary_evidence_floor_canonical"] != "creatine monohydrate"
        material = next(row for row in enriched["ingredient_quality_data"]["ingredients"]
                        if row.get("raw_source_path") == "ingredientRows[5]")
        assert material["canonical_id"] == "creatine_monohydrate"
        assert material["raw_taxonomy"]["forms"][0]["name"] == "Creatine Hydrochloride"
        assert material["quantity"] == 2.0


def test_monohydrate_scope_binds_only_its_source_row_beside_hydrochloride():
    rows = []
    for index, form in enumerate(["Creatine Hydrochloride", "Creatine Monohydrate"]):
        rows.append({"name": form, "raw_source_text": form, "source_label_name": form,
                     "canonical_id": "creatine_monohydrate", "mapped": True,
                     "quantity": 1000 + index, "unit": "mg",
                     "raw_source_path": f"ingredientRows[{index}]"})
    entry = {**reviewed_entries()["INGR_CREATINE_MONOHYDRATE"],
             "matched_canonical_ids": ["creatine_monohydrate"],
             "matched_source_row_refs": ["ingredientRows[0]", "ingredientRows[1]"]}
    product = {"fullName": "Creatine", "activeIngredients": deepcopy(rows),
               "ingredient_quality_data": {"ingredients_scorable": rows}}
    matches, _ = filter_clinical_matches(product, [entry], assess_amount=False)
    assert len(matches) == 1
    assert matches[0]["matched_source_row_refs"] == ["ingredientRows[1]"]
    assert [row["quantity"] for row in product["activeIngredients"]] == [1000, 1001]


def test_meriva_verified_disease_research_keeps_existing_reference_only_guard():
    from pathlib import Path
    data = json.loads((Path(__file__).resolve().parents[1] / "data" / "backed_clinical_studies.json").read_text())
    entry = next(r for r in data["backed_clinical_studies"] if r["id"] == "BRAND_MERIVA")
    assert entry["primary_outcome"] != "Reduce Stress/Anxiety"
    assert "muscle_recovery" not in entry["endpoint_relevance_tags"]
    assert "meta-analysis" not in entry["published_studies"]
    assert entry["total_enrollment"] == 215
    assert entry.get("registry_completed_trials_count") is None
    assert {r["pmid"] for r in entry["references_structured"]} == {"21194249", "26090395", "38809154"}
    assert entry["external_ids"].get("unii") is None  # pure curcumin is not the whole phytosome
    decision = assess_clinical_applicability({}, entry)
    assert decision == {"status": "not_applicable", "reason_code": "reference_only_clinical_record"}


@pytest.mark.parametrize('label,forms,accepted', [
    ('Shilajit', [], False),
    ('Himalayan Shilajit Extract', [], False),
    ('Purified Shilajit', [], False),
    ('Processed Shilajit', [], False),
    ('PrimaVie Shilajit', [], True),
    ('PrimaVie Shilajit extract', [], True),
    ('PrimaVie', [{'name': 'Shilajit Extract'}], True),
])
def test_shilajit_native_evidence_requires_studied_preparation(enricher, label, forms, accepted):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from scoring_v4.scored_artifact import build_scored_artifact
    raw = {'id': 'SHILAJIT_SCOPE', 'fullName': 'Shilajit tablets', 'brandName': 'Regression',
           'physicalState': {'name': 'Tablet'},
           'servingSizes': [{'minQuantity': 1, 'maxQuantity': 1, 'unit': 'Tablet(s)'}],
           'ingredientRows': [{'name': label, 'forms': forms, 'nestedRows': [],
                               'quantity': [{'quantity': 500, 'unit': 'mg'}]}],
           'otherIngredients': {'ingredients': []}}
    product, _ = enricher.enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    artifact = build_scored_artifact(product)
    matches, _ = resolved_clinical_matches(product)
    ids = {m['id'] for m in matches}
    assert 'PRECLIN_SHILAJIT_GENERIC' not in ids
    assert ('BRAND_PRIMAVIE_SHILAJIT' in ids) is accepted
    if label == 'Processed Shilajit':
        assert artifact['quality_score_status'] == 'not_scored'  # Unmapped named form stays held.
    else:
        assert len(artifact['quality_pillars_v4']) == 6
    if accepted:
        match = next(m for m in matches if m['id'] == 'BRAND_PRIMAVIE_SHILAJIT')
        assert match['matched_source_row_refs'] == ['ingredientRows[0]']
        row = product['ingredient_quality_data']['ingredients_scorable'][0]
        assert row['matched_form'] == 'primavie shilajit'
        assessed = artifact['assessment_readiness']['evidence']['ingredient_assessments'][0]
        assert 'BRAND_PRIMAVIE_SHILAJIT' in assessed['evidence_ids']
        assert match['study_type'] == 'rct_single'
        assert match['effect_direction'] == 'positive_weak'
        assert match['applicability_assessment']['supported_outcomes'] == ['testosterone']


def test_shilajit_records_preserve_research_without_unsupported_outcomes():
    records = reviewed_entries()
    for key in ['PRECLIN_SHILAJIT_GENERIC', 'BRAND_PRIMAVIE_SHILAJIT']:
        entry = records[key]
        assert {r['pmid'] for r in entry['references_structured']} == {'20078516', '26395129'}
        assert entry['health_goals_supported'] == []
        assert entry['endpoint_relevance_tags'] == []
        assert 'registry_completed_trials_count' not in entry
        assert 'rct_multiple' not in json.dumps(entry)
    assert records['PRECLIN_SHILAJIT_GENERIC']['study_type'] == 'reference'
    assert records['BRAND_PRIMAVIE_SHILAJIT']['total_enrollment'] == 96


@pytest.mark.parametrize('label,source_forms,guessed_form,accepted', [
    ('Peppermint Extract', [], '', False),
    ('Mentha Piperita Extract', [], '', False),
    ('Peppermint Oil', [], '', False),
    ('Enteric-coated Peppermint Extract', [], '', False),
    ('Peppermint Extract', [], 'enteric-coated peppermint oil', False),
    ('Enteric-coated Peppermint Oil', [], '', True),
    ('Peppermint Oil', [{'name': 'enteric-coated'}], '', True),
    ('IBgard Peppermint Oil', [], '', True),
])
def test_peppermint_literature_requires_source_oil_and_delivery(enricher, label, source_forms, guessed_form, accepted):
    import evidence_resolver as er
    from scoring_v4.scored_artifact import build_scored_artifact
    row = {'name': label, 'canonical_id': 'peppermint', 'quantity': 200, 'unit': 'mg',
           'raw_source_path': 'ingredientRows[0]', 'raw_source_text': label,
           'raw_taxonomy': {'forms': source_forms}, 'matched_form': guessed_form}
    product = {'id': 'PEPPERMINT_SCOPE', 'activeIngredients': [row],
               'ingredient_quality_data': {'ingredients': [row], 'ingredients_scorable': [row]}}
    product['delivery_data'] = enricher._collect_delivery_data(product)
    result = er.resolve_evidence_for_row(row, product)
    assert (result.disposition == er.EvidenceDisposition.RESOLVED_BY_REVIEWED_CLINICAL_EVIDENCE.value) is accepted
    if 'literature_evidence' in result.owner_facts:
        assert '24100754' in result.owner_facts['literature_evidence']['pmids']
    if 'IBgard' in label:
        assert '26319955' in {r['pmid'] for r in reviewed_entries()['INGR_PEPPERMINT_OIL']['references_structured']}
    artifact = build_scored_artifact(product)
    assert len(artifact['quality_pillars_v4']) == 6


def test_peppermint_scored_record_retains_mixed_primary_outcome_evidence():
    entry = reviewed_entries()['INGR_PEPPERMINT_OIL']
    assert entry['external_ids']['unii'] == 'AV092KU4JH'
    assert entry['effect_direction'] == 'mixed'
    assert entry['total_enrollment'] == 1030
    assert 'registry_completed_trials_count' not in entry
    assert not {'joint_pain', 'sleep', 'stress_mood'} & set(entry['endpoint_relevance_tags'])
    assert {r['pmid'] for r in entry['references_structured']} >= {'35942669', '31470006'}
    assert 'primary' in entry['notable_studies'] and 'not' in entry['notable_studies']


@pytest.mark.parametrize('label,notes,source,extra,accepted', [
    ('Peppermint Oil', 'Enteric coated to minimize aftertaste', 'statements[0]', False, True),
    ('Peppermint Aerial Parts Oil', 'Enteric coating withstands stomach acid', 'statements[0]', False, True),
    ('Peppermint Extract', 'Enteric coated to minimize aftertaste', 'statements[0]', False, False),
    ('Peppermint Oil', 'Ordinary softgel', 'statements[0]', False, False),
    ('Peppermint Oil', 'Not enteric coated', 'statements[0]', False, False),
    ('Peppermint Oil', 'Enteric coated to minimize aftertaste', 'statements[99]', False, False),
    ('Peppermint Oil', 'Enteric coated fish oil', 'statements[0]', True, False),
])
def test_clinical_delivery_binds_existing_source_provenance(label, notes, source, extra, accepted):
    entry = reviewed_entries()['INGR_PEPPERMINT_OIL']
    row = {'name': label, 'canonical_id': 'peppermint', 'raw_source_text': label,
           'quantity': 200, 'unit': 'mg', 'raw_source_path': 'ingredientRows[0]'}
    product = {'activeIngredients': [row], 'statements': [{'type': 'Formulation re: Other', 'notes': notes}],
               'delivery_data': {'systems': [{'canonical_name': 'enteric-coated', 'raw_source_text': 'Enteric coating' if 'coating' in notes else 'Enteric coated', 'match_source': source}]}}
    if extra:
        product['activeIngredients'].append({'name': 'Fish Oil', 'raw_source_text': 'Fish Oil', 'quantity': 1000, 'unit': 'mg', 'raw_source_path': 'ingredientRows[1]'})
    scope = {**entry, 'ingredient': label, 'matched_source_row_refs': ['ingredientRows[0]']}
    assert (assess_clinical_applicability(product, scope, assess_amount=False)['status'] == 'applicable') is accepted


@pytest.mark.parametrize('nested,title', [(False,'Ingredient capsules'),(False,'Enteric-coated peppermint capsules'),(True,'Ingredient capsules')])
def test_native_delivery_keeps_nested_and_row_local_evidence(enricher,nested,title):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from scoring_v4.scored_artifact import build_scored_artifact
    rows=[{'name':'Peppermint Oil','forms':[{'name':'enteric-coated'}],'nestedRows':[], 'quantity':[{'quantity':200,'unit':'mg'}]},
          {'name':'Ginger Root','forms':[],'nestedRows':[],'quantity':[{'quantity':200,'unit':'mg'}]}]
    if nested:
        rows=[{'name':'Digestive Blend','nestedRows':rows,'quantity':[{'quantity':400,'unit':'mg'}]}]
    raw={'id':'DELIVERY_SCOPE','fullName':title,'brandName':'Regression','physicalState':{'name':'Capsule'},
         'servingSizes':[{'minQuantity':1,'maxQuantity':1,'unit':'Capsule(s)'}],
         'ingredientRows':rows,'otherIngredients':{'ingredients':[]}}
    product,_=enricher.enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    matches,_=resolved_clinical_matches(product)
    assert 'INGR_PEPPERMINT_OIL' in {m['id'] for m in matches}
    if title.startswith('Enteric-coated'):
        sources = [x for x in product['delivery_data']['systems'] if x['name'] == 'enteric-coated']
        assert len(sources) >= 2  # Title cannot erase the ingredient-local proof.
        assert product['match_ledger']['domains']['delivery']['matched'] == 1
    artifact=build_scored_artifact(product)
    assert artifact['quality_score_status'] in {'scored', 'not_scored'}
    # Form mapping remains an independent gate; source applicability must not
    # manufacture a mapped ingredient form to make the overall score visible.
    assert score_evidence(product, owner_scoped=True)['score'] > 0


def test_source_strict_delivery_cannot_trust_generated_form_factor():
    row={'name':'Peppermint Oil','raw_source_text':'Peppermint Oil','raw_source_path':'ingredientRows[0]', 'quantity':200,'unit':'mg'}
    entry={**reviewed_entries()['INGR_PEPPERMINT_OIL'],'matched_source_row_refs':['ingredientRows[0]']}
    product={'activeIngredients':[row],'form_factor_canonical':'enteric-coated','physicalState':{'name':'Capsule'},'delivery_data':{'systems':[]}}
    assert assess_clinical_applicability(product,entry,assess_amount=False)['status']=='not_applicable'


@pytest.mark.parametrize('purpose,accepted',[('energy',False),('longevity',False),('testosterone',True)])
def test_primavie_native_trial_cannot_substitute_unrelated_declared_purpose(enricher,purpose,accepted):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from scoring_v4.scored_artifact import build_scored_artifact
    raw={'id':'PRIMAVIE_PURPOSE','fullName':'PrimaVie capsules','brandName':'Regression','physicalState':{'name':'Capsule'},
         'servingSizes':[{'minQuantity':1,'maxQuantity':1,'unit':'Capsule(s)'}],
         'ingredientRows':[{'name':'PrimaVie Shilajit','forms':[],'nestedRows':[],'quantity':[{'quantity':500,'unit':'mg'}]}],
         'statements':[{'type':'Formula re: Contains','notes':f'Shilajit supports {purpose}.'}], 'otherIngredients':{'ingredients':[]}}
    product,_=enricher.enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    artifact=build_scored_artifact(product)
    assert (artifact['quality_pillars_v4']['evidence']['score'] > 0) is accepted


@pytest.mark.parametrize('context', [
    {'fullName':'Ileocolonic Peppermint Oil'},
    {'statements':[{'type':'Formula re: Contains','notes':'Ileocolonic-release peppermint oil'}]},
])
def test_explicit_sole_active_delivery_exclusion_overrides_other_positive_source(enricher,context):
    row={'name':'Peppermint Oil','raw_source_text':'Peppermint Oil','raw_source_path':'ingredientRows[0]',
         'quantity':200,'unit':'mg','raw_taxonomy':{'forms':[{'name':'enteric-coated'}]}}
    product={'activeIngredients':[row],**context}
    product['delivery_data']=enricher._collect_delivery_data(product)
    entry={**reviewed_entries()['INGR_PEPPERMINT_OIL'],'matched_source_row_refs':['ingredientRows[0]']}
    assert assess_clinical_applicability(product,entry,assess_amount=False)['status']=='not_applicable'


def test_native_two_explicit_functions_keep_unbenchmarked_caffeine_in_dose(enricher):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from scoring_v4.scored_artifact import build_scored_artifact
    raw = {'id': 'TWO_SOURCE_FUNCTIONS', 'fullName': 'Everyday Energy', 'brandName': 'Regression',
           'physicalState': {'name': 'Powder'},
           'servingSizes': [{'minQuantity': 1, 'maxQuantity': 1, 'unit': 'Scoop(s)'}],
           'ingredientRows': [
               {'name': 'CoQ10', 'forms': [], 'nestedRows': [], 'quantity': [{'quantity': 100, 'unit': 'mg'}]},
               {'name': 'Caffeine', 'forms': [], 'nestedRows': [], 'quantity': [{'quantity': 40, 'unit': 'mg'}]}],
           'statements': [{'type': 'Formula re: Contains', 'notes':
               'Caffeine helps aid attention and alertness. CoQ10 supports energy production.'}],
           'otherIngredients': {'ingredients': []}}
    product, _ = enricher.enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    artifact = build_scored_artifact(product)
    dose = artifact['_v4_module_breakdown']['dimensions']['dose']['metadata']
    assert dose['purpose_ingredient_count'] == 2
    assert 'caffeine' in dose['unbenchmarked_purpose_ingredients']
    assert not dose['positive_clinical_benchmark_assessments']


@pytest.mark.parametrize("notes, marker, extra, accepted", [
    ("Soothes occasional digestive discomfort\r\nEnteric coating withstands stomach acid\r\nDelivers to the area of discomfort", None, False, True),
    ("Digestive support. Enteric coating withstands stomach acid. Swallow whole.", None, False, True),
    ("Digestive support\nNot enteric coated\nSwallow whole", None, False, False),
    ("Digestive support\nNot enteric coated\nSwallow whole", "enteric coated", False, False),
    ("Digestive support\nEnteric coating withstands stomach acid", "Different source\nEnteric coating withstands stomach acid", False, False),
    ("Digestive support\nEnteric coating withstands stomach acid", None, True, False),
    ("Digestive support\nOrdinary capsule", None, False, False),
])
def test_multiclause_delivery_marker_preserves_provenance_and_negation(notes, marker, extra, accepted):
    row = {"name": "Peppermint Aerial Parts Oil", "canonical_id": "peppermint",
           "raw_source_text": "Peppermint Aerial Parts Oil", "quantity": 0.2, "unit": "mL",
           "raw_source_path": "ingredientRows[0]"}
    product = {"activeIngredients": [row],
               "statements": [{"type": "Formulation re: Other", "notes": notes}],
               "delivery_data": {"systems": [{"canonical_name": "enteric-coated",
                   "match_source": "statements[0]", "raw_source_text": marker or notes}]}}
    if extra:
        product["activeIngredients"].append({"name": "Fish Oil", "raw_source_text": "Fish Oil",
            "quantity": 1000, "unit": "mg", "raw_source_path": "ingredientRows[1]"})
    entry = {**reviewed_entries()["INGR_PEPPERMINT_OIL"],
             "ingredient": row["name"], "matched_source_row_refs": [row["raw_source_path"]]}
    result = assess_clinical_applicability(product, entry, assess_amount=False)
    assert (result["status"] == "applicable") is accepted


@pytest.mark.parametrize('missing', ['identity', 'route', 'exposure_basis', 'population', 'outcomes',
                                    'source_pmids', 'limitations', 'clinical_review', 'dose'])
def test_contributing_record_requires_complete_authoritative_source_context(monkeypatch, missing):
    import clinical_applicability
    from test_assessment_readiness import _install_completed_release_context
    context = _install_completed_release_context(monkeypatch)
    assert clinical_applicability.assess_clinical_source_review({'id': 'used'})['is_complete'] is True
    context.pop(missing)
    # A caller's optimistic receipt cannot repair the source record.
    result = clinical_applicability.assess_clinical_source_review({'id': 'used',
        'source_review': {'is_complete': True}, 'study_contexts': [{'review_status': 'clinician_approved'}]})
    assert result['is_complete'] is False
    assert result['errors']


@pytest.mark.parametrize('status,expected', [('verified', True), ('source_not_reported', True),
                                            ('extraction_pending', False)])
def test_source_regimen_review_is_not_a_required_numeric_dose_benchmark(monkeypatch, status, expected):
    from test_assessment_readiness import _install_completed_release_context
    from clinical_applicability import assess_clinical_source_review
    context = _install_completed_release_context(monkeypatch, status)
    assert 'minimum_daily_dose' not in context['dose']
    assert 'maximum_daily_dose' not in context['dose']
    assert assess_clinical_source_review({'id': 'used'})['is_complete'] is expected


@pytest.mark.parametrize('field,value', [('human_status', 'ambiguous'), ('source_integrity', 'expression_of_concern')])
def test_approval_without_eligibility_flag_cannot_complete_uncertain_source(monkeypatch, field, value):
    from test_assessment_readiness import _install_completed_release_context
    from clinical_applicability import assess_clinical_source_review
    context = _install_completed_release_context(monkeypatch)
    context.pop('scoring_eligible', None)
    context[field] = value
    assert assess_clinical_source_review({'id': 'used'})['is_complete'] is False


@pytest.mark.parametrize('field,value', [('administration_frequency', None),
    ('administration_frequency', 'extraction_pending'), ('co_therapies', None)])
def test_incomplete_regimen_cannot_be_a_completed_source_review(monkeypatch, field, value):
    from test_assessment_readiness import _install_completed_release_context
    from clinical_applicability import assess_clinical_source_review
    context = _install_completed_release_context(monkeypatch)
    assert assess_clinical_source_review({'id': 'used'})['is_complete']
    if value is None:
        context['dose'].pop(field)
    else:
        context['dose'][field] = value
    assert not assess_clinical_source_review({'id': 'used'})['is_complete']


def test_malformed_curated_context_cannot_silently_disappear(monkeypatch):
    import clinical_applicability
    from test_assessment_readiness import _install_completed_release_context
    context = _install_completed_release_context(monkeypatch)
    monkeypatch.setattr(clinical_applicability, 'reviewed_entries',
                        lambda: {'used': {'study_contexts': [context, 'malformed']}})
    assert not clinical_applicability.assess_clinical_source_review({'id': 'used'})['is_complete']


def _scored_glucosamine_copy(monkeypatch, *, pending_contexts=False):
    """A credit-path copy of the real glucosamine owner.

    Dr. Pham's 2026-10-28 ruling made INGR_GLUCOSAMINE_SULFATE (with chondroitin)
    a completed reference-only review, which short-circuits before the
    hydrochloride exclusion. The copy keeps the real applicability scope and
    contexts and restores the pre-ruling credit path so the exclusion itself
    stays tested.
    """
    import clinical_applicability
    owners = deepcopy(reviewed_entries())
    record = owners['INGR_GLUCOSAMINE_SULFATE']
    assert record['study_type'] == record['evidence_level'] == 'reference'
    record.update(study_type='systematic_review_meta', evidence_level='ingredient-human')
    if pending_contexts:
        for context in record['study_contexts']:
            context['review_status'] = 'source_verified_pending_clinical_review'
    monkeypatch.setattr(clinical_applicability, 'reviewed_entries', lambda: owners)
    return record


@pytest.mark.parametrize('form', ['Glucosamine Hydrochloride', 'Glucosamine HCl'])
@pytest.mark.parametrize('quantity', [None, 1500])
def test_glucosamine_sulfate_sources_cannot_credit_hydrochloride(monkeypatch, form, quantity):
    row = {'name': form, 'canonical_id': 'glucosamine', 'quantity': quantity, 'unit': 'mg',
           'raw_source_path': 'ingredientRows[0]'}
    entry = {**reviewed_entries()['INGR_GLUCOSAMINE_SULFATE'],
             'ingredient': form, 'matched_source_row_refs': ['ingredientRows[0]']}
    # Real registry: a completed no-credit decision for every glucosamine form.
    result = assess_clinical_applicability({'activeIngredients': [row]}, entry, assess_amount=False)
    assert result == {'status': 'not_applicable', 'reason_code': 'reference_only_clinical_record'}
    # The sulfate sources' own scope still rejects hydrochloride on a credit path.
    _scored_glucosamine_copy(monkeypatch)
    result = assess_clinical_applicability({'activeIngredients': [row]}, entry, assess_amount=False)
    assert result['status'] == 'not_applicable'
    assert result['reason_code'] == 'clinical_form_excluded'


@pytest.mark.parametrize('form', ['Glucosamine', 'Glucosamine sulfate 2KCl', 'Crystalline glucosamine sulfate'])
def test_glucosamine_not_excluded_does_not_establish_completed_clinical_review(monkeypatch, form):
    from clinical_applicability import assess_clinical_source_review
    row = {'name': form, 'canonical_id': 'glucosamine', 'quantity': 1500, 'unit': 'mg',
           'raw_source_path': 'ingredientRows[0]'}
    entry = {**reviewed_entries()['INGR_GLUCOSAMINE_SULFATE'],
             'ingredient': form, 'matched_source_row_refs': ['ingredientRows[0]']}
    # Real registry: completion comes from Dr. Pham's signed ruling, and it is
    # a no-credit decision, not credit earned by passing the exclusion.
    result = assess_clinical_applicability({'activeIngredients': [row]}, entry, assess_amount=False)
    assert result == {'status': 'not_applicable', 'reason_code': 'reference_only_clinical_record'}
    assert assess_clinical_source_review(entry)['is_complete'] is True
    # Passing the hydrochloride exclusion alone still completes nothing.
    _scored_glucosamine_copy(monkeypatch, pending_contexts=True)
    result = assess_clinical_applicability({'activeIngredients': [row]}, entry, assess_amount=False)
    assert result['status'] != 'not_applicable'
    assert assess_clinical_source_review(entry)['is_complete'] is False


@pytest.mark.parametrize('source_case,expected', [
    ('unrelated', False), ('excluded_only', False), ('retracted_only', False),
    ('concern_only', False), ('missing_sources', False), ('eligible', True),
    ('trial_with_correction', True), ('legacy_published', True),
    ('legacy_explicit_exclusion', False), ('record_hold', False),
])
def test_source_context_must_be_attributable_to_eligible_record_source(monkeypatch, source_case, expected):
    import clinical_applicability
    from test_assessment_readiness import _install_completed_release_context
    context = _install_completed_release_context(monkeypatch)
    pmid = context['source_pmids'][0]
    reference = {'pmid': pmid}
    record = {'id': 'used', 'study_contexts': [context], 'references_structured': [reference]}
    if source_case == 'unrelated':
        reference['pmid'] = '99999999'
    elif source_case in {'excluded_only', 'legacy_explicit_exclusion'}:
        reference['scoring_eligible'] = False
        if source_case == 'legacy_explicit_exclusion':
            record['published_studies'] = [pmid]
    elif source_case == 'retracted_only':
        reference['retracted'] = True
    elif source_case == 'concern_only':
        reference['expression_of_concern'] = True
    elif source_case == 'missing_sources':
        record.pop('references_structured')
    elif source_case == 'legacy_published':
        record.pop('references_structured')
        record['published_studies'] = [pmid]
    elif source_case == 'record_hold':
        record['scoring_eligible'] = False
    elif source_case == 'trial_with_correction':
        context['source_pmids'].append('99999999')
        record['references_structured'].append({'pmid': '99999999', 'scoring_eligible': False})
    monkeypatch.setattr(clinical_applicability, 'reviewed_entries', lambda: {'used': record})
    result = clinical_applicability.assess_clinical_source_review({'id': 'used'})
    assert result['is_complete'] is expected
    if not expected:
        assert any('source' in error for error in result['errors'])


@pytest.mark.parametrize('field', ['references_structured', 'published_studies'])
@pytest.mark.parametrize('malformed', [None, 123, '11106141', {'pmid': '11106141'}, [None]])
def test_source_context_malformed_record_sources_fail_closed(monkeypatch, field, malformed):
    import clinical_applicability
    from test_assessment_readiness import _install_completed_release_context
    context = _install_completed_release_context(monkeypatch)
    pmid = context['source_pmids'][0]
    record = {'id': 'used', 'study_contexts': [context],
              'references_structured': [{'pmid': pmid}], 'published_studies': [pmid]}
    record[field] = malformed
    monkeypatch.setattr(clinical_applicability, 'reviewed_entries', lambda: {'used': record})
    result = clinical_applicability.assess_clinical_source_review({'id': 'used'})
    assert result['is_complete'] is False
    assert 'clinical_source_references_invalid' in result['errors']


@pytest.mark.parametrize('case,expected', [
    ('completed_reference', True), ('ordinary_affirmative', False),
    ('record_hold', False), ('pending_approval', False),
    ('missing_provenance', False), ('retracted_source', False),
    ('unfinished_outcome', False), ('excluded_source', False),
])
def test_completed_negative_calendar_review_is_separate_from_scoring_eligibility(monkeypatch,case,expected):
    import clinical_applicability as owner
    from test_assessment_readiness import _install_completed_release_context
    from probiotic_measurements import context_accepted_for_scoring
    context = _install_completed_release_context(monkeypatch)
    context['scoring_eligible'] = False
    context['dose'].update(duration_basis='fixed_protocol', duration_days=None,
                           duration_as_printed={'value': 6, 'unit': 'months'})
    context['outcomes'][0]['direction'] = 'null'
    record = {'id': 'used', 'study_type': 'reference', 'evidence_level': 'reference',
              'study_contexts': [context], 'references_structured': [{'pmid':context['source_pmids'][0]}]}
    if case == 'ordinary_affirmative': record.update(study_type='rct_single', evidence_level='ingredient-human')
    elif case == 'record_hold': record['scoring_eligible'] = False
    elif case == 'pending_approval': context['review_status']='source_verified_pending_clinical_review'
    elif case == 'missing_provenance': context.pop('clinical_review')
    elif case == 'retracted_source': context['source_integrity']='retracted'
    elif case == 'unfinished_outcome': context['outcomes'][0]['hierarchy']='unresolved'
    elif case == 'excluded_source': record['references_structured'][0]['scoring_eligible']=False
    monkeypatch.setattr(owner, 'reviewed_entries', lambda:{'used':record})
    assert owner.assess_clinical_source_review(record)['is_complete'] is expected
    assert context_accepted_for_scoring(context) is False


@pytest.mark.parametrize('case,expected', [
    ('reviewed_exclusion', True), ('missing_review', False), ('foreign_source', False),
    ('missing_locator', False), ('missing_reason', False), ('missing_identity', False),
    ('unreviewed_reference', False), ('record_hold', False), ('affirmative', False),
    ('pending_context', False),
])
def test_reference_source_rejection_can_complete_without_invented_trial_facts(monkeypatch, case, expected):
    import clinical_applicability as owner
    from probiotic_measurements import context_accepted_for_scoring

    context = {'context_id': 'used_rejection', 'components': ['used'],
               'source_pmids': ['39269340'], 'review_status': 'rejected_source',
               'scoring_eligible': False,
               'clinical_review': {'reviewer': 'Dr Pham', 'reviewed_at': '2026-10-26',
                   'scope': 'identity_dose_outcome_applicability'},
               'dose': {'source_provenance': {'pmid': '39269340',
                   'source_url': 'https://pubmed.ncbi.nlm.nih.gov/39269340/',
                   'location': 'Primary abstract: uncontrolled pilot design and results'}},
               'limitations': ['Uncontrolled pilot does not establish causal benefit.']}
    record = {'id': 'used', 'study_type': 'reference', 'evidence_level': 'reference',
              'references_structured': [{'pmid': '39269340', 'scoring_eligible': False}],
              'study_contexts': [context]}
    if case == 'missing_review':
        context.pop('clinical_review')
    elif case == 'foreign_source':
        context['source_pmids'] = ['12345678']
    elif case == 'missing_locator':
        context['dose']['source_provenance'].pop('location')
    elif case == 'missing_reason':
        context['limitations'] = []
    elif case == 'missing_identity':
        context['components'] = ['different_record']
    elif case == 'unreviewed_reference':
        record['references_structured'].append({'pmid': '12345678'})
    elif case == 'record_hold':
        record['scoring_eligible'] = False
    elif case == 'affirmative':
        record.update(study_type='rct', evidence_level='ingredient-human')
    elif case == 'pending_context':
        record['study_contexts'].append({**context, 'review_status': 'source_verified_pending_clinical_review'})
    monkeypatch.setattr(owner, 'reviewed_entries', lambda: {'used': record})
    assert owner.assess_clinical_source_review({'id': 'used'})['is_complete'] is expected
    assert context_accepted_for_scoring(context) is False


@pytest.mark.parametrize('record_id', ['PRECLIN_FISETIN', 'INGR_PROBIOTICS'])
def test_returned_scoped_source_rejections_finish_review_without_earning_credit(record_id):
    from probiotic_measurements import context_accepted_for_scoring
    record = reviewed_entries()[record_id]
    assert record['study_type'] == 'reference'
    assert record['evidence_level'] == 'reference'
    assert all(ref['scoring_eligible'] is False for ref in record['references_structured'])
    assert all(not context_accepted_for_scoring(c) for c in record['study_contexts'])
    assert assess_clinical_applicability({}, {'id': record_id}) == {
        'status': 'not_applicable', 'reason_code': 'reference_only_clinical_record'}
    from clinical_applicability import assess_clinical_source_review
    assert assess_clinical_source_review({'id': record_id})['is_complete'] is True


def test_contributing_exact_strain_context_uses_existing_native_validator(monkeypatch):
    import clinical_applicability as owner
    from copy import deepcopy
    from test_assessment_readiness import _install_completed_release_context
    context = deepcopy(_install_completed_release_context(monkeypatch))
    key = 'STRAIN_LGG'
    context.update(identity_scope='exact_strain', components=[key], purpose='treatment')
    context['population']['age_group'] = 'adult'
    context['dose'].update(measurement_type='viable_count', unit='CFU', values=[1e9],
                           dose_basis='per_strain_daily')
    record = {'id': key, 'study_contexts': [context],
              'references_structured': [{'pmid': context['source_pmids'][0]}]}
    monkeypatch.setattr(owner, 'reviewed_entries', lambda: {key: record})
    result = owner.assess_clinical_source_review({'id': key})
    assert result['is_complete'], result['errors']
    context['components'] = ['UNREGISTERED_STRAIN']
    assert not owner.assess_clinical_source_review({'id': key})['is_complete']


def test_inositol_pooled_source_is_released_only_for_its_retraction_free_cycle_pool():
    """Dr. Pham, 2026-10-28: the 36703143 hold is resolved by the retracted-trial
    analysis (credited cycle pool excludes both retracted reports), with credit
    confined to PCOS cycle regularity and no fertility/hormone claim."""
    from evidence_resolver import clinical_record_sources_eligible
    record = reviewed_entries()['INGR_INOSITOL']
    refs = {r['pmid']: r for r in record['references_structured']}
    assert not refs['36703143'].get('retracted')
    assert not refs['38163998'].get('retracted')
    assert clinical_record_sources_eligible({'references_structured': [refs['36703143']]})
    assert record['applicability']['source_pmids'] == ['36703143']
    # The outcome equals the credited context's condition, so the condition and
    # population gate runs; a bare "cycle regularity" term was categorized as
    # digestive and let men's multivitamins borrow PCOS evidence.
    assert record['applicability']['supported_outcomes'] == ['pcos_menstrual_cycle_regularity']
    assert {'fertility', 'ovulation', 'hormone balance'} <= set(record['applicability']['excluded_claim_terms'])
    credited = [c for c in record['study_contexts'] if c.get('scoring_eligible') is True]
    assert [c['source_pmids'] for c in credited] == [['36703143']]
    assert [c['condition'] for c in credited] == record['applicability']['supported_outcomes']
    limitations = ' '.join(credited[0]['limitations'])
    assert '18074942' in limitations and '28980870' in limitations
    assert 'Neither pooled cycle trial is among the retracted included reports' in limitations


@pytest.mark.parametrize('record_id,held_pmid,independent_pmid', [
    ('INGR_LACTOFERRIN', '35276902', '19639462'),
])
def test_affected_pooled_source_is_held_without_declaring_its_independent_sources_retracted(record_id, held_pmid, independent_pmid):
    from evidence_resolver import clinical_record_sources_eligible
    record = reviewed_entries()[record_id]
    refs = {r['pmid']: r for r in record['references_structured']}
    assert refs[held_pmid]['scoring_eligible'] is False
    assert not refs[held_pmid].get('retracted')
    assert not clinical_record_sources_eligible({'references_structured': [refs[held_pmid]]})
    assert refs[independent_pmid].get('scoring_eligible') is not False
    assert clinical_record_sources_eligible({'references_structured': [refs[independent_pmid]]})


def test_native_exclusion_extension_cannot_silently_cover_other_purpose_types():
    from clinical_applicability import _valid_native_claim_scope
    row = {'purpose': 'physiology', 'source_pmids': ['22912552'],
           'applicability': {'scope': 'ingredient', 'source_pmids': ['22912552'],
                             'excluded_claim_terms': ['digestive health']}}
    assert not _valid_native_claim_scope(row)
    row['purpose'] = 'treatment'
    assert _valid_native_claim_scope(row)


@pytest.mark.parametrize('rid,claim,expected', [
    ('INGR_RIBOFLAVIN_B2', 'Migraine support', 'applicable'),
    ('INGR_RIBOFLAVIN_B2', 'Mental clarity support', 'not_applicable'),
    # A negated phrase is not a claim; a claim-free label keeps scoped credit.
    ('INGR_RIBOFLAVIN_B2', 'Not for migraine support', 'applicable'),
    ('INGR_CRANBERRY', 'Recurrent UTI prevention', 'applicable'),
    ('INGR_CRANBERRY', 'Immune support', 'not_applicable'),
    ('INGR_CRANBERRY', 'Urinary tract support', 'applicable'),
])
def test_signed_condition_scopes_are_enforced_by_the_generic_consumer(rid, claim, expected):
    record = reviewed_entries()[rid]
    canonical, name = ('riboflavin', 'Riboflavin') if rid.endswith('B2') else ('cranberry', 'Cranberry extract')
    row = {'name': name, 'canonical_id': canonical, 'raw_source_text': name,
           'quantity': 400, 'unit': 'mg', 'raw_source_path': 'ingredientRows[0]',
           'mapped': True, 'score_eligible_by_cleaner': True, 'source_section': 'active'}
    product = {'product_name': claim, 'ingredient_quality_data': {'ingredients_scorable': [row]}}
    entry = {'id': rid, 'ingredient': name, 'matched_source_row_refs': ['ingredientRows[0]']}
    result = assess_clinical_applicability(product, entry, assess_amount=False)
    assert result['status'] == expected
    assert record['study_contexts'][0]['clinical_review']['reviewer'] == 'Dr. Pham'


def test_signed_prevention_scope_cannot_be_inferred_from_warnings():
    row = {'name': 'Cranberry extract', 'raw_source_text': 'Cranberry extract', 'canonical_id': 'cranberry',
           'quantity': 500, 'unit': 'mg', 'raw_source_path': 'ingredientRows[0]', 'mapped': True,
           'score_eligible_by_cleaner': True, 'source_section': 'active'}
    product = {'product_name': 'Cranberry', 'warnings': 'Ask about recurrent UTI prevention',
               'ingredient_quality_data': {'ingredients_scorable': [row]}}
    result = assess_clinical_applicability(product, {'id': 'INGR_CRANBERRY', 'ingredient': row['name'],
        'matched_source_row_refs': ['ingredientRows[0]']}, assess_amount=False)
    # A warning is neither a claim nor an assumed diagnosis: scoped credit only.
    assert result['status'] == 'applicable'
    assert result['claim_alignment']['state'] == 'absent'


@pytest.mark.parametrize('target,expected', [
    ('Adults - Women ONLY', 'applicable'),
    ('Adults - Men ONLY', 'not_applicable'),
    ('Pregnant and lactating', 'not_applicable'),
    ('Children (4-8 Years)', 'not_applicable'),
])
def test_signed_population_limits_survive_generic_prevention_matching(monkeypatch, target, expected):
    import clinical_applicability as ca
    row = {'name': 'Cranberry extract', 'raw_source_text': 'Cranberry extract', 'canonical_id': 'cranberry',
           'quantity': 500, 'unit': 'mg', 'raw_source_path': 'ingredientRows[0]', 'mapped': True,
           'score_eligible_by_cleaner': True, 'source_section': 'active'}
    product = {'product_name': 'Recurrent UTI prevention', 'targetGroups': [target],
               'ingredient_quality_data': {'ingredients_scorable': [row]}}
    result = ca.assess_clinical_applicability(product, {'id': 'INGR_CRANBERRY', 'ingredient': row['name'],
        'matched_source_row_refs': ['ingredientRows[0]']}, assess_amount=False)
    assert result['status'] == expected


@pytest.mark.parametrize('population', [None, 'adults', [], {'description': 123}, {'description': True}, {'description': []}, {'description': {}}])
def test_malformed_condition_scope_population_fails_closed(monkeypatch, population):
    import clinical_applicability as ca
    records = deepcopy(reviewed_entries())
    records['INGR_RIBOFLAVIN_B2']['study_contexts'][0]['population'] = population
    monkeypatch.setattr(ca, 'reviewed_entries', lambda: records)
    row = {'name': 'Riboflavin', 'canonical_id': 'riboflavin', 'quantity': 400, 'unit': 'mg',
           'raw_source_path': 'ingredientRows[0]', 'mapped': True, 'score_eligible_by_cleaner': True}
    result = ca.assess_clinical_applicability({'product_name': 'Migraine support',
        'ingredient_quality_data': {'ingredients_scorable': [row]}},
        {'id': 'INGR_RIBOFLAVIN_B2', 'ingredient': row['name'], 'matched_source_row_refs': ['ingredientRows[0]']},
        assess_amount=False)
    assert result['status'] == 'unresolved'


@pytest.mark.parametrize('target', ['Adults - Men ONLY', 'Pregnant and lactating', 'Children (4-8 Years)'])
def test_unmatched_condition_context_cannot_lend_population_scope(monkeypatch, target):
    import clinical_applicability as ca
    records = deepcopy(reviewed_entries())
    record = records['INGR_CRANBERRY']
    sibling = deepcopy(record['study_contexts'][0])
    sibling['context_id'] = 'synthetic_unrelated_population_control'
    sibling['condition'] = 'migraine'
    sibling['population'] = {'age_group': 'mixed', 'description': 'Adults and children of either sex'}
    record['study_contexts'].append(sibling)
    record['applicability']['supported_outcomes'].append('migraine')
    monkeypatch.setattr(ca, 'reviewed_entries', lambda: records)
    row = {'name': 'Cranberry extract', 'raw_source_text': 'Cranberry extract', 'canonical_id': 'cranberry',
           'quantity': 500, 'unit': 'mg', 'raw_source_path': 'ingredientRows[0]', 'mapped': True,
           'score_eligible_by_cleaner': True, 'source_section': 'active'}
    product = {'product_name': 'Recurrent UTI prevention', 'targetGroups': [target],
               'ingredient_quality_data': {'ingredients_scorable': [row]}}
    result = ca.assess_clinical_applicability(product, {'id': 'INGR_CRANBERRY', 'ingredient': row['name'],
        'matched_source_row_refs': ['ingredientRows[0]']}, assess_amount=False)
    assert result['status'] == 'not_applicable'


@pytest.mark.parametrize('case', ['pending', 'source_mismatch', 'unsigned', 'missing_contexts'])
def test_condition_scoped_policy_cannot_fall_back_when_review_context_is_lost(monkeypatch, case):
    import clinical_applicability as ca
    records = deepcopy(reviewed_entries())
    record = records['INGR_CRANBERRY']
    context = record['study_contexts'][0]
    if case == 'pending':
        context['review_status'] = 'source_verified_pending_clinical_review'
        context['scoring_eligible'] = False
    elif case == 'source_mismatch':
        context['source_pmids'] = ['99999999']
    elif case == 'unsigned':
        context.pop('clinical_review')
    else:
        record['study_contexts'] = []
    monkeypatch.setattr(ca, 'reviewed_entries', lambda: records)
    row = {'name': 'Cranberry extract', 'raw_source_text': 'Cranberry extract', 'canonical_id': 'cranberry', 'quantity': 400, 'unit': 'mg',
           'raw_source_path': 'ingredientRows[0]', 'mapped': True, 'score_eligible_by_cleaner': True, 'source_section': 'active'}
    product = {'product_name': 'Recurrent UTI prevention', 'targetGroups': ['Adults - Men ONLY'],
               'ingredient_quality_data': {'ingredients_scorable': [row]}}
    result = ca.assess_clinical_applicability(product, {'id': 'INGR_CRANBERRY',
        'ingredient': row['name'], 'matched_source_row_refs': ['ingredientRows[0]']}, assess_amount=False)
    assert result['status'] == 'unresolved'


def test_a_reviewed_scope_keeps_every_legacy_excluded_form():
    """clinical_applicability reads exclude_aliases only when a record has no
    applicability policy. A new scope must carry those forms into
    excluded_form_terms, or an excluded preparation (arginine AKG, label 269278)
    loses its completed "different preparation" assessment (2026-10-28)."""
    missing = {
        record_id: sorted(set(record['exclude_aliases'])
                          - set(record['applicability'].get('excluded_form_terms') or []))
        for record_id, record in reviewed_entries().items()
        if record.get('applicability') and record.get('exclude_aliases')
    }
    assert {record_id: forms for record_id, forms in missing.items() if forms} == {}


# Condition-specific evidence: claim and population applicability (rulings of
# October 28, 2026; scripts/audits/condition_scope_rule_20261028). No label
# claim is required, credit stays condition-scoped, an unrelated claim earns
# nothing, and special populations need explicit product targeting.

def _row(canonical, name, quantity=500, unit='mg', ref='ingredientRows[0]', **extra):
    return {'name': name, 'raw_source_text': name, 'canonical_id': canonical, 'quantity': quantity,
            'unit': unit, 'raw_source_path': ref, 'mapped': True, 'score_eligible_by_cleaner': True,
            'source_section': 'active', **extra}


def _assess(rid, row, product_name, statements=(), target_groups=()):
    product = {'product_name': product_name, 'ingredient_quality_data': {'ingredients_scorable': [row]},
               'statements': [{'type': 'Formulation re: Other', 'notes': text} for text in statements],
               'targetGroups': list(target_groups)}
    entry = {'id': rid, 'ingredient': row['name'], 'matched_source_row_refs': [row['raw_source_path']]}
    return assess_clinical_applicability(product, entry, assess_amount=False)


@pytest.mark.parametrize('rid,canonical,name', [
    ('INGR_CRANBERRY', 'cranberry', 'Cranberry extract'),
    ('INGR_SELENIUM', 'selenium', 'Selenium'),
    ('INGR_INOSITOL', 'inositol', 'Inositol'),
    ('INGR_VITAMIN_C', 'vitamin_c', 'Vitamin C'),
    ('INGR_RIBOFLAVIN_B2', 'riboflavin', 'Riboflavin'),
])
def test_claim_free_label_earns_scoped_credit_from_signed_condition_research(rid, canonical, name):
    result = _assess(rid, _row(canonical, name, quantity=1000), name)
    assert result['status'] == 'applicable'
    assert result['claim_alignment']['state'] == 'absent'
    assert result['population_applicability']['state'] == 'eligible'
    assert result['supported_outcomes'] == reviewed_entries()[rid]['applicability']['supported_outcomes']


def test_claim_free_coq10_keeps_heart_failure_scope():
    result = _assess('INGR_COQ10', _row('coq10', 'CoQ10', quantity=100), 'CoQ10 100 mg')
    assert result['status'] == 'applicable'
    assert result['claim_alignment']['state'] == 'absent'
    assert result['supported_outcomes'] == ['heart_failure_adjunct']
    assert 'heart failure' in result['studied_population'].lower()


@pytest.mark.parametrize('product_name,statements', [
    ('CoQ10 Energy Support', ()),
    ('CoQ10 100 mg', ('CoQ10 supports cellular energy production.',)),
    # A signed product-level exclusion keeps its meaning beside an aligned claim.
    ('CoQ10 Energy Support', ('CoQ10 supports heart function.',)),
])
def test_coq10_energy_positioning_cannot_borrow_heart_failure_research(product_name, statements):
    result = _assess('INGR_COQ10', _row('coq10', 'CoQ10', quantity=100), product_name, statements)
    assert result['status'] == 'not_applicable'
    assert result['reason_code'] == 'label_purpose_evidence_mismatch'


def test_broad_heart_health_claim_is_not_general_cardiovascular_efficacy():
    row = _row('coq10', 'CoQ10', quantity=100)
    # Dr Pham's signed CoQ10 exclusions name heart and cardiovascular health:
    # the heart-failure sources cannot substantiate that positioning at all.
    signed = _assess('INGR_COQ10', row, 'CoQ10 100 mg', ('CoQ10 supports heart health.',))
    assert signed['status'] == 'not_applicable'
    assert signed['reason_code'] == 'label_purpose_evidence_mismatch'
    # An unexcluded related claim keeps only the studied heart-failure scope.
    related = _assess('INGR_COQ10', row, 'CoQ10 100 mg', ('CoQ10 supports heart function.',))
    assert related['status'] == 'applicable'
    assert related['claim_alignment']['state'] == 'aligned'
    assert related['supported_outcomes'] == ['heart_failure_adjunct']
    assert 'Not energy' in related['studied_population']


def test_potassium_blood_pressure_claim_keeps_hypertensive_population_scope():
    result = _assess('INGR_POTASSIUM', _row('potassium', 'Potassium', quantity=99), 'Potassium 99 mg',
                     ('Potassium supports healthy blood pressure.',))
    assert result['status'] == 'applicable'
    assert result['claim_alignment']['state'] == 'aligned'
    assert 'hypertension' in result['studied_population'].lower()
    assert 'not significant in normotensive' in result['studied_population']


def test_pcos_cycle_regularity_is_not_digestive_regularity():
    from evidence_resolver import evidence_indication_categories
    assert 'digestive' not in evidence_indication_categories('pcos_menstrual_cycle_regularity')
    assert 'digestive' in evidence_indication_categories('supports bowel regularity')
    result = _assess('INGR_INOSITOL', _row('inositol', 'Inositol', quantity=2000), 'Inositol',
                     ('Inositol supports digestive regularity.',))
    assert result['status'] == 'not_applicable'
    assert result['claim_alignment']['state'] == 'unrelated'


@pytest.mark.parametrize('text,category,present', [
    ('supports healthy blood pressure', 'cardiovascular', True),
    ('Supports cardiometabolic, neurocognitive and musculoskeletal health', 'cardiovascular', True),
    ('Support for nitric oxide production and vascular health', 'cardiovascular', True),
    ('enhances blood flow', 'cardiovascular', True),
    ('promote heart health', 'cardiovascular', True),
    ('blood orange flavor', 'cardiovascular', False),
    ('maintain strong bones', 'bone', True),
    ('extra strength formula', 'muscle_strength_mass', False),
    ('supports lean muscle mass', 'muscle_strength_mass', True),
    ('acute chemotherapy nausea', 'nausea', True),
    ('acute chemotherapy nausea', 'digestive', False),
    ('hashimoto_thyroiditis', 'thyroid', True),
    ('knee_osteoarthritis', 'joint', True),
])
def test_indication_phrases_are_recognized_narrowly(text, category, present):
    from evidence_resolver import evidence_indication_categories
    assert (category in evidence_indication_categories(text)) is present


def test_recognized_but_unclassifiable_claim_is_not_claim_absence():
    result = _assess('INGR_SELENIUM', _row('selenium', 'Selenium', quantity=0.2), 'Selenium',
                     ('Selenium supports normal enzyme activity.',))
    assert result['status'] == 'unresolved'
    assert result['claim_alignment']['state'] == 'ambiguous'
    assert result['claim_alignment']['sources'] == ['statements[0].notes:sentence[0]']


def test_mixed_claims_keep_supported_research_without_supporting_the_unrelated_claim():
    result = _assess('INGR_VITAMIN_C', _row('vitamin_c', 'Vitamin C', quantity=1000), 'Vitamin C',
                     ('Vitamin C supports immune health. Vitamin C supports healthy skin.',))
    assert result['status'] == 'applicable'
    assert result['claim_alignment']['state'] == 'mixed'
    assert result['supported_outcomes'] == ['common_cold_severity']


def test_aligned_claim_earns_no_more_than_no_claim():
    row = _row('cranberry', 'Cranberry extract')
    silent = _assess('INGR_CRANBERRY', row, 'Cranberry')
    claimed = _assess('INGR_CRANBERRY', row, 'Cranberry', ('Cranberry extract supports urinary tract health.',))
    assert claimed['claim_alignment']['state'] == 'aligned'
    assert {k: v for k, v in silent.items() if k != 'claim_alignment'} == \
        {k: v for k, v in claimed.items() if k != 'claim_alignment'}


def test_scoped_credit_cannot_bypass_preparation_or_population_limits():
    seed = _assess('INGR_CRANBERRY', _row('cranberry', 'Cranberry seed oil'), 'Cranberry seed oil')
    assert seed['status'] == 'not_applicable'
    men = _assess('INGR_CRANBERRY', _row('cranberry', 'Cranberry extract'), 'Cranberry',
                  target_groups=['Adults - Men ONLY'])
    assert men['status'] == 'not_applicable'
    assert men['population_applicability']['state'] == 'explicit_conflict'


def test_general_ginger_uses_only_its_adult_context_and_pregnancy_ginger_only_its_pregnancy_context():
    row = _row('ginger', 'Ginger root extract', quantity=1000)
    general = _assess('INGR_GINGER', row, 'Ginger root')
    assert general['status'] == 'applicable'
    assert general['supported_outcomes'] == ['acute_chemotherapy_nausea']
    assert 'pregnan' not in general['studied_population'].lower()
    prenatal = _assess('INGR_GINGER', row, 'Prenatal Ginger', target_groups=['Pregnant'])
    assert prenatal['status'] == 'applicable'
    assert prenatal['supported_outcomes'] == ['nausea_vomiting_of_pregnancy']
    assert 'cancer' not in prenatal['studied_population'].lower()


def test_pregnancy_targeted_label_cannot_inherit_nonpregnant_pcos_result():
    result = _assess('INGR_INOSITOL', _row('inositol', 'Inositol', quantity=2000), 'Prenatal Inositol',
                     target_groups=['Pregnant'])
    assert result['status'] == 'not_applicable'
    assert result['population_applicability']['state'] == 'explicit_conflict'


@pytest.mark.parametrize('product_name,targets,state', [
    ('Daily Probiotic', [], 'special_targeting_absent'),
    ('Baby Probiotic Drops', ['Infants (0-12 months)'], 'eligible'),
    # A children's product is not an infant product: colic was studied in infants.
    ('Kids Probiotic', ['Children (4-8 Years)'], 'special_targeting_absent'),
])
def test_infant_only_research_needs_infant_targeting_not_a_colic_claim(product_name, targets, state):
    from clinical_applicability import assess_context_population
    import studied_formulas
    colic = next(c for c in studied_formulas._clinical_strain_registry()['STRAIN_LACTIS_BB12']['study_contexts']
                 if c['condition'] == 'infant_colic')
    product = {'product_name': product_name, 'targetGroups': targets}
    assert assess_context_population(product, colic) == state


def test_precaution_naming_children_is_not_infant_targeting():
    from clinical_applicability import assess_context_population
    import studied_formulas
    colic = next(c for c in studied_formulas._clinical_strain_registry()['STRAIN_LACTIS_BB12']['study_contexts']
                 if c['condition'] == 'infant_colic')
    product = {'product_name': 'Daily Probiotic', 'statements': [
        {'type': 'Precautions', 'notes': 'Keep out of reach of children. Not for infants.'}]}
    assert assess_context_population(product, colic) == 'special_targeting_absent'


@pytest.mark.parametrize('product_name,targets,credited', [
    ('Daily Probiotic', [], False),
    ('Baby Probiotic Drops', ['Infants (0-12 months)'], True),
])
def test_bb12_infant_colic_research_reaches_only_infant_products(product_name, targets, credited):
    from scoring_v4.modules.probiotic_evidence import score_evidence
    from test_probiotic_applicability_rubric import strain_product
    product = strain_product(clinical_id='STRAIN_LACTIS_BB12',
                             name='Bifidobacterium animalis subsp. lactis BB-12', dose=1e9)
    product['product_name'] = product_name
    product['targetGroups'] = targets
    evidence = score_evidence(product)
    colic_pmids = {'31797399', '34550055'}
    used = {pmid for strain in evidence['metadata']['evidence_assessment']['strain_assessments']
            for pmid in strain.get('scoring_source_pmids') or []}
    assert bool(used & colic_pmids) is credited
    assert (evidence['score'] > 0) is credited


def test_a_predominantly_male_sample_is_not_a_sex_restriction():
    from clinical_applicability import assess_context_population
    context = {'population': {'age_group': None, 'description': 'Healthy adults 18-50 in resistance training; predominantly men.'}}
    women = {'product_name': 'Creatine', 'targetGroups': ['Women (not pregnant or lactating)']}
    assert assess_context_population(women, context) == 'eligible'
    context['population']['description'] = 'Healthy men aged 21-35.'
    assert assess_context_population(women, context) == 'explicit_conflict'


@pytest.mark.parametrize('text,category,present', [
    ('Contents are sold by weight, not volume', 'metabolic', False),
    ('Supports healthy body weight', 'metabolic', True),
    ('Supports lean muscle recovery', 'muscle_strength_mass', True),
])
def test_fill_statements_and_lean_muscle_claims_are_read_by_phrase(text, category, present):
    from evidence_resolver import evidence_indication_categories
    assert (category in evidence_indication_categories(text)) is present


def test_purpose_rejection_keeps_the_studied_branded_material_for_formulation():
    from clinical_applicability import filter_clinical_matches, preparation_verified_clinical_matches
    row = _row('ashwagandha', 'KSM-66 Ashwagandha root extract', quantity=600)
    product = {'product_name': 'Energy Xtra', 'ingredient_quality_data': {'ingredients_scorable': [row]}}
    entry = {'id': 'BRAND_KSM66', 'ingredient': row['name'], 'matched_source_row_refs': [row['raw_source_path']]}
    accepted, rejected = filter_clinical_matches(product, [entry], assess_amount=False)
    # Evidence: an energy label cannot borrow the stress research.
    assert accepted == []
    assert rejected[0]['reason_code'] == 'label_purpose_evidence_mismatch'
    assert rejected[0]['matched_source_row_refs'] == ['ingredientRows[0]']
    product['evidence_data'] = {'clinical_matches': accepted, 'rejected_clinical_matches': rejected}
    # Formulation: the label still carries the studied KSM-66 preparation.
    verified = preparation_verified_clinical_matches(product)
    assert [match['id'] for match in verified] == ['BRAND_KSM66']
    # A wrong preparation is never preparation-verified.
    other = _row('ashwagandha', 'Ashwagandha root powder', quantity=600)
    accepted, rejected = filter_clinical_matches({**product, 'ingredient_quality_data': {
        'ingredients_scorable': [other]}}, [entry], assess_amount=False)
    assert rejected[0]['reason_code'] == 'clinical_form_mismatch'
    assert 'matched_source_row_refs' not in rejected[0]


@pytest.mark.parametrize('product_name,statements,excluded', [
    # Single signed words count only as claimed objects.
    ('CoQ10 Energy Support', (), True),
    ('CoQ10 100 mg', ('Supports cellular energy production.',), True),
    # A title keeps the exact signed word: a product name is positioning.
    ('Pro Energy Series CoQ10', (), True),
    ('CoQ10 Energy + Heart Function', (), True),
    ('Statin Companion CoQ10', (), True),
    # A claim verb anywhere earlier in the sentence makes the word claimed.
    ('Re-Forge', ('Clinically studied ingredients help boost protein synthesis, metabolize fatty acids and cellular energy.',), True),
    # A mechanism sentence is not an energy claim.
    ('CoQ10 100 mg', ("It is an essential component of your heart's energy producing system.",), False),
    # A precaution naming a signed term is not a claim.
    ('Inositol', ('Consult your doctor before use during pregnancy.',), False),
    ('Inositol', ('Supports a healthy pregnancy.',), True),
])
def test_signed_exclusions_match_claims_not_product_lines_or_precautions(product_name, statements, excluded):
    from clinical_applicability import _excluded_claim_matches
    product = {'product_name': product_name,
               'statements': [{'type': 'General Statements: All Other Content', 'notes': text} for text in statements]}
    policy = {'excluded_claim_terms': ['energy', 'statin', 'pregnancy', 'heart health']}
    assert _excluded_claim_matches(product, policy) is excluded


def _nvp_context():
    return next(c for c in reviewed_entries()['INGR_GINGER']['study_contexts']
                if c['condition'] == 'nausea_vomiting_of_pregnancy')


@pytest.mark.parametrize('title,targets,state', [
    ('Ginger Chews (Not for use during pregnancy)', [], 'special_targeting_absent'),
    ('Post-Pregnancy Recovery Ginger', [], 'special_targeting_absent'),
    ('Lactation Support Tea', ['Lactating'], 'special_targeting_absent'),
    ('Ginger', ['Women (not pregnant or lactating)'], 'special_targeting_absent'),
    ('Prenatal Ginger', [], 'eligible'),
    ('Ginger', ['Pregnant Women'], 'eligible'),
])
def test_pregnancy_targeting_is_affirmative_and_not_lactation(title, targets, state):
    from clinical_applicability import assess_context_population
    assert assess_context_population({'product_name': title, 'targetGroups': targets}, _nvp_context()) == state


def test_lactation_only_research_needs_lactation_targeting():
    from clinical_applicability import assess_context_population
    context = {'population': {'age_group': 'adult', 'description': '120 breastfeeding mothers 1-3 months postpartum'}}
    assert assess_context_population({'product_name': 'Lactation Support', 'targetGroups': ['Lactating']},
                                     context) == 'eligible'
    assert assess_context_population({'product_name': 'Fenugreek'}, context) == 'special_targeting_absent'


@pytest.mark.parametrize('text', [
    'Gluten-Free, Lactose-Free', 'Cholesterol-free', 'Lipid-soluble vitamin', 'Shark Cartilage 750 mg',
    "Won't cause stomach distress", 'If you have diabetes consult your physician', 'Calm Magnesium Powder',
])
def test_absence_precaution_and_ingredient_words_are_not_claims(text):
    from clinical_applicability import native_product_positioning_categories
    product = {'product_name': 'Riboflavin', 'statements': [
        {'type': 'General Statements: All Other Content', 'notes': text}]}
    assert native_product_positioning_categories(product, purposes_only=True) == set()
    result = _assess('INGR_RIBOFLAVIN_B2', _row('riboflavin', 'Riboflavin', quantity=400), 'Riboflavin')
    product_result = assess_clinical_applicability(
        {**product, 'ingredient_quality_data': {'ingredients_scorable': [_row('riboflavin', 'Riboflavin', quantity=400)]}},
        {'id': 'INGR_RIBOFLAVIN_B2', 'ingredient': 'Riboflavin', 'matched_source_row_refs': ['ingredientRows[0]']},
        assess_amount=False)
    assert product_result['status'] == result['status'] == 'applicable'


def test_directions_for_use_are_not_a_marketed_purpose():
    from clinical_applicability import native_product_positioning_categories
    product = {'product_name': 'Ginger', 'suggested_use': 'Take with food to reduce nausea.'}
    assert native_product_positioning_categories(product, purposes_only=True) == set()


def test_unclassified_product_level_function_claim_is_not_claim_absence():
    result = _assess('INGR_SELENIUM', _row('selenium', 'Selenium', quantity=0.2),
                     'Selenium - Supports Normal Enzyme Activity')
    assert result['status'] == 'unresolved'
    assert result['claim_alignment']['state'] == 'ambiguous'


def test_a_bare_muscle_claim_relates_to_both_muscle_outcome_families():
    from evidence_resolver import evidence_indication_categories
    assert {'muscle_strength_mass', 'muscle_recovery'} <= evidence_indication_categories('Joint, Bone & Muscle')


def test_an_exclusion_sentence_is_not_the_studied_population():
    from clinical_applicability import assess_context_population
    context = {'population': {'age_group': 'adult', 'description':
        '38 RCTs in adults with hypertension. Pregnant participants were excluded.'}}
    assert assess_context_population({'product_name': 'Magnesium'}, context) == 'eligible'
    assert assess_context_population({'product_name': 'Prenatal Magnesium'}, context) == 'explicit_conflict'


@pytest.mark.parametrize('case,status', [
    ('approved', 'applicable'),
    ('pending', 'unresolved'),
    ('unsigned', 'unresolved'),
    ('source_mismatch', 'unresolved'),
    ('reference_only', 'not_applicable'),
    ('wrong_preparation', 'not_applicable'),
    ('special_population_untargeted', 'not_applicable'),
])
def test_a_claim_free_label_cannot_bypass_clinical_eligibility(monkeypatch, case, status):
    """No claim is required, but a claim-free label still passes every reviewed gate."""
    import clinical_applicability as ca
    records = deepcopy(reviewed_entries())
    record = records['INGR_CRANBERRY']
    context = record['study_contexts'][0]
    name = 'Cranberry extract'
    if case == 'pending':
        context.update(review_status='source_verified_pending_clinical_review', scoring_eligible=False)
    elif case == 'unsigned':
        context.pop('clinical_review')
    elif case == 'source_mismatch':
        context['source_pmids'] = ['99999999']
    elif case == 'reference_only':
        record['study_type'] = 'reference'
    elif case == 'wrong_preparation':
        name = 'Cranberry seed oil'
    elif case == 'special_population_untargeted':
        context['population'] = {'age_group': 'child', 'description': 'Children aged 1-12 with recurrent UTI'}
    monkeypatch.setattr(ca, 'reviewed_entries', lambda: records)
    result = _assess('INGR_CRANBERRY', _row('cranberry', name), 'Cranberry')
    assert result['status'] == status
    if status == 'applicable':
        assert result['claim_alignment']['state'] == 'absent'
