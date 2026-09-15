"""Physical label identity is source-owned, not a clinical eligibility proxy."""

from copy import deepcopy

import pytest

from scoring_v4.modules.probiotic_formulation import score_formulation
from studied_formulas import label_owned_native_strains
from test_native_clinical_strain_provenance import _owned_product
from test_probiotic_identity_completeness import product_with_identities


@pytest.mark.parametrize("name", ["Lactobacillus acidophilus", "Bifidobacterium longum Unknown-A123"])
@pytest.mark.parametrize("projections", ["all", "known_only", "none"])
@pytest.mark.parametrize("remove_clinical", [False, True])
def test_source_membership_does_not_shrink_when_unresolved_projection_is_missing(name, projections, remove_clinical):
    from build_final_db import build_detail_blob
    from scoring_v4.modules.probiotic_dose import score_dose
    from scoring_v4.modules.probiotic_transparency import score_transparency

    product = product_with_identities(1, 1)
    product["probiotic_data"]["is_probiotic_product"] = True
    product["activeIngredients"][1]["name"] = name
    product["probiotic_data"]["probiotic_blends"][1]["strains"] = [name]
    product["probiotic_data"]["probiotic_blends"][0]["cfu_data"] = {"has_cfu": True, "cfu_count": 1e9}
    product["activeIngredients"].extend([
        {"name": "Vitamin D", "category": "vitamin", "raw_source_path": "ingredientRows[2]"},
        {"name": "C. sinensis", "category": "botanical", "raw_source_path": "ingredientRows[3]"},
    ])
    if projections != "all":
        product["probiotic_data"]["probiotic_blends"] = product["probiotic_data"]["probiotic_blends"][:1] if projections == "known_only" else []
    if remove_clinical:
        product["probiotic_data"]["clinical_strains"] = []
    formulation = score_formulation(product)
    assert formulation["metadata"]["total_strain_count"] == 2
    assert formulation["metadata"]["identified_strain_count"] == 1
    assert formulation["components"]["exact_identity_completeness"] == 4
    dose = score_dose(product)
    assert dose["metadata"]["total_strain_count"] == 2
    assert dose["components"]["per_strain_cfu_disclosure"] == (0 if projections == "none" else 5)
    transparency = score_transparency(product)
    assert transparency["metadata"]["total_strain_count"] == 2
    assert transparency["components"]["per_strain_cfu_on_label"] == (0 if projections == "none" else 3.5)
    assert build_detail_blob(product, {})["probiotic_detail"]["total_strain_count"] == 2


@pytest.mark.parametrize("source", [
    {"category": "probiotic"},
    {"name": None, "category": "bacteria"},
    {"name": "", "category": "probiotic"},
    {"name": "Vitamin D", "category": "vitamin"},
    {"name": "C. sinensis", "category": "botanical"},
    {"name": "Lactobacillus ferment extract", "category": "bacteria"},
    {"name": "Probiotic Blend", "cleaner_row_role": "blend_header_total"},
    {"name": "Probiotic Blend", "hierarchyType": "blend_header"},
    {"name": "Probiotic Blend", "dose_class": "blend_total_weight"},
    {"name": "Probiotic Blend", "score_exclusion_reason": "blend_header_total"},
])
def test_source_completion_keeps_existing_eligibility_and_header_boundaries(source):
    product = product_with_identities(1)
    product["activeIngredients"].append({**source, "raw_source_path": "ingredientRows[1]"})
    result = score_formulation(product)
    assert result["metadata"]["total_strain_count"] == 1
    assert result["components"]["exact_identity_completeness"] == 8


def test_source_completion_retains_explicit_probiotic_role_without_inventing_identity():
    product = product_with_identities(1)
    product["activeIngredients"].append({"name": "Unknown organism", "category": "probiotic",
                                          "raw_source_path": "ingredientRows[1]"})
    result = score_formulation(product)
    assert result["metadata"]["total_strain_count"] == 2
    assert result["components"]["exact_identity_completeness"] == 4


