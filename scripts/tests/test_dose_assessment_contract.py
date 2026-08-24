"""Typed dose/UL assessment and fail-closed conversion regressions."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from enrich_supplements_v3 import SupplementEnricherV3  # noqa: E402


@pytest.fixture(scope="module")
def enricher() -> SupplementEnricherV3:
    return SupplementEnricherV3()


def _row(
    name: str,
    canonical_id: str,
    quantity: float,
    unit: str,
    *,
    standard_name: str | None = None,
    daily_value: float | None = None,
    matched_form: str | None = None,
) -> dict:
    return {
        "name": name,
        "raw_source_text": name,
        "raw_source_path": f"ingredientRows[{canonical_id}]",
        "standardName": standard_name or name,
        "canonical_id": canonical_id,
        "canonical_source_db": "ingredient_quality_map",
        "quantity": quantity,
        "unit": unit,
        "dailyValue": daily_value,
        "matched_form": matched_form,
    }


def _collect(enricher: SupplementEnricherV3, *rows: dict) -> dict:
    return enricher._collect_rda_ul_data(
        {"activeIngredients": list(rows), "inactiveIngredients": []},
        min_servings_per_day=1,
        max_servings_per_day=1,
    )


def test_failed_conversion_never_substitutes_raw_value(enricher) -> None:
    result = _collect(
        enricher,
        _row("Zinc", "zinc", 200, "%", daily_value=100),
    )

    exported = result["analyzed_ingredients"][0]
    assessment = result["dose_assessments"][0]

    assert exported["converted_quantity"] is None
    assert exported["converted_unit"] is None
    assert assessment["source_value"] == 200
    assert assessment["source_unit"] == "%"
    assert assessment["normalized_value"] is None
    assert assessment["normalized_unit"] is None
    assert assessment["conversion_status"] == "failed"
    assert assessment["ul_assessment_status"] == "unresolved_unit"
    assert assessment["readiness"] == "incomplete"


def test_probiotic_percentage_children_are_composition_not_distinct_exposure(
    enricher,
) -> None:
    parent = _row(
        "Probiotic Complex Blend",
        "probiotic_blend",
        4_000_000_000,
        "Organism(s)",
    )
    parent["raw_source_path"] = "ingredientRows[0]"
    child = _row(
        "Lactobacillus acidophilus",
        "lactobacillus_acidophilus",
        40,
        "%",
    )
    child.update({
        "raw_source_path": "ingredientRows[0].nestedRows[0]",
        "isNestedIngredient": True,
        "parentBlend": "Probiotic Complex Blend",
        "ingredientGroup": "Lactobacillus Acidophilus",
    })

    result = _collect(enricher, parent, child)
    by_path = {
        assessment["source_path"]: assessment
        for assessment in result["dose_assessments"]
    }

    parent_assessment = by_path["ingredientRows[0]"]
    child_assessment = by_path["ingredientRows[0].nestedRows[0]"]
    assert parent_assessment["reason_code"] == "not_ul_applicable"
    assert parent_assessment["readiness"] == "not_applicable"
    assert child_assessment["owner_row_ref"] == parent_assessment["source_row_ref"]
    assert child_assessment["source_value"] == 40
    assert child_assessment["source_unit"] == "%"
    assert child_assessment["normalized_value"] is None
    assert child_assessment["normalized_unit"] is None
    assert child_assessment["reason_code"] == (
        "composition_share_of_declared_total"
    )
    assert child_assessment["ul_assessment_status"] == "not_distinct_exposure"
    assert child_assessment["readiness"] == "not_applicable"


def test_rda_collection_uses_disclosed_nested_scorable_dose_not_parent_proxy(
    enricher,
) -> None:
    child = {
        **_row("Conjugated Linoleic Acid", "cla", 770, "mg"),
        "raw_source_path": "ingredientRows[0].nestedRows[0]",
        "isNestedIngredient": True,
        "parentBlend": "Tonalin Conjugated Linoleic Acid Complex",
        "cleaner_row_role": "active_scorable",
        "score_eligible_by_cleaner": True,
        "role_classification": "active_scorable",
        "scoreable_identity": True,
        "mapped_identity": True,
        "identity_disposition": "clean",
        "source_section": "active",
        "dose_class": "therapeutic_mass",
    }
    parent = {
        **_row(
            "Tonalin Conjugated Linoleic Acid Complex",
            "cla",
            1000,
            "mg",
        ),
        "raw_source_path": "ingredientRows[0]",
        "nestedIngredients": [child],
    }
    product = {
        "activeIngredients": [parent],
        "inactiveIngredients": [],
        "ingredient_quality_data": {
            "ingredients_scorable": [child],
            "ingredients": [child],
        },
    }

    result = enricher._collect_rda_ul_data(
        product,
        min_servings_per_day=1,
        max_servings_per_day=1,
    )

    by_path = {
        assessment["source_path"]: assessment
        for assessment in result["dose_assessments"]
    }
    assert by_path["ingredientRows[0].nestedRows[0]"]["source_value"] == 770
    assert by_path["ingredientRows[0].nestedRows[0]"]["source_unit"] == "mg"


def test_plain_parent_nutrient_amount_is_elemental_without_daily_value(
    enricher,
) -> None:
    result = _collect(
        enricher,
        _row("Zinc", "zinc", 20, "mg"),
    )

    exported = result["analyzed_ingredients"][0]
    assessment = result["dose_assessments"][0]
    assert exported["ul_gate_eligible"] is True
    assert exported["ul_exposure_basis"] == "supplement_facts_parent_nutrient_amount"
    assert assessment["source_path"] == "ingredientRows[zinc]"
    assert assessment["linked_row_refs"] == ["ingredientRows[zinc]"]
    assert assessment["ul_assessment_status"] == "assessed_within_limit"
    assert assessment["readiness"] == "complete"


def test_compound_mass_without_established_ul_is_not_applicable(enricher) -> None:
    result = _collect(
        enricher,
        _row(
            "Green Tea leaf extract",
            "green_tea_extract",
            100,
            "mg",
            standard_name="Green Tea Extract",
        ),
    )

    assessment = result["dose_assessments"][0]
    assert result["analyzed_ingredients"][0]["ul_gate_ineligible_reason"] == (
        "compound_mass_not_elemental"
    )
    assert assessment["reason_code"] == "not_ul_applicable"
    assert assessment["ul_assessment_status"] == "no_ul_applicable"
    assert assessment["readiness"] == "not_applicable"


def test_non_nutrient_name_cannot_partially_match_an_rda_nutrient(enricher) -> None:
    result = _collect(
        enricher,
        _row(
            "Calcium-D-Glucarate",
            "calcium_d_glucarate",
            1000,
            "mg",
            standard_name="Calcium D-Glucarate",
        ),
    )

    assessment = result["dose_assessments"][0]
    assert assessment["canonical_id"] == "calcium_d_glucarate"
    assert assessment["reason_code"] == "not_ul_applicable"
    assert assessment["ul_assessment_status"] == "no_ul_applicable"
    assert assessment["readiness"] == "not_applicable"


@pytest.mark.parametrize(
    "row,expected_status,expected_readiness",
    [
        (
            _row("Zinc", "zinc", 20, "mg", daily_value=182),
            "assessed_within_limit",
            "complete",
        ),
        (
            _row("Zinc", "zinc", 200, "mg", daily_value=1818),
            "assessed_over_limit",
            "complete",
        ),
        (
            _row("Vitamin B12", "vitamin_b12", 100, "mcg", daily_value=4167),
            "no_ul_applicable",
            "not_applicable",
        ),
        (
            _row("Vitamin A", "vitamin_a", 25_000, "IU", daily_value=833),
            "unresolved_form",
            "incomplete",
        ),
        (
            _row(
                "Zinc Picolinate",
                "zinc",
                200,
                "mg",
                standard_name="Zinc",
            ),
            "unresolved_compound_mass",
            "incomplete",
        ),
    ],
)
def test_ul_assessment_uses_explicit_states(
    enricher,
    row,
    expected_status,
    expected_readiness,
) -> None:
    result = _collect(enricher, row)

    assessment = result["dose_assessments"][0]
    assert assessment["ul_assessment_status"] == expected_status
    assert assessment["readiness"] == expected_readiness


def test_one_calculation_exception_does_not_discard_other_rows(
    enricher,
    monkeypatch,
) -> None:
    original = enricher.rda_calculator.compute_nutrient_adequacy

    def flaky(*args, **kwargs):
        nutrient = kwargs.get("nutrient") or (args[0] if args else "")
        if "zinc" in str(nutrient).lower():
            raise RuntimeError("synthetic zinc failure")
        return original(*args, **kwargs)

    monkeypatch.setattr(enricher.rda_calculator, "compute_nutrient_adequacy", flaky)
    result = _collect(
        enricher,
        _row("Zinc", "zinc", 20, "mg", daily_value=182),
        _row("Vitamin C", "vitamin_c", 90, "mg", daily_value=100),
    )

    by_canonical = {
        item["canonical_id"]: item for item in result["dose_assessments"]
    }
    assert result["collection_status"] == "complete_with_row_errors"
    assert by_canonical["zinc"]["ul_assessment_status"] == "assessment_error"
    assert by_canonical["zinc"]["readiness"] == "incomplete"
    assert by_canonical["vitamin_c"]["ul_assessment_status"] == "assessed_within_limit"
    assert by_canonical["vitamin_c"]["readiness"] == "complete"


def test_conversion_exception_cannot_become_same_unit_passthrough(
    enricher,
    monkeypatch,
) -> None:
    original = enricher.unit_converter.convert_nutrient

    def flaky(*args, **kwargs):
        nutrient = kwargs.get("nutrient") or (args[0] if args else "")
        if "zinc" in str(nutrient).lower():
            raise RuntimeError("synthetic zinc conversion failure")
        return original(*args, **kwargs)

    monkeypatch.setattr(enricher.unit_converter, "convert_nutrient", flaky)
    result = _collect(
        enricher,
        _row("Zinc", "zinc", 20, "mg", daily_value=182),
        _row("Vitamin C", "vitamin_c", 90, "mg", daily_value=100),
    )

    by_canonical = {
        item["canonical_id"]: item for item in result["dose_assessments"]
    }
    assert result["collection_status"] == "complete_with_row_errors"
    assert by_canonical["zinc"]["normalized_value"] is None
    assert by_canonical["zinc"]["normalized_unit"] is None
    assert by_canonical["zinc"]["conversion_status"] == "failed"
    assert by_canonical["zinc"]["ul_assessment_status"] == "unresolved_unit"
    assert by_canonical["zinc"]["readiness"] == "incomplete"
    assert by_canonical["vitamin_c"]["readiness"] == "complete"


def test_unexpected_collection_failure_never_asserts_within_limit(
    enricher,
    monkeypatch,
) -> None:
    def broken_exposure_basis(*args, **kwargs):
        raise RuntimeError("synthetic collection failure")

    monkeypatch.setattr(enricher, "_ul_exposure_basis", broken_exposure_basis)
    result = _collect(
        enricher,
        _row("Zinc", "zinc", 20, "mg", daily_value=182),
    )

    assert result["collection_status"] == "failed"
    assert result["has_over_ul"] is None
    assert result["collection_error"] == "synthetic collection failure"
    assert result["dose_assessment_errors"][-1]["reason"] == "dose_collection_exception"


def test_disabled_collection_is_explicitly_incomplete(enricher) -> None:
    result = enricher._empty_rda_ul_payload("disabled_by_config")

    assert result["collection_status"] == "failed"
    assert result["has_over_ul"] is None
    assert result["dose_assessments"] == []
    assert result["dose_assessment_errors"] == [
        {"reason": "disabled_by_config"}
    ]
