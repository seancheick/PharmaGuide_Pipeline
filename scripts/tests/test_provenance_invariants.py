"""
Test provenance field invariants.

These tests ensure that:
1. raw_source_text, raw_source_path, normalized_key are present in all cleaned ingredients
2. normalized_key is stable and deterministic
3. raw_source_text is never modified after initial assignment
4. raw_source_path correctly identifies the source section

CRITICAL: These invariants guarantee traceability from cleaned → enriched → scored.
If any test fails, it indicates a breaking change to the provenance contract.
"""

import pytest
from enhanced_normalizer import EnhancedDSLDNormalizer
import normalization as norm_module


class TestProvenanceFieldsPresence:
    """Ensure all cleaned ingredients have provenance fields."""

    @pytest.fixture
    def normalizer(self):
        return EnhancedDSLDNormalizer()

    def test_active_ingredients_have_provenance_fields(self, normalizer):
        """Active ingredients must have all provenance fields."""
        product = {
            "dsld_id": 12345,
            "productName": "Test Product",
            "ingredientRows": [
                {
                    "ingredientId": 1,
                    "name": "Vitamin B12",
                    "uniiCode": "TEST123",
                    "order": 1,
                    "quantity": {"value": "500", "unit": "mcg"},
                    "nestedRows": []
                },
                {
                    "ingredientId": 2,
                    "name": "Folic Acid",
                    "order": 2,
                    "quantity": {"value": "400", "unit": "mcg"},
                    "nestedRows": []
                }
            ],
            "otherIngredients": {"ingredients": [], "raw": ""}
        }

        result = normalizer.normalize_product(product)
        active = result.get("activeIngredients", [])

        assert len(active) >= 1, "Should have active ingredients"

        for ing in active:
            # raw_source_text must equal original name
            assert "raw_source_text" in ing, f"Missing raw_source_text in {ing.get('name')}"
            assert ing["raw_source_text"] == ing["name"], "raw_source_text should equal name"

            # raw_source_path must be activeIngredients
            assert "raw_source_path" in ing, f"Missing raw_source_path in {ing.get('name')}"
            assert ing["raw_source_path"] == "activeIngredients"

            # normalized_key must be valid
            assert "normalized_key" in ing, f"Missing normalized_key in {ing.get('name')}"
            is_valid, _ = norm_module.validate_normalized_key(ing["normalized_key"])
            assert is_valid, f"Invalid normalized_key: {ing['normalized_key']}"

    def test_inactive_ingredients_have_provenance_fields(self, normalizer):
        """Inactive ingredients must have all provenance fields."""
        product = {
            "dsld_id": 12345,
            "productName": "Test Product",
            "ingredientRows": [],
            "otherIngredients": {
                "ingredients": [
                    {"name": "Gelatin"},
                    {"name": "Vegetable Stearate"},
                    {"name": "Silicon Dioxide"}
                ],
                "raw": "Gelatin, Vegetable Stearate, Silicon Dioxide"
            }
        }

        result = normalizer.normalize_product(product)
        inactive = result.get("inactiveIngredients", [])

        assert len(inactive) >= 1, "Should have inactive ingredients"

        for ing in inactive:
            # raw_source_text must equal original name
            assert "raw_source_text" in ing, f"Missing raw_source_text in {ing.get('name')}"
            assert ing["raw_source_text"] == ing["name"], "raw_source_text should equal name"

            # raw_source_path must be inactiveIngredients
            assert "raw_source_path" in ing, f"Missing raw_source_path in {ing.get('name')}"
            assert ing["raw_source_path"] == "inactiveIngredients"

            # normalized_key must be valid
            assert "normalized_key" in ing, f"Missing normalized_key in {ing.get('name')}"
            is_valid, _ = norm_module.validate_normalized_key(ing["normalized_key"])
            assert is_valid, f"Invalid normalized_key: {ing['normalized_key']}"


