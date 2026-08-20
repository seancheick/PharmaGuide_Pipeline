#!/usr/bin/env python3
"""DV-backed dose unit correction regressions.

DSLD occasionally carries a mass unit typo while preserving a coherent
percent Daily Value. The cleaner should trust the label math when it proves a
mg->mcg typo, then preserve the raw DSLD amount for audit.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_final_db import build_detail_blob  # noqa: E402
from scripts.api_audit.audit_dv_plausibility import audit  # noqa: E402
from scripts.enhanced_normalizer import EnhancedDSLDNormalizer  # noqa: E402
from scripts.enrich_supplements_v3 import SupplementEnricherV3  # noqa: E402


def _quantity(amount: float, unit: str, percent_dv: float | None = None, target_group: str | None = None) -> list[dict]:
    row = {
        "quantity": amount,
        "unit": unit,
        "servingSizeOrder": 1,
        "servingSizeQuantity": 1,
        "servingSizeUnit": "Tablet",
    }
    if percent_dv is not None:
        row["dailyValueTargetGroup"] = [{
            "percent": percent_dv,
            "targetGroup": target_group or "Adults and children 4 or more years",
            "dailyValueTargetGroupName": target_group or "Adults and children 4 or more years",
            "servingSizeQuantity": 1,
            "servingSizeUnitOfMeasure": "Tablet",
        }]
    return [row]


def _raw_product(ingredient_rows: list[dict], name: str = "DV Correction Test") -> dict:
    return {
        "id": "dv-correction-test",
        "productId": 999001,
        "fullName": name,
        "brandName": "Test Brand",
        "productVersionCode": "1",
        "productType": {
            "langualCodeDescription": "Dietary Supplement"
        },
        "ingredientRows": ingredient_rows,
        "servingSizes": [
            {"quantity": 1, "unit": "Tablet"}
        ],
        "otheringredients": {"ingredients": []},
        "statements": [{"text": "Take one tablet daily."}],
    }


def _cleaned_active(raw_product: dict) -> dict:
    cleaned = EnhancedDSLDNormalizer().normalize_product(raw_product)
    assert cleaned.get("activeIngredients"), cleaned
    return cleaned["activeIngredients"][0]


def _minimal_scored() -> dict:
    return {
        "score_80": 60.0,
        "display": "60/80",
        "display_100": "75/100",
        "score_100_equivalent": 75.0,
        "grade": "Good",
        "verdict": "SAFE",
        "safety_verdict": "SAFE",
        "mapped_coverage": 1.0,
        "badges": [],
        "flags": [],
        "section_scores": {},
        "summary": {},
        "supp_type": "multivitamin",
        "unmapped_actives": [],
        "breakdown": {
            "C": {
                "score": 10.0,
                "max": 20.0,
                "ingredient_points": {},
                "matched_entries": 1,
                "top_n_applied": 1,
                "depth_bonus": 0.0,
                "sub_clinical_canonicals": [],
            }
        },
    }


def test_vitamin_d_mg_with_prenatal_dv_corrects_to_mcg_and_preserves_raw() -> None:
    raw = _raw_product(
        [
            {
                "order": 1,
                "name": "Vitamin D3",
                "category": "vitamin",
                "ingredientGroup": "Vitamin D",
                "quantity": _quantity(
                    50,
                    "mg",
                    percent_dv=330,
                    target_group="Pregnant women and lactating women",
                ),
                "forms": [{"name": "Cholecalciferol", "ingredientGroup": "Vitamin D"}],
            }
        ],
        name="Prenatal Multivitamin",
    )

    active = _cleaned_active(raw)

    assert active["quantity"] == pytest.approx(50.0)
    assert active["unit"] == "mcg"
    assert active["dailyValue"] == pytest.approx(330.0)
    dq = active["dose_data_quality"]
    assert dq["status"] == "corrected"
    assert dq["raw_amount"] == pytest.approx(50.0)
    assert dq["raw_unit"] == "mg"
    assert dq["corrected_unit"] == "mcg"
    assert dq["daily_value_target_group"] == "pregnant_lactating"
    assert dq["daily_value_reference_amount"] == pytest.approx(15.0)
    assert dq["mismatch_ratio"] >= 100


def test_vitamin_d_real_adult_label_math_allows_rounding_drift() -> None:
    """DSLD 223563: 100 mg + 660% DV is a source-unit typo for 100 mcg."""
    raw = _raw_product([
        {
            "order": 1,
            "name": "Vitamin D3",
            "category": "vitamin",
            "ingredientGroup": "Vitamin D (cholecalciferol)",
            "quantity": _quantity(100, "mg", percent_dv=660),
        }
    ])

    active = _cleaned_active(raw)

    assert active["quantity"] == pytest.approx(100.0)
    assert active["unit"] == "mcg"
    assert active["dose_data_quality"]["status"] == "corrected"


@pytest.mark.parametrize(
    ("ingredient_name", "amount", "raw_unit", "percent_dv", "expected_unit"),
    [
        ("Vitamin B6", 1.7, "Gram(s)", 100, "mg"),
        ("Vitamin C", 250, "Gram(s)", 278, "mg"),
        ("Selenium", 55, "mg", 79, "mcg"),
    ],
)
def test_dv_math_repairs_plural_mass_units_and_legacy_dv_rounding(
    ingredient_name: str,
    amount: float,
    raw_unit: str,
    percent_dv: float,
    expected_unit: str,
) -> None:
    """DSLD mass-unit typos are repaired only when statutory %DV proves them."""
    category = "mineral" if ingredient_name == "Selenium" else "vitamin"
    raw = _raw_product([
        {
            "order": 1,
            "name": ingredient_name,
            "category": category,
            "ingredientGroup": ingredient_name,
            "quantity": _quantity(amount, raw_unit, percent_dv=percent_dv),
        }
    ])

    active = _cleaned_active(raw)

    assert active["quantity"] == pytest.approx(amount)
    assert active["unit"] == expected_unit
    assert active["dose_data_quality"]["status"] == "corrected"
    assert active["dose_data_quality"]["raw_unit"] == raw_unit


def test_vitamin_d_np_unit_uses_coherent_daily_value_evidence() -> None:
    """A numeric nutrient row marked NP can still have a provable missing unit."""
    raw = _raw_product([
        {
            "order": 1,
            "name": "Vitamin D2",
            "category": "vitamin",
            "ingredientGroup": "Vitamin D",
            "quantity": _quantity(20, "NP", percent_dv=100),
            "forms": [{"name": "Ergocalciferol", "ingredientGroup": "Vitamin D"}],
        }
    ])

    active = _cleaned_active(raw)

    assert active["quantity"] == pytest.approx(20.0)
    assert active["unit"] == "mcg"
    assert active["dose_data_quality"]["reason"] == "daily_value_missing_unit"
    assert active["dose_data_quality"]["raw_unit"] == "NP"


def test_nested_folic_acid_unit_uses_parent_dfe_equivalence() -> None:
    """A nested component can prove its unit from its measured DFE parent."""
    raw = _raw_product([
        {
            "order": 1,
            "name": "Folate",
            "category": "vitamin",
            "ingredientGroup": "Folate",
            "quantity": _quantity(666, "mcg DFE", percent_dv=167),
            "nestedRows": [
                {
                    "order": 2,
                    "name": "Folic Acid",
                    "category": "vitamin",
                    "ingredientGroup": "Folate",
                    "quantity": _quantity(400, "mg"),
                    "nestedRows": [],
                    "forms": [],
                }
            ],
        }
    ])

    cleaned = EnhancedDSLDNormalizer().normalize_product(raw)
    folic_acid = next(
        row for row in cleaned["activeIngredients"]
        if row["name"] == "Folic Acid"
    )

    assert folic_acid["quantity"] == pytest.approx(400.0)
    assert folic_acid["unit"] == "mcg"
    assert folic_acid["dose_data_quality"]["reason"] == (
        "parent_equivalence_unit_mismatch"
    )

    enriched, warnings = SupplementEnricherV3().enrich_product(cleaned)
    assert not warnings
    blob = build_detail_blob(enriched, _minimal_scored())
    folate_rows = [
        row for row in blob["display_ingredients"]
        if row.get("label_display_name") == "Folate"
    ]
    assert len(folate_rows) == 1
    assert folate_rows[0]["exact_dose_text"] == "666 mcg DFE"
    assert folate_rows[0]["parenthetical_dose_text"] == "400 mcg folic acid"


def test_nested_folic_acid_uses_repaired_bare_mcg_parent_context() -> None:
    """The parent's restored DFE unit must reach its already-flattened child."""
    raw = _raw_product([
        {
            "order": 1,
            "name": "Folate",
            "category": "vitamin",
            "ingredientGroup": "Folate",
            "quantity": _quantity(333, "mcg", percent_dv=83),
            "nestedRows": [
                {
                    "order": 2,
                    "name": "Folic Acid",
                    "category": "vitamin",
                    "ingredientGroup": "Folate",
                    "quantity": _quantity(200, "mg"),
                    "nestedRows": [],
                    "forms": [],
                }
            ],
        }
    ])

    cleaned = EnhancedDSLDNormalizer().normalize_product(raw)
    folate = next(row for row in cleaned["activeIngredients"] if row["name"] == "Folate")
    folic_acid = next(
        row for row in cleaned["activeIngredients"] if row["name"] == "Folic Acid"
    )

    assert folate["unit"] == "mcg DFE"
    assert folic_acid["quantity"] == pytest.approx(200.0)
    assert folic_acid["unit"] == "mcg"
    assert folic_acid["parentBlendUnit"] == "mcg DFE"
    assert folic_acid["dose_data_quality"]["reason"] == (
        "parent_equivalence_unit_mismatch"
    )


