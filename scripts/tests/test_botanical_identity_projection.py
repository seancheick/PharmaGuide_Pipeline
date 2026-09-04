"""One registry-owned botanical identity must reach every source-row surface."""

from __future__ import annotations

from copy import deepcopy

import pytest

from enrich_supplements_v3 import SupplementEnricherV3
from scoring_input_contract import get_scoring_ingredients
from scoring_v4.scored_artifact import build_scored_artifact
from scoring_v4.modules.generic_evidence import resolved_clinical_matches


@pytest.fixture(scope="module")
def enricher() -> SupplementEnricherV3:
    return SupplementEnricherV3()


def _product(product_id: str, quantity: float, source_ref: str) -> dict:
    """The owning row reduced from manifest-owned GNC 312254 / 312701."""
    forms = [{
        "name": "Camellia sinensis Leaf Extract", "ingredientId": 302633,
        "category": "botanical", "ingredientGroup": "Tea (unspecified)",
        "uniiCode": "W2ZU1RY8B0", "prefix": None, "percent": None,
    }]
    row = {
        "name": "Black Tea Leaf Extract", "raw_source_text": "Black Tea Leaf Extract",
        "standardName": "Green Tea Extract", "canonical_id": "green_tea_extract",
        "canonical_source_db": "ingredient_quality_map",
        "cleaner_match_method": "unii_form_exact_match",
        "ingredientGroup": "Black Tea", "raw_category": "botanical",
        "raw_source_path": source_ref, "quantity": quantity, "unit": "mg",
        "forms": forms, "raw_taxonomy": {
            "category": "botanical", "ingredientGroup": "Black Tea",
            "forms": deepcopy(forms), "isNestedIngredient": False,
        },
        "cleaner_row_role": "active_scorable", "score_eligible_by_cleaner": True,
        "score_exclusion_reason": None, "source_section": "active",
        "dose_class": "therapeutic_mass", "nestedIngredients": [],
        "parentBlend": None, "isNestedIngredient": False,
    }
    return {
        "id": product_id, "fullName": "Black Tea Leaf Extract",
        "activeIngredients": [row], "inactiveIngredients": [],
    }


@pytest.mark.parametrize("product_id,quantity,source_ref", [
    ("312254", 272.0, "ingredientRows[1]"),
    ("312701", 100.0, "ingredientRows[7]"),
])
def test_black_tea_source_identity_is_coherent_on_active_iqd_and_scoring_rows(
    enricher: SupplementEnricherV3, product_id: str, quantity: float, source_ref: str,
) -> None:
    source = _product(product_id, quantity, source_ref)
    before = deepcopy(source)
    product, issues = enricher.enrich_product(deepcopy(source))
    assert product.get("enrichment_status") != "validation_failed", issues
    expected = ("black_tea_leaf", "botanical_ingredients", "Black Tea Leaf")
    active = product["activeIngredients"][0]
    quality = product["ingredient_quality_data"]["ingredients"][0]
    assert (active["canonical_id"], active["canonical_source_db"], active["standardName"]) == expected
    assert (quality["canonical_id"], quality["canonical_source_db"], quality["standard_name"]) == expected
    for row in (active, quality):
        assert row["canonical_id_before"] == "green_tea_extract"
        assert row["canonical_id_after"] == "black_tea_leaf"
        assert row["identity_disposition"] == "taxonomy_only"
        assert row["scoreable_identity"] is False
    assert (quality["recognized_entry_id"], quality["recognition_source"],
            quality["recognized_entry_name"]) == expected
    assert quality["recognition_type"] == "botanical_marker_lineage"
    for field in ("bio_score", "score", "form_id", "matched_form", "final_form_bio_score"):
        assert quality.get(field) is None
    scoring = get_scoring_ingredients(product, strict=True)
    projected = next(row for row in scoring.rows if row.get("raw_source_path") == source_ref)
    assert (projected["canonical_id"], projected["canonical_source_db"], projected["standardName"]) == expected
    assert projected["quantity"] == quantity
    for field in ("name", "raw_source_text", "raw_source_path", "forms", "raw_taxonomy",
                  "quantity", "unit", "parentBlend", "isNestedIngredient"):
        assert active[field] == before["activeIngredients"][0][field]


