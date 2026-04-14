"""
Harmful Additives ↔ IQM Dual Scoring Tests

Verifies the architectural invariant: harmful_additives membership must NEVER
block IQM quality scoring.  These are separate concerns:
  - Section A (IQM): quality bonuses for bioavailability, premium forms, etc.
  - Section B1 (harmful_additives): safety penalties for known harmful additives

An ingredient that appears in BOTH databases must receive:
  1. Its full IQM quality score in Section A
  2. Its harmful_additives penalty in Section B1

BUG CONTEXT (2026-04-14):
  _recognition_blocks_scoring() in _should_skip_from_scoring() fires BEFORE
  _is_known_therapeutic(), causing 8+ dual-classified ingredients to be
  classified as non_scorable and get zero IQM credit.  Same ordering bug
  exists in _should_promote_to_scorable() for inactive ingredients.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from enrich_supplements_v3 import SupplementEnricherV3

_DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data'))


def _load_json(filename):
    with open(os.path.join(_DATA_DIR, filename)) as f:
        return json.load(f)


# All IQM parents that also appear in harmful_additives or banned_recalled
# with high_risk/watchlist status (the allowlisted overlaps).
DUAL_CLASSIFIED_IQM_KEYS = [
    "garcinia_cambogia",
    "kavalactones",
    "synephrine",
    "yohimbe",
    "cascara_sagrada",
    "7_keto_dhea",
]


class TestHarmfulAdditiveNeverBlocksIQM:
    """Harmful additive recognition must not prevent IQM quality scoring."""

    @pytest.fixture(scope="class")
    def enricher(self):
        return SupplementEnricherV3()

    @pytest.fixture(scope="class")
    def iqm(self):
        return _load_json("ingredient_quality_map.json")

    @pytest.fixture(scope="class")
    def harmful_db(self):
        return _load_json("harmful_additives.json")

    # ------------------------------------------------------------------
    # Core invariant: _should_skip_from_scoring must return None (scorable)
    # for any ingredient that exists in IQM, regardless of harmful_additives
    # ------------------------------------------------------------------

    @pytest.mark.parametrize("iqm_key", DUAL_CLASSIFIED_IQM_KEYS)
    def test_dual_classified_ingredient_is_not_skipped(self, enricher, iqm, iqm_key):
        """IQM ingredient that also appears in harmful/banned must NOT be skipped."""
        entry = iqm.get(iqm_key)
        assert entry is not None, f"IQM key {iqm_key} not found in ingredient_quality_map"

        # Use the IQM parent key as the ingredient name (matches how enricher resolves)
        standard_name = entry.get("standard_name", iqm_key)
        # Build a minimal ingredient dict
        ingredient = {
            "ingredientName": standard_name,
            "standardName": standard_name,
            "quantity": "500",
            "unit": "mg",
        }

        quality_map = iqm
        botanicals_db = _load_json("standardized_botanicals.json")

        skip = enricher._should_skip_from_scoring(
            ingredient, quality_map, botanicals_db
        )
        assert skip is None, (
            f"IQM ingredient '{standard_name}' (key={iqm_key}) was incorrectly skipped "
            f"with reason: {skip}. Harmful additive status must not block IQM scoring."
        )

    # ------------------------------------------------------------------
    # Verify harmful_additives entries found in IQM are still recognized
    # as non-scorable by the recognition system (the recognition itself
    # is fine — it's the BLOCKING that's wrong)
    # ------------------------------------------------------------------

    @pytest.mark.parametrize("iqm_key", DUAL_CLASSIFIED_IQM_KEYS)
    def test_dual_classified_is_still_recognized(self, enricher, iqm, iqm_key):
        """Recognition should still fire — it just shouldn't block scoring."""
        entry = iqm.get(iqm_key)
        standard_name = entry.get("standard_name", iqm_key)

        recognized = enricher._is_recognized_non_scorable(standard_name, standard_name)
        # Some dual-classified ingredients are recognized, some aren't.
        # The point is: even if recognized, scoring must not be blocked.
        # This test documents the recognition result for each.
        if recognized:
            source = recognized.get("recognition_source")
            assert source in {
                "harmful_additives",
                "banned_recalled_ingredients",
                "other_ingredients",
                "botanical_ingredients",
                "standardized_botanicals",
            }, f"Unexpected recognition source: {source}"