def test_folate_parent_with_explicit_folic_acid_child_restores_dfe_unit() -> None:
    """Modern labels can lose only the DFE qualifier in the DSLD API.

    The 267:160 declaration ratio, current 67% DV, and explicit folic-acid
    child together identify the parent as the printed DFE total without
    guessing the form of an otherwise bare legacy folate row.
    """
    raw = _raw_product([
        {
            "order": 1,
            "name": "Folate",
            "category": "vitamin",
            "ingredientGroup": "Folate",
            "quantity": _quantity(267, "mcg", percent_dv=67),
            "nestedRows": [
                {
                    "order": 2,
                    "name": "Folic Acid",
                    "category": "vitamin",
                    "ingredientGroup": "Folate",
                    "quantity": _quantity(160, "mcg"),
                    "nestedRows": [],
                    "forms": [],
                }
            ],
        }
    ])

    cleaned = EnhancedDSLDNormalizer().normalize_product(raw)
    folate = next(
        row for row in cleaned["activeIngredients"]
        if row["name"] == "Folate"
    )

    assert folate["quantity"] == pytest.approx(267.0)
    assert folate["unit"] == "mcg DFE"
    assert folate["dose_data_quality"]["reason"] == (
        "explicit_folic_acid_child_dfe_total"
    )
    assert folate["dose_data_quality"]["raw_unit"] == "mcg"


