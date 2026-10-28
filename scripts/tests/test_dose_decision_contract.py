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
            "form_match_status": "mapped",
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
            "form_match_status": "mapped",
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
            "form_match_status": "n/a",
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
            "form_match_status": "mapped",
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
    assert result.converted_value == pytest.approx(10000.0)
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
    assert result.converted_value == pytest.approx(10000.0)
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
            # 1,200 IU is 804 mg natural or 1,080 mg all-rac: the form decides.
            "quantity": 1200,
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


def _vitamin_e_pregnancy_ul_decision(ingredient: dict, servings: float = 1.0):
    """The production pregnancy UL rule, not a test copy of its threshold."""
    import json

    rules_path = Path(__file__).parent.parent / "data" / "ingredient_interaction_rules.json"
    rules = json.loads(rules_path.read_text())["interaction_rules"]
    rule = next(r for r in rules if r["id"] == "RULE_IQM_VITAMIN_E_PREGNANCY_EXCESS")
    return SupplementEnricherV3()._evaluate_dose_thresholds_for_target(
        rule["dose_thresholds"],
        "condition",
        "pregnancy",
        {"name": "Vitamin E", "standard_name": "Vitamin E", **ingredient},
        servings,
        "monitor",
    )


@pytest.mark.parametrize(
    ("ingredient", "status", "severity", "disposition"),
    [
        # Above the UL in every form: 3,000 IU >= 2,010 mg (natural, the lowest).
        ({"quantity": 3000, "unit": "IU"}, "above_threshold", "avoid", "block"),
        # Within the UL in every form: 400 IU <= 360 mg (all-rac, the highest).
        ({"quantity": 400, "unit": "IU"}, "below_threshold", "monitor", "suppress"),
        # The UL counts all-rac mass: 1,500 IU synthetic is 1,350 mg, not 675.
        (
            {"quantity": 1500, "unit": "IU", "matched_form": "dl-alpha-tocopheryl acetate"},
            "above_threshold", "avoid", "block",
        ),
        # Natural activity and UL mass coincide: 1,400 IU is 938 mg.
        (
            {"quantity": 1400, "unit": "IU", "matched_form": "d-alpha-tocopherol"},
            "below_threshold", "monitor", "suppress",
        ),
        # Straddling the UL (871 to 1,170 mg) is unresolved: review, not silence.
        ({"quantity": 1300, "unit": "IU"}, "form_unknown", "monitor", "review"),
        # 1,800 IU exceeds both ODS equivalents (1,500 IU natural, 1,100 IU
        # synthetic): 1,206 to 1,620 mg, above the UL whatever the form.
        ({"quantity": 1800, "unit": "IU"}, "above_threshold", "avoid", "block"),
        # A parent row in mg declares activity; its UL mass is 1x to 2x by form.
        ({"quantity": 671, "unit": "mg"}, "form_unknown", "monitor", "review"),
        ({"quantity": 1072, "unit": "mg"}, "above_threshold", "avoid", "block"),
        ({"quantity": 400, "unit": "mg"}, "below_threshold", "monitor", "suppress"),
        # A family mass bounds its alpha-tocopherol from above (it may hold none).
        (
            {"name": "Mixed Tocopherols", "quantity": 441, "unit": "mg", "matched_form": "mixed tocopherols"},
            "below_threshold", "monitor", "suppress",
        ),
        (
            {"name": "Mixed Tocopherols", "quantity": 1200, "unit": "mg", "matched_form": "mixed tocopherols"},
            "form_unknown", "monitor", "review",
        ),
        # The authored comparator is ">": exactly the UL is within it.
        (
            {"quantity": 1000, "unit": "mg", "matched_form": "d-alpha-tocopherol"},
            "below_threshold", "monitor", "suppress",
        ),
        (
            {"quantity": 1001, "unit": "mg", "matched_form": "d-alpha-tocopherol"},
            "above_threshold", "avoid", "block",
        ),
    ],
)
def test_vitamin_e_pregnancy_ul_compares_ul_exposure_bounds(
    ingredient, status, severity, disposition
):
    """NIH ODS: the UL covers all eight stereoisomers (1,100 IU synthetic or
    1,500 IU natural). An outcome every possible form agrees on is not
    uncertain; only a range straddling the UL is form_unknown, which the rule
    authors as review (Dr Pham, 2026-10-28).
    https://ods.od.nih.gov/factsheets/VitaminE-HealthProfessional/
    """
    selected, decision = _vitamin_e_pregnancy_ul_decision(ingredient)

    assert decision["evaluation_status"] == status
    assert selected == severity
    assert decision["consumer_disposition"] == disposition
    assert decision["release_blocking"] is False


