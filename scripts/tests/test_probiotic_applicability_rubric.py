"""Clinical credit follows source evidence, not wording or blend length."""
from copy import deepcopy

import pytest

import studied_formulas
from scoring_v4.modules.probiotic_evidence import score_evidence
from test_studied_formula_assessment import seed_label


def strain_product(*, dose=None, clinical_id="STRAIN_LGG", name="Lactobacillus rhamnosus GG"):
    row = {"name": name, "raw_source_path": "ingredientRows[0]", "quantity": dose or 0,
           "unit": "CFU" if dose else "NP"}
    return {"product_name": "Daily Probiotic", "form_factor_canonical": "capsule",
            "serving_basis": {"min_servings_per_day": 1, "max_servings_per_day": 1,
                              "servings_per_day_source": "label"},
            "target_population": "adult", "activeIngredients": [row],
            "probiotic_data": {"probiotic_blends": [{"strains": [name],
                "raw_source_path": row["raw_source_path"], "cfu_data": {
                    "has_cfu": dose is not None,
                    "cfu_count": dose, "raw_source_path": row["raw_source_path"],
                    "evidence_scope": "row_level"}}], "clinical_strains": [{"strain": name,
                "clinical_id": clinical_id, "source_row_ref": row["raw_source_path"],
                "cfu_per_day": dose, "adequacy_tier": "good" if dose else None,
                "clinical_support_level": "high", "indication_primary": "digestive"}]}}


@pytest.mark.parametrize("phrase", ["Digestive support", "Immune support", "Gut health", ""])
def test_formula_core_evidence_is_invariant_to_marketing(phrase):
    p = seed_label()
    before = score_evidence(p)
    p["statements"] = [{"type": "Formulation re: Other", "notes": phrase}]
    after = score_evidence(p)
    assert before["score"] == after["score"]
    assert before["components"] == after["components"]
    assert "claim_alignment" in after["metadata"]
    assert studied_formulas.assess_studied_formula(p)["status"] == "assessed_studied_formula"


def test_many_undosed_strains_cannot_accumulate_full_evidence():
    p = strain_product()
    one = score_evidence(p)
    for index, (cid, name) in enumerate([
        ("STRAIN_RHAMNOSUS_HN001", "Lactobacillus rhamnosus HN001"),
        ("STRAIN_LONGUM_BB536", "Bifidobacterium longum BB536"),
        ("STRAIN_LACTIS_BB12", "Bifidobacterium lactis BB-12"),
    ], 1):
        other = strain_product(clinical_id=cid, name=name)
        other["activeIngredients"][0]["raw_source_path"] = f"ingredientRows[{index}]"
        other["probiotic_data"]["clinical_strains"][0]["source_row_ref"] = f"ingredientRows[{index}]"
        p["activeIngredients"] += other["activeIngredients"]
        p["probiotic_data"]["clinical_strains"] += other["probiotic_data"]["clinical_strains"]
    assert score_evidence(p)["score"] == one["score"]
    assert score_evidence(p)["score"] < 20


def test_industry_tiers_cannot_be_called_a_verified_clinical_dose():
    p = strain_product(dose=10_000_000_000)
    p["probiotic_data"]["clinical_strains"][0]["dose_basis"] = "clinical"  # stale/caller stamp
    assessment = studied_formulas.assess_probiotic_evidence(p)
    row = assessment["strain_assessments"][0]
    assert row["status"] == "strain_dose_reference_unreviewed"
    assert row["dose_applicable"] is False


def test_native_dose_copy_distinguishes_potency_from_clinical_efficacy():
    from scoring_v4.modules.probiotic_dose import score_dose
    from scoring_v4.quality_score import _probiotic_dose_reason

    dose = score_dose(strain_product(dose=1e10))
    assert dose["metadata"]["reference_basis"] == "industry_potency_not_trial_efficacy"
    assert "not proof of clinical benefit" in _probiotic_dose_reason(dose, "fallback")


