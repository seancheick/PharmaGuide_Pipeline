"""v4 Probiotic module — supplement_type=probiotic class.

Per `docs/plans/SCORING_V4_PROPOSAL.md` §4 (dimension weights) and §6
(probiotic per-class rubric line-by-line):

    Dimension          Cap     Subsequent slice that fills it
    -----------------  ----    -------------------------------
    Formulation         25     P2.1 — total CFU 4 + ≥10B 4 + named species 4
                               + clinical strains 4 + delivery 4 + prebiotic 5
    Dose                25     P2.2 — per-strain CFU disclosed 15 + adequacy 10
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

P2.3 state: Formulation, Dose, and Evidence are populated; Trust and
Transparency remain skeletons. Subsequent P2.x slices fill them in-place;
the shape never changes.

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
)
from scoring_v4.modules.generic_trust import score_trust
from scoring_v4.modules.probiotic_dose import score_dose
from scoring_v4.modules.probiotic_evidence import score_evidence
from scoring_v4.modules.probiotic_formulation import score_formulation


PHASE_MARKER = "P2.4_probiotic_trust"


# Dimension caps per §4 line 176, probiotic column.
# Order is rendering order in audit / UI.
DIMENSION_CAPS = (
    ("formulation", 25),
    ("dose", 25),
    ("evidence", 20),
    ("trust", 15),
    ("transparency", 15),
)


@dataclass
class ProbioticModuleResult:
    """Container for the probiotic-module breakdown.

    Mirrors `GenericModuleResult` shape so audit / score-delta / Flutter
    tooling can read a single `shadow_score_v4_breakdown["module"]`
    contract regardless of which class scored the product.

    Final score assembly (P2.6) — same pattern as P1.3.6 generic:

        class_subtotal = (sum(d.score for d in dimensions.values()) /
                          sum_of_evaluable_max) * 100   # rescale around None dims
        adjusted = class_subtotal + manufacturer_trust.score
                                  + manufacturer_violations.score
        raw_score_100 = clamp(0, 100, adjusted)
        score_100     = P1.5 calibration applied to raw_score_100
                        (TBD: probiotic-specific calibration may differ
                         from generic affine; reviewed during P2.6
                         against probiotic canary set).
    """

    module: str = "probiotic"
    dimensions: Dict[str, DimensionResult] = field(default_factory=dict)
    manufacturer_trust: ManufacturerTrustResult = field(default_factory=ManufacturerTrustResult)
    manufacturer_violations: ManufacturerViolationsResult = field(default_factory=ManufacturerViolationsResult)
    raw_score_100: Optional[float] = None
    score_100: Optional[float] = None
    phase: str = PHASE_MARKER
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_breakdown(self) -> Dict[str, Any]:
        """Render as the dict shape used in `shadow_score_v4_breakdown["module"]`.
        This is the public contract for audit / score-delta tooling and the
        Flutter score-detail view. Matches `GenericModuleResult.to_breakdown`
        shape so consumers don't need class-aware unpacking."""
        return {
            "module": self.module,
            "dimensions": {name: dim.to_dict() for name, dim in self.dimensions.items()},
            "manufacturer_trust": self.manufacturer_trust.to_dict(),
            "manufacturer_violations": self.manufacturer_violations.to_dict(),
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

    P2.4 state: returns a fully-instantiated result with Formulation, Dose,
    Evidence, and Trust populated; Transparency remains skeleton.
    Subsequent P2.x slices populate `components`, `penalties`, and `score`
    per dimension.

    Never raises on malformed input. The completeness gate (Layer 2)
    handles real input validation upstream in the shadow pipeline.

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
    trust_payload = score_trust(product)
    trust_dim = result.dimensions["trust"]
    trust_dim.score = trust_payload["score"]
    trust_dim.components = trust_payload["components"]
    trust_dim.penalties = trust_payload["penalties"]
    trust_dim.metadata = trust_payload.get("metadata", {})

    result.phase = PHASE_MARKER
    return result
