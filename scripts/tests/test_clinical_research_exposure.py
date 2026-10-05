"""Approved descriptive clinical exposure never supplies positive adequacy."""
from copy import deepcopy
import pytest
from test_clinical_applicability import zinc_product
from scoring_v4.scored_artifact import build_scored_artifact


def product(record_id, name, canonical, amount):
    p = zinc_product("zinc acetate", amount, "lozenge")
    row = p["ingredient_quality_data"]["ingredients_scorable"][0]
    if canonical != "zinc":
        row.update(name=name, standard_name=name, canonical_id=canonical, forms=[])
        p["form_factor_canonical"] = "powder"
    p["servings_per_day_min"] = p["servings_per_day_max"] = 1
    match = p["evidence_data"]["clinical_matches"][0]
    from clinical_applicability import reviewed_entries
    match.update(reviewed_entries()[record_id])
    match.update(id=record_id, ingredient=row["name"], matched_canonical_ids=[canonical])
    return p


@pytest.mark.parametrize("amount", [2.4, 150, 208, None])
def test_public_evidence_preserves_matching_zinc_research_at_every_amount(amount):
    from scoring_v4.modules.generic_evidence import resolved_clinical_matches
    p = product("INGR_ZINC_PICOLINATE", "Zinc", "zinc", amount)
    matches, _ = resolved_clinical_matches(p)
    assert any(m["id"] == "INGR_ZINC_PICOLINATE" for m in matches)
    a = build_scored_artifact(p)
    assert a["quality_pillars_v4"]["evidence"]["score"] > 0


@pytest.mark.parametrize("record,name,canonical,amount,status", [
    ("INGR_ZINC_PICOLINATE", "Zinc", "zinc", 79, "below"),
    ("INGR_ZINC_PICOLINATE", "Zinc", "zinc", 80, "matches"),
    ("INGR_ZINC_PICOLINATE", "Zinc", "zinc", 92, "matches"),
    ("INGR_ZINC_PICOLINATE", "Zinc", "zinc", 150, "between"),
    ("INGR_ZINC_PICOLINATE", "Zinc", "zinc", 192, "matches"),
    ("INGR_ZINC_PICOLINATE", "Zinc", "zinc", 207, "matches"),
    ("INGR_ZINC_PICOLINATE", "Zinc", "zinc", 208, "above"),
    ("INGR_D_MANNOSE", "D-Mannose", "d_mannose", 1000, "below"),
    ("INGR_D_MANNOSE", "D-Mannose", "d_mannose", 2000, "matches"),
    ("INGR_D_MANNOSE", "D-Mannose", "d_mannose", 4000, "above"),
    ("INGR_D_ASPARTIC_ACID", "D-Aspartic Acid", "d_aspartic_acid", 1500, "below"),
    ("INGR_D_ASPARTIC_ACID", "D-Aspartic Acid", "d_aspartic_acid", 3000, "matches"),
    ("INGR_D_ASPARTIC_ACID", "D-Aspartic Acid", "d_aspartic_acid", 4500, "between"),
    ("INGR_D_ASPARTIC_ACID", "D-Aspartic Acid", "d_aspartic_acid", 6000, "matches"),
    ("INGR_D_ASPARTIC_ACID", "D-Aspartic Acid", "d_aspartic_acid", 7000, "above"),
    ("INGR_WHITE_KIDNEY_BEAN", "White Kidney Bean Extract", "common_bean_extract", 1500, "reference_uncertain"),
])
def test_descriptive_regimen_boundaries(record, name, canonical, amount, status):
    from dose_assessment import clinical_research_exposure_assessments, positive_clinical_benchmark
    p = product(record, name, canonical, amount)
    assessment, = clinical_research_exposure_assessments(p)
    assert assessment["status"] == status
    assert assessment["kind"] == "studied_regimen"
    row = p["ingredient_quality_data"]["ingredients_scorable"][0]
    assert positive_clinical_benchmark(p, row) is None
    p["rda_ul_data"] = {"clinical_exposure_assessments": [assessment]}
    a = build_scored_artifact(p)
    facts = a["quality_pillars_v4"]["dose"]["explanation"]["facts"]
    assert any(f["value_display"] == assessment["notes"] for f in facts)
    control = deepcopy(p)
    control["rda_ul_data"].pop("clinical_exposure_assessments")
    assert a["quality_pillars_v4"]["dose"]["score"] == build_scored_artifact(control)["quality_pillars_v4"]["dose"]["score"]

