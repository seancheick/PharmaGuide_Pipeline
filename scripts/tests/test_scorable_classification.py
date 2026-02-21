"""
Tests for Two-Pass Scorable Ingredient Classification System

This test module verifies the correct behavior of the enrichment system's
two-pass classification that separates:
- Scorable therapeutic actives (map + quality-score)
- Non-scorable label rows / excipients / headers (skip from quality scoring)

Test scenarios per spec:
1. Nested sorbitol/xylitol under "Total Carbohydrates" (isAdditive=true) -> skipped
2. Real botanical with dose (Elderberry) -> scorable
3. Header row "Proprietary Blend" without dose -> skipped
4. "Complex" ingredient WITH dose -> NOT skipped (scorable)
5. high_unmapped_ratio uses scorable-only denominator
6. Skipped rows still available for safety/additive checks
"""

import pytest
import sys
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from enrich_supplements_v3 import SupplementEnricherV3
from constants import (
    SKIP_REASON_ADDITIVE,
    SKIP_REASON_ADDITIVE_TYPE,
    SKIP_REASON_RECOGNIZED_NON_SCORABLE,
    SKIP_REASON_NESTED_NON_THERAPEUTIC,
    SKIP_REASON_BLEND_HEADER_NO_DOSE,
    SKIP_REASON_BLEND_HEADER_WITH_WEIGHT,
    SKIP_REASON_LABEL_PHRASE,
    SKIP_REASON_NUTRITION_FACT,
    PROMOTE_REASON_ABSORPTION_ENHANCER,
)


@pytest.fixture
def enricher():
    """Create enricher instance for testing."""
    return SupplementEnricherV3()


@pytest.fixture
def fixture_product_with_additives():
    """
    Fixture product containing:
    1. Nested sorbitol/xylitol under "Total Carbohydrates" (isAdditive=true, isNestedIngredient=true)
    2. Real botanical with dose (Elderberry)
    3. Header row "Proprietary Blend" without dose
    4. "Complex" ingredient with dose (must NOT be skipped)
    """
    return {
        "id": "test_fixture_001",
        "fullName": "Test Lozenge with Mixed Ingredients",
        "brandName": "Test Brand",
        "activeIngredients": [
            # 1. Nested additive under non-therapeutic parent - SHOULD BE SKIPPED
            {
                "name": "Sorbitol",
                "standardName": "sorbitol",
                "quantity": 2.0,
                "unit": "g",
                "isAdditive": True,
                "additiveType": "sugar_alcohol",
                "isNestedIngredient": True,
                "parentBlend": "Total Carbohydrates",
                "hierarchyType": None
            },
            # 2. Another additive - SHOULD BE SKIPPED
            {
                "name": "Xylitol",
                "standardName": "xylitol",
                "quantity": 1.0,
                "unit": "g",
                "isAdditive": True,
                "additiveType": "sugar_alcohol",
                "isNestedIngredient": True,
                "parentBlend": "Total Carbohydrates",
                "hierarchyType": None
            },
            # 3. Real botanical with dose - SHOULD BE SCORABLE
            {
                "name": "Elderberry Extract",
                "standardName": "Sambucus nigra",
                "quantity": 200.0,
                "unit": "mg",
                "isAdditive": False,
                "hierarchyType": None
            },
            # 4. Header row without dose - SHOULD BE SKIPPED
            {
                "name": "Proprietary Blend",
                "standardName": "Proprietary Blend",
                "quantity": None,
                "unit": None,
                "isAdditive": False,
                "hierarchyType": None
            },
            # 5. Complex with dose - SHOULD BE SCORABLE (not a header)
            {
                "name": "Vitamin B Complex",
                "standardName": "Vitamin B Complex",
                "quantity": 50.0,
                "unit": "mg",
                "isAdditive": False,
                "hierarchyType": None
            },
            # 6. Stevia (sweetener but NOT marked as additive) - tricky case
            # If isAdditive is not set but it's a known sweetener, behavior depends on DB
            {
                "name": "Stevia leaf extract",
                "standardName": "stevia",
                "quantity": 5.0,
                "unit": "mg",
                "isAdditive": False,  # Not marked, but it's clearly a sweetener
                "hierarchyType": None
            },
        ],
        "inactiveIngredients": [
            # Should NOT be promoted - common excipient
            {
                "name": "Natural Flavors",
                "standardName": "natural flavors",
                "isAdditive": True,
                "additiveType": "flavor"
            },
            # Could be promoted if it's in a botanical DB with dose
            {
                "name": "Ginger Root Extract",
                "standardName": "Zingiber officinale",
                "quantity": 50.0,
                "unit": "mg",
                "isAdditive": False
            },
        ]
    }


@pytest.fixture
def fixture_blend_only_product():
    """
    Fixture for a blend-only product where:
    - Only a "Proprietary Blend" header exists without components
    - scorable ingredients list should be empty or nearly empty
    - Should trigger blend_only_product flag
    """
    return {
        "id": "test_blend_only_001",
        "fullName": "Mystery Herbal Blend",
        "brandName": "Obscure Brand",
        "activeIngredients": [
            {
                "name": "Proprietary Herbal Blend",
                "standardName": "Proprietary Herbal Blend",
                "quantity": 500.0,  # Has total amount but no components
                "unit": "mg",
                "isAdditive": False,
                "hierarchyType": None
            },
            {
                "name": "Sorbitol",
                "standardName": "sorbitol",
                "quantity": 1.0,
                "unit": "g",
                "isAdditive": True,
                "additiveType": "sugar_alcohol",
                "isNestedIngredient": True,
                "parentBlend": "Total Carbohydrates",
            },
        ],
        "inactiveIngredients": []
    }


class TestScorableClassificationPass1:
    """Test Pass 1: Skip filters for activeIngredients"""

    def test_additive_is_skipped(self, enricher, fixture_product_with_additives):
        """Ingredients with isAdditive=true should be skipped from scoring."""
        result = enricher._collect_ingredient_quality_data(fixture_product_with_additives)

        skipped_names = [ing['name'] for ing in result['ingredients_skipped']]
        scorable_names = [ing['name'] for ing in result['ingredients_scorable']]

        assert "Sorbitol" in skipped_names, "Sorbitol should be skipped (isAdditive=true)"
        assert "Xylitol" in skipped_names, "Xylitol should be skipped (isAdditive=true)"
        assert "Sorbitol" not in scorable_names
        assert "Xylitol" not in scorable_names

    def test_skip_reason_is_recorded(self, enricher, fixture_product_with_additives):
        """Skipped ingredients should have skip_reason recorded."""
        result = enricher._collect_ingredient_quality_data(fixture_product_with_additives)

        skipped_dict = {ing['name']: ing for ing in result['ingredients_skipped']}

        # Sorbitol is recognized_non_scorable (checked before isAdditive)
        assert skipped_dict['Sorbitol']['skip_reason'] in (
            SKIP_REASON_ADDITIVE, SKIP_REASON_RECOGNIZED_NON_SCORABLE
        )

    def test_blend_header_without_dose_is_skipped(self, enricher, fixture_product_with_additives):
        """Header rows like 'Proprietary Blend' without dose should be skipped."""
        result = enricher._collect_ingredient_quality_data(fixture_product_with_additives)

        skipped_names = [ing['name'] for ing in result['ingredients_skipped']]
        assert "Proprietary Blend" in skipped_names

        skipped_dict = {ing['name']: ing for ing in result['ingredients_skipped']}
        assert skipped_dict['Proprietary Blend']['skip_reason'] == SKIP_REASON_BLEND_HEADER_NO_DOSE

    def test_complex_with_dose_is_not_skipped(self, enricher, fixture_product_with_additives):
        """'Complex' with a dose should NOT be skipped - it's a real ingredient."""
        result = enricher._collect_ingredient_quality_data(fixture_product_with_additives)

        scorable_names = [ing['name'] for ing in result['ingredients_scorable']]
        skipped_names = [ing['name'] for ing in result['ingredients_skipped']]

        assert "Vitamin B Complex" in scorable_names, "Vitamin B Complex with dose should be scorable"
        assert "Vitamin B Complex" not in skipped_names

    def test_botanical_with_dose_is_scorable(self, enricher, fixture_product_with_additives):
        """Real botanical with dose should be scorable."""
        result = enricher._collect_ingredient_quality_data(fixture_product_with_additives)

        scorable_names = [ing['name'] for ing in result['ingredients_scorable']]
        assert "Elderberry Extract" in scorable_names

    def test_botanical_from_standardized_db_is_scorable(self, enricher):
        """Botanical present only in standardized_botanicals should be scorable."""
        quality_db = enricher.databases.get('ingredient_quality_map', {})
        botanicals_db = enricher.databases.get('standardized_botanicals', {})

        if isinstance(botanicals_db, dict):
            botanicals_list = botanicals_db.get('standardized_botanicals', [])
        else:
            botanicals_list = botanicals_db

        if not isinstance(botanicals_list, list) or not botanicals_list:
            pytest.skip("No standardized botanicals list available")

        norm = enricher._normalize_text
        quality_names = set()
        for key, data in quality_db.items():
            if key.startswith('_') or not isinstance(data, dict):
                continue
            quality_names.add(norm(data.get('standard_name', key)))
            for alias in data.get('aliases', []) or []:
                quality_names.add(norm(alias))
            for form_name, form_data in (data.get('forms', {}) or {}).items():
                quality_names.add(norm(form_name))
                for alias in form_data.get('aliases', []) or []:
                    quality_names.add(norm(alias))

        candidate = None
        for botanical in botanicals_list:
            if not isinstance(botanical, dict):
                continue
            bot_name = norm(botanical.get('standard_name', ''))
            if not bot_name:
                continue
            if bot_name not in quality_names:
                candidate = botanical.get('standard_name')
                break

        if not candidate:
            pytest.skip("No botanical found outside ingredient_quality_map")

        product = {
            "id": "test_botanical_db_only",
            "fullName": "Test Botanical Only",
            "activeIngredients": [
                {
                    "name": candidate,
                    "standardName": candidate,
                    "quantity": 50.0,
                    "unit": "mg"
                }
            ],
            "inactiveIngredients": []
        }

        result = enricher._collect_ingredient_quality_data(product)
        scorable_names = [ing['name'] for ing in result['ingredients_scorable']]
        assert candidate in scorable_names


