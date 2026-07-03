"""v4 Fiber/Digestive module — fiber, prebiotic fiber, and digestive enzymes."""

from __future__ import annotations

from typing import Any

from scoring_v4.modules.fiber_digestive_dose import score_dose
from scoring_v4.modules.fiber_digestive_formulation import score_formulation
from scoring_v4.modules.generic import GenericModuleResult, _assemble_score, _empty_dimensions
from scoring_v4.modules.generic_evidence import score_evidence
from scoring_v4.modules.generic_manufacturer import (
    score_manufacturer_trust,
    score_manufacturer_violations,
)
from scoring_v4.modules.generic_transparency import score_transparency
from scoring_v4.modules.safety_hygiene import score_safety_hygiene_base
from scoring_v4.modules.verification_bonus import score_verification_bonus


PHASE_MARKER = "P1.8_fiber_digestive_module"


def score_fiber_digestive(product: Any) -> GenericModuleResult:
    """Score fiber/digestive products against category-specific dose/form facts."""
    if not isinstance(product, dict):
        product = {}

    result = GenericModuleResult(module="fiber_digestive", dimensions=_empty_dimensions())

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

    evidence_payload = score_evidence(product, apply_primary_floor=True)
    evidence_dim = result.dimensions["evidence"]
    evidence_dim.score = evidence_payload["score"]
    evidence_dim.components = evidence_payload["components"]
    evidence_dim.penalties = evidence_payload["penalties"]
    evidence_dim.metadata = evidence_payload.get("metadata", {})

    vb_payload = score_verification_bonus(product, "generic")
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
    result.phase = PHASE_MARKER
    result.metadata["phase"] = PHASE_MARKER
    return result
