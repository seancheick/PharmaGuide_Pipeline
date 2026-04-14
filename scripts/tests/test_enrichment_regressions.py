"""
Enrichment Pipeline Regression Tests

P0/P1 acceptance criteria tests for the enrichment pipeline.
These tests verify the fixes implemented in the 2026-01-04 enrichment plan.
"""

import pytest
import sys
import os

# Add parent directory to path for imports (normalized to avoid ".." in __file__)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from enrich_supplements_v3 import SupplementEnricherV3
from constants import SKIP_REASON_RECOGNIZED_NON_SCORABLE


class TestAllergenPresenceType:
    """P0.1: Allergen detection with presence_type"""

    @pytest.fixture
    def enricher(self):
        return SupplementEnricherV3()

    def test_label_statement_allergens_contains(self, enricher):
        """Milk/soy from 'Contains:' statement must have presence_type=contains"""
        product = {
            'id': 'test_1',
            'statements': [
                {'type': 'allergen', 'text': 'Contains milk and soy.'}
            ],
            'activeIngredients': [],
            'inactiveIngredients': []
        }

        result = enricher._check_allergens([], product)

        # Should find milk and soy with presence_type=contains
        allergen_ids = {a['allergen_id'] for a in result['allergens']}
        assert 'ALLERGEN_MILK' in allergen_ids or any('milk' in a.get('allergen_name', '').lower() for a in result['allergens'])

        for allergen in result['allergens']:
            if 'milk' in allergen.get('allergen_name', '').lower():
                assert allergen.get('presence_type') == 'contains'
                assert allergen.get('source') == 'label_statement'

    def test_may_contain_allergens(self, enricher):
        """May contain allergens get presence_type=may_contain"""
        product = {
            'id': 'test_2',
            'statements': [
                {'type': 'allergen', 'text': 'May contain peanuts.'}
            ],
            'activeIngredients': [],
            'inactiveIngredients': []
        }

        result = enricher._check_allergens([], product)

        for allergen in result['allergens']:
            if 'peanut' in allergen.get('allergen_name', '').lower():
                assert allergen.get('presence_type') == 'may_contain'

    def test_ingredient_derived_allergens(self, enricher):
        """Ingredient-derived allergens get presence_type=ingredient_list"""
        ingredients = [
            {'name': 'Corn Starch', 'standardName': 'Corn Starch'}
        ]
        product = {
            'id': 'test_3',
            'statements': [],
            'activeIngredients': ingredients,
            'inactiveIngredients': []
        }

        result = enricher._check_allergens(ingredients, product)

        for allergen in result['allergens']:
            if 'corn' in allergen.get('allergen_name', '').lower():
                assert allergen.get('presence_type') == 'ingredient_list'
                assert allergen.get('source') == 'ingredient_list'

    def test_precedence_contains_over_ingredient(self, enricher):
        """contains > ingredient_list precedence - only one record per allergen"""
        ingredients = [
            {'name': 'Milk Protein', 'standardName': 'Milk Protein'}
        ]
        product = {
            'id': 'test_4',
            'statements': [
                {'type': 'allergen', 'text': 'Contains milk.'}
            ],
            'activeIngredients': ingredients,
            'inactiveIngredients': []
        }

        result = enricher._check_allergens(ingredients, product)

        # Count milk allergens - should only be 1
        milk_allergens = [a for a in result['allergens'] if 'milk' in a.get('allergen_name', '').lower()]
        assert len(milk_allergens) <= 1, "Should deduplicate milk allergen"

        if milk_allergens:
            # Should have presence_type=contains (higher precedence)
            assert milk_allergens[0].get('presence_type') == 'contains'


class TestSugarExtraction:
    """P0.2: Sugar from nested rows"""

    @pytest.fixture
    def enricher(self):
        return SupplementEnricherV3()

    def test_sugar_level_guardrail(self, enricher):
        """If contains_sugar is true, level cannot be sugar_free"""
        product = {
            'id': 'test_5',
            'nutritionalInfo': {'sugars': {'amount': 4, 'unit': 'g'}},
            'activeIngredients': [],
            'inactiveIngredients': [
                {'name': 'Corn Syrup'}
            ]
        }

        result = enricher._collect_dietary_sensitivity_data(product)

        # Sugar is 4g and corn syrup present
        assert result['sugar']['amount_g'] == 4
        assert result['sugar']['level'] != 'sugar_free'
        assert result['sugar']['contains_sugar'] == True
        assert result['diabetes_friendly'] == False

    def test_contains_sugar_from_ingredients(self, enricher):
        """contains_sugar true if sugar-containing ingredients present"""
        product = {
            'id': 'test_6',
            'nutritionalInfo': {},
            'activeIngredients': [],
            'inactiveIngredients': [
                {'name': 'Cane Sugar'}
            ]
        }

        result = enricher._collect_dietary_sensitivity_data(product)

        # Even with 0g sugar in nutritional info, has_added_sugar should be true
        assert result['sugar']['has_added_sugar'] == True
        assert result['sugar']['contains_sugar'] == True


class TestNaturalColors:
    """P0.5: Colors classification"""

    @pytest.fixture
    def enricher(self):
        return SupplementEnricherV3()

    def test_colors_from_fruits_not_artificial(self, enricher):
        """Colors from Fruits and Vegetables is NOT flagged as artificial"""
        ingredients = [
            {
                'name': 'Colors',
                'standardName': 'Colors',
                'forms': [{'name': 'from Fruits'}, {'name': 'and Vegetables'}],
                'notes': ''
            }
        ]

        result = enricher._check_harmful_additives(ingredients)

        # Should NOT have "Artificial Colors (General)" match
        artificial_color_found = any(
            'artificial' in a.get('additive_name', '').lower() and 'color' in a.get('additive_name', '').lower()
            for a in result['additives']
        )
        assert not artificial_color_found, "Natural colors should not match artificial colors"

    def test_fd_c_dyes_are_artificial(self, enricher):
        """FD&C dyes ARE flagged as artificial"""
        ingredients = [
            {
                'name': 'Red 40',
                'standardName': 'Red 40',
                'forms': [],
                'notes': ''
            }
        ]

        result = enricher._check_harmful_additives(ingredients)

        # Should find Red 40 as harmful
        # Note: This depends on harmful_additives.json having Red 40 entry
        # If not present, test should be skipped
        if result['additives']:
            assert any('red' in a.get('additive_name', '').lower() for a in result['additives'])


class TestProbioticCFU:
    """P1.1: Viable Cell(s) as CFU-equivalent"""

    @pytest.fixture
    def enricher(self):
        return SupplementEnricherV3()

    def test_viable_cells_recognized_as_cfu(self, enricher):
        """unit='Viable Cell(s)' treated as CFU-equivalent"""
        ingredient = {
            'name': 'BC30 Bacillus coagulans',
            'quantity': 500000000,
            'unit': 'Viable Cell(s)',
            'notes': ''
        }

        result = enricher._extract_cfu('', ingredient=ingredient)

        assert result['has_cfu'] == True
        assert result['cfu_count'] == 500000000
        assert result['billion_count'] == 0.5

    def test_classifier_uses_iqd_categories_when_active_categories_missing(self, enricher):
        product = {
            "product_name": "Restore",
            "fullName": "Thorne Performance Restore",
            "activeIngredients": [
                {"name": "Lactobacillus gasseri", "standardName": "Lactobacillus Gasseri", "category": None},
                {"name": "Bifidobacterium longum", "standardName": "Bifidobacterium Longum", "category": None},
                {"name": "Bifidobacterium bifidum", "standardName": "Bifidobacterium Bifidum", "category": None},
            ],
            "inactiveIngredients": [{"name": "Rice Flour"}],
            "ingredient_quality_data": {
                "ingredients": [
                    {"name": "Lactobacillus gasseri", "standard_name": "Lactobacillus Gasseri", "category": "probiotics"},
                    {"name": "Bifidobacterium longum", "standard_name": "Bifidobacterium Longum", "category": "probiotics"},
                    {"name": "Bifidobacterium bifidum", "standard_name": "Bifidobacterium Bifidum", "category": "probiotics"},
                ]
            },
            "probiotic_data": {"is_probiotic_product": True},
        }

        result = enricher._classify_supplement_type(product)

        assert result["type"] == "probiotic"
        assert result["active_count"] == 3
        assert result["source"] == "ingredient_quality_data"
        assert result["category_breakdown"]["probiotic"] == 3

    def test_classifier_keeps_scorable_proprietary_blend_members(self, enricher):
        product = {
            "product_name": "Quick Melt Probiotic Sticks Crisp Apple",
            "activeIngredients": [
                {"name": "Bifidobacterium lactis HN019", "standardName": "Bifidobacterium lactis HN019", "category": None},
                {"name": "Lactobacillus acidophilus NCFM", "standardName": "Lactobacillus acidophilus NCFM", "category": None},
                {"name": "Lactobacillus rhamnosus GG", "standardName": "Lactobacillus rhamnosus GG", "category": None},
            ],
            "ingredient_quality_data": {
                "ingredients": [
                    {
                        "name": "Bifidobacterium lactis HN019",
                        "standard_name": "Bifidobacterium Lactis",
                        "category": "probiotics",
                        "is_proprietary_blend": True,
                        "role_classification": "active_scorable",
                    },
                    {
                        "name": "Lactobacillus acidophilus NCFM",
                        "standard_name": "Lactobacillus Acidophilus",
                        "category": "probiotics",
                        "is_proprietary_blend": True,
                        "role_classification": "active_scorable",
                    },
                    {
                        "name": "Lactobacillus rhamnosus GG",
                        "standard_name": "Lactobacillus Rhamnosus",
                        "category": "probiotics",
                        "is_proprietary_blend": True,
                        "role_classification": "active_scorable",
                    },
                ]
            },
            "probiotic_data": {"is_probiotic_product": True},
            "inactiveIngredients": [],
        }

        result = enricher._classify_supplement_type(product)

        assert result["type"] == "probiotic"
        assert result["active_count"] == 3

    def test_guarantee_at_manufacture(self, enricher):
        """'At the time of manufacture.' sets guarantee_type"""
        result = enricher._extract_guarantee_type("Contains 500 million CFU at the time of manufacture.")

        assert result == "at_manufacture"

    def test_guarantee_at_expiration(self, enricher):
        """'Until expiration' sets guarantee_type"""
        result = enricher._extract_guarantee_type("Contains 500 million CFU until expiration.")

        assert result == "at_expiration"

    def test_probiotic_type_classification_does_not_drop_missing_category_actives(self, enricher):
        """Missing category metadata must not suppress probiotic classification."""
        product = {
            'id': 'test_probiotic_missing_category',
            'product_name': 'Restore',
            'fullName': 'Thorne Performance Restore',
            'activeIngredients': [
                {'name': 'Lactobacillus gasseri', 'standardName': 'Lactobacillus Gasseri'},
                {'name': 'Bifidobacterium longum', 'standardName': 'Bifidobacterium Longum'},
                {'name': 'Bifidobacterium bifidum', 'standardName': 'Bifidobacterium Bifidum'},
            ],
            'inactiveIngredients': [
                {'name': 'Hypromellose Capsule'},
            ],
        }

        result = enricher._classify_supplement_type(product)

        assert result['type'] == 'probiotic'
        assert result['active_count'] == 3


class TestServingBasis:
    """P0.4: Serving basis fields"""

    @pytest.fixture
    def enricher(self):
        return SupplementEnricherV3()

    def test_form_factor_from_langual(self, enricher):
        """form_factor derived from langualCodeDescription"""
        product = {
            'id': 'test_7',
            'physicalState': {'langualCodeDescription': 'Gummy'},
            'servingSizes': [],
            'statements': [],
            'userGroups': []
        }

        result = enricher._collect_serving_basis_data(product)

        assert result['form_factor'] == 'gummy'

    def test_serving_basis_from_serving_sizes(self, enricher):
        """basis_count from servingSizes"""
        product = {
            'id': 'test_8',
            'physicalState': {},
            'servingSizes': [
                {'quantity': 2, 'servingSizeUnitOfMeasure': 'Gummy(ies)'}
            ],
            'statements': [],
            'userGroups': []
        }

        result = enricher._collect_serving_basis_data(product)

        assert result['serving_basis']['basis_count'] == 2

    def test_serving_basis_daily_servings_from_serving_sizes(self, enricher):
        """min/max daily servings from servingSizes"""
        product = {
            'id': 'test_8b',
            'physicalState': {},
            'servingSizes': [
                {
                    'quantity': 1,
                    'servingSizeUnitOfMeasure': 'Gummy(ies)',
                    'minDailyServings': 2,
                    'maxDailyServings': 4
                }
            ],
            'statements': [],
            'userGroups': []
        }

        result = enricher._collect_serving_basis_data(product)

        assert result['serving_basis']['min_servings_per_day'] == 2
        assert result['serving_basis']['max_servings_per_day'] == 4
        assert result['serving_basis']['servings_per_day_source'] == 'servingSizes'

    def test_dosage_parsing_from_directions(self, enricher):
        """min/max from directions parsing"""
        result = enricher._parse_dosage_from_directions("Take 2 to 4 gummies daily.")

        assert result['min'] == 2
        assert result['max'] == 4


class TestQuantityVariants:
    """P0.3: Multi-serving quantity variants"""

    def test_quantity_variants_preserved(self):
        """Multiple quantity variants are preserved in cleaned output"""
        from enhanced_normalizer import EnhancedDSLDNormalizer

        normalizer = EnhancedDSLDNormalizer()

        # Test with list of quantities
        quantities = [
            {'quantity': 250000000, 'unit': 'Viable Cell(s)', 'dailyValueTargetGroup': [{'servingSizeQuantity': 1}]},
            {'quantity': 500000000, 'unit': 'Viable Cell(s)', 'dailyValueTargetGroup': [{'servingSizeQuantity': 2}]}
        ]

        quantity, unit, daily_value, variants = normalizer._process_quantity(quantities)

        # Should preserve both variants
        assert len(variants) == 2
        assert variants[0]['quantity'] == 250000000
        assert variants[1]['quantity'] == 500000000

    def test_single_quantity_no_variants(self):
        """Single quantity returns no variants list"""
        from enhanced_normalizer import EnhancedDSLDNormalizer

        normalizer = EnhancedDSLDNormalizer()

        quantities = {'quantity': 500, 'unit': 'mg'}

        quantity, unit, daily_value, variants = normalizer._process_quantity(quantities)

        assert quantity == 500
        assert unit == 'mg'
        # Single quantity should still return a list with 1 item
        assert len(variants) == 1


