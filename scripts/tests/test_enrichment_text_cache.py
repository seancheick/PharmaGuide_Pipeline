#!/usr/bin/env python3
"""Tests for per-product text memoization behavior in enrichment."""

import os
import sys

import pytest

# Add parent directory to path for imports (normalized to avoid ".." in __file__)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from enrich_supplements_v3 import SupplementEnricherV3


class TestEnrichmentTextCache:
    @pytest.fixture
    def enricher(self):
        return SupplementEnricherV3()

    def test_get_all_product_text_without_cache_reflects_mutation(self, enricher):
        """Cache is disabled by default outside enrich_product calls."""
        product = {"fullName": "Original Name", "brandName": "Brand"}
        text_before = enricher._get_all_product_text(product)
        product["fullName"] = "Updated Name"
        text_after = enricher._get_all_product_text(product)

        assert "Original Name" in text_before
        assert "Updated Name" in text_after
        assert text_before != text_after

    def test_cached_text_and_lowered_text_consistent_when_enabled(self, enricher):
        """When cache is enabled, repeated calls should reuse cached text payloads."""
        product = {"fullName": "Alpha Product", "brandName": "BrandX"}

        enricher._product_text_cache_enabled = True
        try:
            text1 = enricher._get_all_product_text(product)
            text2 = enricher._get_all_product_text(product)
            lower1 = enricher._get_all_product_text_lower(product)
            lower2 = enricher._get_all_product_text_lower(product)
        finally:
            enricher._product_text_cache_enabled = False
            enricher._product_text_cache.clear()
            enricher._product_text_lower_cache.clear()

        assert text1 == text2
        assert lower1 == lower2
        assert lower1 == text1.lower()
