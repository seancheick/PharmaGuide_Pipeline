"""v4 multi/prenatal Evidence dimension (P3.3).

Multi/prenatal Evidence uses the already-verified generic multiplicative
pipeline as its source of truth, then rescales from the generic 20-point
cap to the multi/prenatal 15-point cap. This preserves top-N dampening,
effect-direction handling, dose guards, and depth bonus without inventing
new evidence math for broad nutrient panels.
"""

from __future__ import annotations

from typing import Any, Dict

from scoring_v4.modules.generic_helpers import _as_float, _safe_dict
from scoring_v4.modules.generic_evidence import score_evidence as score_generic_evidence


PHASE_MARKER = "P3.3_multi_prenatal_evidence"
CAP_EVIDENCE = 15.0
GENERIC_CAP_EVIDENCE = 20.0
RESCALE_FACTOR = CAP_EVIDENCE / GENERIC_CAP_EVIDENCE


def _clamp(low: float, high: float, value: float) -> float:
    return max(low, min(high, value))


def score_evidence(product: Any) -> Dict[str, Any]:
    """Return the multi/prenatal Evidence 15 dimension payload."""
    if not isinstance(product, dict):
        product = {}

    generic_payload = score_generic_evidence(product)
    generic_score = _as_float(generic_payload.get("score"), 0.0) or 0.0
    adjusted = _clamp(0.0, CAP_EVIDENCE, generic_score * RESCALE_FACTOR)

    components = {
        "class_adjusted_clinical_evidence": round(adjusted, 4),
    }

    return {
        "score": round(adjusted, 4),
        "max": CAP_EVIDENCE,
        "components": components,
        "penalties": {},
        "phase": PHASE_MARKER,
        "metadata": {
            "phase": PHASE_MARKER,
            "method": "generic_evidence_pipeline_rescaled_to_multi_prenatal_cap",
            "dampening_policy": "generic_top_n_then_0_75_rescale",
            "generic_evidence_score": round(generic_score, 4),
            "generic_evidence_components": dict(_safe_dict(generic_payload.get("components"))),
            "generic_evidence_metadata": dict(_safe_dict(generic_payload.get("metadata"))),
            "rescale_factor": RESCALE_FACTOR,
        },
    }

