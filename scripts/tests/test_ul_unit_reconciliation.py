"""
P0-1a regression — UL/RDA unit reconciliation in RDAULCalculator.

Root cause: ``compute_nutrient_adequacy`` compared the label ``amount`` directly
against the RDA/UL table's ``rda_ai``/``ul`` without reconciling the label
``unit`` against the table's own ``unit``. ``unit_converter.convert_nutrient`` is
a no-op for plain minerals (it only converts vitamin IU/forms), so the label
unit reached the calculator unchanged and mismatched units were divided:

  - Boron 150 mcg vs a 20 **mg** UL  -> 150/20 = 750% "over UL"  (FALSE positive)
  - Copper 2 mg vs a 900 **mcg** RDA -> 2/900 = 0.22% RDA         (FALSE negative)

Medical impact: false over-UL flags (would drive false CAUTION once the verdict
gate lands) AND missed real exposures where the label unit is larger than the
table unit.

Fix: convert ``amount`` from its unit to the table's unit before computing
pct_rda / pct_ul / over_ul. When the units are incompatible (e.g. raw IU vs a
mass reference), the check is NOT evaluated (pct_ul=None) rather than comparing
mismatched numbers — "not evaluable", never a false flag.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from rda_ul_calculator import RDAULCalculator


@pytest.fixture(scope="module")
def calc() -> RDAULCalculator:
    return RDAULCalculator()


class TestSmallLabelUnitVsLargerTableUnit:
    """Label in mcg, table UL in mg — must convert down, not divide raw."""

    def test_boron_150mcg_not_over_20mg_ul(self, calc) -> None:
        # 150 mcg = 0.15 mg; UL = 20 mg -> 0.75% UL, nowhere near over.
        r = calc.compute_nutrient_adequacy(nutrient="Boron", amount=150, unit="mcg")
        assert r.over_ul is False, (
            f"Boron 150 mcg wrongly flagged over a 20 mg UL (pct_ul={r.pct_ul})"
        )
        assert r.pct_ul is not None and r.pct_ul < 5, (
            f"Boron 150 mcg should be ~0.75% of a 20 mg UL, got {r.pct_ul}"
        )


class TestLargeLabelUnitVsSmallerTableUnit:
    """Label in mg, table RDA/UL in mcg — must convert up, not divide raw."""

    def test_copper_2mg_converts_to_2000mcg(self, calc) -> None:
        # 2 mg = 2000 mcg; RDA 900 mcg -> ~222% RDA; UL 10000 mcg -> 20% UL.
        r = calc.compute_nutrient_adequacy(nutrient="Copper", amount=2, unit="mg")
        assert r.pct_rda == pytest.approx(222.2, rel=0.05), (
            f"Copper 2 mg should be ~222% of a 900 mcg RDA, got {r.pct_rda}"
        )
        assert r.pct_ul == pytest.approx(20.0, rel=0.1), (
            f"Copper 2 mg should be ~20% of a 10000 mcg UL, got {r.pct_ul}"
        )
        assert r.over_ul is False


class TestIncompatibleUnitsNotEvaluated:
    """Raw IU against a mass reference cannot be compared — must not flag."""

    def test_vitamin_a_raw_iu_not_compared_to_mcg_ul(self, calc) -> None:
        # Vitamin A table unit is "mcg RAE". Raw IU needs form-aware conversion
        # (retinol vs beta-carotene) upstream; the calculator must NOT compare
        # 5000 (IU) to a 3000 (mcg RAE) UL and declare it over.
        r = calc.compute_nutrient_adequacy(nutrient="Vitamin A", amount=5000, unit="IU")
        assert r.pct_ul is None, (
            f"Vitamin A raw IU must not be compared to a mcg-RAE UL, got pct_ul={r.pct_ul}"
        )
        assert r.over_ul is False


class TestMatchingUnitsUnchanged:
    """Regression guards: when label unit already matches the table unit,
    behavior is byte-identical to before the fix."""

    def test_vitamin_d3_250mcg_still_over_ul(self, calc) -> None:
        # Units already match (mcg vs mcg UL 100) — real over-UL must survive.
        r = calc.compute_nutrient_adequacy(nutrient="Vitamin D3", amount=250, unit="mcg")
        assert r.over_ul is True
        assert r.pct_ul == pytest.approx(250.0, rel=0.05)

    def test_vitamin_c_500mg_native_unit_unchanged(self, calc) -> None:
        # mg label vs mg UL (2000) — 25% UL, not over.
        r = calc.compute_nutrient_adequacy(nutrient="Vitamin C", amount=500, unit="mg")
        assert r.over_ul is False
        assert r.pct_ul == pytest.approx(25.0, rel=0.1)
