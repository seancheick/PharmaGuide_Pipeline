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
