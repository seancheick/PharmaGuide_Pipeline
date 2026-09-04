"""Clinical matching must use the quantified label owner, not its blend header."""

from copy import deepcopy

import pytest

from test_green_tea_evidence_identity import _source_product


@pytest.fixture(scope="module")
def enricher():
    from enrich_supplements_v3 import SupplementEnricherV3

    return SupplementEnricherV3()


def _green_tea_complex(*, disclosed=True):
    # DSLD 20009: a 400 mg complex comprises 250 mg leaf powder and
    # 150 mg extract. The 400 mg total is never an extract dose.
    product = _source_product("Green Tea Complex")
    product["id"] = "20009"
    parent = product["activeIngredients"][0]
    parent.update(
        quantity=400.0, raw_source_path="ingredientRows[1]",
        dose_class="blend_total_weight", cleaner_row_role="blend_header_total",
        score_eligible_by_cleaner=False, isProprietaryBlend=True,
    )
    powder = deepcopy(_source_product("Green Tea Powder")["activeIngredients"][0])
    powder.update(
        canonical_id="green_tea_leaf", canonical_source_db="botanical_ingredients",
        raw_source_path="ingredientRows[1].nestedRows[0]", quantity=250.0,
        parentBlend="Green Tea Complex", isNestedIngredient=True,
    )
    extract = deepcopy(_source_product("Green Tea Extract", forms=[{
        "name": "EGCG", "prefix": "Standardized to", "percent": 40,
        "category": "non-nutrient/non-botanical", "ingredientGroup": "EGCG",
    }])["activeIngredients"][0])
    extract.update(
        raw_source_path="ingredientRows[1].nestedRows[1]",
        quantity=150.0 if disclosed else 0.0, unit="mg" if disclosed else "NP",
        parentBlend="Green Tea Complex", isNestedIngredient=True,
    )
    if not disclosed:
        extract.update(
            cleaner_row_role="nested_display_only", score_eligible_by_cleaner=False,
            dose_class="undisclosed_blend_child", score_exclusion_reason="nested_display_only",
        )
    for row in (powder, extract):
        row["raw_taxonomy"].update(
            parentBlend="Green Tea Complex", isNestedIngredient=True, nested_depth=1,
        )
    parent["nestedIngredients"] = [powder, extract]
    return product


def test_quantified_nested_extract_owns_its_evidence_and_amount(enricher):
    source = _green_tea_complex()
    product, issues = enricher.enrich_product(deepcopy(source))
    assert product.get("enrichment_status") != "validation_failed", issues
    rows = enricher._primary_active_ingredients_for_enrichment(product)
    assert "ingredientRows[1]" not in {row["raw_source_path"] for row in rows}
    extract = next(row for row in rows
                   if row["raw_source_path"] == "ingredientRows[1].nestedRows[1]")
    assert extract["quantity"] == 150.0
    assert extract["forms"] == source["activeIngredients"][0]["nestedIngredients"][1]["forms"]
    matches = [m for m in product["evidence_data"]["clinical_matches"]
               if m["id"] == "INGR_GREEN_TEA"]
    assert len(matches) == 1
    assert matches[0]["matched_source_row_refs"] == ["ingredientRows[1].nestedRows[1]"]
    assert matches[0]["ingredient"] == "Green Tea Extract"


def test_nested_display_only_child_cannot_borrow_the_complex_amount(enricher):
    product, issues = enricher.enrich_product(_green_tea_complex(disclosed=False))
    assert product.get("enrichment_status") != "validation_failed", issues
    rows = enricher._primary_active_ingredients_for_enrichment(product)
    assert "ingredientRows[1].nestedRows[1]" not in {
        row["raw_source_path"] for row in rows
    }
    assert not [m for m in product["evidence_data"]["clinical_matches"]
                if m["id"] == "INGR_GREEN_TEA"]


def test_dose_projection_keeps_ancestor_context_without_promoting_it_to_evidence(enricher):
    product, _ = enricher.enrich_product(_green_tea_complex())
    rows = enricher._dose_active_ingredients_for_enrichment(product)
    by_ref = {row["raw_source_path"]: row for row in rows}
    assert by_ref["ingredientRows[1]"]["quantity"] == 400.0
    assert by_ref["ingredientRows[1].nestedRows[1]"]["quantity"] == 150.0
    assert by_ref["ingredientRows[1]"]["score_eligible_by_cleaner"] is False