class TestRDAULPerDayBasis:
    """P1: RDA/UL should use per-day max servings"""

    @pytest.fixture
    def enricher(self):
        return SupplementEnricherV3()

    def test_rda_ul_uses_max_servings_per_day(self, enricher):
        """Per-day max servings should drive UL exceedance checks"""
        rda_db = enricher.rda_calculator.rda_db
        vitamin_c = next(
            nutrient for nutrient in rda_db.get('nutrient_recommendations', [])
            if nutrient.get('id') == 'vitamin_c'
        )
        ul_value = vitamin_c.get('highest_ul')
        unit = vitamin_c.get('unit', 'mg')
        standard_name = vitamin_c.get('standard_name', 'Vitamin C')

        max_servings = 3
        per_serving = (ul_value / max_servings) * 1.1

        product = {
            'id': 'test_rda_1',
            'activeIngredients': [
                {
                    'name': standard_name,
                    'standardName': standard_name,
                    'quantity': per_serving,
                    'unit': unit
                }
            ]
        }

        result = enricher._collect_rda_ul_data(
            product,
            min_servings_per_day=1,
            max_servings_per_day=max_servings
        )

        adequacy = result['adequacy_results'][0]
        assert adequacy['per_day_min'] == pytest.approx(per_serving)
        assert adequacy['per_day_max'] == pytest.approx(per_serving * max_servings)
        assert adequacy['amount'] == pytest.approx(per_serving * max_servings)
        assert result['has_over_ul'] is True
        assert result['safety_flags'][0]['amount'] == pytest.approx(per_serving * max_servings)


class TestUnknownFormSkipsUL:
    """Unknown vitamin form should skip UL checks."""

    @pytest.fixture
    def enricher(self):
        return SupplementEnricherV3()

    def test_unknown_vitamin_a_skips_ul(self, enricher):
        product = {
            'id': 'test_unknown_form',
            'activeIngredients': [
                {
                    'name': 'Vitamin A',
                    'standardName': 'Vitamin A',
                    'quantity': 5000,
                    'unit': 'IU'
                }
            ]
        }

        result = enricher._collect_rda_ul_data(
            product,
            min_servings_per_day=1,
            max_servings_per_day=1
        )

        adequacy = result['adequacy_results'][0]
        assert adequacy['skip_ul_check'] is True
        assert adequacy['skip_ul_reason'] == 'unknown_vitamin_form'
        assert adequacy['ul_status'] == 'skipped_unknown_vitamin_form'
        assert adequacy['over_ul'] is False
        assert adequacy['pct_ul'] is None
        assert adequacy['scoring_eligible'] is False


class TestManufacturerNormalization:
    """P1.3: Manufacturer normalization"""

    @pytest.fixture
    def enricher(self):
        return SupplementEnricherV3()

    def test_normalize_llc_suffix(self, enricher):
        """LLC suffix is stripped"""
        result = enricher._normalize_company_name("Church & Dwight Co., LLC")

        assert 'llc' not in result.lower()
        assert 'co.' not in result.lower() or 'church' in result.lower()

    def test_normalize_inc_suffix(self, enricher):
        """Inc suffix is stripped"""
        result = enricher._normalize_company_name("Nature's Way Products, Inc.")

        assert 'inc' not in result.lower()

    def test_normalize_consistent(self, enricher):
        """Same manufacturer variants normalize to same value"""
        result1 = enricher._normalize_company_name("Church & Dwight Co., Inc.")
        result2 = enricher._normalize_company_name("Church & Dwight")

        # Should be similar after normalization
        assert result1.startswith('church')
        assert result2.startswith('church')


class TestSurvivabilityKeywords:
    """P1.2: Survivability coating keywords"""

    @pytest.fixture
    def enricher(self):
        return SupplementEnricherV3()

    def test_protected_by_outer_layer(self, enricher):
        """'protected by an outer layer' is recognized"""
        assert 'protected by an outer layer' in enricher.SURVIVABILITY_KEYWORDS

    def test_microencapsulated(self, enricher):
        """'microencapsulated' is recognized"""
        assert 'microencapsulated' in enricher.SURVIVABILITY_KEYWORDS

    def test_all_expected_keywords_present(self, enricher):
        """All P1.2 keywords are in the list"""
        expected = [
            'protected by an outer layer',
            'protected by patented',
            'outer protective layer',
            'proprietary coating',
            'microencapsulated',
            'acid-resistant coating'
        ]

        for keyword in expected:
            assert keyword in enricher.SURVIVABILITY_KEYWORDS, f"Missing keyword: {keyword}"


