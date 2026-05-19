"""v4 Layer 2 — Completeness Gate.

Decides whether an enriched product has enough structured data to enter
the live catalog and score pipeline. This is deliberately narrower than
quality scoring: missing hard minimums yields NOT_SCORED; missing
nice-to-have fields should lower confidence or score later.

Per SCORING_V4_PROPOSAL.md §4 Layer 2:

  completeness fail → is_live_eligible=false
                    → verdict=NOT_SCORED (archive / QA only)
                    → excluded from the live Flutter catalog

The gate is class-aware. A probiotic with named strains + total CFU but
no per-strain CFU is eligible; the per-strain gap belongs in confidence
or module scoring, not in live eligibility.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence


MAPPED_COVERAGE_MIN = 0.85
MULTI_DOSE_COVERAGE_MIN = 0.60


@dataclass
class CompletenessResult:
    """Outcome of the Layer 2 completeness gate."""

    module: str = "generic"
    is_live_eligible: bool = False
    verdict: Optional[str] = "NOT_SCORED"
    reason: Optional[str] = "incomplete_product_data"
    missing_fields: List[str] = field(default_factory=list)
    mapped_coverage: float = 0.0
    dose_coverage: Optional[float] = None
    checked_fields: List[str] = field(default_factory=list)


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _norm(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def _as_float(value: Any, default: Optional[float] = 0.0) -> Optional[float]:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _active_ingredients(product: Dict[str, Any]) -> List[Dict[str, Any]]:
    iqd = _safe_dict(product.get("ingredient_quality_data"))
    candidates: Sequence[Any] = (
        _safe_list(iqd.get("ingredients_scorable"))
        or _safe_list(iqd.get("ingredients"))
        or _safe_list(product.get("activeIngredients"))
        or _safe_list(product.get("active_ingredients"))
    )
    rows = [i for i in candidates if isinstance(i, dict)]
    return [i for i in rows if not i.get("is_filler")]


def _has_active_identity(ingredient: Dict[str, Any]) -> bool:
    return bool(
        ingredient.get("canonical_id")
        or ingredient.get("matched_id")
        or ingredient.get("ingredient_id")
        or ingredient.get("mapped") is True
    )


def _dose_value(ingredient: Dict[str, Any]) -> Optional[float]:
    for key in ("dose", "amount", "quantity", "dosage", "daily_value_amount"):
        value = _as_float(ingredient.get(key), None)
        if value is not None and value > 0:
            return value
    return None


def _dose_unit(ingredient: Dict[str, Any]) -> str:
    for key in ("unit", "dose_unit", "amount_unit", "dosage_unit", "quantity_unit"):
        unit = _norm(ingredient.get(key))
        if unit and unit not in {"np", "n/a", "na", "none"}:
            return unit
    return ""


def _has_dose_with_unit(ingredient: Dict[str, Any]) -> bool:
    return _dose_value(ingredient) is not None and bool(_dose_unit(ingredient))


def _mapped_coverage(product: Dict[str, Any], ingredients: List[Dict[str, Any]]) -> float:
    explicit = _as_float(product.get("mapped_coverage"), None)
    if explicit is not None:
        return max(0.0, min(1.0, explicit))

    iqd = _safe_dict(product.get("ingredient_quality_data"))
    total_active = int(_as_float(iqd.get("total_active"), 0) or 0)
    unmapped_present = "unmapped_scorable_count" in iqd or "unmapped_count" in iqd
    unmapped = int(
        _as_float(
            iqd.get("unmapped_scorable_count", iqd.get("unmapped_count")),
            0,
        )
        or 0
    )
    if total_active > 0 and unmapped_present and unmapped >= 0:
        mapped = max(0, total_active - unmapped)
        return round(mapped / total_active, 4)

    if not ingredients:
        return 0.0
    mapped_count = sum(1 for i in ingredients if _has_active_identity(i))
    return round(mapped_count / len(ingredients), 4)


def _form_factor(product: Dict[str, Any]) -> str:
    for key in ("form_factor", "product_form", "dosage_form", "form"):
        value = _norm(product.get(key))
        if value:
            return value
    return ""


def _status_is_active(product: Dict[str, Any]) -> bool:
    status = _norm(product.get("product_status") or product.get("status"))
    if not status:
        # Legacy enriched blobs may omit status. P1.2 treats missing as
        # unknown-but-eligible; the active-only catalog gate is P0.3.
        return True
    return status in {"active", "on_market", "on market", "marketed", "current"}


def _base_checks(product: Dict[str, Any], ingredients: List[Dict[str, Any]]) -> tuple[List[str], float]:
    missing: List[str] = []
    coverage = _mapped_coverage(product, ingredients)
    if not _status_is_active(product):
        missing.append("product_status_active")
    if not _form_factor(product):
        missing.append("form_factor")
    if not ingredients or not any(_has_active_identity(i) for i in ingredients):
        missing.append("active_identity")
    if coverage < MAPPED_COVERAGE_MIN:
        missing.append("mapped_coverage")
    return missing, coverage


def _total_cfu_billion(product: Dict[str, Any]) -> float:
    pdata = _safe_dict(product.get("probiotic_data"))
    total = _as_float(pdata.get("total_billion_count"), None)
    if total is not None and total > 0:
        return total
    total = 0.0
    for blend in _safe_list(pdata.get("probiotic_blends")):
        if not isinstance(blend, dict):
            continue
        cfu_data = _safe_dict(blend.get("cfu_data"))
        total += _as_float(cfu_data.get("billion_count"), 0.0) or 0.0
    return total or 0.0


def _named_strain_count(product: Dict[str, Any]) -> int:
    pdata = _safe_dict(product.get("probiotic_data"))
    explicit = int(_as_float(pdata.get("total_strain_count"), 0) or 0)
    if explicit > 0:
        return explicit

    strains = set()
    for blend in _safe_list(pdata.get("probiotic_blends")):
        if not isinstance(blend, dict):
            continue
        for strain in _safe_list(blend.get("strains")):
            name = str(strain).strip()
            if name:
                strains.add(name.lower())
    return len(strains)


def _dose_coverage(ingredients: List[Dict[str, Any]]) -> float:
    if not ingredients:
        return 0.0
    dose_count = sum(1 for i in ingredients if _has_dose_with_unit(i))
    return round(dose_count / len(ingredients), 4)


def _finalize(
    module: str,
    missing: List[str],
    mapped_coverage: float,
    dose_coverage: Optional[float],
    checked_fields: List[str],
) -> CompletenessResult:
    # Preserve first occurrence order while removing duplicates.
    unique_missing = list(dict.fromkeys(missing))
    eligible = not unique_missing
    return CompletenessResult(
        module=module,
        is_live_eligible=eligible,
        verdict=None if eligible else "NOT_SCORED",
        reason=None if eligible else "incomplete_product_data",
        missing_fields=unique_missing,
        mapped_coverage=round(mapped_coverage, 4),
        dose_coverage=dose_coverage,
        checked_fields=checked_fields,
    )


def evaluate_completeness_gate(product: Dict[str, Any], module: str) -> CompletenessResult:
    """Evaluate the v4 Layer 2 live-catalog eligibility gate.

    Never raises. Missing or malformed product data fails closed to
    NOT_SCORED, except missing legacy `status` which remains eligible
    until the separate active-only catalog gate lands.
    """
    if not isinstance(product, dict):
        return CompletenessResult(
            module=module or "generic",
            missing_fields=["product_payload"],
            checked_fields=["product_payload"],
        )

    module = module if module in {"generic", "probiotic", "multi_or_prenatal"} else "generic"
    ingredients = _active_ingredients(product)
    missing, coverage = _base_checks(product, ingredients)
    checked_fields = [
        "product_status_active",
        "form_factor",
        "active_identity",
        "mapped_coverage",
    ]
    dose_cov: Optional[float] = None

    if module == "probiotic":
        checked_fields.extend(["total_cfu", "named_strain"])
        if _total_cfu_billion(product) <= 0:
            missing.append("total_cfu")
        if _named_strain_count(product) <= 0:
            missing.append("named_strain")
        # Per-strain CFU and clinical-strain codes are soft fields.
        return _finalize(module, missing, coverage, dose_cov, checked_fields)

    if module == "multi_or_prenatal":
        checked_fields.append("micronutrient_panel_dose_coverage")
        dose_cov = _dose_coverage(ingredients)
        # True multis need 60% dose-bearing panel coverage. Small prenatal
        # specialty products (e.g. prenatal DHA) can still ship if their
        # active identity + dose are present; they are routed here for
        # dose/safety expectations, not because they have a full panel.
        if len(ingredients) >= 8 and dose_cov < MULTI_DOSE_COVERAGE_MIN:
            missing.append("micronutrient_panel_dose_coverage")
        elif len(ingredients) < 8 and ingredients and not any(_has_dose_with_unit(i) for i in ingredients):
            missing.append("dose_with_unit")
        return _finalize(module, missing, coverage, dose_cov, checked_fields)

    # Generic module: single nutrients, botanicals, omega, sports stacks.
    checked_fields.append("dose_with_unit")
    if not any(_has_dose_with_unit(i) for i in ingredients):
        missing.append("dose_with_unit")
    return _finalize(module, missing, coverage, dose_cov, checked_fields)
