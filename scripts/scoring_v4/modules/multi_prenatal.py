"""v4 Multi / prenatal module — P3.

Per `docs/plans/SCORING_V4_PROPOSAL.md` §4, broad multivitamin and
prenatal products use a different weight profile from generic
single-ingredient products:

    Dimension          Cap     Subsequent slice that fills it
    -----------------  ----    -------------------------------
    Formulation         25     P3.1 — panel form quality, prenatal-critical
                               nutrient form checks, gummy/formulation limits
    Dose                30     P3.2 — RDA/AI coverage, UL safety, prenatal
                               critical nutrient adequacy floors
    Evidence            15     P3.3 — nutrient-outcome support and class
                               evidence, lower cap than generic
    Testing & Trust     15     P3.4 — B4a SKU + B4b GMP + B4c traceability
    Transparency        15     P3.5 — panel disclosure, blend opacity, claims,
                               allergens, marketing penalties
    Total class score  100

P3.5 state: all five class dimensions are populated; final score assembly,
manufacturer adjustments, verdict, and confidence land in P3.6. Later P3
slices populate the existing dictionaries in place so downstream audit /
Flutter consumers do not chase shape changes.

Per §13 architecture lock, this module does not import from
`score_supplements.py` (v3). It reuses the shared v4 breakdown dataclasses
from `scoring_v4.modules.generic` because the public shape is identical
across modules; only weights and sub-rubrics differ.
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
from scoring_v4.modules.multi_prenatal_dose import score_dose
from scoring_v4.modules.multi_prenatal_evidence import score_evidence
from scoring_v4.modules.multi_prenatal_formulation import score_formulation
from scoring_v4.modules.multi_prenatal_transparency import score_transparency


PHASE_MARKER = "P3.5_multi_prenatal_transparency"


# Dimension caps per §4, multi/prenatal column. Order is rendering order in
# audit / UI and should remain stable across P3 slices.
DIMENSION_CAPS = (
    ("formulation", 25),
    ("dose", 30),
    ("evidence", 15),
    ("trust", 15),
    ("transparency", 15),
)


@dataclass
class MultiPrenatalModuleResult:
    """Container for the multi/prenatal-module breakdown.

    Mirrors GenericModuleResult / ProbioticModuleResult shape so consumers
    can read `shadow_score_v4_breakdown["module"]` uniformly regardless of
    class. P3.5 populates all five dimensions and leaves downstream math
    unset.
    """

    module: str = "multi_or_prenatal"
    dimensions: Dict[str, DimensionResult] = field(default_factory=dict)
    manufacturer_trust: ManufacturerTrustResult = field(default_factory=ManufacturerTrustResult)
    manufacturer_violations: ManufacturerViolationsResult = field(default_factory=ManufacturerViolationsResult)
    raw_score_100: Optional[float] = None
    score_100: Optional[float] = None
    phase: str = PHASE_MARKER
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_breakdown(self) -> Dict[str, Any]:
        """Render as the public shadow-breakdown dict contract."""
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
    return {name: DimensionResult(max=float(cap)) for name, cap in DIMENSION_CAPS}


def score_multi_prenatal(product: Any) -> MultiPrenatalModuleResult:
    """Score a multi/prenatal-class product against the current P3 state.

    Never raises on malformed input. Layer 2 completeness owns production
    eligibility; this defensive behavior supports tests and direct callers
    that bypass the pipeline.
    """
    if not isinstance(product, dict):
        product = {}

    result = MultiPrenatalModuleResult(
        dimensions=_empty_dimensions(),
        metadata={
            "module_state": "dimensions_complete",
            "deferred_slices": [
                "P3.6_final_assembly",
            ],
        },
    )

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

    trust_payload = score_trust(product)
    trust_dim = result.dimensions["trust"]
    trust_dim.score = trust_payload["score"]
    trust_dim.components = trust_payload["components"]
    trust_dim.penalties = trust_payload["penalties"]
    trust_dim.metadata = trust_payload.get("metadata", {})

    transparency_payload = score_transparency(product)
    transparency_dim = result.dimensions["transparency"]
    transparency_dim.score = transparency_payload["score"]
    transparency_dim.components = transparency_payload["components"]
    transparency_dim.penalties = transparency_payload["penalties"]
    transparency_dim.metadata = transparency_payload.get("metadata", {})
    return result
