"""A9: `safety_assessment_status` says whether the catalog safety checks finished.

The field states whether the safety checks finished, separate from Evidence and
overall quality. It is not a display rule: a product with an incomplete assessment
or a caution shows no all-clear (Sean, 2026-11-03). Anything unknown fails closed.
"""
import json
import logging
from pathlib import Path

import pytest

from assessment_readiness import safety_assessment_status, upper_limit_amounts_unknown
from core_export_model import APP_CORE_COLUMNS, PRODUCTS_CORE_COLUMNS

FIXTURES = Path(__file__).parent / "fixtures"
FINISHED = {
    "quality_score_status": "scored",
    "product_safety_status": "no_known_catalog_concern",
    "safety_gate": {"ingredient_assessment_complete": True, "ingredient_assessment_errors": []},
    "dose_safety": {"state_counts": {"material_but_unresolved": 0}},
    "release": {"is_complete": True, "blockers": [], "unread_printed_nutrient_amounts": 0, "upper_limit_amounts_unknown": 0},
    "evidence_result_state": "evaluated_applicable",
}


def _status(**changes):
    return safety_assessment_status(**{**FINISHED, **changes})


def _open(*blockers):
    return {"is_complete": False, "blockers": list(blockers), "unread_printed_nutrient_amounts": 0, "upper_limit_amounts_unknown": 0}


def test_finished_checks_are_complete():
    assert _status() == "complete"


def test_the_dose_owner_omits_a_state_it_did_not_count():
    assert _status(dose_safety={"state_counts": {"confirmed_over_threshold": 1}}) == "complete"


@pytest.mark.parametrize("blocker", [
    "evidence_assessment_incomplete",
    "probiotic_evidence_assessment_incomplete",
    "probiotic_contributing_evidence_receipts_missing",
    "probiotic_contributing_context_incomplete:p299v_ibs_rome3_22912552",
    "contributing_evidence_receipts_missing",
    "contributing_source_review_incomplete:some_record",
    "clinical_applicability_unreviewed:some_record",
    "hidden_amount_quality_open",
])
def test_an_evidence_only_gap_leaves_the_safety_checks_complete(blocker):
    assert _status(release=_open(blocker)) == "complete"


def test_an_open_omega_evidence_review_is_an_identity_gap():
    # The omega owner holds Evidence only when EPA/DHA material identity is
    # unresolved (omega_evidence._evidence_result_state), never for a pending review.
    assert _status(release=_open("omega_evidence_assessment_incomplete")) == "incomplete"


def test_an_unresolved_identity_behind_an_evidence_blocker_is_incomplete():
    assert _status(release=_open("evidence_assessment_incomplete"),
                   evidence_result_state="identity_material_unresolved") == "incomplete"


def test_a_product_with_no_evidence_result_is_not_held_for_one():
    # A safety-suppressed product never reached Evidence.
    assert _status(evidence_result_state=None) == "complete"


@pytest.mark.parametrize("blocker", [
    "identity_assessment_incomplete",
    "dose_assessment_incomplete",
    "dose_benchmark_identity_unresolved",
    "dose_amount_unread",
    "hidden_amount_safety_open",
    "verification_assessment_incomplete",
    "route_assessment_incomplete",
    "identity_migration_inference",
    "a_blocker_added_next_year",
])
def test_any_other_blocker_is_incomplete(blocker):
    assert _status(release=_open("evidence_assessment_incomplete", blocker)) == "incomplete"


@pytest.mark.parametrize("changes", [
    {"quality_score_status": "not_scored"},
    {"quality_score_status": None},
    {"quality_score_status": "something_new"},
    {"product_safety_status": "not_assessed"},
    {"product_safety_status": None},
    {"product_safety_status": "something_new"},
    {"safety_gate": {}},
    {"safety_gate": None},
    {"safety_gate": {"ingredient_assessment_complete": False, "ingredient_assessment_errors": []}},
    {"safety_gate": {"ingredient_assessment_complete": True,
                     "ingredient_assessment_errors": ["capture_unavailable:inactiveIngredients"]}},
    {"safety_gate": {"ingredient_assessment_complete": True, "ingredient_assessment_errors": [],
                     "needs_review": True}},
    {"dose_safety": None},
    {"dose_safety": {}},
    {"dose_safety": {"state_counts": {"material_but_unresolved": 1}}},
    {"dose_safety": {"state_counts": {"material_but_unresolved": None}}},
    {"dose_safety": {"state_counts": None}},
    {"release": None},
    {"release": {}},
    {"release": {"is_complete": False}},
    {"release": {"is_complete": False, "blockers": "evidence_assessment_incomplete"}},
    {"release": {"is_complete": False, "blockers": [None]}},
    {"release": {"is_complete": True, "blockers": []}},
    {"release": {"is_complete": True, "blockers": [], "unread_printed_nutrient_amounts": 2, "upper_limit_amounts_unknown": 0}},
    {"release": {"is_complete": True, "blockers": [], "unread_printed_nutrient_amounts": None, "upper_limit_amounts_unknown": 0}},
    {"release": {"is_complete": True, "blockers": [], "unread_printed_nutrient_amounts": 0, "upper_limit_amounts_unknown": 1}},
    {"release": {"is_complete": True, "blockers": [], "unread_printed_nutrient_amounts": 0, "upper_limit_amounts_unknown": None}},
    {"release": {"is_complete": True, "blockers": [], "unread_printed_nutrient_amounts": 0}},
])
def test_anything_unknown_or_unfinished_fails_closed(changes):
    assert _status(**changes) == "incomplete"


