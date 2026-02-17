"""
Banned matching regression tests for allowlist/denylist logic.
"""

import logging
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from enrich_supplements_v3 import SupplementEnricherV3


@pytest.fixture
def enricher():
    return SupplementEnricherV3()


def _banned_ids(enricher, name):
    result = enricher._check_banned_substances([{"name": name, "standardName": name}])
    return {s.get("banned_id") for s in result.get("substances", [])}


@pytest.mark.parametrize("variant", ["IGF-1", "IGF 1", "IGF–1", "igf1"])
def test_igf1_variants_match(enricher, variant):
    banned_ids = _banned_ids(enricher, variant)
    assert "BANNED_IGF1" in banned_ids


@pytest.mark.parametrize("variant", ["IGF-1 LR3", "IGF-1LR3", "Long R3 IGF-1"])
def test_igf1_lr3_matches_separately(enricher, variant):
    banned_ids = _banned_ids(enricher, variant)
    assert "BANNED_IGF1_LR3" in banned_ids
    assert "BANNED_IGF1" not in banned_ids


def test_igf1_punctuation_match(enricher):
    banned_ids = _banned_ids(enricher, "Contains IGF-1, 10mg")
    assert "BANNED_IGF1" in banned_ids


@pytest.mark.parametrize("variant", ["PHO", "PHOs", "partially hydrogenated oil", "partially hydrogenated oils"])
def test_pho_variants_match(enricher, variant):
    banned_ids = _banned_ids(enricher, variant)
    assert "BANNED_PHO" in banned_ids


@pytest.mark.parametrize("variant", ["IGF binding protein", "IGFBP", "IGFBP3"])
def test_igf_binding_protein_denied(enricher, variant):
    banned_ids = _banned_ids(enricher, variant)
    assert "BANNED_IGF1" not in banned_ids


def test_igf_slash_variant_denied(enricher):
    banned_ids = _banned_ids(enricher, "contains IGF/1")
    assert "BANNED_IGF1" not in banned_ids


def test_pho_free_claim_denied(enricher):
    banned_ids = _banned_ids(enricher, "PHO-free")
    assert "BANNED_PHO" not in banned_ids


def test_allowlist_requires_canonical_id():
    enricher = SupplementEnricherV3.__new__(SupplementEnricherV3)
    enricher.logger = logging.getLogger("test_banned_matching")
    enricher.config = {"validation": {"strict_db_validation": True}}
    enricher.databases = {
        "banned_recalled_ingredients": {
            "permanently_banned": [{"id": "BANNED_TEST", "standard_name": "Test"}]
        },
        "banned_match_allowlist": {
            "allowlist": [{"id": "ALLOW_TEST"}],
            "denylist": []
        }
    }

    with pytest.raises(ValueError):
        enricher._validate_banned_match_allowlist()


# =============================================================================
# Product Recall False Positive Tests
# =============================================================================


class TestProductRecallFalsePositives:
    """
    Ensure competing brand products don't match recalled products.

    These tests verify that brand-qualified aliases and negative_match_terms
    correctly prevent false positive matches between similar product names
    from different brands.
    """

    def test_amazing_grass_not_matched_as_live_it_up(self, enricher):
        """Amazing Grass Super Greens should NOT match RECALLED_LIVE_IT_UP_SUPER_GREENS."""
        banned_ids = _banned_ids(enricher, "Amazing Grass Super Greens Original")
        assert "RECALLED_LIVE_IT_UP_SUPER_GREENS" not in banned_ids, \
            "Amazing Grass product should not match Live it Up recall due to negative_match_terms"

    def test_garden_of_life_greens_not_matched(self, enricher):
        """Garden of Life greens should NOT match Live it Up recall."""
        product_name = "Garden of Life Raw Organic Perfect Food Green Superfood"
        banned_ids = _banned_ids(enricher, product_name)
        assert "RECALLED_LIVE_IT_UP_SUPER_GREENS" not in banned_ids, \
            "Garden of Life product should not match Live it Up recall"

    def test_organifi_green_juice_not_matched(self, enricher):
        """Organifi Green Juice should NOT match Live it Up recall."""
        banned_ids = _banned_ids(enricher, "Organifi Green Juice Super Greens")
        assert "RECALLED_LIVE_IT_UP_SUPER_GREENS" not in banned_ids, \
            "Organifi product should not match Live it Up recall due to negative_match_terms"

    def test_actual_recalled_product_still_matches(self, enricher):
        """Actual recalled product should still match."""
        banned_ids = _banned_ids(enricher, "Live it Up Super Greens Original")
        assert "RECALLED_LIVE_IT_UP_SUPER_GREENS" in banned_ids, \
            "Actual Live it Up product should still match the recall entry"

    def test_live_it_up_wild_berry_matches(self, enricher):
        """Live it Up Wild Berry variant should match recall."""
        banned_ids = _banned_ids(enricher, "Live it Up Super Greens Wild Berry")
        assert "RECALLED_LIVE_IT_UP_SUPER_GREENS" in banned_ids, \
            "Live it Up Wild Berry product should match the recall entry"

    def test_flonase_not_matched_as_reboost(self, enricher):
        """Flonase nasal spray should NOT match ReBoost/ClearLife recall."""
        banned_ids = _banned_ids(enricher, "Flonase Allergy Relief Nasal Spray")
        assert "RECALLED_REBOOST_CLEARLIFE_NASAL_SPRAY" not in banned_ids, \
            "Flonase should not match ReBoost/ClearLife recall due to negative_match_terms"

    def test_flexeril_not_matched_as_unichem(self, enricher):
        """Flexeril brand should NOT match Unichem cyclobenzaprine recall."""
        banned_ids = _banned_ids(enricher, "Flexeril Cyclobenzaprine 10mg")
        assert "RECALLED_UNICHEM_CYCLOBENZAPRINE" not in banned_ids, \
            "Flexeril should not match Unichem recall due to negative_match_terms"

    def test_generic_super_greens_no_brand_no_match(self, enricher):
        """Generic 'super greens' without brand context should not match specific recalls."""
        # This should NOT match because our aliases are now brand-qualified
        banned_ids = _banned_ids(enricher, "super greens original powder")
        assert "RECALLED_LIVE_IT_UP_SUPER_GREENS" not in banned_ids, \
            "Generic 'super greens' without brand should not match brand-specific recall"
