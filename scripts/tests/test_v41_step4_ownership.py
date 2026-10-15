"""V4.1 Step 4 ownership: unfinished work, unread amounts and the shared neutral.

A label limitation (an amount the label never printed, a hidden blend share)
stays scored. PharmaGuide's own unfinished work (a printed amount we could not
read, a benchmark identity we could not resolve) marks the assessment partial.
An unbenchmarked amount is worth the same 11.4 public Dose points on every
route that uses the shared neutral, and hiding information never raises a total.
"""
from __future__ import annotations

import copy
import logging

import pytest

from audit_v4_archetype_fixtures import load_fixture_suite
from scoring_v4.quality_score import _probiotic_dose_reason, assemble_quality_score
from scoring_v4.scored_artifact import build_scored_artifact, unfinished_source_assessment

logging.disable(logging.WARNING)


def _fixture(case_id: str) -> dict:
    return copy.deepcopy(load_fixture_suite().by_id(case_id).product)


def _assemble(module: str, breakdown: dict) -> dict:
    return assemble_quality_score({"raw_score_v4_100": 50.0, "v4_verdict": "SAFE", "v4_module": module,
                                   "v4_breakdown": {"module": breakdown}})


# --- unfinished work vs label limitation ------------------------------------

@pytest.mark.parametrize(("printed", "reference", "expected"), [
    (6.0, True, "partial"),     # 331688 shape: a printed zinc number with an "NP" unit
    (0.0, True, "complete"),    # nothing printed: the label's limitation
    (None, True, "complete"),
    (6.0, False, "complete"),   # 54463 shape: a non-nutrient (phytosterols) with no RDA/UL reference
])
def test_a_printed_nutrient_amount_we_could_not_read_holds_the_assessment(printed, reference, expected):
    product = _fixture("prenatal_multi__ideal")
    # The adequacy owner's real skipped-row shape: no amount, no RDA/AI (it was
    # never computed), but the nutrient's reference record when one exists.
    product["rda_ul_data"]["adequacy_results"].append({
        "canonical_id": "zinc" if reference else "phytosterols", "nutrient": "Zinc",
        "rda_ai": None, "amount": None, "scoring_eligible": False,
        "data_by_group": {"19-30": {"rda": 11.0, "ul": 40.0}} if reference else {},
        "ul_status": "skipped_amount_not_declared", "original_quantity": printed, "original_unit": "NP",
    })
    artifact = build_scored_artifact(product)
    # A number printed without a readable unit is our parse gap; no number is
    # the label's limitation. Either way the score itself is still reported.
    assert artifact["quality_score_status"] == "scored"
    assert artifact["quality_assessment_status"] == expected


@pytest.mark.parametrize(("benchmark", "expected"), [
    ("unresolved", "dose_benchmark_identity_unresolved"), ("absent", None), ("present", None),
])
def test_only_an_unresolved_benchmark_identity_is_unfinished_work(benchmark, expected):
    breakdown = {"module": "generic", "dimensions": {"dose": {"metadata": {
        "specialized_purpose_assessments": [{"metadata": {"benchmark": benchmark}}]}}}}
    assert unfinished_source_assessment({}, breakdown) == expected


@pytest.mark.parametrize(("amount", "unit", "amount_g"), [
    (1.0, "NP", None),                    # a printed number with no readable unit
    (3.0, "Gram(s) - estimated", None),   # an unusable DSLD unit
    (3.0, "", 3.0),                       # blank: FDA declares sugars in grams
    (3.0, "Gram(s)", 3.0),
])
def test_sugar_owner_keeps_the_level_but_no_amount_it_could_not_read(amount, unit, amount_g):
    from enrich_supplements_v3 import SupplementEnricherV3

    sugar = SupplementEnricherV3()._analyze_sugar_content({}, {"sugars": {"amount": amount, "unit": unit}})
    assert sugar["amount_g"] == amount_g
    assert sugar["level"] == "low" and sugar["contains_sugar"] is True
    unfinished = unfinished_source_assessment({"dietary_sensitivity_data": {"sugar": sugar}}, {})
    assert unfinished == (None if amount_g is not None else "sugar_amount_unread")


def test_export_never_prints_a_sugar_amount_it_does_not_have():
    from build_final_db import build_top_warnings

    enriched = {"dietary_sensitivity_data": {"sugar": {
        "level": "high", "level_display": "High Sugar", "amount_g": None, "contains_sugar": True,
    }}}
    details = [str(w.get("detail") or w.get("title") or "") for w in build_top_warnings(enriched)]
    assert any("High Sugar" in d for d in details)
    assert not any("None" in d for d in details)


# --- one neutral for an unbenchmarked amount --------------------------------

def test_an_unbenchmarked_generic_amount_is_the_shared_neutral():
    from scoring_v4.modules.generic import score_generic
    from test_v4_generic_dose_p132a import _product

    breakdown = score_generic(_product(adequacy_results=[])).to_breakdown()
    assert _assemble("generic", breakdown)["quality_pillars_v4"]["dose"]["score"] == 11.4


def test_an_offlist_sports_primary_is_the_shared_neutral():
    from scoring_v4.modules.sports import score_sports
    from test_v4_sports_dose_preworkout_actives import _product, _row

    breakdown = score_sports(_product(
        _row("l_carnitine", 1, "Gram(s)"), _row("branched_chain_amino_acids", 250, "mg"),
        name="Carnitine 1000 + BCAA", primary_type="amino_acid",
    )).to_breakdown()
    assert breakdown["dimensions"]["dose"]["metadata"]["dose_basis"] == "generic_dose_proxy_for_offlist_primary"
    assert _assemble("sports", breakdown)["quality_pillars_v4"]["dose"]["score"] == 11.4


# --- hiding information never raises a total --------------------------------

@pytest.mark.parametrize("case_id", ["generic_botanical_branded__ideal", "generic_single_molecule__ideal",
                                     "sports_single__ideal", "probiotic__ideal"])
def test_hiding_every_printed_amount_never_raises_the_total(case_id):
    product = _fixture(case_id)
    base = build_scored_artifact(copy.deepcopy(product))
    for row in product["ingredient_quality_data"]["ingredients_scorable"]:
        row.pop("quantity", None)
        row.pop("unit", None)
    hidden = build_scored_artifact(product)
    assert (hidden["quality_score_v4_100"] or 0.0) <= base["quality_score_v4_100"]


# --- a measured low dose is not described as an unbenchmarked one -----------

def test_a_measured_below_benchmark_strain_dose_says_so():
    copy_text = _probiotic_dose_reason({"metadata": {
        "cfu_adequacy_basis": "no_cfu_adequacy_credit", "per_strain_cfu_disclosed_count": 1,
        "cfu_adequacy_contributions": [{"tier": "low", "points": 0.0}],
    }}, "fallback")
    assert copy_text == ("Disclosed per-strain amounts are below the dose benchmarks for the strains "
                         "that have one, so they earn no dose credit.")


def test_enricher_dietary_warning_never_prints_a_sugar_amount_it_does_not_have():
    from enrich_supplements_v3 import SupplementEnricherV3

    warnings = SupplementEnricherV3()._generate_dietary_warnings(
        {"exceeds_diabetic_threshold": True, "level": "moderate", "amount_g": None},
        {"exceeds_aha_threshold": False},
        {"has_high_glycemic": False, "has_sugar_alcohols": False},
    )
    sugar = [w for w in warnings if w["type"] == "diabetes"]
    # The diabetic warning still fires (under-warning is worse), without a number.
    assert len(sugar) == 1
    assert "None" not in sugar[0]["message"]