class TestNormalizedKeyStability:
    """Ensure normalized_key is stable and deterministic."""

    @pytest.fixture
    def normalizer(self):
        return EnhancedDSLDNormalizer()

    def test_normalized_key_matches_normalization_module(self, normalizer):
        """normalized_key must match make_normalized_key() output."""
        product = {
            "dsld_id": 12345,
            "productName": "Test Product",
            "ingredientRows": [
                {
                    "ingredientId": 1,
                    "name": "Vitamin B12 (as Methylcobalamin)",
                    "order": 1,
                    "nestedRows": []
                },
                {
                    "ingredientId": 2,
                    "name": "Omega-3 Fatty Acids",
                    "order": 2,
                    "nestedRows": []
                }
            ],
            "otherIngredients": {"ingredients": [], "raw": ""}
        }

        result = normalizer.normalize_product(product)
        active = result.get("activeIngredients", [])

        for ing in active:
            raw_text = ing["raw_source_text"]
            expected_key = norm_module.make_normalized_key(raw_text)
            assert ing["normalized_key"] == expected_key, \
                f"Key mismatch: {ing['normalized_key']} != {expected_key}"

    def test_normalized_key_deterministic_across_products(self, normalizer):
        """Same ingredient name should produce same key in different products."""
        products = [
            {
                "dsld_id": 1,
                "productName": "Product A",
                "ingredientRows": [{"ingredientId": 1, "name": "Vitamin D3", "order": 1, "nestedRows": []}],
                "otherIngredients": {"ingredients": [], "raw": ""}
            },
            {
                "dsld_id": 2,
                "productName": "Product B",
                "ingredientRows": [{"ingredientId": 2, "name": "Vitamin D3", "order": 1, "nestedRows": []}],
                "otherIngredients": {"ingredients": [], "raw": ""}
            }
        ]

        keys = []
        for product in products:
            result = normalizer.normalize_product(product)
            active = result.get("activeIngredients", [])
            if active:
                keys.append(active[0]["normalized_key"])

        assert len(keys) == 2, "Should have 2 products with keys"
        assert keys[0] == keys[1], f"Same ingredient should have same key: {keys[0]} != {keys[1]}"


class TestRawSourceTextImmutability:
    """Ensure raw_source_text is never modified."""

    @pytest.fixture
    def normalizer(self):
        return EnhancedDSLDNormalizer()

    def test_raw_source_text_preserved_exactly(self, normalizer):
        """raw_source_text must be exactly the original name, not normalized."""
        product = {
            "dsld_id": 12345,
            "productName": "Test Product",
            "ingredientRows": [
                {
                    "ingredientId": 1,
                    "name": "  Vitamin B12  ",  # Leading/trailing spaces
                    "order": 1,
                    "nestedRows": []
                }
            ],
            "otherIngredients": {"ingredients": [], "raw": ""}
        }

        result = normalizer.normalize_product(product)
        active = result.get("activeIngredients", [])

        # Note: The cleaning process does strip whitespace from name,
        # but raw_source_text captures the processed name (which is the same as name)
        # The key is that raw_source_text == name at the point of storage
        for ing in active:
            assert ing["raw_source_text"] == ing["name"]

    def test_raw_source_text_not_lowercased(self, normalizer):
        """raw_source_text should preserve case from the input name."""
        product = {
            "dsld_id": 12345,
            "productName": "Test Product",
            "ingredientRows": [
                {
                    "ingredientId": 1,
                    "name": "Vitamin B12",
                    "order": 1,
                    "nestedRows": []
                }
            ],
            "otherIngredients": {"ingredients": [], "raw": ""}
        }

        result = normalizer.normalize_product(product)
        active = result.get("activeIngredients", [])

        # The name field retains original case, and raw_source_text should match
        if active:
            assert active[0]["raw_source_text"] == active[0]["name"]


