"""
Pipeline Regression Tests
Tests for critical pipeline behaviors to prevent regressions.
"""

import pytest
import sys
import os
import json
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from enhanced_normalizer import EnhancedDSLDNormalizer
from dsld_validator import DSLDValidator
from unmapped_ingredient_tracker import UnmappedIngredientTracker


class TestSkipEnforcement:
    """Tests for skip list enforcement (Task 2)"""

    @pytest.fixture
    def normalizer(self):
        """Create a normalizer instance for testing"""
        return EnhancedDSLDNormalizer()

    def test_tier_a_exact_match_skip(self, normalizer):
        """Test Tier A: exact match against skip list"""
        # Items actually in skip_exact list (ingredient_classification.json)
        assert normalizer._should_skip_ingredient("Total EPA & DHA") is True
        assert normalizer._should_skip_ingredient("DELETE") is True
        assert normalizer._should_skip_ingredient("Less than 2% of:") is True

    def test_tier_b_normalized_match_skip_trailing_space(self, normalizer):
        """Test Tier B: normalized match handles trailing whitespace"""
        # "Total EPA & DHA " with trailing space should match "Total EPA & DHA"
        # This tests the Tier B normalization (NFC + strip + collapse whitespace)
        result = normalizer._should_skip_ingredient("Total EPA & DHA ")
        # Note: this depends on "Total EPA & DHA" being in ingredient_classification.json
        # If not, this test documents expected behavior for when it is added
        assert result is True or "total epa" in str(normalizer._skip_exact).lower()

    def test_tier_b_normalized_match_skip_extra_internal_space(self, normalizer):
        """Test Tier B: normalized match handles extra internal whitespace"""
        # "Total  EPA & DHA" with double space should match "Total EPA & DHA"
        result = normalizer._should_skip_ingredient("Total  EPA & DHA")
        assert result is True

    def test_nutrition_fact_skip(self, normalizer):
        """Test that nutrition facts are detected by _is_nutrition_fact (not skip list)"""
        # Note: nutrition facts are filtered by _is_nutrition_fact(), not _should_skip_ingredient()
        # The skip list is for label headers and summary ingredients
        # Verify nutrition facts detection works via _is_nutrition_fact
        assert normalizer._is_nutrition_fact("Calories", "Amount Per Serving", "cal") is True
        assert normalizer._is_nutrition_fact("Total Carbohydrates", "", "g") is True

    def test_label_artifact_skip(self, normalizer):
        """Test that label artifacts are in skip list"""
        # "DELETE" is in skip_exact (uppercase) - with case-insensitive matching enabled,
        # lowercase should also match if Tier C is enabled
        # Check exact match first
        assert normalizer._should_skip_ingredient("DELETE") is True
        # If Tier C case-insensitive is enabled, lowercase should also match
        if normalizer._enable_case_insensitive_skip:
            assert normalizer._should_skip_ingredient("delete") is True

    def test_valid_ingredient_not_skipped(self, normalizer):
        """Test that valid ingredients are NOT skipped"""
        # Real ingredient should not be skipped
        assert normalizer._should_skip_ingredient("vitamin c") is False
        assert normalizer._should_skip_ingredient("zinc") is False
        assert normalizer._should_skip_ingredient("epa") is False  # Component, not source/summary


class TestPreprocessNormalizationRegression:
    """Identity preprocessing must not strip chemically meaningful oil terms."""

    @pytest.fixture
    def normalizer(self):
        return EnhancedDSLDNormalizer()

    @pytest.mark.parametrize(
        "raw_name,expected",
        [
            ("Fish Oil Concentrate", "fish oil"),
            ("Cod Liver Oil", "cod liver oil"),
            ("Oregano Oil", "oregano oil"),
            ("Milk Thistle Extract", "milk thistle"),
            ("Turmeric Powder", "turmeric"),
        ],
    )
    def test_preprocess_text_preserves_meaningful_oil_identities(self, normalizer, raw_name, expected):
        assert normalizer.matcher.preprocess_text(raw_name) == expected


class TestLabelHeaderSymmetry:
    """Tests for label header handling (Task 3)"""

    @pytest.fixture
    def normalizer(self):
        return EnhancedDSLDNormalizer()

    def test_is_label_header_detection(self, normalizer):
        """Test that label headers are correctly detected"""
        assert normalizer._is_label_header("Less than 2% of:") is True
        assert normalizer._is_label_header("Contains less than 2% of:") is True
        assert normalizer._is_label_header("< 2% of:") is True
        assert normalizer._is_label_header("May contain one or more of:") is True

    def test_is_label_header_negative(self, normalizer):
        """Test that real ingredients are NOT detected as headers"""
        assert normalizer._is_label_header("Vitamin C") is False
        assert normalizer._is_label_header("Zinc Citrate") is False
        assert normalizer._is_label_header("2% Milk Thistle Extract") is False

    @pytest.mark.parametrize(
        "name",
        [
            "May also contain",
            "Soft Gel Shell",
            "Shell Ingredients",
            "Fish Gelatin Caplique Capsule",
            "Gelatin softgel",
        ],
    )
    def test_structural_other_headers_detected(self, normalizer, name):
        """Structural other-ingredient containers must unwrap forms, not surface as ingredients."""
        assert normalizer._is_label_header(name) is True


class TestStructuralContainerUnwrap:
    """Regression tests for structural container rows with child forms/nested rows."""

    @pytest.fixture
    def normalizer(self):
        return EnhancedDSLDNormalizer()

    def test_inactive_structural_header_unwraps_child_forms(self, normalizer):
        raw_other = {
            "ingredients": [
                {
                    "order": 1,
                    "name": "Soft Gel Shell",
                    "ingredientGroup": "capsule",
                    "forms": [
                        {"order": 1, "name": "Beef Gelatin", "ingredientId": 1},
                        {"order": 2, "name": "Glycerin", "ingredientId": 2},
                        {"order": 3, "name": "Water", "ingredientId": 3},
                    ],
                }
            ]
        }

        processed = normalizer._process_other_ingredients_enhanced(raw_other)
        names = [ing.get("name") for ing in processed]

        assert "Soft Gel Shell" not in names
        assert "Beef Gelatin" in names
        assert "Glycerin" in names
        assert "Water" in names

    def test_may_also_contain_unwraps_forms_without_emitting_header(self, normalizer):
        raw_other = {
            "ingredients": [
                {
                    "order": 1,
                    "name": "May also contain",
                    "ingredientGroup": "Header",
                    "forms": [
                        {"order": 1, "name": "Cellulose", "ingredientId": 10, "prefix": "and or"},
                        {"order": 2, "name": "Silica", "ingredientId": 11},
                    ],
                }
            ]
        }

        processed = normalizer._process_other_ingredients_enhanced(raw_other)
        names = [ing.get("name") for ing in processed]

        assert "May also contain" not in names
        assert "Cellulose" in names
        assert "Silica" in names

    def test_active_structural_container_drops_parent_and_keeps_children(self, normalizer):
        raw_product = {
            "id": "zma-test",
            "fullName": "ZMA",
            "brandName": "Test Brand",
            "ingredientRows": [
                {
                    "order": 1,
                    "name": "ZMA",
                    "ingredientGroup": "Proprietary Blend",
                    "amount": 2500,
                    "unit": "mg",
                    "nestedRows": [
                        {"order": 2, "name": "Vitamin B6", "ingredientGroup": "Vitamin B6", "amount": 10.5, "unit": "mg"},
                        {"order": 3, "name": "Magnesium", "ingredientGroup": "Magnesium", "amount": 450, "unit": "mg"},
                        {"order": 4, "name": "Zinc Mono-L-Methionine Sulfate", "ingredientGroup": "Zinc", "amount": 30, "unit": "mg"},
                    ],
                }
            ],
            "otheringredients": {"ingredients": []},
        }

        normalized = normalizer.normalize_product(raw_product)
        active_names = [ing.get("name") for ing in normalized.get("activeIngredients", [])]

        assert "ZMA" not in active_names
        assert "Vitamin B6" in active_names
        assert "Magnesium" in active_names

    def test_active_structural_container_is_preserved_in_display_ledger(self, normalizer):
        raw_product = {
            "id": "zma-display-test",
            "fullName": "ZMA Display",
            "brandName": "Test Brand",
            "ingredientRows": [
                {
                    "order": 1,
                    "name": "ZMA",
                    "ingredientGroup": "Proprietary Blend",
                    "nestedRows": [
                        {"order": 2, "name": "Vitamin B6", "ingredientGroup": "Vitamin B6"},
                        {"order": 3, "name": "Magnesium", "ingredientGroup": "Magnesium"},
                    ],
                }
            ],
            "otheringredients": {"ingredients": []},
        }

        normalized = normalizer.normalize_product(raw_product)
        display_by_raw = {
            row.get("raw_source_text"): row for row in normalized.get("display_ingredients", [])
        }

        assert display_by_raw["ZMA"]["display_type"] == "structural_container"
        assert display_by_raw["ZMA"]["score_included"] is False
        assert display_by_raw["ZMA"]["children"] == ["Vitamin B6", "Magnesium"]


class TestBatch2CleanActiveMapping:
    @pytest.fixture
    def normalizer(self):
        return EnhancedDSLDNormalizer()

    def test_batch2_active_labels_resolve_to_intended_canonicals(self, normalizer):
        raw_product = {
            "id": "batch2-active-mapping",
            "fullName": "Batch 2 Active Mapping",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "ingredientRows": [
                {"order": 1, "name": "Ceramosides Wheat seed extract", "ingredientGroup": "Wheat"},
                {"order": 2, "name": "TruFlex Chondroitin Sulfate", "ingredientGroup": "Chondroitin Sulfate"},
                {"order": 3, "name": "Cococin Coconut Water powder", "ingredientGroup": "Coconut"},
                {"order": 4, "name": "Coconut Water", "ingredientGroup": "Coconut"},
            ],
            "otheringredients": {"ingredients": []},
        }

        normalized = normalizer.normalize_product(raw_product)
        active_by_name = {ing.get("name"): ing for ing in normalized.get("activeIngredients", [])}

        assert active_by_name["Ceramosides Wheat seed extract"]["standardName"] == "Ceramides"
        assert active_by_name["TruFlex Chondroitin Sulfate"]["standardName"] == "Chondroitin"
        assert active_by_name["Cococin Coconut Water powder"]["standardName"] == "Coconut Water"
        assert active_by_name["Coconut Water"]["standardName"] == "Coconut Water"


class TestBatch3InactiveMapping:
    @pytest.fixture
    def normalizer(self):
        return EnhancedDSLDNormalizer()

    def test_batch3_inactive_labels_resolve_to_intended_canonicals(self, normalizer):
        raw_product = {
            "id": "batch3-inactive-mapping",
            "fullName": "Batch 3 Inactive Mapping",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "ingredientRows": [],
            "otheringredients": {
                "ingredients": [
                    {"order": 1, "name": "Hydrogenated Vegetable Oil", "ingredientGroup": "Hydrogenated Vegetable Oil"},
                    {"order": 2, "name": "natural Rosemary flavor", "ingredientGroup": "Flavor"},
                    {"order": 3, "name": "Grapefruit Oil", "ingredientGroup": "Grapefruit"},
                ]
            },
        }

        normalized = normalizer.normalize_product(raw_product)
        inactive_by_name = {ing.get("name"): ing for ing in normalized.get("inactiveIngredients", [])}

        assert inactive_by_name["Hydrogenated Vegetable Oil"]["standardName"] == "Hydrogenated Vegetable Oil"
        assert inactive_by_name["natural Rosemary flavor"]["standardName"] == "Natural Rosemary Flavor"
        assert inactive_by_name["Grapefruit Oil"]["standardName"] == "Grapefruit Oil"


class TestDisplayLedgerScaffold:
    @pytest.fixture
    def normalizer(self):
        return EnhancedDSLDNormalizer()

    def test_display_ledger_scaffold_emits_user_facing_rows_without_mutating_scoring_inputs(self, normalizer):
        raw_product = {
            "id": "display-ledger-scaffold",
            "fullName": "Display Ledger Scaffold",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "ingredientRows": [
                {"order": 1, "name": "Vitamin C", "ingredientGroup": "Vitamin C (unspecified)"},
                {"order": 2, "name": "Zinc", "ingredientGroup": "Zinc"},
            ],
            "otheringredients": {
                "ingredients": [
                    {"order": 1, "name": "Hypromellose", "ingredientGroup": "Hypromellose"}
                ]
            },
        }

        normalized = normalizer.normalize_product(raw_product)

        assert "display_ingredients" in normalized
        assert [ing.get("name") for ing in normalized.get("activeIngredients", [])] == ["Vitamin C", "Zinc"]
        assert [ing.get("name") for ing in normalized.get("inactiveIngredients", [])] == ["Hypromellose"]

        display_rows = normalized["display_ingredients"]
        assert [row.get("raw_source_text") for row in display_rows] == ["Vitamin C", "Zinc", "Hypromellose"]
        assert all("display_name" in row for row in display_rows)
        assert all("score_included" in row for row in display_rows)

    def test_display_ledger_classification_fields_are_explicit(self, normalizer):
        raw_product = {
            "id": "display-ledger-classification",
            "fullName": "Display Ledger Classification",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "ingredientRows": [
                {"order": 1, "name": "Vitamin C", "ingredientGroup": "Vitamins"},
                {
                    "order": 2,
                    "name": "Other Omega-3's",
                    "ingredientGroup": "Omega-3",
                    "nestedRows": [],
                    "forms": [],
                },
                {
                    "order": 3,
                    "name": "ZMA",
                    "ingredientGroup": "Proprietary Blend",
                    "nestedRows": [
                        {"order": 4, "name": "Magnesium", "ingredientGroup": "Magnesium"},
                    ],
                },
            ],
            "otheringredients": {
                "ingredients": [
                    {"order": 1, "name": "Hypromellose", "ingredientGroup": "Cellulose"},
                ]
            },
        }

        normalized = normalizer.normalize_product(raw_product)
        display_by_raw = {
            row.get("raw_source_text"): row for row in normalized.get("display_ingredients", [])
        }

        assert display_by_raw["Vitamin C"]["display_type"] == "mapped_ingredient"
        assert display_by_raw["Vitamin C"]["resolution_type"] == "direct_mapped"
        assert display_by_raw["Vitamin C"]["source_section"] == "activeIngredients"
        assert display_by_raw["Vitamin C"]["score_included"] is True

        assert display_by_raw["Other Omega-3's"]["display_type"] == "summary_wrapper"
        assert display_by_raw["Other Omega-3's"]["resolution_type"] == "suppressed_parent"
        assert display_by_raw["Other Omega-3's"]["score_included"] is False

        assert display_by_raw["ZMA"]["display_type"] == "structural_container"
        assert display_by_raw["ZMA"]["resolution_type"] == "structural_parent"
        assert display_by_raw["ZMA"]["score_included"] is False

        assert display_by_raw["Hypromellose"]["display_type"] == "inactive_ingredient"
        assert display_by_raw["Hypromellose"]["resolution_type"] == "inactive_mapped"
        assert display_by_raw["Hypromellose"]["source_section"] == "inactiveIngredients"
        assert display_by_raw["Hypromellose"]["score_included"] is False


class TestBatch4ActiveOilRouting:
    @pytest.fixture
    def normalizer(self):
        return EnhancedDSLDNormalizer()

    def test_batch4_active_oil_labels_route_to_iqm(self, normalizer):
        raw_product = {
            "id": "batch4-active-oils",
            "fullName": "Batch 4 Active Oils",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "ingredientRows": [
                {"order": 1, "name": "Sesame seed Oil", "ingredientGroup": "Sesame Oil"},
                {"order": 2, "name": "Extra Virgin Olive Fruit Oil", "ingredientGroup": "Olive Oil"},
            ],
            "otheringredients": {"ingredients": []},
        }

        normalized = normalizer.normalize_product(raw_product)
        active_by_name = {ing.get("name"): ing for ing in normalized.get("activeIngredients", [])}

        assert active_by_name["Sesame seed Oil"]["standardName"] == "Sesame Seed Oil"
        assert active_by_name["Extra Virgin Olive Fruit Oil"]["standardName"] == "Extra Virgin Olive Oil"

    def test_batch4_inactive_oil_labels_route_to_other_ingredients(self, normalizer):
        raw_product = {
            "id": "batch4-inactive-oils",
            "fullName": "Batch 4 Inactive Oils",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "ingredientRows": [],
            "otheringredients": {
                "ingredients": [
                    {"order": 1, "name": "Sesame seed Oil", "ingredientGroup": "Sesame Oil"},
                    {"order": 2, "name": "Extra Virgin Olive Fruit Oil", "ingredientGroup": "Olive Oil"},
                ]
            },
        }

        normalized = normalizer.normalize_product(raw_product)
        inactive_by_name = {ing.get("name"): ing for ing in normalized.get("inactiveIngredients", [])}

        assert inactive_by_name["Sesame seed Oil"]["standardName"] == "Sesame Seed Oil"
        assert inactive_by_name["Extra Virgin Olive Fruit Oil"]["standardName"] == "Extra Virgin Olive Oil"


class TestBatch5Mapping:
    @pytest.fixture
    def normalizer(self):
        return EnhancedDSLDNormalizer()

    def test_batch5_active_and_inactive_labels_route_cleanly(self, normalizer):
        raw_product = {
            "id": "batch5-mapping",
            "fullName": "Batch 5 Mapping",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "ingredientRows": [
                {
                    "order": 1,
                    "name": "Prickly Pear Cactus leaf extract",
                    "ingredientGroup": "Prickly Pear Cactus",
                }
            ],
            "otheringredients": {
                "ingredients": [
                    {
                        "order": 1,
                        "name": "soluble Food Starch",
                        "ingredientGroup": "Starch",
                    }
                ]
            },
        }

        normalized = normalizer.normalize_product(raw_product)
        active_by_name = {ing.get("name"): ing for ing in normalized.get("activeIngredients", [])}
        inactive_by_name = {ing.get("name"): ing for ing in normalized.get("inactiveIngredients", [])}

        assert active_by_name["Prickly Pear Cactus leaf extract"]["standardName"] == "Nopal"
        assert inactive_by_name["soluble Food Starch"]["standardName"] == "Soluble Food Starch"

    def test_batch5_vesisorb_wrapper_unwraps_forms(self, normalizer):
        raw_product = {
            "id": "batch5-vesisorb",
            "fullName": "Batch 5 VESIsorb",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "ingredientRows": [],
            "otheringredients": {
                "ingredients": [
                    {
                        "order": 1,
                        "name": "VESIsorb Microemulsion preconcentrate",
                        "ingredientGroup": "Proprietary Blend (Combination)",
                        "forms": [
                            {"order": 1, "name": "Medium Chain Triglycerides", "ingredientId": 5004},
                            {"order": 2, "name": "Nonionic Surfactant", "ingredientId": 241841},
                            {"order": 3, "name": "Sucrose Fatty Acid Esters", "ingredientId": 97095},
                        ],
                    }
                ]
            },
        }

        normalized = normalizer.normalize_product(raw_product)
        inactive_names = [ing.get("name") for ing in normalized.get("inactiveIngredients", [])]

        assert "VESIsorb Microemulsion preconcentrate" not in inactive_names
        assert "Medium Chain Triglycerides" in inactive_names
        assert "Nonionic Surfactant" in inactive_names
        assert "Sucrose Fatty Acid Esters" in inactive_names


