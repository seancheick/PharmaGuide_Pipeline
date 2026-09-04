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
