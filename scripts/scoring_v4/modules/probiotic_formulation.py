"""v4 Probiotic Formulation dimension — P2.1.

Scores probiotic-specific formulation quality against the 25-point
rubric in SCORING_V4_PROPOSAL §6. This module is intentionally focused
on formulation signals only; per-strain CFU adequacy belongs to P2.2
Dose and strain-clinical evidence belongs to P2.3 Evidence.
"""

from __future__ import annotations

import math
import re
from typing import Any, Dict

from scoring_input_contract import get_scoring_ingredients
from scoring_v4.modules.generic_formulation import shared_formulation_penalty_detail
from studied_formulas import label_owned_native_strains
from probiotic_measurements import declared_total_cfu


PHASE_MARKER = "P2.1_probiotic_formulation"
from scoring_v4.quality_score_config import block as _cfg_block

_FVM = _cfg_block("formulation_variant_magnitudes", "probiotic")["probiotic"]


CAP_FORMULATION = _FVM["cap_formulation"]


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or isinstance(value, bool):
            return default
        number = float(value)
        return number if math.isfinite(number) else default
    except (TypeError, ValueError, OverflowError):
        return default


def _as_int(value: Any, default: int = 0) -> int:
    return int(_as_float(value, default))


def score_formulation(product: Any) -> Dict[str, Any]:
    """Return the probiotic Formulation dimension payload.

    Components:
      - total CFU disclosed: 4
      - CFU amount tier: 5
      - named species diversity: 4, using an appropriate-diversity curve
        rather than rewarding strain count indefinitely
      - exact label-owned strain identities: 8 (not clinical benefit)
      - delivery/survivability: 3
      - prebiotic complement: 1

    An exact reviewed whole-formula AFU assessment uses these same component
    budgets for native potency, studied strain identity and delivery. It does
    not claim a CFU amount or independent research for each constituent.
    """
    product = product if isinstance(product, dict) else {}
    pdata = _probiotic_payload(product)

    total_billion = _total_billion_count(pdata)
    strain_count = _total_strain_count(pdata)
    identity_count = len({row["clinical_id"] for row in label_owned_native_strains(product)})

    components = {
        "total_cfu_disclosed": _score_total_cfu_disclosed(total_billion),
        "cfu_amount": _score_cfu_amount(total_billion),
        "named_species_diversity": _score_named_species_diversity(strain_count),
        "identified_strain_codes": _score_identified_strain_codes(identity_count),
        "delivery_survivability": _score_delivery_survivability(product, pdata),
        "prebiotic_complement": _score_prebiotic_complement(product, pdata),
    }
    from studied_formulas import assess_studied_formula
    formula = assess_studied_formula(product)
    if formula["status"] == "assessed_studied_formula":
        # Same six component budgets, assessed in the study's native unit.
        # Do not feed AFU into the CFU size tiers or call formula evidence an
        # independent clinical trial for every constituent strain.
        components.pop("total_cfu_disclosed")
        components.pop("cfu_amount")
        components.pop("identified_strain_codes")
        components.update(native_potency_disclosed=4.0, studied_formula_potency=5.0,
                          studied_formula_strain_identity=8.0,
                          delivery_survivability=3.0, prebiotic_complement=1.0)
    shared_penalties = shared_formulation_penalty_detail(product)
    penalties = dict(shared_penalties["penalties"])
    penalty_magnitude = sum(abs(float(value or 0.0)) for value in penalties.values())
    raw_score = sum(components.values())
    score = max(0.0, min(CAP_FORMULATION, raw_score - penalty_magnitude))
    metadata = {
        "phase": PHASE_MARKER,
        "raw_score": round(raw_score, 4),
        "pre_penalty_score": round(raw_score, 4),
        "total_billion_count": total_billion,
        "total_strain_count": strain_count,
        "identified_strain_count": identity_count,
        "cap_applied": raw_score > CAP_FORMULATION,
    }
    metadata.update(shared_penalties["metadata"])
    if formula["status"] == "assessed_studied_formula":
        metadata["studied_formula_assessment"] = formula
    return {
        "score": round(score, 2),
        "max": CAP_FORMULATION,
        "components": components,
        "penalties": penalties,
        "metadata": metadata,
    }


def _total_billion_count(pdata: Dict[str, Any]) -> float:
    return declared_total_cfu(pdata) / 1e9


def _total_strain_count(pdata: Dict[str, Any]) -> int:
    count = _as_int(pdata.get("total_strain_count"), 0)
    if count > 0:
        return count
    strains = set()
    for blend in _safe_list(pdata.get("probiotic_blends")):
        blend = _safe_dict(blend)
        for strain in _safe_list(blend.get("strains")):
            key = str(strain or "").strip().lower()
            if key:
                strains.add(key)
    return len(strains)