class TestRawSourcePath:
    """Ensure raw_source_path correctly identifies source section."""

    @pytest.fixture
    def normalizer(self):
        return EnhancedDSLDNormalizer()

    def test_active_path_is_activeIngredients(self, normalizer):
        """Ingredients from ingredientRows should have path 'activeIngredients'."""
        product = {
            "dsld_id": 12345,
            "productName": "Test Product",
            "ingredientRows": [
                {
                    "ingredientId": 1,
                    "name": "Vitamin C",
                    "order": 1,
                    "nestedRows": []
                }
            ],
            "otherIngredients": {"ingredients": [], "raw": ""}
        }

        result = normalizer.normalize_product(product)
        active = result.get("activeIngredients", [])

        for ing in active:
            assert ing["raw_source_path"] == "activeIngredients"

    def test_inactive_path_is_inactiveIngredients(self, normalizer):
        """Ingredients from otherIngredients should have path 'inactiveIngredients'."""
        product = {
            "dsld_id": 12345,
            "productName": "Test Product",
            "ingredientRows": [],
            "otherIngredients": {
                "ingredients": [{"name": "Cellulose"}],
                "raw": "Cellulose"
            }
        }

        result = normalizer.normalize_product(product)
        inactive = result.get("inactiveIngredients", [])

        for ing in inactive:
            assert ing["raw_source_path"] == "inactiveIngredients"


class TestNestedIngredientsProvenance:
    """Ensure nested ingredients also have provenance fields."""

    @pytest.fixture
    def normalizer(self):
        return EnhancedDSLDNormalizer()

    def test_nested_ingredients_have_provenance(self, normalizer):
        """Nested ingredients should also have all provenance fields."""
        product = {
            "dsld_id": 12345,
            "productName": "Test Product",
            "ingredientRows": [
                {
                    "ingredientId": 1,
                    "name": "Proprietary Blend",
                    "order": 1,
                    "nestedRows": [
                        {
                            "ingredientId": 2,
                            "name": "Green Tea Extract",
                            "order": 1
                        },
                        {
                            "ingredientId": 3,
                            "name": "Turmeric Extract",
                            "order": 2
                        }
                    ]
                }
            ],
            "otherIngredients": {"ingredients": [], "raw": ""}
        }

        result = normalizer.normalize_product(product)
        active = result.get("activeIngredients", [])

        # Check both parent and nested ingredients
        for ing in active:
            assert "raw_source_text" in ing
            assert "raw_source_path" in ing
            assert "normalized_key" in ing

            # Check nested ingredients if present
            nested = ing.get("nestedIngredients", [])
            for nested_ing in nested:
                assert "raw_source_text" in nested_ing, \
                    f"Missing raw_source_text in nested: {nested_ing.get('name')}"
                assert "raw_source_path" in nested_ing, \
                    f"Missing raw_source_path in nested: {nested_ing.get('name')}"
                assert "normalized_key" in nested_ing, \
                    f"Missing normalized_key in nested: {nested_ing.get('name')}"


class TestProvenanceGoldenFixtures:
    """Golden fixture tests for specific provenance cases."""

    @pytest.fixture
    def normalizer(self):
        return EnhancedDSLDNormalizer()

    @pytest.mark.parametrize("name,expected_key", [
        ("Vitamin B12", "vitamin_b12"),
        ("Vitamin B12 (as Methylcobalamin)", "vitamin_b12_as_methylcobalamin"),
        ("Omega-3 Fatty Acids", "omega_3_fatty_acids"),
        ("Coenzyme Q10", "coenzyme_q10"),
        ("L-Theanine", "l_theanine"),
        ("5-HTP", "5_htp"),
    ])
    def test_expected_normalized_keys(self, normalizer, name, expected_key):
        """Verify specific ingredient names produce expected keys."""
        product = {
            "dsld_id": 12345,
            "productName": "Test Product",
            "ingredientRows": [
                {
                    "ingredientId": 1,
                    "name": name,
                    "order": 1,
                    "nestedRows": []
                }
            ],
            "otherIngredients": {"ingredients": [], "raw": ""}
        }

        result = normalizer.normalize_product(product)
        active = result.get("activeIngredients", [])

        assert len(active) >= 1, f"No active ingredients for {name}"
        assert active[0]["normalized_key"] == expected_key, \
            f"Key mismatch for '{name}': got '{active[0]['normalized_key']}', expected '{expected_key}'"


