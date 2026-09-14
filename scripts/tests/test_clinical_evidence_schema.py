"""Regression tests for the frozen native clinical-evidence context contract."""

from __future__ import annotations

import copy
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from clinical_evidence_schema import (  # noqa: E402
    CONTEXT_SCHEMA_VERSION,
    validate_frozen_context,
)


def _context() -> dict:
    return {
        "context_schema_version": CONTEXT_SCHEMA_VERSION,
        "context_id": "ctx-1",
        "source_pmids": ["12345678"],
        "identity_scope": "exact_strain",
        "components": ["STRAIN_LGG"],
        "population": {"age_group": "adult", "description": "Adults"},
        "purpose": "treatment",
        "condition": "constipation",
        "evidence_role": "direct_rct",
        "component_registration_status": "fully_registered",
        "dose": {
            "basis": "discrete_daily_arms",
            "dose_basis": "per_strain_daily",
            "dose_status": "verified",
            "unit": "CFU",
            "values": [1e10],
            "dosage_forms": ["capsule"],
            "duration_days": 28,
            "duration_basis": "fixed_protocol",
            "co_therapies": [],
            "source_provenance": {
                "pmid": "12345678",
                "location": "full_text_methods",
            },
        },
        "outcomes": [
            {
                "name": "stool_frequency",
                "hierarchy": "primary",
                "kind": "patient_important",
                "direction": "positive",
                "outcome_role": "direct_between_group_effect",
            }
        ],
        "trial_family": "trial-1",
        "limitations": ["Synthetic test only"],
        "review_status": "source_verified_pending_clinical_review",
    }


def test_frozen_context_accepts_the_canonical_vocabularies() -> None:
    assert validate_frozen_context(_context(), known_component_ids={"STRAIN_LGG"}) == []


def test_verified_dose_requires_same_pmid_and_location() -> None:
    context = _context()
    context["dose"]["source_provenance"]["pmid"] = "99999999"
    errors = validate_frozen_context(context, known_component_ids={"STRAIN_LGG"})
    assert "dose.source_provenance.pmid_not_in_context" in errors


def test_tied_to_cotherapy_cannot_carry_a_fixed_duration() -> None:
    context = _context()
    context["dose"].update(
        duration_basis="tied_to_cotherapy",
        duration_days=14,
        co_therapies=["antibiotic therapy"],
    )
    errors = validate_frozen_context(context, known_component_ids={"STRAIN_LGG"})
    assert "dose.duration_days_must_be_null_for_tied_to_cotherapy" in errors


def test_duration_days_is_canonical_and_as_printed_is_only_a_preserved_alias() -> None:
    context = _context()
    context["dose"].update(
        duration_days=182,
        duration_as_printed={"value": 6, "unit": "months"},
    )
    assert validate_frozen_context(context, known_component_ids={"STRAIN_LGG"}) == []

    context["dose"].pop("duration_days")
    errors = validate_frozen_context(context, known_component_ids={"STRAIN_LGG"})
    assert "dose.fixed_protocol_duration_required" in errors


def test_recoverable_manual_is_not_a_second_dose_state() -> None:
    context = _context()
    context["dose"]["dose_status"] = "recoverable_manual"
    errors = validate_frozen_context(context, known_component_ids={"STRAIN_LGG"})
    assert "dose.dose_status_invalid" in errors


def test_network_ranking_cannot_be_a_positive_patient_effect() -> None:
    context = _context()
    context["evidence_role"] = "network_meta_analysis"
    context["scoring_eligible"] = False
    context["outcomes"] = [
        {
            "name": "ibs_severity_score_ranking",
            "hierarchy": "unresolved",
            "kind": "evidence_ranking",
            "direction": "unresolved",
            "outcome_role": "network_ranking",
        }
    ]
    assert validate_frozen_context(context, known_component_ids={"STRAIN_LGG"}) == []

    positive = copy.deepcopy(context)
    positive["outcomes"][0]["direction"] = "positive"
    errors = validate_frozen_context(positive, known_component_ids={"STRAIN_LGG"})
    assert "outcome.network_ranking_direction_must_be_unresolved" in errors


