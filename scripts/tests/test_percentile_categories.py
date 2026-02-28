#!/usr/bin/env python3
"""Percentile category inference and schema tests."""

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from enrich_supplements_v3 import SupplementEnricherV3


def _enriched_stub(canonical_ids, form_factor="powder", supp_type="specialty"):
    return {
        "ingredient_quality_data": {
            "ingredients_scorable": [{"canonical_id": item} for item in canonical_ids],
            "ingredients": [{"canonical_id": item} for item in canonical_ids],
        },
        "form_factor": form_factor,
        "supplement_type": {"type": supp_type},
    }


class TestPercentileCategoryInference:
    @pytest.fixture
    def enricher(self):
        return SupplementEnricherV3()

    def test_greens_powder_classification(self, enricher):
        product = {
            "fullName": "Raw Organic Perfect Food Green Superfood Juiced Greens Powder",
            "product_name": "Raw Organic Perfect Food Greens",
        }
        enriched = _enriched_stub(
            ["spirulina", "chlorella", "barley_grass", "wheatgrass"],
            form_factor="powder",
        )

        result = enricher._infer_percentile_category(product, enriched)
        assert result["percentile_category"] == "greens_powder"
        assert result["percentile_category_source"] == "inferred"
        assert result["percentile_category_confidence"] >= 0.4

    def test_protein_powder_not_greens(self, enricher):
        product = {
            "fullName": "Gold Standard Whey Protein Powder",
            "product_name": "Gold Standard Whey",
        }
        enriched = _enriched_stub(
            ["whey_protein_isolate", "whey_protein_concentrate"],
            form_factor="powder",
        )

        result = enricher._infer_percentile_category(product, enriched)
        assert result["percentile_category"] == "protein_powder"
        assert result["percentile_category"] != "greens_powder"

    def test_green_tea_extract_capsule_not_greens_powder(self, enricher):
        product = {
            "fullName": "Green Tea Extract 500mg Capsules",
            "product_name": "Green Tea Extract",
        }
        enriched = _enriched_stub(["green_tea_extract"], form_factor="capsule")

        result = enricher._infer_percentile_category(product, enriched)
        assert result["percentile_category"] != "greens_powder"

    def test_explicit_percentile_category_overrides_inference(self, enricher):
        product = {
            "fullName": "Mixed Product Name",
            "percentile_category": "fish_oil",
        }
        enriched = _enriched_stub(["spirulina", "chlorella"], form_factor="powder")

        result = enricher._infer_percentile_category(product, enriched)
        assert result["percentile_category"] == "fish_oil"
        assert result["percentile_category_source"] == "explicit"
        assert result["percentile_category_confidence"] == 1.0


class TestPercentileCategorySchema:
    def test_percentile_categories_schema_shape(self):
        path = Path(__file__).parent.parent / "data" / "percentile_categories.json"
        data = json.loads(path.read_text(encoding="utf-8"))

        assert isinstance(data.get("_metadata"), dict)
        assert data["_metadata"].get("schema_version") == "4.1.0"
        assert isinstance(data.get("categories"), dict)
        assert isinstance(data.get("classification_rules"), dict)

        fallback_ids = [
            category_id
            for category_id, category_def in data["categories"].items()
            if isinstance(category_def, dict) and category_def.get("is_fallback")
        ]
        assert len(fallback_ids) == 1

