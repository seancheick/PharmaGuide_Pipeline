"""The interaction evaluator consumes the canonical serving-frequency policy.

`_collect_interaction_profile` used to re-read `serving_basis` itself
(max -> min -> 1.0) rather than resolving the daily range the same way the v4
scorers do. That was the last remaining second brain: it agreed with the
canonical policy only because the writer happened to be correct, which is the
exact coupling that let the 2026-08-06 reciprocal defect reach per-day dose
thresholds.

per_day is the default basis when a rule omits it, and every dose threshold in
ingredient_interaction_rules.json is per_day, so this multiplier scales the
amount that decides whether a clinical warning is shown or suppressed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from enrich_supplements_v3 import SupplementEnricherV3  # noqa: E402
from serving_frequency import resolve_daily_serving_multiplier  # noqa: E402

DATA_DIR = SCRIPTS_DIR / "data"

# 1 / 22.727 g per serving — the exact shape the enricher shipped before the fix.
CORRUPT_MULTIPLIER = 0.044


def _enricher() -> SupplementEnricherV3:
    enricher = SupplementEnricherV3.__new__(SupplementEnricherV3)
    enricher.databases = {
        "ingredient_interaction_rules": json.loads(
            (DATA_DIR / "ingredient_interaction_rules.json").read_text()
        ),
        "clinical_risk_taxonomy": json.loads(
            (DATA_DIR / "clinical_risk_taxonomy.json").read_text()
        ),
    }
    return enricher


def _creatine_record(**serving: Any) -> Dict[str, Any]:
    row = {
        "name": "Creatine Monohydrate",
        "standard_name": "Creatine Monohydrate",
        "canonical_id": "creatine_monohydrate",
        "quantity": 5000.0,
        "unit": "mg",
        "mapped": True,
        "scoreable_identity": True,
        "cleaner_row_role": "active_scorable",
        "category": "amino_acids",
    }
    return {
        "dsld_id": "TEST-CREATINE",
        "ingredient_quality_data": {
            "ingredients": [row],
            "ingredients_scorable": [row],
            "ingredients_skipped": [],
            "total_active": 1,
            "unmapped_count": 0,
        },
        **serving,
    }


def _per_day_amounts(profile: Dict[str, Any]) -> list[float]:
    """Every computed per_day amount the evaluator recorded."""
    amounts = []
    for alert in profile.get("ingredient_alerts") or []:
        for hit in alert.get("condition_hits") or []:
            evaluation = hit.get("dose_threshold_evaluation") or {}
            for threshold in evaluation.get("thresholds_checked") or []:
                if threshold.get("basis") != "per_day":
                    continue
                amount = threshold.get("computed_amount")
                if isinstance(amount, (int, float)):
                    amounts.append(float(amount))
    return amounts


def test_interaction_dose_ignores_a_deflated_serving_basis() -> None:
    """The label declares one serving a day; the stored value is that divided.

    Under the old enricher-local read this scaled 5,000 mg of creatine down to
    220 mg/day, dropping it below the 10 g kidney threshold.
    """
    record = _creatine_record(
        servingSizes=[{"minQuantity": 22.0, "minDailyServings": 1, "maxDailyServings": 1}],
        serving_basis={
            "min_servings_per_day": CORRUPT_MULTIPLIER,
            "max_servings_per_day": CORRUPT_MULTIPLIER,
            "basis_reason": "net_contents_servings_per_container",
            "servings_per_day_source": "servingSizes",
            "parsed_from_directions": True,
        },
    )

    amounts = _per_day_amounts(_enricher()._collect_interaction_profile(record))

    assert amounts, "expected at least one evaluated per_day threshold"
    for amount in amounts:
        assert amount == pytest.approx(5.0)  # 5,000 mg x 1 serving, in grams


def test_interaction_dose_ignores_an_inflated_serving_basis() -> None:
    """The infant-D3 shape, applied to a dose-gated rule: 33.3 = 1/0.03 mL."""
    record = _creatine_record(
        servingSizes=[{"minQuantity": 0.03, "minDailyServings": 1, "maxDailyServings": 1}],
        serving_basis={
            "min_servings_per_day": 33.3,
            "max_servings_per_day": 33.3,
            "basis_reason": "net_contents_servings_per_container",
            "servings_per_day_source": "servingSizes",
        },
    )

    amounts = _per_day_amounts(_enricher()._collect_interaction_profile(record))

    assert amounts, "expected at least one evaluated per_day threshold"
    for amount in amounts:
        assert amount == pytest.approx(5.0)


def test_interaction_dose_scales_by_a_real_multi_serving_label() -> None:
    """A genuine 3-servings-a-day label must still triple the daily exposure."""
    record = _creatine_record(
        servingSizes=[{"minQuantity": 5.0, "minDailyServings": 3, "maxDailyServings": 3}]
    )

    amounts = _per_day_amounts(_enricher()._collect_interaction_profile(record))

    assert amounts, "expected at least one evaluated per_day threshold"
    for amount in amounts:
        assert amount == pytest.approx(15.0)


def test_dosing_instruction_uses_the_adult_row_not_serving_sizes_zero() -> None:
    """The user-facing dose instruction was the last servingSizes[0] reader.

    DSLD 317115's shape: a 5 mL child row at 1-3/day and a 10 mL adult row at
    1-4/day. `generate_dosing_summary` derived its cadence from element zero
    whenever serving_basis was absent, printing "three times daily" for a label
    directing up to four.
    """
    from build_final_db import generate_dosing_summary

    record = {
        "form_factor_canonical": "liquid",
        "servingSizes": [
            {"minQuantity": 5.0, "maxQuantity": 5.0, "unit": "mL",
             "minDailyServings": 1, "maxDailyServings": 3},
            {"minQuantity": 10.0, "maxQuantity": 10.0, "unit": "mL",
             "minDailyServings": 1, "maxDailyServings": 4},
        ],
    }

    assert "four times daily" in generate_dosing_summary(record)["dosing_summary"]


def test_rda_adequacy_resolves_the_same_range_as_the_thresholds() -> None:
    """%RDA and UL proximity are per-day, so they share the policy too."""
    from serving_frequency import resolve_daily_serving_range

    record = _creatine_record(
        servingSizes=[{"minQuantity": 10.0, "minDailyServings": 1, "maxDailyServings": 4}],
        serving_basis={
            "min_servings_per_day": CORRUPT_MULTIPLIER,
            "max_servings_per_day": CORRUPT_MULTIPLIER,
            "servings_per_day_source": "servingSizes",
        },
    )

    assert resolve_daily_serving_range(record)[:2] == (1.0, 4.0)


def test_interaction_and_scoring_resolve_the_same_multiplier() -> None:
    """One policy: the enricher and the v4 helper cannot disagree by construction."""
    from scoring_v4.modules.generic_helpers import daily_serving_multiplier

    records = [
        _creatine_record(
            servingSizes=[{"minQuantity": 10.0, "minDailyServings": 1, "maxDailyServings": 4}],
            serving_basis={"min_servings_per_day": 1, "max_servings_per_day": 4},
        ),
        _creatine_record(
            serving_basis={
                "min_servings_per_day": 0.5,
                "max_servings_per_day": 0.5,
                "servings_per_day_source": "directions",
            }
        ),
        _creatine_record(
            serving_basis={
                "min_servings_per_day": CORRUPT_MULTIPLIER,
                "max_servings_per_day": CORRUPT_MULTIPLIER,
                "servings_per_day_source": "servingSizes",
            }
        ),
        _creatine_record(),
    ]

    for record in records:
        assert daily_serving_multiplier(record) == pytest.approx(
            resolve_daily_serving_multiplier(record)
        )
