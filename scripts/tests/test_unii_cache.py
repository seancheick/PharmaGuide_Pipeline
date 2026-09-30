"""Tests for UNII local cache and IQM integration.

Covers:
- UniiCache loading and lookups
- IQM entry resolution (external_ids, aliases, forms)
- Build script output schema validation
"""

import json
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unii_cache import UniiCache


# -------------------------------------------------------------------------
# Cache loading and basic lookups
# -------------------------------------------------------------------------


class TestUniiCacheLoading:
    @pytest.fixture
    def cache(self):
        return UniiCache(enable_api_fallback=False)

    def test_cache_has_substances(self, cache):
        assert cache.size > 100_000  # 172K expected

    def test_stats_returns_dict(self, cache):
        stats = cache.stats()
        assert "loaded" in stats
        assert "cache_substances" in stats
        assert stats["loaded"] is True


class TestUniiLookup:
    @pytest.fixture
    def cache(self):
        return UniiCache(enable_api_fallback=False)

    def test_ascorbic_acid(self, cache):
        assert cache.lookup("ascorbic acid") == "PQ6CK8PD0R"

    def test_cholecalciferol(self, cache):
        assert cache.lookup("cholecalciferol") == "1C6V77QF41"

    def test_melatonin(self, cache):
        assert cache.lookup("melatonin") == "JL5DK93RCL"

    def test_caffeine(self, cache):
        assert cache.lookup("caffeine") == "3G6A5W338E"

    def test_case_insensitive(self, cache):
        assert cache.lookup("ASCORBIC ACID") == "PQ6CK8PD0R"
        assert cache.lookup("Melatonin") == "JL5DK93RCL"

    def test_unknown_returns_none(self, cache):
        assert cache.lookup("xyzzy_not_a_substance_12345") is None

    def test_empty_string(self, cache):
        assert cache.lookup("") is None

    def test_none_input(self, cache):
        assert cache.lookup(None) is None


class TestReverseLookup:
    @pytest.fixture
    def cache(self):
        return UniiCache(enable_api_fallback=False)

    def test_reverse_ascorbic_acid(self, cache):
        name = cache.reverse_lookup("PQ6CK8PD0R")
        assert name is not None
        assert "ASCORBIC" in name.upper()

    def test_reverse_unknown(self, cache):
        assert cache.reverse_lookup("ZZZZZZZZZZ") is None

    def test_reverse_empty(self, cache):
        assert cache.reverse_lookup("") is None


# -------------------------------------------------------------------------
# IQM entry resolution
# -------------------------------------------------------------------------


# -------------------------------------------------------------------------
# Cache file schema
# -------------------------------------------------------------------------


class TestCacheFileSchema:
    @pytest.fixture
    def cache_data(self):
        cache_path = os.path.join(
            os.path.dirname(__file__), "..", "data", "fda_unii_cache.json"
        )
        if not os.path.exists(cache_path):
            pytest.skip("UNII cache not built — run build_unii_cache.py first")
        with open(cache_path) as f:
            return json.load(f)

    def test_has_metadata(self, cache_data):
        meta = cache_data["_metadata"]
        assert meta["schema_version"] == "1.0.0"
        assert "FDA" in meta["source"]
        assert meta["total_substances"] > 100_000

    def test_has_name_to_unii(self, cache_data):
        n2u = cache_data["name_to_unii"]
        assert isinstance(n2u, dict)
        assert len(n2u) > 100_000

    def test_has_unii_to_name(self, cache_data):
        u2n = cache_data["unii_to_name"]
        assert isinstance(u2n, dict)
        assert len(u2n) > 100_000

    def test_known_substance_present(self, cache_data):
        n2u = cache_data["name_to_unii"]
        assert n2u.get("ascorbic acid") == "PQ6CK8PD0R"
        assert n2u.get("caffeine") == "3G6A5W338E"
