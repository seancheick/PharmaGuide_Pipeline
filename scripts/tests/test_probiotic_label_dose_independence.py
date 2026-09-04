"""Label identity and measured potency must not inherit citation-review state."""
from copy import deepcopy
import json

import pytest

import studied_formulas
from scoring_v4.modules.probiotic_dose import score_dose
from scoring_v4.modules.probiotic_evidence import score_evidence
from scoring_v4.modules.probiotic_formulation import score_formulation
from scoring_v4.modules.probiotic_transparency import score_transparency
from test_probiotic_applicability_rubric import strain_product
from test_studied_formula_assessment import seed_label


def owned_label(dose=1e10):
    product = strain_product(dose=dose)
    product["probiotic_data"].update(total_strain_count=1,
        total_billion_count=(dose or 0) / 1e9, guarantee_type="at_expiration")
    return product


def aggregate_label():
    product = owned_label(None)
    other = strain_product(dose=None, clinical_id="STRAIN_LACTIS_BB12",
                           name="Bifidobacterium lactis BB-12")
    other["activeIngredients"][0]["raw_source_path"] = "ingredientRows[1]"
    other["probiotic_data"]["clinical_strains"][0]["source_row_ref"] = "ingredientRows[1]"
    product["activeIngredients"] += other["activeIngredients"]
    product["probiotic_data"]["clinical_strains"] += other["probiotic_data"]["clinical_strains"]
    product["probiotic_data"].update(total_strain_count=2, total_billion_count=11,
                                    total_cfu=11e9, has_cfu=True)
    return product


@pytest.mark.parametrize("aggregate", [False, True])
@pytest.mark.parametrize("change", ["hold", "support", "effect"])
def test_citation_review_does_not_change_label_dose_or_formulation(monkeypatch, aggregate, change):
    product = aggregate_label() if aggregate else owned_label()
    before = score_dose(product), score_formulation(product)
    registry = deepcopy(studied_formulas._clinical_strain_registry())
    thresholds = registry["STRAIN_LGG"]["cfu_thresholds"]
    if change == "hold":
        thresholds["dr_pham_signoff"] = False
        product["probiotic_data"]["clinical_strains"][0].update(
            research_match_status="pending_review", review_status="pending_review",
            dr_pham_signoff=False, clinical_support_level=None)
    elif change == "support":
        thresholds["evidence"]["clinical_support_level"] = "weak"
        thresholds["evidence"]["evidence_strength"] = "weak"
    else:
        thresholds["evidence"]["effect_direction"] = "negative"
    monkeypatch.setattr(studied_formulas, "_clinical_strain_registry", lambda: registry)
    after = score_dose(product), score_formulation(product)
    for old, new in zip(before, after):
        assert old["score"] == new["score"]
        assert old["components"] == new["components"]
    if change == "hold":
        assert score_evidence(product)["score"] == 0


def test_aggregate_blend_keeps_presence_credit_without_inventing_strain_allocations():
    dose = score_dose(aggregate_label())
    assert dose["components"]["per_strain_cfu_disclosure"] == 0
    assert dose["components"]["cfu_adequacy"] == 4  # existing named-total floor
    proxy = dose["metadata"]["aggregate_cfu_proxy"]
    assert proxy["reason"] == "aggregate_cfu_named_label_presence"
    assert "proxy_cfu_per_strain" not in proxy
    assert "proxy_tier" not in proxy
    assert dose["metadata"]["cfu_adequacy_basis"] == "aggregate_cfu_disclosed_only"


def test_duplicate_enrichment_projection_cannot_multiply_dose_or_identity_credit():
    product = owned_label()
    before = score_dose(product), score_formulation(product)
    product["probiotic_data"]["clinical_strains"] *= 3
    after = score_dose(product), score_formulation(product)
    assert [p["score"] for p in before] == [p["score"] for p in after]


@pytest.mark.parametrize("reverse", [False, True])
def test_conflicting_duplicate_reviews_fail_closed_independently_of_row_order(reverse):
    p = owned_label()
    before = score_dose(p)["score"], score_formulation(p)["score"]
    verified = p["probiotic_data"]["clinical_strains"][0]
    verified.update(review_status="clinician_verified", dr_pham_signoff=True,
                    research_match_status="exact_strain")
    held = {**verified, "review_status": "pending_review", "dr_pham_signoff": False,
            "research_match_status": "pending_review"}
    p["probiotic_data"]["clinical_strains"] = [verified, held][:: -1 if reverse else 1]
    assert score_evidence(p)["score"] == 0
    assert (score_dose(p)["score"], score_formulation(p)["score"]) == before
    rows = studied_formulas.assess_probiotic_evidence(p)["strain_assessments"]
    assert len(rows) == 1
    assert rows[0]["research_accepted"] is False


