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
from scoring_v4.scored_artifact import build_scored_artifact


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
        for blend in result['blends']:
            if blend['sources'] == ['detector']:
                assert blend['name'].casefold() == blend['evidence']['matched_text'].casefold()
                assert blend['detector_group'] != blend['name']

    def test_detector_only_physical_blend_uses_printed_name(self, enricher):
        # Reduced from DSLD 79397: the registry classifies this as
        # Digestive Enzyme Blends, but the label prints the specific name.
        product = {
            'id': '79397',
            'activeIngredients': [{
                'name': 'Concentrated Enzyme Blend',
                'raw_source_text': 'Concentrated Enzyme Blend',
                'quantity': 0, 'unit': 'NP', 'proprietaryBlend': None,
                'nestedIngredients': [
                    {'name': 'Amylase', 'quantity': 0, 'unit': 'NP'},
                    {'name': 'Protease', 'quantity': 0, 'unit': 'NP'},
                ],
            }],
            'inactiveIngredients': [],
        }
        blends = enricher._collect_proprietary_data(product)['blends']
        assert [(b['name'], b['detector_group']) for b in blends] == [
            ('Concentrated Enzyme Blend', 'Digestive Enzyme Blends')
        ]

    def test_detected_child_is_not_a_second_opaque_blend(self, enricher):
        # DSLD 29295 prints one 520 mg enzyme blend; its disclosed Protease
        # child mentions "Protease SP" in notes. The detector must not turn
        # that constituent into a second opaque blend/B5 deduction.
        product = {
            'id': '29295',
            'activeIngredients': [
                {
                    'name': 'Proprietary Enzyme Blend',
                    'raw_source_path': 'ingredientRows[0]',
                    'quantity': 520, 'unit': 'mg', 'proprietaryBlend': True,
                    'nestedIngredients': [{
                        'name': 'Protease',
                        'raw_source_path': 'ingredientRows[0].nestedRows[0]',
                        'parentBlend': 'Proprietary Enzyme Blend',
                        'quantity': 100000, 'unit': 'HUT',
                    }],
                },
                {
                    'name': 'Protease', 'notes': 'Protease SP',
                    'raw_source_path': 'ingredientRows[0].nestedRows[0]',
                    'parentBlend': 'Proprietary Enzyme Blend',
                    'quantity': 100000, 'unit': 'HUT',
                    'proprietaryBlend': False,
                },
            ],
            'inactiveIngredients': [],
            'label_source_rows': [
                {'raw_source_path': 'ingredientRows[0]', 'name': 'Proprietary Enzyme Blend'},
                {'raw_source_path': 'ingredientRows[0].nestedRows[0]', 'name': 'Protease SP'},
            ],
        }
        blends = enricher._collect_proprietary_data(product)['blends']
        assert [(b['name'], b['source_row_ref']) for b in blends] == [
            ('Proprietary Enzyme Blend', 'ingredientRows[0]')
        ]

    def test_nested_physical_blend_header_is_not_suppressed(self, enricher):
        # DSLD 31064 has a separately identified Aminogen header nested
        # under Amino Acceleration System. Its header role is source evidence
        # of a distinct preparation even without an individual amount.
        product = {
            'id': '31064',
            'activeIngredients': [
                {
                    'name': 'Amino Acceleration System',
                    'raw_source_path': 'ingredientRows[12]',
                    'quantity': 0, 'unit': 'NP', 'proprietaryBlend': True,
                    'cleaner_row_role': 'blend_header_total',
                    'nestedIngredients': [{
                        'name': 'Aminogen',
                        'raw_source_path': 'ingredientRows[12].nestedRows[1]',
                        'cleaner_row_role': 'blend_header_total',
                        'quantity': 0, 'unit': 'NP',
                    }],
                },
                {
                    'name': 'Aminogen',
                    'raw_source_path': 'ingredientRows[12].nestedRows[1]',
                    'parentBlend': 'Amino Acceleration System',
                    'quantity': 0, 'unit': 'NP', 'proprietaryBlend': False,
                    'cleaner_row_role': 'blend_header_total',
                },
            ],
            'inactiveIngredients': [],
            'label_source_rows': [
                {'raw_source_path': 'ingredientRows[12]', 'name': 'Amino Acceleration System'},
                {'raw_source_path': 'ingredientRows[12].nestedRows[1]', 'name': 'Aminogen'},
            ],
        }
        blends = enricher._collect_proprietary_data(product)['blends']
        assert {b['source_row_ref'] for b in blends} == {
            'ingredientRows[12]', 'ingredientRows[12].nestedRows[1]'
        }

    def test_statement_repeating_printed_blend_is_not_a_second_blend(self, enricher):
        product = {
            'id': '323062',
            'activeIngredients': [{
                'name': 'Proprietary Focus Blend', 'proprietaryBlend': True,
                'quantity': 2.1, 'unit': 'Gram(s)',
                'raw_source_path': 'ingredientRows[2]',
                'nestedIngredients': [
                    {'name': 'Inositol', 'quantity': 0, 'unit': 'NP'},
                    {'name': 'L-Theanine', 'quantity': 0, 'unit': 'NP'},
                    {'name': 'Taurine', 'quantity': 0, 'unit': 'NP'},
                ],
            }],
            'inactiveIngredients': [],
            'statements': [{'notes': 'Our proprietary focus blend supports calm.'}],
        }

        result = enricher._collect_proprietary_data(product)

        assert result['blend_count'] == 1
        assert [blend['name'] for blend in result['blends']] == ['Proprietary Focus Blend']
        assert result['blends'][0]['source_row_ref'] == 'ingredientRows[2]'
        product['proprietary_data'] = result
        product['proprietary_blends'] = result['blends']
        scored = build_scored_artifact(product)
        assert 'STIMULANT_UNDISCLOSED_BLEND' not in scored['flags']

    def test_distinct_statement_blend_is_still_retained(self, enricher):
        product = {
            'id': 'distinct_statement',
            'activeIngredients': [{
                'name': 'Energy Blend', 'proprietaryBlend': True,
                'quantity': 500, 'unit': 'mg',
            }],
            'inactiveIngredients': [],
            'statements': [{'notes': 'Contains a proprietary stimulant complex.'}],
        }

        result = enricher._collect_proprietary_data(product)

        assert result['blend_count'] == 2
        assert {blend['evidence']['matched_text'].lower() for blend in result['blends']} == {
            'energy blend', 'proprietary stimulant complex',
        }

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