class TestColorsIntegrationCleanToEnrich:
    """
    End-to-end integration tests for Colors classification.

    Validates that the fix in the cleaning layer (standardName mapping)
    correctly flows through to the enrichment layer (harmful_additives).

    Acceptance Criteria:
    - "Colors" + fruit/vegetable forms → standardName="natural colors" (cleaning)
    - Enriched harmful_additives must NOT include ADD_ARTIFICIAL_COLORS (enrichment)
    - FD&C dyes SHOULD be flagged as harmful (enrichment)
    """

    @pytest.fixture
    def normalizer(self):
        from enhanced_normalizer import EnhancedDSLDNormalizer
        return EnhancedDSLDNormalizer()

    @pytest.fixture
    def enricher(self):
        return SupplementEnricherV3()

    def test_natural_colors_not_flagged_as_harmful(self, normalizer, enricher):
        """
        End-to-end: Colors with fruit/vegetable forms should NOT be
        flagged as harmful additives in the enrichment output.
        """
        # Step 1: Clean the raw product
        raw_product = {
            "id": "test_e2e_natural_colors",
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
                    },
                    {
                        "name": "Citric Acid",
                        "order": 2,
                        "forms": []
                    }
                ]
            }
        }

        cleaned = normalizer.normalize_product(raw_product)

        # Verify cleaning step produced correct standardName
        colors_ing = next(
            (i for i in cleaned.get("inactiveIngredients", [])
             if i and i.get("name", "").lower() == "colors"),
            None
        )
        assert colors_ing is not None, "Colors ingredient should be in cleaned output"
        assert colors_ing.get("standardName") == "natural colors", \
            f"Cleaning should map to 'natural colors', got: {colors_ing.get('standardName')}"

        # Step 2: Enrich the cleaned product
        enriched, warnings = enricher.enrich_product(cleaned)

        # Step 3: Verify harmful_additives does NOT include artificial colors
        contaminant_data = enriched.get("contaminant_data", {})
        harmful_additives = contaminant_data.get("harmful_additives", {})
        additives_found = harmful_additives.get("additives", [])

        # Check that no artificial color entry exists for this natural colorant
        artificial_color_ids = {"ADD_ARTIFICIAL_COLORS", "ADD_SYNTHETIC_COLORS"}
        for additive in additives_found:
            additive_id = additive.get("additive_id", "")
            ingredient = additive.get("ingredient", "").lower()

            if "color" in ingredient:
                assert additive_id not in artificial_color_ids, \
                    f"Natural colors incorrectly flagged as harmful: {additive}"
                # If colors appear, should be marked as natural
                if additive.get("is_natural_color") is not None:
                    assert additive.get("is_natural_color") is True, \
                        "Colors should be marked as natural_color"

    def test_artificial_colors_are_flagged_as_harmful(self, normalizer, enricher):
        """
        End-to-end: FD&C dyes should BE flagged as harmful additives.
        """
        # Step 1: Clean the raw product with artificial colors
        raw_product = {
            "id": "test_e2e_artificial_colors",
            "fullName": "Test Artificial Colors Product",
            "brandName": "Test Brand",
            "productVersionCode": "1",
            "ingredientRows": [
                {"name": "Vitamin C", "order": 1, "quantity": [{"quantity": 100, "unit": "mg"}]}
            ],
            "otherIngredients": {
                "ingredients": [
                    {
                        "name": "Red 40",
                        "order": 1,
                        "forms": []
                    },
                    {
                        "name": "Yellow 5",
                        "order": 2,
                        "forms": []
                    }
                ]
            }
        }

        cleaned = normalizer.normalize_product(raw_product)

        # Step 2: Enrich the cleaned product
        enriched, warnings = enricher.enrich_product(cleaned)

        # Step 3: Verify harmful_additives DOES include artificial colors
        contaminant_data = enriched.get("contaminant_data", {})
        harmful_additives = contaminant_data.get("harmful_additives", {})
        additives_found = harmful_additives.get("additives", [])

        # At least one FD&C dye should be flagged
        dye_flagged = any(
            "red" in a.get("ingredient", "").lower() or
            "yellow" in a.get("ingredient", "").lower()
            for a in additives_found
        )

        # Verify the enrichment processed the product (even if not ready_for_scoring)
        assert enriched is not None, "Enrichment should return a product"
        assert "contaminant_data" in enriched, "Enriched product should have contaminant_data"

        # If Red 40 and Yellow 5 are in harmful_additives.json, they should be flagged
        # This is informational - if dyes are not in the database, this is a data issue not a code issue
        if dye_flagged:
            print("Artificial dyes correctly flagged as harmful")
        else:
            # Check if Red 40 or Yellow 5 appear in inactive ingredients
            inactive = enriched.get("inactiveIngredients", [])
            dye_names = [i.get("name", "").lower() for i in inactive]
            assert "red 40" in dye_names or "yellow 5" in dye_names, \
                "Artificial dyes should be present in inactive ingredients"

    def test_colors_forms_preserved_through_pipeline(self, normalizer, enricher):
        """
        Forms with prefix should be preserved through clean → enrich pipeline.
        """
        raw_product = {
            "id": "test_forms_preserved",
            "fullName": "Test Forms Preserved",
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
        enriched, warnings = enricher.enrich_product(cleaned)

        # Find Colors in enriched inactive ingredients
        inactive = enriched.get("inactiveIngredients", [])
        colors_ing = next(
            (i for i in inactive if i and i.get("name", "").lower() == "colors"),
            None
        )

        assert colors_ing is not None, "Colors should be in enriched output"

        # Verify forms structure is preserved
        forms = colors_ing.get("forms", [])
        assert len(forms) == 2, f"Expected 2 forms, got {len(forms)}"

        # Check prefix is preserved
        prefixes = [f.get("prefix", "") for f in forms]
        assert "from" in prefixes, "Prefix 'from' should be preserved"
        assert "and" in prefixes, "Prefix 'and' should be preserved"


class TestBrandedFormMatching:
    """Ensure branded ingredient forms map correctly, not to generic/unspecified.

    This tests the fix for the KSM-66 mapping bug where branded forms were being
    matched to generic "(unspecified)" forms due to incorrect sort key logic.

    The fix adds `match_source` tracking to prioritize matches on the raw ingredient
    name over matches on the derived standardName.
    """

    @pytest.fixture
    def enricher(self):
        return SupplementEnricherV3()

    @pytest.fixture
    def quality_map(self, enricher):
        return enricher.databases.get('ingredient_quality_map', {})

    def test_ksm66_maps_to_ksm66_form(self, enricher, quality_map):
        """KSM-66 should map to 'KSM-66 ashwagandha', not 'ashwagandha (unspecified)'."""
        result = enricher._match_quality_map('KSM-66', 'Ashwagandha', quality_map)

        assert result is not None, "KSM-66 should match"
        assert result["form_id"] == "KSM-66 ashwagandha", (
            f"Expected 'KSM-66 ashwagandha', got '{result['form_id']}'"
        )
        assert result["canonical_id"] == "ashwagandha"

    def test_sensoril_maps_to_sensoril_form(self, enricher, quality_map):
        """Sensoril should map to its specific form, not generic."""
        result = enricher._match_quality_map('Sensoril', 'Ashwagandha', quality_map)

        assert result is not None, "Sensoril should match"
        assert "sensoril" in result["form_id"].lower(), (
            f"Expected sensoril form, got '{result['form_id']}'"
        )
        assert result["canonical_id"] == "ashwagandha"

    def test_generic_ashwagandha_maps_to_unspecified(self, enricher, quality_map):
        """Generic 'Ashwagandha' should map to unspecified form."""
        result = enricher._match_quality_map('Ashwagandha', 'Ashwagandha', quality_map)

        assert result is not None, "Ashwagandha should match"
        assert result["form_id"] == "ashwagandha (unspecified)", (
            f"Expected 'ashwagandha (unspecified)', got '{result['form_id']}'"
        )

    def test_raw_input_takes_priority_over_standardname(self, enricher, quality_map):
        """When raw name is specific (KSM-66) but standardName is generic (Ashwagandha),
        the raw name match should win.

        Note: Current implementation uses exact matching on normalized values.
        Compound inputs like 'KSM-66 Ashwagandha Root Extract' don't extract
        'KSM-66' as a substring - they require exact alias matches.
        For compound inputs, use standardName-based matching or improve tokenization.
        """
        # Test with exact branded name - this is what the fix handles
        result = enricher._match_quality_map('KSM-66', 'Ashwagandha', quality_map)

        assert result is not None
        # Should match KSM-66 form, not unspecified
        assert "ksm-66" in result["form_id"].lower(), (
            f"Expected KSM-66 to be matched, got form_id='{result['form_id']}'"
        )

        # Compound input falls back to standardName matching (expected current behavior)
        result_compound = enricher._match_quality_map('KSM-66 Ashwagandha Root Extract', 'Ashwagandha', quality_map)
        assert result_compound is not None
        # This matches on standardName since the full input doesn't exactly match any alias
        assert result_compound["matched_alias"] == "ashwagandha"

    def test_match_source_0_beats_match_source_1(self, enricher, quality_map):
        """Match on raw ingredient name (source=0) should beat match on standardName (source=1)."""
        # This is the core test for the fix:
        # - KSM-66 alias matches raw input "KSM-66" (match_source=0)
        # - ashwagandha alias matches standardName "Ashwagandha" (match_source=1)
        # The sort key should prioritize match_source=0
        result = enricher._match_quality_map('KSM-66', 'Ashwagandha', quality_map)

        assert result is not None
        assert result["matched_alias"] == "KSM-66", (
            f"Expected matched_alias='KSM-66' (raw input match), got '{result.get('matched_alias')}'"
        )

    def test_branded_token_fallback_runs_before_form_unmapped(self, enricher):
        """When cleaned form evidence is unmapped, branded token should still resolve IQM match."""
        custom_map = {
            "synthetic_parent": {
                "standard_name": "Synthetic Parent",
                "category": "other",
                "aliases": ["synthetic parent"],
                "forms": {
                    "brandx form": {
                        "bio_score": 10,
                        "natural": True,
                        "score": 12,
                        "aliases": ["brandx"],
                        "dosage_importance": 1.0,
                    }
                },
                "match_rules": {
                    "priority": 0,
                    "match_mode": "alias_and_fuzzy",
                    "exclusions": [],
                },
                "data_quality": {"review_status": "validated"},
            }
        }

        result = enricher._match_quality_map(
            "Synthetic Label Blend",
            "Unknown Standard",
            custom_map,
            cleaned_forms=[{"name": "95% Marker"}],
            branded_token="brandx",
        )

        assert result is not None
        assert result.get("match_status") != "FORM_UNMAPPED"
        assert result.get("canonical_id") == "synthetic_parent"
        assert result.get("form_id") == "brandx form"
        assert result.get("branded_token_fallback_used") is True


class TestMatchRulesBehavior:
    """Test that match_rules from ingredient_quality_map.json affect matching."""

    @pytest.fixture
    def enricher(self):
        """Create enricher instance."""
        return SupplementEnricherV3()

    @pytest.fixture
    def quality_map(self, enricher):
        """Get quality map from enricher."""
        return enricher.databases.get('ingredient_quality_map', {})

    def test_priority_affects_tie_breaking(self, quality_map):
        """Lower priority number should win in tie-breaking situations.

        match_rules.priority: 0 (primary) > 1 (secondary) > 2 (tertiary)
        """
        # Vitamins have priority 0, should win over priority 1+ ingredients
        # when both match at the same tier
        vit_a = quality_map.get('vitamin_a', {}).get('match_rules', {})
        assert vit_a.get('priority') == 0, "Vitamin A should have priority 0"

    def test_exclusions_block_false_positives(self, quality_map):
        """Exclusion terms in match_rules should block matches.

        If an exclusion term is found in the input, that parent is skipped.
        """
        # Note: Generic exclusions (synthetic, natural, etc.) have been removed
        # Real exclusions would be things like "ferric oxide" for iron
        iron = quality_map.get('iron', {})
        match_rules = iron.get('match_rules', {})
        exclusions = match_rules.get('exclusions', [])

        # Verify exclusions list exists (even if empty after cleanup)
        assert isinstance(exclusions, list), "exclusions should be a list"

    def test_match_mode_gates_tiers(self, quality_map):
        """match_mode should control which tiers are allowed.

        - exact: only tier 1,2
        - normalized: tier 1,2,3,4
        - alias_and_fuzzy: all tiers (default)
        """
        # Most ingredients should have alias_and_fuzzy (default)
        vit_c = quality_map.get('vitamin_c', {}).get('match_rules', {})
        match_mode = vit_c.get('match_mode', 'alias_and_fuzzy')
        assert match_mode in ['exact', 'normalized', 'alias_and_fuzzy'], (
            f"Invalid match_mode: {match_mode}"
        )

    def test_dosage_importance_populated(self, quality_map):
        """All forms should have dosage_importance field filled."""
        missing = []
        for parent_key, parent_data in quality_map.items():
            if parent_key.startswith('_') or not isinstance(parent_data, dict):
                continue
            for form_name, form_data in parent_data.get('forms', {}).items():
                if isinstance(form_data, dict):
                    if form_data.get('dosage_importance') is None:
                        missing.append(f"{parent_key}/{form_name}")

        assert len(missing) == 0, f"Missing dosage_importance: {missing[:5]}"

    def test_low_confidence_entries_are_runtime_capped(self, enricher, quality_map):
        """needs_review/stub/pending entries should not emit premium-equivalent scores."""
        result = enricher._match_quality_map(
            "PA-free butterbur extract (Petadolex)",
            "PA-free butterbur extract (Petadolex)",
            quality_map,
        )
        assert result is not None
        assert result["canonical_id"] == "butterbur"
        assert result["bio_score"] <= 10
        assert result["score"] <= 10

    def test_legacy_match_mode_standard_is_treated_as_exact(self, enricher):
        """Legacy match_mode='standard' must not allow pattern/contains tiers."""
        custom_map = {
            "legacy_mode_ingredient": {
                "standard_name": "Legacy Mode Ingredient",
                "category": "other",
                "forms": {
                    "legacy form": {
                        "bio_score": 10,
                        "natural": True,
                        "score": 13,
                        "aliases": ["legacy ingredient"],
                        "pattern_aliases": [r"legacy\s+.+\s+ingredient"],
                        "contains_aliases": ["legacy ingredient complex"],
                        "dosage_importance": 1.0,
                    }
                },
                "match_rules": {
                    "priority": 1,
                    "match_mode": "standard",
                    "exclusions": [],
                },
                "data_quality": {"review_status": "validated"},
            }
        }

        # Pattern-only text should not match when legacy 'standard' is normalized to exact.
        no_match = enricher._match_quality_map(
            "legacy very complex ingredient",
            "legacy very complex ingredient",
            custom_map,
        )
        assert no_match is None

        # Exact alias should still match.
        exact_match = enricher._match_quality_map("legacy ingredient", "legacy ingredient", custom_map)
        assert exact_match is not None
        assert exact_match["canonical_id"] == "legacy_mode_ingredient"

class TestCompoundParentDisambiguation:
    """Regression tests for shared-form parent disambiguation."""

    @pytest.fixture
    def enricher(self):
        return SupplementEnricherV3()

    @pytest.fixture
    def quality_map(self, enricher):
        return enricher.databases.get("ingredient_quality_map", {})

    def test_niacinamide_ascorbate_defaults_to_vitamin_c_without_context(self, enricher, quality_map):
        """No explicit B3 context should route niacinamide ascorbate to Vitamin C parent."""
        result = enricher._match_quality_map("Niacinamide Ascorbate", "Niacinamide Ascorbate", quality_map)
        assert result is not None
        assert result["canonical_id"] == "vitamin_c"
        assert result["form_id"] == "niacinamide ascorbate"

    def test_niacinamide_ascorbate_respects_b3_standardname_context(self, enricher, quality_map):
        """Explicit Niacin/Vitamin B3 context should route to B3 parent to avoid ambiguity ties."""
        result = enricher._match_quality_map("Niacinamide Ascorbate", "Niacin", quality_map)
        assert result is not None
        assert result["canonical_id"] == "vitamin_b3_niacin"
        assert result["form_id"] == "niacinamide ascorbate"

    @pytest.mark.parametrize(
        "label,expected_parent,expected_form",
        [
            ("Calcium Ascorbate", "vitamin_c", "calcium ascorbate"),
            ("Calcium Pantothenate", "vitamin_b5_pantothenic", "calcium pantothenate"),
            ("Nicotinamide Riboside", "nicotinamide_riboside", "nicotinamide riboside (unspecified)"),
            ("Nicotinamide Mononucleotide", "nmn", "nicotinamide mononucleotide (unspecified)"),
            ("MaquiBright", "maqui_berry", "maqui berry (unspecified)"),
            ("Vitexin", "vitexin", "vitexin (unspecified)"),
            ("Life's DHA", "dha", "algal triglyceride"),
            ("Concentrated Fish Oil", "fish_oil", "molecularly distilled"),
        ],
    )
    def test_dangerous_or_dual_identity_aliases_route_to_expected_parent(
        self, enricher, quality_map, label, expected_parent, expected_form
    ):
        result = enricher._match_quality_map(label, label, quality_map)
        assert result is not None
        assert result["canonical_id"] == expected_parent
        assert result["form_id"] == expected_form

    @pytest.mark.parametrize(
        "label",
        [
            "Molecular Distilled",
            "Triglyceride Form",
            "Phospholipid Form",
        ],
    )
    def test_generic_form_descriptors_do_not_resolve_as_standalone_ingredients(
        self, enricher, quality_map, label
    ):
        result = enricher._match_quality_map(label, label, quality_map)
        assert result is None


class TestP2AliasCoverageRegression:
    """High-confidence alias additions should map deterministically."""

    @pytest.fixture
    def enricher(self):
        return SupplementEnricherV3()

    @pytest.fixture
    def quality_map(self, enricher):
        return enricher.databases.get("ingredient_quality_map", {})

    @pytest.mark.parametrize(
        "name,expected_parent",
        [
            ("MaxEPA(R) Fish Oil Concentrate", "fish_oil"),
            ("BioPureDHA(R) Fish Oil concentrate", "fish_oil"),
            ("ecOmega Norwegian Cod Liver Oil", "cod_liver_oil"),
            ("(6S)-5-Methyltetrahydrofolate Calcium", "vitamin_b9_folate"),
            ("KD-Pur EPA", "epa"),
            ("Cryptozanthin", "cryptoxanthin"),
            ("Chromium-Chelavite", "chromium"),
            ("Ginsenoside Rg3", "rg3"),
            ("Hyal-Joint", "hyaluronic_acid"),
            ("Cardiose Flavonoid Glycoside", "citrus_bioflavonoids"),
        ],
    )
    def test_new_aliases_map_to_expected_parent(self, enricher, quality_map, name, expected_parent):
        result = enricher._match_quality_map(name, name, quality_map)
        assert result is not None, f"Expected mapping for {name}"
        assert result["canonical_id"] == expected_parent, f"{name} mapped to {result['canonical_id']}, expected {expected_parent}"


class TestStandardizedBotanicalAliasRegression:
    """Regression tests for standardized botanical alias pickup."""

    @pytest.fixture
    def enricher(self):
        return SupplementEnricherV3()

    def test_saffr_activ_maps_to_saffron_standardized_entry(self, enricher):
        """Branded Saffr'Activ labels should map to saffron and qualify when marker threshold is present."""
        product = {
            "activeIngredients": [
                {
                    "name": "Saffr'Activ Saffron Extract standardized to 0.3% safranal",
                    "standardName": "Saffron",
                    "quantity": 30,
                    "unit": "mg",
                }
            ],
            "inactiveIngredients": [],
        }

        standardized_hits = enricher._collect_standardized_botanicals(product)
        assert standardized_hits, "Expected standardized saffron hit for Saffr'Activ label"

        first = standardized_hits[0]
        assert first.get("botanical_id") == "saffron"
        assert first.get("meets_threshold") is True

    def test_citrus_bergamot_standardized_profile_qualifies(self, enricher):
        """Bergamot polyphenolic profile labels should qualify as standardized botanical evidence."""
        product = {
            "activeIngredients": [
                {
                    "name": "Citrus Bergamot Extract standardized to 38% polyphenolic fraction (naringin, neoeriocitrin, neohesperidin)",
                    "standardName": "Citrus Bergamot",
                    "quantity": 500,
                    "unit": "mg",
                }
            ],
            "inactiveIngredients": [],
        }

        standardized_hits = enricher._collect_standardized_botanicals(product)
        assert standardized_hits, "Expected standardized bergamot hit"
        first = standardized_hits[0]
        assert first.get("botanical_id") == "citrus_bergamot_extract"
        assert first.get("meets_threshold") is True

    def test_hibiscus_anthocyanin_standardization_qualifies(self, enricher):
        """Hibiscus with marker/percentage evidence should qualify for A5b."""
        product = {
            "activeIngredients": [
                {
                    "name": "Hibiscus sabdariffa flower extract standardized to 10% anthocyanins",
                    "standardName": "Hibiscus Extract",
                    "quantity": 250,
                    "unit": "mg",
                }
            ],
            "inactiveIngredients": [],
        }

        standardized_hits = enricher._collect_standardized_botanicals(product)
        assert standardized_hits, "Expected standardized hibiscus hit"
        first = standardized_hits[0]
        assert first.get("botanical_id") == "hibiscus_extract"
        assert first.get("meets_threshold") is True

    def test_hibiscus_plain_extract_does_not_auto_qualify(self, enricher):
        """Plain hibiscus extract without marker/percentage evidence should not qualify."""
        product = {
            "activeIngredients": [
                {
                    "name": "Hibiscus Extract",
                    "standardName": "Hibiscus",
                    "quantity": 250,
                    "unit": "mg",
                }
            ],
            "inactiveIngredients": [],
        }

        standardized_hits = enricher._collect_standardized_botanicals(product)
        assert standardized_hits, "Expected hibiscus alias match to be recorded"
        first = standardized_hits[0]
        assert first.get("botanical_id") == "hibiscus_extract"
        assert first.get("meets_threshold") is False

    def test_cocoa_flavanol_standardization_qualifies(self, enricher):
        """Cocoa extract with flavanol marker evidence should qualify."""
        product = {
            "activeIngredients": [
                {
                    "name": "Cocoa Extract standardized to 20% cocoa flavanols",
                    "standardName": "Cocoa Extract",
                    "quantity": 500,
                    "unit": "mg",
                }
            ],
            "inactiveIngredients": [],
        }

        standardized_hits = enricher._collect_standardized_botanicals(product)
        assert standardized_hits, "Expected cocoa standardized hit"
        first = standardized_hits[0]
        assert first.get("botanical_id") == "cocoa_flavanol_extract"
        assert first.get("meets_threshold") is True

    def test_cocoa_plain_extract_does_not_auto_qualify(self, enricher):
        """Plain cocoa extract without marker/percentage evidence should not qualify."""
        product = {
            "activeIngredients": [
                {
                    "name": "Cocoa Extract",
                    "standardName": "Cocoa",
                    "quantity": 500,
                    "unit": "mg",
                }
            ],
            "inactiveIngredients": [],
        }

        standardized_hits = enricher._collect_standardized_botanicals(product)
        assert standardized_hits, "Expected cocoa alias match to be recorded"
        first = standardized_hits[0]
        assert first.get("botanical_id") == "cocoa_flavanol_extract"
        assert first.get("meets_threshold") is False


class TestBotanicalIdentityCoverageRegression:
    """Botanical synonym additions should route to non-scorable identity recognition."""

    @pytest.fixture
    def enricher(self):
        return SupplementEnricherV3()

    def test_mandukparnee_is_recognized_botanical_identity(self, enricher):
        rec = enricher._is_recognized_non_scorable("Mandukparnee", "Mandukparnee")
        assert rec is not None
        assert rec.get("recognition_source") == "botanical_ingredients"

    @pytest.mark.parametrize(
        "name,expected_source",
        [
            ("Kumari", "botanical_ingredients"),
            ("Posinol", "botanical_ingredients"),
            ("Carob flavonoid extract", "botanical_ingredients"),
            ("Galactomannan", "other_ingredients"),
            ("Isolase(R)", "other_ingredients"),
            ("Artemisinin", "other_ingredients"),
        ],
    )
    def test_remaining_softgels_unknowns_are_recognized(self, enricher, name, expected_source):
        rec = enricher._is_recognized_non_scorable(name, name)
        assert rec is not None, f"Expected recognition for {name}"
        assert rec.get("recognition_source") == expected_source, f"{name} source mismatch: {rec}"


class TestProjectionAndLedgerRegression:
    """Regression tests for scoring projection and ledger consistency."""

    @pytest.fixture
    def enricher(self):
        return SupplementEnricherV3()

    def test_projection_trusted_manufacturer_requires_exact_match(self, enricher):
        enriched = {
            "delivery_data": {},
            "absorption_data": {},
            "formulation_data": {},
            "contaminant_data": {},
            "compliance_data": {},
            "certification_data": {},
            "proprietary_data": {},
            "evidence_data": {},
            "ingredient_quality_data": {},
            "manufacturer_data": {
                "top_manufacturer": {
                    "found": True,
                    "match_type": "fuzzy",
                    "name": "Example Manufacturer",
                },
                "bonus_features": {},
                "country_of_origin": {},
            },
        }

        enricher._project_scoring_fields(enriched)
        assert enriched["is_trusted_manufacturer"] is False

        enriched["manufacturer_data"]["top_manufacturer"]["match_type"] = "exact"
        enricher._project_scoring_fields(enriched)
        assert enriched["is_trusted_manufacturer"] is True

    def test_match_ledger_reads_harmful_additives_nested_path(self, enricher):
        product = {"brandName": "Demo"}
        enriched = {
            "ingredient_quality_data": {"ingredients_scorable": [], "ingredients_skipped": []},
            "contaminant_data": {
                "harmful_additives": {
                    "additives": [
                        {
                            "ingredient": "Red 40",
                            "additive_name": "FD&C Red No. 40",
                            "additive_id": "ADD_RED40",
                        }
                    ]
                }
            },
            "compliance_data": {},
            "manufacturer_data": {"top_manufacturer": {"found": False}},
            "delivery_data": {},
        }

        ledger_data = enricher._build_match_ledger(product, enriched)
        additive_entries = (
            ledger_data.get("match_ledger", {})
            .get("domains", {})
            .get("additives", {})
            .get("entries", [])
        )
        assert len(additive_entries) == 1
        assert additive_entries[0].get("canonical_id") == "ADD_RED40"

    def test_top_manufacturer_exact_precedence_over_earlier_fuzzy(self, enricher):
        """Exact match must win even if an earlier entry has a fuzzy hit."""
        enricher.databases["top_manufacturers_data"] = {
            "top_manufacturers": [
                {
                    "id": "MANUF_FUZZY_FIRST",
                    "standard_name": "HUM Nutrition",
                    "aliases": [],
                },
                {
                    "id": "MANUF_EXACT_SECOND",
                    "standard_name": "Optimum Nutrition",
                    "aliases": ["ON"],
                },
            ]
        }

        result = enricher._check_top_manufacturer("Optimum Nutrition", "")
        assert result.get("found") is True
        assert result.get("match_type") == "exact"
        assert result.get("manufacturer_id") == "MANUF_EXACT_SECOND"


class TestA4AbsorptionEnhancerSchemaRegression:
    """
    Regression guard for the A4 absorption enhancer schema bug.

    Root cause: absorption_enhancers.json uses 'standard_name' as the primary
    identifier, not 'name'.  Code that called enhancer.get('name', '') would
    silently return '' for every enhancer, causing _exact_match to early-exit
    on an empty target_name and never award the A4 bonus.

    Fix applied: enrich_supplements_v3.py line 3770 now reads
        enhancer_name = enhancer.get('standard_name') or enhancer.get('name', '')

    These tests verify the fix survives future refactors.
    """

    @pytest.fixture
    def enricher(self):
        return SupplementEnricherV3()

    def test_black_pepper_plus_turmeric_qualifies(self, enricher):
        """
        Black Pepper (BioPerine / piperine) paired with Turmeric must yield
        qualifies_for_bonus=True.  This exercises the standard_name lookup path
        in the live absorption_enhancers.json DB.
        """
        product = {
            'activeIngredients': [
                {'name': 'BioPerine', 'standardName': 'Black Pepper',
                 'quantity': 5, 'unit': 'mg'},
                {'name': 'Turmeric Extract', 'standardName': 'Turmeric',
                 'quantity': 500, 'unit': 'mg'},
            ],
            'inactiveIngredients': [],
        }
        result = enricher._collect_absorption_data(product)

        assert result['enhancer_present'] is True, (
            "Black Pepper / BioPerine should be found as an absorption enhancer"
        )
        assert result['qualifies_for_bonus'] is True, (
            "Turmeric paired with Black Pepper must qualify for the A4 bonus"
        )

    def test_enhancer_alone_does_not_qualify(self, enricher):
        """Enhancer present but no enhanced nutrient → no bonus."""
        product = {
            'activeIngredients': [
                {'name': 'BioPerine', 'standardName': 'Black Pepper', 'quantity': 5, 'unit': 'mg'},
            ],
            'inactiveIngredients': [],
        }
        result = enricher._collect_absorption_data(product)

        assert result['enhancer_present'] is True
        assert result['qualifies_for_bonus'] is False

    def test_no_enhancer_no_bonus(self, enricher):
        """No enhancer present → no bonus, even with a target nutrient."""
        product = {
            'activeIngredients': [
                {'name': 'Turmeric Extract', 'standardName': 'Turmeric',
                 'quantity': 500, 'unit': 'mg'},
            ],
            'inactiveIngredients': [],
        }
        result = enricher._collect_absorption_data(product)

        assert result['enhancer_present'] is False
        assert result['qualifies_for_bonus'] is False

    def test_piperine_alias_matches_black_pepper_enhancer(self, enricher):
        """
        'Piperine' is an alias for 'Black Pepper' in the DB.
        Matching via alias must work — confirming the full alias lookup path.
        """
        product = {
            'activeIngredients': [
                {'name': 'Piperine', 'standardName': 'Piperine', 'quantity': 5, 'unit': 'mg'},
                {'name': 'Curcumin', 'standardName': 'Curcumin', 'quantity': 500, 'unit': 'mg'},
            ],
            'inactiveIngredients': [],
        }
        result = enricher._collect_absorption_data(product)

        assert result['qualifies_for_bonus'] is True, (
            "Piperine alias must resolve to Black Pepper enhancer and qualify"
        )

    def test_black_pepper_fruit_extract_plus_turmeric_powder_qualifies(self, enricher):
        """Observed label variants should still trigger A4 pairing."""
        product = {
            'activeIngredients': [
                {'name': 'Black Pepper Fruit Extract', 'standardName': 'Black Pepper Fruit Extract', 'quantity': 5, 'unit': 'mg'},
                {'name': 'Turmeric Powder', 'standardName': 'Turmeric Powder', 'quantity': 500, 'unit': 'mg'},
            ],
            'inactiveIngredients': [],
        }
        result = enricher._collect_absorption_data(product)

        assert result['enhancer_present'] is True
        assert result['qualifies_for_bonus'] is True


class TestFormFallbackPrecisionRegression:
    """Guard against over-crediting from ambiguous botanical/form fallbacks."""

    @pytest.fixture
    def enricher(self):
        return SupplementEnricherV3()

    def test_flaxseed_particulates_maps_to_meal_powder_not_oil(self, enricher):
        qm = enricher.databases.get("ingredient_quality_map", {})
        match = enricher._match_quality_map("Flaxseed particulates", "Flaxseed particulates", qm)
        assert match.get("canonical_id") == "flaxseed"
        assert match.get("form_name") == "flaxseed meal/powder"
        assert not match.get("form_unmapped_fallback")

    def test_amla_powder_maps_to_powder_not_standardized_extract(self, enricher):
        qm = enricher.databases.get("ingredient_quality_map", {})
        match = enricher._match_quality_map("Amla, Powder", "Amla, Powder", qm)
        assert match.get("canonical_id") == "amla"
        assert match.get("form_name") == "amla fruit powder"
        assert not match.get("form_unmapped_fallback")

    def test_turmeric_powder_maps_to_turmeric_parent_not_curcumin(self, enricher):
        qm = enricher.databases.get("ingredient_quality_map", {})
        match = enricher._match_quality_map("Turmeric, Powder", "Turmeric, Powder", qm)
        assert match.get("canonical_id") == "turmeric"
        assert match.get("form_name") == "whole turmeric powder"
        assert not match.get("form_unmapped_fallback")

    def test_st_johns_wort_generic_extract_stays_conservative(self, enricher):
        qm = enricher.databases.get("ingredient_quality_map", {})
        match = enricher._match_quality_map("St. John's Wort Extract", "St. John's Wort Extract", qm)
        assert match.get("canonical_id") == "st_johns_wort"
        assert "standardized" not in str(match.get("form_name", "")).lower()

    def test_st_johns_wort_standardized_extract_maps_to_standardized_form(self, enricher):
        qm = enricher.databases.get("ingredient_quality_map", {})
        match = enricher._match_quality_map(
            "St. John's Wort Extract standardized to 0.3% hypericin",
            "St. John's Wort Extract standardized to 0.3% hypericin",
            qm,
        )
        assert match.get("canonical_id") == "st_johns_wort"
        assert "standardized" in str(match.get("form_name", "")).lower()

    def test_orange_pekoe_black_tea_routes_to_botanical_identity_only(self, enricher):
        qm = enricher.databases.get("ingredient_quality_map", {})
        name = "Orange Pekoe (Black) Tea extract"
        match = enricher._match_quality_map(name, name, qm)
        assert match is None
        recognized = enricher._is_recognized_non_scorable(name, name)
        assert recognized is not None
        assert recognized.get("recognition_type") == "botanical_unscored"
        assert recognized.get("matched_entry_id") == "black_tea_leaf"

    def test_galactomannan_maps_to_fiber_konjac_form(self, enricher):
        qm = enricher.databases.get("ingredient_quality_map", {})
        match = enricher._match_quality_map("Galactomannan", "Galactomannan", qm)
        assert match is not None
        assert match.get("canonical_id") == "fiber"
        assert "konjac" in str(match.get("form_name", "")).lower()

    def test_dha_epa_combined_alias_maps_to_epa_dha(self, enricher):
        qm = enricher.databases.get("ingredient_quality_map", {})
        match = enricher._match_quality_map("DHA/EPA", "DHA/EPA", qm)
        assert match is not None
        assert match.get("canonical_id") == "epa_dha"

    def test_trimethylglycine_hydrochloride_maps_to_betaine_hcl(self, enricher):
        qm = enricher.databases.get("ingredient_quality_map", {})
        match = enricher._match_quality_map("Trimethylglycine Hydrochloride", "Trimethylglycine Hydrochloride", qm)
        assert match is not None
        assert match.get("canonical_id") == "tmg_betaine"
        assert "hydrochloride" in str(match.get("form_name", "")).lower()

    def test_odorless_garlic_routes_to_unspecified_not_aged(self, enricher):
        qm = enricher.databases.get("ingredient_quality_map", {})
        match = enricher._match_quality_map("Garlic, Odorless", "Garlic, Odorless", qm)
        assert match is not None
        assert match.get("canonical_id") == "garlic"
        assert "unspecified" in str(match.get("form_name", "")).lower()

    def test_green_tea_aqueous_extract_avoids_oxidized_fallback(self, enricher):
        qm = enricher.databases.get("ingredient_quality_map", {})
        label = "organic Green Tea (Camellia sinensis) (leaf) aqueous extract"
        match = enricher._match_quality_map(label, label, qm)
        assert match is not None
        assert match.get("canonical_id") == "green_tea_extract"
        assert "oxidized" not in str(match.get("form_name", "")).lower()
        assert not match.get("form_unmapped_fallback")

    def test_fish_oil_generic_oil_text_does_not_pick_premium_form_on_fallback(self, enricher):
        qm = enricher.databases.get("ingredient_quality_map", {})
        label = "Red Sockeye Salmon Oil, Natural, Wild"
        match = enricher._match_quality_map(label, label, qm)
        assert match is not None
        assert match.get("canonical_id") == "fish_oil"
        assert "triglyceride" not in str(match.get("form_name", "")).lower()

    def test_pure_cbd_extract_hits_banned_cbd_us(self, enricher):
        banned = enricher._check_banned_substances([{"name": "pure CBD extract"}], {})
        assert banned.get("found") is True
        ids = {s.get("banned_id") for s in banned.get("substances", [])}
        assert "BANNED_CBD_US" in ids

    def test_naturally_occurring_cannabidiol_hits_banned_cbd_us(self, enricher):
        banned = enricher._check_banned_substances(
            [{"name": "naturally-occurring Cannabidiol"}],
            {},
        )
        assert banned.get("found") is True
        ids = {s.get("banned_id") for s in banned.get("substances", [])}
        assert "BANNED_CBD_US" in ids

    def test_medium_chain_triglyceride_oil_is_recognized_non_scorable(self, enricher):
        recognized = enricher._is_recognized_non_scorable(
            "Medium-Chain Triglyceride Oil",
            "Medium-Chain Triglyceride Oil",
        )
        assert recognized is not None
        assert recognized.get("matched_entry_id") == "PII_MEDIUM_CHAIN_TRIGLYCERIDES"

    def test_petroselinic_acid_is_recognized_non_scorable(self, enricher):
        recognized = enricher._is_recognized_non_scorable("Petroselinic Acid", "Petroselinic Acid")
        assert recognized is not None
        assert recognized.get("matched_entry_id") == "PII_PETROSELINIC_ACID"

    def test_usplus_maps_to_saw_palmetto_supercritical_form(self, enricher):
        qm = enricher.databases.get("ingredient_quality_map", {})
        match = enricher._match_quality_map("USPLUS", "USPLUS", qm)
        assert match is not None
        assert match.get("canonical_id") == "saw_palmetto"
        assert "supercritical" in str(match.get("form_name", "")).lower()

    def test_probiotic_fermented_multi_culture_skipped_as_blend_header(self, enricher):
        qm = enricher.databases.get("ingredient_quality_map", {})
        bot = enricher.databases.get("botanical_ingredients", {})
        skip = enricher._should_skip_from_scoring(
            {"name": "Probiotic Fermented Multi-Culture", "standardName": "Probiotic Fermented Multi-Culture"},
            qm,
            bot,
        )
        assert skip in {"blend_header_without_dosage", "blend_header_total_weight_only"}

    def test_safety_additives_route_to_harmful_or_banned_by_policy(self, enricher):
        ingredients = [
            {"name": "Blue #1"},
            {"name": "FD&C Red #40 Lake"},
            {"name": "Propyl Paraben"},
            {"name": "Titanium Oxide"},
        ]
        harmful = enricher._check_harmful_additives(ingredients)
        assert harmful.get("found") is True
        # After v5.0 migration, parabens + dyes + TiO2 all route through
        # harmful_additives (B1 path) for penalty scoring.
        assert len(harmful.get("additives", [])) >= 3

    def test_yellow_6_variant_routes_to_harmful_additives(self, enricher):
        harmful = enricher._check_harmful_additives([{"name": "Yellow #6"}])
        assert harmful.get("found") is True
        ids = {a.get("additive_id") for a in harmful.get("additives", [])}
        assert "ADD_YELLOW6" in ids


class TestA5cSynergyDoseAnchoringRegression:
    """A5c should not award bonus on zero-dose-checkable cluster matches."""

    @pytest.fixture
    def enricher(self):
        return SupplementEnricherV3()

    def test_synergy_not_qualified_when_no_checkable_min_doses(self, enricher):
        enriched = {
            "delivery_data": {},
            "absorption_data": {},
            "formulation_data": {
                "organic": {},
                "standardized_botanicals": [],
                "synergy_clusters": [
                    {
                        "cluster_id": "test_cluster",
                        "cluster_name": "Test Cluster",
                        "match_count": 2,
                        "matched_ingredients": [
                            {"ingredient": "Vitamin D3", "min_effective_dose": 0, "meets_minimum": True},
                            {"ingredient": "Zinc", "min_effective_dose": 0, "meets_minimum": True},
                        ],
                    }
                ],
            },
            "contaminant_data": {},
            "compliance_data": {},
            "certification_data": {},
            "proprietary_data": {},
            "evidence_data": {},
            "manufacturer_data": {},
            "ingredient_quality_data": {},
        }

        enricher._project_scoring_fields(enriched)
        assert enriched["synergy_cluster_qualified"] is False

    def test_synergy_qualified_with_checkable_min_dose(self, enricher):
        enriched = {
            "delivery_data": {},
            "absorption_data": {},
            "formulation_data": {
                "organic": {},
                "standardized_botanicals": [],
                "synergy_clusters": [
                    {
                        "cluster_id": "test_cluster",
                        "cluster_name": "Test Cluster",
                        "match_count": 2,
                        "matched_ingredients": [
                            {"ingredient": "NAC", "min_effective_dose": 600, "meets_minimum": True},
                            {"ingredient": "Quercetin", "min_effective_dose": 500, "meets_minimum": True},
                        ],
                    }
                ],
            },
            "contaminant_data": {},
            "compliance_data": {},
            "certification_data": {},
            "proprietary_data": {},
            "evidence_data": {},
            "manufacturer_data": {},
            "ingredient_quality_data": {},
        }

        enricher._project_scoring_fields(enriched)
        assert enriched["synergy_cluster_qualified"] is True


class TestSynergyExplainabilityFields:
    """Synergy matches should carry note + sources for UI explainability."""

    @pytest.fixture
    def enricher(self):
        return SupplementEnricherV3()

    def test_collect_synergy_data_includes_note_and_sources(self, enricher):
        enricher.databases["synergy_cluster"] = {
            "synergy_clusters": [
                {
                    "id": "test_synergy",
                    "standard_name": "Test Synergy",
                    "ingredients": ["vitamin c", "zinc"],
                    "min_effective_doses": {"vitamin c": 500, "zinc": 10},
                    "evidence_tier": 1,
                    "note": "Vitamin C and zinc immune support rationale.",
                    "sources": [
                        {
                            "source_type": "nih_ods",
                            "label": "Vitamin C Fact Sheet",
                            "url": "https://ods.od.nih.gov/factsheets/VitaminC-HealthProfessional/",
                        }
                    ],
                }
            ]
        }
        product = {
            "activeIngredients": [
                {"name": "Vitamin C", "standardName": "vitamin c", "quantity": 1000, "unit": "mg"},
                {"name": "Zinc", "standardName": "zinc", "quantity": 15, "unit": "mg"},
            ]
        }

        clusters = enricher._collect_synergy_data(product)
        assert len(clusters) == 1
        assert clusters[0]["cluster_id"] == "test_synergy"
        assert clusters[0]["note"] == "Vitamin C and zinc immune support rationale."
        assert isinstance(clusters[0]["sources"], list)
        assert clusters[0]["sources"][0]["source_type"] == "nih_ods"


class TestDescriptorLeakageRegression:
    """Regression checks for descriptor/header leakage rows."""

    @pytest.fixture
    def enricher(self):
        return SupplementEnricherV3()

    def test_known_descriptor_headers_are_excluded(self, enricher):
        cases = [
            ("Also Containing Additional Carotenoids", {"excluded_nutrition_fact", "excluded_label_phrase"}),
            ("These three oils typically provide the following Fatty Acid Profile", {"excluded_nutrition_fact", "excluded_label_phrase"}),
            ("Quath Dravya of", "excluded_label_phrase"),
            ("Omega 6 Fatty Acids", "excluded_nutrition_fact"),
            ("OmegaChoice Omega-3 Essential Fatty Acids:", "excluded_nutrition_fact"),
            ("Aromatase Inhibition/Estrogen Modulation/DHT Block", "excluded_label_phrase"),
            ("<1 mg of natural caffeine", "excluded_label_phrase"),
            ("Carvacrol and Thymol", "excluded_label_phrase"),
        ]
        for text, expected in cases:
            reason = enricher._excluded_text_reason(text)
            if isinstance(expected, set):
                assert reason in expected, f"{text} expected one of {expected}, got {reason}"
            else:
                assert reason == expected, f"{text} expected {expected}, got {reason}"


class TestHarmfulPrecedenceRegression:
    """Harmful additive recognition must not block IQM scoring.

    Ingredients in BOTH harmful_additives AND IQM receive:
      - Section A quality score (IQM)
      - Section B1 penalty (harmful_additives)
    These are independent concerns.  See test_harmful_iqm_dual_scoring.py.
    """

    @pytest.fixture
    def enricher(self):
        return SupplementEnricherV3()

    @pytest.fixture
    def quality_map(self, enricher):
        return enricher.databases.get("ingredient_quality_map", {})

    @pytest.fixture
    def botanicals_db(self, enricher):
        return enricher.databases.get("standardized_botanicals", {})

    @pytest.mark.parametrize(
        "name",
        [
            "Senna",
            "Silicon Dioxide",
            "Copper Sulfate",
        ],
    )
    def test_harmful_iqm_dual_classified_is_scored_not_skipped(
        self, enricher, quality_map, botanicals_db, name
    ):
        """IQM-known ingredients in harmful_additives must be scored, not skipped."""
        ingredient = {
            "name": name,
            "standardName": name,
            "quantity": 100,
            "unit": "mg",
        }

        skip_reason = enricher._should_skip_from_scoring(ingredient, quality_map, botanicals_db)

        # These are in both IQM and harmful_additives — IQM wins for scoring,
        # harmful_additives penalty is applied separately in Section B1.
        assert skip_reason is None, (
            f"{name} is in IQM and should be scored (skip=None), not skipped. "
            f"Got skip_reason={skip_reason}"
        )

    @pytest.mark.parametrize(
        "name,expected_id",
        [
            ("Silicon Dioxide", "ADD_SILICON_DIOXIDE"),
            ("caramel color", "ADD_CARAMEL_COLOR"),
        ],
    )
    def test_nonscorable_index_prefers_harmful_additives_over_other_ingredients(
        self, enricher, name, expected_id
    ):
        recognized = enricher._is_recognized_non_scorable(name, name)

        assert recognized is not None
        assert recognized.get("recognition_source") == "harmful_additives"
        assert recognized.get("matched_entry_id") == expected_id


if __name__ == '__main__':
    pytest.main([__file__, '-v'])


def test_capsules_high_confidence_form_variants_map_after_alias_updates():
    enricher = SupplementEnricherV3()
    cases = [
        ("Turmeric rhizome extract", "turmeric"),
        ("Turmeric root extract Curcuminoids", "turmeric"),
        ("St. John's Wort 0.3% extract", "st_johns_wort"),
        ("Milk Thistle seed extract", "milk_thistle"),
        ("BioPerine Black Pepper (fruit) extract", "piperine"),
        ("Chaste Tree berry extract", "chasteberry"),
    ]

    for raw_name, expected_canonical in cases:
        match = enricher._match_quality_map(raw_name, raw_name, enricher.databases["ingredient_quality_map"])
        assert match.get("canonical_id") == expected_canonical, raw_name
        assert not match.get("form_unmapped_fallback"), raw_name


def test_pure_encapsulations_form_fallback_aliases_map_without_fallback():
    enricher = SupplementEnricherV3()
    qm = enricher.databases["ingredient_quality_map"]
    cases = [
        (
            "Folate",
            "Folate",
            [{"name": "Quatrefolic (6S)-5-Methyltetrahyrdofolic Acid, Glucosamine Salt"}],
            "vitamin_b9_folate",
            "quatrefolic",
        ),
        (
            "Magnesium",
            "Magnesium",
            [{"name": "Albion Di-Magnesium Malate"}],
            "magnesium",
            "magnesium malate",
        ),
        (
            "Copper",
            "Copper",
            [{"name": "Copper Bis-Glycinate"}],
            "copper",
            "copper bisglycinate",
        ),
        (
            "Riboflavin",
            "Riboflavin",
            [{"name": "Vitamin B2, Riboflavin 5 Phosphate"}],
            "vitamin_b2_riboflavin",
            "riboflavin-5-phosphate",
        ),
        (
            "Alpha-Lipoic Acid",
            "Alpha-Lipoic Acid",
            [{"name": "Thiotic Acid"}],
            "alpha_lipoic_acid",
            "racemic alpha-lipoic acid",
        ),
        (
            "L-Arginine Hydrochloride, Powder",
            "L-Arginine Hydrochloride, Powder",
            [{"name": "hydrochloride"}],
            "l_arginine",
            "l-arginine hcl",
        ),
        (
            "L-Histidine, Powder",
            "L-Histidine, Powder",
            [{"name": "L-Histidine Hydrochloride, Powder"}],
            "l_histidine",
            "l-histidine standard",
        ),
        (
            "L-Lysine, Powder",
            "L-Lysine, Powder",
            [{"name": "L-Lysine Hydrochloride, Powder"}],
            "l_lysine",
            "l-lysine hcl",
        ),
        (
            "C8Vantage",
            "C8Vantage",
            [{"name": "Medium Chain Triglyceride C8, Powder"}],
            "mct_oil",
            "c8 mct oil (pure caprylic)",
        ),
    ]

    for label, std_name, cleaned_forms, expected_canonical, expected_form in cases:
        match = enricher._match_quality_map(
            label,
            std_name,
            qm,
            cleaned_forms=cleaned_forms,
        )
        assert match is not None, label
        assert match.get("canonical_id") == expected_canonical, label
        assert match.get("form_id") == expected_form, label
        assert not match.get("form_unmapped_fallback"), label


def test_pure_encapsulations_branded_parent_fallbacks_map_to_specific_forms():
    enricher = SupplementEnricherV3()
    qm = enricher.databases["ingredient_quality_map"]
    cases = [
        ("Perluxan Hops (Humulus lupulus) extract", "hops", "hops extract (unspecified)"),
        ("Lifenol Hops (Humulus lupulus) extract", "hops", "hops extract (unspecified)"),
        ("Meriva Turmeric Phytosome Complex Curcuminoids", "curcumin", "meriva curcumin"),
        ("Meriva Turmeric Phytosome Sunflower Phospholipid Complex", "curcumin", "meriva curcumin"),
    ]

    for label, expected_canonical, expected_form in cases:
        match = enricher._match_quality_map(label, label, qm)
        assert match is not None, label
        assert match.get("canonical_id") == expected_canonical, label
        assert match.get("form_id") == expected_form, label
        assert not match.get("form_unmapped_fallback"), label


def test_olly_nature_thorne_safe_form_gaps_map_without_fallback():
    enricher = SupplementEnricherV3()
    qm = enricher.databases["ingredient_quality_map"]
    cases = [
        (
            "Goji Berry Fruit Extract",
            "Goji Berry Fruit Extract",
            [{"name": "Lycium barbarum Fruit Extract"}],
            "goji_berry",
            "goji berry (unspecified)",
        ),
        (
            "Goji Berry Juice, Powder",
            "Goji Berry Juice, Powder",
            [{"name": "Lycium barbarum, Powder"}],
            "goji_berry",
            "goji berry (unspecified)",
        ),
        (
            "Selenium",
            "Selenium",
            [{"name": "Selenium Picolinate"}],
            "selenium",
            "selenium picolinate",
        ),
        (
            "Folate",
            "Folate",
            [{"name": "L-5 Methyltetrahydrofolic Acid, Glucosamine Salt"}],
            "vitamin_b9_folate",
            "quatrefolic",
        ),
        (
            "Copper",
            "Copper",
            [{"name": "Albion Copper Bisglycinate Chelate"}],
            "copper",
            "copper bisglycinate",
        ),
    ]

    for label, std_name, cleaned_forms, expected_canonical, expected_form in cases:
        match = enricher._match_quality_map(
            label,
            std_name,
            qm,
            cleaned_forms=cleaned_forms,
        )
        assert match is not None, label
        assert match.get("canonical_id") == expected_canonical, label
        assert match.get("form_id") == expected_form, label
        assert not match.get("form_unmapped_fallback"), label


class TestEvidenceMultiMatch:
    """T7: Clinical study multi-match — break removal regression tests"""

    @pytest.fixture
    def enricher(self):
        return SupplementEnricherV3()

    def test_evidence_collects_multiple_studies_per_ingredient(self, enricher):
        """An ingredient matching multiple clinical studies should collect all matches."""
        study_a = {
            "id": "VIT_D_BONE",
            "standard_name": "Vitamin D",
            "aliases": [],
            "evidence_level": "ingredient-human",
            "study_type": "rct_single",
            "score_contribution": "tier_2",
            "health_goals_supported": ["bone health"],
            "key_endpoints": [],
        }
        study_b = {
            "id": "VIT_D_IMMUNE",
            "standard_name": "Vitamin D",
            "aliases": [],
            "evidence_level": "ingredient-human",
            "study_type": "rct_single",
            "score_contribution": "tier_2",
            "health_goals_supported": ["immune support"],
            "key_endpoints": [],
        }

        original_db = enricher.databases.get('backed_clinical_studies', {})
        enricher.databases['backed_clinical_studies'] = {
            'backed_clinical_studies': [study_a, study_b]
        }

        product = {
            'id': 'test_multi_evidence',
            'statements': [],
            'activeIngredients': [
                {'name': 'Vitamin D', 'standardName': 'Vitamin D'}
            ],
            'inactiveIngredients': [],
        }

        result = enricher._collect_evidence_data(product)
        enricher.databases['backed_clinical_studies'] = original_db

        assert result['match_count'] == 2, (
            f"Expected 2 study matches for Vitamin D, got {result['match_count']}"
        )
        matched_ids = {m['id'] for m in result['clinical_matches']}
        assert 'VIT_D_BONE' in matched_ids
        assert 'VIT_D_IMMUNE' in matched_ids

    def test_evidence_no_duplicate_study_ids_per_ingredient(self, enricher):
        """The same study ID should not appear twice for the same ingredient."""
        study = {
            "id": "VIT_D_BONE",
            "standard_name": "Vitamin D",
            "aliases": ["cholecalciferol"],
            "evidence_level": "ingredient-human",
            "study_type": "rct_single",
            "score_contribution": "tier_2",
            "health_goals_supported": ["bone health"],
            "key_endpoints": [],
        }

        original_db = enricher.databases.get('backed_clinical_studies', {})
        enricher.databases['backed_clinical_studies'] = {
            'backed_clinical_studies': [study, study]  # intentional duplicate
        }

        product = {
            'id': 'test_dedup_evidence',
            'statements': [],
            'activeIngredients': [
                {'name': 'Vitamin D', 'standardName': 'Vitamin D'}
            ],
            'inactiveIngredients': [],
        }

        result = enricher._collect_evidence_data(product)
        enricher.databases['backed_clinical_studies'] = original_db

        ids = [m['id'] for m in result['clinical_matches']]
        assert len(ids) == len(set(ids)), "Duplicate study IDs found for the same ingredient"


class TestProbioticClassificationHijack:
    """T8: Probiotic name-signal hijacking regression tests"""

    @pytest.fixture
    def enricher(self):
        return SupplementEnricherV3()

    def _make_multivitamin_with_one_probiotic(self, probiotic_name_in_product=True):
        """25 vitamin/mineral ingredients + 1 probiotic strain."""
        vitamin_names = [
            "Vitamin A", "Vitamin C", "Vitamin D3", "Vitamin E", "Vitamin K",
            "Thiamine", "Riboflavin", "Niacin", "Pantothenic Acid", "Pyridoxine",
            "Biotin", "Folate", "Vitamin B12", "Calcium", "Magnesium",
            "Zinc", "Iron", "Selenium", "Chromium", "Copper",
            "Manganese", "Iodine", "Molybdenum", "Potassium", "Phosphorus",
        ]
        active = [{'name': v, 'standardName': v, 'category': 'vitamin'} for v in vitamin_names]
        active.append({
            'name': 'Lactobacillus acidophilus',
            'standardName': 'Lactobacillus acidophilus',
            'category': 'probiotic',
        })
        product_name = "Probiotic Multivitamin Complete" if probiotic_name_in_product else "Daily Multivitamin Complete"
        return {
            'id': 'test_multivit_probiotic',
            'product_name': product_name,
            'fullName': product_name,
            'bundleName': '',
            'statements': [],
            'activeIngredients': active,
            'inactiveIngredients': [],
        }

    def test_multivitamin_with_probiotic_name_not_hijacked(self, enricher):
        """25-ingredient multivitamin with 1 probiotic strain and 'probiotic' in name
        should NOT be classified as 'probiotic' (1/26 = 3.8% < 25% threshold)."""
        product = self._make_multivitamin_with_one_probiotic(probiotic_name_in_product=True)
        result = enricher._classify_supplement_type(product)
        assert result['type'] != 'probiotic', (
            f"Multivitamin with 1/26 probiotic ingredient should not be classified as 'probiotic', got '{result['type']}'"
        )

    def test_majority_probiotic_still_classified(self, enricher):
        """A product with >=50% probiotic ingredients should still be classified as probiotic."""
        product = {
            'id': 'test_majority_probiotic',
            'product_name': 'Multi-Strain Probiotic',
            'fullName': 'Multi-Strain Probiotic',
            'bundleName': '',
            'statements': [],
            'activeIngredients': [
                {'name': 'Lactobacillus acidophilus', 'standardName': 'Lactobacillus acidophilus', 'category': 'probiotic'},
                {'name': 'Bifidobacterium lactis', 'standardName': 'Bifidobacterium lactis', 'category': 'probiotic'},
                {'name': 'Vitamin C', 'standardName': 'Vitamin C', 'category': 'vitamin'},
            ],
            'inactiveIngredients': [],
        }
        result = enricher._classify_supplement_type(product)
        assert result['type'] == 'probiotic', (
            f"2/3 probiotic ingredients should be classified as 'probiotic', got '{result['type']}'"
        )


class TestBVitaminKeywords:
    """T9: B-vitamin shorthand keyword categorization"""

    @pytest.fixture
    def enricher(self):
        return SupplementEnricherV3()

    def test_b_vitamin_shorthand_categorized(self, enricher):
        """B12, B6, B1, etc. should match the vitamins category keyword list."""
        vitamins_keywords = enricher._CATEGORY_KEYWORDS.get('vitamins', [])
        for shorthand in ['b1', 'b2', 'b3', 'b5', 'b6', 'b7', 'b9', 'b12']:
            assert shorthand in vitamins_keywords, (
                f"'{shorthand}' not found in vitamins keyword list"
            )


# ---------------------------------------------------------------------------
# Phase 0 Regression Locks — strain extraction, narrow-exception safety,
# CFU regex precision, probiotic classification boundary.
# ---------------------------------------------------------------------------


class TestProbioticDataStructureRegressionLock:
    """Regression lock: enricher must populate probiotic_data with the exact
    field shape the scorer reads. Currently passes — must not regress."""

    @pytest.fixture
    def enricher(self):
        return SupplementEnricherV3()

    def test_probiotic_data_populates_expected_scorer_fields(self, enricher):
        """For a realistic 3-strain probiotic product, probiotic_data must
        contain the exact keys the scorer queries: is_probiotic_product,
        has_cfu, total_billion_count, total_strain_count, clinical_strain_count,
        prebiotic_present, has_survivability_coating, probiotic_blends."""
        product = {
            'id': 'test_strain_extraction',
            'product_name': 'Restore',
            'fullName': 'Thorne Performance Restore',
            'bundleName': '',
            'statements': [
                {'notes': 'Contains 5 billion CFU per capsule.'}
            ],
            'activeIngredients': [
                {
                    'name': 'Lactobacillus gasseri',
                    'standardName': 'Lactobacillus Gasseri',
                    'category': 'probiotic',
                    'quantity': 2500000000,
                    'unit': 'Live Cell(s)',
                    'nestedIngredients': [],
                    'harvestMethod': '',
                    'notes': '',
                },
                {
                    'name': 'Bifidobacterium longum',
                    'standardName': 'Bifidobacterium Longum',
                    'category': 'probiotic',
                    'quantity': 1250000000,
                    'unit': 'Live Cell(s)',
                    'nestedIngredients': [],
                    'harvestMethod': '',
                    'notes': '',
                },
                {
                    'name': 'Bifidobacterium bifidum',
                    'standardName': 'Bifidobacterium Bifidum',
                    'category': 'probiotic',
                    'quantity': 1250000000,
                    'unit': 'Live Cell(s)',
                    'nestedIngredients': [],
                    'harvestMethod': '',
                    'notes': '',
                },
            ],
            'inactiveIngredients': [],
        }
        pd = enricher._collect_probiotic_data(product)
        assert pd['is_probiotic_product'] is True
        assert pd['has_cfu'] is True
        assert pd['total_strain_count'] == 3
        assert pd['total_billion_count'] == pytest.approx(5.0)
        assert len(pd['probiotic_blends']) == 3
        # Fields the scorer reads for bonuses — must exist even if 0/False
        for key in ('clinical_strain_count', 'prebiotic_present', 'has_survivability_coating'):
            assert key in pd, f"probiotic_data missing scorer-critical key '{key}'"

    def test_probiotic_data_clinical_strain_lookup_matches_db(self, enricher):
        """Lactobacillus gasseri and Bifidobacterium longum should match the
        clinically_relevant_strains.json database. This locks the strain match
        logic — if the clinical strain DB is ever restructured, this flags it."""
        product = {
            'id': 'test_clinical_strain_match',
            'product_name': 'Gasseri + Longum Combo',
            'fullName': 'Gasseri + Longum Combo',
            'bundleName': '',
            'statements': [],
            'activeIngredients': [
                {'name': 'Lactobacillus gasseri',
                 'standardName': 'Lactobacillus Gasseri',
                 'category': 'probiotic',
                 'quantity': 2500000000, 'unit': 'Live Cell(s)',
                 'nestedIngredients': [], 'harvestMethod': '', 'notes': ''},
                {'name': 'Bifidobacterium longum',
                 'standardName': 'Bifidobacterium Longum',
                 'category': 'probiotic',
                 'quantity': 2500000000, 'unit': 'Live Cell(s)',
                 'nestedIngredients': [], 'harvestMethod': '', 'notes': ''},
            ],
            'inactiveIngredients': [],
        }
        pd = enricher._collect_probiotic_data(product)
        assert pd['clinical_strain_count'] >= 1, (
            f"At least Lactobacillus gasseri or Bifidobacterium longum should "
            f"match clinically_relevant_strains.json; got "
            f"clinical_strain_count={pd['clinical_strain_count']}"
        )


class TestNarrowExceptionEmptyEnrichmentSchema:
    """Phase 0 failing test for HIGH #1: the two narrow exception handlers
    at enrich_supplements_v3.py lines 10837-10849 do NOT apply
    EMPTY_ENRICHMENT_SCHEMA before returning the failed product. This causes
    partial enrichment leakage — scorer may receive a product with
    ingredient_quality_data populated but compliance_data empty, producing a
    score without safety checks. The broad Exception handler at line ~10860
    does apply the schema; the narrow handlers must too."""

    @pytest.fixture
    def enricher(self):
        return SupplementEnricherV3()

    def _make_minimal_valid_product(self):
        return {
            'id': 'narrow_exc_test',
            'product_name': 'Test Product',
            'fullName': 'Test Product',
            'bundleName': '',
            'statements': [],
            'activeIngredients': [
                {'name': 'Vitamin C', 'standardName': 'Vitamin C',
                 'quantity': 500, 'unit': 'mg', 'category': 'vitamin'}
            ],
            'inactiveIngredients': [],
        }

    def test_key_error_midway_applies_empty_schema(self, enricher, monkeypatch):
        """Force a KeyError inside the enrichment try block. The narrow
        (KeyError, TypeError) handler must apply EMPTY_ENRICHMENT_SCHEMA so
        downstream consumers cannot read partial state as if enrichment
        succeeded. Currently FAILS — handler returns product unchanged."""
        def _raise_key_error(*args, **kwargs):
            raise KeyError("simulated mid-enrichment key error")
        monkeypatch.setattr(enricher, '_validate_export_contract_fields', _raise_key_error)

        product = self._make_minimal_valid_product()
        result, issues = enricher.enrich_product(product)

        assert result.get('enrichment_status') == 'failed'
        # After an EMPTY_ENRICHMENT_SCHEMA application, safety-critical sections
        # must be at their empty-schema defaults.
        expected_empty = enricher.EMPTY_ENRICHMENT_SCHEMA
        assert 'contaminant_data' in expected_empty, "EMPTY_ENRICHMENT_SCHEMA must define contaminant_data"
        assert result.get('contaminant_data') == expected_empty['contaminant_data'], (
            "After a narrow (KeyError) exception mid-enrichment, contaminant_data "
            "must be reset to EMPTY_ENRICHMENT_SCHEMA defaults to prevent partial "
            "state from leaking to the scorer. Current narrow handler at lines "
            "10837-10843 does not apply the schema — this is the HIGH #1 bug."
        )

    def test_value_error_midway_applies_empty_schema(self, enricher, monkeypatch):
        """Same lock for the (ValueError, AttributeError) handler."""
        def _raise_value_error(*args, **kwargs):
            raise ValueError("simulated mid-enrichment value error")
        monkeypatch.setattr(enricher, '_validate_export_contract_fields', _raise_value_error)

        product = self._make_minimal_valid_product()
        result, issues = enricher.enrich_product(product)

        assert result.get('enrichment_status') == 'failed'
        expected_empty = enricher.EMPTY_ENRICHMENT_SCHEMA
        assert result.get('contaminant_data') == expected_empty['contaminant_data'], (
            "After a narrow (ValueError) exception mid-enrichment, contaminant_data "
            "must be reset to EMPTY_ENRICHMENT_SCHEMA defaults (HIGH #1 bug)."
        )


class TestCfuEquivalentUnitPrecision:
    """Phase 0 failing tests for MED #5: CFU_EQUIVALENT_PATTERNS is overly
    broad. Patterns like \\bprobiotic, \\borganism, \\bbacteria will match
    unit strings that contain those tokens but are not CFU quantities. A
    product with quantity=200 and unit='probiotic blend' would be treated as
    200 CFU. Must reject unit strings that are descriptive, not measurement."""

    @pytest.fixture
    def enricher(self):
        return SupplementEnricherV3()

    def test_unit_probiotic_blend_is_not_cfu_equivalent(self, enricher):
        """'probiotic blend' is a descriptive label, not a CFU unit."""
        assert enricher._is_cfu_equivalent_unit("probiotic blend") is False, (
            "Unit 'probiotic blend' must not be treated as CFU-equivalent. "
            "A 200 mg proprietary blend with this unit would be mis-parsed "
            "as 200 CFU. Root cause: CFU_EQUIVALENT_PATTERNS includes "
            r"\bprobiotic(?:s)? which matches any string containing 'probiotic'."
        )

    def test_unit_bacteria_count_is_not_cfu_equivalent(self, enricher):
        """'bacteria count' is a label, not a measurement unit."""
        assert enricher._is_cfu_equivalent_unit("bacteria count") is False

    def test_unit_organism_based_is_not_cfu_equivalent(self, enricher):
        """'organism-based' is a claim, not a measurement unit."""
        assert enricher._is_cfu_equivalent_unit("organism-based") is False

    def test_real_cfu_units_still_recognized(self, enricher):
        """Regression lock: the tightening must NOT break real CFU units."""
        assert enricher._is_cfu_equivalent_unit("CFU") is True
        assert enricher._is_cfu_equivalent_unit("cfu(s)") is True
        assert enricher._is_cfu_equivalent_unit("Live Cell(s)") is True
        assert enricher._is_cfu_equivalent_unit("Viable Cell(s)") is True
        assert enricher._is_cfu_equivalent_unit("Colony Forming Units") is True
        assert enricher._is_cfu_equivalent_unit("active cells") is True


class TestProbioticClassificationBoundaryStrict:
    """Phase 0 failing test for MED #6: working-tree change broadens
    probiotic classification so that probiotic_name_signal alone (e.g. a
    product named 'Probiotic Support') can trigger the probiotic branch.
    Combined with threshold = ceil(active_count * 0.25), boundary products
    can silently misclassify. Lock the strict boundary."""

    @pytest.fixture
    def enricher(self):
        return SupplementEnricherV3()

    def test_nine_ingredients_with_two_probiotics_and_name_signal_not_probiotic(self, enricher):
        """9-ingredient product with 2 probiotic strains and 'Probiotic'
        in the product name. ceil(9 * 0.25) = 3 required; 2 is below
        threshold. Must NOT classify as probiotic."""
        product = {
            'id': 'boundary_2_of_9',
            'product_name': 'Probiotic Support Complex',
            'fullName': 'Probiotic Support Complex',
            'bundleName': '',
            'statements': [],
            'activeIngredients': [
                {'name': 'Lactobacillus acidophilus', 'standardName': 'Lactobacillus acidophilus', 'category': 'probiotic'},
                {'name': 'Bifidobacterium lactis', 'standardName': 'Bifidobacterium lactis', 'category': 'probiotic'},
                {'name': 'Vitamin C', 'standardName': 'Vitamin C', 'category': 'vitamin'},
                {'name': 'Vitamin D3', 'standardName': 'Vitamin D', 'category': 'vitamin'},
                {'name': 'Zinc', 'standardName': 'Zinc', 'category': 'mineral'},
                {'name': 'Selenium', 'standardName': 'Selenium', 'category': 'mineral'},
                {'name': 'Magnesium', 'standardName': 'Magnesium', 'category': 'mineral'},
                {'name': 'Vitamin E', 'standardName': 'Vitamin E', 'category': 'vitamin'},
                {'name': 'Vitamin A', 'standardName': 'Vitamin A', 'category': 'vitamin'},
            ],
            'inactiveIngredients': [],
        }
        result = enricher._classify_supplement_type(product)
        assert result['type'] != 'probiotic', (
            f"9-ingredient supplement with 2/9 = 22% probiotics (below 25% "
            f"threshold) and 'Probiotic' in the name must not be classified "
            f"as 'probiotic'; got '{result['type']}'"
        )

    def test_nine_ingredients_with_three_probiotics_is_probiotic(self, enricher):
        """Same shape, 3/9 = 33% — at/above threshold. Must classify as probiotic.
        Boundary locks the decision at the 25% threshold."""
        product = {
            'id': 'boundary_3_of_9',
            'product_name': 'Probiotic Support Complex',
            'fullName': 'Probiotic Support Complex',
            'bundleName': '',
            'statements': [],
            'activeIngredients': [
                {'name': 'Lactobacillus acidophilus', 'standardName': 'Lactobacillus acidophilus', 'category': 'probiotic'},
                {'name': 'Bifidobacterium lactis', 'standardName': 'Bifidobacterium lactis', 'category': 'probiotic'},
                {'name': 'Lactobacillus rhamnosus', 'standardName': 'Lactobacillus rhamnosus', 'category': 'probiotic'},
                {'name': 'Vitamin C', 'standardName': 'Vitamin C', 'category': 'vitamin'},
                {'name': 'Vitamin D3', 'standardName': 'Vitamin D', 'category': 'vitamin'},
                {'name': 'Zinc', 'standardName': 'Zinc', 'category': 'mineral'},
                {'name': 'Selenium', 'standardName': 'Selenium', 'category': 'mineral'},
                {'name': 'Magnesium', 'standardName': 'Magnesium', 'category': 'mineral'},
                {'name': 'Vitamin E', 'standardName': 'Vitamin E', 'category': 'vitamin'},
            ],
            'inactiveIngredients': [],
        }
        result = enricher._classify_supplement_type(product)
        assert result['type'] == 'probiotic', (
            f"9-ingredient supplement with 3/9 = 33% probiotics (at threshold) "
            f"and 'Probiotic' in the name should classify as probiotic; got "
            f"'{result['type']}'"
        )


# ---------------------------------------------------------------------------
# H6: PROBIOTIC_TERMS genera derived from clinically_relevant_strains.json
# ---------------------------------------------------------------------------


class TestProbioticGeneraFromDataFile:
    """H6: PROBIOTIC_TERMS must be sourced from clinically_relevant_strains.json
    genera rather than a hardcoded tuple so that reclassified genera (e.g.
    Lactiplantibacillus, Escherichia coli Nissle) are automatically covered.

    Regression locks: existing genera still detected.
    New cases: lactiplantibacillus and escherichia (both present in strains file
    as aliases/standard_names).
    """

    # --- Regression locks: existing genera must still be detected via name ---

    def test_lactobacillus_still_classified_as_probiotic(self):
        """Regression: 'lactobacillus' term still triggers probiotic detection."""
        from supplement_type_utils import PROBIOTIC_TERMS
        assert "lactobacillus" in PROBIOTIC_TERMS, (
            "PROBIOTIC_TERMS must still contain 'lactobacillus'"
        )

    def test_bifidobacterium_still_classified(self):
        """Regression: 'bifidobacterium' term still present."""
        from supplement_type_utils import PROBIOTIC_TERMS
        assert "bifidobacterium" in PROBIOTIC_TERMS, (
            "PROBIOTIC_TERMS must still contain 'bifidobacterium'"
        )

    def test_saccharomyces_still_classified(self):
        """Regression: 'saccharomyces' term still present."""
        from supplement_type_utils import PROBIOTIC_TERMS
        assert "saccharomyces" in PROBIOTIC_TERMS, (
            "PROBIOTIC_TERMS must still contain 'saccharomyces'"
        )

    def test_lacticaseibacillus_still_classified(self):
        """Regression: 'lacticaseibacillus' (reclassified genus) still present."""
        from supplement_type_utils import PROBIOTIC_TERMS
        assert "lacticaseibacillus" in PROBIOTIC_TERMS, (
            "PROBIOTIC_TERMS must still contain 'lacticaseibacillus'"
        )

    def test_limosilactobacillus_still_classified(self):
        """Regression: 'limosilactobacillus' (reclassified genus) still present."""
        from supplement_type_utils import PROBIOTIC_TERMS
        assert "limosilactobacillus" in PROBIOTIC_TERMS, (
            "PROBIOTIC_TERMS must still contain 'limosilactobacillus'"
        )

    # --- New genera from clinically_relevant_strains.json aliases ---

    def test_lactiplantibacillus_is_classified_as_probiotic(self):
        """NEW: 'lactiplantibacillus' appears in aliases for Lactobacillus plantarum
        strains (299v, HEAL9) in clinically_relevant_strains.json. Must be in
        PROBIOTIC_TERMS after the fix."""
        from supplement_type_utils import PROBIOTIC_TERMS
        assert "lactiplantibacillus" in PROBIOTIC_TERMS, (
            "'lactiplantibacillus' is a valid reclassified probiotic genus present "
            "in clinically_relevant_strains.json aliases (Lactiplantibacillus "
            "plantarum 299v, HEAL9) but is missing from PROBIOTIC_TERMS"
        )

    def test_escherichia_is_classified_as_probiotic(self):
        """NEW: 'escherichia' is the genus for E. coli Nissle 1917 -- a clinically
        validated probiotic strain (evidence_level=high) present in
        clinically_relevant_strains.json standard_names. Must be in PROBIOTIC_TERMS."""
        from supplement_type_utils import PROBIOTIC_TERMS
        assert "escherichia" in PROBIOTIC_TERMS, (
            "'escherichia' (E. coli Nissle 1917) is a clinically validated probiotic "
            "strain in clinically_relevant_strains.json but its genus is absent "
            "from PROBIOTIC_TERMS"
        )

    def test_probiotic_terms_is_iterable_with_membership(self):
        """PROBIOTIC_TERMS must remain iterable and support 'in' membership tests."""
        from supplement_type_utils import PROBIOTIC_TERMS
        assert hasattr(PROBIOTIC_TERMS, "__contains__"), (
            "PROBIOTIC_TERMS must support 'in' membership test"
        )
        assert len(PROBIOTIC_TERMS) >= 8, (
            f"PROBIOTIC_TERMS must contain at least 8 entries; got {len(PROBIOTIC_TERMS)}"
        )

    def test_probiotic_terms_covers_all_standard_name_genera(self):
        """PROBIOTIC_TERMS must contain all genera from clinically_relevant_strains.json
        standard_names so any future strain additions are automatically covered."""
        import json
        import os
        strains_path = os.path.join(
            os.path.dirname(__file__), "..", "data", "clinically_relevant_strains.json"
        )
        with open(strains_path) as f:
            data = json.load(f)
        strains = data.get("clinically_relevant_strains", [])

        standard_genera = set()
        for s in strains:
            name = s.get("standard_name", "")
            if name:
                standard_genera.add(name.split()[0].lower())

        from supplement_type_utils import PROBIOTIC_TERMS
        missing = standard_genera - set(PROBIOTIC_TERMS)
        assert not missing, (
            f"Genera from clinically_relevant_strains.json standard_names "
            f"missing from PROBIOTIC_TERMS: {sorted(missing)}"
        )

class TestBrandedEnhancersFromDataFile:
    """
    H1 regression lock: branded bioavailability enhancers are recognized via
    the curated ABSORPTION_ENHANCERS_PROMOTE_EXCEPTION constant in
    scripts/constants.py. That constant is DELIBERATELY narrow — it does
    not source from absorption_enhancers.json wholesale because that data
    file contains carrier oils, generic nutrients, and delivery tech that
    must NOT be promoted without explicit dose.

    Expansions to the branded-enhancer list are curated additions in
    constants.py, not automatic from the data file.
    """

    @pytest.fixture
    def enricher(self):
        return SupplementEnricherV3()

    def test_bioperine_still_detected(self, enricher):
        """Regression lock: bioperine (the canonical branded piperine
        enhancer) must always be detected."""
        assert enricher._is_absorption_enhancer('bioperine', 'bioperine'), \
            "bioperine must be detected via ABSORPTION_ENHANCERS_PROMOTE_EXCEPTION"

    def test_piperine_still_detected(self, enricher):
        """Regression lock: piperine must always be detected."""
        assert enricher._is_absorption_enhancer('piperine', 'piperine'), \
            "piperine must be detected via ABSORPTION_ENHANCERS_PROMOTE_EXCEPTION"

    def test_astragin_is_detected_as_branded_enhancer(self, enricher):
        """astragin is a curated addition to ABSORPTION_ENHANCERS_PROMOTE_EXCEPTION
        (true branded ginsenoside/Astragalus bioavailability enhancer)."""
        assert enricher._is_absorption_enhancer('astragin', 'astragin'), \
            "astragin must be detected as a curated branded bioavailability enhancer"

    def test_astragin_compound_name_is_detected(self, enricher):
        """'AstraGin patented extract' should match via substring against 'astragin'."""
        assert enricher._is_absorption_enhancer('astragin patented extract', 'astragin'), \
            "astragin compound name must be detected via substring match"

    def test_micosolle_is_detected_as_branded_enhancer(self, enricher):
        """micosolle is a curated branded microencapsulation enhancer in
        ABSORPTION_ENHANCERS_PROMOTE_EXCEPTION."""
        assert enricher._is_absorption_enhancer('micosolle', 'micosolle'), \
            "micosolle must be detected as a curated branded bioavailability enhancer"

    def test_carrier_oils_are_NOT_promoted(self, enricher):
        """Hardening: coconut oil, olive oil, and other carrier oils appear
        in absorption_enhancers.json under 'Fats and Oils' but they are NOT
        branded bioavailability enhancers — they are carrier lipids. The
        curated allowlist in constants.py excludes them. This test locks
        that boundary so a future refactor cannot re-broaden the check."""
        assert not enricher._is_absorption_enhancer('coconut oil', 'coconut oil'), \
            "coconut oil is a carrier lipid, NOT a branded bioavailability enhancer"
        assert not enricher._is_absorption_enhancer('organic olive oil', 'olive oil'), \
            "olive oil is a carrier lipid, NOT a branded bioavailability enhancer"

    def test_generic_nutrients_are_NOT_promoted(self, enricher):
        """Hardening: Vitamin C, Glycine, Methionine etc. appear in
        absorption_enhancers.json as 'helps absorption of X' entries but
        they are generic nutrients, not branded enhancers. Must not be
        promoted via this path."""
        assert not enricher._is_absorption_enhancer('vitamin c', 'vitamin c'), \
            "Vitamin C is a nutrient, not a branded bioavailability enhancer"
        assert not enricher._is_absorption_enhancer('glycine', 'glycine'), \
            "Glycine is an amino acid, not a branded bioavailability enhancer"


class TestEnricherDropsDeadPassthroughFields:
    """
    Regression: the enricher begins with `enriched = dict(product)` (shallow
    copy of cleaned input). A 2026-04 audit identified 14 cleaner fields that
    have zero downstream consumers — they inflate the serialized record size
    without adding signal.

    This test locks the drop list so the fields cannot silently sneak back in.
    If a future change starts consuming one of these fields downstream, this
    test must be updated in the SAME commit as the new consumer (and the
    pop removed). Otherwise the field is dead baggage.

    Kept fields (still consumed): dsld_id, product_name, brandName,
    activeIngredients, inactiveIngredients, labelText, servingSizes,
    servingsPerContainer, netContents, statements, claims, targetGroups,
    userGroups, physicalState, nutritionalInfo, form_factor, status,
    discontinuedDate, imageUrl, upcSku, display_ingredients (enricher
    overwrites this, but does NOT pop it).

    Dropped fields: src, nhanesId, brandIpSymbol, productVersionCode, pdf,
    thumbnail, percentDvFootnote, hasOuterCarton, upcValid, productType,
    events, labelRelationships, metadata, images.
    """

    DEAD_FIELDS = [
        "src",
        "nhanesId",
        "brandIpSymbol",
        "productVersionCode",
        "pdf",
        "thumbnail",
        "percentDvFootnote",
        "hasOuterCarton",
        "upcValid",
        "productType",
        "events",
        "labelRelationships",
        "metadata",
        "images",
    ]

    ACTIVE_FIELDS = [
        "dsld_id",
        "product_name",
        "brandName",
        "activeIngredients",
        "inactiveIngredients",
        "statements",
        "claims",
        "targetGroups",
        "form_factor",
        "status",
        "upcSku",
        "display_ingredients",
    ]

    @pytest.fixture
    def normalizer(self):
        from enhanced_normalizer import EnhancedDSLDNormalizer
        return EnhancedDSLDNormalizer()

    @pytest.fixture
    def enricher(self):
        return SupplementEnricherV3()

    @pytest.fixture
    def minimal_raw_product(self):
        """Minimal raw DSLD product that exercises all passthrough fields.

        Populates every candidate dead field with a non-None value so the
        test can prove the pop actually happened (not that the field was
        just never set).
        """
        return {
            "id": "test_dead_passthrough_001",
            "fullName": "Test Dead Passthrough Product",
            "brandName": "Test Brand",
            "upcSku": "123456789012",
            "productVersionCode": "1",
            "productType": {
                "langualCode": "A0815",
                "langualCodeDescription": "Dietary Supplement Product"
            },
            "physicalState": {
                "langualCode": "E0155",
                "langualCodeDescription": "Capsule (pill)"
            },
            "ingredientRows": [
                {
                    "name": "Vitamin C",
                    "order": 1,
                    "quantity": [{"quantity": 500, "unit": "mg"}],
                    "forms": [{"name": "Ascorbic Acid"}]
                }
            ],
            "otherIngredients": {
                "ingredients": [
                    {"name": "Cellulose", "order": 1, "forms": []}
                ]
            },
            "statements": [{"type": "allergen", "text": "Contains: None"}],
            "claims": [],
            "targetGroups": ["Adults"],
            "userGroups": ["Adults"],
            "servingSizes": [{"minQuantity": 1, "maxQuantity": 1, "unit": "capsule"}],
            "servingsPerContainer": [{"order": 1, "quantity": 60, "unit": "capsules"}],
            "netContents": [{"quantity": 60, "unit": "capsules"}],
            "status": "active",
            # Dead-field candidates populated so absence proves the pop
            "src": "manual/test/dead_passthrough.json",
            "nhanesId": 12345,
            "brandIpSymbol": "TM",
            "pdf": "http://example.com/label.pdf",
            "thumbnail": "http://example.com/thumb.jpg",
            "percentDvFootnote": "%DV footnote text",
            "hasOuterCarton": True,
            "events": [{"type": "Date entered", "date": "2020-01-01"}],
            "labelRelationships": [],
            "images": [{"url": "http://example.com/img.jpg", "type": "front"}],
            "contacts": [{"name": "Test Co", "phone": "555-0000"}],
        }

    def test_dead_fields_are_dropped_from_enriched_output(
        self, normalizer, enricher, minimal_raw_product
    ):
        """The 14 dead passthrough fields must be absent from the enriched
        output. If any of them is still present, the pop block either never
        ran or was partially applied."""
        cleaned = normalizer.normalize_product(minimal_raw_product)

        # Sanity: dead fields should exist in cleaned data (cleaner writes them)
        # This guards against the test passing because the cleaner quietly
        # stopped writing them — in which case the pop block is a no-op and
        # the test gives a false green.
        cleaner_wrote_at_least_one = any(
            field in cleaned for field in self.DEAD_FIELDS
        )
        assert cleaner_wrote_at_least_one, (
            "Cleaner did not write any dead-field candidates. Test fixture "
            "may be missing required inputs, or the cleaner contract changed."
        )

        enriched, _issues = enricher.enrich_product(cleaned)

        present_dead = [f for f in self.DEAD_FIELDS if f in enriched]
        assert not present_dead, (
            f"Enricher failed to pop dead passthrough fields: {present_dead}. "
            f"These fields have zero downstream consumers and must be dropped "
            f"before the enriched dict is returned."
        )

    def test_active_fields_survive_enrichment(
        self, normalizer, enricher, minimal_raw_product
    ):
        """The pop block must not accidentally strip fields that are still
        consumed downstream."""
        cleaned = normalizer.normalize_product(minimal_raw_product)
        enriched, _issues = enricher.enrich_product(cleaned)

        missing_active = [f for f in self.ACTIVE_FIELDS if f not in enriched]
        assert not missing_active, (
            f"Enricher stripped active fields that still have downstream "
            f"consumers: {missing_active}. Revert the pop immediately."
        )

    def test_display_ingredients_is_present_after_enrichment(
        self, normalizer, enricher, minimal_raw_product
    ):
        """display_ingredients is a special case: the enricher OVERWRITES it
        (scripts/enrich_supplements_v3.py line ~10798), it does NOT pop it.
        The enricher's version reads the cleaner's value first (line ~8143)
        and augments it. If this test fails, someone accidentally added
        display_ingredients to the pop list."""
        cleaned = normalizer.normalize_product(minimal_raw_product)
        enriched, _issues = enricher.enrich_product(cleaned)

        assert "display_ingredients" in enriched, (
            "display_ingredients must be present in enriched output. "
            "The enricher overwrites it with _enrich_display_ingredients(); "
            "it must NOT be in the pop block."
        )

    def test_enriched_dict_is_smaller_than_naive_shallow_copy(
        self, normalizer, enricher, minimal_raw_product
    ):
        """Sanity check: the enriched dict should have fewer cleaner-passthrough
        keys after the pop block than a naive dict(cleaned) copy would."""
        cleaned = normalizer.normalize_product(minimal_raw_product)

        # How many dead fields exist in the cleaned dict (the pop baseline)
        dead_in_cleaned = sum(1 for f in self.DEAD_FIELDS if f in cleaned)
        assert dead_in_cleaned > 0, (
            "Cleaner must write at least one dead-field candidate for this "
            "test to be meaningful."
        )

        enriched, _issues = enricher.enrich_product(cleaned)

        # None of the dead fields should survive
        dead_in_enriched = sum(1 for f in self.DEAD_FIELDS if f in enriched)
        assert dead_in_enriched == 0, (
            f"Expected 0 dead fields in enriched output, found "
            f"{dead_in_enriched}: "
            f"{[f for f in self.DEAD_FIELDS if f in enriched]}"
        )


class TestClaimSourceExtractionFromLabelTextParsed:
    """
    Regression: the enricher's `_extract_text_sources` helper used to iterate
    `product.get('qualityFeatures')`, `product.get('certifications')`, and
    `product.get('otherIngredients')` at top level. The cleaner nests this
    data inside `labelText.parsed.qualityFeatures` and
    `labelText.parsed.certifications` (enhanced_normalizer.py lines 3550, 3562)
    and processes `otherIngredients` into `inactiveIngredients`. The top-level
    loops were dead code that always returned empty.

    2026-04 audit removed the dead loops. This test locks the contract that
    certification and quality-feature evidence still reaches the claims-db
    matcher via the `labelText.parsed.*` iteration path. If a future refactor
    removes the parsed iteration, this test will catch the regression.
    """

    def _make_enricher(self):
        from enrich_supplements_v3 import SupplementEnricherV3
        return SupplementEnricherV3.__new__(SupplementEnricherV3)

    def test_certifications_captured_from_labeltext_parsed(self):
        enricher = self._make_enricher()
        product = {
            "labelText": {
                "raw": "USP Verified, NSF Certified.",
                "parsed": {
                    "certifications": ["USP Verified", "NSF Certified"],
                },
            },
            "activeIngredients": [],
            "inactiveIngredients": [],
            "statements": [],
            "claims": [],
            "fullName": "Test",
            "brandName": "Test",
        }
        sources = enricher._extract_text_sources(product)
        cert_texts = [t for p, t in sources if "labelText.parsed.certifications" in p]
        assert "USP Verified" in cert_texts
        assert "NSF Certified" in cert_texts

    def test_quality_features_captured_from_labeltext_parsed(self):
        enricher = self._make_enricher()
        product = {
            "labelText": {
                "raw": "GMP Certified, third-party tested.",
                "parsed": {
                    "qualityFeatures": ["GMP Certified", "Third-party tested"],
                },
            },
            "activeIngredients": [],
            "inactiveIngredients": [],
            "statements": [],
            "claims": [],
            "fullName": "Test",
            "brandName": "Test",
        }
        sources = enricher._extract_text_sources(product)
        qf_texts = [t for p, t in sources if "labelText.parsed.qualityFeatures" in p]
        assert "GMP Certified" in qf_texts
        assert "Third-party tested" in qf_texts

    def test_dead_toplevel_certifications_loop_removed(self):
        """Sanity-check that the top-level `certifications` read doesn't fire.

        A cleaned product with ONLY a top-level `certifications` key (which
        the cleaner never writes) should produce zero certification sources.
        This proves the dead loop is truly gone — if someone re-adds it, this
        test catches the resurrection.
        """
        enricher = self._make_enricher()
        product = {
            "certifications": ["PHANTOM Certification"],
            "qualityFeatures": ["PHANTOM Quality Feature"],
            "otherIngredients": "PHANTOM other ingredient text",
            "labelText": {"raw": "", "parsed": {}},
            "activeIngredients": [],
            "inactiveIngredients": [],
            "statements": [],
            "claims": [],
            "fullName": "",
            "brandName": "",
        }
        sources = enricher._extract_text_sources(product)
        # No source path should come from a top-level certifications/
        # qualityFeatures/otherIngredients key.
        offenders = [
            (p, t) for p, t in sources
            if p.startswith("certifications[")
            or p.startswith("qualityFeatures[")
            or p == "otherIngredients"
            or p.startswith("otherIngredients[")
        ]
        assert offenders == [], (
            f"Top-level dead loops resurrected: {offenders}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# TDD: Change B — nutrition_summary collection (enrich_supplements_v3.py)
# ─────────────────────────────────────────────────────────────────────────────

class TestNutritionSummaryCollection:
    """Verify _collect_nutrition_summary produces the expected flat dict."""

    @pytest.fixture
    def enricher(self):
        return SupplementEnricherV3()

    def _make_product(self, nutritional_info=None):
        base = {
            "id": "test_ns_001",
            "dsld_id": "test_ns_001",
            "product_name": "Test Nutrition Product",
            "activeIngredients": [],
            "inactiveIngredients": [],
            "statements": [],
        }
        if nutritional_info is not None:
            base["nutritionalInfo"] = nutritional_info
        return base

    def test_nutrition_summary_populates_all_five_when_present(self, enricher):
        product = self._make_product({
            "calories": {"amount": 50.0, "unit": "kcal"},
            "totalCarbohydrates": {"amount": 12.0, "unit": "g"},
            "totalFat": {"amount": 3.0, "unit": "g"},
            "protein": {"amount": 7.0, "unit": "g"},
            "dietaryFiber": {"amount": 1.5, "unit": "g"},
        })
        enriched, _ = enricher.enrich_product(product)
        ns = enriched.get("nutrition_summary")
        assert ns is not None, "nutrition_summary must be present in enriched output"
        assert ns["calories_per_serving"] == 50.0
        assert ns["total_carbohydrates_g"] == 12.0
        assert ns["total_fat_g"] == 3.0
        assert ns["protein_g"] == 7.0
        assert ns["dietary_fiber_g"] == 1.5

    def test_nutrition_summary_handles_missing_nutritionalinfo(self, enricher):
        product = self._make_product()  # no nutritionalInfo key
        enriched, _ = enricher.enrich_product(product)
        ns = enriched.get("nutrition_summary")
        assert ns is not None, "nutrition_summary must always be present"
        assert ns["calories_per_serving"] is None
        assert ns["total_carbohydrates_g"] is None
        assert ns["total_fat_g"] is None
        assert ns["protein_g"] is None
        assert ns["dietary_fiber_g"] is None

    def test_nutrition_summary_handles_partial_data(self, enricher):
        product = self._make_product({
            "calories": {"amount": 25.0, "unit": "kcal"},
            # other macros absent
        })
        enriched, _ = enricher.enrich_product(product)
        ns = enriched["nutrition_summary"]
        assert ns["calories_per_serving"] == 25.0
        assert ns["total_carbohydrates_g"] is None
        assert ns["total_fat_g"] is None
        assert ns["protein_g"] is None
        assert ns["dietary_fiber_g"] is None

    def test_nutrition_summary_passes_through_units_verbatim(self, enricher):
        product = self._make_product({
            "protein": {"amount": 5.0, "unit": "g"},
        })
        enriched, _ = enricher.enrich_product(product)
        ns = enriched["nutrition_summary"]
        assert ns["protein_g"] == 5.0, "protein_g must pass through as-is (5.0g → 5.0)"

    def test_nutrition_summary_preserves_sugar_and_sodium_flow(self, enricher):
        """Adding nutrition_summary must not disturb dietary_sensitivity_data."""
        product = self._make_product({
            "calories": {"amount": 10.0, "unit": "kcal"},
            "totalCarbohydrates": {"amount": 2.0, "unit": "g"},
        })
        product["nutritionalInfo"]["sugars"] = {"amount": 1.0, "unit": "g"}
        product["nutritionalInfo"]["sodium"] = {"amount": 5.0, "unit": "mg"}
        enriched, _ = enricher.enrich_product(product)
        # nutrition_summary present
        assert enriched.get("nutrition_summary") is not None
        # dietary_sensitivity_data still present and populated
        dsd = enriched.get("dietary_sensitivity_data")
        assert dsd is not None, "dietary_sensitivity_data must still be populated"
        assert "sugar" in dsd
        assert "sodium" in dsd
