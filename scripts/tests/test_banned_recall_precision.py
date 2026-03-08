#!/usr/bin/env python3
"""Precision guards for product-level banned/recalled matching."""

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from enrich_supplements_v3 import SupplementEnricherV3


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3()


def _set_banned_db(enricher: SupplementEnricherV3, ingredients):
    enricher.databases["banned_recalled_ingredients"] = {"ingredients": ingredients}
    enricher.databases["banned_match_allowlist"] = {"allowlist": [], "denylist": []}


def _banned_ids(result):
    return {s.get("banned_id") for s in result.get("substances", [])}


def test_scoped_product_recall_does_not_match_brand_only(enricher):
    """Product-scoped recalls must not match by brand fallback alone."""
    _set_banned_db(
        enricher,
        [
            {
                "id": "RECALLED_PRODUCT_SCOPED",
                "entity_type": "product",
                "status": "recalled",
                "match_mode": "active",
                "standard_name": "Acme Bladder Relief",
                "aliases": ["acme bladder relief", "my bladder"],
                "recall_scope": {"brand": "Acme Bladder Relief"},
            }
        ],
    )

    product = {
        "fullName": "Acme Cranberry Support",
        "brandName": "My Bladder",
    }

    result = enricher._check_banned_substances([], product)
    assert "RECALLED_PRODUCT_SCOPED" not in _banned_ids(result)


def test_scoped_product_recall_matches_product_identity(enricher):
    """Product-scoped recall should still match exact product identity."""
    _set_banned_db(
        enricher,
        [
            {
                "id": "RECALLED_PRODUCT_SCOPED",
                "entity_type": "product",
                "status": "recalled",
                "match_mode": "active",
                "standard_name": "Acme Bladder Relief",
                "aliases": ["acme bladder relief", "my bladder"],
                "recall_scope": {"brand": "Acme Bladder Relief"},
            }
        ],
    )

    product = {
        "fullName": "Acme Bladder Relief",
        "brandName": "Acme Labs",
    }

    result = enricher._check_banned_substances([], product)
    assert "RECALLED_PRODUCT_SCOPED" in _banned_ids(result)


def test_product_entries_do_not_use_token_bounded_fallback(enricher):
    """Avoid product-name partial matches that can over-block."""
    _set_banned_db(
        enricher,
        [
            {
                "id": "RECALLED_PRODUCT_SCOPED",
                "entity_type": "product",
                "status": "recalled",
                "match_mode": "active",
                "standard_name": "Acme Bladder Relief",
                "aliases": ["acme bladder relief"],
                "recall_scope": {"brand": "Acme Bladder Relief"},
            }
        ],
    )

    product = {
        "fullName": "Acme Bladder Relief Extra Strength",
        "brandName": "Acme Labs",
    }

    result = enricher._check_banned_substances([], product)
    assert "RECALLED_PRODUCT_SCOPED" not in _banned_ids(result)


def test_unscoped_brand_level_product_ban_can_match_brand_fallback(enricher):
    """Brand-level bans (no recall_scope) retain brand fallback behavior."""
    _set_banned_db(
        enricher,
        [
            {
                "id": "BANNED_BRAND_LEVEL",
                "entity_type": "product",
                "status": "banned",
                "match_mode": "active",
                "standard_name": "Acme Labs Products",
                "aliases": ["acme labs"],
                "recall_scope": None,
            }
        ],
    )

    product = {
        "fullName": "Acme Daily Multivitamin",
        "brandName": "Acme Labs",
    }

    result = enricher._check_banned_substances([], product)
    assert "BANNED_BRAND_LEVEL" in _banned_ids(result)


def test_mormon_tea_alias_still_matches_ephedra(enricher):
    """Ephedra common-name aliases must not self-suppress via negative terms."""
    fresh_enricher = SupplementEnricherV3()
    result = fresh_enricher._check_banned_substances(
        [{"name": "Mormon Tea", "standardName": "Mormon Tea"}],
        {"fullName": "Test Product", "brandName": "Test Brand"},
    )

    assert "BANNED_EPHEDRA" in _banned_ids(result)


def test_safe_13_butylene_glycol_does_not_false_positive(enricher):
    """Safe 1,3-butylene glycol must not hit the 1,4-butanediol ban."""
    fresh_enricher = SupplementEnricherV3()
    result = fresh_enricher._check_banned_substances(
        [{"name": "1,3-Butylene Glycol", "standardName": "1,3-Butylene Glycol"}],
        {"fullName": "Test Product", "brandName": "Test Brand"},
    )

    assert "BANNED_14_BUTANEDIOL" not in _banned_ids(result)


def test_malformed_denylist_regex_does_not_crash_or_block_match(enricher):
    """Malformed denylist patterns should degrade safely instead of aborting enrichment."""
    _set_banned_db(
        enricher,
        [
            {
                "id": "BANNED_TEST_REGEX",
                "entity_type": "ingredient",
                "status": "banned",
                "match_mode": "active",
                "standard_name": "Test Substance",
                "aliases": ["test substance"],
            }
        ],
    )
    enricher.databases["banned_match_allowlist"] = {
        "allowlist": [],
        "denylist": [
            {
                "id": "DENY_BAD_REGEX",
                "canonical_id": "BANNED_TEST_REGEX",
                "match_policy": "regex",
                "pattern": "[",
            }
        ],
    }

    result = enricher._check_banned_substances(
        [{"name": "Test Substance", "standardName": "Test Substance"}],
        {"fullName": "Test Product", "brandName": "Test Brand"},
    )

    assert "BANNED_TEST_REGEX" in _banned_ids(result)


def test_dmsa_matches_single_canonical_banned_entry():
    """DMSA/succimer should dedupe to a single banned entity."""
    fresh_enricher = SupplementEnricherV3()
    result = fresh_enricher._check_banned_substances(
        [{"name": "DMSA", "standardName": "DMSA"}],
        {"fullName": "Chelation Product", "brandName": "Test Brand"},
    )

    banned_ids = _banned_ids(result)
    assert len(banned_ids) == 1
    assert "BANNED_DMSA_SUCCIMER" in banned_ids
