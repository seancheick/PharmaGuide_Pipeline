#!/usr/bin/env python3
"""Tests for preferred-parent context lookup behavior."""

import os
import sys

import pytest

# Add parent directory to path for imports (normalized to avoid ".." in __file__)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from enrich_supplements_v3 import SupplementEnricherV3


class TestParentContextLookup:
    @pytest.fixture
    def enricher(self):
        return SupplementEnricherV3()

    def test_lookup_uses_first_seen_parent_for_collisions(self, enricher):
        """When aliases collide, first-seen parent should win (loop-order parity)."""
        quality_map = {
            "parent_a": {
                "standard_name": "Parent A",
                "aliases": ["shared alias"],
                "forms": {},
            },
            "parent_b": {
                "standard_name": "Parent B",
                "aliases": ["shared alias"],
                "forms": {},
            },
        }

        preferred = enricher._infer_preferred_parent_from_context_cached(
            "shared alias", quality_map
        )
        assert preferred == "parent_a"

    def test_custom_maps_do_not_use_stale_cache(self, enricher):
        """Custom maps should be recomputed each call so mutations are respected."""
        quality_map = {
            "parent_a": {
                "standard_name": "Parent A",
                "aliases": ["alias x"],
                "forms": {},
            },
            "parent_b": {
                "standard_name": "Parent B",
                "aliases": [],
                "forms": {},
            },
        }

        first = enricher._infer_preferred_parent_from_context_cached("alias x", quality_map)
        assert first == "parent_a"

        # Mutate map in-place; second lookup should reflect updated structure.
        quality_map["parent_a"]["aliases"] = []
        quality_map["parent_b"]["aliases"] = ["alias x"]

        second = enricher._infer_preferred_parent_from_context_cached("alias x", quality_map)
        assert second == "parent_b"
