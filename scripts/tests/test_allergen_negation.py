#!/usr/bin/env python3
"""
Allergen Negation Handling Tests

Verifies that allergen detection correctly handles negation contexts.
Statements like "Contains no milk/egg/soy" should NOT trigger allergen detection.

Policy (production path: statements[] -> _parse_allergen_statement):
- A negated clause ("contains no X", "does not contain X", "free from/of X",
  "without X", "no added X") declares nothing; "no X" declares nothing because
  only "contains", "may contain" and facility wording declare an allergen.
- Structured ingredient rows are never negated by a label claim.

Run with: pytest tests/test_allergen_negation.py -v
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from enrich_supplements_v3 import SupplementEnricherV3


_ALLERGENS = {
    'allergens': [
        {'id': 'ALG_MILK', 'standard_name': 'milk', 'aliases': ['dairy', 'lactose', 'casein', 'whey'],
         'severity_level': 'high', 'regulatory_status': 'major_allergen', 'general_handling': 'flag_and_warn'},
        {'id': 'ALG_SOY', 'standard_name': 'soy', 'aliases': ['soya', 'soybean', 'soy lecithin'],
         'severity_level': 'high', 'regulatory_status': 'major_allergen', 'general_handling': 'flag_and_warn'},
        {'id': 'ALG_EGG', 'standard_name': 'eggs', 'aliases': ['egg', 'albumin', 'ovalbumin'],
         'severity_level': 'high', 'regulatory_status': 'major_allergen', 'general_handling': 'flag_and_warn'},
        {'id': 'ALG_WHEAT', 'standard_name': 'wheat', 'aliases': ['gluten', 'wheat flour'],
         'severity_level': 'high', 'regulatory_status': 'major_allergen', 'general_handling': 'flag_and_warn'},
    ]
}


class TestAllergenNegationPolicy:
    """Label statements go through the production path (`statements[]` ->
    `_parse_allergen_statement`), not a helper production never calls."""

    @pytest.fixture(scope='class')
    def enricher(self):
        enricher = SupplementEnricherV3()
        enricher.databases['allergens'] = _ALLERGENS
        return enricher

    @staticmethod
    def _detected(enricher, statement):
        product = {
            'dsld_id': '99990',
            'fullName': 'Test Vitamin',
            'statements': [{'type': 'Precautions', 'notes': statement}],
            'activeIngredients': [{'name': 'Vitamin C', 'quantity': '100', 'unit': 'mg'}],
            'inactiveIngredients': [{'name': 'Cellulose'}],
        }
        allergens = enricher._collect_contaminant_data(product).get('allergens', {}).get('allergens', [])
        return {a.get('allergen_name') for a in allergens}

    @pytest.mark.parametrize('statement', [
        'this product contains no milk or dairy',
        'Contains no milk or dairy',
        'free from soy and other allergens',
        'this formula is free of eggs',
        'made without wheat or gluten',
        'this supplement does not contain milk',
        'no soy, no gluten, no artificial colors',
        'no dairy products used',
    ])
    def test_negated_statement_declares_no_allergen(self, enricher, statement):
        assert self._detected(enricher, statement) == set()

    @pytest.mark.parametrize('statement,expected', [
        ('contains milk and soy lecithin', {'milk', 'soy'}),
        ('Contains: milk.', {'milk'}),
        ('May contain soy.', {'soy'}),
    ])
    def test_positive_statement_declares_its_allergens(self, enricher, statement, expected):
        assert self._detected(enricher, statement) == expected


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
            'fullName': 'Test Vitamin',
            'statements': [{'type': 'Precautions', 'notes': 'Contains no milk, egg, or soy.'}],
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
            'fullName': 'Test Vitamin with Soy',
            'statements': [],
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
            'fullName': 'Complex Test',
            'statements': [{'type': 'Precautions', 'notes': 'Contains no milk. May contain traces of tree nuts.'}],
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
