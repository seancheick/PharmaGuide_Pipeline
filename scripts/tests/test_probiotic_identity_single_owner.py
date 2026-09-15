"""One probiotic identity owner for enrichment, taxonomy, routing and scoring input.

``probiotic_measurements.is_probiotic_source_identity`` owns row-level probiotic
identity, including the rule that a resolved non-probiotic IQM identity outranks
a broad or wrong DSLD category. Routing, the scoring input contract and the
enricher's CFU-accessory checks previously kept their own regex copies and
category shortcuts, so Spirulina and a mislabeled Turmeric extract still counted
as probiotic there while Leuconostoc (a real microbe the old text missed) did not.
Row shapes are copied from stored enriched products.
"""

from __future__ import annotations

import copy

import pytest

import probiotic_measurements as owner

SPIRULINA_IQD = {
    "name": "Parry Organic Spirulina", "standard_name": "Spirulina", "category": "functional_foods",
    "canonical_id": "spirulina", "canonical_source_db": "ingredient_quality_map", "dose_class": "therapeutic_mass",
    "raw_source_path": "ingredientRows[5]", "quantity": 1500.0, "unit": "mg", "role_classification": "active_scorable",
    "raw_taxonomy": {"category": "bacteria", "ingredientGroup": "Blue-Green Algae"},
}
TURMERIC_IQD = {
    "name": "standardized Turmeric extract", "standard_name": "Turmeric", "category": "herbs",
    "canonical_id": "turmeric", "canonical_source_db": "ingredient_quality_map", "dose_class": "therapeutic_mass",
    "raw_source_path": "ingredientRows[26]", "quantity": 50.0, "unit": "mg", "role_classification": "active_scorable",
    "raw_taxonomy": {"category": "bacteria", "ingredientGroup": "Turmeric"},
}
LEUCONOSTOC_IQD = {
    "name": "Leuconostoc cremoris", "standard_name": "Leuconostoc Cremoris", "category": "probiotics",
    "canonical_id": "leuconostoc_cremoris", "canonical_source_db": "ingredient_quality_map",
    "raw_source_path": "ingredientRows[1]", "quantity": 1.0, "unit": "Billion CFU", "role_classification": "active_scorable",
    "raw_taxonomy": {"category": "bacteria", "ingredientGroup": "Leuconostoc cremoris"},
}
ACIDOPHILUS_IQD = {
    "name": "Lactobacillus acidophilus", "standard_name": "Lactobacillus Acidophilus", "category": "probiotics",
    "canonical_id": "lactobacillus_acidophilus", "canonical_source_db": "ingredient_quality_map",
    "raw_source_path": "ingredientRows[0]", "quantity": 1.0, "unit": "Billion CFU", "role_classification": "active_scorable",
    "raw_taxonomy": {"category": "bacteria", "ingredientGroup": "Lactobacillus acidophilus"},
}
VITAMIN_C_IQD = {
    "name": "Vitamin C", "standard_name": "Vitamin C", "category": "vitamins", "canonical_id": "vitamin_c",
    "canonical_source_db": "ingredient_quality_map", "raw_source_path": "ingredientRows[2]",
    "quantity": 60.0, "unit": "mg", "role_classification": "active_scorable", "raw_taxonomy": {"category": "vitamin"},
}
LEUCONOSTOC_CLEANER = {
    "name": "Leuconostoc cremoris", "standardName": "Leuconostoc Cremoris", "raw_category": "bacteria",
    "canonical_id": "leuconostoc_cremoris", "canonical_source_db": "ingredient_quality_map",
    "cleaner_row_role": "active_scorable", "score_eligible_by_cleaner": True, "raw_source_path": "ingredientRows[0]",
    "quantity": 1.0, "unit": "Billion CFU", "raw_taxonomy": {"category": "bacteria", "ingredientGroup": "Leuconostoc cremoris"},
}
SPIRULINA_CLEANER = {
    "name": "Parry Organic Spirulina", "standardName": "Spirulina", "raw_category": "bacteria",
    "canonical_id": "spirulina", "canonical_source_db": "ingredient_quality_map",
    "cleaner_row_role": "active_scorable", "score_eligible_by_cleaner": True, "raw_source_path": "ingredientRows[1]",
    "quantity": 1500.0, "unit": "mg", "raw_taxonomy": {"category": "bacteria", "ingredientGroup": "Blue-Green Algae"},
}


