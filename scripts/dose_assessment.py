"""Canonical typed dose and upper-limit assessment contract.

Enrichment is the sole producer. Scoring and release gates consume the typed
states instead of reinterpreting nullable booleans, failed conversions, or
free-text skip reasons.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, Optional


ASSESSED_WITHIN_LIMIT = "assessed_within_limit"
ASSESSED_OVER_LIMIT = "assessed_over_limit"
NO_UL_APPLICABLE = "no_ul_applicable"
NOT_DISTINCT_EXPOSURE = "not_distinct_exposure"
UNRESOLVED_UNIT = "unresolved_unit"
UNRESOLVED_FORM = "unresolved_form"
UNRESOLVED_COMPOUND_MASS = "unresolved_compound_mass"
ASSESSMENT_ERROR = "assessment_error"

READINESS_COMPLETE = "complete"
READINESS_INCOMPLETE = "incomplete"
READINESS_NOT_APPLICABLE = "not_applicable"

CONVERSION_CONVERTED = "converted"
CONVERSION_NOT_REQUIRED = "not_required"
CONVERSION_NOT_APPLICABLE = "not_applicable"
CONVERSION_FAILED = "failed"

_NOT_DISTINCT_REASONS = {
    "form_component_of_declared_total",
    "compound_duplicate_row",
    "vitamin_a_components_own_ul",
}
_NO_UL_REASONS = {
    "not_ul_applicable",
    "beta_carotene_no_established_ul",
    "non_folic_acid_folate_ul_basis",
}
_UNRESOLVED_FORM_REASONS = {
    "unknown_folate_form_lineage",
    "unknown_vitamin_form",
    "mixed_vitamin_a_preformed_fraction_unknown",
}
_UNRESOLVED_UNIT_REASONS = {
    "amount_not_declared",
    "conversion_failed",
    "unit_unrecognized",
    "no_conversion_rule",
    "conversion_exception",
}


def _finite_number(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


@dataclass(frozen=True)
class DoseAssessment:
    source_row_ref: Optional[str]
    owner_row_ref: Optional[str]
    ingredient: str
    canonical_id: Optional[str]
    material: bool
    source_value: Optional[float]
    source_unit: Optional[str]
    normalized_value: Optional[float]
    normalized_unit: Optional[str]
    conversion_rule_id: Optional[str]
    conversion_status: str
    ul_assessment_status: str
    ul_value: Optional[float]
    ul_unit: Optional[str]
    pct_ul: Optional[float]
    ul_gate_eligible: Optional[bool]
    reason_code: Optional[str]
    readiness: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def build_dose_assessment(
    *,
    source_row_ref: Any,
    owner_row_ref: Any,
    ingredient: Any,
    canonical_id: Any,
    source_value: Any,
    source_unit: Any,
    normalized_value: Any,
    normalized_unit: Any,
    conversion_evidence: Any,
    dose_role: Any,
    skip_ul_check: bool,
    skip_ul_reason: Any,
    ul_status: Any,
    ul_value: Any,
    ul_unit: Any,
    pct_ul: Any,
    over_ul: bool,
    ul_gate_eligible: Any,
    ul_gate_ineligible_reason: Any,
    assessment_error: Any = None,
) -> DoseAssessment:
    """Build one typed result from a single source-label exposure row."""
    evidence = conversion_evidence if isinstance(conversion_evidence, dict) else {}
    source_amount = _finite_number(source_value)
    normalized_amount = _finite_number(normalized_value)
    material = bool(source_amount is not None and source_amount > 0)
    reason = str(skip_ul_reason or ul_gate_ineligible_reason or "").strip() or None
    role = str(dose_role or "").strip().lower()

    if assessment_error:
        conversion_status = (
            CONVERSION_NOT_REQUIRED
            if normalized_amount is not None
            else CONVERSION_FAILED
        )
        assessment_status = ASSESSMENT_ERROR
        readiness = READINESS_INCOMPLETE
        reason = "dose_assessment_exception"
    else:
        rule_id = str(evidence.get("conversion_rule_id") or "").strip().lower()
        if evidence.get("success") is True and normalized_amount is not None:
            conversion_status = (
                CONVERSION_NOT_REQUIRED
                if rule_id in {
                    "identity_mass_passthrough",
                    "identity",
                    "mass_conversion",
                }
                and _finite_number(evidence.get("conversion_factor")) == 1.0
                else CONVERSION_CONVERTED
            )
        elif evidence.get("nonfatal_reason") and normalized_amount is not None:
            conversion_status = CONVERSION_NOT_REQUIRED
        elif reason in _NO_UL_REASONS or role == "form_component":
            conversion_status = (
                CONVERSION_NOT_APPLICABLE
                if normalized_amount is None
                else CONVERSION_CONVERTED
            )
        else:
            conversion_status = CONVERSION_FAILED

        normalized_ul_status = str(ul_status or "").strip().lower()
        if reason in _NOT_DISTINCT_REASONS or role == "form_component":
            assessment_status = NOT_DISTINCT_EXPOSURE
            readiness = READINESS_NOT_APPLICABLE
        elif reason in _NO_UL_REASONS or normalized_ul_status in {
            "not_determined",
            "not_applicable",
        }:
            assessment_status = NO_UL_APPLICABLE
            readiness = READINESS_NOT_APPLICABLE
        elif reason in _UNRESOLVED_FORM_REASONS:
            assessment_status = UNRESOLVED_FORM
            readiness = READINESS_INCOMPLETE
        elif (
            reason == "compound_mass_not_elemental"
            or (
                ul_gate_eligible is False
                and str(ul_gate_ineligible_reason or "").strip()
                == "compound_mass_not_elemental"
            )
        ):
            assessment_status = UNRESOLVED_COMPOUND_MASS
            readiness = READINESS_INCOMPLETE
        elif reason in _UNRESOLVED_UNIT_REASONS or normalized_amount is None:
            assessment_status = UNRESOLVED_UNIT
            readiness = READINESS_INCOMPLETE
        elif over_ul:
            assessment_status = ASSESSED_OVER_LIMIT
            readiness = READINESS_COMPLETE
        elif _finite_number(pct_ul) is not None:
            assessment_status = ASSESSED_WITHIN_LIMIT
            readiness = READINESS_COMPLETE
        elif normalized_ul_status.startswith("not_applicable"):
            assessment_status = NO_UL_APPLICABLE
            readiness = READINESS_NOT_APPLICABLE
        elif skip_ul_check:
            assessment_status = UNRESOLVED_UNIT
            readiness = READINESS_INCOMPLETE
        else:
            assessment_status = NO_UL_APPLICABLE
            readiness = READINESS_NOT_APPLICABLE

    return DoseAssessment(
        source_row_ref=str(source_row_ref or "").strip() or None,
        owner_row_ref=str(owner_row_ref or "").strip() or None,
        ingredient=str(ingredient or "").strip(),
        canonical_id=str(canonical_id or "").strip() or None,
        material=material,
        source_value=source_amount,
        source_unit=str(source_unit or "").strip() or None,
        normalized_value=normalized_amount,
        normalized_unit=str(normalized_unit or "").strip() or None,
        conversion_rule_id=(
            str(evidence.get("conversion_rule_id") or "").strip() or None
        ),
        conversion_status=conversion_status,
        ul_assessment_status=assessment_status,
        ul_value=_finite_number(ul_value),
        ul_unit=str(ul_unit or "").strip() or None,
        pct_ul=_finite_number(pct_ul),
        ul_gate_eligible=(
            ul_gate_eligible if isinstance(ul_gate_eligible, bool) else None
        ),
        reason_code=reason,
        readiness=readiness,
    )


def has_incomplete_material_dose_assessment(
    assessments: Iterable[Any],
) -> bool:
    """Return whether any material exposure is not ready for live scoring."""
    for assessment in assessments or []:
        if not isinstance(assessment, dict):
            return True
        if (
            assessment.get("material") is True
            and assessment.get("readiness")
            not in {READINESS_COMPLETE, READINESS_NOT_APPLICABLE}
        ):
            return True
    return False
