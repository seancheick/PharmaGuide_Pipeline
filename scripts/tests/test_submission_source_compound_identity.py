"""Source preparations retain their own identity through shared enrichment."""

from copy import deepcopy

import pytest

from enrich_supplements_v3 import SupplementEnricherV3


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3()


@pytest.mark.parametrize("source", [
    "inositol niacinate", "Inositol Nicotinate",
    "Inositol Hexanicotinate", "Inositol Hexaniacinate",
])
def test_inositol_niacinate_does_not_claim_d_chiro(enricher, source):
    product = {
        "id": "source-preparation-test", "product_name": "Inositol",
        "activeIngredients": [{
            "name": "Inositol", "standardName": "Inositol",
            "canonical_id": "inositol",
            "canonical_source_db": "ingredient_quality_map",
            "quantity": 1, "unit": "mg",
            "forms": [{"name": source}],
        }], "inactiveIngredients": [],
    }
    original = deepcopy(product)
    enriched, errors = enricher.enrich_product(product)
    assert not errors
    row = enriched["ingredient_quality_data"]["ingredients"][0]
    assert row["canonical_id"] == "inositol"
    assert row["form_id"] == "inositol from inositol hexanicotinate"
    assert row["bio_score"] == 5
    assert row["absorption"] is None
    assert "D-chiro" not in (row["notes"] or "")
    assert row["quantity"] == 1
    assert enriched["activeIngredients"][0]["forms"] == original["activeIngredients"][0]["forms"]


@pytest.mark.parametrize("source", [
    "tributyrin", "CoreBiome", "CoreBiome tributyrin", "CoreBiome butyrate",
    "glyceryl tributyrate", "glycerol tributyrate",
])
def test_tributyrin_is_not_unspecified_free_acid(enricher, source):
    product = {
        "id": "tributyrin-test", "product_name": "Tributyrin",
        "activeIngredients": [{
            "name": source, "standardName": "Butyric Acid",
            "canonical_id": "butyric_acid",
            "canonical_source_db": "ingredient_quality_map",
            "quantity": 300, "unit": "mg",
            "forms": [{"name": source}],
        }], "inactiveIngredients": [],
    }
    enriched, errors = enricher.enrich_product(product)
    assert not errors
    row = enriched["ingredient_quality_data"]["ingredients"][0]
    assert row["canonical_id"] == "butyric_acid"
    assert row["form_id"] == "tributyrin"
    assert row["bio_score"] == 5
    assert row["absorption"] is None
    assert row["quantity"] == 300


def test_unknown_inositol_source_does_not_select_named_ester(enricher):
    product = {
        "id": "unknown-source-test", "product_name": "Inositol",
        "activeIngredients": [{
            "name": "Inositol", "standardName": "Inositol",
            "canonical_id": "inositol",
            "canonical_source_db": "ingredient_quality_map",
            "quantity": 1, "unit": "mg",
            "forms": [{"name": "unidentified preparation"}],
        }], "inactiveIngredients": [],
    }
    enriched, errors = enricher.enrich_product(product)
    assert not errors
    row = enriched["ingredient_quality_data"]["ingredients"][0]
    assert row["form_id"] != "inositol from inositol hexanicotinate"


@pytest.mark.parametrize("parent,name,source,expected", [
    ("vitamin_b3_niacin", "Niacin", "inositol niacinate", "inositol hexanicotinate"),
    ("inositol", "Inositol", "myo-inositol", "myo-inositol"),
    ("inositol", "Inositol", "d-chiro-inositol", "d-chiro-inositol"),
    ("butyric_acid", "Butyric Acid", "sodium butyrate", "sodium butyrate"),
    ("butyric_acid", "Butyric Acid", "butyric acid", "butyric acid (unspecified)"),
])
def test_existing_parent_and_form_identities_remain_distinct(enricher, parent, name, source, expected):
    product = {
        "id": "existing-identity", "product_name": name,
        "activeIngredients": [{
            "name": name, "standardName": name,
            "canonical_id": parent, "canonical_source_db": "ingredient_quality_map",
            "quantity": 10, "unit": "mg", "forms": [{"name": source}],
        }], "inactiveIngredients": [],
    }
    enriched, errors = enricher.enrich_product(product)
    assert not errors
    row = enriched["ingredient_quality_data"]["ingredients"][0]
    assert row["canonical_id"] == parent
    assert row["form_id"] == expected


@pytest.mark.parametrize("name,source", [
    # Native DSLD shape (e.g. Nature's Way 293377): PS row, source form only.
    ("Phosphatidylserine", "Sunflower Lecithin"),
    # Submitted label: the printed row keeps its wording; the source form is
    # recorded the way DSLD records PS sources (plain name, no "from").
    ("Phosphatidyl Serine from Sunflower (Helianthus annuus L.) Seed",
     "Sunflower (Helianthus annuus L.) Seed"),
])
def test_sunflower_sourced_phosphatidylserine_selects_the_sunflower_form(enricher, name, source):
    product = {
        "id": "sunflower-ps", "product_name": name,
        "activeIngredients": [{
            "name": name, "standardName": "Phosphatidylserine",
            "canonical_id": "phosphatidylserine",
            "canonical_source_db": "ingredient_quality_map",
            "quantity": 100, "unit": "mg", "forms": [{"name": source}],
        }], "inactiveIngredients": [],
    }
    enriched, errors = enricher.enrich_product(product)
    assert not errors
    row = enriched["ingredient_quality_data"]["ingredients"][0]
    assert row["canonical_id"] == "phosphatidylserine"
    assert row["form_id"] == "sunflower phosphatidylserine"
    assert row["quantity"] == 100


def test_a_sunflower_source_alias_never_turns_lecithin_into_phosphatidylserine(enricher):
    product = {
        "id": "sunflower-lecithin", "product_name": "Sunflower Lecithin",
        "activeIngredients": [{
            "name": "Sunflower Lecithin", "standardName": "Lecithin",
            "canonical_id": "lecithin", "canonical_source_db": "ingredient_quality_map",
            "quantity": 1200, "unit": "mg", "forms": [],
        }], "inactiveIngredients": [],
    }
    enriched, errors = enricher.enrich_product(product)
    assert not errors
    row = enriched["ingredient_quality_data"]["ingredients"][0]
    assert row["canonical_id"] == "lecithin"