@pytest.fixture(scope="module")
def pipeline():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3

    logging.disable(logging.INFO)
    return EnhancedDSLDNormalizer(), SupplementEnricherV3()


def _enrich(pipeline, label, mutate=None):
    raw = json.loads((FIXTURES / label).read_text())
    if mutate:
        mutate(raw)
    normalizer, enricher = pipeline
    enriched, _ = enricher.enrich_product(normalizer.normalize_product(raw))
    return enriched


def _score(pipeline, label, mutate=None):
    from scoring_v4.scored_artifact import build_scored_artifact

    return build_scored_artifact(_enrich(pipeline, label, mutate))


def test_a_real_label_missing_only_evidence_review_is_complete(pipeline):
    scored = _score(pipeline, "a9_completion_12147_raw.json")
    assert scored["quality_assessment_status"] == "partial"
    assert scored["assessment_readiness"]["release_assessment"]["blockers"] == [
        "evidence_assessment_incomplete"]
    assert scored["safety_assessment_status"] == "complete"


def test_a_finished_real_label_is_complete(pipeline):
    scored = _score(pipeline, "form_association_12012_raw.json")
    assert scored["quality_assessment_status"] == "complete"
    assert scored["safety_assessment_status"] == "complete"


def test_an_unread_panel_is_incomplete(pipeline):
    from scoring_v4.scored_artifact import build_scored_artifact

    enriched = _enrich(pipeline, "form_association_12012_raw.json")
    enriched.pop("inactiveIngredients")
    scored = build_scored_artifact(enriched)
    assert scored["quality_score_status"] == "scored"
    assert scored["safety_assessment_status"] == "incomplete"


def test_a_failed_resolver_is_incomplete(pipeline, monkeypatch):
    from scoring_v4 import gate_safety

    def unavailable():
        raise RuntimeError("resolver data unavailable")

    monkeypatch.setattr(gate_safety, "_inactive_resolver", unavailable)
    scored = _score(pipeline, "form_association_12012_raw.json")
    assert scored["product_safety_status"] == "not_assessed"
    assert scored["safety_assessment_status"] == "incomplete"


def test_a_label_below_the_coverage_floor_is_incomplete(pipeline):
    def only_an_unknown_row(raw):
        row = {key: value for key, value in raw["ingredientRows"][0].items() if key != "forms"}
        raw["ingredientRows"] = [{**row, "name": "Zzyzx Proprietary Thing",
                                  "ingredientGroup": "Zzyzx Proprietary Thing",
                                  "quantity": [{"quantity": 0, "unit": "NP", "operator": "=",
                                                "servingSizeQuantity": 1, "servingSizeUnit": ""}]}]

    scored = _score(pipeline, "form_association_12012_raw.json", only_an_unknown_row)
    assert scored["score_unavailable_reason"] == "blocked_by_completeness_gate"
    assert scored["safety_assessment_status"] == "incomplete"


def test_a_fish_oil_with_unprinted_epa_dha_is_incomplete(pipeline):
    scored = _score(pipeline, "a9_omega_identity_gap_252496_raw.json")
    assert scored["assessment_readiness"]["release_assessment"]["blockers"] == [
        "omega_evidence_assessment_incomplete"]
    assert scored["product_safety_status"] == "no_known_catalog_concern"
    assert scored["safety_assessment_status"] == "incomplete"


def test_an_unresolved_evidence_identity_is_incomplete(pipeline):
    scored = _score(pipeline, "a9_evidence_identity_gap_307560_raw.json")
    metadata = scored["_v4_module_breakdown"]["dimensions"]["evidence"]["metadata"]
    assert metadata["evidence_result_state"] == "identity_material_unresolved"
    assert scored["assessment_readiness"]["identity"]["readiness"] == "complete"
    assert scored["safety_assessment_status"] == "incomplete"


