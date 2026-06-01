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

P1.5 state: Formulation (P1.3.1b), Dose (P1.3.2a proxy), Evidence
(P1.3.3 multiplicative pipeline), Testing & Trust (P1.3.4), and
Transparency (P1.3.5) are online, with Manufacturer Trust / Violations
and final score assembly now wired. Final display score uses the P1.5
affine calibration `25 + 0.75 * raw_score_100` to correct canary score
compression without changing dimension math. Dose uses an
RDA/UL proxy because the supplemental-window math per §6 line 369 needs
a `typical_dietary_intake` reference table that does not yet exist; the
dose dimension's `metadata` carries explicit proxy markers so downstream
tooling never mistakes the proxy band for final NIH/NHANES window math.
Audit and score-delta tooling reads against this contract.

The module never raises on malformed input — empty / non-dict products
get the same zero-math skeleton. Real input validation lives in the
completeness gate (Layer 2), which short-circuits before this module
runs in the production pipeline. The module's defensive behavior exists
for test fixtures + direct callers that bypass the gate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from scoring_v4.modules.generic_dose import score_dose
from scoring_v4.modules.generic_evidence import score_evidence
from scoring_v4.modules.generic_formulation import score_formulation
from scoring_v4.modules.generic_manufacturer import (
    score_manufacturer_trust,
    score_manufacturer_violations,
)
from scoring_v4.modules.generic_transparency import score_transparency
from scoring_v4.modules.verification_bonus import score_verification_bonus
from scoring_v4.modules.safety_hygiene import (
    SafetyHygieneResult,
    score_safety_hygiene_base,
)


PHASE_MARKER = "P1.5_affine_calibration"
CALIBRATION_INTERCEPT = 25.0
CALIBRATION_SLOPE = 0.75
CALIBRATION_METHOD = "affine_p15"


# Core dimension caps. Order is rendering order in audit / UI.
# Phase 4 (Trust→Verification Bonus): the former ("trust", 15) DIMENSION was
# removed from the denominator and converted to an additive verification_bonus
# (0-8). Core now sums to 85; verification is added like manufacturer_trust.
DIMENSION_CAPS = (
    ("formulation", 30),
    ("dose", 25),
    ("evidence", 20),
    ("transparency", 10),
)

MANUFACTURER_TRUST_CAP = 5
MANUFACTURER_VIOLATIONS_FLOOR = -25
# Phase 4 botanical guard: a botanical whose dose dimension is non-evaluable
# must not be stamped POOR purely from removing the old renormalization, before
# Phase 6's botanical dose adapter lands. Floors raw at the SAFE/POOR boundary.
BOTANICAL_RAW_FLOOR = 40.0


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
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "max": self.max,
            "components": dict(self.components),
            "metadata": dict(self.metadata),
        }


@dataclass
class ManufacturerViolationsResult:
    """Separate 0 to -25 adjustment (§6 line 401). NOT inside the +15
    Trust cap — it's an independent dimension at the -25 scale. Populated
    by P1.3.6 from `manufacturer_violations.json` rules."""

    score: Optional[float] = None
    floor: float = MANUFACTURER_VIOLATIONS_FLOOR
    components: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "floor": self.floor,
            "components": dict(self.components),
            "metadata": dict(self.metadata),
        }


@dataclass
class VerificationBonusResult:
    """Additive verification bonus (0-8), Phase 4. Replaces the former 0-15
    Testing & Trust dimension; scores the same B4a-d signals (via the module's
    trust scorer) rescaled ×8/15 and added like manufacturer_trust rather than
    sitting in the denominator. `components` are the original 0-15-scale sub-scores
    (audit); `score` is the bounded bonus assembly adds."""

    score: float = 0.0
    max: float = 8.0
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
class GenericModuleResult:
    """Container for the generic-module breakdown.

    Final score assembly (Phase 4 — Trust→Verification Bonus):

        core_subtotal = sum(d.score for d in dimensions.values())   # NATIVE, max 85, NO renorm
        adjusted = core_subtotal + verification_bonus.score + manufacturer_trust.score
                   + manufacturer_violations.score + safety_hygiene_base.score
        raw_score_100 = max(0, min(100, adjusted))   # botanical floor may apply
        score_100 = affine-calibrated raw_score_100

    `phase` lets audit / delta tooling know which dimensions are populated.
    """

    module: str = "generic"
    dimensions: Dict[str, DimensionResult] = field(default_factory=dict)
    verification_bonus: VerificationBonusResult = field(default_factory=VerificationBonusResult)
    manufacturer_trust: ManufacturerTrustResult = field(default_factory=ManufacturerTrustResult)
    manufacturer_violations: ManufacturerViolationsResult = field(default_factory=ManufacturerViolationsResult)
    safety_hygiene_base: SafetyHygieneResult = field(default_factory=SafetyHygieneResult)
    # Phase 4 botanical guard flag: set by the module when the dose dimension is
    # non-evaluable for a botanical, so assembly floors raw out of POOR until Phase 6.
    botanical_dose_deferred: bool = False
    raw_score_100: Optional[float] = None
    score_100: Optional[float] = None
    phase: str = PHASE_MARKER
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_breakdown(self) -> Dict[str, Any]:
        """Render as the dict shape used in `shadow_score_v4_breakdown["module"]`.
        This is the public contract for audit / score-delta tooling and the
        Flutter score-detail view."""
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
    """Build the core-dimension skeleton with caps locked from DIMENSION_CAPS.
    Insertion order matches rendering order in audit / UI."""
    return {name: DimensionResult(max=float(cap)) for name, cap in DIMENSION_CAPS}


