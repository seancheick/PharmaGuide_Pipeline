"""v4 Omega module — fish-oil / EPA-DHA / krill / algae class.

Per `docs/plans/SCORING_V4_PROPOSAL.md` §4 (dimension weights) and §9
(Omega / fish oil policy):

    Dimension          Cap     Subsequent slice that fills it
    -----------------  ----    -------------------------------
    Formulation         25     P1.6.1 — form_tier (TG 8 / PL 7 / rTG 6 /
                               EE 4 / undefined 2) + source_disclosed 4
                               + premium_form_a2_carry 5 + sustainability_cert 4
                               (Friend of the Sea / MSC, rules_db verified)
    Dose                25     P1.6.2 — EPA+DHA per-day bands (rescaled to /20
                               from scoring_config omega3_dose_bonus.bands)
                               + EPA:DHA ratio sanity (/5, in 1:3..3:1 range)
    Evidence            20     P1.6.3 — generic evidence pipeline with
                               omega-specific canonicals (EPA/DHA/EPA+DHA)
                               + indication_relevance (+5 at AHA CVD dose)
    Testing & Trust     15     P1.6.4 — IFOS scope-aware verified ONLY policy:
                               sku/product_line score 10; needs_review and
                               brand_only stay 0 (per Sean 2026-05-20).
                               + B4b GMP up to 4 + B4c traceability up to 1
    Transparency        15     P1.6.5 — EPA/DHA disclosed 5 + form disclosed 3
                               + source disclosed 3 + oxidation disclosed 2
                               + B3 claim_compliance (cap 4) minus B2/B5/B6
    Total class score  100

Plus two SEPARATE adjustments (§6 line 390, module-agnostic):

    Manufacturer Trust         0 to +5    (D1+D2+rollup; reuses generic)
    Manufacturer Violations    0 to -25   (manufacturer_violations.json rules
                                          + severity/recency; reuses generic)

P1.6.6 state: all 5 dimensions, manufacturer adjustments, and final
rubric-score assembly are online. Router, completeness gate, and the v4
scorer dispatch the omega class into a complete module result.

Per §13 architecture lock, this module does not import from
`score_supplements.py` (v3). Shared infrastructure (DimensionResult,
ManufacturerTrustResult, ManufacturerViolationsResult) is imported from
`scoring_v4.modules.generic` since the breakdown contract is identical
across modules — only the dimension caps and per-dimension sub-rubrics
differ between classes.

Per Sean's 2026-05-20 review: "Do not invent fields. Audit real canary
blobs first." Field audit confirmed available fields for omega scoring:
EPA/DHA quantities via ingredient_quality_data[canonical_id ∈ {epa,dha}],
IFOS scope via verified_cert_programs, GMP/COA via P1.8-hardened paths,
sustainability via certification_data.evidence_based.third_party_programs.
Form/oxidation must be parsed from product_name + ingredient names
(no explicit field on labels).
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
from scoring_v4.modules.omega_dose import score_dose
from scoring_v4.modules.omega_evidence import score_evidence
from scoring_v4.modules.omega_formulation import score_formulation
from scoring_v4.modules.omega_transparency import score_transparency
from scoring_v4.modules.verification_bonus import score_verification_bonus
from scoring_v4.modules.safety_hygiene import (
    SafetyHygieneResult,
    score_safety_hygiene_base,
)


PHASE_MARKER = "P1.6.6_omega_final_assembly"


# Dimension caps per §4 + omega_rubric.json. Order is rendering order in
# audit / UI. Locked by test_v4_omega_module_skeleton_p160.
from scoring_v4.quality_score_config import block as _cfg_block

_CM = _cfg_block("category_magnitudes", "omega")["omega"]


DIMENSION_CAPS = tuple((n, c) for n, c in _CM["dimension_caps"])


@dataclass
class OmegaModuleResult:
    """Container for the omega-module breakdown.

    Mirrors `GenericModuleResult` / `ProbioticModuleResult` shape so audit /
    score-delta / Flutter tooling can read a single
    `v4_breakdown["module"]` contract regardless of which
    class scored the product.

    Final assembly (Phase 4) uses the shared generic._assemble_score: core
    dimensions summed on native scale (max 85, NO renormalization), plus the
    additive verification_bonus / manufacturer_trust / manufacturer_violations /
    safety_hygiene, clamped to [0, 100]. Since Phase 9 this raw rubric score
    is the production score.
    """

    module: str = "omega"
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
        Matches `GenericModuleResult.to_breakdown` /
        `ProbioticModuleResult.to_breakdown` so consumers don't need
        class-aware unpacking."""
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


def score_omega(product: Any) -> OmegaModuleResult:
    """Score an omega-class product against the v4 omega rubric.

    P1.6.6 state: returns a fully-instantiated result with all 5 dimensions,
    manufacturer trust / violations, raw score, production score, and module
    metadata populated.

    Never raises on malformed input — empty / non-dict products get the
    same zero-math skeleton. Real input validation lives in the
    completeness gate (Layer 2), which short-circuits before this module
    runs in the production pipeline.

    Args:
        product: Enriched product dict (same contract as v3 consumes).
            Currently passed through to per-dimension stubs unchanged.

    Returns:
        OmegaModuleResult with the locked breakdown shape.
    """
    if not isinstance(product, dict):
        product = {}

    result = OmegaModuleResult(dimensions=_empty_dimensions())

    # P1.6.6 — each per-dimension scorer fills in its score, components,
    # penalties, and metadata before final assembly below.
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

    vb_payload = score_verification_bonus(product, "omega")
    result.verification_bonus.score = vb_payload["score"]
    result.verification_bonus.max = vb_payload["max"]
    result.verification_bonus.components = vb_payload["components"]
    result.verification_bonus.penalties = vb_payload.get("penalties", {})
    result.verification_bonus.metadata = vb_payload.get("metadata", {})

    transparency_payload = score_transparency(product)
    transparency_dim = result.dimensions["transparency"]
    transparency_dim.score = transparency_payload["score"]
    transparency_dim.components = transparency_payload["components"]
    transparency_dim.penalties = transparency_payload["penalties"]
    transparency_dim.metadata = transparency_payload.get("metadata", {})

    # P1.6.6 — Manufacturer Trust (+0..+5) and Manufacturer Violations
    # (0..-25). Reused verbatim from generic — Manufacturer dimensions
    # are module-agnostic per §6 line 390. Brand-level IFOS / cert
    # signals that we kept OUT of product Trust (P1.6.4 policy) can
    # legitimately route to Manufacturer Trust D1 here.
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
