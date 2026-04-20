"""
Sprint D1.1 regression test — amaranth plant vs FD&C Red No. 2 dye.

Context: Prior to Sprint D1.1 the banned_recalled_ingredients.json entry
``BANNED_FDC_RED_2_AMARANTH`` carried the bare alias ``"amaranth"``,
which collided with the botanical_ingredients.json entry ``amaranth_grain``
(the edible Amaranthus pseudocereal). Reverse-index priority (banned > botanical)
caused the bare "amaranth" to route to the banned dye — 66 GNC / Nature_Made /
Vitafusion / GoL products labeled with amaranth grain protein or flour were
receiving BLOCKED verdicts instead of scoring as normal supplements.

Fix: removed the bare "amaranth" alias from the dye entry. Only dye-specific
aliases remain ("amaranth dye", "amaranth red dye", "amaranth colorant",
"E123", "C.I. 16185", "fd&c red no. 2"). The grain now correctly routes
to botanical_ingredients.amaranth_grain via the reverse index.

This test guards that the split stays in place. Regression would re-block
the 66 products immediately and be visible in the deep accuracy audit.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from enhanced_normalizer import EnhancedDSLDNormalizer


@pytest.fixture(scope="module")
def normalizer() -> EnhancedDSLDNormalizer:
    return EnhancedDSLDNormalizer()


class TestAmaranthPlantRoutesToBotanical:
    """The grain name variants must map to amaranth_grain, not the dye."""

    @pytest.mark.parametrize("raw", [
        "amaranth",
        "Amaranth",
        "AMARANTH",
        "organic amaranth",
        "Organic Amaranth",
        "Amaranthus",
        "amaranthus",
    ])
    def test_grain_variants_map_to_botanical(self, normalizer, raw) -> None:
        result = normalizer._resolve_canonical_identity(raw, raw_name=raw)
        assert result is not None, f"{raw!r} produced no canonical"
        assert result == ("amaranth_grain", "botanical_ingredients"), (
            f"{raw!r} mis-routed. Got {result!r}. "
            f"The banned_recalled alias collision must stay fixed."
        )


class TestAmaranthDyeStillBanned:
    """Dye-specific aliases must continue to hit the banned_recalled entry."""

    @pytest.mark.parametrize("raw", [
        "amaranth dye",
        "amaranth red dye",
        "amaranth colorant",
        "E123",
        "C.I. 16185",
        "fd&c red no. 2",
        "FD&C Red No. 2",
        "red 2",
        "red no. 2",
        "fdc red 2",
        "food red 9",
        "acid red 27",
    ])
    def test_dye_aliases_remain_banned(self, normalizer, raw) -> None:
        result = normalizer._resolve_canonical_identity(raw, raw_name=raw)
        assert result is not None, f"{raw!r} produced no canonical"
        canonical_id, source_db = result
        assert canonical_id == "BANNED_FDC_RED_2_AMARANTH", (
            f"{raw!r} should still be the banned dye. Got {result!r}."
        )
        assert source_db == "banned_recalled"


class TestBareAmaranthNotInBannedAliases:
    """Read the JSON directly — no bare 'amaranth' alias allowed in the dye entry."""

    def test_banned_dye_entry_does_not_contain_bare_amaranth(self) -> None:
        import json
        banned_path = (
            Path(__file__).parent.parent / "data" / "banned_recalled_ingredients.json"
        )
        banned = json.loads(banned_path.read_text())
        dye_entries = [
            e for e in banned.get("ingredients", [])
            if isinstance(e, dict) and e.get("id") == "BANNED_FDC_RED_2_AMARANTH"
        ]
        assert len(dye_entries) == 1, "BANNED_FDC_RED_2_AMARANTH must exist exactly once"
        aliases_lower = [a.lower() for a in dye_entries[0].get("aliases", [])]
        assert "amaranth" not in aliases_lower, (
            "Regression: bare 'amaranth' alias re-introduced on the banned dye entry. "
            "This collides with botanical_ingredients.amaranth_grain and causes 66 "
            "healthy amaranth grain products to receive BLOCKED verdicts. Use "
            "'amaranth dye' / 'amaranth red dye' / 'amaranth colorant' instead."
        )


class TestAmaranthGrainBotanicalEntryExists:
    """Catch accidental deletion of the grain entry."""

    def test_amaranth_grain_in_botanicals(self) -> None:
        import json
        bot_path = (
            Path(__file__).parent.parent / "data" / "botanical_ingredients.json"
        )
        bot = json.loads(bot_path.read_text())
        # The botanical file structure: top-level dict with category keys that are lists
        found = False
        for k, v in bot.items():
            if k.startswith("_") or not isinstance(v, list):
                continue
            for item in v:
                if isinstance(item, dict) and item.get("id") == "amaranth_grain":
                    found = True
                    aliases_lower = [a.lower() for a in item.get("aliases", [])]
                    assert "amaranth" in aliases_lower, (
                        "amaranth_grain must carry the bare 'amaranth' alias so "
                        "products labeled with the plain name resolve correctly."
                    )
                    break
            if found:
                break
        assert found, "amaranth_grain entry must exist in botanical_ingredients.json"
