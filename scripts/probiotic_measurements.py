"""Preserve AFU label measurements without pretending they are CFU.

This is a measurement adapter, not a clinical benchmark. No universal AFU/CFU
conversion or AFU adequacy range is authored. Rows remain assessment-incomplete
until an independently reviewed, compatible reference is implemented.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation

_AFU_UNIT = re.compile(
    r"(?:(million|billion)\s+)?(?:afu|active fluorescent units?)(?:\(s\))?",
    re.IGNORECASE,
)
AFU_REVIEW_REASON = "probiotic_afu_reference_unavailable"


def collect_afu_measurements(product: Mapping) -> list[dict]:
    """Read cleaned row quantities plus the lossless label-display projection.

    A row can occur in the nested and flattened cleaner projections. Its source
    reference and amount identify one measurement. Different serving amounts
    are retained, never summed into an invented product or per-strain dose.
    """
    found: dict[tuple, dict] = {}

    def add(ref, value, unit, serving=None):
        match = _AFU_UNIT.fullmatch(str(unit or "").strip())
        if not match:
            return
        scale = {"million": 1_000_000, "billion": 1_000_000_000}.get((match[1] or "").lower(), 1)
        try:
            decimal_source = Decimal(str(value).replace(",", ""))
            source = float(decimal_source)
            normalized = float(decimal_source * scale)
        except (InvalidOperation, TypeError, ValueError, OverflowError):
            source = normalized = float("nan")
        valid = math.isfinite(normalized) and normalized > 0 and not isinstance(value, bool)
        source_value = source if math.isfinite(source) else str(value)
        normalized = normalized if valid else None
        serving = serving or {}
        basis = tuple(serving.get(k) or None for k in (
            "serving_size_order", "serving_size_quantity", "serving_size_unit",
        ))
        key = (ref, normalized, basis) if valid else (ref, str(value), str(unit), basis)
        found.setdefault(key, {
            "source_row_ref": ref,
            "source_value": source_value,
            "source_unit": str(unit).strip(),
            "normalized_value": normalized,
            "normalized_unit": "AFU",
            "serving_size_order": basis[0],
            "serving_size_quantity": basis[1],
            "serving_size_unit": basis[2],
            "assessment_status": "unresolved_reference" if valid else "invalid_amount",
        })

    def visit(rows, prefix):
        for index, row in enumerate(rows or []):
            if not isinstance(row, Mapping):
                continue
            ref = row.get("raw_source_path") or f"{prefix}[{index}]"
            variants = row.get("quantityVariants") or []
            if variants:
                for variant in variants:
                    if isinstance(variant, Mapping):
                        add(ref, variant.get("quantity"), variant.get("unit"), variant)
            else:
                add(ref, row.get("quantity"), row.get("unit"))
            visit(row.get("nestedIngredients"), f"{ref}.nestedRows")

    visit(product.get("activeIngredients"), "activeIngredients")
    for row in product.get("display_ingredients") or []:
        if not isinstance(row, Mapping) or row.get("source_section") != "activeIngredients":
            continue
        ref = row.get("raw_source_path")
        if not ref:
            continue
        values = [{"exact_dose_text": row.get("exact_dose_text")}]
        values.extend(row.get("serving_variants") or [])
        for value in values:
            if not isinstance(value, Mapping):
                continue
            parts = str(value.get("exact_dose_text") or "").split(maxsplit=1)
            if len(parts) == 2:
                add(ref, parts[0], parts[1], value)
    return list(found.values())


def pending_afu_measurements(product: Mapping) -> list[dict]:
    """Consume the enrichment-owned measurement contract, including blob alias."""
    pdata = product.get("probiotic_data") or product.get("probiotic_detail") or {}
    if not isinstance(pdata, Mapping):
        return []
    rows = pdata.get("afu_measurements")
    if rows is None:
        return []
    # Only the current, exact formula contract can settle an AFU exposure. Never
    # trust an enriched/caller-supplied success stamp or convert AFU into CFU.
    from studied_formulas import assess_studied_formula
    if assess_studied_formula(product)["status"] == "assessed_studied_formula":
        return []
    if not isinstance(rows, list):
        rows = [rows]
    return [
        row if (
            isinstance(row, dict)
            and isinstance(row.get("source_row_ref"), str)
            and row["source_row_ref"].strip()
        ) else {
            "source_row_ref": f"probiotic_data.afu_measurements[{index}]",
            "assessment_status": "invalid_measurement_payload",
        }
        for index, row in enumerate(rows)
    ]
