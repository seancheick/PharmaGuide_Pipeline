"""V4 probiotic route fix — zero-quantity (phantom) non-probiotic panel.

Regression (found 2026-06-15 in the pre-250K route audit): the non-probiotic
panel counters (`scoring_input_contract._route_non_probiotic_scorable_count` and
the parity mirror `scoring_v4.router._non_probiotic_scorable_count`) count EVERY
non-probiotic scorable row regardless of disclosed amount. An *undisclosed*
(quantity == 0) blend therefore inflates the panel and demotes a genuine
probiotic to ``generic``:

  Kids 5 Billion CFU (327401 / 64941): 5 strains + 5B CFU, but ~23 fruit/veg
    "superfood" rows are all quantity==0 -> FULL panel 23, demoted to generic.
  Probiotic GX (242572): 20B CFU + "Probiotic" name, 1 strain + a digestive
    "Enzyme Blend" header (disclosed) whose 3 enzyme children are quantity==0 ->
    FULL panel 4, demoted to generic.

The fix uses a DISCLOSED (positive-quantity) count for the pure-strain promotion
paths (``panel == 0``) and the small-adjunct-with-name gate, while KEEPING the
full count for the ``strain_count >= panel`` dominance threshold. The naive fix
(positive-qty everywhere) over-promotes real multivitamins, so these guards are
load-bearing and pinned below:

  Garden of Life "Women 50 & Wiser" (multivitamin, full positive vitamin panel +
    85B CFU / 26 strains) must STAY multi — 26 strains must not edge the FULL
    panel (30) even though it edges the disclosed vitamin count (24).
  Golden Milk (turmeric/ashwagandha hero disclosed at qty==0; iron/potassium
    disclosed) must STAY generic — disclosed panel != 0, so the pure-strain path
    cannot fire, and a specific mineral taxonomy + no probiotic name blocks it.
  "Magnesium with Pre & Probiotics" / "Digestive Enzymes With Probiotics" combos
    must STAY non-probiotic — the non-probiotic hero precedes the probiotic token.

Both routing brains (the live ``scoring_input_contract`` path behind
``class_for_product`` and the ``scoring_v4.router`` parity baseline
``_legacy_class_for_product``) must agree, so every case asserts both.
"""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from scoring_input_contract import _route_non_probiotic_scorable_count  # noqa: E402
from scoring_v4.router import (  # noqa: E402
    class_for_product,
    _legacy_class_for_product,
    _non_probiotic_scorable_count,
)


def _prod(name, primary_type, scorable, *, strains, billion, is_prob=True):
    return {
        "product_name": name,
        "primary_type": primary_type,
        "probiotic_data": {
            "is_probiotic_product": is_prob,
            "total_strain_count": strains,
            "has_cfu": bool(billion),
            "total_cfu": (billion or 0) * 1_000_000_000.0,
            "total_billion_count": billion,
        },
        "ingredient_quality_data": {"total_active": len(scorable), "ingredients_scorable": scorable},
    }


def _row(name, canonical, qty, unit="mg"):
    return {"name": name, "canonical_id": canonical, "mapped": True, "quantity": qty, "unit": unit}


def _route(product):
    """Assert the live and legacy routers agree, and return the agreed route."""
    live = class_for_product(product)
    legacy = _legacy_class_for_product(product)
    assert live == legacy, f"router parity drift: live={live} legacy={legacy}"
    return live


# --------------------------------------------------------------------------- #
# Fixtures modelled on the real enriched catalog rows (see module docstring).
# --------------------------------------------------------------------------- #

def _kids_5b():
    # 6 quantity==0 "superfood" rows + 2 positive blend rows the counter already
    # skips (inulin = prebiotic, probiotic blend) -> disclosed non-prob panel = 0.
    rows = [
        _row(n, c, 0)
        for n, c in [
            ("Strawberry", "strawberry"), ("Carrot", "carrot"), ("Spinach", "spinach"),
            ("Broccoli", "broccoli"), ("Kale", "kale"), ("Beet", "beetroot"),
        ]
    ] + [
        _row("Inulin", "inulin", 50),
        _row("Probiotic & Microbiome Blends", "probiotic_microbiome_blend", 100),
    ]
    return _prod("Kids 5 Billion CFU", "probiotic", rows, strains=5, billion=5.0)


def _probiotic_gx():
    # 3 quantity==0 enzyme children + 1 disclosed "Enzyme Blend" header.
    rows = [_row(n, "digestive_enzymes", 0) for n in ("Amylase", "Lipase", "Protease")]
    rows += [_row("Enzyme Blend", "digestive_enzymes", 75)]
    return _prod("Probiotic GX", "probiotic", rows, strains=1, billion=20.0)