def test_bare_legacy_folate_is_not_reinterpreted_as_dfe() -> None:
    """A historical bare-mcg folate row lacks enough evidence for DFE."""
    raw = _raw_product([
        {
            "order": 1,
            "name": "Folate",
            "category": "vitamin",
            "ingredientGroup": "Folate",
            "quantity": _quantity(400, "mcg", percent_dv=100),
            "nestedRows": [],
        }
    ])

    folate = _cleaned_active(raw)

    assert folate["unit"] == "mcg"
    assert "dose_data_quality" not in folate


def test_iodine_adult_dv_corrects_mg_to_mcg() -> None:
    raw = _raw_product([
        {
            "order": 1,
            "name": "Iodine",
            "category": "mineral",
            "ingredientGroup": "Iodine",
            "quantity": _quantity(150, "mg", percent_dv=100),
        }
    ])

    active = _cleaned_active(raw)

    assert active["quantity"] == pytest.approx(150.0)
    assert active["unit"] == "mcg"
    assert active["dose_data_quality"]["daily_value_target_group"] == "adult_4_plus"


def test_folate_mg_dfe_source_typo_preserves_dfe_while_correcting_scale() -> None:
    """DSLD 259791: 1,360 mg DFE at 340% DV is really 1,360 mcg DFE.

    The semantic DFE qualifier is part of the label identity and must survive
    the DV-proven mg->mcg repair. Treating the whole unit string as a bare
    mass token previously left this 1,000x source typo uncorrected.
    """
    raw = _raw_product([
        {
            "order": 1,
            "name": "Folate",
            "category": "vitamin",
            "ingredientGroup": "Folate",
            "quantity": _quantity(1360, "mg DFE", percent_dv=340),
        }
    ])

    active = _cleaned_active(raw)

    assert active["quantity"] == pytest.approx(1360.0)
    assert active["unit"] == "mcg DFE"
    assert active["dose_data_quality"]["status"] == "corrected"
    assert active["dose_data_quality"]["raw_unit"] == "mg DFE"
    assert active["dose_data_quality"]["corrected_unit"] == "mcg DFE"