def test_an_unread_nutrient_on_a_sports_label_is_incomplete_without_holding_its_tier(pipeline):
    scored = _score(pipeline, "a9_sports_unread_nutrient_16730_raw.json")
    assert scored["_v4_module"] == "sports"
    release = scored["assessment_readiness"]["release_assessment"]
    assert release["unread_printed_nutrient_amounts"] > 0
    assert release["unfinished_source_assessment"] is None
    assert scored["safety_assessment_status"] == "incomplete"


@pytest.mark.parametrize("label, unknown, score", [
    ("a9_upper_limit_293959_raw.json", 1, 61.5),  # Vitamin E, nothing printed.
])
def test_an_upper_limit_nutrient_with_no_amount_withholds_only_the_all_clear(pipeline, label, unknown, score):
    """An unknown amount is never a zero (Sean, November 4). Quality and the outcome stand."""
    scored = _score(pipeline, label)
    assert scored["assessment_readiness"]["release_assessment"]["upper_limit_amounts_unknown"] == unknown
    assert scored["safety_assessment_status"] == "incomplete"
    assert scored["product_safety_status"] == "no_known_catalog_concern"
    assert scored["quality_assessment_status"] == "complete"
    assert scored["quality_score_v4_100"] == score


@pytest.mark.parametrize("label, status, reason", [
    ("a9_upper_limit_293959_raw.json", "incomplete", "upper_limit_amount_undisclosed"),
    ("a9_upper_limit_16725_raw.json", "complete", None),  # Its %DV bounds rule out an excess.
    ("a9_upper_limit_277314_raw.json", "complete", None),  # Vitamin D <2% for children and adults in one column.
    ("a9_upper_limit_243679_raw.json", "incomplete", None),  # Niacin's bound crosses, and it prints a percent.
    ("a9_upper_limit_297685_raw.json", "complete", None),  # Gamma-carotene is outside the preformed limit.
    ("a9_upper_limit_12634_raw.json", "complete", None),
    ("a9_upper_limit_294543_raw.json", "complete", None),
])
def test_the_reason_is_named_only_where_the_label_discloses_nothing(pipeline, label, status, reason):
    scored = _score(pipeline, label)
    assert scored["safety_assessment_status"] == status
    assert scored["safety_assessment_reason"] == reason


@pytest.mark.parametrize("label", [
    "a9_upper_limit_294543_raw.json",  # Vitamin D 0 mcg.
    "a9_upper_limit_12634_raw.json",   # Vitamins A and C, calcium and iron, "0 NP" printed as 0% DV.
])
def test_a_printed_zero_is_an_amount_the_upper_limit_check_can_read(pipeline, label):
    """A measured zero leaves nothing unknown, however DSLD records it."""
    scored = _score(pipeline, label)
    assert scored["assessment_readiness"]["release_assessment"]["upper_limit_amounts_unknown"] == 0
    assert scored["safety_assessment_status"] == "complete"


def test_a_ban_stays_blocked_with_no_score(pipeline):
    scored = _score(pipeline, "designer_steroid_33360_raw.json")
    assert scored["product_safety_status"] == "blocked"
    assert scored["quality_score_v4_100"] is None
    assert scored["safety_assessment_status"] == "complete"


# --- Export -----------------------------------------------------------------

def _dv_row(canonical="iron", percent=100.0, group="adult_4_plus", **extra):
    return {"canonical_id": canonical, "name": canonical, "quantity": 0.0, "unit": "NP", "dailyValue": percent,
            "daily_value_target_group": group, "cleaner_row_role": "daily_value_no_amount", **extra}


def _unknown(rows, servings=1):
    return upper_limit_amounts_unknown({"activeIngredients": rows, "serving_basis": {"max_servings_per_day": servings}})


@pytest.mark.parametrize("rows, servings, unknown", [
    ([_dv_row(percent=249.0)], 1, 0),  # Iron: 18 mg x 249% = 44.82, under 45.
    ([_dv_row(percent=250.0)], 1, 1),  # At the limit stays held.
    ([_dv_row(percent=125.0)], 2, 1),  # The day counts, not the serving.
    ([_dv_row(percent=125.0), _dv_row(percent=125.0)], 1, 2),  # Rows of one nutrient add up.
    ([_dv_row(percent=10.0)], None, 1),  # Servings unknown: no day to bound.
    ([_dv_row(percent=10.0, group=None)], 1, 1),  # No target group recorded.
    ([_dv_row(percent=10.0, group="pregnant_lactating")], 1, 1),  # Only the adult DVs are held.
    ([_dv_row(percent=10.0), _dv_row(percent=None, cleaner_row_role=None)], 1, 2),  # One row prints nothing.
    ([_dv_row("boron", percent=10.0)], 1, 1),  # No DV exists to bound it.
    ([_dv_row("vitamin_a", percent=199.0)], 1, 0),  # 1,500 mcg RAE, the pre-2016 DV: 2,985, under 3,000.
    ([_dv_row("vitamin_a", percent=200.0)], 1, 1),
    ([_dv_row("calcium", percent=153.0)], 1, 0),  # 1,300 mg x 153% = 1,989: under the lowest adult limit, 2,000.
    ([_dv_row("calcium", percent=154.0)], 1, 1),  # Over 2,000, though under the highest limit, 3,000.
    ([_dv_row(percent=20.0, quantityVariants=[
        {"daily_value": 300.0, "daily_value_target_group": "adult_4_plus"}])], 1, 1),  # The larger serving's percent.
])
def test_a_printed_percent_rules_out_an_excess_only_while_the_bound_is_below_the_limit(rows, servings, unknown):
    assert _unknown(rows, servings) == unknown


