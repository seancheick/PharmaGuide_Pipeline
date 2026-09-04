"""Structured strain identities stay attached to their own label row and dose."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from assessment_readiness import _probiotic_native_evidence_state
from build_final_db import build_detail_blob
from studied_formulas import independent_clinical_strains


@pytest.fixture(scope="module")
def enricher():
    from enrich_supplements_v3 import SupplementEnricherV3

    return SupplementEnricherV3()


def _row(name, form=None, *, index=0, cfu=10_000_000_000):
    return {
        "name": name, "raw_source_text": name,
        "raw_source_path": f"ingredientRows[{index}]",
        "category": "probiotic", "quantity": cfu, "unit": "CFU",
        "cleaner_row_role": "active_scorable", "score_eligible_by_cleaner": True,
        "forms": [{"name": form}] if form else [],
    }


def _collect(enricher, rows):
    product = {
        "id": "structured-strain-contract", "product_name": "Probiotic capsule",
        "activeIngredients": rows, "inactiveIngredients": [],
    }
    product["probiotic_data"] = enricher._collect_probiotic_data(product)
    return product


@pytest.mark.parametrize("mixed", [False, True])
@pytest.mark.parametrize("flattened", [False, True])
def test_allocation_scope_is_emitted_from_actual_blend_members(enricher, mixed, flattened):
    owner = _row("Probiotic Blend")
    owner["cleaner_row_role"] = "blend_header_total"
    owner["nestedIngredients"] = [_row("Lactobacillus rhamnosus GG")]
    if mixed:
        owner["nestedIngredients"].append({"name": "Inulin", "category": "prebiotic"})
    for index, child in enumerate(owner["nestedIngredients"]):
        child["raw_source_path"] = f"ingredientRows[0].nestedRows[{index}]"
    rows = [owner]
    if flattened:
        rows.extend(owner.pop("nestedIngredients"))
    product = _collect(enricher, rows)
    assert (owner["raw_source_path"] in product["probiotic_data"]["strain_allocation_owner_refs"]) is not mixed


def test_flattened_nested_blends_use_leaf_owners_without_swallowing_prebiotic(enricher):
    rows = [
        {"name": "Probiotic Blend", "raw_source_path": "ingredientRows[0]", "cleaner_row_role": "blend_header_total"},
        {"name": "Lactobacilli Blend", "raw_source_path": "ingredientRows[0].nestedRows[0]", "cleaner_row_role": "blend_header_total"},
        {"name": "Lactobacillus rhamnosus GG", "raw_source_path": "ingredientRows[0].nestedRows[0].nestedRows[0]"},
        {"name": "Prebiotic Blend", "raw_source_path": "ingredientRows[1]", "cleaner_row_role": "blend_header_total"},
        {"name": "Inulin", "raw_source_path": "ingredientRows[1].nestedRows[0]"},
    ]
    product = _collect(enricher, rows)
    assert set(product["probiotic_data"]["strain_allocation_owner_refs"]) == {
        "ingredientRows[0]", "ingredientRows[0].nestedRows[0]"}

    rows.insert(3, {"name": "Unresolved Blend", "raw_source_path": "ingredientRows[0].nestedRows[1]",
                    "cleaner_row_role": "blend_header_total"})
    assert "ingredientRows[0]" not in _collect(enricher, rows)["probiotic_data"]["strain_allocation_owner_refs"]


def test_real_fortify_subblend_opacity_uses_source_owner_not_first_child_index(enricher):
    from scoring_v4.modules.probiotic_transparency import score_transparency

    path = SCRIPTS_ROOT / "products/output_Natures_Way/cleaned/cleaned_batch_2.json"
    if not path.exists():
        pytest.skip("Local Fortify source unavailable; synthetic ownership cases remain unconditional")
    product = next(p for p in json.loads(path.read_text()) if str(p.get("id")) == "327965")
    product["probiotic_data"] = enricher._collect_probiotic_data(product)
    product["proprietary_data"] = enricher._collect_proprietary_data(product)
    rows = score_transparency(product)["metadata"]["B5_blend_evidence"]
    for row in rows:
        if row["blend_name"] in {"Lactobacilli Blend", "Bifidobacteria Blend"}:
            assert row["source_row_ref"] in product["probiotic_data"]["strain_allocation_owner_refs"]
            assert row["computed_blend_penalty_magnitude"] == 0
    assert any(r["blend_name"] == "Proprietary Plant-Based Prebiotic Blend"
               and r["computed_blend_penalty_magnitude"] > 0 for r in rows)


def test_real_327965_retains_three_distinct_howaru_source_owners(enricher):
    path = SCRIPTS_ROOT / "products/output_Natures_Way/cleaned/cleaned_batch_2.json"
    if not path.exists():
        pytest.skip("Local Nature's Way cleaned corpus is absent; synthetic ownership cases are unconditional")
    product = next(p for p in json.loads(path.read_text()) if str(p.get("id")) == "327965")
    owners = [r for r in product["activeIngredients"] if r["name"].lower() == "howaru"]
    assert len(owners) == 3
    product["probiotic_data"] = enricher._collect_probiotic_data(product)
    expected = {"STRAIN_ACIDOPHILUS_NCFM", "STRAIN_RHAMNOSUS_HN001", "STRAIN_LACTIS_HN019"}
    clinical = [r for r in independent_clinical_strains(product) if r["clinical_id"] in expected]
    assert {r["clinical_id"] for r in clinical} == expected
    assert {r["source_row_ref"] for r in clinical} == {r["raw_source_path"] for r in owners}
    assert all(r["label_name"].lower() == "howaru" and r["cfu_per_day"] is None for r in clinical)
    assert product["probiotic_data"]["total_cfu"] == 100_000_000_000
    assert product["probiotic_data"]["total_strain_count"] == 13  # unchanged label-count policy
    blob = build_detail_blob(product, {})
    exported = {r["raw_source_path"]: r for r in blob["ingredients"]}
    for owner in owners:
        assert _probiotic_native_evidence_state(product, owner) is not None
        assert exported[owner["raw_source_path"]]["clinical_support_level"] is not None
        assert exported[owner["raw_source_path"]]["adequacy_tier"] is None


@pytest.mark.parametrize("name,form", [
    ("Bifidobacterium longum", "BB536"),
    ("B. longum", "Bifidobacterium longum BB536"),
    ("HOWARU", "Lactobacillus acidophilus NCFM"),
])
def test_owner_form_proof_reaches_readiness_and_export(enricher, name, form):
    owner = _row(name, form)
    sibling = _row(name, index=1, cfu=0)
    product = _collect(enricher, [owner, sibling])
    clinical = independent_clinical_strains(product)
    assert len(clinical) == 1
    assert clinical[0]["source_row_ref"] == owner["raw_source_path"]
    assert clinical[0]["label_name"] == name
    assert clinical[0]["strain"] != name
    assert clinical[0]["cfu_per_day"] == 10_000_000_000
    assert _probiotic_native_evidence_state(product, owner) is not None
    assert _probiotic_native_evidence_state(product, sibling) is None
    exported = build_detail_blob(product, {})["ingredients"]
    assert exported[0]["clinical_support_level"] is not None
    assert exported[0]["adequacy_tier"] is not None
    assert exported[1]["clinical_support_level"] is None
    assert exported[1]["adequacy_tier"] is None


@pytest.mark.parametrize("name,form", [
    ("Lactobacillus longum", "BB536"),
    ("Lactobacillus longum", "Bifidobacterium longum BB536"),
    ("Bifidobacterium breve", "Bifidobacterium longum BB536"),
    ("Bifidobacterium longum BB-12", "BB536"),
    ("Lactobacillus acidophilus CUL60", "Lactobacillus acidophilus NCFM"),
])
def test_conflicting_parent_identity_cannot_borrow_its_form(enricher, name, form):
    product = _collect(enricher, [_row(name, form)])
    assert product["probiotic_data"]["clinical_strains"] == []


def test_notes_and_sibling_forms_are_not_owner_identity(enricher):
    owner = _row("Bifidobacterium longum")
    owner["notes"] = "Contains Bifidobacterium longum BB536"
    sibling = _row("Bifidobacterium longum", "BB536", index=1, cfu=0)
    product = _collect(enricher, [owner, sibling])
    clinical = independent_clinical_strains(product)
    assert len(clinical) == 1
    assert clinical[0]["source_row_ref"] == sibling["raw_source_path"]
    assert clinical[0]["cfu_per_day"] is None
    assert _probiotic_native_evidence_state(product, owner) is None


@pytest.mark.parametrize("forgery", ["wrong_owner", "missing_owner", "changed_form"])
def test_recorded_source_reference_is_reproved_against_actual_label(enricher, forgery):
    product = _collect(enricher, [_row("Bifidobacterium longum", "BB536"), _row("Lactobacillus acidophilus", index=1)])
    product["probiotic_data"]["clinical_strains"] = [{
        "strain": "Bifidobacterium longum BB536", "clinical_id": "STRAIN_LONGUM_BB536",
        "source_row_ref": "ingredientRows[0]", "label_name": "Bifidobacterium longum",
        "research_match_status": "exact_strain", "clinical_support_level": "strong",
    }]
    if forgery == "wrong_owner":
        product["probiotic_data"]["clinical_strains"][0]["source_row_ref"] = "ingredientRows[1]"
    elif forgery == "missing_owner":
        product["probiotic_data"]["clinical_strains"][0]["source_row_ref"] = "ingredientRows[99]"
    else:
        product["activeIngredients"][0]["forms"] = [{"name": "BB-12"}]
    assert independent_clinical_strains(product) == []
    blob = build_detail_blob(product, {})
    assert blob["probiotic_detail"]["clinical_strains"] == []
    assert all(row["clinical_support_level"] is None for row in blob["ingredients"])


@pytest.mark.parametrize("name", ["HOWARU", "Lactobacillus acidophilus NCFM"])
def test_multiple_distinct_strain_forms_cannot_inherit_whole_owner_cfu(enricher, name):
    owner = _row(name, "Lactobacillus acidophilus NCFM")
    owner["forms"].append({"name": "Lactobacillus rhamnosus HN001"})
    product = _collect(enricher, [owner])
    assert product["probiotic_data"]["clinical_strains"] == []
    assert product["probiotic_data"]["total_cfu"] == 10_000_000_000


def test_scientific_form_identity_does_not_double_count_disclosed_cfu(enricher):
    from scoring_v4.modules.probiotic_dose import score_dose

    product = _collect(enricher, [_row("Bifidobacterium longum", "BB536"), _row("Lactobacillus acidophilus", index=1, cfu=0)])
    assert len(independent_clinical_strains(product)) == 1
    dose = score_dose(product)
    assert dose["metadata"]["per_strain_cfu_disclosed_count"] == 1
    assert dose["components"]["per_strain_cfu_disclosure"] == 5
    assert product["probiotic_data"]["total_cfu"] == 10_000_000_000


@pytest.mark.parametrize("duplicates", [False, True])
def test_legacy_no_ref_fallback_requires_one_exact_label_owner(enricher, duplicates):
    rows = [_row("Bifidobacterium longum BB536")]
    if duplicates:
        rows.append(_row("Bifidobacterium longum BB536", index=1, cfu=0))
    product = _collect(enricher, rows)
    clinical = product["probiotic_data"]["clinical_strains"][:1]
    clinical[0].pop("source_row_ref", None)
    product["probiotic_data"]["clinical_strains"] = clinical
    expected = not duplicates
    assert (_probiotic_native_evidence_state(product, rows[0]) is not None) is expected
    for row in build_detail_blob(product, {})["ingredients"]:
        assert (row["clinical_support_level"] is not None) is expected


def test_invalid_clinical_ref_never_falls_back_to_matching_name(enricher):
    owner = _row("Bifidobacterium longum BB536")
    product = _collect(enricher, [owner])
    product["probiotic_data"]["clinical_strains"][0]["source_row_ref"] = "ingredientRows[99]"
    assert _probiotic_native_evidence_state(product, owner) is None
    assert build_detail_blob(product, {})["ingredients"][0]["clinical_support_level"] is None


def test_full_form_cannot_override_conflicting_parent_taxonomy(enricher):
    owner = _row("HOWARU", "Lactobacillus acidophilus NCFM")
    owner["standardName"] = "Bifidobacterium"
    assert _collect(enricher, [owner])["probiotic_data"]["clinical_strains"] == []


def test_same_species_distinct_label_codes_keep_both_disclosures(enricher):
    from scoring_v4.modules.probiotic_dose import score_dose

    product = _collect(enricher, [_row("Lactobacillus rhamnosus GG"), _row("Lactobacillus rhamnosus HN001", index=1)])
    assert len(independent_clinical_strains(product)) == 2
    assert score_dose(product)["metadata"]["per_strain_cfu_disclosed_count"] == 2


@pytest.mark.parametrize("forms", [
    ["Lactobacillus acidophilus NCFM", "Lactobacillus acidophilus (NCFM)"],
    ["Lactobacillus acidophilus NCFM", "Lactobacillus acidophilus"],
])
def test_redundant_exact_forms_and_species_descriptor_are_not_distinct_strains(enricher, forms):
    owner = _row("Lactobacillus acidophilus NCFM")
    owner["forms"] = [{"name": form} for form in forms]
    product = _collect(enricher, [owner])
    assert len(independent_clinical_strains(product)) == 1
    assert product["probiotic_data"]["clinical_strains"][0]["cfu_per_day"] == 10_000_000_000


@pytest.mark.parametrize("name,form", [
    ("Saccharomyces boulardii", "S. cerevisiae strain"),
    ("Bacillus coagulans MTCC5856", "Lactobacillus sporogenes"),
])
def test_exact_direct_strain_survives_generic_species_form_descriptor(enricher, name, form):
    product = _collect(enricher, [_row(name, form)])
    assert len(independent_clinical_strains(product)) == 1
    assert product["probiotic_data"]["clinical_strains"][0]["strain"] == name


@pytest.mark.parametrize("name,form", [
    ("Lactobacillus acidophilus NCFM", "Lactobacillus acidophilus CUL60"),
    ("Bifidobacterium longum BB536", "Bifidobacterium lactis BB-12"),
    ("Lactobacillus rhamnosus GG", "Bifidobacterium rhamnosus gg"),
])
def test_exact_direct_name_cannot_override_contradictory_explicit_form_code(enricher, name, form):
    assert _collect(enricher, [_row(name, form)])["probiotic_data"]["clinical_strains"] == []


@pytest.mark.parametrize("brand,product_id", [
    ("Jarrow_Formulas", "307727"), ("Jarrow_Formulas", "307728"), ("Thorne", "337852"),
])
def test_real_direct_name_generic_form_controls(enricher, brand, product_id):
    path = SCRIPTS_ROOT / f"products/output_{brand}_enriched/enriched/enriched_cleaned_batch_1.json"
    if not path.exists():
        pytest.skip("Local manifest-owned direct-strain control is absent")
    from stage_manifest import select_stage_input_files

    assert path in select_stage_input_files(path.parent, "enrich", require_manifest=True)
    product = next(p for p in json.loads(path.read_text()) if str(p.get("id")) == product_id)
    product["probiotic_data"] = enricher._collect_probiotic_data(product)
    clinical = independent_clinical_strains(product)
    assert len(clinical) == 1
    assert clinical[0]["strain"] == product["activeIngredients"][0]["name"]
    assert clinical[0]["source_row_ref"] == "ingredientRows[0]"


@pytest.mark.parametrize("name,code", [
    ("Lactobacillus rhamnosus", "LGG"),
    ("Bifidobacterium animalis subsp. lactis", "BB-12"),
    ("Bifidobacterium longum", "BB536"),
])
def test_exact_group_code_is_owned_through_producer_readiness_and_export(enricher, name, code):
    owner = _row(name)
    owner["ingredientGroup"] = code
    owner["notes"] = ""  # typed code, not prose
    sibling = _row(name, index=1, cfu=0)
    product = _collect(enricher, [owner, sibling])
    clinical = independent_clinical_strains(product)
    assert len(clinical) == 1
    assert clinical[0]["source_row_ref"] == owner["raw_source_path"]
    assert clinical[0]["label_name"] == name
    assert clinical[0]["cfu_per_day"] == 10_000_000_000
    assert _probiotic_native_evidence_state(product, owner) is not None
    assert _probiotic_native_evidence_state(product, sibling) is None
    exported = build_detail_blob(product, {})["ingredients"]
    assert exported[0]["clinical_support_level"] is not None
    assert exported[1]["clinical_support_level"] is None


@pytest.mark.parametrize("case", [
    "no_source_ref", "notes_only", "taxonomy_only", "wrong_genus",
    "wrong_code", "conflicting_form", "group_alone", "genus_only",
])
def test_group_code_requires_exact_source_owned_species_without_conflicts(enricher, case):
    owner = _row("Lactobacillus rhamnosus")
    owner["ingredientGroup"] = "LGG"
    if case == "no_source_ref":
        owner.pop("raw_source_path")
    elif case == "notes_only":
        owner["ingredientGroup"] = "Lactobacillus rhamnosus"
        owner["notes"] = "strain LGG"
    elif case == "taxonomy_only":
        owner["ingredientGroup"] = "Lactobacillus rhamnosus"
    elif case == "wrong_genus":
        owner["name"] = owner["raw_source_text"] = "Bifidobacterium rhamnosus"
    elif case == "wrong_code":
        owner["ingredientGroup"] = "GGX"
    elif case == "conflicting_form":
        owner["forms"] = [{"name": "Lactobacillus rhamnosus HN001"}]
    elif case == "genus_only":
        owner["name"] = owner["raw_source_text"] = "Lactobacillus"
    else:
        owner["name"] = owner["raw_source_text"] = "Probiotic"
    assert _collect(enricher, [owner])["probiotic_data"]["clinical_strains"] == []