def test_folate_total_and_folic_acid_child_emit_separate_intake_and_ul_roles() -> None:
    """The label total owns intake; its folic-acid child owns the scoped UL.

    These are two views of one declaration, not two nutrient doses. The
    emitted lineage lets the client count 1,360 mcg DFE once while comparing
    the explicit 800 mcg folic-acid contribution to the synthetic-folate UL.
    """
    raw = _raw_product([
        {
            "order": 1,
            "name": "Folate",
            "category": "vitamin",
            "ingredientGroup": "Folate",
            "quantity": _quantity(1360, "mg DFE", percent_dv=340),
            "nestedRows": [
                {
                    "order": 2,
                    "name": "Folic Acid",
                    "category": "vitamin",
                    "ingredientGroup": "Folate",
                    "quantity": _quantity(800, "mcg"),
                    "nestedRows": [],
                    "forms": [],
                }
            ],
        }
    ])

    cleaned = EnhancedDSLDNormalizer().normalize_product(raw)
    enriched, warnings = SupplementEnricherV3().enrich_product(cleaned)
    assert not warnings
    rows = [
        row for row in enriched["rda_ul_data"]["analyzed_ingredients"]
        if row.get("canonical_id") == "vitamin_b9_folate"
    ]
    assert len(rows) == 2
    parent = next(row for row in rows if row["ingredient"] == "Folate")
    child = next(row for row in rows if row["ingredient"] == "Folic Acid")

    assert parent["dose_role"] == "declared_total"
    assert parent["per_day_max"] == pytest.approx(1360.0)
    assert child["dose_role"] == "ul_scoped_component"
    assert child["parent_label_key"] == parent["source_label_key"]
    assert child["skip_ul_check"] is False
    assert child["per_day_max"] == pytest.approx(1360.0)


def test_percent_only_panel_mineral_routes_to_nutrition_not_active() -> None:
    """Legacy protein labels can expose only %DV for panel calcium/iron."""
    raw = _raw_product(
        [
            {
                "order": 1,
                "name": "Calcium",
                "category": "mineral",
                "ingredientGroup": "Calcium",
                "quantity": _quantity(6, "%"),
            },
            {
                "order": 2,
                "name": "Iron",
                "category": "mineral",
                "ingredientGroup": "Iron",
                "quantity": _quantity(8, "%"),
            },
        ],
        name="Whey Protein Powder",
    )

    cleaned = EnhancedDSLDNormalizer().normalize_product(raw)

    assert cleaned["activeIngredients"] == []
    nutrition_rows = [
        row
        for row in cleaned["display_ingredients"]
        if row.get("display_type") == "nutrition_fact"
    ]
    assert [(row["label_display_name"], row["exact_dose_text"]) for row in nutrition_rows] == [
        ("Calcium", "6 %"),
        ("Iron", "8 %"),
    ]


