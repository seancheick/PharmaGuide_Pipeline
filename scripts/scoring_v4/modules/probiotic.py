"""v4 Probiotic module — supplement_type=probiotic class.

Per `docs/plans/SCORING_V4_PROPOSAL.md` §4 (dimension weights) and §6
(probiotic per-class rubric line-by-line):

    Core dimension      Cap     Subsequent slice that fills it
    ------------------  ----    -------------------------------
    Formulation         15     total potency disclosure 4 + exact label identity
                               completeness 8 + delivery 3
    Dose                25     P2.2 — per-strain CFU disclosed 10 + adequacy 15
                               (source-owned daily potency; aggregate presence
                                does not manufacture strain-level doses)
    Evidence            20     P2.3 — strain-clinical credit (multiplicative
                               pipeline, cap_per_ingredient 7) + indication
                               relevance 8
    Transparency        15     P2.5 — strain identities 8 + per-strain CFU 7;
                               minus B2 allergen + B5 opacity (class-aware
                               probiotic 0.4x) + B6 marketing; B3 claims checked, 0 points
    Core subtotal       75

Plus separate adjustments before the raw-score clamp:

    Verification Bonus         0 to +8    (P2.4 B4a/B4b/B4c signals, rescaled
                                          from the former 0-15 Trust dimension)
    Manufacturer Trust         0 to +5    (D1+D2+rollup; reuses generic)
    Manufacturer Violations    0 to -25   (manufacturer_violations.json rules
                                          + severity/recency; reuses generic)
    Safety Hygiene Base        0 to +4    (catalog safety-signal absence)

P2.6 state: the probiotic module is complete. All four core dimensions,
the additive verification/manufacturer/safety adjustments, and final raw
rubric-score assembly are populated. The public six-pillar score is assembled
separately by `scoring_v4.quality_score`. The breakdown shape is intentionally
identical to the generic module so downstream tooling can read both classes
uniformly.

Per §13 architecture lock, this module does not import from
`score_supplements.py` (v3). Shared infrastructure (DimensionResult and
the one ModuleResult) is imported from `scoring_v4.modules.generic` since
the breakdown contract is identical across modules — only the dimension caps
and per-dimension sub-rubrics differ between classes.

The module never raises on malformed input — empty / non-dict products
get the same zero-math skeleton. Real input validation lives in the
completeness gate (Layer 2), which short-circuits before this module
runs in the production pipeline.
"""

from __future__ import annotations

from scoring_v4.modules.generic_helpers import score_declared_serving_dose

from typing import Any, Dict

from scoring_v4.modules.generic import (
    DimensionResult,
    ModuleResult,
    _assemble_score,
)
from scoring_v4.modules.generic_manufacturer import (
    score_manufacturer_trust,
    score_manufacturer_violations,
)
from scoring_v4.modules.verification_bonus import score_verification_bonus
from scoring_v4.modules.probiotic_dose import score_dose
from scoring_v4.modules.probiotic_evidence import score_evidence
from scoring_v4.modules.probiotic_formulation import score_formulation
from scoring_v4.modules.probiotic_transparency import score_transparency
from scoring_v4.modules.safety_hygiene import score_safety_hygiene_base


PHASE_MARKER = "P2.6_probiotic_final_assembly"


# Dimension caps per §4 line 176, probiotic column.
# Order is rendering order in audit / UI.
from scoring_v4.quality_score_config import block as _cfg_block

_CM = _cfg_block("category_magnitudes", "probiotic")["probiotic"]


DIMENSION_CAPS = tuple((n, c) for n, c in _CM["dimension_caps"])


def _empty_dimensions() -> Dict[str, DimensionResult]:
    """Build the 4-dimension skeleton with caps locked from DIMENSION_CAPS.
    Insertion order matches rendering order in audit / UI."""
    return {name: DimensionResult(max=float(cap)) for name, cap in DIMENSION_CAPS}