@pytest.mark.parametrize("record,name,canonical", [
    ("INGR_ZINC_PICOLINATE", "Zinc", "zinc"),
    ("INGR_D_MANNOSE", "D-Mannose", "d_mannose"),
    ("INGR_D_ASPARTIC_ACID", "D-Aspartic Acid", "d_aspartic_acid"),
    ("INGR_WHITE_KIDNEY_BEAN", "White Kidney Bean Extract", "common_bean_extract"),
])
def test_unknown_amount_preserves_review_and_reports_unavailable(record, name, canonical):
    from dose_assessment import clinical_research_exposure_assessments
    from scoring_v4.modules.generic_evidence import resolved_clinical_matches
    p = product(record, name, canonical, None)
    assert resolved_clinical_matches(p)[0]
    assessment, = clinical_research_exposure_assessments(p)
    assert assessment["status"] == "unknown"
    assert assessment["minimum"] is None


def test_unknown_frequency_never_claims_a_studied_daily_regimen():
    from dose_assessment import clinical_research_exposure_assessments
    p = product("INGR_D_MANNOSE", "D-Mannose", "d_mannose", 2000)
    p.pop("servings_per_day_min")
    p.pop("servings_per_day_max")
    assessment, = clinical_research_exposure_assessments(p)
    assert assessment["status"] == "unknown"
    assert "frequency" in assessment["notes"]


@pytest.mark.parametrize("minimum,maximum,status", [(1, 2, "crosses_regimens"), (0.5, 0.75, "below"), (1.5, 2, "above")])
def test_serving_ranges_are_not_flattened_to_one_match(minimum, maximum, status):
    from dose_assessment import clinical_research_exposure_assessments
    p = product("INGR_D_MANNOSE", "D-Mannose", "d_mannose", 2000)
    p.update(servings_per_day_min=minimum, servings_per_day_max=maximum)
    assessment, = clinical_research_exposure_assessments(p)
    assert assessment["status"] == status
    assert (assessment["minimum"], assessment["maximum"]) == (2000*minimum, 2000*maximum)


@pytest.mark.parametrize("form,delivery", [("zinc picolinate", "lozenge"), ("zinc acetate", "capsule")])
def test_wrong_zinc_preparation_or_delivery_cannot_borrow_regimen(form, delivery):
    from dose_assessment import clinical_research_exposure_assessments
    p = zinc_product(form, 80, delivery)
    p.update(servings_per_day_min=1, servings_per_day_max=1)
    assert clinical_research_exposure_assessments(p) == []


def test_null_records_carry_zero_affirmative_evidence_at_all_amounts():
    from scoring_v4.modules.generic_evidence import resolved_clinical_matches, score_evidence
    for record, name, canonical in [("INGR_D_MANNOSE", "D-Mannose", "d_mannose"),
                                     ("INGR_D_ASPARTIC_ACID", "D-Aspartic Acid", "d_aspartic_acid")]:
        for amount in [500, 2000, 3000, 6000, 10000, None]:
            p = product(record, name, canonical, amount)
            matches, _ = resolved_clinical_matches(p)
            assert matches[0]["effect_direction"] == "null"
            assert score_evidence(p, apply_primary_floor=True)["score"] == 0


def test_exposure_requires_its_own_linked_row_not_a_siblings_amount():
    from dose_assessment import clinical_research_exposure_assessments
    p = product("INGR_D_MANNOSE", "D-Mannose", "d_mannose", None)
    row = p["ingredient_quality_data"]["ingredients_scorable"][0]
    p["ingredient_quality_data"]["ingredients_scorable"].append({**row, "quantity":2000, "raw_source_path":"ingredientRows[1]"})
    assessment, = clinical_research_exposure_assessments(p)
    assert assessment["source_row_ref"] == "ingredientRows[0]"
    assert assessment["status"] == "unknown"


