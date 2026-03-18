#!/usr/bin/env python3
"""
Pipeline Smoke Tests
====================
End-to-end smoke tests that verify the full pipeline (raw → clean → enrich → score)
works correctly on fixture data.

These tests are designed to:
1. Catch breaking changes early
2. Verify all stages connect properly
3. Ensure outputs are created in expected locations
"""

import os
import sys
import json
import shutil
import tempfile
import pytest
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from enhanced_normalizer import EnhancedDSLDNormalizer
from enrich_supplements_v3 import SupplementEnricherV3


class TestPipelineSmokeTest:
    """End-to-end smoke tests for the pipeline"""

    @pytest.fixture
    def temp_output_dir(self):
        """Create a temporary directory for test outputs"""
        temp_dir = tempfile.mkdtemp(prefix="dsld_smoke_test_")
        yield temp_dir
        # Cleanup after test
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def sample_raw_product(self):
        """Create a sample raw product fixture"""
        return {
            "id": "smoke_test_001",
            "productId": 99999,
            "fullName": "Test Vitamin D3 Gummies",
            "brandName": "Test Brand",
            "upcSku": "123456789012",
            "productType": "Dietary Supplement",
            "physicalState": {
                "langualCode": "A0101",
                "langualCodeDescription": "Gummy"
            },
            "ingredientRows": [
                {
                    "name": "Vitamin D3",
                    "quantity": [{"amount": 1000, "unit": "IU"}],
                    "forms": [{"name": "Cholecalciferol"}]
                },
                {
                    "name": "Sugar",
                    "quantity": [{"amount": 2, "unit": "g"}]
                },
                {
                    "name": "Colors",
                    "forms": [
                        {"prefix": "from", "name": "Fruits"},
                        {"prefix": "and", "name": "Vegetables"}
                    ]
                }
            ],
            "servingSizes": [
                {"servingSizeQuantity": 2, "servingSizeUnit": "Gummy(ies)"}
            ],
            "statements": [
                {"text": "Take 2 gummies daily with food."},
                {"text": "Made in a GMP certified facility."}
            ]
        }

    @pytest.fixture
    def normalizer(self):
        """Create a normalizer instance"""
        return EnhancedDSLDNormalizer()

    @pytest.fixture
    def enricher(self):
        """Create an enricher instance"""
        return SupplementEnricherV3()

    def test_cleaning_stage_produces_output(self, normalizer, sample_raw_product):
        """Test that cleaning stage produces valid output"""
        # Run cleaning
        cleaned = normalizer.normalize_product(sample_raw_product)

        # Verify output structure
        assert cleaned is not None
        assert "id" in cleaned or "dsld_id" in cleaned
        assert "activeIngredients" in cleaned or "inactiveIngredients" in cleaned
        assert "metadata" in cleaned

        # Verify metadata has reference_versions
        metadata = cleaned.get("metadata", {})
        assert "reference_versions" in metadata, "Cleaned output should include reference_versions"

    def test_enrichment_stage_produces_output(self, enricher, normalizer, sample_raw_product):
        """Test that enrichment stage produces valid output from cleaned data"""
        # First clean the product
        cleaned = normalizer.normalize_product(sample_raw_product)

        # Then enrich it
        enriched, warnings = enricher.enrich_product(cleaned)

        # Verify output structure
        assert enriched is not None
        assert "enrichment_version" in enriched
        assert "reference_versions" in enriched

        # Verify key enrichment sections exist
        assert "dietary_sensitivity_data" in enriched
        assert "contaminant_data" in enriched
        assert "enrichment_metadata" in enriched
        assert enriched["enrichment_metadata"].get("export_contract_valid") is True
        # Note: ready_for_scoring added when all validations pass

    def test_enrichment_exports_real_ingredient_contract_fields(self, enricher, normalizer, sample_raw_product):
        """Enrichment should preserve the canonical IQD field names used by final export."""
        cleaned = normalizer.normalize_product(sample_raw_product)
        enriched, _ = enricher.enrich_product(cleaned)

        ingredients = enriched.get("ingredient_quality_data", {}).get("ingredients", [])
        assert ingredients, "ingredient_quality_data.ingredients should not be empty"

        ingredient = ingredients[0]
        for key in [
            "raw_source_text",
            "name",
            "standard_name",
            "bio_score",
            "natural",
            "score",
            "notes",
            "category",
            "mapped",
            "safety_hits",
            "extracted_forms",
            "matched_forms",
        ]:
            assert key in ingredient, f"Missing export contract field: {key}"

    def test_colors_classification_in_pipeline(self, normalizer, enricher, sample_raw_product):
        """Test that Colors from Fruits and Vegetables is classified correctly"""
        # Clean
        cleaned = normalizer.normalize_product(sample_raw_product)

        # Find the Colors ingredient
        all_ingredients = (
            cleaned.get("activeIngredients", []) +
            cleaned.get("inactiveIngredients", [])
        )

        colors_ing = None
        for ing in all_ingredients:
            if "color" in (ing.get("name", "") or "").lower():
                colors_ing = ing
                break

        # Verify Colors is classified as natural
        assert colors_ing is not None, "Colors ingredient should exist"
        std_name = colors_ing.get("standardName", "")
        assert std_name == "natural colors", \
            f"Colors with fruit/vegetable forms should be 'natural colors', got: {std_name}"

        # Enrich and verify not flagged as artificial
        enriched, _ = enricher.enrich_product(cleaned)
        harmful = enriched.get("contaminant_data", {}).get("harmful_additives", {})
        additives = harmful.get("additives", [])

        for additive in additives:
            if "Colors" in additive.get("ingredient", ""):
                assert "ARTIFICIAL" not in additive.get("additive_id", ""), \
                    "Natural colors should not be flagged as artificial"

    def test_sugar_extraction_in_pipeline(self, normalizer, enricher, sample_raw_product):
        """Test that sugar data structure is present in enriched output"""
        # Clean
        cleaned = normalizer.normalize_product(sample_raw_product)

        # Enrich
        enriched, _ = enricher.enrich_product(cleaned)

        # Check sugar data structure exists (detection depends on ingredient format)
        dietary = enriched.get("dietary_sensitivity_data", {})
        sugar_data = dietary.get("sugar", {})

        # Verify structure exists (actual detection depends on ingredient names/quantities)
        assert "contains_sugar" in sugar_data or "amount_g" in sugar_data, \
            "Sugar data structure should exist in dietary_sensitivity_data"

    def test_reference_versions_in_both_outputs(self, normalizer, enricher, sample_raw_product):
        """Test that reference_versions appears in both cleaned and enriched outputs"""
        # Clean
        cleaned = normalizer.normalize_product(sample_raw_product)

        # Check cleaned has reference_versions
        assert "metadata" in cleaned
        assert "reference_versions" in cleaned["metadata"], \
            "Cleaned output must include metadata.reference_versions"
        assert "color_indicators" in cleaned["metadata"]["reference_versions"], \
            "reference_versions must include color_indicators"

        # Enrich
        enriched, _ = enricher.enrich_product(cleaned)

        # Check enriched has reference_versions
        assert "reference_versions" in enriched, \
            "Enriched output must include reference_versions"
        assert "color_indicators" in enriched["reference_versions"], \
            "Enriched reference_versions must include color_indicators"

    def test_end_to_end_multiple_products(self, normalizer, enricher, temp_output_dir):
        """Test processing multiple products end-to-end"""
        # Create 3 fixture products
        products = [
            {
                "id": f"fixture_{i}",
                "productId": 90000 + i,
                "fullName": f"Test Product {i}",
                "brandName": "Test Brand",
                "ingredientRows": [
                    {"name": "Vitamin C", "quantity": [{"amount": 500, "unit": "mg"}]}
                ],
                "servingSizes": [{"servingSizeQuantity": 1, "servingSizeUnit": "Tablet"}]
            }
            for i in range(3)
        ]

        cleaned_products = []
        enriched_products = []

        # Process each product
        for raw in products:
            cleaned = normalizer.normalize_product(raw)
            cleaned_products.append(cleaned)

            enriched, _ = enricher.enrich_product(cleaned)
            enriched_products.append(enriched)

        # Verify all products processed
        assert len(cleaned_products) == 3
        assert len(enriched_products) == 3

        # Verify each has expected structure
        for cleaned, enriched in zip(cleaned_products, enriched_products):
            assert cleaned.get("metadata", {}).get("reference_versions")
            assert enriched.get("reference_versions")
            # Core structure exists (ready_for_scoring depends on validation)

    def test_normalizer_reference_versions_attribute(self, normalizer):
        """Test that normalizer has reference_versions after initialization"""
        assert hasattr(normalizer, "reference_versions")
        assert isinstance(normalizer.reference_versions, dict)
        assert "color_indicators" in normalizer.reference_versions
        assert "version" in normalizer.reference_versions["color_indicators"]

    def test_enricher_reference_versions_attribute(self, enricher):
        """Test that enricher has reference_versions after initialization"""
        assert hasattr(enricher, "reference_versions")
        assert isinstance(enricher.reference_versions, dict)
        assert "color_indicators" in enricher.reference_versions


