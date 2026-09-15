"""Formulation rewards complete label identity, independently of count/potency."""

from copy import deepcopy

import pytest

from scoring_v4.modules.probiotic_formulation import score_formulation


IDENTITIES = [
    ("Lactobacillus rhamnosus GG", "STRAIN_LGG"),
    ("Lactobacillus plantarum 299v", "STRAIN_PLANTARUM_299V"),
    ("Lactobacillus reuteri DSM 17938", "STRAIN_REUTERI_DSM17938"),
    ("Bifidobacterium longum BB536", "STRAIN_LONGUM_BB536"),
    ("Lactobacillus rhamnosus HN001", "STRAIN_RHAMNOSUS_HN001"),
]


def product_with_identities(exact=1, unknown=0):
    rows, clinical, blends = [], [], []
    for index, (name, cid) in enumerate(
        IDENTITIES[:exact] + [(f"Unknown organism {i}", None) for i in range(unknown)]
    ):
        ref = f"ingredientRows[{index}]"
        rows.append({"name": name, "raw_source_path": ref})
        blends.append({"name": name, "raw_source_path": ref, "strains": [name]})
        if cid:
            clinical.append({"strain": name, "clinical_id": cid, "source_row_ref": ref})
    return {
        "activeIngredients": rows,
        "probiotic_data": {
            "total_billion_count": 1, "total_strain_count": 99,
            "has_survivability_coating": True,
            "probiotic_blends": blends, "clinical_strains": clinical,
        },
    }


def test_complete_single_and_five_strains_receive_same_formulation():
    single = score_formulation(product_with_identities(1))
    five = score_formulation(product_with_identities(5))
    assert single["score"] == five["score"] == 15
    assert single["max"] == five["max"] == 16
    assert single["components"]["exact_identity_completeness"] == 8
    assert five["components"]["exact_identity_completeness"] == 8
    assert "cfu_amount" not in single["components"]
    assert "named_species_diversity" not in single["components"]


@pytest.mark.parametrize("stale_count", [0, 1, 4, 99, None, True, "bad"])
def test_partial_identity_uses_label_denominator_in_every_dimension(stale_count):
    from scoring_v4.modules.probiotic_dose import score_dose
    from scoring_v4.modules.probiotic_transparency import score_transparency

    product = product_with_identities(2, 2)
    product["probiotic_data"]["total_strain_count"] = stale_count
    for blend in product["probiotic_data"]["probiotic_blends"][:2]:
        blend["cfu_data"] = {"has_cfu": True, "cfu_count": 1e9}
    formulation = score_formulation(product)
    assert formulation["score"] == 11
    assert formulation["metadata"]["total_strain_count"] == 4
    dose = score_dose(product)
    assert dose["metadata"]["total_strain_count"] == 4
    assert dose["components"]["per_strain_cfu_disclosure"] == 5
    assert score_transparency(product)["components"]["per_strain_cfu_on_label"] == 3.5


@pytest.mark.parametrize("malformed", [None, 5, True, {}, [], "", " "])
def test_malformed_names_and_count_only_payloads_never_create_identity_credit(malformed):
    from scoring_v4.modules.probiotic_dose import score_dose
    from scoring_v4.modules.probiotic_transparency import score_transparency

    product = {"probiotic_data": {
        "total_strain_count": 4,
        "clinical_strains": [{"clinical_id": "STRAIN_LGG"}],
        "probiotic_blends": [{"strains": [malformed],
                              "cfu_data": {"has_cfu": True, "cfu_count": 1e9}}],
    }}
    assert score_formulation(product)["metadata"]["total_strain_count"] == 0
    assert score_dose(product)["score"] == 0
    transparency = score_transparency(product)
    assert transparency["components"]["strain_identities_named"] == 0
    assert transparency["components"]["per_strain_cfu_on_label"] == 0


def test_species_only_and_potency_invariance():
    product = product_with_identities(0)
    product["probiotic_data"]["probiotic_blends"] = [{"strains": ["Lactobacillus rhamnosus"]}]
    assert score_formulation(product)["score"] == 7
    product = product_with_identities(1)
    before = score_formulation(product)
    product["probiotic_data"]["total_billion_count"] = 50
    after = score_formulation(product)
    assert before["components"] == after["components"]


