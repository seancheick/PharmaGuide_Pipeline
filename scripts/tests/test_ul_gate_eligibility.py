"""UL verdict eligibility must follow typed dose evidence, not a DV shortcut.

Daily Value remains high-confidence evidence that a row declares the nutrient
amount. A source UNII that exactly matches the canonical IQM parent's UNII is
also direct-identity evidence. A form may additionally participate when the
clinical reference explicitly places that exact form inside the nutrient UL's
scope; all other compound/form rows remain conservatively ineligible.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from enrich_supplements_v3 import SupplementEnricherV3


@pytest.fixture(scope="module")
def enricher() -> SupplementEnricherV3:
    return SupplementEnricherV3()


def _mag(active):
    return {"activeIngredients": active, "inactiveIngredients": []}


def test_compound_mass_row_flag_is_gate_ineligible(enricher):
    # Zinc Picolinate 200 mg with NO dailyValue -> compound mass; 200 vs 40 mg UL.
    product = _mag([
        {"name": "Zinc Picolinate", "standardName": "Zinc", "canonical_id": "zinc",
         "canonical_source_db": "ingredient_quality_map",
         "quantity": 200, "unit": "mg", "dailyValue": None},
    ])
    result = enricher._collect_rda_ul_data(product, min_servings_per_day=1, max_servings_per_day=1)
    flags = [f for f in result["safety_flags"] if "zinc" in (f.get("nutrient") or "").lower()]
    assert flags, "expected an over-UL flag for 200 mg zinc vs a 40 mg UL"
    assert flags[0].get("ul_gate_eligible") is False
    assert flags[0].get("ul_gate_ineligible_reason") == "compound_mass_not_elemental"
    assert flags[0].get("ul_exposure_basis") == "compound_or_form_mass"
    assert result["has_over_ul"] is False


def test_p5p_is_included_in_total_vitamin_b6_ul_exposure(enricher):
    """P5P is a vitamin B6 vitamer, not an unrelated compound mass.

    NIH ODS defines pyridoxal 5'-phosphate as one of the compounds with
    vitamin B6 activity and applies the US adult UL to total vitamin B6
    intake.  A separately disclosed P5P row must therefore add to another
    vitamin B6 row instead of leaving the product's dose readiness unresolved.
    """
    product = _mag([
        {
            "name": "Vitamin B6",
            "standardName": "Vitamin B6",
            "canonical_id": "vitamin_b6_pyridoxine",
            "canonical_source_db": "ingredient_quality_map",
            "quantity": 90,
            "unit": "mg",
            "dailyValue": 5294,
        },
        {
            "name": "Pyridoxal 5-Phosphate",
            "standardName": "Vitamin B6 (Pyridoxine)",
            "canonical_id": "vitamin_b6_pyridoxine",
            "canonical_source_db": "ingredient_quality_map",
            "raw_taxonomy": {"ingredientGroup": "Vitamin B6"},
            "quantity": 20,
            "unit": "mg",
            "dailyValue": None,
        },
    ])

    result = enricher._collect_rda_ul_data(
        product,
        min_servings_per_day=1,
        max_servings_per_day=1,
    )
    p5p = next(
        row
        for row in result["dose_assessments"]
        if row["ingredient"] == "Pyridoxal 5-Phosphate"
    )
    p5p_adequacy = next(
        row
        for row in result["adequacy_results"]
        if row["nutrient"] == "Vitamin B6 (Pyridoxine)"
    )

    assert p5p["ul_gate_eligible"] is True
    assert p5p_adequacy["ul_exposure_basis"] == (
        "ul_scoped_form_named_substance_amount"
    )
    assert p5p["ul_assessment_status"] == "assessed_within_limit"
    assert p5p["readiness"] == "complete"
    assert result["has_over_ul"] is True
    aggregate = next(
        flag
        for flag in result["safety_flags"]
        if flag.get("aggregation") == "canonical_sum"
    )
    assert aggregate["canonical_id"] == "vitamin_b6_pyridoxine"
    assert aggregate["amount"] == pytest.approx(110.0)


@pytest.mark.parametrize(
    ("row", "expected_pct_ul"),
    [
        (
            {
                "name": "Boron Glycinate",
                "standardName": "Boron",
                "canonical_id": "boron",
                "canonical_source_db": "ingredient_quality_map",
                "quantity": 3,
                "unit": "mg",
                "dailyValue": None,
            },
            15.0,
        ),
        (
            {
                "name": "Retinyl Acetate",
                "standardName": "Vitamin A",
                "canonical_id": "vitamin_a",
                "canonical_source_db": "ingredient_quality_map",
                "quantity": 600,
                "unit": "mcg",
                "dailyValue": None,
            },
            20.0,
        ),
    ],
)
def test_single_compound_mass_below_ul_uses_conservative_upper_bound(
    enricher,
    row,
    expected_pct_ul,
):
    """A whole compound cannot contain more active moiety than its mass.

    This establishes a safety upper bound only. It must not turn the compound
    mass into an elemental dose or award adequacy credit.
    """
    result = enricher._collect_rda_ul_data(
        _mag([row]),
        min_servings_per_day=1,
        max_servings_per_day=1,
    )

    assessment = result["dose_assessments"][0]
    adequacy = result["adequacy_results"][0]
    assert assessment["reason_code"] == "worst_case_compound_mass_within_ul"
    assert assessment["ul_assessment_status"] == "assessed_within_limit"
    assert assessment["readiness"] == "complete"
    assert assessment["pct_ul"] == pytest.approx(expected_pct_ul)
    assert assessment["ul_gate_eligible"] is False
    assert adequacy["ul_assessment_basis"] == (
        "maximum_possible_active_moiety_exposure"
    )
    assert adequacy["scoring_eligible"] is False
    assert adequacy["pct_rda"] is None
    assert result["has_over_ul"] is False


def test_multiple_compound_rows_do_not_clear_on_individual_upper_bounds(enricher):
    product = _mag([
        {
            "name": "Zinc Picolinate",
            "standardName": "Zinc",
            "canonical_id": "zinc",
            "canonical_source_db": "ingredient_quality_map",
            "quantity": 30,
            "unit": "mg",
            "dailyValue": None,
        },
        {
            "name": "Zinc Citrate",
            "standardName": "Zinc",
            "canonical_id": "zinc",
            "canonical_source_db": "ingredient_quality_map",
            "quantity": 30,
            "unit": "mg",
            "dailyValue": None,
        },
    ])

    result = enricher._collect_rda_ul_data(
        product,
        min_servings_per_day=1,
        max_servings_per_day=1,
    )

    assert all(
        row["ul_assessment_status"] == "unresolved_compound_mass"
        for row in result["dose_assessments"]
    )
    assert all(
        row["readiness"] == "incomplete"
        for row in result["dose_assessments"]
    )


def test_p5p_form_and_parent_b6_total_within_ul_is_complete(enricher):
    product = _mag([
        {
            "name": "Vitamin B6",
            "standardName": "Vitamin B6",
            "canonical_id": "vitamin_b6_pyridoxine",
            "canonical_source_db": "ingredient_quality_map",
            "uniiCode": "KV2JZ1BI6Z",
            "quantity": 75,
            "unit": "mg",
            "dailyValue": 4412,
        },
        {
            "name": "Pyridoxal 5-Phosphate",
            "standardName": "Vitamin B6",
            "canonical_id": "vitamin_b6_pyridoxine",
            "canonical_source_db": "ingredient_quality_map",
            "uniiCode": "F06SGE49M6",
            "quantity": 6,
            "unit": "mg",
            "dailyValue": None,
        },
    ])

    result = enricher._collect_rda_ul_data(
        product,
        min_servings_per_day=1,
        max_servings_per_day=1,
    )
    compound = next(
        row
        for row in result["dose_assessments"]
        if row["ingredient"] == "Pyridoxal 5-Phosphate"
    )
    adequacy = next(
        row
        for row in result["adequacy_results"]
        if row.get("ul_exposure_basis")
        == "ul_scoped_form_named_substance_amount"
    )

    assert compound["ul_assessment_status"] == "assessed_within_limit"
    assert compound["readiness"] == "complete"
    assert adequacy["ul_exposure_basis"] == (
        "ul_scoped_form_named_substance_amount"
    )
    assert adequacy["scoring_eligible"] is True
    assert adequacy["pct_rda"] is not None
    assert result["has_over_ul"] is False


def test_elemental_dv_row_flag_is_gate_eligible(enricher):
    # Element-named Zinc 200 mg WITH a dailyValue -> elemental -> gate-eligible.
    product = _mag([
        {"name": "Zinc", "standardName": "Zinc", "canonical_id": "zinc",
         "canonical_source_db": "ingredient_quality_map",
         "quantity": 200, "unit": "mg", "dailyValue": 1818.0},
    ])
    result = enricher._collect_rda_ul_data(product, min_servings_per_day=1, max_servings_per_day=1)
    flags = [f for f in result["safety_flags"] if "zinc" in (f.get("nutrient") or "").lower()]
    assert flags, "expected an over-UL flag for 200 mg zinc"
    assert flags[0].get("ul_gate_eligible") is True
    assert flags[0].get("ul_exposure_basis") == "daily_value_confirmed_nutrient_amount"


@pytest.mark.parametrize("daily_value", [True, "1818", -1, float("nan"), float("inf")])
def test_malformed_daily_value_does_not_establish_ul_exposure(enricher, daily_value):
    product = _mag([
        {
            "name": "Zinc Picolinate",
            "standardName": "Zinc",
            "canonical_id": "zinc",
            "canonical_source_db": "ingredient_quality_map",
            "quantity": 200,
            "unit": "mg",
            "dailyValue": daily_value,
        },
    ])

    result = enricher._collect_rda_ul_data(
        product,
        min_servings_per_day=1,
        max_servings_per_day=1,
    )
    flag = next(
        flag
        for flag in result["safety_flags"]
        if "zinc" in (flag.get("nutrient") or "").lower()
    )

    assert flag["ul_gate_eligible"] is False
    assert flag["ul_exposure_basis"] == "compound_or_form_mass"


def test_parent_unii_row_without_daily_value_is_gate_eligible(enricher):
    # Live DSLD 13460 is one plain Niacin row with the canonical-parent UNII,
    # 1000 mg, and no DV. Its labelled amount is niacin itself, not a carrier
    # compound, so absence of DV must not suppress the clinical gate.
    product = _mag([
        {
            "name": "Niacin",
            "standardName": "Vitamin B3 (Niacin)",
            "canonical_id": "vitamin_b3_niacin",
            "canonical_source_db": "ingredient_quality_map",
            "uniiCode": "2679MF687A",
            "quantity": 1000,
            "unit": "mg",
            "dailyValue": None,
        },
    ])

    result = enricher._collect_rda_ul_data(
        product,
        min_servings_per_day=1,
        max_servings_per_day=1,
    )
    flags = [
        flag
        for flag in result["safety_flags"]
        if "niacin" in (flag.get("nutrient") or "").lower()
    ]

    assert flags, "expected an over-UL flag for 1000 mg niacin vs 35 mg UL"
    assert flags[0]["ul_gate_eligible"] is True
    assert flags[0]["ul_gate_ineligible_reason"] is None
    assert flags[0]["ul_exposure_basis"] == "canonical_parent_substance_amount"
    assert result["has_over_ul"] is True


def test_reference_scoped_form_unii_without_daily_value_is_gate_eligible(enricher):
    # NIH applies the supplemental-niacin UL to nicotinamide/niacinamide.
    # A direct form-UNII match therefore establishes that a standalone
    # niacinamide amount measures an in-scope substance even without a DV.
    product = _mag([
        {
            "name": "Niacinamide",
            "standardName": "Vitamin B3 (Niacin)",
            "canonical_id": "vitamin_b3_niacin",
            "canonical_source_db": "ingredient_quality_map",
            "uniiCode": "25X51I8RD4",
            "quantity": 650,
            "unit": "mg NE",
            "dailyValue": None,
        },
    ])

    result = enricher._collect_rda_ul_data(
        product,
        min_servings_per_day=1,
        max_servings_per_day=1,
    )
    flag = next(
        flag
        for flag in result["safety_flags"]
        if "niacin" in (flag.get("nutrient") or "").lower()
    )

    assert flag["ul_gate_eligible"] is True
    assert flag["ul_gate_ineligible_reason"] is None
    assert flag["ul_exposure_basis"] == "ul_scoped_form_substance_amount"
    assert result["has_over_ul"] is True


def test_vitamin_d3_activity_without_daily_value_is_ul_gate_eligible(enricher):
    """Legacy labels may declare D3 in IU without printing a Daily Value.

    FDA GSRS identifies 1C6V77QF41 as cholecalciferol, one of the two active
    components of the Vitamin D substance record.  The NIH Vitamin D UL covers
    total intake from supplements, so a directly identified D3 activity amount
    must not be mistaken for an unresolved compound mass.
    """
    product = _mag([
        {
            "name": "Vitamin D3",
            "standardName": "Vitamin D",
            "canonical_id": "vitamin_d",
            "canonical_source_db": "ingredient_quality_map",
            "uniiCode": "1C6V77QF41",
            "quantity": 2000,
            "unit": "IU",
            "dailyValue": None,
            "forms": [
                {
                    "name": "Cholecalciferol",
                    "uniiCode": "1C6V77QF41",
                }
            ],
        },
    ])

    result = enricher._collect_rda_ul_data(
        product,
        min_servings_per_day=1,
        max_servings_per_day=1,
    )
    assessment = result["dose_assessments"][0]

    assert assessment["normalized_value"] == pytest.approx(50)
    assert assessment["normalized_unit"] == "mcg"
    assert assessment["ul_gate_eligible"] is True
    assert assessment["ul_assessment_status"] == "assessed_within_limit"
    assert assessment["readiness"] == "complete"


def test_explicit_folic_acid_mass_without_daily_value_is_ul_gate_eligible(enricher):
    """A row named Folic Acid measures the UL-scoped synthetic form itself."""
    result = enricher._collect_rda_ul_data(
        _mag([
            {
                "name": "Folic Acid",
                "raw_source_text": "Folic Acid",
                "standardName": "Folate",
                "canonical_id": "vitamin_b9_folate",
                "canonical_source_db": "ingredient_quality_map",
                "quantity": 400,
                "unit": "mcg",
                "dailyValue": None,
            }
        ]),
        min_servings_per_day=1,
        max_servings_per_day=1,
    )
    assessment = result["dose_assessments"][0]

    assert assessment["normalized_value"] == pytest.approx(680)
    assert assessment["normalized_unit"] == "mcg DFE"
    assert assessment["ul_gate_eligible"] is True
    assert assessment["ul_assessment_status"] == "assessed_within_limit"
    assert assessment["readiness"] == "complete"


def test_choline_bitartrate_uses_verified_active_moiety_mass(enricher):
    """A named salt mass is converted, never treated as elemental by default."""
    result = enricher._collect_rda_ul_data(
        _mag([
            {
                "name": "Choline Bitartrate",
                "raw_source_text": "Choline Bitartrate",
                "standardName": "Choline",
                "canonical_id": "choline",
                "canonical_source_db": "ingredient_quality_map",
                "uniiCode": "6K2W7T9V6Y",
                "quantity": 1000,
                "unit": "mg",
                "dailyValue": None,
            }
        ]),
        min_servings_per_day=1,
        max_servings_per_day=1,
    )
    assessment = result["dose_assessments"][0]

    assert assessment["normalized_value"] == pytest.approx(
        1000 * (104.17 / 253.25)
    )
    assert assessment["normalized_unit"] == "mg"
    assert assessment["conversion_rule_id"] == "choline_bitartrate_to_choline"
    assert assessment["ul_gate_eligible"] is True
    assert assessment["ul_assessment_status"] == "assessed_within_limit"
    assert assessment["readiness"] == "complete"


def test_magnesium_hydroxide_uses_verified_elemental_mass(enricher):
    """An exact magnesium-hydroxide mass uses verified stoichiometry."""
    result = enricher._collect_rda_ul_data(
        _mag([
            {
                "name": "Magnesium Hydroxide",
                "raw_source_text": "Magnesium Hydroxide",
                "standardName": "Magnesium",
                "canonical_id": "magnesium",
                "canonical_source_db": "ingredient_quality_map",
                "quantity": 2.6,
                "unit": "g",
                "dailyValue": None,
            }
        ]),
        min_servings_per_day=1,
        max_servings_per_day=1,
    )
    assessment = result["dose_assessments"][0]
    adequacy = result["adequacy_results"][0]

    assert assessment["normalized_value"] == pytest.approx(
        2.6 * 1000 * (24.305 / 58.320)
    )
    assert assessment["normalized_unit"] == "mg"
    assert assessment["conversion_rule_id"] == (
        "magnesium_hydroxide_to_magnesium"
    )
    assert adequacy["ul_exposure_basis"] == (
        "verified_compound_active_moiety_conversion"
    )
    assert assessment["ul_gate_eligible"] is True
    assert assessment["ul_assessment_status"] == "assessed_over_limit"
    assert assessment["readiness"] == "complete"
    assert result["has_over_ul"] is True


def test_inositol_hexanicotinate_uses_verified_niacin_moiety_for_ul(enricher):
    # The DRI UL applies to all supplemental forms of niacin without a
    # bioavailability adjustment. This exact compound has six verified
    # nicotinic-acid moieties; its whole mass is not used as a raw fallback.
    product = _mag([
        {
            "name": "Inositol Hexanicotinate",
            "standardName": "Vitamin B3 (Niacin)",
            "canonical_id": "vitamin_b3_niacin",
            "canonical_source_db": "ingredient_quality_map",
            "quantity": 1500,
            "unit": "mg",
            "dailyValue": None,
        },
    ])

    basis = enricher._ul_exposure_basis(
        product["activeIngredients"][0],
        canonical_id="vitamin_b3_niacin",
        standard_name="Vitamin B3 (Niacin)",
    )

    result = enricher._collect_rda_ul_data(
        product,
        min_servings_per_day=1,
        max_servings_per_day=1,
    )
    assessment = result["dose_assessments"][0]
    adequacy = result["adequacy_results"][0]

    assert basis["ul_gate_eligible"] is True
    assert basis["ul_exposure_basis"] == (
        "ul_scoped_form_named_substance_amount"
    )
    assert assessment["conversion_rule_id"] == (
        "inositol_hexanicotinate_to_niacin_equivalents"
    )
    assert assessment["normalized_value"] == pytest.approx(
        1500 * ((6 * 123.11) / 810.7)
    )
    assert assessment["ul_gate_eligible"] is True
    assert assessment["ul_assessment_status"] == "assessed_over_limit"
    assert assessment["readiness"] == "complete"
    assert adequacy["ul_exposure_basis"] == (
        "verified_compound_active_moiety_conversion"
    )
    assert result["has_over_ul"] is True


def test_nested_form_components_that_sum_to_parent_are_not_double_counted(enricher):
    # Live Thorne labels declare one Niacin total and then split that total
    # into nested niacinamide + nicotinic-acid components. The components sum
    # to the parent; they are lineage detail, not additional exposure.
    product = _mag([
        {
            "name": "Niacin",
            "raw_source_text": "Niacin",
            "standardName": "Vitamin B3 (Niacin)",
            "canonical_id": "vitamin_b3_niacin",
            "canonical_source_db": "ingredient_quality_map",
            "uniiCode": "2679MF687A",
            "quantity": 38,
            "unit": "mg",
            "dailyValue": 238,
            "isNestedIngredient": False,
        },
        {
            "name": "Niacinamide",
            "raw_source_text": "Niacinamide",
            "standardName": "Vitamin B3 (Niacin)",
            "canonical_id": "vitamin_b3_niacin",
            "canonical_source_db": "ingredient_quality_map",
            "uniiCode": "25X51I8RD4",
            "quantity": 30,
            "unit": "mg",
            "dailyValue": None,
            "isNestedIngredient": True,
            "parentBlend": "Niacin",
        },
        {
            "name": "Niacin",
            "raw_source_text": "Niacin",
            "standardName": "Vitamin B3 (Niacin)",
            "canonical_id": "vitamin_b3_niacin",
            "canonical_source_db": "ingredient_quality_map",
            "uniiCode": "2679MF687A",
            "quantity": 8,
            "unit": "mg",
            "dailyValue": None,
            "isNestedIngredient": True,
            "parentBlend": "Niacin",
        },
    ])

    result = enricher._collect_rda_ul_data(
        product,
        min_servings_per_day=1,
        max_servings_per_day=1,
    )
    analyzed = [
        row
        for row in result["analyzed_ingredients"]
        if "niacin" in (row.get("ingredient") or "").lower()
    ]
    flags = [
        flag
        for flag in result["safety_flags"]
        if "niacin" in (flag.get("nutrient") or "").lower()
    ]

    assert len(analyzed) == 3
    assert analyzed[0]["dose_role"] == "declared_total"
    assert all(row["dose_role"] == "form_component" for row in analyzed[1:])
    assert all(row["skip_ul_check"] is True for row in analyzed[1:])
    assert len(flags) == 1
    assert flags[0]["amount"] == pytest.approx(38)
    assert flags[0]["pct_ul"] == pytest.approx(38 / 35 * 100)
    assert flags[0]["ul_gate_eligible"] is True


def test_nested_same_identity_amount_is_label_restatement_not_second_exposure(enricher):
    # Live DSLD 312939 declares Vitamin B3 500 mg and nests "Niacin
    # 500 mg NE" beneath that row. These are two representations of one
    # label dose, not 1000 mg of exposure.
    product = _mag([
        {
            "name": "Vitamin B3",
            "raw_source_text": "Vitamin B3",
            "standardName": "Vitamin B3 (Niacin)",
            "canonical_id": "vitamin_b3_niacin",
            "canonical_source_db": "ingredient_quality_map",
            "uniiCode": "2679MF687A",
            "quantity": 500,
            "unit": "mg",
            "dailyValue": 3125,
            "isNestedIngredient": False,
        },
        {
            "name": "Niacin",
            "raw_source_text": "Niacin",
            "standardName": "Vitamin B3 (Niacin)",
            "canonical_id": "vitamin_b3_niacin",
            "canonical_source_db": "ingredient_quality_map",
            "quantity": 500,
            "unit": "mg NE",
            "dailyValue": None,
            "isNestedIngredient": True,
            "parentBlend": "Vitamin B3",
        },
    ])

    result = enricher._collect_rda_ul_data(
        product,
        min_servings_per_day=1,
        max_servings_per_day=1,
    )
    analyzed = result["analyzed_ingredients"]
    nested = next(row for row in analyzed if row["ingredient"] == "Niacin")
    flags = [
        flag
        for flag in result["safety_flags"]
        if "niacin" in (flag.get("nutrient") or "").lower()
        or "vitamin b3" in (flag.get("nutrient") or "").lower()
    ]

    assert nested["dose_role"] == "form_component"
    assert nested["skip_ul_check"] is True
    assert nested["skip_ul_reason"] == "form_component_of_declared_total"
    assert len(flags) == 1
    assert flags[0]["amount"] == pytest.approx(500)
    assert flags[0]["ul_gate_eligible"] is True


def test_nested_source_compound_is_owned_by_declared_nutrient_total(enricher):
    # Live DSLD 201426 decomposes one 500 mg inositol-hexanicotinate source
    # under two nutrient views: 400 mg Niacin with a DV and 100 mg Inositol.
    # The two compound rows are the same capsule source material, not another
    # 1000 mg of niacin exposure on top of the declared 400 mg nutrient total.
    product = _mag([
        {
            "name": "Niacin",
            "raw_source_text": "Niacin",
            "standardName": "Vitamin B3 (Niacin)",
            "canonical_id": "vitamin_b3_niacin",
            "canonical_source_db": "ingredient_quality_map",
            "quantity": 400,
            "unit": "mg",
            "dailyValue": 2500,
            "isNestedIngredient": False,
        },
        {
            "name": "Inositol Hexanicotinate",
            "raw_source_text": "Inositol Hexanicotinate",
            "standardName": "Vitamin B3 (Niacin)",
            "canonical_id": "vitamin_b3_niacin",
            "canonical_source_db": "ingredient_quality_map",
            "raw_taxonomy": {"ingredientGroup": "Inositol nicotinate"},
            "quantity": 500,
            "unit": "mg",
            "dailyValue": None,
            "isNestedIngredient": True,
            "parentBlend": "Niacin",
        },
        {
            "name": "Inositol",
            "raw_source_text": "Inositol",
            "standardName": "Inositol",
            "canonical_id": "inositol",
            "canonical_source_db": "ingredient_quality_map",
            "quantity": 100,
            "unit": "mg",
            "dailyValue": None,
            "isNestedIngredient": False,
        },
        {
            "name": "Inositol Hexaniacinate",
            "raw_source_text": "Inositol Hexaniacinate",
            "standardName": "Vitamin B3 (Niacin)",
            "canonical_id": "vitamin_b3_niacin",
            "canonical_source_db": "ingredient_quality_map",
            "raw_taxonomy": {"ingredientGroup": "Inositol nicotinate"},
            "quantity": 500,
            "unit": "mg",
            "dailyValue": None,
            "isNestedIngredient": True,
            "parentBlend": "Inositol",
        },
    ])

    result = enricher._collect_rda_ul_data(
        product,
        min_servings_per_day=1,
        max_servings_per_day=1,
    )
    analyzed = result["analyzed_ingredients"]
    niacin_total = next(row for row in analyzed if row["ingredient"] == "Niacin")
    compounds = [
        row
        for row in analyzed
        if "hexani" in row["ingredient"].lower()
    ]
    niacin_flags = [
        flag
        for flag in result["safety_flags"]
        if "niacin" in (flag.get("nutrient") or "").lower()
    ]

    assert len(compounds) == 2
    assert all(row["dose_role"] == "form_component" for row in compounds)
    assert all(row["skip_ul_check"] is True for row in compounds)
    assert all(
        row["parent_label_key"] == niacin_total["source_label_key"]
        for row in compounds
    )
    assert len(niacin_flags) == 1
    assert niacin_flags[0]["amount"] == pytest.approx(400)


def test_branded_parent_nutrient_row_uses_declared_parent_form_amount(enricher):
    # The same official DSLD 328300 label declares "Boron (calcium
    # fructoborate as patented Fruitex B OsteoBoron) 3 mg". The row name is
    # branded, but DSLD's nutrient group and exact Boron form prove that the
    # displayed 3 mg is the nutrient amount rather than compound mass.
    product = _mag([
        {
            "name": "Fruitex B OsteoBoron",
            "raw_source_text": "Fruitex B OsteoBoron",
            "standardName": "Boron",
            "canonical_id": "boron",
            "canonical_source_db": "ingredient_quality_map",
            "raw_taxonomy": {
                "category": "mineral",
                "ingredientGroup": "Boron",
                "forms": [
                    {
                        "name": "Boron",
                        "category": "mineral",
                        "ingredientGroup": "Boron",
                        "uniiCode": "N9E3X5056Q",
                    }
                ],
            },
            "quantity": 3,
            "unit": "mg",
            "dailyValue": None,
            "isNestedIngredient": False,
        },
    ])

    result = enricher._collect_rda_ul_data(
        product,
        min_servings_per_day=1,
        max_servings_per_day=1,
    )
    analyzed = result["analyzed_ingredients"][0]
    assessment = result["dose_assessments"][0]

    assert analyzed["ul_gate_eligible"] is True
    assert analyzed["ul_exposure_basis"] == (
        "declared_parent_nutrient_form_amount"
    )
    assert assessment["ul_assessment_status"] == "assessed_within_limit"
    assert assessment["pct_ul"] == pytest.approx(15.0)
    assert assessment["readiness"] == "complete"


def test_branded_non_ul_substance_does_not_enter_nutrient_ul_lane(enricher):
    product = _mag([
        {
            "name": "CarnoSyn",
            "raw_source_text": "CarnoSyn",
            "standardName": "Beta-Alanine",
            "canonical_id": "beta-alanine",
            "canonical_source_db": "ingredient_quality_map",
            "raw_taxonomy": {
                "category": "amino acid",
                "ingredientGroup": "Beta-Alanine",
                "forms": [
                    {
                        "name": "Beta-Alanine",
                        "category": "amino acid",
                        "ingredientGroup": "Beta-Alanine",
                        "uniiCode": "11P2JDE17B",
                    }
                ],
            },
            "quantity": 3200,
            "unit": "mg",
            "dailyValue": None,
            "isNestedIngredient": False,
        },
    ])

    result = enricher._collect_rda_ul_data(
        product,
        min_servings_per_day=1,
        max_servings_per_day=1,
    )
    analyzed = result["analyzed_ingredients"][0]

    assert analyzed["ul_gate_eligible"] is False
    assert analyzed["ul_exposure_basis"] == "compound_or_form_mass"


def test_misnested_adjacent_form_components_reconcile_to_nutrient_total(enricher):
    # Live DSLD 64333 attaches two Vitamin B6 form rows to the preceding
    # Niacin row, then emits their exact 105 mg Vitamin B6 total immediately
    # after it. Exact path adjacency, canonical identity, unit, and sum prove
    # an API nesting defect; the components are not another 105 mg exposure.
    product = _mag([
        {
            "name": "Niacin",
            "raw_source_text": "Niacin",
            "raw_source_path": "ingredientRows[6]",
            "standardName": "Vitamin B3 (Niacin)",
            "canonical_id": "vitamin_b3_niacin",
            "canonical_source_db": "ingredient_quality_map",
            "quantity": 862,
            "unit": "mg",
            "dailyValue": 4310,
            "isNestedIngredient": False,
        },
        {
            "name": "Pyridoxal 5-Phosphate",
            "raw_source_text": "Pyridoxal 5-Phosphate",
            "raw_source_path": "ingredientRows[6].nestedRows[0]",
            "standardName": "Vitamin B6 (Pyridoxine)",
            "canonical_id": "vitamin_b6_pyridoxine",
            "canonical_source_db": "ingredient_quality_map",
            "quantity": 100,
            "unit": "mg",
            "dailyValue": None,
            "isNestedIngredient": True,
            "parentBlend": "Niacin",
        },
        {
            "name": "Pyridoxine Hydrochloride",
            "raw_source_text": "Pyridoxine Hydrochloride",
            "raw_source_path": "ingredientRows[6].nestedRows[1]",
            "standardName": "Vitamin B6 (Pyridoxine)",
            "canonical_id": "vitamin_b6_pyridoxine",
            "canonical_source_db": "ingredient_quality_map",
            "quantity": 5,
            "unit": "mg",
            "dailyValue": None,
            "isNestedIngredient": True,
            "parentBlend": "Niacin",
        },
        {
            "name": "Vitamin B6",
            "raw_source_text": "Vitamin B6",
            "raw_source_path": "ingredientRows[7]",
            "standardName": "Vitamin B6 (Pyridoxine)",
            "canonical_id": "vitamin_b6_pyridoxine",
            "canonical_source_db": "ingredient_quality_map",
            "quantity": 105,
            "unit": "mg",
            "dailyValue": 5250,
            "isNestedIngredient": False,
        },
    ])

    result = enricher._collect_rda_ul_data(
        product,
        min_servings_per_day=1,
        max_servings_per_day=1,
    )
    analyzed = result["analyzed_ingredients"]
    vitamin_b6 = next(
        row for row in analyzed if row["ingredient"] == "Vitamin B6"
    )
    components = [
        row
        for row in analyzed
        if row["ingredient"]
        in {"Pyridoxal 5-Phosphate", "Pyridoxine Hydrochloride"}
    ]
    b6_flags = [
        flag
        for flag in result["safety_flags"]
        if "vitamin b6" in (flag.get("nutrient") or "").lower()
    ]

    assert len(components) == 2
    assert all(row["dose_role"] == "form_component" for row in components)
    assert all(
        row["parent_label_key"] == vitamin_b6["source_label_key"]
        for row in components
    )
    assert all(row["skip_ul_check"] is True for row in components)
    assert len(b6_flags) == 1
    assert b6_flags[0]["amount"] == pytest.approx(105)


def test_vitamin_a_total_owns_adequacy_while_preformed_child_owns_ul(enricher):
    """A mixed Vitamin A label is one intake total plus an UL-scoped breakdown."""
    product = _mag([
        {
            "name": "Vitamin A",
            "raw_source_text": "Vitamin A",
            "standardName": "Vitamin A",
            "canonical_id": "vitamin_a",
            "canonical_source_db": "ingredient_quality_map",
            "quantity": 1.05,
            "unit": "mg",
            "dailyValue": 117.0,
            "isNestedIngredient": False,
        },
        {
            "name": "Beta-Carotene",
            "raw_source_text": "Beta-Carotene",
            "standardName": "Beta-Carotene",
            "canonical_id": "beta_carotene",
            "canonical_source_db": "ingredient_quality_map",
            "quantity": 450,
            "unit": "mcg",
            "dailyValue": None,
            "isNestedIngredient": True,
            "parentBlend": "Vitamin A",
        },
        {
            "name": "Vitamin A Palmitate",
            "raw_source_text": "Vitamin A Palmitate",
            "standardName": "Vitamin A",
            "canonical_id": "vitamin_a",
            "canonical_source_db": "ingredient_quality_map",
            "matched_form": "retinyl palmitate",
            "quantity": 600,
            "unit": "mcg",
            "dailyValue": None,
            "isNestedIngredient": True,
            "parentBlend": "Vitamin A",
        },
        {
            "name": "Mixed Carotenoids",
            "raw_source_text": "Mixed Carotenoids",
            "standardName": "Vitamin A",
            "canonical_id": "vitamin_a",
            "canonical_source_db": "ingredient_quality_map",
            "quantity": 46,
            "unit": "mcg",
            "dailyValue": None,
            "isNestedIngredient": False,
        },
    ])

    result = enricher._collect_rda_ul_data(
        product,
        min_servings_per_day=1,
        max_servings_per_day=1,
    )
    rows = result["analyzed_ingredients"]
    parent = next(row for row in rows if row["ingredient"] == "Vitamin A")
    beta = next(row for row in rows if row["ingredient"] == "Beta-Carotene")
    retinyl = next(row for row in rows if row["ingredient"] == "Vitamin A Palmitate")

    assert parent["dose_role"] == "declared_total"
    assert parent["pct_rda"] == pytest.approx(1050 / 900 * 100)
    assert parent["skip_ul_reason"] == "vitamin_a_components_own_ul"
    assert parent["ul_assessment_status"] == "not_applicable"
    assert beta["dose_role"] == "form_component"
    assert beta["parent_label_key"] == parent["source_label_key"]
    assert beta["skip_ul_reason"] == "form_component_of_declared_total"
    assert retinyl["dose_role"] == "ul_scoped_component"
    assert retinyl["parent_label_key"] == parent["source_label_key"]
    assert retinyl["skip_ul_check"] is True
    assert retinyl["skip_ul_reason"] == (
        "worst_case_compound_mass_within_ul"
    )
    assert retinyl["ul_assessment_status"] == "assessed_within_limit"
    assert retinyl["per_day_max"] == pytest.approx(600)
    assert result["safety_flags"] == []


def test_mixed_vitamin_a_total_does_not_assume_all_preformed(enricher):
    result = enricher._collect_rda_ul_data(
        _mag([
            {
                "name": "Vitamin A",
                "raw_source_text": "Vitamin A",
                "standardName": "Vitamin A",
                "canonical_id": "vitamin_a",
                "canonical_source_db": "ingredient_quality_map",
                "quantity": 15000,
                "unit": "IU",
                "dailyValue": 300,
                "forms": [
                    {"name": "Beta-Carotene"},
                    {"name": "Retinyl Acetate"},
                ],
                "isNestedIngredient": False,
            },
            {
                "name": "Beta-Carotene",
                "raw_source_text": "Beta-Carotene",
                "standardName": "Beta-Carotene",
                "canonical_id": "beta_carotene",
                "canonical_source_db": "ingredient_quality_map",
                "quantity": 5625,
                "unit": "mcg",
                "dailyValue": None,
                "isNestedIngredient": True,
                "parentBlend": "Vitamin A",
            }
        ]),
        min_servings_per_day=1,
        max_servings_per_day=1,
    )

    parent = next(
        row for row in result["analyzed_ingredients"]
        if row["ingredient"] == "Vitamin A"
    )
    beta = next(
        row for row in result["analyzed_ingredients"]
        if row["ingredient"] == "Beta-Carotene"
    )
    assert parent["per_day_min"] == pytest.approx(4500)
    assert parent["pct_rda"] == pytest.approx(500)
    assert parent["skip_ul_reason"] == (
        "mixed_vitamin_a_preformed_fraction_unknown"
    )
    assert parent["ul_assessment_status"] == "indeterminate"
    assert parent["ul_for_default_profile"] is None
    assert beta["dose_role"] == "form_component"
    assert beta["parent_label_key"] == parent["source_label_key"]
    assert beta["pct_rda"] is None
    assert result["safety_flags"] == []


@pytest.mark.parametrize(
    ("quantity", "unit", "notes", "expected_total_rae", "expected_preformed"),
    [
        (
            3000,
            "mcg",
            "Vitamin A (Form: as 50% Beta-Carotene, and as 50% Retinyl Acetate)",
            3000,
            1500,
        ),
        (
            3750,
            "mcg",
            "Vitamin A (Form: as Beta Carotene, and as 40% Vitamin A Acetate)",
            3750,
            1500,
        ),
        (
            15000,
            "IU",
            "Vitamin A (Form: as 67% Beta Carotene, & as Retinyl Acetate)",
            4500,
            1485,
        ),
    ],
)
def test_explicit_mixed_vitamin_a_fraction_assesses_preformed_ul(
    enricher,
    quantity,
    unit,
    notes,
    expected_total_rae,
    expected_preformed,
):
    """NIH directs mixed supplements to apply the retinyl percentage to the UL."""
    result = enricher._collect_rda_ul_data(
        _mag([{
            "name": "Vitamin A",
            "raw_source_text": "Vitamin A",
            "standardName": "Vitamin A",
            "canonical_id": "vitamin_a",
            "canonical_source_db": "ingredient_quality_map",
            "quantity": quantity,
            "unit": unit,
            "notes": notes,
            "forms": [
                {"name": "Beta-Carotene"},
                {"name": "Retinyl Acetate"},
            ],
            "isNestedIngredient": False,
            "raw_source_path": "ingredientRows[0]",
        }]),
        min_servings_per_day=1,
        max_servings_per_day=1,
    )

    assessment = result["dose_assessments"][0]
    adequacy = result["adequacy_results"][0]
    assert assessment["conversion_rule_id"] == (
        "vitamin_a_mixed_explicit_preformed_fraction"
    )
    assert assessment["normalized_value"] == pytest.approx(expected_total_rae)
    assert assessment["normalized_unit"] == "mcg RAE"
    assert assessment["reason_code"] == (
        "explicit_mixed_vitamin_a_preformed_fraction"
    )
    assert assessment["ul_assessment_status"] == "assessed_within_limit"
    assert assessment["pct_ul"] == pytest.approx(
        expected_preformed / 3000 * 100
    )
    assert assessment["readiness"] == "complete"
    assert adequacy["adequacy_exposure"]["per_day"] == pytest.approx(
        expected_total_rae
    )
    assert adequacy["safety_exposure"]["per_day"] == pytest.approx(
        expected_preformed
    )
    assert adequacy["preformed_vitamin_a_fraction"] == pytest.approx(
        expected_preformed / expected_total_rae
    )


@pytest.mark.parametrize(
    "notes",
    [
        "as 120% Beta Carotene and Retinyl Acetate",
        "as 110% Beta Carotene and as 10% Retinyl Acetate",
        "as 50% Beta Carotene and as 60% Retinyl Acetate",
    ],
)
def test_invalid_mixed_vitamin_a_percentage_remains_unresolved(
    enricher,
    notes,
):
    result = enricher._collect_rda_ul_data(
        _mag([{
            "name": "Vitamin A",
            "raw_source_text": "Vitamin A",
            "standardName": "Vitamin A",
            "canonical_id": "vitamin_a",
            "canonical_source_db": "ingredient_quality_map",
            "quantity": 15000,
            "unit": "IU",
            "notes": notes,
            "forms": [
                {"name": "Beta-Carotene"},
                {"name": "Retinyl Acetate"},
            ],
            "isNestedIngredient": False,
        }]),
        min_servings_per_day=1,
        max_servings_per_day=1,
    )

    assessment = result["dose_assessments"][0]
    assert assessment["reason_code"] == (
        "mixed_vitamin_a_preformed_fraction_unknown"
    )
    assert assessment["ul_assessment_status"] == "unresolved_form"
    assert assessment["readiness"] == "incomplete"


def test_fish_liver_oil_vitamin_a_is_assessed_as_preformed(enricher):
    """Fish liver oil is a preformed-A source, not an unknown carotenoid mix."""
    result = enricher._collect_rda_ul_data(
        _mag([{
            "name": "Vitamin A",
            "raw_source_text": "Vitamin A",
            "standardName": "Vitamin A",
            "canonical_id": "vitamin_a",
            "canonical_source_db": "ingredient_quality_map",
            "quantity": 3000,
            "unit": "mcg",
            "dailyValue": 333,
            "notes": "Vitamin A (Form: as Fish Liver Oil)",
            "forms": [{"name": "Fish Liver Oil"}],
            "isNestedIngredient": False,
            "raw_source_path": "ingredientRows[0]",
        }]),
        min_servings_per_day=1,
        max_servings_per_day=1,
    )

    assessment = result["dose_assessments"][0]
    assert assessment["conversion_rule_id"] == "vitamin_a_retinol"
    assert assessment["normalized_value"] == pytest.approx(3000)
    assert assessment["normalized_unit"] == "mcg RAE"
    assert assessment["pct_ul"] == pytest.approx(100)
    assert assessment["ul_assessment_status"] == "assessed_within_limit"
    assert assessment["readiness"] == "complete"


def test_mixed_vitamin_a_below_ul_is_safe_under_all_preformed_upper_bound(
    enricher,
):
    result = enricher._collect_rda_ul_data(
        _mag([{
            "name": "Vitamin A",
            "raw_source_text": "Vitamin A",
            "standardName": "Vitamin A",
            "canonical_id": "vitamin_a",
            "canonical_source_db": "ingredient_quality_map",
            "quantity": 5000,
            "unit": "IU",
            "dailyValue": 100,
            "forms": [
                {"name": "Beta-Carotene"},
                {"name": "Retinyl Acetate"},
            ],
            "isNestedIngredient": False,
        }]),
        min_servings_per_day=1,
        max_servings_per_day=1,
    )

    row = result["analyzed_ingredients"][0]
    adequacy = result["adequacy_results"][0]
    assessment = result["dose_assessments"][0]
    assert row["per_day_max"] == pytest.approx(1500)
    assert row["skip_ul_reason"] == (
        "worst_case_preformed_vitamin_a_within_ul"
    )
    assert row["ul_for_default_profile"] == pytest.approx(3000)
    assert adequacy["pct_ul"] == pytest.approx(50)
    assert row["ul_assessment_status"] == "assessed_within_limit"
    assert assessment["ul_assessment_status"] == "assessed_within_limit"
    assert assessment["readiness"] == "complete"


def test_mixed_vitamin_a_parent_miscanonicalized_as_beta_still_uses_bound(
    enricher,
):
    result = enricher._collect_rda_ul_data(
        _mag([{
            "name": "Vitamin A",
            "raw_source_text": "Vitamin A",
            "standardName": "Vitamin A",
            "canonical_id": "beta_carotene",
            "canonical_source_db": "ingredient_quality_map",
            "quantity": 220,
            "unit": "mcg",
            "dailyValue": 24,
            "forms": [
                {"name": "Beta-Carotene"},
                {"name": "Retinyl Acetate"},
            ],
        }]),
        min_servings_per_day=1,
        max_servings_per_day=1,
    )

    assessment = result["dose_assessments"][0]
    assert assessment["reason_code"] == (
        "worst_case_preformed_vitamin_a_within_ul"
    )
    assert assessment["ul_assessment_status"] == "assessed_within_limit"
    assert assessment["readiness"] == "complete"


def test_unknown_vitamin_a_legacy_iu_uses_preformed_upper_bound(enricher):
    result = enricher._collect_rda_ul_data(
        _mag([{
            "name": "Vitamin A",
            "raw_source_text": "Vitamin A",
            "standardName": "Vitamin A",
            "canonical_id": "vitamin_a",
            "canonical_source_db": "ingredient_quality_map",
            "quantity": 5000,
            "unit": "IU",
            "dailyValue": None,
            "forms": [],
        }]),
        min_servings_per_day=1,
        max_servings_per_day=1,
    )

    assessment = result["dose_assessments"][0]
    adequacy = result["adequacy_results"][0]
    assert assessment["normalized_value"] == pytest.approx(1500)
    assert assessment["normalized_unit"] == "mcg RAE"
    assert assessment["reason_code"] == (
        "worst_case_preformed_vitamin_a_within_ul"
    )
    assert assessment["readiness"] == "complete"
    assert adequacy["pct_rda"] is None
    assert adequacy["scoring_eligible"] is False


def test_nested_preformed_component_uses_parent_scoped_upper_bound(enricher):
    result = enricher._collect_rda_ul_data(
        _mag([
            {
                "name": "Vitamin A",
                "raw_source_text": "Vitamin A",
                "standardName": "Vitamin A",
                "canonical_id": "vitamin_a",
                "canonical_source_db": "ingredient_quality_map",
                "quantity": 1350,
                "unit": "mcg",
                "dailyValue": 150,
                "forms": [
                    {"name": "Beta-Carotene"},
                    {"name": "Retinyl Acetate"},
                ],
                "isNestedIngredient": False,
                "raw_source_path": "ingredientRows[1]",
            },
            {
                "name": "Retinyl Acetate",
                "raw_source_text": "Retinyl Acetate",
                "standardName": "Vitamin A",
                "canonical_id": "vitamin_a",
                "canonical_source_db": "ingredient_quality_map",
                "quantity": 675,
                "unit": "mcg",
                "dailyValue": None,
                "isNestedIngredient": True,
                "parentBlend": "Vitamin A",
                "raw_source_path": "ingredientRows[1].nestedRows[1]",
            },
        ]),
        min_servings_per_day=1,
        max_servings_per_day=1,
    )
    parent = next(
        row
        for row in result["dose_assessments"]
        if row["ingredient"] == "Vitamin A"
    )
    child = next(
        row
        for row in result["dose_assessments"]
        if row["ingredient"] == "Retinyl Acetate"
    )

    assert parent["ul_assessment_status"] == "assessed_within_limit"
    assert parent["readiness"] == "complete"
    assert child["reason_code"] == "worst_case_compound_mass_within_ul"
    assert child["ul_assessment_status"] == "assessed_within_limit"
    assert child["readiness"] == "complete"


def test_unidentified_vitamin_a_child_does_not_claim_ul_ownership(enricher):
    result = enricher._collect_rda_ul_data(
        _mag([
            {
                "name": "Vitamin A",
                "raw_source_text": "Vitamin A",
                "standardName": "Vitamin A",
                "canonical_id": "vitamin_a",
                "canonical_source_db": "ingredient_quality_map",
                "quantity": 1000,
                "unit": "mcg",
                "dailyValue": 111,
                "isNestedIngredient": False,
            },
            {
                "name": "Vitamin A Source",
                "raw_source_text": "Vitamin A Source",
                "standardName": "Vitamin A",
                "canonical_id": "vitamin_a",
                "canonical_source_db": "ingredient_quality_map",
                "quantity": 1000,
                "unit": "mcg",
                "dailyValue": None,
                "isNestedIngredient": True,
                "parentBlend": "Vitamin A",
            },
        ]),
        min_servings_per_day=1,
        max_servings_per_day=1,
    )

    parent = next(
        row for row in result["analyzed_ingredients"]
        if row["ingredient"] == "Vitamin A"
    )
    assert parent["skip_ul_reason"] == (
        "worst_case_preformed_vitamin_a_within_ul"
    )
    assert parent["ul_assessment_status"] == "assessed_within_limit"


def test_standalone_beta_carotene_counts_for_adequacy_without_preformed_a_ul(enricher):
    result = enricher._collect_rda_ul_data(
        _mag([
            {
                "name": "Beta-Carotene",
                "raw_source_text": "Beta-Carotene",
                "standardName": "Beta-Carotene",
                "canonical_id": "beta_carotene",
                "canonical_source_db": "ingredient_quality_map",
                "quantity": 2250,
                "unit": "mcg",
                "dailyValue": None,
                "isNestedIngredient": False,
            }
        ]),
        min_servings_per_day=1,
        max_servings_per_day=1,
    )

    row = result["analyzed_ingredients"][0]
    assert row["nutrient_group_id"] == "vitamin_a"
    assert row["per_day_min"] == pytest.approx(1125)
    assert row["pct_rda"] == pytest.approx(1125 / 900 * 100)
    assert row["skip_ul_reason"] == "beta_carotene_no_established_ul"
    assert row["ul_assessment_status"] == "not_applicable"
    assert row["ul_for_default_profile"] is None
    assert result["safety_flags"] == []


@pytest.mark.parametrize(
    ("name", "canonical_id"),
    [
        ("Alpha-Carotene", "alpha_carotene"),
        ("Beta-Cryptoxanthin", "cryptoxanthin"),
    ],
)
def test_other_provitamin_a_carotenoids_convert_without_preformed_a_ul(
    enricher, name, canonical_id
):
    """NIH defines 24 mcg of either carotenoid as 1 mcg RAE.

    The preformed-vitamin-A UL does not apply to these provitamin A
    carotenoids, so an identified standalone row is complete rather than an
    unknown Vitamin A form.
    """
    result = enricher._collect_rda_ul_data(
        _mag([
            {
                "name": name,
                "raw_source_text": name,
                "standardName": "Vitamin A",
                "canonical_id": canonical_id,
                "canonical_source_db": "ingredient_quality_map",
                "quantity": 240,
                "unit": "mcg",
                "dailyValue": None,
                "isNestedIngredient": False,
            }
        ]),
        min_servings_per_day=1,
        max_servings_per_day=1,
    )

    row = result["analyzed_ingredients"][0]
    assessment = result["dose_assessments"][0]
    assert row["per_day_min"] == pytest.approx(10)
    assert row["skip_ul_reason"] == "provitamin_a_carotenoid_no_established_ul"
    assert row["ul_assessment_status"] == "not_applicable"
    assert assessment["ul_assessment_status"] == "no_ul_applicable"
    assert assessment["readiness"] == "not_applicable"


def test_mixed_carotenoid_complex_has_no_preformed_vitamin_a_ul(enricher):
    result = enricher._collect_rda_ul_data(
        _mag([{
            "name": "Mixed Carotenoids",
            "standardName": "Vitamin A",
            "canonical_id": "vitamin_a",
            "canonical_source_db": "ingredient_quality_map",
            "quantity": 12,
            "unit": "mg",
            "dailyValue": None,
        }]),
        min_servings_per_day=1,
        max_servings_per_day=1,
    )
    assessment = result["dose_assessments"][0]
    assert assessment["reason_code"] == (
        "provitamin_a_carotenoid_no_established_ul"
    )
    assert assessment["ul_assessment_status"] == "no_ul_applicable"
    assert assessment["readiness"] == "not_applicable"


@pytest.mark.parametrize(
    ("unit", "expected_reason", "expected_status"),
    [
        ("NP", "amount_not_declared", "indeterminate"),
        ("GDU", "not_ul_applicable", "not_applicable"),
        ("FU", "not_ul_applicable", "not_applicable"),
        ("U", "not_ul_applicable", "not_applicable"),
    ],
)
def test_non_mass_label_states_do_not_masquerade_as_conversion_failures(
    enricher, unit, expected_reason, expected_status
):
    canonical = "bromelain" if unit == "GDU" else "nattokinase" if unit == "FU" else "lysozyme"
    result = enricher._collect_rda_ul_data(
        _mag([
            {
                "name": canonical.title(),
                "standardName": canonical.title(),
                "canonical_id": canonical,
                "canonical_source_db": "ingredient_quality_map",
                "quantity": 100,
                "unit": unit,
            }
        ]),
        min_servings_per_day=1,
        max_servings_per_day=1,
    )
    row = result["analyzed_ingredients"][0]

    assert row["skip_ul_reason"] == expected_reason
    assert row["ul_assessment_status"] == expected_status


def test_mcu_on_a_vitamin_remains_a_data_defect_until_source_corrected(enricher):
    result = enricher._collect_rda_ul_data(
        _mag([
            {
                "name": "Biotin",
                "standardName": "Biotin",
                "canonical_id": "biotin",
                "canonical_source_db": "ingredient_quality_map",
                "quantity": 1500,
                "unit": "m.c.u.",
            }
        ]),
        min_servings_per_day=1,
        max_servings_per_day=1,
    )

    row = result["analyzed_ingredients"][0]
    assert row["skip_ul_reason"] == "conversion_failed"
    assert row["ul_assessment_status"] == "indeterminate"


@pytest.mark.parametrize(
    ("canonical", "name", "unit"),
    [
        ("digestive_enzymes", "Protease", "HUT"),
        ("alpha_amylase", "Glucoamylase", "AGU"),
        ("lactobacillus_acidophilus", "Lactobacillus acidophilus", "CFU"),
        ("bifidobacterium_bifidum", "Bifidobacterium bifidum", "{Organisms}"),
        ("peppermint", "Peppermint Oil", "mL"),
        ("garlic", "Allicin", "mcg/g"),
    ],
)
def test_domain_units_outside_ul_scope_are_not_conversion_defects(
    enricher, canonical, name, unit
):
    result = enricher._collect_rda_ul_data(
        _mag([
            {
                "name": name,
                "standardName": name,
                "canonical_id": canonical,
                "canonical_source_db": "ingredient_quality_map",
                "quantity": 100,
                "unit": unit,
            }
        ]),
        min_servings_per_day=1,
        max_servings_per_day=1,
    )

    row = result["analyzed_ingredients"][0]
    assert row["skip_ul_reason"] == "not_ul_applicable"
    assert row["ul_assessment_status"] == "not_applicable"


@pytest.mark.parametrize("unit", ["mmg", "Jar(s)"])
def test_invalid_source_units_remain_conversion_defects(enricher, unit):
    result = enricher._collect_rda_ul_data(
        _mag([
            {
                "name": "Test Ingredient",
                "standardName": "Test Ingredient",
                "canonical_id": "test_ingredient",
                "canonical_source_db": "ingredient_quality_map",
                "quantity": 250,
                "unit": unit,
            }
        ]),
        min_servings_per_day=1,
        max_servings_per_day=1,
    )

    row = result["analyzed_ingredients"][0]
    assert row["skip_ul_reason"] == "conversion_failed"
    assert row["ul_assessment_status"] == "indeterminate"


def test_botanical_volume_unit_does_not_hide_a_vitamin_conversion_defect(enricher):
    result = enricher._collect_rda_ul_data(
        _mag([
            {
                "name": "Vitamin A (as Retinyl Acetate)",
                "standardName": "Vitamin A (as Retinyl Acetate)",
                "canonical_id": "vitamin_a",
                "canonical_source_db": "ingredient_quality_map",
                "quantity": 1,
                "unit": "mL",
            }
        ]),
        min_servings_per_day=1,
        max_servings_per_day=1,
    )

    row = result["analyzed_ingredients"][0]
    assert row["skip_ul_reason"] == "conversion_failed"
    assert row["ul_assessment_status"] == "indeterminate"


def test_nested_daily_value_row_owns_exposure_over_larger_source_compound_mass(enricher):
    # Live DSLD 299037 represents Magtein source mass as a 1000 mg parent and
    # the delivered Magnesium amount as a nested 72 mg row carrying 17% DV.
    # The DV-confirmed child is the nutrient exposure; the larger parent mass
    # must not be compared with the elemental magnesium UL.
    product = _mag([
        {
            "name": "Magnesium",
            "raw_source_text": "Magnesium",
            "standardName": "Magnesium",
            "canonical_id": "magnesium",
            "canonical_source_db": "ingredient_quality_map",
            "uniiCode": "I38ZP9992A",
            "quantity": 1000,
            "unit": "mg",
            "dailyValue": None,
            "isNestedIngredient": False,
        },
        {
            "name": "Magtein Magnesium L-Threonate",
            "raw_source_text": "Magtein Magnesium L-Threonate",
            "standardName": "Magnesium",
            "canonical_id": "magnesium",
            "canonical_source_db": "ingredient_quality_map",
            "quantity": 72,
            "unit": "mg",
            "dailyValue": 17,
            "isNestedIngredient": True,
            "parentBlend": "Magnesium",
            "is_compound_duplicate": True,
        },
    ])

    result = enricher._collect_rda_ul_data(
        product,
        min_servings_per_day=2,
        max_servings_per_day=2,
    )
    analyzed = result["analyzed_ingredients"]
    source_mass = next(row for row in analyzed if row["ingredient"] == "Magnesium")
    delivered = next(
        row
        for row in analyzed
        if row["ingredient"] == "Magtein Magnesium L-Threonate"
    )

    assert source_mass["dose_role"] == "form_component"
    assert source_mass["skip_ul_check"] is True
    assert source_mass["skip_ul_reason"] == "form_component_of_declared_total"
    assert delivered["dose_role"] == "declared_total"
    assert delivered["skip_ul_check"] is False
    assert delivered["ul_exposure_basis"] == "daily_value_confirmed_nutrient_amount"
    assert [
        flag
        for flag in result["safety_flags"]
        if "magnesium" in (flag.get("nutrient") or "").lower()
    ] == []


def test_emergency_strength_potassium_iodide_emits_special_use_flag(enricher):
    product = _mag([
        {
            "name": "Potassium Iodide",
            "raw_source_text": "Potassium Iodide",
            "standardName": "Iodine",
            "canonical_id": "iodine",
            "quantity": 130,
            "unit": "mg",
            "dailyValue": None,
        },
    ])

    result = enricher._collect_rda_ul_data(product)

    assert result["special_use_flags"] == [{
        "code": "POTASSIUM_IODIDE_EMERGENCY_USE_ONLY",
        "ingredient": "Potassium Iodide",
        "amount": 130.0,
        "unit": "mg",
        "severity": "high",
        "action": (
            "Use only during a radiation emergency when public-health or "
            "emergency-management officials direct it; do not take it "
            "routinely or before a radiation exposure."
        ),
        "source": "FDA",
        "source_url": (
            "https://www.fda.gov/drugs/bioterrorism-and-drug-preparedness/"
            "frequently-asked-questions-potassium-iodide-ki"
        ),
    }]


def test_nutritional_potassium_iodide_dose_does_not_emit_emergency_flag(enricher):
    product = _mag([
        {
            "name": "Potassium Iodide",
            "standardName": "Iodine",
            "canonical_id": "iodine",
            "quantity": 225,
            "unit": "mcg",
        },
    ])

    result = enricher._collect_rda_ul_data(product)

    assert result["special_use_flags"] == []