@pytest.mark.parametrize("conflict", [None, "review", "blocked", "inactivated"])
def test_export_consolidates_native_projections_without_losing_holds(conflict):
    from build_final_db import build_detail_blob

    p = owned_label()
    p["probiotic_data"]["is_probiotic_product"] = True
    row = p["probiotic_data"]["clinical_strains"][0]
    row.update(review_status="clinician_verified", research_match_status="exact_strain")
    duplicate = deepcopy(row)
    if conflict == "review":
        duplicate.update(review_status="pending_review", research_match_status="pending_review")
    elif conflict == "blocked":
        duplicate.update(is_blocked=True, block_reason="Rejected source identity")
    elif conflict == "inactivated":
        duplicate.update(is_inactivated=True)
    outputs = []
    for rows in ([row, duplicate], [duplicate, row]):
        p["probiotic_data"]["clinical_strains"] = rows
        detail = build_detail_blob(p, {})["probiotic_detail"]
        assert detail["clinical_strain_count"] == 1
        outputs.append(detail["clinical_strains"])
    assert outputs[0] == outputs[1]
    exported = outputs[0][0]
    if conflict == "review":
        assert exported["research_match_status"] == "pending_review"
        assert exported["clinical_support_level"] is None
    elif conflict == "blocked":
        assert exported["is_blocked"] is True
        assert exported["block_reason"] == "Rejected source identity"
        assert score_formulation(p)["components"]["identified_strain_codes"] == 0
    elif conflict == "inactivated":
        assert exported["is_inactivated"] is True
        assert score_dose(p)["metadata"]["cfu_adequacy_v3_points"] == 0


@pytest.mark.parametrize("count", [None, 0, -1, True, float("nan"), float("inf"), "inf"])
def test_has_cfu_flag_cannot_manufacture_numeric_disclosure(count):
    product = owned_label()
    product["probiotic_data"].update(total_cfu=0, total_billion_count=0)
    product["probiotic_data"]["probiotic_blends"][0]["cfu_data"]["cfu_count"] = count
    dose = score_dose(product)
    assert dose["components"]["per_strain_cfu_disclosure"] == 0
    assert dose["score"] == 0
    json.dumps(dose, allow_nan=False)


@pytest.mark.parametrize("field", ["total_strain_count", "total_billion_count", "total_cfu"])
@pytest.mark.parametrize("value", [True, float("nan"), float("inf")])
def test_nonfinite_summary_cannot_crash_or_inflate_potency(field, value):
    product = {"probiotic_data": {field: value}}
    for scorer in (score_dose, score_formulation):
        result = scorer(product)
        assert result["score"] == 0
        json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("count", [True, float("nan"), float("inf"), -1, None, 11])
def test_export_cfu_summary_uses_the_same_validated_measurement_as_scoring(count):
    from build_final_db import build_detail_blob

    p = {"probiotic_data": {"is_probiotic_product": True, "has_cfu": True,
                             "total_cfu": 1e10, "total_billion_count": count}}
    detail = build_detail_blob(p, {})["probiotic_detail"]
    assert detail["total_cfu"] == 0
    assert detail["total_billion_count"] == 0
    assert detail["has_cfu"] is False
    assert detail["total_cfu_label"] == ""
    json.dumps(detail, allow_nan=False)


def test_export_cfu_summary_can_normalize_one_valid_count_without_inventing_a_second_measurement():
    from build_final_db import build_detail_blob

    p = {"probiotic_data": {"is_probiotic_product": True, "total_cfu": 1e10}}
    detail = build_detail_blob(p, {})["probiotic_detail"]
    assert detail["total_billion_count"] == 10
    assert detail["has_cfu"] is True
    assert detail["total_cfu_label"] == "10 billion CFU"


