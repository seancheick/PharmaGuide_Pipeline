"""Shared probiotic measurement and registry-scope adapters.

This is a measurement adapter, not a clinical benchmark. No universal AFU/CFU
conversion or AFU adequacy range is authored. CFU potency bands and research
scope retain the registry's meaning; neither invents clinical dose applicability.
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


def normalized_cfu_count(measure: Mapping) -> float | None:
    """Read one normalized CFU measurement; reject invalid or conflicting twins.

    CFU and billion-CFU are the same unit at a known scale, unlike AFU or mass.
    An explicitly invalid count is not rescued by a second redundant field.
    """
    values = []
    for field, scale in (("cfu_count", 1.0), ("billion_count", 1e9)):
        if field not in measure:
            continue
        value = measure[field]
        if isinstance(value, bool):
            return None
        try:
            number = float(value) * scale
        except (TypeError, ValueError, OverflowError):
            return None
        if not math.isfinite(number) or number <= 0:
            return None
        values.append(number)
    if not values or any(not math.isclose(values[0], v, rel_tol=1e-9) for v in values[1:]):
        return None
    return values[0]


def declared_total_cfu(pdata: Mapping) -> float:
    """Consume enrichment's ownership-reconciled total, never re-sum projections."""
    measure = {target: pdata[source] for source, target in (
        ("total_cfu", "cfu_count"), ("total_billion_count", "billion_count")
    ) if source in pdata}
    return normalized_cfu_count(measure) or 0.0


def strain_cfu_tier(cfu_per_day, tiers_cfu_per_day) -> str | None:
    """Map a per-strain CFU count to the registry's potency band.

    These bands do not establish trial-dose applicability or clinical efficacy.

    Returns one of ``"low" | "adequate" | "good" | "excellent"`` or
    ``None`` when the dose is zero/missing or the bands dict is empty.
    Tolerates band-key order and missing ``upper_exclusive`` (treats it
    as +infinity) / missing ``lower_inclusive`` (treats it as 0).
    """
    if (isinstance(cfu_per_day, bool) or not isinstance(cfu_per_day, (int, float))
            or not math.isfinite(cfu_per_day) or cfu_per_day <= 0):
        return None
    if not isinstance(tiers_cfu_per_day, dict) or not tiers_cfu_per_day:
        return None

    for tier_name in ("low", "adequate", "good", "excellent"):
        band = tiers_cfu_per_day.get(tier_name)
        if not isinstance(band, dict):
            continue
        lower = band.get("lower_inclusive", 0)
        upper = band.get("upper_exclusive")
        lower_ok = cfu_per_day >= (lower if isinstance(lower, (int, float)) else 0)
        upper_ok = (
            upper is None
            or (isinstance(upper, (int, float)) and cfu_per_day < upper)
        )
        if lower_ok and upper_ok:
            return tier_name
    return None


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


def clinical_strain_research_scope(entry: dict) -> dict:
    """One registry-owned scope decision for presentation and scored evidence."""
    entry = entry if isinstance(entry, dict) else {}
    thresholds = entry.get("cfu_thresholds") or {}
    thresholds = thresholds if isinstance(thresholds, dict) else {}
    evidence = thresholds.get("evidence") or {}
    evidence = evidence if isinstance(evidence, dict) else {}
    validation = evidence.get("clinical_validation") or {}
    validation = validation if isinstance(validation, dict) else {}
    evidence_type = str(evidence.get("type") or "").strip().lower()
    explicit = str(validation.get("q1_strain_explicit") or "").strip().upper()
    human = str(validation.get("q3_human_clinical") or "").strip().upper()
    human_evidence = human == "YES" if human else any(
        token in evidence_type for token in ("rct", "meta_analysis", "clinical", "guideline", "human"))
    if explicit == "FORMULA_LEVEL" or evidence_type == "product_formula_rct":
        scope = "formula_specific"
    elif explicit == "YES" or "strain_specific" in evidence_type:
        scope = "strain_specific"
    elif explicit == "NO":
        scope = "species_general"
    else:
        scope = "scope_unresolved"
    return {"evidence_scope": scope, "human_evidence": human_evidence}
