"""Typed evidence, verification, and aggregate readiness contracts."""

from __future__ import annotations

import sys
from pathlib import Path


SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


def _row(
    name: str,
    canonical_id: str,
    *,
    quantity: float = 300.0,
    unit: str = "mg",
) -> dict:
    return {
        "name": name,
        "standard_name": name,
        "canonical_id": canonical_id,
        "mapped_identity": True,
        "identity_disposition": "clean",
        "source_section": "active",
        "cleaner_row_role": "active_scorable",
        "score_eligible_by_cleaner": True,
        "dose_class": "therapeutic_mass",
        "role_classification": "active_scorable",
        "scoreable_identity": True,
        "score_eligible": True,
        "quantity": quantity,
        "dose": quantity,
        "unit": unit,
        "has_dose": True,
        "raw_source_path": "ingredientRows[0]",
        "source_row_ref": "ingredientRows[0]",
    }


def _product(row: dict, *, title: str | None = None, matches: list[dict] | None = None) -> dict:
    return {
        "dsld_id": "readiness-fixture",
        "assessment_readiness_contract_version": "1.0.0",
        "product_name": title or row["name"],
        "form_factor": "capsule",
        "supplement_taxonomy": {
            "primary_type": "single_nutrient",
            "classification_contract_version": "1.2.0",
        },
        "ingredient_quality_data": {
            "ingredients_scorable": [row],
            "ingredients": [row],
            "total_active": 1,
        },
        "evidence_data": {
            "clinical_matches": matches or [],
        },
        "certification_data": {
            "verification_assessment": {
                "state": "verified_absent",
                "readiness": "complete",
                "reason_code": "registry_evaluated_no_match",
                "matched_programs": [],
            }
        },
        "rda_ul_data": {
            "collection_status": "complete",
            "dose_assessments": [
                {
                    "source_row_ref": "ingredientRows[0]",
                    "canonical_id": row["canonical_id"],
                    "material": True,
                    "conversion_status": "not_required",
                    "ul_assessment_status": "no_ul_applicable",
                    "readiness": "not_applicable",
                }
            ],
        },
    }


def _match(row: dict, effect_direction: str) -> dict:
    return {
        "id": "INGR_TEST_REVIEWED",
        "ingredient": row["name"],
        "standard_name": row["name"],
        "matched_canonical_id": row["canonical_id"],
        "study_type": "systematic_review_meta",
        "evidence_level": "ingredient-human",
        "effect_direction": effect_direction,
        "references_structured": [{"pmid": "fixture-only"}],
    }


def test_positive_human_evidence_marks_material_active_supported() -> None:
    from assessment_readiness import evaluate_assessment_readiness

    row = _row("Ashwagandha", "ashwagandha")
    result = evaluate_assessment_readiness(
        _product(row, matches=[_match(row, "positive_strong")]),
        module="generic",
    )

    assessment = result["evidence"]["ingredient_assessments"][0]
    assert assessment["material"] is True
    assert assessment["state"] == "evaluated_supported"
    assert assessment["reason_code"] == "reviewed_human_evidence_supportive"
    assert result["evidence"]["readiness"] == "complete"
    assert result["is_live_ready"] is True


def test_mixed_or_null_evidence_is_evaluated_without_becoming_supported() -> None:
    from assessment_readiness import evaluate_assessment_readiness

    row = _row("Saw Palmetto", "saw_palmetto")
    result = evaluate_assessment_readiness(
        _product(row, matches=[_match(row, "mixed")]),
        module="generic",
    )

    assessment = result["evidence"]["ingredient_assessments"][0]
    assert assessment["state"] == "evaluated_limited_or_negative"
    assert assessment["reason_code"] == "reviewed_evidence_limited_or_negative"
    assert result["evidence"]["readiness"] == "complete"
    assert result["is_live_ready"] is True


def test_unreviewed_material_botanical_is_not_ready() -> None:
    from assessment_readiness import evaluate_assessment_readiness

    row = _row("Unreviewed Botanical", "unreviewed_botanical")
    result = evaluate_assessment_readiness(_product(row), module="generic")

    assessment = result["evidence"]["ingredient_assessments"][0]
    assert assessment["state"] == "not_yet_evaluated"
    assert assessment["reason_code"] == "no_reviewed_evidence_assessment"
    assert result["evidence"]["readiness"] == "incomplete"
    assert result["is_live_ready"] is False
    assert "evidence_assessment_readiness" in result["unavailable_reasons"]


def test_typed_dose_collection_must_cover_every_material_active() -> None:
    from assessment_readiness import evaluate_assessment_readiness

    row = _row("Ashwagandha", "ashwagandha")
    product = _product(row, matches=[_match(row, "mixed")])
    product["rda_ul_data"]["dose_assessments"] = []

    result = evaluate_assessment_readiness(product, module="generic")

    assert result["dose"]["readiness"] == "incomplete"
    assert result["dose"]["material_active_count"] == 1
    assert result["dose"]["material_assessment_count"] == 0
    assert "dose_assessment_readiness" in result["unavailable_reasons"]


