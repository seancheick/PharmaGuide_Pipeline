"""Exact formula evidence never becomes a universal AFU conversion."""
from copy import deepcopy

import pytest

from studied_formulas import assess_studied_formula, formula_clinical_match
from probiotic_measurements import pending_afu_measurements
from scoring_v4.modules.probiotic_dose import score_dose
from scoring_v4.modules.probiotic_evidence import score_evidence


def seed_label():
    # Transcribed from the approved label, not generated from the rule registry.
    groups = [
        ["B. longum SD-BB536-JP", "B. breve SD-BR3-IT", "L. plantarum SD-LP1-IT",
         "L. rhamnosus SD-LR6-IT", "L. rhamnosus HRVD113-US", "B. infantis SD-M63-JP",
         "B. lactis SD-BS5-IT", "B. lactis HRVD524-US", "L. crispatus SD-LCR01-IT",
         "L. casei HRVD300-US", "B. breve HRVD521-US", "B. longum HRVD90b-US",
         "B. lactis SD-150-BE", "L. fermentum SD-LF8-IT", "L. rhamnosus SD-GG-BE",
         "L. reuteri SD-RD830-FR"],
        ["B. adolescentis SD-BA5-IT", "L. reuteri SD-LRE2-IT"],
        ["L. salivarius SD-LS1-IT", "B. lactis SD-CECT8145-SP",
         "B. longum SD-CECT7347-SP", "L. casei SD-CECT9104-SP"],
        ["L. plantarum SD-LPLDL-UK", "B. lactis SD-MB2409-IT"],
    ]
    rows, measurements = [], []
    for i, names in enumerate(groups):
        ref = f"ingredientRows[{i}]"
        rows.append({"name": f"Probiotic Blend {i}", "raw_source_path": ref,
                     "nestedIngredients": [{"name": n, "raw_source_path": f"{ref}.nestedRows[{j}]"}
                                           for j, n in enumerate(names)]})
        measurements.append({"source_row_ref": ref, "source_value": [37, 8.05, 3.3, 5.25][i],
                             "source_unit": "Billion AFU", "normalized_unit": "AFU",
                             "normalized_value": [37, 8.05, 3.3, 5.25][i] * 1e9})
    rows.append({"name": "MAPP Microbiota-Accessible Polyphenolic Precursors",
                 "canonical_id": "pomegranate", "quantity": 400, "unit": "mg",
                 "raw_source_path": "ingredientRows[4]",
                 "forms": [{"name": "Indian Pomegranate (Fruit)"}],
                 "notes": "Indian pomegranate fruit; greater than 40% polyphenolic bioactives."})
    return {"brandName": "Seed", "fullName": "DS-01 Daily Synbiotic",
            "form_factor_canonical": "capsule", "activeIngredients": rows,
            "serving_basis": {"basis_count": 2, "basis_unit": "capsule",
                              "min_servings_per_day": 1, "max_servings_per_day": 1,
                              "servings_per_day_source": "servingSizes"},
            "probiotic_data": {"afu_measurements": measurements, "clinical_strains": []}}


def test_exact_seed_formula_receives_native_afu_assessment_and_scoped_evidence():
    product = seed_label()
    result = assess_studied_formula(product)
    assert result["status"] == "assessed_studied_formula"
    assert result["daily_dose"] == {"value": 53600000000, "unit": "AFU"}
    assert len(result["strain_source_row_refs"]) == 24
    assert result["source_pmids"] == ["41599868", "40944126"]
    assert pending_afu_measurements(product) == []
    dose = score_dose(product)
    assert dose["score"] == 15
    assert dose["components"] == {"per_strain_cfu_disclosure": 0, "studied_formula_dose_adequacy": 15}
    assert "total_cfu" not in result
    evidence = formula_clinical_match(product)
    assert evidence["study_type"] == "rct_single"
    assert evidence["evidence_scope"] == "formula_specific"


@pytest.mark.parametrize("change", ["strain", "species", "amount", "unit", "prebiotic",
                                    "extra", "missing", "name", "serving", "duplicate_ref",
                                    "counterfeit_status", "standardization", "redistributed_afu",
                                    "generic_prebiotic", "regrouped_strains"])