def test_species_research_is_not_presented_as_exact_strain_evidence():
    from scoring_v4.quality_score import _pillar_evidence

    p = strain_product(dose=5e9, clinical_id="STRAIN_SACCHAROMYCES",
                       name="Saccharomyces boulardii")
    # A copied status must not upgrade the registry's species-general scope.
    p["probiotic_data"]["clinical_strains"][0]["research_match_status"] = "exact_strain"
    evidence = score_evidence(p)
    row = evidence["metadata"]["evidence_assessment"]["strain_assessments"][0]
    assert row["evidence_scope"] == "species_general"
    assert row["status"] == "strain_dose_reference_unreviewed"
    assert row["dose_applicable"] is False
    assert evidence["metadata"]["native_clinical_strain_evidence_rows"][0]["evidence_scope"] == "species_general"
    cfg = {"evidence_subscale": {"archetype_reference": {"probiotic": 20}, "default_reference": 20}}
    copy = _pillar_evidence(evidence, 20, "probiotic", cfg)["reason"]
    assert "species-level" in copy
    assert "exact studied strain" in copy
    assert "Named strains" not in copy


@pytest.mark.parametrize("field,value", [
    ("source_pmids", [None]), ("supported_outcomes", [""]),
    ("dosage_forms", [None]), ("target_population", {}),
])
def test_malformed_curated_scope_is_unreviewed(reviewed_dose, field, value):
    studied_formulas._clinical_strain_registry()["STRAIN_LGG"]["applicability"][field] = value
    assessment = studied_formulas.assess_probiotic_evidence(strain_product(dose=1e10))
    assert assessment["strain_assessments"][0]["status"] == "strain_dose_reference_unreviewed"


def test_unknown_dose_and_wrong_strain_are_distinct():
    unknown = studied_formulas.assess_probiotic_evidence(strain_product())
    wrong = studied_formulas.assess_probiotic_evidence(strain_product(name="Lactobacillus rhamnosus HN001"))
    assert unknown["strain_assessments"][0]["status"] == "strain_dose_unknown"
    assert wrong["strain_assessments"][0]["status"] == "strain_identity_mismatch"
    assert score_evidence(strain_product(name="Lactobacillus rhamnosus HN001"))["score"] == 0


@pytest.mark.parametrize("owners,accepted", [(0, False), (1, True), (2, False)])
def test_legacy_native_match_requires_one_actual_label_owner(owners, accepted):
    p = strain_product()
    p["probiotic_data"]["clinical_strains"][0].pop("source_row_ref")
    owner = p["activeIngredients"][0]
    p["activeIngredients"] = [{**owner, "raw_source_path": f"ingredientRows[{i}]"} for i in range(owners)]
    result = studied_formulas.assess_probiotic_evidence(p)["strain_assessments"][0]
    assert result["research_accepted"] is accepted
    assert (score_evidence(p)["score"] > 0) is accepted


@pytest.fixture
def reviewed_dose(monkeypatch):
    # Synthetic reviewed policy exercises the same contract without publishing a claim.
    registry = deepcopy(studied_formulas._clinical_strain_registry())
    registry["STRAIN_LGG"]["applicability"] = {
        "dose_unit": "CFU", "minimum_daily_dose": 1e9, "maximum_daily_dose": 2e10,
        "dosage_forms": ["capsule"], "target_population": "adult",
        "studied_population": "Synthetic adult test population",
        "supported_outcomes": ["digestive"], "source_pmids": ["26756877"],
    }
    monkeypatch.setattr(studied_formulas, "_clinical_strain_registry", lambda: registry)


@pytest.mark.parametrize("change,expected", [
    (None, "strain_dose_applicable"), ("low", "strain_dose_incompatible"),
    ("high", "strain_dose_incompatible"), ("form", "strain_context_mismatch"),
    ("population", "strain_context_mismatch"), ("missing_population", "strain_context_unresolved"),
    ("unknown", "strain_dose_unknown"),
])
def test_reviewed_strain_dose_scope_is_reproved(reviewed_dose, change, expected):
    p = strain_product(dose=1e10)
    for key, value in (("low", 1e6), ("high", 1e12), ("unknown", None)):
        if change == key:
            p["probiotic_data"]["probiotic_blends"][0]["cfu_data"]["cfu_count"] = value
    if change == "form": p["form_factor_canonical"] = "yogurt"
    if change == "population": p["target_population"] = "infant"
    if change == "missing_population": p.pop("target_population")
    assert studied_formulas.assess_probiotic_evidence(p)["strain_assessments"][0]["status"] == expected


