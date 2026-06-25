"""Tests for CAERS adverse event signal ingestion (ingest_caers.py).

Covers ingredient extraction, signal aggregation, and output schema for the
analytics ingestion pipeline (the dashboard CAERS-audit page consumes it).

The B8 CAERS scoring penalty was retired 2026-06-24 — it had been disabled in
production since 2026-04-30 (raw report counts are confounded by exposure
base-rate; genuinely risky ingredients are covered by B0/B1). Only the
analytics pipeline remains.
"""

import json
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# -------------------------------------------------------------------------
# ingest_caers.py unit tests
# -------------------------------------------------------------------------

from api_audit.ingest_caers import (
    _normalize,
    build_ingredient_vocabulary,
    classify_signal_strength,
    extract_ingredients_from_name,
    SIGNAL_STRONG,
    SIGNAL_MODERATE,
    SIGNAL_WEAK,
)


class TestNormalize:
    def test_basic(self):
        assert _normalize("Green Tea Extract") == "green tea extract"

    def test_strips_non_alpha(self):
        assert _normalize("Vitamin B-12 (500mcg)") == "vitamin b 12 500mcg"

    def test_collapses_whitespace(self):
        assert _normalize("  fish   oil  ") == "fish oil"


class TestBuildIngredientVocabulary:
    @pytest.fixture
    def iqm_path(self):
        return os.path.join(
            os.path.dirname(__file__), "..", "data", "ingredient_quality_map.json"
        )

    def test_returns_dict(self, iqm_path):
        vocab = build_ingredient_vocabulary(iqm_path)
        assert isinstance(vocab, dict)
        assert len(vocab) > 100

    def test_canonical_ids_included(self, iqm_path):
        vocab = build_ingredient_vocabulary(iqm_path)
        assert "vitamin d" in vocab
        assert vocab["vitamin d"] == "vitamin_d"

    def test_cui_codes_excluded(self, iqm_path):
        vocab = build_ingredient_vocabulary(iqm_path)
        # CUI codes like C0012345 should not be keys
        for key in vocab:
            assert not key.startswith("c0") or len(key) < 6


class TestExtractIngredientsFromName:
    @pytest.fixture
    def iqm_vocab(self):
        iqm_path = os.path.join(
            os.path.dirname(__file__), "..", "data", "ingredient_quality_map.json"
        )
        return build_ingredient_vocabulary(iqm_path)

    def test_single_ingredient_product(self, iqm_vocab):
        result = extract_ingredients_from_name("NATURE'S BOUNTY MELATONIN 5MG", iqm_vocab)
        assert "melatonin" in result

    def test_fish_oil_product(self, iqm_vocab):
        result = extract_ingredients_from_name("NORDIC NATURALS ULTIMATE OMEGA FISH OIL", iqm_vocab)
        assert "fish_oil_omega3" in result

    def test_green_tea_extract(self, iqm_vocab):
        result = extract_ingredients_from_name("GREEN TEA EXTRACT 500MG CAPSULES", iqm_vocab)
        assert "green_tea_extract" in result

    def test_multivitamin_filtered_out(self, iqm_vocab):
        result = extract_ingredients_from_name(
            "CENTRUM SILVER WOMEN'S 50+ MULTIVITAMINS TABLET", iqm_vocab
        )
        assert len(result) == 0

    def test_prenatal_filtered_out(self, iqm_vocab):
        result = extract_ingredients_from_name("ONE A DAY PRENATAL VITAMINS", iqm_vocab)
        assert len(result) == 0

    def test_too_many_ingredients_filtered(self, iqm_vocab):
        # Product with 4+ distinct ingredients should be filtered
        result = extract_ingredients_from_name(
            "CALCIUM MAGNESIUM ZINC IRON SELENIUM COMPLEX", iqm_vocab
        )
        assert len(result) == 0

    def test_canonical_dedup_fish_oil(self, iqm_vocab):
        # "omega 3 fish oil" should deduplicate to one canonical ID
        result = extract_ingredients_from_name("OMEGA 3 FISH OIL 1000MG", iqm_vocab)
        assert result == {"fish_oil_omega3"}

    def test_kratom(self, iqm_vocab):
        result = extract_ingredients_from_name("KRATOM POWDER 500MG", iqm_vocab)
        assert "kratom" in result

    def test_empty_string(self, iqm_vocab):
        result = extract_ingredients_from_name("", iqm_vocab)
        assert len(result) == 0

    def test_no_match(self, iqm_vocab):
        result = extract_ingredients_from_name("SUPER BETA PROSTATE", iqm_vocab)
        assert len(result) == 0


class TestClassifySignalStrength:
    def test_strong(self):
        assert classify_signal_strength(SIGNAL_STRONG) == "strong"
        assert classify_signal_strength(500) == "strong"

    def test_moderate(self):
        assert classify_signal_strength(SIGNAL_MODERATE) == "moderate"
        assert classify_signal_strength(SIGNAL_STRONG - 1) == "moderate"

    def test_weak(self):
        assert classify_signal_strength(SIGNAL_WEAK) == "weak"
        assert classify_signal_strength(SIGNAL_MODERATE - 1) == "weak"

    def test_minimal(self):
        assert classify_signal_strength(0) == "minimal"
        assert classify_signal_strength(SIGNAL_WEAK - 1) == "minimal"


# -------------------------------------------------------------------------
# caers_adverse_event_signals.json schema tests
# -------------------------------------------------------------------------

class TestCAERSOutputSchema:
    @pytest.fixture
    def signals_data(self):
        path = os.path.join(
            os.path.dirname(__file__), "..", "data", "caers_adverse_event_signals.json"
        )
        with open(path) as f:
            return json.load(f)

    def test_has_metadata(self, signals_data):
        meta = signals_data["_metadata"]
        assert meta["schema_version"] == "1.0.0"
        assert "FDA CAERS" in meta["source"]
        assert meta["total_ingredients_with_signals"] > 0

    def test_has_signals(self, signals_data):
        assert len(signals_data["signals"]) > 0

    def test_signal_schema(self, signals_data):
        for canon_id, sig in signals_data["signals"].items():
            assert sig["canonical_id"] == canon_id
            assert isinstance(sig["total_reports"], int)
            assert isinstance(sig["serious_reports"], int)
            assert sig["serious_reports"] <= sig["total_reports"]
            assert sig["signal_strength"] in {"strong", "moderate", "weak"}
            assert isinstance(sig["outcomes"], dict)
            assert isinstance(sig["top_reactions"], list)
            assert len(sig["top_reactions"]) > 0

    def test_outcomes_keys(self, signals_data):
        expected_keys = {
            "hospitalization", "er_visit", "life_threatening",
            "death", "disability", "required_intervention",
        }
        for sig in signals_data["signals"].values():
            assert set(sig["outcomes"].keys()) == expected_keys

    def test_kratom_has_strong_signal(self, signals_data):
        kratom = signals_data["signals"].get("kratom")
        assert kratom is not None
        assert kratom["signal_strength"] == "strong"
        assert kratom["serious_reports"] >= 100

    def test_green_tea_extract_has_signal(self, signals_data):
        gte = signals_data["signals"].get("green_tea_extract")
        assert gte is not None
        assert gte["serious_reports"] >= 10

    def test_no_minimal_signals_included(self, signals_data):
        for sig in signals_data["signals"].values():
            assert sig["signal_strength"] != "minimal"
            assert sig["serious_reports"] >= SIGNAL_WEAK
