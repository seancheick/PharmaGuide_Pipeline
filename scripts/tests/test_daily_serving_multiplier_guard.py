"""The daily-serving multiplier must reject implausible serving-basis values.

`sleep_support`, `immune_support` and `joint_support` each read
`serving_basis.max_servings_per_day` / `min_servings_per_day` and accepted ANY
value > 0, with no `servingSizes[].minDailyServings` precedence and no sanity
floor. A 2026-08-06 unit-confusion bug in `enrich_supplements_v3.py` wrote
reciprocal-of-serving-size values (0.044 = 1/22.7 g) into exactly those keys for
469 enriched records, which would have crushed every daily dose these modules
compute by ~23x.

The writer bug is fixed (see test_serving_basis_daily_servings.py) and no
affected product routed to these three modules, so this pins the *defensive*
contract: the consumer no longer trusts an impossible multiplier.

Contract, matching omega_dose._extract_daily_servings / generic_evidence:
  1. servingSizes[] daily servings (the label) win.
  2. then top-level servings_per_day_max/min.
  3. then serving_basis / serving_info, but only when >= 1.0 — or > 0 when the
     value was parsed from label directions, which is where a genuine
     every-other-day regimen legitimately comes from.
  4. otherwise 1.0.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from scoring_v4.modules.generic_helpers import (  # noqa: E402
    daily_serving_multiplier,
    daily_serving_range,
)
from scoring_v4.modules.generic_evidence import _dose_map  # noqa: E402
from scoring_v4.modules.omega_dose import _extract_daily_servings  # noqa: E402
from serving_frequency import format_daily_frequency  # noqa: E402
from scoring_v4.modules.immune_support import immune_active_doses  # noqa: E402
from scoring_v4.modules.joint_support import joint_active_doses  # noqa: E402
from scoring_v4.modules.sleep_support import (  # noqa: E402
    MELATONIN_CANONICALS,
    active_daily_mg,
)

# 1 / 22.727 g per serving — the exact shape the enricher shipped.
CORRUPT_MULTIPLIER = 0.044


def _row(name: str, canonical_id: str, quantity: float, unit: str) -> Dict[str, Any]:
    return {
        "name": name,
        "standard_name": name,
        "canonical_id": canonical_id,
        "quantity": quantity,
        "unit": unit,
        "bio_score": 12.0,
        "mapped": True,
        "scoreable_identity": True,
        "cleaner_row_role": "active_scorable",
        "category": "vitamin",
    }


def _product(row: Dict[str, Any], **serving: Any) -> Dict[str, Any]:
    return {
        "ingredient_quality_data": {
            "ingredients_scorable": [row],
            "ingredients": [row],
            "total_active": 1,
            "unmapped_count": 0,
        },
        **serving,
    }


CORRUPT_BASIS = {
    "serving_basis": {
        "min_servings_per_day": CORRUPT_MULTIPLIER,
        "max_servings_per_day": CORRUPT_MULTIPLIER,
        "basis_reason": "net_contents_servings_per_container",
        "parsed_from_directions": False,
    }
}


# --- the three consumers, exercised through their real dose functions --------


def test_sleep_dose_ignores_impossible_serving_basis() -> None:
    product = _product(_row("Melatonin", "melatonin", 3.0, "mg"), **CORRUPT_BASIS)

    assert active_daily_mg(product, MELATONIN_CANONICALS) == pytest.approx(3.0)


def test_immune_dose_ignores_impossible_serving_basis() -> None:
    product = _product(_row("Zinc", "zinc", 15.0, "mg"), **CORRUPT_BASIS)

    assert immune_active_doses(product)["zinc_mg"] == pytest.approx(15.0)


def test_joint_dose_ignores_impossible_serving_basis() -> None:
    product = _product(
        _row("Glucosamine Sulfate", "glucosamine", 1500.0, "mg"), **CORRUPT_BASIS
    )

    doses = {d["active"]: d for d in joint_active_doses(product)}
    assert doses["glucosamine"]["daily_mg"] == pytest.approx(1500.0)


def test_generic_evidence_dose_map_ignores_a_label_sourced_fraction() -> None:
    """generic_evidence used `parsed_from_directions` as its escape hatch.

    DSLD 243667's shape: the label declares 1 serving a day, the flag is set
    because directions text parsed, and the stored value is the divided one.
    Evidence minima are daily doses, so a 0.199 multiplier compares a 500 mg
    ingredient as 99 mg against the literature.
    """
    product = _product(
        _row("Vitamin C", "vitamin_c", 500.0, "mg"),
        servingSizes=[{"minDailyServings": 1, "maxDailyServings": 1}],
        serving_basis={
            "min_servings_per_day": 0.19873150105708243,
            "max_servings_per_day": 0.19873150105708243,
            "servings_per_day_source": "servingSizes",
            "parsed_from_directions": True,
            "basis_reason": "net_contents_servings_per_container",
        },
    )

    assert _dose_map(product)["vitamin c"][0] == pytest.approx(500.0)


def test_generic_evidence_dose_map_scales_by_a_real_multi_serving_label() -> None:
    """A genuine 2-servings-a-day label still doubles the daily dose."""
    product = _product(
        _row("Vitamin C", "vitamin_c", 500.0, "mg"),
        servingSizes=[{"minDailyServings": 2, "maxDailyServings": 2}],
    )

    assert _dose_map(product)["vitamin c"][0] == pytest.approx(1000.0)


def test_sleep_dose_still_scales_by_a_real_multi_serving_regimen() -> None:
    """The guard must not flatten legitimate 2-servings-a-day labels."""
    product = _product(
        _row("Melatonin", "melatonin", 3.0, "mg"),
        serving_basis={"min_servings_per_day": 2, "max_servings_per_day": 2},
    )

    assert active_daily_mg(product, MELATONIN_CANONICALS) == pytest.approx(6.0)


# --- the shared helper's precedence contract --------------------------------


def test_label_serving_sizes_outrank_serving_basis() -> None:
    product = {
        "servingSizes": [{"minDailyServings": 2, "maxDailyServings": 2}],
        **CORRUPT_BASIS,
    }

    assert daily_serving_multiplier(product) == pytest.approx(2.0)


def test_top_level_servings_per_day_outranks_serving_basis() -> None:
    product = {"servings_per_day_max": 3, **CORRUPT_BASIS}

    assert daily_serving_multiplier(product) == pytest.approx(3.0)


def test_serving_basis_is_used_when_plausible() -> None:
    product = {"serving_basis": {"max_servings_per_day": 4, "min_servings_per_day": 1}}

    assert daily_serving_multiplier(product) == pytest.approx(4.0)


def test_directions_parsed_fraction_is_trusted() -> None:
    """A real every-other-day regimen only ever arrives via the directions parse."""
    product = {
        "serving_basis": {
            "min_servings_per_day": 0.5,
            "max_servings_per_day": 0.5,
            "servings_per_day_source": "directions",
        }
    }

    assert daily_serving_multiplier(product) == pytest.approx(0.5)


def test_unparsed_fraction_falls_back_to_one_serving() -> None:
    assert daily_serving_multiplier(dict(CORRUPT_BASIS)) == pytest.approx(1.0)


def test_serving_info_is_honoured_for_detail_blobs() -> None:
    """Detail blobs carry serving_info rather than serving_basis."""
    product = {"serving_info": {"max_servings_per_day": 2, "min_servings_per_day": 2}}

    assert daily_serving_multiplier(product) == pytest.approx(2.0)


def test_canonical_adult_serving_wins_over_the_first_serving_entry() -> None:
    """serving_basis already encodes the enricher's adult-serving selection.

    DSLD 317115 (Sambucus syrup) declares a 5 mL child serving at 1-3/day AND a
    10 mL adult serving at 1-4/day. `_select_canonical_serving` picks the adult
    entry, so serving_basis carries max=4. Reading servingSizes[0] instead would
    silently score the product on the child regimen.
    """
    product = {
        "servingSizes": [
            {"minQuantity": 5.0, "unit": "mL", "minDailyServings": 1, "maxDailyServings": 3},
            {"minQuantity": 10.0, "unit": "mL", "minDailyServings": 1, "maxDailyServings": 4},
        ],
        "serving_basis": {
            "min_servings_per_day": 1,
            "max_servings_per_day": 4,
            "basis_count": 10.0,
            "basis_unit": "ml",
            "selection_policy": "adult_primary",
        },
    }

    assert daily_serving_multiplier(product) == pytest.approx(4.0)


def test_serving_basis_above_the_label_ceiling_is_rejected() -> None:
    """The reciprocal bug inflates as well as deflates.

    DSLD 205006 (Pure Infant Vitamin D3, 0.03 mL per serving) shipped
    serving_basis max=33.3 — that is 1/0.03, the same division seen from the
    other side. The label declares one serving a day, so no value above that
    ceiling can be believed.
    """
    product = {
        "servingSizes": [
            {"minQuantity": 0.03, "unit": "mL", "minDailyServings": 1, "maxDailyServings": 1}
        ],
        "serving_basis": {"min_servings_per_day": 33.3, "max_servings_per_day": 33.3},
    }

    assert daily_serving_multiplier(product) == pytest.approx(1.0)


def test_missing_contract_defaults_to_one_serving() -> None:
    assert daily_serving_multiplier({}) == pytest.approx(1.0)


# --- omega shares the same resolver, but needs the min..max range -----------

SAMBUCUS_SHAPED = {
    "servingSizes": [
        {"minQuantity": 5.0, "unit": "mL", "minDailyServings": 1, "maxDailyServings": 3},
        {"minQuantity": 10.0, "unit": "mL", "minDailyServings": 1, "maxDailyServings": 4},
    ],
    "serving_basis": {"min_servings_per_day": 1, "max_servings_per_day": 4},
}


def test_omega_uses_the_canonical_adult_serving_range() -> None:
    """omega read servingSizes[0], which is the child row on this shape."""
    assert _extract_daily_servings(SAMBUCUS_SHAPED) == (1.0, 4.0, False)


def test_omega_ignores_a_deflated_serving_basis() -> None:
    product = {
        "servingSizes": [{"minDailyServings": 1, "maxDailyServings": 1}],
        **CORRUPT_BASIS,
    }

    assert _extract_daily_servings(product) == (1.0, 1.0, False)


def test_omega_rejects_a_serving_basis_above_the_label_ceiling() -> None:
    """The infant-D3 inflation shape: 33.3 = 1/0.03 mL against a 1/day label."""
    product = {
        "servingSizes": [{"minDailyServings": 1, "maxDailyServings": 1}],
        "serving_basis": {"min_servings_per_day": 33.3, "max_servings_per_day": 33.3},
    }

    assert _extract_daily_servings(product) == (1.0, 1.0, False)


def test_parsed_from_directions_does_not_excuse_a_label_sourced_fraction() -> None:
    """DSLD 243667: `parsed_from_directions` is not the provenance of these values.

    The enricher sets that flag whenever it managed to parse the directions text
    at all, independently of where min/max_servings_per_day actually came from.
    Here `servings_per_day_source` is "servingSizes" — the label's own 1/day,
    then divided. Only `servings_per_day_source == "directions"` licenses a
    below-one value.
    """
    product = {
        "servingSizes": [{"minDailyServings": 1, "maxDailyServings": 1}],
        "serving_basis": {
            "min_servings_per_day": 0.19873150105708243,
            "max_servings_per_day": 0.19873150105708243,
            "servings_per_day_source": "servingSizes",
            "parsed_from_directions": True,
            "basis_reason": "net_contents_servings_per_container",
        },
    }

    assert daily_serving_multiplier(product) == pytest.approx(1.0)
    assert _extract_daily_servings(product) == (1.0, 1.0, False)


def test_label_wins_when_serving_basis_is_plausible_but_still_wrong() -> None:
    """DSLD 183945: label says 2/day, serving_basis says 1.0 — 2 divided by 2.

    A corrupted value that happens to land in a believable range is still
    corrupted, so a declared label range is never overridden by serving_basis.
    """
    product = {
        "servingSizes": [{"minDailyServings": 2, "maxDailyServings": 2}],
        "serving_basis": {
            "min_servings_per_day": 1.0,
            "max_servings_per_day": 1.0,
            "servings_per_day_source": "servingSizes",
            "basis_reason": "net_contents_servings_per_container",
        },
    }

    assert daily_serving_multiplier(product) == pytest.approx(2.0)
    assert _extract_daily_servings(product) == (2.0, 2.0, False)


def test_omega_keeps_a_genuine_multi_serving_range() -> None:
    """A 1-3/day label must stay a range — omega scores the midpoint."""
    product = {"servingSizes": [{"minDailyServings": 1, "maxDailyServings": 3}]}

    assert _extract_daily_servings(product) == (1.0, 3.0, False)


def test_inverted_label_range_is_normalised_not_trusted_literally() -> None:
    """DSLD 60324 / 259262 declare minDailyServings=3 with maxDailyServings=1.

    The source data has the two swapped — a "1 to 3 times daily" label mapped
    backwards. Reading the `max` field literally gives 1 and under-counts the
    regimen, so the pair is ordered before use: the range is 1-3 and the
    maximum directed daily use is 3.
    """
    product = {"servingSizes": [{"minDailyServings": 3, "maxDailyServings": 1}]}

    assert daily_serving_range(product) == (1.0, 3.0, False)
    assert daily_serving_multiplier(product) == pytest.approx(3.0)


def test_omega_flags_the_default_when_nothing_is_declared() -> None:
    assert _extract_daily_servings({}) == (1.0, 1.0, True)


def test_range_and_multiplier_agree() -> None:
    """The multiplier is the top of the resolved range — one policy, two shapes."""
    _, range_max, _ = daily_serving_range(SAMBUCUS_SHAPED)

    assert daily_serving_multiplier(SAMBUCUS_SHAPED) == pytest.approx(range_max)


@pytest.mark.parametrize("bad", [True, False, None, [], {}, "many"])
def test_non_numeric_values_never_become_a_multiplier(bad: Any) -> None:
    """Booleans are ints in Python — `True` must not slip through as 1.0."""
    product = {"serving_basis": {"max_servings_per_day": bad, "min_servings_per_day": bad}}

    assert daily_serving_multiplier(product) == pytest.approx(1.0)


@pytest.mark.parametrize(
    "bad",
    [float("nan"), float("inf"), float("-inf"), "nan", "inf", "-inf", "1e10000"],
)
def test_non_finite_values_never_become_a_multiplier(bad: Any) -> None:
    """JSON-adjacent numeric input must never propagate NaN or infinity."""
    product = {
        "serving_basis": {
            "max_servings_per_day": bad,
            "min_servings_per_day": bad,
            "servings_per_day_source": "directions",
        }
    }

    assert daily_serving_multiplier(product) == pytest.approx(1.0)


def test_numeric_strings_are_coerced() -> None:
    """Enriched JSON carries some quantities as strings; they are still counts."""
    product = {"serving_basis": {"max_servings_per_day": "2", "min_servings_per_day": "2"}}

    assert daily_serving_multiplier(product) == pytest.approx(2.0)


@pytest.mark.parametrize(
    ("servings_per_day", "expected"),
    [
        (0.5, "every other day"),
        (1 / 3, "every 3 days"),
        (1 / 7, "weekly"),
        (1.0, "daily"),
        (2.0, "twice daily"),
    ],
)
def test_daily_frequency_copy_preserves_fractional_regimens(
    servings_per_day: float,
    expected: str,
) -> None:
    assert format_daily_frequency(servings_per_day) == expected