@pytest.mark.parametrize("within_blend", [False, True])
def test_duplicate_alias_and_projection_share_identity_and_disclosure_key(within_blend):
    from scoring_v4.modules.probiotic_dose import score_dose
    from scoring_v4.modules.probiotic_transparency import score_transparency
    product = product_with_identities(1)
    blend = product["probiotic_data"]["probiotic_blends"][0]
    blend["cfu_data"] = {"has_cfu": True, "cfu_count": 1e9}
    alias = deepcopy(blend)
    alias["strains"] = ["L. rhamnosus GG"]
    if within_blend:
        blend["strains"].append("L. rhamnosus GG")
    product["probiotic_data"]["probiotic_blends"].extend([deepcopy(blend)] if within_blend else [deepcopy(blend), alias])
    product["activeIngredients"].append(deepcopy(product["activeIngredients"][0]))
    result = score_formulation(product)
    assert result["metadata"]["total_strain_count"] == 1
    assert result["components"]["exact_identity_completeness"] == 8
    assert score_dose(product)["metadata"]["per_strain_cfu_disclosed_count"] == 1
    assert score_transparency(product)["components"]["per_strain_cfu_on_label"] == 7


@pytest.mark.parametrize("mutation", ["wrong_id", "no_owner", "id_only", "no_blends"])
def test_exact_identity_requires_matching_source_proof(mutation):
    from scoring_v4.modules.probiotic_transparency import score_transparency
    from studied_formulas import label_owned_native_strains
    product = product_with_identities(1)
    clinical = product["probiotic_data"]["clinical_strains"][0]
    if mutation == "wrong_id":
        clinical["clinical_id"] = "STRAIN_LONGUM_BB536"
    elif mutation == "no_owner":
        product["activeIngredients"] = []
    elif mutation == "id_only":
        del clinical["strain"]
    else:
        product["probiotic_data"]["probiotic_blends"] = []
    result = score_formulation(product)
    assert result["components"]["exact_identity_completeness"] == (0 if mutation == "no_owner" else 8)
    assert result["metadata"]["total_strain_count"] == 1
    if mutation != "no_blends":
        assert label_owned_native_strains(product) == []
    if mutation == "no_blends":
        assert score_transparency(product)["components"]["strain_identities_named"] == 8


def test_count_only_and_detached_ids_cannot_supply_missing_label_names():
    from scoring_v4.modules.probiotic_dose import score_dose
    from scoring_v4.modules.probiotic_transparency import score_transparency
    product = {"probiotic_data": {"total_strain_count": 12,
                                 "clinical_strains": [{"clinical_id": "STRAIN_LGG"}]}}
    assert score_formulation(product)["score"] == 0
    assert score_dose(product)["score"] == 0
    assert score_transparency(product)["score"] == 0


def test_species_general_registry_identity_is_not_exact():
    from studied_formulas import _clinical_strain_registry
    registry = _clinical_strain_registry()
    cid = "STRAIN_SACCHAROMYCES"
    reference = registry[cid]
    name = reference["standard_name"]
    product = product_with_identities(1)
    product["activeIngredients"][0]["name"] = name
    product["probiotic_data"]["probiotic_blends"][0]["strains"] = [name]
    product["probiotic_data"]["clinical_strains"][0].update(strain=name, clinical_id=cid)
    assert score_formulation(product)["components"]["exact_identity_completeness"] == 0


@pytest.mark.parametrize("amount", [None, True, 0, -1, "nan", "infinity"])
def test_invalid_total_cfu_does_not_receive_potency_disclosure(amount):
    product = product_with_identities(1)
    product["probiotic_data"]["total_billion_count"] = amount
    assert score_formulation(product)["components"]["total_cfu_disclosed"] == 0


@pytest.mark.parametrize("exact,unknown,expected", [(1, 0, 18.8), (5, 0, 18.8), (2, 2, 13.8), (0, 1, 8.8)])
def test_public_formulation_uses_16_point_reference(exact, unknown, expected):
    from scoring_v4.modules.probiotic import score_probiotic
    from scoring_v4.quality_score import assemble_quality_score
    product = product_with_identities(exact, unknown)
    module = score_probiotic(product).to_breakdown()
    public = assemble_quality_score({"v4_module": "probiotic", "v4_verdict": "SAFE", "raw_score_v4_100": 50,
                                    "v4_breakdown": {"module": module}})
    assert public["quality_pillars_v4"]["formulation"]["score"] == expected
    assert public["quality_pillars_v4"]["formulation"]["max"] == 20


