"""v4 multi/prenatal Evidence dimension (P3.3).

Evidence answers whether the essential nutrient panel defining the product's
purpose is supported by established nutrition authority.  Dose adequacy and
form quality remain in their own pillars; incidental add-ins cannot create
Evidence breadth.
"""

from __future__ import annotations

from typing import Any, Dict

from evidence_resolver import resolve_authority_panel_evidence
from scoring_v4.modules.multi_prenatal_dose import (
    CORE_MULTI_ANCHORS,
    PRENATAL_CORE_ANCHORS,
    TARGETED_MULTI_ANCHORS,
    TARGETED_MULTI_SELECTED_ANCHORS,
    _is_prenatal,
    _is_targeted_multi,
    _nutrient_key,
)


PHASE_MARKER = "P3.3_multi_prenatal_evidence"
from scoring_v4.quality_score_config import block as _cfg_block

_EM = _cfg_block("evidence_magnitudes", "multi_prenatal")["multi_prenatal"]


CAP_EVIDENCE = _EM["cap_evidence"]
GENERIC_CAP_EVIDENCE = _EM["generic_cap_evidence"]  # compatibility/config validation


def _panel_contract(product: Dict[str, Any]) -> tuple[str, tuple[str, ...], int]:
    if _is_prenatal(product):
        return "prenatal", PRENATAL_CORE_ANCHORS, len(PRENATAL_CORE_ANCHORS)
    if _is_targeted_multi(product):
        return "targeted_multi", TARGETED_MULTI_ANCHORS, TARGETED_MULTI_SELECTED_ANCHORS
    return "broad_multi", CORE_MULTI_ANCHORS, len(CORE_MULTI_ANCHORS)


def score_evidence(product: Any) -> Dict[str, Any]:
    """Return the multi/prenatal Evidence 20 dimension payload."""
    if not isinstance(product, dict):
        product = {}

    mode, expected, full_count = _panel_contract(product)
    authority = resolve_authority_panel_evidence(
        product,
        expected_keys=expected,
        row_key=lambda row: _nutrient_key(
            row.get("canonical_id") or row.get("standard_name") or row.get("name")
        ),
        full_score=CAP_EVIDENCE,
        full_count=full_count,
    )
    adjusted = float(authority["score"])

    components = {
        "essential_panel_authority": round(adjusted, 4),
    }

    return {
        "score": round(adjusted, 4),
        "max": CAP_EVIDENCE,
        "components": components,
        "penalties": {},
        "phase": PHASE_MARKER,
        "metadata": {
            "phase": PHASE_MARKER,
            "method": "essential_nutrient_panel_authority_coverage",
            "panel_mode": mode,
            "authority_covered_count": len(authority["covered_keys"]),
            "authority_full_count": full_count,
            "authority_covered_keys": authority["covered_keys"],
            "authority_expected_keys": authority["expected_keys"],
            "authority_unresolved_keys": authority["unresolved_keys"],
            "authority_resolution_reasons": authority["resolution_reasons"],
        },
    }