def test_unknown_dose_does_not_receive_exact_dose_evidence_credit(reviewed_dose):
    assert score_evidence(strain_product(dose=1e10))["score"] > score_evidence(strain_product())["score"]


def test_formula_dose_not_reduced_for_unknown_individual_allocations():
    from scoring_v4.modules.probiotic_dose import score_dose
    dose = score_dose(seed_label())
    assert dose["score"] == dose["max"]
    assert dose["metadata"]["per_strain_cfu_disclosed_count"] == 0
    assert "per_strain_cfu_disclosure" not in dose["components"]


def test_caller_dose_cannot_override_owner_measurement(reviewed_dose):
    from scoring_v4.modules.probiotic_dose import score_dose
    p = strain_product(dose=1e6)
    expected = score_dose(p)
    p["probiotic_data"]["clinical_strains"][0]["cfu_per_day"] = 1e10
    p["probiotic_data"]["clinical_strains"][0]["adequacy_tier"] = "excellent"
    assert studied_formulas.assess_probiotic_evidence(p)["strain_assessments"][0]["status"] == "strain_dose_incompatible"
    assert score_dose(p)["score"] == expected["score"]
    assert score_dose(p)["metadata"]["cfu_adequacy_contributions"][0]["cfu_per_day"] == 1e6


def test_caller_stamp_alone_does_not_create_disclosed_strain_dose():
    from scoring_v4.modules.probiotic_dose import score_dose
    p = strain_product()
    p["probiotic_data"]["clinical_strains"][0]["cfu_per_day"] = 1e10
    p["probiotic_data"]["clinical_strains"][0]["adequacy_tier"] = "excellent"
    assert score_dose(p)["components"]["per_strain_cfu_disclosure"] == 0


def test_blend_total_cannot_be_borrowed_by_one_strain(reviewed_dose):
    p = strain_product(dose=1e10)
    p["probiotic_data"]["probiotic_blends"][0]["strains"].append("Different strain")
    assert studied_formulas.assess_probiotic_evidence(p)["strain_assessments"][0]["status"] == "strain_dose_unknown"


def test_generic_strain_entry_cannot_bypass_wrong_identity():
    from test_v4_probiotic_evidence_p23 import _match
    p = strain_product(name="Lactobacillus rhamnosus HN001")
    p["evidence_data"] = {"clinical_matches": [_match(id="STRAIN_LGG")]}
    assert score_evidence(p)["score"] == 0


def test_evidence_metadata_is_json_serializable():
    import json
    json.dumps(score_evidence(seed_label()), allow_nan=False)


def test_registry_medium_support_is_not_lost():
    p = strain_product(clinical_id="STRAIN_LONGUM_BB536", name="Bifidobacterium longum BB536")
    assert score_evidence(p)["score"] == 6


def test_unfavorable_strain_does_not_hide_a_separate_supported_record():
    from test_v4_probiotic_evidence_p23 import _match
    p = strain_product()
    other = strain_product(clinical_id="STRAIN_LONGUM_BB536", name="Bifidobacterium longum BB536")
    other["activeIngredients"][0]["raw_source_path"] = "ingredientRows[1]"
    other["probiotic_data"]["clinical_strains"][0]["source_row_ref"] = "ingredientRows[1]"
    p["activeIngredients"] += other["activeIngredients"]
    p["probiotic_data"]["clinical_strains"] += other["probiotic_data"]["clinical_strains"]
    p["evidence_data"] = {"clinical_matches": [_match(id="STRAIN_LGG", effect_direction="negative")]}
    assert score_evidence(p)["score"] == 6


def test_evidence_copy_distinguishes_missing_applicability_from_poor_quality():
    from scoring_v4.quality_score import _pillar_evidence
    from scoring_v4.quality_score_config import config
    dim = score_evidence(strain_product())
    result = _pillar_evidence(dim, 20, "probiotic", config())
    assert "dose is not established for this label" in result["reason"]


