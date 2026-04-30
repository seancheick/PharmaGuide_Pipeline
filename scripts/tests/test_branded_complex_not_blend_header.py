#!/usr/bin/env python3
"""
Branded single-active ingredients ending in "Complex" or "Blend" must NOT
be skipped as blend headers (Round 2 anomaly fix).

Bug discovered 2026-04-30: 16 products with mapped IQM-recognized branded
single-actives were silently dropped as `blend_header_total_weight_only`
because:
1. Their name matches the LOW_CONFIDENCE blend pattern `\\bcomplex$` or
   `\\bblend$` (e.g., "BioCell Collagen hydrolyzed Collagen Complex",
   "Diindolylmethane Complex", "Turmeric (Curcuma longa) Blend")
2. The cleaner sets hierarchy_type='source' on parents that have a
   source-descriptor form ("Chicken Sternal Cartilage" for BioCell)
3. B4 in `_should_skip_from_scoring` treats hierarchy_type='source' as
   structural-blend evidence and applies the low-confidence skip

Fix: source descriptors describe ingredient ORIGIN (where the active comes
from), not blend NATURE. They must not be treated as blend-header
evidence. Only true 'summary' and 'blend_header' hierarchy types should
trigger structural-blend signal.

Affected products (sample):
  Pure Encapsulations Collagen JS         BioCell Collagen Complex
  Pure Encapsulations DIMPRO 100          Diindolylmethane Complex
  Nature Made Turmeric Curcumin           Turmeric (Curcuma longa) Blend
"""

import json
import logging
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
logging.disable(logging.CRITICAL)

from enrich_supplements_v3 import SupplementEnricherV3  # noqa: E402


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3()


def _make_ingredient(name, qty=1000, unit='mg', hierarchy_type='source'):
    """Construct an ingredient row matching the BioCell pattern."""
    return {
        'name': name,
        'standardName': '',
        'quantity': qty,
        'unit': unit,
        'amount': {'unit': unit, 'value': qty},
        'hierarchyType': hierarchy_type,
        'mapped': True,
    }


def test_biocell_collagen_complex_not_blend_header(enricher):
    """BioCell Collagen Complex is a single branded active, not a blend."""
    ing = _make_ingredient("BioCell Collagen hydrolyzed Collagen Complex")
    skip_reason = enricher._should_skip_from_scoring(
        ing, enricher.databases.get('ingredient_quality_map', {}),
        enricher.databases.get('standardized_botanicals', {}),
    )
    assert skip_reason is None, (
        f"BioCell Collagen Complex must NOT be skipped — got skip_reason={skip_reason!r}. "
        "It is a branded single-active ingredient with a source descriptor."
    )


def test_diindolylmethane_complex_not_blend_header(enricher):
    """DIM Complex (Diindolylmethane Complex) is a single active."""
    ing = _make_ingredient("Diindolylmethane Complex")
    skip_reason = enricher._should_skip_from_scoring(
        ing, enricher.databases.get('ingredient_quality_map', {}),
        enricher.databases.get('standardized_botanicals', {}),
    )
    assert skip_reason is None


def test_turmeric_blend_with_source_descriptor_not_blend_header(enricher):
    """Turmeric (Curcuma longa) Blend with source-descriptor hierarchy
    must not be filtered as a blend header."""
    ing = _make_ingredient("Turmeric (Curcuma longa) Blend", hierarchy_type='source')
    skip_reason = enricher._should_skip_from_scoring(
        ing, enricher.databases.get('ingredient_quality_map', {}),
        enricher.databases.get('standardized_botanicals', {}),
    )
    assert skip_reason is None


# ---------------------------------------------------------------------------
# Real blend headers must STILL be skipped
# ---------------------------------------------------------------------------


def test_proprietary_blend_with_dose_still_skipped(enricher):
    """Explicit proprietary blend with structural flag — still skip."""
    ing = {
        'name': 'Energy Boost Proprietary Blend',
        'standardName': '',
        'quantity': 500, 'unit': 'mg',
        'amount': {'unit': 'mg', 'value': 500},
        'proprietaryBlend': True,
        'ingredientGroup': 'Proprietary Blend',
        'hierarchyType': 'blend_header',
        'mapped': False,
    }
    skip_reason = enricher._should_skip_from_scoring(
        ing, enricher.databases.get('ingredient_quality_map', {}),
        enricher.databases.get('standardized_botanicals', {}),
    )
    assert skip_reason is not None, "Genuine proprietary blend must still be skipped"


def test_summary_hierarchy_blend_complex_still_skipped(enricher):
    """hierarchy_type='summary' is a real blend-header signal — keep skip."""
    ing = {
        'name': 'Total Antioxidant Complex',
        'standardName': '',
        'quantity': 250, 'unit': 'mg',
        'amount': {'unit': 'mg', 'value': 250},
        'hierarchyType': 'summary',
        'mapped': False,
    }
    skip_reason = enricher._should_skip_from_scoring(
        ing, enricher.databases.get('ingredient_quality_map', {}),
        enricher.databases.get('standardized_botanicals', {}),
    )
    assert skip_reason == 'blend_header_total_weight_only', (
        f"hierarchy_type='summary' + Complex pattern must still skip — got {skip_reason!r}"
    )
