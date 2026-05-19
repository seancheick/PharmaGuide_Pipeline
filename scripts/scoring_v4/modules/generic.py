"""v4 Generic module — single-ingredient, simple stacks, omega-3, botanicals.

Per `docs/plans/SCORING_V4_PROPOSAL.md` §4 (dimension weights) and §6
(per-class rubric line-by-line):

    Dimension          Cap     Subsequent slice that fills it
    -----------------  ----    -------------------------------
    Formulation         30     P1.3.1 — bio_score 15 + premium 4 + delivery 3
                               + absorption 3 + excellence 4 + single-ingredient 1
                               + enzyme 2; minus B0 (moderate/watchlist) + B1
                               + dietary sugar
    Dose                25     P1.3.2 — supplemental-window 22 + multi-form 3
                               minus B7 (>150% UL)
    Evidence            20     P1.3.3 — full multiplicative pipeline (study_type
                               * evidence_level * effect_direction * enrollment
                               * dose_guard * top_N + depth_bonus); cap per
                               ingredient = 7
    Testing & Trust     15     P1.3.4 — B4a SKU-verified (scope-aware, config
                               cap 12 with 8/4/2 SKU rungs) + B4b GMP up to 4
                               + B4c traceability up to 1; sub-components are
                               hard-clamped to the 15-point dimension cap
    Transparency        10     P1.3.5 — clear-single base + B3 claim_compliance
                               up to +4; minus B2 allergen + B5 opacity
                               (class-aware) + B6 marketing
    Total class score  100

Plus two SEPARATE adjustments (§6 line 390):

    Manufacturer Trust         0 to +5    (D1+D2+rollup; P1.3.6)
    Manufacturer Violations    0 to -25   (manufacturer_violations.json rules
                                          + severity/recency; P1.3.6)

P1.3.1b state: Formulation is complete; Dose / Evidence / Trust /
Transparency and manufacturer adjustments remain skeleton. Subsequent
P1.3.x slices fill them in-place; the shape never changes. Audit and
score-delta tooling reads against this contract.

The module never raises on malformed input — empty / non-dict products
get the same zero-math skeleton. Real input validation lives in the
completeness gate (Layer 2), which short-circuits before this module
runs in the production pipeline. The module's defensive behavior exists
for test fixtures + direct callers that bypass the gate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from scoring_v4.modules.generic_formulation import score_formulation


PHASE_MARKER = "P1.3.1b_formulation_complete"


# Dimension caps per §4 line 176. Order is rendering order in audit / UI.
DIMENSION_CAPS = (
    ("formulation", 30),
    ("dose", 25),
    ("evidence", 20),
    ("trust", 15),
    ("transparency", 10),
)

MANUFACTURER_TRUST_CAP = 5
MANUFACTURER_VIOLATIONS_FLOOR = -25


@dataclass
class DimensionResult:
    """One of the 5 class dimensions (Formulation, Dose, Evidence, Trust,
    Transparency). `score` is None until the dimension's scoring slice
    lands; `components` records positive sub-line credit (e.g. bio_score 15);
    `penalties` records deductions (e.g. B1_harmful_additives -2.5);
    `metadata` carries phase/deferred-line data that audit tooling needs
    without mixing non-numeric values into components or penalties.
    """

    score: Optional[float] = None
    max: float = 0.0
    components: Dict[str, float] = field(default_factory=dict)
    penalties: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "max": self.max,
            "components": dict(self.components),
            "penalties": dict(self.penalties),
            "metadata": dict(self.metadata),
        }


@dataclass
class ManufacturerTrustResult:
    """Separate +5 dimension (§6 line 390). D1 reputation + D2 disclosure +
    D3/D4/D5 rollup. Populated by P1.3.6."""

    score: Optional[float] = None
    max: float = MANUFACTURER_TRUST_CAP
    components: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "max": self.max,
            "components": dict(self.components),
        }


@dataclass
class ManufacturerViolationsResult:
    """Separate 0 to -25 adjustment (§6 line 401). NOT inside the +15
    Trust cap — it's an independent dimension at the -25 scale. Populated
    by P1.3.6 from `manufacturer_violations.json` rules."""

    score: Optional[float] = None
    floor: float = MANUFACTURER_VIOLATIONS_FLOOR
    components: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "floor": self.floor,
            "components": dict(self.components),
        }


@dataclass
class GenericModuleResult:
    """Container for the generic-module breakdown.

    Final score assembly (P1.3.6):

        class_subtotal = sum(d.score for d in dimensions.values())   # capped at 100
        adjusted = class_subtotal + manufacturer_trust.score + manufacturer_violations.score
        score_100 = max(0, min(100, adjusted))

    `phase` lets audit / delta tooling know which dimensions are populated.
    Removed (or rolled forward) once full math is online at P1.5.
    """

    module: str = "generic"
    dimensions: Dict[str, DimensionResult] = field(default_factory=dict)
    manufacturer_trust: ManufacturerTrustResult = field(default_factory=ManufacturerTrustResult)
    manufacturer_violations: ManufacturerViolationsResult = field(default_factory=ManufacturerViolationsResult)
    score_100: Optional[float] = None
    phase: str = PHASE_MARKER

    def to_breakdown(self) -> Dict[str, Any]:
        """Render as the dict shape used in `shadow_score_v4_breakdown["module"]`.
        This is the public contract for audit / score-delta tooling and the
        Flutter score-detail view."""
        return {
            "module": self.module,
            "dimensions": {name: dim.to_dict() for name, dim in self.dimensions.items()},
            "manufacturer_trust": self.manufacturer_trust.to_dict(),
            "manufacturer_violations": self.manufacturer_violations.to_dict(),
            "score_100": self.score_100,
            "phase": self.phase,
        }


def _empty_dimensions() -> Dict[str, DimensionResult]:
    """Build the 5-dimension skeleton with caps locked from DIMENSION_CAPS.
    Insertion order matches rendering order in audit / UI."""
    return {name: DimensionResult(max=float(cap)) for name, cap in DIMENSION_CAPS}


def score_generic(product: Any) -> GenericModuleResult:
    """Score a generic-class product against the v4 rubric.

    P1.3.1b state: Formulation dimension fully scored. Dose /
    Evidence / Trust / Transparency still skeleton (None scores).
    score_100 stays None until P1.3.6 final assembly.

    Never raises on malformed input. The completeness gate (Layer 2)
    handles real input validation upstream in the shadow pipeline.

    Args:
        product: Enriched product dict (same contract as v3 consumes).

    Returns:
        GenericModuleResult with the locked breakdown shape. The
        formulation dimension's `score` is final for that dimension; other
        dimensions remain None.
    """
    if not isinstance(product, dict):
        product = {}

    result = GenericModuleResult(dimensions=_empty_dimensions())

    # Layer 3 — Formulation dimension (P1.3.1b complete). Subsequent slices
    # populate the other 4 dimensions and manufacturer + violations.
    formulation_payload = score_formulation(product)
    formulation_dim = result.dimensions["formulation"]
    formulation_dim.score = formulation_payload["score"]
    formulation_dim.components = formulation_payload["components"]
    formulation_dim.penalties = formulation_payload["penalties"]
    formulation_dim.metadata = formulation_payload.get("metadata", {})

    # Module-level phase reflects the most-recent slice landed. Audit
    # tooling reads this to know whether to trust the per-dimension
    # scores. Formulation is complete; the overall module score remains
    # unavailable until P1.3.6 final assembly.
    result.phase = PHASE_MARKER

    return result