@pytest.mark.parametrize(
    ("decide", "expected_amount", "method"),
    [
        # Unknown 3,000 IU vitamin E: at least 2,010 mg (natural), not 2,700.
        (lambda: _vitamin_e_pregnancy_ul_decision({"quantity": 3000, "unit": "IU"}), 2010.0, "ul_exposure_bound"),
        # Synthetic 1,500 IU has one UL mass: 1,350 mg.
        (
            lambda: _vitamin_e_pregnancy_ul_decision(
                {"quantity": 1500, "unit": "IU", "matched_form": "dl-alpha-tocopheryl acetate"}
            ),
            1350.0, "ul_exposure",
        ),
    ],
)
def test_exported_amount_is_the_proven_minimum(decide, expected_amount, method):
    """build_final_db exports converted_amount as evaluated_daily_amount and the
    app's stack summer adds it across products, so a form range exports only
    what every form guarantees."""
    _selected, decision = decide()

    assert decision["dose_evaluation"]["converted_amount"] == pytest.approx(expected_amount)
    assert decision["dose_evaluation"]["conversion_method"] == method


def test_unspecified_vitamin_a_exports_no_preformed_amount():
    _selected, decision = SupplementEnricherV3()._evaluate_dose_thresholds_for_target(
        _rule("RULE_IQM_VITAMIN_A_PREGNANCY_DOSE")["dose_thresholds"],
        "condition",
        "pregnancy",
        {"name": "Vitamin A", "standard_name": "Vitamin A", "quantity": 2000, "unit": "mcg"},
        1.0,
        "caution",
    )

    assert decision["evaluation_status"] == "below_threshold"
    # The stack summer skips a zero, so it never sums this row as retinol.
    assert decision["dose_evaluation"]["converted_amount"] == 0.0


def test_vitamin_e_pregnancy_ul_uses_the_directed_daily_exposure():
    # Two 800 IU servings: 1,072 to 1,440 mg/day, above the UL in every form.
    selected, decision = _vitamin_e_pregnancy_ul_decision(
        {"quantity": 800, "unit": "IU"}, servings=2.0
    )

    assert decision["evaluation_status"] == "above_threshold"
    assert selected == "avoid"
    assert decision["consumer_disposition"] == "block"


def _rule(rule_id: str) -> dict:
    import json

    rules_path = Path(__file__).parent.parent / "data" / "ingredient_interaction_rules.json"
    rules = json.loads(rules_path.read_text())["interaction_rules"]
    return next(r for r in rules if r["id"] == rule_id)