def _score_total_cfu_disclosed(total_billion: float) -> float:
    return 4.0 if total_billion > 0 else 0.0


def _score_cfu_amount(total_billion: float) -> float:
    if total_billion >= 50:
        return 5.0
    if total_billion >= 10:
        return 4.0
    if total_billion > 1:
        return 3.0
    if total_billion > 0:
        return 1.5
    return 0.0


def _score_named_species_diversity(strain_count: int) -> float:
    if strain_count >= 16:
        return 2.0
    if strain_count >= 9:
        return 3.0
    if strain_count >= 3:
        return 4.0
    if strain_count > 0:
        return 3.0
    return 0.0


def _score_identified_strain_codes(identity_count: int) -> float:
    if identity_count >= 5:
        return 8.0
    if identity_count >= 3:
        return 7.0
    if identity_count >= 2:
        return 5.0
    if identity_count >= 1:
        return 3.0
    return 0.0


def _score_delivery_survivability(product: Dict[str, Any], pdata: Dict[str, Any]) -> float:
    if pdata.get("has_survivability_coating"):
        return 3.0

    tier = product.get("delivery_tier")
    if tier is None:
        tier = _safe_dict(product.get("delivery_data")).get("highest_tier")
    tier_int = _as_int(tier, 0)
    return {1: 3.0, 2: 2.5, 3: 1.5}.get(tier_int, 0.0)


_PREBIOTIC_RE = re.compile(
    r"\b(prebiotic|inulin|fructooligosaccharides?|fos|"
    r"galactooligosaccharides?|gos|chicory|acacia|fiber)\b",
    re.IGNORECASE,
)


def _score_prebiotic_complement(product: Dict[str, Any], pdata: Dict[str, Any]) -> float:
    """Dose-aware scoring for the 1-point prebiotic complement component.

    Presence alone is a weak formulation signal. Full credit requires a disclosed
    multi-gram prebiotic amount, so tiny excipient-level fiber does not score the
    same as a purposefully formulated synbiotic.
    """
    if not pdata.get("prebiotic_present"):
        return 0.0

    dose_g = _prebiotic_dose_g(product, pdata)
    if dose_g is None:
        return 0.25
    if dose_g >= 3.0:
        return 1.0
    if dose_g >= 1.0:
        return 0.5
    if dose_g > 0.0:
        return 0.25
    return 0.0


def _prebiotic_dose_g(product: Dict[str, Any], pdata: Dict[str, Any]) -> float | None:
    for key in ("prebiotic_dose_g", "prebiotic_grams", "prebiotic_amount_g"):
        value = _as_float(pdata.get(key), None)
        if value is not None and value > 0:
            return value

    best: float | None = None
    for row in _ingredient_rows(product):
        row = _safe_dict(row)
        if not row:
            continue
        text = " ".join(
            str(row.get(key) or "")
            for key in (
                "name",
                "standardName",
                "standard_name",
                "canonical_id",
                "raw_source_text",
                "display_label",
            )
        )
        if not _PREBIOTIC_RE.search(text):
            continue
        grams = _row_quantity_g(row)
        if grams is None:
            continue
        best = grams if best is None else max(best, grams)
    return best


def _ingredient_rows(product: Dict[str, Any]) -> list[Dict[str, Any]]:
    try:
        return [
            row for row in get_scoring_ingredients(product or {}, strict=True).rows
            if isinstance(row, dict)
        ]
    except Exception:
        return []


def _row_quantity_g(row: Dict[str, Any]) -> float | None:
    quantity = None
    for key in ("quantity", "amount", "dose", "dosage"):
        quantity = _as_float(row.get(key), None)
        if quantity is not None:
            break
    if quantity is None:
        return None
    unit = str(
        row.get("unit_normalized")
        or row.get("unit")
        or row.get("dose_unit")
        or ""
    ).strip().lower()
    if unit in {"g", "gram", "grams", "gm"}:
        return quantity
    if unit in {"mg", "milligram", "milligrams"}:
        return quantity / 1000.0
    if unit in {"mcg", "microgram", "micrograms", "ug", "µg"}:
        return quantity / 1_000_000.0
    return None


def _probiotic_payload(product: Dict[str, Any]) -> Dict[str, Any]:
    """Read enriched-input `probiotic_data` and final-blob `probiotic_detail`.

    The v4 pipeline scores enriched rows, but canary/debug tools often
    call the module directly against shipped detail blobs.
    """
    return _safe_dict(product.get("probiotic_data") or product.get("probiotic_detail"))