@pytest.mark.parametrize("invalid_record", ["missing_record", "missing_name", "blank_name"])
@pytest.mark.parametrize("strict", [True, False])
def test_invalid_botanical_record_blocks_marker_and_retains_required_coverage(
    invalid_record: str, strict: bool,
) -> None:
    enricher = SupplementEnricherV3()
    source = _product("unresolved-botanical-owner", 100.0, "ingredientRows[0]")
    row = source["activeIngredients"][0]
    row.update(canonical_id="black_tea_leaf", canonical_source_db="botanical_ingredients")
    # Inject malformed reference data at the database boundary, never a mocked
    # identity decision or matcher. The stale Green Tea IQM candidate remains.
    botanical_db = deepcopy(enricher.databases["botanical_ingredients"])
    entries = botanical_db["botanical_ingredients"]
    entry = next(item for item in entries if item["id"] == "black_tea_leaf")
    if invalid_record == "missing_record":
        entries.remove(entry)
    elif invalid_record == "missing_name":
        entry.pop("standard_name")
    else:
        entry["standard_name"] = " "
    enricher.databases = {**enricher.databases, "botanical_ingredients": botanical_db}
    enricher._build_performance_indexes()
    peer = deepcopy(row)
    peer.update(name="Vitamin C", raw_source_text="Vitamin C", standardName="Vitamin C",
                canonical_id="vitamin_c", canonical_source_db="ingredient_quality_map",
                raw_source_path="ingredientRows[1]", ingredientGroup="Vitamin C",
                forms=[], raw_taxonomy={"category": "vitamin", "ingredientGroup": "Vitamin C", "forms": []})
    source["activeIngredients"].append(peer)
    product, _ = enricher.enrich_product(deepcopy(source))

    quality = product["ingredient_quality_data"]["ingredients"][0]
    assert quality["identity_disposition"] == "identity_conflict"
    assert quality["identity_decision_reason"] == "botanical_source_identity_unresolved"
    assert quality["mapped_identity"] is False
    assert quality["canonical_id"] is None
    assert quality["bio_score"] is None
    assert quality["score"] is None
    scoring = get_scoring_ingredients(product, strict=strict)
    assert scoring.unmapped_count == 1
    assert scoring.mapped_coverage == 0.5
    assert [item["canonical_id"] for item in scoring.rows] == ["vitamin_c"]
    artifact = build_scored_artifact(product)
    assert artifact["quality_score_status"] == "not_scored"
    assert artifact["assessment_readiness"]["identity"]["readiness"] == "incomplete"


@pytest.mark.parametrize("label,group", [
    ("Black Tea Leaf Extract", "Black Tea"), ("Caffeine", "Caffeine"),
])
def test_unknown_declared_botanical_id_cannot_gain_marker_credit(
    enricher: SupplementEnricherV3, label: str, group: str,
) -> None:
    source = _product("unknown-botanical-record", 100.0, "ingredientRows[0]")
    source["activeIngredients"][0].update(
        canonical_id="nonexistent_botanical_source", canonical_source_db="botanical_ingredients",
    )
    if label == "Caffeine":
        source["activeIngredients"][0].update(
            name=label, raw_source_text=label, standardName=label, ingredientGroup=group,
            forms=[], raw_taxonomy={"category": "botanical", "ingredientGroup": group, "forms": []},
        )
    product, _ = enricher.enrich_product(deepcopy(source))
    quality = product["ingredient_quality_data"]["ingredients"][0]
    assert quality["identity_disposition"] == "identity_conflict"
    assert quality["canonical_id"] is None
    assert quality["scoreable_identity"] is False
    assert quality["bio_score"] is None
    assert quality["score"] is None
    scoring = get_scoring_ingredients(product, strict=True)
    assert scoring.rows == []
    assert scoring.unmapped_count == 1