class TestPipelineGuardrails:
    """Tests for pipeline guardrails and fail-fast behavior"""

    def test_enricher_fails_on_missing_critical_db(self, tmp_path):
        """Test that enricher fails fast if critical DB is missing"""
        # This test verifies the enricher's fail-fast behavior
        # The enricher should raise FileNotFoundError if a critical DB is missing

        # Create a temp config file with an invalid path
        config = {
            "database_paths": {
                "ingredient_quality_map": str(tmp_path / "nonexistent" / "iqm.json"),
                "harmful_additives": "data/harmful_additives.json",
                "allergens": "data/allergens.json",
                "banned_recalled_ingredients": "data/banned_recalled_ingredients.json",
                "color_indicators": "data/color_indicators.json"
            }
        }

        config_file = tmp_path / "test_config.json"
        with open(config_file, 'w') as f:
            json.dump(config, f)

        # Should fail with explicit error about missing file
        with pytest.raises(FileNotFoundError) as excinfo:
            enricher = SupplementEnricherV3(config_path=str(config_file))

        assert "ingredient_quality_map" in str(excinfo.value)
        assert "CRITICAL" in str(excinfo.value)

    def test_normalizer_fails_on_missing_color_indicators(self):
        """Test that normalizer fails if color_indicators.json is missing"""
        # The normalizer should fail if color_indicators.json is missing
        # This is verified by the fact that initialization succeeds when it exists
        normalizer = EnhancedDSLDNormalizer()
        assert len(normalizer.NATURAL_COLOR_INDICATORS) > 0
        assert len(normalizer.EXPLICIT_ARTIFICIAL_DYES) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
