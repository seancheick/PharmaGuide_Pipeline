"""A9: `safety_assessment_status` says whether the catalog safety checks finished.

The field states whether the safety checks finished, separate from Evidence and
overall quality. It is not a display rule: a product with an incomplete assessment
or a caution shows no all-clear (Sean, 2026-11-03). Anything unknown fails closed.
"""
import json
import logging
from pathlib import Path

import pytest

from assessment_readiness import safety_assessment_status
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
    ("a9_upper_limit_16725_raw.json", 2, 60.3),   # Calcium and iron, %DV with no amount the check can read.
])
def test_an_upper_limit_nutrient_with_no_amount_withholds_only_the_all_clear(pipeline, label, unknown, score):
    """An unknown amount is never a zero (Sean, November 4). Quality and the outcome stand."""
    scored = _score(pipeline, label)
    assert scored["assessment_readiness"]["release_assessment"]["upper_limit_amounts_unknown"] == unknown
    assert scored["safety_assessment_status"] == "incomplete"
    assert scored["product_safety_status"] == "no_known_catalog_concern"
    assert scored["quality_assessment_status"] == "complete"
    assert scored["quality_score_v4_100"] == score


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

def test_the_column_is_declared_for_the_app():
    assert "safety_assessment_status" in PRODUCTS_CORE_COLUMNS
    assert "safety_assessment_status" in APP_CORE_COLUMNS


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
