"""Joint-support calibration helpers for generic v4 scoring.

Joint products still route through the generic module. These helpers keep the
route stable while avoiding RDA/UL proxy behavior for non-RDA joint actives.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

from collagen_taxonomy import (
    UNDENATURED_TYPE_II,
    UNSPECIFIED,
    classify_collagen_subtype_strict,
)
from scoring_v4.modules.generic_helpers import (
    daily_serving_multiplier,
    get_active_ingredients,
    primary_type_of,
    _as_float,
    _norm_text,
)


from scoring_v4.quality_score_config import block as _cfg_block

_CM = _cfg_block("category_magnitudes", "joint_support")["joint_support"]


JOINT_SUPPORT_EVIDENCE_CAP = _CM["evidence_cap"]

JOINT_TARGET_DOSE_MG = dict(_CM["target_dose_mg"])

_JOINT_ALIASES = {
    "glucosamine": ("glucosamine",),
    "chondroitin": ("chondroitin",),
    "msm": ("msm", "methylsulfonylmethane"),
    "hyaluronic_acid": ("hyaluronic acid", "hyaluronan"),
}


def is_joint_support_product(product: Dict[str, Any]) -> bool:
    return primary_type_of(product) == "joint_support"


def joint_support_evidence_cap(product: Dict[str, Any]) -> Optional[float]:
    if is_joint_support_product(product):
        return JOINT_SUPPORT_EVIDENCE_CAP
    return None


def score_joint_support_dose(product: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not is_joint_support_product(product):
        return None

    actives = joint_active_doses(product)
    if not actives:
        return None

    adequate = [item["active"] for item in actives if item["ratio"] >= 1.0]
    best_ratio = max(item["ratio"] for item in actives)
    if len(adequate) >= 2:
        score = 22.0
        band = "multi_active_clinical_dose"
    elif adequate:
        score = 20.0
        band = "single_active_clinical_dose"
    else:
        score = round(max(0.0, min(1.0, best_ratio)) * 20.0, 4)
        band = "below_joint_support_range"

    return {
        "score": score,
        "band": band,
        "adequate_actives": adequate,
        "actives": actives,
    }


def joint_active_doses(product: Dict[str, Any]) -> list[Dict[str, Any]]:
    daily_multiplier = _daily_serving_multiplier(product)
    by_active: Dict[str, Dict[str, Any]] = {}
    for row in get_active_ingredients(product):
        active = _joint_active_id(row)
        if not active:
            continue
        mg = _row_quantity_mg(row)
        if mg is None:
            continue
        daily_mg = mg * daily_multiplier
        target = JOINT_TARGET_DOSE_MG[active]
        payload = {
            "active": active,
            "daily_mg": round(daily_mg, 4),
            "target_mg": target,
            "ratio": round(daily_mg / target, 4),
        }
        current = by_active.get(active)
        if current is None or payload["daily_mg"] > current["daily_mg"]:
            by_active[active] = payload
    return sorted(by_active.values(), key=lambda item: item["ratio"], reverse=True)


def _joint_active_id(row: Dict[str, Any]) -> Optional[str]:
    fields = (
        row.get("canonical_id"),
        row.get("scoring_parent_id"),
        row.get("evidence_canonical_id"),
        row.get("standard_name"),
        row.get("name"),
        row.get("matched_form"),
        row.get("raw_source_text"),
    )
    keys = tuple(
        dict.fromkeys(
            normalized
            for value in fields
            for normalized in (
                _norm_text(value),
                _norm_text(value).replace("_", " "),
            )
            if normalized
        )
    )
    if _is_undenatured_type_ii(row, keys):
        return "uc_ii"
    for active, aliases in _JOINT_ALIASES.items():
        if active in keys or active.replace("_", " ") in keys:
            return active
        if any(_any_alias_matches(aliases, key) for key in keys):
            return active
    return None


def _is_undenatured_type_ii(
    row: Dict[str, Any],
    normalized_fields: Iterable[str],
) -> bool:
    """Use the shared collagen taxonomy for the 40 mg UC-II identity.

    Hydrolyzed Type II collagen has a different clinical dose range. The
    enricher's explicit subtype is authoritative when present; older artifacts
    fall back to row-local classification, never concatenated cross-field text.
    """

    stamped = _norm_text(row.get("collagen_subtype")).replace(" ", "_")
    if stamped and stamped != UNSPECIFIED:
        return stamped == UNDENATURED_TYPE_II
    return any(
        classify_collagen_subtype_strict(field) == UNDENATURED_TYPE_II
        for field in normalized_fields
    )


def _any_alias_matches(aliases: Iterable[str], text: str) -> bool:
    return any(alias in text for alias in aliases)


def _row_quantity_mg(row: Dict[str, Any]) -> Optional[float]:
    quantity = _as_float(row.get("quantity"), None)
    if quantity is None or quantity <= 0:
        return None
    unit = _norm_text(row.get("unit_normalized") or row.get("unit"))
    compact = unit.replace(" ", "")
    if unit in {"mg", "milligram", "milligrams", "milligram(s)"} or compact in {
        "mg",
        "milligram",
        "milligrams",
        "milligram(s)",
    }:
        return quantity
    if unit in {"g", "gram", "grams", "gram(s)"} or compact in {
        "g",
        "gram",
        "grams",
        "gram(s)",
    }:
        return quantity * 1000.0
    if unit in {"mcg", "ug", "microgram", "micrograms", "microgram(s)"} or compact in {
        "mcg",
        "ug",
        "microgram",
        "micrograms",
        "microgram(s)",
    }:
        return quantity / 1000.0
    return None


def _daily_serving_multiplier(product: Dict[str, Any]) -> float:
    return daily_serving_multiplier(product)
