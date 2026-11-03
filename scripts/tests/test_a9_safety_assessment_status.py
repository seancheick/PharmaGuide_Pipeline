"""A9: `safety_assessment_status` says whether the catalog safety checks finished.

Sean, 2026-11-03: a product whose only gap is the Evidence review may say "no known
concerns" once its safety checks are complete. The field states that fact and is
separate from Evidence and overall quality. Anything unknown fails closed.
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
    "release": {"is_complete": True, "blockers": []},
}


def _status(**changes):
    return safety_assessment_status(**{**FINISHED, **changes})


def test_finished_checks_are_complete():
    assert _status() == "complete"


def test_the_dose_owner_omits_a_state_it_did_not_count():
    assert _status(dose_safety={"state_counts": {"confirmed_over_threshold": 1}}) == "complete"


@pytest.mark.parametrize("blocker", [
    "evidence_assessment_incomplete",
    "probiotic_evidence_assessment_incomplete",
    "omega_evidence_assessment_incomplete",
    "probiotic_contributing_evidence_receipts_missing",
    "probiotic_contributing_context_incomplete:p299v_ibs_rome3_22912552",
    "contributing_evidence_receipts_missing",
    "contributing_source_review_incomplete:some_record",
    "clinical_applicability_unreviewed:some_record",
])
def test_an_evidence_only_gap_leaves_the_safety_checks_complete(blocker):
    assert _status(release={"is_complete": False, "blockers": [blocker]}) == "complete"


@pytest.mark.parametrize("blocker", [
    "identity_assessment_incomplete",
    "dose_assessment_incomplete",
    "dose_benchmark_identity_unresolved",
    "dose_amount_unread",
    "verification_assessment_incomplete",
    "route_assessment_incomplete",
    "identity_migration_inference",
    "a_blocker_added_next_year",
])
def test_any_other_blocker_is_incomplete(blocker):
    release = {"is_complete": False, "blockers": ["evidence_assessment_incomplete", blocker]}
    assert _status(release=release) == "incomplete"


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
    scored = _score(pipeline, "a9_partial_full_evidence_328830_raw.json")
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