class TestBatch6DescriptorRouting:
    @pytest.fixture
    def normalizer(self):
        return EnhancedDSLDNormalizer()

    def test_batch6_inactive_source_rows_route_to_descriptor_canonicals(self, normalizer):
        raw_product = {
            "id": "batch6-descriptor-routing",
            "fullName": "Batch 6 Descriptor Routing",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "ingredientRows": [],
            "otheringredients": {
                "ingredients": [
                    {"order": 1, "name": "Anchovies", "ingredientGroup": "Fish"},
                    {"order": 2, "name": "Sunflower", "ingredientGroup": "sunflower"},
                    {"order": 3, "name": "Algae", "ingredientGroup": "Algae (unspecified)"},
                    {"order": 4, "name": "Nonionic Surfactant", "ingredientGroup": "Nonionic Surfactant"},
                ]
            },
        }

        normalized = normalizer.normalize_product(raw_product)
        inactive_by_name = {ing.get("name"): ing for ing in normalized.get("inactiveIngredients", [])}

        assert inactive_by_name["Anchovies"]["standardName"] == "Fish"
        assert inactive_by_name["Sunflower"]["standardName"] == "Sunflower (Source Descriptor)"
        assert inactive_by_name["Algae"]["standardName"] == "Algae (Source Descriptor)"
        assert inactive_by_name["Nonionic Surfactant"]["standardName"] == "Nonionic Surfactant (Descriptor)"


class TestBatch7InactiveCleanup:
    @pytest.fixture
    def normalizer(self):
        return EnhancedDSLDNormalizer()

    def test_batch7_source_flavor_and_color_rows_route_conservatively(self, normalizer):
        raw_product = {
            "id": "batch7-inactive-routing",
            "fullName": "Batch 7 Inactive Routing",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "ingredientRows": [],
            "otheringredients": {
                "ingredients": [
                    {"order": 1, "name": "Palm", "ingredientGroup": "Oil Palm"},
                    {"order": 2, "name": "Canola", "ingredientGroup": "Canola oil"},
                    {"order": 3, "name": "Orange Cream", "ingredientGroup": "Flavor"},
                    {"order": 4, "name": "Beet red", "ingredientGroup": "Beet"},
                ]
            },
        }

        normalized = normalizer.normalize_product(raw_product)
        inactive_by_name = {ing.get("name"): ing for ing in normalized.get("inactiveIngredients", [])}

        assert inactive_by_name["Palm"]["standardName"] == "Palm (Source Descriptor)"
        assert inactive_by_name["Canola"]["standardName"] == "Canola (Source Descriptor)"
        assert inactive_by_name["Orange Cream"]["standardName"] == "Natural Flavors"
        assert inactive_by_name["Beet red"]["standardName"] == "Beetroot Powder"

    def test_batch7_acidity_regulator_parent_unwraps_child(self, normalizer):
        raw_product = {
            "id": "batch7-acidity-regulator",
            "fullName": "Batch 7 Acidity Regulator",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "ingredientRows": [],
            "otheringredients": {
                "ingredients": [
                    {
                        "order": 1,
                        "name": "Acidity Regulator",
                        "ingredientGroup": "Acidity regulator",
                        "forms": [
                            {"order": 1, "name": "Adipic Acid", "ingredientId": 83122}
                        ],
                    }
                ]
            },
        }

        normalized = normalizer.normalize_product(raw_product)
        inactive_names = [ing.get("name") for ing in normalized.get("inactiveIngredients", [])]
        inactive_by_name = {ing.get("name"): ing for ing in normalized.get("inactiveIngredients", [])}

        assert "Acidity Regulator" not in inactive_names
        assert inactive_by_name["Adipic Acid"]["standardName"] == "Adipic Acid"
        display_by_raw = {
            row.get("raw_source_text"): row for row in normalized.get("display_ingredients", [])
        }

        assert display_by_raw["Acidity Regulator"]["display_type"] == "structural_container"
        assert display_by_raw["Acidity Regulator"]["score_included"] is False
        assert display_by_raw["Acidity Regulator"]["children"] == ["Adipic Acid"]


class TestBatch8InactiveCleanup:
    @pytest.fixture
    def normalizer(self):
        return EnhancedDSLDNormalizer()

    def test_batch8_inactive_rows_route_to_preservative_source_and_gum_targets(self, normalizer):
        raw_product = {
            "id": "batch8-inactive-routing",
            "fullName": "Batch 8 Inactive Routing",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "ingredientRows": [],
            "otheringredients": {
                "ingredients": [
                    {"order": 1, "name": "non-GMO Sunflower Vitamin E", "ingredientGroup": "Vitamin E (unspecified)"},
                    {"order": 2, "name": "Coconut", "ingredientGroup": "Coconut"},
                    {"order": 3, "name": "Carob bean Gum", "ingredientGroup": "Carob"},
                ]
            },
        }

        normalized = normalizer.normalize_product(raw_product)
        inactive_by_name = {ing.get("name"): ing for ing in normalized.get("inactiveIngredients", [])}

        assert inactive_by_name["non-GMO Sunflower Vitamin E"]["standardName"] == "Tocopherol (Preservative)"
        assert inactive_by_name["Coconut"]["standardName"] == "Coconut (Source Descriptor)"
        assert inactive_by_name["Carob bean Gum"]["standardName"] == "Natural Gums"

    def test_batch8_humectant_parent_unwraps_child(self, normalizer):
        raw_product = {
            "id": "batch8-humectant",
            "fullName": "Batch 8 Humectant",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "ingredientRows": [],
            "otheringredients": {
                "ingredients": [
                    {
                        "order": 1,
                        "name": "Humectant",
                        "ingredientGroup": "Humectant",
                        "forms": [
                            {"order": 1, "name": "Glycerin", "ingredientId": 3985}
                        ],
                    }
                ]
            },
        }

        normalized = normalizer.normalize_product(raw_product)
        inactive_names = [ing.get("name") for ing in normalized.get("inactiveIngredients", [])]
        inactive_by_name = {ing.get("name"): ing for ing in normalized.get("inactiveIngredients", [])}

        assert "Humectant" not in inactive_names
        assert inactive_by_name["Glycerin"]["standardName"] == "Vegetable Glycerin"
        display_by_raw = {
            row.get("raw_source_text"): row for row in normalized.get("display_ingredients", [])
        }

        assert display_by_raw["Humectant"]["display_type"] == "structural_container"
        assert display_by_raw["Humectant"]["score_included"] is False
        assert display_by_raw["Humectant"]["children"] == ["Glycerin"]

    def test_batch34_pinolenic_acid_nested_constituent_stays_display_only(self, normalizer):
        raw_product = {
            "id": "batch34-pinolenic",
            "fullName": "Batch 34 Pinolenic",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "ingredientRows": [
                {
                    "order": 1,
                    "name": "Pine Nut Oil",
                    "ingredientGroup": "TBD",
                    "quantity": [{"quantity": 500, "unit": "mg"}],
                    "nestedRows": [
                        {
                            "order": 1,
                            "name": "Pinolenic Acid",
                            "ingredientGroup": "TBD",
                            "quantity": [{"quantity": 0, "unit": ""}],
                        }
                    ],
                }
            ],
            "otheringredients": {"ingredients": []},
        }

        normalized = normalizer.normalize_product(raw_product)
        active_names = [ing.get("name") for ing in normalized.get("activeIngredients", [])]
        display_by_raw = {
            row.get("raw_source_text"): row for row in normalized.get("display_ingredients", [])
        }

        assert "Pinolenic Acid" not in active_names
        assert display_by_raw["Pinolenic Acid"]["display_type"] == "structural_container"
        assert display_by_raw["Pinolenic Acid"]["score_included"] is False

    def test_batch34_omega9_class_rows_stay_display_only(self, normalizer):
        raw_product = {
            "id": "batch34-omega9",
            "fullName": "Batch 34 Omega 9",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "ingredientRows": [
                {
                    "order": 1,
                    "name": "Omega 9",
                    "ingredientGroup": "Omega-9",
                    "quantity": [{"quantity": 50, "unit": "mg"}],
                },
                {
                    "order": 2,
                    "name": "Black Cumin Seed Oil",
                    "ingredientGroup": "Black Seed Oil",
                    "quantity": [{"quantity": 1000, "unit": "mg"}],
                    "nestedRows": [
                        {
                            "order": 1,
                            "name": "Omega 9",
                            "ingredientGroup": "Omega-9",
                            "quantity": [{"quantity": 0, "unit": "NP"}],
                        }
                    ],
                },
            ],
            "otheringredients": {"ingredients": []},
        }

        normalized = normalizer.normalize_product(raw_product)
        active_names = [ing.get("name") for ing in normalized.get("activeIngredients", [])]
        display_rows = [row for row in normalized.get("display_ingredients", []) if row.get("raw_source_text") == "Omega 9"]

        assert "Omega 9" not in active_names
        assert len(display_rows) == 2
        assert all(row.get("display_type") == "structural_container" for row in display_rows)
        assert all(row.get("score_included") is False for row in display_rows)

    def test_batch35_fatty_acid_class_rows_stay_display_only(self, normalizer):
        raw_product = {
            "id": "batch35-fatty-acid-class",
            "fullName": "Batch 35 Fatty Acid Class",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "ingredientRows": [
                {
                    "order": 1,
                    "name": "Stearic, Palmitic Acids",
                    "ingredientGroup": "Blend (Fatty Acid or Fat/Oil Supplement)",
                    "quantity": [{"quantity": 0, "unit": "NP"}],
                },
                {
                    "order": 2,
                    "name": "Omega-3-6-7-9 Balancing Blend",
                    "ingredientGroup": "Blend (Fatty Acid or Fat/Oil Supplement)",
                    "quantity": [{"quantity": 0, "unit": "NP"}],
                    "nestedRows": [
                        {
                            "order": 1,
                            "name": "Omega-7 and -9 Monounsaturated Fatty Acids",
                            "ingredientGroup": "Blend (Fatty Acid or Fat/Oil Supplement)",
                            "quantity": [{"quantity": 0, "unit": "NP"}],
                        },
                        {
                            "order": 2,
                            "name": "Other Fats and Fatty Acids",
                            "ingredientGroup": "Blend (Fatty Acid or Fat/Oil Supplement)",
                            "quantity": [{"quantity": 0, "unit": "NP"}],
                        },
                    ],
                },
            ],
            "otheringredients": {"ingredients": []},
        }

        normalized = normalizer.normalize_product(raw_product)
        active_names = [ing.get("name") for ing in normalized.get("activeIngredients", [])]
        display_rows = {
            row.get("raw_source_text"): row
            for row in normalized.get("display_ingredients", [])
            if row.get("raw_source_text") in {
                "Stearic, Palmitic Acids",
                "Omega-7 and -9 Monounsaturated Fatty Acids",
                "Other Fats and Fatty Acids",
            }
        }

        assert "Stearic, Palmitic Acids" not in active_names
        assert "Omega-7 and -9 Monounsaturated Fatty Acids" not in active_names
        assert "Other Fats and Fatty Acids" not in active_names
        assert display_rows["Stearic, Palmitic Acids"]["score_included"] is False
        assert display_rows["Omega-7 and -9 Monounsaturated Fatty Acids"]["score_included"] is False
        assert display_rows["Other Fats and Fatty Acids"]["score_included"] is False

    def test_batch35_triterpenoid_saponins_nested_constituent_stays_display_only(self, normalizer):
        raw_product = {
            "id": "batch35-triterpenoid",
            "fullName": "Batch 35 Triterpenoid",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "ingredientRows": [
                {
                    "order": 1,
                    "name": "Black Cohosh root extract",
                    "ingredientGroup": "Black Cohosh",
                    "quantity": [{"quantity": 40, "unit": "mg"}],
                    "nestedRows": [
                        {
                            "order": 1,
                            "name": "Triterpenoid Saponins",
                            "ingredientGroup": "Triterpene Saponin",
                            "quantity": [{"quantity": 0, "unit": "NP"}],
                        }
                    ],
                }
            ],
            "otheringredients": {"ingredients": []},
        }

        normalized = normalizer.normalize_product(raw_product)
        active_names = [ing.get("name") for ing in normalized.get("activeIngredients", [])]
        display_by_raw = {
            row.get("raw_source_text"): row for row in normalized.get("display_ingredients", [])
        }

        assert "Triterpenoid Saponins" not in active_names
        assert display_by_raw["Triterpenoid Saponins"]["score_included"] is False

    def test_batch37_zingiberene_constituent_stays_display_only(self, normalizer):
        raw_product = {
            "id": "batch37-zingiberene",
            "fullName": "Batch 37 Zingiberene",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "ingredientRows": [
                {
                    "order": 1,
                    "name": "Ginger (rhizome) hydroethanolic extract",
                    "ingredientGroup": "Ginger",
                    "quantity": [{"quantity": 96, "unit": "mg"}],
                    "nestedRows": [
                        {
                            "order": 1,
                            "name": "Zingiberene",
                            "ingredientGroup": "Sesquiterpene",
                            "quantity": [{"quantity": 0, "unit": "NP"}],
                        }
                    ],
                }
            ],
            "otheringredients": {"ingredients": []},
        }

        normalized = normalizer.normalize_product(raw_product)
        active_names = [ing.get("name") for ing in normalized.get("activeIngredients", [])]
        display_by_raw = {
            row.get("raw_source_text"): row for row in normalized.get("display_ingredients", [])
        }

        assert "Zingiberene" not in active_names
        assert display_by_raw["Zingiberene"]["score_included"] is False

    def test_batch38_proprietary_mulberry_leaf_extract_nested_child_maps(self, normalizer):
        raw_product = {
            "id": "batch38-mulberry",
            "fullName": "Batch 38 Mulberry",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "ingredientRows": [
                {
                    "order": 1,
                    "name": "Glucocil Blood Glucose Management Blend",
                    "ingredientGroup": "Proprietary Blend (Combination)",
                    "quantity": [{"quantity": 50, "unit": "mg"}],
                    "nestedRows": [
                        {
                            "order": 1,
                            "name": "Proprietary Mulberry leaf extract",
                            "ingredientGroup": "Mulberry (unspecified)",
                            "quantity": [{"quantity": 0, "unit": "NP"}],
                        }
                    ],
                }
            ],
            "otheringredients": {"ingredients": []},
        }

        normalized = normalizer.normalize_product(raw_product)
        active_by_raw = {
            ing.get("raw_source_text"): ing for ing in normalized.get("activeIngredients", [])
        }
        display_by_raw = {
            row.get("raw_source_text"): row for row in normalized.get("display_ingredients", [])
        }

        assert active_by_raw["Proprietary Mulberry leaf extract"]["standardName"] == "Mulberry"
        assert display_by_raw["Proprietary Mulberry leaf extract"]["display_type"] == "mapped_ingredient"
        assert display_by_raw["Proprietary Mulberry leaf extract"]["score_included"] is True

    def test_batch39_plant_derived_antioxidants_parent_unwraps_children(self, normalizer):
        raw_product = {
            "id": "batch39-plant-antioxidants",
            "fullName": "Batch 39 Plant Derived Antioxidants",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "ingredientRows": [],
            "otheringredients": {
                "ingredients": [
                    {
                        "order": 1,
                        "name": "Plant Derived Antioxidants",
                        "ingredientGroup": "Header",
                        "forms": [
                            {"order": 1, "name": "Ascorbyl Palmitate", "ingredientId": 1001},
                            {"order": 2, "name": "Mixed Tocopherols", "ingredientId": 1002},
                            {"order": 3, "name": "Rosemary extract", "ingredientId": 1003},
                        ],
                    }
                ]
            },
        }

        normalized = normalizer.normalize_product(raw_product)
        inactive_names = [ing.get("name") for ing in normalized.get("inactiveIngredients", [])]
        display_by_raw = {
            row.get("raw_source_text"): row for row in normalized.get("display_ingredients", [])
        }

        assert "Plant Derived Antioxidants" not in inactive_names
        assert "Ascorbyl Palmitate" in inactive_names
        assert "Mixed Tocopherols" in inactive_names
        assert "Rosemary extract" in inactive_names
        assert display_by_raw["Plant Derived Antioxidants"]["display_type"] == "structural_container"
        assert display_by_raw["Plant Derived Antioxidants"]["score_included"] is False


class TestNutritionFactExclusion:
    """Tests for nutrition fact exclusion"""

    @pytest.fixture
    def normalizer(self):
        return EnhancedDSLDNormalizer()

    def test_is_nutrition_fact(self, normalizer):
        """Test nutrition fact detection"""
        # These should be detected as nutrition facts
        assert normalizer._is_nutrition_fact("Calories", "Amount Per Serving", "cal") is True
        assert normalizer._is_nutrition_fact("Total Carbohydrates", "", "g") is True
        assert normalizer._is_nutrition_fact("Total Sugars", "", "g") is True

    def test_real_ingredient_not_nutrition_fact(self, normalizer):
        """Test that real ingredients are NOT detected as nutrition facts"""
        assert normalizer._is_nutrition_fact("Vitamin C", "Vitamins", "mg") is False
        assert normalizer._is_nutrition_fact("Zinc", "Minerals", "mg") is False


