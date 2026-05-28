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