@pytest.mark.parametrize(
    ("target", "ingredient", "status", "severity", "disposition"),
    [
        # Unspecified form: the preformed share is unknown, never assumed 100%.
        ("pregnancy", {"quantity": 9000, "unit": "mcg"}, "form_unknown", "caution", "review"),
        ("pregnancy", {"quantity": 25000, "unit": "IU"}, "form_unknown", "caution", "review"),
        ("ttc", {"quantity": 9000, "unit": "mcg"}, "form_unknown", "caution", "review"),
        # Within the UL even if all of it were retinol (6,660 IU; 1.5 mg 4,995 IU).
        ("pregnancy", {"quantity": 2000, "unit": "mcg"}, "below_threshold", "caution", "suppress"),
        ("pregnancy", {"quantity": 1.5, "unit": "mg"}, "below_threshold", "caution", "suppress"),
        # Confirmed preformed vitamin A keeps the authored serious warning.
        (
            "pregnancy",
            {"quantity": 9000, "unit": "mcg", "matched_form": "retinyl palmitate"},
            "above_threshold", "contraindicated", "block",
        ),
        # The authored comparator is ">": exactly 10,000 IU is within it.
        (
            "pregnancy",
            {"quantity": 10000, "unit": "IU", "matched_form": "retinyl palmitate"},
            "below_threshold", "caution", "suppress",
        ),
        (
            "pregnancy",
            {"quantity": 10001, "unit": "IU", "matched_form": "retinyl palmitate"},
            "above_threshold", "contraindicated", "block",
        ),
    ],
)
def test_vitamin_a_pregnancy_ul_counts_only_preformed_vitamin_a(
    target, ingredient, status, severity, disposition
):
    """NIH ODS: the 3,000 mcg RAE (10,000 IU) UL applies to preformed vitamin A
    only. An unspecified form is unresolved (review, Dr Pham 2026-10-28), not
    silence and not a confirmed retinol exceedance.
    https://ods.od.nih.gov/factsheets/VitaminA-HealthProfessional/
    """
    selected, decision = SupplementEnricherV3()._evaluate_dose_thresholds_for_target(
        _rule("RULE_IQM_VITAMIN_A_PREGNANCY_DOSE")["dose_thresholds"],
        "condition",
        target,
        {"name": "Vitamin A", "standard_name": "Vitamin A", **ingredient},
        1.0,
        "caution",
    )

    assert decision["evaluation_status"] == status
    assert selected == severity
    assert decision["consumer_disposition"] == disposition


def test_unspecified_vitamin_a_reaches_only_preformed_rules():
    """The threshold evaluator bounds unspecified vitamin A as 0-100% preformed.
    That is only right for preformed-UL rules: a rule on total vitamin A
    activity or beta-carotene must not reach an unspecified row."""
    import json

    rules_path = Path(__file__).parent.parent / "data" / "ingredient_interaction_rules.json"
    rules = json.loads(rules_path.read_text())["interaction_rules"]
    enricher = SupplementEnricherV3()
    unspecified = {"form_id": "vitamin a (unspecified)", "form_match_status": "mapped"}
    reached = {
        rule["id"]
        for rule in rules
        if (rule.get("subject_ref") or {}).get("canonical_id") == "vitamin_a"
        and rule.get("dose_thresholds")
        and enricher._interaction_rule_applies(rule, unspecified)
    }

    assert reached == {"RULE_IQM_VITAMIN_A_PREGNANCY_DOSE"}
    beta_carotene = {"form_id": "beta-carotene synthetic", "form_match_status": "mapped"}
    assert not enricher._interaction_rule_applies(
        _rule("RULE_IQM_VITAMIN_A_PREGNANCY_DOSE"), beta_carotene
    )


def _bitter_orange_pregnancy_decision(ingredient: dict):
    rule = _rule("RULE_BANNED_BITTER_ORANGE_PREGNANCY")
    return SupplementEnricherV3()._evaluate_dose_thresholds_for_target(
        rule["dose_thresholds"],
        "condition",
        "pregnancy",
        {"name": "Bitter Orange", "standard_name": "Bitter Orange", **ingredient},
        1.0,
        "avoid",
        materiality=rule["condition_rules"][0].get("materiality"),
    )


def test_bitter_orange_extract_mass_is_not_a_synephrine_dose():
    """200 mg of extract is not 200 mg of synephrine (NCCIH: labeled synephrine
    content is often inaccurate). The 3 mg threshold needs a disclosed
    synephrine amount; without one the pregnancy warning stays hard (avoid,
    block) and is not reported as a confirmed exceedance."""
    selected, decision = _bitter_orange_pregnancy_decision({"quantity": 200, "unit": "mg"})

    assert decision["evaluation_status"] == "amount_unknown"
    assert decision["matched_threshold"] is not True
    assert selected == "avoid"
    assert decision["consumer_disposition"] == "block"