class TestHarmfulAdditiveInactivePromotion:
    """Dual-classified ingredients in inactiveIngredients must be promotable."""

    @pytest.fixture(scope="class")
    def enricher(self):
        return SupplementEnricherV3()

    @pytest.fixture(scope="class")
    def iqm(self):
        return _load_json("ingredient_quality_map.json")

    @pytest.mark.parametrize("iqm_key", DUAL_CLASSIFIED_IQM_KEYS)
    def test_dual_classified_inactive_can_be_promoted(self, enricher, iqm, iqm_key):
        """IQM ingredient in inactiveIngredients must not be blocked from promotion."""
        entry = iqm.get(iqm_key)
        assert entry is not None
        # Use the IQM key (label-facing name) rather than standard_name which
        # may contain parenthetical compound names that trigger unrelated
        # excipient substring filters (e.g. "Hydroxycitric Acid" ⊃ "citric acid").
        label_name = iqm_key.replace("_", " ").title()

        # _should_promote_to_scorable uses internal field names (name, not ingredientName)
        ingredient = {
            "name": label_name,
            "ingredientName": label_name,
            "standardName": label_name,
            "quantity": "500",
            "unit": "mg",
        }

        quality_map = iqm
        botanicals_db = _load_json("standardized_botanicals.json")

        result = enricher._should_promote_to_scorable(
            ingredient, quality_map, botanicals_db, current_scorable_count=0
        )
        assert result is not None, (
            f"IQM ingredient '{label_name}' (key={iqm_key}) was incorrectly blocked "
            f"from promotion. Harmful additive status must not prevent IQM scoring."
        )


class TestRecognitionBlocksScoringPolicy:
    """_recognition_blocks_scoring must never block IQM-known ingredients."""

    @pytest.fixture(scope="class")
    def enricher(self):
        return SupplementEnricherV3()

    def test_harmful_recognition_does_not_block(self, enricher):
        """harmful_additives recognition alone must not block scoring."""
        recognition = {
            "recognition_source": "harmful_additives",
            "recognition_reason": "known_additive",
        }
        # The function itself may still return True (it identifies penalty sources),
        # but in the calling context it must be checked AFTER _is_known_therapeutic.
        # This test documents the expected return for audit purposes.
        result = enricher._recognition_blocks_scoring(recognition)
        # After the fix, this should return False — harmful_additives should
        # never block scoring; they're a separate penalty concern.
        assert result is False, (
            "_recognition_blocks_scoring should return False for harmful_additives. "
            "Harmful additives are a Section B1 penalty, not a scoring blocker."
        )

    def test_banned_recalled_still_blocks(self, enricher):
        """banned/recalled ingredients SHOULD block scoring (they fail B0 gate)."""
        recognition = {
            "recognition_source": "banned_recalled_ingredients",
            "recognition_reason": "banned",
        }
        result = enricher._recognition_blocks_scoring(recognition)
        # banned_recalled should still block — but ONLY for status=banned/recalled.
        # high_risk/watchlist entries that are also in IQM should be handled
        # by the _is_known_therapeutic override in the calling function.
        assert result is True, (
            "banned_recalled_ingredients should still block scoring at this level. "
            "The calling function handles the IQM override for high_risk/watchlist."
        )

    def test_other_ingredients_does_not_block(self, enricher):
        recognition = {"recognition_source": "other_ingredients"}
        assert enricher._recognition_blocks_scoring(recognition) is False

    def test_botanical_does_not_block(self, enricher):
        recognition = {"recognition_source": "botanical_ingredients"}
        assert enricher._recognition_blocks_scoring(recognition) is False

    def test_none_does_not_block(self, enricher):
        assert enricher._recognition_blocks_scoring(None) is False


