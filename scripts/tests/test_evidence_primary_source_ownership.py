"""Structural source totals must not compete with their own evidenced active."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from scoring_input_contract import get_scoring_ingredients
from scoring_v4.modules.generic_evidence import score_evidence


def _ps_complex_product():
    # DSLD 213475 declares 100 mg PS within a 500 mg SerinAid complex.
    # Use the existing evidence record unchanged: this tests ownership, not
    # its clinical classification, score magnitudes, or a new dose threshold.
    registry = json.loads(
        (Path(__file__).resolve().parents[1] / "data/backed_clinical_studies.json")
        .read_text()
    )
    evidence = deepcopy(next(
        entry for entry in registry["backed_clinical_studies"]
        if entry["id"] == "BRAND_PHOSPHATIDYLSERINE"
    ))
    child_ref = "ingredientRows[1].nestedRows[0]"
    evidence.update(
        ingredient="Phosphatidylserine",
        matched_source_row_refs=[child_ref],
        matched_canonical_ids=["phosphatidylserine"],
    )
    child = {
        "name": "Phosphatidylserine",
        "standard_name": "Phosphatidylserine",
        "canonical_id": "phosphatidylserine",
        "canonical_source_db": "ingredient_quality_map",
        "quantity": 100.0,
        "unit": "mg",
        "mapped": True,
        "mapped_identity": True,
        "scoreable_identity": True,
        "identity_disposition": "clean",
        "canonical_id_before": "phosphatidylserine",
        "canonical_id_after": "phosphatidylserine",
        "source_section": "active",
        "raw_source_path": child_ref,
        "raw_source_text": "Phosphatidylserine",
        "dose_class": "therapeutic_mass",
        "cleaner_row_role": "active_scorable",
        "score_eligible_by_cleaner": True,
    }
    complex_total = {
        "name": "SerinAid Phosphatidylserine complex",
        "canonical_id": "phosphatidylserine",
        "clean_identity_id": "phosphatidylserine",
        "scoring_parent_id": "phosphatidylserine",
        "evidence_canonical_id": "phosphatidylserine",
        "canonical_source_db": "ingredient_quality_map",
        "evidence_origin": "compatibility_derived",
        "evidence_type": "blend_anchor_mass",
        "scoreable": True,
        "scoreable_identity": True,
        "score_eligible_by_cleaner": True,
        "dose_class": "therapeutic_mass",
        "dose_value": 500.0,
        "dose_unit": "mg",
        "source": "activeIngredients",
        "raw_source_path": "ingredientRows[1]",
        "evidence_scope": "blend_level",
        "linked_rows": ["ingredientRows[1]"],
        "confidence": "medium",
        "reason": "identity_bearing_blend_header_mass",
    }
    return {
        "id": "213475-source-owner-regression",
        "product_name": "Phosphatidylserine 100 mg",
        "ingredient_quality_data": {
            "ingredients": [child],
            "ingredients_scorable": [child],
        },
        "product_scoring_evidence": [complex_total],
        "evidence_data": {"clinical_matches": [evidence]},
    }


def test_ps_complex_total_does_not_dilute_its_only_evidenced_active():
    product = _ps_complex_product()
    child_ref = "ingredientRows[1].nestedRows[0]"
    original = deepcopy(product)
    rows = get_scoring_ingredients(product, strict=True).rows
    by_ref = {row["raw_source_path"]: row for row in rows}
    assert set(by_ref) == {"ingredientRows[1]", child_ref}
    assert by_ref[child_ref]["quantity"] == 100.0
    assert by_ref[child_ref].get("scoring_input_kind") != "product_level_evidence"
    assert by_ref["ingredientRows[1]"]["quantity"] == 500.0
    assert by_ref["ingredientRows[1]"]["scoring_input_kind"] == "product_level_evidence"
    assert {row["canonical_id"] for row in rows} == {"phosphatidylserine"}

    without_total = deepcopy(product)
    without_total["product_scoring_evidence"] = []
    control = score_evidence(without_total, apply_primary_floor=True)
    actual = score_evidence(product, apply_primary_floor=True)
    assert product == original
    assert control["metadata"]["primary_evidence_floor"] > 0
    assert actual["metadata"]["primary_evidence_floor"] == (
        control["metadata"]["primary_evidence_floor"]
    )
    assert actual["score"] == control["score"]


@pytest.mark.parametrize("canonical,quantity", [
    ("phosphatidylserine", 500.0),
    ("phosphatidylserine", 5000.0),
    ("protein", 25000.0),
])
def test_unrelated_aggregate_still_competes_with_trace_active(canonical, quantity):
    product = _ps_complex_product()
    aggregate = product["product_scoring_evidence"][0]
    aggregate.update(
        name="Unrelated complex",
        raw_source_path="ingredientRows[2]",
        linked_rows=["ingredientRows[2]"],
        dose_value=quantity,
    )
    for field in ("canonical_id", "clean_identity_id", "scoring_parent_id",
                  "evidence_canonical_id"):
        aggregate[field] = canonical

    result = score_evidence(product, apply_primary_floor=True)

    assert result["metadata"]["primary_evidence_floor"] == 0.0


def _reverse_hierarchy_product():
    # DSLD 218600 (cloud_source_lineage_fixtures.json): the label prints
    # "Phosphatidylserine 200 mg" as the score-eligible active row at
    # ingredientRows[2] and nests its supplying "Phosphatidylserine complex"
    # 1,000 mg BENEATH it at ingredientRows[2].nestedRows[0] as a
    # blend_header_total. The supplying complex is the same physical material
    # as the active it quantifies; only structural containment proves that.
    product = _ps_complex_product()
    active = product["ingredient_quality_data"]["ingredients"][0]
    active.update(quantity=200.0, raw_source_path="ingredientRows[2]")
    total = product["product_scoring_evidence"][0]
    total.update(
        name="Phosphatidylserine complex",
        dose_value=1000.0,
        raw_source_path="ingredientRows[2].nestedRows[0]",
        linked_rows=["ingredientRows[2].nestedRows[0]"],
    )
    evidence = product["evidence_data"]["clinical_matches"][0]
    evidence["matched_source_row_refs"] = ["ingredientRows[2]"]
    return product


def test_reverse_hierarchy_supplying_complex_does_not_dilute_its_owner():
    product = _reverse_hierarchy_product()
    original = deepcopy(product)

    without_total = deepcopy(product)
    without_total["product_scoring_evidence"] = []
    control = score_evidence(without_total, apply_primary_floor=True)
    actual = score_evidence(product, apply_primary_floor=True)

    assert product == original
    assert control["metadata"]["primary_evidence_floor"] > 0
    assert actual["metadata"]["primary_evidence_floor"] == (
        control["metadata"]["primary_evidence_floor"]
    )
    assert actual["score"] == control["score"]


def test_sibling_complex_without_owner_link_still_competes():
    # DSLD 218838 (cloud_source_lineage_fixtures.json): "Phosphatidylserine
    # Complex" 500 mg (ingredientRows[2]), "Phosphatidylserine" 100 mg
    # (ingredientRows[3]) and "Phosphatidylcholine" 60 mg (ingredientRows[4])
    # are SIBLING rows with no structural owner links. The label alone does not
    # prove the complex supplies the PS row, so the complex must keep competing;
    # resolving that label is an explicit open review item, not an inference
    # this scorer may make from shared canonical identity.
    product = _ps_complex_product()
    active = product["ingredient_quality_data"]["ingredients"][0]
    active["raw_source_path"] = "ingredientRows[3]"
    sibling = {
        **active,
        "name": "Phosphatidylcholine",
        "standard_name": "Phosphatidylcholine",
        "canonical_id": "phosphatidylcholine",
        "quantity": 60.0,
        "raw_source_path": "ingredientRows[4]",
        "raw_source_text": "Phosphatidylcholine",
    }
    product["ingredient_quality_data"]["ingredients"].append(sibling)
    product["ingredient_quality_data"]["ingredients_scorable"].append(sibling)
    total = product["product_scoring_evidence"][0]
    total.update(
        name="Phosphatidylserine Complex",
        raw_source_path="ingredientRows[2]",
        linked_rows=["ingredientRows[2]"],
    )
    evidence = product["evidence_data"]["clinical_matches"][0]
    evidence["matched_source_row_refs"] = ["ingredientRows[3]"]
    original = deepcopy(product)

    result = score_evidence(product, apply_primary_floor=True)

    assert product == original
    assert result["metadata"]["primary_evidence_floor"] == 0.0


def test_owned_sibling_constituent_still_competes_inside_the_blend():
    # A heavier co-constituent nested beside the evidenced child is different
    # physical material, even though both live under the same owning total.
    # Excluding the parent total must not silence real sibling competition.
    product = _ps_complex_product()
    child = product["ingredient_quality_data"]["ingredients"][0]
    sibling = {
        **child,
        "name": "Phosphatidylcholine",
        "standard_name": "Phosphatidylcholine",
        "canonical_id": "phosphatidylcholine",
        "quantity": 300.0,
        "raw_source_path": "ingredientRows[1].nestedRows[1]",
        "raw_source_text": "Phosphatidylcholine",
    }
    product["ingredient_quality_data"]["ingredients"].append(sibling)
    product["ingredient_quality_data"]["ingredients_scorable"].append(sibling)
    original = deepcopy(product)

    result = score_evidence(product, apply_primary_floor=True)

    assert product == original
    assert result["metadata"]["primary_evidence_floor"] == 0.0


@pytest.mark.parametrize("linked_rows,floor_preserved", [
    (["ingredientRows[1]"], True),
    (["activeIngredients[0]"], False),
])
def test_synthetic_total_links_through_original_tree_not_names(
    linked_rows, floor_preserved
):
    # DSLD 213475 also emits the complex total as a synthetic activeIngredients
    # entry. Ownership of the nested child must come from the declared original
    # ingredientRows tree (linked_rows / raw_source_path), never from the
    # matching canonical_id or display name it shares with the child.
    product = _ps_complex_product()
    total = product["product_scoring_evidence"][0]
    total.update(
        raw_source_path="activeIngredients[0]",
        linked_rows=list(linked_rows),
    )
    original = deepcopy(product)

    without_total = deepcopy(product)
    without_total["product_scoring_evidence"] = []
    control = score_evidence(without_total, apply_primary_floor=True)
    actual = score_evidence(product, apply_primary_floor=True)

    assert product == original
    assert control["metadata"]["primary_evidence_floor"] > 0
    if floor_preserved:
        assert actual["metadata"]["primary_evidence_floor"] == (
            control["metadata"]["primary_evidence_floor"]
        )
    else:
        assert actual["metadata"]["primary_evidence_floor"] == 0.0
