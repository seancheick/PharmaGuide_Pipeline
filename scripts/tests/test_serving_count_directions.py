"""Directions that count servings set the daily frequency directly.

"Consume one serving daily" (Re-Built Mass XP 244288) already states servings
per day; the dosage-unit parser divided such counts by the serving size or
missed them, leaving the frequency defaulted.
"""
import pytest

from enrich_supplements_v3 import SupplementEnricherV3
from serving_frequency import resolve_daily_serving_range


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3()


@pytest.mark.parametrize("directions,expected", [
    ("Mix three scoops with 16 fl. oz. of cold water. Consume one serving daily.", (1.0, 1.0)),
    ("Mix two heaping scoops (360 g) with water. Consume 1-2 servings per day.", (1.0, 2.0)),
])
def test_directions_stated_in_servings_set_the_daily_frequency(enricher, directions, expected):
    product = {
        "servingSizes": [{"minQuantity": 255.0, "maxQuantity": 255.0, "unit": "Gram(s)",
                          "minDailyServings": 1, "maxDailyServings": 1,
                          "dailyServingsSource": "default"}],
        "statements": [{"type": "Suggested/Recommended/Usage/Directions", "notes": directions}],
    }
    basis = enricher._collect_serving_basis_data(product)["serving_basis"]
    assert (basis["min_servings_per_day"], basis["max_servings_per_day"]) == expected
    assert basis["servings_per_day_source"] == "directions"
    assert resolve_daily_serving_range({**product, "serving_basis": basis}) == (*expected, False)


def test_serving_ceiling_is_not_a_directed_frequency(enricher):
    basis = enricher._collect_serving_basis_data({
        "servingSizes": [{"minQuantity": 30.0, "maxQuantity": 30.0, "unit": "Gram(s)",
                          "dailyServingsSource": "default"}],
        "statements": [{"type": "Suggested/Recommended/Usage/Directions",
                        "notes": "Mix one scoop with water. Do not exceed 3 servings daily."}],
    })["serving_basis"]
    assert basis["servings_per_day_source"] == "default"


def test_age_group_regimens_are_not_merged_into_one_range(enricher):
    # 206377: one serving for ages 4-8 and two for 9-12. A merged 1-2 range
    # would apply two servings to a 4-8 year old (a false pediatric UL alert).
    basis = enricher._collect_serving_basis_data({
        "servingSizes": [{"minQuantity": 2.0, "maxQuantity": 2.0, "unit": "Chewable Tablet(s)",
                          "dailyServingsSource": "default"}],
        "statements": [{"type": "Suggested/Recommended/Usage/Directions",
                        "notes": "For children 4-8 years of age, take one serving daily; for "
                                 "children 9-12 years of age, take two servings daily."}],
    })["serving_basis"]
    assert basis["max_servings_per_day"] != 2.0