def test_unreviewed_adjunct_is_not_applicable_to_material_readiness() -> None:
    from assessment_readiness import evaluate_assessment_readiness

    primary = _row("Magnesium", "magnesium", quantity=300)
    adjunct = _row("Trace Botanical", "trace_botanical", quantity=1)
    adjunct["raw_source_path"] = "ingredientRows[1]"
    adjunct["source_row_ref"] = "ingredientRows[1]"
    product = _product(primary)
    product["product_name"] = "Magnesium"
    product["ingredient_quality_data"] = {
        "ingredients_scorable": [primary, adjunct],
        "ingredients": [primary, adjunct],
        "total_active": 2,
    }

    result = evaluate_assessment_readiness(product, module="generic")

    by_id = {
        item["canonical_id"]: item
        for item in result["evidence"]["ingredient_assessments"]
    }
    assert by_id["magnesium"]["state"] == "evaluated_supported"
    assert by_id["trace_botanical"]["state"] == "not_applicable"
    assert result["evidence"]["readiness"] == "complete"


def test_dri_essential_has_explicit_nutrition_authority_assessment() -> None:
    from assessment_readiness import evaluate_assessment_readiness

    row = _row("Magnesium", "magnesium")
    result = evaluate_assessment_readiness(_product(row), module="generic")

    assessment = result["evidence"]["ingredient_assessments"][0]
    assert assessment["state"] == "evaluated_supported"
    assert assessment["reason_code"] == "established_dri_nutrition_authority"
    assert assessment["evidence_ids"] == []


def test_verification_preserves_present_absent_and_not_evaluated_states() -> None:
    from assessment_readiness import evaluate_verification_assessment

    present = evaluate_verification_assessment({
        "certification_data": {
            "verification_assessment": {
                "state": "verified_present",
                "readiness": "complete",
                "reason_code": "registry_verified_product_match",
                "matched_programs": ["NSF Sport"],
            }
        }
    })
    absent = evaluate_verification_assessment({
        "certification_data": {
            "verification_assessment": {
                "state": "verified_absent",
                "readiness": "complete",
                "reason_code": "registry_evaluated_no_match",
                "matched_programs": [],
            }
        }
    })
    missing = evaluate_verification_assessment({})

    assert present["state"] == "verified_present"
    assert absent["state"] == "verified_absent"
    assert missing["state"] == "not_evaluated"
    assert missing["readiness"] == "incomplete"


def test_probiotic_native_clinical_strain_and_cfu_are_material_assessments() -> None:
    from assessment_readiness import evaluate_assessment_readiness

    row = _row("Probiotic Blend", "probiotic_blend", quantity=50, unit="billion CFU")
    product = _product(row, title="Daily Probiotic")
    product["supplement_taxonomy"] = {"primary_type": "probiotic"}
    product["probiotic_data"] = {
        "is_probiotic_product": True,
        "total_billion_count": 50,
        "total_strain_count": 1,
        "clinical_strains": [
            {
                "clinical_id": "fixture-clinical-strain",
                "name": "Fixture strain",
                "clinical_support_level": "high",
            }
        ],
    }
    product.pop("rda_ul_data")

    result = evaluate_assessment_readiness(product, module="probiotic")

    assessment = result["evidence"]["ingredient_assessments"][0]
    assert assessment["material"] is True
    assert assessment["state"] == "evaluated_supported"
    assert result["dose"]["assessment_source"] == "probiotic_total_cfu"
    assert result["is_live_ready"] is True


def test_completeness_gate_blocks_unfinished_material_evidence() -> None:
    from assessment_readiness import evaluate_assessment_readiness
    from scoring_v4.gate_completeness import evaluate_completeness_gate

    product = _product(_row("Unreviewed Botanical", "unreviewed_botanical"))
    readiness = evaluate_assessment_readiness(product, module="generic")
    result = evaluate_completeness_gate(
        product,
        module="generic",
        assessment_readiness=readiness,
    )

    assert result.is_live_eligible is False
    assert "evidence_assessment_readiness" in result.missing_fields
    assert "verification_assessment_readiness" not in result.missing_fields


def test_v4_scorer_quarantines_unfinished_material_evidence() -> None:
    from score_supplements_v4 import score_product_v4

    product = _product(_row("Unreviewed Botanical", "unreviewed_botanical"))
    result = score_product_v4(product)

    assert result["quality_score_status"] == "not_scored"
    assert result["v4_verdict"] == "NOT_SCORED"
    assert result["quality_score_v4_100"] is None
    readiness = result["v4_breakdown"]["assessment_readiness"]
    assert readiness["is_live_ready"] is False
    assert readiness["evidence"]["not_yet_evaluated_count"] == 1
    assert "evidence_assessment_readiness" in (
        result["v4_breakdown"]["completeness_gate"]["missing_fields"]
    )


def test_schema_2x_input_measures_readiness_without_changing_score_status() -> None:
    from score_supplements_v4 import score_product_v4

    product = _product(_row("Unreviewed Botanical", "unreviewed_botanical"))
    product.pop("assessment_readiness_contract_version")

    result = score_product_v4(product)

    readiness = result["v4_breakdown"]["assessment_readiness"]
    assert readiness["enforcement_mode"] == "shadow"
    assert readiness["is_live_ready"] is False
    assert result["quality_score_status"] == "scored"
