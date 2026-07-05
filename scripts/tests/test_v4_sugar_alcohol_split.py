#!/usr/bin/env python3
"""Dietary-sugar SPLIT: de-conflate sugar alcohols from syrup/high-glycemic (2026-07-04).

CALIBRATION CHANGE (not score-neutral): pure sugar alcohols (erythritol/xylitol/
sorbitol with no syrup and not high-glycemic) now take a light `sugar_alcohol_source`
penalty (1.0) instead of being lumped with corn-syrup / high-glycemic sugar at 2.0.
Real added sugar (syrup or high-glycemic) is unchanged at 2.0. Validated by an
S6-style corpus sim: ~93 alcohol-only products gain ~1.8 pts, real-sugar products
untouched. B (syrup->3) is parked.
"""
import json
import sys
from pathlib import Path

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from scoring_v4.modules import generic_formulation as gf   # noqa: E402

FM = json.loads((SCRIPTS_ROOT / "scoring_v4" / "config" / "quality_score.json").read_text())["formulation_magnitudes"]


def _det(sugar=None, sweeteners=None):
    return gf._dietary_sugar_penalty_detail(
        {"dietary_sensitivity_data": {"sugar": sugar or {}, "sweeteners": sweeteners or {}}}
    )


def test_config_and_runtime_have_split_keys():
    assert FM["dietary_sugar_sugar_alcohol_penalty"] == 1.0
    assert FM["dietary_sugar_high_glycemic_or_syrup_penalty"] == 2.0
    assert "dietary_sugar_high_glycemic_or_alcohol_penalty" not in FM  # old lumped key gone
    assert gf.DIETARY_SUGAR_SUGAR_ALCOHOL_PENALTY == 1.0
    assert gf.DIETARY_SUGAR_HIGH_GLYCEMIC_OR_SYRUP_PENALTY == 2.0


def test_pure_sugar_alcohol_gets_light_split_penalty():
    d = _det(sweeteners={"sugar_alcohols": ["erythritol"]})
    assert d["penalty"] == 1.0
    assert d["reason"] == "sugar_alcohol_source"


def test_syrup_stays_real_sugar_band():
    d = _det(sugar={"sugar_sources": ["corn syrup"], "contains_sugar": True, "has_added_sugar": True})
    assert d["penalty"] == 2.0
    assert d["reason"] == "high_glycemic_or_syrup"


def test_high_glycemic_stays_real_sugar_band():
    d = _det(sweeteners={"high_glycemic": ["glucose"]})
    assert d["penalty"] == 2.0
    assert d["reason"] == "high_glycemic_or_syrup"


def test_sugar_alcohol_plus_syrup_stays_real_sugar_band():
    # real sugar wins — an alcohol product that ALSO has syrup is not "benign"
    d = _det(sugar={"sugar_sources": ["glucose syrup"]}, sweeteners={"sugar_alcohols": ["maltitol"]})
    assert d["penalty"] == 2.0
    assert d["reason"] == "high_glycemic_or_syrup"


def test_gram_bands_unchanged():
    assert _det(sugar={"level": "high"})["penalty"] == 4.0
    assert _det(sugar={"level": "high"})["reason"] == "high_sugar_grams"
    assert _det(sugar={"level": "moderate"})["penalty"] == 3.0
    assert _det(sugar={"has_added_sugar": True})["penalty"] == 1.0
    assert _det(sugar={"has_added_sugar": True})["reason"] == "low_added_sugar_source"
    assert _det()["penalty"] == 0.0 and _det()["reason"] is None
