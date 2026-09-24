"""Immutable benchmark exposure; identity and quantity ownership stay upstream.

Call with strict scoring rows. This module changes units and time basis only;
it never infers an ingredient, a dose from a carrier, or a treatment duration.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, localcontext
import math
from typing import Any, Mapping

from normalization import analyte_unit_parent, canonicalize_nutrient_unit
from serving_frequency import resolve_daily_serving_range
from unit_converter import convert_mass, convert_nutrient


@dataclass(frozen=True)
class Exposure:
    basis: str
    unit: str
    per_serving_amount: float | None
    minimum: float | None
    maximum: float | None
    source_path: str
    frequency_defaulted: bool
    quantity_operator: str = "="
    # Why the amount is not exact ("quantity_qualified", "daily_frequency_unknown",
    # ...): provenance for an amount that is still benchmarked below.
    uncertainty: str | None = None
    # What Dose benchmarks: the label's stated number at the resolved daily
    # range (one serving a day when the label is silent). A qualifier or a
    # defaulted frequency is recorded above as provenance, never scored as 0.
    benchmark_amount: float | None = None

    @property
    def exact(self) -> bool:
        return self.uncertainty is None


# The label's amount cannot be read: its quantity columns conflict with none
# selected ("ambiguous"), or a nutrition scalar disagrees with its source row
# ("unknown"). No amount is benchmarked; the completeness gate keeps the product
# out of the catalog until the source column is resolved upstream.
UNRESOLVED_OPERATORS = frozenset({"ambiguous", "unknown"})


def quantity_is_unresolved(row: Mapping[str, Any]) -> bool:
    return _quantity_operator(row) in UNRESOLVED_OPERATORS


def _quantity_operator(row: Mapping[str, Any]) -> str:
    explicit = row.get("quantity_operator")
    if explicit is not None:
        return str(explicit).strip() or "="
    taxonomy = row.get("raw_taxonomy")
    if not isinstance(taxonomy, Mapping):
        taxonomy = {}
    variants = row.get("quantityVariants") or taxonomy.get("quantityVariants") or []
    selected = [v for v in variants if isinstance(v, dict) and v.get("selected_for_analysis")]
    if not selected:
        selected = [v for v in variants if isinstance(v, dict)]
    operators = {str(v.get("operator") or "=").strip() for v in selected}
    return next(iter(operators)) if len(operators) == 1 else "ambiguous" if operators else "="


def _decimal_product(*values: Decimal) -> float:
    """Multiply supplied decimal representations before the public float cast."""
    with localcontext() as context:
        context.prec = max(28, sum(len(value.as_tuple().digits) for value in values))
        product = Decimal(1)
        for value in values:
            product *= value
        return float(product)


def row_exposure(product: dict, row: Mapping[str, Any], *, basis: str, unit: str = "g") -> Exposure:
    """Resolve a mass exposure, recording what the label leaves uncertain.

    Qualified quantities and a defaulted frequency keep their bounds and an
    `uncertainty` as provenance; Dose still benchmarks `benchmark_amount`, the stated
    number at the resolved daily range. Unsupported bases (including a course
    duration) have no benchmark amount.
    """
    low, high, defaulted = resolve_daily_serving_range(product)
    path = str(row.get("raw_source_path") or row.get("source") or "")
    operator = _quantity_operator(row)
    amount = row.get("quantity")
    if amount is None:
        amount = row.get("normalized_amount")
    source_unit = canonicalize_nutrient_unit(str(row.get("unit_normalized") or row.get("unit") or row.get("normalized_unit") or ""))
    target_unit = canonicalize_nutrient_unit(unit)
    raw_source_unit = str(row.get("unit_normalized") or row.get("unit") or row.get("normalized_unit") or "")
    analyte_parents = {analyte_unit_parent(u) for u in (raw_source_unit, unit)} - {None}
    if analyte_parents and analyte_parents != {row.get("canonical_id")}:
        source_unit = ""  # an analyte-qualified unit ("mg alpha-tocopherol") measures only its own nutrient
    converted = None
    decimal_amount = decimal_factor = None
    if not isinstance(amount, bool):
        try:
            number = float(amount)
            decimal_amount = Decimal(str(amount))
        except (TypeError, ValueError, OverflowError, InvalidOperation):
            number = math.nan
        mass_units = {"g", "mg", "mcg"}
        result = None
        if math.isfinite(number) and decimal_amount.is_finite() and decimal_amount >= 0 and source_unit and target_unit:
            if source_unit == target_unit:
                # Already the benchmark unit (e.g. mcg DFE declared on the label).
                result = convert_mass(number, "mg", "mg")
            elif source_unit in mass_units and target_unit in mass_units:
                result = convert_mass(number, source_unit, target_unit)
            else:
                # IU and nutrient-activity units (mg NE, mcg DFE) belong to the
                # shared nutrient converter, which detects form (natural vs
                # synthetic vitamin E, folic acid vs 5-MTHF). Only a
                # high-confidence form-specific rule becomes an exposure.
                nutrient = str(row.get("standard_name") or row.get("name") or "")
                text = " ".join(str(row.get(k) or "") for k in ("name", "matched_form")).strip()
                result = convert_nutrient(nutrient, number, str(row.get("unit_normalized") or row.get("unit") or ""), target_unit, text)
                if result.confidence != "high":
                    result = None
            factor = result.conversion_factor if result is not None else None
            if (result is not None and result.success and result.converted_value is not None and math.isfinite(result.converted_value)
                    and not isinstance(factor, bool) and factor is not None and math.isfinite(factor) and factor > 0):
                decimal_factor = Decimal(str(factor))
                candidate = _decimal_product(decimal_amount, decimal_factor)
                if math.isfinite(candidate):
                    converted = candidate
    benchmark = None
    if converted is not None and basis in {"daily", "per_use"} and operator not in UNRESOLVED_OPERATORS:
        benchmark = _decimal_product(decimal_amount, decimal_factor, Decimal(str(high))) if basis == "daily" else converted
        if not math.isfinite(benchmark):
            benchmark = None
    reason = None
    minimum = maximum = None
    if converted is None:
        reason = "mass_amount_or_unit_unusable"
    elif basis not in {"daily", "per_use"}:
        reason = "exposure_basis_unsupported"
    elif basis == "daily" and defaulted:
        reason = "daily_frequency_unknown"
    else:
        minimum, maximum = ((_decimal_product(decimal_amount, decimal_factor, Decimal(str(low))),
                             _decimal_product(decimal_amount, decimal_factor, Decimal(str(high))))
                            if basis == "daily" else (converted, converted))
        if not math.isfinite(minimum) or not math.isfinite(maximum):
            minimum = maximum = None
            reason = "exposure_not_finite"
        elif operator not in {"", "="}:
            reason = "quantity_qualified"
            if operator in {"<", "<=", "≤"}:
                minimum = 0.0
            elif operator in {">", ">=", "≥"}:
                maximum = None
            else:
                minimum = maximum = None
    return Exposure(basis, target_unit, converted, minimum, maximum, path, defaulted, operator, reason, benchmark)