@pytest.mark.parametrize(
    ("ingredient", "status", "severity"),
    [
        # 6% synephrine standardization of 200 mg: 12 mg, over the threshold.
        (
            {"quantity": 200, "unit": "mg", "delivers_markers": [{
                "marker_canonical_id": "synephrine",
                "estimation_method": "standardization_pct",
                "estimated_dose_mg": 12.0,
            }]},
            "above_threshold", "contraindicated",
        ),
        # A label row that is synephrine itself is explicit exposure.
        ({"quantity": 3, "unit": "mg", "canonical_id": "synephrine"}, "above_threshold", "contraindicated"),
        ({"quantity": 2, "unit": "mg", "canonical_id": "synephrine"}, "below_threshold", "avoid"),
    ],
)
def test_bitter_orange_disclosed_synephrine_meets_the_threshold(ingredient, status, severity):
    selected, decision = _bitter_orange_pregnancy_decision(ingredient)

    assert decision["evaluation_status"] == status
    assert selected == severity
    assert decision["consumer_disposition"] == "block"


def test_both_bitter_orange_pregnancy_rules_stay_hard():
    """The second rule's shared fallback must not be what keeps a pregnant user
    warned: each rule's own pregnancy outcome is hard on its own."""
    fallback = _rule("RULE_BANNED_BITTER_ORANGE_HYPERTENSION")["pregnancy_lactation"]
    explicit = _rule("RULE_BANNED_BITTER_ORANGE_PREGNANCY")["condition_rules"][0]

    assert fallback["pregnancy_category"] in {"avoid", "contraindicated"}
    assert explicit["severity"] in {"avoid", "contraindicated"}


def test_vitamin_e_ul_exposure_amount_is_the_upper_bound():
    converter = UnitConverter()
    unknown = converter.convert_nutrient("Vitamin E", 1000, "IU", ingredient_name="Vitamin E")
    synthetic = converter.convert_nutrient(
        "Vitamin E", 1000, "IU", ingredient_name="Vitamin E dl-alpha-tocopheryl acetate"
    )

    assert converter._ul_exposure_bounds(unknown, measured_name="Vitamin E") == pytest.approx((670.0, 900.0))
    assert converter._ul_exposure_amount(unknown, measured_name="Vitamin E") == pytest.approx(900.0)
    assert converter._ul_exposure_bounds(synthetic, measured_name="Vitamin E") == pytest.approx((900.0, 900.0))


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
            "form_match_status": "mapped",
        },
        1.0,
        "caution",
    )

    assert decision["evaluation_status"] == "above_threshold"
    assert decision["release_blocking"] is False
    assert decision["dose_evaluation"]["converted_amount"] == pytest.approx(180.0)
    assert decision["dose_evaluation"]["conversion_method"] == "vitamin_e_dl_alpha_tocopherol"


@pytest.mark.parametrize("label", ["Mixed Carotenoids", "Carotenoids"])
def test_generic_carotenoid_mix_is_form_unknown_not_beta_carotene(label):
    """A carotenoid-family mass label cannot establish Vitamin A activity.

    Do not borrow beta-carotene's conversion factor for a label that does not
    identify beta-carotene or state RAE/IU.  Pregnancy logic must preserve
    that uncertainty rather than release-blocking an impossible conversion.
    """
    enricher = SupplementEnricherV3()
    threshold = {
        "scope": "condition",
        "target_id": "pregnancy",
        "basis": "per_day",
        "comparator": ">",
        "value": 10_000,
        "unit": "IU",
        "severity_if_met": "review",
        "severity_if_not_met": "monitor",
        "unknown_form_disposition": "suppress",
    }

    _severity, decision = enricher._evaluate_dose_thresholds_for_target(
        [threshold],
        "condition",
        "pregnancy",
        {
            "quantity": 12,
            "unit": "mg",
            "name": label,
            "raw_source_text": label,
            "standard_name": "Vitamin A",
        },
        1.0,
        "caution",
    )

    assert decision["evaluation_status"] == "form_unknown"
    assert decision["consumer_disposition"] == "suppress"
    assert decision["release_blocking"] is False


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