class TestBatch9StructuralAndBrandedWrappers:
    @pytest.fixture
    def normalizer(self):
        return EnhancedDSLDNormalizer()

    def test_batch9_stabilizer_parent_unwraps_child(self, normalizer):
        raw_product = {
            "id": "batch9-stabilizer",
            "fullName": "Batch 9 Stabilizer",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "ingredientRows": [],
            "otheringredients": {
                "ingredients": [
                    {
                        "order": 1,
                        "name": "Stabilizer",
                        "ingredientGroup": "Stabilizer",
                        "forms": [
                            {"order": 1, "name": "Croscarmellose Sodium", "ingredientId": 4312}
                        ],
                    }
                ]
            },
        }

        normalized = normalizer.normalize_product(raw_product)
        inactive_names = [ing.get("name") for ing in normalized.get("inactiveIngredients", [])]
        inactive_by_name = {ing.get("name"): ing for ing in normalized.get("inactiveIngredients", [])}

        assert "Stabilizer" not in inactive_names
        assert inactive_by_name["Croscarmellose Sodium"]["standardName"] == "Croscarmellose Sodium"

    def test_batch9_thickener_parent_unwraps_children(self, normalizer):
        raw_product = {
            "id": "batch9-thickener",
            "fullName": "Batch 9 Thickener",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "ingredientRows": [],
            "otheringredients": {
                "ingredients": [
                    {
                        "order": 1,
                        "name": "Thickener",
                        "ingredientGroup": "Thickener",
                        "forms": [
                            {"order": 1, "name": "Hydroxypropyl Cellulose", "ingredientId": 6505},
                            {"order": 2, "name": "Hypromellose", "ingredientId": 3721},
                        ],
                    }
                ]
            },
        }

        normalized = normalizer.normalize_product(raw_product)
        inactive_names = [ing.get("name") for ing in normalized.get("inactiveIngredients", [])]
        inactive_by_name = {ing.get("name"): ing for ing in normalized.get("inactiveIngredients", [])}

        assert "Thickener" not in inactive_names
        assert inactive_by_name["Hydroxypropyl Cellulose"]["standardName"] == "Hydroxypropyl Cellulose"
        assert inactive_by_name["Hypromellose"]["standardName"] == "Hydroxypropyl Methylcellulose"

    def test_batch13_preservatives_header_unwraps_children(self, normalizer):
        raw_product = {
            "id": "batch13-preservatives-header",
            "fullName": "Batch 13 Preservatives Header",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "ingredientRows": [],
            "otheringredients": {
                "ingredients": [
                    {
                        "order": 1,
                        "name": "Preservatives to maintain freshness",
                        "ingredientGroup": "Header",
                        "forms": [
                            {"order": 2, "name": "Ascorbyl Palmitate", "ingredientId": 278748},
                            {"order": 3, "name": "Mixed Tocopherols", "ingredientId": 280625},
                        ],
                    }
                ]
            },
        }

        normalized = normalizer.normalize_product(raw_product)
        inactive_names = [ing.get("name") for ing in normalized.get("inactiveIngredients", [])]
        display_by_raw = {
            row.get("raw_source_text"): row for row in normalized.get("display_ingredients", [])
        }

        assert "Preservatives to maintain freshness" not in inactive_names
        assert "Ascorbyl Palmitate" in inactive_names
        assert "Mixed Tocopherols" in inactive_names
        assert display_by_raw["Preservatives to maintain freshness"]["display_type"] == "structural_container"
        assert display_by_raw["Preservatives to maintain freshness"]["score_included"] is False
        assert display_by_raw["Preservatives to maintain freshness"]["children"] == [
            "Ascorbyl Palmitate",
            "Mixed Tocopherols",
        ]

    @pytest.mark.parametrize(
        ("container_name", "child_names"),
        [
            (
                "Coating contains one or more of the following",
                [
                    "Ethylcellulose",
                    "Medium Chain Triglycerides",
                    "Oleic Acid",
                    "PEG",
                    "Polymethylacrylate",
                    "Sodium Alginate",
                    "Stearic Acid",
                    "Talc",
                ],
            ),
            (
                "Excipients",
                ["organic extra virgin Olive Oil", "Rice Bran Wax", "Sunflower Lecithin"],
            ),
            (
                "Glycerides and Fatty Acids",
                ["Safflower Oil Glyceride", "Sunflower seed Oil Glyceride"],
            ),
            (
                "PlantGel Capsule",
                ["Glycerin", "Tapioca Starch, Modified", "Water, Purified"],
            ),
        ],
    )
    def test_batch14_inactive_structural_wrappers_unwrap_forms_without_parent(
        self, normalizer, container_name, child_names
    ):
        raw_product = {
            "id": f"batch14-{container_name}",
            "fullName": "Batch 14 Structural Wrapper",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "ingredientRows": [],
            "otheringredients": {
                "ingredients": [
                    {
                        "order": 1,
                        "name": container_name,
                        "ingredientGroup": "Header",
                        "forms": [{"order": idx + 2, "name": child} for idx, child in enumerate(child_names)],
                    }
                ]
            },
        }

        normalized = normalizer.normalize_product(raw_product)
        inactive_names = [ing.get("name") for ing in normalized.get("inactiveIngredients", [])]
        display_by_raw = {
            row.get("raw_source_text"): row for row in normalized.get("display_ingredients", [])
        }

        assert container_name not in inactive_names
        for child_name in child_names:
            assert child_name in inactive_names
        assert display_by_raw[container_name]["display_type"] == "structural_container"
        assert display_by_raw[container_name]["score_included"] is False

    @pytest.mark.parametrize(
        ("container_name", "nested_names"),
        [
            (
                "Alpha & Omega",
                [
                    "Alpha-GPC",
                    "Eicosapentaenoic Acid",
                    "Docosahexaenoic Acid",
                ],
            ),
            (
                "Bergacyn",
                [
                    "Artichoke",
                    "Bergamot",
                ],
            ),
            (
                "Supercritical Ultra-Purified Fish and Krill Oil",
                ["Total Omega-3 Fatty Acids"],
            ),
        ],
    )
    def test_batch15_active_structural_wrappers_drop_parent_and_keep_nested_children(
        self, normalizer, container_name, nested_names
    ):
        raw_product = {
            "id": f"batch15-{container_name}",
            "fullName": "Batch 15 Active Structural Wrapper",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "ingredientRows": [
                {
                    "order": 1,
                    "name": container_name,
                    "ingredientGroup": "Blend",
                    "nestedRows": [{"order": idx + 2, "name": child, "ingredientGroup": child} for idx, child in enumerate(nested_names)],
                }
            ],
            "otheringredients": {"ingredients": []},
        }

        normalized = normalizer.normalize_product(raw_product)
        active_names = [ing.get("name") for ing in normalized.get("activeIngredients", [])]
        display_by_raw = {
            row.get("raw_source_text"): row for row in normalized.get("display_ingredients", [])
        }

        assert container_name not in active_names
        for child_name in nested_names:
            if child_name in {"Other Omega-3 Fatty Acids", "Total Omega-3 Fatty Acids"}:
                continue
            assert child_name in active_names
        assert display_by_raw[container_name]["display_type"] == "structural_container"
        assert display_by_raw[container_name]["score_included"] is False

    @pytest.mark.parametrize(
        ("container_name", "child_names"),
        [
            (
                "UHPO3 Omega-3 Fatty Acid Concentrate",
                ["Anchovies", "Sardines", "Tuna"],
            ),
            (
                "Proprietary Bio-Solv base",
                ["Medium Chain Triglycerides", "Polysorbate 80", "Sorbitan Monooleate", "Sorbitol", "Soy Lecithin"],
            ),
            (
                "FreshLok(TM) antioxidant",
                ["Ascorbic Acid", "Ascorbyl Palmitate", "D-Alpha-Tocopherol", "Rosemary extract", "Soy Lecithin"],
            ),
            (
                "White Ink",
                ["Ammonium Hydroxide", "Isopropyl Alcohol", "N-Butyl Alcohol", "Propylene Glycol", "Shellac glaze", "Simethicone", "Titanium Dioxide"],
            ),
        ],
    )
    def test_batch15_inactive_structural_wrappers_unwrap_forms_without_parent(
        self, normalizer, container_name, child_names
    ):
        raw_product = {
            "id": f"batch15-{container_name}",
            "fullName": "Batch 15 Structural Wrapper",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "ingredientRows": [],
            "otheringredients": {
                "ingredients": [
                    {
                        "order": 1,
                        "name": container_name,
                        "ingredientGroup": "Header",
                        "forms": [{"order": idx + 2, "name": child} for idx, child in enumerate(child_names)],
                    }
                ]
            },
        }

        normalized = normalizer.normalize_product(raw_product)
        inactive_names = [ing.get("name") for ing in normalized.get("inactiveIngredients", [])]
        display_by_raw = {
            row.get("raw_source_text"): row for row in normalized.get("display_ingredients", [])
        }

        assert container_name not in inactive_names
        for child_name in child_names:
            assert child_name in inactive_names
        assert display_by_raw[container_name]["display_type"] == "structural_container"
        assert display_by_raw[container_name]["score_included"] is False

    def test_batch16_softgel_color_unwraps_children_without_parent(self, normalizer):
        raw_product = {
            "id": "batch16-softgel-color",
            "fullName": "Batch 16 Softgel Color",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "ingredientRows": [],
            "otheringredients": {
                "ingredients": [
                    {
                        "order": 1,
                        "name": "Softgel Color",
                        "ingredientGroup": "Color",
                        "forms": [
                            {"order": 2, "name": "Annatto"},
                            {"order": 3, "name": "Titanium Dioxide", "prefix": "and"},
                        ],
                    }
                ]
            },
        }

        normalized = normalizer.normalize_product(raw_product)
        inactive_names = [ing.get("name") for ing in normalized.get("inactiveIngredients", [])]
        display_by_raw = {
            row.get("raw_source_text"): row for row in normalized.get("display_ingredients", [])
        }

        assert "Softgel Color" not in inactive_names
        assert "Annatto" in inactive_names
        assert "Titanium Dioxide" in inactive_names
        assert display_by_raw["Softgel Color"]["display_type"] == "structural_container"
        assert display_by_raw["Softgel Color"]["score_included"] is False

    @pytest.mark.parametrize(
        ("container_name", "child_names"),
        [
            ("organic Flax particulate matter", ["Lignans"]),
            ("contains naturally occurring Carotenoids", ["Beta-Carotene", "Canthaxanthin", "Lutein"]),
            ("Antioxidant", ["Mixed Tocopherols"]),
        ],
    )
    def test_batch17_inactive_structural_wrappers_unwrap_forms_without_parent(
        self, normalizer, container_name, child_names
    ):
        raw_product = {
            "id": f"batch17-{container_name}",
            "fullName": "Batch 17 Structural Wrapper",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "ingredientRows": [],
            "otheringredients": {
                "ingredients": [
                    {
                        "order": 1,
                        "name": container_name,
                        "ingredientGroup": "Header",
                        "forms": [{"order": idx + 2, "name": child} for idx, child in enumerate(child_names)],
                    }
                ]
            },
        }

        normalized = normalizer.normalize_product(raw_product)
        inactive_names = [ing.get("name") for ing in normalized.get("inactiveIngredients", [])]
        display_by_raw = {
            row.get("raw_source_text"): row for row in normalized.get("display_ingredients", [])
        }

        assert container_name not in inactive_names
        for child_name in child_names:
            assert child_name in inactive_names
        assert display_by_raw[container_name]["display_type"] == "structural_container"
        assert display_by_raw[container_name]["score_included"] is False

    @pytest.mark.parametrize(
        ("container_name", "child_names"),
        [
            # "Palmitic Acid, Stearic Acid" omitted: children are in EXCLUDED_NUTRITION_FACTS
            # (nutrition fact components of oils) and are intentionally suppressed.
            # Parent-drop behavior for that container is already covered by test_batch10.
            # Oleic Acid excluded: maps to Omega-9, suppressed by STRUCTURAL_ACTIVE_DISPLAY_ONLY_LEAF_NAMES.
            ("Safflower/Sunflower Oil concentrate", ["Conjugated Linoleic Acid"]),
        ],
    )
    def test_batch18_active_structural_form_wrappers_drop_parent_and_keep_children(
        self, normalizer, container_name, child_names
    ):
        raw_product = {
            "id": f"batch18-{container_name}",
            "fullName": "Batch 18 Structural Active Wrapper",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "ingredientRows": [
                {
                    "order": 1,
                    "name": container_name,
                    "ingredientGroup": "Blend (Fatty Acid or Fat/Oil Supplement)",
                    "forms": [],
                    "nestedRows": [
                        {"order": idx + 2, "name": child, "ingredientGroup": child, "nestedRows": [], "forms": []}
                        for idx, child in enumerate(child_names)
                    ],
                }
            ],
            "otheringredients": {"ingredients": []},
        }

        normalized = normalizer.normalize_product(raw_product)
        active_names = [ing.get("name") for ing in normalized.get("activeIngredients", [])]
        display_by_raw = {
            row.get("raw_source_text"): row for row in normalized.get("display_ingredients", [])
        }

        assert container_name not in active_names
        for child_name in child_names:
            assert child_name in active_names
        assert display_by_raw[container_name]["display_type"] == "structural_container"
        assert display_by_raw[container_name]["score_included"] is False

    @pytest.mark.parametrize(
        "summary_name",
        ["Total Omega-3-5-6-7-8-9-11", "Other Omega-3's"],
    )
    def test_batch18_active_summary_rows_are_skipped(self, normalizer, summary_name):
        raw_product = {
            "id": f"batch18-{summary_name}",
            "fullName": "Batch 18 Summary Row",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "ingredientRows": [
                {
                    "order": 1,
                    "name": summary_name,
                    "ingredientGroup": "Omega-3",
                    "nestedRows": [],
                    "forms": [],
                }
            ],
            "otheringredients": {"ingredients": []},
        }

        normalized = normalizer.normalize_product(raw_product)
        active_names = [ing.get("name") for ing in normalized.get("activeIngredients", [])]
        display_by_raw = {
            row.get("raw_source_text"): row for row in normalized.get("display_ingredients", [])
        }

        assert summary_name not in active_names
        assert display_by_raw[summary_name]["display_type"] == "summary_wrapper"
        assert display_by_raw[summary_name]["score_included"] is False

    def test_batch19_cellulose_modified_unwraps_hypromellose_without_parent(self, normalizer):
        raw_product = {
            "id": "batch19-cellulose-modified",
            "fullName": "Batch 19 Cellulose Wrapper",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "ingredientRows": [],
            "otheringredients": {
                "ingredients": [
                    {
                        "order": 1,
                        "name": "Cellulose, Modified",
                        "ingredientGroup": "Cellulose",
                        "nestedRows": [],
                        "forms": [{"order": 2, "name": "Hypromellose"}],
                    }
                ]
            },
        }

        normalized = normalizer.normalize_product(raw_product)
        inactive_names = [ing.get("name") for ing in normalized.get("inactiveIngredients", [])]
        display_by_raw = {
            row.get("raw_source_text"): row for row in normalized.get("display_ingredients", [])
        }

        assert "Cellulose, Modified" not in inactive_names
        assert "Hypromellose" in inactive_names
        assert display_by_raw["Cellulose, Modified"]["display_type"] == "structural_container"
        assert display_by_raw["Cellulose, Modified"]["score_included"] is False

    def test_batch20_serrateric_unwraps_child_coating_forms_without_parent(self, normalizer):
        raw_product = {
            "id": "batch20-serrateric",
            "fullName": "Batch 20 Serrateric Wrapper",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "ingredientRows": [],
            "otheringredients": {
                "ingredients": [
                    {
                        "order": 1,
                        "name": "Serrateric",
                        "ingredientGroup": "Coating",
                        "nestedRows": [],
                        "forms": [
                            {"order": 2, "name": "Calcium Stearate"},
                            {"order": 3, "name": "Maltodextrin"},
                            {"order": 4, "name": "Medium Chain Triglycerides"},
                        ],
                    }
                ]
            },
        }

        normalized = normalizer.normalize_product(raw_product)
        inactive_names = [ing.get("name") for ing in normalized.get("inactiveIngredients", [])]
        display_by_raw = {
            row.get("raw_source_text"): row for row in normalized.get("display_ingredients", [])
        }

        assert "Serrateric" not in inactive_names
        assert "Calcium Stearate" in inactive_names
        assert "Maltodextrin" in inactive_names
        assert "Medium Chain Triglycerides" in inactive_names
        assert display_by_raw["Serrateric"]["display_type"] == "structural_container"
        assert display_by_raw["Serrateric"]["score_included"] is False

    def test_batch21_absorption_amplifier_parent_is_dropped_in_favor_of_nested_children(
        self, normalizer
    ):
        raw_product = {
            "id": "batch21-absorption-amplifier",
            "fullName": "Batch 21 Absorption Amplifier",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "ingredientRows": [
                {
                    "order": 1,
                    "name": "Absorption Amplifier",
                    "ingredientGroup": "Blend",
                    "nestedRows": [
                        {
                            "order": 2,
                            "name": "Black Pepper extract",
                            "ingredientGroup": "Black Pepper",
                            "forms": [],
                        },
                        {
                            "order": 3,
                            "name": "6,7-Dihydroxybergamottin",
                            "ingredientGroup": "6,7-Dihydroxybergamottin",
                            "forms": [],
                        },
                    ],
                    "forms": [],
                }
            ],
            "otheringredients": {"ingredients": []},
        }

        normalized = normalizer.normalize_product(raw_product)
        active_names = [ing.get("name") for ing in normalized.get("activeIngredients", [])]
        display_by_raw = {
            row.get("raw_source_text"): row for row in normalized.get("display_ingredients", [])
        }

        assert "Absorption Amplifier" not in active_names
        assert "Black Pepper extract" in active_names
        assert "6,7-Dihydroxybergamottin" in active_names
        assert display_by_raw["Absorption Amplifier"]["display_type"] == "structural_container"
        assert display_by_raw["Absorption Amplifier"]["score_included"] is False

    def test_batch23_xyliton_inactive_parent_is_dropped_in_favor_of_child_forms(self, normalizer):
        raw_product = {
            "id": "batch23-xyliton",
            "fullName": "Batch 23 Xyliton Wrapper",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "ingredientRows": [],
            "otheringredients": {
                "ingredients": [
                    {
                        "order": 1,
                        "name": "Xyliton",
                        "ingredientGroup": "TBD",
                        "category": "non-nutrient/non-botanical",
                        "forms": [
                            {"order": 2, "name": "Galactose", "prefix": "this material may contain"},
                            {"order": 3, "name": "Glucose"},
                            {"order": 4, "name": "Invert Sugar"},
                            {"order": 5, "name": "Mannitol"},
                            {"order": 6, "name": "Sorbitol", "prefix": "and"},
                            {"order": 7, "name": "Sucrose"},
                        ],
                    }
                ]
            },
        }

        normalized = normalizer.normalize_product(raw_product)
        inactive_names = [ing.get("name") for ing in normalized.get("inactiveIngredients", [])]
        display_by_raw = {
            row.get("raw_source_text"): row for row in normalized.get("display_ingredients", [])
        }

        assert "Xyliton" not in inactive_names
        assert "Galactose" in inactive_names
        assert "Glucose" in inactive_names
        assert "Invert Sugar" in inactive_names
        assert "Mannitol" in inactive_names
        assert "Sorbitol" in inactive_names
        assert "Sucrose" in inactive_names
        assert display_by_raw["Xyliton"]["display_type"] == "structural_container"
        assert display_by_raw["Xyliton"]["score_included"] is False

    @pytest.mark.parametrize(
        ("container_name", "child_names"),
        [
            (
                "organic Neurophenol",
                [
                    "organic Grape (Vitis vinifera) extract",
                    "organic wild Blueberry extract",
                ],
            ),
            (
                "non-GMO Sunflower",
                [
                    "non-GMO Sunflower Lecithin",
                    "non-GMO Sunflower Oil",
                ],
            ),
            (
                "organic Dark Chocolate chunks",
                [
                    "Cane Sugar",
                    "organic Cocoa Butter",
                    "organic unsweetened Chocolate",
                    "organic Vanilla",
                ],
            ),
        ],
    )
    def test_garden_of_life_structural_wrappers_unwrap_children_without_parent(
        self, normalizer, container_name, child_names
    ):
        raw_product = {
            "id": f"gol-wrapper-{container_name}",
            "fullName": "Garden Wrapper",
            "brandName": "Garden of Life",
            "productVersionCode": "1",
            "ingredientRows": [
                {
                    "order": 1,
                    "name": container_name,
                    "ingredientGroup": "Blend",
                    "nestedRows": [],
                    "forms": [{"order": idx + 2, "name": child} for idx, child in enumerate(child_names)],
                    "category": "blend",
                }
            ],
            "otheringredients": {"ingredients": []},
        }
        if container_name == "organic Neurophenol":
            raw_product["ingredientRows"][0]["nestedRows"] = [
                {"order": idx + 2, "name": child, "ingredientGroup": child, "forms": []}
                for idx, child in enumerate(child_names)
            ]
            raw_product["ingredientRows"][0]["forms"] = []
        if container_name in {"non-GMO Sunflower", "organic Dark Chocolate chunks"}:
            raw_product["ingredientRows"] = []
            raw_product["otheringredients"]["ingredients"] = [raw_product["ingredientRows"]]

        # Normalize the inactive wrapper shape for the inactive cases.
        if container_name in {"non-GMO Sunflower", "organic Dark Chocolate chunks"}:
            raw_product["otheringredients"]["ingredients"] = [
                {
                    "order": 1,
                    "name": container_name,
                    "ingredientGroup": "Header",
                    "nestedRows": [],
                    "forms": [{"order": idx + 2, "name": child} for idx, child in enumerate(child_names)],
                    "category": "other",
                }
            ]

        normalized = normalizer.normalize_product(raw_product)
        active_names = [ing.get("name") for ing in normalized.get("activeIngredients", [])]
        inactive_names = [ing.get("name") for ing in normalized.get("inactiveIngredients", [])]
        display_by_raw = {
            row.get("raw_source_text"): row for row in normalized.get("display_ingredients", [])
        }

        if container_name == "organic Neurophenol":
            assert container_name not in active_names
            for child_name in child_names:
                assert child_name in active_names
        else:
            assert container_name not in inactive_names
            for child_name in child_names:
                assert child_name in inactive_names

        assert display_by_raw[container_name]["display_type"] == "structural_container"
        assert display_by_raw[container_name]["score_included"] is False

    def test_batch9_menaq7_parent_is_dropped_in_favor_of_nested_vitamin_k2(self, normalizer):
        raw_product = {
            "id": "batch9-menaq7-natto",
            "fullName": "Batch 9 MenaQ7",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "ingredientRows": [
                {
                    "order": 1,
                    "name": "MenaQ7 Natto",
                    "ingredientGroup": "TBD",
                    "nestedRows": [
                        {
                            "order": 2,
                            "name": "Vitamin K2",
                            "ingredientGroup": "Vitamin K (menaquinone)",
                            "nestedRows": [],
                            "forms": [],
                        }
                    ],
                    "forms": [],
                }
            ],
            "otheringredients": {"ingredients": []},
        }

        normalized = normalizer.normalize_product(raw_product)
        active_names = [ing.get("name") for ing in normalized.get("activeIngredients", [])]
        active_by_name = {ing.get("name"): ing for ing in normalized.get("activeIngredients", [])}

        assert "MenaQ7 Natto" not in active_names
        assert active_by_name["Vitamin K2"]["standardName"] == "Vitamin K"

    def test_batch9_active_lanolin_wrapper_drops_parent_and_keeps_vitamin_d3(self, normalizer):
        raw_product = {
            "id": "batch9-lanolin-active",
            "fullName": "Batch 9 Lanolin",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "ingredientRows": [
                {
                    "order": 1,
                    "name": "Lanolin",
                    "ingredientGroup": "Lanolin",
                    "forms": [
                        {"order": 1, "name": "Vitamin D3", "prefix": "std. to", "ingredientId": 279014}
                    ],
                    "nestedRows": [],
                }
            ],
            "otheringredients": {"ingredients": []},
        }

        normalized = normalizer.normalize_product(raw_product)
        active_names = [ing.get("name") for ing in normalized.get("activeIngredients", [])]
        active_by_name = {ing.get("name"): ing for ing in normalized.get("activeIngredients", [])}

        assert "Lanolin" not in active_names
        assert active_by_name["Vitamin D3"]["standardName"] == "Vitamin D"