@pytest.mark.parametrize("name, unknown", [
    ("Gamma-Carotene", 0),
    ("Beta Carotene", 0),
    ("Retinyl Palmitate and Beta-Carotene", 1),  # Some of it is preformed.
    ("Vitamin A", 1),
])
def test_only_a_row_that_is_itself_a_carotene_leaves_the_preformed_limit(name, unknown):
    assert _unknown([{"canonical_id": "vitamin_a", "name": name, "quantity": 0.0, "unit": "NP", "dailyValue": None}]) == unknown


@pytest.mark.parametrize("variant", [
    {"adult_daily_value": 300.0},
    {"daily_value": 300.0, "daily_value_target_group": "adult_4_plus"},
    {},
])
def test_upper_limit_reason_counts_percent_on_another_label_column(variant):
    from assessment_readiness import upper_limit_amounts_undisclosed, upper_limit_amounts_unknown

    row = _dv_row(percent=None, quantityVariants=[variant])
    product = {"activeIngredients": [row], "serving_basis": {"max_servings_per_day": 1}}
    assert upper_limit_amounts_unknown(product) == 1
    assert upper_limit_amounts_undisclosed(product) == (0 if variant else 1)


def test_the_percent_bound_reaches_no_amount_score_or_warning(pipeline):
    """16725 prints Iron 30% DV. The all-clear returns; the row stays dose-less."""
    scored = _score(pipeline, "a9_upper_limit_16725_raw.json")
    assert scored["assessment_readiness"]["release_assessment"]["upper_limit_amounts_unknown"] == 0
    assert scored["product_safety_status"] == "no_known_catalog_concern"
    assert scored["quality_score_v4_100"] == 60.3
    enriched = _enrich(pipeline, "a9_upper_limit_16725_raw.json")
    iron = next(row for row in enriched["activeIngredients"] if row["canonical_id"] == "iron")
    assert (iron["quantity"], iron["unit"], iron["dailyValue"]) == (0.0, "NP", 30.0)
    assert iron["daily_value_target_group"] == "adult_4_plus"
    assert not [item for item in enriched["rda_ul_data"]["adequacy_results"] if item.get("nutrient") == "Iron"]


def test_every_bound_is_the_higher_daily_value_in_the_limit_unit():
    from scoring_reference_resolver import rda_ul_reference_entry, upper_limit_bound_dv

    data = json.loads((Path(__file__).resolve().parents[1] / "data" / "daily_values.json").read_text())
    bounds = data["upper_limit_bound_dvs"]
    assert len(bounds) == 18
    for canonical, record in bounds.items():
        assert record["bound"] == max(record["current_dv"], record["pre_2016_dv"]), canonical
        assert record["unit"] == rda_ul_reference_entry(canonical_id=canonical)["unit"], canonical
        assert upper_limit_bound_dv(canonical) == record


def test_the_column_is_declared_for_the_app():
    assert "safety_assessment_status" in PRODUCTS_CORE_COLUMNS
    assert "safety_assessment_status" in APP_CORE_COLUMNS
    assert "safety_assessment_reason" in APP_CORE_COLUMNS


@pytest.mark.parametrize("value, expected", [
    ("upper_limit_amount_undisclosed", "upper_limit_amount_undisclosed"),
    (None, None),
    ("", None),
    ("something_else", None),
])
def test_the_reason_column_carries_only_a_declared_value(value, expected):
    from build_final_db import _safety_assessment_reason_value

    assert _safety_assessment_reason_value({"safety_assessment_reason": value}) == expected


@pytest.mark.parametrize("value, expected", [
    ("complete", "complete"),
    ("incomplete", "incomplete"),
    (None, None),
    ("", None),
    ("finished", None),
])
def test_the_column_carries_only_a_declared_value(value, expected):
    from build_final_db import _safety_assessment_status_value

    assert _safety_assessment_status_value({"safety_assessment_status": value}) == expected