def score_generic(product: Any) -> GenericModuleResult:
    """Score a generic-class product against the v4 rubric.

    P1.5 state: Formulation, Dose, Evidence, Trust, Transparency,
    Manufacturer Trust, Manufacturer Violations, raw_score_100, and
    calibrated score_100 are populated.

    Never raises on malformed input. The completeness gate (Layer 2)
    handles real input validation upstream in the shadow pipeline.

    Args:
        product: Enriched product dict (same contract as v3 consumes).

    Returns:
        GenericModuleResult with the locked breakdown shape. The
        populated dimensions have phase metadata; skeleton dimensions
        remain None until their slice lands.
    """
    if not isinstance(product, dict):
        product = {}

    result = GenericModuleResult(dimensions=_empty_dimensions())

    # Layer 3 — Formulation dimension (P1.3.1b complete).
    formulation_payload = score_formulation(product)
    formulation_dim = result.dimensions["formulation"]
    formulation_dim.score = formulation_payload["score"]
    formulation_dim.components = formulation_payload["components"]
    formulation_dim.penalties = formulation_payload["penalties"]
    formulation_dim.metadata = formulation_payload.get("metadata", {})

    # Layer 3 — Dose dimension (P1.3.2a proxy). The dose breakdown carries
    # explicit proxy-method metadata; the metadata is the contract that tells
    # audit / score-delta / Flutter tooling not to mistake the proxy band
    # for final NIH/NHANES supplemental-window math.
    dose_payload = score_dose(product)
    dose_dim = result.dimensions["dose"]
    dose_dim.score = dose_payload["score"]
    dose_dim.components = dose_payload["components"]
    dose_dim.penalties = dose_payload["penalties"]
    dose_dim.metadata = dose_payload.get("metadata", {})

    # Layer 3 — Evidence dimension (P1.3.3 complete for generic).
    # Phase 8: the generic module opts into the primary-ingredient evidence floor
    # (it has the count-over-quality flaw); omega/probiotic/multi/sports do not.
    evidence_payload = score_evidence(product, apply_primary_floor=True)
    evidence_dim = result.dimensions["evidence"]
    evidence_dim.score = evidence_payload["score"]
    evidence_dim.components = evidence_payload["components"]
    evidence_dim.penalties = evidence_payload["penalties"]
    evidence_dim.metadata = evidence_payload.get("metadata", {})

    # Phase 4 — verification bonus (replaces the former Testing & Trust
    # dimension). Same B4a-d signals via the trust scorer, rescaled ×8/15 and
    # added additively instead of sitting in the denominator.
    vb_payload = score_verification_bonus(product, "generic")
    result.verification_bonus.score = vb_payload["score"]
    result.verification_bonus.max = vb_payload["max"]
    result.verification_bonus.components = vb_payload["components"]
    result.verification_bonus.penalties = vb_payload.get("penalties", {})
    result.verification_bonus.metadata = vb_payload.get("metadata", {})

    # Phase 6 superseded the Phase-4 botanical_dose_deferred floor guard: the
    # botanical dose adapter now always returns a real score (0..22, never None),
    # so a botanical's dose dimension is never excluded and never needs flooring.
    # The result.botanical_dose_deferred field + assembly floor remain as inert
    # infrastructure (always False here) but are no longer set.

    # Layer 3 — Transparency dimension (P1.3.5 complete for generic).
    transparency_payload = score_transparency(product)
    transparency_dim = result.dimensions["transparency"]
    transparency_dim.score = transparency_payload["score"]
    transparency_dim.components = transparency_payload["components"]
    transparency_dim.penalties = transparency_payload["penalties"]
    transparency_dim.metadata = transparency_payload.get("metadata", {})

    # Separate manufacturer dimensions (P1.3.6). Manufacturer Trust is a
    # small positive adjustment; Manufacturer Violations is a separate
    # negative adjustment and never burns the +15 Testing & Trust cap.
    manufacturer_trust_payload = score_manufacturer_trust(product)
    result.manufacturer_trust.score = manufacturer_trust_payload["score"]
    result.manufacturer_trust.max = manufacturer_trust_payload["max"]
    result.manufacturer_trust.components = manufacturer_trust_payload["components"]
    result.manufacturer_trust.metadata = manufacturer_trust_payload.get("metadata", {})

    manufacturer_violations_payload = score_manufacturer_violations(product)
    result.manufacturer_violations.score = manufacturer_violations_payload["score"]
    result.manufacturer_violations.floor = manufacturer_violations_payload["floor"]
    result.manufacturer_violations.components = manufacturer_violations_payload["components"]
    result.manufacturer_violations.metadata = manufacturer_violations_payload.get("metadata", {})
    result.safety_hygiene_base = score_safety_hygiene_base(product)

    _assemble_score(result)

    # Module-level phase reflects the most-recent slice landed. Audit
    # tooling reads this to know whether to trust the per-dimension
    # scores. The overall module score remains unavailable until P1.3.6
    # final assembly.
    result.phase = PHASE_MARKER

    return result


