"""Production-path regression coverage for the vitamin K identity family."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import build_final_db
from enhanced_normalizer import EnhancedDSLDNormalizer
from enrich_supplements_v3 import SupplementEnricherV3


def _label_row(name: str, amount_mcg: float, form: str) -> dict:
    return {
        "name": name,
        "ingredientGroup": "Vitamin K",
        "category": "vitamin",
        "quantity": [{"quantity": amount_mcg, "unit": "mcg"}],
        "forms": [{"name": form}],
    }


@pytest.fixture(scope="module")
def vitamin_k_product() -> tuple[SupplementEnricherV3, dict]:
    normalizer = EnhancedDSLDNormalizer()
    cleaned_rows = [
        normalizer._process_single_ingredient_enhanced(
            _label_row("Vitamin K", 100, "Vitamin K1"),
            is_active=True,
        ),
        normalizer._process_single_ingredient_enhanced(
            _label_row("Vitamin K2", 30, "Menaquinone-7"),
            is_active=True,
        ),
    ]
    return (
        SupplementEnricherV3(
            config_path=str(SCRIPTS_DIR / "config" / "enrichment_config.json")
        ),
        {
            "id": "246021",
            "fullName": "Calcium K/D",
            "activeIngredients": cleaned_rows,
        },
    )


def test_k2_keeps_specific_identity_form_score_and_dose(
    vitamin_k_product: tuple[SupplementEnricherV3, dict],
) -> None:
    enricher, product = vitamin_k_product
    cleaned_rows = product["activeIngredients"]

    assert cleaned_rows[0]["canonical_id"] == "vitamin_k"
    assert cleaned_rows[1]["canonical_id"] == "vitamin_k2"

    quality = enricher._collect_ingredient_quality_data(product)
    rows = {
        row["raw_source_text"]: row
        for row in quality["ingredients"]
        if row.get("raw_source_text") in {"Vitamin K", "Vitamin K2"}
    }

    # The label's declared K1 form becomes the enriched identity, while the
    # cleaner's bare "Vitamin K" source text remains available for fidelity.
    assert rows["Vitamin K"]["canonical_id"] == "vitamin_k1"
    assert rows["Vitamin K2"]["canonical_id"] == "vitamin_k2"
    assert rows["Vitamin K2"]["bio_score"] == 12
    assert rows["Vitamin K"].get("is_compound_duplicate") is not True
    assert rows["Vitamin K2"].get("is_compound_duplicate") is not True

    rda = enricher._collect_rda_ul_data(
        product,
        min_servings_per_day=1,
        max_servings_per_day=3,
    )
    analyzed = {
        row["ingredient"]: row
        for row in rda["analyzed_ingredients"]
        if row.get("ingredient") in {"Vitamin K", "Vitamin K2"}
    }

    assert analyzed["Vitamin K"]["per_day_max"] == 300
    assert analyzed["Vitamin K2"]["per_day_max"] == 90
    assert analyzed["Vitamin K2"].get("skip_ul_reason") != "compound_duplicate_row"
    assert sum(row["per_day_max"] for row in analyzed.values()) == 390


def test_export_group_is_explicit_and_excludes_k3() -> None:
    build_final_db.IQM_REFERENCE_INDEX = None

    assert build_final_db._nutrient_group_id("vitamin_k") is None
    assert build_final_db._nutrient_group_id("vitamin_k1") == "vitamin_k"
    assert build_final_db._nutrient_group_id("vitamin_k2") == "vitamin_k"
    assert build_final_db._nutrient_group_id("vitamin_k3") is None