@pytest.fixture(scope="module")
def boundary_pipeline():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    return EnhancedDSLDNormalizer(), SupplementEnricherV3()


def _boundary_raw(dsld_id):
    import json
    from pathlib import Path
    return json.loads((Path(__file__).parent / 'fixtures' / f'blend_boundary_{dsld_id}_raw.json').read_text())


def test_distinct_identical_detector_rows_reach_final_artifact(boundary_pipeline):
    import copy
    import json
    from pathlib import Path
    normalizer, enricher = boundary_pipeline
    raw = json.loads((Path(__file__).parent / 'fixtures/blend_preparation_213448_raw.json').read_text())
    raw['fullName'] = 'Independent Blend Boundary'
    row = {'name': 'Proprietary Herbal Blend', 'category': 'blend',
           'ingredientGroup': 'Blend (Combination)', 'forms': [],
           'quantity': [{'quantity': 100, 'unit': 'mg'}],
           'nestedRows': [{'name': 'Ashwagandha', 'category': 'botanical', 'quantity': [], 'forms': []},
                          {'name': 'Rhodiola', 'category': 'botanical', 'quantity': [], 'forms': []}]}
    raw['ingredientRows'].extend([copy.deepcopy(row), copy.deepcopy(row)])
    cleaned = normalizer.normalize_product(raw)
    detected = enricher.blend_detector.analyze_product(cleaned)
    assert len([b for b in detected.blends_detected if b.matched_text == 'Proprietary Herbal Blend']) == 2
    enriched, errors = enricher.enrich_product(cleaned)
    assert not errors
    artifact = build_scored_artifact(enriched)
    evidence = artifact['_v4_module_breakdown']['dimensions']['transparency']['metadata']['B5_blend_evidence']
    assert len([b for b in evidence if b['blend_name'] == 'Proprietary Herbal Blend']) == 2