@pytest.mark.parametrize("consumer", ["routing", "completeness", "legacy_readiness", "dose_reason"])
@pytest.mark.parametrize("total", [True, float("inf"), 11, None])
def test_validation_is_shared_by_route_gate_readiness_and_dose_reason(consumer, total):
    from test_v4_completeness_gate import _ingredient, _product

    pdata = {"is_probiotic_product": True, "has_cfu": True,
             "total_cfu": 3e9, "total_billion_count": total, "total_strain_count": 2,
             "probiotic_blends": [{"strains": ["Lactobacillus acidophilus", "Bifidobacterium lactis"],
                                    "cfu_data": {"billion_count": 11}}]}
    p = _product(module="probiotic", probiotic_data=pdata, ingredients=[
        _ingredient(name="Lactobacillus acidophilus", canonical_id="lactobacillus_acidophilus")])
    if consumer == "routing":
        from scoring_v4.route_features import extract_route_features
        features = extract_route_features(p, [])
        assert features["probiotic_has_cfu"] is False
        assert features["probiotic_total_billion_count"] == 0
    elif consumer == "completeness":
        from scoring_v4.gate_completeness import evaluate_completeness_gate
        assert "total_cfu_not_disclosed" in evaluate_completeness_gate(p, "probiotic").soft_missing
    elif consumer == "legacy_readiness":
        from assessment_readiness import _dose_readiness
        result = _dose_readiness(p, [{"material": True, "source_row_ref": "ingredientRows[0]"}],
                                 module="probiotic")
        assert result["readiness"] == "incomplete"
    else:
        assert score_dose(p)["metadata"]["window_proxy_reason"] == "per_strain_cfu_missing"


def test_completeness_never_resums_duplicate_child_measurements_to_invent_a_total():
    from scoring_v4.gate_completeness import _total_cfu_billion
    assert _total_cfu_billion({"probiotic_data": {"probiotic_blends": [
        {"cfu_data": {"billion_count": 11}}, {"cfu_data": {"billion_count": 11}}]}}) == 0


def test_legacy_product_evidence_cannot_repair_conflicting_cfu_totals():
    from scoring_input_contract import _derive_probiotic_cfu_evidence

    pdata = {"is_probiotic_product": True, "total_cfu": 3e9, "total_billion_count": 3,
             "total_strain_count": 1, "probiotic_blends": [{"strains": ["Lactobacillus acidophilus"]}],
             "cfu_raw_source_path": "ingredientRows[0]", "cfu_linked_rows": ["ingredientRows[0]"]}
    p = {"probiotic_data": pdata, "supplement_taxonomy": {"primary_type": "probiotic"}}
    assert _derive_probiotic_cfu_evidence(p)["dose_value"] == 3e9
    pdata["total_billion_count"] = 11
    assert _derive_probiotic_cfu_evidence(p) is None


def test_conflicting_total_cannot_supply_the_high_cfu_route_predicate():
    from scoring_input_contract import _route_is_probiotic_class
    from test_v4_completeness_gate import _product

    pdata = {"is_probiotic_product": True, "has_cfu": True, "total_cfu": 11e9,
             "total_billion_count": 11, "total_strain_count": 1}
    p = _product(probiotic_data=pdata)
    assert _route_is_probiotic_class(p, "daily blend") is True
    pdata["total_cfu"] = 3e9
    assert _route_is_probiotic_class(p, "daily blend") is False


def test_goal_dose_gate_cannot_trust_an_invalid_total():
    from build_final_db import _probiotic_goal_cluster_applies

    p = {"probiotic_data": {"is_probiotic_product": True, "total_strain_count": 2,
                             "total_cfu": 3e9, "total_billion_count": 11}}
    assert _probiotic_goal_cluster_applies(p, enforce_dose_gate=False) is True
    assert _probiotic_goal_cluster_applies(p, enforce_dose_gate=True) is False


def test_serving_header_never_replaces_literal_label_text_with_a_conflicting_total():
    from build_final_db import _fold_probiotic_serving_headers

    p = {"probiotic_data": {"total_cfu": 3e9, "total_billion_count": 11,
                            "probiotic_blends": [{"name": "Probiotic Blend",
                                "raw_source_path": "ingredientRows[0]", "is_blend_header_total": True}]}}
    ledger = [{"label_display_name": "Probiotic Blend", "nested_depth": 0,
               "raw_source_path": f"ingredientRows[{i}]", "source_section": "activeIngredients",
               "exact_dose_text": f"{5 * (i + 1)} billion CFU"} for i in range(2)]
    folded = _fold_probiotic_serving_headers(p, ledger)
    assert folded[0]["exact_dose_text"] == "5 billion CFU"


def test_dose_basis_names_actual_winner_not_merely_available_aggregate():
    product = aggregate_label()
    source = owned_label(5e10)
    product["probiotic_data"]["probiotic_blends"] = source["probiotic_data"]["probiotic_blends"]
    product["activeIngredients"][0] = source["activeIngredients"][0]
    dose = score_dose(product)
    assert dose["metadata"]["cfu_adequacy_basis"] == "per_strain_cfu_disclosed"
    assert dose["metadata"]["aggregate_cfu_proxy"]["applied"] is False


