"""Report-only sensitivity analysis must not mutate or bless production scores."""
from copy import deepcopy

import pytest


def dimensions():
    return {
        "formulation": {"score": 24, "max": 25, "components": {
            "total_cfu_disclosed": 4, "cfu_amount": 5,
            "named_species_diversity": 4, "identified_strain_codes": 8,
            "delivery_survivability": 3}, "penalties": {},
            "metadata": {"identified_strain_count": 1, "total_strain_count": 1}},
        "dose": {"score": 14, "max": 25, "components": {
            "per_strain_cfu_disclosure": 10, "cfu_adequacy": 4}, "penalties": {},
            "metadata": {"cfu_adequacy_basis": "aggregate_cfu_disclosed_only"}},
        "transparency": {"score": 10, "max": 15, "components": {
            "strain_identities_named": 8, "per_strain_cfu_on_label": 0,
            "aggregate_cfu_disclosure_proxy": 2}, "penalties": {}},
        "evidence": {"score": 8, "max": 20, "components": {"research": 8}, "penalties": {}},
    }


def alter(value, variant, pdata=None):
    from audits.probiotic_rubric_review_2026_09_04.shadow import alter_dimensions
    return alter_dimensions(value, pdata or {}, variant)


def test_size_count_ablation_preserves_source_and_other_pillars():
    original = dimensions()
    saved = deepcopy(original)
    result = alter(original, "form_no_size_diversity")
    assert original == saved
    assert result["formulation"]["score"] == 15
    assert result["dose"] == original["dose"]
    assert result["evidence"] == original["evidence"]


@pytest.mark.parametrize("identified,total,expected", [(1, 1, 8), (2, 2, 8), (1, 20, .4), (0, 0, 0)])
def test_identity_fraction_does_not_reward_larger_fully_identified_blends(identified, total, expected):
    source = dimensions()
    source["formulation"]["metadata"].update(identified_strain_count=identified, total_strain_count=total)
    assert alter(source, "identity_fraction")["formulation"]["components"]["identified_strain_codes"] == expected


@pytest.mark.parametrize("cfu", [100_000_000, 100_000_000_000])
def test_flat_disclosure_is_quantity_invariant(cfu):
    result = alter(dimensions(), "flat_total_disclosure", {"total_cfu": cfu})
    assert result["transparency"]["components"]["aggregate_cfu_disclosure_proxy"] == 4


def test_flat_disclosure_does_not_rescue_invalid_total_or_stack():
    source = dimensions()
    source["transparency"]["components"]["per_strain_cfu_on_label"] = 7
    assert alter(source, "flat_total_disclosure", {"total_cfu": 1e9})["transparency"]["components"]["aggregate_cfu_disclosure_proxy"] == 0
    assert alter(source, "flat_total_disclosure", {"total_cfu": float("inf")})["transparency"]["components"]["aggregate_cfu_disclosure_proxy"] == 0


@pytest.mark.parametrize("reviewed,per_strain,expected", [(True, 0, 4), (True, 7, 0), (False, 0, 0)])
def test_flat_disclosure_handles_verified_formula_native_unit(reviewed, per_strain, expected):
    source = dimensions()
    source["transparency"]["components"] = {
        "aggregate_native_afu_disclosure": 2,
        "per_strain_cfu_on_label": per_strain,
    }
    source["transparency"]["metadata"] = {"studied_formula_assessment": {
        "status": "assessed_studied_formula" if reviewed else "not_applicable"}}
    result = alter(source, "flat_total_disclosure")
    assert result["transparency"]["components"]["aggregate_native_afu_disclosure"] == expected


def test_dose_ablation_withholds_disclosure_not_actual_measures():
    source = dimensions()
    assert alter(source, "dose_without_disclosure")["dose"]["score"] == 0
    source["dose"]["metadata"]["cfu_adequacy_basis"] = "per_strain_cfu_disclosed"
    assert alter(source, "dose_without_disclosure")["dose"]["score"] == 4


def test_formula_is_not_exempt_from_formulation_potency_ablation():
    source = dimensions()
    source["formulation"]["components"] = {
        "native_potency_disclosed": 4, "studied_formula_potency": 5,
        "studied_formula_strain_identity": 8, "named_species_diversity": 2,
        "delivery_survivability": 3, "prebiotic_complement": 1}
    assert alter(source, "form_no_size_diversity")["formulation"]["score"] == 16


def test_unknown_shadow_never_silently_uses_baseline():
    with pytest.raises(ValueError):
        alter(dimensions(), "typo")


@pytest.mark.parametrize("status", ["suppressed_safety", "not_scored"])
def test_report_preserves_unscored_records_without_module_breakdown(status):
    from audits.probiotic_rubric_review_2026_09_04.shadow import audit_record
    record = {"id": "held", "name": "Held label", "brand": "Test", "full_reenrichment": False,
              "candidate": {"score": None, "status": status, "pillars": {}},
              "candidate_detail": {"_v4_module_breakdown": None, "probiotic_data": {},
                                   "native_evidence_assessment": {}}}
    result = audit_record(record)
    assert result["dimensions"] == {}
    assert result["baseline"]["status"] == status
    assert all(row["score"] is None for row in result["shadows"].values())
    assert all(row["status"] == status for row in result["shadows"].values())


def test_impact_exposes_denominators_and_excludes_unscored():
    from audits.probiotic_rubric_review_2026_09_04.shadow import impact
    rows = [{"baseline": {"score": old}, "shadows": {"probe": {"score": new}}}
            for old, new in [(10, 20), (20, 10), (None, None)]]
    result = impact(rows, "probe")
    assert result["population_count"] == 3
    assert result["scored_count"] == 2
    assert result["excluded_unscored_count"] == 1
    assert result["scored_pair_count"] == 1
    assert result["strict_pairwise_rank_reversals"] == 1


def test_empty_scored_population_is_explicit_not_divided_by_zero():
    from audits.probiotic_rubric_review_2026_09_04.shadow import impact
    result = impact([], "probe")
    assert result["scored_count"] == 0
    assert result["mean_delta"] is None


def test_adversarial_probes_are_labelled_and_do_not_change_registry():
    from audits.probiotic_rubric_review_2026_09_04.probes import run_probes
    from studied_formulas import _clinical_strain_registry
    before = deepcopy(_clinical_strain_registry())
    result = run_probes()
    assert _clinical_strain_registry() == before
    assert result["clinical_approval"] is False
    assert len(result["cases"]) == 10
    assert all(row["synthetic"] for row in result["cases"])
    case = {r["name"]: r for r in result["cases"]}
    assert case["LGG 0.1B"]["dimensions"]["dose"]["components"]["cfu_adequacy"] == 0
    assert case["two reviewed-scope fixtures"]["dimensions"]["evidence"]["score"] > case["one reviewed-scope fixture"]["dimensions"]["evidence"]["score"]
    assert case["two-strain finished-formula fixture"]["dimensions"]["dose"]["score"] == 25