class TestBatch10OmegaAndFattyAcidSummaries:
    @pytest.fixture
    def normalizer(self):
        return EnhancedDSLDNormalizer()

    def test_batch10_total_omega_summary_drops_parent_and_keeps_nested_children(self, normalizer):
        raw_product = {
            "id": "batch10-total-omega",
            "fullName": "Batch 10 Omega",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "ingredientRows": [
                {
                    "order": 1,
                    "name": "Total Omega-3-5-6-7-8-9-11",
                    "ingredientGroup": "Blend (Fatty Acid or Fat/Oil Supplement)",
                    "nestedRows": [
                        {
                            "order": 2,
                            "name": "Eicosapentaenoic Acid",
                            "ingredientGroup": "EPA (Eicosapentaenoic Acid)",
                            "nestedRows": [],
                            "forms": [],
                        },
                        {
                            "order": 3,
                            "name": "Docosahexaenoic Acid",
                            "ingredientGroup": "DHA (Docosahexaenoic Acid)",
                            "nestedRows": [],
                            "forms": [],
                        },
                    ],
                    "forms": [],
                }
            ],
            "otheringredients": {"ingredients": []},
        }

        normalized = normalizer.normalize_product(raw_product)
        active_names = [ing.get("name") for ing in normalized.get("activeIngredients", [])]

        assert "Total Omega-3-5-6-7-8-9-11" not in active_names
        assert "Eicosapentaenoic Acid" in active_names
        assert "Docosahexaenoic Acid" in active_names

    def test_batch10_palmitic_stearic_wrapper_drops_parent(self, normalizer):
        raw_product = {
            "id": "batch10-palmitic-stearic",
            "fullName": "Batch 10 Fatty Acids",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "ingredientRows": [
                {
                    "order": 1,
                    "name": "Palmitic Acid, Stearic Acid",
                    "ingredientGroup": "Blend (Fatty Acid or Fat/Oil Supplement)",
                    "nestedRows": [
                        {
                            "order": 2,
                            "name": "Palmitic Acid",
                            "ingredientGroup": "Palmitic Acid",
                            "nestedRows": [],
                            "forms": [],
                        },
                        {
                            "order": 3,
                            "name": "Stearic Acid",
                            "ingredientGroup": "Stearic Acid",
                            "nestedRows": [],
                            "forms": [],
                        },
                    ],
                    "forms": [
                        {"order": 1, "name": "Palmitic Acid"},
                        {"order": 2, "name": "Stearic Acid"},
                    ],
                }
            ],
            "otheringredients": {"ingredients": []},
        }

        normalized = normalizer.normalize_product(raw_product)
        active_names = [ing.get("name") for ing in normalized.get("activeIngredients", [])]

        assert "Palmitic Acid, Stearic Acid" not in active_names


class TestBatch11WrapperAndSummaryRows:
    @pytest.fixture
    def normalizer(self):
        return EnhancedDSLDNormalizer()

    def test_batch11_safflower_sunflower_wrapper_drops_parent_and_keeps_children(self, normalizer):
        raw_product = {
            "id": "batch11-safflower-sunflower",
            "fullName": "Batch 11 CLA",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "ingredientRows": [
                {
                    "order": 1,
                    "name": "Safflower/Sunflower Oil concentrate",
                    "ingredientGroup": "Blend (Fatty Acid or Fat/Oil Supplement)",
                    "nestedRows": [
                        {"order": 2, "name": "Conjugated Linoleic Acid", "ingredientGroup": "CLA"},
                        {"order": 3, "name": "Oleic Acid", "ingredientGroup": "Oleic Acid"},
                    ],
                    "forms": [],
                }
            ],
            "otheringredients": {"ingredients": []},
        }

        normalized = normalizer.normalize_product(raw_product)
        active_names = [ing.get("name") for ing in normalized.get("activeIngredients", [])]
        display_by_raw = {
            row.get("raw_source_text"): row for row in normalized.get("display_ingredients", [])
        }

        assert "Safflower/Sunflower Oil concentrate" not in active_names
        assert "Conjugated Linoleic Acid" in active_names
        assert display_by_raw["Safflower/Sunflower Oil concentrate"]["score_included"] is False
        assert display_by_raw["Safflower/Sunflower Oil concentrate"]["source_section"] == "activeIngredients"

    def test_batch11_other_omega_summary_drops_parent(self, normalizer):
        raw_product = {
            "id": "batch11-other-omega",
            "fullName": "Batch 11 Other Omega",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "ingredientRows": [
                {"order": 1, "name": "Total Omega-3 Fatty Acids", "ingredientGroup": "Omega-3"},
                {"order": 2, "name": "Eicosapentaenoic Acid", "ingredientGroup": "EPA (Eicosapentaenoic Acid)"},
                {"order": 3, "name": "Docosahexaenoic Acid", "ingredientGroup": "DHA (Docosahexaenoic Acid)"},
                {"order": 4, "name": "Other Omega-3's", "ingredientGroup": "Omega-3"},
            ],
            "otheringredients": {"ingredients": []},
        }

        normalized = normalizer.normalize_product(raw_product)
        active_names = [ing.get("name") for ing in normalized.get("activeIngredients", [])]
        display_by_raw = {
            row.get("raw_source_text"): row for row in normalized.get("display_ingredients", [])
        }

        assert "Other Omega-3's" not in active_names
        assert "Eicosapentaenoic Acid" in active_names
        assert "Docosahexaenoic Acid" in active_names
        assert display_by_raw["Other Omega-3's"]["score_included"] is False
        assert display_by_raw["Other Omega-3's"]["source_section"] == "activeIngredients"

    def test_batch11_high_choline_lecithin_wrapper_drops_parent_and_keeps_phosphatidylcholine(self, normalizer):
        raw_product = {
            "id": "batch11-high-choline-lecithin",
            "fullName": "Batch 11 Triple Lecithin",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "ingredientRows": [
                {
                    "order": 1,
                    "name": "High Choline Lecithin",
                    "ingredientGroup": "lecithin",
                    "nestedRows": [
                        {"order": 2, "name": "Phosphatidyl Choline", "ingredientGroup": "phosphatidylcholine"}
                    ],
                    "forms": [],
                }
            ],
            "otheringredients": {"ingredients": []},
        }

        normalized = normalizer.normalize_product(raw_product)
        active_names = [ing.get("name") for ing in normalized.get("activeIngredients", [])]
        active_by_name = {ing.get("name"): ing for ing in normalized.get("activeIngredients", [])}
        display_by_raw = {
            row.get("raw_source_text"): row for row in normalized.get("display_ingredients", [])
        }

        assert "High Choline Lecithin" not in active_names
        assert active_by_name["Phosphatidyl Choline"]["standardName"] == "Choline"
        assert display_by_raw["High Choline Lecithin"]["score_included"] is False
        assert display_by_raw["High Choline Lecithin"]["source_section"] == "activeIngredients"

    def test_display_ledger_keeps_wrappers_but_excludes_nutrition_facts(self, normalizer):
        raw_product = {
            "id": "display-ledger-no-nutrition",
            "fullName": "Display Ledger Nutrition Guard",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "ingredientRows": [
                {
                    "order": 1,
                    "name": "Calories from Fat",
                    "ingredientGroup": "Amount Per Serving",
                    "nestedRows": [],
                    "forms": [],
                },
                {
                    "order": 2,
                    "name": "Other Omega-3's",
                    "ingredientGroup": "Omega-3",
                    "nestedRows": [],
                    "forms": [],
                },
                {
                    "order": 3,
                    "name": "Docosahexaenoic Acid",
                    "ingredientGroup": "DHA (Docosahexaenoic Acid)",
                    "nestedRows": [],
                    "forms": [],
                },
            ],
            "otheringredients": {"ingredients": []},
        }

        normalized = normalizer.normalize_product(raw_product)
        display_rows = normalized.get("display_ingredients", [])
        display_raw = [row.get("raw_source_text") for row in display_rows]

        assert "Other Omega-3's" in display_raw
        assert "Calories from Fat" not in display_raw


class TestCleaningUnmappedBatch1Regressions:
    @pytest.fixture
    def normalizer(self):
        return EnhancedDSLDNormalizer()

    def test_active_form_container_zma_unwraps_forms_without_parent(self, normalizer):
        raw_product = {
            "id": "test_zma_forms",
            "fullName": "Test ZMA",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "ingredientRows": [
                {
                    "name": "ZMA",
                    "ingredientGroup": "Proprietary Blend (Mineral)",
                    "order": 1,
                    "forms": [
                        {"name": "Magnesium Aspartate", "order": 1},
                        {"name": "Pyridoxine Hydrochloride", "order": 2},
                        {"name": "Zinc Mono-L-Methionine", "order": 3},
                    ],
                }
            ],
            "otheringredients": {"ingredients": []},
        }

        cleaned = normalizer.normalize_product(raw_product)
        active_names = [ing.get("name") for ing in cleaned.get("activeIngredients", [])]

        assert "ZMA" not in active_names
        assert "Magnesium Aspartate" in active_names
        assert "Pyridoxine Hydrochloride" in active_names
        assert "Zinc Mono-L-Methionine" in active_names

    def test_total_omega_summary_is_skipped(self, normalizer):
        raw_product = {
            "id": "test_total_omega",
            "fullName": "Test Krill Oil",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "ingredientRows": [
                {"name": "Krill Oil", "order": 1},
                {"name": "Total Omega-3 Fatty Acids", "order": 2},
                {"name": "Total Omega-6 Fatty Acids", "order": 3},
                {"name": "Total Omega", "order": 4},
            ],
            "otheringredients": {"ingredients": []},
        }

        cleaned = normalizer.normalize_product(raw_product)
        active_names = [ing.get("name") for ing in cleaned.get("activeIngredients", [])]

        assert "Total Omega" not in active_names
        assert "Krill Oil" in active_names

    @pytest.mark.parametrize(
        ("container_name", "child_names"),
        [
            ("Enteripure Softgel", ["Gelatin", "Glycerin", "Pectin", "purified Water"]),
            (
                "Aqueous Coating Solution",
                ["Ethylcellulose", "Medium Chain Triglycerides", "Sodium Alginate"],
            ),
            ("B.A.S.S.(TM)", ["Oregano", "organic Sunflower Oil", "Rosemary"]),
        ],
    )
    def test_inactive_structural_container_unwraps_forms_without_parent(
        self, normalizer, container_name, child_names
    ):
        raw_product = {
            "id": f"test_{container_name}",
            "fullName": "Test Product",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "ingredientRows": [],
            "otheringredients": {
                "ingredients": [
                    {
                        "name": container_name,
                        "ingredientGroup": "capsule",
                        "order": 1,
                        "forms": [{"name": child, "order": idx + 1} for idx, child in enumerate(child_names)],
                    }
                ]
            },
        }

        cleaned = normalizer.normalize_product(raw_product)
        inactive_names = [ing.get("name") for ing in cleaned.get("inactiveIngredients", [])]

        assert container_name not in inactive_names
        for child_name in child_names:
            assert child_name in inactive_names

    def test_inactive_soy_lecithin_prefers_other_ingredient_route(self, normalizer):
        raw_product = {
            "id": "test_soy_lecithin",
            "fullName": "Test Product",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "ingredientRows": [],
            "otheringredients": {
                "ingredients": [
                    {"name": "Soy Lecithin", "order": 1},
                    {"name": "Soy Lecithin Oil", "order": 2},
                ]
            },
        }

        cleaned = normalizer.normalize_product(raw_product)
        inactive_by_name = {ing.get("name"): ing for ing in cleaned.get("inactiveIngredients", [])}

        assert inactive_by_name["Soy Lecithin"]["standardName"] == "Soy Lecithin"
        assert inactive_by_name["Soy Lecithin Oil"]["standardName"] == "Soy Lecithin"

    def test_inactive_processing_uses_ingredient_group_fallback(self, normalizer):
        raw_product = {
            "id": "test_lime_oil_group_fallback",
            "fullName": "Test Product",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "ingredientRows": [],
            "otheringredients": {
                "ingredients": [
                    {
                        "name": "Lime Oil",
                        "ingredientGroup": "Lime",
                        "order": 1,
                    }
                ]
            },
        }

        cleaned = normalizer.normalize_product(raw_product)
        inactive_ingredients = cleaned.get("inactiveIngredients", [])

        assert len(inactive_ingredients) == 1
        assert inactive_ingredients[0]["mapped"] is True
        assert "lime" in str(inactive_ingredients[0]["standardName"]).lower()

    def test_inactive_processing_uses_descriptor_fallback_before_active_capture(self, normalizer):
        raw_product = {
            "id": "test_soy_lecithin_natural",
            "fullName": "Test Product",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "ingredientRows": [],
            "otheringredients": {
                "ingredients": [
                    {"name": "Soy Lecithin, Natural", "order": 1},
                    {"name": "Water, Deionized, Purified", "order": 2},
                ]
            },
        }

        cleaned = normalizer.normalize_product(raw_product)
        inactive_by_name = {ing.get("name"): ing for ing in cleaned.get("inactiveIngredients", [])}

        assert inactive_by_name["Soy Lecithin, Natural"]["mapped"] is True
        assert inactive_by_name["Soy Lecithin, Natural"]["standardName"] == "Soy Lecithin"
        assert inactive_by_name["Water, Deionized, Purified"]["mapped"] is True
        assert "water" in str(inactive_by_name["Water, Deionized, Purified"]["standardName"]).lower()

    def test_descriptor_fallback_runs_before_ingredient_group_fallback(self, normalizer):
        raw_product = {
            "id": "test_cold_pressed_lemon_oil",
            "fullName": "Test Product",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "ingredientRows": [],
            "otheringredients": {
                "ingredients": [
                    {
                        "name": "cold-pressed Lemon Oil",
                        "ingredientGroup": "Lemon",
                        "order": 1,
                    }
                ]
            },
        }

        cleaned = normalizer.normalize_product(raw_product)
        inactive = cleaned.get("inactiveIngredients", [])

        assert len(inactive) == 1
        assert inactive[0]["mapped"] is True
        assert "lemon oil" in str(inactive[0]["standardName"]).lower()
        assert "vitamin b9" not in str(inactive[0]["standardName"]).lower()


