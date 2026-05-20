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

P3.2 state: Formulation and Dose are populated; Evidence, Trust, and
Transparency remain scaffolded. Later P3 slices populate the existing
dictionaries in place so downstream audit / Flutter consumers do not chase
shape changes.

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
from scoring_v4.modules.multi_prenatal_dose import score_dose
from scoring_v4.modules.multi_prenatal_formulation import score_formulation


PHASE_MARKER = "P3.2_multi_prenatal_dose"


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
    class. P3.2 populates Formulation + Dose and leaves downstream math unset.
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
            "module_state": "dose_partial",
            "deferred_slices": [
                "P3.3_evidence",
                "P3.4_trust",
                "P3.5_transparency",
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
    return result
