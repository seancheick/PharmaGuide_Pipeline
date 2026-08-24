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


def test_unreviewed_material_botanical_is_measured_but_does_not_gate() -> None:
    from assessment_readiness import evaluate_assessment_readiness

    row = _row("Unreviewed Botanical", "unreviewed_botanical")
    result = evaluate_assessment_readiness(_product(row), module="generic")

    assessment = result["evidence"]["ingredient_assessments"][0]
    assert assessment["state"] == "not_yet_evaluated"
    assert assessment["reason_code"] == "no_reviewed_evidence_assessment"
    assert result["evidence"]["readiness"] == "incomplete"
    # Evidence is measured in shadow: an uncurated ingredient is a gap in our
    # curation, not a defect in the product, so it must not delist it.
    assert result["is_live_ready"] is True
    assert "evidence" in result["shadow_incomplete_dimensions"]
    assert "evidence_assessment_readiness" not in result["unavailable_reasons"]


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


def test_mapped_active_without_declared_dose_is_a_dose_not_identity_failure() -> None:
    from assessment_readiness import evaluate_assessment_readiness

    row = _row("Vitamin B12", "vitamin_b12", quantity=0, unit="NP")
    row.update({"dose": 0, "has_dose": False})
    product = _product(row)
    product["ingredient_quality_data"].update({
        "ingredients_scorable": [],
        "ingredients": [row],
        "total_active": 1,
    })
    product["rda_ul_data"] = {
        "collection_status": "complete",
        "dose_assessments": [],
    }

    result = evaluate_assessment_readiness(product, module="generic")

    assert result["identity"]["readiness"] == "complete"
    assert result["identity"]["reason_code"] == "mapped_source_actives"
    assert result["dose"]["readiness"] == "incomplete"
    assert result["dose"]["reason_code"] == "no_scoreable_active_dose"
    assert result["unavailable_reasons"] == ["dose_assessment_readiness"]


def test_product_projection_reuses_typed_source_row_dose_assessment() -> None:
    """A scoring projection is not a second physical exposure."""
    from assessment_readiness import evaluate_assessment_readiness

    row = _row("Fish Oil", "fish_oil", quantity=1200.0)
    product = _product(row, title="Fish Oil 1200 mg")
    product["supplement_taxonomy"] = {"primary_type": "omega_3"}
    product["product_scoring_evidence"] = [
        {
            "evidence_type": "omega_epa_dha_aggregate",
            "scoreable": True,
            "scoreable_identity": True,
            "score_eligible_by_cleaner": True,
            "dose_class": "therapeutic_mass",
            "dose_value": 1200.0,
            "dose_unit": "mg",
            "source": "active",
            "raw_source_path": "ingredientRows[0]",
            "evidence_scope": "row_level",
            "linked_rows": ["ingredientRows[0]"],
            "confidence": "low",
            "reason": "omega_epa_dha_aggregate_from_label_row",
            "name": "Fish Oil",
            "canonical_id": "epa_dha",
            "evidence_canonical_id": "epa_dha",
            "canonical_source_db": "ingredient_quality_map",
            "evidence_origin": "native_enrichment",
            "source_section": "product",
        }
    ]
    product["rda_ul_data"]["dose_assessments"][0].update({
        "source_path": "ingredientRows[0]",
        "dose_class": "therapeutic_mass",
        "source_value": 1200.0,
        "source_unit": "mg",
    })

    result = evaluate_assessment_readiness(product, module="omega")

    assert result["evidence"]["material_active_count"] == 1
    assert result["dose"]["material_exposure_count"] == 1
    assert result["dose"]["material_assessment_count"] == 1
    assert result["dose"]["assessment_source"] == "typed_dose_assessments"
    assert result["dose"]["readiness"] == "complete"


def test_mapped_product_evidence_is_a_score_eligible_coverage_exposure() -> None:
    from assessment_readiness import evaluate_assessment_readiness

    row = _row("Quercetin", "quercetin")
    product = _product(row, matches=[_match(row, "mixed")])
    product["ingredient_quality_data"] = {
        "ingredients_scorable": [],
        "ingredients": [],
        "total_active": 0,
    }
    product["product_scoring_evidence"] = [
        {
            "evidence_type": "blend_anchor_mass",
            "scoreable": True,
            "scoreable_identity": True,
            "score_eligible_by_cleaner": True,
            "mapped": True,
            "dose_class": "therapeutic_mass",
            "dose_value": 300.0,
            "dose_unit": "mg",
            "source": "blend_total",
            "raw_source_path": "ingredientRows[0]",
            "evidence_scope": "blend_level",
            "linked_rows": ["ingredientRows[0]"],
            "confidence": "high",
            "reason": "identity_bearing_blend_total",
            "name": "Quercetin",
            "canonical_id": "quercetin",
            "clean_identity_id": "quercetin",
            "scoring_parent_id": "quercetin",
            "evidence_canonical_id": "quercetin",
            "canonical_source_db": "ingredient_quality_map",
            "evidence_origin": "native_enrichment",
            "source_section": "product",
        }
    ]
    product["rda_ul_data"]["dose_assessments"][0].update({
        "source_path": "ingredientRows[0]",
        "dose_class": "therapeutic_mass",
        "source_value": 300.0,
        "source_unit": "mg",
    })

    result = evaluate_assessment_readiness(product, module="generic")

    assert result["identity"]["mapped_count"] == 1
    assert result["identity"]["mapped_coverage"] == 1.0
    assert result["identity"]["mapped_product_evidence_count"] == 1
    assert result["identity"]["readiness"] == "complete"
    assert result["is_live_ready"] is True


