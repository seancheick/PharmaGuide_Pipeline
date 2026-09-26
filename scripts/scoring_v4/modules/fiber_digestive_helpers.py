"""Shared helpers for the fiber/digestive v4 module."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from scoring_v4.modules.generic_helpers import (
    _norm_text,
    _safe_dict,
    get_active_ingredients,
)



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

# Routing owns the fiber canonical identity; the scorer reads the same set.
from scoring_v4.route_features import (
    FIBER_CANONICALS, PHGG_CANONICALS, GUAR_CANONICALS,
    COMPATIBLE_GUAR_CANONICALS, PHGG_ROW_TERMS,
    is_fiber_row, is_hydrolyzed_guar_fiber_row,
)


def row_text(row: Dict[str, Any]) -> str:
    return " ".join(_norm_text(row.get(field)) for field in (
        "name", "standard_name", "standardName", "canonical_id", "matched_form",
        "raw_source_text", "category",
    ))


def canonical(row: Dict[str, Any]) -> str:
    return _norm_text(row.get("canonical_id")).replace("-", "_")


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


def nutrition_fiber_exposure(product: Dict[str, Any]):
    """Consume the nutrition owner without matching names back to actives."""
    from scoring_v4.exposure import row_exposure
    for container_key in ("nutrition_detail", "nutrition_summary"):
        container = _safe_dict((product or {}).get(container_key))
        grams = dose_grams({"quantity": container.get("dietary_fiber_g"), "unit": "g"})
        if grams is None or grams <= 0:
            continue
        source = _safe_dict(container.get("dietary_fiber_source"))
        owner = {
            "quantity": source.get("amount"), "unit": source.get("unit"),
            "raw_source_path": source.get("raw_source_path"),
            "quantityVariants": source.get("quantityVariants"),
        }
        source_amount = dose_grams(owner)
        if source_amount is not None and source_amount == grams and source.get("raw_source_path"):
            return row_exposure(product, owner, basis="daily", unit="g")
        # Preserve the shared scalar contract for historical artifacts. Lost
        # qualifiers cannot be reconstructed; new cleaning carries the owner.
        return row_exposure(product, {
            "quantity": grams, "unit": "g",
            "raw_source_path": f"{container_key}.dietary_fiber_g",
            **({"quantity_operator": "unknown"} if source else {}),
        }, basis="daily", unit="g")
    return None


def nutrition_fiber_grams(product: Dict[str, Any]) -> Optional[float]:
    exposure = nutrition_fiber_exposure(product)
    return exposure.per_serving_amount if exposure is not None else None


def dose_grams(row: Dict[str, Any]) -> Optional[float]:
    from scoring_v4.exposure import row_exposure
    return row_exposure({}, row, basis="per_use", unit="g").per_serving_amount


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
