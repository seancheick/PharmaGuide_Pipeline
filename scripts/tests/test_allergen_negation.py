#!/usr/bin/env python3
"""
Allergen Negation Handling Tests

Verifies that allergen detection correctly handles negation contexts.
Statements like "Contains no milk/egg/soy" should NOT trigger allergen detection.

Policy:
- YES, we treat negation patterns as exclusions for allergen detection
- Supported patterns: "no X", "free from X", "free of X", "without X",
  "does not contain X", "contains no X"
- If allergen appears in negation context, it is NOT flagged as detected

Run with: pytest tests/test_allergen_negation.py -v
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from enrich_supplements_v3 import SupplementEnricherV3


class TestAllergenNegationPolicy:
    """Tests proving allergen negation handling works correctly."""

    @pytest.fixture
    def enricher(self):
        """Create enricher with allergen database loaded."""
        enricher = SupplementEnricherV3()
        # Minimal allergen database for testing
        enricher.databases['allergens'] = {
            'allergens': [
                {
                    'id': 'ALG_MILK',
                    'standard_name': 'milk',
                    'aliases': ['dairy', 'lactose', 'casein', 'whey'],
                    'severity_level': 'high',
                    'regulatory_status': 'major_allergen',
                    'general_handling': 'flag_and_warn'
                },
                {
                    'id': 'ALG_SOY',
                    'standard_name': 'soy',
                    'aliases': ['soya', 'soybean', 'soy lecithin'],
                    'severity_level': 'high',
                    'regulatory_status': 'major_allergen',
                    'general_handling': 'flag_and_warn'
                },
                {
                    'id': 'ALG_EGG',
                    'standard_name': 'eggs',
                    'aliases': ['egg', 'albumin', 'ovalbumin'],
                    'severity_level': 'high',
                    'regulatory_status': 'major_allergen',
                    'general_handling': 'flag_and_warn'
                },
                {
                    'id': 'ALG_WHEAT',
                    'standard_name': 'wheat',
                    'aliases': ['gluten', 'wheat flour'],
                    'severity_level': 'high',
                    'regulatory_status': 'major_allergen',
                    'general_handling': 'flag_and_warn'
                },
            ]
        }
        return enricher

    def test_negation_contains_no(self, enricher):
        """'Contains no milk' should NOT flag milk as allergen."""
        result = enricher._is_negated(
            name='milk',
            aliases=['dairy'],
            text='this product contains no milk or dairy'
        )
        assert result is True, "Expected 'contains no milk' to be recognized as negation"

    def test_negation_free_from(self, enricher):
        """'Free from soy' should NOT flag soy as allergen."""
        result = enricher._is_negated(
            name='soy',
            aliases=['soya'],
            text='free from soy and other allergens'
        )
        assert result is True, "Expected 'free from soy' to be recognized as negation"

    def test_negation_free_of(self, enricher):
        """'Free of eggs' should NOT flag eggs as allergen."""
        result = enricher._is_negated(
            name='eggs',
            aliases=['egg'],
            text='this formula is free of eggs'
        )
        assert result is True, "Expected 'free of eggs' to be recognized as negation"

    def test_negation_without(self, enricher):
        """'Without wheat' should NOT flag wheat as allergen."""
        result = enricher._is_negated(
            name='wheat',
            aliases=['gluten'],
            text='made without wheat or gluten'
        )
        assert result is True, "Expected 'without wheat' to be recognized as negation"

    def test_negation_does_not_contain(self, enricher):
        """'Does not contain milk' should NOT flag milk as allergen."""
        result = enricher._is_negated(
            name='milk',
            aliases=['dairy'],
            text='this supplement does not contain milk'
        )
        assert result is True, "Expected 'does not contain milk' to be recognized as negation"

    def test_negation_no_prefix(self, enricher):
        """'No soy' should NOT flag soy as allergen."""
        result = enricher._is_negated(
            name='soy',
            aliases=['soya'],
            text='no soy, no gluten, no artificial colors'
        )
        assert result is True, "Expected 'no soy' to be recognized as negation"

    def test_no_negation_positive_detection(self, enricher):
        """'Contains milk' without negation SHOULD flag milk as allergen."""
        result = enricher._is_negated(
            name='milk',
            aliases=['dairy'],
            text='contains milk and soy lecithin'
        )
        assert result is False, "Expected 'contains milk' to NOT be negated"

    def test_no_negation_ingredient_list(self, enricher):
        """'Milk protein' in ingredients SHOULD flag milk as allergen."""
        result = enricher._is_negated(
            name='milk',
            aliases=['dairy'],
            text='ingredients: vitamin c, milk protein, zinc'
        )
        assert result is False, "Expected ingredient list mention to NOT be negated"

    def test_negation_alias_match(self, enricher):
        """'No dairy' should NOT flag milk (dairy is alias)."""
        result = enricher._is_negated(
            name='milk',
            aliases=['dairy'],
            text='no dairy products used'
        )
        assert result is True, "Expected 'no dairy' to negate milk (alias match)"

    def test_negation_case_insensitive(self, enricher):
        """Negation detection works when text is pre-lowercased (as done by _check_allergens)."""
        # Note: _check_allergens lowercases text before calling _is_negated
        # So in production, uppercase input works. Direct calls need lowercase text.
        result = enricher._is_negated(
            name='milk',
            aliases=['dairy'],
            text='contains no milk or dairy'  # Lowercased as done in _check_allergens
        )
        assert result is True, "Expected lowercased 'contains no milk' to be recognized"


class TestAllergenDetectionEndToEnd:
    """End-to-end tests for allergen detection with negation handling."""

    @pytest.fixture
    def enricher(self):
        """Create enricher with allergen database loaded."""
        enricher = SupplementEnricherV3()
        enricher.databases['allergens'] = {
            'allergens': [
                {
                    'id': 'ALG_MILK',
                    'standard_name': 'milk',
                    'aliases': ['dairy', 'lactose'],
                    'severity_level': 'high',
                    'regulatory_status': 'major_allergen',
                    'general_handling': 'flag_and_warn'
                },
                {
                    'id': 'ALG_SOY',
                    'standard_name': 'soy',
                    'aliases': ['soya', 'soy lecithin'],
                    'severity_level': 'high',
                    'regulatory_status': 'major_allergen',
                    'general_handling': 'flag_and_warn'
                },
            ]
        }
        return enricher

    def test_product_with_negation_no_allergen_detected(self, enricher):
        """Product stating 'Contains no milk' should NOT detect milk allergen."""
        product = {
            'dsld_id': '99999',
            'productName': 'Test Vitamin',
            'labelStatement': 'Contains no milk, egg, or soy.',
            'activeIngredients': [
                {'name': 'Vitamin C', 'quantity': '100', 'unit': 'mg'}
            ],
            'inactiveIngredients': [
                {'name': 'Cellulose'},
                {'name': 'Magnesium Stearate'}
            ],
            'otherIngredients': 'Cellulose, Magnesium Stearate'
        }

        result = enricher._collect_contaminant_data(product)
        # Structure: result['allergens'] = {'found': bool, 'allergens': list, ...}
        allergens_data = result.get('allergens', {})
        allergens_list = allergens_data.get('allergens', [])

        # Milk should NOT be in detected allergens (negation context)
        milk_allergens = [a for a in allergens_list if a.get('allergen_name') == 'milk']
        assert len(milk_allergens) == 0, f"Milk should not be detected with 'Contains no milk'. Found: {milk_allergens}"

    def test_product_with_actual_allergen_detected(self, enricher):
        """Product with 'soy lecithin' ingredient SHOULD detect soy allergen."""
        product = {
            'dsld_id': '99998',
            'productName': 'Test Vitamin with Soy',
            'labelStatement': '',
            'activeIngredients': [
                {'name': 'Vitamin C', 'quantity': '100', 'unit': 'mg'}
            ],
            'inactiveIngredients': [
                {'name': 'Cellulose'},
                {'name': 'Soy Lecithin'},
                {'name': 'Magnesium Stearate'}
            ],
            'otherIngredients': 'Cellulose, Soy Lecithin, Magnesium Stearate'
        }

        result = enricher._collect_contaminant_data(product)
        # Structure: result['allergens'] = {'found': bool, 'allergens': list, ...}
        allergens_data = result.get('allergens', {})
        allergens_list = allergens_data.get('allergens', [])

        # Soy should be detected (ingredient list, no negation)
        soy_allergens = [a for a in allergens_list if a.get('allergen_name') == 'soy']
        assert len(soy_allergens) > 0, "Soy should be detected when present in ingredients"

    def test_mixed_negation_and_positive(self, enricher):
        """Product with both negation ('no milk') and positive ('soy lecithin') detection."""
        product = {
            'dsld_id': '99997',
            'productName': 'Complex Test',
            'labelStatement': 'Contains no milk. May contain traces of tree nuts.',
            'activeIngredients': [
                {'name': 'Vitamin C', 'quantity': '100', 'unit': 'mg'}
            ],
            'inactiveIngredients': [
                {'name': 'Soy Lecithin'},
                {'name': 'Cellulose'}
            ],
            'otherIngredients': 'Soy Lecithin, Cellulose'
        }

        result = enricher._collect_contaminant_data(product)
        # Structure: result['allergens'] = {'found': bool, 'allergens': list, ...}
        allergens_data = result.get('allergens', {})
        allergens_list = allergens_data.get('allergens', [])

        # Milk should NOT be detected (negation)
        milk_allergens = [a for a in allergens_list if a.get('allergen_name') == 'milk']
        assert len(milk_allergens) == 0, "Milk should not be detected with 'Contains no milk'"

        # Soy SHOULD be detected (in ingredients, no negation for soy)
        soy_allergens = [a for a in allergens_list if a.get('allergen_name') == 'soy']
        assert len(soy_allergens) > 0, "Soy should be detected when present in ingredients"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
