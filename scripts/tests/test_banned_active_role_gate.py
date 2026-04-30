#!/usr/bin/env python3
"""
Active/inactive role gating for banned-substance matching.

When a banned_recalled entry has `match_mode: 'active'`, the matcher must
skip ingredients tagged with `_source_section='inactive'`. This prevents
false positives for substances that are dangerous as active ingredients
but acceptable as excipients (talc as glidant, titanium dioxide as
coating, docusate as softgel emulsifier).

When `match_mode: 'any'` (or absent for backward compat), the matcher
scans all ingredients regardless of section — used for true contaminants
(lead, mercury, arsenic) which are dangerous regardless of declaration.
"""

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


def _ids(result):
    return {s.get("banned_id") for s in result.get("substances", [])}


# ---------------------------------------------------------------------------
# match_mode='active': inactive-section ingredients must be ignored
# ---------------------------------------------------------------------------


def test_active_mode_skips_inactive_ingredient(enricher):
    """Talc as inactive glidant must NOT trip a match_mode='active' entry."""
    _set_banned_db(
        enricher,
        [
            {
                "id": "BANNED_ADD_TALC",
                "entity_type": "ingredient",
                "status": "high_risk",
                "match_mode": "active",
                "standard_name": "Talc",
                "aliases": ["talc", "talcum", "talcum powder"],
            }
        ],
    )

    product = {
        "fullName": "Mega Men Multivitamin",
        "brandName": "GNC",
        "activeIngredients": [{"name": "Vitamin C"}],
        "inactiveIngredients": [{"name": "Talc"}],
    }

    actives_tagged = [{**i, "_source_section": "active"} for i in product["activeIngredients"]]
    inactives_tagged = [{**i, "_source_section": "inactive"} for i in product["inactiveIngredients"]]
    all_ings = actives_tagged + inactives_tagged

    result = enricher._check_banned_substances(all_ings, product)
    assert "BANNED_ADD_TALC" not in _ids(result), (
        "Talc as inactive glidant should NOT fire a match_mode='active' entry"
    )


def test_active_mode_fires_on_active_ingredient(enricher):
    """Talc declared as active ingredient must still trip the entry."""
    _set_banned_db(
        enricher,
        [
            {
                "id": "BANNED_ADD_TALC",
                "entity_type": "ingredient",
                "status": "high_risk",
                "match_mode": "active",
                "standard_name": "Talc",
                "aliases": ["talc", "talcum", "talcum powder"],
            }
        ],
    )

    product = {
        "fullName": "Some Cosmetic Powder",
        "brandName": "X",
        "activeIngredients": [{"name": "Talc"}],
        "inactiveIngredients": [],
    }

    actives_tagged = [{**i, "_source_section": "active"} for i in product["activeIngredients"]]
    all_ings = actives_tagged

    result = enricher._check_banned_substances(all_ings, product)
    assert "BANNED_ADD_TALC" in _ids(result), (
        "Talc as active ingredient should still fire match_mode='active'"
    )


def test_active_mode_titanium_dioxide_inactive_coating(enricher):
    """Titanium Dioxide as inactive tablet coating must not fire (E171)."""
    _set_banned_db(
        enricher,
        [
            {
                "id": "BANNED_ADD_TITANIUM_DIOXIDE",
                "entity_type": "ingredient",
                "status": "high_risk",
                "match_mode": "active",
                "standard_name": "Titanium Dioxide (E171)",
                "aliases": ["titanium dioxide", "e171", "ci 77891"],
            }
        ],
    )

    product = {
        "fullName": "Some Tablet Multivitamin",
        "brandName": "X",
        "activeIngredients": [{"name": "Vitamin D"}],
        "inactiveIngredients": [{"name": "Titanium Dioxide"}],
    }

    all_ings = (
        [{**i, "_source_section": "active"} for i in product["activeIngredients"]]
        + [{**i, "_source_section": "inactive"} for i in product["inactiveIngredients"]]
    )

    result = enricher._check_banned_substances(all_ings, product)
    assert "BANNED_ADD_TITANIUM_DIOXIDE" not in _ids(result), (
        "TiO2 as inactive tablet coating should not fire match_mode='active'"
    )