def _gol_women_50():
    # 24 disclosed vitamins/minerals + 6 quantity==0 phantom rows -> FULL 30,
    # disclosed 24, with 26 strains. Name carries "Probiotics".
    vits = [_row(f"Vitamin/Mineral {i}", f"micro_{i}", 100) for i in range(24)]
    phantom = [_row(n, c, 0) for n, c in [
        ("Bulgarian Yogurt", "lactobacillus_bulgaricus"), ("Green Pea", "pea"),
        ("Carrot", "carrot"), ("Plum", "plum"), ("Cherry", "dark_sweet_cherry"),
        ("Strawberry", "strawberry"),
    ]]
    return _prod("Women 50 & Wiser Raw Probiotics", "multivitamin", vits + phantom,
                 strains=26, billion=85.0)


def _golden_milk():
    # turmeric/ashwagandha HERO disclosed at qty==0; iron/potassium + blends
    # disclosed -> disclosed non-prob panel = 4 (NOT zero). No probiotic name.
    rows = [
        _row("Iron", "iron", 8), _row("Potassium", "potassium", 100),
        _row("Organic Golden Milk Blend", "organic_golden_milk_blend", 500),
        _row("Organic Turmeric Blend", "turmeric", 400),
    ] + [_row(n, c, 0) for n, c in [
        ("Turmeric", "turmeric"), ("Ashwagandha", "ashwagandha"), ("Ginger", "ginger"),
        ("Cinnamon", "cinnamon"), ("Cardamom", "cardamom"), ("Black Pepper", "piperine"),
    ]]
    return _prod("Golden Milk", "single_mineral", rows, strains=3, billion=1.0)


def _magnesium_with_probiotics():
    rows = [_row("Magnesium", "magnesium", 200), _row("Prebiotic Fiber", "inulin", 0)]
    return _prod("Magnesium with Pre & Probiotics Gummies", "probiotic", rows,
                 strains=2, billion=1.25)


def _enzymes_with_probiotics():
    rows = [_row(n, "digestive_enzymes", 0) for n in ("Amylase", "Lipase", "Cellulase", "Bromelain")]
    rows += [_row("Enzyme Blend", "digestive_enzymes", 90)]
    return _prod("Enhanced Super Digestive Enzymes With Probiotics", "probiotic", rows,
                 strains=2, billion=1.0)


def _digestive_enzymes_dominant():
    rows = [_row(f"Enzyme {i}", "digestive_enzymes", 50) for i in range(13)]
    return _prod("Digestive Enzymes", "probiotic", rows, strains=1, billion=1.0)


# --------------------------------------------------------------------------- #
# RED: genuine probiotics demoted by a phantom (quantity==0) panel.
# --------------------------------------------------------------------------- #

def test_kids_5b_cfu_phantom_superfood_panel_routes_probiotic():
    assert _route(_kids_5b()) == "probiotic"


def test_probiotic_gx_phantom_enzyme_children_routes_probiotic():
    assert _route(_probiotic_gx()) == "probiotic"


# --------------------------------------------------------------------------- #
# GUARD: the naive "positive-qty everywhere" fix over-promotes these. They must
# stay non-probiotic with the disclosed-count-only-for-pure-strain fix.
# --------------------------------------------------------------------------- #

def test_gol_women_50_full_vitamin_panel_with_strains_stays_multi():
    # 26 strains edge the 24 disclosed vitamins but NOT the full panel of 30.
    assert _route(_gol_women_50()) == "multi_or_prenatal"


def test_golden_milk_zero_qty_botanical_hero_stays_non_probiotic():
    assert _route(_golden_milk()) != "probiotic"


def test_magnesium_with_probiotics_hero_precedes_stays_non_probiotic():
    assert _route(_magnesium_with_probiotics()) != "probiotic"


def test_digestive_enzymes_with_probiotics_hero_precedes_stays_non_probiotic():
    assert _route(_enzymes_with_probiotics()) != "probiotic"


def test_disclosed_enzyme_dominant_single_strain_stays_non_probiotic():
    assert _route(_digestive_enzymes_dominant()) != "probiotic"


# --------------------------------------------------------------------------- #
# Counter contract: disclosed count excludes quantity==0 rows; full count keeps
# them. Pinned on BOTH the live and parity counters.
# --------------------------------------------------------------------------- #

def test_live_counter_full_includes_zero_qty_disclosed_excludes():
    kids = _kids_5b()
    assert _route_non_probiotic_scorable_count(kids) == 6
    assert _route_non_probiotic_scorable_count(kids, require_disclosed=True) == 0


def test_parity_counter_full_includes_zero_qty_disclosed_excludes():
    kids = _kids_5b()
    assert _non_probiotic_scorable_count(kids) == 6
    assert _non_probiotic_scorable_count(kids, require_disclosed=True) == 0


def test_probiotic_gx_disclosed_panel_is_one_full_is_four():
    gx = _probiotic_gx()
    assert _route_non_probiotic_scorable_count(gx) == 4
    assert _route_non_probiotic_scorable_count(gx, require_disclosed=True) == 1
    assert _non_probiotic_scorable_count(gx) == 4
    assert _non_probiotic_scorable_count(gx, require_disclosed=True) == 1
