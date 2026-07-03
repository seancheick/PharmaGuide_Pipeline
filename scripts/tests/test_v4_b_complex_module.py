#!/usr/bin/env python3
"""B-complex v4 route/module calibration.

The B-complex class is a focused daily micronutrient product, not a broad
multi/prenatal and not a stimulant energy stack. These tests lock the scoring
intent so clean, moderate-dose active-form products can reach a fair top band
while megadose / over-UL products carry the visible safety penalty.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from score_supplements_v4 import score_product_v4  # noqa: E402


def _row(
    canonical_id: str,
    name: str,
    quantity: float,
    unit: str,
    *,
    bio_score: float = 13.0,
    matched_form: str = "",
    category: str = "vitamins",
    idx: int = 0,
) -> dict:
    return {
        "canonical_id": canonical_id,
        "name": name,
        "standard_name": name,
        "quantity": quantity,
        "unit": unit,
        "unit_normalized": unit,
        "category": category,
        "mapped": True,
        "mapped_identity": True,
        "scoreable_identity": True,
        "score_eligible_by_cleaner": True,
        "cleaner_row_role": "active_scorable",
        "role_classification": "active_scorable",
        "source_section": "activeIngredients",
        "raw_source_path": f"activeIngredients[{idx}]",
        "dose_class": "mass",
        "bio_score": bio_score,
        "matched_form": matched_form,
    }


def _rda(nutrient: str, pct_rda: float, pct_ul: float | None = None) -> dict:
    row = {
        "nutrient": nutrient,
        "standard_name": nutrient,
        "pct_rda": pct_rda,
        "scoring_eligible": True,
    }
    if pct_ul is not None:
        row["pct_ul"] = pct_ul
    return row


def _ideal_b_complex() -> dict:
    rows = [
        _row("vitamin_b1_thiamine", "Thiamin", 10, "mg", idx=0),
        _row("vitamin_b2_riboflavin", "Riboflavin-5-Phosphate", 10, "mg", matched_form="riboflavin-5-phosphate", idx=1),
        _row("vitamin_b3_niacin", "Niacinamide", 20, "mg", matched_form="niacinamide", idx=2),
        _row("vitamin_b5_pantothenic_acid", "Pantothenic Acid", 25, "mg", idx=3),
        _row("vitamin_b6_pyridoxine", "P5P", 10, "mg", matched_form="pyridoxal-5-phosphate", idx=4),
        _row("vitamin_b9_folate", "L-5-MTHF", 400, "mcg", matched_form="l-5-mthf", idx=5),
        _row("vitamin_b12_cobalamin", "Methylcobalamin + Adenosylcobalamin", 500, "mcg", matched_form="methylcobalamin adenosylcobalamin", idx=6),
        _row("vitamin_b7_biotin", "Biotin", 100, "mcg", idx=7),
        _row("choline", "Choline", 250, "mg", category="other_nutrients", idx=8),
    ]
    return {
        "product_name": "Active B-Complex Daily Clean Capsule",
        "brand_name": "PharmaGuide Benchmark",
        "brandName": "PharmaGuide Benchmark",
        "primary_type": "b_complex",
        "supplement_taxonomy": {"primary_type": "b_complex"},
        "status": "active",
        "ingredient_quality_data": {
            "ingredients_scorable": rows,
            "ingredients": rows,
            "mapped_coverage": 1.0,
        },
        "rda_ul_data": {
            "adequacy_results": [
                _rda("Vitamin B1", 833),
                _rda("Vitamin B2", 769),
                _rda("Niacin", 125, 57),
                _rda("Pantothenic Acid", 500),
                _rda("Vitamin B6", 588, 59),
                _rda("Folate", 100, 40),
                _rda("Vitamin B12", 20833),
                _rda("Biotin", 333),
                _rda("Choline", 45),
            ],
            "safety_flags": [],
        },
        "verified_cert_programs": [
            {
                "program": "NSF Certified for Sport",
                "scope": "sku",
                "matched_brand": "PharmaGuide Benchmark",
            }
        ],
        "certification_data": {
            "gmp": {"gmp_certified_or_compliant": True},
        },
        "has_batch_coa": True,
    }


def _megadose_b_complex() -> dict:
    product = _ideal_b_complex()
    product["product_name"] = "Mega B-100 Energy Soft Chews"
    product["verified_cert_programs"] = []
    product["certification_data"] = {}
    product["rda_ul_data"] = {
        "adequacy_results": [
            _rda("Vitamin B1", 8333),
            _rda("Vitamin B2", 7692),
            _rda("Niacin", 625, 286),
            _rda("Vitamin B6", 5882, 588),
            _rda("Folate", 300, 120),
            _rda("Vitamin B12", 208333),
            _rda("Biotin", 33333),
        ],
        "safety_flags": [
            {"nutrient": "Niacin", "pct_ul": 286, "severity": "high"},
            {"nutrient": "Vitamin B6", "pct_ul": 588, "severity": "high"},
            {"nutrient": "Folate", "pct_ul": 120, "severity": "moderate"},
        ],
    }
    product["harmful_additives"] = [
        {"additive_name": "FD&C Red 40", "severity_level": "moderate"},
    ]
    return product


def test_clean_active_form_b_complex_scores_in_fair_top_band() -> None:
    scored = score_product_v4(_ideal_b_complex())

    assert scored["v4_module"] == "b_complex"
    assert scored["v4_breakdown"]["module"]["module"] == "b_complex"
    assert scored["quality_score_v4_100"] >= 84.0
    assert scored["quality_score_v4_100"] <= 92.0


def test_over_ul_b_complex_carries_dose_and_safety_hygiene_penalty() -> None:
    scored = score_product_v4(_megadose_b_complex())

    dose = scored["v4_breakdown"]["module"]["dimensions"]["dose"]
    safety = scored["quality_pillars_v4"]["safety_hygiene"]

    assert scored["v4_module"] == "b_complex"
    assert dose["penalties"]["B7_dose_safety"] < 0
    assert safety["score"] < safety["max"]
    assert scored["quality_score_v4_100"] < 70.0
