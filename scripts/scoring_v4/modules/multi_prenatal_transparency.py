"""v4 multi/prenatal Transparency dimension (P3.5).

Transparency for broad panels should answer a simple question: can the user
and scorer see what each panel nutrient is and how much is present?

Positive components:
  - panel ingredient identities disclosed   4
  - panel individual doses disclosed        7
  - B3 claim_compliance bonus               up to 4

Penalties reuse the v4 generic Transparency implementation, including the
class-aware B5 multiplier where multi/prenatal proprietary opacity is more
serious than probiotic opacity.

Per §13 architecture lock, this module does not import from
`score_supplements.py` (v3).
"""

from __future__ import annotations

from typing import Any, Dict

from scoring_v4.modules.generic_helpers import (
    _norm_text,
    has_usable_individual_dose,
)
from scoring_v4.modules.generic_transparency import (
    _derive_claim_validations,
    _score_b2_allergen_penalty,
    _score_b3_claim_compliance,
    _score_b5_proprietary_blend_penalty,
    _score_b6_disease_claim_penalty,
)
from scoring_v4.modules.multi_prenatal_formulation import _active_ingredients


PHASE_MARKER = "P3.5_multi_prenatal_transparency"

DIMENSION_CAP = 15.0
CAP_PANEL_IDENTITY_DISCLOSURE = 4.0
CAP_PANEL_INDIVIDUAL_DOSE_DISCLOSURE = 7.0


def score_transparency(product: Any) -> Dict[str, Any]:
    """Compute multi/prenatal Transparency.

    Returns the standard v4 dimension payload and never raises on malformed
    input.
    """
    if not isinstance(product, dict):
        product = {}

    flags: list[str] = []
    b2, b2_meta = _score_b2_allergen_penalty(product)
    allergen_valid, gluten_valid, vegan_valid, claim_flags = _derive_claim_validations(product, b2)
    flags.extend(claim_flags)
    b3 = _score_b3_claim_compliance(
        allergen_free=allergen_valid,
        gluten_free=gluten_valid,
        vegan_or_vegetarian=vegan_valid,
    )
    b5, b5_evidence = _score_b5_proprietary_blend_penalty(product, flags)
    b6 = _score_b6_disease_claim_penalty(product, flags)

    identity_score, identity_meta = _score_panel_identity_disclosure(product)
    dose_score, dose_meta = _score_panel_individual_dose_disclosure(product)

    components = {
        "panel_identity_disclosure": round(identity_score, 4),
        "panel_individual_dose_disclosure": round(dose_score, 4),
        "B3_claim_compliance": round(b3, 4),
    }
    penalties = {
        "B2_allergen_presence": _neg_or_zero(b2),
        "B5_proprietary_blend_opacity": _neg_or_zero(b5),
        "B6_marketing_claims": _neg_or_zero(b6),
    }
    raw_total = (
        sum(float(value) for value in components.values())
        - sum(abs(float(value)) for value in penalties.values())
    )
    score = _clamp(0.0, DIMENSION_CAP, raw_total)

    metadata = {
        "phase": PHASE_MARKER,
        "raw_score": round(raw_total, 4),
        "cap_applied": raw_total > DIMENSION_CAP,
        "floor_applied": raw_total < 0.0,
        "claim_validations": {
            "allergen_free": bool(allergen_valid),
            "gluten_free": bool(gluten_valid),
            "vegan_or_vegetarian": bool(vegan_valid),
        },
        "flags": sorted(set(flags)),
        "B2_raw_before_cap": round(b2_meta["raw_before_cap"], 4),
        "B2_seen_allergens": b2_meta["seen_allergens"],
        "B5_blend_evidence": b5_evidence,
        "B5_blend_count": len(b5_evidence),
        **identity_meta,
        **dose_meta,
    }

    return {
        "score": round(score, 4),
        "max": DIMENSION_CAP,
        "components": components,
        "penalties": penalties,
        "phase": PHASE_MARKER,
        "metadata": metadata,
    }


def _score_panel_identity_disclosure(product: Dict[str, Any]) -> tuple[float, Dict[str, Any]]:
    rows = _active_ingredients(product)
    if not rows:
        return 0.0, {
            "panel_active_count": 0,
            "panel_named_count": 0,
            "panel_identity_coverage": 0.0,
        }

    named_count = sum(1 for row in rows if _has_panel_identity(row))
    coverage = min(1.0, named_count / len(rows))
    return round(CAP_PANEL_IDENTITY_DISCLOSURE * coverage, 4), {
        "panel_active_count": len(rows),
        "panel_named_count": named_count,
        "panel_identity_coverage": round(coverage, 4),
    }


def _score_panel_individual_dose_disclosure(product: Dict[str, Any]) -> tuple[float, Dict[str, Any]]:
    rows = _active_ingredients(product)
    if not rows:
        return 0.0, {
            "panel_dose_count": 0,
            "panel_dose_coverage": 0.0,
        }

    dose_count = sum(1 for row in rows if has_usable_individual_dose(row))
    coverage = min(1.0, dose_count / len(rows))
    return round(CAP_PANEL_INDIVIDUAL_DOSE_DISCLOSURE * coverage, 4), {
        "panel_dose_count": dose_count,
        "panel_dose_coverage": round(coverage, 4),
    }


def _has_panel_identity(row: Dict[str, Any]) -> bool:
    if not isinstance(row, dict):
        return False
    for field in ("canonical_id", "standard_name", "standardName", "name"):
        if _norm_text(row.get(field)):
            return True
    return False


def _neg_or_zero(value: float) -> float:
    if value <= 0:
        return 0.0
    return round(-float(value), 4)


def _clamp(low: float, high: float, value: float) -> float:
    return max(low, min(high, value))