class TestScoringPipelineEndToEnd:
    """
    End-to-end: a product with a dual-classified active ingredient must
    get BOTH its Section A quality score AND its Section B1 penalty.
    """

    @pytest.fixture(scope="class")
    def enricher(self):
        return SupplementEnricherV3()

    def _make_product_with_ingredient(self, ing_name, quantity="500", unit="mg"):
        """Build a minimal DSLD-shaped product with one active ingredient."""
        return {
            "dsld_id": 99999,
            "product_name": f"Test Product ({ing_name})",
            "fullName": f"Test Product ({ing_name})",
            "productName": f"Test Product ({ing_name})",
            "brandName": "TestBrand",
            "activeIngredients": [
                {
                    "ingredientName": ing_name,
                    "standardName": ing_name,
                    "quantity": quantity,
                    "unit": unit,
                }
            ],
            "inactiveIngredients": [],
        }

    @pytest.mark.parametrize("ing_name,iqm_key", [
        ("Garcinia Cambogia", "garcinia_cambogia"),
        ("Yohimbe", "yohimbe"),
    ])
    def test_dual_ingredient_gets_iqm_score(self, enricher, ing_name, iqm_key):
        """Dual-classified ingredient must appear in scorable list, not skipped."""
        product = self._make_product_with_ingredient(ing_name)
        enriched, _warnings = enricher.enrich_product(product)

        iq_data = enriched.get("ingredient_quality_data", {})
        scorable = iq_data.get("ingredients_scorable", [])
        skipped = iq_data.get("ingredients_skipped", [])

        # Enricher may populate name or standard_name — check both
        def _all_names(entry):
            return {
                (entry.get("name") or "").lower(),
                (entry.get("standard_name") or "").lower(),
            }

        scorable_all = set()
        for s in scorable:
            scorable_all |= _all_names(s)
        skipped_all = set()
        for s in skipped:
            skipped_all |= _all_names(s)

        # IQM standard_name may include parenthetical compound names
        # e.g. "Garcinia Cambogia (Hydroxycitric Acid)" for input "Garcinia Cambogia"
        target = ing_name.lower()
        found_in_scorable = any(target in n for n in scorable_all if n)
        found_in_skipped = any(target in n for n in skipped_all if n)

        assert found_in_scorable, (
            f"'{ing_name}' should be in ingredients_scorable but was not. "
            f"Scorable names: {scorable_all}, Skipped names: {skipped_all}"
        )
        assert not found_in_skipped, (
            f"'{ing_name}' should NOT be in ingredients_skipped but was found there "
            f"with classification that blocks IQM scoring."
        )


class TestExcipientSubstringFalsePositive:
    """Excipient partial matching must use word boundaries.

    "citric acid" is a legitimate excipient in EXCIPIENT_NEVER_PROMOTE,
    but "hydroxycitric acid" (the active compound in Garcinia Cambogia)
    is NOT an excipient.  Substring matching must not fire across word
    boundaries.
    """

    @pytest.fixture(scope="class")
    def enricher(self):
        return SupplementEnricherV3()

    @pytest.fixture(scope="class")
    def iqm(self):
        return _load_json("ingredient_quality_map.json")

    def test_citric_acid_is_excipient(self, enricher):
        """Actual citric acid should be recognized as excipient."""
        is_exc, reason = enricher._compute_excipient_flags(
            {"name": "citric acid", "standardName": "citric acid"}
        )
        assert is_exc is True

    def test_hydroxycitric_acid_is_not_excipient(self, enricher):
        """Hydroxycitric acid must NOT be flagged as excipient."""
        is_exc, reason = enricher._compute_excipient_flags(
            {"name": "hydroxycitric acid", "standardName": "hydroxycitric acid"}
        )
        assert is_exc is False, (
            f"'hydroxycitric acid' falsely matched excipient via substring. "
            f"reason={reason}"
        )

    def test_garcinia_cambogia_hca_not_excipient(self, enricher):
        """Garcinia Cambogia (Hydroxycitric Acid) must NOT be excipient."""
        is_exc, reason = enricher._compute_excipient_flags(
            {"name": "garcinia cambogia (hydroxycitric acid)",
             "standardName": "garcinia cambogia (hydroxycitric acid)"}
        )
        assert is_exc is False, (
            f"Garcinia Cambogia falsely matched excipient. reason={reason}"
        )

    def test_organic_sunflower_oil_is_excipient(self, enricher):
        """Legitimate partial match: 'organic sunflower oil' contains 'sunflower oil'."""
        is_exc, reason = enricher._compute_excipient_flags(
            {"name": "organic sunflower oil", "standardName": "organic sunflower oil"}
        )
        assert is_exc is True

    def test_ascorbic_acid_not_matched_by_stearic_acid(self, enricher):
        """'ascorbic acid' must not be matched by 'stearic acid' substring."""
        is_exc, reason = enricher._compute_excipient_flags(
            {"name": "ascorbic acid", "standardName": "ascorbic acid"}
        )
        # ascorbic acid is NOT in EXCIPIENT_NEVER_PROMOTE (it's vitamin C)
        assert is_exc is False, (
            f"'ascorbic acid' falsely matched excipient. reason={reason}"
        )

    def test_hydroxycitric_acid_not_blocked_from_promotion(self, enricher, iqm):
        """Hydroxycitric acid must be promotable from inactive ingredients."""
        botanicals_db = _load_json("standardized_botanicals.json")
        ingredient = {
            "name": "Garcinia Cambogia",
            "ingredientName": "Garcinia Cambogia",
            "standardName": "Garcinia Cambogia",
            "quantity": "500",
            "unit": "mg",
        }
        result = enricher._should_promote_to_scorable(
            ingredient, iqm, botanicals_db, current_scorable_count=0
        )
        assert result is not None, (
            "Garcinia Cambogia should be promotable (IQM-known therapeutic)"
        )
