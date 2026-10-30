"""Directed daily use and a printed daily ceiling are different label facts.

Sean, 2026-10-29: recommended/optional use and a printed maximum ceiling are
modelled separately in the one serving owner (`serving_frequency`). The
directed range (`minDailyServings`/`maxDailyServings`) is what the label tells
a user to take; `ceilingDailyServings` is the "not to exceed" number. The
ceiling is conservative exposure: it feeds interaction dose thresholds and
the UL screen, with its source named. It is never a direction: the dosing
summary never tells a user to take it, and the Dose optional-use deduction is
judged at the highest directed use, not at the ceiling. A label without a
ceiling behaves exactly as before.

Motivating label: submission S18, CON-CRĒT Creatine HCl, "Take 1-2 servings
per day for general health. Take 2-3 servings per day for intense exercise,
not to exceed 5 servings per day". Stored as 1/5 it exported "Take 1 capsule
5 times daily".
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from build_final_db import generate_dosing_summary  # noqa: E402
from scoring_v4.dose_safety import CONFIRMED_OVER_THRESHOLD, evaluate_dose_safety  # noqa: E402
from serving_frequency import (  # noqa: E402
    resolve_daily_serving_ceiling,
    resolve_daily_serving_multiplier,
    resolve_daily_serving_range,
)


def _serving(low, high, ceiling=None, **extra):
    row = {"order": 1, "minQuantity": 1, "maxQuantity": 1, "unit": "Capsule(s)",
           "minDailyServings": low, "maxDailyServings": high, "dailyServingsSource": "label"}
    if ceiling is not None:
        row["ceilingDailyServings"] = ceiling
    row.update(extra)
    return row


def _product(low, high, ceiling=None, **extra):
    return {"form_factor": "capsule", "servingSizes": [_serving(low, high, ceiling)],
            "serving_basis": {"basis_count": 1, "basis_unit": "capsule"}, **extra}


# ── the owner ───────────────────────────────────────────────────────────────


def test_ceiling_is_exposure_not_directed_use():
    product = _product(1, 3, 5)
    assert resolve_daily_serving_range(product) == (1.0, 3.0, False)
    assert resolve_daily_serving_ceiling(product) == 5.0
    # Interaction dose thresholds compare against conservative exposure.
    assert resolve_daily_serving_multiplier(product) == 5.0


def test_no_ceiling_control_is_unchanged():
    product = _product(1, 3)
    assert resolve_daily_serving_ceiling(product) is None
    assert resolve_daily_serving_multiplier(product) == 3.0


def test_ceiling_below_directed_maximum_never_lowers_exposure():
    product = _product(1, 3, 2)
    assert resolve_daily_serving_ceiling(product) is None
    assert resolve_daily_serving_multiplier(product) == 3.0


def test_ceiling_alone_still_screens_exposure_without_inventing_directions():
    product = {"servingSizes": [{"minQuantity": 1, "maxQuantity": 1, "unit": "Capsule(s)",
                                 "ceilingDailyServings": 4}]}
    assert resolve_daily_serving_range(product) == (1.0, 1.0, True)
    assert resolve_daily_serving_multiplier(product) == 4.0


# ── consumer display ────────────────────────────────────────────────────────


def test_s18_dosing_summary_never_instructs_the_ceiling():
    summary = generate_dosing_summary(_product(1, 3, 5))["dosing_summary"]
    assert summary == "Take 1 capsule 1-3 times daily"
    assert "5" not in summary


def test_directed_range_displays_the_range_not_only_the_top():
    assert generate_dosing_summary(_product(1, 3))["dosing_summary"] == "Take 1 capsule 1-3 times daily"
    assert generate_dosing_summary(_product(1, 2))["dosing_summary"] == "Take 1 capsule 1-2 times daily"


@pytest.mark.parametrize("low,high,expected", [
    (1, 1, "Take 1 capsule daily"),
    (2, 2, "Take 1 capsule twice daily"),
    (3, 3, "Take 1 capsule three times daily"),
])
def test_fixed_frequency_controls_are_unchanged(low, high, expected):
    assert generate_dosing_summary(_product(low, high))["dosing_summary"] == expected


# ── Dose optional-use deduction vs safety disclosure ────────────────────────


def _flagged(low, high, ceiling, pct_ul_at_exposure):
    product = _product(low, high, ceiling)
    product["rda_ul_data"] = {"safety_flags": [{"nutrient": "Zinc", "canonical_id": "zinc",
                                                "pct_ul": pct_ul_at_exposure, "ul_gate_eligible": True}]}
    return evaluate_dose_safety(product)


def test_exceedance_only_at_the_ceiling_is_disclosed_not_deducted():
    # 10 mg zinc: 75% of the UL at 3 directed servings, 125% at the ceiling of 5.
    result = _flagged(1, 3, 5, 125.0)
    assert [flag.state for flag in result.flags] == [CONFIRMED_OVER_THRESHOLD]
    assert result.dose_ceiling() is None


def test_optional_use_deduction_is_judged_at_directed_maximum():
    # 20 mg zinc: 50% at 1 serving, 150% at 3, 250% at the ceiling of 5.
    ceiling = _flagged(1, 3, 5, 250.0).dose_ceiling()
    assert ceiling["cap_public"] is None and ceiling["deduction_public"] == 2.0
    assert ceiling["pct_ul"] == pytest.approx(150.0)
    assert ceiling["pct_ul_at_minimum"] == pytest.approx(50.0)
    assert ceiling["pct_ul_at_label_ceiling"] == pytest.approx(250.0)


def test_minimum_use_exceedance_keeps_the_hard_cap_with_a_ceiling():
    # One directed serving already exceeds: 200% at 1/1, 400% at the ceiling of 2.
    ceiling = _flagged(1, 1, 2, 400.0).dose_ceiling()
    assert ceiling["cap_public"] == 0.0
    assert ceiling["pct_ul"] == pytest.approx(200.0)
    assert ceiling["minimum_exceeds"] is True


def test_no_ceiling_dose_ceiling_is_unchanged():
    ceiling = _flagged(1, 4, None, 137.0).dose_ceiling()
    assert ceiling["deduction_public"] == 2.0 and ceiling["pct_ul"] == 137.0
    assert ceiling["pct_ul_at_minimum"] == 34.25
    assert "pct_ul_at_label_ceiling" not in ceiling


# ── UL screen at the ceiling names its source ───────────────────────────────


@pytest.fixture(scope="module")
def enricher():
    from enrich_supplements_v3 import SupplementEnricherV3
    return SupplementEnricherV3()


def _zinc_product(mg, low, high, ceiling):
    return {
        "activeIngredients": [{"name": "Zinc", "standardName": "Zinc", "canonical_id": "zinc",
                               "canonical_source_db": "ingredient_quality_map",
                               "quantity": mg, "unit": "mg"}],
        "inactiveIngredients": [],
        "servingSizes": [_serving(low, high, ceiling)],
    }


def test_ul_screen_at_the_ceiling_says_it_is_the_label_maximum(enricher):
    product = _zinc_product(10, 1, 3, 5)
    result = enricher._collect_rda_ul_data(
        product, min_servings_per_day=1, max_servings_per_day=resolve_daily_serving_multiplier(product))
    flags = [flag for flag in result["safety_flags"] if flag.get("canonical_id") == "zinc"
             or "zinc" in str(flag.get("nutrient") or "").lower()]
    assert len(flags) == 1 and flags[0]["pct_ul"] == pytest.approx(125.0)
    assert "label's stated maximum of 5 servings a day" in flags[0]["warning"]
    assert "directed" not in flags[0]["warning"]


def test_ul_screen_without_a_ceiling_keeps_directed_wording(enricher):
    product = _zinc_product(20, 1, 3, None)
    result = enricher._collect_rda_ul_data(product, min_servings_per_day=1, max_servings_per_day=3)
    flags = [flag for flag in result["safety_flags"] if flag.get("canonical_id") == "zinc"
             or "zinc" in str(flag.get("nutrient") or "").lower()]
    assert len(flags) == 1 and flags[0]["warning"].startswith("At maximum directed daily use")


# ── label entry paths carry the field ──────────────────────────────────────


def test_submission_import_accepts_a_ceiling_and_rejects_one_below_directions():
    from product_submission_import import SubmissionImportError, _validate_serving_size
    def entry(ceiling):
        row = _serving(1, 3, ceiling)
        row.pop("dailyServingsSource")  # cleaner-stamped, never submitted
        return row

    _validate_serving_size(entry(5), "servingSizes[0]")
    with pytest.raises(SubmissionImportError, match="ceilingDailyServings"):
        _validate_serving_size(entry(2), "servingSizes[0]")


def test_cleaner_preserves_the_ceiling():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    normalizer = EnhancedDSLDNormalizer.__new__(EnhancedDSLDNormalizer)
    [row] = normalizer._process_serving_sizes([{"minQuantity": 1, "maxQuantity": 1, "unit": "Capsule(s)",
                                                "minDailyServings": 1, "maxDailyServings": 3,
                                                "ceilingDailyServings": 5}])
    assert row["ceilingDailyServings"] == 5 and row["maxDailyServings"] == 3
    [plain] = normalizer._process_serving_sizes([{"minQuantity": 1, "maxQuantity": 1, "unit": "Capsule(s)",
                                                  "minDailyServings": 1, "maxDailyServings": 3}])
    assert "ceilingDailyServings" not in plain


def test_review_console_keeps_the_ceiling():
    from submission_review.serve import _MANUAL_LABEL_SERVING_FIELDS
    assert "ceilingDailyServings" in _MANUAL_LABEL_SERVING_FIELDS


def test_no_ceiling_flag_values_stay_bit_identical():
    # 180.7 * 3 / 3 != 180.7 in floating point; a ceiling-free label must not drift.
    result = _flagged(1, 3, None, 180.7)
    assert result.flags[0].pct_ul_at_directed_maximum == 180.7
    assert result.dose_ceiling()["pct_ul"] == 180.7


def test_ceiling_is_rebased_with_a_facts_panel_basis():
    # Serving row: 2 tablets, 1-2 times daily, not to exceed 3; every Facts
    # amount is for 4 tablets, so directed use is 0.5-1 Facts servings a day.
    variant = {"serving_size_quantity": 4, "serving_size_unit": "Tablet(s)"}
    product = {
        "servingSizes": [{"order": 1, "minQuantity": 2, "maxQuantity": 2, "unit": "Tablet(s)",
                          "minDailyServings": 1, "maxDailyServings": 2, "ceilingDailyServings": 3,
                          "dailyServingsSource": "label"}],
        "activeIngredients": [{"name": "Zinc", "raw_taxonomy": {"quantityVariants": [variant]}}],
    }
    assert resolve_daily_serving_range(product) == (0.5, 1.0, False)
    assert resolve_daily_serving_ceiling(product) == pytest.approx(1.5)


def test_ul_wording_names_the_printed_ceiling_after_a_facts_panel_rebase(enricher):
    # 2 tablets, 1-2 times daily, not to exceed 3; Facts amounts are per 4
    # tablets, so exposure is 1.5 Facts servings. The label printed 3.
    variant = {"serving_size_quantity": 4, "serving_size_unit": "Tablet(s)"}
    product = {
        "activeIngredients": [{"name": "Zinc", "standardName": "Zinc", "canonical_id": "zinc",
                               "canonical_source_db": "ingredient_quality_map",
                               "quantity": 40, "unit": "mg",
                               "raw_taxonomy": {"quantityVariants": [variant]}}],
        "inactiveIngredients": [],
        "servingSizes": [{"order": 1, "minQuantity": 2, "maxQuantity": 2, "unit": "Tablet(s)",
                          "minDailyServings": 1, "maxDailyServings": 2, "ceilingDailyServings": 3,
                          "dailyServingsSource": "label"}],
    }
    result = enricher._collect_rda_ul_data(
        product, min_servings_per_day=0.5, max_servings_per_day=resolve_daily_serving_multiplier(product))
    flags = [flag for flag in result["safety_flags"] if flag.get("canonical_id") == "zinc"
             or "zinc" in str(flag.get("nutrient") or "").lower()]
    assert len(flags) == 1 and flags[0]["pct_ul"] == pytest.approx(150.0)
    assert "label's stated maximum of 3 servings a day" in flags[0]["warning"]
    assert "1.5 servings" not in flags[0]["warning"]


def test_ceiling_alone_keeps_the_defaulted_minimum_marked_estimated(enricher):
    # No directions, only "not to exceed 4": the one-serving minimum is a
    # default, so the RDA output must not present it as label-declared.
    product = _zinc_product(20, None, None, 4)
    product["servingSizes"][0].pop("dailyServingsSource")
    enriched, _ = enricher.enrich_product({"id": "ceiling_only", "fullName": "Zinc", **product})
    rows = [row for row in enriched["rda_ul_data"]["adequacy_results"]
            if "zinc" in str(row.get("nutrient") or "").lower()]
    assert rows and all(row["is_servings_estimated"] is True for row in rows)
    assert enriched["rda_ul_data"]["safety_flags"][0]["pct_ul"] == pytest.approx(200.0)
