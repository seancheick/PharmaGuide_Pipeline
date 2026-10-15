"""v4 Probiotic Formulation dimension — P2.1.

Scores probiotic formulation with the canonical form-quality owners (V4.1
Step 4): the shared IQM form rating and probiotic-applicable delivery tier.
Per-strain CFU adequacy belongs to P2.2 Dose, strain-clinical evidence to
P2.3 Evidence and CFU/identity disclosure to Transparency.
"""

from __future__ import annotations

import math
from typing import Any, Dict

from scoring_v4.modules.generic_formulation import (
    UNRATED_FORM_NEUTRAL,
    _bio_score_assessment,
    _score_delivery_system,
    shared_formulation_penalty_detail,
)
from scoring_v4.modules.generic_helpers import eligible_delivery_data
from probiotic_measurements import declared_total_cfu, probiotic_label_identity_summary


PHASE_MARKER = "P2.1_probiotic_formulation"
from scoring_v4.quality_score_config import block as _cfg_block

_FVM = _cfg_block("formulation_variant_magnitudes", "probiotic")["probiotic"]


CAP_FORMULATION = _FVM["cap_formulation"]


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


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
    """Return the probiotic Formulation dimension payload (V4.1 Step 4).

    Canonical form quality, as for every other route: the shared IQM rating
    (an unrated form keeps the shared neutral) plus the shared delivery-tier
    points, counted only for a delivery system that actually protects this
    product's probiotic strains. CFU disclosure and strain identity are
    Transparency facts and earn nothing here.
    """
    product = product if isinstance(product, dict) else {}
    pdata = _probiotic_payload(product)

    total_billion = _total_billion_count(pdata)
    identities = probiotic_label_identity_summary(product)
    from probiotic_measurements import is_probiotic_source_identity

    # Form quality belongs to the strains: a rated co-ingredient (an optional
    # prebiotic, a vitamin) cannot supply probiotic form quality (1.20.0).
    bio_score, form_assessed_count = _bio_score_assessment(product, is_probiotic_source_identity)
    if form_assessed_count == 0:
        bio_score = UNRATED_FORM_NEUTRAL
    delivery_data = _probiotic_delivery(product, eligible_delivery_data(product))

    components = {
        "A1_bio_score": round(bio_score, 4),
        "A3_delivery_system": round(_score_delivery_system(delivery_data), 4),
    }
    shared_penalties = shared_formulation_penalty_detail(product)
    penalties = dict(shared_penalties["penalties"])
    penalty_magnitude = sum(abs(float(value or 0.0)) for value in penalties.values())
    raw_score = sum(components.values())
    score = max(0.0, min(CAP_FORMULATION, raw_score - penalty_magnitude))
    metadata = {
        "phase": PHASE_MARKER,
        "delivery_data": delivery_data,
        "iqm_form_quality_assessed_count": form_assessed_count,
        "raw_score": round(raw_score, 4),
        "pre_penalty_score": round(raw_score, 4),
        "total_billion_count": total_billion,
        "total_strain_count": identities["total_strain_count"],
        "identified_strain_count": identities["identified_strain_count"],
        "cap_applied": raw_score > CAP_FORMULATION,
    }
    metadata.update(shared_penalties["metadata"])
    return {
        "score": round(score, 2),
        "max": CAP_FORMULATION,
        "components": components,
        "penalties": penalties,
        "metadata": metadata,
    }


def _total_billion_count(pdata: Dict[str, Any]) -> float:
    return declared_total_cfu(pdata) / 1e9


def _probiotic_delivery(product: Dict[str, Any], delivery_data: Dict[str, Any]) -> Dict[str, Any]:
    """The eligible delivery systems that protect this product's probiotic strains.

    Independent supported delivery and source-specific applicability are both
    required: an unrelated ingredient cannot supply probiotic protection.
    """
    from form_vocab import matches_probiotic_delivery
    from clinical_applicability import _source_delivery_forms
    from studied_formulas import label_owned_strain_identities

    from probiotic_measurements import is_probiotic_source_identity

    rows = [owner for owner, _ in label_owned_strain_identities(product)
            if is_probiotic_source_identity(owner)]
    systems = [
        system for system in (_safe_dict(delivery_data).get("systems") or [])
        if isinstance(system, dict)
        and matches_probiotic_delivery(str(system.get("canonical_name") or system.get("name") or ""))
        and _as_int(system.get("tier"), 0) in (1, 2, 3)
        and any(_source_delivery_forms(
            {**product, "delivery_data": {"systems": [system]}}, row, product_level=True,
        ) for row in rows)
    ]
    tiers = [_as_int(system.get("tier"), 0) for system in systems]
    return {**_safe_dict(delivery_data), "systems": systems,
            "highest_tier": min(tiers) if tiers else None}


def _probiotic_payload(product: Dict[str, Any]) -> Dict[str, Any]:
    """Read enriched-input `probiotic_data` and final-blob `probiotic_detail`.

    The v4 pipeline scores enriched rows, but canary/debug tools often
    call the module directly against shipped detail blobs.
    """
    return _safe_dict(product.get("probiotic_data") or product.get("probiotic_detail"))