def test_fresh_contract_never_uses_legacy_dose_migration_inference() -> None:
    from assessment_readiness import evaluate_assessment_readiness

    row = _row("Ashwagandha", "ashwagandha")
    product = _product(row, matches=[_match(row, "mixed")])
    product["rda_ul_data"] = {
        "collection_status": "complete",
        "dose_assessments": [],
        "adequacy_results": [],
        "safety_flags": [],
    }

    result = evaluate_assessment_readiness(product, module="generic")

    assert result["dose"]["readiness"] == "incomplete"
    assert result["dose"].get("migration_inference") is not True


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


def test_probiotic_native_clinical_strain_and_typed_dose_are_material_assessments() -> None:
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
    result = evaluate_assessment_readiness(product, module="probiotic")

    assessment = result["evidence"]["ingredient_assessments"][0]
    assert assessment["material"] is True
    assert assessment["state"] == "evaluated_supported"
    assert result["dose"]["assessment_source"] == "typed_dose_assessments"
    assert result["is_live_ready"] is True


def test_completeness_gate_does_not_block_on_shadow_evidence() -> None:
    from assessment_readiness import evaluate_assessment_readiness
    from scoring_v4.gate_completeness import evaluate_completeness_gate

    product = _product(_row("Unreviewed Botanical", "unreviewed_botanical"))
    readiness = evaluate_assessment_readiness(product, module="generic")
    result = evaluate_completeness_gate(
        product,
        module="generic",
        assessment_readiness=readiness,
    )

    assert result.is_live_eligible is True
    assert "evidence_assessment_readiness" not in result.missing_fields
    assert "verification_assessment_readiness" not in result.missing_fields


def test_v4_scorer_scores_and_records_unfinished_material_evidence() -> None:
    """The backlog is reported on the artifact, not paid for by delisting."""
    from score_supplements_v4 import score_product_v4

    product = _product(_row("Unreviewed Botanical", "unreviewed_botanical"))
    result = score_product_v4(product)

    assert result["quality_score_status"] == "scored"
    assert result["quality_score_v4_100"] is not None
    readiness = result["v4_breakdown"]["assessment_readiness"]
    assert readiness["is_live_ready"] is True
    assert readiness["evidence"]["not_yet_evaluated_count"] == 1
    assert readiness["shadow_incomplete_dimensions"] == ["evidence"]
    assert "evidence_assessment_readiness" not in (
        result["v4_breakdown"]["completeness_gate"]["missing_fields"]
    )


def test_schema_2x_input_measures_readiness_without_changing_score_status() -> None:
    from score_supplements_v4 import score_product_v4

    product = _product(_row("Unreviewed Botanical", "unreviewed_botanical"))
    product.pop("assessment_readiness_contract_version")

    result = score_product_v4(product)

    readiness = result["v4_breakdown"]["assessment_readiness"]
    assert readiness["enforcement_mode"] == "shadow"
    assert readiness["evidence"]["readiness"] == "incomplete"
    assert result["quality_score_status"] == "scored"


def test_real_label_aggregate_identity_keeps_its_individual_evidence_question() -> None:
    """Canonical vocabulary alone cannot turn a source label row synthetic."""
    from assessment_readiness import evaluate_assessment_readiness

    row = _row("Fiber", "fiber", quantity=25.0)
    result = evaluate_assessment_readiness(_product(row), module="fiber_digestive")

    evidence = result["evidence"]
    assessment = evidence["ingredient_assessments"][0]
    assert assessment["scoring_input_kind"] != "product_level_evidence"
    assert assessment["evidence_applicability"] == "individual_ingredient"
    assert assessment["state"] == "not_yet_evaluated"
    assert assessment["reason_code"] == "no_reviewed_evidence_assessment"
    assert evidence["not_yet_evaluated_count"] == 1
    assert evidence["readiness"] == "incomplete"