@pytest.mark.parametrize("stale_projection", [False, True])
@pytest.mark.parametrize("alias", [False, True])
def test_nonlive_projection_cannot_change_live_identity_denominator_or_disclosure(stale_projection, alias):
    from build_final_db import build_detail_blob
    from scoring_v4.modules.probiotic_dose import score_dose
    from scoring_v4.modules.probiotic_transparency import score_transparency

    product = product_with_identities(2)
    product["probiotic_data"].update(is_probiotic_product=True, clinical_strains=[])
    product["activeIngredients"][1]["forms"] = [{"name": "heat killed"}]
    live, nonlive = product["probiotic_data"]["probiotic_blends"]
    live["cfu_data"] = {"has_cfu": True, "cfu_count": 1e9}
    nonlive["cfu_data"] = {"has_cfu": True, "cfu_count": 50e9}
    if alias:
        nonlive["strains"] = ["L. plantarum 299v"]
    if not stale_projection:
        product["probiotic_data"]["probiotic_blends"] = [live]
    formulation = score_formulation(product)
    assert formulation["metadata"]["total_strain_count"] == 1
    assert formulation["metadata"]["identified_strain_count"] == 1
    assert formulation["components"]["exact_identity_completeness"] == 8
    dose = score_dose(product)
    assert dose["metadata"]["per_strain_cfu_disclosed_count"] == 1
    assert dose["components"]["per_strain_cfu_disclosure"] == 10
    assert score_transparency(product)["components"]["per_strain_cfu_on_label"] == 7
    assert build_detail_blob(product, {})["probiotic_detail"]["total_strain_count"] == 1


def test_mixed_live_nonlive_aggregate_does_not_become_an_individual_cfu_amount():
    from scoring_v4.modules.probiotic_dose import score_dose
    product = product_with_identities(2)
    product["activeIngredients"][1]["forms"] = [{"name": "heat killed"}]
    product["probiotic_data"]["probiotic_blends"] = [{
        "strains": [row["name"] for row in product["activeIngredients"]],
        "cfu_data": {"has_cfu": True, "cfu_count": 50e9},
    }]
    assert score_formulation(product)["metadata"]["total_strain_count"] == 1
    assert score_dose(product)["metadata"]["per_strain_cfu_disclosed_count"] == 0


@pytest.mark.parametrize("name", ["L. rhamnosus GG", "lactobacillus rhamnosus gg"])
def test_source_alias_case_does_not_change_exact_identity_specificity(name):
    product = product_with_identities(1)
    product["activeIngredients"][0]["name"] = name
    product["probiotic_data"]["probiotic_blends"][0]["strains"] = [name]
    product["probiotic_data"]["clinical_strains"] = []
    assert score_formulation(product)["components"]["exact_identity_completeness"] == 8


@pytest.mark.parametrize("duplicate_owner", [False, True])
def test_legacy_exact_label_retains_existing_unique_owner_proof(duplicate_owner):
    product = _owned_product(clinical_id="STRAIN_LGG", strain="Lactobacillus rhamnosus GG")
    product["activeIngredients"][0].pop("raw_source_path")
    product["probiotic_data"]["probiotic_blends"][0].pop("raw_source_path")
    if duplicate_owner:
        product["activeIngredients"].append(deepcopy(product["activeIngredients"][0]))
    assert len(label_owned_native_strains(product)) == (0 if duplicate_owner else 1)
    for clinical in (product["probiotic_data"]["clinical_strains"], []):
        product["probiotic_data"]["clinical_strains"] = clinical
        assert score_formulation(product)["components"]["exact_identity_completeness"] == (0 if duplicate_owner else 8)


@pytest.mark.parametrize("ref", [["ingredientRows[1]"], {"path": "ingredientRows[1]"}, 1, True, ""])
def test_malformed_sibling_source_path_cannot_rescue_legacy_owner(ref):
    product = product_with_identities(1)
    owner = product["activeIngredients"][0]
    owner.pop("raw_source_path")
    product["activeIngredients"].append({**owner, "raw_source_path": ref})
    product["probiotic_data"]["probiotic_blends"][0].pop("raw_source_path")
    product["probiotic_data"]["clinical_strains"] = []
    assert score_formulation(product)["components"]["exact_identity_completeness"] == 0


@pytest.mark.parametrize("form", [42, True, False, {}, {"name": 42}, {"name": True}])
def test_malformed_form_members_cannot_authorize_exact_identity(form):
    product = product_with_identities(1)
    product["activeIngredients"][0]["forms"] = [form]
    assert score_formulation(product)["components"]["exact_identity_completeness"] == 0
    assert label_owned_native_strains(product) == []


@pytest.mark.parametrize("conflict", ["different_strain", "malformed_forms", "different_member_set"])
def test_conflicting_representations_of_same_source_path_fail_closed(conflict):
    product = product_with_identities(1)
    owner = product["activeIngredients"][0]
    duplicate = deepcopy(owner)
    if conflict == "different_strain":
        duplicate["name"] = "Lactobacillus rhamnosus HN001"
    elif conflict == "malformed_forms":
        duplicate["forms"] = [True]
    else:
        for row in (owner, duplicate):
            row["name"] = "HOWARU"
            row["forms"] = [{"name": "Lactobacillus acidophilus NCFM"}]
        owner["forms"].append({"name": "Lactobacillus rhamnosus HN001"})
        product["probiotic_data"]["probiotic_blends"][0]["strains"] = ["HOWARU"]
    product["activeIngredients"].append(duplicate)
    assert score_formulation(product)["components"]["exact_identity_completeness"] == 0


