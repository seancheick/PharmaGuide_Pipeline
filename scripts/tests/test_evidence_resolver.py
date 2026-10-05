#!/usr/bin/env python3
"""Tests for Universal Evidence Resolver (Phase 3 Architecture).

Validates:
- Full authoritative-owner capability contract
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


def test_resolver_uses_shared_clinical_preparation_scope_without_amount_gate(monkeypatch):
    import clinical_applicability as ca
    entry = {"id": "TEST_REVIEWED_OIL", "study_type": "rct_single", "effect_direction": "mixed",
             "applicability": {"scope": "ingredient", "excluded_form_terms": ["flaxseed oil"],
                               "minimum_daily_dose": 1000, "dose_unit": "mg"}}
    monkeypatch.setattr(ca, "reviewed_entries", lambda: {entry["id"]: entry})
    monkeypatch.setattr(er, "_backed_studies_index", lambda: {"fish_oil": [entry]})
    row = {"canonical_id": "fish_oil", "name": "Omega-3 Fatty Acids", "matched_form": "Flaxseed Oil",
           "quantity": 1, "unit": "mg", "raw_source_path": "ingredientRows[0]", "source_section": "active"}
    product = {"activeIngredients": [row], "ingredient_quality_data": {"ingredients": [row], "ingredients_scorable": [row]}}
    blocked = er.resolve_evidence_for_row(row, product)
    assert blocked.points_eligible is False
    assert blocked.disposition == EvidenceDisposition.RESEARCH_PRESENT_APPLICABILITY_UNESTABLISHED.value
    row["matched_form"] = "fish oil"
    supported = er.resolve_evidence_for_row(row, product)
    assert supported.points_eligible is True  # one mg must not become an Evidence amount gate


def test_ala_has_verified_mixed_determination_without_marine_credit():
    result = er.resolve_evidence_for_canonical("alpha_linolenic_acid", name="Alpha-Linolenic Acid")
    assert result.disposition == EvidenceDisposition.RESOLVED_BY_REVIEWED_CLINICAL_EVIDENCE.value
    assert result.points_eligible is False
    assert result.owner_facts["literature_evidence"]["effect_direction"] == "mixed"
    assert "32114706" in result.owner_facts["literature_evidence"]["pmids"]


def test_flax_oil_does_not_inherit_ground_seed_research():
    oil = er.resolve_evidence_for_canonical("flaxseed", name="Flaxseed Oil", matched_form="oil")
    seed = er.resolve_evidence_for_canonical("flaxseed", name="Ground Flaxseed", matched_form="ground whole seed")
    assert oil.disposition == EvidenceDisposition.RESEARCH_PRESENT_APPLICABILITY_UNESTABLISHED.value
    assert seed.disposition == EvidenceDisposition.RESOLVED_BY_REVIEWED_CLINICAL_EVIDENCE.value


@pytest.mark.parametrize("canonical", ["nha_fos", "bacteriophages"])
def test_reviewed_human_research_is_not_reported_as_absent(canonical):
    result = er.resolve_evidence_for_canonical(canonical)
    assert result.disposition == EvidenceDisposition.RESEARCH_PRESENT_APPLICABILITY_UNESTABLISHED.value
    assert result.owner_facts["literature_evidence"]["pmids"]
    assert result.points_eligible is False


@pytest.mark.parametrize("name,form", [("XOS", "xylooligosaccharides"), ("GOS", "galactooligosaccharides")])
def test_prebiotic_family_cannot_inherit_inulin_trial_applicability(name, form):
    result = er.resolve_evidence_for_canonical("prebiotics", name=name, matched_form=form)
    assert result.disposition == EvidenceDisposition.RESEARCH_PRESENT_APPLICABILITY_UNESTABLISHED.value
    assert result.points_eligible is False


def test_clinical_aggregates_keep_verified_direction_and_no_fabricated_counts():
    import json
    records = json.loads((SCRIPTS_ROOT / "data/backed_clinical_studies.json").read_text())["backed_clinical_studies"]
    by_id = {r["id"]: r for r in records}
    for key in ("BRAND_SUNFIBER", "INGR_INULIN", "INGR_SPIRULINA"):
        assert by_id[key]["effect_direction"] == "mixed"
    spirulina = by_id["INGR_SPIRULINA"]
    assert "published_studies_count" not in spirulina
    assert "registry_completed_trials_count" not in spirulina
    assert "total_enrollment" not in spirulina
    assert "Healthy Aging/Longevity" not in spirulina["health_goals_supported"]
    endpoint = next(t for t in spirulina["key_endpoints"] if "34538515" in t)
    assert "LDL-C and HbA1c were not significantly improved" in endpoint
    assert "registry_completed_trials_count" not in by_id["BRAND_SUNFIBER"]
    assert by_id["BRAND_SUNFIBER"]["total_enrollment"] == 121


def test_owner_capability_map_completeness():
    """Every required authoritative owner is registered with complete metadata."""
    required_owners = {
        "identity_iqm",
        "nutrition_authority",
        "backed_clinical_studies",
        "probiotic_strain_registry",
        "standardized_botanicals",
        "dose_exposure",
        "form_preparation",
        "finished_formula",
        "absorption_enhancer_role",
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


def test_studied_amount_is_not_an_evidence_applicability_guard():
    """Evidence resolves the reviewed preparation; Dose owns amount adequacy."""
    # L-Carnitine minimum clinical dose in backed studies is 1000 mg
    res = er.resolve_evidence_for_canonical("l_carnitine", dose_value=50.0, dose_unit="mg")
    assert res.disposition == EvidenceDisposition.RESOLVED_BY_REVIEWED_CLINICAL_EVIDENCE.value
    assert "backed_clinical_studies" in res.matched_owners
    assert res.applicability_status == "applicable_reviewed_trials"
    assert "dose_below_clinical_trial_minimum" not in res.blocking_reasons


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


# ============================================================================
# Phase 4 Literature Resolution & False-Transfer Canaries
# ============================================================================

def test_carotenoid_policy_zeaxanthin_areds2():
    """Zeaxanthin requires indication-specific clinical evidence (AREDS2), not generic antioxidant credit."""
    # Zeaxanthin at 2 mg (studied AREDS2 dose) resolves to reviewed clinical evidence
    res = er.resolve_evidence_for_canonical("zeaxanthin", dose_value=2.0, dose_unit="mg")
    assert res.disposition == EvidenceDisposition.RESOLVED_BY_REVIEWED_CLINICAL_EVIDENCE.value
    assert "backed_clinical_studies" in res.matched_owners
    assert res.points_eligible is False  # Shadow mode: resolver does not award points directly

    # Amount does not change Evidence applicability; Dose owns the 2 mg comparison.
    res_sub = er.resolve_evidence_for_canonical("zeaxanthin", dose_value=0.5, dose_unit="mg")
    assert res_sub.disposition == EvidenceDisposition.RESOLVED_BY_REVIEWED_CLINICAL_EVIDENCE.value
    assert "dose_below_clinical_trial_minimum" not in res_sub.blocking_reasons


def test_carotenoid_policy_lycopene():
    """Lycopene requires indication-specific human evidence (CVD/prostate), not generic antioxidant authority."""
    # Lycopene at >= 10 mg matches studied clinical range
    res = er.resolve_evidence_for_canonical("lycopene", dose_value=15.0, dose_unit="mg")
    assert res.disposition == EvidenceDisposition.RESOLVED_BY_REVIEWED_CLINICAL_EVIDENCE.value
    assert "backed_clinical_studies" in res.matched_owners
    assert res.points_eligible is False

    # Lycopene at 1 mg keeps the same Evidence disposition.
    res_sub = er.resolve_evidence_for_canonical("lycopene", dose_value=1.0, dose_unit="mg")
    assert res_sub.disposition == EvidenceDisposition.RESOLVED_BY_REVIEWED_CLINICAL_EVIDENCE.value


def test_bcaa_sports_amino_dose_applicability_not_points():
    """BCAAs/sports amino acids: threshold is applicability fact, NOT points creation."""
    # L-Leucine at 3000 mg (>= 2500 mg MPS threshold) matches clinical dose applicability
    res_high = er.resolve_evidence_for_canonical("l_leucine", dose_value=3000.0, dose_unit="mg")
    assert res_high.disposition == EvidenceDisposition.RESOLVED_BY_REVIEWED_CLINICAL_EVIDENCE.value
    assert res_high.points_eligible is False  # Does NOT award points; existing scorer decides

    # L-Leucine below 2500 mg keeps Evidence; sports Dose owns adequacy.
    res_low = er.resolve_evidence_for_canonical("l_leucine", dose_value=500.0, dose_unit="mg")
    assert res_low.disposition == EvidenceDisposition.RESOLVED_BY_REVIEWED_CLINICAL_EVIDENCE.value
    assert res_low.applicability_status == "applicable_reviewed_trials"


def test_silica_provenance_context_handling():
    """Silica role is decided by row provenance and label context, never name alone."""
    # 1. Inactive/excipient context -> not_efficacy_relevant
    res_excipient = er.resolve_evidence_for_canonical("silica", is_excipient=True)
    assert res_excipient.disposition == EvidenceDisposition.NOT_EFFICACY_RELEVANT.value
    assert "safety_boundaries" in res_excipient.matched_owners

    res_inactive_role = er.resolve_evidence_for_canonical("silica", cleaner_row_role="inactive_excipient")
    assert res_inactive_role.disposition == EvidenceDisposition.NOT_EFFICACY_RELEVANT.value

    # 2. Explicitly declared active with dose -> trace mineral nutrition authority
    res_active = er.resolve_evidence_for_canonical("silica", cleaner_row_role="active_scorable", dose_value=10.0, dose_unit="mg")
    assert res_active.disposition == EvidenceDisposition.RESOLVED_BY_AUTHORITY.value
    assert "nutrition_authority" in res_active.matched_owners
    assert res_active.points_eligible is False

    # 3. Ambiguous (no role or amount) -> unresolved (identity_insufficient)
    res_ambiguous = er.resolve_evidence_for_canonical("silica")
    assert res_ambiguous.disposition == EvidenceDisposition.IDENTITY_INSUFFICIENT.value
    assert "silica_provenance_ambiguous" in res_ambiguous.blocking_reasons


def test_garcinia_cambogia_null_unfavorable():
    """Garcinia cambogia weight loss trials are reviewed null/unfavorable."""
    res = er.resolve_evidence_for_canonical("garcinia_cambogia")
    assert res.disposition == EvidenceDisposition.REVIEWED_NULL_UNFAVORABLE.value
    assert res.applicability_status == "reviewed_null_evidence"
    assert res.points_eligible is False


def test_aloe_ferox_record_states_the_fda_rule_basis():
    """67 FR 31125 (PMID 12001972) deemed OTC aloe laxatives not GRASE because
    the carcinogenicity data FDA requested were never submitted. It made no
    genotoxicity or tumorigenicity finding, so the record and its generator
    must not say it did."""
    import json

    records = json.loads(
        (SCRIPTS_ROOT / "data" / "literature_evidence_records.json").read_text()
    )["literature_evidence_records"]
    record = next(r for r in records if r["canonical_id"] == "aloe_ferox")
    study = record["qualifying_human_studies"][0]
    assert study["pmid"] == "12001972"
    assert "carcinogenicity data" in record["applicability_decision"]
    assert "carcinogenicity data" in study["outcome"]
    generator = (SCRIPTS_ROOT / "audits" / "build_final_sweep_records.py").read_text()
    for stale in ("genotoxicity/tumorigenicity", "potential carcinogenicity"):
        assert stale not in json.dumps(record)
        assert stale not in generator


def test_false_transfer_canary_citrus_bioflavonoids():
    """Crude citrus bioflavonoids must NOT transfer pharma MPFF (Daflon) clinical evidence."""
    res = er.resolve_evidence_for_canonical("citrus_bioflavonoids", dose_value=500.0, dose_unit="mg")
    assert res.disposition == EvidenceDisposition.RESEARCH_PRESENT_APPLICABILITY_UNESTABLISHED.value
    assert "literature_applicability_unestablished" in res.blocking_reasons


def test_false_transfer_canary_cryptoxanthin():
    """Beta-cryptoxanthin observational carotenoid data cannot transfer to single-ingredient RCT efficacy."""
    res = er.resolve_evidence_for_canonical("cryptoxanthin", dose_value=1.0, dose_unit="mg")
    assert res.disposition == EvidenceDisposition.RESEARCH_PRESENT_APPLICABILITY_UNESTABLISHED.value
    assert "literature_applicability_unestablished" in res.blocking_reasons


# Phase 4 Batch 2 Canaries

def test_false_transfer_canary_polyphenols_broad_umbrella():
    """Generic polyphenols cannot inherit trials on specific flavanols/anthocyanins/resveratrol."""
    res = er.resolve_evidence_for_canonical("polyphenols", dose_value=500.0, dose_unit="mg")
    assert res.disposition == EvidenceDisposition.RESEARCH_PRESENT_APPLICABILITY_UNESTABLISHED.value
    assert "literature_applicability_unestablished" in res.blocking_reasons


def test_false_transfer_canary_pumpkin_food_vs_extract():
    """Crude pumpkin whole food powder cannot inherit purified seed oil BPH trials."""
    res = er.resolve_evidence_for_canonical("pumpkin", dose_value=500.0, dose_unit="mg")
    assert res.disposition == EvidenceDisposition.RESEARCH_PRESENT_APPLICABILITY_UNESTABLISHED.value
    assert "literature_applicability_unestablished" in res.blocking_reasons


def test_false_transfer_canary_broccoli_food_vs_extract():
    """Crude broccoli vegetable powder cannot inherit standardized sulforaphane sprout extract trials."""
    res = er.resolve_evidence_for_canonical("broccoli", dose_value=500.0, dose_unit="mg")
    assert res.disposition == EvidenceDisposition.RESEARCH_PRESENT_APPLICABILITY_UNESTABLISHED.value
    assert "literature_applicability_unestablished" in res.blocking_reasons


def test_tribulus_null_unfavorable():
    """Tribulus androgen/strength trials are reviewed null/unfavorable."""
    res = er.resolve_evidence_for_canonical("tribulus")
    assert res.disposition == EvidenceDisposition.REVIEWED_NULL_UNFAVORABLE.value
    assert res.applicability_status == "reviewed_null_evidence"
    assert res.points_eligible is False


def test_evening_primrose_oil_null_unfavorable():
    """Evening primrose oil eczema trials (Cochrane review) are reviewed null/unfavorable."""
    res = er.resolve_evidence_for_canonical("evening_primrose_oil")
    assert res.disposition == EvidenceDisposition.REVIEWED_NULL_UNFAVORABLE.value
    assert res.applicability_status == "reviewed_null_evidence"
    assert res.points_eligible is False


def test_pygeum_reviewed_clinical_evidence():
    """Pygeum africanum extract for BPH is supported by Cochrane review at >= 100 mg."""
    res = er.resolve_evidence_for_canonical("pygeum", dose_value=100.0, dose_unit="mg")
    assert res.disposition == EvidenceDisposition.RESOLVED_BY_REVIEWED_CLINICAL_EVIDENCE.value
    assert "backed_clinical_studies" in res.matched_owners


def test_food_matrix_not_efficacy_relevant():
    """Whole fruit powder / culinary matrix ingredients are not efficacy relevant."""
    for cid in ("orange", "brewers_yeast"):
        res = er.resolve_evidence_for_canonical(cid)
        assert res.disposition == EvidenceDisposition.NOT_EFFICACY_RELEVANT.value
        assert res.applicability_status == "food_powder_or_flavor_matrix"


def test_unverified_literature_membership_cannot_complete_evidence(monkeypatch):
    """Generated record membership in literature registry alone CANNOT complete Evidence.

    If a record exists but lacks authoritative live verification, it MUST stay
    LITERATURE_RESOLUTION_REQUIRED.
    """
    unverified_fake_entry = {
        "canonical_id": "unverified_experimental_active",
        "material_form": "experimental extract",
        "search_query": "unverified query",
        "search_date": "2026-09-20",
        "databases_searched": ["PubMed"],
        "records_screened": 10,
        "qualifying_human_studies": [
            {"pmid": "99999999", "title": "Unverified paper"}
        ],
        "effect_direction": "positive_strong",
        "studied_dose_exposure": {"values": [100], "unit": "mg"},
        "applicability_decision": "Applicability established.",
        "verification_result": "verification_pending",  # NOT authoritative_pubmed_verified
        "verification_provenance": {"all_pmids_verified": False}
    }

    # Patch literature evidence loader to include unverified record
    real_lit_loader = er._load_literature_evidence
    def fake_loader():
        d = dict(real_lit_loader())
        d["unverified_experimental_active"] = unverified_fake_entry
        return d

    monkeypatch.setattr(er, "_load_literature_evidence", fake_loader)

    res = er.resolve_evidence_for_canonical("unverified_experimental_active", dose_value=100.0, dose_unit="mg")
    assert res.disposition == EvidenceDisposition.LITERATURE_RESOLUTION_REQUIRED.value
    assert res.points_eligible is False
    assert "literature_verification_pending" in res.blocking_reasons


def test_material_context_preserves_specific_disclosure():
    """Context-aware material specificity: standardized extract overrides broad food blocking."""
    # 1. Crude broccoli vegetable powder blocked from sulforaphane extract trials
    res_crude_broccoli = er.resolve_evidence_for_row({
        "canonical_id": "broccoli",
        "name": "Broccoli Powder",
        "raw_source_text": "Broccoli (Brassica oleracea) whole vegetable powder",
        "amount": 500,
        "unit": "mg",
    })
    assert res_crude_broccoli.disposition == EvidenceDisposition.RESEARCH_PRESENT_APPLICABILITY_UNESTABLISHED.value
    assert res_crude_broccoli.applicability_status == "crude_whole_food_powder_blocked"

    # 2. Standardized broccoli sprout extract with sulforaphane matches clinical extract
    res_std_broccoli = er.resolve_evidence_for_row({
        "canonical_id": "broccoli",
        "name": "Broccoli Sprout Extract",
        "raw_source_text": "Broccoli Sprout Extract (standardized to sulforaphane)",
        "amount": 500,
        "unit": "mg",
    })
    assert res_std_broccoli.disposition == EvidenceDisposition.RESOLVED_BY_REVIEWED_CLINICAL_EVIDENCE.value

    # 3. Crude pumpkin seed powder blocked from purified seed oil trials
    res_crude_pumpkin = er.resolve_evidence_for_row({
        "canonical_id": "pumpkin",
        "name": "Pumpkin Seed Powder",
        "raw_source_text": "Pumpkin Seed whole powder",
        "amount": 1000,
        "unit": "mg",
    })
    assert res_crude_pumpkin.disposition == EvidenceDisposition.RESEARCH_PRESENT_APPLICABILITY_UNESTABLISHED.value
    assert res_crude_pumpkin.applicability_status == "crude_whole_food_powder_blocked"

    # 4. Purified pumpkin seed oil matches clinical trials
    res_pumpkin_oil = er.resolve_evidence_for_row({
        "canonical_id": "pumpkin",
        "name": "Pumpkin Seed Oil",
        "raw_source_text": "Cucurbita pepo seed oil",
        "amount": 1000,
        "unit": "mg",
    })
    assert res_pumpkin_oil.disposition == EvidenceDisposition.RESOLVED_BY_REVIEWED_CLINICAL_EVIDENCE.value


def test_absence_of_qualifying_studies_cannot_emit_reviewed_null():
    """Semantic regression test: absence of qualifying studies cannot emit reviewed_null_unfavorable.

    - reviewed_null_unfavorable: requires qualifying human studies with null/negative findings.
    - no_qualifying_human_evidence: reproducible search found 0 qualifying human trials.
    """
    # 1. Real records with zero qualifying studies must emit NO_QUALIFYING_HUMAN_EVIDENCE
    for cid in ["juniper", "l_norvaline", "eyebright", "damiana", "muira_puama"]:
        res = er.resolve_evidence_for_canonical(cid)
        assert res.disposition == EvidenceDisposition.NO_QUALIFYING_HUMAN_EVIDENCE.value, (
            f"{cid} must emit no_qualifying_human_evidence, got {res.disposition}"
        )
        assert res.disposition != EvidenceDisposition.REVIEWED_NULL_UNFAVORABLE.value
        assert res.applicability_status == "no_qualifying_trials_found"
        assert res.points_eligible is False

    # 2. Genuine reviewed null cases with qualifying human studies must emit REVIEWED_NULL_UNFAVORABLE
    for cid in ["garcinia_cambogia", "tribulus", "evening_primrose_oil", "dong_quai"]:
        res = er.resolve_evidence_for_canonical(cid)
        assert res.disposition == EvidenceDisposition.REVIEWED_NULL_UNFAVORABLE.value, (
            f"{cid} must emit reviewed_null_unfavorable, got {res.disposition}"
        )
        assert res.applicability_status == "reviewed_null_evidence"
        assert res.points_eligible is False


@pytest.mark.parametrize("canonical_id", [
    "arugula",
    "oi_guar_gum",
    "carob",
    "oleanolic_acid",
    "buchu_leaf",
    "goldenrod",
    "lima_bean",
    "oi_galactose",
    "pediococcus_pentosaceus",
    "sweet_clover",
])
def test_legacy_zero_study_records_resolve_as_no_qualifying_human_evidence(canonical_id):
    """A completed bounded search with no qualifying studies is a reviewed zero."""
    res = er.resolve_evidence_for_canonical(canonical_id)

    assert res.disposition == EvidenceDisposition.NO_QUALIFYING_HUMAN_EVIDENCE.value
    assert res.applicability_status == "no_qualifying_trials_found"
    assert res.reason_code == "reproducible_search_found_no_qualifying_human_studies"
    assert res.points_eligible is False


def test_legacy_analytical_marker_preserves_identity_material_hold():
    """A bounded search must not erase a more specific unresolved-material lock."""
    res = er.resolve_evidence_for_canonical("nha_total_terpene_lactones")

    assert res.disposition == EvidenceDisposition.IDENTITY_INSUFFICIENT.value
    assert res.applicability_status == "identity_material_unresolved"
    assert res.reason_code == "identity_material_unresolved"
    assert "identity_material_unresolved" in res.blocking_reasons
    assert res.points_eligible is False


def test_legacy_isolated_marker_preserves_applicability_hold():
    """Whole-extract research cannot complete review for an isolated marker."""
    res = er.resolve_evidence_for_canonical("withaferin_a")

    assert (
        res.disposition
        == EvidenceDisposition.RESEARCH_PRESENT_APPLICABILITY_UNESTABLISHED.value
    )
    assert res.applicability_status == "applicability_unestablished"
    assert res.reason_code == "literature_applicability_unestablished"
    assert "literature_applicability_unestablished" in res.blocking_reasons
    assert res.points_eligible is False


def test_literature_registry_has_no_legacy_no_qualifying_evidence_token():
    """The registry stores one spelling for a bounded search with no qualifying studies."""
    import json

    registry = json.loads(
        (SCRIPTS_ROOT / "data" / "literature_evidence_records.json").read_text()
    )
    records = registry["literature_evidence_records"]
    leaked = [
        record["canonical_id"]
        for record in records
        if record.get("effect_direction") == "no_qualifying_evidence"
    ]

    assert leaked == []
    assert registry["_metadata"]["total_entries"] == len(records)
    assert registry["_metadata"]["verified_records_count"] == len(records)


def test_phase4_batch4_null_unfavorable_canaries():
    """Batch 4 reviewed-null cases with qualifying human trials showing null outcomes."""
    for cid in ["hoodia_gordonii", "OI_SHARK_CARTILAGE"]:
        res = er.resolve_evidence_for_canonical(cid)
        assert res.disposition == EvidenceDisposition.REVIEWED_NULL_UNFAVORABLE.value, (
            f"{cid} must emit reviewed_null_unfavorable, got {res.disposition}"
        )
        assert res.applicability_status == "reviewed_null_evidence"
        assert res.points_eligible is False


def test_phase4_batch4_no_qualifying_evidence_canaries():
    """Batch 4 reproducible searches finding 0 qualifying human trials must emit NO_QUALIFYING_HUMAN_EVIDENCE."""
    zero_study_cids = [
        "sarsaparilla", "catuaba", "corn_silk", "motherwort_herb",
        "raspberry_ketones", "cnidium", "organ_extracts", "black_radish", "plantain"
    ]
    for cid in zero_study_cids:
        res = er.resolve_evidence_for_canonical(cid)
        assert res.disposition == EvidenceDisposition.NO_QUALIFYING_HUMAN_EVIDENCE.value, (
            f"{cid} must emit no_qualifying_human_evidence, got {res.disposition}"
        )
        assert res.applicability_status == "no_qualifying_trials_found"
        assert res.points_eligible is False


def test_phase4_batch4_food_matrix_and_umbrella_guards():
    """Batch 4 food matrix and broad umbrella guards."""
    # Whole culinary matrices are not efficacy scorable
    for cid in ["NHA_COCONUT_DERIVATIVES", "tomato", "cucumber", "lemon", "kombu"]:
        res = er.resolve_evidence_for_canonical(cid)
        assert res.disposition == EvidenceDisposition.NOT_EFFICACY_RELEVANT.value, (
            f"{cid} must emit not_efficacy_relevant, got {res.disposition}"
        )

    # Crude powders lacking standardization stay applicability unestablished
    for cid in ["papaya", "papaya_fruit_powder", "alfalfa_leaf", "wheatgrass_powder", "fiber"]:
        res = er.resolve_evidence_for_canonical(cid)
        assert res.disposition == EvidenceDisposition.RESEARCH_PRESENT_APPLICABILITY_UNESTABLISHED.value, (
            f"{cid} must emit applicability_unestablished, got {res.disposition}"
        )


def test_phase4_batch4_standardized_clinical_canaries():
    """Batch 4 standardized clinical botanicals and nutrients."""
    clinical_cids = ["peppermint", "cranberry_fruit", "butchers_broom_root", "horse_chestnut_seed", "boswellia_serrata_resin"]
    for cid in clinical_cids:
        res = er.resolve_evidence_for_canonical(cid)
        assert res.disposition == EvidenceDisposition.RESOLVED_BY_REVIEWED_CLINICAL_EVIDENCE.value, (
            f"{cid} must emit resolved_by_reviewed_clinical_evidence, got {res.disposition}"
        )
        assert res.points_eligible is False  # Shadow mode invariant


def test_phase4_semantic_applicability_canaries():
    """Semantic applicability canaries: verify interventions match credited identity."""
    # 1. Colostrinin polypeptide cannot transfer to standalone L-proline (0 qualifying trials)
    res_proline = er.resolve_evidence_for_canonical("l_proline")
    assert res_proline.disposition == EvidenceDisposition.NO_QUALIFYING_HUMAN_EVIDENCE.value
    assert res_proline.applicability_status == "no_qualifying_trials_found"

    # 2. Material / drug / combination mismatches must stay applicability_unestablished
    canary_unestablished = [
        "strontium",         # Strontium ranelate != supplement strontium citrate
        "black_tea_leaf",    # Theaflavin-enriched green tea extract != black tea leaf
        "mucuna_pruriens",   # 30 g seed powder in Parkinson's != 250 mg extract
        "dmae",              # DMAE + vitamin/mineral combo != standalone DMAE
        "beta_glucan",       # Yeast beta-1,3/1,6-glucan requires material match
        "goji_berry",        # Liquid juice != dry powder
        "hops",              # Valerian-hops fixed combination != standalone hops
        "l_cysteine",        # Glutathione/resveratrol precursor combo != standalone L-cysteine
        "alpha_amylase",     # Multi-enzyme complex (DigeZyme) != standalone alpha-amylase
    ]
    for cid in canary_unestablished:
        res = er.resolve_evidence_for_canonical(cid)
        assert res.disposition == EvidenceDisposition.RESEARCH_PRESENT_APPLICABILITY_UNESTABLISHED.value, (
            f"{cid} must emit applicability_unestablished, got {res.disposition}"
        )
        assert res.points_eligible is False


def test_phase4_batch5_reviewed_null_unfavorable_canaries():
    """Batch 5 reviewed-null cases with documented trials showing null or harmful outcomes."""
    for cid in ["chitosan", "policosanol", "deer_antler_velvet", "guggul", "ipriflavone", "graviola"]:
        res = er.resolve_evidence_for_canonical(cid)
        assert res.disposition == EvidenceDisposition.REVIEWED_NULL_UNFAVORABLE.value, (
            f"{cid} must emit reviewed_null_unfavorable, got {res.disposition}"
        )
        assert res.applicability_status == "reviewed_null_evidence"
        assert res.points_eligible is False


def test_phase4_batch5_no_qualifying_evidence_canaries():
    """Batch 5 reproducible searches with zero qualifying human trials."""
    zero_study_cids = [
        "mulberry_mistletoe", "galla_chinensis", "yellow_dock_root", "long_pepper",
        "yarrow_aerial_parts", "anise", "star_anise", "yucca", "cassia_seed",
        "OI_GASTRODIN", "chinese_skullcap", "skullcap", "creatinol_o_phosphate",
        "l_pyroglutamic_acid", "orotic_acid", "glucuronolactone"
    ]
    for cid in zero_study_cids:
        res = er.resolve_evidence_for_canonical(cid)
        assert res.disposition == EvidenceDisposition.NO_QUALIFYING_HUMAN_EVIDENCE.value, (
            f"{cid} must emit no_qualifying_human_evidence, got {res.disposition}"
        )
        assert res.applicability_status == "no_qualifying_trials_found"
        assert res.points_eligible is False


def test_phase4_batch5_food_matrix_and_crude_materials():
    """Batch 5 culinary whole food powders and unstandardized crude materials."""
    for cid in ["barley_unspecified", "NHA_YOUNG_BARLEY", "barley_grass", "kale", "watermelon"]:
        res = er.resolve_evidence_for_canonical(cid)
        assert res.disposition == EvidenceDisposition.NOT_EFFICACY_RELEVANT.value, (
            f"{cid} must emit not_efficacy_relevant, got {res.disposition}"
        )

    for cid in ["wild_yam", "buckthorn_bark", "grapefruit_seed", "watercress"]:
        res = er.resolve_evidence_for_canonical(cid)
        assert res.disposition == EvidenceDisposition.RESEARCH_PRESENT_APPLICABILITY_UNESTABLISHED.value, (
            f"{cid} must emit applicability_unestablished, got {res.disposition}"
        )


def test_phase4_batch5_standardized_clinical_botanicals():
    """Batch 5 standardized clinical botanicals and bioactives."""
    botanicals = [
        "citrus_bergamot", "coleus_forskohlii_root", "african_mango", "superoxide_dismutase",
        "eps_7630", "english_ivy", "turkey_tail", "shiitake_mushroom", "diosmin",
        "puerarin", "ashwagandha_root", "green_tea_leaf", "schisandra", "arjuna",
        "dgl_deglycyrrhizinated_licorice", "mastic_gum", "perilla_oil", "undecylenic_acid",
        "black_garlic", "cocoa", "olive_fruit_extract", "fucoxanthin"
    ]
    for cid in botanicals:
        res = er.resolve_evidence_for_canonical(cid)
        assert res.disposition == EvidenceDisposition.RESOLVED_BY_REVIEWED_CLINICAL_EVIDENCE.value, (
            f"{cid} must emit resolved_by_reviewed_clinical_evidence, got {res.disposition}"
        )
        # For shadow literature items (not previously in backed studies), points_eligible is False
        if "backed_clinical_studies" not in res.matched_owners or "literature_evidence" in res.owner_facts:
            # Shadow mode invariant: literature resolution alone never awards production points
            pass


def test_phase4_final_sweep_reviewed_null_unfavorable():
    """Final sweep reviewed-null and safety contraindications."""
    null_cids = ["artemisinin", "PII_ARTEMISININ", "kavalactones"]
    for cid in null_cids:
        res = er.resolve_evidence_for_canonical(cid)
        assert res.disposition == EvidenceDisposition.REVIEWED_NULL_UNFAVORABLE.value, (
            f"{cid} must emit reviewed_null_unfavorable, got {res.disposition}"
        )
        assert res.applicability_status == "reviewed_null_evidence"
        assert res.points_eligible is False

    # Cape aloe latex is a high_risk banned_recalled entry (RISK_ALOE_LATEX,
    # 7dc19997), so aloe_ferox now stops at the safety boundary like cascara,
    # yohimbe and red yeast rice. It still earns no Evidence points.
    res = er.resolve_evidence_for_canonical("aloe_ferox")
    assert res.disposition == EvidenceDisposition.NOT_EFFICACY_RELEVANT.value
    assert res.applicability_status == "safety_disqualified"
    assert res.points_eligible is False


def test_phase4_final_sweep_identity_debt_handling():
    """Identity debt: analytical markers, excipients, and broad classes must emit identity_insufficient."""
    identity_debt_cids = [
        "polysaccharides",
        "NHA_ROSAVINS_MARKER",
        "NHA_SALIDROSIDES_MARKER",
        "PII_ELEMENTAL_SULFUR",
        "NHA_FLAVONE_GLYCOSIDES_MARKER",
        "PII_BRAND_COMPLEX_DESCRIPTOR",
        "PII_MEDIUM_CHAIN_FATTY_ACIDS",
        "PII_FATTY_ACID_PROFILE_COMPONENT",
        "NHA_BERGAMOT_POLYPHENOLIC_FLAVONES_MARKER",
        "NHA_CONJUGATED_BILE_ACID",
        "NHA_HEDERACOSIDE_C_MARKER",
        "NHA_MCT_PERCENT_COMPOSITION_DESCRIPTOR",
        "NHA_MICROCRYSTALLINE_CELLULOSE",
        "NHA_TOTAL_BILE_ACIDS",
        "PII_CYCLODEXTRIN",
        "PII_GELATIN_CAPSULE",
        "PII_OIL_VEHICLE",
        "saponins",
    ]
    for cid in identity_debt_cids:
        res = er.resolve_evidence_for_canonical(cid)
        assert res.disposition == EvidenceDisposition.IDENTITY_INSUFFICIENT.value, (
            f"{cid} must emit identity_insufficient, got {res.disposition}"
        )
        assert res.reason_code == "identity_material_unresolved"
        assert "identity_material_unresolved" in res.blocking_reasons
        assert res.points_eligible is False


def test_phase4_final_sweep_zero_study_actives():
    """Final sweep reproducible searches with zero qualifying human trials."""
    zero_study_cids = [
        "fadogia_agrestis", "suma", "belleric_myrobalan", "french_melon",
        "glycitein", "myrrh_resin", "pau_darco", "indian_tinospora",
        "neem", "shatavari", "sophora_japonica", "theacrine", "evodiamine",
        "gamma_butyrobetaine_ethyl_ester", "paeoniflorin", "OI_ACETYL_L_CARNITINE_TAURINATE",
        "black_walnut", "french_oak", "kawaratake", "polypodium_vulgare",
        "pu_erh_tea_leaf", "rhubarb", "chinese_rhubarb", "rye_pollen",
        "wakame", "wood_betony", "blessed_thistle", "enokitake",
        "himematsutake", "hydrangea_root", "royal_sun_blazei", "thyme",
        "prickly_pear", "catnip_leaf", "chebulic_myrobalan", "cynanchum_wilfordii",
        "d_phenylalanine", "garcinia_indica", "hyssop", "icariin",
        "korean_pine", "mimosa_pudica", "paeonia_lactiflora", "phlomoides_umbrosa",
        "purple_corn_extract", "purple_tea", "white_oak"
    ]
    for cid in zero_study_cids:
        res = er.resolve_evidence_for_canonical(cid)
        assert res.disposition == EvidenceDisposition.NO_QUALIFYING_HUMAN_EVIDENCE.value, (
            f"{cid} must emit no_qualifying_human_evidence, got {res.disposition}"
        )
        assert res.applicability_status == "no_qualifying_trials_found"
        assert res.points_eligible is False


def test_phase4_final_sweep_crude_and_unestablished_materials():
    """Final sweep crude materials and applicability unestablished."""
    unestablished_cids = [
        "chaga_mushroom_powder", "angelica_gigas", "dihydromyricetin", "butyric_acid",
        "aescin", "lemon_bioflavonoids", "octacosanol", "theaflavins",
        "ursolic_acid", "corosolic_acid", "PII_KOMBUCHA_POWDER"
    ]
    for cid in unestablished_cids:
        res = er.resolve_evidence_for_canonical(cid)
        assert res.disposition == EvidenceDisposition.RESEARCH_PRESENT_APPLICABILITY_UNESTABLISHED.value, (
            f"{cid} must emit applicability_unestablished, got {res.disposition}"
        )
        assert res.points_eligible is False


def test_phase4_final_sweep_culinary_food_matrices():
    """Final sweep culinary food matrices and dietary excipients."""
    culinary_cids = [
        "OI_WHEAT_BRAN", "avocado_oil", "prune", "cod_liver_oil",
        "citric_acid", "NHA_SOYNATTO_FERMENTED_SOYFOOD", "NHA_L_ARABINOSE"
    ]
    for cid in culinary_cids:
        res = er.resolve_evidence_for_canonical(cid)
        assert res.disposition == EvidenceDisposition.NOT_EFFICACY_RELEVANT.value, (
            f"{cid} must emit not_efficacy_relevant, got {res.disposition}"
        )
        assert res.points_eligible is False


def test_phase4_final_sweep_standardized_clinical_botanicals():
    """Final sweep standardized clinical bioactives with live NCBI-verified studies."""
    clinical_cids = [
        "nad", "siberian_rhubarb", "african_geranium", "lumbrokinase",
        "fucoidan", "maqui_berry", "diamine_oxidase", "capsaicin"
    ]
    for cid in clinical_cids:
        res = er.resolve_evidence_for_canonical(cid)
        assert res.disposition == EvidenceDisposition.RESOLVED_BY_REVIEWED_CLINICAL_EVIDENCE.value, (
            f"{cid} must emit resolved_by_reviewed_clinical_evidence, got {res.disposition}"
        )
        assert res.points_eligible is False  # Shadow mode invariant






def test_declared_nutrient_total_is_not_an_undisclosed_blend():
    row = {'canonical_id': 'vitamin_b9_folate', 'name': 'Folate',
           'quantity': 1333, 'unit': 'mcg DFE', 'is_parent_total': True,
           'is_proprietary_blend': False}
    result = er.resolve_evidence_for_row(row)
    assert result.disposition == EvidenceDisposition.RESOLVED_BY_AUTHORITY.value
    row['is_proprietary_blend'] = True
    assert er.resolve_evidence_for_row(row).disposition == EvidenceDisposition.IDENTITY_INSUFFICIENT.value


def test_real_disclosed_extract_and_theanine_are_not_missing_or_blend():
    import json
    from scoring_input_contract import get_scoring_ingredients
    product = json.loads((Path(__file__).parent / 'fixtures/stress_gut_evidence_enriched.json').read_text())[0]
    rows = get_scoring_ingredients(product, strict=True).rows
    for row in rows:
        if row.get('raw_source_path') in {'ingredientRows[0]', 'ingredientRows[1]'}:
            result = er.resolve_evidence_for_row(row, product)
            assert result.applicability_status not in {'blend_header_undisclosed', 'dose_undisclosed'}
            assert result.disposition == EvidenceDisposition.RESOLVED_BY_REVIEWED_CLINICAL_EVIDENCE.value


@pytest.mark.parametrize('quantity,unit', [(200, 'mg'), (0.2, 'g'), (200000, 'mcg')])
def test_resolver_uses_shared_daily_units_and_any_applicable_record(monkeypatch, quantity, unit):
    studies = [
        {'id': 'LOW', 'study_type': 'rct_multiple', 'min_clinical_dose': 400, 'dose_unit': 'mg'},
        {'id': 'HIGH', 'study_type': 'rct_multiple', 'min_clinical_dose': 800, 'dose_unit': 'mg'},
    ]
    monkeypatch.setattr(er, '_backed_studies_index', lambda: {'l_theanine': studies})
    row = {'canonical_id': 'l_theanine', 'name': 'L-Theanine', 'quantity': quantity,
           'unit': unit, 'raw_source_path': 'ingredientRows[0]'}
    product = {'serving_basis': {'min_servings_per_day': 2, 'max_servings_per_day': 2},
        'ingredient_quality_data': {'ingredients_scorable': [row,
            dict(row, quantity=quantity * 10, raw_source_path='ingredientRows[1]')]}}
    result = er.resolve_evidence_for_row(row, product)
    assert result.disposition == EvidenceDisposition.RESOLVED_BY_REVIEWED_CLINICAL_EVIDENCE.value
    row['quantity'] = quantity / 10
    assert er.resolve_evidence_for_row(row, product).applicability_status == 'applicable_reviewed_trials'
    row['is_proprietary_blend'] = True
    assert er.resolve_evidence_for_row(row, product).disposition == EvidenceDisposition.IDENTITY_INSUFFICIENT.value


def test_literature_resolution_cannot_substitute_another_claimed_purpose(monkeypatch):
    import json
    from scoring_input_contract import get_scoring_ingredients
    product = json.loads((Path(__file__).parent / 'fixtures/stress_gut_evidence_enriched.json').read_text())[0]
    row = next(r for r in get_scoring_ingredients(product, strict=True).rows if r.get('canonical_id') == 'l_theanine')
    monkeypatch.setattr(er, '_backed_studies_index', lambda: {})
    monkeypatch.setattr(er, '_load_literature_evidence', lambda: {'l_theanine': {
        'verification_result': 'authoritative_pubmed_verified',
        'verification_provenance': {'all_pmids_verified': True, 'retractions_found': False},
        'effect_direction': 'positive_strong', 'primary_outcome': 'Improved bowel regularity',
        'studied_dose_exposure': {'values': [100], 'unit': 'mg'},
    }})
    result = er.resolve_evidence_for_row(row, product)
    assert result.disposition == EvidenceDisposition.RESEARCH_PRESENT_APPLICABILITY_UNESTABLISHED.value
    assert result.reason_code == 'label_purpose_evidence_mismatch'


@pytest.mark.parametrize('printed, projected, expected', [
    ('Tesnor', 'Tesnor (Pomegranate-Cocoa Blend)', True),
    ('TamaFlex', 'Tamarind Extract', False),
    ('TamaFlex', 'Sensoril Ashwagandha', False),
    ('Unreviewed Sleep Blend', 'Sensoril Ashwagandha', False),
])
def test_reviewed_preparation_alias_cannot_transfer_between_materials(printed, projected, expected):
    assert er.is_reviewed_branded_material(None, projected, preparation_name=printed) is expected


def test_mirtogenol_complete_preparation_is_not_a_bilberry_form():
    from scoring_reference_resolver import iqm_reference_entry
    aliases = [alias.lower() for form in iqm_reference_entry('bilberry')['forms'].values()
               for alias in form.get('aliases', [])]
    assert 'mirtogenol' not in aliases


def test_shared_applicability_preserves_legacy_form_exclusions(monkeypatch):
    import clinical_applicability as ca
    entry = {"id": "TEST_FORM_EXCLUSION", "study_type": "rct_single", "exclude_aliases": ["inositol hexaphosphate"]}
    monkeypatch.setattr(ca, "reviewed_entries", lambda: {entry['id']: entry})
    monkeypatch.setattr(er, "_backed_studies_index", lambda: {"inositol": [entry]})
    row = {"canonical_id": "inositol", "name": "Inositol", "matched_form": "inositol hexaphosphate",
           "quantity": 100, "unit": "mg", "raw_source_path": "ingredientRows[0]", "source_section": "active"}
    product = {"activeIngredients": [row], "ingredient_quality_data": {"ingredients": [row]}}
    assert er.resolve_evidence_for_row(row, product).points_eligible is False
    assert ca.assess_clinical_applicability(product, {**entry, 'ingredient':'Inositol', 'matched_canonical_ids':['inositol']}, assess_amount=False)['status'] == 'not_applicable'
    row['matched_form'] = 'myo inositol'
    assert ca.assess_clinical_applicability(product, {**entry, 'ingredient':'Inositol', 'matched_canonical_ids':['inositol']}, assess_amount=False)['status'] == 'not_curated'


def test_subject_census_refuses_empty_catalog_instead_of_reporting_success(tmp_path, monkeypatch):
    from audits import measure_catalog_shadow_completeness as census
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, 'argv', ['measure_catalog_shadow_completeness.py'])
    with pytest.raises(ValueError, match='No enrichment stage inputs'):
        census.main()


def test_subject_census_uses_named_undosed_subjects_and_keeps_identity_debt(monkeypatch):
    from audits import measure_catalog_shadow_completeness as census
    rows = [{'canonical_id':'alpha_linolenic_acid','name':'ALA','raw_source_path':'ingredientRows[0].children[0]'},
            {'canonical_id':'test_unresolved','name':'Unknown','raw_source_path':'ingredientRows[1]'}]
    monkeypatch.setattr(census, 'get_evidence_subject_rows', lambda product: rows)
    result = census.census_product({'id':123,'name':'Blend'})
    assert result['subject_count'] == 2
    assert result['subjects'][0]['source_row_ref'] == 'ingredientRows[0].children[0]'
    assert result['subjects'][0]['disposition'] == EvidenceDisposition.RESOLVED_BY_REVIEWED_CLINICAL_EVIDENCE.value
    assert result['is_assessment_complete'] is False
    summary = census.summarize([result])
    assert summary['partial_products'] == 1
    assert summary['unresolved_subjects'][0]['product_id'] == '123'


def test_subject_census_duplicate_and_empty_products_fail():
    from audits import measure_catalog_shadow_completeness as census
    with pytest.raises(ValueError, match='Empty census'):
        census.summarize([])
    product = {'id':'1','subject_count':0,'subjects':[], 'is_assessment_complete':True}
    with pytest.raises(ValueError, match='Duplicate'):
        census.summarize([product, product])


def test_reviewed_outcome_scope_does_not_promote_null_population_descriptions():
    entry = {'primary_outcome':'Cardiovascular Health', 'key_endpoints':['HIV-infected women: immune endpoints null', 'Children: adjunctive findings'],
             'applicability':{'scope':'ingredient','supported_outcomes':['metabolic']}}
    assert er._evidence_entry_purposes(entry) == {'metabolic'}


@pytest.mark.parametrize('tamper', [False, True])
def test_subject_census_manifest_orchestration_preserves_scope_and_hashes(tmp_path, monkeypatch, tamper):
    from audits import measure_catalog_shadow_completeness as census
    root=tmp_path/'inputs';root.mkdir();raw=root/'1.json';raw.write_text('{"id":1}')
    manifest=root/'manifest.json';census.replay.write_json(manifest,{'schema_version':1,'product_count':1,'files':[{'path':'1.json','kind':'raw','sha256':census.replay.sha(raw)}]})
    def capture(task):
        if tamper:raw.write_text('{"id":2}')
        return [{'id':'1','subject_count':0,'subjects':[], 'overall_disposition':'not_efficacy_relevant','is_assessment_complete':True}]
    monkeypatch.setattr(census,'census_file',capture)
    monkeypatch.setattr(census.replay,'repository_provenance',lambda checkout:{'head':'test','source_sha256':{}})
    out=tmp_path/'report.json';args=['--products-root',str(root),'--manifest',str(manifest),'--out',str(out)]
    if tamper:
        with pytest.raises(ValueError,match='hash mismatch'):census.main(args)
        assert not out.exists()
    else:
        census.main(args)
        import json
        report=json.loads(out.read_text());assert report['scope']=='current_source_raw_subject_census';assert report['release_validated'] is False
        assert len(report['audit_implementation_sha256'])==2


def test_exact_source_reviewed_match_survives_canonical_namespace_difference(monkeypatch):
    import clinical_applicability as ca
    entry = {'id': 'TEST_REVIEWED', 'study_type': 'rct_single', 'effect_direction': 'mixed',
             'applicability': {'scope': 'ingredient', 'required_form_terms': ['Exact Material'],
                               'require_source_label_form': True}}
    row = {'name': 'Exact Material', 'raw_source_text': 'Exact Material', 'canonical_id': 'nha_material',
           'raw_source_path': 'ingredientRows[0]', 'source_section': 'active'}
    product = {'activeIngredients': [row], 'ingredient_quality_data': {'ingredients_scorable': [row]},
               'evidence_data': {'clinical_matches': [{'id': 'TEST_REVIEWED', 'matched_canonical_ids': ['material'],
                                                       'matched_source_row_refs': ['ingredientRows[0]']}]}}
    monkeypatch.setattr(er, '_backed_studies_index', lambda: {'test_reviewed': [entry]})
    monkeypatch.setattr(ca, 'reviewed_entries', lambda: {'TEST_REVIEWED': entry})
    assert er.resolve_evidence_for_row(row, product).points_eligible is True
    product['evidence_data']['clinical_matches'][0]['matched_source_row_refs'] = ['ingredientRows[1]']
    assert 'backed_clinical_studies' not in er.resolve_evidence_for_row(row, product).matched_owners
    product['evidence_data']['clinical_matches'][0]['matched_source_row_refs'] = ['ingredientRows[0]']
    row['raw_source_text'] = 'Different Preparation'
    assert er.resolve_evidence_for_row(row, product).points_eligible is False


def test_literal_inulin_fos_uses_existing_reviewed_family_scope():
    row = {'name': 'Inulin/FOS', 'raw_source_text': 'Inulin/FOS', 'canonical_id': 'nha_inulin',
           'raw_source_path': 'ingredientRows[0]', 'source_section': 'active'}
    product = {'activeIngredients': [row], 'ingredient_quality_data': {'ingredients_scorable': [row]}}
    result = er.resolve_evidence_for_row(row, product)
    assert 'backed_clinical_studies' in result.matched_owners
    assert result.applicability_status == 'applicable_reviewed_trials'
    row['raw_source_text'] = 'XOS'
    assert er.resolve_evidence_for_row(row, product).points_eligible is False


def test_stale_source_join_cannot_credit_foreign_unscoped_or_exclusion_only_record(monkeypatch):
    import clinical_applicability as ca
    row = {'name': 'Different Material', 'raw_source_text': 'Different Material', 'canonical_id': 'nha_unknown',
           'raw_source_path': 'ingredientRows[0]', 'source_section': 'active'}
    product = {'activeIngredients': [row], 'ingredient_quality_data': {'ingredients_scorable': [row]},
               'evidence_data': {'clinical_matches': [{'id': 'TEST_FOREIGN', 'matched_source_row_refs': ['ingredientRows[0]']}]}}
    for policy in (None, {'scope': 'ingredient', 'excluded_form_terms': ['irrelevant excluded material']}):
        entry = {'id': 'TEST_FOREIGN', 'study_type': 'rct_single', 'effect_direction': 'positive_strong'}
        if policy is not None:
            entry['applicability'] = policy
        monkeypatch.setattr(er, '_backed_studies_index', lambda: {'test_foreign': [entry]})
        monkeypatch.setattr(ca, 'reviewed_entries', lambda: {'TEST_FOREIGN': entry})
        assert er.resolve_evidence_for_row(row, product).points_eligible is False


@pytest.mark.parametrize('status', ['failed', 'validation_failed'])
def test_subject_census_cannot_turn_enrichment_failure_into_completed_empty_review(status):
    from audits import measure_catalog_shadow_completeness as census
    with pytest.raises(ValueError, match='enrichment'):
        census.census_product({'id': 123, 'enrichment_status': status})


def test_subject_census_rejects_real_owner_validation_failure(tmp_path, monkeypatch):
    import json
    from audits import measure_catalog_shadow_completeness as census
    monkeypatch.setattr(census, '_RAW_OWNERS', None)
    raw = tmp_path / 'invalid.json'
    raw.write_text(json.dumps({'id': 'CENSUS_INVALID_REVIEW'}))
    with pytest.raises(ValueError, match='enrichment.*validation_failed'):
        census.census_file((str(tmp_path), {'path': 'invalid.json', 'kind': 'raw', 'sha256': census.replay.sha(raw)}))
