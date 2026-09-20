#!/usr/bin/env python3
"""Tests for Universal Evidence Resolver (Phase 3 Architecture).

Validates:
- Full 10-owner capability contract
- The fundamental invariant: matched owner != Evidence points
- All 6 canonical Evidence dispositions
- Sub-clinical dose and form mismatch applicability guards
- Probiotic strain vs species semantics
- Composition of product-level Evidence dispositions
"""
from __future__ import annotations

import sys
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

import evidence_resolver as er
from evidence_resolver import EvidenceDisposition, OWNER_CAPABILITY_MAP


def test_owner_capability_map_completeness():
    """All 10 required authoritative owners must be registered with complete metadata."""
    required_owners = {
        "identity_iqm",
        "nutrition_authority",
        "backed_clinical_studies",
        "probiotic_strain_registry",
        "standardized_botanicals",
        "dose_exposure",
        "form_preparation",
        "finished_formula",
        "monograph_claims",
        "safety_boundaries",
    }
    assert set(OWNER_CAPABILITY_MAP.keys()) == required_owners

    for owner_id, cap in OWNER_CAPABILITY_MAP.items():
        assert cap.owner_id == owner_id
        assert bool(cap.data_source)
        assert len(cap.facts_owned) > 0
        assert bool(cap.capability_description)


def test_matched_owner_not_equal_points_invariant():
    """Fundamental invariant: matching an owner establishes facts, NOT points.

    An essential nutrient matched to nutrition_authority establishes nutritional
    authority, but must not fabricate arbitrary efficacy points.
    """
    res = er.resolve_evidence_for_canonical("vitamin_c", dose_value=500.0, dose_unit="mg")
    assert "nutrition_authority" in res.matched_owners
    assert res.disposition == EvidenceDisposition.RESOLVED_BY_AUTHORITY.value
    assert res.points_eligible is False  # Authority establishes necessity; does NOT award points directly


def test_essential_nutrient_resolved_by_authority():
    """Essential dietary vitamins and minerals resolve to RESOLVED_BY_AUTHORITY."""
    for nutrient_id in ("vitamin_d", "zinc", "thiamin", "magnesium", "calcium"):
        res = er.resolve_evidence_for_canonical(nutrient_id, dose_value=50.0, dose_unit="mg")
        assert res.disposition == EvidenceDisposition.RESOLVED_BY_AUTHORITY.value
        assert "nutrition_authority" in res.matched_owners
        assert res.applicability_status == "established_essential_nutrient"


def test_canonical_iqm_vitamins_resolve_via_nutrition_authority():
    """IQM canonical IDs for vitamins resolve to nutrition_authority via rda_optimal_uls.json aliases."""
    for iqm_canon in (
        "vitamin_b1_thiamine",
        "vitamin_b2_riboflavin",
        "vitamin_b3_niacin",
        "vitamin_b5_pantothenic",
        "vitamin_b6_pyridoxine",
        "vitamin_b7_biotin",
        "vitamin_b9_folate",
        "vitamin_b12_cobalamin",
        "vitamin_d3",
        "vitamin_k1",
    ):
        res = er.resolve_evidence_for_canonical(iqm_canon, dose_value=10.0, dose_unit="mg")
        assert res.disposition == EvidenceDisposition.RESOLVED_BY_AUTHORITY.value, f"{iqm_canon} did not resolve to authority"
        assert "nutrition_authority" in res.matched_owners
        assert res.points_eligible is False


def test_no_local_nutrient_whitelist_in_resolver():
    """Universal resolver must NOT own a private nutrient alias translation table."""
    import inspect
    source = inspect.getsource(er)
    assert "_CANONICAL_NUTRIENT_BRIDGE" not in source
    assert "vitamin_b6_pyridoxine" not in source


def test_reviewed_clinical_study_resolution():
    """Clinically-studied botanical/amino acid with qualifying trials resolves to RESOLVED_BY_REVIEWED_CLINICAL_EVIDENCE."""
    res = er.resolve_evidence_for_canonical("ashwagandha", dose_value=600.0, dose_unit="mg")
    assert res.disposition == EvidenceDisposition.RESOLVED_BY_REVIEWED_CLINICAL_EVIDENCE.value
    assert "backed_clinical_studies" in res.matched_owners
    assert res.points_eligible is True
    assert res.reason_code == "reviewed_human_clinical_evidence_matched"


