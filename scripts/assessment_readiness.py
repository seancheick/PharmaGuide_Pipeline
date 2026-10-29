"""Typed readiness for identity, dose, evidence, verification, and routing.

Identity, dose, verification, and route readiness protect the live catalog.
Evidence-review completeness is measured alongside them without equating an
unfinished curation backlog with weak product quality. This module does not
change pillar weights or invent evidence: a reviewed negative result is
complete, while a missing review remains explicitly incomplete.
"""

from __future__ import annotations

import math
import re
from typing import Any, Dict, Iterable, List, Mapping

from dose_assessment import CONVERSION_FAILED, NO_UL_APPLICABLE
from scoring_v4.exposure import quantity_is_unresolved
from probiotic_measurements import AFU_REVIEW_REASON, pending_afu_measurements, declared_total_cfu, unresolved_cfu_measurements, is_probiotic_source_identity
from scoring_input_contract import (
    MATERIAL_ROLES,
    ROLE_ADJUNCT,
    build_scoring_classification,
    classify_ingredient_roles,
    get_scoring_ingredients,
    get_source_score_eligible_active_rows,
    has_scoring_identity,
    has_source_printed_amount,
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

# Readiness dimensions that gate calculation eligibility. Evidence stays out
# so unfinished curation never changes provisional quality calculations. The
# independent internal release assessment below requires completed owner work.
ENFORCED_READINESS_DIMENSIONS = frozenset({
    "identity",
    "dose",
    "verification",
    "route",
})

CATALOG_DISPOSITION_SCORE_CANDIDATE = "score_candidate"
CATALOG_DISPOSITION_REQUIRES_REMEDIATION = "requires_remediation"
CATALOG_DISPOSITION_INTENTIONAL_NON_SCOREABLE = "intentional_non_scoreable"

_INTENTIONAL_NON_SCOREABLE_RULES = (
    (
        "external_use_only",
        ("external use only", "not intended for consumption"),
        "all",
    ),
    (
        "professional_formulation_material",
        ("not intended for individual use", "qualified professionals only"),
        "all",
    ),
    (
        "formulation_excipient",
        (
            "use as required in the formulation",
            "use as needed per formula",
        ),
        "any",
    ),
    (
        "culinary_sweetener",
        ("as a sweetener", "substitute for sugar"),
        "any",
    ),
    (
        "culinary_food",
        ("for cooking", "cooking or baking", "cooking, baking"),
        "any",
    ),
    (
        "nutrition_beverage",
        ("as a nutritious drink",),
        "any",
    ),
)

_INTENTIONAL_SPECIAL_USE_RULES = (
    (
        "emergency_use_only",
        "POTASSIUM_IODIDE_EMERGENCY_USE_ONLY",
        (
            "should only be taken in emergency situations",
            "short-term use emergency supplement",
        ),
    ),
)

_STANDALONE_CARBOHYDRATE_POWDER_RE = re.compile(
    r"^(?:maltodextrin|dextrose)\s+powder(?:\s+\d+(?:\.\d+)?\s*g)?$",
    re.IGNORECASE,
)


def has_canonical_enforced_dimensions(value: Any) -> bool:
    """Return whether an artifact declares the exact calculation contract."""
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
_PROBIOTIC_IDENTITY_TOKENS = (
    "probiotic",
    "lactobacillus",
    "bifidobacterium",
    "bacillus_coagulans",
    "streptococcus_salivarius",
    "saccharomyces_boulardii",
)
_OMEGA_RELEVANT_CANONICALS = frozenset({
    "epa",
    "dha",
    "epa_dha",
    "fish_oil",
    "krill_oil",
    "cod_liver_oil",
    "algal_oil",
    "algae_oil",
    "omega_3",
    "omega3",
    "omega_3_fatty_acids",
})
_SPORTS_PRIMARY_IDENTITY_CANONICALS = frozenset({
    "protein",
    "whey_protein",
    "casein",
    "pea_protein",
    "rice_protein",
    "soy_protein",
    "creatine_monohydrate",
    "beta_alanine",
    "l_citrulline",
    "hmb",
    "l_leucine",
    "l_isoleucine",
    "l_valine",
})
_SPORTS_RELEVANT_CANONICALS = _SPORTS_PRIMARY_IDENTITY_CANONICALS | frozenset({
    "creatine",
    "creatine_hydrochloride",
    "creatine_hcl",
    "creatine_nitrate",
    "creatine_citrate",
    "buffered_creatine",
    "magnesium_creatine_chelate",
    "branched_chain_amino_acids",
    "eaa",
    "essential_amino_acids",
    "l_arginine",
    "l_glutamine",
    "l_carnitine",
    "acetyl_l_carnitine",
    "alpha_gpc",
    "atp",
    "adenosine_triphosphate",
    "betaine",
    "betaine_anhydrous",
    "tmg_betaine",
    "taurine",
    "l_tyrosine",
    "tyrosine",
    "caffeine",
    "caffeine_anhydrous",
    "agmatine",
    "agmatine_sulfate",
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


def _probiotic_native_evidence_state(product: Mapping[str, Any], row: Mapping[str, Any] | None = None) -> str | None:
    from studied_formulas import (
        assess_probiotic_evidence, clinical_strain_matches_source_row,
        independent_clinical_strains, label_owned_native_strains, reviewed_native_context_present,
    )
    owned = label_owned_native_strains(product)
    if row is not None:
        owned = [strain for strain in owned
                 if clinical_strain_matches_source_row(product, strain, row)]
    if owned:
        reviewed = assess_probiotic_evidence(product)["strain_assessments"]
        owned_ids = {strain.get("clinical_id") for strain in owned}
        conclusions = [assessment for assessment in reviewed
                       if assessment.get("clinical_id") in owned_ids]
        if conclusions and all(
                assessment.get("status") == "strain_reviewed_no_qualifying_human_evidence"
                or (assessment.get("status") == "strain_context_not_applicable"
                    and not assessment.get("research_accepted")
                    and reviewed_native_context_present(assessment))
                for assessment in conclusions):
            # A completed contextual review can be limited without supporting
            # this product. Do not turn that applicability gap into missing review.
            return EVIDENCE_EVALUATED_LIMITED_OR_NEGATIVE
    strains = independent_clinical_strains(product)
    if row is not None:
        strains = [
            strain for strain in strains
            if clinical_strain_matches_source_row(product, strain, row)
        ]
    if not strains:
        return None
    # The enricher's clinical_support_level follows the evidence direction; an
    # empty value is reviewed evidence that supports no claim (null, unresolved)
    # and must not fall back to the direction-blind registry evidence_level.
    tokens = {
        _norm(row.get("clinical_support_level")) or "not_supportive"
        if "clinical_support_level" in row else
        _norm(
            row.get("evidence_level")
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


def _resolved_evidence_assessment(resolution: Any) -> tuple[str, str, str | None]:
    """Project the canonical resolution into the existing readiness vocabulary."""
    from evidence_resolver import EvidenceDisposition

    disposition = resolution.disposition
    if (disposition == EvidenceDisposition.RESOLVED_BY_AUTHORITY.value
            and "nutrition_authority" in resolution.owner_facts
            and (resolution.owner_facts["nutrition_authority"].get("is_essential") is True
                 or resolution.reason_code == "dietary_reference_intake_authority_established")):
        return EVIDENCE_EVALUATED_SUPPORTED, resolution.reason_code, EVIDENCE_APPLICABILITY_NUTRITION_AUTHORITY
    if (disposition in {
            EvidenceDisposition.NO_QUALIFYING_HUMAN_EVIDENCE.value,
            EvidenceDisposition.REVIEWED_NULL_UNFAVORABLE.value,
        } and ("literature_evidence" in resolution.owner_facts
               or (disposition == EvidenceDisposition.REVIEWED_NULL_UNFAVORABLE.value
                   and "backed_clinical_studies" in resolution.owner_facts))):
        return EVIDENCE_EVALUATED_LIMITED_OR_NEGATIVE, resolution.reason_code, None
    if (disposition == EvidenceDisposition.RESOLVED_BY_REVIEWED_CLINICAL_EVIDENCE.value
            and "literature_evidence" in resolution.owner_facts):
        state = (EVIDENCE_EVALUATED_SUPPORTED if resolution.points_eligible
                 else EVIDENCE_EVALUATED_LIMITED_OR_NEGATIVE)
        return state, resolution.reason_code, None
    completed_scope_reasons = {
        "clinical_form_mismatch", "clinical_delivery_mismatch",
        "clinical_identity_excluded", "clinical_form_excluded",
        "formula_reference_not_individual_evidence", "clinical_population_mismatch",
        "label_purpose_evidence_mismatch",
    }
    if (disposition == EvidenceDisposition.RESEARCH_PRESENT_APPLICABILITY_UNESTABLISHED.value
            and (("backed_clinical_studies" in resolution.matched_owners
                  and resolution.reason_code in completed_scope_reasons | {
                      "reference_only_clinical_record",
                      "dose_below_studied_range", "form_mismatch_with_clinical_trials",
                  })
                 or ("literature_evidence" in resolution.owner_facts
                     and resolution.reason_code in completed_scope_reasons))):
        # Reviewed non-applicability is a conclusion; a held source is not.
        return EVIDENCE_EVALUATED_LIMITED_OR_NEGATIVE, resolution.reason_code, None
    if disposition == EvidenceDisposition.NOT_EFFICACY_RELEVANT.value:
        return EVIDENCE_NOT_APPLICABLE, resolution.reason_code, EVIDENCE_APPLICABILITY_NOT_APPLICABLE
    reason = (resolution.reason_code if resolution.reason_code == "clinical_sources_ineligible"
              else "no_reviewed_evidence_assessment")
    return EVIDENCE_NOT_YET_EVALUATED, reason, None


def evaluate_evidence_assessment(
    product: Mapping[str, Any],
    *,
    module: str,
) -> Dict[str, Any]:
    """Classify every score row without treating a missing match as a review."""
    # Use the same subject set and whole-label prominence context as the
    # Evidence resolver. Undosed named blend members still need a review.
    from evidence_resolver import _evidence_subject_roles, evidence_owner_canonicals
    subjects, subject_roles, other_rows, other_roles = _evidence_subject_roles(product, module)
    evidence_owners = evidence_owner_canonicals(product, module=module)
    # Retain structural strict rows for the exposure consumer, while marking
    # them outside the individual Evidence question.
    rows, roles = subjects + other_rows, subject_roles + other_roles
    matches, recovered_matches = resolved_clinical_matches(
        dict(product), owner_scoped=module in {"generic", "fiber_digestive", "sports"}
    )
    indexed_matches = [
        (match, _match_identity_keys(match))
        for match in matches
        if isinstance(match, dict)
    ]
    assessments: List[Dict[str, Any]] = []
    incomplete_refs: List[str] = []
    for index, (row, role) in enumerate(zip(rows, roles)):
        canonical_id = _norm(row.get("canonical_id")) or None
        source_ref = _row_ref(row, index)
        role_name = str(role.get("role") or ROLE_ADJUNCT)
        material = role_name in MATERIAL_ROLES
        # A source-owned native review is the same conclusion on a mixed
        # product route. The native helper still binds it to this label row.
        probiotic_state = (_probiotic_native_evidence_state(product, row)
                           if module == "probiotic" or is_probiotic_source_identity(row)
                           else None)
        linked = [
            match
            for match, keys in indexed_matches
            if (source_ref in match.get("matched_source_row_refs", [])
                if match.get("matched_source_row_refs") else _identity_keys(row) & keys)
        ]
        evidence_ids = list(dict.fromkeys(
            evidence_id
            for evidence_id in (_entry_id(match) for match in linked)
            if evidence_id
        ))

        applicability = EVIDENCE_APPLICABILITY_INDIVIDUAL
        if index >= len(subjects):
            applicability = EVIDENCE_APPLICABILITY_NOT_APPLICABLE
            state = EVIDENCE_NOT_APPLICABLE
            reason = "structural_row_not_evidence_subject"
        elif not material and canonical_id not in evidence_owners:
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
        elif any(match.get("evidence_origin") == "verified_formula_contract" for match in linked):
            applicability = EVIDENCE_APPLICABILITY_MODULE_AGGREGATE
            state = EVIDENCE_EVALUATED_SUPPORTED
            reason = "reviewed_complete_formula_evidence"
        elif any(_is_supportive_human_match(match) for match in linked):
            state = EVIDENCE_EVALUATED_SUPPORTED
            reason = "reviewed_human_evidence_supportive"
        elif linked:
            state = EVIDENCE_EVALUATED_LIMITED_OR_NEGATIVE
            reason = "reviewed_evidence_limited_or_negative"
        elif probiotic_state is not None:
            state = probiotic_state
            reason = "reviewed_native_clinical_strain_evidence"
        else:
            # The canonical resolver owns completed negative and inapplicable
            # reviews too. Missing positive credit is not a missing review.
            from evidence_resolver import resolve_evidence_for_row
            resolution = resolve_evidence_for_row(row, product=product)
            state, reason, resolved_applicability = _resolved_evidence_assessment(resolution)
            if resolved_applicability is not None:
                applicability = resolved_applicability

        if (
            applicability == EVIDENCE_APPLICABILITY_INDIVIDUAL
            and state == EVIDENCE_NOT_YET_EVALUATED
        ):
            incomplete_refs.append(source_ref)
        dose_class = _norm(row.get("dose_class"))
        source_value = row.get("quantity", row.get("dose_value"))
        source_unit = row.get("unit") or row.get("dose_unit")
        if dose_class == "enzyme_activity":
            activity_value = row.get("activity_quantity")
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
    # D31: an undosed owner can have a research question without a
    # material Dose row. Keep physical material flags and amounts intact.
    readiness = (
        READINESS_NOT_APPLICABLE
        if material_count == 0 and individual_count == 0
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


def evaluate_catalog_disposition(product: Mapping[str, Any]) -> Dict[str, Any]:
    """Separate explicit QA-only labels from genuine scoring remediation.

    This classifier is deliberately narrow. A product is only called
    intentionally non-scoreable when either a verified special-use policy and
    its label wording agree, or the strict scoring contract has no rows and
    the label itself states a non-consumer, formulation, sweetener, or culinary
    use. Ambiguous zero-dose supplements remain in remediation.
    """
    statements = _safe_list(product.get("statements"))
    normalized_statements: list[tuple[str, str]] = []
    for index, statement in enumerate(statements):
        if not isinstance(statement, Mapping):
            continue
        notes = re.sub(
            r"\s+",
            " ",
            str(statement.get("notes") or "").strip().casefold(),
        )
        if notes:
            normalized_statements.append((f"statements[{index}].notes", notes))

    special_use_codes = {
        str(flag.get("code") or "").strip()
        for flag in _safe_list(_safe_dict(product.get("rda_ul_data")).get(
            "special_use_flags"
        ))
        if isinstance(flag, Mapping)
    }
    for reason_code, required_code, phrases in _INTENTIONAL_SPECIAL_USE_RULES:
        if required_code not in special_use_codes:
            continue
        matching_paths = [
            path
            for path, notes in normalized_statements
            if any(phrase in notes for phrase in phrases)
        ]
        if matching_paths:
            return {
                "disposition": CATALOG_DISPOSITION_INTENTIONAL_NON_SCOREABLE,
                "reason_code": reason_code,
                "evidence_paths": matching_paths,
            }

    scoring_input = get_scoring_ingredients(
        dict(product),
        strict=True,
        allow_legacy_fallback=False,
    )
    if scoring_input.rows:
        return {
            "disposition": CATALOG_DISPOSITION_SCORE_CANDIDATE,
            "reason_code": "strict_scoring_rows_present",
            "evidence_paths": [],
        }
    if get_source_score_eligible_active_rows(product):
        return {
            "disposition": CATALOG_DISPOSITION_REQUIRES_REMEDIATION,
            "reason_code": "source_active_assessment_required",
            "evidence_paths": [],
        }

    for field in ("product_name", "fullName", "name"):
        title = re.sub(r"\s+", " ", str(product.get(field) or "").strip())
        if title and _STANDALONE_CARBOHYDRATE_POWDER_RE.fullmatch(title):
            return {
                "disposition": CATALOG_DISPOSITION_INTENTIONAL_NON_SCOREABLE,
                "reason_code": "standalone_carbohydrate_powder",
                "evidence_paths": [field],
            }

    for reason_code, phrases, match_mode in _INTENTIONAL_NON_SCOREABLE_RULES:
        matching_paths = []
        for path, notes in normalized_statements:
            phrase_matches = [phrase in notes for phrase in phrases]
            matched = all(phrase_matches) if match_mode == "all" else any(phrase_matches)
            if matched:
                matching_paths.append(path)
        if matching_paths:
            return {
                "disposition": CATALOG_DISPOSITION_INTENTIONAL_NON_SCOREABLE,
                "reason_code": reason_code,
                "evidence_paths": matching_paths,
            }

    return {
        "disposition": CATALOG_DISPOSITION_REQUIRES_REMEDIATION,
        "reason_code": "no_score_eligible_active_rows",
        "evidence_paths": [],
    }


def evaluate_verification_assessment(product: Mapping[str, Any]) -> Dict[str, Any]:
    """Preserve verified-present, evaluated-absent, and not-evaluated."""
    cert = product.get("certification_data")
    if isinstance(cert, Mapping):
        explicit = cert.get("verification_assessment")
        if isinstance(explicit, Mapping):
            state = str(explicit.get("state") or "")
            readiness = str(explicit.get("readiness") or "")
            # State and readiness must agree: an evaluated result (present or
            # absent) is complete, and not_evaluated is never complete.
            if (state, readiness) in {
                (VERIFICATION_VERIFIED_PRESENT, READINESS_COMPLETE),
                (VERIFICATION_VERIFIED_ABSENT, READINESS_COMPLETE),
                (VERIFICATION_NOT_EVALUATED, READINESS_INCOMPLETE),
            }:
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
        from scoring_v4.cert_evidence import (
            cert_entry_brand_matches_product,
            is_verified_product_cert_entry,
        )

        entries = _verified_programs(product)
        verified = [
            entry
            for entry in entries
            if is_verified_product_cert_entry(dict(product), dict(entry))
        ]
        # Another brand's listing is an evaluated no-match, not incomplete
        # evidence for this product.
        product_scope_candidates = [
            entry for entry in entries
            if str(entry.get("scope") or "") in {"sku", "product_line"}
            and cert_entry_brand_matches_product(dict(product), dict(entry))
        ]
        if product_scope_candidates and not verified:
            return {
                "state": VERIFICATION_NOT_EVALUATED,
                "readiness": READINESS_INCOMPLETE,
                "reason_code": "legacy_registry_match_missing_current_provenance",
                "matched_programs": [],
                "migration_inference": True,
            }
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


def has_sports_primary_identity_signal(product: Mapping[str, Any]) -> bool:
    """Return whether a rejected row preserves a disclosed sports identity."""
    scoring_input = get_scoring_ingredients(dict(product), strict=True)
    for rejected in scoring_input.rejected_rows:
        row = rejected.row if isinstance(rejected.row, dict) else {}
        if rejected.reason not in {
            "missing_dose_evidence",
            "product_evidence_not_scoreable:missing_primary_sports_dose",
        }:
            continue
        if _norm(row.get("canonical_id")) in _SPORTS_PRIMARY_IDENTITY_CANONICALS:
            return True
    return False


def has_module_relevant_identity(
    product: Mapping[str, Any],
    module: str,
    *,
    rows: Iterable[Mapping[str, Any]] | None = None,
) -> bool:
    """Return whether identity evidence is relevant to the routed module.

    Generic mapping coverage answers whether rows were identified. Specialized
    modules additionally need at least one identity that their rubric can
    interpret; mapped calcium, fiber, or a blend header cannot stand in for a
    disclosed protein, omega, or probiotic identity.
    """
    if module not in {"probiotic", "omega", "sports"}:
        return True
    scoring_rows = list(rows) if rows is not None else list(
        get_scoring_ingredients(
            dict(product),
            strict=True,
            allow_legacy_fallback=False,
        ).rows
    )
    if module == "probiotic":
        probiotic_data = _safe_dict(product.get("probiotic_data"))
        try:
            strain_count = float(probiotic_data.get("total_strain_count") or 0)
        except (TypeError, ValueError):
            strain_count = 0.0
        if math.isfinite(strain_count) and strain_count > 0:
            return True
        for blend in _safe_list(probiotic_data.get("probiotic_blends")):
            if isinstance(blend, Mapping) and any(
                str(strain).strip() for strain in _safe_list(blend.get("strains"))
            ):
                return True
        if any(_norm(row.get("evidence_type")) == "probiotic_cfu" for row in scoring_rows):
            return True
        for row in scoring_rows:
            identity = " ".join(
                _norm(row.get(key))
                for key in ("canonical_id", "name", "standard_name", "standardName")
            )
            if any(token in identity for token in _PROBIOTIC_IDENTITY_TOKENS):
                return True
        return False
    if module == "omega":
        return any(
            _norm(row.get("evidence_type")) == "omega_epa_dha_aggregate"
            or _norm(row.get("canonical_id")) in _OMEGA_RELEVANT_CANONICALS
            for row in scoring_rows
        )
    return (
        any(
            _norm(row.get("evidence_type")) == "sports_primary_dose"
            or _norm(row.get("canonical_id")) in _SPORTS_RELEVANT_CANONICALS
            for row in scoring_rows
        )
        or has_sports_primary_identity_signal(product)
    )


def _identity_readiness(
    product: Mapping[str, Any],
    module: str,
    *,
    catalog_disposition: Mapping[str, Any],
) -> Dict[str, Any]:
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
    # The contract owns what counts as a scoring identity: a verified row by
    # its mapped identity, a structural label-taxonomy anchor (an unmapped
    # blend total) by its anchor alone. Its `mapped` flag is truthfully False
    # and must not be re-read here as "unidentified".
    mapped_product_evidence = [
        row
        for row in product_evidence_rows
        if row.get("scoreable_identity") is True and has_scoring_identity(row)
    ]
    source_rows = get_source_score_eligible_active_rows(product)
    mapped_source_rows = [
        row
        for row in source_rows
        if row.get("mapped_identity") is not False
        and bool(str(row.get("canonical_id") or "").strip())
        and _norm(row.get("identity_disposition"))
        not in {"unresolved", "rejected", "parse_error", "identity_conflict", "missing_display_label"}
    ]
    source_mapped_count = len(mapped_source_rows)
    source_unmapped_count = len(source_rows) - source_mapped_count
    source_mapped_coverage = (
        source_mapped_count / len(source_rows)
        if source_rows
        else None
    )
    intentionally_non_scoreable = (
        catalog_disposition.get("disposition")
        == CATALOG_DISPOSITION_INTENTIONAL_NON_SCOREABLE
    )
    if intentionally_non_scoreable:
        source_identity_complete = False
        reason_code = str(
            catalog_disposition.get("reason_code")
            or "intentional_non_scoreable_product"
        )
    elif scoring_input.zero_scorable_reason:
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
    module_identity_complete = has_module_relevant_identity(
        product,
        module,
        # Identity and dose are separate readiness dimensions. A mapped label
        # active remains valid module identity when the scorer excludes it only
        # because its dose is absent. Passing the cleaner-owned source rows here
        # lets dose readiness name that actual defect without making carrier or
        # structural rows scoreable.
        rows=[*scoring_input.rows, *source_rows],
    )
    if source_identity_complete and not module_identity_complete:
        reason_code = f"missing_{module}_relevant_identity"
    complete = source_identity_complete and module_identity_complete and not blocking_findings
    return {
        "readiness": (
            READINESS_NOT_APPLICABLE
            if intentionally_non_scoreable
            else READINESS_COMPLETE if complete else READINESS_INCOMPLETE
        ),
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
        "module": module,
        "module_relevant_identity": module_identity_complete,
    }


def _dose_readiness(
    product: Mapping[str, Any],
    evidence_assessments: Iterable[Mapping[str, Any]],
    *,
    module: str,
) -> Dict[str, Any]:
    # A typed assessment or a "no UL" finding cannot turn conflicting
    # source quantities into completed dose work. Reuse the exposure owner's
    # qualifier decision, before route/material projections can drop the row.
    unresolved_source_refs = sorted({
        _row_ref(row, index)
        for index, row in enumerate(get_source_score_eligible_active_rows(product))
        if quantity_is_unresolved(row)
    })
    if unresolved_source_refs:
        return {"readiness": READINESS_INCOMPLETE, "collection_status": "incomplete",
                "assessment_source": "source_quantities", "reason_code": "unresolved_source_quantity",
                "incomplete_source_row_refs": unresolved_source_refs}
    # Measurement holds follow their source rows, regardless of product route.
    unresolved = unresolved_cfu_measurements(product)
    if unresolved:
        return {"readiness": READINESS_INCOMPLETE, "collection_status": "incomplete",
                "assessment_source": "probiotic_measurements", "reason_code": "unresolved_source_quantity",
                "incomplete_source_row_refs": sorted({r["source_row_ref"] for r in unresolved if r["source_row_ref"]}),
                "measurements": unresolved}
    afu_rows = pending_afu_measurements(product)
    if afu_rows:
        return {
            "readiness": READINESS_INCOMPLETE,
            "collection_status": "unresolved_reference",
            "assessment_source": "probiotic_afu_measurements",
            "reason_code": AFU_REVIEW_REASON,
            "incomplete_source_row_refs": sorted({row["source_row_ref"] for row in afu_rows}),
            "measurements": afu_rows,
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

    material_rows = [
        row
        for row in evidence_assessments
        if isinstance(row, Mapping) and row.get("material") is True
    ]
    material_count = len(material_rows)
    rda_ul = _safe_dict(product.get("rda_ul_data"))
    assessments = _safe_list(rda_ul.get("dose_assessments"))
    collection_status = str(rda_ul.get("collection_status") or "")
    failed_conversion_refs = sorted({
        str(assessment.get("source_path") or assessment.get("source_row_ref") or "unknown")
        for assessment in assessments
        if isinstance(assessment, Mapping)
        and assessment.get("material") is True
        and assessment.get("conversion_status") == CONVERSION_FAILED
        and assessment.get("ul_assessment_status") == NO_UL_APPLICABLE
    })
    # "No UL" cannot waive an unresolved nutrient-specific unit, even if the
    # unrecognized unit caused an adjunct evidence role. Other incomplete dose
    # representations still use the source-owned assessment matching below.
    if failed_conversion_refs:
        return {
            "readiness": READINESS_INCOMPLETE,
            "reason_code": "conversion_failed",
            "collection_status": collection_status,
            "assessment_count": len(assessments),
            "material_active_count": material_count,
            "assessment_source": "typed_dose_assessments",
            "incomplete_source_row_refs": failed_conversion_refs,
        }
    if material_count == 0:
        source_rows = get_source_score_eligible_active_rows(product)
        assessments = [
            assessment
            for assessment in _safe_list(rda_ul.get("dose_assessments"))
            if isinstance(assessment, Mapping)
        ]

        def _ready_typed_source_assessment(
            source_ref: str, source_row: Mapping[str, Any],
        ) -> Mapping[str, Any] | None:
            for assessment in assessments:
                assessment_refs = {
                    str(assessment.get("source_path") or "").strip(),
                    str(assessment.get("source_row_ref") or "").strip(),
                    *(
                        str(item).strip()
                        for item in _safe_list(
                            assessment.get("linked_row_refs")
                        )
                    ),
                }
                if source_ref not in assessment_refs:
                    continue
                source_value = _number(assessment.get("source_value"))
                source_unit = _unit(assessment.get("source_unit"))
                if (
                    source_value is not None
                    and (source_value > 0 or (
                        source_value == 0
                        and _number(source_row.get("quantity")) == 0
                        and source_unit == _unit(source_row.get("unit"))
                        and has_source_printed_amount(source_row, allow_zero=True)
                    ))
                    and source_unit
                    and assessment.get("readiness")
                    in {READINESS_COMPLETE, READINESS_NOT_APPLICABLE}
                ):
                    return assessment
            return None

        ready_source_assessments: Dict[str, Mapping[str, Any]] = {}
        missing_dose_refs = []
        for index, row in enumerate(source_rows):
            source_ref = _row_ref(row, index)
            typed = _ready_typed_source_assessment(source_ref, row)
            if typed is not None:
                ready_source_assessments[source_ref] = typed
                continue
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
                missing_dose_refs.append(source_ref)
            else:
                # A disclosed amount without a matching typed assessment is
                # still incomplete; the raw value is never a release fallback.
                missing_dose_refs.append(source_ref)
        if source_rows:
            if (
                collection_status
                in {READINESS_COMPLETE, "complete_with_row_errors"}
                and len(ready_source_assessments) == len(source_rows)
            ):
                return {
                    "readiness": READINESS_COMPLETE,
                    "collection_status": collection_status,
                    "assessment_count": len(assessments),
                    "material_active_count": 0,
                    "material_exposure_count": len(source_rows),
                    "material_assessment_count": len(
                        ready_source_assessments
                    ),
                    "assessment_source": "typed_source_dose_assessments",
                }
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
                "assessment_count": len(assessments),
                "material_active_count": 0,
                "material_exposure_count": len(source_rows),
                "material_assessment_count": len(ready_source_assessments),
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

    probiotic_total_cfu = 0.0
    if module == "probiotic":
        probiotic = _safe_dict(
            product.get("probiotic_data")
        )
        probiotic_total_cfu = declared_total_cfu(probiotic)

    def _is_declared_probiotic_total(requirement: tuple[Any, ...]) -> bool:
        """Return whether the module-owned total proves this CFU exposure.

        CFU has no RDA/UL assessment. The scoring contract's product-level CFU
        row is itself the typed dose evidence, but only when its value agrees
        with the source-owned total. This deliberately does not accept a
        caller-supplied strain count, clinical dose, AFU value, or mismatched
        projection.
        """
        _source_ref, dose_class, value, unit = requirement
        if (
            module != "probiotic"
            or dose_class != "probiotic_cfu"
            or value is None
            or value <= 0
            or unit != "cfu"
            or probiotic_total_cfu <= 0
        ):
            return False
        tolerance = max(1e-9, abs(probiotic_total_cfu) * 1e-9)
        return abs(value - probiotic_total_cfu) <= tolerance

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

    module_owned_assessments: Dict[tuple[Any, ...], Mapping[str, Any]] = {
        requirement: {
            "readiness": READINESS_COMPLETE,
            "dose_class": "probiotic_cfu",
            "source_value": requirement[2],
            "source_unit": "CFU",
            "assessment_source": "probiotic_total_cfu",
        }
        for requirement in requirements
        if _is_declared_probiotic_total(requirement)
    }
    matched_assessments: Dict[tuple[Any, ...], Mapping[str, Any]] = dict(
        module_owned_assessments
    )
    for requirement in requirements:
        if requirement in matched_assessments:
            continue
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
    typed_requirements = set(requirements) - set(module_owned_assessments)
    typed_collection_complete = (
        not typed_requirements
        or (
            "dose_assessments" in rda_ul
            and collection_status in {
            READINESS_COMPLETE,
            "complete_with_row_errors",
            }
        )
    )
    complete = (
        typed_collection_complete
        and material_assessment_count == len(requirements)
        and not incomplete_refs
    )
    if complete:
        if module_owned_assessments and typed_requirements:
            assessment_source = (
                "typed_dose_assessments_and_probiotic_total_cfu"
            )
        elif module_owned_assessments:
            assessment_source = "probiotic_total_cfu"
        else:
            assessment_source = "typed_dose_assessments"
        return {
            "readiness": READINESS_COMPLETE,
            "collection_status": collection_status or "module_complete",
            "assessment_count": len(assessments) + len(module_owned_assessments),
            "material_active_count": material_count,
            "material_exposure_count": len(requirements),
            "material_assessment_count": material_assessment_count,
            "assessment_source": assessment_source,
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
            product.get("probiotic_data")
        )
        if declared_total_cfu(probiotic) > 0:
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
    catalog_disposition = evaluate_catalog_disposition(product)
    identity = _identity_readiness(
        product,
        module,
        catalog_disposition=catalog_disposition,
    )
    # Evidence includes undosed blend subjects. Dose retains its strict
    # exposure contract; no parent amount or new denominator is inferred.
    from evidence_resolver import evidence_row_key
    strict_keys = {evidence_row_key(row) for row in
                   get_scoring_ingredients(dict(product), strict=True,
                                           allow_legacy_fallback=False).rows}
    dose = _dose_readiness(
        product,
        [row for row in evidence["ingredient_assessments"]
         if evidence_row_key({**row, "raw_source_path": row["source_row_ref"]}) in strict_keys],
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
    unavailable_reasons = []
    if (
        catalog_disposition.get("disposition")
        == CATALOG_DISPOSITION_INTENTIONAL_NON_SCOREABLE
    ):
        unavailable_reasons.append("intentional_non_scoreable_product")
    unavailable_reasons.extend(
        f"{name}_assessment_readiness"
        for name, payload in dimensions.items()
        if name in ENFORCED_READINESS_DIMENSIONS
        and not _is_ready(str(payload.get("readiness") or ""))
    )
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
        "catalog_disposition": catalog_disposition,
        **dimensions,
        "is_live_ready": not unavailable_reasons,
        "unavailable_reasons": unavailable_reasons,
        "shadow_incomplete_dimensions": shadow_incomplete_dimensions,
    }


def _current_omega_authority_receipt(product: Mapping, evidence: Mapping) -> bool:
    """Validate the existing shared omega nutrition result, not a clinical receipt."""
    from evidence_resolver import resolve_omega_evidence_standard
    from scoring_v4.quality_score_config import config

    meta = _safe_dict(evidence.get("metadata"))
    if meta.get("selected_nutrition_authority") != "omega_3":
        return False
    resolved = resolve_omega_evidence_standard(product)
    cfg = config()
    expected = round(resolved["score"] * cfg["evidence_subscale"]["archetype_reference"]["generic_single_molecule"]
                     / cfg["pillars"]["evidence"]["weight"], 4)
    return bool(resolved["applicability_qualified"] and expected > 0
        and meta.get("selected_nutrition_authority") == "omega_3"
        and meta.get("nutrition_authority_canonical") == "omega_3"
        and meta.get("nutrition_authority_floor_applied") is True
        and meta.get("primary_evidence_floor_decisive") is True
        and evidence.get("score") == meta.get("primary_evidence_floor") == expected
        and _safe_dict(evidence.get("components")).get("primary_evidence_floor") == expected
        and meta.get("source_references") == resolved["source_references"])


def evaluate_release_assessment(
    product: Mapping[str, Any], readiness: Mapping[str, Any],
    module_breakdown: Mapping[str, Any], *, unfinished_source: str | None,
) -> Dict[str, Any]:
    """Internal completion decision; never changes provisional calculation.

    Consume the existing identity, exposure and clinical owners. A completed
    negative answer and an explicitly recorded label limitation are conclusions;
    missing owner facts are not. Scored artifacts retain this receipt because
    the enriched source needed to reconstruct it is intentionally omitted.
    """
    blockers = []
    if unfinished_source:
        blockers.append(unfinished_source)
    intentional = (_safe_dict(readiness.get("catalog_disposition")).get("disposition")
                   == CATALOG_DISPOSITION_INTENTIONAL_NON_SCOREABLE)
    dimensions = _safe_dict(module_breakdown.get("dimensions"))
    evidence_meta = _safe_dict(_safe_dict(dimensions.get("evidence")).get("metadata"))
    module = str(module_breakdown.get("module") or "")
    for name in ("identity", "dose", "verification", "route"):
        payload = _safe_dict(readiness.get(name))
        if intentional and name in {"identity", "dose", "route"}:
            continue
        if payload.get("migration_inference") is True:
            blockers.append(f"{name}_migration_inference")
        if _is_ready(str(payload.get("readiness") or "")):
            continue
        # Only an explicit source-owned missing label amount closes this
        # particular question. A missing typed row or failed printed conversion
        # must never be waived by no_scoreable_active_dose.
        refs = payload.get("incomplete_source_row_refs") or []
        typed = _safe_list(_safe_dict(product.get("rda_ul_data")).get("dose_assessments"))
        hidden_refs = {
            str(row.get("source_path") or row.get("source_row_ref") or "")
            for row in typed if isinstance(row, dict)
            and row.get("reason_code") == "amount_not_declared"
            and row.get("source_value") in (None, "")
        }
        if name == "dose" and refs and set(refs) <= hidden_refs:
            continue
        blockers.append(f"{name}_assessment_incomplete")
    if not intentional:
        if module == "omega":
            # Native omega standards own this question; generic evidence is
            # retained only as audit metadata and contributes no omega credit.
            if evidence_meta.get("evidence_result_state") not in {
                    "evaluated_authority", "evaluated_applicable", "applicability_unestablished"}:
                blockers.append("omega_evidence_assessment_incomplete")
        elif module == "probiotic":
            native = _safe_dict(evidence_meta.get("evidence_assessment"))
            strains = _safe_list(native.get("strain_assessments"))
            pending = {"strain_reference_unreviewed", "strain_identity_mismatch",
                       "strain_identity_or_review_unresolved", "strain_context_review_pending",
                       "strain_dose_reference_unreviewed"}
            reviewed_conclusion = evidence_meta.get("evidence_result_state") in {
                "evaluated_applicable", "evaluated_null", "evaluated_unfavorable",
                "no_qualifying_human_evidence",
            }
            if (not native or not reviewed_conclusion
                    or any(row.get("status") in pending for row in strains)):
                blockers.append("probiotic_evidence_assessment_incomplete")
            if float(_safe_dict(dimensions.get("evidence")).get("score") or 0) > 0:
                contexts = evidence_meta.get("contributing_native_contexts")
                records = evidence_meta.get("contributing_record_assessments")
                if not isinstance(contexts, list) or not isinstance(records, list) or not (contexts or records):
                    blockers.append("probiotic_contributing_evidence_receipts_missing")
                else:
                    from studied_formulas import context_accepted_for_scoring
                    from clinical_evidence_schema import validate_frozen_context
                    for context in contexts:
                        if (not context_accepted_for_scoring(context)
                                or validate_frozen_context(context, require_complete_review=True)):
                            blockers.append("probiotic_contributing_context_incomplete:" + str(context.get("context_id") or "unknown"))
                    for receipt in records:
                        from clinical_applicability import assess_clinical_source_review
                        if not assess_clinical_source_review(receipt)["is_complete"]:
                            blockers.append("contributing_source_review_incomplete:" + str(receipt.get("id") or "unknown"))
                        if (receipt.get("status") not in {"applicable", "assessed_studied_formula"}
                                or receipt.get("scope_qualification_complete") is not True):
                            blockers.append("clinical_applicability_unreviewed:" + str(receipt.get("id") or "unknown"))
        elif not _is_ready(str(_safe_dict(readiness.get("evidence")).get("readiness") or "")):
            blockers.append("evidence_assessment_incomplete")
        # The scoring owner records only records used by the winning generic
        # path. Missing applicability cannot publish provisional legacy credit.
        if module in {"generic", "sports", "fiber_digestive"}:
            if any(isinstance(row, Mapping)
                   and row.get("scoring_input_kind") == "product_level_evidence"
                   and row.get("evidence_applicability") == EVIDENCE_APPLICABILITY_MODULE_AGGREGATE
                   for row in _safe_list(_safe_dict(readiness.get("evidence")).get("ingredient_assessments"))):
                from evidence_resolver import EvidenceDisposition, resolve_product_evidence
                from scoring_v4.modules.generic_evidence import evidence_completeness_gap

                aggregate = resolve_product_evidence(dict(product), owner_scoped=True, module=module)
                gap = evidence_completeness_gap(dict(product), aggregate, owner_scoped=True)
                pending_applicability = any(
                    resolution.disposition == EvidenceDisposition.RESEARCH_PRESENT_APPLICABILITY_UNESTABLISHED.value
                    and _resolved_evidence_assessment(resolution)[0] == EVIDENCE_NOT_YET_EVALUATED
                    for resolution in aggregate.resolutions
                )
                if gap or pending_applicability:
                    blockers.append("evidence_assessment_incomplete")
            receipts = evidence_meta.get("contributing_record_assessments")
            if receipts is None:
                # Category modules may embed the generic owner's receipt.
                receipts = _safe_dict(evidence_meta.get("generic_evidence_metadata")).get("contributing_record_assessments")
            if isinstance(receipts, list):
                authority = evidence_meta.get("selected_nutrition_authority")
                selected_authority = (
                    authority in DRI_ESSENTIAL_NUTRIENTS
                    and evidence_meta.get("nutrition_authority_floor_applied") is True
                    and evidence_meta.get("primary_evidence_floor_decisive") is True
                    and evidence_meta.get("nutrition_authority_canonical") == authority
                )
                selected_authority = selected_authority or _current_omega_authority_receipt(
                    product, _safe_dict(dimensions.get("evidence")))
                if (not receipts and float(_safe_dict(dimensions.get("evidence")).get("score") or 0) > 0
                        and not selected_authority):
                    blockers.append("contributing_evidence_receipts_missing")
                for receipt in receipts:
                    if (receipt.get("status") != "applicable"
                            or receipt.get("scope_qualification_complete") is not True):
                        blockers.append("clinical_applicability_unreviewed:" + str(receipt.get("id") or "unknown"))
                    from clinical_applicability import assess_clinical_source_review
                    if not assess_clinical_source_review(receipt)["is_complete"]:
                        blockers.append("contributing_source_review_incomplete:" + str(receipt.get("id") or "unknown"))
            elif float(_safe_dict(dimensions.get("evidence")).get("score") or 0) > 0:
                blockers.append("contributing_evidence_receipts_missing")
    return {"is_complete": not blockers, "blockers": list(dict.fromkeys(blockers)),
            "unfinished_source_assessment": unfinished_source}


def _current_evidence_dimension_receipt(enriched: Mapping, module: str, evidence: Mapping) -> bool:
    """Validate only the retained dimension through its existing numerical owner.

    This does not assemble a product score or change any result. Calling the
    owner on an isolated source copy also checks its current winning dependency
    receipts, including source holds, scope and numerical caps, without copying
    those policies into publication. Native generic audit metadata cannot earn
    native credit.
    """
    from copy import deepcopy
    import json
    from scoring_input_contract import score_eligible_identity_view

    if module not in {"generic", "sports", "fiber_digestive", "omega", "b_complex", "multi_or_prenatal"}:
        return False
    # The public scorer enters through this same projection: identities kept
    # only for interactions must not become Evidence owners during validation.
    source = score_eligible_identity_view(deepcopy(dict(enriched)))
    if module in {"generic", "sports", "fiber_digestive"}:
        from scoring_v4.modules.generic_evidence import score_evidence
        current = score_evidence(source, apply_primary_floor=True, owner_scoped=True)
    elif module == "omega":
        from scoring_v4.modules.omega_evidence import score_evidence
        current = score_evidence(source)
        # This extension proves withheld native science only. Positive omega
        # authority already has its completed native release assessment.
        if current.get("score") != 0:
            return False
    elif module == "b_complex":
        from scoring_v4.modules.b_complex import _score_evidence
        current = _score_evidence(source)
    elif module == "multi_or_prenatal":
        from scoring_v4.modules.multi_prenatal_evidence import score_evidence
        current = score_evidence(source)
    else:
        return False
    # ModuleResult serializes these fields; phase is metadata, not a second
    # dimension field. JSON equality preserves bool/number distinctions.
    fields = ("score", "max", "components", "penalties", "metadata")
    return json.dumps({key: current.get(key) for key in fields}, sort_keys=True) == json.dumps(
        {key: evidence.get(key) for key in fields}, sort_keys=True)


def _retained_evidence_is_publishable(scored: Mapping, enriched: Mapping) -> bool:
    """Validate retained science against a current, lineage-verified source.

    Completion remains false. Only the missing Evidence review may remain open;
    this consumes the existing applicability and numerical-path receipts, never
    assembles a product score or grants an implicit clinical approval.
    """
    from scoring_v4.scored_artifact import unfinished_source_assessment
    from scoring_v4.gate_safety import safety_resolvers_failed
    from clinical_applicability import _number
    from clinical_evidence_schema import is_reference_only
    from scoring_v4.modules.generic_evidence import _clinical_source_id

    readiness = _safe_dict(scored.get("assessment_readiness"))
    release = _safe_dict(readiness.get("release_assessment"))
    module = _safe_dict(scored.get("_v4_module_breakdown"))
    evidence = _safe_dict(_safe_dict(module.get("dimensions")).get("evidence"))
    meta = _safe_dict(evidence.get("metadata"))
    safety = _safe_dict(scored.get("_v4_safety_gate"))
    allowed_blockers = {"evidence_assessment_incomplete", "probiotic_evidence_assessment_incomplete"}
    if module.get("module") == "omega":
        allowed_blockers.add("omega_evidence_assessment_incomplete")
    if module.get("module") == "probiotic":
        allowed_blockers |= {"probiotic_contributing_context_incomplete:" + str(row.get("context_id"))
                             for row in meta.get("contributing_native_contexts") or [] if isinstance(row, Mapping)}
    if (scored.get("quality_score_status") != "scored"
            or scored.get("quality_assessment_status") != "partial"
            or release.get("is_complete") is not False
            or not isinstance(release.get("blockers"), list) or not release["blockers"]
            or any(not isinstance(reason, str) for reason in release["blockers"])
            or set(release["blockers"]) - allowed_blockers
            or release.get("unfinished_source_assessment") is not None
            or readiness.get("enforcement_mode") != "enforced"
            or not has_canonical_enforced_dimensions(readiness.get("enforced_dimensions"))
            or readiness.get("is_live_ready") is not True
            or _number(scored.get("mapped_coverage")) != 1.0
            or _safe_dict(scored.get("strict_scoring_contract")).get("passed") is not True
            or safety.get("ingredient_assessment_complete") is not True
            or safety_resolvers_failed(safety.get("ingredient_assessment_errors"))
            or safety.get("short_circuits_scoring") is not False
            or safety.get("quarantine_required") is not False
            or _safe_dict(scored.get("_v4_completeness_gate")).get("is_live_eligible") is not True):
        return False
    if any(not _is_ready(str(_safe_dict(readiness.get(name)).get("readiness") or ""))
           or _safe_dict(readiness.get(name)).get("migration_inference") is True
           for name in ENFORCED_READINESS_DIMENSIONS):
        return False
    records = meta.get("contributing_record_assessments", [] if module.get("module") in {
        "multi_or_prenatal", "b_complex", "omega"} else None)
    if not isinstance(records, list) or any(not isinstance(row, Mapping) for row in records):
        return False
    fresh = evaluate_release_assessment(enriched, readiness, module,
        unfinished_source=unfinished_source_assessment(dict(enriched), dict(module)))
    if set(fresh["blockers"]) != set(release["blockers"]):
        return False
    pillar = _safe_dict(_safe_dict(scored.get("quality_pillars_v4")).get("evidence"))
    entries = _safe_dict(pillar.get("receipt")).get("entries")
    score, public = _number(evidence.get("score")), _number(pillar.get("score"))
    if (score is None or public is None or not isinstance(records, list)
            or not isinstance(entries, list)
            or any(not isinstance(row, Mapping) or _number(row.get("points")) is None for row in entries)
            or abs(sum(_number(row["points"]) for row in entries) - public) > .001
            or meta.get("evidence_result_state") != pillar.get("evidence_result_state")):
        return False
    from scoring_v4.quality_score import _normalized_receipt, _pillar_evidence
    from scoring_v4.quality_score_config import config
    cfg = config()
    weight = cfg["pillars"]["evidence"]["weight"]
    archetype = _safe_dict(pillar.get("components")).get("archetype")
    if _number(pillar.get("max")) != weight or not archetype:
        return False
    try:
        rebuilt = _pillar_evidence(dict(evidence), weight, archetype, cfg)
        if rebuilt["components"] != pillar.get("components") or rebuilt["score"] != public:
            return False
        replay = _normalized_receipt("evidence", dict(pillar), dict(evidence), weight,
            lambda dim: _pillar_evidence(dim, weight, archetype, cfg))
    except (RuntimeError, ValueError, TypeError, KeyError):
        return False
    if replay != pillar["receipt"]:
        return False
    current_receipt = _current_evidence_dimension_receipt(enriched, str(module.get("module") or ""), evidence)
    if module.get("module") != "probiotic":
        return current_receipt
    # Generic Evidence retains signed clinical exposure constraints. Native
    # probiotic record qualification deliberately uses its amount-free seam.
    matches, _ = resolved_clinical_matches(dict(enriched), owner_scoped=module.get("module") != "probiotic",
                                          assess_amount=module.get("module") != "probiotic")
    accepted = {_clinical_source_id(row): row for row in matches if not is_reference_only(row)}
    points = meta.get("ingredient_points", {} if module.get("module") in {"probiotic", "multi_or_prenatal"} else None)
    if not isinstance(points, Mapping) or any(_number(value) is None for value in points.values()):
        return False
    if score == public == 0:
        if meta.get("evidence_result_state") not in {
                "clinical_review_not_covered", "applicability_unestablished",
                "research_present_applicability_unestablished", "native_research_review_incomplete"}:
            return False
        components = evidence.get("components")
        if (records or any(_number(row["points"]) != 0 for row in entries)
                or any(_number(value) != 0 for value in points.values())
                or not isinstance(components, Mapping) or not components
                or any(_number(value) != 0 for value in components.values())):
            return False
        if module.get("module") == "probiotic":
            from studied_formulas import assess_probiotic_evidence, assess_studied_formula
            from scoring_v4.modules.probiotic_evidence import _eligible_native_contexts
            from clinical_applicability import qualifying_purpose_outcomes
            native = assess_probiotic_evidence(dict(enriched))
            if (meta.get("contributing_native_contexts") != []
                    or meta.get("evidence_assessment") != native
                    or assess_studied_formula(dict(enriched)).get("status") == "assessed_studied_formula"
                    or any(any(row.get("kind") == "patient_important" for row in qualifying_purpose_outcomes(context)[0])
                           for _, context in _eligible_native_contexts(native))):
                return False
            return not any(key.startswith(("STRAIN_", "FORMULA_")) for key in accepted)
        return module.get("module") in {"generic", "sports", "fiber_digestive"} and not accepted
    if module.get("module") == "probiotic":
        from studied_formulas import assess_probiotic_evidence
        from scoring_v4.modules import probiotic_evidence as native_owner
        from scoring_v4.modules.probiotic_evidence import _eligible_native_contexts, _qualifying_outcomes
        from clinical_evidence_schema import validate_frozen_context
        assessment = assess_probiotic_evidence(dict(enriched))
        formula = native_owner.assess_studied_formula_identity(dict(enriched))
        if formula.get("status") == "assessed_studied_formula":
            return False
        owned = [row for row in matches if (not native_owner._is_strain_match(row)
                 or native_owner.strain_assessments_for_match(row, assessment))
                 and native_owner._is_probiotic_owned_match(row, formula)]
        relevance = native_owner._claim_alignment(dict(enriched), {**assessment, "formula_assessment": formula})
        family = native_owner._strongest_single_family_certainty(probiotic_owned=owned, assessment=assessment,
            relevance=relevance, settings=native_owner._EM, formula=formula)
        consistency = native_owner._independent_consistency(assessment)
        components, expected_score, _ = native_owner._family_component_points(family, formula, relevance, consistency)
        if (family.get("source") != "native_context" or score != round(expected_score, 4)
                or evidence.get("components") != components):
            return False
        eligible = _eligible_native_contexts(assessment)
        current = {context["context_id"]: context for _, context in eligible}
        contexts = meta.get("contributing_native_contexts")
        if records or not isinstance(contexts, list) or not contexts:
            return False
        expected_ids = {family["context"]["context_id"]}
        if components["independent_replication_consistency"] > 0:
            selected = next(row for row in consistency["conditions"] if row["credit"] == consistency["credit"])
            expected_ids |= {context["context_id"] for _, context in eligible
                if context.get("condition") == selected["condition"]
                and (context.get("trial_family") or context.get("context_id")) in selected["families"]}
        if {row.get("context_id") for row in contexts if isinstance(row, Mapping)} != expected_ids:
            return False
        for context in contexts:
            if not isinstance(context, Mapping) or context != current.get(context.get("context_id")):
                return False
            errors = validate_frozen_context(context, require_complete_review=True)
            outcomes = _qualifying_outcomes(dict(context))
            if (set(errors) - {"outcomes.review_incomplete"} or not outcomes
                    or any(row.get("hierarchy") == "primary" and row.get("direction") == "unresolved"
                           for row in context.get("outcomes") or [])):
                return False
            if errors and not any(row.get("hierarchy") == "primary" and row.get("direction") == "positive"
                                  for row in outcomes):
                return False
            # This is a validation projection only. The source and receipt
            # retain every unresolved/uncredited outcome and remain partial.
            if validate_frozen_context({**context, "outcomes": outcomes}, require_complete_review=True):
                return False
        return True
    return False
