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
        "uncontrolled_intervention",
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

# --- ingredient lane ---------------------------------------------------------
# The probiotic lane's identity scopes cannot describe a non-probiotic material,
# so the ingredient lane names its own. Everything else (dose, outcomes, review
# state, provenance) stays on the shared contract above.
INGREDIENT_IDENTITY_SCOPES = frozenset(
    {"exact_form", "ingredient_general", "branded_material", "botanical_preparation", "combination"}
)

# How the study delivered the exposure. A diet that replaces saturated fat with
# linoleic-acid-rich oil is not the exposure a 500 mg capsule delivers.
EXPOSURE_BASIS = frozenset(
    {"supplement_dose", "dietary_substitution", "food_matrix", "fortification", "infusion"}
)

ROUTES = frozenset({"oral", "sublingual", "iv", "im", "enteral_tube", "topical", "vaginal",
                    "intranasal", "inhaled", "other"})

# Human status is decided from several signals, because a very recent record is
# not yet MeSH-indexed. Ambiguous fails closed instead of counting as human.
HUMAN_STATUS = frozenset({"confirmed", "ambiguous", "nonhuman"})

# A retraction and a correction are not the same event.
SOURCE_INTEGRITY = frozenset({"none", "retracted", "expression_of_concern", "corrected", "erratum"})

REVIEW_ROLES = frozenset({"systematic_review", "meta_analysis", "network_meta_analysis"})

COMPONENT_REGISTRATION_STATUS = frozenset(
    {"fully_registered", "unregistered_components_present", "identity_uncertain"}
)
OUTCOME_KINDS = frozenset({"patient_important", "surrogate", "evidence_ranking"})
OUTCOME_HIERARCHIES = frozenset({"primary", "secondary", "post_hoc", "guideline", "not_reported", "unresolved"})
# One owner for what a study dose counts in: the runtime validator and the dose
# classifier import this mapping rather than keeping their own copy.
DOSE_MEASUREMENT_UNITS = {
    "viable_count": frozenset({"CFU"}),
    "mass": frozenset({"mg", "g"}),
    "afu": frozenset({"AFU"}),
    "spores": frozenset({"spores", "CFU"}),
}


REFERENCE_CLASSIFICATION_FIELDS = ("study_type", "evidence_level")


