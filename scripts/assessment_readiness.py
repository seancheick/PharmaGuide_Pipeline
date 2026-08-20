"""Typed readiness for identity, dose, evidence, verification, and routing.

The quality score may only describe a live, non-blocked product after every
material assessment has completed.  This module is the single scoring-time
producer of that cross-cutting result.  It does not change pillar weights or
invent evidence: a reviewed negative result is complete, while a missing
review remains explicitly incomplete.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Mapping

from dose_assessment import has_incomplete_material_dose_assessment
from scoring_input_contract import (
    ROLE_ADJUNCT,
    ROLE_CLAIM_PROMINENT,
    ROLE_MAJOR,
    ROLE_PRIMARY,
    build_scoring_classification,
    classify_ingredient_roles,
    get_scoring_ingredients,
)
from scoring_v4.modules.generic_evidence import (
    DRI_ESSENTIAL_NUTRIENTS,
    resolved_clinical_matches,
)


ASSESSMENT_READINESS_SCHEMA_VERSION = "1.0.0"

READINESS_COMPLETE = "complete"
READINESS_INCOMPLETE = "incomplete"
READINESS_NOT_APPLICABLE = "not_applicable"

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

        if not material:
            state = EVIDENCE_NOT_APPLICABLE
            reason = "non_material_active"
        elif canonical_id in DRI_ESSENTIAL_NUTRIENTS:
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

        if material and state == EVIDENCE_NOT_YET_EVALUATED:
            incomplete_refs.append(source_ref)
        assessments.append({
            "source_row_ref": source_ref,
            "canonical_id": canonical_id,
            "name": row.get("name") or row.get("standard_name"),
            "role": role_name,
            "material": material,
            "state": state,
            "reason_code": reason,
            "evidence_ids": evidence_ids,
        })

    material_count = sum(1 for row in assessments if row["material"])
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
    complete = (
        scoring_input.mapped_count > 0
        and scoring_input.unmapped_count == 0
        and scoring_input.mapped_coverage == 1.0
        and not blocking_findings
    )
    return {
        "readiness": READINESS_COMPLETE if complete else READINESS_INCOMPLETE,
        "mapped_count": scoring_input.mapped_count,
        "unmapped_count": scoring_input.unmapped_count,
        "mapped_coverage": scoring_input.mapped_coverage,
        "contract_findings": list(scoring_input.contract_findings),
        "blocking_contract_findings": blocking_findings,
    }


def _dose_readiness(
    product: Mapping[str, Any],
    material_count: int,
    *,
    module: str,
) -> Dict[str, Any]:
    if material_count == 0:
        return {
            "readiness": READINESS_NOT_APPLICABLE,
            "collection_status": None,
            "assessment_count": 0,
        }
    rda_ul = _safe_dict(product.get("rda_ul_data"))
    assessments = _safe_list(rda_ul.get("dose_assessments"))
    collection_status = str(rda_ul.get("collection_status") or "")
    material_assessment_count = sum(
        1
        for assessment in assessments
        if isinstance(assessment, dict) and assessment.get("material") is True
    )
    complete = (
        "dose_assessments" in rda_ul
        and collection_status == READINESS_COMPLETE
        and material_assessment_count >= material_count
        and not has_incomplete_material_dose_assessment(assessments)
    )
    if complete:
        return {
            "readiness": READINESS_COMPLETE,
            "collection_status": collection_status,
            "assessment_count": len(assessments),
            "material_active_count": material_count,
            "material_assessment_count": material_assessment_count,
            "assessment_source": "typed_dose_assessments",
        }

    # Schema-2.x migration boundary.  Old enriched fixtures and frozen inputs
    # can prove that the legacy evaluator ran only when both of its result
    # collections exist.  Candidate-release audits reject this inference; a
    # fresh 2.4 build must carry typed dose_assessments for every material row.
    if (
        "adequacy_results" in rda_ul
        and isinstance(rda_ul.get("adequacy_results"), list)
        and "safety_flags" in rda_ul
        and isinstance(rda_ul.get("safety_flags"), list)
    ):
        return {
            "readiness": READINESS_COMPLETE,
            "collection_status": "legacy_complete",
            "assessment_count": len(rda_ul.get("adequacy_results") or []),
            "material_active_count": material_count,
            "material_assessment_count": material_count,
            "assessment_source": "schema_2x_legacy_migration_inference",
            "migration_inference": True,
        }

    if module == "probiotic":
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
                "material_assessment_count": material_count,
                "assessment_source": "probiotic_total_cfu",
            }

    return {
        "readiness": READINESS_COMPLETE if complete else READINESS_INCOMPLETE,
        "collection_status": collection_status or None,
        "assessment_count": len(assessments),
        "material_active_count": material_count,
        "material_assessment_count": material_assessment_count,
    }


def _route_readiness(product: Mapping[str, Any], module: str) -> Dict[str, Any]:
    classification = build_scoring_classification(
        dict(product),
        classification_origin="scoring_readiness_recompute",
    )
    decision = _safe_dict(classification.get("route_decision"))
    resolved_module = str(decision.get("module") or classification.get("route_module") or module)
    complete = resolved_module in _VALID_MODULES and resolved_module == module
    return {
        "readiness": READINESS_COMPLETE if complete else READINESS_INCOMPLETE,
        "module": resolved_module or None,
        "reason_codes": list(decision.get("reason_codes") or []),
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
        evidence["material_active_count"],
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
        if not _is_ready(str(payload.get("readiness") or ""))
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
        **dimensions,
        "is_live_ready": not unavailable_reasons,
        "unavailable_reasons": unavailable_reasons,
    }
