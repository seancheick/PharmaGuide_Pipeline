"""Shared helpers for the fiber/digestive v4 module."""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional

from scoring_v4.modules.generic_helpers import (
    _as_float,
    _norm_text,
    _safe_dict,
    _safe_list,
    get_active_ingredients,
)


FIBER_CANONICALS = frozenset({
    "fiber",
    "psyllium",
    "psyllium_husk",
    "inulin",
    "acacia_fiber",
    "acacia_gum",
    "partially_hydrolyzed_guar_gum",
    "guar_gum",
    "glucomannan",
    "konjac_glucomannan",
    "beta_glucan",
    "wheat_dextrin",
    "pectin",
    "resistant_starch",
    "prebiotics",
})

FIBER_TERMS = (
    "fiber",
    "fibre",
    "psyllium",
    "inulin",
    "acacia",
    "guar",
    "glucomannan",
    "konjac",
    "beta glucan",
    "wheat dextrin",
    "pectin",
    "resistant starch",
    "prebiotic",
)

PHGG_CANONICALS = frozenset({
    "nha_sunfiber",
    "nha_sunfiber_ag",
    "partially_hydrolyzed_guar_gum",
})

GUAR_CANONICALS = frozenset({
    "guar_gum",
    "oi_guar_gum",
})

COMPATIBLE_GUAR_CANONICALS = frozenset({
    "",
    "fiber",
    *GUAR_CANONICALS,
})

PHGG_ROW_TERMS = (
    re.compile(r"\bphgg\b"),
    re.compile(r"\bsunfiber(?:\s+ag)?\b"),
    re.compile(r"\bpartially\s+hydrolyzed\s+guar(?:\s+gum)?\b"),
    re.compile(r"\bhydrolyzed\s+guar\s+gum\b"),
    re.compile(r"\bguar\s+gum\s+hydrolyzed\b"),
)


def row_text(row: Dict[str, Any]) -> str:
    return " ".join(
        _norm_text(row.get(field))
        for field in (
            "name",
            "standard_name",
            "standardName",
            "canonical_id",
            "matched_form",
            "raw_source_text",
            "category",
        )
    )


def canonical(row: Dict[str, Any]) -> str:
    return _norm_text(row.get("canonical_id")).replace("-", "_")


def _normalize_signal_text(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _norm_text(value)).strip()


def _phgg_signal_text(row: Dict[str, Any]) -> str:
    pieces = [
        _normalize_signal_text(row.get("name")),
        _normalize_signal_text(row.get("raw_source_text")),
    ]
    for form in _safe_list(row.get("forms")):
        if isinstance(form, dict):
            pieces.append(_normalize_signal_text(form.get("name")))
    raw_taxonomy = _safe_dict(row.get("raw_taxonomy"))
    for form in _safe_list(raw_taxonomy.get("forms")):
        if isinstance(form, dict):
            pieces.append(_normalize_signal_text(form.get("name")))
    return " ".join(piece for piece in pieces if piece)


def is_hydrolyzed_guar_fiber_row(row: Dict[str, Any]) -> bool:
    if not isinstance(row, dict):
        return False
    cid = canonical(row)
    if cid in PHGG_CANONICALS:
        return True
    if cid not in COMPATIBLE_GUAR_CANONICALS:
        return False
    text = _phgg_signal_text(row)
    return any(pattern.search(text) for pattern in PHGG_ROW_TERMS)


def is_fiber_row(row: Dict[str, Any]) -> bool:
    if not isinstance(row, dict):
        return False
    if is_hydrolyzed_guar_fiber_row(row):
        return True
    if canonical(row) in FIBER_CANONICALS:
        return True
    if _norm_text(row.get("category")) == "fiber":
        return True
    text = row_text(row)
    return any(term in text for term in FIBER_TERMS)


def fiber_rows(product: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [row for row in get_active_ingredients(product) if is_fiber_row(row)]


def has_fiber_context(product: Dict[str, Any]) -> bool:
    if fiber_rows(product):
        return True
    name = _norm_text(
        product.get("product_name")
        or product.get("fullName")
        or product.get("name")
    )
    return any(term in name for term in FIBER_TERMS)


def nutrition_fiber_grams(product: Dict[str, Any]) -> Optional[float]:
    for container_key in ("nutrition_detail", "nutrition_summary"):
        container = _safe_dict((product or {}).get(container_key))
        grams = _as_float(container.get("dietary_fiber_g"), None)
        if grams is not None and grams > 0:
            return grams
    return None


def dose_grams(row: Dict[str, Any]) -> Optional[float]:
    value = _as_float(row.get("quantity") or row.get("normalized_amount") or row.get("dosage"), None)
    if value is None or value <= 0:
        return None
    unit = _norm_text(row.get("unit_normalized") or row.get("unit") or row.get("normalized_unit") or row.get("dosage_unit"))
    compact = unit.replace(" ", "")
    if compact in {"g", "gram", "grams", "gram(s)"}:
        return value
    if compact in {"mg", "milligram", "milligrams", "milligram(s)"}:
        return value / 1000.0
    return None


def total_fiber_grams(rows: Iterable[Dict[str, Any]]) -> float:
    total = 0.0
    for row in rows:
        grams = dose_grams(row)
        if grams is not None:
            total += grams
    return round(total, 4)


def product_name_text(product: Dict[str, Any]) -> str:
    return _norm_text(
        " ".join(
            str((product or {}).get(field) or "")
            for field in ("product_name", "fullName", "brandName", "brand_name")
        )
    )