def test_synergy_cluster_uses_nested_extract_dose_not_complex_header(enricher):
    product, issues = enricher.enrich_product(_green_tea_complex())
    assert product.get("enrichment_status") != "validation_failed", issues

    original_db = enricher.databases["synergy_cluster"]
    enricher.databases["synergy_cluster"] = {
        "synergy_clusters": [{
            "id": "green-tea-dose-owner",
            "standard_name": "green-tea-dose-owner",
            "ingredients": ["green tea extract"],
            "canonical_ids": ["green tea extract"],
            "min_effective_doses": {"green tea extract": 200},
            "allow_single_ingredient": True,
            "primary_ingredients": ["green tea extract"],
        }],
        "min_effective_dose_units": {},
    }
    try:
        clusters = enricher._collect_synergy_data(product)
    finally:
        enricher.databases["synergy_cluster"] = original_db

    assert len(clusters) == 1
    assert clusters[0]["underdosed_single"] is True
    assert clusters[0]["matched_ingredients"] == [{
        "ingredient": "Green Tea Extract",
        "cluster_ingredient": "green tea extract",
        "quantity": 150.0,
        "unit": "mg",
        "min_effective_dose": 200,
        "min_effective_dose_unit": "mg",
        "evaluated_quantity": 150.0,
        "evaluated_unit": "mg",
        "dose_evaluable": True,
        "meets_minimum": False,
    }]


def test_standardized_botanical_collector_uses_disclosed_child_only(enricher):
    product, issues = enricher.enrich_product(_green_tea_complex())
    assert product.get("enrichment_status") != "validation_failed", issues

    botanicals = enricher._collect_standardized_botanicals(product)
    assert len(botanicals) == 1
    assert botanicals[0]["botanical_id"] == "green_tea"
    assert botanicals[0]["name"] == "Green Tea Extract"


def test_standardized_botanical_collector_excludes_display_only_child(enricher):
    product, issues = enricher.enrich_product(_green_tea_complex(disclosed=False))
    assert product.get("enrichment_status") != "validation_failed", issues
    assert enricher._collect_standardized_botanicals(product) == []


def test_absorption_collector_does_not_borrow_non_scorable_parent_target(enricher):
    product = {
        "id": "absorption-parent-borrow",
        "fullName": "Curcumin Complex + Piperine",
        "activeIngredients": [],
        "inactiveIngredients": [],
        "servingSizes": [{
            "order": 1,
            "minQuantity": 1.0,
            "maxQuantity": 1.0,
            "unit": "Capsule(s)",
            "minDailyServings": 1,
            "maxDailyServings": 1,
        }],
    }
    parent = deepcopy(_source_product("Curcumin")["activeIngredients"][0])
    parent.update(
        name="Curcumin Complex",
        raw_source_text="Curcumin Complex",
        raw_source_path="ingredientRows[0]",
        standardName="Curcumin",
        canonical_id="curcumin",
        ingredientGroup="Curcumin",
        raw_category="non-nutrient/non-botanical",
        quantity=500.0,
        unit="mg",
        cleaner_row_role="blend_header_total",
        score_eligible_by_cleaner=False,
        dose_class="blend_total_weight",
        isProprietaryBlend=True,
    )
    parent["raw_taxonomy"].update(category="non-nutrient/non-botanical", ingredientGroup="Curcumin")
    piperine = deepcopy(_source_product("Piperine")["activeIngredients"][0])
    piperine.update(
        raw_source_path="ingredientRows[1]",
        standardName="Piperine",
        canonical_id="piperine",
        ingredientGroup="Piperine",
        raw_category="non-nutrient/non-botanical",
        quantity=20.0,
        unit="mg",
    )
    piperine["raw_taxonomy"].update(category="non-nutrient/non-botanical", ingredientGroup="Piperine")
    product["activeIngredients"] = [parent, piperine]

    enriched, issues = enricher.enrich_product(product)
    assert enriched.get("enrichment_status") != "validation_failed", issues

    absorption = enricher._collect_absorption_data(enriched)
    assert absorption["enhancer_present"] is True
    assert absorption["enhanced_nutrients_present"] == []
    assert absorption["qualifies_for_bonus"] is False