class TestScorableClassificationPass2:
    """Test Pass 2: Rescue therapeutic actives from inactiveIngredients"""

    def test_excipient_not_promoted(self, enricher, fixture_product_with_additives):
        """Common excipients should NOT be promoted from inactive."""
        result = enricher._collect_ingredient_quality_data(fixture_product_with_additives)

        promoted_names = [ing['name'] for ing in result['promoted_from_inactive']]
        assert "Natural Flavors" not in promoted_names


class TestScorableMetrics:
    """Test that unmapped metrics use scorable-only counts"""

    def test_unmapped_count_excludes_skipped(self, enricher, fixture_product_with_additives):
        """unmapped_scorable_count should not include skipped ingredients."""
        result = enricher._collect_ingredient_quality_data(fixture_product_with_additives)

        # Skipped ingredients should not contribute to unmapped count
        assert result['skipped_non_scorable_count'] >= 3  # At least Sorbitol, Xylitol, Proprietary Blend

        # Total active is all activeIngredients
        assert result['total_active'] == 6

        # Total scorable should be less than total active
        assert result['total_scorable_active_count'] < result['total_active']

    def test_skipped_reasons_breakdown(self, enricher, fixture_product_with_additives):
        """skipped_reasons_breakdown should count each reason."""
        result = enricher._collect_ingredient_quality_data(fixture_product_with_additives)

        breakdown = result['skipped_reasons_breakdown']
        assert (SKIP_REASON_ADDITIVE in breakdown
                or SKIP_REASON_ADDITIVE_TYPE in breakdown
                or SKIP_REASON_RECOGNIZED_NON_SCORABLE in breakdown)
        assert SKIP_REASON_BLEND_HEADER_NO_DOSE in breakdown


class TestBlendOnlyDetection:
    """Test blend-only product detection"""

    def test_blend_only_product_detected(self, enricher, fixture_blend_only_product):
        """Products with only blend headers and no real actives should be flagged."""
        result = enricher._collect_ingredient_quality_data(fixture_blend_only_product)

        # With the Proprietary Herbal Blend having a dose (500mg), it might not be skipped
        # But if total_scorable is very low and there are blend headers, blend_only_product
        # detection should still work
        assert 'blend_only_product' in result


class TestBackwardCompatibility:
    """Test that legacy fields are still populated for backward compatibility"""

    def test_legacy_fields_present(self, enricher, fixture_product_with_additives):
        """Legacy fields should still be populated."""
        result = enricher._collect_ingredient_quality_data(fixture_product_with_additives)

        # Legacy fields
        assert 'ingredients' in result
        assert 'unmapped_count' in result
        assert 'total_active' in result
        assert 'premium_form_count' in result

        # New fields
        assert 'ingredients_scorable' in result
        assert 'ingredients_skipped' in result
        assert 'unmapped_scorable_count' in result
        assert 'total_scorable_active_count' in result

    def test_legacy_ingredients_equals_scorable(self, enricher, fixture_product_with_additives):
        """Legacy 'ingredients' should contain same items as 'ingredients_scorable'."""
        result = enricher._collect_ingredient_quality_data(fixture_product_with_additives)

        # Legacy 'ingredients' should match 'ingredients_scorable' (plus any promoted)
        legacy_names = set(ing['name'] for ing in result['ingredients'])
        scorable_names = set(ing['name'] for ing in result['ingredients_scorable'])

        # They should be equal (promoted are added to both)
        assert legacy_names == scorable_names


class TestSafetyCheckPreservation:
    """Test that skipped ingredients are still available for safety checks"""

    def test_skipped_have_full_data(self, enricher, fixture_product_with_additives):
        """Skipped ingredients should retain their data for safety checks."""
        result = enricher._collect_ingredient_quality_data(fixture_product_with_additives)

        for skipped in result['ingredients_skipped']:
            assert 'name' in skipped
            assert 'standard_name' in skipped
            assert 'skip_reason' in skipped
            # Original source data available
            assert 'source_section' in skipped


class TestHighUnmappedRatioWithScorableOnly:
    """Test that high_unmapped_ratio uses scorable-only denominator"""

    def test_unmapped_ratio_calculation(self, enricher, fixture_product_with_additives):
        """Verify unmapped ratio is calculated using scorable counts only."""
        result = enricher._collect_ingredient_quality_data(fixture_product_with_additives)

        unmapped_scorable = result['unmapped_scorable_count']
        total_scorable = result['total_scorable_active_count']

        if total_scorable > 0:
            ratio = unmapped_scorable / total_scorable
            # This ratio should be based only on scorable ingredients,
            # not inflated by skipped excipients/headers
            assert ratio <= 1.0  # Can't exceed 100%


class TestHardeningBlendHeaderWithWeight:
    """Test Risk B: Blend headers with total weight should still be skipped"""

    def test_proprietary_blend_with_weight_is_skipped(self, enricher):
        """
        Blend headers with total weight (e.g., 'Proprietary Blend 500 mg')
        should be skipped from scoring - the weight is the total, not per-ingredient.
        """
        product = {
            "id": "test_blend_weight_001",
            "fullName": "Product with Weighted Blend Header",
            "activeIngredients": [
                {
                    "name": "Proprietary Blend",
                    "standardName": "Proprietary Blend",
                    "quantity": 500.0,  # Total blend weight
                    "unit": "mg",
                    "isAdditive": False,
                    "hierarchyType": None
                },
                # Nested components without individual doses
                {
                    "name": "Green Tea Extract",
                    "standardName": "Camellia sinensis",
                    "quantity": None,
                    "unit": None,
                    "isAdditive": False,
                    "isNestedIngredient": True,
                    "parentBlend": "Proprietary Blend"
                },
            ],
            "inactiveIngredients": []
        }

        result = enricher._collect_ingredient_quality_data(product)

        skipped_names = [ing['name'] for ing in result['ingredients_skipped']]
        skipped_dict = {ing['name']: ing for ing in result['ingredients_skipped']}

        # The blend header should be skipped even with weight
        assert "Proprietary Blend" in skipped_names
        assert skipped_dict['Proprietary Blend']['skip_reason'] in (
            SKIP_REASON_BLEND_HEADER_NO_DOSE,
            SKIP_REASON_BLEND_HEADER_WITH_WEIGHT
        )


