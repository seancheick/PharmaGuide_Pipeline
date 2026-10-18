"""Benefit at the minimum directed daily use, excess at the maximum.

A label that says "1 to 3 servings a day" guarantees the lowest amount to
everyone who follows it; the top is what a user may reach. Sean chose one rule
for every route on 2026-09-28 (scripts/audits/rr_correctness_20260928/
CALIBRATION_PACKET.md item 2): adequacy credit reads the minimum, and every
above-range reduction, high-dose flag and interaction threshold reads the
maximum. RDA adequacy, omega and botanicals already did; sports, fiber, generic
Evidence, immune, joint and sleep credited the maximum.
"""
import pytest

from test_quality_exposure_identity import product, row
from scoring_v4.exposure import row_exposure
from scoring_v4.modules.fiber_digestive_dose import score_dose as fiber_dose
from scoring_v4.modules.sports_dose import score_dose as sports_dose


def ranged(value, low, high):
    value["servingSizes"][0].update(minDailyServings=low, maxDailyServings=high)
    return value


def test_exposure_benchmarks_the_minimum_and_keeps_the_top():
    exposure = row_exposure(ranged(product([row("creatine", 2)]), 1, 3), row("creatine", 2), basis="daily")
    assert (exposure.benchmark_amount, exposure.benchmark_maximum) == (2, 6)


def test_sports_adequacy_reads_the_minimum():
    # 1.5 g, 1-2 servings: everyone gets 1.5 g; only some reach 3 g.
    result = sports_dose(ranged(product([row("creatine_monohydrate", 1.5)]), 1, 2))
    assert result["metadata"]["dose_basis"] == "creatine_contribution_policy"
    assert result["score"] == 10


def test_sports_above_target_plateaus_at_minimum_daily_use():
    # 4 g at minimum daily use meets the contribution target; 12 g keeps plateau.
    result = sports_dose(ranged(product([row("creatine_monohydrate", 4)]), 1, 3))
    assert result["metadata"]["dose_basis"] == "creatine_contribution_policy"
    assert result["score"] == 20


def test_fiber_adequacy_reads_the_minimum():
    assert fiber_dose(ranged(product([row("psyllium", 3)]), 1, 3))["score"] == fiber_dose(
        product([row("psyllium", 3)], 1))["score"]


def test_immune_high_zinc_reads_the_maximum_and_bands_the_minimum():
    from scoring_v4.modules.immune_support import (
        HIGH_ZINC_THRESHOLD_MG,
        immune_active_doses,
        score_immune_support_dose,
    )
    from test_daily_serving_multiplier_guard import _row

    per_serving = HIGH_ZINC_THRESHOLD_MG * 0.6  # in range once, above the threshold twice
    rows = [_row("Zinc", "zinc", per_serving, "mg")]
    value = {
        "primary_type": "immune_support",
        "ingredient_quality_data": {"ingredients_scorable": rows, "ingredients": rows},
        "servingSizes": [{"minDailyServings": 1, "maxDailyServings": 2}],
        "rda_ul_data": {"adequacy_results": [{
            "nutrient": "Zinc", "canonical_id": "zinc", "pct_rda": per_serving / 11 * 100,
            "scoring_eligible": True,
        }]},
    }
    assert immune_active_doses(value)["zinc_mg"] == pytest.approx(per_serving)
    result = score_immune_support_dose(value)
    assert result["metadata"]["high_zinc"] is True
    # The source-owned minimum use already exceeds the nutritional reference;
    # the maximum determines the diagnostic flag, never another adequacy cut.
    assert result["components"]["zinc_daily_range"] == 3.0


def test_sleep_high_dose_band_reads_the_maximum():
    from scoring_v4.modules.sleep_support import score_sleep_support_dose
    from scoring_v4.modules.generic_helpers import unbenchmarked_dose_credit
    from test_daily_serving_multiplier_guard import _row

    rows = [_row("Melatonin", "melatonin", 3.0, "mg")]
    value = {
        "primary_type": "sleep_support",
        "ingredient_quality_data": {"ingredients_scorable": rows, "ingredients": rows},
        "servingSizes": [{"minDailyServings": 1, "maxDailyServings": 3}],
    }
    # The retired sleep window cannot turn 9 mg into an extra Dose penalty.
    # Both exposure endpoints remain available as label facts.
    result = score_sleep_support_dose(value)
    assert result["daily_mg"] == 3.0
    assert result["daily_mg_max"] == 9.0
    assert result["band"] == "no_benchmark_neutral"
    assert result["score"] == unbenchmarked_dose_credit()
