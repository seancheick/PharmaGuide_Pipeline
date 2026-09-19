#!/usr/bin/env python3
"""The dietary-sugar scorer may not contradict the canonical sugar owner.

Maltodextrin is listed under `sweeteners.high_glycemic` because its glycemic
index really is ~85-105. True, and useful. But as a sub-2% capsule carrier it is
not dietary sugar, and the enricher that OWNS that question had already said so:
level "sugar_free", contains_sugar false, sugar_sources empty.

The penalty branch fired anyway. 1,146 products classified SUGAR-FREE took a
dietary-sugar penalty, and because B1_dietary_sugar mirrors into Safety
(penalty_registry FORMULA_QUALITY_MIRROR) while the low-severity additive clamp
does not cover it, 1,101 of them were also told "Safety concern: additive or
sweetener concerns" on no other basis. 779 had no independent safety fact at all.

One label occurrence had become three findings. Maltodextrin keeps the one it
earns: the additive owner scores ADD_MALTODEXTRIN as category filler,
severity_level low, 0.5 - and that penalty IS low-severity, so it clamps out of
Safety correctly.

These tests are written against the sugar DETERMINATION, never the ingredient
name, so a future carrier classified the same way is covered without a patch.
"""
from scoring_v4.modules.generic_formulation import _dietary_sugar_penalty_detail

SUGAR_FREE = {"amount_g": 0.0, "level": "sugar_free", "contains_sugar": False,
              "has_added_sugar": False, "sugar_sources": []}


def _product(sugar, sweeteners):
    return {"dietary_sensitivity_data": {"sugar": sugar, "sweeteners": sweeteners}}


# ── 1. a sugar-free carrier earns no sugar finding ───────────────────────────

def test_a_high_glycemic_carrier_is_not_dietary_sugar_when_the_owner_says_sugar_free():
    detail = _dietary_sugar_penalty_detail(
        _product(SUGAR_FREE, {"high_glycemic": ["maltodextrin"]}))

    assert detail["penalty"] == 0.0
    assert detail["reason"] is None
    assert detail["canonical_finds_no_sugar"] is True


def test_the_guard_is_not_keyed_on_the_ingredient_name():
    """Any carrier classified high-glycemic on a sugar-free product is covered,
    not just the one that exposed the bug."""
    for carrier in ("maltodextrin", "tapioca maltodextrin", "some future carrier"):
        detail = _dietary_sugar_penalty_detail(
            _product(SUGAR_FREE, {"high_glycemic": [carrier]}))
        assert detail["penalty"] == 0.0, carrier


# ── 2/3. real sugar is untouched ─────────────────────────────────────────────

def test_a_product_with_real_sugar_grams_still_pays():
    for level, expected_reason in (("high", "high_sugar_grams"),
                                   ("moderate", "moderate_sugar_grams")):
        detail = _dietary_sugar_penalty_detail(_product(
            {"level": level, "contains_sugar": True, "has_added_sugar": True,
             "sugar_sources": ["cane sugar"]},
            {"high_glycemic": []}))
        assert detail["penalty"] > 0, level
        assert detail["reason"] == expected_reason


def test_a_syrup_source_still_pays():
    detail = _dietary_sugar_penalty_detail(_product(
        {"level": "low", "contains_sugar": True, "has_added_sugar": True,
         "sugar_sources": ["brown rice syrup"]},
        {"high_glycemic": []}))

    assert detail["penalty"] > 0
    assert detail["reason"] == "high_glycemic_or_syrup"


def test_a_genuine_high_glycemic_sweetener_on_a_sugar_bearing_product_still_pays():
    """The guard only fires when the owner found NO sugar. A product that does
    contain sugar keeps the high-glycemic treatment."""
    detail = _dietary_sugar_penalty_detail(_product(
        {"level": "low", "contains_sugar": True, "has_added_sugar": True,
         "sugar_sources": ["dextrose"]},
        {"high_glycemic": ["dextrose"]}))

    assert detail["penalty"] > 0
    assert detail["reason"] == "high_glycemic_or_syrup"


# ── 4. sugar alcohols are not sugars, and keep their own separate treatment ──

def test_sugar_alcohols_still_pay_on_a_sugar_free_product():
    """FDA "sugar free" is <0.5 g SUGARS; polyols are not sugars. The 2026-07-04
    de-conflation gives them their own light penalty, and this guard must not
    swallow it - 495 products legitimately land here."""
    detail = _dietary_sugar_penalty_detail(
        _product(SUGAR_FREE, {"high_glycemic": [], "sugar_alcohols": ["erythritol"]}))

    assert detail["penalty"] > 0
    assert detail["reason"] == "sugar_alcohol_source"


def test_a_carrier_plus_a_real_polyol_lands_on_the_polyol_not_the_carrier():
    detail = _dietary_sugar_penalty_detail(_product(
        SUGAR_FREE, {"high_glycemic": ["maltodextrin"], "sugar_alcohols": ["xylitol"]}))

    assert detail["reason"] == "sugar_alcohol_source"