def test_product_level_projection_carries_no_individual_evidence_question() -> None:
    """Pipeline projections are module-owned regardless of canonical identity."""
    from assessment_readiness import evaluate_assessment_readiness

    row = _row("Quercetin Blend Total", "quercetin")
    product = _product(row)
    product["ingredient_quality_data"] = {
        "ingredients_scorable": [],
        "ingredients": [],
        "total_active": 0,
    }
    product["product_scoring_evidence"] = [
        {
            **row,
            "scoreable": True,
            "scoring_input_kind": "product_level_evidence",
            "evidence_type": "blend_anchor_mass",
            "evidence_scope": "blend_level",
            "source": "blend_total",
            "source_section": "product",
            "dose_value": row["quantity"],
            "dose_unit": row["unit"],
            "linked_rows": [row["source_row_ref"]],
            "confidence": "high",
            "reason": "identity_bearing_blend_total",
            "clean_identity_id": "quercetin",
            "scoring_parent_id": "quercetin",
            "evidence_canonical_id": "quercetin",
            "canonical_source_db": "ingredient_quality_map",
            "evidence_origin": "native_enrichment",
        }
    ]

    evidence = evaluate_assessment_readiness(product, module="generic")["evidence"]

    assessment = evidence["ingredient_assessments"][0]
    assert assessment["scoring_input_kind"] == "product_level_evidence"
    assert assessment["evidence_applicability"] == "module_aggregate"
    assert assessment["state"] == "not_applicable"
    assert assessment["reason_code"] == "module_scoped_product_projection"
    assert evidence["not_yet_evaluated_count"] == 0
    assert evidence["readiness"] == "complete"


def test_uncurated_individual_ingredient_still_reports_incomplete() -> None:
    """The aggregate carve-out must not swallow genuine curation gaps."""
    from assessment_readiness import evaluate_assessment_readiness

    row = _row("Lycopene", "lycopene")
    evidence = evaluate_assessment_readiness(_product(row), module="generic")["evidence"]

    assessment = evidence["ingredient_assessments"][0]
    assert assessment["evidence_applicability"] == "individual_ingredient"
    assert assessment["state"] == "not_yet_evaluated"
    assert evidence["not_yet_evaluated_count"] == 1
    assert evidence["readiness"] == "incomplete"


def test_dri_nutrient_is_authority_assessed_not_individually_curated() -> None:
    from assessment_readiness import evaluate_assessment_readiness

    row = _row("Zinc", "zinc", quantity=15.0)
    evidence = evaluate_assessment_readiness(_product(row), module="generic")["evidence"]

    assessment = evidence["ingredient_assessments"][0]
    assert assessment["evidence_applicability"] == "nutrition_authority"
    assert assessment["state"] == "evaluated_supported"
    assert evidence["readiness"] == "complete"


def test_applicability_counts_cover_every_assessment() -> None:
    from assessment_readiness import evaluate_assessment_readiness

    row = _row("Lycopene", "lycopene")
    evidence = evaluate_assessment_readiness(_product(row), module="generic")["evidence"]

    assessments = evidence["ingredient_assessments"]
    assert sum(evidence["applicability_counts"].values()) == len(assessments)
    assert evidence["individual_assessment_count"] == evidence[
        "applicability_counts"
    ].get("individual_ingredient", 0)


def test_evidence_is_measured_but_does_not_gate_live_eligibility() -> None:
    """Evidence readiness is shadow: an uncurated ingredient is not a defect.

    Enforcing it would quarantine on curation backlog rather than on anything
    true about the product, so it is reported and excluded from the gate.
    """
    from assessment_readiness import (
        ENFORCED_READINESS_DIMENSIONS,
        evaluate_assessment_readiness,
    )

    assert "evidence" not in ENFORCED_READINESS_DIMENSIONS
    assert ENFORCED_READINESS_DIMENSIONS == {
        "identity",
        "dose",
        "verification",
        "route",
    }

    row = _row("Lycopene", "lycopene")
    result = evaluate_assessment_readiness(_product(row), module="generic")

    assert result["evidence"]["readiness"] == "incomplete"
    assert result["shadow_incomplete_dimensions"] == ["evidence"]
    assert "evidence_assessment_readiness" not in result["unavailable_reasons"]
    assert result["is_live_ready"] is True
    assert result["enforced_dimensions"] == sorted(ENFORCED_READINESS_DIMENSIONS)


def test_unresolved_protein_product_intent_blocks_route_readiness() -> None:
    from assessment_readiness import evaluate_assessment_readiness

    row = _row("Calcium", "calcium", quantity=200.0)
    product = _product(row, title="Keto Protein Chocolate")
    result = evaluate_assessment_readiness(product, module="generic")

    assert result["route"]["readiness"] == "incomplete"
    assert "protein_identity_or_mass_missing" in result["route"]["reason_codes"]
    assert "route_assessment_readiness" in result["unavailable_reasons"]