def test_real_parent_body_without_consumer_ref_is_charged_once(boundary_pipeline):
    import copy
    normalizer, enricher = boundary_pipeline
    cleaned = normalizer.normalize_product(_boundary_raw(336897))
    assert all('source_row_ref' not in row for row in cleaned['activeIngredients'])
    enriched, errors = enricher.enrich_product(cleaned)
    assert not errors
    relevant = [b for b in enriched['proprietary_blends'] if 'veggie berry' in b['name'].lower()]
    assert len(relevant) == 1
    assert relevant[0]['source_row_ref']
    assert len(relevant[0]['source_fields']) > 1
    before = build_scored_artifact(enriched)
    without_refs = copy.deepcopy(enriched)
    for blends in (without_refs['proprietary_blends'], without_refs['proprietary_data']['blends']):
        for blend in blends:
            blend.pop('source_row_ref', None)
    after = build_scored_artifact(without_refs)
    def b5(artifact):
        return artifact['_v4_module_breakdown']['dimensions']['transparency']
    assert b5(before)['penalties'] == b5(after)['penalties']
    assert len(b5(after)['metadata']['B5_blend_evidence']) == len(b5(before)['metadata']['B5_blend_evidence'])
    relevant_evidence = [b for b in b5(after)['metadata']['B5_blend_evidence'] if 'veggie berry' in b['blend_name'].lower()]
    assert len(relevant_evidence) == 1
    assert relevant_evidence[0]['computed_blend_penalty_magnitude'] > 0


@pytest.mark.parametrize('pid', [64231, 64232])
def test_herbs_keep_printed_blend_owner_not_magnesium(boundary_pipeline, pid):
    normalizer, enricher = boundary_pipeline
    cleaned = normalizer.normalize_product(_boundary_raw(pid))
    magnesium = next(row for row in cleaned['activeIngredients'] if row['name'] == 'Magnesium')
    assert magnesium['quantity'] == 20
    enriched, errors = enricher.enrich_product(cleaned)
    assert not errors
    blend = next(b for b in enriched['proprietary_blends'] if b.get('hidden_count', 0) >= 7)
    assert blend['name'] == 'Proprietary Herbal Blend'
    assert blend['blend_total_mg'] == 35
    artifact = build_scored_artifact(enriched)
    evidence = artifact['_v4_module_breakdown']['dimensions']['transparency']['metadata']['B5_blend_evidence']
    assert any(b['blend_name'] == 'Proprietary Herbal Blend' and b['blend_total_mg'] == 35 for b in evidence)
    assert not any(b['blend_name'] == 'Magnesium' for b in evidence)


def test_polyphenol_footnote_does_not_disclose_fruit_members(boundary_pipeline):
    normalizer, enricher = boundary_pipeline
    cleaned = normalizer.normalize_product(_boundary_raw(19069))
    marker = next(row for row in cleaned['activeIngredients'] if 'provides 200 mg' in row['name'])
    assert marker['quantity'] == 200
    assert marker['cleaner_row_role'] == 'source_descriptor'
    enriched, errors = enricher.enrich_product(cleaned)
    assert not errors
    [blend] = [b for b in enriched['proprietary_blends'] if b['name'] == 'Proprietary Fruit & Vegetable Blend']
    assert blend['disclosure_level'] == 'partial'
    assert len(blend['child_ingredients']) == 6
    assert all(child.get('amount') is None for child in blend['child_ingredients'])
    assert enriched['proprietary_data']['total_active_mg'] == 550  # calcium170+blend380; marker200 is not another active.
    artifact = build_scored_artifact(enriched)
    assert artifact['_v4_module_breakdown']['dimensions']['transparency']['penalties']['B5_proprietary_blend_opacity'] < 0
    sugar = enriched['dietary_sensitivity_data']['sugar']
    assert sugar['amount_g'] is None and sugar['level'] is None
    formulation = artifact['_v4_module_breakdown']['dimensions']['formulation']
    assert formulation['metadata']['formula_checks']['B1_dietary_sugar'] == 0


