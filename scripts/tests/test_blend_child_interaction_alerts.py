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


def test_top_level_np_vitamin_row_reads_as_a_panel_zero(enricher):
    # "Vitamin A 0 NP" printed as 0% DV outside a blend is a nutrition-panel
    # zero (Q23: the cleaner keeps dailyValue 0.0).
    row = _top("Vitamin A", "vitamin_a", 0.0, "NP")
    row["dailyValue"] = 0.0
    profile = enricher._collect_interaction_profile(_product([], [row]))
    assert not [a for a in profile["ingredient_alerts"]
                if (a.get("subject_ref") or {}).get("canonical_id") == "vitamin_a"]


def _hit(profile, rule_id, key, target):
    for alert in _hits(profile, rule_id):
        for hit in alert["condition_hits"] + alert["drug_class_hits"]:
            if hit.get(key) == target:
                return hit
    return None


def test_presence_rule_with_a_dose_tier_still_flags_when_the_amount_is_unknown(enricher):
    """Sean, 2026-09-26: a presence rule always flags; only a dose-dependent rule
    falls back to the missing-amount setting. Licorice in pregnancy is presence
    (avoid, contraindicated from 71 mg); an unquantified child must not hide it."""
    child = _child("Licorice Root Extract", "licorice", "ingredientRows[2].nestedRows[3]")
    profile = enricher._collect_interaction_profile(_product([], [child]))
    pregnancy = _hit(profile, "RULE_IQM_LICORICE_HYPERTENSION", "condition_id", "pregnancy")
    assert pregnancy["severity"] == "avoid"
    decision = pregnancy["dose_decision"]
    assert decision["evaluation_status"] == "amount_unknown"
    assert decision["consumer_disposition"] == "block"
    assert decision["decision_rule"]["amount_missing_disposition"] == "block"
    # Licorice hypertension is presence too since D8 (2026-09-26): 100 mg/day
    # glycyrrhizic acid is no floor for people with hypertension, so an
    # unquantified child still flags it.
    hypertension = _hit(profile, "RULE_IQM_LICORICE_HYPERTENSION", "condition_id", "hypertension")
    assert hypertension["dose_decision"]["consumer_disposition"] != "suppress"
    # A dose-dependent sub-rule keeps the missing-amount default (garlic's
    # 600 mg hypertension floor).
    garlic = _child("Garlic Extract", "garlic", "ingredientRows[2].nestedRows[4]")
    garlic_bp = _hit(enricher._collect_interaction_profile(_product([], [garlic])),
                     "RULE_INGREDIENT_GARLIC", "condition_id", "hypertension")
    assert garlic_bp["dose_decision"]["consumer_disposition"] == "suppress"


def test_authored_missing_amount_policy_still_wins_over_presence(enricher):
    """Beta-carotene's smoker tiers carry Dr. Pham's explicit amount-missing
    'suppress' (policy 2026-09-21): an authored choice is kept."""
    child = _child("Beta-Carotene", "beta_carotene", "ingredientRows[1].nestedRows[0]")
    profile = enricher._collect_interaction_profile(_product([], [child]))
    smoker = _hit(profile, "RULE_IQM_BETA_CAROTENE_LUNG_CANCER", "condition_id", "current_smoker")
    assert smoker is None or smoker["dose_decision"]["consumer_disposition"] == "suppress"


def _top(name, canonical_id, quantity, unit, skip="recognized_non_scorable", role="active_scorable"):
    return {"name": name, "raw_source_text": name, "standard_name": name, "canonical_id": canonical_id,
            "raw_source_path": "ingredientRows[5]", "cleaner_row_role": role, "skip_reason": skip,
            "quantity": quantity, "unit": unit}


def test_top_level_row_that_shows_presence_is_evaluated(enricher):
    """D1c (2026-09-26): a top-level row the scorer skipped still counts when the
    label shows the ingredient: a listing without an amount, or a %DV only."""
    listed = _top("L-Tryptophan", "l_tryptophan", 0.0, "unspecified")
    profile = enricher._collect_interaction_profile(_product([], [listed]))
    assert _hits(profile, "RULE_IQM_L_TRYPTOPHAN")


def test_measured_zero_on_the_nutrition_panel_is_not_presence(enricher):
    zero = _top("Vitamin A", "vitamin_a", 0.0, "mcg")
    profile = enricher._collect_interaction_profile(_product([], [zero]))
    assert not [a for a in profile["ingredient_alerts"] if (a.get("subject_ref") or {}).get("canonical_id") == "vitamin_a"]