class TestHardeningUnitGarbage:
    """Test Risk A: Unit garbage and pseudo-units should not count as valid dose"""

    def test_whitespace_unit_is_no_dose(self, enricher):
        """Unit with only whitespace should be treated as no dose."""
        product = {
            "id": "test_whitespace_unit",
            "fullName": "Product with Whitespace Unit",
            "activeIngredients": [
                {
                    "name": "Proprietary Formula",
                    "standardName": "Proprietary Formula",
                    "quantity": 2,
                    "unit": "   ",  # Whitespace only
                    "isAdditive": False,
                }
            ],
            "inactiveIngredients": []
        }

        result = enricher._collect_ingredient_quality_data(product)
        skipped_names = [ing['name'] for ing in result['ingredients_skipped']]

        # Should be skipped as blend header without valid dose
        assert "Proprietary Formula" in skipped_names

    def test_serving_unit_is_no_dose(self, enricher):
        """'serving' is a pseudo-unit, not a valid therapeutic dose unit."""
        product = {
            "id": "test_serving_unit",
            "fullName": "Product with Serving Unit",
            "activeIngredients": [
                {
                    "name": "Proprietary Matrix",
                    "standardName": "Proprietary Matrix",
                    "quantity": 1,
                    "unit": "serving",  # Pseudo-unit
                    "isAdditive": False,
                }
            ],
            "inactiveIngredients": []
        }

        result = enricher._collect_ingredient_quality_data(product)
        skipped_names = [ing['name'] for ing in result['ingredients_skipped']]

        # Should be skipped - "serving" is not a valid therapeutic unit
        assert "Proprietary Matrix" in skipped_names

    def test_na_unit_is_no_dose(self, enricher):
        """'n/a' unit should be treated as no dose."""
        product = {
            "id": "test_na_unit",
            "fullName": "Product with N/A Unit",
            "activeIngredients": [
                {
                    "name": "Proprietary Complex",
                    "standardName": "Proprietary Complex",
                    "quantity": 100,
                    "unit": "n/a",
                    "isAdditive": False,
                }
            ],
            "inactiveIngredients": []
        }

        result = enricher._collect_ingredient_quality_data(product)
        skipped_names = [ing['name'] for ing in result['ingredients_skipped']]

        assert "Proprietary Complex" in skipped_names


class TestHardeningInactiveSweetenerWithDose:
    """Test that inactive sweeteners with dose are NOT promoted"""

    def test_stevia_with_dose_not_promoted(self, enricher):
        """
        Stevia in inactive ingredients with dose should NOT be promoted.
        This tests the excipient never-promote list.
        """
        product = {
            "id": "test_stevia_not_promoted",
            "fullName": "Product with Stevia in Inactive",
            "activeIngredients": [
                {
                    "name": "Vitamin C",
                    "standardName": "Ascorbic Acid",
                    "quantity": 500.0,
                    "unit": "mg",
                    "isAdditive": False,
                }
            ],
            "inactiveIngredients": [
                {
                    "name": "Stevia leaf extract",
                    "standardName": "stevia",
                    "quantity": 10.0,  # Has dose
                    "unit": "mg",
                    "isAdditive": False  # Not marked as additive
                }
            ]
        }

        result = enricher._collect_ingredient_quality_data(product)

        promoted_names = [ing['name'] for ing in result['promoted_from_inactive']]
        scorable_names = [ing['name'] for ing in result['ingredients_scorable']]

        # Stevia should NOT be promoted even with dose
        assert "Stevia leaf extract" not in promoted_names
        assert "Stevia leaf extract" not in scorable_names


class TestHardeningCarrierOilsNotPromoted:
    """Test that carrier oils in EXCIPIENT_NEVER_PROMOTE are not promoted from inactive."""

    def test_sunflower_oil_with_dose_not_promoted(self, enricher):
        """
        Sunflower Oil in inactive ingredients should NOT be promoted,
        even if it has a dose. It's a carrier, not a therapeutic ingredient.
        """
        product = {
            "id": "test_sunflower_oil_not_promoted",
            "fullName": "Product with Sunflower Oil in Inactive",
            "activeIngredients": [
                {
                    "name": "Vitamin D3",
                    "standardName": "Cholecalciferol",
                    "quantity": 1000.0,
                    "unit": "IU",
                    "isAdditive": False,
                }
            ],
            "inactiveIngredients": [
                {
                    "name": "Sunflower Oil",
                    "standardName": "sunflower oil",
                    "quantity": 50.0,  # Has dose
                    "unit": "mg",
                    "isAdditive": False  # Not marked as additive
                }
            ]
        }

        result = enricher._collect_ingredient_quality_data(product)

        promoted_names = [ing['name'] for ing in result['promoted_from_inactive']]
        scorable_names = [ing['name'] for ing in result['ingredients_scorable']]

        # Sunflower Oil should NOT be promoted
        assert "Sunflower Oil" not in promoted_names, \
            "Sunflower Oil should NOT be promoted - it's a carrier oil"
        assert "Sunflower Oil" not in scorable_names, \
            "Sunflower Oil should NOT appear in scorable ingredients"

    def test_coconut_oil_with_dose_not_promoted(self, enricher):
        """Coconut Oil should NOT be promoted even with dose."""
        product = {
            "id": "test_coconut_oil_not_promoted",
            "fullName": "Product with Coconut Oil",
            "activeIngredients": [
                {
                    "name": "MCT",
                    "standardName": "Medium Chain Triglycerides",
                    "quantity": 1000.0,
                    "unit": "mg",
                    "isAdditive": False,
                }
            ],
            "inactiveIngredients": [
                {
                    "name": "Organic Coconut Oil",
                    "standardName": "coconut oil",
                    "quantity": 100.0,
                    "unit": "mg",
                    "isAdditive": False
                }
            ]
        }

        result = enricher._collect_ingredient_quality_data(product)
        promoted_names = [ing['name'] for ing in result['promoted_from_inactive']]

        assert "Organic Coconut Oil" not in promoted_names, \
            "Coconut Oil should NOT be promoted - it's a carrier oil"

    def test_olive_oil_not_promoted(self, enricher):
        """Olive Oil should NOT be promoted even with dose."""
        product = {
            "id": "test_olive_oil_not_promoted",
            "fullName": "Product with Olive Oil",
            "activeIngredients": [
                {
                    "name": "Vitamin E",
                    "standardName": "d-Alpha Tocopherol",
                    "quantity": 400.0,
                    "unit": "IU",
                    "isAdditive": False,
                }
            ],
            "inactiveIngredients": [
                {
                    "name": "Extra Virgin Olive Oil",
                    "standardName": "olive oil",
                    "quantity": 50.0,
                    "unit": "mg",
                    "isAdditive": False
                }
            ]
        }

        result = enricher._collect_ingredient_quality_data(product)
        promoted_names = [ing['name'] for ing in result['promoted_from_inactive']]

        assert "Extra Virgin Olive Oil" not in promoted_names

    def test_apple_cider_vinegar_not_promoted(self, enricher):
        """Apple Cider Vinegar should NOT be promoted - it's a food powder."""
        product = {
            "id": "test_acv_not_promoted",
            "fullName": "Product with ACV",
            "activeIngredients": [
                {
                    "name": "Vitamin B12",
                    "standardName": "Methylcobalamin",
                    "quantity": 1000.0,
                    "unit": "mcg",
                    "isAdditive": False,
                }
            ],
            "inactiveIngredients": [
                {
                    "name": "Apple Cider Vinegar",
                    "standardName": "apple cider vinegar",
                    "quantity": 500.0,
                    "unit": "mg",
                    "isAdditive": False
                }
            ]
        }

        result = enricher._collect_ingredient_quality_data(product)
        promoted_names = [ing['name'] for ing in result['promoted_from_inactive']]

        assert "Apple Cider Vinegar" not in promoted_names, \
            "Apple Cider Vinegar should NOT be promoted - it's a food powder"