def test_formula_gate_rejects_partial_or_spoofed_identity(change):
    product = seed_label()
    rows = product["activeIngredients"]
    if change == "strain": rows[0]["nestedIngredients"][0]["name"] = "B. longum UNSTUDIED"
    if change == "species": rows[0]["nestedIngredients"][0]["name"] = "B. breve SD-BB536-JP"
    if change == "amount": product["probiotic_data"]["afu_measurements"][0]["normalized_value"] /= 2
    if change == "unit": product["probiotic_data"]["afu_measurements"][0]["normalized_unit"] = "CFU"
    if change == "prebiotic": rows[-1]["quantity"] = 200
    if change == "extra": rows.append({"name": "Unreviewed active", "quantity": 100, "unit": "mg"})
    if change == "missing": rows[0]["nestedIngredients"].pop()
    if change == "name": product["brandName"] = "Different manufacturer"
    if change == "serving": product["serving_basis"]["max_servings_per_day"] = 2
    if change == "duplicate_ref": rows[0]["nestedIngredients"][1]["raw_source_path"] = rows[0]["nestedIngredients"][0]["raw_source_path"]
    if change == "counterfeit_status":
        product["probiotic_data"]["studied_formula_assessment"] = {"status": "assessed_studied_formula"}
        rows[0]["nestedIngredients"].clear()
    if change == "standardization": rows[-1]["notes"] = "20% polyphenols"
    if change == "generic_prebiotic": rows[-1]["name"] = "Pomegranate extract"
    if change == "redistributed_afu":
        for m, delta in zip(product["probiotic_data"]["afu_measurements"], [1, -1, 0, 0]):
            m["source_value"] += delta
            m["normalized_value"] += delta * 1e9
    if change == "regrouped_strains":
        a, b = rows[0]["nestedIngredients"][0], rows[1]["nestedIngredients"][0]
        a["name"], b["name"] = b["name"], a["name"]
    assert assess_studied_formula(product)["status"] != "assessed_studied_formula"
    assert pending_afu_measurements(product)
    assert formula_clinical_match(product) is None


@pytest.mark.parametrize("field", ["serving_basis", "probiotic_data", "forms"])
def test_malformed_formula_contract_is_unresolved_not_a_pipeline_crash(field):
    product = seed_label()
    if field == "forms": product["activeIngredients"][-1]["forms"] = None
    else: product[field] = ["malformed"]
    assert assess_studied_formula(product)["status"] != "assessed_studied_formula"


def test_unreviewed_formula_strains_do_not_earn_independent_strain_credit():
    product = {"probiotic_data": {"clinical_strains": [{"strain": "B. breve SD-BR3-IT",
               "clinical_support_level": "moderate", "review_status": "pending_review",
               "research_match_status": "pending_review", "evidence_scope": "formula_specific",
               "indication_primary": "digestive"}]}}
    result = score_evidence(product)
    assert result["metadata"]["native_clinical_strain_evidence_score"] == 0
    assert result["metadata"]["strain_indication_categories"] == []


def test_formula_formulation_recognizes_native_potency_without_cfu_tiers():
    from scoring_v4.modules.probiotic_formulation import score_formulation
    result = score_formulation(seed_label())
    assert result["components"]["native_potency_disclosed"] == 4
    assert result["components"]["studied_formula_potency"] == 5
    assert result["components"]["studied_formula_strain_identity"] == 8
    assert result["components"]["prebiotic_complement"] == 1
    assert result["components"]["delivery_survivability"] == 3
    assert result["metadata"]["total_billion_count"] == 0
    assert "cfu_amount" not in result["components"]


def test_formula_transparency_credits_total_afu_but_not_per_strain_amounts():
    from scoring_v4.modules.probiotic_transparency import score_transparency, CAP_AGGREGATE_CFU_DISCLOSURE_PROXY
    from scoring_v4.quality_score import _probiotic_transparency_reason
    result = score_transparency(seed_label())
    assert result["components"]["aggregate_native_afu_disclosure"] == CAP_AGGREGATE_CFU_DISCLOSURE_PROXY
    assert result["components"]["per_strain_cfu_on_label"] == 0
    assert "CFU" not in _probiotic_transparency_reason(result, "fallback")
    assert "AFU" in _probiotic_transparency_reason(result, "fallback")


def test_native_strain_review_does_not_mark_an_unrelated_active_evaluated():
    from assessment_readiness import _probiotic_native_evidence_state
    owner = {"name": "Lactobacillus rhamnosus GG", "raw_source_path": "ingredientRows[0]"}
    unrelated = {"name": "Unreviewed plant extract", "raw_source_path": "ingredientRows[1]"}
    product = {"activeIngredients": [owner, unrelated],
               "probiotic_data": {"clinical_strains": [{"clinical_id": "STRAIN_LGG",
               "strain": owner["name"], "source_row_ref": owner["raw_source_path"],
               "clinical_support_level": "strong"}]}}
    assert _probiotic_native_evidence_state(product, owner) == "evaluated_supported"
    assert _probiotic_native_evidence_state(product, unrelated) is None
