#!/usr/bin/env python3
"""Config-alignment tests for enrichment fuzzy thresholds."""

import os
import sys

import pytest

# Add parent directory to path for imports (normalized to avoid ".." in __file__)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import enrich_supplements_v3 as enrich_module
from enrich_supplements_v3 import SupplementEnricherV3


class _DummyFuzz:
    @staticmethod
    def WRatio(_a, _b):
        return 88

    @staticmethod
    def partial_ratio(_a, _b):
        return 88


class TestFuzzyThresholdConfig:
    @pytest.fixture
    def enricher(self):
        return SupplementEnricherV3()

    def test_company_fuzzy_threshold_resolved_from_config(self, enricher):
        """processing_config.fuzzy_threshold=85 should normalize to 0.85."""
        assert enricher.company_fuzzy_threshold == pytest.approx(0.85, rel=1e-6)

    def test_fuzzy_company_match_uses_configured_threshold(self, enricher, monkeypatch):
        """Matching should use resolved config threshold when none is passed explicitly."""
        monkeypatch.setattr(enrich_module, "RAPIDFUZZ_AVAILABLE", True)
        monkeypatch.setattr(enrich_module, "rf_fuzz", _DummyFuzz)
        monkeypatch.setattr(enricher, "_normalize_company_name", lambda x: str(x).lower())

        enricher.company_fuzzy_threshold = 0.85
        matched_low, score_low = enricher._fuzzy_company_match("Acme Labs", "Acme Labz")
        assert matched_low is True
        assert score_low == pytest.approx(0.88, rel=1e-6)

        enricher.company_fuzzy_threshold = 0.90
        matched_high, score_high = enricher._fuzzy_company_match("Acme Labs", "Acme Labz")
        assert matched_high is False
        assert score_high == pytest.approx(0.88, rel=1e-6)

    def test_fuzzy_company_match_respects_enable_fuzzy_flag(self, enricher, monkeypatch):
        """When enable_fuzzy_matching is false, fuzzy matching should not run."""
        monkeypatch.setattr(enrich_module, "RAPIDFUZZ_AVAILABLE", True)
        monkeypatch.setattr(enrich_module, "rf_fuzz", _DummyFuzz)
        monkeypatch.setattr(enricher, "_normalize_company_name", lambda x: str(x).lower())

        enricher.config.setdefault("processing_config", {})["enable_fuzzy_matching"] = False
        matched, score = enricher._fuzzy_company_match("Acme Labs", "Acme Labz")
        assert matched is False
        assert score == pytest.approx(0.0, rel=1e-6)
