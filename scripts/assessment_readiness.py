"""Typed readiness for identity, dose, evidence, verification, and routing.

The quality score may only describe a live, non-blocked product after every
material assessment has completed.  This module is the single scoring-time
producer of that cross-cutting result.  It does not change pillar weights or
invent evidence: a reviewed negative result is complete, while a missing
review remains explicitly incomplete.
"""

from __future__ import annotations

import math
import re
from typing import Any, Dict, Iterable, List, Mapping

from scoring_input_contract import (
    ROLE_ADJUNCT,
    ROLE_CLAIM_PROMINENT,
    ROLE_MAJOR,
    ROLE_PRIMARY,
    build_scoring_classification,
    classify_ingredient_roles,
    get_scoring_ingredients,
    has_unresolved_identity_reason,
    score_exclusion_reason,
)
from scoring_v4.modules.generic_evidence import (
    DRI_ESSENTIAL_NUTRIENTS,
    resolved_clinical_matches,
)


ASSESSMENT_READINESS_SCHEMA_VERSION = "1.0.0"

READINESS_COMPLETE = "complete"
READINESS_INCOMPLETE = "incomplete"
READINESS_NOT_APPLICABLE = "not_applicable"

# Who owns the evidence question for a row. `state` records the answer; this
# records whether an individual clinical record is the thing that answers it.
EVIDENCE_APPLICABILITY_INDIVIDUAL = "individual_ingredient"
EVIDENCE_APPLICABILITY_NUTRITION_AUTHORITY = "nutrition_authority"
EVIDENCE_APPLICABILITY_MODULE_AGGREGATE = "module_aggregate"
EVIDENCE_APPLICABILITY_NOT_APPLICABLE = "not_applicable"

# Readiness dimensions that gate the live catalog. Evidence is deliberately
# absent: `not_yet_evaluated` records an uncurated ingredient, not a defective
# product, and enforcing it would quarantine on curation backlog. It stays fully
# measured and reported in shadow so the backlog is visible and burnable.
ENFORCED_READINESS_DIMENSIONS = frozenset({
    "identity",
    "dose",
    "verification",
    "route",
})


def has_canonical_enforced_dimensions(value: Any) -> bool:
    """Return whether an artifact declares the exact release-gating contract."""
    return (
        isinstance(value, list)
        and len(value) == len(ENFORCED_READINESS_DIMENSIONS)
        and all(isinstance(name, str) for name in value)
        and frozenset(value) == ENFORCED_READINESS_DIMENSIONS
    )

EVIDENCE_EVALUATED_SUPPORTED = "evaluated_supported"
EVIDENCE_EVALUATED_LIMITED_OR_NEGATIVE = "evaluated_limited_or_negative"
EVIDENCE_NOT_YET_EVALUATED = "not_yet_evaluated"
EVIDENCE_NOT_APPLICABLE = "not_applicable"

VERIFICATION_VERIFIED_PRESENT = "verified_present"
VERIFICATION_VERIFIED_ABSENT = "verified_absent"
VERIFICATION_NOT_EVALUATED = "not_evaluated"

_MATERIAL_ROLES = frozenset({ROLE_PRIMARY, ROLE_CLAIM_PROMINENT, ROLE_MAJOR})
_VALID_MODULES = frozenset({
    "generic",
    "probiotic",
    "multi_or_prenatal",
    "b_complex",
    "omega",
    "sports",
    "fiber_digestive",
})
_SUPPORTIVE_EFFECTS = frozenset({"positive_strong", "positive_weak"})
_HUMAN_EVIDENCE_LEVELS = frozenset({
    "product-human",
    "product_human",
    "product-rct",
    "product_rct",
    "product",
    "branded-rct",
    "branded_rct",
    "ingredient-human",
    "ingredient_human",
    "strain-clinical",
    "strain_clinical",
})
_NONHUMAN_STUDY_TYPES = frozenset({
    "reference",
    "animal_study",
    "in_vitro",
})
_ROUTE_INCOMPLETE_REASON_CODES = frozenset({
    "protein_identity_or_mass_missing",
})


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")


