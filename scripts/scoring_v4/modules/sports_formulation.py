"""v4 sports protein formulation adapter.

The generic formulation scorer under-recognizes protein powders because it is
built around vitamin/mineral form quality and broad supplement composition.
This adapter keeps the shared safety/sugar penalties but scores protein powders
on the formulation facts that matter for the category: source quality,
transparent protein dosing, amino-profile disclosure, focus, and daily-use
cleanliness.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from scoring_v4.modules.generic_formulation import (
    score_formulation as score_generic_formulation,
    shared_formulation_penalty_detail,
)
from scoring_v4.modules.generic_helpers import (
    _norm_text,
    _safe_dict,
    _safe_list,
    get_active_ingredients,
)
from scoring_v4.modules.sports_helpers import (
    BCAA_CANONICALS,
    EAA_CANONICALS,
    SPORTS_PROTEIN_CANONICALS,
    canonical,
    dose_g,
    primary_sports_identity,
)


DIMENSION_CAP = 30.0
PHASE_MARKER = "P1.7_sports_protein_formulation_v1"

_WHEY_TERMS = ("whey",)
_WHEY_ISOLATE_TERMS = ("whey protein isolate", "whey isolate")
_CASEIN_TERMS = ("casein", "micellar casein")
_SOY_TERMS = ("soy protein",)
_PEA_TERMS = ("pea protein",)
_RICE_TERMS = ("rice protein", "brown rice protein")
_COLLAGEN_TERMS = ("collagen", "gelatin")
_SPIKING_TERMS = ("glycine", "taurine", "creatine", "glutamine")


def score_formulation(product: Dict[str, Any]) -> Dict[str, Any]:
    """Score sports formulation, applying the protein adapter only when relevant."""
    if not isinstance(product, dict):
        product = {}

    if not _is_protein_context(product):
        return score_generic_formulation(product)

    rows = get_active_ingredients(product)
    protein_rows = _protein_rows(rows)
    if not protein_rows:
        return score_generic_formulation(product)

    source_quality, source_class = _source_quality(protein_rows, product)
    dose_transparency = _dose_transparency(protein_rows, source_class)
    amino_disclosure = _amino_profile_disclosure(rows)
    focus = _protein_focus(rows, source_class)
    clean_daily_use = _clean_daily_use(product)

    components: Dict[str, float] = {
        "sports_protein_source_quality": round(source_quality, 4),
        "sports_protein_dose_transparency": round(dose_transparency, 4),
        "sports_amino_profile_disclosure": round(amino_disclosure, 4),
        "sports_protein_focus": round(focus, 4),
        "sports_clean_daily_use": round(clean_daily_use, 4),
    }

    shared = shared_formulation_penalty_detail(product)
    penalties: Dict[str, float] = dict(shared["penalties"])
    penalties.update(_protein_penalties(product, rows, protein_rows, source_class))

    positive = sum(components.values())
    penalty_total = sum(abs(float(v or 0.0)) for v in penalties.values())
    score = max(0.0, min(DIMENSION_CAP, positive - penalty_total))

    return {
        "score": round(score, 4),
        "max": DIMENSION_CAP,
        "components": components,
        "penalties": penalties,
        "phase": PHASE_MARKER,
        "metadata": {
            "phase": PHASE_MARKER,
            "sports_protein_profile_applied": True,
            "protein_source_class": source_class,
            "protein_rows_evaluated": len(protein_rows),
            "dietary_sugar": shared["metadata"].get("dietary_sugar"),
        },
    }


def _is_protein_context(product: Dict[str, Any]) -> bool:
    taxonomy = _safe_dict((product or {}).get("supplement_taxonomy"))
    ptype = _norm_text(
        (product or {}).get("primary_type")
        or taxonomy.get("primary_type")
        or (product or {}).get("supplement_type")
    )
    category = _norm_text(taxonomy.get("percentile_category"))
    name = _norm_text((product or {}).get("product_name") or (product or {}).get("fullName"))
    return (
        ptype == "protein_powder"
        or category == "protein_powder"
        or primary_sports_identity(product) == "protein"
        or "protein" in name
    )


def _row_text(row: Dict[str, Any]) -> str:
    fields = (
        "name",
        "standard_name",
        "canonical_id",
        "matched_form",
        "form",
        "ingredient_form",
        "raw_source_text",
    )
    return " ".join(_norm_text((row or {}).get(field)) for field in fields)


def _has_any(text: str, terms: Tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _protein_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        text = _row_text(row)
        canon = canonical(row)
        if (
            canon in SPORTS_PROTEIN_CANONICALS
            or _has_any(text, _WHEY_TERMS + _CASEIN_TERMS + _SOY_TERMS + _PEA_TERMS + _RICE_TERMS + _COLLAGEN_TERMS)
        ):
            out.append(row)
    return out


def _source_quality(protein_rows: List[Dict[str, Any]], product: Dict[str, Any]) -> Tuple[float, str]:
    texts = [_row_text(row) for row in protein_rows]
    canons = {canonical(row) for row in protein_rows}
    product_text = _norm_text((product or {}).get("product_name") or (product or {}).get("fullName"))
    combined = " ".join(texts)
    source_text = f"{combined} {product_text}" if "protein" in combined else combined

    if _has_any(source_text, _COLLAGEN_TERMS):
        return 4.0, "collagen_or_gelatin"

    if any(row.get("is_proprietary_blend") for row in protein_rows) and not _has_named_complete_source(canons, source_text):
        return 3.0, "opaque_protein_matrix"

    if _has_any(source_text, _WHEY_ISOLATE_TERMS) or ("whey" in source_text and "isolate" in source_text):
        return 15.0, "whey_isolate"
    if _has_any(source_text, _CASEIN_TERMS) or "casein" in canons:
        return 14.0, "casein"
    if "whey_protein" in canons or _has_any(source_text, _WHEY_TERMS):
        return 13.0, "whey_protein"
    if "soy_protein" in canons or _has_any(source_text, _SOY_TERMS):
        return 13.0, "soy_protein"
    if ("pea_protein" in canons and "rice_protein" in canons) or (
        _has_any(source_text, _PEA_TERMS) and _has_any(source_text, _RICE_TERMS)
    ):
        return 12.0, "complete_plant_blend"
    if "pea_protein" in canons or _has_any(source_text, _PEA_TERMS):
        return 9.0, "single_plant_protein"
    if "rice_protein" in canons or _has_any(source_text, _RICE_TERMS):
        return 8.0, "single_plant_protein"
    return 6.0, "generic_protein"


def _has_named_complete_source(canons: set[str], text: str) -> bool:
    return bool(
        {"whey_protein", "casein", "soy_protein"} & canons
        or _has_any(text, _WHEY_TERMS + _CASEIN_TERMS + _SOY_TERMS)
        or ("pea_protein" in canons and "rice_protein" in canons)
    )


def _dose_transparency(protein_rows: List[Dict[str, Any]], source_class: str) -> float:
    best_g = max((dose_g(row) or 0.0) for row in protein_rows)
    if best_g >= 20.0:
        points = 4.0
    elif best_g >= 10.0:
        points = 2.5
    elif best_g > 0.0:
        points = 1.0
    else:
        points = 0.0

    if source_class not in {"opaque_protein_matrix", "generic_protein"}:
        points += 1.0
    return min(5.0, points)


def _amino_profile_disclosure(rows: List[Dict[str, Any]]) -> float:
    canons = {canonical(row) for row in rows}
    if EAA_CANONICALS.issubset(canons):
        return 3.0
    if BCAA_CANONICALS.issubset(canons):
        return 2.0
    if "l_leucine" in canons:
        return 1.5
    return 0.0


def _protein_focus(rows: List[Dict[str, Any]], source_class: str) -> float:
    if source_class == "collagen_or_gelatin":
        return 1.0
    if source_class == "opaque_protein_matrix":
        return 1.0

    non_accessory = 0
    for row in rows:
        canon = canonical(row)
        if canon in EAA_CANONICALS or canon in BCAA_CANONICALS:
            continue
        if canon in {"vitamin_d", "calcium", "sodium", "potassium"}:
            continue
        if dose_g(row) is not None:
            non_accessory += 1
    if non_accessory <= 2:
        return 4.0
    return 3.0


def _clean_daily_use(product: Dict[str, Any]) -> float:
    dietary = _safe_dict((product or {}).get("dietary_sensitivity_data"))
    sugar = _safe_dict(dietary.get("sugar"))
    sweeteners = _safe_dict(dietary.get("sweeteners"))
    artificial = _safe_list(sweeteners.get("artificial"))
    sugar_alcohols = _safe_list(sweeteners.get("sugar_alcohols"))
    high_glycemic = _safe_list(sweeteners.get("high_glycemic") or sweeteners.get("high_glycemic_sweeteners"))
    level = _norm_text(sugar.get("level"))

    score = 2.0
    if artificial:
        score -= min(2.0, len(artificial) * 1.0)
    if sugar_alcohols:
        score -= 1.0
    if high_glycemic:
        score -= 1.0
    if level == "high":
        score -= 2.0
    elif level == "moderate":
        score -= 1.0
    return max(0.0, min(2.0, score))


def _protein_penalties(
    product: Dict[str, Any],
    rows: List[Dict[str, Any]],
    protein_rows: List[Dict[str, Any]],
    source_class: str,
) -> Dict[str, float]:
    penalties: Dict[str, float] = {
        "sports_artificial_sweeteners": -_artificial_sweetener_penalty(product),
        "sports_opaque_protein_blend": -_opaque_protein_penalty(product, protein_rows, source_class),
        "sports_amino_spiking_risk": -_amino_spiking_penalty(rows, protein_rows, source_class),
        "sports_collagen_not_complete_protein": -_collagen_penalty(source_class),
    }
    return {key: round(value, 4) for key, value in penalties.items() if value < 0}


def _artificial_sweetener_penalty(product: Dict[str, Any]) -> float:
    dietary = _safe_dict((product or {}).get("dietary_sensitivity_data"))
    sweeteners = _safe_dict(dietary.get("sweeteners"))
    artificial = _safe_list(sweeteners.get("artificial"))
    return min(4.0, len(artificial) * 2.0)


def _opaque_protein_penalty(
    product: Dict[str, Any],
    protein_rows: List[Dict[str, Any]],
    source_class: str,
) -> float:
    if source_class == "opaque_protein_matrix":
        return 8.0
    blends = [
        blend
        for blend in _safe_list((product or {}).get("proprietary_blends"))
        if isinstance(blend, dict)
    ]
    if any(row.get("is_proprietary_blend") for row in protein_rows):
        return 6.0
    for blend in blends:
        level = _norm_text(blend.get("disclosure_level"))
        name = _norm_text(blend.get("name"))
        if "protein" in name and level in {"", "none", "partial"}:
            return 8.0
    return 0.0


def _amino_spiking_penalty(
    rows: List[Dict[str, Any]],
    protein_rows: List[Dict[str, Any]],
    source_class: str,
) -> float:
    row_text = " ".join(_row_text(row) for row in rows)
    has_spiking_amino = _has_any(row_text, _SPIKING_TERMS)
    transparent_complete_source = source_class in {
        "whey_isolate",
        "casein",
        "whey_protein",
        "soy_protein",
        "complete_plant_blend",
    }
    if has_spiking_amino and (
        source_class == "opaque_protein_matrix"
        or any(row.get("is_proprietary_blend") for row in protein_rows)
    ):
        return 6.0
    if has_spiking_amino and not transparent_complete_source:
        return 3.0
    return 0.0


def _collagen_penalty(source_class: str) -> float:
    return 8.0 if source_class == "collagen_or_gelatin" else 0.0