def test_scoring_eligible_is_a_boolean_when_present() -> None:
    context = _context()
    context["scoring_eligible"] = "false"
    errors = validate_frozen_context(context, known_component_ids={"STRAIN_LGG"})
    assert "context.scoring_eligible_invalid" in errors


def test_combination_per_strain_dose_requires_component_doses() -> None:
    context = _context()
    context.update(
        identity_scope="combination",
        components=["STRAIN_LGG", "STRAIN_LACTIS_BI07"],
        component_registration_status="fully_registered",
    )
    context["dose"].update(
        dose_basis="per_strain_daily",
        values=[],
        component_doses=[
            {"component": "STRAIN_LGG", "dose_cfu_per_day": 1e10},
            {"component": "STRAIN_LACTIS_BI07", "dose_cfu_per_day": 2.5e9},
        ],
    )
    assert validate_frozen_context(
        context,
        known_component_ids={"STRAIN_LGG", "STRAIN_LACTIS_BI07"},
    ) == []

    context["dose"].pop("component_doses")
    errors = validate_frozen_context(
        context,
        known_component_ids={"STRAIN_LGG", "STRAIN_LACTIS_BI07"},
    )
    assert "dose.component_doses_required_for_combination" in errors


def test_exact_strain_extraction_pending_can_leave_dose_values_empty() -> None:
    context = _context()
    context["dose"].update(
        dose_status="extraction_pending",
        values=[],
        source_provenance=None,
    )
    assert validate_frozen_context(context, known_component_ids={"STRAIN_LGG"}) == []


def test_exact_strain_source_not_reported_still_cannot_hide_an_empty_verified_dose() -> None:
    context = _context()
    context["dose"].update(dose_status="source_not_reported", values=[])
    errors = validate_frozen_context(context, known_component_ids={"STRAIN_LGG"})
    assert "dose.values_required_for_exact_strain" in errors


def test_unregistered_component_state_must_be_explicit() -> None:
    context = _context()
    context["components"] = ["STRAIN_LGG", "STRAIN_NOT_IN_REGISTRY"]
    context["component_registration_status"] = "fully_registered"
    errors = validate_frozen_context(context, known_component_ids={"STRAIN_LGG"})
    assert "components.unregistered_state_must_be_present" in errors


def test_malformed_identity_lists_fail_closed_with_codes_not_exceptions() -> None:
    for components in (None, 5, "STRAIN_LGG", [{"id": "STRAIN_LGG"}], []):
        context = _context()
        context["components"] = components
        assert "context.components_invalid" in validate_frozen_context(
            context, known_component_ids={"STRAIN_LGG"})
    context = _context()
    context["source_pmids"] = None
    assert "context.source_pmids_invalid" in validate_frozen_context(
        context, known_component_ids={"STRAIN_LGG"})


def test_dose_unit_must_match_its_measurement_type() -> None:
    for update in ({"unit": "spores"}, {"unit": "cfu"}, {"unit": None},
                   {"unit": "CFU", "measurement_type": "mass"}):
        context = _context()
        context["dose"].update(update)
        errors = validate_frozen_context(context, known_component_ids={"STRAIN_LGG"})
        assert "dose.unit_measurement_mismatch" in errors, update
    context = _context()
    context["dose"].update(unit="spores", measurement_type="spores")
    assert validate_frozen_context(context, known_component_ids={"STRAIN_LGG"}) == []


def test_nominal_assigned_arm_without_a_value_is_pending_not_reported() -> None:
    context = _context()
    context["dose"].update(dose_basis="nominal_assigned_arm", dose_status="source_not_reported",
                           values=[], source_provenance=None)
    errors = validate_frozen_context(context, known_component_ids={"STRAIN_LGG"})
    assert "dose.values_required_for_exact_strain" in errors
