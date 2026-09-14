"""Canonical schema vocabulary for native probiotic evidence contexts.

This module owns the structured vocabulary used by newly curated study
contexts.  Older contexts remain readable through the legacy ``dose.basis``
field; a context opts into the frozen contract with ``context_schema_version``.
The validator is deliberately side-effect free so a review packet or patch
checker can use it without changing the registry.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Set


CONTEXT_SCHEMA_VERSION = "1.1.0"

DOSE_STATUS = frozenset(
    {
        "verified",
        "source_not_reported",
        "extraction_pending",
        "conflicting_source_values",
        "combination_total_only",
    }
)

DOSE_BASIS = frozenset(
    {
        "per_strain_daily",
        "combination_total_daily",
        "nominal_assigned_arm",
        "measured_viability",
        "single_challenge",
        "not_applicable",
    }
)

DURATION_BASIS = frozenset(
    {
        "fixed_protocol",
        "tied_to_cotherapy",
        "participant_specific",
        "endpoint_followup_only",
        "not_recorded",
        "extraction_pending",
    }
)

EVIDENCE_ROLE = frozenset(
    {
        "direct_rct",
        "network_meta_analysis",
        "systematic_review",
        "meta_analysis",
        "guideline",
        "companion_analysis",
        "observational_study",
        "mechanistic_study",
    }
)

OUTCOME_ROLE = frozenset(
    {
        "direct_between_group_effect",
        "network_ranking",
        "within_group_change",
        "surrogate",
        "post_hoc_subgroup",
        "companion_reported_context",
    }
)

COMPONENT_REGISTRATION_STATUS = frozenset(
    {"fully_registered", "unregistered_components_present", "identity_uncertain"}
)
OUTCOME_KINDS = frozenset({"patient_important", "surrogate", "evidence_ranking"})


def _positive_number(value: object) -> bool:
    if isinstance(value, bool):
        return False
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return False
    return math.isfinite(number) and number > 0


def _nonempty_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _text_list(value: object, *, allow_empty: bool = False) -> bool:
    return (
        isinstance(value, list)
        and (allow_empty or bool(value))
        and all(_nonempty_text(item) for item in value)
    )


def _source_provenance_errors(context: Mapping, dose: Mapping) -> list[str]:
    status = dose.get("dose_status")
    provenance = dose.get("source_provenance")
    if status != "verified":
        return []
    if not isinstance(provenance, Mapping):
        return ["dose.source_provenance_required_for_verified"]
    pmid = provenance.get("pmid")
    if not _nonempty_text(pmid):
        return ["dose.source_provenance.pmid_required"]
    context_pmids = {str(value) for value in context.get("source_pmids", [])}
    errors = []
    if str(pmid) not in context_pmids:
        errors.append("dose.source_provenance.pmid_not_in_context")
    if not _nonempty_text(provenance.get("location")):
        errors.append("dose.source_provenance.location_required")
    if "source_url" in provenance and not _nonempty_text(provenance.get("source_url")):
        errors.append("dose.source_provenance.source_url_invalid")
    return errors


def _dose_errors(context: Mapping, known_component_ids: Set[str] | None) -> list[str]:
    dose = context.get("dose")
    if not isinstance(dose, Mapping):
        return ["dose.required"]

    errors: list[str] = []
    if dose.get("dose_status") not in DOSE_STATUS:
        errors.append("dose.dose_status_invalid")
    if dose.get("dose_basis") not in DOSE_BASIS:
        errors.append("dose.dose_basis_invalid")
    if dose.get("duration_basis") not in DURATION_BASIS:
        errors.append("dose.duration_basis_invalid")

    values = dose.get("values")
    if not isinstance(values, list) or any(not _positive_number(value) for value in values):
        errors.append("dose.values_invalid")

    component_doses = dose.get("component_doses")
    if component_doses is not None:
        if not isinstance(component_doses, list) or not component_doses:
            errors.append("dose.component_doses_invalid")
        else:
            seen: set[str] = set()
            for item in component_doses:
                if not isinstance(item, Mapping):
                    errors.append("dose.component_doses_item_invalid")
                    continue
                component = item.get("component")
                if not _nonempty_text(component) or component in seen:
                    errors.append("dose.component_doses_component_invalid")
                if _nonempty_text(component):
                    seen.add(str(component))
                if not _positive_number(item.get("dose_cfu_per_day")):
                    errors.append("dose.component_doses_value_invalid")
            if set(context.get("components", [])) != seen:
                errors.append("dose.component_doses_must_cover_components")

    if dose.get("dose_basis") == "per_strain_daily":
        if context.get("identity_scope") == "combination" and component_doses is None:
            errors.append("dose.component_doses_required_for_combination")
        # An exact-strain record can be structurally complete while its dose
        # still awaits extraction from the cited source.  Do not force a
        # number into ``values`` merely to satisfy the shape validator; the
        # explicit pending status is the contract's safe representation.
        if (context.get("identity_scope") != "combination"
                and not values
                and dose.get("dose_status") != "extraction_pending"):
            errors.append("dose.values_required_for_exact_strain")

    if dose.get("dose_status") == "combination_total_only":
        if context.get("identity_scope") != "combination" or not values:
            errors.append("dose.combination_total_only_requires_combination_values")

    if dose.get("duration_basis") == "tied_to_cotherapy":
        if dose.get("duration_days") is not None:
            errors.append("dose.duration_days_must_be_null_for_tied_to_cotherapy")
        if not _text_list(dose.get("co_therapies"), allow_empty=False):
            errors.append("dose.co_therapies_required_for_tied_to_cotherapy")

    if dose.get("duration_basis") == "fixed_protocol":
        has_days = _positive_number(dose.get("duration_days"))
        if not has_days:
            errors.append("dose.fixed_protocol_duration_required")
    as_printed = dose.get("duration_as_printed")
    if as_printed is not None:
        if not isinstance(as_printed, Mapping):
            errors.append("dose.duration_as_printed_invalid")
        elif (
            not _positive_number(as_printed.get("value"))
            or as_printed.get("unit") not in {"days", "weeks", "months"}
        ):
            errors.append("dose.duration_as_printed_invalid")

    errors.extend(_source_provenance_errors(context, dose))

    # Registry membership is checked by the caller because this module is also
    # used for synthetic review fixtures.  If an unknown component is present,
    # the state must say so explicitly rather than silently treating it as an
    # exact registered formula.
    if known_component_ids is not None:
        unknown = set(context.get("components", [])) - set(known_component_ids)
        if unknown and context.get("component_registration_status") != "unregistered_components_present":
            errors.append("components.unregistered_state_must_be_present")
        if not unknown and context.get("component_registration_status") == "unregistered_components_present":
            errors.append("components.unregistered_state_must_not_be_present")
    return errors


def _outcome_errors(context: Mapping) -> list[str]:
    outcomes = context.get("outcomes")
    if not isinstance(outcomes, list) or not outcomes:
        return ["outcomes.required"]
    errors: list[str] = []
    for index, outcome in enumerate(outcomes):
        prefix = f"outcome[{index}]"
        if not isinstance(outcome, Mapping):
            errors.append(f"{prefix}.invalid")
            continue
        if not _nonempty_text(outcome.get("name")):
            errors.append(f"{prefix}.name_required")
        if outcome.get("kind") not in OUTCOME_KINDS:
            errors.append(f"{prefix}.kind_invalid")
        if outcome.get("hierarchy") not in {
            "primary",
            "secondary",
            "post_hoc",
            "guideline",
            "unresolved",
        }:
            errors.append(f"{prefix}.hierarchy_invalid")
        if outcome.get("direction") not in {
            "positive",
            "mixed",
            "null",
            "negative",
            "unresolved",
        }:
            errors.append(f"{prefix}.direction_invalid")
        role = outcome.get("outcome_role")
        if role is not None and role not in OUTCOME_ROLE:
            errors.append(f"{prefix}.outcome_role_invalid")
        if role == "network_ranking":
            if outcome.get("kind") != "evidence_ranking":
                errors.append("outcome.network_ranking_kind_must_be_evidence_ranking")
            if outcome.get("direction") != "unresolved":
                errors.append("outcome.network_ranking_direction_must_be_unresolved")
            if context.get("evidence_role") != "network_meta_analysis":
                errors.append("outcome.network_ranking_requires_network_meta_analysis")
            if context.get("scoring_eligible") is not False:
                errors.append("outcome.network_ranking_must_not_be_scoring_eligible")
    return errors


def validate_frozen_context(
    context: Mapping,
    *,
    known_component_ids: Set[str] | None = None,
) -> list[str]:
    """Return stable error codes for a context using schema ``1.1.0``.

    This function never mutates its input.  It intentionally validates only the
    frozen contract; legacy contexts can continue through the existing legacy
    validator until they are migrated in an explicit batch.
    """

    if not isinstance(context, Mapping):
        return ["context.invalid"]
    errors: list[str] = []
    if context.get("context_schema_version") != CONTEXT_SCHEMA_VERSION:
        errors.append("context.schema_version_invalid")
    if context.get("evidence_role") not in EVIDENCE_ROLE:
        errors.append("context.evidence_role_invalid")
    if context.get("component_registration_status") not in COMPONENT_REGISTRATION_STATUS:
        errors.append("context.component_registration_status_invalid")
    if "scoring_eligible" in context and not isinstance(context.get("scoring_eligible"), bool):
        errors.append("context.scoring_eligible_invalid")
    errors.extend(_dose_errors(context, known_component_ids))
    errors.extend(_outcome_errors(context))
    return errors
