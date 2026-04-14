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

    def test_cache_loads(self, cache):
        assert cache.is_loaded is True

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


class TestBulkLookup:
    @pytest.fixture
    def cache(self):
        return UniiCache(enable_api_fallback=False)

    def test_bulk_returns_dict(self, cache):
        result = cache.bulk_lookup(["ascorbic acid", "caffeine", "nonexistent_xyz"])
        assert isinstance(result, dict)
        assert result["ascorbic acid"] == "PQ6CK8PD0R"
        assert result["caffeine"] == "3G6A5W338E"
        assert result["nonexistent_xyz"] is None


# -------------------------------------------------------------------------
# IQM entry resolution
# -------------------------------------------------------------------------


class TestIQMEntryLookup:
    @pytest.fixture
    def cache(self):
        return UniiCache(enable_api_fallback=False)

    @pytest.fixture
    def iqm(self):
        iqm_path = os.path.join(
            os.path.dirname(__file__), "..", "data", "ingredient_quality_map.json"
        )
        with open(iqm_path) as f:
            return json.load(f)

    def test_entry_with_external_ids_unii(self, cache, iqm):
        """Entries with external_ids.unii should return that directly."""
        entry = iqm.get("vitamin_a", {})
        unii = cache.lookup_for_iqm_entry("vitamin_a", entry)
        assert unii is not None
        assert unii == entry.get("external_ids", {}).get("unii")

    def test_entry_resolved_via_forms(self, cache, iqm):
        """Entries without direct UNII should resolve via form chemical names."""
        # Find an entry that has forms but no external_ids.unii
        for key, entry in iqm.items():
            if key == "_metadata":
                continue
            ext = entry.get("external_ids", {})
            has_ext_unii = isinstance(ext, dict) and ext.get("unii")
            has_top_unii = bool(entry.get("unii"))
            forms = entry.get("forms", {})
            if not has_ext_unii and not has_top_unii and isinstance(forms, dict) and len(forms) > 0:
                unii = cache.lookup_for_iqm_entry(key, entry)
                if unii:
                    # Found one resolved via forms
                    assert isinstance(unii, str)
                    assert len(unii) == 10  # UNII codes are 10 chars
                    return
        pytest.skip("No form-only resolvable entries found")

    def test_probiotics_returns_none(self, cache, iqm):
        """Probiotics is a category, not a chemical — should not resolve."""
        entry = iqm.get("probiotics", {})
        if not entry:
            pytest.skip("probiotics not in IQM")
        unii = cache.lookup_for_iqm_entry("probiotics", entry)
        assert unii is None

    def test_overall_match_rate_above_60_pct(self, cache, iqm):
        """At least 60% of IQM entries should resolve to a UNII."""
        total = 0
        matched = 0
        for key, entry in iqm.items():
            if key == "_metadata":
                continue
            total += 1
            if cache.lookup_for_iqm_entry(key, entry):
                matched += 1
        rate = matched / total if total else 0
        assert rate >= 0.60, f"UNII match rate {rate:.1%} is below 60% threshold"


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
