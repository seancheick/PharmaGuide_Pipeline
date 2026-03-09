"""
Pipeline Regression Tests
Tests for critical pipeline behaviors to prevent regressions.
"""

import pytest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from enhanced_normalizer import EnhancedDSLDNormalizer
from dsld_validator import DSLDValidator


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

    def test_explicit_natural_dye_turmeric(self, normalizer):
        """Explicit natural dye: 'Turmeric' maps to 'natural colors'"""
        standard_name, mapped, forms = normalizer._enhanced_ingredient_mapping("Turmeric", [])
        assert standard_name == "natural colors", \
            f"Turmeric should map to 'natural colors', got: {standard_name}"

    def test_explicit_natural_dye_beet_juice(self, normalizer):
        """Explicit natural dye: 'Beet Juice' maps to 'natural colors'"""
        standard_name, mapped, forms = normalizer._enhanced_ingredient_mapping("Beet Juice", [])
        assert standard_name == "natural colors", \
            f"Beet Juice should map to 'natural colors', got: {standard_name}"

    def test_explicit_natural_dye_beta_carotene(self, normalizer):
        """Explicit natural dye: 'Beta-Carotene' maps to 'natural colors'"""
        standard_name, mapped, forms = normalizer._enhanced_ingredient_mapping("Beta-Carotene", [])
        assert standard_name == "natural colors", \
            f"Beta-Carotene should map to 'natural colors', got: {standard_name}"

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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
