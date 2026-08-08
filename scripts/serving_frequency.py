"""Canonical daily-serving-frequency policy.

How many servings a day a label directs. One implementation, consumed by both
pipeline stages:

  enrich_supplements_v3._collect_interaction_profile  (per-day dose thresholds)
  scoring_v4.modules.generic_helpers.daily_serving_range  (v4 dimension scorers)
  build_final_db.generate_dosing_summary  (consumer cadence copy)
  audits/v4_reviewer_benchmark/build_review_doc.py  (reviewer dose facts)

This is a leaf: it imports nothing from either stage, so enrichment does not
depend on scoring and the dependency arrow stays pointed the way the pipeline
runs. Do not re-derive daily servings anywhere else — call this.

Why it exists. A 2026-08-06 enricher defect divided the label's daily serving
count by the physical serving size, which are different axes: a 22.7 g serving
taken once a day became "0.044 servings per day". The same division inflated
records whose serving is under one unit — a 0.03 mL infant vitamin D3 serving
became 33.3 servings a day. The writer is fixed, but five consumers had each
re-interpreted these fields slightly differently, so a single bad value reached
scoring and clinical dose thresholds through five separate readings. Collapsing
them removes the drift surface, not just the defect.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Optional, Tuple

__all__ = [
    "format_daily_frequency",
    "resolve_daily_serving_range",
    "resolve_daily_serving_multiplier",
]

# Provenance values the enricher writes into serving_basis.servings_per_day_source.
SOURCE_DIRECTIONS = "directions"


def _positive_float(value: Any) -> Optional[float]:
    """Coerce to a positive float, rejecting bools (which are ints in Python)."""
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number > 0 else None


def _ordered_pair(low: Any, high: Any) -> Optional[Tuple[float, float]]:
    """Coerce a (min, max) pair to positive floats, tolerating either being absent.

    Ordering matters: DSLD 60324 and 259262 declare minDailyServings=3 with
    maxDailyServings=1 — a "1 to 3 times daily" label mapped backwards. Reading
    the max field literally would under-count the regimen.
    """
    lo = _positive_float(low)
    hi = _positive_float(high)
    if lo is None and hi is None:
        return None
    if lo is None:
        lo = hi
    if hi is None:
        hi = lo
    return (hi, lo) if lo > hi else (lo, hi)


def _label_declared_daily_range(record: Dict[str, Any]) -> Optional[Tuple[float, float]]:
    """The canonical serving row's declared daily-serving range.

    Products can declare several serving rows (e.g. a 5 mL child serving and a
    10 mL adult serving). This mirrors the enricher's `_select_canonical_serving`
    by taking the row with the highest serving quantity — the adult default —
    rather than `servingSizes[0]`, which is the child row on such products.
    """
    serving_sizes = record.get("servingSizes")
    if not isinstance(serving_sizes, list):
        return None

    best: Optional[Tuple[float, float]] = None
    best_quantity = -1.0
    for entry in serving_sizes:
        if not isinstance(entry, dict):
            continue
        pair = _ordered_pair(
            entry.get("minDailyServings") or entry.get("min_daily_servings"),
            entry.get("maxDailyServings") or entry.get("max_daily_servings"),
        )
        if pair is None:
            continue
        quantity = 0.0
        for key in ("quantity", "servingSizeQuantity", "maxQuantity", "minQuantity"):
            number = _positive_float(entry.get(key))
            if number is not None:
                quantity = number
                break
        if best is None or quantity > best_quantity:
            best, best_quantity = pair, quantity
    return best


def resolve_daily_serving_range(record: Dict[str, Any]) -> Tuple[float, float, bool]:
    """Return (min_servings_per_day, max_servings_per_day, was_defaulted).

    The label's own declaration wins. `serving_basis` is only consulted when the
    label declares no daily servings, because the values stored there are
    derived and were the ones the reciprocal defect corrupted. They are wrong
    even when they land somewhere believable: DSLD 183945 declares 2 servings a
    day and stored 1.0.

    When the label is silent, `serving_basis` is guarded. A below-one value is
    believed only when `servings_per_day_source` is "directions" — the one place
    a genuine every-other-day or weekly regimen originates. `parsed_from_directions`
    is NOT that signal: the enricher sets it whenever it parsed the directions
    text at all, so 346 of the corrupted records carried it.

    Falls back to one serving a day, which neither inflates nor crushes a dose.
    """
    label = _label_declared_daily_range(record)
    if label is not None:
        return label[0], label[1], False

    pair = _ordered_pair(
        record.get("servings_per_day_min"), record.get("servings_per_day_max")
    )
    if pair is not None:
        return pair[0], pair[1], False

    # serving_basis on enriched records; serving_info on shipped detail blobs.
    for container_key in ("serving_basis", "serving_info"):
        container = record.get(container_key)
        if not isinstance(container, dict) or not container:
            continue
        pair = _ordered_pair(
            container.get("min_servings_per_day"),
            container.get("max_servings_per_day"),
        )
        if pair is None:
            continue
        source = str(container.get("servings_per_day_source") or "").strip().lower()
        if pair[1] < 1.0 and source != SOURCE_DIRECTIONS:
            continue
        return pair[0], pair[1], False

    return 1.0, 1.0, True


def resolve_daily_serving_multiplier(record: Dict[str, Any]) -> float:
    """Servings per day to scale a per-serving amount by.

    The top of `resolve_daily_serving_range` — the maximum directed daily use,
    which is what both the dose thresholds and the evidence minima compare
    against.
    """
    return resolve_daily_serving_range(record)[1]


def format_daily_frequency(servings_per_day: Any) -> str:
    """Render a resolved daily frequency without flattening fractional regimens."""
    count = _positive_float(servings_per_day)
    if count is None:
        return "daily"
    if math.isclose(count, 1.0):
        return "daily"
    if count < 1.0:
        interval = 1.0 / count
        rounded_interval = round(interval)
        if math.isclose(interval, rounded_interval, rel_tol=1e-6, abs_tol=1e-6):
            if rounded_interval == 2:
                return "every other day"
            if rounded_interval == 7:
                return "weekly"
            return f"every {rounded_interval} days"
        return "on the labeled schedule"
    if math.isclose(count, 2.0):
        return "twice daily"
    if math.isclose(count, 3.0):
        return "three times daily"
    if math.isclose(count, 4.0):
        return "four times daily"
    formatted = f"{count:g}"
    return f"{formatted} times daily"