def test_formula_native_dose_is_unchanged_and_never_converted_to_cfu():
    result = score_dose(seed_label())
    assert result["score"] == 25
    assert result["metadata"]["dose_adequacy_basis"] == "studied_formula_native_afu"


def test_direct_mass_floor_requires_exact_source_owner_not_substring():
    from test_v4_probiotic_dose_p22 import _no_cfu_probiotic, _strain
    p = _no_cfu_probiotic(active_rows=[{"name": "Lactobacillus rhamnosus GGX",
        "quantity": 25, "unit": "mg"}], clinical_strains=[_strain(
            "Lactobacillus rhamnosus GG", cfu_per_day=None)])
    assert score_dose(p)["score"] == 0


def test_source_owner_not_current_review_flag_controls_formulation_identity():
    p = owned_label()
    p["activeIngredients"][0]["name"] = "Lactobacillus rhamnosus HN001"
    assert score_formulation(p)["components"]["identified_strain_codes"] == 0


def test_normalized_billion_count_can_prove_disclosure_without_clinical_review():
    p = owned_label()
    m = p["probiotic_data"]["probiotic_blends"][0]["cfu_data"]
    m.pop("cfu_count")
    m["billion_count"] = 10
    assert score_dose(p)["components"]["per_strain_cfu_disclosure"] == 10
    assert score_dose(p)["components"]["cfu_adequacy"] == 6


@pytest.mark.parametrize("change", ["scope", "owner", "conflicting_counts"])
def test_product_total_or_conflicting_measure_cannot_pose_as_individual_disclosure(change):
    p = owned_label()
    p["probiotic_data"].update(total_cfu=0, total_billion_count=0)
    m = p["probiotic_data"]["probiotic_blends"][0]["cfu_data"]
    if change == "scope":
        m["evidence_scope"] = "product_level"
    elif change == "owner":
        m["raw_source_path"] = "ingredientRows[4]"
    else:
        m["billion_count"] = 50
    dose = score_dose(p)
    assert dose["components"]["per_strain_cfu_disclosure"] == 0
    assert dose["score"] == 0


def test_pillars_do_not_reconstruct_a_conflicting_or_missing_total_from_child_projections():
    p = aggregate_label()
    p["probiotic_data"]["total_cfu"] = 3e9  # contradicts the 11B twin
    p["probiotic_data"]["probiotic_blends"] = [{"strains": ["a", "b"],
        "cfu_data": {"has_cfu": True, "billion_count": 40, "cfu_count": 40e9}}]
    for present in (True, False):
        if not present:
            p["probiotic_data"].pop("total_cfu")
            p["probiotic_data"].pop("total_billion_count")
        assert score_dose(p)["components"]["cfu_adequacy"] == 0
        assert score_formulation(p)["components"]["total_cfu_disclosed"] == 0
        assert score_transparency(p)["components"]["aggregate_cfu_disclosure_proxy"] == 0


def test_identical_source_measurement_projections_do_not_erase_daily_potency():
    p = owned_label()
    before = score_dose(p)
    p["probiotic_data"]["probiotic_blends"] *= 2
    assert score_dose(p)["score"] == before["score"]


def test_daily_range_uses_minimum_for_potency_without_inventing_a_discrete_studied_dose():
    p = owned_label()
    before = score_dose(p)
    p["serving_basis"]["max_servings_per_day"] = 2
    dose = score_dose(p)
    assert dose["score"] == before["score"]
    row = dose["metadata"]["cfu_adequacy_contributions"][0]
    assert row["cfu_per_day"] == 1e10
    assert row["maximum_cfu_per_day"] == 2e10
    assert studied_formulas.assess_probiotic_evidence(p)["strain_assessments"][0]["cfu_per_day"] is None


def test_conflicting_source_measurements_cannot_award_daily_potency():
    p = owned_label()
    other = deepcopy(p["probiotic_data"]["probiotic_blends"][0])
    other["cfu_data"]["cfu_count"] = 50e9
    p["probiotic_data"]["probiotic_blends"].append(other)
    assert score_dose(p)["components"]["cfu_adequacy"] == 0


def test_matching_path_does_not_authorize_another_strains_measurement():
    p = owned_label()
    p["probiotic_data"]["probiotic_blends"][0]["strains"] = ["Bifidobacterium lactis BB-12"]
    assert score_dose(p)["components"]["cfu_adequacy"] == 0