def score_probiotic(product: Any) -> ModuleResult:
    """Score a probiotic-class product against the v4 probiotic rubric.

    P2.6 state: returns a fully-instantiated result with all dimensions,
    manufacturer adjustments, raw score, and production score populated.

    Never raises on malformed input. The completeness gate (Layer 2)
    handles real input validation upstream in the v4 pipeline.

    Args:
        product: Enriched product dict consumed by all four dimension scorers.

    Returns:
        ModuleResult with the locked breakdown shape.
    """
    if not isinstance(product, dict):
        product = {}

    result = ModuleResult(module="probiotic", phase=PHASE_MARKER, dimensions=_empty_dimensions())
    formulation_payload = score_formulation(product)
    formulation_dim = result.dimensions["formulation"]
    formulation_dim.score = formulation_payload["score"]
    formulation_dim.components = formulation_payload["components"]
    formulation_dim.penalties = formulation_payload["penalties"]
    formulation_dim.metadata = formulation_payload.get("metadata", {})

    dose_payload = score_declared_serving_dose(product, score_dose)
    dose_dim = result.dimensions["dose"]
    dose_dim.score = dose_payload["score"]
    dose_dim.components = dose_payload["components"]
    dose_dim.penalties = dose_payload["penalties"]
    dose_dim.metadata = dose_payload.get("metadata", {})
    if dose_dim.score is None:
        # Production readiness stops this earlier. Direct module audits must
        # also preserve an unresolved assessment instead of summing it as zero.
        result.metadata["score_unavailable_reason"] = dose_dim.metadata.get("reason_code")
        return result

    evidence_payload = score_evidence(product)
    evidence_dim = result.dimensions["evidence"]
    evidence_dim.score = evidence_payload["score"]
    evidence_dim.components = evidence_payload["components"]
    evidence_dim.penalties = evidence_payload["penalties"]
    evidence_dim.metadata = evidence_payload.get("metadata", {})

    # P2.4 — the additive verification bonus reuses the generic B4a/B4b/B4c
    # source logic, rescaled from its historical 0-15 audit range to 0-8.
    # No probiotic-specific cert programs exist in
    # the catalog today (NSF/USP/Informed are class-agnostic; IFOS is gated
    # marine-only via _is_omega_like and correctly filtered for probiotics).
    # The cross-module `brand_only` / `needs_review` scope policy question
    # is tracked separately as P1.7.
    vb_payload = score_verification_bonus(product, "probiotic")
    result.verification_bonus.score = vb_payload["score"]
    result.verification_bonus.max = vb_payload["max"]
    result.verification_bonus.components = vb_payload["components"]
    result.verification_bonus.penalties = vb_payload.get("penalties", {})
    result.verification_bonus.metadata = vb_payload.get("metadata", {})

    # P2.5 — Transparency dimension. Probiotic-specific positive components
    # (strain identities 8, per-strain CFU 7) with B3 reuse from generic
    # plus B2/B5/B6 penalty reuse. B5 class-aware multiplier (probiotic 0.4x)
    # is applied inside the shared `_score_b5_proprietary_blend_penalty`
    # via _b5_class_for_product detecting probiotic supp_type.
    transparency_payload = score_transparency(product)
    transparency_dim = result.dimensions["transparency"]
    transparency_dim.score = transparency_payload["score"]
    transparency_dim.components = transparency_payload["components"]
    transparency_dim.penalties = transparency_payload["penalties"]
    transparency_dim.metadata = transparency_payload.get("metadata", {})

    # P2.6 — Manufacturer Trust (+0..+5) and Manufacturer Violations
    # (0..-25, escalating to -35/-50 with multiple recent Class-I
    # violations). Reuses the generic helpers verbatim — Manufacturer
    # dimensions are module-agnostic per §6 line 390.
    mt_payload = score_manufacturer_trust(product)
    result.manufacturer_trust.score = mt_payload["score"]
    result.manufacturer_trust.max = mt_payload["max"]
    result.manufacturer_trust.components = mt_payload["components"]
    result.manufacturer_trust.metadata = mt_payload.get("metadata", {})

    mv_payload = score_manufacturer_violations(product)
    result.manufacturer_violations.score = mv_payload["score"]
    result.manufacturer_violations.floor = mv_payload["floor"]
    result.manufacturer_violations.components = mv_payload["components"]
    result.manufacturer_violations.metadata = mv_payload.get("metadata", {})
    result.safety_hygiene_base = score_safety_hygiene_base(product)

    # Phase 4: shared assembly (generic._assemble_score) — single source of
    # truth. Reset the module phase marker the shared assembler stamped.
    _assemble_score(result)
    result.metadata["phase"] = PHASE_MARKER
    result.phase = PHASE_MARKER
    return result
