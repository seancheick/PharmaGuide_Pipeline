"""Label-declared daily servings must never be divided by the serving size.

Regression for the 2026-08-06 defect: when `_derive_serving_size_from_container`
produced a larger basis_count than the label's own serving quantity, the writer
re-ran the already-in-servings `minDailyServings` / `maxDailyServings` through
`_serving_units_to_servings()`. That helper divides a *unit count* by
*units per serving*; feeding it a value that is already a servings-per-day count
yields the reciprocal of the serving size — 22.7 g per serving became
"0.044 servings per day".

All 469 affected enriched records carried the same signature:
basis_reason="net_contents_servings_per_container" and
servings_per_day_source="servingSizes".
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from enrich_supplements_v3 import SupplementEnricherV3

DIST_BLOBS = Path(__file__).parent.parent / "dist" / "detail_blobs"

# Floor below which a servings-per-day figure cannot describe a real regimen.
# 1/7 ≈ 0.143 is "once a week"; anything under that is a unit-confusion artifact.
IMPLAUSIBLE_SERVINGS_PER_DAY = 0.14


def _enricher() -> SupplementEnricherV3:
    return SupplementEnricherV3.__new__(SupplementEnricherV3)


# Real source fields, copied verbatim from the enriched corpus.
LABEL_DECLARED_CASES = [
    pytest.param(
        {
            "servingSizes": [
                {
                    "order": 1,
                    "minQuantity": 22.0,
                    "maxQuantity": 22.0,
                    "unit": "Gram(s)",
                    "notes": "about 3 tbsp",
                    "minDailyServings": 1,
                    "maxDailyServings": 1,
                    "normalizedServing": 22.0,
                    "servingQuantitySource": "label",
                    "dailyServingsSource": "label",
                }
            ],
            "netContents": [
                {"order": 1, "quantity": 250, "unit": "Gram(s)", "display": "250 Gram(s)"}
            ],
            "servingsPerContainer": 11,
        },
        1.0,
        1.0,
        id="330331-beef-bone-broth-22g",
    ),
    pytest.param(
        {
            "servingSizes": [
                {
                    "order": 1,
                    "minQuantity": 23.0,
                    "maxQuantity": 23.0,
                    "unit": "Gram(s)",
                    "notes": "1 scoop",
                    "minDailyServings": 1,
                    "maxDailyServings": 1,
                    "normalizedServing": 23.0,
                    "servingQuantitySource": "label",
                    "dailyServingsSource": "label",
                }
            ],
            "netContents": [
                {"order": 1, "quantity": 650, "unit": "Gram(s)", "display": "650 Gram(s)"}
            ],
            "servingsPerContainer": 28,
        },
        1.0,
        1.0,
        id="29098-raw-protein-chocolate-cacao",
    ),
    pytest.param(
        {
            "servingSizes": [
                {
                    "order": 1,
                    "minQuantity": 20.47,
                    "maxQuantity": 20.47,
                    "unit": "Gram(s)",
                    "notes": "2 Scoops",
                    "minDailyServings": 1,
                    "maxDailyServings": 1,
                    "normalizedServing": 20.47,
                    "servingQuantitySource": "label",
                    "dailyServingsSource": "label",
                }
            ],
            "netContents": [
                {"order": 1, "quantity": 614.1, "unit": "Gram(s)", "display": "614.1 Gram(s)"}
            ],
            "servingsPerContainer": 30,
        },
        1.0,
        1.0,
        id="219950-precision-bcaa-peach-tea",
    ),
    pytest.param(
        # Count-unit variant: 180 capsules / 90 servings derives 2 capsules per
        # serving, which is larger than the label's 1-capsule quantity. The label
        # says 1-4 servings per day; the defect shipped 0.5-2.0 — a "plausible"
        # every-other-day figure that is really the same division.
        {
            "servingSizes": [
                {
                    "order": 1,
                    "minQuantity": 1.0,
                    "maxQuantity": 1.0,
                    "unit": "Veg Capsule(s)",
                    "minDailyServings": 1,
                    "maxDailyServings": 4,
                    "normalizedServing": 1.0,
                    "servingQuantitySource": "label",
                    "dailyServingsSource": "label",
                }
            ],
            "netContents": [
                {"order": 1, "quantity": 180, "unit": "Capsule(s)", "display": "180 Capsule(s)"}
            ],
            "servingsPerContainer": 90,
        },
        1.0,
        4.0,
        id="312859-veg-capsule-1-to-4-per-day",
    ),
]


@pytest.mark.parametrize("product,expected_min,expected_max", LABEL_DECLARED_CASES)
def test_label_daily_servings_survive_container_derived_basis(
    product: dict, expected_min: float, expected_max: float
) -> None:
    """minDailyServings/maxDailyServings are already per-day counts, not unit counts."""
    basis = _enricher()._collect_serving_basis_data(product)["serving_basis"]

    assert basis["min_servings_per_day"] == pytest.approx(expected_min)
    assert basis["max_servings_per_day"] == pytest.approx(expected_max)
    assert basis["servings_per_day_source"] == "servingSizes"


def test_container_derived_basis_count_is_still_applied() -> None:
    """The serving-size derivation itself is correct and must not regress."""
    product = LABEL_DECLARED_CASES[0].values[0]

    basis = _enricher()._collect_serving_basis_data(product)["serving_basis"]

    assert basis["basis_count"] == pytest.approx(250 / 11)
    assert basis["basis_reason"] == "net_contents_servings_per_container"
    assert basis["basis_unit"] == "gram"


def test_genuine_fractional_label_regimen_is_preserved() -> None:
    """A label that really says half a serving per day keeps that value.

    The fix removes a bogus division; it must not clamp legitimate
    every-other-day regimens up to 1.0.
    """
    product = {
        "servingSizes": [
            {
                "order": 1,
                "minQuantity": 1.0,
                "maxQuantity": 1.0,
                "unit": "Veg Capsule(s)",
                "minDailyServings": 0.5,
                "maxDailyServings": 0.5,
                "servingQuantitySource": "label",
                "dailyServingsSource": "label",
            }
        ],
        "netContents": [
            {"order": 1, "quantity": 180, "unit": "Capsule(s)", "display": "180 Capsule(s)"}
        ],
        "servingsPerContainer": 90,
    }

    basis = _enricher()._collect_serving_basis_data(product)["serving_basis"]

    assert basis["min_servings_per_day"] == pytest.approx(0.5)
    assert basis["max_servings_per_day"] == pytest.approx(0.5)


def test_directions_parsed_unit_counts_still_convert_to_servings() -> None:
    """The unit->servings conversion is correct for directions-parsed unit counts.

    "Take 2 capsules daily" with a 2-capsule serving is 1 serving per day. This
    path has no label-declared daily servings, so the conversion still applies.
    """
    product = {
        "servingSizes": [
            {
                "order": 1,
                "minQuantity": 2.0,
                "maxQuantity": 2.0,
                "unit": "Capsule(s)",
                "servingQuantitySource": "label",
            }
        ],
        "labelText": {"parsed": {"directions": "Take 2 capsules daily."}},
    }

    basis = _enricher()._collect_serving_basis_data(product)["serving_basis"]

    assert basis["servings_per_day_source"] == "directions"
    assert basis["min_servings_per_day"] == pytest.approx(1.0)


@pytest.mark.skipif(not DIST_BLOBS.is_dir(), reason="detail blobs not built")
def test_no_shipped_blob_reports_implausible_servings_per_day() -> None:
    """Corpus guard: no shipped product may claim a sub-weekly serving regimen.

    RED until the pipeline is re-run (re-enrich -> score -> build); the shipped
    blobs are written from the enriched records this fix corrects.
    """
    offenders = []
    for blob in sorted(DIST_BLOBS.glob("*.json")):
        try:
            serving = json.loads(blob.read_text()).get("serving_info") or {}
        except (json.JSONDecodeError, OSError):
            continue
        value = serving.get("min_servings_per_day")
        if isinstance(value, (int, float)) and 0 < value < IMPLAUSIBLE_SERVINGS_PER_DAY:
            offenders.append((blob.stem, value, serving.get("basis_unit")))

    assert not offenders, (
        f"{len(offenders)} products ship < {IMPLAUSIBLE_SERVINGS_PER_DAY} servings/day; "
        f"first 5: {offenders[:5]}"
    )