class TestHardeningAbsorptionEnhancerWithoutDose:
    """Test Risk C: Absorption enhancers can be promoted even without dose"""

    def test_bioperine_without_dose_promoted(self, enricher):
        """
        BioPerine (black pepper extract) should be promoted from inactive
        even without explicit dose - it's a known absorption enhancer.
        """
        product = {
            "id": "test_bioperine_promoted",
            "fullName": "Product with BioPerine",
            "activeIngredients": [
                {
                    "name": "Turmeric Extract",
                    "standardName": "Curcuma longa",
                    "quantity": 500.0,
                    "unit": "mg",
                    "isAdditive": False,
                }
            ],
            "inactiveIngredients": [
                {
                    "name": "BioPerine® black pepper extract",
                    "standardName": "Piper nigrum",
                    "quantity": None,  # No dose specified
                    "unit": None,
                    "isAdditive": False
                }
            ]
        }

        result = enricher._collect_ingredient_quality_data(product)

        promoted = result['promoted_from_inactive']
        promoted_names = [ing['name'] for ing in promoted]

        # BioPerine should be promoted as absorption enhancer
        assert "BioPerine® black pepper extract" in promoted_names

        # Check promotion reason
        for promo in promoted:
            if promo['name'] == "BioPerine® black pepper extract":
                assert promo['promotion_reason'] == PROMOTE_REASON_ABSORPTION_ENHANCER
                break

    def test_plain_black_pepper_without_dose_promoted(self, enricher):
        """
        Plain 'black pepper extract' should also be promoted as absorption enhancer.
        """
        product = {
            "id": "test_pepper_promoted",
            "fullName": "Product with Black Pepper",
            "activeIngredients": [
                {
                    "name": "Curcumin",
                    "standardName": "Curcumin",
                    "quantity": 400.0,
                    "unit": "mg",
                    "isAdditive": False,
                }
            ],
            "inactiveIngredients": [
                {
                    "name": "Black pepper extract",
                    "standardName": "black pepper extract",
                    "quantity": None,
                    "unit": None,
                    "isAdditive": False
                }
            ]
        }

        result = enricher._collect_ingredient_quality_data(product)
        promoted_names = [ing['name'] for ing in result['promoted_from_inactive']]

        assert "Black pepper extract" in promoted_names


class TestHardeningAliasCollisions:
    """Test Risk D: Alias collision regression tests"""

    def test_pepper_not_confused_with_black_pepper(self, enricher):
        """
        'Pepper' alone should not match 'black pepper extract'.
        This tests that we use exact matching, not substring.
        """
        # This is more about ensuring our matching logic is exact
        # The absorption enhancer check should use exact or phrase matching

        product = {
            "id": "test_pepper_confusion",
            "fullName": "Product with Pepper",
            "activeIngredients": [
                {
                    "name": "Vitamin D3",
                    "standardName": "Cholecalciferol",
                    "quantity": 1000.0,
                    "unit": "IU",
                    "isAdditive": False,
                }
            ],
            "inactiveIngredients": [
                {
                    "name": "Pepper",  # Just "pepper", not "black pepper extract"
                    "standardName": "pepper",
                    "quantity": None,
                    "unit": None,
                    "isAdditive": False
                }
            ]
        }

        result = enricher._collect_ingredient_quality_data(product)
        promoted_names = [ing['name'] for ing in result['promoted_from_inactive']]

        # Plain "Pepper" should NOT be promoted as absorption enhancer
        # because it doesn't match the specific "black pepper extract" pattern
        assert "Pepper" not in promoted_names

    def test_ginger_flavor_not_confused_with_ginger_extract(self, enricher):
        """
        'Ginger flavor' should not be promoted as absorption enhancer.
        Only 'ginger extract' or 'ginger root extract' qualifies.
        """
        product = {
            "id": "test_ginger_confusion",
            "fullName": "Product with Ginger Flavor",
            "activeIngredients": [
                {
                    "name": "Zinc",
                    "standardName": "Zinc",
                    "quantity": 15.0,
                    "unit": "mg",
                    "isAdditive": False,
                }
            ],
            "inactiveIngredients": [
                {
                    "name": "Ginger flavor",
                    "standardName": "ginger flavor",
                    "quantity": None,
                    "unit": None,
                    "isAdditive": False
                }
            ]
        }

        result = enricher._collect_ingredient_quality_data(product)
        promoted_names = [ing['name'] for ing in result['promoted_from_inactive']]

        # Ginger flavor is a flavor, not an absorption enhancer
        assert "Ginger flavor" not in promoted_names


class TestScorableNamesNormalized:
    """Test the new scorable_ingredient_names_normalized output field"""

    def test_normalized_names_present(self, enricher, fixture_product_with_additives):
        """scorable_ingredient_names_normalized should be present in output."""
        result = enricher._collect_ingredient_quality_data(fixture_product_with_additives)

        assert 'scorable_ingredient_names_normalized' in result
        assert isinstance(result['scorable_ingredient_names_normalized'], list)

    def test_normalized_names_contains_scorable(self, enricher, fixture_product_with_additives):
        """Normalized names should include all scorable ingredients."""
        result = enricher._collect_ingredient_quality_data(fixture_product_with_additives)

        normalized_names = set(result['scorable_ingredient_names_normalized'])
        scorable_names = [ing['name'].lower().strip()
                         for ing in result['ingredients_scorable']]

        # Each scorable ingredient should have at least one normalized form present
        for name in scorable_names:
            # At least the lowercased name should be present
            assert any(name in norm or norm in name
                       for norm in normalized_names), \
                f"Expected {name} to have normalized form in output"


