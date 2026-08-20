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
    assert assessment["ul_assessment_status"] == "assessed_within_limit"
    assert assessment["readiness"] == "complete"


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
                20,
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
