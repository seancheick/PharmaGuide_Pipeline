"""Dose V4.1 §4: every Dose receipt shows daily use, what was assessed and how
it combines, adequacy before safety, the upper reference with its population,
exposure and cap, and a final Dose that reconciles exactly."""
import sys

import pytest

from test_dose_final_safety_ceiling import product as ceiling_product
from scoring_v4.scored_artifact import build_scored_artifact


def _suite():
    import audit_v4_archetype_fixtures as fixtures
    return fixtures.load_fixture_suite().cases


@pytest.mark.parametrize("case", _suite(), ids=lambda case: case.case_id)
def test_every_archetype_dose_receipt_reconciles(case):
    pillars = build_scored_artifact(case.product).get("quality_pillars_v4")
    if not pillars:
        pytest.skip("not scored")
    dose = pillars["dose"]
    receipt = dose["explanation"]["dose_receipt"]
    assert receipt["reconciles"] is True
    assert receipt["final"] == dose["score"]
    assert receipt["aggregation"] is not None, case.case_id
    assert any(fact["id"] == "dose_arithmetic" for fact in dose["explanation"]["facts"])
    if receipt["upper_reference"]:
        assert dose["score"] <= receipt["upper_reference"]["cap_public"]


def test_the_worked_example_reads_like_the_plan():
    # 120 mg magnesium, 1-4 servings (Pure 205309 shape): adequacy 20, cap 10.
    product = ceiling_product(137.14, pct_rda=30.0, low=1, high=4)
    row = product["rda_ul_data"]["adequacy_results"][0]
    row.update(per_day_min=120.0, per_day_max=480.0)
    product["product_name"] = "Magnesium Glycinate"
    dose = build_scored_artifact(product)["quality_pillars_v4"]["dose"]
    receipt = dose["explanation"]["dose_receipt"]
    assert receipt["daily_use"] == {"minimum_servings": 1.0, "maximum_servings": 4.0, "defaulted": False}
    [item] = receipt["contributions"]
    assert item["reference_kind"] == "pharmaguide_policy" and item["reference_value"] == 84.0
    assert item["pct_of_reference"] == pytest.approx(142.86, abs=0.01)
    assert (item["amount_at_minimum"], item["amount_at_maximum"]) == (120.0, 480.0)
    upper = receipt["upper_reference"]
    assert upper["ul"] == 350.0 and upper["ul_population"] == "general adult" and upper["cap_public"] == 10.0
    assert receipt["adequacy_before_safety"] == 20.0 and receipt["final"] == 10.0
    facts = {fact["id"]: fact["value_display"] for fact in dose["explanation"]["facts"]}
    assert facts["dose_arithmetic"] == "Adequacy 20/20, capped at 10: Dose 10/20."
    assert "(general adult limit)" in facts["dose_upper_reference"]
    assert "PharmaGuide scoring policy" in facts["dose_upper_reference"]