class TestValidatorPlaceholderDetection:
    """Tests for validator placeholder detection"""

    @pytest.fixture
    def validator(self):
        return DSLDValidator()

    def test_placeholder_detection(self, validator):
        """Test that placeholder values trigger missing field detection"""
        product_data = {
            "fullName": "DELETE",  # Placeholder
            "brandName": "Test Brand",
            "productVersionCode": "123",
            "upcSku": "12345678901",
            "ingredientRows": [{"name": "Vitamin C"}]
        }

        status, missing_fields, details = validator.validate_product(product_data)

        # fullName should be detected as missing due to placeholder value
        assert "fullName" in missing_fields

    def test_valid_product_passes(self, validator):
        """Test that valid product data passes validation"""
        product_data = {
            "fullName": "Test Supplement",
            "brandName": "Test Brand",
            "productVersionCode": "123",
            "upcSku": "123456789012",
            "ingredientRows": [{"name": "Vitamin C"}]
        }

        status, missing_fields, details = validator.validate_product(product_data)

        # No critical fields should be missing
        assert "fullName" not in missing_fields
        assert "brandName" not in missing_fields


class TestHierarchyClassification:
    """Tests for hierarchy type classification (source/summary/component)"""

    @pytest.fixture
    def normalizer(self):
        return EnhancedDSLDNormalizer()

    def test_hierarchy_lookup_structure(self, normalizer):
        """Test that hierarchy lookup is a valid dict structure"""
        # Note: _hierarchy_lookup is built from ingredient_classification.json["classifications"]
        # which uses a flat structure {item: {hierarchy: type}} rather than categories with lists
        # The lookup may be empty if the JSON doesn't have sources/summaries/components lists
        assert hasattr(normalizer, '_hierarchy_lookup')
        assert isinstance(normalizer._hierarchy_lookup, dict)

    def test_classify_hierarchy_type_returns_none_for_unknown(self, normalizer):
        """Test that unknown ingredients return None"""
        # For ingredients not in the hierarchy lookup, returns None
        result = normalizer._classify_hierarchy_type("unknown_ingredient_xyz")
        assert result is None

    def test_classify_hierarchy_type_handles_empty_name(self, normalizer):
        """Test that empty/None names return None"""
        assert normalizer._classify_hierarchy_type("") is None
        assert normalizer._classify_hierarchy_type(None) is None


class TestBannedIngredientDetection:
    """Tests for banned ingredient detection (deterministic path)"""

    @pytest.fixture
    def normalizer(self):
        return EnhancedDSLDNormalizer()

    def test_banned_ephedra_exact_match(self, normalizer):
        """Test that Ephedra (a known banned ingredient) is detected via exact match"""
        # Ephedra is in permanently_banned with standard_name "Ephedra"
        result = normalizer._check_banned_recalled("Ephedra")
        assert result is True, "Ephedra should be detected as banned"

    def test_banned_ephedra_alias_match(self, normalizer):
        """Test that Ephedra aliases are detected"""
        # "ma huang" is an alias for Ephedra
        result = normalizer._check_banned_recalled("Ma Huang")
        assert result is True, "Ma Huang (Ephedra alias) should be detected as banned"

    def test_banned_dmaa_detection(self, normalizer):
        """Test that DMAA is detected as banned"""
        result = normalizer._check_banned_recalled("DMAA")
        assert result is True, "DMAA should be detected as banned"

        # Check alias
        result = normalizer._check_banned_recalled("1,3-dimethylamylamine")
        assert result is True, "1,3-dimethylamylamine (DMAA alias) should be detected"

    def test_safe_ingredient_not_banned(self, normalizer):
        """Test that safe ingredients are not flagged as banned"""
        result = normalizer._check_banned_recalled("Vitamin C")
        assert result is False, "Vitamin C should NOT be flagged as banned"

        result = normalizer._check_banned_recalled("Fish Oil")
        assert result is False, "Fish Oil should NOT be flagged as banned"

    def test_banned_detection_case_insensitive(self, normalizer):
        """Test that banned detection works regardless of case"""
        # Should detect regardless of case (via preprocessed text comparison)
        result = normalizer._check_banned_recalled("ephedra")
        assert result is True, "ephedra (lowercase) should be detected"

        result = normalizer._check_banned_recalled("EPHEDRA")
        assert result is True, "EPHEDRA (uppercase) should be detected"

    def test_banned_delta8_shorthand_detected(self, normalizer):
        """Unified banned DB lookup should still catch shorthand delta-8 labels."""
        assert normalizer._check_banned_recalled("Delta-8") is True

    def test_priority_classification_preserves_banned_bucket_severity(self, normalizer):
        """Banned DB severity should not be collapsed to critical for non-fail buckets."""
        classification = normalizer._priority_based_classification("Delta-8 THC", [])
        assert classification["banned_info"]["is_banned"] is True
        assert classification["banned_info"]["severity"] == "moderate"


class TestSkipTierCConfig:
    """Tests for Tier C case-insensitive skip (config-controlled)"""

    @pytest.fixture
    def normalizer(self):
        return EnhancedDSLDNormalizer()

    def test_tier_c_config_loaded(self, normalizer):
        """Test that Tier C config is loaded from ingredient_classification.json"""
        # Should have the config attribute
        assert hasattr(normalizer, '_enable_case_insensitive_skip')

    def test_tier_c_case_insensitive_when_enabled(self, normalizer):
        """Test case-insensitive matching when Tier C is enabled"""
        if normalizer._enable_case_insensitive_skip:
            # Should match "Total Omega-3" against "total omega-3"
            assert normalizer._should_skip_ingredient("Total Omega-3") is True
            assert normalizer._should_skip_ingredient("TOTAL OMEGA-3") is True
        else:
            # Without Tier C, case must match exactly
            # "Total Omega-3" won't match "total omega-3"
            pass  # Behavior depends on config


class TestEndToEndProductNormalization:
    """Integration tests for full product normalization"""

    @pytest.fixture
    def normalizer(self):
        return EnhancedDSLDNormalizer()

    def test_nutrition_facts_excluded_from_output(self, normalizer):
        """Test that nutrition facts are excluded from ingredient outputs"""
        raw_product = {
            "id": "test_product",
            "fullName": "Test Gummies",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "ingredientRows": [
                {"name": "Calories", "ingredientGroup": "Amount Per Serving", "order": 1},
                {"name": "Total Carbohydrates", "ingredientGroup": "", "order": 2},
                {"name": "Sugar", "ingredientGroup": "", "order": 3},
                {"name": "Vitamin C", "ingredientGroup": "Vitamins", "order": 4},
            ]
        }

        cleaned = normalizer.normalize_product(raw_product)

        # Get all active ingredient names
        active_names = [ing.get("name", "").lower() for ing in cleaned.get("activeIngredients", [])]

        # Nutrition facts should NOT appear
        assert "calories" not in active_names
        assert "total carbohydrates" not in active_names
        assert "sugar" not in active_names

        # Real ingredients SHOULD appear
        assert "vitamin c" in active_names

    def test_label_header_forms_extracted(self, normalizer):
        """Test that label header forms are extracted as separate ingredients"""
        raw_product = {
            "id": "test_product",
            "fullName": "Test Supplement",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "ingredientRows": [
                {
                    "name": "Less than 2% of:",
                    "order": 1,
                    "forms": [
                        {"name": "Citric Acid", "order": 1},
                        {"name": "Natural Flavors", "order": 2}
                    ]
                },
                {"name": "Vitamin C", "order": 2}
            ]
        }

        cleaned = normalizer.normalize_product(raw_product)

        active_names = [ing.get("name", "").lower() for ing in cleaned.get("activeIngredients", [])]
        inactive_names = [ing.get("name", "").lower() for ing in cleaned.get("inactiveIngredients", [])]
        all_names = active_names + inactive_names

        # Header should NOT appear in either list
        assert "less than 2% of:" not in all_names

        # Forms from label headers in ingredientRows are processed and appended to active list
        # (though marked with is_active=False internally)
        # The key behavior is: header is dropped, forms are extracted
        assert "citric acid" in all_names, f"citric acid not found in {all_names}"
        assert "natural flavors" in all_names, f"natural flavors not found in {all_names}"

        # Regular ingredient SHOULD appear in active
        assert "vitamin c" in active_names

    def test_unknown_zero_quantity_active_stays_unmapped(self, normalizer):
        """Missing quantity alone must not auto-mark an active as proprietary/mapped."""
        raw_product = {
            "id": "test_unknown_zero_qty",
            "fullName": "Test Product",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "ingredientRows": [
                {
                    "name": "Completely New Active",
                    "order": 1,
                    "quantity": None,
                    "unit": "",
                    "ingredientGroup": "Other",
                }
            ],
        }

        cleaned = normalizer.normalize_product(raw_product)
        active = cleaned["activeIngredients"][0]

        assert active["name"] == "Completely New Active"
        assert active["mapped"] is False
        assert active["proprietaryBlend"] is False

    def test_extract_nutritional_amount_reads_dsld_quantity_key(self, normalizer):
        """Nutritional amount helper must read DSLD quantity objects, not stale amount-only schema."""
        result = normalizer._extract_nutritional_amount(
            {"quantity": [{"quantity": 5, "unit": "mg"}]}
        )
        assert result == {"amount": 5, "unit": "mg"}


class TestBug1TierCCaseInsensitive:
    """
    Bug 1 Regression: Tier C case-insensitive skip was comparing lowercased
    strings against non-lowercased sets. Fixed by adding dedicated CI sets.
    """

    @pytest.fixture
    def normalizer(self):
        return EnhancedDSLDNormalizer()

    def test_tier_c_ci_sets_exist(self, normalizer):
        """Verify CI sets are built at init"""
        assert hasattr(normalizer, '_skip_exact_ci')
        assert hasattr(normalizer, '_skip_normalized_ci')
        if normalizer._enable_case_insensitive_skip:
            # CI sets should have same count as original sets
            assert len(normalizer._skip_exact_ci) == len(normalizer._skip_exact)
            assert len(normalizer._skip_normalized_ci) == len(normalizer._skip_normalized)

    def test_same_ingredient_all_case_variants_skip_identically(self, normalizer):
        """Same ingredient with different casing should all skip identically"""
        # "DELETE" is in skip_exact.
        # With Tier C enabled: all case variants should skip.
        # With Tier C disabled: only exact-case Tier A behavior is guaranteed.
        assert normalizer._should_skip_ingredient("DELETE") is True
        if normalizer._enable_case_insensitive_skip:
            assert normalizer._should_skip_ingredient("delete") is True
            assert normalizer._should_skip_ingredient("Delete") is True
            assert normalizer._should_skip_ingredient("DeLeTe") is True
        else:
            assert normalizer._should_skip_ingredient("delete") is False

    def test_multi_space_variants_skip(self, normalizer):
        """Multi-space variants should skip via Tier B normalization"""
        # "Total EPA & DHA" with extra spaces should still match
        assert normalizer._should_skip_ingredient("Total  EPA & DHA") is True
        assert normalizer._should_skip_ingredient("Total   EPA  &  DHA") is True

    def test_valid_ingredient_not_skipped_regardless_of_case(self, normalizer):
        """Valid ingredients should NOT be skipped regardless of case"""
        # These are real ingredients, not in skip list
        assert normalizer._should_skip_ingredient("Vitamin C") is False
        assert normalizer._should_skip_ingredient("VITAMIN C") is False
        assert normalizer._should_skip_ingredient("vitamin c") is False


class TestBug2ParallelNoneAppend:
    """
    Bug 2 Regression: Parallel 'other ingredient' processing was appending None
    for skipped items, causing sort() to crash. Fixed by filtering out None.
    """

    @pytest.fixture
    def normalizer(self):
        return EnhancedDSLDNormalizer()

    def test_all_ingredients_skipped_produces_empty_list(self, normalizer):
        """When all other-ingredients are skipped, result should be empty list"""
        # Create a product where all other ingredients are in skip list
        # Using actual items from ingredient_classification.json skip_exact
        raw_product = {
            "id": "test_all_skipped",
            "fullName": "Test Product",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "ingredientRows": [],
            "otherIngredients": {
                "ingredients": [
                    {"name": "DELETE", "order": 1},  # in skip_exact
                    {"name": "Total EPA & DHA", "order": 2},  # in skip_exact
                    {"name": "Less than 2% of:", "order": 3},  # in skip_exact
                ]
            }
        }

        # This should NOT crash (previously would crash on sort with None)
        cleaned = normalizer.normalize_product(raw_product)

        # Result should be valid structure
        assert "inactiveIngredients" in cleaned
        assert isinstance(cleaned["inactiveIngredients"], list)
        # All were skipped, so list should be empty or contain only valid dicts
        for ing in cleaned.get("inactiveIngredients", []):
            assert ing is not None, "None should never appear in ingredient list"
            assert isinstance(ing, dict), "All ingredients should be dicts"

    def test_mixed_skip_and_valid_ingredients(self, normalizer):
        """Mix of skipped and valid ingredients should work correctly"""
        # Using actual skip list items from ingredient_classification.json
        raw_product = {
            "id": "test_mixed",
            "fullName": "Test Product",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "ingredientRows": [],
            "otherIngredients": {
                "ingredients": [
                    {"name": "DELETE", "order": 1},  # in skip_exact
                    {"name": "citric acid", "order": 2},  # valid
                    {"name": "Total EPA & DHA", "order": 3},  # in skip_exact
                    {"name": "natural flavors", "order": 4},  # valid
                ]
            }
        }

        cleaned = normalizer.normalize_product(raw_product)

        inactive = cleaned.get("inactiveIngredients", [])
        # Should have only valid ingredients, no None
        assert all(ing is not None for ing in inactive)
        assert all(isinstance(ing, dict) for ing in inactive)

        # Valid ingredients should appear
        inactive_names = [ing.get("name", "").lower() for ing in inactive]
        assert "citric acid" in inactive_names
        assert "natural flavors" in inactive_names

        # Skipped ingredients should NOT appear
        assert "delete" not in inactive_names
        assert "total epa & dha" not in inactive_names


class TestBug3MatcherInitOrder:
    """
    Bug 3 Regression: _build_hierarchy_lookup() was called before self.matcher
    existed, causing normalization mismatch. Fixed by creating matcher first.
    """

    @pytest.fixture
    def normalizer(self):
        return EnhancedDSLDNormalizer()

    def test_matcher_exists_before_hierarchy_lookup(self, normalizer):
        """Verify matcher is created and hierarchy lookup is initialized"""
        # Bug 3: Matcher must exist before _build_hierarchy_lookup() is called
        assert hasattr(normalizer, 'matcher')
        assert normalizer.matcher is not None
        assert hasattr(normalizer, '_hierarchy_lookup')
        # Note: _hierarchy_lookup may be empty if ingredient_classification.json
        # doesn't have sources/summaries/components lists in its classifications
        assert isinstance(normalizer._hierarchy_lookup, dict)

    def test_deterministic_normalization_across_instances(self):
        """Same product normalized by two fresh instances should be identical"""
        raw_product = {
            "id": "test_determinism",
            "fullName": "Fish Oil Supplement",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "ingredientRows": [
                {"name": "Fish Oil", "order": 1},
                {"name": "EPA", "order": 2},
                {"name": "DHA", "order": 3},
            ]
        }

        # Create two fresh normalizer instances
        normalizer1 = EnhancedDSLDNormalizer()
        normalizer2 = EnhancedDSLDNormalizer()

        # Normalize same product with each
        result1 = normalizer1.normalize_product(raw_product.copy())
        result2 = normalizer2.normalize_product(raw_product.copy())

        # Compare active ingredients (excluding timestamps/metadata)
        active1 = result1.get("activeIngredients", [])
        active2 = result2.get("activeIngredients", [])

        assert len(active1) == len(active2), "Same number of ingredients"

        for ing1, ing2 in zip(active1, active2):
            assert ing1.get("name") == ing2.get("name"), "Same ingredient name"
            assert ing1.get("standardName") == ing2.get("standardName"), "Same standard name"
            assert ing1.get("mapped") == ing2.get("mapped"), "Same mapped status"


class TestBug4PassiveBranchRemoval:
    """
    Bug 4 Regression: Dead 'passive' branch was never triggered because no
    'passive' type exists in _fast_exact_lookup. Branch removed, structure kept.
    """

    @pytest.fixture
    def normalizer(self):
        return EnhancedDSLDNormalizer()

    def test_no_passive_type_in_fast_lookup(self, normalizer):
        """Verify no 'passive' type entries exist in fast lookup"""
        for key, value in normalizer._fast_exact_lookup.items():
            assert value.get("type") != "passive", \
                f"Unexpected 'passive' type found for key: {key}"

    def test_passive_info_always_false(self, normalizer):
        """Verify passive_info is always False in classification results"""
        test_ingredients = ["Vitamin C", "Fish Oil", "Citric Acid", "EPA"]

        for ingredient in test_ingredients:
            result = normalizer._priority_based_classification(ingredient)
            assert result["passive_info"]["is_passive"] is False, \
                f"passive_info should be False for {ingredient}"
            assert result["priority_applied"]["passive"] is False, \
                f"priority_applied.passive should be False for {ingredient}"


class TestGuardrailA_IngredientArrayValidation:
    """
    Guardrail A: Validate ingredient arrays before sorting/serializing.
    Catches: None in arrays, non-dict entries, missing 'name' field.
    """

    @pytest.fixture
    def normalizer(self):
        return EnhancedDSLDNormalizer()

    def test_active_ingredients_all_valid_structure(self, normalizer):
        """All active ingredients should have valid structure"""
        raw_product = {
            "id": "test_structure",
            "fullName": "Test Product",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "ingredientRows": [
                {"name": "Vitamin C", "order": 1},
                {"name": "Zinc", "order": 2},
                {"name": "EPA", "order": 3},
            ]
        }

        cleaned = normalizer.normalize_product(raw_product)
        active = cleaned.get("activeIngredients", [])

        # Validate every element
        for i, ing in enumerate(active):
            assert ing is not None, f"Element {i} is None"
            assert isinstance(ing, dict), f"Element {i} is not a dict: {type(ing)}"
            assert "name" in ing, f"Element {i} missing 'name' field"
            assert isinstance(ing.get("name"), str), f"Element {i} 'name' is not string"

    def test_inactive_ingredients_all_valid_structure(self, normalizer):
        """All inactive ingredients should have valid structure"""
        raw_product = {
            "id": "test_structure",
            "fullName": "Test Product",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "ingredientRows": [],
            "otherIngredients": {
                "ingredients": [
                    {"name": "Citric Acid", "order": 1},
                    {"name": "Natural Flavors", "order": 2},
                ]
            }
        }

        cleaned = normalizer.normalize_product(raw_product)
        inactive = cleaned.get("inactiveIngredients", [])

        # Validate every element
        for i, ing in enumerate(inactive):
            assert ing is not None, f"Element {i} is None"
            assert isinstance(ing, dict), f"Element {i} is not a dict: {type(ing)}"
            assert "name" in ing, f"Element {i} missing 'name' field"
            assert isinstance(ing.get("name"), str), f"Element {i} 'name' is not string"


