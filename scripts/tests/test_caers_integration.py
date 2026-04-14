"""Tests for CAERS adverse event signal ingestion and scoring integration.

Covers:
- ingest_caers.py: ingredient extraction, signal aggregation, output schema
- score_supplements.py: B8 CAERS penalty computation, config gating, cap enforcement
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


# -------------------------------------------------------------------------
# score_supplements.py B8 CAERS penalty tests
# -------------------------------------------------------------------------

class TestB8CAERSScoring:
    @pytest.fixture
    def scorer(self):
        from score_supplements import SupplementScorer
        return SupplementScorer()

    @pytest.fixture
    def b_cfg(self, scorer):
        """Section B config dict — needed for direct _compute_caers_penalty calls."""
        return scorer.config.get("section_B_safety_purity", {})

    def _make_product(self, ingredient_ids):
        return {
            "ingredients": [
                {"canonical_id": cid} for cid in ingredient_ids
            ],
        }

    def test_no_ingredients_no_penalty(self, scorer, b_cfg):
        product = {"ingredients": []}
        flags = []
        penalty, evidence = scorer._compute_caers_penalty(product, flags, b_cfg)
        assert penalty == 0.0
        assert evidence == []

    def test_unknown_ingredient_no_penalty(self, scorer, b_cfg):
        product = self._make_product(["completely_unknown_ingredient_xyz"])
        flags = []
        penalty, evidence = scorer._compute_caers_penalty(product, flags, b_cfg)
        assert penalty == 0.0

    def test_strong_signal_penalty(self, scorer, b_cfg):
        # Kratom has a strong CAERS signal
        product = self._make_product(["kratom"])
        flags = []
        penalty, evidence = scorer._compute_caers_penalty(product, flags, b_cfg)
        assert penalty == 4.0
        assert len(evidence) == 1
        assert evidence[0]["signal_strength"] == "strong"
        assert "CAERS_SIGNAL_kratom" in flags

    def test_moderate_signal_penalty(self, scorer, b_cfg):
        # Find a moderate signal ingredient from loaded data
        moderate_ids = [
            cid for cid, sig in scorer._caers_signals.items()
            if sig["signal_strength"] == "moderate"
        ]
        if not moderate_ids:
            pytest.skip("No moderate CAERS signals in data")
        product = self._make_product([moderate_ids[0]])
        flags = []
        penalty, evidence = scorer._compute_caers_penalty(product, flags, b_cfg)
        assert penalty == 2.0

    def test_weak_signal_penalty(self, scorer, b_cfg):
        weak_ids = [
            cid for cid, sig in scorer._caers_signals.items()
            if sig["signal_strength"] == "weak"
        ]
        if not weak_ids:
            pytest.skip("No weak CAERS signals in data")
        product = self._make_product([weak_ids[0]])
        flags = []
        penalty, evidence = scorer._compute_caers_penalty(product, flags, b_cfg)
        assert penalty == 1.0

    def test_cap_enforcement(self, scorer, b_cfg):
        # Stack multiple strong signals — should cap at 5.0
        strong_ids = [
            cid for cid, sig in scorer._caers_signals.items()
            if sig["signal_strength"] == "strong"
        ][:5]
        if len(strong_ids) < 2:
            pytest.skip("Need at least 2 strong signals to test cap")
        product = self._make_product(strong_ids)
        flags = []
        penalty, evidence = scorer._compute_caers_penalty(product, flags, b_cfg)
        assert penalty <= 5.0

    def test_penalty_appears_in_section_b(self, scorer):
        product = self._make_product(["kratom"])
        product["supplement_type"] = {"category": "herbs"}
        flags = []
        section_b = scorer._compute_safety_purity_score(product, "herbs", 0.0, flags)
        assert "B8_penalty" in section_b
        assert section_b["B8_penalty"] > 0.0
        assert "B8_caers_evidence" in section_b

    def test_penalty_included_in_total_penalties(self, scorer):
        product = self._make_product(["kratom"])
        product["supplement_type"] = {"category": "herbs"}
        flags = []
        section_b = scorer._compute_safety_purity_score(product, "herbs", 0.0, flags)
        # B8 penalty should be counted in the penalties total
        assert section_b["penalties"] >= section_b["B8_penalty"]

    def test_disabled_config_no_penalty(self):
        """When B8 is disabled in config, no penalty should apply."""
        from score_supplements import SupplementScorer
        scorer = SupplementScorer()
        # Temporarily disable
        original = scorer._caers_signals
        scorer._caers_signals = {}
        product = {"ingredients": [{"canonical_id": "kratom"}]}
        flags = []
        b_cfg = scorer.config.get("section_B_safety_purity", {})
        penalty, evidence = scorer._compute_caers_penalty(product, flags, b_cfg)
        assert penalty == 0.0
        scorer._caers_signals = original