@pytest.mark.parametrize(
    "name,category,ingredient_group,amount,unit,percent_dv",
    [
        ("Calcium", "mineral", "Calcium", 200, "mg", 15),
        ("Magnesium", "mineral", "Magnesium", 100, "mg", 24),
        ("Vitamin D3", "vitamin", "Vitamin D", 2000, "IU", 330),
        ("Potassium Iodide", "mineral", "Iodine", 130, "mg", None),
    ],
)
def test_dv_correction_noops_outside_dv_proven_mg_to_mcg(
    name: str,
    category: str,
    ingredient_group: str,
    amount: float,
    unit: str,
    percent_dv: float | None,
) -> None:
    raw = _raw_product([
        {
            "order": 1,
            "name": name,
            "category": category,
            "ingredientGroup": ingredient_group,
            "quantity": _quantity(amount, unit, percent_dv=percent_dv),
        }
    ])

    active = _cleaned_active(raw)

    assert active["quantity"] == pytest.approx(amount)
    assert active["unit"] == unit
    assert "dose_data_quality" not in active


def test_corrected_vitamin_d_flows_to_rda_and_final_display_without_false_ul_flag() -> None:
    raw = _raw_product(
        [
            {
                "order": 1,
                "name": "Vitamin D3",
                "category": "vitamin",
                "ingredientGroup": "Vitamin D",
                "quantity": _quantity(
                    50,
                    "mg",
                    percent_dv=330,
                    target_group="Pregnant women and lactating women",
                ),
                "forms": [{"name": "Cholecalciferol", "ingredientGroup": "Vitamin D"}],
            }
        ],
        name="Prenatal Multivitamin",
    )

    cleaned = EnhancedDSLDNormalizer().normalize_product(raw)
    enriched, warnings = SupplementEnricherV3().enrich_product(cleaned)
    assert not warnings

    rda = enriched["rda_ul_data"]
    assert rda["safety_flags"] == []
    vitamin_d_rows = [
        row for row in rda["adequacy_results"]
        if row.get("nutrient") in {"Vitamin D", "Vitamin D3"}
    ]
    assert len(vitamin_d_rows) == 1
    assert vitamin_d_rows[0]["amount"] == pytest.approx(50.0)
    assert vitamin_d_rows[0]["unit"] == "mcg"
    assert vitamin_d_rows[0]["original_unit"] == "mcg"

    blob = build_detail_blob(enriched, _minimal_scored())
    vitamin_d = next(row for row in blob["ingredients"] if row["standardName"] == "Vitamin D")
    assert vitamin_d["display_dose_label"] == "50 mcg"
    assert vitamin_d["dose_data_quality"]["status"] == "corrected"


def test_dv_plausibility_audit_reports_corrected_and_uncorrected_mismatches(tmp_path: Path) -> None:
    detail_dir = tmp_path / "detail_blobs"
    detail_dir.mkdir()
    corrected = {
        "id": "corrected-product",
        "product_name": "Corrected Vitamin D",
        "ingredients": [
            {
                "name": "Vitamin D3",
                "standardName": "Vitamin D",
                "quantity": 50,
                "unit": "mcg",
                "dailyValue": 330,
                "dose_data_quality": {
                    "status": "corrected",
                    "reason": "daily_value_unit_mismatch",
                    "daily_value_target_group": "pregnant_lactating",
                    "daily_value_reference_amount": 15,
                    "daily_value_reference_unit": "mcg",
                    "mismatch_ratio": 1010.101,
                },
            }
        ],
    }
    uncorrected = {
        "id": "uncorrected-product",
        "product_name": "Uncorrected Iodine",
        "ingredients": [
            {
                "name": "Iodine",
                "standardName": "Iodine",
                "quantity": 150,
                "unit": "mg",
                "dailyValue": 100,
                "daily_value_target_group": "adult_4_plus",
            }
        ],
    }
    (detail_dir / "corrected.json").write_text(json.dumps(corrected), encoding="utf-8")
    (detail_dir / "uncorrected.json").write_text(json.dumps(uncorrected), encoding="utf-8")

    output = tmp_path / "dv_audit.csv"
    counts = audit(detail_dir, output)

    assert counts["corrected"] == 1
    assert counts["uncorrected_dv_mismatch"] == 1
    csv_text = output.read_text(encoding="utf-8")
    assert "corrected" in csv_text
    assert "uncorrected_dv_mismatch" in csv_text
