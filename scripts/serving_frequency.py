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
import re
from typing import Any, Dict, Optional, Tuple

__all__ = [
    "format_daily_frequency",
    "resolve_daily_serving_range",
    "resolve_daily_serving_multiplier",
    "select_canonical_serving",
]

# Provenance values the enricher writes into serving_basis.servings_per_day_source.
SOURCE_DIRECTIONS = "directions"

_COUNT_WORDS = {
    "one": 1.0,
    "two": 2.0,
    "three": 3.0,
    "four": 4.0,
}
_DOSAGE_FORM_PATTERN = re.compile(
    r"\b(one|two|three|four|\d+(?:\.\d+)?)\s+"
    r"(tablets?|softgels?|capsules?|caplets?|gummies?|packets?)\b",
    re.IGNORECASE,
)


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


def _canonical_dosage_form(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"\(s\)", "", text)
    text = re.sub(r"[^a-z]", "", text)
    aliases = {"gummie": "gummy"}
    text = aliases.get(text, text)
    return text[:-1] if text.endswith("s") else text


def _facts_panel_daily_range(record: Dict[str, Any]) -> Optional[Tuple[float, float]]:
    """Rebase split intake occasions onto the declared Supplement Facts panel.

    Some DSLD labels describe each intake occasion in ``servingSizes`` while
    the ingredient rows remain expressed for the complete daily Facts panel.
    Example: 2 tablets twice daily, with every quantity explicitly based on
    4 tablets.  Scale only when the ingredient-row basis is unanimous and uses
    the same dosage form; this keeps ordinary multi-serving labels untouched.
    """
    serving = select_canonical_serving(record.get("servingSizes"))
    if not isinstance(serving, dict):
        return None
    serving_quantity = next(
        (
            number
            for key in ("quantity", "servingSizeQuantity", "maxQuantity", "minQuantity")
            if (number := _positive_float(serving.get(key))) is not None
        ),
        None,
    )
    serving_unit = _canonical_dosage_form(serving.get("unit"))
    daily_range = _ordered_pair(
        serving.get("minDailyServings") or serving.get("min_daily_servings"),
        serving.get("maxDailyServings") or serving.get("max_daily_servings"),
    )
    if serving_quantity is None or not serving_unit or daily_range is None:
        return None

    facts_bases: set[float] = set()

    def visit(rows: Any) -> None:
        if not isinstance(rows, list):
            return
        for row in rows:
            if not isinstance(row, dict):
                continue
            raw_taxonomy = row.get("raw_taxonomy")
            variants = (
                raw_taxonomy.get("quantityVariants")
                if isinstance(raw_taxonomy, dict)
                else None
            )
            if isinstance(variants, list):
                for variant in variants:
                    if not isinstance(variant, dict):
                        continue
                    basis = _positive_float(
                        variant.get("serving_size_quantity")
                        or variant.get("servingSizeQuantity")
                    )
                    basis_unit = _canonical_dosage_form(
                        variant.get("serving_size_unit")
                        or variant.get("servingSizeUnit")
                    )
                    if basis is not None and basis_unit == serving_unit:
                        facts_bases.add(basis)
            visit(row.get("nestedIngredients"))

    visit(record.get("activeIngredients"))
    if len(facts_bases) != 1:
        return None
    facts_basis = next(iter(facts_bases))
    if facts_basis <= serving_quantity:
        return None
    # The facts-panel basis cannot exceed every physical unit the label allows
    # in a day. Larger values are known DSLD field defects (for example a
    # 30-count package copied into a one-chew serving row), not dose evidence.
    if facts_basis > serving_quantity * daily_range[1] * 1.05:
        return None

    return (
        serving_quantity * daily_range[0] / facts_basis,
        serving_quantity * daily_range[1] / facts_basis,
    )


def select_canonical_serving(serving_sizes: Any) -> Optional[Dict[str, Any]]:
    """Select the label serving row used as the product's analysis basis.

    DSLD commonly emits child and adult serving rows together. The established
    pipeline policy is to use the row with the largest positive serving
    quantity (the adult/default column), falling back to the first row when no
    quantity is usable. Keep that policy here so cleaning and enrichment select
    the same Supplement Facts column.
    """
    if not isinstance(serving_sizes, list) or not serving_sizes:
        return None

    selected: Optional[Dict[str, Any]] = None
    selected_quantity = -1.0
    first_row: Optional[Dict[str, Any]] = None
    for row in serving_sizes:
        if not isinstance(row, dict):
            continue
        if first_row is None:
            first_row = row
        quantity = next(
            (
                number
                for key in (
                    "quantity",
                    "servingSizeQuantity",
                    "maxQuantity",
                    "minQuantity",
                    "normalizedServing",
                )
                if (number := _positive_float(row.get(key))) is not None
            ),
            None,
        )
        if quantity is not None and quantity > selected_quantity:
            selected = row
            selected_quantity = quantity
    return selected or first_row


def _composite_pack_daily_range(record: Dict[str, Any]) -> Optional[Tuple[float, float]]:
    """Resolve each form independently in a heterogeneous daily combo pack.

    DSLD can encode ``one tablet and one softgel daily`` as maxDailyServings=2
    on the tablet Supplement Facts row. That value counts two physical items,
    not two servings of every tablet nutrient. Only override the declared range
    when directions explicitly name at least two distinct dosage forms and the
    current serving row matches one of them.
    """
    serving_sizes = record.get("servingSizes")
    statements = record.get("statements")
    if not isinstance(serving_sizes, list) or not isinstance(statements, list):
        return None

    direction_texts = []
    for statement in statements:
        if not isinstance(statement, dict):
            continue
        statement_type = str(statement.get("type") or "").lower()
        text = str(statement.get("notes") or statement.get("text") or "").strip()
        if text and ("direction" in statement_type or "suggest" in statement_type):
            direction_texts.append(text)
    directions = " ".join(direction_texts)
    if "daily" not in directions.lower():
        return None

    counts_by_form: Dict[str, list[float]] = {}
    for count_text, form_text in _DOSAGE_FORM_PATTERN.findall(directions):
        count = _COUNT_WORDS.get(count_text.lower())
        if count is None:
            count = _positive_float(count_text)
        form = _canonical_dosage_form(form_text)
        if count is not None and form:
            counts_by_form.setdefault(form, []).append(count)
    if len(counts_by_form) < 2:
        return None

    best_quantity = -1.0
    selected_form = ""
    for entry in serving_sizes:
        if not isinstance(entry, dict):
            continue
        quantity = next(
            (
                number
                for key in ("quantity", "servingSizeQuantity", "maxQuantity", "minQuantity")
                if (number := _positive_float(entry.get(key))) is not None
            ),
            0.0,
        )
        form = _canonical_dosage_form(entry.get("unit"))
        if quantity > best_quantity:
            selected_form, best_quantity = form, quantity
    counts = counts_by_form.get(selected_form) or []
    if not counts or best_quantity <= 0:
        return None
    return min(counts) / best_quantity, max(counts) / best_quantity


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

    entry = select_canonical_serving(serving_sizes)
    if entry is None:
        return None
    return _ordered_pair(
        entry.get("minDailyServings") or entry.get("min_daily_servings"),
        entry.get("maxDailyServings") or entry.get("max_daily_servings"),
    )


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
    composite = _composite_pack_daily_range(record)
    if composite is not None:
        return composite[0], composite[1], False

    facts_panel = _facts_panel_daily_range(record)
    if facts_panel is not None:
        return facts_panel[0], facts_panel[1], False

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