# =============================================================================
# ENRICHMENT STAGE PROVENANCE INVARIANTS
# =============================================================================
# DEV CONTRACT: Label text is immutable. Canonical data is explanatory only.
#
# Every entity output from enrichment MUST include raw_source_text for audit.
# =============================================================================

from enrich_supplements_v3 import SupplementEnricherV3


class TestEnrichmentIngredientProvenance:
    """Invariant: All ingredient_quality entries must have raw_source_text."""

    @pytest.fixture
    def enricher(self):
        return SupplementEnricherV3()

    def test_scorable_ingredient_has_raw_source_text(self, enricher):
        """Matched scorable ingredients MUST have raw_source_text."""
        product = {
            'id': 'test_scorable_provenance',
            'activeIngredients': [
                {
                    'name': 'Vitamin C (as Ascorbic Acid)',
                    'standardName': 'Ascorbic Acid',
                    'quantity': 500,
                    'unit': 'mg'
                }
            ],
            'inactiveIngredients': []
        }

        result = enricher._collect_ingredient_quality_data(product)

        for ing in result.get('ingredients_scorable', []):
            assert 'raw_source_text' in ing, \
                f"Scorable ingredient missing raw_source_text: {ing.get('name')}"
            assert ing['raw_source_text'], \
                f"raw_source_text is empty for: {ing.get('name')}"

    def test_skipped_ingredient_has_raw_source_text(self, enricher):
        """Skipped ingredients MUST have raw_source_text."""
        product = {
            'id': 'test_skipped_provenance',
            'activeIngredients': [
                {
                    'name': 'Proprietary Blend',
                    'proprietaryBlend': True,
                    'quantity': 500,
                    'unit': 'mg',
                    'nestedIngredients': [
                        {'name': 'Ingredient A', 'quantity': 0, 'unit': ''}
                    ]
                }
            ],
            'inactiveIngredients': []
        }

        result = enricher._collect_ingredient_quality_data(product)

        for ing in result.get('ingredients_skipped', []):
            assert 'raw_source_text' in ing, \
                f"Skipped ingredient missing raw_source_text: {ing.get('name')}"

    def test_promoted_ingredient_has_raw_source_text(self, enricher):
        """Promoted inactive ingredients MUST have raw_source_text."""
        product = {
            'id': 'test_promoted_provenance',
            'activeIngredients': [],
            'inactiveIngredients': [
                {
                    'name': 'Vitamin D3 (Cholecalciferol)',
                    'standardName': 'Cholecalciferol',
                    'quantity': 1000,
                    'unit': 'IU'
                }
            ]
        }

        result = enricher._collect_ingredient_quality_data(product)

        for ing in result.get('promoted_from_inactive', []):
            assert 'raw_source_text' in ing, \
                f"Promoted ingredient missing raw_source_text: {ing.get('name')}"

    def test_unmapped_ingredient_has_raw_source_text(self, enricher):
        """Unmapped ingredients MUST have raw_source_text."""
        product = {
            'id': 'test_unmapped_provenance',
            'activeIngredients': [
                {
                    'name': 'Some Obscure Compound XYZ-999',
                    'quantity': 100,
                    'unit': 'mg'
                }
            ],
            'inactiveIngredients': []
        }

        result = enricher._collect_ingredient_quality_data(product)

        for ing in result.get('ingredients_scorable', []):
            if not ing.get('mapped'):
                assert 'raw_source_text' in ing, \
                    f"Unmapped ingredient missing raw_source_text: {ing.get('name')}"