@pytest.mark.parametrize('name', ['D-Beta Tocopherol', 'D-Gamma Tocopherol', 'D-Delta Tocopherol', 'Mixed Tocopherols', 'Tocotrienols', 'D-Alpha-Tocotrienol', 'RRR-Alpha Tocotrienol', 'DL-Alpha-Tocotrienol'])
@pytest.mark.parametrize('amount,unit', [(300, 'mg'), (1500, 'mg'), (1.5, 'g'), (1500000, 'mcg')])
def test_nonalpha_physical_mass_cannot_meet_alpha_tocopherol_threshold(name, amount, unit):
    enricher = SupplementEnricherV3()
    thresholds = [{
        'scope': 'condition', 'target_id': 'pregnancy', 'basis': 'per_day',
        'comparator': '>', 'value': 1000, 'unit': 'mg',
        'severity_if_met': 'avoid', 'severity_if_not_met': 'monitor',
        'unknown_form_disposition': 'suppress',
    }]
    _, decision = enricher._evaluate_dose_thresholds_for_target(
        thresholds, 'condition', 'pregnancy',
        {'name': name, 'standard_name': 'Vitamin E', 'canonical_id': 'vitamin_e',
         'quantity': amount, 'unit': unit, 'matched_form': 'mixed tocopherols'},
        1.0, 'monitor',
    )
    # The mass bounds alpha-tocopherol from above, never from below: within
    # the limit it is assessed within it; above it the alpha share decides.
    within = amount * {'mg': 1, 'g': 1000, 'mcg': 0.001}[unit] <= 1000
    assert decision['evaluation_status'] == ('below_threshold' if within else 'form_unknown')
    assert decision['consumer_disposition'] == 'suppress'
    assert decision['matched_threshold'] is False
    assert decision['release_blocking'] is False

@pytest.mark.parametrize('name', ['Vitamin E', 'D-Alpha Tocopherol', 'DL-Alpha Tocopherol'])
def test_declared_alpha_activity_retains_mass_threshold_comparison(name):
    enricher = SupplementEnricherV3()
    value, reason, _ = enricher._convert_amount_to_target_unit_with_evidence(
        amount=1500, from_unit='mg', target_unit='mg',
        ingredient_name=name, standard_name='Vitamin E',
    )
    assert value == 1500
    assert reason is None


@pytest.mark.parametrize("target", ["pregnancy", "ttc"])
@pytest.mark.parametrize("amount,status", [(3000, "below_threshold"), (3001, "above_threshold"), (3003, "above_threshold")])
def test_preformed_vitamin_a_threshold_preserves_exact_mcg_boundary(target, amount, status):
    selected, decision = SupplementEnricherV3()._evaluate_dose_thresholds_for_target(
        _rule("RULE_IQM_VITAMIN_A_PREGNANCY_DOSE")["dose_thresholds"],
        "condition", target,
        {"name": "Vitamin A", "standard_name": "Vitamin A", "quantity": amount,
         "unit": "mcg", "matched_form": "retinyl palmitate"},
        1.0, "caution",
    )
    assert decision["evaluation_status"] == status
    assert decision["consumer_disposition"] == ("suppress" if amount == 3000 else "block")
    assert selected == ("caution" if amount == 3000 else "contraindicated" if target == "pregnancy" else "avoid")


@pytest.mark.parametrize("amount,status,disposition", [(3000, "below_threshold", "suppress"), (3001, "form_unknown", "review")])
def test_unknown_vitamin_a_boundary_never_assumes_a_retinol_fraction(amount, status, disposition):
    _selected, decision = SupplementEnricherV3()._evaluate_dose_thresholds_for_target(
        _rule("RULE_IQM_VITAMIN_A_PREGNANCY_DOSE")["dose_thresholds"],
        "condition", "pregnancy",
        {"name": "Vitamin A", "standard_name": "Vitamin A", "quantity": amount, "unit": "mcg"},
        1.0, "caution",
    )
    assert decision["evaluation_status"] == status
    assert decision["consumer_disposition"] == disposition
