"""
Sprint E1.2.2.d — display_badge regression tests.

Badge is a PURE FUNCTION of already-trusted fields. No inference, no
new heuristics, no dose-from-blend-total guessing. Dev rule: "Badges
reflect what the system already knows — not what it guesses."

Taxonomy (5 values only):
  * ``well_dosed``     — scorer adequacy tier is adequate/good
  * ``low_dose``       — scorer adequacy tier is low
  * ``high_dose``      — scorer adequacy tier is excellent/above-range
  * ``not_disclosed``  — prop-blend member without individual dose
  * ``no_data``        — fallback (scorer has no adequacy signal OR dose missing)

Short-circuit decision order:
  1. blend member + undisclosed dose → not_disclosed
  2. no dose or NP unit              → no_data
  3. scorer-computed adequacy tier   → map tier → badge
  4. else                            → no_data (never well_dosed by inference)

Covers invariant #2 (no_false_well_dosed_on_undisclosed) from E1.0.1.
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

from scripts.build_final_db import _compute_display_badge  # noqa: E402


# ---------------------------------------------------------------------------
# Rule 1 — blend member without individual dose → not_disclosed
# ---------------------------------------------------------------------------

def test_blend_member_without_dose_is_not_disclosed() -> None:
    ing = {
        "name": "Amylase",
        "quantity": 0.0,
        "unit": "NP",
        "isNestedIngredient": True,
        "parentBlend": "Proprietary Blend",
        "proprietaryBlend": True,
    }
    assert _compute_display_badge(ing) == "not_disclosed"


def test_blend_member_even_with_known_parent_mass_is_not_disclosed() -> None:
    """Anti-inference: even if parent blend total is known, each member
    WITHOUT its own dose renders as not_disclosed. We must never divide
    or infer."""
    ing = {
        "quantity": 0.0,
        "unit": "NP",
        "isNestedIngredient": True,
        "parentBlend": "Herbal Blend",
        "parentBlendMass": 500.0,   # blend total present
        "parentBlendUnit": "mg",
        "proprietaryBlend": True,
    }
    assert _compute_display_badge(ing) == "not_disclosed"


def test_blend_member_with_individual_dose_is_not_not_disclosed() -> None:
    """Partial disclosure: a blend member with its own mg value on the
    label no longer qualifies for the not_disclosed shortcut."""
    ing = {
        "quantity": 250,
        "unit": "mg",
        "isNestedIngredient": True,
        "parentBlend": "Herbal Blend",
        "proprietaryBlend": True,
    }
    # Without scorer adequacy signal we still return no_data (rule 4),
    # but NOT not_disclosed (rule 1 is only for undisclosed cases).
    assert _compute_display_badge(ing) != "not_disclosed"


# ---------------------------------------------------------------------------
# Rule 2 — no dose / NP unit on non-blend → no_data
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("qty,unit", [
    (0, ""),
    (0, "NP"),
    (0.0, "NP"),
    (None, None),
    (0, "n/p"),
])
def test_missing_or_np_dose_is_no_data(qty, unit) -> None:
    ing = {"quantity": qty, "unit": unit, "isNestedIngredient": False}
    assert _compute_display_badge(ing) == "no_data"


def test_empty_ingredient_is_no_data() -> None:
    assert _compute_display_badge({}) == "no_data"


# ---------------------------------------------------------------------------
# Rule 3 — scorer-supplied adequacy tier → badge map
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("tier,expected", [
    ("low",        "low_dose"),
    ("adequate",   "well_dosed"),
    ("good",       "well_dosed"),
    ("excellent",  "high_dose"),
    ("above_typical_range", "high_dose"),
])
def test_scorer_adequacy_tier_maps_to_badge(tier: str, expected: str) -> None:
    """When the scorer already computed adequacy (e.g. via E1.3.2 probiotic
    CFU adequacy path), badge maps the tier label."""
    ing = {
        "quantity": 100,
        "unit": "mg",
        "adequacy_tier": tier,
    }
    assert _compute_display_badge(ing) == expected


def test_unknown_adequacy_tier_falls_back_to_no_data() -> None:
    """Defensive: a future scorer tier label we don't know about must
    NOT silently become well_dosed. Fall through to no_data."""
    ing = {"quantity": 100, "unit": "mg", "adequacy_tier": "wibble"}
    assert _compute_display_badge(ing) == "no_data"


# ---------------------------------------------------------------------------
# Rule 4 — dose present but no adequacy signal → no_data (NEVER well_dosed)
# ---------------------------------------------------------------------------

def test_disclosed_dose_without_adequacy_signal_is_no_data() -> None:
    """KSM-66 600 mg without a scorer-emitted adequacy tier stays
    no_data. We do NOT infer well_dosed from dose magnitude alone."""
    ing = {
        "name": "KSM-66",
        "quantity": 600,
        "unit": "mg",
        "isNestedIngredient": False,
    }
    assert _compute_display_badge(ing) == "no_data"


# ---------------------------------------------------------------------------
# Anti-overclaim — blend undisclosed can NEVER be well_dosed
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("maliciously_set_tier", ["adequate", "good", "excellent"])
def test_blend_undisclosed_never_becomes_well_dosed(maliciously_set_tier: str) -> None:
    """Invariant #2 hardening: even if upstream erroneously attached an
    adequacy tier to a blend-undisclosed member, the badge must NOT
    render as well_dosed. Rule 1 short-circuits first."""
    ing = {
        "quantity": 0.0,
        "unit": "NP",
        "isNestedIngredient": True,
        "proprietaryBlend": True,
        "adequacy_tier": maliciously_set_tier,
    }
    badge = _compute_display_badge(ing)
    assert badge == "not_disclosed"
    assert badge != "well_dosed"


# ---------------------------------------------------------------------------
# Non-mutation guarantee
# ---------------------------------------------------------------------------

def test_badge_does_not_mutate_ingredient() -> None:
    ing = {
        "name": "KSM-66",
        "quantity": 600,
        "unit": "mg",
        "adequacy_tier": "adequate",
    }
    before = dict(ing)
    _compute_display_badge(ing)
    assert ing == before


# ---------------------------------------------------------------------------
# Canary expectations (dev pre-defined)
# ---------------------------------------------------------------------------

def test_plantizyme_enzyme_canary() -> None:
    """35491 enzymes: all blend members, undisclosed → not_disclosed."""
    ing = {"quantity": 0.0, "unit": "NP", "isNestedIngredient": True,
           "proprietaryBlend": True}
    assert _compute_display_badge(ing) == "not_disclosed"


def test_ksm66_600mg_canary_without_scorer_signal() -> None:
    """306237 KSM-66 600 mg — conservative until scorer provides
    adequacy signal (E1.3.2 path)."""
    ing = {"quantity": 600, "unit": "mg", "isNestedIngredient": False}
    assert _compute_display_badge(ing) == "no_data"


def test_probiotic_with_adequacy_tier_maps() -> None:
    """19067 probiotic — IF the scorer attached adequacy_tier=adequate
    via the (future) E1.3.2 probiotic CFU path, we render well_dosed."""
    ing = {
        "quantity": 10_000_000_000,
        "unit": "CFU",
        "adequacy_tier": "adequate",
    }
    assert _compute_display_badge(ing) == "well_dosed"


# ---------------------------------------------------------------------------
# Badge value must always be one of the 5 taxonomy strings
# ---------------------------------------------------------------------------

VALID_BADGES = {"well_dosed", "low_dose", "high_dose", "not_disclosed", "no_data"}


@pytest.mark.parametrize("ing", [
    {},
    {"quantity": 0, "unit": ""},
    {"quantity": 100, "unit": "mg"},
    {"quantity": 0, "unit": "NP", "isNestedIngredient": True, "proprietaryBlend": True},
    {"quantity": 100, "unit": "mg", "adequacy_tier": "low"},
    {"quantity": 100, "unit": "mg", "adequacy_tier": "wibble"},
])
def test_badge_always_in_taxonomy(ing) -> None:
    assert _compute_display_badge(ing) in VALID_BADGES