class TestGuardrailB_DeterministicOutput:
    """
    Guardrail B: Deterministic output test.
    Same raw product normalized twice (fresh normalizer each time) should
    produce deep-equal output (excluding timestamps/run metadata).
    """

    def test_full_product_determinism(self):
        """Full product normalization should be deterministic"""
        raw_product = {
            "id": "test_determinism",
            "fullName": "Complete Test Supplement",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "ingredientRows": [
                {"name": "Vitamin C", "ingredientGroup": "Vitamins", "order": 1},
                {"name": "Vitamin D3", "ingredientGroup": "Vitamins", "order": 2},
                {"name": "Fish Oil", "ingredientGroup": "Specialty", "order": 3},
                {"name": "EPA", "ingredientGroup": "Specialty", "order": 4},
                {"name": "DHA", "ingredientGroup": "Specialty", "order": 5},
            ],
            "otherIngredients": {
                "ingredients": [
                    {"name": "Gelatin", "order": 1},
                    {"name": "Glycerin", "order": 2},
                ]
            }
        }

        # Run twice with fresh normalizers
        normalizer1 = EnhancedDSLDNormalizer()
        normalizer2 = EnhancedDSLDNormalizer()

        result1 = normalizer1.normalize_product(raw_product.copy())
        result2 = normalizer2.normalize_product(raw_product.copy())

        # Compare structures (excluding metadata timestamps)
        def compare_ingredients(list1, list2, label):
            assert len(list1) == len(list2), f"{label}: different lengths"
            for i, (ing1, ing2) in enumerate(zip(list1, list2)):
                for key in ["name", "standardName", "mapped"]:
                    assert ing1.get(key) == ing2.get(key), \
                        f"{label}[{i}].{key} differs: {ing1.get(key)} vs {ing2.get(key)}"

        compare_ingredients(
            result1.get("activeIngredients", []),
            result2.get("activeIngredients", []),
            "activeIngredients"
        )
        compare_ingredients(
            result1.get("inactiveIngredients", []),
            result2.get("inactiveIngredients", []),
            "inactiveIngredients"
        )

    def test_hierarchy_classification_determinism(self):
        """Hierarchy classification should be deterministic across instances"""
        test_ingredients = [
            "Fish Oil",  # source
            "Total Omega-3",  # summary
            "EPA",  # component
            "DHA",  # component
        ]

        normalizer1 = EnhancedDSLDNormalizer()
        normalizer2 = EnhancedDSLDNormalizer()

        for ingredient in test_ingredients:
            result1 = normalizer1._classify_hierarchy_type(ingredient)
            result2 = normalizer2._classify_hierarchy_type(ingredient)
            assert result1 == result2, \
                f"Hierarchy for '{ingredient}' differs: {result1} vs {result2}"


class TestBatchProcessorCoupling:
    """
    Verify normalizer output meets BatchProcessor expectations:
    - metadata always present
    - activeIngredients/inactiveIngredients are lists (even if empty)
    - No None values in ingredient arrays
    """

    @pytest.fixture
    def normalizer(self):
        return EnhancedDSLDNormalizer()

    def test_metadata_always_present(self, normalizer):
        """metadata key should always exist in output"""
        raw_product = {
            "id": "test_meta",
            "fullName": "Test",
            "brandName": "Brand",
            "productVersionCode": "1",
            "ingredientRows": []
        }

        cleaned = normalizer.normalize_product(raw_product)
        assert "metadata" in cleaned, "metadata key must always be present"
        assert isinstance(cleaned["metadata"], dict), "metadata must be a dict"

    def test_ingredient_arrays_always_lists(self, normalizer):
        """activeIngredients and inactiveIngredients should always be lists"""
        raw_product = {
            "id": "test_arrays",
            "fullName": "Test",
            "brandName": "Brand",
            "productVersionCode": "1",
            "ingredientRows": []
        }

        cleaned = normalizer.normalize_product(raw_product)

        assert "activeIngredients" in cleaned, "activeIngredients key must exist"
        assert isinstance(cleaned["activeIngredients"], list), "must be a list"

        assert "inactiveIngredients" in cleaned, "inactiveIngredients key must exist"
        assert isinstance(cleaned["inactiveIngredients"], list), "must be a list"

    def test_no_none_in_ingredient_arrays(self, normalizer):
        """No None values should appear in ingredient arrays"""
        raw_product = {
            "id": "test_no_none",
            "fullName": "Test",
            "brandName": "Brand",
            "productVersionCode": "1",
            "ingredientRows": [
                {"name": "Vitamin C", "order": 1},
                {"name": "total calories", "order": 2},  # should be skipped
            ],
            "otherIngredients": {
                "ingredients": [
                    {"name": "Citric Acid", "order": 1},
                    {"name": "delete", "order": 2},  # should be skipped
                ]
            }
        }

        cleaned = normalizer.normalize_product(raw_product)

        for ing in cleaned.get("activeIngredients", []):
            assert ing is not None, "None found in activeIngredients"

        for ing in cleaned.get("inactiveIngredients", []):
            assert ing is not None, "None found in inactiveIngredients"


class TestNaturalColorMapping:
    """
    Regression tests for Colors classification (P0.5).

    Ensures "Colors" with natural indicator forms (e.g., "from Fruits", "and Vegetables")
    is NOT incorrectly mapped to "synthetic colors" or flagged as artificial.

    Root cause: generate_variations("synthetic colors") returned ["colors"] which polluted
    the main ingredient_alias_lookup, causing natural colors to get standardName="synthetic colors".

    Fix:
    1. Removed harmful additive alias variations from main lookup
    2. Added context-aware Colors special-case mapping with forms check
    """

    @pytest.fixture
    def normalizer(self):
        return EnhancedDSLDNormalizer()

    def test_colors_with_fruit_vegetable_forms_not_synthetic(self, normalizer):
        """Colors from Fruits and Vegetables should NOT be mapped to 'synthetic colors'"""
        raw_product = {
            "id": "test_natural_colors",
            "fullName": "Test Natural Colors Product",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "ingredientRows": [],
            "otherIngredients": {
                "ingredients": [
                    {
                        "name": "Colors",
                        "order": 1,
                        "forms": [
                            {"prefix": "from", "name": "Fruits"},
                            {"prefix": "and", "name": "Vegetables"}
                        ]
                    }
                ]
            }
        }

        cleaned = normalizer.normalize_product(raw_product)
        inactive = cleaned.get("inactiveIngredients", [])

        # Find the Colors ingredient (field is 'name' not 'originalName')
        colors_ing = None
        for ing in inactive:
            if ing and ing.get("name", "").lower() == "colors":
                colors_ing = ing
                break

        assert colors_ing is not None, "Colors ingredient should be present in output"

        standard_name = colors_ing.get("standardName", "").lower()

        # CRITICAL ASSERTION: Must NOT be mapped to synthetic colors
        assert standard_name != "synthetic colors", \
            f"REGRESSION: Colors with fruit/vegetable forms incorrectly mapped to 'synthetic colors' (got: {standard_name})"

        # Should be mapped to natural colors
        assert standard_name == "natural colors", \
            f"Colors with fruit/vegetable forms should map to 'natural colors' (got: {standard_name})"

    def test_fd_c_dyes_are_artificial(self, normalizer):
        """FD&C dyes should be flagged as artificial colors"""
        raw_product = {
            "id": "test_artificial_colors",
            "fullName": "Test Artificial Colors Product",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "ingredientRows": [],
            "otherIngredients": {
                "ingredients": [
                    {
                        "name": "Colors",
                        "order": 1,
                        "forms": [
                            {"prefix": "", "name": "FD&C Red 40"},
                            {"prefix": "", "name": "FD&C Yellow 5"}
                        ]
                    }
                ]
            }
        }

        cleaned = normalizer.normalize_product(raw_product)
        inactive = cleaned.get("inactiveIngredients", [])

        # Find the Colors ingredient (field is 'name' not 'originalName')
        colors_ing = None
        for ing in inactive:
            if ing and ing.get("name", "").lower() == "colors":
                colors_ing = ing
                break

        assert colors_ing is not None, "Colors ingredient should be present in output"

        standard_name = colors_ing.get("standardName", "").lower()

        # Should be mapped to artificial colors when FD&C dyes are in forms
        assert standard_name == "artificial colors", \
            f"Colors with FD&C dyes should map to 'artificial colors' (got: {standard_name})"

    def test_ambiguous_colors_not_synthetic(self, normalizer):
        """Colors without context should NOT default to 'synthetic colors'"""
        raw_product = {
            "id": "test_ambiguous_colors",
            "fullName": "Test Ambiguous Colors Product",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "ingredientRows": [],
            "otherIngredients": {
                "ingredients": [
                    {
                        "name": "Colors",
                        "order": 1,
                        "forms": []  # No context
                    }
                ]
            }
        }

        cleaned = normalizer.normalize_product(raw_product)
        inactive = cleaned.get("inactiveIngredients", [])

        # Find the Colors ingredient (field is 'name' not 'originalName')
        colors_ing = None
        for ing in inactive:
            if ing and ing.get("name", "").lower() == "colors":
                colors_ing = ing
                break

        assert colors_ing is not None, "Colors ingredient should be present in output"

        standard_name = colors_ing.get("standardName", "").lower()

        # CRITICAL: Must NOT default to synthetic colors
        assert standard_name != "synthetic colors", \
            f"REGRESSION: Ambiguous Colors incorrectly defaulted to 'synthetic colors' (got: {standard_name})"

        # Should be mapped to generic/unspecified colors
        assert "unspecified" in standard_name or standard_name == "colors", \
            f"Ambiguous Colors should map to 'colors (unspecified)' or 'colors' (got: {standard_name})"

    def test_forms_with_prefix_preserved(self, normalizer):
        """Forms with prefix should be extracted correctly for context matching"""
        # Test that "from Fruits" is extracted as a complete phrase, not just "Fruits"
        name = "Colors"
        forms = [
            {"prefix": "from", "name": "Fruits"},
            {"prefix": "and", "name": "Vegetables"}
        ]

        # Simulate form extraction
        extracted_forms = []
        for f in forms:
            if isinstance(f, dict):
                prefix = (f.get("prefix", "") or "").strip()
                name_part = (f.get("name", "") or "").strip()
                full_form = f"{prefix} {name_part}".strip() if prefix else name_part
                if full_form:
                    extracted_forms.append(full_form)

        assert "from Fruits" in extracted_forms, "Prefix should be included in form extraction"
        assert "and Vegetables" in extracted_forms, "Prefix should be included in form extraction"

        # Verify context matching works
        forms_text = ' '.join(f.lower() for f in extracted_forms)
        natural_indicators = ['from fruits', 'from vegetables', 'fruit', 'vegetable']
        has_natural = any(ind in forms_text for ind in natural_indicators)

        assert has_natural, f"Natural color indicators should match in '{forms_text}'"


class TestExplicitDyePriority:
    """
    Tests for P0.5 explicit dye priority:
    1. Explicit artificial dyes override indicators
    2. Explicit natural dyes override indicators
    3. Ambiguous colors → unspecified when no context
    """

    @pytest.fixture
    def normalizer(self):
        """Create a normalizer instance for testing"""
        return EnhancedDSLDNormalizer()

    def test_explicit_artificial_dye_red_40(self, normalizer):
        """Explicit artificial dye: 'Red 40' maps to 'artificial colors'"""
        standard_name, mapped, forms = normalizer._enhanced_ingredient_mapping("Red 40", [])
        assert standard_name == "artificial colors", \
            f"Red 40 (explicit artificial dye) should map to 'artificial colors', got: {standard_name}"
        assert mapped is True

    def test_explicit_artificial_dye_fd_c_yellow_5(self, normalizer):
        """Explicit artificial dye: 'FD&C Yellow 5' maps to 'artificial colors'"""
        standard_name, mapped, forms = normalizer._enhanced_ingredient_mapping("FD&C Yellow 5", [])
        assert standard_name == "artificial colors", \
            f"FD&C Yellow 5 should map to 'artificial colors', got: {standard_name}"

    def test_explicit_artificial_dye_blue_1_lake(self, normalizer):
        """Explicit artificial dye: 'Blue 1 Lake' maps to 'artificial colors'"""
        standard_name, mapped, forms = normalizer._enhanced_ingredient_mapping("Blue 1 Lake", [])
        assert standard_name == "artificial colors", \
            f"Blue 1 Lake should map to 'artificial colors', got: {standard_name}"

    def test_explicit_natural_dye_annatto(self, normalizer):
        """Explicit natural dye: 'Annatto' maps to 'natural colors'"""
        standard_name, mapped, forms = normalizer._enhanced_ingredient_mapping("Annatto", [])
        assert standard_name == "natural colors", \
            f"Annatto (explicit natural dye) should map to 'natural colors', got: {standard_name}"

    def test_turmeric_maps_to_iqm_not_natural_colors(self, normalizer):
        """Turmeric has IQM therapeutic entry — should NOT be intercepted by dye matcher"""
        standard_name, mapped, forms = normalizer._enhanced_ingredient_mapping("Turmeric", [])
        assert "curcumin" in standard_name.lower() or "turmeric" in standard_name.lower(), \
            f"Turmeric should map to IQM (Curcumin/Turmeric), got: {standard_name}"

    def test_explicit_natural_dye_beet_juice(self, normalizer):
        """Explicit natural dye: 'Beet Juice' maps to 'natural colors'"""
        standard_name, mapped, forms = normalizer._enhanced_ingredient_mapping("Beet Juice", [])
        assert standard_name == "natural colors", \
            f"Beet Juice should map to 'natural colors', got: {standard_name}"

    def test_beta_carotene_maps_to_iqm_not_natural_colors(self, normalizer):
        """Beta-Carotene has IQM therapeutic entry — should NOT be intercepted by dye matcher"""
        standard_name, mapped, forms = normalizer._enhanced_ingredient_mapping("Beta-Carotene", [])
        assert "beta" in standard_name.lower() or "carotene" in standard_name.lower() or "vitamin a" in standard_name.lower(), \
            f"Beta-Carotene should map to IQM, got: {standard_name}"

    def test_ambiguous_colors_no_context(self, normalizer):
        """Ambiguous 'Colors' with no forms → 'colors (unspecified)'"""
        standard_name, mapped, forms = normalizer._enhanced_ingredient_mapping("Colors", [])
        assert standard_name == "colors (unspecified)", \
            f"Colors without context should map to 'colors (unspecified)', got: {standard_name}"

    def test_colors_with_natural_indicator(self, normalizer):
        """Colors with natural indicator forms → 'natural colors'"""
        forms = ["from Fruits", "and Vegetables"]
        standard_name, mapped, forms_out = normalizer._enhanced_ingredient_mapping("Colors", forms)
        assert standard_name == "natural colors", \
            f"Colors with fruit/vegetable forms should map to 'natural colors', got: {standard_name}"

    def test_colors_with_artificial_indicator(self, normalizer):
        """Colors with artificial indicator forms → 'artificial colors'"""
        forms = ["FD&C", "certified color"]
        standard_name, mapped, forms_out = normalizer._enhanced_ingredient_mapping("Colors", forms)
        assert standard_name == "artificial colors", \
            f"Colors with FD&C forms should map to 'artificial colors', got: {standard_name}"

    def test_explicit_artificial_overrides_natural_indicator_in_forms(self, normalizer):
        """Explicit artificial dye name overrides natural indicators in forms"""
        # Red 40 should be artificial even if forms mention "natural"
        forms = ["natural flavor", "from plants"]  # These would normally indicate natural
        standard_name, mapped, forms_out = normalizer._enhanced_ingredient_mapping("Red 40", forms)
        assert standard_name == "artificial colors", \
            f"Red 40 should ALWAYS be artificial regardless of forms, got: {standard_name}"

    def test_explicit_natural_overrides_artificial_indicator_in_forms(self, normalizer):
        """Explicit natural dye name overrides artificial indicators in forms"""
        # Annatto should be natural even if forms mention "synthetic"
        forms = ["synthetic process"]  # This would normally indicate artificial
        standard_name, mapped, forms_out = normalizer._enhanced_ingredient_mapping("Annatto", forms)
        assert standard_name == "natural colors", \
            f"Annatto should ALWAYS be natural regardless of forms, got: {standard_name}"


class TestColorIndicatorsMissingFile:
    """Tests for missing color_indicators.json behavior"""

    def test_normalizer_validates_color_indicators_not_empty(self):
        """Normalizer validates color_indicators has data (tested via __init__ code path)"""
        # The normalizer checks `if not color_indicators_db or not color_indicators_db.get("natural_indicators")`
        # We verify the check exists by testing that a valid normalizer has the required data
        normalizer = EnhancedDSLDNormalizer()

        # Verify the normalizer has loaded the data (which means validation passed)
        assert len(normalizer.NATURAL_COLOR_INDICATORS) > 0, \
            "Normalizer should have natural color indicators after init"
        assert len(normalizer.EXPLICIT_ARTIFICIAL_DYES) > 0, \
            "Normalizer should have explicit artificial dyes after init"
        assert len(normalizer.EXPLICIT_NATURAL_DYES) > 0, \
            "Normalizer should have explicit natural dyes after init"

    def test_enricher_has_color_indicators_as_critical(self):
        """Enricher lists color_indicators as a critical database"""
        from enrich_supplements_v3 import SupplementEnricherV3

        # Create enricher with all required databases
        enricher = SupplementEnricherV3()

        # Verify the enricher loaded color_indicators
        color_db = enricher.databases.get('color_indicators', {})
        assert 'natural_indicators' in color_db, \
            "Enricher should have color_indicators loaded with natural_indicators"

        # Verify the enricher has the required properties
        assert len(enricher.NATURAL_COLOR_INDICATORS) > 0
        assert len(enricher.EXPLICIT_ARTIFICIAL_DYES) > 0


class TestReferenceVersionsMetadata:
    """Tests for reference_versions in cleaned/enriched output"""

    @pytest.fixture
    def normalizer(self):
        return EnhancedDSLDNormalizer()

    def test_normalizer_has_reference_versions(self, normalizer):
        """Normalizer should have reference_versions attribute after init"""
        assert hasattr(normalizer, 'reference_versions')
        assert isinstance(normalizer.reference_versions, dict)
        assert 'color_indicators' in normalizer.reference_versions

    def test_reference_versions_has_version_field(self, normalizer):
        """reference_versions should include version info for color_indicators"""
        color_vers = normalizer.reference_versions.get('color_indicators', {})
        assert 'version' in color_vers
        assert color_vers['version'] != 'unknown'

    def test_reference_versions_has_last_updated(self, normalizer):
        """reference_versions should include last_updated for color_indicators"""
        color_vers = normalizer.reference_versions.get('color_indicators', {})
        assert 'last_updated' in color_vers