# Stored cleaner row from 232325 "Oral Hygiene": the curated identity is a
# nonviable heat-treated L. plantarum L-137 preparation, but this label prints no
# processing wording and DSLD files it under ``bacteria``.
IMMUNO_LP20_CLEANER = {
    "name": "Immuno-LP20", "standardName": "Immuno-LP20", "raw_source_text": "Immuno-LP20",
    "raw_category": "bacteria", "canonical_id": "NHA_IMMUNO_LP20", "canonical_source_db": "other_ingredients",
    "dose_class": "therapeutic_mass", "quantity": 50.0, "unit": "mg", "cleaner_row_role": "active_scorable",
    "forms": [{"name": "L. plantarum L-137", "category": "bacteria", "ingredientGroup": "Lactobacillus plantarum"}],
    "raw_taxonomy": {"category": "bacteria", "ingredientGroup": "Lactobacillus plantarum"},
}
IMMUNO_LP20_STRICT = {
    "name": "Immuno-LP20", "standardName": "Immuno-LP20", "raw_source_text": "Immuno-LP20",
    "canonical_id": "nha_immuno_lp20", "canonical_source_db": "other_ingredients", "dose_class": "therapeutic_mass",
    "quantity": 50.0, "unit": "mg", "cleaner_row_role": "active_scorable", "role_classification": "active_scorable",
    "forms": [{"name": "L. plantarum L-137", "category": "bacteria", "ingredientGroup": "Lactobacillus plantarum"}],
    "raw_taxonomy": {"category": "bacteria", "ingredientGroup": "Lactobacillus plantarum"},
}
BLIS_M18_STRICT = {
    "name": "BLIS M18 S. salivarius M18", "category": "probiotics", "canonical_id": "streptococcus_salivarius",
    "canonical_source_db": "ingredient_quality_map", "dose_class": "therapeutic_mass", "quantity": 10.0, "unit": "mg",
    "role_classification": "active_scorable",
}
# Stored nested carrier from 177233 "Zinc": yeast-cultured mineral source, 0 mg, not an organism.
YEAST_CARRIER_177233 = {
    "name": "S. cerevisiae", "standardName": "Saccharomyces cerevisiae (yeast)", "raw_source_text": "S. cerevisiae",
    "raw_category": "other", "canonical_id": "PII_SACCHAROMYCES_CEREVISIAE", "canonical_source_db": "other_ingredients",
    "cleaner_row_role": "nested_display_only", "raw_source_path": "ingredientRows[1].nestedRows[1]",
    "quantity": 0.0, "unit": "NP", "forms": [], "isNestedIngredient": True, "parentBlend": "Nourishing Food Blend",
    "raw_taxonomy": {"category": "other", "ingredientGroup": "Saccharomyces cerevisiae"},
}


def _route_product(*rows: dict) -> dict:
    from scoring_input_contract import _ROUTE_SCORING_ROWS_CACHE_KEY

    return {_ROUTE_SCORING_ROWS_CACHE_KEY: [copy.deepcopy(row) for row in rows]}


@pytest.fixture(scope="module")
def enricher():
    from enrich_supplements_v3 import SupplementEnricherV3
    return SupplementEnricherV3()


def test_probiotic_identity_regex_has_one_owner():
    import scoring_input_contract
    import supplement_taxonomy

    assert supplement_taxonomy.has_probiotic_identity_text is owner.has_probiotic_identity_text
    assert scoring_input_contract.is_probiotic_source_identity is owner.is_probiotic_source_identity


