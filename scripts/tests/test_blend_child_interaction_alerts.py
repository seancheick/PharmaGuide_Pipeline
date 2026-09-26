"""Ingredients inside a blend keep their interaction alerts (Sean, D1, 2026-09-26).

A blend child with a resolved IQM identity was dropped from interaction
evaluation because only scorable rows were scanned (05433a3c, 2026-06-24, no
clinical rationale recorded). Being nested in a blend does not make an
identified ingredient safe, so presence rules fire on it. An unknown child
amount never borrows the blend total: dose rules read the child's own row and
follow their authored amount-missing policy.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


@pytest.fixture(scope="module")
def enricher():
    from enrich_supplements_v3 import SupplementEnricherV3

    return SupplementEnricherV3()


def _child(name: str, canonical_id: str, path: str, quantity=None, unit=None) -> dict:
    return {
        "name": name,
        "raw_source_text": name,
        "standard_name": name,
        "canonical_id": canonical_id,
        "raw_source_path": path,
        "cleaner_row_role": "nested_display_only",
        "skip_reason": "nested_under_non_therapeutic_parent",
        "quantity": quantity,
        "unit": unit,
    }


def _product(scorable: list, skipped: list) -> dict:
    return {
        "dsld_id": "TEST_BLEND_CHILD",
        "product_name": "Test blend",
        "ingredient_quality_data": {
            "ingredients_scorable": scorable,
            "ingredients": list(scorable) + list(skipped),
            "ingredients_skipped": list(skipped),
        },
    }


def _hits(profile: dict, rule_id: str) -> list:
    return [a for a in profile["ingredient_alerts"] if a["rule_id"] == rule_id]


def test_blend_child_presence_rule_fires(enricher):
    child = _child("L-Tryptophan", "l_tryptophan", "ingredientRows[2].nestedRows[1]")
    profile = enricher._collect_interaction_profile(_product([], [child]))
    alerts = _hits(profile, "RULE_IQM_L_TRYPTOPHAN")
    assert alerts, "a nested L-tryptophan must keep its MAOI contraindication"
    assert profile["drug_class_summary"]["maois"]["highest_severity"] == "contraindicated"


def test_blend_child_without_amount_never_satisfies_a_dose_rule(enricher):
    child = _child("Garlic", "garlic", "ingredientRows[3].nestedRows[0]")
    profile = enricher._collect_interaction_profile(_product([], [child]))
    [alert] = _hits(profile, "RULE_INGREDIENT_GARLIC")
    conditions = {h["condition_id"]: h for h in alert["condition_hits"]}
    drugs = {h["drug_class_id"]: h for h in alert["drug_class_hits"]}
    # Presence rule: fires on identity alone.
    assert conditions["surgery_scheduled"]["severity"] == "avoid"
    # Dose rule: the amount is unknown, so the authored amount-missing policy
    # decides; no dose is invented from the blend.
    decision = drugs["anticoagulants"]["dose_decision"]
    assert decision["evaluation_status"] == "amount_unknown"
    assert decision["consumer_disposition"] == "suppress"


def test_blend_child_does_not_repeat_a_rule_its_scorable_twin_fired(enricher):
    scored = {
        "name": "Garlic Extract",
        "raw_source_text": "Garlic Extract",
        "standard_name": "Garlic",
        "canonical_id": "garlic",
        "raw_source_path": "ingredientRows[0]",
        "quantity": 500.0,
        "unit": "mg",
    }
    child = _child("Garlic", "garlic", "ingredientRows[3].nestedRows[0]")
    profile = enricher._collect_interaction_profile(_product([scored], [child]))
    alerts = _hits(profile, "RULE_INGREDIENT_GARLIC")
    assert len(alerts) == 1
    assert alerts[0]["ingredient_name"] == "Garlic Extract"


def test_top_level_non_scorable_row_stays_out(enricher):
    # A nutrition-panel row such as "Vitamin A 0%" is not a blend child and
    # does not establish a meaningful amount; D1 covers blend children only.
    row = {
        "name": "L-Tryptophan",
        "raw_source_text": "L-Tryptophan",
        "standard_name": "L-Tryptophan",
        "canonical_id": "l_tryptophan",
        "raw_source_path": "ingredientRows[4]",
        "cleaner_row_role": "daily_value_no_amount",
        "skip_reason": "daily_value_no_amount",
    }
    profile = enricher._collect_interaction_profile(_product([], [row]))
    assert not _hits(profile, "RULE_IQM_L_TRYPTOPHAN")
