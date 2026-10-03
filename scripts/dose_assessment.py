"""Canonical typed dose and upper-limit assessment contract.

Enrichment is the sole producer. Scoring and release gates consume the typed
states instead of reinterpreting nullable booleans, failed conversions, or
free-text skip reasons.
"""

from __future__ import annotations

import math
import json
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from normalization import canonicalize_mass_unit
from scoring_v4.exposure import row_exposure


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
    "component_within_assessed_parent_total",
    "composition_share_of_declared_total",
    "form_component_of_declared_total",
    "compound_duplicate_row",
    "vitamin_a_components_own_ul",
}
_NO_UL_REASONS = {
    "not_ul_applicable",
    "beta_carotene_no_established_ul",
    "provitamin_a_carotenoid_no_established_ul",
    "non_folic_acid_folate_ul_basis",
}
_BOUNDED_UL_REASONS = {
    "worst_case_compound_mass_within_ul",
    "worst_case_folic_acid_within_ul",
    "worst_case_natural_vitamin_e_within_ul",
    "worst_case_preformed_vitamin_a_within_ul",
    "worst_case_vitamin_e_mass_within_ul",
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

_POSITIVE_BENCHMARK_DIRECTIONS = {"positive_strong", "positive_moderate", "positive_weak"}
_CLINICAL_RECORDS_PATH = Path(__file__).resolve().parent / "data" / "backed_clinical_studies.json"


@dataclass(frozen=True)
class ClinicalBenchmarkAssessment:
    record_id: str
    benchmark_value: float
    benchmark_maximum: Optional[float]
    benchmark_unit: str
    exposure_value: float
    ratio: float
    source_row_ref: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AggregateClinicalBenchmarkAssessment:
    record_id: str
    benchmark_value: float
    benchmark_maximum: Optional[float]
    benchmark_unit: str
    exposure_value: float
    ratio: float
    member_canonical_ids: tuple[str, ...]

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["member_canonical_ids"] = list(self.member_canonical_ids)
        return payload


@lru_cache(maxsize=1)
def _positive_clinical_benchmark_records() -> tuple[Dict[str, Any], ...]:
    raw = json.loads(_CLINICAL_RECORDS_PATH.read_text(encoding="utf-8"))
    return tuple(
        record for record in raw.get("backed_clinical_studies", [])
        if isinstance(record, dict)
        and str(record.get("effect_direction") or "").strip().lower() in _POSITIVE_BENCHMARK_DIRECTIONS
        and (_finite_number(record.get("min_clinical_dose")) or 0) > 0
    )


def _identity_text(value: Any) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _record_names(record: Dict[str, Any]) -> set[str]:
    return {
        text for text in (
            _identity_text(record.get("standard_name")),
            *(_identity_text(alias) for alias in record.get("aliases") or []),
        ) if text
    }


def _row_names(row: Dict[str, Any]) -> set[str]:
    return {
        text for text in (
            _identity_text(row.get("canonical_id")),
            _identity_text(row.get("standard_name") or row.get("standardName")),
            _identity_text(row.get("name")),
            _identity_text(row.get("matched_form")),
        ) if text
    }


def positive_clinical_benchmark(
    product: Dict[str, Any], row: Dict[str, Any],
) -> Optional[ClinicalBenchmarkAssessment]:
    """Return an exact, positive, applicable preparation benchmark for ``row``.

    Clinical records remain the source of the reviewed benchmark.  Exact
    enrichment source linkage is authoritative.  A branded whole-preparation
    row may also match its own registry name/alias; generic parent or member
    identity never borrows that branded benchmark.  Null/mixed/inapplicable
    records are absent from the eligible record set.
    """
    row_ref = str(row.get("raw_source_path") or row.get("source_row_ref") or "").strip()
    row_names = _row_names(row)
    matches = [
        match for match in ((product.get("evidence_data") or {}).get("clinical_matches") or [])
        if isinstance(match, dict)
    ]
    candidates: list[Dict[str, Any]] = []
    eligible_by_id = {str(record.get("id")): record for record in _positive_clinical_benchmark_records()}

    def applicable_record(record: Dict[str, Any], *, source_refs: Iterable[str] = ()) -> bool:
        from clinical_applicability import assess_clinical_applicability
        from evidence_resolver import evidence_record_matches_declared_purpose

        scoped_record = {**record, "matched_source_row_refs": [
            ref for ref in source_refs if ref
        ]}
        decision = assess_clinical_applicability(product, scoped_record, assess_amount=False)
        return (
            decision.get("status") in {"applicable", "not_curated"}
            and evidence_record_matches_declared_purpose(product, row, record)
        )

    for match in matches:
        record = eligible_by_id.get(str(match.get("id") or ""))
        if record is None:
            continue
        is_brand = str(record.get("id") or "").upper().startswith("BRAND_")
        if is_brand and not (row_names & _record_names(record)):
            # Source linkage can associate a blend member or generic parent
            # with the whole branded intervention. Dose requires the exact
            # branded preparation on this row.
            continue
        refs = {str(ref).strip() for ref in match.get("matched_source_row_refs") or [] if str(ref).strip()}
        if row_ref and row_ref in refs and applicable_record(record, source_refs=refs):
            candidates.append(record)
    for record in _positive_clinical_benchmark_records():
        if not str(record.get("id") or "").upper().startswith("BRAND_"):
            continue
        if (
            row_names & _record_names(record)
            and record not in candidates
            and applicable_record(record, source_refs=[row_ref] if row_ref else [])
        ):
            candidates.append(record)

    exact_branded = [
        record for record in candidates
        if str(record.get("id") or "").upper().startswith("BRAND_")
        and row_names & _record_names(record)
    ]
    if exact_branded:
        candidates = exact_branded

    if not candidates:
        # The verified literature registry has structured material/purpose
        # applicability but stores its studied range separately from the
        # backed-study registry. Reuse the canonical resolver's applicability
        # decision, then project only a positive exact range into Dose.
        from evidence_resolver import (
            EvidenceDisposition,
            resolve_evidence_for_row,
        )
        resolution = resolve_evidence_for_row(row, product=product)
        literature = (resolution.owner_facts or {}).get("literature_evidence") or {}
        studied = literature.get("studied_dose") or {}
        values = studied.get("values") if isinstance(studied, dict) else None
        if (
            resolution.disposition == EvidenceDisposition.RESOLVED_BY_REVIEWED_CLINICAL_EVIDENCE.value
            and str(literature.get("effect_direction") or "").strip().lower() in _POSITIVE_BENCHMARK_DIRECTIONS
            and isinstance(values, list) and values
            and str(studied.get("basis") or "").strip().lower() in {"daily_intake", "per_serving_threshold"}
        ):
            positive_values = [value for value in (_finite_number(item) for item in values) if value and value > 0]
            if positive_values:
                candidates.append({
                    "id": "LIT_" + str(row.get("canonical_id") or row.get("name") or "").upper(),
                    "effect_direction": literature.get("effect_direction"),
                    "min_clinical_dose": min(positive_values),
                    "max_studied_clinical_dose": max(positive_values),
                    "dose_unit": studied.get("unit") or "mg",
                })

    assessments = []
    for record in candidates:
        benchmark = _finite_number(record.get("min_clinical_dose"))
        unit = str(record.get("dose_unit") or "mg").strip().lower()
        if benchmark is None or benchmark <= 0:
            continue
        exposure = row_exposure(product, row, basis="daily", unit=unit).benchmark_amount
        if exposure is None or exposure <= 0:
            continue
        assessments.append(ClinicalBenchmarkAssessment(
            record_id=str(record.get("id") or ""),
            benchmark_value=benchmark,
            benchmark_maximum=_finite_number(record.get("max_studied_clinical_dose")),
            benchmark_unit=unit,
            exposure_value=exposure,
            ratio=exposure / benchmark,
            source_row_ref=row_ref,
        ))
    return min(assessments, key=lambda item: (item.benchmark_value, item.record_id), default=None)


def positive_aggregate_clinical_benchmark(
    product: Dict[str, Any], rows: Iterable[Dict[str, Any]],
) -> Optional[AggregateClinicalBenchmarkAssessment]:
    """Return one exact benchmark for a reviewed multi-ingredient formula.

    Aggregate records such as the complete BCAA triad describe one intervention,
    so Dose must sum its required members once.  Every required identity must be
    present exactly once with a compatible disclosed exposure, and the curated
    aggregate record must already be projected into the product's clinical
    matches.  Individual members never borrow the formula benchmark.
    """
    eligible_by_id = {
        str(record.get("id")): record
        for record in _positive_clinical_benchmark_records()
        if isinstance(record.get("aggregate_canonical_ids"), list)
        and record.get("aggregate_canonical_ids")
    }
    matches = [
        match for match in ((product.get("evidence_data") or {}).get("clinical_matches") or [])
        if isinstance(match, dict) and str(match.get("id") or "") in eligible_by_id
    ]
    rows_by_canonical: Dict[str, list[Dict[str, Any]]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        canonical = str(row.get("canonical_id") or "").strip().lower()
        if canonical:
            rows_by_canonical.setdefault(canonical, []).append(row)

    assessments: list[AggregateClinicalBenchmarkAssessment] = []
    for match in matches:
        record = eligible_by_id[str(match.get("id"))]
        members = tuple(
            str(value).strip().lower()
            for value in record.get("aggregate_canonical_ids") or []
            if str(value).strip()
        )
        if not members or any(len(rows_by_canonical.get(member, [])) != 1 for member in members):
            continue
        benchmark = _finite_number(record.get("min_clinical_dose"))
        unit = str(record.get("dose_unit") or "mg").strip().lower()
        if benchmark is None or benchmark <= 0:
            continue
        exposures = [
            row_exposure(product, rows_by_canonical[member][0], basis="daily", unit=unit).benchmark_amount
            for member in members
        ]
        if any(value is None or value <= 0 for value in exposures):
            continue
        exposure = sum(float(value) for value in exposures if value is not None)
        assessments.append(AggregateClinicalBenchmarkAssessment(
            record_id=str(record.get("id") or ""),
            benchmark_value=benchmark,
            benchmark_maximum=_finite_number(record.get("max_studied_clinical_dose")),
            benchmark_unit=unit,
            exposure_value=exposure,
            ratio=exposure / benchmark,
            member_canonical_ids=members,
        ))
    return min(assessments, key=lambda item: (item.benchmark_value, item.record_id), default=None)


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
    source_path: Optional[str]
    linked_row_refs: tuple[str, ...]
    owner_row_ref: Optional[str]
    ingredient: str
    canonical_id: Optional[str]
    dose_class: Optional[str]
    evidence_type: Optional[str]
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
        payload = asdict(self)
        payload["linked_row_refs"] = list(self.linked_row_refs)
        return payload


def build_dose_assessment(
    *,
    source_row_ref: Any,
    source_path: Any,
    linked_row_refs: Any,
    owner_row_ref: Any,
    ingredient: Any,
    canonical_id: Any,
    dose_class: Any,
    evidence_type: Any,
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
        elif (
            reason in _NO_UL_REASONS
            or reason in _BOUNDED_UL_REASONS
            or role == "form_component"
        ):
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
        elif (
            reason in _NO_UL_REASONS
            or normalized_ul_status.startswith("not_determined")
            or normalized_ul_status.startswith("not_applicable")
        ):
            assessment_status = NO_UL_APPLICABLE
            readiness = READINESS_NOT_APPLICABLE
            # No UL cannot validate an unresolved nutrient-specific unit.
            # A known native mass (e.g. alpha-carotene mg) remains usable even
            # without retinol equivalence. Do not invent that converted value.
            # Native activity/count units with no nutrient rule are unchanged.
            if (
                material
                and evidence.get("success") is False
                and evidence.get("conversion_rule_id")
                and not evidence.get("nonfatal_reason")
                and canonicalize_mass_unit(source_unit) not in {"g", "mg", "mcg"}
            ):
                conversion_status = CONVERSION_FAILED
                readiness = READINESS_INCOMPLETE
                reason = "conversion_failed"
        elif reason in _UNRESOLVED_FORM_REASONS:
            assessment_status = UNRESOLVED_FORM
            readiness = READINESS_INCOMPLETE
        elif (
            reason in _BOUNDED_UL_REASONS
            and _finite_number(pct_ul) is not None
        ):
            assessment_status = ASSESSED_WITHIN_LIMIT
            readiness = READINESS_COMPLETE
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
        source_path=str(source_path or "").strip() or None,
        linked_row_refs=tuple(dict.fromkeys(
            str(value).strip()
            for value in (linked_row_refs or [])
            if str(value).strip()
        )),
        owner_row_ref=str(owner_row_ref or "").strip() or None,
        ingredient=str(ingredient or "").strip(),
        canonical_id=str(canonical_id or "").strip() or None,
        dose_class=str(dose_class or "").strip() or None,
        evidence_type=str(evidence_type or "").strip() or None,
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