def _row_ref(row: Mapping[str, Any], index: int) -> str:
    return str(
        row.get("source_row_ref")
        or row.get("raw_source_path")
        or f"scoringRows[{index}]"
    )


def _identity_keys(row: Mapping[str, Any]) -> set[str]:
    keys = {
        _norm(row.get(field))
        for field in (
            "canonical_id",
            "name",
            "standard_name",
            "standardName",
            "raw_source_text",
            "evidence_canonical_id",
            "scoring_parent_id",
        )
    }
    return {key for key in keys if key}


def _match_identity_keys(match: Mapping[str, Any]) -> set[str]:
    keys = {
        _norm(match.get(field))
        for field in (
            "matched_canonical_id",
            "marker_via_ingredient",
            "evidence_group_id",
            "ingredient",
            "standard_name",
            "study_name",
            "matched_term",
        )
    }
    for canonical in _safe_list(match.get("aggregate_canonical_ids")):
        keys.add(_norm(canonical))
    for canonical in _safe_list(match.get("matched_canonical_ids")):
        keys.add(_norm(canonical))
    return {key for key in keys if key}


def _entry_id(match: Mapping[str, Any]) -> str:
    return str(match.get("id") or match.get("study_id") or "").strip()


def _is_supportive_human_match(match: Mapping[str, Any]) -> bool:
    effect = _norm(match.get("effect_direction"))
    level = _norm(match.get("evidence_level"))
    study_type = _norm(match.get("study_type"))
    return (
        effect in _SUPPORTIVE_EFFECTS
        and level in {_norm(value) for value in _HUMAN_EVIDENCE_LEVELS}
        and study_type not in _NONHUMAN_STUDY_TYPES
    )


def _probiotic_native_evidence_state(product: Mapping[str, Any]) -> str | None:
    probiotic = _safe_dict(product.get("probiotic_data") or product.get("probiotic_detail"))
    strains = [
        row
        for row in _safe_list(probiotic.get("clinical_strains"))
        if isinstance(row, dict)
    ]
    if not strains:
        return None
    tokens = {
        _norm(
            row.get("clinical_support_level")
            or row.get("evidence_level")
            or row.get("evidence_strength")
            or row.get("support_level")
        )
        for row in strains
        if (
            row.get("clinical_id")
            or row.get("strain")
            or row.get("standard_name")
            or row.get("name")
        )
    }
    if tokens & {"strong", "moderate", "high", "well_supported", "supported"}:
        return EVIDENCE_EVALUATED_SUPPORTED
    if tokens:
        return EVIDENCE_EVALUATED_LIMITED_OR_NEGATIVE
    return EVIDENCE_NOT_YET_EVALUATED


