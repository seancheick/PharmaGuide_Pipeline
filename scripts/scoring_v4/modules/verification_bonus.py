"""V4 verification bonus — Phase 4 (Trust → Verification Bonus).

Converts the former 0-15 Testing & Trust DIMENSION into an additive
verification BONUS (0-8), like ``manufacturer_trust``. It scores the SAME
verification signals (B4a-d via the module-appropriate trust scorer) but
bounded and additive instead of sitting inside the 100-pt denominator — so an
uncertified clean product is no longer penalised by a missing dimension.

Mechanism (per the locked design): delegate to the module's existing trust
scorer (``generic_trust`` for generic/sports/probiotic/multi, ``omega_trust``
for omega — both clamp the dimension at 15) and linear-rescale the 0-15 result
by 8/15. Rescale (not hard-clamp) preserves the per-cert diminishing-returns
gradation. Parity is therefore PER-MODULE: ``bonus == round(trust_score*8/15)``
for that module's own scorer (generic and omega scorers are structurally
different and are NOT expected to agree cross-module).

Spec: docs/superpowers/specs/2026-05-31-v4-verification-bonus-design.md
"""
from __future__ import annotations

from typing import Any, Dict

VERIFICATION_BONUS_CAP = 8.0
_TRUST_DIMENSION_CAP = 15.0
_RESCALE = VERIFICATION_BONUS_CAP / _TRUST_DIMENSION_CAP  # 8/15 ≈ 0.5333


def _trust_payload(product: Dict[str, Any], module: str) -> Dict[str, Any]:
    """Delegate to the module-appropriate trust scorer (lazy import avoids any
    module-load cycles; both scorers clamp their result at 15)."""
    if module == "omega":
        from scoring_v4.modules.omega_trust import score_trust
    else:
        from scoring_v4.modules.generic_trust import score_trust
    return score_trust(product)


def score_verification_bonus(product: Dict[str, Any], module: str) -> Dict[str, Any]:
    """Return the additive verification bonus (0-8) for ``product``.

    The returned ``components`` are the original 0-15-scale B4a-d sub-scores
    (kept for audit transparency); ``score`` is the rescaled, bounded bonus that
    assembly adds to the core. ``metadata.source_trust_score_0_15`` records the
    pre-rescale total so the transform is fully auditable.
    """
    trust = _trust_payload(product, module)
    trust_score = float(trust.get("score") or 0.0)
    bonus = round(min(VERIFICATION_BONUS_CAP, max(0.0, trust_score * _RESCALE)), 4)
    return {
        "score": bonus,
        "max": VERIFICATION_BONUS_CAP,
        "components": trust.get("components", {}),
        "penalties": trust.get("penalties", {}),
        "metadata": {
            "phase": "P1.4.0_verification_bonus",
            "source_trust_score_0_15": round(trust_score, 4),
            "rescale_factor": round(_RESCALE, 6),
            "trust_module": "omega" if module == "omega" else "generic",
            "trust_metadata": trust.get("metadata", {}),
        },
    }