class TestBlendPatternCounterTests:
    """
    Counter-tests to ensure blend patterns don't create false positives.

    These tests verify that legitimate therapeutic ingredients WITH doses
    are NOT incorrectly skipped as blend headers, even if they contain
    words like "extract", "blend", "fruit", etc.
    """

    def test_omega3_with_dose_not_skipped_as_header(self, enricher):
        """Omega-3 (EPA/DHA) 1000 mg should be scorable, not a blend header."""
        product = {
            'dsld_id': 'test-omega',
            'fullName': 'Fish Oil Test',
            'activeIngredients': [
                {'name': 'Omega-3 (EPA/DHA)', 'quantity': 1000, 'unit': 'mg'}
            ],
            'otherIngredients': []
        }
        result = enricher._collect_ingredient_quality_data(product)
        scorable_names = [ing['name'] for ing in result['ingredients_scorable']]
        skipped_names = [ing['name'] for ing in result['ingredients_skipped']]

        assert 'Omega-3 (EPA/DHA)' in scorable_names
        assert 'Omega-3 (EPA/DHA)' not in skipped_names

    def test_elderberry_extract_with_dose_not_skipped(self, enricher):
        """Elderberry fruit extract 150 mg should be scorable."""
        product = {
            'dsld_id': 'test-elderberry',
            'fullName': 'Elderberry Test',
            'activeIngredients': [
                {'name': 'Elderberry fruit extract', 'quantity': 150, 'unit': 'mg'}
            ],
            'otherIngredients': []
        }
        result = enricher._collect_ingredient_quality_data(product)
        scorable_names = [ing['name'] for ing in result['ingredients_scorable']]

        assert 'Elderberry fruit extract' in scorable_names

    def test_chamomile_extract_with_dose_not_skipped(self, enricher):
        """Chamomile extract 50 mg should be scorable."""
        product = {
            'dsld_id': 'test-chamomile',
            'fullName': 'Chamomile Test',
            'activeIngredients': [
                {'name': 'Chamomile extract', 'quantity': 50, 'unit': 'mg'}
            ],
            'otherIngredients': []
        }
        result = enricher._collect_ingredient_quality_data(product)
        scorable_names = [ing['name'] for ing in result['ingredients_scorable']]

        assert 'Chamomile extract' in scorable_names

    def test_probiotic_without_blend_word_not_skipped(self, enricher):
        """Probiotic (L. rhamnosus GG) 10B CFU should be scorable."""
        product = {
            'dsld_id': 'test-probiotic',
            'fullName': 'Probiotic Test',
            'activeIngredients': [
                {'name': 'Probiotic (L. rhamnosus GG)', 'quantity': 10, 'unit': 'billion CFU'}
            ],
            'otherIngredients': []
        }
        result = enricher._collect_ingredient_quality_data(product)
        scorable_names = [ing['name'] for ing in result['ingredients_scorable']]

        assert 'Probiotic (L. rhamnosus GG)' in scorable_names

    def test_fish_oil_concentrate_with_dose_not_skipped(self, enricher):
        """Fish oil concentrate 1000 mg should be scorable."""
        product = {
            'dsld_id': 'test-fishoil',
            'fullName': 'Fish Oil Test',
            'activeIngredients': [
                {'name': 'Fish oil concentrate', 'quantity': 1000, 'unit': 'mg'}
            ],
            'otherIngredients': []
        }
        result = enricher._collect_ingredient_quality_data(product)
        scorable_names = [ing['name'] for ing in result['ingredients_scorable']]

        assert 'Fish oil concentrate' in scorable_names

    def test_omega3_blend_with_dose_scorable(self, enricher):
        """Omega-3 Blend (EPA/DHA) 1000 mg should be scorable, not skipped as header."""
        product = {
            'dsld_id': 'test-omega3-blend',
            'fullName': 'Omega-3 Blend Test',
            'activeIngredients': [
                {'name': 'Omega-3 Blend (EPA/DHA)', 'quantity': 1000, 'unit': 'mg'}
            ],
            'otherIngredients': []
        }
        result = enricher._collect_ingredient_quality_data(product)
        scorable_names = [ing['name'] for ing in result['ingredients_scorable']]
        skipped_names = [ing['name'] for ing in result['ingredients_skipped']]

        # Should be scorable because it has a therapeutic dose
        assert 'Omega-3 Blend (EPA/DHA)' in scorable_names
        assert 'Omega-3 Blend (EPA/DHA)' not in skipped_names

    def test_mixed_tocotrienols_complex_with_dose_scorable(self, enricher):
        """Mixed Tocotrienols (Tocotrienol Complex) 50 mg - realistic label."""
        product = {
            'dsld_id': 'test-tocotrienol-complex',
            'fullName': 'Tocotrienol Test',
            'activeIngredients': [
                {'name': 'Mixed Tocotrienols (Tocotrienol Complex)', 'quantity': 50, 'unit': 'mg'}
            ],
            'otherIngredients': []
        }
        result = enricher._collect_ingredient_quality_data(product)
        scorable_names = [ing['name'] for ing in result['ingredients_scorable']]
        skipped_names = [ing['name'] for ing in result['ingredients_skipped']]

        # Realistic label with dose should be scorable
        assert 'Mixed Tocotrienols (Tocotrienol Complex)' in scorable_names
        assert 'Mixed Tocotrienols (Tocotrienol Complex)' not in skipped_names

    def test_carotenoid_complex_with_dose_scorable(self, enricher):
        """Carotenoid Complex 10 mg - realistic label."""
        product = {
            'dsld_id': 'test-carotenoid-complex',
            'fullName': 'Carotenoid Test',
            'activeIngredients': [
                {'name': 'Carotenoid Complex', 'quantity': 10, 'unit': 'mg'}
            ],
            'otherIngredients': []
        }
        result = enricher._collect_ingredient_quality_data(product)
        scorable_names = [ing['name'] for ing in result['ingredients_scorable']]
        skipped_names = [ing['name'] for ing in result['ingredients_skipped']]

        assert 'Carotenoid Complex' in scorable_names
        assert 'Carotenoid Complex' not in skipped_names

    def test_phospholipid_complex_with_dose_scorable(self, enricher):
        """Phospholipid Complex 300 mg - realistic label."""
        product = {
            'dsld_id': 'test-phospholipid-complex',
            'fullName': 'Phospholipid Test',
            'activeIngredients': [
                {'name': 'Phospholipid Complex', 'quantity': 300, 'unit': 'mg'}
            ],
            'otherIngredients': []
        }
        result = enricher._collect_ingredient_quality_data(product)
        scorable_names = [ing['name'] for ing in result['ingredients_scorable']]
        skipped_names = [ing['name'] for ing in result['ingredients_skipped']]

        # Has specific dose, should be scorable
        assert 'Phospholipid Complex' in scorable_names
        assert 'Phospholipid Complex' not in skipped_names


class TestBlendPatternPositiveTests:
    """
    Positive tests to ensure blend headers WITHOUT doses ARE skipped.

    These verify that header-like names without therapeutic doses
    are correctly identified and skipped from quality scoring.
    """

    def test_superfood_immune_blend_no_dose_skipped(self, enricher):
        """Superfood / Immune Support Blend (no dose) should be skipped."""
        product = {
            'dsld_id': 'test-superfood',
            'fullName': 'Superfood Test',
            'activeIngredients': [
                {'name': 'Superfood / Immune Support Blend', 'quantity': None, 'unit': None},
                {'name': 'Vitamin C', 'quantity': 500, 'unit': 'mg'}
            ],
            'otherIngredients': []
        }
        result = enricher._collect_ingredient_quality_data(product)
        skipped_names = [ing['name'] for ing in result['ingredients_skipped']]
        scorable_names = [ing['name'] for ing in result['ingredients_scorable']]

        assert 'Superfood / Immune Support Blend' in skipped_names
        assert 'Vitamin C' in scorable_names

    def test_probiotic_strain_blend_no_dose_skipped(self, enricher):
        """Probiotic Strain Blend (no dose) should be skipped."""
        product = {
            'dsld_id': 'test-probiotic-blend',
            'fullName': 'Probiotic Test',
            'activeIngredients': [
                {'name': 'Probiotic Strain Blend', 'quantity': 0, 'unit': ''}
            ],
            'otherIngredients': []
        }
        result = enricher._collect_ingredient_quality_data(product)
        skipped_names = [ing['name'] for ing in result['ingredients_skipped']]

        assert 'Probiotic Strain Blend' in skipped_names

    def test_omega_fatty_acid_blend_no_dose_skipped(self, enricher):
        """Omega Fatty Acid Blend (no dose) should be skipped."""
        product = {
            'dsld_id': 'test-omega-blend',
            'fullName': 'Omega Blend Test',
            'activeIngredients': [
                {'name': 'Omega Fatty Acid Blend', 'quantity': None, 'unit': None}
            ],
            'otherIngredients': []
        }
        result = enricher._collect_ingredient_quality_data(product)
        skipped_names = [ing['name'] for ing in result['ingredients_skipped']]

        assert 'Omega Fatty Acid Blend' in skipped_names

    def test_proprietary_cartilage_blend_with_dose_skipped(self, enricher):
        """Proprietary Cartilage Blend 500 mg should be skipped (high-confidence pattern)."""
        product = {
            'dsld_id': 'test-cartilage',
            'fullName': 'Joint Support Test',
            'activeIngredients': [
                {'name': 'Proprietary Cartilage Blend', 'quantity': 500, 'unit': 'mg'}
            ],
            'otherIngredients': []
        }
        result = enricher._collect_ingredient_quality_data(product)
        skipped_names = [ing['name'] for ing in result['ingredients_skipped']]
        skip_reasons = result['skipped_reasons_breakdown']

        assert 'Proprietary Cartilage Blend' in skipped_names
        # High-confidence pattern with dose = blend_header_total_weight_only
        assert SKIP_REASON_BLEND_HEADER_WITH_WEIGHT in skip_reasons

    def test_general_proprietary_blend_skipped(self, enricher):
        """General Proprietary Blend should be skipped (high-confidence pattern)."""
        product = {
            'dsld_id': 'test-general-prop',
            'fullName': 'General Test',
            'activeIngredients': [
                {'name': 'General Proprietary Blend', 'quantity': 250, 'unit': 'mg'}
            ],
            'otherIngredients': []
        }
        result = enricher._collect_ingredient_quality_data(product)
        skipped_names = [ing['name'] for ing in result['ingredients_skipped']]

        assert 'General Proprietary Blend' in skipped_names

    def test_therapeutic_blend_container_with_nested_skips(self, enricher):
        """
        A blend container whose ingredientGroup contains 'blend' AND has actual
        nestedIngredients must be skipped even when its name is a known therapeutic.

        Root cause of the original bypass: _should_skip_from_scoring returned
        None at the therapeutic-override check before B1 (nested + blend_in_group)
        could run.  Fix: structural containment check now runs first.
        """
        quality_map = enricher.databases.get('ingredient_quality_map', {})
        botanicals_db = enricher.databases.get('standardized_botanicals', {})
        ingredient = {
            "name": "Full Spectrum Turmeric Blend",
            "standardName": "Turmeric",
            "quantity": 286,
            "unit": "mg",
            "ingredientGroup": "Blend",
            "proprietaryBlend": True,
            "nestedIngredients": [
                {"name": "Turmeric Rhizome Extract", "quantity": 0, "unit": "NP"},
                {"name": "Turmeric Root Extract", "quantity": 0, "unit": "NP"},
            ],
        }
        reason = enricher._should_skip_from_scoring(ingredient, quality_map, botanicals_db)
        assert reason == SKIP_REASON_BLEND_HEADER_WITH_WEIGHT, (
            f"Structural blend container must be skipped even if name is a known "
            f"therapeutic; got skip_reason={reason!r}"
        )

    def test_branded_complex_without_nested_still_scores(self, enricher):
        """
        Branded names containing 'complex' with NO nestedIngredients must not
        be caught by the structural blend check.
        'Curcumin C3 Complex' is a specific branded extract, not a container.
        """
        quality_map = enricher.databases.get('ingredient_quality_map', {})
        botanicals_db = enricher.databases.get('standardized_botanicals', {})
        ingredient = {
            "name": "Curcumin C3 Complex",
            "standardName": "Curcumin",
            "quantity": 500,
            "unit": "mg",
        }
        reason = enricher._should_skip_from_scoring(ingredient, quality_map, botanicals_db)
        assert reason is None, (
            f"Branded 'Complex' without nested children must be scored; "
            f"got skip_reason={reason!r}"
        )