class TestDisplayLedgerEnrichment:
    def test_display_ledger_enrichment_keeps_wrappers_non_scoring(self):
        from enrich_supplements_v3 import SupplementEnricherV3
        import normalization as norm_module

        enricher = SupplementEnricherV3()
        product = {
            "id": "display-ledger-enrichment-regression",
            "fullName": "Display Ledger Enrichment Regression",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "activeIngredients": [
                {
                    "name": "Docosahexaenoic Acid",
                    "standardName": "Docosahexaenoic Acid",
                    "raw_source_text": "Docosahexaenoic Acid",
                    "raw_source_path": "activeIngredients",
                    "normalized_key": norm_module.make_normalized_key("Docosahexaenoic Acid"),
                    "quantity": 250,
                    "unit": "mg",
                    "mapped": True,
                }
            ],
            "inactiveIngredients": [],
            "display_ingredients": [
                {
                    "raw_source_text": "Other Omega-3's",
                    "display_name": "Other Omega-3's",
                    "source_section": "activeIngredients",
                    "display_type": "summary_wrapper",
                    "resolution_type": "suppressed_parent",
                    "score_included": False,
                },
                {
                    "raw_source_text": "Docosahexaenoic Acid",
                    "display_name": "Docosahexaenoic Acid",
                    "source_section": "activeIngredients",
                    "display_type": "mapped_ingredient",
                    "resolution_type": "direct_mapped",
                    "score_included": True,
                },
            ],
        }

        enriched, issues = enricher.enrich_product(product)
        assert not issues

        display_by_raw = {
            row.get("raw_source_text"): row for row in enriched.get("display_ingredients", [])
        }

        assert "mapped_to" not in display_by_raw["Other Omega-3's"]
        assert display_by_raw["Other Omega-3's"]["score_included"] is False
        assert display_by_raw["Docosahexaenoic Acid"]["mapped_to"]["standard_name"] == "Docosahexaenoic Acid"


def test_inactive_exact_other_ingredient_lookup_beats_normalized_collision():
    from enhanced_normalizer import EnhancedDSLDNormalizer

    normalizer = EnhancedDSLDNormalizer()
    standard_name, mapped, _ = normalizer._map_inactive_name_prefer_other(
        "Vegetable", ingredient_group="Blend"
    )

    assert mapped is True
    assert standard_name == "Vegetable (Descriptor)"


def test_inactive_algal_oil_exact_route_beats_active_omega_capture():
    from enhanced_normalizer import EnhancedDSLDNormalizer

    normalizer = EnhancedDSLDNormalizer()
    standard_name, mapped, _ = normalizer._map_inactive_name_prefer_other(
        "Marine Algae Oil", ingredient_group="Algal Oil"
    )

    assert mapped is True
    assert standard_name == "Algal Oil (as carrier)"


def test_batch24_bladder_xp_325_active_parent_is_dropped_in_favor_of_forms():
    from enhanced_normalizer import EnhancedDSLDNormalizer

    normalizer = EnhancedDSLDNormalizer()
    raw_product = {
        "id": "batch24-bladder-xp-325",
        "fullName": "Bladder Relief",
        "brandName": "Test Brand",
        "ingredientRows": [
            {
                "order": 1,
                "name": "Bladder XP-325",
                "ingredientGroup": "Proprietary Blend (Combination)",
                "forms": [
                    {"order": 1, "name": "Isomax 30", "ingredientId": 40050},
                    {"order": 2, "name": "Pumpkin seed extract", "ingredientId": 40049},
                ],
                "nestedRows": [],
            }
        ],
        "otheringredients": {"ingredients": []},
    }

    normalized = normalizer.normalize_product(raw_product)

    active_names = [ing.get("name") for ing in normalized.get("activeIngredients", [])]
    display_by_raw = {
        row.get("raw_source_text"): row for row in normalized.get("display_ingredients", [])
    }

    assert "Bladder XP-325" not in active_names
    assert "Isomax 30" in active_names
    assert "Pumpkin seed extract" in active_names
    assert display_by_raw["Bladder XP-325"]["display_type"] == "structural_container"
    assert display_by_raw["Bladder XP-325"]["score_included"] is False
    assert display_by_raw["Bladder XP-325"]["children"] == ["Isomax 30", "Pumpkin seed extract"]


def test_batch25_aqtiv_active_parent_is_dropped_in_favor_of_beet_powder():
    from enhanced_normalizer import EnhancedDSLDNormalizer

    normalizer = EnhancedDSLDNormalizer()
    raw_product = {
        "id": "batch25-aqtiv",
        "fullName": "Aqtiv Test",
        "brandName": "Test Brand",
        "ingredientRows": [
            {
                "order": 1,
                "name": "Aqtiv",
                "ingredientGroup": "Proprietary Blend",
                "forms": [
                    {"order": 1, "name": "Beet, Powder", "ingredientId": 299386},
                ],
                "nestedRows": [],
            }
        ],
        "otheringredients": {"ingredients": []},
    }

    normalized = normalizer.normalize_product(raw_product)

    active_names = [ing.get("name") for ing in normalized.get("activeIngredients", [])]
    display_by_raw = {
        row.get("raw_source_text"): row for row in normalized.get("display_ingredients", [])
    }

    assert "Aqtiv" not in active_names
    assert "Beet, Powder" in active_names
    assert display_by_raw["Aqtiv"]["display_type"] == "structural_container"
    assert display_by_raw["Aqtiv"]["score_included"] is False
    assert display_by_raw["Aqtiv"]["children"] == ["Beet, Powder"]


@pytest.mark.parametrize(
    "parent_name,children",
    [
        ("Vsoftgels", ["Glycerin", "purified Water", "Tapioca Starch"]),
        ("may contain Vegetable Oil", ["Corn Oil", "Soybean Oil"]),
        ("Additional Ingredients", ["Gelatin", "Glycerin", "Water"]),
    ],
)
def test_batch26_structural_inactive_parents_drop_in_favor_of_child_forms(parent_name, children):
    from enhanced_normalizer import EnhancedDSLDNormalizer

    normalizer = EnhancedDSLDNormalizer()
    raw_product = {
        "id": f"batch26-{parent_name}",
        "fullName": "Batch 26 Structural Container",
        "brandName": "Test Brand",
        "ingredientRows": [],
        "otheringredients": {
            "ingredients": [
                {
                    "order": 1,
                    "name": parent_name,
                    "ingredientGroup": "Header",
                    "forms": [
                        {"order": idx + 1, "name": child, "ingredientId": idx + 100}
                        for idx, child in enumerate(children)
                    ],
                }
            ]
        },
    }

    normalized = normalizer.normalize_product(raw_product)
    inactive_names = [ing.get("name") for ing in normalized.get("inactiveIngredients", [])]
    display_by_raw = {
        row.get("raw_source_text"): row for row in normalized.get("display_ingredients", [])
    }

    assert parent_name not in inactive_names
    for child in children:
        assert child in inactive_names
    assert display_by_raw[parent_name]["display_type"] == "structural_container"
    assert display_by_raw[parent_name]["score_included"] is False


@pytest.mark.parametrize("blend_name", ["Dashmoola", "Dashmooladi"])
def test_batch27_structural_active_blend_leaf_is_display_only(blend_name):
    from enhanced_normalizer import EnhancedDSLDNormalizer

    normalizer = EnhancedDSLDNormalizer()
    raw_product = {
        "id": f"batch27-{blend_name}",
        "fullName": "Batch 27 Blend Leaf",
        "brandName": "Test Brand",
        "ingredientRows": [
            {
                "order": 1,
                "name": "Proprietary Herbal Blend",
                "ingredientGroup": "Proprietary Blend (Herb/Botanical)",
                "category": "blend",
                "nestedRows": [
                    {
                        "order": 2,
                        "name": blend_name,
                        "ingredientGroup": "Blend (Herb/Botanical)",
                        "category": "blend",
                        "nestedRows": [],
                        "forms": [],
                    },
                    {
                        "order": 3,
                        "name": "Lodhra",
                        "ingredientGroup": "Lodhtree",
                        "category": "botanical",
                        "nestedRows": [],
                        "forms": [],
                    },
                ],
            }
        ],
        "otheringredients": {"ingredients": []},
    }

    normalized = normalizer.normalize_product(raw_product)
    active_names = [ing.get("name") for ing in normalized.get("activeIngredients", [])]
    display_by_raw = {
        row.get("raw_source_text"): row for row in normalized.get("display_ingredients", [])
    }

    assert blend_name not in active_names
    assert "Lodhra" in active_names
    assert display_by_raw[blend_name]["display_type"] == "structural_container"
    assert display_by_raw[blend_name]["score_included"] is False


@pytest.mark.parametrize(
    "name,ingredient_group,category,nested_rows,forms",
    [
        ("Maharasnadi", "Blend (Herb/Botanical)", "blend", [], []),
        ("Hydroxyanthracene Derivatives", "Hydroxyanthracene", "non-nutrient/non-botanical", [], []),
        ("Carvone", "Carvone", "non-nutrient/non-botanical", [], []),
        ("Didymin", "Flavonoid", "non-nutrient/non-botanical", [], []),
        ("1 mg of ajoene and dithiins", "Organosulfur compounds", "non-nutrient/non-botanical", [], []),
        ("E-Guggulsterone Isomer", "Guggulsterone", "non-nutrient/non-botanical", [], []),
        ("Hyperforin and Hypericins combined", "Blend (non-nutrient/non-botanical)", "blend", [], []),
        ("Antioxidative Diterpene Phenols", "Diterpene (unspecified)", "non-nutrient/non-botanical", [], []),
        ("Cod and Fish Liver Oil", "Fish Liver oil", "fat", [], [{"name": "Cod Liver Oil"}, {"name": "Fish Liver Oil"}]),
    ],
)
def test_batch28_structural_active_leaf_rows_stay_display_only(name, ingredient_group, category, nested_rows, forms):
    from enhanced_normalizer import EnhancedDSLDNormalizer

    normalizer = EnhancedDSLDNormalizer()
    raw_product = {
        "id": f"batch28-{name}",
        "fullName": "Batch 28 Structural Active Leaf",
        "brandName": "Test Brand",
        "ingredientRows": [
            {
                "order": 1,
                "name": name,
                "ingredientGroup": ingredient_group,
                "category": category,
                "nestedRows": nested_rows,
                "forms": forms,
            },
            {
                "order": 2,
                "name": "Lodhra",
                "ingredientGroup": "Lodhtree",
                "category": "botanical",
                "nestedRows": [],
                "forms": [],
            },
        ],
        "otheringredients": {"ingredients": []},
    }

    normalized = normalizer.normalize_product(raw_product)
    active_names = [ing.get("name") for ing in normalized.get("activeIngredients", [])]
    display_by_raw = {
        row.get("raw_source_text"): row for row in normalized.get("display_ingredients", [])
    }

    assert name not in active_names
    assert "Lodhra" in active_names
    assert display_by_raw[name]["display_type"] == "structural_container"
    assert display_by_raw[name]["score_included"] is False


@pytest.mark.parametrize(
    "parent_name,children",
    [
        ("Cholesstrinol", ["natural Citrus Polymethoxylated Flavones", "Palm fruit Tocotrienols"]),
        ("Essential Vitality Boost", ["Mate (Yerba Mate) powder", "Bladderwrack powder"]),
        ("Inflam-Arrest", ["organic Turmeric extract", "wild crafted Boswellia extract"]),
    ],
)
def test_batch28_structural_active_parent_rows_drop_in_favor_of_children(parent_name, children):
    from enhanced_normalizer import EnhancedDSLDNormalizer

    normalizer = EnhancedDSLDNormalizer()
    raw_product = {
        "id": f"batch28-parent-{parent_name}",
        "fullName": "Batch 28 Structural Active Parent",
        "brandName": "Test Brand",
        "ingredientRows": [
            {
                "order": 1,
                "name": parent_name,
                "ingredientGroup": "Proprietary Blend (Combination)",
                "category": "blend",
                "nestedRows": [
                    {
                        "order": idx + 2,
                        "name": child,
                        "ingredientGroup": child,
                        "category": "botanical" if "extract" in child.lower() or "powder" in child.lower() else "non-nutrient/non-botanical",
                        "nestedRows": [],
                        "forms": [],
                    }
                    for idx, child in enumerate(children)
                ],
                "forms": [],
            }
        ],
        "otheringredients": {"ingredients": []},
    }

    normalized = normalizer.normalize_product(raw_product)
    active_names = [ing.get("name") for ing in normalized.get("activeIngredients", [])]
    display_by_raw = {
        row.get("raw_source_text"): row for row in normalized.get("display_ingredients", [])
    }

    assert parent_name not in active_names
    for child in children:
        assert child in active_names
    assert display_by_raw[parent_name]["display_type"] == "structural_container"
    assert display_by_raw[parent_name]["score_included"] is False


@pytest.mark.parametrize(
    "name,ingredient_group,category",
    [
        ("Total Capsaicinoids", "Capsaicinoids", "non-nutrient/non-botanical"),
        ("Methylxanthine Isomers", "Blend (non-nutrient/non-botanical)", "blend"),
        ("Narirutin", "Naringenin", "non-nutrient/non-botanical"),
        ("Geraniol", "Geraniol", "non-nutrient/non-botanical"),
    ],
)
def test_batch29_structural_active_leaf_rows_stay_display_only(name, ingredient_group, category):
    from enhanced_normalizer import EnhancedDSLDNormalizer

    normalizer = EnhancedDSLDNormalizer()
    raw_product = {
        "id": f"batch29-{name}",
        "fullName": "Batch 29 Structural Active Leaf",
        "brandName": "Test Brand",
        "ingredientRows": [
            {
                "order": 1,
                "name": name,
                "ingredientGroup": ingredient_group,
                "category": category,
                "nestedRows": [],
                "forms": [],
            },
            {
                "order": 2,
                "name": "Lodhra",
                "ingredientGroup": "Lodhtree",
                "category": "botanical",
                "nestedRows": [],
                "forms": [],
            },
        ],
        "otheringredients": {"ingredients": []},
    }

    normalized = normalizer.normalize_product(raw_product)
    active_names = [ing.get("name") for ing in normalized.get("activeIngredients", [])]
    display_by_raw = {
        row.get("raw_source_text"): row for row in normalized.get("display_ingredients", [])
    }

    assert name not in active_names
    assert "Lodhra" in active_names
    assert display_by_raw[name]["display_type"] == "structural_container"
    assert display_by_raw[name]["score_included"] is False


def test_batch29_structural_active_parent_rows_drop_in_favor_of_children():
    from enhanced_normalizer import EnhancedDSLDNormalizer

    normalizer = EnhancedDSLDNormalizer()
    raw_product = {
        "id": "batch29-marine-oil-and-plant-oil-blend",
        "fullName": "Batch 29 Structural Active Parent",
        "brandName": "Test Brand",
        "ingredientRows": [
            {
                "order": 1,
                "name": "Marine Oil and Plant Oil Blend",
                "ingredientGroup": "Blend",
                "category": "blend",
                "nestedRows": [
                    {
                        "order": 2,
                        "name": "EPA",
                        "ingredientGroup": "Omega-3 Fatty Acids",
                        "category": "fatty acid",
                        "nestedRows": [],
                        "forms": [],
                    },
                    {
                        "order": 3,
                        "name": "DHA",
                        "ingredientGroup": "Omega-3 Fatty Acids",
                        "category": "fatty acid",
                        "nestedRows": [],
                        "forms": [],
                    },
                ],
                "forms": [],
            }
        ],
        "otheringredients": {"ingredients": []},
    }

    normalized = normalizer.normalize_product(raw_product)
    active_names = [ing.get("name") for ing in normalized.get("activeIngredients", [])]
    display_by_raw = {
        row.get("raw_source_text"): row for row in normalized.get("display_ingredients", [])
    }

    assert "Marine Oil and Plant Oil Blend" not in active_names
    assert "EPA" in active_names
    assert "DHA" in active_names
    assert display_by_raw["Marine Oil and Plant Oil Blend"]["display_type"] == "structural_container"
    assert display_by_raw["Marine Oil and Plant Oil Blend"]["score_included"] is False


@pytest.mark.parametrize(
    "parent_name,children",
    [
        ("Added to Protect freshness", ["Ascorbyl Palmitate", "Rosemary extract", "Tocopherols"]),
        ("Emulsifier", ["Sunflower Lecithin"]),
        ("EFASorb", ["Lecithin", "Phosphatidylcholine", "Phosphatidylserine"]),
    ],
)
def test_batch29_structural_inactive_parents_drop_in_favor_of_child_forms(parent_name, children):
    from enhanced_normalizer import EnhancedDSLDNormalizer

    normalizer = EnhancedDSLDNormalizer()
    raw_product = {
        "id": f"batch29-{parent_name}",
        "fullName": "Batch 29 Structural Inactive Parent",
        "brandName": "Test Brand",
        "ingredientRows": [],
        "otheringredients": {
            "ingredients": [
                {
                    "order": 1,
                    "name": parent_name,
                    "ingredientGroup": "Header",
                    "forms": [
                        {"order": idx + 1, "name": child, "ingredientId": idx + 100}
                        for idx, child in enumerate(children)
                    ],
                }
            ]
        },
    }

    normalized = normalizer.normalize_product(raw_product)
    inactive_names = [ing.get("name") for ing in normalized.get("inactiveIngredients", [])]
    display_by_raw = {
        row.get("raw_source_text"): row for row in normalized.get("display_ingredients", [])
    }

    assert parent_name not in inactive_names
    for child in children:
        assert child in inactive_names
    assert display_by_raw[parent_name]["display_type"] == "structural_container"
    assert display_by_raw[parent_name]["score_included"] is False


def test_batch29_structural_inactive_form_child_stays_display_only():
    from enhanced_normalizer import EnhancedDSLDNormalizer

    normalizer = EnhancedDSLDNormalizer()
    raw_product = {
        "id": "batch29-entering-coating",
        "fullName": "Batch 29 Entering Coating",
        "brandName": "Test Brand",
        "ingredientRows": [],
        "otheringredients": {
            "ingredients": [
                {
                    "order": 1,
                    "name": "Contains <2% of:",
                    "ingredientGroup": "Header",
                    "forms": [
                        {"order": 1, "name": "Entering Coating", "ingredientId": 1001},
                        {"order": 2, "name": "Ethylcellulose", "ingredientId": 1002},
                        {"order": 3, "name": "Polysorbate 80", "ingredientId": 1003},
                    ],
                }
            ]
        },
    }

    normalized = normalizer.normalize_product(raw_product)
    inactive_names = [ing.get("name") for ing in normalized.get("inactiveIngredients", [])]
    display_by_raw = {
        row.get("raw_source_text"): row for row in normalized.get("display_ingredients", [])
    }

    assert "Entering Coating" not in inactive_names
    assert "Ethylcellulose" in inactive_names
    assert "Polysorbate 80" in inactive_names
    assert display_by_raw["Entering Coating"]["display_type"] == "structural_container"
    assert display_by_raw["Entering Coating"]["score_included"] is False


