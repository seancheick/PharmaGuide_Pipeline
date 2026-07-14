"""C7.2 regression — nutrition-panel sodium/sugar unit reconciliation.

`_analyze_sodium_content` / `_analyze_sugar_content` previously detected the
mass unit by *substring* (`'g' in unit` / `'mg' in unit`), so spelled-out or
microgram units mis-scaled the amount by 1000x:

  - sodium ``55 "Milligram(s)"`` → ``'g' in 'milligram(s)'`` True and
    ``'mg' not in 'milligram(s)'`` True → **×1000 → 55,000 mg** → false
    "High Sodium" and a flipped ``hypertension_friendly``.
  - sodium ``55 "mcg"`` → same ×1000 → 55,000 mg.
  - sugar ``5 "Milligram(s)"`` → ``'mg' in 'milligram(s)'`` False → left as
    **5 g** (1000× over-count) → false "High Sugar".

The fix routes both through the single mass-conversion authority
(``_normalize_threshold_unit`` → ``canonicalize_mass_unit`` → ``_convert_mass``)
that the rest of the enricher already uses — no per-function substring math.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from enrich_supplements_v3 import SupplementEnricherV3


@pytest.fixture(scope="module")
def enricher() -> SupplementEnricherV3:
    return SupplementEnricherV3()


_EMPTY_PRODUCT = {"activeIngredients": [], "otherIngredients": [], "inactiveIngredients": []}


class TestSodiumUnitReconciliation:
    """55 units of sodium must scale correctly regardless of unit spelling."""

    @pytest.mark.parametrize("unit,expected_mg,expect_high", [
        ("mg", 55.0, False),
        ("Milligram(s)", 55.0, False),   # substring bug → was 55,000 / High
        ("milligrams", 55.0, False),
        ("mcg", 0.1, False),             # round(0.055,1); substring bug → was 55,000 / High
        ("microgram", 0.1, False),
        ("g", 55000.0, True),            # control: grams genuinely ×1000
        ("Gram(s)", 55000.0, True),
    ])
    def test_sodium_amount_and_level(self, enricher, unit, expected_mg, expect_high) -> None:
        r = enricher._analyze_sodium_content(
            _EMPTY_PRODUCT, {"sodium": {"amount": 55, "unit": unit}}
        )
        assert r["amount_mg"] == pytest.approx(expected_mg), (
            f"55 {unit!r} sodium → {r['amount_mg']} mg (expected {expected_mg})"
        )
        assert (r["level"] == "high") == expect_high, (
            f"55 {unit!r} sodium classified level={r['level']!r} "
            f"(expected {'high' if expect_high else 'not-high'})"
        )


class TestSugarUnitReconciliation:
    """5 units of sugar must scale correctly regardless of unit spelling."""

    @pytest.mark.parametrize("unit,expected_g,expect_high", [
        ("g", 5.0, False),
        ("Gram(s)", 5.0, False),
        ("mg", 0.0, False),              # 5 mg → 0.005 g → rounds 0.0 (negligible)
        ("Milligram(s)", 0.0, False),    # substring miss → was left as 5 g / High
        ("mcg", 0.0, False),
    ])
    def test_sugar_amount_and_level(self, enricher, unit, expected_g, expect_high) -> None:
        r = enricher._analyze_sugar_content(
            _EMPTY_PRODUCT, {"sugars": {"amount": 5, "unit": unit}}
        )
        assert r["amount_g"] == pytest.approx(expected_g, abs=1e-6), (
            f"5 {unit!r} sugar → {r['amount_g']} g (expected {expected_g})"
        )
        assert (r["level"] == "high") == expect_high, (
            f"5 {unit!r} sugar classified level={r['level']!r} "
            f"(expected {'high' if expect_high else 'not-high'})"
        )