class TestGummiesHeaderLeakRegression:
    """Regression tests for gummies header-leak fixes."""

    def test_percentage_header_variants_not_promoted(self, enricher):
        """Header variants like 'May also contain <2% of:' must never promote."""
        quality_map = enricher.databases.get('ingredient_quality_map', {})
        botanicals_db = enricher.databases.get('standardized_botanicals', {})
        variants = [
            "Contains < 2%",
            "Less than 2%:",
            "May also contain <2% of:",
        ]

        for label in variants:
            result = enricher._should_promote_to_scorable(
                {"name": label, "standardName": label, "quantity": 0, "unit": ""},
                quality_map,
                botanicals_db,
                current_scorable_count=0,
            )
            assert result is None, f"{label} should never be promoted"

    def test_blend_with_dose_and_proprietary_flag_skips(self, enricher):
        """LOW-confidence blend pattern + proprietary flag must skip even with dose."""
        quality_map = enricher.databases.get('ingredient_quality_map', {})
        botanicals_db = enricher.databases.get('standardized_botanicals', {})
        ingredient = {
            "name": "SmartyPants Probiotic Blend",
            "standardName": "SmartyPants Probiotic Blend",
            "quantity": 50,
            "unit": "mg",
            "proprietaryBlend": True,
            "ingredientGroup": "SmartyPants Probiotic Blend",
        }
        reason = enricher._should_skip_from_scoring(ingredient, quality_map, botanicals_db)
        assert reason == SKIP_REASON_BLEND_HEADER_WITH_WEIGHT

    def test_omega_rollup_skips_as_non_therapeutic(self, enricher):
        """Omega rollup headers should be skipped and never counted as active-unmapped."""
        quality_map = enricher.databases.get('ingredient_quality_map', {})
        botanicals_db = enricher.databases.get('standardized_botanicals', {})
        ingredient = {
            "name": "Other Omega-3 Fatty Acids",
            "standardName": "Other Omega-3 Fatty Acids",
            "isNestedIngredient": True,
            "parentBlend": "Omega-3 Fatty Acids",
            "quantity": 15,
            "unit": "mg",
        }
        reason = enricher._should_skip_from_scoring(ingredient, quality_map, botanicals_db)
        assert reason in {SKIP_REASON_BLEND_HEADER_WITH_WEIGHT, SKIP_REASON_NUTRITION_FACT}


class TestFormUnmappedFallbackRegression:
    """Regression test for form-unmapped fallback behavior."""

    def test_form_unmapped_falls_back_to_parent_not_unmapped(self, enricher):
        """
        If cleaned forms[] has an unrecognized form, mapper should:
        - keep mapped=True via conservative parent fallback
        - retain form_unmapped_fallback trace fields for QA.
        """
        quality_map = enricher.databases.get('ingredient_quality_map', {})

        match = enricher._match_quality_map(
            "Vitamin E",
            "Vitamin E",
            quality_map,
            cleaned_forms=[{"name": "D-Alpha-Tocopheryl Acid Succinate"}],
        )
        assert match is not None
        assert match.get("match_status") == "FORM_UNMAPPED_FALLBACK"

        entry = enricher._build_quality_entry(
            {"name": "Vitamin E", "standardName": "Vitamin E", "quantity": 30, "unit": "mg"},
            match,
            hierarchy_type=None,
            source_section="active",
        )
        assert entry.get("mapped") is True
        assert entry.get("identity_decision_reason") == "form_unmapped_fallback"
        assert entry.get("form_unmapped") is True

    def test_generic_source_token_does_not_trigger_form_unmapped_fallback(self, enricher):
        """
        Generic/source-only tokens (e.g., fish-oil provenance) should not be
        treated as form-loss failures. They should fall back to normal parent
        matching without FORM_UNMAPPED_FALLBACK telemetry.
        """
        quality_map = enricher.databases.get('ingredient_quality_map', {})
        match = enricher._match_quality_map(
            "DHA (Docosahexaenoic Acid)",
            "DHA (Docosahexaenoic Acid)",
            quality_map,
            cleaned_forms=[{"name": "Fish Oil"}],
        )
        assert match is not None
        assert match.get("match_status") != "FORM_UNMAPPED_FALLBACK"

    def test_parent_level_dha_fallback_uses_unspecified_form(self, enricher):
        """
        Parent-level DHA matches with unknown form must use the conservative
        unspecified form, not the first/premium form in the database.
        """
        quality_map = enricher.databases.get('ingredient_quality_map', {})
        match = enricher._match_quality_map(
            "Docosahexaenoic Acid",
            "Docosahexaenoic Acid",
            quality_map,
        )
        assert match is not None
        assert match.get("canonical_id") == "dha"
        assert str(match.get("form_id", "")).lower() == "unspecified"
        assert float(match.get("score", 0)) <= 13.0

    def test_combined_dha_epa_does_not_get_premium_form_credit(self, enricher):
        """
        Combined labels like 'DHA, EPA' without explicit delivery/form evidence
        must map to a conservative omega-3 unspecified form (no premium boost).
        """
        quality_map = enricher.databases.get('ingredient_quality_map', {})
        match = enricher._match_quality_map(
            "DHA, EPA",
            "DHA, EPA",
            quality_map,
            cleaned_forms=[
                {"name": "Docosahexaenoic Acid"},
                {"name": "Eicosapentaenoic Acid"},
            ],
        )
        assert match is not None
        assert match.get("canonical_id") == "omega_3"
        assert "unspecified" in str(match.get("form_id", "")).lower()
        assert float(match.get("score", 0)) <= 11.0


