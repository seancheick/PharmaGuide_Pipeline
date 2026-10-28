"""Ingredient-lane study contexts share ONE contract with the probiotic lane.

The frozen context schema owns dose, outcome, provenance and review vocabulary.
The ingredient lane adds only what a non-probiotic material genuinely needs and
the existing contract cannot express: which material identity the study used,
how the exposure was delivered, and its integrity/human status. Each rule below
comes from a real Wave 1 case, named in the test.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from clinical_evidence_schema import (  # noqa: E402
    CONTEXT_SCHEMA_VERSION,
    validate_frozen_context,
    validate_ingredient_context,
)


def _context(**overrides):
    """A minimal valid ingredient context: PMID 11106141, single 12 g oral Gotu Kola."""
    context = {
        "context_id": "gotu_kola_asr_11106141",
        "context_schema_version": CONTEXT_SCHEMA_VERSION,
        "source_pmids": ["11106141"],
        "components": ["gotu_kola"],
        "identity_scope": "botanical_preparation",
        "identity": {"botanical_species": "Centella asiatica", "plant_part": "unstated"},
        "exposure_basis": "supplement_dose",
        "route": "oral",
        "evidence_role": "direct_rct",
        "component_registration_status": "fully_registered",
        "condition": "acute_anxiety_response",
        "purpose": "physiology",
        "trial_family": "gotu_kola_asr_11106141",
        "population": {"age_group": "adult", "description": "healthy adults"},
        "dose": {"measurement_type": "mass", "unit": "mg", "values": [12000],
                 "dose_status": "verified", "dose_basis": "nominal_assigned_arm",
                 "duration_basis": "not_recorded", "dosage_forms": [], "co_therapies": [],
                 "source_provenance": {"pmid": "11106141", "location": "abstract",
                                       "quote": "a single 12-g orally administered dose of Gotu Kola"}},
        "outcomes": [{"name": "acoustic_startle_response", "hierarchy": "primary",
                      "kind": "patient_important", "direction": "positive"}],
        "limitations": ["Single acute dose in healthy adults; not chronic supplementation."],
        "review_status": "source_verified_pending_clinical_review",
        "human_status": "confirmed",
        "source_integrity": "none",
    }
    context.update(overrides)
    return context


def test_a_valid_ingredient_context_passes_both_the_shared_and_lane_rules():
    assert validate_frozen_context(_context(), known_component_ids={"gotu_kola"}) == []
    assert validate_ingredient_context(_context(), known_component_ids={"gotu_kola"}) == []


def test_probiotic_scopes_are_not_ingredient_scopes_and_vice_versa():
    assert "identity.scope_invalid" in validate_ingredient_context(_context(identity_scope="exact_strain"))
    assert "identity.scope_invalid" not in validate_ingredient_context(_context(identity_scope="exact_form"))


def test_botanical_preparation_must_name_the_species_and_plant_part():
    # A root-extract trial is not leaf evidence: the material has to be stated.
    missing_part = _context(identity={"botanical_species": "Centella asiatica"})
    missing_species = _context(identity={"plant_part": "leaf"})

    assert "identity.plant_part_required" in validate_ingredient_context(missing_part)
    assert "identity.botanical_species_required" in validate_ingredient_context(missing_species)


def test_branded_material_must_identify_the_material_not_just_the_ingredient():
    branded = _context(identity_scope="branded_material", identity={"branded_material": "KSM-66"})

    assert "identity.branded_material_source_required" in validate_ingredient_context(branded)
    assert validate_ingredient_context(_context(
        identity_scope="branded_material",
        identity={"branded_material": "KSM-66", "manufacturer": "Ixoreal Biomed"})) == []


def test_exact_form_must_name_the_form():
    # L-carnitine fumarate is not L-carnitine base.
    assert "identity.chemical_form_required" in validate_ingredient_context(
        _context(identity_scope="exact_form", identity={}))


def test_dietary_substitution_exposure_is_not_a_supplement_dose():
    # PMID 23386268 replaced saturated fat with linoleic-acid-rich safflower oil;
    # a 500 mg capsule is not that exposure, so the basis must be explicit.
    assert validate_ingredient_context(_context(exposure_basis="dietary_substitution",
                                                dose={**_context()["dose"], "dose_status": "source_not_reported",
                                                      "dose_basis": "not_applicable", "values": []})) == []
    assert "exposure.basis_invalid" in validate_ingredient_context(_context(exposure_basis="capsule"))
    assert "exposure.basis_required" in validate_ingredient_context(_context(exposure_basis=None))


def test_route_is_required_because_iv_evidence_is_not_oral_evidence():
    # Glutamine and the amino acids are studied heavily by IV and enteral tube.
    assert "route.required" in validate_ingredient_context(_context(route=None))
    assert "route.invalid" in validate_ingredient_context(_context(route="drip"))
    assert validate_ingredient_context(_context(route="iv")) == []


def test_ambiguous_human_status_cannot_be_scoring_eligible():
    ambiguous = _context(human_status="ambiguous", scoring_eligible=True)

    assert "human_status.ambiguous_cannot_be_scoring_eligible" in validate_ingredient_context(ambiguous)
    assert validate_ingredient_context(_context(human_status="ambiguous")) == []


def test_nonhuman_evidence_is_rejected_from_the_ingredient_efficacy_lane():
    assert "human_status.nonhuman_not_eligible" in validate_ingredient_context(_context(human_status="nonhuman"))


def test_retracted_sources_can_never_be_scoring_eligible_and_eoc_is_a_hold():
    assert "source_integrity.retracted_cannot_be_scoring_eligible" in validate_ingredient_context(
        _context(source_integrity="retracted", scoring_eligible=True))
    assert "source_integrity.expression_of_concern_must_be_held" in validate_ingredient_context(
        _context(source_integrity="expression_of_concern", scoring_eligible=True))
    assert validate_ingredient_context(_context(source_integrity="corrected")) == []


def test_claude_cannot_author_an_approved_context():
    assert "review_status.pending_required_for_authoring" in validate_ingredient_context(
        _context(review_status="clinician_approved"), authoring=True)
    assert "review_status.pending_required_for_authoring" not in validate_ingredient_context(
        _context(review_status="clinician_approved"))


def test_systematic_review_membership_is_recorded_or_explicitly_pending():
    review = _context(evidence_role="systematic_review")

    assert "included_studies.required_for_review_roles" in validate_ingredient_context(review)
    assert validate_ingredient_context(dict(review, included_study_pmids="extraction_pending")) == []
    assert validate_ingredient_context(dict(review, included_study_pmids=["12504167"])) == []


def test_reported_regimen_is_kept_beside_any_normalized_daily_value():
    # 10,000 IU/week must not be silently flattened to a daily number.
    context = _context(dose={**_context()["dose"], "values": [1429],
                             "reported_regimen": "10,000 IU once weekly"})

    assert "dose.normalization_provenance_required" in validate_ingredient_context(context)
    assert validate_ingredient_context(_context(dose={
        **_context()["dose"], "values": [1429], "reported_regimen": "10,000 IU once weekly",
        "normalization": {"basis": "weekly_to_daily", "note": "10000 IU / 7 days"}})) == []


def test_held_calendar_month_protocol_keeps_printed_duration_without_invented_days():
    from copy import deepcopy
    context = _context(scoring_eligible=False)
    context['dose'].update(duration_basis='fixed_protocol', duration_days=None,
                           duration_as_printed={'value': 18, 'unit': 'months'})
    before = deepcopy(context)
    assert validate_ingredient_context(context) == []
    assert context == before
    assert context['dose']['duration_days'] is None


def test_calendar_month_exception_does_not_supply_missing_duration_days_key():
    context = _context(scoring_eligible=False)
    context['dose'].update(duration_basis='fixed_protocol', duration_as_printed={'value': 18, 'unit': 'months'})
    context['dose'].pop('duration_days', None)
    assert 'dose.fixed_protocol_duration_required' in validate_ingredient_context(context)


def test_calendar_month_exception_rejects_invalid_printed_duration():
    for value in [None, 0, -1, True, 'unresolved']:
        context = _context(scoring_eligible=False)
        context['dose'].update(duration_basis='fixed_protocol', duration_days=None,
                               duration_as_printed={'value': value, 'unit': 'months'})
        assert 'dose.fixed_protocol_duration_required' in validate_ingredient_context(context)


def test_affirmative_context_cannot_use_unknown_days_for_fixed_protocol():
    for eligible in [True, None, 'false', 0]:
        context = _context(scoring_eligible=eligible)
        context['dose'].update(duration_basis='fixed_protocol', duration_days=None,
                               duration_as_printed={'value': 18, 'unit': 'months'})
        assert 'dose.fixed_protocol_duration_required' in validate_ingredient_context(context)


def test_reported_absence_of_outcome_hierarchy_is_a_completed_source_limitation():
    from copy import deepcopy
    from probiotic_measurements import derived_context_evidence

    context = _context(review_status='clinician_approved', scoring_eligible=True, study_design='rct',
                       clinical_review={'reviewer': 'Synthetic test reviewer',
                                        'reviewed_at': '2026-01-01',
                                        'scope': 'identity_dose_outcome_applicability'})
    context['dose'].update(administration_frequency='one single oral dose',
                           dosage_forms=['oral supplement'])
    context['outcomes'][0]['hierarchy'] = 'not_reported'
    context['limitations'].append('The inspected source does not report an outcome hierarchy; not a prespecified primary result.')
    assert validate_ingredient_context(context, require_complete_review=True) == []

    unfinished = deepcopy(context)
    unfinished['outcomes'][0]['hierarchy'] = 'unresolved'
    assert 'outcomes.review_incomplete' in validate_ingredient_context(unfinished, require_complete_review=True)
    pending = deepcopy(context)
    pending['review_status'] = 'source_verified_pending_clinical_review'
    assert 'review.approval_required' in validate_ingredient_context(pending, require_complete_review=True)

    # Completed reporting limitation does not invent a positive primary outcome.
    native = deepcopy(context)
    native['identity_scope'] = 'exact_strain'
    from studied_formulas import _clinical_strain_registry
    owner = next(iter(_clinical_strain_registry()))
    native['components'] = [owner]
    native['dose'].update(measurement_type='viable_count', unit='CFU', values=[1_000_000], dose_basis='per_strain_daily')
    evidence = derived_context_evidence({'id': owner, 'study_contexts': [native]})
    assert evidence['effect_direction'] == 'unresolved'
    assert evidence['evidence_strength'] == 'weak'


@pytest.mark.parametrize('source', ['²', '0', '-1', '123x', '', None, True])
def test_rejected_source_invalid_pmid_fails_closed_without_crashing(source):
    context = {
        'context_id': 'source_rejection', 'components': ['ingredient'],
        'source_pmids': [source], 'review_status': 'rejected_source',
        'scoring_eligible': False, 'limitations': ['No applicable causal benefit.'],
        'clinical_review': {'reviewer': 'Dr Pham', 'reviewed_at': '2026-10-26',
                            'scope': 'identity_dose_outcome_applicability'},
        'dose': {'source_provenance': {'pmid': source, 'location': 'Abstract',
                                      'source_url': 'https://pubmed.ncbi.nlm.nih.gov/'}},
    }
    assert 'context.source_pmids_invalid' in validate_ingredient_context(context)


@pytest.mark.parametrize('eligible', [False, True, None])
def test_uncontrolled_intervention_is_described_without_authorizing_credit(eligible):
    from probiotic_measurements import context_accepted_for_scoring
    row = _context(evidence_role='uncontrolled_intervention', scoring_eligible=eligible)
    row.update(review_status='clinician_approved', clinical_review={
        'reviewer': 'Synthetic test reviewer', 'reviewed_at': '2020-01-01',
        'scope': 'identity_dose_outcome_applicability'})
    errors = validate_ingredient_context(row)
    assert ('context.evidence_role_invalid' not in errors)
    assert ('context.uncontrolled_intervention_must_not_be_scoring_eligible' in errors) is (eligible is not False)
    assert not context_accepted_for_scoring(row)
    row.pop('context_schema_version', None)
    assert not context_accepted_for_scoring(row)


def test_an_approved_context_must_state_its_scoring_eligibility():
    """Sean, 2026-10-28: a missing scoring_eligible is not a signed scoring decision.
    context_accepted_for_scoring still reads None as eligible (legacy allowance), so
    the validator requires the flag on every clinician-approved context."""
    approved = _context(review_status="clinician_approved")
    approved.pop("scoring_eligible", None)
    assert "review.approved_scoring_eligible_required" in validate_frozen_context(approved)
    for flag in (True, False):
        assert "review.approved_scoring_eligible_required" not in validate_frozen_context(
            _context(review_status="clinician_approved", scoring_eligible=flag))
    assert "review.approved_scoring_eligible_required" not in validate_frozen_context(_context())


def test_every_curated_approved_context_states_its_scoring_eligibility():
    import json
    from pathlib import Path
    data = Path(__file__).resolve().parents[1] / "data"
    missing = []
    for name, key in (("backed_clinical_studies.json", "backed_clinical_studies"),
                      ("clinically_relevant_strains.json", "clinically_relevant_strains")):
        for record in json.loads((data / name).read_text())[key]:
            for context in record.get("study_contexts") or []:
                if (context.get("review_status") == "clinician_approved"
                        and not isinstance(context.get("scoring_eligible"), bool)):
                    missing.append((record["id"], context.get("context_id")))
    assert missing == []