def test_zinc_trial_correspondence_and_ul_concern_can_coexist():
    from dose_assessment import clinical_research_exposure_assessments
    from enrich_supplements_v3 import SupplementEnricherV3
    p = product("INGR_ZINC_PICOLINATE", "Zinc", "zinc", 80)
    p["activeIngredients"] = deepcopy(p["ingredient_quality_data"]["ingredients_scorable"])
    p["activeIngredients"][0].update(name="Zinc", raw_source_text="Zinc", standardName="Zinc", dailyValue=727)
    enricher = SupplementEnricherV3()
    p["rda_ul_data"] = enricher._collect_rda_ul_data(p, min_servings_per_day=1, max_servings_per_day=1)
    assessment, = clinical_research_exposure_assessments(p)
    assert assessment["status"] == "matches"
    ul, = p["rda_ul_data"]["dose_assessments"]
    assert ul["ul_assessment_status"] == "assessed_over_limit"
    p["rda_ul_data"]["clinical_exposure_assessments"] = [assessment]
    a = build_scored_artifact(p)
    assert a["quality_pillars_v4"]["dose"]["explanation"]["facts"]

@pytest.fixture(scope="module")
def enricher():
    from enrich_supplements_v3 import SupplementEnricherV3
    return SupplementEnricherV3()


@pytest.mark.parametrize("record,name,canonical,amount", [
    ("INGR_D_MANNOSE", "D-Mannose", "d_mannose", 1000),
    ("INGR_D_ASPARTIC_ACID", "D-Aspartic Acid", "d_aspartic_acid", 3000),
    ("INGR_WHITE_KIDNEY_BEAN", "White Kidney Bean Extract", "common_bean_extract", 1500),
])
def test_enrichment_produces_the_assessment_consumed_by_public_score(enricher, record, name, canonical, amount):
    from test_green_tea_evidence_identity import _source_product
    source = _source_product(name)
    row = source["activeIngredients"][0]
    row.update(canonical_id=canonical, standardName=name, quantity=amount, ingredientGroup=name)
    row["raw_taxonomy"]["ingredientGroup"] = name
    enriched, issues = enricher.enrich_product(source)
    assert enriched.get("enrichment_status") != "validation_failed", issues
    assessment, = [a for a in enriched["rda_ul_data"]["clinical_exposure_assessments"] if a["record_id"] == record]
    scored = build_scored_artifact(enriched)
    assert any(f["value_display"] == assessment["notes"] for f in scored["quality_pillars_v4"]["dose"]["explanation"]["facts"])


def test_wrong_declared_purpose_cannot_borrow_a_research_regimen():
    from dose_assessment import clinical_research_exposure_assessments
    p = product("INGR_D_MANNOSE", "D-Mannose", "d_mannose", 2000)
    p["statements"] = [{"type":"Formulation re: Other", "notes":"D mannose supports sleep."}]
    assert clinical_research_exposure_assessments(p) == []


def test_population_context_is_preserved_without_inventing_patient_membership():
    from dose_assessment import clinical_research_exposure_assessments
    p = product("INGR_D_MANNOSE", "D-Mannose", "d_mannose", 2000)
    # Product tags cannot establish a recurrent-UTI diagnosis or membership in
    # the clinical cohort. The assessment must remain explicitly study-scoped.
    p["targetGroups"] = ["Men", "Children 4 or More Years of Age"]
    a, = clinical_research_exposure_assessments(p)
    assert "Women 18 or older" in a["studied_population"]
    assert "adult women with recurrent UTI" in a["notes"]
    assert a["supported_outcomes"] == ["recurrent_uti_prevention"]


def test_undisclosed_blend_member_never_borrows_the_parent_total(enricher):
    from test_clinical_source_owner_projection import _green_tea_complex
    source = _green_tea_complex(disclosed=False)
    parent = source["activeIngredients"][0]
    parent.update(name="Proprietary Blend", raw_source_text="Proprietary Blend", quantity=2000, canonical_id="")
    child = parent["nestedIngredients"][1]
    child.update(name="D-Mannose", raw_source_text="D-Mannose", standardName="D-Mannose", canonical_id="d_mannose", ingredientGroup="D-Mannose", forms=[])
    child["raw_taxonomy"].update(ingredientGroup="D-Mannose", forms=[])
    enriched, issues = enricher.enrich_product(source)
    assert enriched.get("enrichment_status") != "validation_failed", issues
    a, = [a for a in enriched["rda_ul_data"]["clinical_exposure_assessments"] if a["record_id"] == "INGR_D_MANNOSE"]
    assert a["status"] == "unknown"
    assert a["minimum"] is None
    assert a["source_row_ref"].endswith("nestedRows[1]")