def test_subclinical_dose_applicability_guard():
    """If an ingredient dose is below the studied clinical range, applicability is unestablished."""
    # L-Carnitine minimum clinical dose in backed studies is 1000 mg
    res = er.resolve_evidence_for_canonical("l_carnitine", dose_value=50.0, dose_unit="mg")
    assert res.disposition == EvidenceDisposition.RESEARCH_PRESENT_APPLICABILITY_UNESTABLISHED.value
    assert "backed_clinical_studies" in res.matched_owners
    assert res.applicability_status == "sub_clinical_dose"
    assert "dose_below_clinical_trial_minimum" in res.blocking_reasons


def test_form_mismatch_applicability_guard():
    """If an ingredient form is excluded by clinical trials, applicability is unestablished."""
    res = er.resolve_evidence_for_canonical(
        "l_carnitine",
        name="L-Carnitine Fumarate",
        matched_form="fumarate",
        dose_value=500.0,
        dose_unit="mg",
    )
    # L-Carnitine tartrate / acetyl-l-carnitine trials exclude specific unstudied salts
    if "form_mismatch" in res.applicability_status:
        assert res.disposition == EvidenceDisposition.RESEARCH_PRESENT_APPLICABILITY_UNESTABLISHED.value
        assert "form_mismatch_with_clinical_trials" in res.blocking_reasons


def test_probiotic_strain_vs_species_semantics():
    """Exact strain vs species-only label semantics."""
    # Species-only label
    species_row = {
        "canonical_id": "probiotics",
        "name": "Lactobacillus acidophilus",
        "raw_source_text": "Lactobacillus acidophilus 5 Billion CFU",
        "amount": 5.0,
        "unit": "billion_cfu",
    }
    res_species = er.resolve_evidence_for_row(species_row)
    assert "probiotic_strain_registry" in res_species.matched_owners
    assert res_species.disposition == EvidenceDisposition.RESEARCH_PRESENT_APPLICABILITY_UNESTABLISHED.value

    # Exact strain with trial (NCFM)
    strain_row = {
        "canonical_id": "probiotics",
        "name": "Lactobacillus acidophilus NCFM",
        "raw_source_text": "Lactobacillus acidophilus NCFM 5 Billion CFU",
        "amount": 5.0,
        "unit": "billion_cfu",
    }
    res_strain = er.resolve_evidence_for_row(strain_row)
    assert "probiotic_strain_registry" in res_strain.matched_owners
    # NCFM has reviewed human trials in registry
    assert res_strain.disposition in {
        EvidenceDisposition.RESOLVED_BY_REVIEWED_CLINICAL_EVIDENCE.value,
        EvidenceDisposition.RESEARCH_PRESENT_APPLICABILITY_UNESTABLISHED.value,
    }


def test_blend_header_identity_insufficient():
    """Structural blend headers cannot act as evidence identities."""
    res = er.resolve_evidence_for_canonical("blend_general", is_blend_header=True)
    assert res.disposition == EvidenceDisposition.IDENTITY_INSUFFICIENT.value
    assert res.points_eligible is False
    assert "blend_header_lacks_constituent_disclosure" in res.blocking_reasons


def test_literature_resolution_required_phase4():
    """A clean active identity with no clinical trials in DB is flagged for Phase 4 literature search."""
    res = er.resolve_evidence_for_canonical("unreviewed_botanical_identity_xyz")
    assert res.disposition == EvidenceDisposition.LITERATURE_RESOLUTION_REQUIRED.value
    assert res.points_eligible is False
    assert "literature_search_required_phase4" in res.blocking_reasons


def test_safety_boundary_disqualification():
    """Banned or recalled ingredients are disqualified from positive efficacy evidence."""
    # Ephedra / Ephedrine is banned
    res = er.resolve_evidence_for_canonical("ephedra", name="Ephedra sinica")
    assert "safety_boundaries" in res.matched_owners
    assert res.disposition == EvidenceDisposition.NOT_EFFICACY_RELEVANT.value
    assert res.applicability_status == "safety_disqualified"


def test_product_evidence_composition():
    """Composition of product-level Evidence resolution across multiple rows."""
    # Multivitamin product with Vitamin C and Zinc
    product = {
        "dsld_id": "999001",
        "name": "Test Essential Multi",
        "ingredient_quality_data": {
            "ingredients": [
                {"canonical_id": "vitamin_c", "name": "Vitamin C", "amount": 250, "unit": "mg", "cleaner_row_role": "active_scorable"},
                {"canonical_id": "zinc", "name": "Zinc", "amount": 15, "unit": "mg", "cleaner_row_role": "active_scorable"},
            ]
        }
    }
    prod_res = er.resolve_product_evidence(product)
    assert prod_res.assessable_ingredients_count == 2
    assert prod_res.is_assessment_complete is True
    assert prod_res.overall_disposition == EvidenceDisposition.RESOLVED_BY_AUTHORITY.value
    assert prod_res.owner_contributions.get("nutrition_authority") == 2