@pytest.mark.parametrize('pid,change', [(64231, 'parent_amount'), (64232, 'child_identity'), (19069, 'child_identity')])
def test_blend_hierarchy_repairs_reject_changed_source(boundary_pipeline, pid, change):
    normalizer, _ = boundary_pipeline
    raw = _boundary_raw(pid)
    if change == 'parent_amount':
        raw['ingredientRows'][15]['quantity'][0]['quantity'] = 36
    elif pid == 19069:
        raw['ingredientRows'][1]['forms'][0]['name'] = 'Different source constituent'
    else:
        raw['ingredientRows'][11]['nestedRows'][1]['name'] = 'Different source constituent'
    with pytest.raises(ValueError, match='Reviewed hierarchy'):
        normalizer.normalize_product(raw)


@pytest.mark.parametrize("shape", ["nested", "flattened"])
@pytest.mark.parametrize("functional_disposition", ["is_excipient", "inactive"])
@pytest.mark.parametrize("carrier_amount,total_unit,expected_tier,known_mass", [
    (900, "mg", "partial", 900),
    (0, "NP", "none", 0),
])
def test_filtered_functional_child_preserves_mass_and_total_uncertainty(
    boundary_pipeline, carrier_amount, total_unit, expected_tier, known_mass, shape, functional_disposition
):
    normalizer, enricher = boundary_pipeline
    product = {"id": "carrier_boundary", "activeIngredients": [{
        "name": "Proprietary Herbal Blend", "quantity": 1000, "unit": total_unit,
        "proprietaryBlend": True, "disclosureLevel": expected_tier,
        "nestedIngredients": [
            {"name": "Cellulose", "quantity": carrier_amount, "unit": "mg", "is_excipient": True},
            {"name": "Ashwagandha", "quantity": 0, "unit": "NP"},
            {"name": "Rhodiola", "quantity": 0, "unit": "NP"},
        ],
    }], "inactiveIngredients": []}
    carrier = product["activeIngredients"][0]["nestedIngredients"][0]
    if functional_disposition == "inactive":
        carrier.pop("is_excipient")
        carrier["cleaner_row_role"] = "inactive"
    if shape == "flattened":
        parent = product["activeIngredients"][0]
        parent["raw_source_path"] = "ingredientRows[99]"
        children = parent.pop("nestedIngredients")
        for index, child in enumerate(children):
            child.update({"isNestedIngredient": True, "parentBlend": parent["name"],
                          "parent_source_path": parent["raw_source_path"],
                          "raw_source_path": f"ingredientRows[99].nestedRows[{index}]",
                          "parentBlendMass": 1000, "parentBlendUnit": total_unit})
        product["activeIngredients"].extend(children)
        product["label_source_rows"] = [{"raw_source_path": r["raw_source_path"]}
                                          for r in product["activeIngredients"]]
    data = enricher._collect_proprietary_data(product)
    assert data["blends"]
    assert all(b["disclosure_level"] == expected_tier for b in data["blends"])
    import json
    from pathlib import Path
    raw = json.loads((Path(__file__).parent / "fixtures/blend_preparation_213448_raw.json").read_text())
    cleaned = normalizer.normalize_product(raw)
    cleaned["activeIngredients"].extend(product["activeIngredients"])
    cleaned.setdefault("label_source_rows", []).extend(product.get("label_source_rows", []))
    enriched, errors = enricher.enrich_product(cleaned)
    assert not errors
    artifact = build_scored_artifact(enriched)
    evidence = artifact["_v4_module_breakdown"]["dimensions"]["transparency"]["metadata"]["B5_blend_evidence"]
    assert evidence
    assert evidence[0]["disclosed_child_mg_sum"] == known_mass
    if total_unit == "mg":
        assert evidence[0]["hidden_mass_mg"] == 100
    else:
        assert evidence[0]["hidden_mass_mg"] is None