def test_existing_full_prebiotic_complement_reaches_public_formulation_max():
    from scoring_v4.modules.probiotic import score_probiotic
    from scoring_v4.quality_score import assemble_quality_score
    product = product_with_identities(1)
    product["probiotic_data"].update(prebiotic_present=True, prebiotic_dose_g=3)
    module = score_probiotic(product).to_breakdown()
    public = assemble_quality_score({"v4_module": "probiotic", "v4_verdict": "SAFE", "raw_score_v4_100": 50,
                                    "v4_breakdown": {"module": module}})
    assert public["quality_pillars_v4"]["formulation"]["score"] == 20


def test_registered_alias_dedup_does_not_require_clinical_projection():
    from studied_formulas import independent_clinical_strains, label_owned_native_strains
    from scoring_v4.modules.probiotic_dose import score_dose
    from scoring_v4.modules.probiotic_transparency import score_transparency
    product = product_with_identities(1)
    product["probiotic_data"]["clinical_strains"] = []
    blend = product["probiotic_data"]["probiotic_blends"][0]
    blend["cfu_data"] = {"has_cfu": True, "cfu_count": 1e9}
    for names in [["Lactobacillus rhamnosus GG"], ["Lactobacillus rhamnosus GG", "L. rhamnosus GG"]]:
        blend["strains"] = names
        formulation = score_formulation(product)
        assert formulation["metadata"]["total_strain_count"] == 1
        assert formulation["components"]["exact_identity_completeness"] == 8
        assert score_dose(product)["components"]["per_strain_cfu_disclosure"] == 10
        assert score_transparency(product)["components"]["per_strain_cfu_on_label"] == 7
        assert label_owned_native_strains(product) == independent_clinical_strains(product) == []


@pytest.mark.parametrize("field", ["forms", "ingredientGroup"])
def test_source_local_unknown_group_codes_match_form_denominator(field):
    from scoring_v4.modules.probiotic_dose import score_dose
    from scoring_v4.modules.probiotic_transparency import score_transparency
    product = product_with_identities(2)
    product["probiotic_data"]["clinical_strains"] = []
    for row, blend, code in zip(product["activeIngredients"], product["probiotic_data"]["probiotic_blends"],
                                ["Unknown-A123", "Unknown-B456"]):
        row["name"] = "B. longum"
        row[field] = [{"name": code}] if field == "forms" else code
        blend.update(name=row["name"], strains=[row["name"]])
    product["probiotic_data"]["probiotic_blends"][0]["cfu_data"] = {"has_cfu": True, "cfu_count": 1e9}
    product["activeIngredients"].append(deepcopy(product["activeIngredients"][0]))
    product["probiotic_data"]["probiotic_blends"].append(deepcopy(product["probiotic_data"]["probiotic_blends"][0]))
    formulation = score_formulation(product)
    assert formulation["metadata"]["total_strain_count"] == 2
    assert formulation["components"]["exact_identity_completeness"] == 0
    assert score_dose(product)["components"]["per_strain_cfu_disclosure"] == 5
    assert score_transparency(product)["components"]["per_strain_cfu_on_label"] == 3.5


def test_exported_count_uses_same_source_owned_denominator_as_scoring():
    from build_final_db import build_detail_blob
    product = product_with_identities(1)
    product["probiotic_data"]["is_probiotic_product"] = True
    assert product["probiotic_data"]["total_strain_count"] == 99
    assert score_formulation(product)["metadata"]["total_strain_count"] == 1
    assert build_detail_blob(product, {})["probiotic_detail"]["total_strain_count"] == 1


@pytest.mark.parametrize("forms", [42, True, False, "invalid", {"name": "invalid"}])
def test_malformed_unrelated_forms_do_not_crash_or_authorize_identity(forms):
    from studied_formulas import _clinical_strain_registry, clinical_strain_identity_from_label
    from scoring_v4.modules.probiotic_dose import score_dose
    from scoring_v4.modules.probiotic_transparency import score_transparency
    product = product_with_identities(1)
    scorers = [score_formulation, score_dose, score_transparency]
    before = [scorer(product) for scorer in scorers]
    product["activeIngredients"].append({"name": "Vitamin D", "raw_source_path": "ingredientRows[1]", "forms": forms})
    assert [scorer(product) for scorer in scorers] == before
    malformed_owner = {**product["activeIngredients"][0], "forms": forms}
    assert clinical_strain_identity_from_label(malformed_owner, _clinical_strain_registry()["STRAIN_LGG"]) is None