def test_unfavorable_research_is_not_described_as_missing_research():
    from scoring_v4.quality_score import _pillar_evidence
    from scoring_v4.quality_score_config import config
    from test_v4_probiotic_evidence_p23 import _match

    p = strain_product()
    p["evidence_data"] = {"clinical_matches": [_match(id="STRAIN_LGG", effect_direction="negative")]}
    dim = score_evidence(p)
    assert dim["score"] == 0
    assert dim["metadata"]["evidence_result_state"] == "evaluated_unfavorable"
    assert "unfavorable" in _pillar_evidence(dim, 20, "probiotic", config())["reason"]


def test_unrecognized_effect_is_not_a_negative_clinical_finding():
    from test_v4_probiotic_evidence_p23 import _match
    p = strain_product()
    p["evidence_data"] = {"clinical_matches": [_match(id="STRAIN_LGG", effect_direction="unreviewed")]}
    assert score_evidence(p)["metadata"]["evidence_result_state"] != "evaluated_unfavorable"


def test_seed_companion_publication_does_not_upgrade_independent_efficacy():
    from clinical_applicability import reviewed_entries
    from studied_formulas import formula_clinical_match
    entry = reviewed_entries()["FORMULA_SEED_DS01"]
    assert {r["pmid"] for r in entry["references_structured"]} == {"41599868", "40944126", "41750436"}
    assert entry["study_type"] == "rct_single"
    assert entry["total_enrollment"] == 350
    assert entry["effect_direction"] == "positive_weak"
    assert entry["formula_contract"]["supported_outcomes"] == ["digestive"]
    match = formula_clinical_match(seed_label())
    assert "published_studies_count" not in match  # publications != independent replications
    assert "per-blend" in match["applicability_assessment"]["limitations"]


@pytest.mark.parametrize("scope,source,removed", [
    ("probiotic_strains_only", "ingredientRows[0]", True),
    ("mixed_or_unresolved", "ingredientRows[0]", False),
    ("probiotic_strains_only", "ingredientRows[9]", False),
])
def test_disclosure_opacity_consolidates_only_owned_pure_strain_blend(scope, source, removed):
    from scoring_v4.modules.probiotic_transparency import score_transparency
    from test_v4_probiotic_transparency_p25 import _probiotic
    names = ["Lactobacillus rhamnosus GG", "Bifidobacterium lactis BB-12"]
    p = _probiotic(strain_count=2, blends=[{"strains": names, "raw_source_path": source,
                   "cfu_data": {"has_cfu": True, "billion_count": 20}}])
    p["probiotic_data"]["strain_allocation_owner_refs"] = [source] if scope == "probiotic_strains_only" else []
    p["activeIngredients"] = [{"name": "Probiotic Complex", "raw_source_path": "ingredientRows[0]",
        "quantity": 100, "unit": "mg", "nestedIngredients": [{"name": n} for n in names]}]
    p["proprietary_blends"] = [{"name": "Probiotic Complex", "disclosure_level": "partial",
        "child_ingredients": [{"name": n} for n in names], "blend_total_mg": 100,
        "source_path": "activeIngredients[0]", "source_row_ref": "ingredientRows[0]", "hidden_count": 2}]
    p["proprietary_data"] = {"total_active_mg": 100, "total_active_ingredients": 2}
    result = score_transparency(p)
    assert (result["penalties"]["B5_proprietary_blend_opacity"] == 0) is removed
    assert result["components"]["per_strain_cfu_on_label"] == 0
    assert result["components"]["aggregate_cfu_disclosure_proxy"] == 4


def test_stale_positional_reference_cannot_consolidate_a_different_blend():
    from scoring_v4.modules.probiotic_transparency import _consolidate_strain_allocation_opacity
    evidence = [{"blend_name": "Prebiotic Blend", "source_path": "activeIngredients[0]",
                 "computed_blend_penalty_magnitude": 1, "computed_blend_penalty": -1}]
    pdata = {"strain_allocation_owner_refs": ["ingredientRows[0]"]}
    penalty, _ = _consolidate_strain_allocation_opacity(pdata, {"status": "unresolved"}, evidence)
    assert penalty == 1