@pytest.mark.parametrize("text", ["Jarro-Dophilus EPS", "One A Day TruBiotics", "Ultra Probiotics", "Lactobacillus rhamnosus"])
def test_shared_regex_keeps_every_token_the_former_copies_recognized(text):
    assert owner.has_probiotic_identity_text(text)


def test_mass_dosed_brewers_yeast_is_not_a_live_probiotic_identity():
    row = {
        "name": "Saccharomyces cerevisiae nutritional yeast",
        "standardName": "Brewer's Yeast",
        "canonical_id": "brewers_yeast",
        "canonical_source_db": "ingredient_quality_map",
        "category": "functional_foods",
        "quantity": 1000,
        "unit": "mg",
    }

    assert owner.is_probiotic_source_identity(row) is False


def test_mass_dosed_explicit_probiotic_is_not_lost_to_a_bad_reference_mapping():
    row = {
        "name": "ibSium probiotic",
        "standardName": "Brewer's Yeast",
        "canonical_id": "brewers_yeast",
        "canonical_source_db": "ingredient_quality_map",
        "category": "functional_foods",
        "quantity": 250,
        "unit": "mg",
    }

    assert owner.is_probiotic_source_identity(row) is True


def test_unquantified_printed_organism_remains_a_named_blend_member():
    row = {
        "name": "Saccharomyces cerevisiae",
        "standardName": "Brewer's Yeast",
        "canonical_id": "brewers_yeast",
        "canonical_source_db": "ingredient_quality_map",
        "category": "functional_foods",
        "quantity": 0,
        "unit": "NP",
    }

    assert owner.is_probiotic_source_identity(row) is True


@pytest.mark.parametrize("unit", ["CFU", "Billion CFU", "AFU"])
def test_resolved_yeast_identity_requires_and_accepts_viability_units(unit):
    row = {
        "name": "Saccharomyces cerevisiae CNCM I-3856",
        "standardName": "Brewer's Yeast",
        "canonical_id": "brewers_yeast",
        "canonical_source_db": "ingredient_quality_map",
        "category": "functional_foods",
        "quantity": 1,
        "unit": unit,
    }

    assert owner.is_probiotic_source_identity(row) is True


def test_probiotic_support_companions_have_one_owner():
    import scoring_input_contract
    import supplement_taxonomy

    assert scoring_input_contract.is_probiotic_support_source is owner.is_probiotic_support_source
    assert supplement_taxonomy.is_probiotic_support_source is owner.is_probiotic_support_source


def test_every_canonical_prebiotic_identity_is_a_probiotic_support_source():
    """The support predicate must consume the canonical catalog, not copy terms."""
    from prebiotic_catalog import prebiotic_catalog

    missed = []
    for standard_name, terms in prebiotic_catalog():
        for label in (standard_name, *terms):
            if not owner.is_probiotic_support_source({"name": label}):
                missed.append((standard_name, label))

    assert missed == []


@pytest.mark.parametrize("row,expected", [
    ({"name": "NutraFlora scFOS", "canonical_id": "prebiotics"}, True),
    ({"name": "Fiber", "iqm_parent_key": "fiber"}, True),
    ({"name": "Galacto-oligosaccharide"}, True),
    ({"name": "Dietary  Fiber"}, True),
    ({"name": "Vitamin C", "canonical_id": "vitamin_c"}, False),
])
def test_probiotic_support_companion_vocabulary(row, expected):
    assert owner.is_probiotic_support_source(row) is expected


def test_route_panel_counts_spirulina_and_mislabeled_turmeric_as_non_probiotic():
    from scoring_input_contract import _route_non_probiotic_scorable_count

    product = _route_product(ACIDOPHILUS_IQD, SPIRULINA_IQD, TURMERIC_IQD, VITAMIN_C_IQD)

    assert _route_non_probiotic_scorable_count(product) == 3


def test_route_panel_keeps_category_only_microbes_out_of_the_non_probiotic_count():
    from scoring_input_contract import _route_non_probiotic_scorable_count

    assert _route_non_probiotic_scorable_count(_route_product(ACIDOPHILUS_IQD, LEUCONOSTOC_IQD)) == 0