@pytest.mark.parametrize("stale_projection", [False, True])
@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("nonlive_name", ["Lactobacillus rhamnosus GG", "L. rhamnosus GG"])
def test_nonlive_same_path_representation_cannot_be_hidden_by_live_duplicate(stale_projection, reverse, nonlive_name):
    from scoring_v4.modules.probiotic_dose import score_dose
    product = product_with_identities(1)
    product["probiotic_data"]["probiotic_blends"][0]["cfu_data"] = {"has_cfu": True, "cfu_count": 1e9}
    nonlive = {**product["activeIngredients"][0], "name": nonlive_name,
               "forms": [{"name": "heat killed"}]}
    product["activeIngredients"].append(nonlive)
    if reverse:
        product["activeIngredients"].reverse()
    if not stale_projection:
        product["probiotic_data"]["probiotic_blends"] = []
    result = score_formulation(product)
    assert result["metadata"]["total_strain_count"] == 0
    assert result["metadata"]["identified_strain_count"] == 0
    assert result["components"]["exact_identity_completeness"] == 0
    assert label_owned_native_strains(product) == []
    assert score_dose(product)["metadata"]["per_strain_cfu_disclosed_count"] == 0
    assert len(product["probiotic_data"]["clinical_strains"]) == 1  # Original diagnostic survives.


def test_ambiguous_registry_alias_does_not_select_an_identity(monkeypatch):
    import studied_formulas
    registry = deepcopy(studied_formulas._clinical_strain_registry())
    registry["STRAIN_LONGUM_BB536"]["aliases"].append("Lactobacillus rhamnosus GG")
    monkeypatch.setattr(studied_formulas, "_clinical_strain_registry", lambda: registry)
    assert score_formulation(product_with_identities(1))["components"]["exact_identity_completeness"] == 0


@pytest.mark.parametrize("policy", ["BLOCKED_PROBIOTIC_STRAINS", "HOLD_PROBIOTIC_STRAINS"])
@pytest.mark.parametrize("label", ["Lactobacillus rhamnosus GG", "L. rhamnosus GG"])
def test_source_blocking_policy_is_independent_of_projection_presence(monkeypatch, policy, label):
    import constants
    monkeypatch.setattr(constants, policy, getattr(constants, policy) | {"lactobacillus rhamnosus gg"})
    product = product_with_identities(1)
    product["activeIngredients"][0]["name"] = label
    product["probiotic_data"]["probiotic_blends"][0]["strains"] = [label]
    for clinical in (product["probiotic_data"]["clinical_strains"], []):
        product["probiotic_data"]["clinical_strains"] = clinical
        assert score_formulation(product)["components"]["exact_identity_completeness"] == 0


@pytest.mark.parametrize("mutation", ["wrong_species", "wrong_code", "missing_ref", "mismatched_ref", "sibling_form"])
def test_structured_identity_requires_its_compatible_source_owner(mutation):
    product = product_with_identities(1)
    owner = product["activeIngredients"][0]
    owner.update(name="Bifidobacterium longum", forms=[{"name": "BB536"}])
    blend = product["probiotic_data"]["probiotic_blends"][0]
    blend["strains"] = [owner["name"]]
    if mutation == "wrong_species":
        owner["name"] = blend["strains"][0] = "Lactobacillus longum"
    elif mutation == "wrong_code":
        owner["name"] = blend["strains"][0] = "Bifidobacterium longum Unknown-A123"
    elif mutation == "missing_ref":
        owner.pop("raw_source_path")
    elif mutation == "mismatched_ref":
        blend["raw_source_path"] = "ingredientRows[99]"
        # This projection cannot borrow a quantity from the independently
        # proven source identity at ingredientRows[0].
        blend["cfu_data"] = {"has_cfu": True, "cfu_count": 1e9}
        from scoring_v4.modules.probiotic_dose import score_dose
        assert score_dose(product)["metadata"]["per_strain_cfu_disclosed_count"] == 0
        assert score_formulation(product)["metadata"]["identified_strain_count"] == 1
        return
    else:
        sibling = deepcopy(owner)
        sibling["raw_source_path"] = "ingredientRows[1]"
        owner["forms"] = []
        product["activeIngredients"].append(sibling)
        result = score_formulation(product)
        assert result["metadata"]["total_strain_count"] == 2
        assert result["components"]["exact_identity_completeness"] == 4
        return
    assert score_formulation(product)["components"]["exact_identity_completeness"] == 0
