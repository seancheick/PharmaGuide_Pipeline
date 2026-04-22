"""
Sprint E1.3.2.c — probiotic CFU adequacy point uplift.

Config-driven scorer hook that converts per-strain adequacy signals
(landed in E1.3.2.a + .b) into Section A points. Hard gates enforce
the "points follow confidence, not presence" invariant.

Scoring formula (per product, summed across matched strains, then
capped at ``per_product_max_uplift``):

    per_strain_points = tier_points[adequacy_tier] * support_level_caps[support]

Hard gates (return 0 for the strain, not for the product):
  * adequacy_tier is None → 0
  * cfu_per_day is None (multi-strain blend) → 0
  * strain not matched to clinical DB → 0

Config lives at ``section_A_ingredient_quality.probiotic_cfu_adequacy``.
``enabled=false`` disables the uplift (no code change required).

Dev check (external review):
  * projected +1% avg Section A across 798 probiotics
  * 0 new activations (products at A=0 stay at 0 — blends)
  * weak-support caps at 0.5x
  * multi-strain blends contribute 0
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from score_supplements import _compute_probiotic_cfu_adequacy_points  # noqa: E402


DEFAULT_CFG = {
    "enabled": True,
    "tier_points": {"low": 0.0, "adequate": 1.0, "good": 2.0, "excellent": 3.0},
    "support_level_caps": {"high": 1.0, "moderate": 0.75, "weak": 0.5},
    "per_product_max_uplift": 5.0,
}


def _strain(tier, support, cfu=10_000_000_000):
    return {
        "adequacy_tier": tier,
        "clinical_support_level": support,
        "cfu_per_day": cfu,
    }


# ---------------------------------------------------------------------------
# Single-strain, all tier × support combinations
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("tier,support,expected", [
    ("low",       "high",     0.0),   # low tier = 0 points regardless
    ("adequate",  "high",     1.0),   # 1 * 1.0
    ("good",      "high",     2.0),   # 2 * 1.0
    ("excellent", "high",     3.0),   # 3 * 1.0
    ("adequate",  "moderate", 0.75),  # 1 * 0.75
    ("good",      "moderate", 1.5),   # 2 * 0.75
    ("excellent", "moderate", 2.25),  # 3 * 0.75
    ("adequate",  "weak",     0.5),   # 1 * 0.5
    ("good",      "weak",     1.0),   # 2 * 0.5
    ("excellent", "weak",     1.5),   # 3 * 0.5
])
def test_single_strain_points_matrix(tier: str, support: str, expected: float) -> None:
    out = _compute_probiotic_cfu_adequacy_points(
        [_strain(tier, support)], DEFAULT_CFG,
    )
    assert out["probiotic_cfu_adequacy_points"] == pytest.approx(expected)


def test_canary_19067_shape() -> None:
    """L. plantarum 299v at 10B CFU, good tier, high support → 2.0 pts."""
    out = _compute_probiotic_cfu_adequacy_points(
        [_strain("good", "high", 10_000_000_000)], DEFAULT_CFG,
    )
    assert out["probiotic_cfu_adequacy_points"] == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# Hard gates — all return 0 for that strain
# ---------------------------------------------------------------------------

def test_multi_strain_blend_contributes_zero() -> None:
    """cfu_per_day=None signals multi-strain blend; adequacy_tier is
    also None. Both hard gates fire — 0 points."""
    out = _compute_probiotic_cfu_adequacy_points(
        [{"adequacy_tier": None, "clinical_support_level": "high", "cfu_per_day": None}],
        DEFAULT_CFG,
    )
    assert out["probiotic_cfu_adequacy_points"] == 0.0


def test_adequacy_tier_none_contributes_zero_even_with_cfu() -> None:
    """Defensive: even if cfu_per_day is known but tier is None (strain
    not in DB), contribution is 0."""
    out = _compute_probiotic_cfu_adequacy_points(
        [{"adequacy_tier": None, "clinical_support_level": "high",
          "cfu_per_day": 10_000_000_000}],
        DEFAULT_CFG,
    )
    assert out["probiotic_cfu_adequacy_points"] == 0.0


def test_unknown_support_level_defaults_to_weak_cap() -> None:
    """Conservative default: unknown support → 0.5 multiplier (weak)."""
    out = _compute_probiotic_cfu_adequacy_points(
        [_strain("good", "unknown_wibble")], DEFAULT_CFG,
    )
    assert out["probiotic_cfu_adequacy_points"] == pytest.approx(1.0)  # 2 * 0.5


# ---------------------------------------------------------------------------
# Multi-strain products (sum, then cap)
# ---------------------------------------------------------------------------

def test_multiple_single_strains_summed() -> None:
    out = _compute_probiotic_cfu_adequacy_points(
        [_strain("good", "high"), _strain("adequate", "moderate")],
        DEFAULT_CFG,
    )
    assert out["probiotic_cfu_adequacy_points"] == pytest.approx(2.0 + 0.75)


def test_per_product_cap_enforced() -> None:
    """Sum beyond 5.0 must cap at 5.0."""
    # 4 strains × 2.0 each = 8.0, capped at 5.0
    strains = [_strain("good", "high") for _ in range(4)]
    out = _compute_probiotic_cfu_adequacy_points(strains, DEFAULT_CFG)
    assert out["probiotic_cfu_adequacy_points"] == 5.0


# ---------------------------------------------------------------------------
# Config-driven: disabled returns 0 even on valid strain data
# ---------------------------------------------------------------------------

def test_disabled_config_returns_zero() -> None:
    cfg = {**DEFAULT_CFG, "enabled": False}
    out = _compute_probiotic_cfu_adequacy_points(
        [_strain("good", "high")], cfg,
    )
    assert out["probiotic_cfu_adequacy_points"] == 0.0


def test_missing_config_returns_zero() -> None:
    out = _compute_probiotic_cfu_adequacy_points(
        [_strain("good", "high")], {},
    )
    assert out["probiotic_cfu_adequacy_points"] == 0.0


def test_empty_strain_list_returns_zero() -> None:
    out = _compute_probiotic_cfu_adequacy_points([], DEFAULT_CFG)
    assert out["probiotic_cfu_adequacy_points"] == 0.0


# ---------------------------------------------------------------------------
# Output shape includes per-strain breakdown for audit
# ---------------------------------------------------------------------------

def test_output_includes_per_strain_breakdown() -> None:
    strains = [_strain("good", "high"), _strain("adequate", "moderate")]
    out = _compute_probiotic_cfu_adequacy_points(strains, DEFAULT_CFG)
    assert "strain_contributions" in out
    assert len(out["strain_contributions"]) == 2
    for sc in out["strain_contributions"]:
        assert "tier" in sc
        assert "support" in sc
        assert "points" in sc