# ---------------------------------------------------------------------------
# match_mode='any': true contaminants must fire regardless of section
# ---------------------------------------------------------------------------


def test_any_mode_fires_on_inactive_for_true_contaminants(enricher):
    """match_mode='any' (e.g. heavy metals) must scan inactives too."""
    _set_banned_db(
        enricher,
        [
            {
                "id": "HM_LEAD",
                "entity_type": "contaminant",
                "status": "high_risk",
                "match_mode": "any",
                "standard_name": "Lead",
                "aliases": ["lead", "lead compounds", "plumbum"],
            }
        ],
    )

    product = {
        "fullName": "Test product",
        "brandName": "X",
        "activeIngredients": [{"name": "Vitamin C"}],
        "inactiveIngredients": [{"name": "Lead"}],
    }

    all_ings = (
        [{**i, "_source_section": "active"} for i in product["activeIngredients"]]
        + [{**i, "_source_section": "inactive"} for i in product["inactiveIngredients"]]
    )

    result = enricher._check_banned_substances(all_ings, product)
    assert "HM_LEAD" in _ids(result), "Lead in any section must fire match_mode='any'"


# ---------------------------------------------------------------------------
# Backward compat: entries without match_mode and untagged ingredients
# ---------------------------------------------------------------------------


def test_missing_source_section_treated_as_active(enricher):
    """Untagged ingredient (legacy callers) should default to 'active' role.

    This preserves backward compatibility for any caller that doesn't tag
    ingredients with _source_section. The matcher should still fire on
    those ingredients for active-mode entries.
    """
    _set_banned_db(
        enricher,
        [
            {
                "id": "BANNED_ADD_TALC",
                "entity_type": "ingredient",
                "status": "high_risk",
                "match_mode": "active",
                "standard_name": "Talc",
                "aliases": ["talc"],
            }
        ],
    )

    product = {
        "fullName": "Test",
        "brandName": "X",
        "activeIngredients": [{"name": "Talc"}],
        "inactiveIngredients": [],
    }

    # NOTE: deliberately NOT tagging with _source_section to test legacy path
    all_ings = product["activeIngredients"]

    result = enricher._check_banned_substances(all_ings, product)
    assert "BANNED_ADD_TALC" in _ids(result), (
        "Untagged ingredients should default to 'active' role for backward compat"
    )


def test_no_match_mode_field_defaults_to_active(enricher):
    """Entry without match_mode defaults to 'active' (safer specificity).

    All current entries in banned_recalled_ingredients.json carry an explicit
    match_mode='active' — that is the documented norm. If a future entry
    omits the field, the safer default is 'active' (no inactive matching),
    forcing the author to explicitly opt into 'any' mode for contaminants.

    A missing match_mode firing on inactives would silently undo our
    false-positive fixes the moment someone added a new entry without
    knowing about the field.
    """
    _set_banned_db(
        enricher,
        [
            {
                "id": "LEGACY_ENTRY",
                "entity_type": "ingredient",
                "status": "banned",
                # NO match_mode field
                "standard_name": "Some Banned Drug",
                "aliases": ["some banned drug"],
            }
        ],
    )

    product = {
        "fullName": "Test",
        "brandName": "X",
        "activeIngredients": [{"name": "Vitamin C"}],
        "inactiveIngredients": [{"name": "Some Banned Drug"}],
    }

    all_ings = (
        [{**i, "_source_section": "active"} for i in product["activeIngredients"]]
        + [{**i, "_source_section": "inactive"} for i in product["inactiveIngredients"]]
    )

    result = enricher._check_banned_substances(all_ings, product)
    assert "LEGACY_ENTRY" not in _ids(result), (
        "Entry without match_mode should default to 'active' — must NOT fire on inactives"
    )

    # And the same entry MUST fire when the substance is in actives
    product_active = {
        "fullName": "Test",
        "brandName": "X",
        "activeIngredients": [{"name": "Some Banned Drug"}],
        "inactiveIngredients": [],
    }
    all_ings_active = [{**i, "_source_section": "active"} for i in product_active["activeIngredients"]]
    result_active = enricher._check_banned_substances(all_ings_active, product_active)
    assert "LEGACY_ENTRY" in _ids(result_active), (
        "Default 'active' mode must still fire when substance is declared as active"
    )
