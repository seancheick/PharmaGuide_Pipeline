"""v4 Probiotic Transparency dimension — P2.5.

Per `docs/plans/SCORING_V4_PROPOSAL.md` §6 line 296-307, probiotic
Transparency 15 has class-specific positive components and reuses the
generic Transparency penalty machinery:

    Positive components (probiotic-specific):
      - all strain identities named on label    8 pts
      - per-strain CFU on label                 7 pts
        (Intentionally double-counts with the Dose dimension per
         §6 line 298 — strong-signal design.)
      - B3 claim_compliance bonus               up to +4
        (allergen_free +2, gluten_free +1, vegan_or_veg +1; reused
         from generic_transparency unchanged.)

    Penalties (reused from generic_transparency):
      - B2 allergen presence                    up to -2
      - B5 opacity (class-aware probiotic 0.4x) up to -5
        (§5 line 255: probiotic with hidden per-strain CFU but
         named strains earns a moderate penalty, not a severe one.)
      - B6 marketing / disease claims           -5

    Final: clamp(0, 15, sum(positives) - sum(|penalties|))

Strain identities (8 pts): credited proportionally. A blend container
("Probiotic Blend") with named children counts the children as named
identities. Empty/unnamed blends drag the credit down.

Per-strain CFU (7 pts): proportional to the disclosure ratio
(disclosed_count / total_strain_count). Reuses the disclosure logic
from `probiotic_dose._per_strain_cfu_disclosed_keys` for consistency.

Per §13 architecture lock, this module does not import from
`score_supplements.py` (v3). Penalty sub-functions are imported from
generic_transparency where v4 already has v3-parity tests (P1.3.5).
"""

from __future__ import annotations

from typing import Any, Dict

from scoring_v4.modules.generic_transparency import (
    _derive_claim_validations,
    _score_b2_allergen_penalty,
    _score_b3_claim_compliance,
    _score_b5_proprietary_blend_penalty,
    _score_b6_disease_claim_penalty,
)
from scoring_v4.modules.probiotic_dose import _per_strain_cfu_disclosed_keys


PHASE_MARKER = "P2.5_probiotic_transparency"

DIMENSION_CAP = 15.0
CAP_STRAIN_IDENTITIES = 8.0
CAP_PER_STRAIN_CFU = 7.0


def score_transparency(product: Any) -> Dict[str, Any]:
    """Compute probiotic Transparency dimension.

    Args:
        product: Enriched product dict. Treated as empty if not a dict.

    Returns:
        Dict with the standard dimension payload shape.
    """
    product = product if isinstance(product, dict) else {}
    pdata = _probiotic_payload(product)

    flags: list = []

    # Reuse penalty machinery + claim validations from generic_transparency.
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

    # Probiotic-specific positive components.
    strain_identities = _score_strain_identities(pdata)
    per_strain_cfu = _score_per_strain_cfu_on_label(pdata)

    components = {
        "strain_identities_named":     round(strain_identities, 4),
        "per_strain_cfu_on_label":     round(per_strain_cfu, 4),
        "B3_claim_compliance":         round(b3, 4),
    }
    penalties = {
        "B2_allergen_presence":            _neg_or_zero(b2),
        "B5_proprietary_blend_opacity":    _neg_or_zero(b5),
        "B6_marketing_claims":             _neg_or_zero(b6),
    }
    raw_total = (
        sum(float(v) for v in components.values())
        - sum(abs(float(v)) for v in penalties.values())
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
        "B5_blend_evidence": b5_evidence,
        "B5_blend_count": len(b5_evidence),
    }

    return {
        "score": round(score, 4),
        "max": DIMENSION_CAP,
        "components": components,
        "penalties": penalties,
        "phase": PHASE_MARKER,
        "metadata": metadata,
    }


def _score_strain_identities(pdata: Dict[str, Any]) -> float:
    """+8 when total_strain_count > 0 AND each blend has at least one
    named strain. Partial credit when some blends are unnamed proprietary
    containers (proportional to named-blend ratio).
    """
    total_strain_count = _as_int(pdata.get("total_strain_count"), 0)
    if total_strain_count <= 0:
        return 0.0

    blends = _safe_list(pdata.get("probiotic_blends"))
    if not blends:
        # No blend list but total_strain_count > 0 — strains must be on
        # clinical_strains; treat as fully named.
        return CAP_STRAIN_IDENTITIES

    named_blend_count = 0
    for blend in blends:
        if not isinstance(blend, dict):
            continue
        strains = [
            str(s).strip()
            for s in _safe_list(blend.get("strains"))
            if str(s or "").strip()
        ]
        if strains:
            named_blend_count += 1

    if named_blend_count == 0:
        return 0.0
    ratio = min(1.0, named_blend_count / len(blends))
    return round(CAP_STRAIN_IDENTITIES * ratio, 4)


def _score_per_strain_cfu_on_label(pdata: Dict[str, Any]) -> float:
    """+7 when all named strains have individual CFU disclosed.
    Proportional credit when only some strains have per-strain CFU.

    Reuses the disclosure-detection logic from probiotic_dose to keep
    consistency between Dose (15 pts) and Transparency (7 pts) per
    §6 line 298 ("intentionally double-counts with the Dose dimension").
    """
    total_strain_count = _as_int(pdata.get("total_strain_count"), 0)
    if total_strain_count <= 0:
        return 0.0

    clinical_strains = _safe_list(pdata.get("clinical_strains"))
    disclosed_keys = _per_strain_cfu_disclosed_keys(pdata, clinical_strains)
    disclosed_count = min(len(disclosed_keys), total_strain_count)
    if disclosed_count <= 0:
        return 0.0
    ratio = min(1.0, disclosed_count / total_strain_count)
    return round(CAP_PER_STRAIN_CFU * ratio, 4)


def _probiotic_payload(product: Dict[str, Any]) -> Dict[str, Any]:
    """Read enriched-input `probiotic_data` and final-blob `probiotic_detail`."""
    return _safe_dict(product.get("probiotic_data") or product.get("probiotic_detail"))


def _neg_or_zero(value: float) -> float:
    if value <= 0:
        return 0.0
    return round(-float(value), 4)


def _clamp(lo: float, hi: float, value: float) -> float:
    return max(lo, min(hi, value))


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default
