"""Consumer dose-decision contract for authored interaction thresholds.

The clinical rule remains the source of severity.  Product evaluation adds two
orthogonal axes: what happened while evaluating this label and how the authored
result may be presented to a consumer.  Flutter must consume these fields; it
must not infer them from ``monitor`` / ``caution``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).parent.parent))

from enrich_supplements_v3 import SupplementEnricherV3
from unit_converter import UnitConverter


def _vitamin_d_threshold() -> dict:
    return {
        "scope": "condition",
        "target_id": "heart_disease",
        "basis": "per_day",
        "comparator": ">",
        "value": 4000,
        "unit": "IU",
        "severity_if_met": "caution",
        "severity_if_not_met": "monitor",
        "consumer_disposition_if_met": "review",
        "consumer_disposition_if_not_met": "suppress",
        "amount_missing_disposition": "good_to_know",
        "conversion_failure_policy": "release_block",
    }


def _evaluate(ingredient: dict, servings: float = 1.0):
    enricher = SupplementEnricherV3()
    return enricher._evaluate_dose_thresholds_for_target(
        [_vitamin_d_threshold()],
        "condition",
        "heart_disease",
        ingredient,
        servings,
        "monitor",
    )


def test_below_threshold_has_suppressed_consumer_disposition_and_trace():
    severity, result = _evaluate(
        {
            "quantity": 50,
            "unit": "mcg",
            "name": "Vitamin D3",
            "standard_name": "Vitamin D3 (Cholecalciferol)",
            "matched_form": "cholecalciferol",
            "form_id": "vitamin_d3_cholecalciferol",
        }
    )

    assert severity == "monitor"  # clinical vocabulary remains unchanged
    assert result["evaluation_status"] == "below_threshold"
    assert result["clinical_severity"] == "monitor"
    assert result["consumer_disposition"] == "suppress"
    assert result["release_blocking"] is False
    assert result["dose_evaluation"] == {
        "observed_amount": 50.0,
        "observed_unit": "mcg",
        "serving_multiplier": 1.0,
        "daily_amount": 50.0,
        "daily_unit": "mcg",
        "converted_amount": 2000.0,
        "threshold": 4000.0,
        "threshold_unit": "iu",
        "comparator": ">",
        "conversion_method": "vitamin_d3",
        "dose_source": "suggested_daily_serving",
        "form_context": "cholecalciferol",
    }


def test_threshold_match_uses_authored_review_disposition():
    severity, result = _evaluate(
        {
            "quantity": 101,
            "unit": "mcg",
            "name": "Vitamin D3",
            "standard_name": "Vitamin D3 (Cholecalciferol)",
            "matched_form": "cholecalciferol",
            "form_id": "vitamin_d3_cholecalciferol",
        }
    )

    assert severity == "caution"
    assert result["evaluation_status"] == "above_threshold"
    assert result["clinical_severity"] == "caution"
    assert result["consumer_disposition"] == "review"
    assert result["dose_evaluation"]["converted_amount"] == 4040.0


def test_missing_amount_uses_explicit_unknown_policy_without_claiming_high_dose():
    severity, result = _evaluate(
        {"unit": "mcg", "name": "Vitamin D3", "standard_name": "Vitamin D3"}
    )

    assert severity == "monitor"
    assert result["evaluation_status"] == "amount_unknown"
    assert result["clinical_severity"] == "monitor"
    assert result["consumer_disposition"] == "good_to_know"
    assert result["release_blocking"] is False
    assert result["dose_evaluation"] is None


def test_unauthored_below_and_missing_states_default_to_suppress():
    """Absent consumer policy must never recreate a presence-only warning."""
    enricher = SupplementEnricherV3()
    threshold = {
        "scope": "condition",
        "target_id": "heart_disease",
        "basis": "per_day",
        "comparator": ">",
        "value": 4000,
        "unit": "IU",
        "severity_if_met": "caution",
        "severity_if_not_met": "monitor",
    }

    _severity, below = enricher._evaluate_dose_thresholds_for_target(
        [threshold],
        "condition",
        "heart_disease",
        {
            "quantity": 50,
            "unit": "mcg",
            "name": "Vitamin D3",
            "standard_name": "Vitamin D3 (Cholecalciferol)",
        },
        1.0,
        "monitor",
    )
    _severity, missing = enricher._evaluate_dose_thresholds_for_target(
        [threshold],
        "condition",
        "heart_disease",
        {"unit": "mcg", "name": "Vitamin D3"},
        1.0,
        "monitor",
    )

    assert below["evaluation_status"] == "below_threshold"
    assert below["consumer_disposition"] == "suppress"
    assert below["decision_rule"]["amount_missing_disposition"] == "suppress"
    assert below["decision_rule"]["unknown_form_disposition"] == "suppress"
    assert below["decision_rule"]["conversion_failure_policy"] == "release_block"
    assert missing["evaluation_status"] == "amount_unknown"
    assert missing["consumer_disposition"] == "suppress"


def test_unauthored_floor_unknown_form_and_amount_default_to_suppress():
    enricher = SupplementEnricherV3()
    floor = {
        "value": 1000,
        "unit": "mg",
        "basis": "per_day",
        "form_scope": ["nicotinic acid"],
    }

    unknown_form = enricher._evaluate_min_effective_dose_decision(
        floor,
        {
            "quantity": 20,
            "unit": "mg",
            "matched_form": "niacin",
            "form_id": "niacin_unspecified",
        },
        1.0,
        "caution",
    )
    missing_amount = enricher._evaluate_min_effective_dose_decision(
        floor,
        {
            "unit": "mg",
            "matched_form": "nicotinic acid",
            "form_id": "nicotinic_acid",
        },
        1.0,
        "caution",
    )

    assert unknown_form["evaluation_status"] == "form_unknown"
    assert unknown_form["consumer_disposition"] == "suppress"
    assert missing_amount["evaluation_status"] == "amount_unknown"
    assert missing_amount["consumer_disposition"] == "suppress"


def test_engineering_conversion_failure_is_suppressed_and_blocks_release():
    severity, result = _evaluate(
        {
            "quantity": 20,
            "unit": "mg NE",
            "name": "Vitamin D3",
            "standard_name": "Vitamin D3 (Cholecalciferol)",
        }
    )

    assert severity == "monitor"
    assert result["evaluation_status"] == "conversion_error"
    assert result["consumer_disposition"] == "suppress"
    assert result["release_blocking"] is True
    assert result["conversion_error"] == "no_conversion_rule"


def test_unauthored_engineering_conversion_failure_still_blocks_release():
    enricher = SupplementEnricherV3()
    threshold = _vitamin_d_threshold()
    threshold.pop("conversion_failure_policy")

    _severity, result = enricher._evaluate_dose_thresholds_for_target(
        [threshold],
        "condition",
        "heart_disease",
        {
            "quantity": 20,
            "unit": "mg NE",
            "name": "Vitamin D3",
            "standard_name": "Vitamin D3 (Cholecalciferol)",
        },
        1.0,
        "monitor",
    )

    assert result["evaluation_status"] == "conversion_error"
    assert result["consumer_disposition"] == "suppress"
    assert result["release_blocking"] is True


def test_missing_specialized_marker_is_unknown_exposure_not_engineering_error():
    enricher = SupplementEnricherV3()
    threshold = {
        "scope": "condition",
        "target_id": "liver_disease",
        "basis": "per_day",
        "comparator": ">=",
        "value": 800,
        "unit": "mg EGCG",
        "severity_if_met": "avoid",
        "severity_if_not_met": "monitor",
        "consumer_disposition_if_met": "block",
        "consumer_disposition_if_not_met": "suppress",
        "conversion_failure_policy": "release_block",
    }

    _severity, result = enricher._evaluate_dose_thresholds_for_target(
        [threshold],
        "condition",
        "liver_disease",
        {
            "canonical_id": "green_tea_extract",
            "quantity": 800,
            "unit": "mg",
            "name": "Green Tea Extract",
            "standard_name": "Green Tea Extract",
        },
        1.0,
        "monitor",
    )

    assert result["evaluation_status"] == "amount_unknown"
    assert result["consumer_disposition"] == "suppress"
    assert result["release_blocking"] is False


def test_explicit_marker_identity_can_be_compared_in_marker_units():
    enricher = SupplementEnricherV3()
    threshold = {
        "scope": "condition",
        "target_id": "bleeding_disorders",
        "basis": "per_day",
        "comparator": ">",
        "value": 100,
        "unit": "mg andrographolide",
        "severity_if_met": "avoid",
        "severity_if_not_met": "monitor",
    }

    severity, result = enricher._evaluate_dose_thresholds_for_target(
        [threshold],
        "condition",
        "bleeding_disorders",
        {
            "canonical_id": "andrographolide",
            "quantity": 120,
            "unit": "mg",
            "name": "Andrographolide",
            "standard_name": "Andrographolide",
        },
        1.0,
        "monitor",
    )

    assert severity == "avoid"
    assert result["evaluation_status"] == "above_threshold"
    assert result["consumer_disposition"] == "block"
    assert result["dose_evaluation"]["converted_amount"] == 120.0
    assert result["dose_evaluation"]["conversion_method"] == "explicit_marker"


def test_vitamin_a_reverse_conversion_preserves_rae_semantics_and_form():
    converter = UnitConverter()

    result = converter.convert_nutrient(
        nutrient="Vitamin A",
        amount=3000,
        from_unit="mcg RAE",
        to_unit="IU",
        ingredient_name="Vitamin A as retinyl palmitate",
    )

    assert result.success is True
    assert result.converted_value == pytest.approx(9990.0)
    assert result.converted_unit == "IU"
    assert result.conversion_rule_id == "vitamin_a_retinol"


def test_preformed_vitamin_a_label_mcg_is_interpreted_as_rae():
    """DSLD can omit ``RAE`` from a preformed-vitamin-A label unit.

    A confirmed retinyl form makes the FDA Nutrition Facts convention
    unambiguous: bare ``mcg`` represents mcg RAE, not mass of retinyl ester.
    """
    converter = UnitConverter()

    result = converter.convert_nutrient(
        nutrient="Vitamin A",
        amount=3000,
        from_unit="mcg",
        to_unit="IU",
        ingredient_name="Vitamin A as retinyl palmitate",
    )

    assert result.success is True
    assert result.converted_value == pytest.approx(9990.0)
    assert result.converted_unit == "IU"
    assert result.conversion_rule_id == "vitamin_a_retinol"


def test_vitamin_d_generic_name_uses_confirmed_d2_form_for_conversion_trace():
    converter = UnitConverter()

    result = converter.convert_nutrient(
        nutrient="Vitamin D",
        amount=20,
        from_unit="mcg",
        to_unit="IU",
        ingredient_name="Vitamin D as ergocalciferol (D2)",
    )

    assert result.success is True
    assert result.converted_value == pytest.approx(800.0)
    assert result.conversion_rule_id == "vitamin_d2"


def test_unknown_vitamin_e_form_is_clinical_uncertainty_not_converter_defect():
    enricher = SupplementEnricherV3()
    threshold = {
        "scope": "condition",
        "target_id": "pregnancy",
        "basis": "per_day",
        "comparator": ">",
        "value": 1000,
        "unit": "mg",
        "severity_if_met": "avoid",
        "severity_if_not_met": "monitor",
        "consumer_disposition_if_met": "block",
        "consumer_disposition_if_not_met": "suppress",
        "amount_missing_disposition": "suppress",
        "unknown_form_disposition": "suppress",
        "conversion_failure_policy": "release_block",
    }

    _severity, decision = enricher._evaluate_dose_thresholds_for_target(
        [threshold],
        "condition",
        "pregnancy",
        {
            "quantity": 400,
            "unit": "IU",
            "name": "Vitamin E",
            "standard_name": "Vitamin E",
        },
        1.0,
        "monitor",
    )

    assert decision["evaluation_status"] == "form_unknown"
    assert decision["consumer_disposition"] == "suppress"
    assert decision["release_blocking"] is False


def test_vitamin_e_floor_uses_resolved_form_for_iu_conversion():
    enricher = SupplementEnricherV3()
    floor = {
        "value": 180,
        "unit": "mg",
        "basis": "per_day",
        "consumer_disposition_if_met": "review",
        "consumer_disposition_if_not_met": "suppress",
        "amount_missing_disposition": "suppress",
        "unknown_form_disposition": "suppress",
    }

    decision = enricher._evaluate_min_effective_dose_decision(
        floor,
        {
            "quantity": 400,
            "unit": "IU",
            "name": "Vitamin E",
            "standard_name": "Vitamin E",
            "matched_form": "dl-alpha-tocopheryl acetate",
            "form_id": "dl-alpha-tocopheryl acetate",
        },
        1.0,
        "caution",
    )

    assert decision["evaluation_status"] == "above_threshold"
    assert decision["release_blocking"] is False
    assert decision["dose_evaluation"]["converted_amount"] == pytest.approx(180.0)
    assert decision["dose_evaluation"]["conversion_method"] == "vitamin_e_dl_alpha_tocopherol"


def test_conversion_failure_emits_the_threshold_contract():
    _severity, decision = _evaluate(
        {
            "quantity": 20,
            "unit": "mg NE",
            "name": "Vitamin D3",
            "standard_name": "Vitamin D3 (Cholecalciferol)",
        }
    )

    assert decision["evaluation_status"] == "conversion_error"
    assert decision["decision_rule"] == {
        "basis": "per_day",
        "comparator": ">",
        "threshold": 4000.0,
        "threshold_unit": "iu",
        "consumer_disposition_if_met": "review",
        "consumer_disposition_if_not_met": "suppress",
        "amount_missing_disposition": "good_to_know",
        "unknown_form_disposition": "suppress",
        "conversion_failure_policy": "release_block",
    }


def test_semantic_units_are_not_collapsed_into_plain_mass():
    enricher = SupplementEnricherV3()

    assert enricher._normalize_threshold_unit("mcg RAE") == "mcg rae"
    assert enricher._normalize_threshold_unit("mcg DFE") == "mcg dfe"
    assert enricher._normalize_threshold_unit("mg NE") == "mg ne"

    # An equivalence unit is bridged by its authored factor, never by dropping
    # the qualifier: 400 mcg DFE is 235.2 mcg folic acid (1/1.7), not 400.
    converted, reason, _method = enricher._convert_amount_to_target_unit_with_evidence(
        amount=400,
        from_unit="mcg DFE",
        target_unit="mcg",
        ingredient_name="Folic Acid",
        standard_name="Folate",
    )
    assert reason is None
    assert converted == pytest.approx(235.2)

    # An equivalence unit carried by the wrong nutrient stays a contract gap.
    converted, reason, _method = enricher._convert_amount_to_target_unit_with_evidence(
        amount=20,
        from_unit="mg NE",
        target_unit="mg",
        ingredient_name="Vitamin D3",
        standard_name="Vitamin D3 (Cholecalciferol)",
    )
    assert converted is None
    assert reason == "no_conversion_rule"


def test_niacin_equivalents_bridge_to_mg_through_an_authored_factor():
    """``mg NE`` -> ``mg`` is data, not a code-level unit collapse.

    unit_conversions.json authors ``mg_ne_to_mg: 1.0`` for niacin (NIH ODS):
    preformed niacin is 1:1 with its equivalents, and the 60:1 tryptophan
    factor applies to dietary protein, never to a niacin ingredient row.
    """
    enricher = SupplementEnricherV3()

    converted, reason, method = enricher._convert_amount_to_target_unit_with_evidence(
        amount=20,
        from_unit="mg NE",
        target_unit="mg",
        ingredient_name="Niacin",
        standard_name="Niacin (Vitamin B3)",
    )
    assert (converted, reason) == (20.0, None)
    assert method == "niacin"


def test_specialized_marker_analysis_requires_explicit_standardization_math():
    enricher = SupplementEnricherV3()
    source = {
        "canonical_id": "turmeric",
        "raw_source_text": "Turmeric Extract 500 mg",
        "quantity": 500,
        "unit": "mg",
        "delivers_markers": [{
            "marker_canonical_id": "curcumin",
            "estimated_dose_mg": None,
            "estimation_method": "none",
            "confidence_scale": 0.0,
        }],
    }
    assert enricher._derived_marker_interaction_rows(source) == []

    source["raw_source_text"] = "Turmeric Extract 500 mg standardized to 95% curcuminoids"
    source["delivers_markers"][0].update({
        "estimated_dose_mg": 475.0,
        "estimation_method": "standardization_pct",
        "confidence_scale": 1.0,
        "basis": "Label declares 95% standardization x 500 mg",
    })
    rows = enricher._derived_marker_interaction_rows(source)

    assert rows == [{
        "canonical_id": "curcumin",
        "canonical_source_db": "ingredient_quality_map",
        "raw_source_text": "Curcumin (from Turmeric Extract 500 mg standardized to 95% curcuminoids)",
        "name": "Curcumin",
        "standard_name": "Curcumin",
        "quantity": 475.0,
        "unit": "mg",
        "unit_normalized": "mg",
        "dose_source": "label_standardization",
        "marker_derivation": {
            "source_canonical_id": "turmeric",
            "estimation_method": "standardization_pct",
            "basis": "Label declares 95% standardization x 500 mg",
        },
        "analysis_only": True,
    }]


def test_marker_threshold_uses_egcg_standardization_not_total_extract_mass():
    enricher = SupplementEnricherV3()
    ingredient = {
        "canonical_id": "green_tea_extract",
        "raw_source_text": "Green Tea Extract standardized to 50% EGCG",
        "name": "Green Tea Extract",
        "standard_name": "Green Tea Extract",
        "quantity": 800,
        "unit": "mg",
        "unit_normalized": "mg",
    }
    ingredient["delivers_markers"] = enricher._compute_delivers_markers(ingredient)
    threshold = {
        "scope": "condition",
        "target_id": "liver_disease",
        "basis": "per_day",
        "comparator": ">=",
        "value": 800,
        "unit": "mg EGCG",
        "severity_if_met": "avoid",
        "severity_if_not_met": "monitor",
        "consumer_disposition_if_met": "block",
        "consumer_disposition_if_not_met": "suppress",
        "conversion_failure_policy": "release_block",
    }

    severity, decision = enricher._evaluate_dose_thresholds_for_target(
        [threshold],
        "condition",
        "liver_disease",
        ingredient,
        1.0,
        "monitor",
    )

    assert severity == "monitor"
    assert decision["evaluation_status"] == "below_threshold"
    assert decision["consumer_disposition"] == "suppress"
    assert decision["dose_evaluation"]["converted_amount"] == 400.0
    assert decision["dose_evaluation"]["threshold_unit"] == "mg egcg"
    assert decision["dose_evaluation"]["conversion_method"] == "label_standardization"