def is_reference_only(entry: Mapping) -> bool:
    """A reviewed reference record keeps research context but earns no credit.

    Both classification fields carry ``reference``; db_integrity_sanity_check
    fails a record where they disagree. Until fixed, either one fails closed.
    """
    return any(str(entry.get(key) or "").strip().lower() == "reference"
               for key in REFERENCE_CLASSIFICATION_FIELDS)


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

    measurement = dose.get("measurement_type") or "viable_count"
    if (measurement not in DOSE_MEASUREMENT_UNITS
            or dose.get("unit") not in DOSE_MEASUREMENT_UNITS[measurement]):
        errors.append("dose.unit_measurement_mismatch")

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
    if dose.get("dose_basis") in {"per_strain_daily", "nominal_assigned_arm"}:
        # An exact-strain record can be structurally complete while its dose
        # still awaits extraction from the cited source.  Do not force a
        # number into ``values`` merely to satisfy the shape validator; the
        # explicit pending status is the contract's safe representation. A
        # nominal assigned arm is still an arm: without a value it is pending.
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

    as_printed = dose.get("duration_as_printed")
    if dose.get("duration_basis") == "fixed_protocol":
        has_days = _positive_number(dose.get("duration_days"))
        # Preserve a held calendar-month regimen without inventing a fixed
        # number of days. Affirmative contexts still need numerical duration;
        # an omitted duration_days key is not an explicit unknown.
        held_calendar_duration = (
            context.get("scoring_eligible") is False
            and "duration_days" in dose
            and dose["duration_days"] is None
            and isinstance(as_printed, Mapping)
            and as_printed.get("unit") == "months"
            and _positive_number(as_printed.get("value"))
        )
        if not has_days and not held_calendar_duration:
            errors.append("dose.fixed_protocol_duration_required")
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
        if outcome.get("hierarchy") not in OUTCOME_HIERARCHIES:
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
        # A trial's primary outcome is not a subgroup finding or a result borrowed
        # from a companion report.
        if outcome.get("hierarchy") == "primary" and role in {"post_hoc_subgroup", "companion_reported_context"}:
            errors.append(f"{prefix}.primary_role_contradiction")
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
    require_complete_review: bool = False,
) -> list[str]:
    """Return stable error codes for a context using schema ``1.1.0``.

    This function never mutates its input.  It intentionally validates only the
    frozen contract; legacy contexts can continue through the existing legacy
    validator until they are migrated in an explicit batch.
    """

    if not isinstance(context, Mapping):
        return ["context.invalid"]
    errors: list[str] = []
    # Malformed identity lists fail closed with error codes; every later check
    # iterates them, so they must never reach the dose and outcome rules.
    if not _text_list(context.get("components")):
        errors.append("context.components_invalid")
    if not _text_list(context.get("source_pmids")):
        errors.append("context.source_pmids_invalid")
    if errors:
        return errors
    if context.get("context_schema_version") != CONTEXT_SCHEMA_VERSION:
        errors.append("context.schema_version_invalid")
    if context.get("evidence_role") not in EVIDENCE_ROLE:
        errors.append("context.evidence_role_invalid")
    if context.get("component_registration_status") not in COMPONENT_REGISTRATION_STATUS:
        errors.append("context.component_registration_status_invalid")
    if (context.get("evidence_role") == "uncontrolled_intervention"
            and context.get("scoring_eligible") is not False):
        errors.append("context.uncontrolled_intervention_must_not_be_scoring_eligible")
    if "scoring_eligible" in context and not isinstance(context.get("scoring_eligible"), bool):
        errors.append("context.scoring_eligible_invalid")
    if (context.get("review_status") == "clinician_approved"
            and not isinstance(context.get("scoring_eligible"), bool)):
        # An omitted flag is not a signed scoring decision (Sean, 2026-10-28).
        errors.append("review.approved_scoring_eligible_required")
    errors.extend(_dose_errors(context, known_component_ids))
    errors.extend(_outcome_errors(context))
    if require_complete_review:
        from probiotic_measurements import clinical_review_provenance_valid
        # A signed negative finding can be fully reviewed without being
        # eligible for points. Consumers still enforce scoring eligibility.
        if (context.get("review_status") != "clinician_approved"
                or not clinical_review_provenance_valid(context)):
            errors.append("review.approval_required")
        for field in ("context_id", "condition", "purpose", "trial_family", "study_design"):
            if not _nonempty_text(context.get(field)):
                errors.append(field + ".required_for_complete_review")
        population = context.get("population")
        if not isinstance(population, Mapping) or not _nonempty_text(population.get("description")):
            errors.append("population.required_for_complete_review")
        if not _text_list(context.get("limitations")):
            errors.append("limitations.required_for_complete_review")
        dose = context.get("dose")
        dose = dose if isinstance(dose, Mapping) else {}
        if dose.get("dose_status") in {"extraction_pending", "conflicting_source_values"}:
            errors.append("dose.source_review_incomplete")
        if dose.get("duration_basis") == "extraction_pending":
            errors.append("dose.duration_review_incomplete")
        # An approved aggregate may explicitly report no single assigned
        # regimen. Its empty delivery list is a reporting limitation, not a
        # missing trial extraction or permission to invent a dosage form.
        no_single_regimen = (
            context.get("evidence_role") in REVIEW_ROLES
            and dose.get("dose_status") == "source_not_reported"
            and dose.get("dose_basis") == "not_applicable"
            and dose.get("values") == []
            and dose.get("duration_basis") == "not_recorded"
            and dose.get("duration_days") is None
        )
        frequency = dose.get("administration_frequency")
        if ((not _nonempty_text(frequency) and not (no_single_regimen and frequency is None))
                or frequency in {"extraction_pending", "conflicting_source_values", "unresolved", "unknown"}):
            errors.append("dose.frequency_review_incomplete")
        if not _text_list(dose.get("co_therapies"), allow_empty=True):
            errors.append("dose.cotherapies_review_incomplete")
        if (not _text_list(dose.get("dosage_forms"))
                and not (no_single_regimen and dose.get("dosage_forms") == [])):
            errors.append("dose.delivery_required_for_complete_review")
        # A source that did not report a regimen is a reviewed limitation, not
        # an instruction to invent an amount. It still needs a source locator.
        provenance = dose.get("source_provenance")
        if (not isinstance(provenance, Mapping)
                or provenance.get("pmid") not in context.get("source_pmids", [])
                or not _nonempty_text(provenance.get("location"))):
            errors.append("dose.source_locator_required_for_complete_review")
        for outcome in context.get("outcomes") or []:
            if isinstance(outcome, Mapping) and (outcome.get("hierarchy") == "unresolved"
                                               or outcome.get("direction") == "unresolved"):
                errors.append("outcomes.review_incomplete")
        if context.get("included_study_pmids") == "extraction_pending":
            errors.append("included_studies.review_incomplete")
    return errors


