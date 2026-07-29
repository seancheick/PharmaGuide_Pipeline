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


def _label_row(name: str, amount_mcg: float, form: str | None) -> dict:
    return {
        "name": name,
        "ingredientGroup": "Vitamin K",
        "category": "vitamin",
        "quantity": [{"quantity": amount_mcg, "unit": "mcg"}],
        "forms": [{"name": form}] if form else [],
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


@pytest.mark.parametrize(
    ("declared_form", "expected_form"),
    [
        (None, "vitamin k2 (unspecified subtype)"),
        ("MenaQ7 Menaquinone", "menaquinone-7 (MK-7)"),
    ],
)
def test_k2_form_resolution_never_infers_inactive_cis_isomer(
    declared_form: str | None,
    expected_form: str,
) -> None:
    normalizer = EnhancedDSLDNormalizer()
    cleaned_row = normalizer._process_single_ingredient_enhanced(
        _label_row("Vitamin K2", 50, declared_form),
        is_active=True,
    )
    product = {
        "id": "k2-form-resolution-canary",
        "fullName": "Vitamin K2 form resolution canary",
        "activeIngredients": [cleaned_row],
    }
    enricher = SupplementEnricherV3(
        config_path=str(SCRIPTS_DIR / "config" / "enrichment_config.json")
    )

    assert cleaned_row["canonical_id"] == "vitamin_k2"
    quality = enricher._collect_ingredient_quality_data(product)
    assert len(quality["ingredients"]) == 1
    row = quality["ingredients"][0]
    assert row["canonical_id"] == "vitamin_k2"
    assert row["matched_form"] == expected_form
    assert row["matched_form"] != "vitamin K2 (cis form)"
    if declared_form is None:
        assert row["bio_score"] == 6
        assert row["score"] == 6
        form_contract = enricher.databases["ingredient_quality_map"][
            "vitamin_k2"
        ]["forms"][expected_form]
        assert form_contract["absorption_structured"] == {"quality": "unknown"}


def test_k2_menaq7_from_form_uses_mk7_in_production_label_shape() -> None:
    normalizer = EnhancedDSLDNormalizer()
    label_row = _label_row("Vitamin K2", 50, "MenaQ7 Menaquinone")
    label_row["ingredientGroup"] = "Vitamin K (menaquinone)"
    label_row["forms"][0].update(
        {
            "ingredientId": 223198,
            "order": 1,
            "prefix": "from",
            "category": "vitamin",
            "ingredientGroup": "Vitamin K (menaquinone)",
        }
    )
    cleaned_row = normalizer._process_single_ingredient_enhanced(
        label_row,
        is_active=True,
    )
    product = {
        "id": "203095",
        "fullName": "Vein Support",
        "activeIngredients": [cleaned_row],
    }
    enricher = SupplementEnricherV3(
        config_path=str(SCRIPTS_DIR / "config" / "enrichment_config.json")
    )

    quality = enricher._collect_ingredient_quality_data(product)
    assert len(quality["ingredients"]) == 1
    row = quality["ingredients"][0]
    assert row["canonical_id"] == "vitamin_k2"
    assert row["matched_form"] == "menaquinone-7 (MK-7)"
    assert row["bio_score"] == 12


def test_k1_as_form_overrides_unspecified_parent_in_production_label_shape() -> None:
    normalizer = EnhancedDSLDNormalizer()
    label_row = _label_row("Vitamin K", 50, "Vitamin K1")
    label_row["ingredientGroup"] = "Vitamin K (unspecified)"
    label_row["forms"][0].update(
        {
            "ingredientId": 279025,
            "order": 1,
            "prefix": "as",
            "category": "vitamin",
            "ingredientGroup": "Vitamin K",
            "uniiCode": "A034SE7857",
        }
    )
    cleaned_row = normalizer._process_single_ingredient_enhanced(
        label_row,
        is_active=True,
    )
    product = {
        "id": "182730",
        "fullName": "Athletic Pure Pack",
        "activeIngredients": [cleaned_row],
    }
    enricher = SupplementEnricherV3(
        config_path=str(SCRIPTS_DIR / "config" / "enrichment_config.json")
    )

    assert cleaned_row["canonical_id"] == "vitamin_k1"
    quality = enricher._collect_ingredient_quality_data(product)
    assert len(quality["ingredients"]) == 1
    row = quality["ingredients"][0]
    assert row["canonical_id"] == "vitamin_k1"
    assert row["mapped"] is True
    assert row["matched_form"] == "phylloquinone"