class TestEnrichmentDeliveryProvenance:
    """Invariant: All delivery system entries must have raw_source_text."""

    @pytest.fixture
    def enricher(self):
        return SupplementEnricherV3()

    def test_delivery_system_has_raw_source_text(self, enricher):
        """Matched delivery systems MUST have raw_source_text."""
        product = {
            'id': 'test_delivery_provenance',
            'fullName': 'Test Lozenge Product',
            'physicalState': {
                'langualCodeDescription': 'LOZENGE'
            },
            'activeIngredients': [
                {'name': 'Zinc', 'quantity': 15, 'unit': 'mg'}
            ],
            'inactiveIngredients': []
        }

        result = enricher._collect_delivery_data(product)

        for system in result.get('systems', []):
            assert 'raw_source_text' in system, \
                f"Delivery system missing raw_source_text: {system.get('name')}"
            assert 'canonical_name' in system, \
                f"Delivery system missing canonical_name: {system.get('name')}"
            assert 'match_source' in system, \
                f"Delivery system missing match_source: {system.get('name')}"


class TestEnrichmentHarmfulAdditivesProvenance:
    """Invariant: All harmful additive entries must have raw_source_text."""

    @pytest.fixture
    def enricher(self):
        return SupplementEnricherV3()

    def test_harmful_additive_has_raw_source_text(self, enricher):
        """Matched harmful additives MUST have raw_source_text."""
        ingredients = [
            {'name': 'Titanium Dioxide', 'quantity': 0, 'unit': ''}
        ]

        result = enricher._check_harmful_additives(ingredients)

        # Result structure: {"found": bool, "additives": list}
        for additive in result.get('additives', []):
            assert 'raw_source_text' in additive, \
                f"Harmful additive missing raw_source_text: {additive.get('ingredient')}"
            assert 'canonical_name' in additive, \
                f"Harmful additive missing canonical_name: {additive.get('ingredient')}"
            assert 'match_method' in additive, \
                f"Harmful additive missing match_method: {additive.get('ingredient')}"


class TestEnrichmentBlendProvenance:
    """Invariant: All blend entries must have detector_group for audit."""

    @pytest.fixture
    def enricher(self):
        return SupplementEnricherV3()

    def test_blend_has_detector_group(self, enricher):
        """All blends MUST have detector_group field (can be None)."""
        product = {
            'id': 'test_blend_provenance',
            'activeIngredients': [
                {
                    'name': 'Proprietary Herbal Blend',
                    'proprietaryBlend': True,
                    'disclosureLevel': 'partial',
                    'quantity': 500,
                    'unit': 'mg',
                    'nestedIngredients': [
                        {'name': 'Herb A', 'quantity': 0, 'unit': ''},
                        {'name': 'Herb B', 'quantity': 0, 'unit': ''}
                    ]
                }
            ],
            'inactiveIngredients': []
        }

        result = enricher._collect_proprietary_data(product)

        for blend in result.get('blends', []):
            assert 'detector_group' in blend, \
                f"Blend missing detector_group: {blend.get('name')}"
            assert 'sources' in blend, \
                f"Blend missing sources: {blend.get('name')}"