def evaluate_evidence_assessment(
    product: Mapping[str, Any],
    *,
    module: str,
) -> Dict[str, Any]:
    """Classify every score row without treating a missing match as a review."""
    scoring_input = get_scoring_ingredients(
        dict(product),
        strict=True,
        allow_legacy_fallback=False,
    )
    rows = list(scoring_input.rows)
    roles = classify_ingredient_roles(dict(product), module=module, rows=rows)
    matches, recovered_matches = resolved_clinical_matches(dict(product))
    indexed_matches = [
        (match, _match_identity_keys(match))
        for match in matches
        if isinstance(match, dict)
    ]
    probiotic_state = (
        _probiotic_native_evidence_state(product)
        if module == "probiotic"
        else None
    )

    assessments: List[Dict[str, Any]] = []
    incomplete_refs: List[str] = []
    for index, (row, role) in enumerate(zip(rows, roles)):
        canonical_id = _norm(row.get("canonical_id")) or None
        source_ref = _row_ref(row, index)
        role_name = str(role.get("role") or ROLE_ADJUNCT)
        material = role_name in _MATERIAL_ROLES
        linked = [
            match
            for match, keys in indexed_matches
            if _identity_keys(row) & keys
        ]
        evidence_ids = list(dict.fromkeys(
            evidence_id
            for evidence_id in (_entry_id(match) for match in linked)
            if evidence_id
        ))

        applicability = EVIDENCE_APPLICABILITY_INDIVIDUAL
        if not material:
            applicability = EVIDENCE_APPLICABILITY_NOT_APPLICABLE
            state = EVIDENCE_NOT_APPLICABLE
            reason = "non_material_active"
        elif row.get("scoring_input_kind") == "product_level_evidence":
            applicability = EVIDENCE_APPLICABILITY_MODULE_AGGREGATE
            state = EVIDENCE_NOT_APPLICABLE
            reason = "module_scoped_product_projection"
        elif canonical_id in DRI_ESSENTIAL_NUTRIENTS:
            applicability = EVIDENCE_APPLICABILITY_NUTRITION_AUTHORITY
            state = EVIDENCE_EVALUATED_SUPPORTED
            reason = "established_dri_nutrition_authority"
        elif any(_is_supportive_human_match(match) for match in linked):
            state = EVIDENCE_EVALUATED_SUPPORTED
            reason = "reviewed_human_evidence_supportive"
        elif linked:
            state = EVIDENCE_EVALUATED_LIMITED_OR_NEGATIVE
            reason = "reviewed_evidence_limited_or_negative"
        elif module == "probiotic" and probiotic_state is not None:
            state = probiotic_state
            reason = "reviewed_native_clinical_strain_evidence"
        else:
            state = EVIDENCE_NOT_YET_EVALUATED
            reason = "no_reviewed_evidence_assessment"

        if (
            applicability == EVIDENCE_APPLICABILITY_INDIVIDUAL
            and state == EVIDENCE_NOT_YET_EVALUATED
        ):
            incomplete_refs.append(source_ref)
        dose_class = _norm(row.get("dose_class"))
        source_value = row.get("quantity", row.get("dose_value"))
        source_unit = row.get("unit") or row.get("dose_unit")
        if dose_class == "enzyme_activity":
            activity_value = row.get(
                "activity_quantity", row.get("activity_value")
            )
            activity_unit = row.get("activity_unit")
            if activity_value not in (None, "") and activity_unit:
                source_value = activity_value
                source_unit = activity_unit
        assessments.append({
            "source_row_ref": source_ref,
            "canonical_id": canonical_id,
            "name": row.get("name") or row.get("standard_name"),
            "role": role_name,
            "material": material,
            "source_value": source_value,
            "source_unit": source_unit,
            "dose_class": row.get("dose_class"),
            "linked_rows": list(_safe_list(row.get("linked_rows"))),
            "scoring_input_kind": row.get("scoring_input_kind"),
            "evidence_type": row.get("evidence_type"),
            "state": state,
            "evidence_applicability": applicability,
            "reason_code": reason,
            "evidence_ids": evidence_ids,
        })

    material_count = sum(1 for row in assessments if row["material"])
    applicability_counts: Dict[str, int] = {}
    for row in assessments:
        key = str(row["evidence_applicability"])
        applicability_counts[key] = applicability_counts.get(key, 0) + 1
    individual_count = applicability_counts.get(
        EVIDENCE_APPLICABILITY_INDIVIDUAL, 0
    )
    readiness = (
        READINESS_NOT_APPLICABLE
        if material_count == 0
        else READINESS_INCOMPLETE
        if incomplete_refs
        else READINESS_COMPLETE
    )
    return {
        "readiness": readiness,
        "material_active_count": material_count,
        "individual_assessment_count": individual_count,
        "applicability_counts": applicability_counts,
        "not_yet_evaluated_count": len(incomplete_refs),
        "not_yet_evaluated_row_refs": incomplete_refs,
        "ingredient_assessments": assessments,
        "resolved_evidence_match_count": len(matches),
        "recovered_evidence_ids": [
            evidence_id
            for evidence_id in (_entry_id(match) for match in recovered_matches)
            if evidence_id
        ],
    }


