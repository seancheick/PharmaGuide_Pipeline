"""
Sprint D1.2 regression tests — banned_recalled strict matching.

Context: prior to Sprint D1.2 the cleaner's ingredientGroup fallback
lookup ran a substring-based negative_match_terms check that broke on
parentheticals and trademark symbols. Label text like
"Essence of organic Orange (peel) oil" (a benign flavor essential oil)
matched the banned "Bitter Orange" canonical because the negative term
"orange peel" could not be found in "orange (peel)" via naive substring
match — the parens separated the two tokens.

Similarly, "organic Matcha Green Tea leaf powder" (a normal culinary
tea) matched the banned "Green Tea Extract (High Dose)" canonical
because "matcha" and "leaf powder" weren't in the negative_match_terms
list of that entry.

Fix: (a) code-side normalization of parens/trademark symbols before
the negative-match substring check, applied uniformly to every banned
entry that uses ingredientGroup fallback; (b) data-side expansion of
negative_match_terms on the Green Tea Extract (High Dose) and Bitter
Orange entries to cover common benign variants.

These tests guard BOTH directions — benign herbs must not be blocked,
AND legitimately banned ingredients must stay flagged.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from enhanced_normalizer import EnhancedDSLDNormalizer


@pytest.fixture(scope="module")
def normalizer() -> EnhancedDSLDNormalizer:
    return EnhancedDSLDNormalizer()


# ---------------------------------------------------------------------------
# Matcha / Green Tea leaf — must NOT hit banned Green Tea Extract (High Dose)
# ---------------------------------------------------------------------------


class TestMatchaGreenTeaNotBanned:
    """Culinary matcha / leaf tea products route away from the banned entry."""

    @pytest.mark.parametrize("raw,group", [
        ("organic Matcha Green Tea leaf powder", "Green Tea"),
        ("Matcha Green Tea", "Green Tea"),
        ("organic Matcha Green Tea", "Green Tea"),
        ("Matcha Green Tea leaf powder", "Green Tea"),
        ("matcha leaf powder", "Green Tea"),
        ("green tea leaf powder", "Green Tea"),
        ("culinary green tea", "Green Tea"),
    ])
    def test_matcha_variants_not_banned(self, normalizer, raw, group) -> None:
        std, mapped, _ = normalizer._enhanced_ingredient_mapping(
            raw, forms=[], ingredient_group=group,
        )
        # Either unmapped (falls to descriptor fallback) OR mapped to a
        # non-banned entry — never the banned Green Tea Extract (High Dose).
        assert "Green Tea Extract (High Dose)" not in (std or ""), (
            f"{raw!r} (group={group!r}) mis-routed to banned Green Tea "
            f"Extract (High Dose). negative_match_terms must veto this."
        )


# ---------------------------------------------------------------------------
# Orange peel oil — must NOT hit banned Bitter Orange
# ---------------------------------------------------------------------------


class TestOrangePeelOilNotBitterOrange:
    """Flavor-grade orange peel oil routes away from the banned synephrine entry."""

    @pytest.mark.parametrize("raw,group", [
        ("Essence of organic Orange (peel) oil", "Bitter orange"),
        ("Essence of Orange Peel Oil", "Bitter orange"),
        ("Orange Peel Oil", "Bitter orange"),
        ("Sweet Orange Essential Oil", "Bitter orange"),
        ("Orange Essential Oil", "Bitter orange"),
        ("Orange Essence", "Bitter orange"),
        ("Orange Flavor", "Bitter orange"),
    ])
    def test_orange_peel_variants_not_banned(self, normalizer, raw, group) -> None:
        std, mapped, _ = normalizer._enhanced_ingredient_mapping(
            raw, forms=[], ingredient_group=group,
        )
        assert "Bitter Orange" not in (std or ""), (
            f"{raw!r} (group={group!r}) mis-routed to banned Bitter Orange. "
            f"Flavor-grade orange peel oil does not contain supplement-dose "
            f"synephrine and must not be blocked."
        )


# ---------------------------------------------------------------------------
# Real banned ingredients must continue to trigger correctly
# ---------------------------------------------------------------------------


class TestLegitimatelyBannedStillFlagged:
    """Regression guard — real synephrine / EGCG extracts remain flagged."""

    def test_bitter_orange_extract_still_banned(self, normalizer) -> None:
        std, mapped, _ = normalizer._enhanced_ingredient_mapping(
            "Bitter Orange Extract", forms=[], ingredient_group="Bitter orange",
        )
        assert mapped
        assert "Bitter Orange" in (std or "")

    def test_synephrine_still_banned(self, normalizer) -> None:
        std, mapped, _ = normalizer._enhanced_ingredient_mapping(
            "Synephrine", forms=[], ingredient_group="Bitter orange",
        )
        assert mapped
        assert "Synephrine" in (std or "") or "Bitter Orange" in (std or "")

    def test_egcg_high_dose_still_banned(self, normalizer) -> None:
        std, mapped, _ = normalizer._enhanced_ingredient_mapping(
            "EGCG >800mg", forms=[], ingredient_group="Green Tea",
        )
        assert mapped
        assert "Green Tea Extract (High Dose)" in (std or "")

    def test_citrus_aurantium_extract_still_banned(self, normalizer) -> None:
        # Species-level name of bitter orange — the real risk.
        std, mapped, _ = normalizer._enhanced_ingredient_mapping(
            "Citrus aurantium", forms=[], ingredient_group="Bitter orange",
        )
        assert mapped


# ---------------------------------------------------------------------------
# Parens/trademark normalization helper behavior
# ---------------------------------------------------------------------------


class TestNegativeMatchParenNormalization:
    """
    The negative-match-term substring check must see past parens, brackets,
    and trademark symbols — a benign herb with a parenthetical qualifier
    must not slip past the veto.
    """

    def test_parens_in_name_do_not_defeat_veto(self, normalizer) -> None:
        # The naive substring check would see "orange (peel) oil" as not
        # containing "orange peel". Post-D1.2, normalization strips parens
        # before the check.
        std, mapped, _ = normalizer._enhanced_ingredient_mapping(
            "Essence of organic Orange (peel) oil",
            forms=[],
            ingredient_group="Bitter orange",
        )
        assert "Bitter Orange" not in (std or "")

    def test_trademark_symbols_do_not_defeat_veto(self, normalizer) -> None:
        # Trademark symbols normalized away so they don't break negative
        # match.
        std, mapped, _ = normalizer._enhanced_ingredient_mapping(
            "Matcha\u2122 Green Tea leaf powder",
            forms=[],
            ingredient_group="Green Tea",
        )
        assert "Green Tea Extract (High Dose)" not in (std or "")


# ---------------------------------------------------------------------------
# negative_match_terms coverage — data-file invariants
# ---------------------------------------------------------------------------


BANNED_PATH = Path(__file__).parent.parent / "data" / "banned_recalled_ingredients.json"


class TestNegativeMatchTermsPresence:
    """
    Guard the negative_match_terms expansion so nobody deletes the matcha /
    leaf / orange-peel veto list without a conscious review.
    """

    def test_green_tea_extract_high_has_matcha_veto(self) -> None:
        banned = json.loads(BANNED_PATH.read_text())
        entries = [
            e for e in banned.get("ingredients", [])
            if isinstance(e, dict) and e.get("id") == "RISK_GREEN_TEA_EXTRACT_HIGH"
        ]
        assert len(entries) == 1
        terms = [
            t.lower() for t in
            (entries[0].get("match_rules", {}) or {}).get("negative_match_terms", [])
        ]
        # Must cover matcha family + leaf-powder culinary forms.
        for required in ("matcha", "green tea leaf powder", "tea leaf"):
            assert required in terms, (
                f"Regression: '{required}' removed from Green Tea Extract (High Dose) "
                f"negative_match_terms. This will re-block ~13 matcha products."
            )

    def test_bitter_orange_has_parenthetical_peel_veto(self) -> None:
        banned = json.loads(BANNED_PATH.read_text())
        entries = [
            e for e in banned.get("ingredients", [])
            if isinstance(e, dict) and e.get("id") == "RISK_BITTER_ORANGE"
        ]
        assert len(entries) == 1
        terms = [
            t.lower() for t in
            (entries[0].get("match_rules", {}) or {}).get("negative_match_terms", [])
        ]
        # Must cover orange-peel variants with / without parens + other citrus.
        for required in ("orange peel oil", "orange essential oil", "sweet orange"):
            assert required in terms, (
                f"Regression: '{required}' removed from Bitter Orange "
                f"negative_match_terms. This will re-block orange peel oil products."
            )
