"""Typed evidence, verification, and aggregate readiness contracts."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


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


def _zero_scorable_product(*statement_notes: str) -> dict:
    row = _row("Label Ingredient", "label_ingredient", quantity=0, unit="NP")
    row.update({
        "scoreable_identity": False,
        "score_eligible": False,
        "has_dose": False,
        "score_exclusion_reason": "recognized_non_scorable",
    })
    product = _product(row)
    product["ingredient_quality_data"]["ingredients_scorable"] = []
    product["statements"] = [
        {"type": "fixture", "notes": notes}
        for notes in statement_notes
    ]
    return product


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


@pytest.mark.parametrize("typed_readiness", ["incomplete", "not_applicable"])
def test_failed_dose_conversion_cannot_hide_as_evidence_adjunct(typed_readiness) -> None:
    from assessment_readiness import evaluate_assessment_readiness
    from scoring_v4.scored_artifact import build_scored_artifact

    primary = _row("Calcium", "calcium", quantity=500)
    unconverted = _row("Vitamin A", "vitamin_a", quantity=900, unit="mg RAE")
    unconverted.update(raw_source_path="ingredientRows[1]", source_row_ref="ingredientRows[1]")
    product = _product(primary, title="Calcium Formula")
    product["ingredient_quality_data"].update(
        ingredients=[primary, unconverted], ingredients_scorable=[primary, unconverted], total_active=2,
    )
    product["rda_ul_data"]["dose_assessments"].append({
        "source_row_ref": "ingredientRows[1]", "canonical_id": "vitamin_a",
        "material": True, "source_value": 900, "source_unit": "mg RAE",
        "normalized_value": None, "conversion_status": "failed",
        "ul_assessment_status": "no_ul_applicable", "readiness": typed_readiness,
    })
    result = evaluate_assessment_readiness(product, module="generic")
    assert result["dose"]["readiness"] == "incomplete"
    assert result["dose"]["incomplete_source_row_refs"] == ["ingredientRows[1]"]
    assert result["is_live_ready"] is False
    assert build_scored_artifact(product)["quality_score_status"] == "not_scored"


def test_ready_same_source_dose_can_resolve_an_incomplete_alternative() -> None:
    from assessment_readiness import evaluate_assessment_readiness

    product = _product(_row("Calcium", "calcium", quantity=500))
    product["rda_ul_data"]["dose_assessments"].append({
        "source_row_ref": "ingredientRows[0]", "canonical_id": "calcium",
        "material": True, "source_value": 50, "source_unit": "NP",
        "normalized_value": None, "conversion_status": "failed",
        "ul_assessment_status": "unresolved_unit", "readiness": "incomplete",
        "reason_code": "amount_not_declared",
    })
    # The initial assessment proves the same row's declared mg dose. A second
    # representation without a unit must not invalidate that owned proof.
    result = evaluate_assessment_readiness(product, module="generic")
    assert result["dose"]["readiness"] == "complete"
    assert result["is_live_ready"] is True


def test_sports_readiness_requires_a_sports_relevant_identity() -> None:
    """Mapped minerals must not make a sports-routed product identity-ready."""
    from assessment_readiness import evaluate_assessment_readiness

    row = _row("Calcium", "calcium")
    product = _product(row, title="Keto Protein")
    product["supplement_taxonomy"] = {
        "primary_type": "sports_nutrition",
        "classification_contract_version": "1.2.0",
    }

    result = evaluate_assessment_readiness(product, module="sports")

    assert result["identity"]["readiness"] == "incomplete"
    assert result["identity"]["reason_code"] == "missing_sports_relevant_identity"
    assert result["is_live_ready"] is False
    assert "identity_assessment_readiness" in result["unavailable_reasons"]


def test_explicit_non_consumer_label_intent_is_typed_qa_disposition() -> None:
    from assessment_readiness import evaluate_assessment_readiness

    cases = {
        "For external use only. Not intended for consumption.": "external_use_only",
        (
            "Not intended for individual use and should be used by qualified "
            "professionals only."
        ): "professional_formulation_material",
        "Suggested use: As a sweetener, use 4 g or to desired taste.": "culinary_sweetener",
        "For cooking, baking, or sauteing up to 350 degrees F.": "culinary_food",
        "This product is not meant to be taken in large doses. Use as required in the formulation.": "formulation_excipient",
    }

    for statement, expected_reason in cases.items():
        result = evaluate_assessment_readiness(
            _zero_scorable_product(statement),
            module="generic",
        )

        assert result["catalog_disposition"] == {
            "disposition": "intentional_non_scoreable",
            "reason_code": expected_reason,
            "evidence_paths": ["statements[0].notes"],
        }
        assert result["identity"]["readiness"] == "not_applicable"
        assert result["identity"]["reason_code"] == expected_reason
        assert result["is_live_ready"] is False
        assert result["unavailable_reasons"] == [
            "intentional_non_scoreable_product"
        ]


def test_emergency_use_only_product_overrides_score_candidate_disposition() -> None:
    """Emergency countermeasures must not receive routine supplement scores."""
    from assessment_readiness import evaluate_assessment_readiness

    row = _row("Potassium Iodide", "iodine", quantity=130, unit="mg")
    product = _product(row, title="Potassium Iodide Tablets 130 mg")
    product["statements"] = [{
        "type": "Precautions re: All Other",
        "notes": (
            "Potassium Iodide should only be taken in emergency situations "
            "when directed by your physician, state, or local health authorities."
        ),
    }]
    product["rda_ul_data"]["special_use_flags"] = [{
        "code": "POTASSIUM_IODIDE_EMERGENCY_USE_ONLY",
        "source": "FDA",
        "source_url": (
            "https://www.fda.gov/drugs/bioterrorism-and-drug-preparedness/"
            "frequently-asked-questions-potassium-iodide-ki"
        ),
    }]

    result = evaluate_assessment_readiness(product, module="generic")

    assert result["catalog_disposition"] == {
        "disposition": "intentional_non_scoreable",
        "reason_code": "emergency_use_only",
        "evidence_paths": ["statements[0].notes"],
    }
    assert result["is_live_ready"] is False
    assert "intentional_non_scoreable_product" in result["unavailable_reasons"]

    product["rda_ul_data"]["special_use_flags"] = []
    without_verified_policy = evaluate_assessment_readiness(product, module="generic")
    assert without_verified_policy["catalog_disposition"]["disposition"] == (
        "score_candidate"
    )


def test_missing_active_without_explicit_non_scoreable_intent_stays_remediation() -> None:
    from assessment_readiness import evaluate_assessment_readiness

    result = evaluate_assessment_readiness(
        _zero_scorable_product("Contains 300 mg omega-3s including EPA and DHA."),
        module="omega",
    )

    assert result["catalog_disposition"]["disposition"] == "requires_remediation"
    assert result["catalog_disposition"]["reason_code"] == "no_score_eligible_active_rows"
    assert result["identity"]["readiness"] == "incomplete"
    assert result["identity"]["reason_code"] == "no_score_eligible_active_rows"
    assert "identity_assessment_readiness" in result["unavailable_reasons"]


def test_mapped_omega_identity_without_child_dose_blocks_on_dose_not_identity() -> None:
    """A known EPA label row remains an identity even when its dose is absent."""
    from assessment_readiness import evaluate_assessment_readiness

    row = _row("Eicosapentaenoic Acid", "epa", quantity=0, unit="unspecified")
    row.update({
        "scoreable_identity": False,
        "score_eligible": False,
        "has_dose": False,
        "role_classification": "recognized_non_scorable",
        "score_exclusion_reason": "recognized_non_scorable",
        "identity_decision_reason": "no_dose_evidence",
    })
    product = _product(row, title="Fish Oil")
    product["supplement_taxonomy"] = {
        "primary_type": "omega_3_fatty_acids",
        "classification_contract_version": "1.2.0",
    }
    product["ingredient_quality_data"]["ingredients_scorable"] = []
    product["rda_ul_data"] = {
        "collection_status": "complete",
        "dose_assessments": [],
    }

    result = evaluate_assessment_readiness(product, module="omega")

    assert result["identity"]["readiness"] == "complete"
    assert result["identity"]["reason_code"] == "mapped_source_actives"
    assert result["dose"]["readiness"] == "incomplete"
    assert result["dose"]["reason_code"] == "no_scoreable_active_dose"
    assert result["unavailable_reasons"] == ["dose_assessment_readiness"]


def test_true_carrier_oil_does_not_become_a_source_active() -> None:
    """recognized_non_scorable carriers stay outside the assessment denominator."""
    from assessment_readiness import evaluate_assessment_readiness

    product = _zero_scorable_product()
    row = product["ingredient_quality_data"]["ingredients"][0]
    row["canonical_id"] = "PII_EXTRA_VIRGIN_OLIVE_OIL"
    row["identity_decision_reason"] = "carrier_oil"

    result = evaluate_assessment_readiness(product, module="generic")

    assert result["identity"]["source_score_eligible_active_count"] == 0
    assert result["identity"]["readiness"] == "incomplete"


@pytest.mark.parametrize(
    "title",
    [
        "Maltodextrin Powder",
        "Maltodextrin Powder 30 g",
        "Dextrose Powder 20 g",
    ],
)
def test_standalone_carbohydrate_powder_is_typed_qa_disposition(title: str) -> None:
    from assessment_readiness import evaluate_assessment_readiness

    product = _zero_scorable_product(
        "Suggested use: As a dietary supplement, mix with water or juice."
    )
    product["product_name"] = title
    product["fullName"] = title

    result = evaluate_assessment_readiness(product, module="generic")

    assert result["catalog_disposition"] == {
        "disposition": "intentional_non_scoreable",
        "reason_code": "standalone_carbohydrate_powder",
        "evidence_paths": ["product_name"],
    }
    assert result["unavailable_reasons"] == [
        "intentional_non_scoreable_product"
    ]


def test_mixed_carbohydrate_formula_stays_in_remediation() -> None:
    from assessment_readiness import evaluate_assessment_readiness

    product = _zero_scorable_product()
    product["product_name"] = "Dextrose + Creatine Powder"
    product["fullName"] = "Dextrose + Creatine Powder"

    result = evaluate_assessment_readiness(product, module="sports")

    assert result["catalog_disposition"]["disposition"] == (
        "requires_remediation"
    )
    assert result["catalog_disposition"]["reason_code"] == (
        "no_score_eligible_active_rows"
    )


def test_explicit_nutrition_beverage_is_typed_qa_disposition() -> None:
    from assessment_readiness import evaluate_assessment_readiness

    product = _zero_scorable_product(
        "Directions: Drink eight ounces per day as a nutritious drink."
    )
    product["product_name"] = "Aloe Vera Juice Natural Wild Berry Flavor"
    product["fullName"] = product["product_name"]

    result = evaluate_assessment_readiness(product, module="generic")

    assert result["catalog_disposition"] == {
        "disposition": "intentional_non_scoreable",
        "reason_code": "nutrition_beverage",
        "evidence_paths": ["statements[0].notes"],
    }


def test_generic_drink_direction_stays_in_remediation() -> None:
    from assessment_readiness import evaluate_assessment_readiness

    result = evaluate_assessment_readiness(
        _zero_scorable_product("Drink eight ounces daily."),
        module="generic",
    )

    assert result["catalog_disposition"]["disposition"] == (
        "requires_remediation"
    )


def test_intentional_non_scoreable_product_gets_actionable_not_scored_reason() -> None:
    from score_supplements_v4 import score_product_v4

    result = score_product_v4(
        _zero_scorable_product(
            "For external use only. Not intended for consumption."
        )
    )

    assert result["quality_score_status"] == "not_scored"
    assert result["score_unavailable_reason"] == "intentional_non_scoreable_product"
    completeness = result["v4_breakdown"]["completeness_gate"]
    assert completeness["missing_fields"] == ["intentional_non_scoreable_product"]


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


def test_non_material_source_row_reuses_its_typed_disclosed_dose() -> None:
    from assessment_readiness import _dose_readiness

    row = _row("Niacin", "vitamin_b3_niacin", quantity=500, unit="mg NE")
    product = _product(row)
    product["rda_ul_data"]["dose_assessments"][0].update({
        "source_path": "ingredientRows[0]",
        "dose_class": "therapeutic_mass",
        "source_value": 500,
        "source_unit": "mg NE",
        "readiness": "complete",
    })

    result = _dose_readiness(
        product,
        [{"material": False}],
        module="generic",
    )

    assert result["readiness"] == "complete"
    assert result["material_exposure_count"] == 1
    assert result["material_assessment_count"] == 1
    assert result["assessment_source"] == "typed_source_dose_assessments"


def test_non_material_enzyme_activity_reuses_typed_activity_dose() -> None:
    from assessment_readiness import _dose_readiness

    row = _row(
        "Alpha-Galactosidase",
        "digestive_enzymes",
        quantity=0,
        unit="NP",
    )
    row.update({
        "dose": 0,
        "has_dose": False,
        "dose_class": "enzyme_activity",
        "activity_quantity": 300,
        "activity_unit": "GALU",
    })
    product = _product(row)
    product["rda_ul_data"]["dose_assessments"] = [{
        "source_row_ref": "ingredientRows[0]",
        "source_path": "ingredientRows[0]",
        "canonical_id": "digestive_enzymes",
        "dose_class": "enzyme_activity",
        "source_value": 300,
        "source_unit": "GALU",
        "ul_assessment_status": "no_ul_applicable",
        "readiness": "not_applicable",
    }]

    result = _dose_readiness(
        product,
        [{"material": False}],
        module="fiber_digestive",
    )

    assert result["readiness"] == "complete"
    assert result["material_exposure_count"] == 1
    assert result["material_assessment_count"] == 1


def test_source_identity_diagnostic_excludes_non_scoring_nutrition_rows() -> None:
    from assessment_readiness import evaluate_assessment_readiness

    active = _row("Magnesium", "magnesium")
    nutrition = _row("Sodium", "sodium", quantity=25, unit="mg")
    nutrition.update({
        "raw_source_path": "ingredientRows[1]",
        "source_row_ref": "ingredientRows[1]",
        "mapped_identity": False,
        "score_exclusion_reason": "excluded_nutrition_fact",
    })
    product = _product(active)
    product["ingredient_quality_data"]["ingredients"] = [active, nutrition]

    result = evaluate_assessment_readiness(product, module="generic")

    assert result["identity"]["source_score_eligible_active_count"] == 1
    assert result["identity"]["source_unmapped_count"] == 0
    assert result["identity"]["source_mapped_coverage"] == 1.0


@pytest.mark.parametrize("collection", ["ingredients", "ingredients_skipped", "both"])
@pytest.mark.parametrize("exclusion", ["quality_map_match", ""])
def test_source_identity_counts_required_conflict_once(
    collection: str, exclusion: str,
) -> None:
    from assessment_readiness import evaluate_assessment_readiness

    active = _row("Magnesium", "magnesium")
    conflict = _row("Yeast preparation", "brewers_yeast")
    conflict.update({
        "raw_source_path": "ingredientRows[1]",
        "source_row_ref": "ingredientRows[1]",
        "identity_disposition": "identity_conflict",
        "scoreable_identity": False,
        "score_exclusion_reason": exclusion,
    })
    product = _product(active)
    product["activeIngredients"] = [active, conflict]
    quality = product["ingredient_quality_data"]
    if collection in {"ingredients", "both"}:
        quality["ingredients"].append(conflict)
    if collection in {"ingredients_skipped", "both"}:
        quality["ingredients_skipped"] = [conflict]

    identity = evaluate_assessment_readiness(product, module="generic")["identity"]

    assert identity["mapped_coverage"] == 0.5
    assert identity["source_score_eligible_active_count"] == 2
    assert identity["source_mapped_count"] == 1
    assert identity["source_unmapped_count"] == 1
    assert identity["source_mapped_coverage"] == 0.5
    assert identity["readiness"] == "incomplete"


def test_source_identity_respects_explicit_cleaner_exclusion_over_legacy_role() -> None:
    from assessment_readiness import evaluate_assessment_readiness

    active = _row("Magnesium", "magnesium")
    excluded = _row("Excluded row", "excluded")
    excluded.update({
        "raw_source_path": "ingredientRows[1]",
        "source_row_ref": "ingredientRows[1]",
        "identity_disposition": "identity_conflict",
        "score_eligible_by_cleaner": False,
    })
    product = _product(active)
    product["activeIngredients"] = [active, excluded]
    product["ingredient_quality_data"]["ingredients"].append(excluded)

    identity = evaluate_assessment_readiness(product, module="generic")["identity"]

    assert identity["source_score_eligible_active_count"] == 1
    assert identity["source_mapped_coverage"] == 1.0


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


def test_declared_total_cfu_satisfies_its_own_probiotic_dose_requirement() -> None:
    """CFU is module-owned dose evidence, not an RDA/UL assessment."""
    from assessment_readiness import _dose_readiness

    product = {
        "assessment_readiness_contract_version": "1.0.0",
        "probiotic_data": {
            "total_cfu": 50_000_000_000,
            "cfu_unit": "CFU",
        },
        "rda_ul_data": {
            "collection_status": "complete",
            "dose_assessments": [
                {
                    "source_row_ref": "ingredientRows[0]",
                    "dose_class": "therapeutic_mass",
                    "source_value": 550.0,
                    "source_unit": "mg",
                    "readiness": "not_applicable",
                }
            ],
        },
    }
    evidence = [
        {
            "source_row_ref": "ingredientRows[0]",
            "material": True,
            "source_value": 550.0,
            "source_unit": "mg",
            "dose_class": "therapeutic_mass",
        },
        {
            "source_row_ref": "statements",
            "material": True,
            "source_value": 50_000_000_000,
            "source_unit": "CFU",
            "dose_class": "probiotic_cfu",
            "evidence_type": "probiotic_cfu",
        },
    ]

    result = _dose_readiness(product, evidence, module="probiotic")

    assert result["readiness"] == "complete"
    assert result["material_exposure_count"] == 2
    assert result["material_assessment_count"] == 2
    assert result["assessment_source"] == (
        "typed_dose_assessments_and_probiotic_total_cfu"
    )


def test_claimed_cfu_that_disagrees_with_declared_total_stays_incomplete() -> None:
    """A caller-supplied CFU row cannot manufacture dose readiness."""
    from assessment_readiness import _dose_readiness

    product = {
        "assessment_readiness_contract_version": "1.0.0",
        "probiotic_data": {"total_cfu": 10_000_000_000},
        "rda_ul_data": {
            "collection_status": "complete",
            "dose_assessments": [],
        },
    }
    evidence = [
        {
            "source_row_ref": "statements",
            "material": True,
            "source_value": 50_000_000_000,
            "source_unit": "CFU",
            "dose_class": "probiotic_cfu",
            "evidence_type": "probiotic_cfu",
        }
    ]

    result = _dose_readiness(product, evidence, module="probiotic")

    assert result["readiness"] == "incomplete"
    assert result["incomplete_source_row_refs"] == ["statements"]


def test_enzyme_activity_requirement_uses_activity_value_not_carrier_mass() -> None:
    from assessment_readiness import evaluate_assessment_readiness

    row = _row("Natto Extract", "nattokinase", quantity=110, unit="mg")
    row.update({
        "dose_class": "enzyme_activity",
        "activity_quantity": 20_000,
        "activity_unit": "FU",
    })
    product = _product(row, title="Nattokinase 20,000 FU")
    product["rda_ul_data"]["dose_assessments"] = [
        {
            "source_row_ref": "ingredientRows[0]",
            "source_path": "ingredientRows[0]",
            "canonical_id": "nattokinase",
            "dose_class": "enzyme_activity",
            "source_value": 20_000,
            "source_unit": "FU",
            "material": True,
            "conversion_status": "not_applicable",
            "ul_assessment_status": "no_ul_applicable",
            "readiness": "not_applicable",
        }
    ]

    result = evaluate_assessment_readiness(product, module="generic")

    ingredient = result["evidence"]["ingredient_assessments"][0]
    assert ingredient["source_value"] == 20_000
    assert ingredient["source_unit"] == "FU"
    assert result["dose"]["material_exposure_count"] == 1
    assert result["dose"]["material_assessment_count"] == 1
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
    stale_legacy = evaluate_verification_assessment({
        "brandName": "Test Brand",
        "certification_data": {},
        "verified_cert_programs": [
            {"program": "NSF Sport", "scope": "sku", "record_id": "old-record"}
        ],
    })

    assert present["state"] == "verified_present"
    assert absent["state"] == "verified_absent"
    assert missing["state"] == "not_evaluated"
    assert missing["readiness"] == "incomplete"
    assert stale_legacy["state"] == "not_evaluated"
    assert stale_legacy["reason_code"] == "legacy_registry_match_missing_current_provenance"

    other_brand_legacy = evaluate_verification_assessment({
        "brandName": "Test Brand",
        "certification_data": {},
        "verified_cert_programs": [{
            "program": "NSF Sport",
            "scope": "sku",
            "record_id": "other-brand-record",
            "source_url": "https://registry.example/nsf-sport",
            "snapshot_date": "2026-09-16",
            "recency_status": "fresh",
            "matched_brand": "Unrelated Megacorp",
        }],
    })
    assert other_brand_legacy["state"] == "verified_absent"
    assert other_brand_legacy["readiness"] == "complete"


@pytest.mark.parametrize("has_label_owner", [True, False])
def test_probiotic_native_clinical_strain_requires_label_owner_for_material_assessment(has_label_owner) -> None:
    from assessment_readiness import evaluate_assessment_readiness

    row = _row("Lactobacillus rhamnosus GG", "lactobacillus_rhamnosus", quantity=50, unit="billion CFU")
    product = _product(row, title="Daily Probiotic")
    if has_label_owner:
        product["activeIngredients"] = [row]
    product["supplement_taxonomy"] = {"primary_type": "probiotic"}
    product["probiotic_data"] = {
        "is_probiotic_product": True,
        "total_billion_count": 50,
        "total_strain_count": 1,
        "clinical_strains": [
            {
                "clinical_id": "STRAIN_LGG",
                "strain": "Lactobacillus rhamnosus GG",
                "clinical_support_level": "high",
            }
        ],
    }
    result = evaluate_assessment_readiness(product, module="probiotic")

    assessment = result["evidence"]["ingredient_assessments"][0]
    assert assessment["material"] is True
    assert assessment["state"] == (
        "evaluated_supported" if has_label_owner else "not_yet_evaluated"
    )
    assert result["dose"]["assessment_source"] == "typed_dose_assessments"
    if has_label_owner:
        assert result["is_live_ready"] is True


def test_a_reviewed_strain_without_supportive_evidence_is_evaluated_not_supported() -> None:
    """HN019's reviewed trials are null: the enricher gives it no support level,
    and its registry evidence_level ("high") must not stand in for one."""
    from assessment_readiness import evaluate_assessment_readiness

    row = _row("Bifidobacterium lactis HN019", "bifidobacterium_lactis", quantity=10, unit="billion CFU")
    product = _product(row, title="Daily Probiotic")
    product["activeIngredients"] = [row]
    product["supplement_taxonomy"] = {"primary_type": "probiotic"}
    product["probiotic_data"] = {
        "is_probiotic_product": True,
        "total_billion_count": 10,
        "total_strain_count": 1,
        "clinical_strains": [{
            "clinical_id": "STRAIN_LACTIS_HN019",
            "strain": "Bifidobacterium lactis HN019",
            "clinical_support_level": None,
            "evidence_level": "high",
        }],
    }
    result = evaluate_assessment_readiness(product, module="probiotic")

    assert result["evidence"]["ingredient_assessments"][0]["state"] == "evaluated_limited_or_negative"


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
    """Canonical vocabulary makes neither a synthetic row nor a completed source review."""
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


def test_row_level_active_projection_keeps_its_individual_evidence_question() -> None:
    """A direct label active is not a synthetic module aggregate.

    Some mapped botanicals are projected from ``activeIngredients`` because
    their form-quality row is absent from ``ingredients_scorable``.  The
    projection still owns an exact label row, identity, and dose and therefore
    must participate in clinical-evidence matching and review readiness.
    """
    from assessment_readiness import evaluate_assessment_readiness

    row = _row("Garlic extract", "garlic", quantity=1200.0)
    product = _product(row, title="Garlic 1200 mg")
    product["ingredient_quality_data"] = {
        "ingredients_scorable": [],
        "ingredients": [row],
        "total_active": 0,
    }
    product["activeIngredients"] = [row]

    evidence = evaluate_assessment_readiness(product, module="generic")["evidence"]

    assessment = evidence["ingredient_assessments"][0]
    assert assessment["scoring_input_kind"] == "label_active_projection"
    assert assessment["evidence_applicability"] == "individual_ingredient"
    # INGR_GARLIC is now a completed review scoped to the studied preparations
    # (Dr. Pham, 2026-10-28). The projected row reaches that reviewed scope and
    # is assessed as a product-specific zero, not left as an open question.
    assert assessment["state"] == "evaluated_limited_or_negative"
    assert assessment["reason_code"] == "clinical_form_mismatch"
    assert evidence["not_yet_evaluated_count"] == 0
    assert evidence["readiness"] == "complete"


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

    row = _row("Unreviewed Botanical", "unreviewed_botanical")
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

    row = _row("Unreviewed Botanical", "unreviewed_botanical")
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

    row = _row("Unreviewed Botanical", "unreviewed_botanical")
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


@pytest.mark.parametrize('state,readiness', [
    ('not_evaluated', 'complete'),
    ('verified_present', 'incomplete'),
    ('verified_absent', 'incomplete'),
])
def test_verification_explicit_state_readiness_must_agree(state, readiness):
    from assessment_readiness import evaluate_verification_assessment
    result = evaluate_verification_assessment({'certification_data': {
        'verification_assessment': {'state': state, 'readiness': readiness}}})
    assert result['state'] == 'not_evaluated'
    assert result['readiness'] == 'incomplete'
    assert result['reason_code'] == 'invalid_verification_assessment_contract'


def test_readiness_retains_reviewed_reference_conclusion_alongside_incidental_matches():
    from assessment_readiness import evaluate_evidence_assessment
    from scoring_v4.modules.generic_evidence import resolved_clinical_matches

    product = _product(
        _row('N-Acetylcysteine', 'nac', quantity=600),
        matches=[{'id': 'INCIDENTAL', 'ingredient': 'Calcium',
                  'standard_name': 'Calcium', 'study_type': 'rct_single'}],
    )
    _, recovered = resolved_clinical_matches(product, owner_scoped=True)
    # Returned exercise-only NAC review is retained as reference, not recovered as affirmative credit.
    assert not any(match['id'] == 'INGR_NAC' for match in recovered)
    assessment = evaluate_evidence_assessment(product, module='generic')
    assert assessment['ingredient_assessments'][0]['reason_code'] == 'reference_only_clinical_record'
    assert assessment['ingredient_assessments'][0]['state'] == 'evaluated_limited_or_negative'
    assert assessment['readiness'] == 'complete'

@pytest.mark.parametrize(
    "disposition,owners,reason,expected",
    [
        ("no_qualifying_human_evidence", ["clinical_strains"], "probiotic_strain_reviewed_no_qualifying_human_evidence", "not_yet_evaluated"),
        ("reviewed_null_unfavorable", ["backed_clinical_studies"], "literature_reviewed_null_or_unfavorable", "evaluated_limited_or_negative"),
        ("resolved_by_reviewed_clinical_evidence", ["backed_clinical_studies"], "literature_reviewed_human_clinical_evidence", "evaluated_limited_or_negative"),
        ("research_present_applicability_unestablished", ["backed_clinical_studies"], "literature_applicability_unestablished", "not_yet_evaluated"),
        ("research_present_applicability_unestablished", ["clinical_strains"], "probiotic_species_or_stub_applicability_unestablished", "not_yet_evaluated"),
        ("literature_resolution_required", [], "unverified_generated_record_cannot_complete_evidence", "not_yet_evaluated"),
        ("identity_insufficient", ["backed_clinical_studies"], "identity_material_unresolved", "not_yet_evaluated"),
    ],
)
def test_readiness_consumes_concluded_resolver_reviews_without_completing_pending_identity(
    monkeypatch, disposition, owners, reason, expected,
):
    import evidence_resolver
    from assessment_readiness import evaluate_evidence_assessment

    row = _row("Unreviewed Botanical", "unreviewed_botanical")
    result = evidence_resolver.EvidenceResolution(
        canonical_id=row["canonical_id"], ingredient_name=row["name"],
        matched_owners=owners, disposition=disposition, points_eligible=False,
        applicability_status="test", reason_code=reason,
        owner_facts={"literature_evidence": {}} if "backed_clinical_studies" in owners else {},
    )
    monkeypatch.setattr(evidence_resolver, "resolve_evidence_for_row", lambda *a, **k: result)
    assessment = evaluate_evidence_assessment(_product(row), module="generic")
    assert assessment["ingredient_assessments"][0]["state"] == expected
    assert assessment["not_yet_evaluated_count"] == int(expected == "not_yet_evaluated")


def test_evidence_readiness_includes_undosed_active_blend_subject():
    from assessment_readiness import evaluate_evidence_assessment
    row = _row("Unreviewed Botanical", "unreviewed_botanical", quantity=0, unit="NP")
    row.update(has_dose=False, role_classification="inactive_non_scorable",
               cleaner_row_role="nested_display_only", score_eligible=False,
               score_eligible_by_cleaner=False, isNestedIngredient=True,
               parentBlend="Botanical Blend")
    product = _product(row)
    product["ingredient_quality_data"]["ingredients_scorable"] = []
    product["activeIngredients"] = [row]
    result = evaluate_evidence_assessment(product, module="generic")
    assessment = next(r for r in result["ingredient_assessments"] if r["canonical_id"] == row["canonical_id"])
    assert assessment["state"] == "not_yet_evaluated"
    assert assessment["source_value"] == 0
    assert result["not_yet_evaluated_count"] == 1

@pytest.mark.parametrize("owned", [True, False])
def test_la5_reviewed_context_requires_exact_label_row_owner(owned):
    # Reviewed combination context is limited evidence, not an unfinished review
    # or a positive individual-strain result. It still requires the label owner.
    from assessment_readiness import _probiotic_native_evidence_state
    row = _row("Lactobacillus acidophilus LA-5", "lactobacillus_acidophilus", quantity=500, unit="million CFU")
    product = _product(row)
    product["activeIngredients"] = [row]
    product["probiotic_data"] = {"is_probiotic_product": True, "clinical_strains": [{
        "clinical_id": "STRAIN_ACIDOPHILUS_LA5", "strain": row["name"],
        "source_row_ref": "ingredientRows[0]", "research_match_status": "no_qualifying_human_evidence",
        "review_status": "literature_reviewed_no_qualifying_evidence",
    }]}
    target = row if owned else {**row, "name": "Lactobacillus acidophilus", "raw_source_path": "ingredientRows[99]", "source_row_ref": "ingredientRows[99]"}
    assert _probiotic_native_evidence_state(product, target) == ("evaluated_limited_or_negative" if owned else None)


@pytest.mark.parametrize("module", ["generic", "multi_or_prenatal", "probiotic"])
@pytest.mark.parametrize("measurement", ["cfu", "afu"])
def test_microorganism_measurement_holds_apply_across_routes(module, measurement) -> None:
    from assessment_readiness import evaluate_assessment_readiness
    from probiotic_measurements import AFU_REVIEW_REASON
    from scoring_v4.scored_artifact import build_scored_artifact

    product = _product(_row("Calcium", "calcium", quantity=500))
    if measurement == "cfu":
        product["probiotic_data"] = {"probiotic_blends": [{
            "strains": ["Lactobacillus acidophilus"],
            "cfu_data": {"has_cfu": True, "cfu_count": -1},
        }]}
        expected_reason = "unresolved_source_quantity"
    else:
        product["probiotic_data"] = {"afu_measurements": [{
            "source_row_ref": "ingredientRows[1]", "afu_count": 1_000_000_000,
            "assessment_status": "unresolved_reference",
        }]}
        expected_reason = AFU_REVIEW_REASON
    readiness = evaluate_assessment_readiness(product, module=module)
    assert readiness["dose"]["readiness"] == "incomplete"
    assert readiness["dose"]["reason_code"] == expected_reason
    assert readiness["is_live_ready"] is False
    assert "dose_assessment_readiness" in readiness["unavailable_reasons"]
    artifact = build_scored_artifact(product)
    assert artifact["quality_score_status"] == "not_scored"
    assert artifact["quality_score_v4_100"] is None
    assert artifact["assessment_readiness"]["dose"]["reason_code"] == expected_reason


@pytest.mark.parametrize("module", ["generic", "multi_or_prenatal"])
@pytest.mark.parametrize("probiotic_data", [{}, {"afu_measurements": []}, {
    "probiotic_blends": [{"strains": ["Lactobacillus acidophilus"],
                          "cfu_data": {"has_cfu": True, "cfu_count": 1_000_000_000}}],
}])
def test_resolved_or_absent_microorganism_measurements_preserve_dose_readiness(module, probiotic_data) -> None:
    from assessment_readiness import evaluate_assessment_readiness

    product = _product(_row("Calcium", "calcium", quantity=500))
    product["probiotic_data"] = probiotic_data
    assert evaluate_assessment_readiness(product, module=module)["dose"]["readiness"] == "complete"


@pytest.mark.parametrize("reviewed", [True, False])
@pytest.mark.parametrize("parent_is_material", [True, False])
def test_undosed_evidence_owner_readiness_does_not_promote_dose_materiality(
    monkeypatch, reviewed, parent_is_material,
):
    """An inherited/fallback research owner is assessable without a known dose."""
    import evidence_resolver
    import assessment_readiness

    row = _row("Undosed Botanical", "undosed_botanical", quantity=None, unit="NP")
    row.update(has_dose=False, isNestedIngredient=True,
               raw_source_path="ingredientRows[0].nestedRows[0]",
               source_row_ref="ingredientRows[0].nestedRows[0]")
    header = _row("Botanical Blend", "botanical_blend", quantity=1000)
    product = _product(row, title="Botanical Formula")
    monkeypatch.setattr(evidence_resolver, "_evidence_subject_roles", lambda *args: (
        [row], [{"role": "adjunct"}], [header],
        [{"role": "major" if parent_is_material else "adjunct"}],
    ))
    monkeypatch.setattr(assessment_readiness, "resolved_clinical_matches",
                        lambda *args, **kwargs: ([_match(row, "positive_strong")] if reviewed else [], []))
    assert row["canonical_id"] in evidence_resolver.evidence_owner_canonicals(product, module="generic")
    result = assessment_readiness.evaluate_evidence_assessment(product, module="generic")
    item = result["ingredient_assessments"][0]
    assert item["evidence_applicability"] == "individual_ingredient"
    assert item["state"] == ("evaluated_supported" if reviewed else "not_yet_evaluated")
    assert result["readiness"] == ("complete" if reviewed else "incomplete")
    assert item["material"] is False  # Dose still consumes physical material roles.
    assert item["role"] == "adjunct"
    assert item["source_value"] is None
    assert item["source_unit"] == "NP"
    assert result["not_yet_evaluated_count"] == int(not reviewed)


def test_undosed_nonowner_remains_outside_individual_evidence(monkeypatch):
    """A named primary elsewhere does not promote an unrelated undosed adjunct."""
    import evidence_resolver
    import assessment_readiness

    owner = _row("N-Acetylcysteine", "nac")
    adjunct = _row("Undosed Adjunct", "undosed_adjunct", quantity=None, unit="NP")
    adjunct.update(has_dose=False, raw_source_path="ingredientRows[1]")
    product = _product(owner)
    monkeypatch.setattr(evidence_resolver, "_evidence_subject_roles", lambda *args: (
        [owner, adjunct], [{"role": "primary"}, {"role": "adjunct"}], [], [],
    ))
    result = assessment_readiness.evaluate_evidence_assessment(product, module="generic")
    item = next(x for x in result["ingredient_assessments"] if x["canonical_id"] == "undosed_adjunct")
    assert item["state"] == "not_applicable"
    assert item["reason_code"] == "non_material_active"
    assert item["source_value"] is None


@pytest.mark.parametrize("module", ["probiotic", "generic", "fiber_digestive", "sports", "multi_or_prenatal"])
@pytest.mark.parametrize("review_status", ["pending_review", "rejected", "needs_revision"])
def test_retained_native_context_cannot_close_explicit_review_hold(review_status, module):
    from assessment_readiness import evaluate_evidence_assessment
    row = _row("Lactobacillus rhamnosus GG", "lactobacillus_rhamnosus", quantity=1e10, unit="CFU")
    product = _product(row)
    product["activeIngredients"] = [row]
    product["probiotic_data"] = {"is_probiotic_product": True, "clinical_strains": [{
        "clinical_id": "STRAIN_LGG", "strain": row["name"],
        "source_row_ref": "ingredientRows[0]", "review_status": review_status,
    }]}
    result = evaluate_evidence_assessment(product, module=module)
    assert result["not_yet_evaluated_count"] == 1
    assert result["ingredient_assessments"][0]["state"] == "not_yet_evaluated"

@pytest.mark.parametrize('dimension', ['identity', 'dose', 'evidence', 'verification', 'route'])
def test_release_completion_is_separate_and_blocks_owned_missing_work(dimension):
    from assessment_readiness import evaluate_release_assessment
    readiness = {name: {'readiness': 'complete'} for name in
                 ('identity', 'dose', 'evidence', 'verification', 'route')}
    readiness[dimension]['readiness'] = 'incomplete'
    result = evaluate_release_assessment({}, readiness, {'module': 'generic'}, unfinished_source=None)
    assert result['is_complete'] is False
    assert f'{dimension}_assessment_incomplete' in result['blockers']
    assert readiness[dimension]['readiness'] == 'incomplete'


@pytest.mark.parametrize('status,expected', [('applicable', True), ('not_curated', False), ('unresolved', False)])
def test_release_completion_uses_actual_generic_credit_dependencies(status, expected, monkeypatch):
    _install_completed_release_context(monkeypatch)
    from assessment_readiness import evaluate_release_assessment
    readiness = {name: {'readiness': 'complete'} for name in
                 ('identity', 'dose', 'evidence', 'verification', 'route')}
    module = {'module': 'generic', 'dimensions': {'evidence': {'score': 14, 'metadata': {
        'contributing_record_assessments': [{'id': 'used', 'status': status, 'scope_qualification_complete': status == 'applicable'}]}}}}
    result = evaluate_release_assessment({}, readiness, module, unfinished_source=None)
    assert result['is_complete'] is expected


@pytest.mark.parametrize('reason,value,expected', [
    ('amount_not_declared', None, True), ('amount_not_declared', 100, False),
    ('conversion_failed', None, False), ('no_ul_applicable', None, False)])
def test_release_dose_label_limitation_requires_explicit_owner_proof(reason, value, expected):
    from assessment_readiness import evaluate_release_assessment
    readiness = {name: {'readiness': 'complete'} for name in
                 ('identity', 'dose', 'evidence', 'verification', 'route')}
    readiness['dose'] = {'readiness': 'incomplete', 'reason_code': 'no_scoreable_active_dose',
                         'incomplete_source_row_refs': ['row1']}
    product = {'rda_ul_data': {'dose_assessments': [{'source_path': 'row1',
               'reason_code': reason, 'source_value': value}]}}
    result = evaluate_release_assessment(product, readiness, {'module': 'generic'}, unfinished_source=None)
    assert result['is_complete'] is expected


def test_release_native_omega_does_not_consume_unused_generic_credit():
    from assessment_readiness import evaluate_release_assessment
    readiness = {name: {'readiness': 'complete'} for name in
                 ('identity', 'dose', 'evidence', 'verification', 'route')}
    readiness['evidence']['readiness'] = 'incomplete'
    module = {'module': 'omega', 'dimensions': {'evidence': {'score': 14, 'metadata': {
        'evidence_result_state': 'evaluated_applicable',
        'generic_evidence_metadata': {'contributing_record_assessments': [{'id': 'unused', 'status': 'not_curated'}]}}}}}
    assert evaluate_release_assessment({}, readiness, module, unfinished_source=None)['is_complete'] is True


@pytest.mark.parametrize('scope_complete,regimen_status,expected', [
    (False, 'verified', False), (True, 'extraction_pending', False),
    (True, 'source_not_reported', True), (True, 'verified', True)])
def test_generic_release_requires_scoped_review_but_never_invents_numeric_benchmark(scope_complete, regimen_status, expected, monkeypatch):
    _install_completed_release_context(monkeypatch, regimen_status)
    from assessment_readiness import evaluate_release_assessment
    readiness = {name: {'readiness': 'complete'} for name in
                 ('identity', 'dose', 'evidence', 'verification', 'route')}
    receipt = {'id': 'used', 'status': 'applicable',
               'scope_qualification_complete': scope_complete,
               'studied_regimens': [{'dose_status': regimen_status}]}
    module = {'module': 'generic', 'dimensions': {'evidence': {'score': 10,
        'metadata': {'contributing_record_assessments': [receipt]}}}}
    assert evaluate_release_assessment({}, readiness, module, unfinished_source=None)['is_complete'] is expected


def test_positive_generic_empty_dependencies_need_selected_authority_proof():
    from assessment_readiness import evaluate_release_assessment
    readiness = {name: {'readiness': 'complete'} for name in
                 ('identity', 'dose', 'evidence', 'verification', 'route')}
    module = {'module': 'generic', 'dimensions': {'evidence': {'score': 14,
        'metadata': {'contributing_record_assessments': []}}}}
    assert evaluate_release_assessment({}, readiness, module, unfinished_source=None)['is_complete'] is False


def test_positive_generic_population_and_outcome_are_not_full_source_review():
    from assessment_readiness import evaluate_release_assessment
    readiness = {name: {'readiness': 'complete'} for name in
                 ('identity', 'dose', 'evidence', 'verification', 'route')}
    receipt = {'id': 'partial', 'status': 'applicable', 'scope_qualification_complete': True,
               'studied_population': 'adults', 'supported_outcomes': ['sleep']}
    module = {'module': 'generic', 'dimensions': {'evidence': {'score': 14,
        'metadata': {'contributing_record_assessments': [receipt]}}}}
    assert evaluate_release_assessment({}, readiness, module, unfinished_source=None)['is_complete'] is False


def _install_completed_release_context(monkeypatch, dose_status='verified'):
    import clinical_applicability
    from test_clinical_evidence_schema_ingredient import _context
    context = _context()
    context.update(review_status='clinician_approved', study_design='rct', purpose='treatment',
                   clinical_review={'reviewer': 'Synthetic reviewer', 'reviewed_at': '2026-01-01T00:00:00Z',
                                    'scope': 'identity_dose_outcome_applicability'})
    context['dose']['dose_status'] = dose_status
    context['dose']['dosage_forms'] = ['capsule']
    context['dose']['administration_frequency'] = 'once_daily'
    if dose_status == 'source_not_reported':
        context['dose'].update(values=[], dose_basis='not_applicable', basis='unresolved')
    synthetic_references = [{'pmid': pmid} for pmid in context['source_pmids']]
    monkeypatch.setattr(clinical_applicability, 'reviewed_entries', lambda: {'used': {'id': 'used', 'study_contexts': [context],
        'references_structured': synthetic_references}})
    return context


def test_empty_generic_dependencies_pass_only_for_actual_selected_nutrition_authority():
    from assessment_readiness import evaluate_release_assessment
    from scoring_v4.modules.generic_evidence import score_evidence
    from test_v4_generic_evidence_p133 import _product, _match
    product = _product(matches=[_match(id='UNREVIEWED_SYNTHETIC', study_type='rct_single', effect_direction='positive_weak')])
    payload = score_evidence(product, apply_primary_floor=True)
    assert payload['metadata']['contributing_record_assessments'] == []
    assert payload['metadata']['selected_nutrition_authority'] == 'magnesium'
    readiness = {name: {'readiness': 'complete'} for name in
                 ('identity', 'dose', 'evidence', 'verification', 'route')}
    module = {'module': 'generic', 'dimensions': {'evidence': payload}}
    assert evaluate_release_assessment(product, readiness, module, unfinished_source=None)['is_complete'] is True
    payload['metadata']['primary_evidence_floor_decisive'] = False
    assert evaluate_release_assessment(product, readiness, module, unfinished_source=None)['is_complete'] is False


def test_zero_native_credit_does_not_close_unreviewed_purpose_transfer():
    from test_probiotic_applicability_rubric import strain_product
    from scoring_v4.modules.probiotic_evidence import score_evidence
    from assessment_readiness import evaluate_release_assessment
    product = strain_product(clinical_id='STRAIN_PLANTARUM_299V',
                             name='Lactobacillus plantarum 299v', dose=1e10)
    evidence = score_evidence(product)
    assert evidence['score'] == 0
    assert evidence['metadata']['evidence_result_state'] == 'research_present_applicability_unestablished'
    readiness = {name: {'readiness': 'complete'} for name in
                 ('identity', 'dose', 'evidence', 'verification', 'route')}
    result = evaluate_release_assessment(product, readiness,
        {'module': 'probiotic', 'dimensions': {'evidence': evidence}}, unfinished_source=None)
    assert result['is_complete'] is False
    assert 'probiotic_evidence_assessment_incomplete' in result['blockers']


@pytest.mark.parametrize("module", ["generic", "fiber_digestive", "sports", "multi_or_prenatal"])
@pytest.mark.parametrize("clinical_id,name", [
    ("STRAIN_ACIDOPHILUS_CUL21", "Lactobacillus acidophilus CUL-21"),
    ("STRAIN_ACIDOPHILUS_LA5", "Lactobacillus acidophilus LA-5"),
])
def test_cross_module_native_review_stays_bound_to_its_label_row(module, clinical_id, name):
    from assessment_readiness import evaluate_evidence_assessment
    reviewed = _row(name, "lactobacillus_acidophilus", quantity=500, unit="million CFU")
    species = {**reviewed, "name": "Lactobacillus acidophilus", "standard_name": "Lactobacillus acidophilus",
               "raw_source_path": "ingredientRows[1]", "source_row_ref": "ingredientRows[1]"}
    unresolved = {**reviewed, "name": "Lactobacillus paracasei DSM-16105", "standard_name": "Lactobacillus paracasei DSM-16105",
                  "canonical_id": "lactobacillus_paracasei", "raw_source_path": "ingredientRows[2]", "source_row_ref": "ingredientRows[2]"}
    product = _product(reviewed)
    product["activeIngredients"] = [reviewed, species, unresolved]
    product["ingredient_quality_data"]["ingredients"] = product["activeIngredients"]
    product["ingredient_quality_data"]["ingredients_scorable"] = product["activeIngredients"]
    product["probiotic_data"] = {"is_probiotic_product": True, "clinical_strains": [{
        "clinical_id": clinical_id, "strain": name, "source_row_ref": "ingredientRows[0]",
        "research_match_status": "no_qualifying_human_evidence",
        "review_status": "literature_reviewed_no_qualifying_evidence",
    }]}
    result = evaluate_evidence_assessment(product, module=module)
    by_ref = {r["source_row_ref"]: r for r in result["ingredient_assessments"]}
    assert by_ref["ingredientRows[0]"]["state"] == "evaluated_limited_or_negative"
    assert by_ref["ingredientRows[0]"]["reason_code"] == "reviewed_native_clinical_strain_evidence"
    # Neither a generic same-species sibling nor an unresolved designation may
    # borrow another source row's completed review.
    for ref in ["ingredientRows[1]", "ingredientRows[2]"]:
        assert by_ref[ref]["state"] == "not_yet_evaluated"


def test_vitamin_a_precursor_uses_existing_nutrition_authority_review():
    from assessment_readiness import evaluate_evidence_assessment
    row = _row('Vitamin A', 'beta_carotene', quantity=900, unit='mcg RAE')
    evidence = evaluate_evidence_assessment(_product(row), module='generic')
    assessment = evidence['ingredient_assessments'][0]
    assert assessment['evidence_applicability'] == 'nutrition_authority'
    assert assessment['state'] == 'evaluated_supported'
    assert assessment['reason_code'] == 'dietary_reference_intake_authority_established'
    assert assessment['evidence_ids'] == []


@pytest.mark.parametrize('canonical', ['boron', 'vanadium'])
def test_nonessential_mineral_does_not_borrow_nutrition_authority(canonical):
    from assessment_readiness import evaluate_evidence_assessment
    evidence = evaluate_evidence_assessment(_product(_row(canonical, canonical)), module='generic')
    assert evidence['ingredient_assessments'][0]['evidence_applicability'] != 'nutrition_authority'


@pytest.mark.parametrize('canonical,name', [('same', 'S-Adenosyl Methionine'), ('l_glycine', 'L-Glycine')])
def test_unresolved_clinical_source_hold_is_not_a_completed_negative_review(canonical, name):
    from assessment_readiness import evaluate_evidence_assessment
    row = _row(name, canonical)
    result = evaluate_evidence_assessment(_product(row), module='generic')
    assert result['readiness'] == 'incomplete'
    assert result['ingredient_assessments'][0]['state'] == 'not_yet_evaluated'
    assert result['ingredient_assessments'][0]['reason_code'] == 'clinical_sources_ineligible'


def test_explicit_zero_source_reuses_completed_typed_assessment():
    from assessment_readiness import _dose_readiness
    row = _row('Vitamin C', 'vitamin_c', quantity=0, unit='mg')
    row['raw_taxonomy'] = {'quantityVariants': [{'quantity': 0, 'unit': 'mg',
        'quantity_parsed': True, 'selected_for_analysis': True}]}
    product = _product(row)
    product['rda_ul_data']['dose_assessments'][0].update({
        'source_path': 'ingredientRows[0]', 'source_value': 0,
        'source_unit': 'mg', 'readiness': 'complete', 'material': False})
    assert _dose_readiness(product, [{'material': False}], module='generic')['readiness'] == 'complete'


@pytest.mark.parametrize("change", ["missing_source", "unparsed", "np", "censored", "missing_typed", "unit_mismatch"])
def test_zero_completion_requires_source_and_typed_proof(change):
    from assessment_readiness import _dose_readiness
    row = _row("Vitamin C", "vitamin_c", quantity=0, unit="mg")
    row["raw_taxonomy"] = {"quantityVariants": [{"quantity": 0, "unit": "mg",
        "quantity_parsed": True, "selected_for_analysis": True, "operator": "="}]}
    product = _product(row)
    typed = product["rda_ul_data"]["dose_assessments"][0]
    typed.update(source_value=0, source_unit="mg", readiness="complete", material=False)
    variant = row["raw_taxonomy"]["quantityVariants"][0]
    if change == "missing_source":
        row.pop("raw_source_path")
    elif change == "unparsed":
        variant["quantity_parsed"] = False
    elif change == "np":
        row["unit"] = variant["unit"] = "NP"
    elif change == "censored":
        variant["operator"] = "<"
    elif change == "missing_typed":
        product["rda_ul_data"]["dose_assessments"] = []
    else:
        typed["source_unit"] = "g"
    assert _dose_readiness(product, [{"material": False}], module="generic")["readiness"] == "incomplete"


@pytest.mark.parametrize('operator', ['ambiguous', 'unknown'])
def test_unresolved_source_quantity_cannot_be_waived_by_complete_typed_assessment(operator):
    from assessment_readiness import _dose_readiness
    row = _row('Caffeine', 'caffeine', quantity=300)
    row['raw_taxonomy'] = {'quantityVariants': [{'quantity': 300, 'unit': 'mg',
        'operator': operator, 'selected_for_analysis': True}]}
    product = _product(row)
    product['rda_ul_data']['dose_assessments'][0].update(source_value=300, source_unit='mg', readiness='complete')
    result = _dose_readiness(product, [{'material': True, 'source_row_ref': 'ingredientRows[0]', 'quantity': 300, 'unit': 'mg'}], module='sports')
    assert result['readiness'] == 'incomplete'
    assert result['reason_code'] == 'unresolved_source_quantity'
    assert result['incomplete_source_row_refs'] == ['ingredientRows[0]']


@pytest.mark.parametrize("case", json.loads((Path(__file__).parent / "fixtures" /
    "module_aggregate_release_cases.json").read_text()), ids=lambda case: case["id"])
def test_rebuilt_module_projections_do_not_complete_unresolved_aggregate_review(case):
    """Minimized final-150 records retain their actual canonical resolutions."""
    from copy import deepcopy
    from assessment_readiness import evaluate_release_assessment
    from evidence_resolver import resolve_product_evidence

    before = deepcopy(case["readiness"])
    resolution = resolve_product_evidence(case["product"], owner_scoped=True, module=case["module"])
    assert resolution.overall_disposition == case["expected_overall"]
    assert sorted(resolution.unresolved_blockers) == case["expected_blockers"]
    assert any(row["evidence_applicability"] == "module_aggregate"
               and row["state"] == "not_applicable"
               for row in before["evidence"]["ingredient_assessments"])
    result = evaluate_release_assessment(case["product"], case["readiness"],
        case["module_breakdown"], unfinished_source=None)
    assert result["is_complete"] is False
    assert "evidence_assessment_incomplete" in result["blockers"]
    assert case["readiness"] == before  # No duplicate individual review ledger.


def _aggregate_release_inputs():
    readiness = {name: {"readiness": "complete"} for name in
                 ("identity", "dose", "evidence", "verification", "route")}
    readiness["evidence"]["ingredient_assessments"] = [{
        "evidence_applicability": "module_aggregate", "state": "not_applicable",
        "reason_code": "module_scoped_product_projection",
        "scoring_input_kind": "product_level_evidence",
    }]
    module = {"module": "generic", "dimensions": {"evidence": {"score": 0,
        "metadata": {"contributing_record_assessments": []}}}}
    return readiness, module


@pytest.mark.parametrize("disposition,reason,owners,facts", [
    ("no_qualifying_human_evidence", "bounded_search_no_qualifying_trials",
     ["literature_evidence"], {"literature_evidence": {}}),
    ("reviewed_null_unfavorable", "reviewed_null_finding",
     ["literature_evidence"], {"literature_evidence": {}}),
    ("research_present_applicability_unestablished", "dose_below_studied_range",
     ["backed_clinical_studies"], {}),
    ("research_present_applicability_unestablished", "form_mismatch_with_clinical_trials",
     ["backed_clinical_studies"], {}),
    ("not_efficacy_relevant", "whole_food_matrix_not_efficacy_relevant", [], {}),
])
def test_completed_aggregate_negative_or_inapplicable_review_can_release(
        monkeypatch, disposition, reason, owners, facts):
    import evidence_resolver
    from assessment_readiness import evaluate_release_assessment

    row = evidence_resolver.EvidenceResolution("fixture", "Fixture", owners,
        disposition, False, "assessed", reason, owner_facts=facts)
    resolution = evidence_resolver.ProductEvidenceResolution("fixture", "Fixture", 1,
        [row], disposition, True, [], {})
    monkeypatch.setattr(evidence_resolver, "resolve_product_evidence",
                        lambda product, **kwargs: resolution)
    readiness, module = _aggregate_release_inputs()
    assert evaluate_release_assessment({}, readiness, module,
        unfinished_source=None)["is_complete"] is True


def test_aggregate_review_keeps_a_documented_manufacturer_amount_limitation(monkeypatch):
    import evidence_resolver
    from assessment_readiness import evaluate_release_assessment

    resolution = evidence_resolver.ProductEvidenceResolution("fixture", "Fixture", 0,
        [], "not_efficacy_relevant", True, [], {})
    monkeypatch.setattr(evidence_resolver, "resolve_product_evidence",
                        lambda product, **kwargs: resolution)
    readiness, module = _aggregate_release_inputs()
    readiness["dose"] = {"readiness": "incomplete", "incomplete_source_row_refs": ["row1"]}
    product = {"rda_ul_data": {"dose_assessments": [{"source_path": "row1",
        "reason_code": "amount_not_declared", "source_value": None}]}}
    assert evaluate_release_assessment(product, readiness, module,
        unfinished_source=None)["is_complete"] is True


def test_aggregate_review_does_not_reassess_intentionally_unscoreable_product(monkeypatch):
    import evidence_resolver
    from assessment_readiness import evaluate_release_assessment

    def forbidden(*args, **kwargs):
        raise AssertionError("An intentionally unscoreable product has no affirmative aggregate review.")

    monkeypatch.setattr(evidence_resolver, "resolve_product_evidence", forbidden)
    readiness, module = _aggregate_release_inputs()
    readiness["catalog_disposition"] = {"disposition": "intentional_non_scoreable"}
    for name in ("identity", "dose", "route"):
        readiness[name]["readiness"] = "incomplete"
    assert evaluate_release_assessment({}, readiness, module,
        unfinished_source=None)["is_complete"] is True


def test_aggregate_review_respects_the_nutrition_owner_and_unused_adjunct():
    from assessment_readiness import evaluate_release_assessment
    from evidence_resolver import resolve_product_evidence

    nutrient = _row("Vitamin C", "vitamin_c", quantity=1000)
    adjunct = _row("Unreviewed Botanical", "unreviewed_botanical", quantity=1)
    adjunct.update(raw_source_path="ingredientRows[1]", source_row_ref="ingredientRows[1]")
    product = _product(nutrient, title="Vitamin C 1000 mg")
    product["ingredient_quality_data"]["ingredients"].append(adjunct)
    product["ingredient_quality_data"]["ingredients_scorable"].append(adjunct)
    product["activeIngredients"] = [nutrient, adjunct]
    assert resolve_product_evidence(product, module="generic").is_assessment_complete is False
    owned = resolve_product_evidence(product, owner_scoped=True, module="generic")
    assert owned.is_assessment_complete is True
    assert [row.canonical_id for row in owned.resolutions] == ["vitamin_c"]
    readiness, module = _aggregate_release_inputs()
    module["dimensions"]["evidence"].update(score=20, metadata={
        "contributing_record_assessments": [],
        "selected_nutrition_authority": "vitamin_c",
        "nutrition_authority_floor_applied": True,
        "primary_evidence_floor_decisive": True,
        "nutrition_authority_canonical": "vitamin_c",
    })
    assert evaluate_release_assessment(product, readiness, module,
        unfinished_source=None)["is_complete"] is True


def test_literature_gap_cannot_be_completed_by_an_earlier_backed_owner_name():
    from assessment_readiness import _resolved_evidence_assessment
    from evidence_resolver import EvidenceResolution
    resolution = EvidenceResolution('nha_univestin', 'Univestin', ['backed_clinical_studies'],
        'research_present_applicability_unestablished', False, 'applicability_unestablished',
        'literature_applicability_unestablished', owner_facts={'literature_evidence': {}},
        blocking_reasons=['literature_applicability_unestablished'])
    assert _resolved_evidence_assessment(resolution)[0] == 'not_yet_evaluated'
