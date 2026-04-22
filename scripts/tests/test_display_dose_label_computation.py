"""
Sprint E1.2.2.b — display_dose_label regression tests.

External-dev rule (medical honesty): "Never imply knowledge the label
does not provide." The only three allowed output classes are:

  * ``"600 mg"`` — individually disclosed on the label
  * ``"Amount not disclosed"`` — proprietary-blend member (even when
    the blend total is known; member-level dose is NOT knowable)
  * ``"—"`` — truly missing (no dose declared anywhere)

Hard prohibitions:
  * NEVER infer per-ingredient dose from blend total / member count
  * NEVER leak the raw "NP" sentinel into user-facing text
  * NEVER emit "0 mg" — zero with a unit is a pipeline bug, render "—"

Covers invariants #2 (no_false_well_dosed_on_undisclosed) and #3
(no_np_leaks_to_display) from E1.0.1.
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

from scripts.build_final_db import _compute_display_dose_label  # noqa: E402


# ---------------------------------------------------------------------------
# Class 1: Individually disclosed → formatted dose
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("qty,unit,expected", [
    (600, "mg", "600 mg"),
    (600.0, "mg", "600 mg"),            # trailing .0 stripped
    (1000, "mg", "1000 mg"),
    (5, "mg", "5 mg"),                   # small dose
    (50, "mcg", "50 mcg"),
    (2, "g", "2 g"),
    (1.5, "mg", "1.5 mg"),               # fractional dose keeps decimal
    (0.5, "mg", "0.5 mg"),
])
def test_disclosed_dose_renders_as_value_unit(qty, unit, expected) -> None:
    ing = {"quantity": qty, "unit": unit, "isNestedIngredient": False, "proprietaryBlend": False}
    assert _compute_display_dose_label(ing) == expected


def test_disclosed_dose_strips_whitespace_around_unit() -> None:
    ing = {"quantity": 500, "unit": " mg ", "isNestedIngredient": False}
    assert _compute_display_dose_label(ing) == "500 mg"


# ---------------------------------------------------------------------------
# Class 2: Proprietary-blend member → "Amount not disclosed"
# ---------------------------------------------------------------------------

def test_prop_blend_member_np_unit_renders_amount_not_disclosed() -> None:
    """Plantizyme Amylase — isNestedIngredient=True, qty=0, unit='NP'."""
    ing = {
        "name": "Amylase",
        "quantity": 0.0,
        "unit": "NP",
        "isNestedIngredient": True,
        "parentBlend": "Proprietary Blend",
        "proprietaryBlend": True,
    }
    assert _compute_display_dose_label(ing) == "Amount not disclosed"


def test_prop_blend_member_zero_quantity_empty_unit() -> None:
    """Some DSLD blend members have qty=0 and unit='' rather than 'NP'."""
    ing = {
        "quantity": 0.0,
        "unit": "",
        "isNestedIngredient": True,
        "parentBlend": "Herbal Blend",
        "proprietaryBlend": True,
    }
    assert _compute_display_dose_label(ing) == "Amount not disclosed"


def test_prop_blend_flag_alone_triggers_not_disclosed() -> None:
    """Even without isNestedIngredient, proprietaryBlend=True with no
    individual dose must render as not disclosed."""
    ing = {
        "quantity": 0.0,
        "unit": "",
        "proprietaryBlend": True,
    }
    assert _compute_display_dose_label(ing) == "Amount not disclosed"


def test_prop_blend_member_with_disclosed_dose_renders_the_dose() -> None:
    """Partial-disclosure case: blend member with its own mg value on the
    label (e.g. "Ashwagandha 250 mg" inside "Herbal Blend 600 mg"). The
    individual dose was actually disclosed, so show it."""
    ing = {
        "quantity": 250,
        "unit": "mg",
        "isNestedIngredient": True,
        "parentBlend": "Herbal Blend",
        "proprietaryBlend": True,
    }
    assert _compute_display_dose_label(ing) == "250 mg"


# ---------------------------------------------------------------------------
# Class 3: Truly missing → em-dash
# ---------------------------------------------------------------------------

def test_truly_missing_renders_em_dash() -> None:
    """Non-blend ingredient with no dose declared — no inference, no NP
    leak; render the em-dash sentinel."""
    ing = {"quantity": 0, "unit": "", "isNestedIngredient": False}
    assert _compute_display_dose_label(ing) == "—"


def test_non_blend_with_np_unit_renders_em_dash() -> None:
    """Non-blend ingredient with unit='NP' is truly missing (the 'NP'
    sentinel must never leak to the user)."""
    ing = {"quantity": 0.0, "unit": "NP", "isNestedIngredient": False}
    assert _compute_display_dose_label(ing) == "—"


def test_missing_quantity_field_renders_em_dash() -> None:
    assert _compute_display_dose_label({}) == "—"


# ---------------------------------------------------------------------------
# Invariant #3 from E1.0.1 — NP must never leak to display_dose_label
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("qty,unit,is_nested", [
    (0, "NP", True),
    (0, "NP", False),
    (0.0, "NP", True),
    (0, "", True),
    (100, "NP", False),  # odd shape: value > 0 with NP unit — still no leak
])
def test_np_never_appears_in_output(qty, unit, is_nested) -> None:
    ing = {"quantity": qty, "unit": unit, "isNestedIngredient": is_nested,
           "proprietaryBlend": is_nested}
    label = _compute_display_dose_label(ing)
    assert "NP" not in label, f"NP leaked: {label!r}"


# ---------------------------------------------------------------------------
# Probiotic CFU special case — readable billion formatting
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("qty,expected", [
    (10_000_000_000, "10 billion CFU"),
    (5_000_000_000, "5 billion CFU"),
    (1_000_000_000, "1 billion CFU"),
    (2_500_000_000, "2.5 billion CFU"),  # non-integer billions keep decimal
    (500_000_000, "500000000 CFU"),      # below 1B falls back to plain count
])
def test_probiotic_cfu_rendered_in_billions_when_large(qty, expected) -> None:
    ing = {"quantity": qty, "unit": "CFU", "isNestedIngredient": False}
    assert _compute_display_dose_label(ing) == expected


def test_lactobacillus_canary_matches_19067_shape() -> None:
    """Canary 19067 Nature Made probiotic — 10B CFU L. plantarum 299v."""
    ing = {
        "name": "Lactobacillus plantarum 299v",
        "quantity": 10_000_000_000.0,
        "unit": "CFU",
        "isNestedIngredient": False,
    }
    assert _compute_display_dose_label(ing) == "10 billion CFU"


# ---------------------------------------------------------------------------
# NEVER infer dose from blend total (dev rule — medical honesty)
# ---------------------------------------------------------------------------

def test_does_not_divide_blend_total_across_members() -> None:
    """Even if parent blend has total_weight=850mg and there are 5
    members, we must NOT emit "170 mg" per member. The label only tells
    us 850mg total; member dose is unknowable."""
    ing = {
        "name": "Amylase",
        "quantity": 0.0,
        "unit": "NP",
        "isNestedIngredient": True,
        "parentBlend": "Proprietary Blend",
        "parentBlendMass": 850.0,       # blend total is known
        "parentBlendUnit": "mg",
        "proprietaryBlend": True,
    }
    label = _compute_display_dose_label(ing)
    # Must NOT contain any inferred number
    assert "170" not in label
    assert "850" not in label
    # Must render honestly
    assert label == "Amount not disclosed"


def test_zero_with_unit_not_rendered_as_zero_mg() -> None:
    """Defense against a bug where qty=0, unit='mg' could render as "0 mg".
    Zero with a unit is almost certainly a pipeline glitch — render em-dash."""
    ing = {"quantity": 0, "unit": "mg", "isNestedIngredient": False}
    assert _compute_display_dose_label(ing) == "—"