def validate_ingredient_context(
    context: Mapping,
    *,
    known_component_ids: Set[str] | None = None,
    authoring: bool = False,
    require_complete_review: bool = False,
) -> list[str]:
    """Return stable error codes for an ingredient-lane study context.

    Runs the shared frozen contract first, then the rules a non-probiotic
    material needs: which identity the study actually used, how the exposure was
    delivered, its route, human status and source integrity. ``authoring=True``
    additionally refuses anything but a pending review status, so a curation run
    cannot mint its own approval.
    """

    if not isinstance(context, Mapping):
        return ["context.invalid"]
    if context.get("review_status") == "rejected_source":
        # A scoped source rejection does not assert a clinical trial regimen.
        # It needs its own traceable source and decision, never invented arms.
        from probiotic_measurements import clinical_review_provenance_valid
        errors = []
        sources = context.get("source_pmids")
        if not _text_list(context.get("components")):
            errors.append("context.components_invalid")
        elif known_component_ids is not None and set(context["components"]) - known_component_ids:
            errors.append("context.components_unknown")
        if not _text_list(sources) or any(
                not pmid.isascii() or not pmid.isdecimal() or pmid.startswith("0") for pmid in sources):
            errors.append("context.source_pmids_invalid")
        if not _nonempty_text(context.get("context_id")):
            errors.append("context_id.required_for_complete_review")
        if context.get("scoring_eligible") is not False:
            errors.append("review.rejected_source_must_not_be_scoring_eligible")
        if not clinical_review_provenance_valid(context):
            errors.append("review.approval_required")
        dose = context.get("dose")
        provenance = dose.get("source_provenance") if isinstance(dose, Mapping) else None
        if (not isinstance(provenance, Mapping)
                or str(provenance.get("pmid") or "") not in (sources or [])
                or not _nonempty_text(provenance.get("location"))
                or not _nonempty_text(provenance.get("source_url"))):
            errors.append("dose.source_provenance_required")
        if not _text_list(context.get("limitations")):
            errors.append("limitations.required_for_complete_review")
        if authoring:
            errors.append("review_status.pending_required_for_authoring")
        return errors
    errors = list(validate_frozen_context(context, known_component_ids=known_component_ids,
                                         require_complete_review=require_complete_review))

    scope = context.get("identity_scope")
    if scope not in INGREDIENT_IDENTITY_SCOPES:
        errors.append("identity.scope_invalid")
    identity = context.get("identity")
    identity = identity if isinstance(identity, Mapping) else {}
    if scope == "botanical_preparation":
        if not _nonempty_text(identity.get("botanical_species")):
            errors.append("identity.botanical_species_required")
        if not _nonempty_text(identity.get("plant_part")):
            errors.append("identity.plant_part_required")
    if scope == "branded_material":
        if not _nonempty_text(identity.get("branded_material")):
            errors.append("identity.branded_material_required")
        # A trademark alone does not establish material equivalence.
        if not any(_nonempty_text(identity.get(key))
                   for key in ("manufacturer", "standardization", "marker", "extract_ratio")):
            errors.append("identity.branded_material_source_required")
    if scope == "exact_form" and not _nonempty_text(identity.get("chemical_form")):
        errors.append("identity.chemical_form_required")

    exposure = context.get("exposure_basis")
    if exposure is None:
        errors.append("exposure.basis_required")
    elif exposure not in EXPOSURE_BASIS:
        errors.append("exposure.basis_invalid")

    route = context.get("route")
    if route is None:
        errors.append("route.required")
    elif route not in ROUTES:
        errors.append("route.invalid")

    human = context.get("human_status")
    if human not in HUMAN_STATUS:
        errors.append("human_status.invalid")
    elif human == "nonhuman":
        errors.append("human_status.nonhuman_not_eligible")
    elif human == "ambiguous" and context.get("scoring_eligible") is True:
        errors.append("human_status.ambiguous_cannot_be_scoring_eligible")

    integrity = context.get("source_integrity")
    if integrity not in SOURCE_INTEGRITY:
        errors.append("source_integrity.invalid")
    elif context.get("scoring_eligible") is True:
        if integrity == "retracted":
            errors.append("source_integrity.retracted_cannot_be_scoring_eligible")
        if integrity == "expression_of_concern":
            errors.append("source_integrity.expression_of_concern_must_be_held")

    if context.get("evidence_role") in REVIEW_ROLES:
        included = context.get("included_study_pmids")
        if included == "extraction_pending":
            pass
        elif not _text_list(included):
            errors.append("included_studies.required_for_review_roles")

    dose = context.get("dose")
    dose = dose if isinstance(dose, Mapping) else {}
    if _nonempty_text(dose.get("reported_regimen")) and dose.get("values"):
        normalization = dose.get("normalization")
        if not isinstance(normalization, Mapping) or not _nonempty_text(normalization.get("basis")):
            errors.append("dose.normalization_provenance_required")

    if require_complete_review:
        if human != "confirmed":
            errors.append("human_status.confirmed_required_for_complete_review")
        if integrity in {"retracted", "expression_of_concern"}:
            errors.append("source_integrity.complete_review_not_eligible")

    if authoring and context.get("review_status") != "source_verified_pending_clinical_review":
        errors.append("review_status.pending_required_for_authoring")

    return errors