def test_contract_strict_active_check_does_not_treat_a_real_microbe_as_an_adjunct():
    from scoring_input_contract import _has_non_probiotic_strict_active

    microbe_only = {"ingredient_quality_data": {"ingredients_scorable": [copy.deepcopy(LEUCONOSTOC_IQD)]}}
    with_greens = {"ingredient_quality_data": {"ingredients_scorable": [
        copy.deepcopy(LEUCONOSTOC_IQD), copy.deepcopy(SPIRULINA_IQD)]}}

    assert _has_non_probiotic_strict_active(microbe_only) is False
    assert _has_non_probiotic_strict_active(with_greens) is True


@pytest.mark.parametrize("row", [IMMUNO_LP20_CLEANER, IMMUNO_LP20_STRICT, YEAST_CARRIER_177233],
                         ids=["immuno_lp20_cleaner", "immuno_lp20_strict", "processing_aid_yeast_carrier"])
def test_resolved_other_ingredients_identity_is_not_an_organism_by_category_or_derived_name(row):
    assert owner.is_probiotic_source_identity(copy.deepcopy(row)) is False


def test_other_ingredients_holds_no_live_probiotic_identity():
    """A resolved other_ingredients record outranks category-only organism evidence.

    That is only safe while the file holds processing aids, label descriptors and
    derived or nonviable preparations. Adding a microbe-, yeast- or culture-named
    record must trigger a review of this rule, so the reviewed set is pinned.
    """
    import json
    import re
    from pathlib import Path

    data = json.loads((Path(owner.__file__).parent / "data" / "other_ingredients.json").read_text())
    yeast_or_culture = re.compile(r"\b(?:yeast|cultures?)\b", re.IGNORECASE)
    named = {
        (entry["id"], entry.get("category"))
        for entry in data["other_ingredients"]
        if any(owner.has_probiotic_identity_text(text) or yeast_or_culture.search(text)
               for text in [str(entry.get("standard_name") or "")] + [str(a) for a in entry.get("aliases") or []])
    }
    assert named == {
        ("NHA_DNF10_YEAST_HYDROLYSATE", "active_pending_relocation"),
        ("NHA_SACCHAROMYCES_CEREVISIAE_EXTRACT", "active_pending_relocation"),
        ("NHA_SYNTOL_DIGESTIVE_YEAST_CLEANSE", "label_descriptor"),
        ("NHA_YEAST_FERMENTATE_DRIED", "active_pending_relocation"),
        ("OI_MOS_YEAST_FRACTION", "active_pending_relocation"),
        ("OI_TOTAL_CULTURES", "label_descriptor"),
        ("PII_FERMENT_MEDIA", "processing_aid"),
        ("PII_KEFIR_STARTER_CULTURE", "processing_aid"),
        ("PII_PROBIOTIC_MICROORGANISMS_DESCRIPTOR", "label_descriptor"),
        ("PII_SACCHAROMYCES_CEREVISIAE", "processing_aid"),
    }


def test_contract_keeps_nonviable_preparation_as_a_non_probiotic_active():
    from scoring_input_contract import _has_non_probiotic_strict_active

    product = {"ingredient_quality_data": {"ingredients_scorable": [
        copy.deepcopy(BLIS_M18_STRICT), copy.deepcopy(IMMUNO_LP20_STRICT)]}}

    assert _has_non_probiotic_strict_active(product) is True


def test_enricher_cfu_accessory_check_uses_the_shared_identity(enricher):
    microbe_only = {"product_name": "Kefir Culture", "activeIngredients": [copy.deepcopy(LEUCONOSTOC_CLEANER)]}
    with_greens = {"product_name": "Kefir Culture", "activeIngredients": [
        copy.deepcopy(LEUCONOSTOC_CLEANER), copy.deepcopy(SPIRULINA_CLEANER)]}

    assert enricher._has_non_probiotic_active_for_cfu_evidence(microbe_only) is False
    assert enricher._has_non_probiotic_active_for_cfu_evidence(with_greens) is True
