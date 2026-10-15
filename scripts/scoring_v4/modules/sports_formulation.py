"""v4 sports protein formulation adapter.

The generic formulation scorer under-recognizes protein powders because it is
built around vitamin/mineral form quality and broad supplement composition.
This adapter keeps the shared safety/sugar penalties (the only sugar and
sweetener charge, 1.21.4) and scores protein powders on protein source
quality. V4.1 Step 4 retired the dose-transparency and amino-profile disclosure
credits (Transparency owns disclosure) and the focus and route-base bonuses.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from scoring_v4.modules.generic_formulation import (
    score_formulation as score_generic_formulation,
    shared_formulation_penalty_detail,
)
from scoring_v4.modules.generic_helpers import (
    _norm_text,
    get_active_ingredients,
)
from scoring_v4.modules.sports_helpers import (
    SPORTS_PROTEIN_CANONICALS,
    canonical,
    primary_sports_identity,
    sports_subtype,
)


from scoring_v4.quality_score_config import block as _cfg_block

_FVM = _cfg_block("formulation_variant_magnitudes", "sports")["sports"]


DIMENSION_CAP = _FVM["dimension_cap"]
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

    components: Dict[str, float] = {
        "sports_protein_source_quality": round(source_quality, 4),
    }

    shared = shared_formulation_penalty_detail(product)
    penalties: Dict[str, float] = dict(shared["penalties"])
    penalties.update(_protein_penalties(rows, protein_rows, source_class))

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
            # Spread the WHOLE shared metadata rather than cherry-picking
            # one key. Picking only "dietary_sugar" silently dropped
            # "inactive_penalty_details" -- the ledger build_final_db needs
            # to colour "Other ingredients" dots. 5,116 products carried a
            # real B1 harmful-additive charge while shipping an empty
            # ledger, so every one of their additive dots rendered green.
            **shared["metadata"],
        },
    }


def _is_protein_context(product: Dict[str, Any]) -> bool:
    """Consume the shared sports purpose result rather than reinterpret it."""
    # Calibration subtype can be stimulant while the shared purpose is protein.
    return primary_sports_identity(product) == "protein" or sports_subtype(product) == "protein"


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


def _protein_penalties(
    rows: List[Dict[str, Any]],
    protein_rows: List[Dict[str, Any]],
    source_class: str,
) -> Dict[str, float]:
    penalties: Dict[str, float] = {
        "sports_amino_spiking_risk": -_amino_spiking_penalty(rows, protein_rows, source_class),
        "sports_collagen_not_complete_protein": -_collagen_penalty(source_class),
    }
    return {key: round(value, 4) for key, value in penalties.items() if value < 0}


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
