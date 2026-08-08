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
ENRICHED_DIRS = sorted(
    (Path(__file__).parent.parent / "products").glob("output_*_enriched/enriched/*.json")
)


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


VALID_FREQUENCY_SOURCES = {"default", "servingSizes", "directions"}


def _label_daily_range(record: dict) -> tuple[float, float] | None:
    """The canonical (highest-quantity) serving row's declared daily range."""
    best = None
    best_quantity = -1.0
    for entry in record.get("servingSizes") or []:
        if not isinstance(entry, dict):
            continue
        values = [
            float(v)
            for v in (entry.get("minDailyServings"), entry.get("maxDailyServings"))
            if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0
        ]
        if not values:
            continue
        quantity = 0.0
        for key in ("quantity", "servingSizeQuantity", "maxQuantity", "minQuantity"):
            value = entry.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
                quantity = float(value)
                break
        if best is None or quantity > best_quantity:
            best, best_quantity = (min(values), max(values)), quantity
    return best


def serving_frequency_violations(record: dict) -> list[str]:
    """Provenance and consistency invariants for a record's daily frequency.

    Replaces an earlier `min_servings_per_day >= 0.14` floor, which was the
    wrong invariant twice over: it could not see the inflation half of the
    reciprocal bug (a 0.03 mL serving yielded 33.3/day), and it would have
    condemned a genuine once-a-week label. These check provenance instead, so
    they catch both directions at any magnitude while leaving real fractional
    regimens alone.
    """
    basis = record.get("serving_basis") or {}
    values = {
        key: basis.get(key)
        for key in ("min_servings_per_day", "max_servings_per_day")
        if isinstance(basis.get(key), (int, float))
        and not isinstance(basis.get(key), bool)
    }
    if not values:
        return []

    source = basis.get("servings_per_day_source")
    label = _label_daily_range(record)
    violations = []

    if source not in VALID_FREQUENCY_SOURCES:
        violations.append(f"unrecognized provenance {source!r}")

    # The reciprocal defect lives entirely in this branch: a physical serving
    # size must never become a daily frequency. Detect it by provenance rather
    # than by magnitude — that is what sees 0.044 and 33.3 with one rule.
    if basis.get("basis_reason") == "net_contents_servings_per_container" and label:
        declared = {label[0], label[1]}
        stored = set(values.values())
        if not stored <= declared:
            violations.append(
                f"container-derived basis reports {sorted(stored)} servings/day "
                f"but the label declares {sorted(declared)}"
            )

    if label:
        for key, value in values.items():
            if value > label[1] + 1e-9:
                violations.append(f"{key}={value} exceeds label maximum {label[1]}")

    # Fractional regimens are legitimate, but only from the label's own
    # directions — never as a by-product of serving-unit arithmetic.
    for key, value in values.items():
        if value < 1.0 and source != "directions":
            violations.append(f"{key}={value} below one serving/day from source {source!r}")

    return violations


@pytest.mark.parametrize(
    "record,expected",
    [
        pytest.param(
            {
                "servingSizes": [{"minQuantity": 22.0, "minDailyServings": 1, "maxDailyServings": 1}],
                "serving_basis": {
                    "min_servings_per_day": 0.044, "max_servings_per_day": 0.044,
                    "basis_reason": "net_contents_servings_per_container",
                    "servings_per_day_source": "servingSizes",
                },
            },
            True,
            id="deflation-330331-22g",
        ),
        pytest.param(
            {
                "servingSizes": [{"minQuantity": 0.03, "minDailyServings": 1, "maxDailyServings": 1}],
                "serving_basis": {
                    "min_servings_per_day": 33.3, "max_servings_per_day": 33.3,
                    "basis_reason": "net_contents_servings_per_container",
                    "servings_per_day_source": "servingSizes",
                },
            },
            True,
            id="inflation-205006-infant-d3",
        ),
        pytest.param(
            {
                "servingSizes": [{"minQuantity": 1.0, "minDailyServings": 1, "maxDailyServings": 4}],
                "serving_basis": {
                    "min_servings_per_day": 0.5, "max_servings_per_day": 2.0,
                    "basis_reason": "net_contents_servings_per_container",
                    "servings_per_day_source": "servingSizes",
                },
            },
            True,
            id="deflation-312859-plausible-looking-half",
        ),
        pytest.param(
            {
                "serving_basis": {
                    "min_servings_per_day": 0.5, "max_servings_per_day": 0.5,
                    "basis_reason": "default",
                    "servings_per_day_source": "directions",
                },
            },
            False,
            id="legitimate-every-other-day-from-directions",
        ),
        pytest.param(
            {
                "serving_basis": {
                    "min_servings_per_day": 0.1, "max_servings_per_day": 0.1,
                    "basis_reason": "default",
                    "servings_per_day_source": "directions",
                },
            },
            False,
            id="legitimate-weekly-vitamin-d-the-old-floor-would-have-failed",
        ),
        pytest.param(
            {
                "servingSizes": [{"minQuantity": 10.0, "minDailyServings": 1, "maxDailyServings": 4}],
                "serving_basis": {
                    "min_servings_per_day": 1, "max_servings_per_day": 4,
                    "basis_reason": "net_contents_servings_per_container",
                    "servings_per_day_source": "servingSizes",
                },
            },
            False,
            id="corrected-317115-adult-range",
        ),
    ],
)
def test_frequency_invariants_catch_both_directions(record: dict, expected: bool) -> None:
    assert bool(serving_frequency_violations(record)) is expected


@pytest.mark.skipif(not ENRICHED_DIRS, reason="no enriched output present")
def test_no_enriched_record_derives_frequency_from_serving_size() -> None:
    """Corpus invariant over the stage that actually owns provenance.

    The detail blob keeps only basis_count/basis_unit/min/max, so it cannot be
    audited for provenance — this runs where `basis_reason` and
    `servings_per_day_source` still exist.
    """
    offenders = []
    scanned = 0
    for batch in ENRICHED_DIRS:
        try:
            payload = json.loads(batch.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        records = payload if isinstance(payload, list) else payload.get("products") or []
        if isinstance(records, dict):
            records = list(records.values())
        for record in records:
            if not isinstance(record, dict):
                continue
            scanned += 1
            problems = serving_frequency_violations(record)
            if problems:
                offenders.append((record.get("dsld_id"), problems[0]))

    assert scanned, "no enriched records scanned — the guard would pass vacuously"
    assert not offenders, (
        f"{len(offenders)} of {scanned} enriched records violate the serving-frequency "
        f"invariants; first 5: {offenders[:5]}"
    )