def _assemble_score(result: GenericModuleResult) -> None:
    """Assemble v4's final 0-100 score from populated dimensions.

    Phase 4: core dimensions (formulation + dose + evidence + transparency,
    max 85) are summed on their NATIVE scale and the additive terms
    (verification_bonus ≤8, manufacturer_trust ≤5, manufacturer_violations,
    safety_hygiene) are added, then clamped to [0, 100]. There is NO
    renormalization of the core to 100 (that hidden inflation was removed with
    the trust dimension). A non-evaluable (`score is None`) dimension contributes
    0 and is listed in `excluded_dimensions`; for botanicals whose dose proxy is
    non-evaluable, the `botanical_dose_deferred` guard floors raw out of POOR
    until Phase 6's dose adapter lands (so missing reference data still doesn't
    punish quality in the interim).
    """
    # Phase 4: the core dimensions are summed on their NATIVE scale (max 85).
    # There is NO renormalization to 100 — the former `(sum/evaluable_max)*100`
    # branch is deliberately gone (it would have silently inflated 85→100, the
    # exact hidden inflation this phase removes). A non-evaluable (None) dimension
    # contributes 0 and is recorded in `excluded_dimensions` for audit.
    core_scores = []
    core_max = 0.0
    excluded = []
    for name, dim in result.dimensions.items():
        if dim.score is None:
            excluded.append(name)
            continue
        core_scores.append(float(dim.score))
        core_max += float(dim.max)
    class_subtotal = sum(core_scores)

    verification_bonus = float(result.verification_bonus.score or 0.0)
    manufacturer_trust = float(result.manufacturer_trust.score or 0.0)
    manufacturer_violations = float(result.manufacturer_violations.score or 0.0)
    safety_hygiene = float(result.safety_hygiene_base.score or 0.0)
    adjusted = (
        class_subtotal
        + verification_bonus
        + manufacturer_trust
        + manufacturer_violations
        + safety_hygiene
    )
    raw_score_100 = max(0.0, min(100.0, adjusted))

    # Phase 4 botanical guard (until Phase 6): keep a botanical whose dose proxy
    # is non-evaluable out of POOR — it lost the old renorm lift, not real quality.
    botanical_floor_applied = False
    if result.botanical_dose_deferred and raw_score_100 < BOTANICAL_RAW_FLOOR:
        raw_score_100 = BOTANICAL_RAW_FLOOR
        botanical_floor_applied = True
    calibrated = CALIBRATION_INTERCEPT + CALIBRATION_SLOPE * raw_score_100
    calibrated_score_100 = max(0.0, min(100.0, calibrated))
    result.raw_score_100 = round(raw_score_100, 1)
    result.score_100 = round(calibrated_score_100, 1)
    result.metadata = {
        "phase": PHASE_MARKER,
        # Phase 4: core summed on native scale (no renorm), so class_subtotal
        # == raw_dimension_sum and evaluable_class_max is the native core max
        # (≤85). Key names retained for audit-tool / score-delta compatibility.
        "raw_dimension_sum": round(class_subtotal, 4),
        "evaluable_class_max": round(core_max, 4),
        "excluded_dimensions": excluded,
        "class_subtotal": round(class_subtotal, 4),
        "verification_bonus_adjustment": round(verification_bonus, 4),
        "manufacturer_trust_adjustment": round(manufacturer_trust, 4),
        "manufacturer_violation_adjustment": round(manufacturer_violations, 4),
        "safety_hygiene_base_adjustment": round(safety_hygiene, 4),
        "safety_hygiene_base": result.safety_hygiene_base.to_dict(),
        "adjusted_score_before_clamp": round(adjusted, 4),
        "raw_score_100_pre_calibration": result.raw_score_100,
        "score_clamped": adjusted < 0.0 or adjusted > 100.0,
        "botanical_dose_deferred": result.botanical_dose_deferred,
        "botanical_raw_floor_applied": botanical_floor_applied,
        "calibration": {
            "method": CALIBRATION_METHOD,
            "intercept": CALIBRATION_INTERCEPT,
            "slope": CALIBRATION_SLOPE,
            "reason": "p1_5_canary_score_compression",
            "raw_score_100": result.raw_score_100,
            "calibrated_score_100": result.score_100,
        },
        "calibrated_score_before_clamp": round(calibrated, 4),
        "calibrated_score_clamped": calibrated < 0.0 or calibrated > 100.0,
    }