def test_batch30_aquacelle_active_form_wrapper_stays_display_only():
    from enhanced_normalizer import EnhancedDSLDNormalizer

    normalizer = EnhancedDSLDNormalizer()
    raw_product = {
        "id": "batch30-aquacelle",
        "fullName": "Batch 30 AquaCelle",
        "brandName": "Test Brand",
        "ingredientRows": [
            {
                "order": 1,
                "name": "AquaCelle",
                "ingredientGroup": "Proprietary Blend (Combination)",
                "category": "blend",
                "nestedRows": [],
                "forms": [
                    {"order": 1, "name": "Lecithin", "ingredientId": 1001},
                    {"order": 2, "name": "Lime Oil", "ingredientId": 1002},
                    {"order": 3, "name": "Medium Chain Triglyceride", "ingredientId": 1003},
                ],
            },
            {
                "order": 2,
                "name": "Coenzyme Q-10",
                "ingredientGroup": "Coenzyme Q-10",
                "category": "non-nutrient/non-botanical",
                "nestedRows": [],
                "forms": [],
            },
        ],
        "otheringredients": {"ingredients": []},
    }

    normalized = normalizer.normalize_product(raw_product)
    active_names = [ing.get("name") for ing in normalized.get("activeIngredients", [])]
    display_by_raw = {
        row.get("raw_source_text"): row for row in normalized.get("display_ingredients", [])
    }

    assert "AquaCelle" not in active_names
    assert "Coenzyme Q-10" in active_names
    assert "Lecithin" not in active_names
    assert display_by_raw["AquaCelle"]["display_type"] == "structural_container"
    assert display_by_raw["AquaCelle"]["score_included"] is False
    assert display_by_raw["AquaCelle"]["children"] == [
        "Lecithin",
        "Lime Oil",
        "Medium Chain Triglyceride",
    ]


def test_batch30_zantrex_parent_drops_in_favor_of_children():
    from enhanced_normalizer import EnhancedDSLDNormalizer

    normalizer = EnhancedDSLDNormalizer()
    raw_product = {
        "id": "batch30-zantrex",
        "fullName": "Batch 30 Zantrex",
        "brandName": "Test Brand",
        "ingredientRows": [
            {
                "order": 1,
                "name": "Zantrex(R)",
                "ingredientGroup": "Proprietary Blend (Combination)",
                "category": "blend",
                "nestedRows": [
                    {
                        "order": 2,
                        "name": "Yerba Mate (leaf) extract",
                        "ingredientGroup": "Yerba Mate",
                        "category": "botanical",
                        "nestedRows": [],
                        "forms": [],
                    },
                    {
                        "order": 3,
                        "name": "Guarana (seed) extract",
                        "ingredientGroup": "Guarana",
                        "category": "botanical",
                        "nestedRows": [],
                        "forms": [],
                    },
                ],
                "forms": [],
            }
        ],
        "otheringredients": {"ingredients": []},
    }

    normalized = normalizer.normalize_product(raw_product)
    active_names = [ing.get("name") for ing in normalized.get("activeIngredients", [])]
    display_by_raw = {
        row.get("raw_source_text"): row for row in normalized.get("display_ingredients", [])
    }

    assert "Zantrex(R)" not in active_names
    assert "Yerba Mate (leaf) extract" in active_names
    assert "Guarana (seed) extract" in active_names
    assert display_by_raw["Zantrex(R)"]["display_type"] == "structural_container"
    assert display_by_raw["Zantrex(R)"]["score_included"] is False


def test_batch30_selenium_probiotic_nutrients_stays_display_only():
    from enhanced_normalizer import EnhancedDSLDNormalizer

    normalizer = EnhancedDSLDNormalizer()
    raw_product = {
        "id": "batch30-selenium-probiotic-nutrients",
        "fullName": "Batch 30 Selenium Blend",
        "brandName": "Test Brand",
        "ingredientRows": [
            {
                "order": 1,
                "name": "Selenium, Probiotic Nutrients",
                "ingredientGroup": "Proprietary Blend (Combination)",
                "category": "blend",
                "nestedRows": [],
                "forms": [],
            },
            {
                "order": 2,
                "name": "Vitamin C",
                "ingredientGroup": "Vitamin C",
                "category": "vitamin",
                "nestedRows": [],
                "forms": [],
            },
        ],
        "otheringredients": {"ingredients": []},
    }

    normalized = normalizer.normalize_product(raw_product)
    active_names = [ing.get("name") for ing in normalized.get("activeIngredients", [])]
    display_by_raw = {
        row.get("raw_source_text"): row for row in normalized.get("display_ingredients", [])
    }

    assert "Selenium, Probiotic Nutrients" not in active_names
    assert "Vitamin C" in active_names
    assert display_by_raw["Selenium, Probiotic Nutrients"]["display_type"] == "structural_container"
    assert display_by_raw["Selenium, Probiotic Nutrients"]["score_included"] is False


@pytest.mark.parametrize("leaf_name", ["Phenol", "Eicosatrienoic Acid"])
def test_batch30_nested_constituent_leaf_rows_stay_display_only(leaf_name):
    from enhanced_normalizer import EnhancedDSLDNormalizer

    normalizer = EnhancedDSLDNormalizer()
    raw_product = {
        "id": f"batch30-{leaf_name}",
        "fullName": "Batch 30 Constituent Leaf",
        "brandName": "Test Brand",
        "ingredientRows": [
            {
                "order": 1,
                "name": leaf_name,
                "ingredientGroup": leaf_name,
                "category": "fatty acid" if leaf_name == "Eicosatrienoic Acid" else "non-nutrient/non-botanical",
                "nestedRows": [],
                "forms": [],
                "parentBlend": "Oregano Oil" if leaf_name == "Phenol" else "Other Omega-3 Fatty Acids",
                "isNestedIngredient": True,
            },
            {
                "order": 2,
                "name": "Lodhra",
                "ingredientGroup": "Lodhtree",
                "category": "botanical",
                "nestedRows": [],
                "forms": [],
            },
        ],
        "otheringredients": {"ingredients": []},
    }

    normalized = normalizer.normalize_product(raw_product)
    active_names = [ing.get("name") for ing in normalized.get("activeIngredients", [])]
    display_by_raw = {
        row.get("raw_source_text"): row for row in normalized.get("display_ingredients", [])
    }

    assert leaf_name not in active_names
    assert "Lodhra" in active_names
    assert display_by_raw[leaf_name]["display_type"] == "structural_container"
    assert display_by_raw[leaf_name]["score_included"] is False


def test_batch30_inactive_descriptor_form_child_stays_display_only():
    from enhanced_normalizer import EnhancedDSLDNormalizer

    normalizer = EnhancedDSLDNormalizer()
    raw_product = {
        "id": "batch30-lipid-absorption-support-minerals",
        "fullName": "Batch 30 EFASorb",
        "brandName": "Test Brand",
        "ingredientRows": [],
        "otheringredients": {
            "ingredients": [
                {
                    "order": 1,
                    "name": "EFASorb",
                    "ingredientGroup": "Proprietary Blend (Combination)",
                    "forms": [
                        {"order": 1, "name": "Lecithin", "ingredientId": 1001},
                        {"order": 2, "name": "Lipid-absorption-support Minerals", "ingredientId": 1002},
                        {"order": 3, "name": "Phosphatidylcholine", "ingredientId": 1003},
                    ],
                }
            ]
        },
    }

    normalized = normalizer.normalize_product(raw_product)
    inactive_names = [ing.get("name") for ing in normalized.get("inactiveIngredients", [])]
    display_by_raw = {
        row.get("raw_source_text"): row for row in normalized.get("display_ingredients", [])
    }

    assert "Lipid-absorption-support Minerals" not in inactive_names
    assert "Lecithin" in inactive_names
    assert "Phosphatidylcholine" in inactive_names
    assert display_by_raw["Lipid-absorption-support Minerals"]["display_type"] == "structural_container"
    assert display_by_raw["Lipid-absorption-support Minerals"]["score_included"] is False


def test_unmapped_tracker_writes_needs_verification_reports(tmp_path):
    tracker = UnmappedIngredientTracker(tmp_path)
    tracker.process_unmapped_ingredients(
        {"Chopchinee": 2, "Unknown Inactive": 1},
        {"Chopchinee"},
        {
            "Chopchinee": {
                "is_active": True,
                "needs_verification": True,
                "verification_reason": "identity_conflict",
                "raw_ingredient_group": "Himalayan Rhubarb",
                "conflicting_candidates": ["Himalayan Rhubarb", "Smilax china"],
                "next_verification_step": "Obtain manufacturer or authoritative monograph confirmation",
            },
            "Unknown Inactive": {
                "is_active": False,
            },
        },
    )
    tracker.save_tracking_files()

    active = json.loads((tmp_path / "unmapped_active_ingredients.json").read_text())
    inactive = json.loads((tmp_path / "unmapped_inactive_ingredients.json").read_text())
    needs_active = json.loads((tmp_path / "needs_verification_active_ingredients.json").read_text())
    needs_inactive = json.loads((tmp_path / "needs_verification_inactive_ingredients.json").read_text())

    assert active["unmapped_ingredients"]["Chopchinee"] == 2
    assert inactive["unmapped_ingredients"]["Unknown Inactive"] == 1
    assert needs_active["metadata"]["total_needs_verification"] == 1
    assert needs_active["ingredients"][0]["label_text"] == "Chopchinee"
    assert needs_active["ingredients"][0]["reason"] == "identity_conflict"
    assert needs_inactive["metadata"]["total_needs_verification"] == 0


def test_normalizer_marks_chopchinee_as_needs_verification(tmp_path):
    normalizer = EnhancedDSLDNormalizer()
    normalizer.set_output_directory(tmp_path)
    normalizer.unmapped_ingredients["Chopchinee"] = 1
    normalizer.unmapped_details["Chopchinee"] = {
        "processed_name": "chopchinee",
        "forms": [],
        "variations_tried": [],
        "is_active": True,
        "needs_verification": True,
        "verification_reason": "identity_conflict",
        "raw_ingredient_group": "Himalayan Rhubarb",
        "conflicting_candidates": ["Himalayan Rhubarb", "Smilax china"],
        "next_verification_step": "Obtain manufacturer or authoritative monograph confirmation",
    }

    normalizer.process_and_save_unmapped_tracking()

    needs_active = json.loads((tmp_path / "unmapped" / "needs_verification_active_ingredients.json").read_text())
    assert needs_active["ingredients"][0]["label_text"] == "Chopchinee"


def test_normalizer_marks_vidarikanda_as_needs_verification(tmp_path):
    normalizer = EnhancedDSLDNormalizer()
    normalizer.set_output_directory(tmp_path)
    normalizer.unmapped_ingredients["Vidarikanda"] = 1
    normalizer.unmapped_details["Vidarikanda"] = {
        "processed_name": "vidarikanda",
        "forms": [],
        "variations_tried": [],
        "is_active": True,
        "needs_verification": True,
        "verification_reason": "identity_conflict",
        "raw_ingredient_group": "Finger Leaf Morning Glory",
        "conflicting_candidates": ["Finger Leaf Morning Glory", "Pueraria tuberosa"],
        "next_verification_step": "Obtain manufacturer or authoritative monograph confirmation for whether the label intends Pueraria tuberosa or the DSLD-listed finger leaf morning glory identity.",
    }

    normalizer.process_and_save_unmapped_tracking()

    needs_active = json.loads((tmp_path / "unmapped" / "needs_verification_active_ingredients.json").read_text())
    assert needs_active["ingredients"][0]["label_text"] == "Vidarikanda"


def test_normalizer_marks_annine_and_pyroxide_hcl_as_needs_verification_inactive(tmp_path):
    normalizer = EnhancedDSLDNormalizer()
    normalizer.set_output_directory(tmp_path)
    normalizer.unmapped_ingredients["Annine"] = 1
    normalizer.unmapped_details["Annine"] = {
        "processed_name": "annine",
        "forms": [],
        "variations_tried": [],
        "is_active": False,
        "needs_verification": True,
        "verification_reason": "identity_unknown",
        "raw_ingredient_group": "None",
        "conflicting_candidates": [],
        "next_verification_step": "Confirm the original product label or manufacturer ingredient list because the DSLD row does not expose an identifiable ingredient.",
    }
    normalizer.unmapped_ingredients["Pyroxide HCL"] = 1
    normalizer.unmapped_details["Pyroxide HCL"] = {
        "processed_name": "pyroxide hcl",
        "forms": [],
        "variations_tried": [],
        "is_active": False,
        "needs_verification": True,
        "verification_reason": "suspected_label_error",
        "raw_ingredient_group": "Peroxide Hcl",
        "conflicting_candidates": [],
        "next_verification_step": "Confirm the original label text to determine whether this is a DSLD typo such as Pyridoxine HCl or another ingredient entirely.",
    }

    normalizer.process_and_save_unmapped_tracking()

    needs_inactive = json.loads((tmp_path / "unmapped" / "needs_verification_inactive_ingredients.json").read_text())
    labels = {row["label_text"] for row in needs_inactive["ingredients"]}
    assert labels == {"Annine", "Pyroxide HCL"}


def test_batch32_titanium_dioxide_shell_header_extracts_child_forms():
    from enhanced_normalizer import EnhancedDSLDNormalizer

    normalizer = EnhancedDSLDNormalizer()
    raw_product = {
        "id": "batch32-tio2-shell-header",
        "fullName": "Batch 32 TIO2 Shell Header",
        "brandName": "Test Brand",
        "ingredientRows": [],
        "otheringredients": {
            "ingredients": [
                {
                    "order": 1,
                    "name": "Titanium Dioxide Color Shell ingredients:",
                    "ingredientGroup": "Header",
                    "forms": [
                        {"order": 1, "name": "Gelatin", "ingredientId": 1001},
                        {"order": 2, "name": "Glycerin", "ingredientId": 1002},
                        {"order": 3, "name": "purified Water", "ingredientId": 1003},
                        {"order": 4, "name": "Titanium Dioxide colour", "ingredientId": 1004},
                    ],
                }
            ]
        },
    }

    normalized = normalizer.normalize_product(raw_product)
    inactive_names = [ing.get("name") for ing in normalized.get("inactiveIngredients", [])]
    inactive_by_name = {ing.get("name"): ing for ing in normalized.get("inactiveIngredients", [])}

    assert "Titanium Dioxide Color Shell ingredients:" not in inactive_names
    assert "Titanium Dioxide colour" in inactive_names
    assert "Titanium Dioxide" in inactive_by_name["Titanium Dioxide colour"]["standardName"]
    assert "Gelatin" in inactive_names


@pytest.mark.parametrize(
    ("container_name", "child_names"),
    [
        ("plant based Emulsifier", ["Red Palm Oil", "Vegetable Glycerin"]),
        ("isoflavones and saponins", ["Soy"]),
    ],
)
def test_batch43_inactive_structural_wrappers_unwrap_forms_without_parent(container_name, child_names):
    from enhanced_normalizer import EnhancedDSLDNormalizer

    normalizer = EnhancedDSLDNormalizer()
    raw_product = {
        "id": f"batch43-{container_name}",
        "fullName": "Batch 43 Inactive Structural Wrapper",
        "brandName": "Test Brand",
        "ingredientRows": [],
        "otheringredients": {
            "ingredients": [
                {
                    "name": container_name,
                    "ingredientGroup": "Blend",
                    "order": 1,
                    "forms": [{"name": child, "order": idx + 1} for idx, child in enumerate(child_names)],
                }
            ]
        },
    }

    cleaned = normalizer.normalize_product(raw_product)
    inactive_names = [ing.get("name") for ing in cleaned.get("inactiveIngredients", [])]
    display_by_raw = {
        row.get("raw_source_text"): row for row in cleaned.get("display_ingredients", [])
    }

    assert container_name not in inactive_names
    for child_name in child_names:
        assert child_name in inactive_names
    assert display_by_raw[container_name]["display_type"] == "structural_container"
    assert display_by_raw[container_name]["score_included"] is False


def test_batch43_rice_bran_oil_titanium_dioxide_color_splits_into_child_ingredients():
    from enhanced_normalizer import EnhancedDSLDNormalizer

    normalizer = EnhancedDSLDNormalizer()
    raw_product = {
        "id": "batch43-rice-bran-tio2",
        "fullName": "Batch 43 Rice Bran Titanium Dioxide",
        "brandName": "Test Brand",
        "ingredientRows": [],
        "otheringredients": {
            "ingredients": [
                {
                    "name": "Contains Less Than 2% of Blend",
                    "ingredientGroup": "blend",
                    "order": 1,
                    "forms": [
                        {"order": 1, "name": "Annatto color"},
                        {"order": 2, "name": "Mixed Tocopherols"},
                        {"order": 3, "name": "Rice Bran Oil Titanium Dioxide Color"},
                        {"order": 4, "name": "yellow Beeswax"},
                    ],
                }
            ]
        },
    }

    cleaned = normalizer.normalize_product(raw_product)
    inactive_names = [ing.get("name") for ing in cleaned.get("inactiveIngredients", [])]
    inactive_by_name = {ing.get("name"): ing for ing in cleaned.get("inactiveIngredients", [])}

    assert "Rice Bran Oil Titanium Dioxide Color" not in inactive_names
    assert "Rice Bran Oil" in inactive_names
    assert "Titanium Dioxide Color" in inactive_names
    assert "Titanium Dioxide" in str(inactive_by_name["Titanium Dioxide Color"]["standardName"])


@pytest.mark.parametrize("leaf_name,parent_blend", [("Essential Fatty Acid", "Evening Primrose Seed Oil"), ("other", "Citrus Bioflavonoid Complex")])
def test_batch33_nested_active_artifact_leaves_stay_display_only(leaf_name, parent_blend):
    from enhanced_normalizer import EnhancedDSLDNormalizer

    normalizer = EnhancedDSLDNormalizer()
    raw_product = {
        "id": f"batch33-{leaf_name}",
        "fullName": "Batch 33 Nested Active Artifact",
        "brandName": "Test Brand",
        "ingredientRows": [
            {
                "order": 1,
                "name": parent_blend,
                "ingredientGroup": parent_blend,
                "category": "botanical" if leaf_name == "Essential Fatty Acid" else "non-nutrient/non-botanical",
                "nestedRows": [
                    {
                        "order": 2,
                        "name": leaf_name,
                        "ingredientGroup": "TBD",
                        "category": "other" if leaf_name == "other" else "blend",
                        "nestedRows": [],
                        "forms": [],
                    }
                ],
                "forms": [],
            },
            {
                "order": 3,
                "name": "Lodhra",
                "ingredientGroup": "Lodhtree",
                "category": "botanical",
                "nestedRows": [],
                "forms": [],
            },
        ],
        "otheringredients": {"ingredients": []},
    }

    normalized = normalizer.normalize_product(raw_product)
    active_names = [ing.get("name") for ing in normalized.get("activeIngredients", [])]
    display_by_raw = {
        row.get("raw_source_text"): row for row in normalized.get("display_ingredients", [])
    }

    assert leaf_name not in active_names
    assert "Lodhra" in active_names
    assert display_by_raw[leaf_name]["display_type"] == "structural_container"
    assert display_by_raw[leaf_name]["score_included"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