class TestCoverageIntegrity:
    """Test coverage metrics integrity and leak detection."""

    def test_total_records_seen_equals_active_count(self, enricher, fixture_product_with_additives):
        """total_records_seen should equal the count of active ingredients."""
        result = enricher._collect_ingredient_quality_data(fixture_product_with_additives)

        # total_records_seen should match len(activeIngredients)
        expected_count = len(fixture_product_with_additives['activeIngredients'])
        assert result['total_records_seen'] == expected_count

    def test_no_unevaluated_records(self, enricher, fixture_product_with_additives):
        """All active records should be classified - no leaks."""
        result = enricher._collect_ingredient_quality_data(fixture_product_with_additives)

        assert result['unevaluated_records'] == 0

    def test_evaluated_equals_scorable_plus_skipped_minus_promoted(self, enricher):
        """
        total_ingredients_evaluated should equal scorable + skipped,
        where scorable includes promoted from inactive.
        """
        product = {
            'dsld_id': 'test-coverage',
            'fullName': 'Coverage Test',
            'activeIngredients': [
                {'name': 'Vitamin C', 'quantity': 500, 'unit': 'mg'},
                {'name': 'Proprietary Blend', 'quantity': None, 'unit': None},
                {'name': 'Elderberry', 'quantity': 100, 'unit': 'mg'},
            ],
            'otherIngredients': [
                {'name': 'Bioperine', 'quantity': 5, 'unit': 'mg'},  # Should be promoted
            ]
        }
        result = enricher._collect_ingredient_quality_data(product)

        total_evaluated = result['total_ingredients_evaluated']
        total_scorable = result['total_scorable_active_count']
        total_skipped = result['skipped_non_scorable_count']

        assert total_evaluated == total_scorable + total_skipped

    def test_schema_version_present(self, enricher, fixture_product_with_additives):
        """quality_data_schema_version should be present."""
        result = enricher._collect_ingredient_quality_data(fixture_product_with_additives)

        assert 'quality_data_schema_version' in result
        assert result['quality_data_schema_version'] == 2


class TestRealLabelMapping:
    """
    Real-label regression tests for new botanicals.
    These verify that real label strings map correctly and become scorable.
    """

    @pytest.fixture
    def enricher(self):
        return SupplementEnricherV3()

    @pytest.mark.parametrize("label_string,expected_canonical", [
        ("Bee Propolis Extract 500 mg", "propolis"),
        ("Black Elderberry Fruit Extract 100 mg", "elderberry"),
        ("Chamomile Flower Extract 50 mg", "chamomile"),
        ("Olive Leaf Extract (Olea europaea) 20 mg", "olive_leaf"),
        ("Lemon Balm Extract (Melissa officinalis) 25 mg", "lemon_balm"),
        ("White Willow Bark 400 mg", "white_willow_bark"),
        ("Astragalus Root Extract 200 mg", "astragalus"),
        ("Licorice Root Extract 100 mg", "licorice"),
        ("Rose Hips 250 mg", "rose_hips"),
        ("Passionflower Extract 100 mg", "passionflower"),
    ])
    def test_botanical_label_is_scorable(self, enricher, label_string, expected_canonical):
        """
        Real label strings should be recognized, mapped, and scorable.
        This catches alias misses that unit tests wouldn't find.
        """
        # Parse dose from label string
        import re
        dose_match = re.search(r'(\d+)\s*(mg|mcg|g|IU)', label_string, re.IGNORECASE)
        quantity = float(dose_match.group(1)) if dose_match else 100
        unit = dose_match.group(2) if dose_match else 'mg'

        # Extract ingredient name (everything before the dose)
        name = re.sub(r'\s*\d+\s*(mg|mcg|g|IU).*', '', label_string, flags=re.IGNORECASE).strip()

        product = {
            'dsld_id': f'test-real-label-{expected_canonical}',
            'fullName': f'Test Product with {name}',
            'activeIngredients': [
                {'name': name, 'quantity': quantity, 'unit': unit}
            ],
            'otherIngredients': []
        }

        result = enricher._collect_ingredient_quality_data(product)

        # Should be scorable
        assert result['total_scorable_active_count'] >= 1, \
            f"'{name}' should be scorable but was not"

        # Check it's in the scorable list
        scorable_names = [ing.get('name', '').lower() for ing in result.get('ingredients_scorable', [])]
        assert any(expected_canonical.replace('_', ' ') in n or
                   n in expected_canonical.replace('_', ' ') or
                   name.lower() in n
                   for n in scorable_names), \
            f"'{name}' not found in scorable ingredients: {scorable_names}"

    @pytest.mark.parametrize("label_string", [
        "Beta Glucan 250 mg",
        "Beta-Glucan 100 mg",
        "β-glucan 200 mg",
        "1,3/1,6 Beta-Glucan 150 mg",
    ])
    def test_beta_glucan_variants_scorable(self, enricher, label_string):
        """Beta-glucan label variants (with/without hyphen, Greek letter) should all be scorable."""
        import re
        dose_match = re.search(r'(\d+)\s*(mg|mcg|g|IU)', label_string, re.IGNORECASE)
        quantity = float(dose_match.group(1)) if dose_match else 100
        unit = dose_match.group(2) if dose_match else 'mg'
        name = re.sub(r'\s*\d+\s*(mg|mcg|g|IU).*', '', label_string, flags=re.IGNORECASE).strip()

        product = {
            'dsld_id': 'test-beta-glucan-variant',
            'fullName': 'Test Beta-Glucan Product',
            'activeIngredients': [
                {'name': name, 'quantity': quantity, 'unit': unit}
            ],
            'otherIngredients': []
        }

        result = enricher._collect_ingredient_quality_data(product)

        assert result['total_scorable_active_count'] >= 1, \
            f"'{label_string}' should be scorable but was not"

    def test_licorice_uk_spelling_scorable(self, enricher):
        """UK spelling 'liquorice' should be recognized."""
        product = {
            'dsld_id': 'test-uk-spelling',
            'fullName': 'UK Liquorice Product',
            'activeIngredients': [
                {'name': 'Liquorice Root Extract', 'quantity': 100, 'unit': 'mg'}
            ],
            'otherIngredients': []
        }

        result = enricher._collect_ingredient_quality_data(product)

        assert result['total_scorable_active_count'] >= 1, \
            "'Liquorice' (UK spelling) should be scorable"

    def test_botanical_with_latin_name_scorable(self, enricher):
        """Latin names should be recognized via aliases."""
        product = {
            'dsld_id': 'test-latin-names',
            'fullName': 'Latin Name Product',
            'activeIngredients': [
                {'name': 'Matricaria chamomilla', 'quantity': 100, 'unit': 'mg'},
                {'name': 'Glycyrrhiza glabra', 'quantity': 50, 'unit': 'mg'},
                {'name': 'Passiflora incarnata', 'quantity': 200, 'unit': 'mg'},
            ],
            'otherIngredients': []
        }

        result = enricher._collect_ingredient_quality_data(product)

        # All three should be scorable
        assert result['total_scorable_active_count'] >= 3, \
            f"Latin names should be scorable, got {result['total_scorable_active_count']}"


