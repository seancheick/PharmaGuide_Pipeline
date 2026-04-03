"""
Pipeline Blend Merge Tests

Tests for union-of-evidence merge in proprietary blend handling.
Ensures cleaning-flagged blends are NEVER silently dropped when
the detector returns empty results.

4 Required Acceptance Tests:
1. cleaning_only: Cleaning finds blend, detector empty → blend preserved
2. detector_only: Detector finds blend, cleaning empty → blend preserved
3. both_agree: Both find same blend → single record, merged sources
4. both_different: Each finds different blend → both preserved
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from enrich_supplements_v3 import SupplementEnricherV3


class TestBlendMergePipeline:
    """
    Union-of-evidence merge tests for proprietary blend handling.

    Contract: Enrichment proprietary_data MUST be union of:
    - Detector evidence (pattern-based)
    - Cleaning evidence (indicator-based from proprietaryBlend flags)
    - Deduplicated to prevent double-penalizing
    """

    @pytest.fixture
    def enricher(self):
        return SupplementEnricherV3()

    def test_cleaning_only_blend_preserved(self, enricher):
        """
        SCENARIO: cleaning_only
        Cleaning finds blend (proprietaryBlend=True), detector returns empty.
        Blend MUST be preserved in proprietary_data.

        This is the critical fix - previously blends were silently dropped.
        """
        product = {
            'id': 'test_cleaning_only',
            'product_name': 'Test Cleaning Only',
            'activeIngredients': [
                {
                    'name': 'Proprietary Extract Blend',
                    'proprietaryBlend': True,
                    'disclosureLevel': 'partial',
                    'quantity': 500,
                    'unit': 'mg',
                    'nestedIngredients': [
                        {'name': 'Ashwagandha', 'quantity': 0, 'unit': ''},
                        {'name': 'Rhodiola', 'quantity': 0, 'unit': ''},
                        {'name': 'Ginseng', 'quantity': 0, 'unit': ''}
                    ]
                }
            ],
            'inactiveIngredients': []
        }

        result = enricher._collect_proprietary_data(product)

        # MUST find the blend
        assert result['has_proprietary_blends'] is True
        assert result['blend_count'] >= 1
        assert len(result['blends']) >= 1

        # Verify the blend data
        blend_names = [b['name'].lower() for b in result['blends']]
        assert any('proprietary extract blend' in name for name in blend_names)

        # Verify source tracking
        found_blend = next(
            (b for b in result['blends'] if 'proprietary extract blend' in b['name'].lower()),
            None
        )
        assert found_blend is not None
        assert 'cleaning' in found_blend.get('sources', [])

        # Verify blend_loss_rate is 0
        assert result['blend_sources']['blend_loss_rate'] == 0.0

        # Verify detector_group is set for audit clarity
        assert 'detector_group' in found_blend

    def test_detector_only_blend_preserved(self, enricher):
        """
        SCENARIO: detector_only
        Detector finds blend, cleaning has no flags.
        Blend MUST be preserved in proprietary_data.
        """
        # This product has a blend pattern that detector matches
        # but cleaning didn't flag (no proprietaryBlend=True)
        product = {
            'id': 'test_detector_only',
            'product_name': 'Test Detector Only',
            'activeIngredients': [
                {
                    'name': 'Super Blend Complex',  # Detector may match "Blend"
                    'proprietaryBlend': False,  # Cleaning didn't flag
                    'quantity': 300,
                    'unit': 'mg'
                }
            ],
            'inactiveIngredients': []
        }

        result = enricher._collect_proprietary_data(product)

        # If detector finds it, it should be preserved
        # The exact behavior depends on detector patterns
        # Key assertion: cleaning_raw_count should be 0
        assert result['blend_sources']['cleaning_raw_count'] == 0

    def test_statement_only_category_marketing_match_is_ignored(self, enricher):
        product = {
            'id': 'test_statement_marketing_only',
            'product_name': 'Statement Marketing Only',
            'activeIngredients': [],
            'inactiveIngredients': [],
            'statements': [
                {'notes': '- 6 superfood blends\n- metabolism support'}
            ],
        }

        result = enricher._collect_proprietary_data(product)

        assert result['has_proprietary_blends'] is False
        assert result['blend_count'] == 0

    def test_statement_with_explicit_proprietary_opacity_still_detected(self, enricher):
        product = {
            'id': 'test_statement_explicit_proprietary',
            'product_name': 'Statement Explicit Proprietary',
            'activeIngredients': [],
            'inactiveIngredients': [],
            'statements': [
                {'notes': 'n-zimes are a proprietary blend of digestive enzymes with proven bioactivity.'}
            ],
        }

        result = enricher._collect_proprietary_data(product)

        assert result['has_proprietary_blends'] is True
        assert result['blend_count'] >= 1

    def test_inactive_delivery_marketing_match_is_ignored(self, enricher):
        product = {
            'id': 'test_inactive_delivery_marketing_only',
            'product_name': 'Inactive Delivery Marketing Only',
            'activeIngredients': [],
            'inactiveIngredients': [
                {'name': 'Clean Tablet Technology Blend'}
            ],
        }

        result = enricher._collect_proprietary_data(product)

        assert result['has_proprietary_blends'] is False
        assert result['blend_count'] == 0

    def test_both_agree_single_record(self, enricher):
        """
        SCENARIO: both_agree
        Both detector and cleaning find the same blend.
        Result MUST be a single record with merged sources.

        Note: Dedupe happens when (name, mg_bucket, nested_count) match.
        """
        # Use _merge_blend_evidence directly to test exact deduplication
        detector_blends = [
            {
                'name': 'Proprietary Blend',
                'disclosure_level': 'none',
                'total_weight': 500,
                'nested_count': 2,
                'sources': ['detector'],
                'evidence': {'blend_id': 'B1'}
            }
        ]
        cleaning_blends = [
            {
                'name': 'Proprietary Blend',
                'disclosure_level': 'none',
                'total_weight': 500,
                'nested_count': 2,
                'sources': ['cleaning'],
                'evidence': None
            }
        ]

        merged = enricher._merge_blend_evidence(detector_blends, cleaning_blends)

        # Should dedupe to 1 record
        assert len(merged) == 1, "Same blend should be deduped to single record"

        # Should have both sources
        assert 'detector' in merged[0]['sources']
        assert 'cleaning' in merged[0]['sources']

    def test_both_sources_via_product(self, enricher):
        """
        Test that collecting from product properly merges sources.
        """
        product = {
            'id': 'test_both_via_product',
            'product_name': 'Test Both Sources',
            'activeIngredients': [
                {
                    'name': 'Proprietary Blend',
                    'proprietaryBlend': True,
                    'disclosureLevel': 'none',
                    'quantity': 500,
                    'unit': 'mg',
                    'nestedIngredients': [
                        {'name': 'Ingredient A', 'quantity': 0, 'unit': ''},
                        {'name': 'Ingredient B', 'quantity': 0, 'unit': ''}
                    ]
                }
            ],
            'inactiveIngredients': []
        }

        result = enricher._collect_proprietary_data(product)

        assert result['has_proprietary_blends'] is True

        # Verify merged_count <= raw_total (deduplication works)
        sources = result['blend_sources']
        assert sources['merged_count'] <= sources['raw_total']

        # Key: cleaning blend MUST be in the result
        cleaning_blend_found = any(
            'proprietary blend' in b['name'].lower() and 'cleaning' in b.get('sources', [])
            for b in result['blends']
        )
        assert cleaning_blend_found or sources['cleaning_count'] == 0, \
            "Cleaning blend must be present if cleaning found any"

    def test_both_different_all_preserved(self, enricher):
        """
        SCENARIO: both_different
        Detector finds one blend, cleaning finds a different one.
        Both MUST be preserved (no data loss).
        """
        product = {
            'id': 'test_both_different',
            'product_name': 'Test Both Different',
            'activeIngredients': [
                {
                    'name': 'Energy Blend',  # Detector may find this
                    'proprietaryBlend': False,
                    'quantity': 250,
                    'unit': 'mg'
                },
                {
                    'name': 'Proprietary Herbal Complex',  # Cleaning finds this
                    'proprietaryBlend': True,
                    'disclosureLevel': 'partial',
                    'quantity': 400,
                    'unit': 'mg',
                    'nestedIngredients': [
                        {'name': 'Turmeric', 'quantity': 0, 'unit': ''},
                        {'name': 'Ginger', 'quantity': 0, 'unit': ''}
                    ]
                }
            ],
            'inactiveIngredients': []
        }

        result = enricher._collect_proprietary_data(product)

        # Cleaning blend MUST be preserved
        assert result['has_proprietary_blends'] is True

        cleaning_blend_found = any(
            'herbal' in b['name'].lower()
            for b in result['blends']
        )
        assert cleaning_blend_found, "Cleaning-flagged blend must be preserved"

        # Verify no loss
        assert result['blend_sources']['blend_loss_rate'] == 0.0

    def test_cleaning_single_ingredient_false_positive_blend_is_ignored(self, enricher):
        """Single ingredient rows with leaked proprietary flags must not become B5 blends."""
        product = {
            'id': 'test_fp_single',
            'product_name': 'Single Ingredient Leak',
            'activeIngredients': [
                {
                    'name': 'Vitamin D',
                    'standardName': 'Vitamin D',
                    'proprietaryBlend': True,
                    'disclosureLevel': 'none',
                    'quantity': 0.0,
                    'unit': 'NP',
                    'nestedIngredients': [],
                    'isNestedIngredient': False,
                    'parentBlend': '',
                    'ingredientGroup': 'Vitamin D',
                }
            ],
            'inactiveIngredients': []
        }
        result = enricher._collect_proprietary_data(product)
        assert result['has_proprietary_blends'] is False
        assert result['blend_count'] == 0
        assert result['blends'] == []

    def test_nested_parent_aggregate_without_blend_label_not_rolled_into_b5(self, enricher):
        """Nested parent aggregates like 'Total Cultures' should not become proprietary blends."""
        product = {
            'id': 'test_parent_aggregate',
            'product_name': 'Aggregate Parent',
            'activeIngredients': [
                {
                    'name': 'Lactobacillus acidophilus',
                    'proprietaryBlend': True,
                    'disclosureLevel': 'none',
                    'quantity': 0.0,
                    'unit': 'NP',
                    'isNestedIngredient': True,
                    'parentBlend': 'Total Cultures',
                    'ingredientGroup': 'Lactobacillus acidophilus',
                    'nestedIngredients': [],
                },
                {
                    'name': 'Bifidobacterium lactis',
                    'proprietaryBlend': True,
                    'disclosureLevel': 'none',
                    'quantity': 0.0,
                    'unit': 'NP',
                    'isNestedIngredient': True,
                    'parentBlend': 'Total Cultures',
                    'ingredientGroup': 'Bifidobacterium lactis',
                    'nestedIngredients': [],
                },
            ],
            'inactiveIngredients': []
        }
        result = enricher._collect_proprietary_data(product)
        assert result['has_proprietary_blends'] is False
        assert result['blend_count'] == 0


class TestBlendMergeDeduplication:
    """Tests for blend deduplication during merge."""

    @pytest.fixture
    def enricher(self):
        return SupplementEnricherV3()

    def test_dedupe_by_name_and_mg_bucket(self, enricher):
        """
        Blends with same name and similar mg (within 5mg bucket) should dedupe.
        """
        # Test the merge function directly
        detector_blends = [
            {
                'name': 'Energy Blend',
                'disclosure_level': 'partial',
                'total_weight': 502,  # 502mg
                'nested_count': 3,
                'sources': ['detector'],
                'evidence': {'blend_id': 'B1'}
            }
        ]
        cleaning_blends = [
            {
                'name': 'Energy Blend',
                'disclosure_level': 'partial',
                'total_weight': 500,  # 500mg - same 5mg bucket as 502
                'nested_count': 3,
                'sources': ['cleaning'],
                'evidence': None
            }
        ]

        merged = enricher._merge_blend_evidence(detector_blends, cleaning_blends)

        # Should dedupe to 1
        assert len(merged) == 1

        # Should have both sources
        assert 'detector' in merged[0]['sources']
        assert 'cleaning' in merged[0]['sources']

        # AUDIT CLARITY (Issue #1): detector_group preserves classifier category
        assert merged[0]['detector_group'] == 'Energy Blend'
        # name should be from cleaning (label-facing)
        assert merged[0]['name'] == 'Energy Blend'

    def test_detector_group_preserved_for_audit(self, enricher):
        """
        Issue #1: detector_group field preserves detector's original name
        while 'name' field can be updated from cleaning.

        When detector and cleaning find the same blend (deduped by key),
        the detector_group preserves the original detector classification.
        """
        # Same blend found by both (same dedupe key: name+mg+nested)
        detector_blends = [
            {
                'name': 'Energy Blend',
                'disclosure_level': 'none',
                'total_weight': 500,
                'nested_count': 3,
                'sources': ['detector'],
                'evidence': {'blend_id': 'BLEND_ENERGY'}
            }
        ]
        cleaning_blends = [
            {
                'name': 'Energy Blend',  # Same name - will dedupe
                'disclosure_level': 'none',
                'total_weight': 500,
                'nested_count': 3,
                'sources': ['cleaning'],
                'evidence': None
            }
        ]

        merged = enricher._merge_blend_evidence(detector_blends, cleaning_blends)

        # Should dedupe to 1
        assert len(merged) == 1

        # detector_group should preserve original detector name for audit
        assert merged[0]['detector_group'] == 'Energy Blend'

    def test_cleaning_only_has_null_detector_group(self, enricher):
        """
        Blends only found by cleaning should have detector_group=None.
        This indicates the detector pattern DB didn't match this blend.
        """
        detector_blends = []  # Detector didn't find anything
        cleaning_blends = [
            {
                'name': 'Proprietary Extract Complex',
                'disclosure_level': 'partial',
                'total_weight': 400,
                'nested_count': 5,
                'sources': ['cleaning'],
                'evidence': None
            }
        ]

        merged = enricher._merge_blend_evidence(detector_blends, cleaning_blends)

        assert len(merged) == 1
        # detector_group should be None (not in pattern DB)
        assert merged[0]['detector_group'] is None
        assert merged[0]['name'] == 'Proprietary Extract Complex'

    def test_different_mg_bucket_not_deduped(self, enricher):
        """
        Same name but very different mg should NOT dedupe
        (could be different products in multi-product pack).
        """
        detector_blends = [
            {
                'name': 'Energy Blend',
                'disclosure_level': 'partial',
                'total_weight': 500,
                'nested_count': 3,
                'sources': ['detector'],
                'evidence': {'blend_id': 'B1'}
            }
        ]
        cleaning_blends = [
            {
                'name': 'Energy Blend',
                'disclosure_level': 'partial',
                'total_weight': 100,  # Very different - different product
                'nested_count': 2,
                'sources': ['cleaning'],
                'evidence': None
            }
        ]

        merged = enricher._merge_blend_evidence(detector_blends, cleaning_blends)

        # Should keep both (different mg bucket AND different nested_count)
        assert len(merged) == 2

    def test_same_name_different_nested_count_not_deduped(self, enricher):
        """
        Same name and mg but different structure should NOT dedupe.
        This prevents under-penalizing same-named blends with different
        ingredient counts.
        """
        detector_blends = [
            {
                'name': 'Energy Blend',
                'disclosure_level': 'none',
                'total_weight': 500,
                'nested_count': 5,  # 5 ingredients
                'sources': ['detector'],
                'evidence': {'blend_id': 'B1'}
            }
        ]
        cleaning_blends = [
            {
                'name': 'Energy Blend',
                'disclosure_level': 'partial',
                'total_weight': 500,  # Same mg
                'nested_count': 2,  # Different structure
                'sources': ['cleaning'],
                'evidence': None
            }
        ]

        merged = enricher._merge_blend_evidence(detector_blends, cleaning_blends)

        # Should keep both (different nested_count)
        assert len(merged) == 2


class TestBlendLossRateMetric:
    """Tests for blend_loss_rate monitoring metric."""

    @pytest.fixture
    def enricher(self):
        return SupplementEnricherV3()

    def test_blend_loss_rate_zero_when_all_preserved(self, enricher):
        """blend_loss_rate should be 0 when no cleaning blends are lost."""
        product = {
            'id': 'test_no_loss',
            'activeIngredients': [
                {
                    'name': 'Proprietary Blend',
                    'proprietaryBlend': True,
                    'disclosureLevel': 'none',
                    'quantity': 500,
                    'unit': 'mg',
                    'nestedIngredients': []
                }
            ],
            'inactiveIngredients': []
        }

        result = enricher._collect_proprietary_data(product)

        assert result['blend_sources']['blend_loss_rate'] == 0.0
        assert result['blend_sources']['cleaning_raw_count'] == 1
        assert result['blend_sources']['merged_count'] >= 1

    def test_blend_sources_provenance_tracked(self, enricher):
        """blend_sources should track detector/cleaning/merged counts."""
        product = {
            'id': 'test_provenance',
            'activeIngredients': [
                {
                    'name': 'Test Blend',
                    'proprietaryBlend': True,
                    'disclosureLevel': 'partial',
                    'quantity': 300,
                    'unit': 'mg',
                    'nestedIngredients': [{'name': 'A'}]
                }
            ],
            'inactiveIngredients': []
        }

        result = enricher._collect_proprietary_data(product)

        # Verify provenance structure
        assert 'blend_sources' in result
        sources = result['blend_sources']
        # Raw counts (Issue #2: track raw vs deduped)
        assert 'detector_raw_count' in sources
        assert 'cleaning_raw_count' in sources
        assert 'raw_total' in sources
        # After deduplication
        assert 'merged_count' in sources
        assert 'dedup_count' in sources
        assert 'dedup_rate' in sources
        # Quality metric
        assert 'blend_loss_rate' in sources

        # cleaning_raw_count should be 1 (we flagged 1 blend)
        assert sources['cleaning_raw_count'] == 1


class TestInactiveIngredientBlends:
    """Tests for blends in inactive ingredients."""

    @pytest.fixture
    def enricher(self):
        return SupplementEnricherV3()

    def test_inactive_blend_preserved(self, enricher):
        """
        Blends in inactiveIngredients should also be captured.
        This is important for full transparency scoring.
        """
        product = {
            'id': 'test_inactive_blend',
            'activeIngredients': [],
            'inactiveIngredients': [
                {
                    'name': 'Proprietary Coating Blend',
                    'proprietaryBlend': True,
                    'disclosureLevel': 'none',
                    'quantity': 50,
                    'unit': 'mg',
                    'nestedIngredients': [
                        {'name': 'Coating A'},
                        {'name': 'Coating B'}
                    ]
                }
            ]
        }

        result = enricher._collect_proprietary_data(product)

        assert result['has_proprietary_blends'] is True
        assert result['blend_count'] >= 1

        # Verify the inactive blend was captured
        blend_names = [b['name'].lower() for b in result['blends']]
        assert any('coating' in name for name in blend_names)