def test_botanical_parent_does_not_take_its_declared_children_identity_or_mass(
    enricher: SupplementEnricherV3,
) -> None:
    source = _product("312701", 100.0, "ingredientRows[7]")
    for index, name, canonical, quantity in (
        (0, "Caffeine", "caffeine", 10.0),
        (1, "Polyphenols", "polyphenols", 60.0),
    ):
        child = deepcopy(source["activeIngredients"][0])
        child.update(
            name=name, raw_source_text=name, standardName=name,
            canonical_id=canonical, canonical_source_db="ingredient_quality_map",
            ingredientGroup=name, quantity=quantity, forms=[],
            raw_source_path=f"ingredientRows[7].nestedRows[{index}]",
            parentBlend="Black Tea Leaf Extract", parentBlendMass=100,
            parentBlendUnit="mg", isNestedIngredient=True,
            raw_taxonomy={"category": "non-nutrient/non-botanical", "ingredientGroup": name,
                          "forms": [], "parentBlend": "Black Tea Leaf Extract", "isNestedIngredient": True},
        )
        source["activeIngredients"].append(child)
    product, _ = enricher.enrich_product(deepcopy(source))
    rows = {row["raw_source_path"]: row for row in get_scoring_ingredients(product, strict=True).rows}
    parent = rows["ingredientRows[7]"]
    assert parent["canonical_id"] == "black_tea_leaf"
    assert parent["standardName"] == "Black Tea Leaf"
    assert parent["quantity"] == 100.0
    assert parent["generic_form_quality_credit"] is False
    assert rows["ingredientRows[7].nestedRows[0]"]["canonical_id"] == "caffeine"
    assert rows["ingredientRows[7].nestedRows[0]"]["quantity"] == 10.0
    assert rows["ingredientRows[7].nestedRows[1]"]["canonical_id"] == "polyphenols"
    assert rows["ingredientRows[7].nestedRows[1]"]["quantity"] == 60.0
    assert "INGR_GREEN_TEA" not in {match["id"] for match in resolved_clinical_matches(product)[0]}
    for original, active in zip(source["activeIngredients"], product["activeIngredients"], strict=True):
        for field in ("name", "raw_source_path", "raw_source_text", "raw_taxonomy", "forms",
                      "quantity", "unit", "parentBlend", "isNestedIngredient"):
            assert active[field] == original[field]


@pytest.mark.parametrize("source_name,canonical,source_db,preferred_name", [
    ("Black Tea Leaf Extract", "black_tea_leaf", "botanical_ingredients", "Black Tea Leaf"),
    ("Cinnamon bark powder", "cinnamon_bark", "botanical_ingredients", "Cinnamon Bark"),
    ("Svetol Green Coffee bean extract", "green_coffee_bean", "standardized_botanicals", "Green Coffee Bean"),
])
def test_valid_source_owner_remains_primary(
    enricher: SupplementEnricherV3, source_name: str, canonical: str,
    source_db: str, preferred_name: str,
) -> None:
    source = _product(f"source-owned-{canonical}", 100.0, "ingredientRows[0]")
    row = source["activeIngredients"][0]
    row.update(name=source_name, raw_source_text=source_name, standardName=preferred_name,
               canonical_id=canonical, canonical_source_db=source_db, forms=[])
    row["raw_taxonomy"].update(ingredientGroup=preferred_name, forms=[])
    row["ingredientGroup"] = preferred_name
    product, _ = enricher.enrich_product(deepcopy(source))
    active = product["activeIngredients"][0]
    quality = product["ingredient_quality_data"]["ingredients"][0]
    assert (active["canonical_id"], active["canonical_source_db"], active["standardName"]) == (
        canonical, source_db, preferred_name,
    )
    assert quality["canonical_id"] == canonical
    assert quality["scoreable_identity"] is False
    assert quality.get("bio_score") is None
    assert quality.get("score") is None


def test_source_owned_standardized_marker_form_stays_secondary(
    enricher: SupplementEnricherV3,
) -> None:
    source = _product("231908", 400.0, "ingredientRows[0]")
    form = {"name": "Chlorogenic Acids", "prefix": "std. to", "percent": 50,
            "category": "non-nutrient/non-botanical", "ingredientGroup": "chlorogenic acid"}
    source["activeIngredients"][0].update(
        name="CoffeeGenic Green Coffee extract", raw_source_text="CoffeeGenic Green Coffee extract",
        canonical_id="green_coffee_bean", canonical_source_db="standardized_botanicals",
        standardName="Green Coffee Bean", ingredientGroup="Green Coffee",
        cleaner_match_method=None, branded_token_extracted="CoffeeGenic", forms=[form],
        raw_taxonomy={"category": "botanical", "ingredientGroup": "Green Coffee", "forms": [deepcopy(form)]},
    )
    product, _ = enricher.enrich_product(deepcopy(source))
    active = product["activeIngredients"][0]
    quality = product["ingredient_quality_data"]["ingredients"][0]
    assert active["canonical_id"] == "green_coffee_bean"
    assert active["standardName"] == "Green Coffee Bean"
    assert quality["identity_disposition"] == "taxonomy_only"
    assert quality["recognition_source"] == "standardized_botanicals"
    assert quality["recognized_entry_name"] == "Green Coffee Bean"
    assert quality["bio_score"] is None
    assert quality["score"] is None
    assert active["forms"] == [form]
    assert active["quantity"] == 400.0