def _verified_programs(product: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    cert = _safe_dict(product.get("certification_data"))
    entries = product.get("verified_cert_programs")
    if entries is None:
        entries = cert.get("verified_cert_programs")
    return [entry for entry in _safe_list(entries) if isinstance(entry, Mapping)]


def _scores_as_verified(entry: Mapping[str, Any]) -> bool:
    return (
        str(entry.get("scope") or "") in {"sku", "product_line"}
        and not entry.get("scoring_blocked_reason")
    )


def _source_score_eligible_active_rows(
    product: Mapping[str, Any],
) -> list[Mapping[str, Any]]:
    """Return cleaner-owned active rows even when dose filtering removes them."""
    quality = _safe_dict(product.get("ingredient_quality_data"))
    rows = quality.get("ingredients")
    return [
        row
        for row in _safe_list(rows)
        if isinstance(row, Mapping)
        and _norm(row.get("source_section")) != "inactive"
        and (
            not score_exclusion_reason(dict(row))
            or has_unresolved_identity_reason(dict(row))
        )
        and (
            row.get("score_eligible_by_cleaner") is True
            or _norm(row.get("cleaner_row_role")) == "active_scorable"
        )
    ]


def evaluate_verification_assessment(product: Mapping[str, Any]) -> Dict[str, Any]:
    """Preserve verified-present, evaluated-absent, and not-evaluated."""
    cert = product.get("certification_data")
    if isinstance(cert, Mapping):
        explicit = cert.get("verification_assessment")
        if isinstance(explicit, Mapping):
            state = str(explicit.get("state") or "")
            readiness = str(explicit.get("readiness") or "")
            if (
                state in {
                    VERIFICATION_VERIFIED_PRESENT,
                    VERIFICATION_VERIFIED_ABSENT,
                    VERIFICATION_NOT_EVALUATED,
                }
                and readiness in {READINESS_COMPLETE, READINESS_INCOMPLETE}
            ):
                return dict(explicit)
            return {
                "state": VERIFICATION_NOT_EVALUATED,
                "readiness": READINESS_INCOMPLETE,
                "reason_code": "invalid_verification_assessment_contract",
                "matched_programs": [],
            }

        # Schema-2.x migration boundary. The presence of certification_data
        # proves the enrichment collector ran; old artifacts simply omitted its
        # explicit completion marker. Remove this branch with schema 3.
        verified = [entry for entry in _verified_programs(product) if _scores_as_verified(entry)]
        programs = list(dict.fromkeys(
            str(entry.get("program") or "").strip()
            for entry in verified
            if str(entry.get("program") or "").strip()
        ))
        return {
            "state": (
                VERIFICATION_VERIFIED_PRESENT
                if verified
                else VERIFICATION_VERIFIED_ABSENT
            ),
            "readiness": READINESS_COMPLETE,
            "reason_code": (
                "legacy_registry_verified_product_match"
                if verified
                else "legacy_registry_evaluated_no_match"
            ),
            "matched_programs": programs,
            "migration_inference": True,
        }

    return {
        "state": VERIFICATION_NOT_EVALUATED,
        "readiness": READINESS_INCOMPLETE,
        "reason_code": "verification_collector_not_run",
        "matched_programs": [],
    }


def _identity_readiness(product: Mapping[str, Any]) -> Dict[str, Any]:
    scoring_input = get_scoring_ingredients(
        dict(product),
        strict=True,
        allow_legacy_fallback=False,
    )
    blocking_findings = [
        finding
        for finding in scoring_input.contract_findings
        if not finding.startswith("missing_required_fields:")
        and finding != "missing_identity_disposition"
    ]
    product_evidence_rows = [
        row
        for row in scoring_input.rows
        if row.get("scoring_input_kind") == "product_level_evidence"
    ]
    mapped_product_evidence = [
        row
        for row in product_evidence_rows
        if row.get("scoreable_identity") is True
        and row.get("mapped") is not False
        and bool(str(row.get("canonical_id") or "").strip())
    ]
    source_rows = _source_score_eligible_active_rows(product)
    mapped_source_rows = [
        row
        for row in source_rows
        if row.get("mapped_identity") is not False
        and bool(str(row.get("canonical_id") or "").strip())
        and _norm(row.get("identity_disposition"))
        not in {"unresolved", "rejected", "parse_error"}
    ]
    source_mapped_count = len(mapped_source_rows)
    source_unmapped_count = len(source_rows) - source_mapped_count
    source_mapped_coverage = (
        source_mapped_count / len(source_rows)
        if source_rows
        else None
    )
    if scoring_input.zero_scorable_reason:
        if source_rows:
            source_identity_complete = (
                source_mapped_count > 0
                and source_unmapped_count == 0
                and source_mapped_coverage == 1.0
                and len(mapped_product_evidence) == len(product_evidence_rows)
            )
            reason_code = (
                "mapped_source_actives"
                if source_identity_complete
                else "unmapped_source_actives"
            )
        else:
            source_identity_complete = False
            reason_code = "no_score_eligible_active_rows"
    else:
        source_identity_complete = (
            scoring_input.mapped_count > 0
            and scoring_input.unmapped_count == 0
            and scoring_input.mapped_coverage == 1.0
            and len(mapped_product_evidence) == len(product_evidence_rows)
        )
        reason_code = (
            "mapped_scoring_actives"
            if source_identity_complete
            else "scoring_identity_incomplete"
        )
    complete = (
        source_identity_complete
        and not blocking_findings
    )
    return {
        "readiness": READINESS_COMPLETE if complete else READINESS_INCOMPLETE,
        "reason_code": reason_code,
        "mapped_count": scoring_input.mapped_count,
        "unmapped_count": scoring_input.unmapped_count,
        "mapped_coverage": scoring_input.mapped_coverage,
        "product_evidence_count": len(product_evidence_rows),
        "mapped_product_evidence_count": len(mapped_product_evidence),
        "contract_findings": list(scoring_input.contract_findings),
        "blocking_contract_findings": blocking_findings,
        "source_score_eligible_active_count": len(source_rows),
        "source_mapped_count": source_mapped_count,
        "source_unmapped_count": source_unmapped_count,
        "source_mapped_coverage": source_mapped_coverage,
        "zero_scorable_reason": scoring_input.zero_scorable_reason,
    }


def _dose_readiness(
    product: Mapping[str, Any],
    evidence_assessments: Iterable[Mapping[str, Any]],
    *,
    module: str,
) -> Dict[str, Any]:
    material_rows = [
        row
        for row in evidence_assessments
        if isinstance(row, Mapping) and row.get("material") is True
    ]
    material_count = len(material_rows)
    if material_count == 0:
        source_rows = _source_score_eligible_active_rows(product)
        missing_dose_refs = []
        for index, row in enumerate(source_rows):
            try:
                amount = float(row.get("quantity") or row.get("dose") or 0)
            except (TypeError, ValueError):
                amount = 0.0
            unit = _norm(row.get("unit"))
            if (
                row.get("has_dose") is False
                or amount <= 0
                or unit in {"", "np", "not_provided", "not_applicable"}
            ):
                missing_dose_refs.append(_row_ref(row, index))
        if source_rows:
            return {
                "readiness": READINESS_INCOMPLETE,
                "reason_code": (
                    "no_scoreable_active_dose"
                    if len(missing_dose_refs) == len(source_rows)
                    else "no_strict_dose_candidates"
                ),
                "collection_status": _safe_dict(
                    product.get("rda_ul_data")
                ).get("collection_status"),
                "assessment_count": len(_safe_list(
                    _safe_dict(product.get("rda_ul_data")).get(
                        "dose_assessments"
                    )
                )),
                "material_active_count": 0,
                "material_exposure_count": len(source_rows),
                "material_assessment_count": 0,
                "incomplete_source_row_refs": missing_dose_refs,
            }
        return {
            "readiness": READINESS_NOT_APPLICABLE,
            "reason_code": "no_score_eligible_active_rows",
            "collection_status": None,
            "assessment_count": 0,
            "material_active_count": 0,
            "material_exposure_count": 0,
            "material_assessment_count": 0,
        }

    def _number(value: Any) -> float | None:
        if isinstance(value, bool):
            return None
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        return parsed if math.isfinite(parsed) else None

    def _unit(value: Any) -> str:
        return re.sub(r"\s+", "", str(value or "").strip().lower())

    def _requirement_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
        value = _number(row.get("source_value"))
        return (
            str(row.get("source_row_ref") or "").strip(),
            _norm(row.get("dose_class")),
            round(value, 12) if value is not None else None,
            _unit(row.get("source_unit")),
        )

    requirements: Dict[tuple[Any, ...], Mapping[str, Any]] = {}
    for row in material_rows:
        requirements.setdefault(_requirement_key(row), row)

    rda_ul = _safe_dict(product.get("rda_ul_data"))
    assessments = _safe_list(rda_ul.get("dose_assessments"))
    collection_status = str(rda_ul.get("collection_status") or "")

    def _matches(
        requirement: tuple[Any, ...],
        assessment: Mapping[str, Any],
    ) -> bool:
        source_ref, dose_class, value, unit = requirement
        assessment_refs = {
            str(assessment.get("source_path") or "").strip(),
            str(assessment.get("source_row_ref") or "").strip(),
            *(
                str(item).strip()
                for item in _safe_list(assessment.get("linked_row_refs"))
            ),
        }
        assessment_refs.discard("")
        if source_ref not in assessment_refs:
            return False
        assessment_class = _norm(assessment.get("dose_class"))
        if dose_class and assessment_class and dose_class != assessment_class:
            return False
        assessment_value = _number(assessment.get("source_value"))
        if value is not None and assessment_value is not None:
            tolerance = max(1e-9, abs(value) * 1e-9)
            if abs(value - assessment_value) > tolerance:
                return False
        assessment_unit = _unit(assessment.get("source_unit"))
        if unit and assessment_unit and unit != assessment_unit:
            return False
        return True

    matched_assessments: Dict[tuple[Any, ...], Mapping[str, Any]] = {}
    for requirement in requirements:
        match = next(
            (
                assessment
                for assessment in assessments
                if isinstance(assessment, Mapping)
                and _matches(requirement, assessment)
            ),
            None,
        )
        if match is not None:
            matched_assessments[requirement] = match

    incomplete_refs = [
        requirement[0]
        for requirement in requirements
        if requirement not in matched_assessments
        or matched_assessments[requirement].get("readiness")
        not in {READINESS_COMPLETE, READINESS_NOT_APPLICABLE}
    ]
    material_assessment_count = len(matched_assessments)
    complete = (
        "dose_assessments" in rda_ul
        and collection_status in {
            READINESS_COMPLETE,
            "complete_with_row_errors",
        }
        and material_assessment_count == len(requirements)
        and not incomplete_refs
    )
    if complete:
        return {
            "readiness": READINESS_COMPLETE,
            "collection_status": collection_status,
            "assessment_count": len(assessments),
            "material_active_count": material_count,
            "material_exposure_count": len(requirements),
            "material_assessment_count": material_assessment_count,
            "assessment_source": "typed_dose_assessments",
        }

    # Schema-2.x migration boundary.  Old enriched fixtures and frozen inputs
    # can prove that the legacy evaluator ran only when both of its result
    # collections exist.  Candidate-release audits reject this inference; a
    # fresh 2.4 build must carry typed dose_assessments for every material row.
    is_fresh_contract = (
        str(product.get("assessment_readiness_contract_version") or "").strip()
        == ASSESSMENT_READINESS_SCHEMA_VERSION
    )
    if (
        not is_fresh_contract
        and "adequacy_results" in rda_ul
        and isinstance(rda_ul.get("adequacy_results"), list)
        and "safety_flags" in rda_ul
        and isinstance(rda_ul.get("safety_flags"), list)
    ):
        return {
            "readiness": READINESS_COMPLETE,
            "collection_status": "legacy_complete",
            "assessment_count": len(rda_ul.get("adequacy_results") or []),
            "material_active_count": material_count,
            "material_exposure_count": len(requirements),
            "material_assessment_count": len(requirements),
            "assessment_source": "schema_2x_legacy_migration_inference",
            "migration_inference": True,
        }

    if not is_fresh_contract and module == "probiotic":
        probiotic = _safe_dict(
            product.get("probiotic_data") or product.get("probiotic_detail")
        )
        try:
            total_billion = float(probiotic.get("total_billion_count") or 0.0)
        except (TypeError, ValueError):
            total_billion = 0.0
        if total_billion > 0:
            return {
                "readiness": READINESS_COMPLETE,
                "collection_status": "module_complete",
                "assessment_count": 1,
                "material_active_count": material_count,
                "material_exposure_count": len(requirements),
                "material_assessment_count": len(requirements),
                "assessment_source": "probiotic_total_cfu",
            }

    return {
        "readiness": READINESS_COMPLETE if complete else READINESS_INCOMPLETE,
        "collection_status": collection_status or None,
        "assessment_count": len(assessments),
        "material_active_count": material_count,
        "material_exposure_count": len(requirements),
        "material_assessment_count": material_assessment_count,
        "incomplete_source_row_refs": list(dict.fromkeys(incomplete_refs)),
    }


def _route_readiness(product: Mapping[str, Any], module: str) -> Dict[str, Any]:
    classification = build_scoring_classification(
        dict(product),
        classification_origin="scoring_readiness_recompute",
    )
    decision = _safe_dict(classification.get("route_decision"))
    resolved_module = str(decision.get("module") or classification.get("route_module") or module)
    reason_codes = list(decision.get("reason_codes") or [])
    complete = (
        resolved_module in _VALID_MODULES
        and resolved_module == module
        and not (_ROUTE_INCOMPLETE_REASON_CODES & set(reason_codes))
    )
    return {
        "readiness": READINESS_COMPLETE if complete else READINESS_INCOMPLETE,
        "module": resolved_module or None,
        "reason_codes": reason_codes,
        "route_confidence": decision.get("confidence") or classification.get("route_confidence"),
        "classifier_version": decision.get("classifier_version"),
    }


def _is_ready(state: str) -> bool:
    return state in {READINESS_COMPLETE, READINESS_NOT_APPLICABLE}


def evaluate_assessment_readiness(
    product: Mapping[str, Any],
    *,
    module: str,
) -> Dict[str, Any]:
    """Return the canonical aggregate readiness decision for one product."""
    product = product if isinstance(product, Mapping) else {}
    evidence = evaluate_evidence_assessment(product, module=module)
    identity = _identity_readiness(product)
    dose = _dose_readiness(
        product,
        evidence["ingredient_assessments"],
        module=module,
    )
    verification = evaluate_verification_assessment(product)
    route = _route_readiness(product, module)
    dimensions = {
        "identity": identity,
        "dose": dose,
        "evidence": evidence,
        "verification": verification,
        "route": route,
    }
    unavailable_reasons = [
        f"{name}_assessment_readiness"
        for name, payload in dimensions.items()
        if name in ENFORCED_READINESS_DIMENSIONS
        and not _is_ready(str(payload.get("readiness") or ""))
    ]
    # Measured but not gating. Kept separate so the backlog stays visible and
    # countable without deciding the product's live eligibility.
    shadow_incomplete_dimensions = [
        name
        for name, payload in dimensions.items()
        if name not in ENFORCED_READINESS_DIMENSIONS
        and not _is_ready(str(payload.get("readiness") or ""))
    ]
    contract_version = str(
        product.get("assessment_readiness_contract_version") or ""
    ).strip()
    return {
        "schema_version": ASSESSMENT_READINESS_SCHEMA_VERSION,
        "enforcement_mode": (
            "enforced"
            if contract_version == ASSESSMENT_READINESS_SCHEMA_VERSION
            else "shadow"
        ),
        "input_contract_version": contract_version or None,
        "enforced_dimensions": sorted(ENFORCED_READINESS_DIMENSIONS),
        **dimensions,
        "is_live_ready": not unavailable_reasons,
        "unavailable_reasons": unavailable_reasons,
        "shadow_incomplete_dimensions": shadow_incomplete_dimensions,
    }