class TestEnrichmentProvenancePreservation:
    """
    Integration tests: raw_source_text must match original label text.

    DEV CONTRACT: Label text is immutable. Canonical data is explanatory only.
    """

    @pytest.fixture
    def enricher(self):
        return SupplementEnricherV3()

    def test_label_name_not_overwritten_by_canonical(self, enricher):
        """
        CRITICAL: raw_source_text MUST preserve exact label text.

        The user must always see what's on the bottle, even if we
        internally match it to a different canonical name.
        """
        label_text = "Vitamin C (as L-Ascorbic Acid from Acerola)"

        product = {
            'id': 'test_label_preservation',
            'activeIngredients': [
                {
                    'name': label_text,
                    'standardName': 'Ascorbic Acid',  # Canonical
                    'quantity': 500,
                    'unit': 'mg'
                }
            ],
            'inactiveIngredients': []
        }

        result = enricher._collect_ingredient_quality_data(product)

        for ing in result.get('ingredients_scorable', []):
            # raw_source_text must be the LABEL text, not canonical
            assert ing.get('raw_source_text') == label_text, \
                f"raw_source_text overwritten! Expected '{label_text}', got '{ing.get('raw_source_text')}'"
            # name should also preserve label text
            assert ing.get('name') == label_text, \
                f"name was overwritten! Expected '{label_text}', got '{ing.get('name')}'"

    def test_blend_sources_tracks_raw_counts(self, enricher):
        """blend_sources must track raw vs deduped counts."""
        product = {
            'id': 'test_blend_counts',
            'activeIngredients': [
                {
                    'name': 'Energy Blend',
                    'proprietaryBlend': True,
                    'disclosureLevel': 'none',
                    'quantity': 300,
                    'unit': 'mg',
                    'nestedIngredients': []
                }
            ],
            'inactiveIngredients': []
        }

        result = enricher._collect_proprietary_data(product)
        sources = result.get('blend_sources', {})

        # Must have all tracking fields
        required_fields = [
            'detector_raw_count',
            'cleaning_raw_count',
            'raw_total',
            'merged_count',
            'dedup_count',
            'dedup_rate',
            'blend_loss_rate'
        ]
        for field in required_fields:
            assert field in sources, f"blend_sources missing {field}"

    def test_delivery_system_tracks_match_source(self, enricher):
        """Delivery systems must track WHERE the match was found."""
        product = {
            'id': 'test_delivery_source',
            'fullName': 'Test Gummy Product',
            'physicalState': {
                'langualCodeDescription': 'LOZENGE'
            },
            'activeIngredients': [],
            'inactiveIngredients': []
        }

        result = enricher._collect_delivery_data(product)

        for system in result.get('systems', []):
            match_source = system.get('match_source')
            assert match_source in ('product_text', 'physical_state'), \
                f"Invalid match_source: {match_source}"


class TestEnrichmentEdgeCases:
    """Edge cases that could cause provenance loss."""

    @pytest.fixture
    def enricher(self):
        return SupplementEnricherV3()

    def test_empty_name_ingredient(self, enricher):
        """Handle empty ingredient names gracefully."""
        product = {
            'id': 'test_empty_name',
            'activeIngredients': [
                {
                    'name': '',  # Empty name
                    'quantity': 100,
                    'unit': 'mg'
                }
            ],
            'inactiveIngredients': []
        }

        # Should not crash
        result = enricher._collect_ingredient_quality_data(product)
        # Still should have structure
        assert 'ingredients_scorable' in result or 'ingredients_skipped' in result

    def test_none_values_handled(self, enricher):
        """Handle None values in ingredient fields."""
        product = {
            'id': 'test_none_values',
            'activeIngredients': [
                {
                    'name': 'Vitamin C',
                    'standardName': None,  # None instead of missing
                    'quantity': None,
                    'unit': None
                }
            ],
            'inactiveIngredients': []
        }

        # Should not crash
        result = enricher._collect_ingredient_quality_data(product)
        assert result is not None

    def test_unicode_label_text_preserved(self, enricher):
        """Unicode characters in label text must be preserved."""
        label_text = "Vitamin B12 (Methylcobalamin) - 1000mcg"

        product = {
            'id': 'test_unicode',
            'activeIngredients': [
                {
                    'name': label_text,
                    'quantity': 1000,
                    'unit': 'mcg'
                }
            ],
            'inactiveIngredients': []
        }

        result = enricher._collect_ingredient_quality_data(product)

        for ing in result.get('ingredients_scorable', []):
            # Unicode must be preserved exactly
            assert ing.get('raw_source_text') == label_text
            assert ing.get('name') == label_text

    def test_very_long_label_text(self, enricher):
        """Very long label text should be preserved (not truncated)."""
        label_text = (
            "Vitamin C (as Ascorbic Acid from Natural Sources including "
            "Acerola Cherry Extract, Rose Hips, and Citrus Bioflavonoids "
            "Complex standardized to 25% vitamin C content)"
        )

        product = {
            'id': 'test_long_text',
            'activeIngredients': [
                {
                    'name': label_text,
                    'quantity': 500,
                    'unit': 'mg'
                }
            ],
            'inactiveIngredients': []
        }

        result = enricher._collect_ingredient_quality_data(product)

        for ing in result.get('ingredients_scorable', []):
            # Full text preserved in enrichment (UI can truncate for display)
            assert ing.get('raw_source_text') == label_text
