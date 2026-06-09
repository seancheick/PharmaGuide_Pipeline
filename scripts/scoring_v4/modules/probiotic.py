"""v4 Probiotic module — supplement_type=probiotic class.

Per `docs/plans/SCORING_V4_PROPOSAL.md` §4 (dimension weights) and §6
(probiotic per-class rubric line-by-line):

    Dimension          Cap     Subsequent slice that fills it
    -----------------  ----    -------------------------------
    Formulation         25     P2.1 — total CFU 4 + ≥10B 4 + appropriate
                               diversity 4 + clinical strains 5 + delivery 5
                               + prebiotic 3
    Dose                25     P2.2 — per-strain CFU disclosed 10 + adequacy 15
                               (CFU/strain × tier × support level, capped per §6)
    Evidence            20     P2.3 — strain-clinical credit (multiplicative
                               pipeline, cap_per_ingredient 7) + indication
                               relevance 8
    Testing & Trust     15     P2.4 — B4a SKU + B4b GMP + B4c traceability;
                               hard-clamp 15 (reuses generic_trust)
    Transparency        15     P2.5 — strain identities 8 + per-strain CFU 7;
                               minus B2 allergen + B5 opacity (class-aware
                               probiotic 0.4x) + B6 marketing; B3 claims +4
    Total class score  100

Plus two SEPARATE adjustments (§6 line 390):

    Manufacturer Trust         0 to +5    (D1+D2+rollup; reuses generic)
    Manufacturer Violations    0 to -25   (manufacturer_violations.json rules
                                          + severity/recency; reuses generic)

P2.6 state: the probiotic module is complete. All five dimensions,
manufacturer adjustments, and final rubric-score assembly are populated.
The shape is intentionally identical to the generic module breakdown so
downstream tooling can read both classes uniformly.

Per §13 architecture lock, this module does not import from
`score_supplements.py` (v3). Shared infrastructure (DimensionResult,
ManufacturerTrustResult, ManufacturerViolationsResult) is imported from
`scoring_v4.modules.generic` since the breakdown contract is identical
across modules — only the dimension caps and per-dimension sub-rubrics
differ between classes.

The module never raises on malformed input — empty / non-dict products
get the same zero-math skeleton. Real input validation lives in the
completeness gate (Layer 2), which short-circuits before this module
runs in the production pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from scoring_v4.modules.generic import (
    DimensionResult,
    ManufacturerTrustResult,
    ManufacturerViolationsResult,
    VerificationBonusResult,
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
from scoring_v4.modules.safety_hygiene import (
    SafetyHygieneResult,
    score_safety_hygiene_base,
)


PHASE_MARKER = "P2.6_probiotic_final_assembly"


# Dimension caps per §4 line 176, probiotic column.
# Order is rendering order in audit / UI.
DIMENSION_CAPS = (
    ("formulation", 25),
    ("dose", 25),
    ("evidence", 20),
    ("transparency", 15),
)


@dataclass
class ProbioticModuleResult:
    """Container for the probiotic-module breakdown.

    Mirrors `GenericModuleResult` shape so audit / score-delta / Flutter
    tooling can read a single `v4_breakdown["module"]`
    contract regardless of which class scored the product.

    Final assembly (Phase 4) uses the shared generic._assemble_score: core
    dimensions summed on native scale (max 85, NO renormalization) plus the
    additive verification_bonus / manufacturer adjustments / safety_hygiene,
    clamped to [0, 100]. Since Phase 9 this raw rubric score is the
    production score.
    """

    module: str = "probiotic"
    dimensions: Dict[str, DimensionResult] = field(default_factory=dict)
    verification_bonus: VerificationBonusResult = field(default_factory=VerificationBonusResult)
    manufacturer_trust: ManufacturerTrustResult = field(default_factory=ManufacturerTrustResult)
    manufacturer_violations: ManufacturerViolationsResult = field(default_factory=ManufacturerViolationsResult)
    safety_hygiene_base: SafetyHygieneResult = field(default_factory=SafetyHygieneResult)
    botanical_dose_deferred: bool = False
    raw_score_100: Optional[float] = None
    score_100: Optional[float] = None
    phase: str = PHASE_MARKER
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_breakdown(self) -> Dict[str, Any]:
        """Render as the dict shape used in `v4_breakdown["module"]`.
        This is the public contract for audit / score-delta tooling and the
        Flutter score-detail view. Matches `GenericModuleResult.to_breakdown`
        shape so consumers don't need class-aware unpacking."""
        return {
            "module": self.module,
            "dimensions": {name: dim.to_dict() for name, dim in self.dimensions.items()},
            "verification_bonus": self.verification_bonus.to_dict(),
            "manufacturer_trust": self.manufacturer_trust.to_dict(),
            "manufacturer_violations": self.manufacturer_violations.to_dict(),
            "safety_hygiene_base": self.safety_hygiene_base.to_dict(),
            "raw_score_100": self.raw_score_100,
            "score_100": self.score_100,
            "phase": self.phase,
            "metadata": dict(self.metadata),
        }


def _empty_dimensions() -> Dict[str, DimensionResult]:
    """Build the 5-dimension skeleton with caps locked from DIMENSION_CAPS.
    Insertion order matches rendering order in audit / UI."""
    return {name: DimensionResult(max=float(cap)) for name, cap in DIMENSION_CAPS}


def score_probiotic(product: Any) -> ProbioticModuleResult:
    """Score a probiotic-class product against the v4 probiotic rubric.

    P2.6 state: returns a fully-instantiated result with all dimensions,
    manufacturer adjustments, raw score, and production score populated.

    Never raises on malformed input. The completeness gate (Layer 2)
    handles real input validation upstream in the v4 pipeline.

    Args:
        product: Enriched product dict (same contract as v3 consumes).
            Currently unused — present for forward compatibility so
            subsequent slices don't change the signature.

    Returns:
        ProbioticModuleResult with the locked breakdown shape.
    """
    if not isinstance(product, dict):
        product = {}

    result = ProbioticModuleResult(dimensions=_empty_dimensions())
    formulation_payload = score_formulation(product)
    formulation_dim = result.dimensions["formulation"]
    formulation_dim.score = formulation_payload["score"]
    formulation_dim.components = formulation_payload["components"]
    formulation_dim.penalties = formulation_payload["penalties"]
    formulation_dim.metadata = formulation_payload.get("metadata", {})

    dose_payload = score_dose(product)
    dose_dim = result.dimensions["dose"]
    dose_dim.score = dose_payload["score"]
    dose_dim.components = dose_payload["components"]
    dose_dim.penalties = dose_payload["penalties"]
    dose_dim.metadata = dose_payload.get("metadata", {})

    evidence_payload = score_evidence(product)
    evidence_dim = result.dimensions["evidence"]
    evidence_dim.score = evidence_payload["score"]
    evidence_dim.components = evidence_payload["components"]
    evidence_dim.penalties = evidence_payload["penalties"]
    evidence_dim.metadata = evidence_payload.get("metadata", {})

    # P2.4 — Trust dimension reuses the generic B4a/B4b/B4c logic.
    # Probiotic Trust 15 has the same caps and sub-rubrics as generic Trust
    # 15 per §6 line 292-295. No probiotic-specific cert programs exist in
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