class TestNormalizationEquivalence:
    """
    Tests for punctuation/slash normalization.
    Ensures that label variants with em-dashes, slashes, parentheses
    normalize correctly for matching.
    """

    @pytest.fixture
    def enricher(self):
        return SupplementEnricherV3()

    @pytest.mark.parametrize("original,expected", [
        # Em-dash normalization
        ("elderberry—fruit extract", "elderberry-fruit extract"),
        # Slash normalization: only NUMERIC slashes are converted (1/2 → 1 2)
        # Non-numeric slashes are preserved for ingredient specificity
        ("elderberry / fruit extract", "elderberry / fruit extract"),
        ("superfood / immune blend", "superfood / immune blend"),
        # Parentheses preserved (important for Latin names)
        ("olive leaf (Olea europaea)", "olive leaf (olea europaea)"),
        ("chamomile (matricaria)", "chamomile (matricaria)"),
        # Hyphen preserved
        ("beta-glucan", "beta-glucan"),
        ("1,3/1,6 beta-glucan", "1 3 1 6 beta-glucan"),  # slash and comma normalized
        # Greek beta (β) → beta
        ("β-glucan", "beta-glucan"),
        ("1,3/1,6 β-glucan", "1 3 1 6 beta-glucan"),
        # Micro sign (µ) → mc
        ("100µg", "100mcg"),
        # Trademark symbols removed
        ("Sambucol™ Elderberry", "sambucol elderberry"),
        ("BioPerine®", "bioperine"),
    ])
    def test_normalize_text_equivalence(self, enricher, original, expected):
        """Verify text normalization handles punctuation variants correctly."""
        result = enricher._normalize_text(original)
        assert result == expected, f"'{original}' should normalize to '{expected}', got '{result}'"

    def test_hyphen_and_space_variants_both_match(self, enricher):
        """Label variants with hyphens vs spaces should both resolve (not unmapped)."""
        quality_map = enricher.databases.get('ingredient_quality_map', {})

        # Both should match to some entry (either beta_glucan or prebiotics)
        variant1 = enricher._match_quality_map("beta glucan", "beta glucan", quality_map)
        variant2 = enricher._match_quality_map("beta-glucan", "beta-glucan", quality_map)

        assert variant1 is not None, "beta glucan (space) should match some entry"
        assert variant2 is not None, "beta-glucan (hyphen) should match some entry"
        # Note: These may match different entries (beta_glucan vs prebiotics)
        # but both should be mapped, not unmapped

    def test_parenthetical_latin_names_match(self, enricher):
        """Labels with Latin names in parentheses should match."""
        quality_map = enricher.databases.get('ingredient_quality_map', {})

        # These should all match olive_leaf
        test_labels = [
            "Olive Leaf",
            "Olive Leaf Extract",
            "olive leaf (olea europaea)",
            "Olea europaea",
        ]

        for label in test_labels:
            result = enricher._match_quality_map(label, label, quality_map)
            assert result is not None, f"'{label}' should match olive_leaf"
            assert "olive" in result.get('standard_name', '').lower(), \
                f"'{label}' should match to Olive Leaf, got {result.get('standard_name')}"


class TestQualityMapPrecedence:
    def test_exact_beats_normalized(self, enricher):
        quality_map = {
            "exact_entry": {
                "standard_name": "Exact Form",
                "category": "test",
                "forms": {
                    "EGCG™": {
                        "bio_score": 10,
                        "natural": True,
                        "score": 10,
                        "aliases": ["EGCG™"]
                    }
                }
            },
            "normalized_entry": {
                "standard_name": "Normalized Form",
                "category": "test",
                "forms": {
                    "EGCG": {
                        "bio_score": 5,
                        "natural": False,
                        "score": 5,
                        "aliases": ["EGCG"]
                    }
                }
            }
        }

        result = enricher._match_quality_map("EGCG™", "EGCG™", quality_map)
        assert result is not None
        assert result["standard_name"] == "Exact Form"

    def test_form_exact_beats_parent_exact(self, enricher):
        quality_map = {
            "green_tea": {
                "standard_name": "Green Tea",
                "category": "test",
                "aliases": ["EGCG"],
                "forms": {
                    "green tea catechins": {
                        "bio_score": 12,
                        "natural": True,
                        "score": 12,
                        "aliases": ["EGCG"]
                    }
                }
            }
        }

        result = enricher._match_quality_map("EGCG", "EGCG", quality_map)
        assert result is not None
        assert result["form_name"] == "green tea catechins"

    def test_longest_alias_wins_in_pattern_tier(self, enricher):
        quality_map = {
            "elderberry_extract": {
                "standard_name": "Elderberry Extract",
                "category": "test",
                "forms": {
                    "elderberry extract": {
                        "bio_score": 8,
                        "natural": True,
                        "score": 8,
                        "contains_aliases": ["elderberry extract"]
                    }
                }
            },
            "elderberry_fruit_extract": {
                "standard_name": "Elderberry Fruit Extract",
                "category": "test",
                "forms": {
                    "elderberry fruit extract": {
                        "bio_score": 10,
                        "natural": True,
                        "score": 10,
                        "contains_aliases": ["elderberry fruit extract"]
                    }
                }
            }
        }

        result = enricher._match_quality_map(
            "Elderberry Fruit Extract 100 mg",
            "Elderberry Fruit Extract 100 mg",
            quality_map
        )
        assert result is not None
        assert result["standard_name"] == "Elderberry Fruit Extract"

    def test_pattern_tier_never_overrides_exact(self, enricher):
        quality_map = {
            "exact_entry": {
                "standard_name": "Exact Match",
                "category": "test",
                "forms": {
                    "EGCG": {
                        "bio_score": 10,
                        "natural": True,
                        "score": 10,
                        "aliases": ["EGCG"]
                    }
                }
            },
            "pattern_entry": {
                "standard_name": "Pattern Match",
                "category": "test",
                "forms": {
                    "contains_eg": {
                        "bio_score": 5,
                        "natural": False,
                        "score": 5,
                        "contains_aliases": ["EG"]
                    }
                }
            }
        }

        result = enricher._match_quality_map("EGCG", "EGCG", quality_map)
        assert result is not None
        assert result["standard_name"] == "Exact Match"

    def test_deterministic_match_same_input(self, enricher):
        quality_map = {
            "entry_one": {
                "standard_name": "Entry One",
                "category": "test",
                "forms": {
                    "alpha": {
                        "bio_score": 8,
                        "natural": True,
                        "score": 8,
                        "aliases": ["Alpha"]
                    }
                }
            },
            "entry_two": {
                "standard_name": "Entry Two",
                "category": "test",
                "forms": {
                    "beta": {
                        "bio_score": 6,
                        "natural": False,
                        "score": 6,
                        "aliases": ["Beta"]
                    }
                }
            }
        }

        first = enricher._match_quality_map("Alpha", "Alpha", quality_map)
        second = enricher._match_quality_map("Alpha", "Alpha", quality_map)
        assert first == second

    def test_deterministic_with_shuffled_keys(self, enricher):
        quality_map = {
            "alpha_entry": {
                "standard_name": "Alpha Herb",
                "category": "test",
                "forms": {
                    "alpha_form": {
                        "bio_score": 8,
                        "natural": True,
                        "score": 8,
                        "aliases": ["Herb"]
                    }
                }
            },
            "beta_entry": {
                "standard_name": "Beta Herb",
                "category": "test",
                "forms": {
                    "beta_form": {
                        "bio_score": 7,
                        "natural": True,
                        "score": 7,
                        "aliases": ["Herb"]
                    }
                }
            }
        }

        shuffled_map = dict(reversed(list(quality_map.items())))

        first = enricher._match_quality_map("Herb", "Herb", quality_map)
        second = enricher._match_quality_map("Herb", "Herb", shuffled_map)
        assert first == second

    def test_normalized_match_handles_parenthesis_characters(self, enricher):
        quality_map = enricher.databases.get("ingredient_quality_map", {})
        result = enricher._match_quality_map(
            "organic Oregano (Origanum vulgare) (leaf) supercritical extract",
            "organic Oregano (Origanum vulgare) (leaf) supercritical extract",
            quality_map,
        )
        assert result is not None
        assert result.get("canonical_id") == "oregano"

    def test_normalized_match_handles_comma_qualifier_reorder(self, enricher):
        quality_map = enricher.databases.get("ingredient_quality_map", {})
        result = enricher._match_quality_map(
            "Garlic Bulb Extract, Odorless",
            "Garlic Bulb Extract, Odorless",
            quality_map,
        )
        assert result is not None
        assert result.get("canonical_id") == "garlic"

    def test_recognized_non_scorable_handles_cold_pressed_comma_variants(self, enricher):
        recognized = enricher._is_recognized_non_scorable(
            "Pumpkin Seed Oil, Cold-Pressed",
            "Pumpkin Seed Oil, Cold-Pressed",
        )
        assert recognized is not None
        assert recognized.get("recognition_source") in {
            "other_ingredients",
            "botanical_ingredients",
            "standardized_botanicals",
            "excipient_list",
        }


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
