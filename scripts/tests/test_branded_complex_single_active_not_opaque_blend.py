#!/usr/bin/env python3
"""Branded SINGLE-active ingredients whose name ends in "Complex"/"Matrix"
must NOT be emitted as fully-opaque proprietary blends (v4 B5 root fix).

Bug (v4 scoring): the cleaner (`enhanced_normalizer`) stamps
``proprietaryBlend=True`` + ``disclosureLevel='none'`` on ANY single
ingredient whose name merely *contains* a marketing suffix token
("complex"/"matrix"/"formula"/...). The enricher's
``_collect_proprietary_data`` then turns that soft hint into an
*authoritative* opaque-blend record, so a branded single active with a
disclosed dose and no sub-ingredients is penalized by the B5 transparency
opacity penalty even though it hides nothing.

Verified evidence (enriched corpus): 183201 EpiCor, 273386 Curcumin C3
Complex, 227855 Clarinol CLA, 213448 Boron Complex, 201803/66380 Citrus
Bioflavonoid Complex — each emits
``proprietary_blends=[{disclosure_level:"none", total_weight:<dose>,
hidden_count:0, nested_count:0, child_ingredients:[], sources:["cleaning"]}]``.

ROOT FIX: a candidate with NO sub-ingredients, NO blend parent, that
resolves to ONE known canonical therapeutic ingredient (the chemical-
identity test, same predicate the scorer already trusts via
``_is_known_therapeutic``) is a branded single active — not an opaque
blend. It must NOT produce a B5-scoreable opaque-blend record.

GUARDRAIL (must stay penalized): genuine multi-ingredient blends that
disclose only a total ("Proprietary Blend", "Super Greens Blend") do NOT
resolve to a single canonical ingredient, and blends with undisclosed
nested children are structurally opaque. Both keep the penalty.
"""

import logging
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
logging.disable(logging.CRITICAL)

from enrich_supplements_v3 import SupplementEnricherV3  # noqa: E402


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3()


def _single_active_product(name, standard_name, qty=250, unit="mg"):
    """A cleaned product carrying ONE branded single-active flagged by the
    cleaner as a proprietary blend (disclosure 'none', no sub-ingredients).

    Mirrors the real cleaned shape: scalar ``quantity``, populated
    ``standardName`` (the cleaner resolves the canonical identity), and an
    empty ``nestedIngredients`` list.
    """
    return {
        "id": "999999",
        "fullName": f"{name} Product",
        "brandName": "Test Brand",
        "activeIngredients": [
            {
                "name": name,
                "standardName": standard_name,
                "quantity": qty,
                "unit": unit,
                "proprietaryBlend": True,
                "disclosureLevel": "none",
                "nestedIngredients": [],
            }
        ],
        "inactiveIngredients": [],
    }


def _opaque_blend_entries(proprietary_data):
    return [
        b
        for b in (proprietary_data.get("blends") or [])
        if str(b.get("disclosure_level", "")).lower() == "none"
    ]


# ---------------------------------------------------------------------------
# Branded single actives — must NOT be opaque blends
# ---------------------------------------------------------------------------

# (display name, cleaner-resolved standardName) for the verified corpus cases.
SINGLE_ACTIVE_CASES = [
    ("Curcumin C3 Complex", "Curcumin"),                       # 273386
    ("EpiCor dried Yeast Fermentate Complex", "Yeast Fermentate"),  # 183201
    ("Clarinol CLA Complex", "Conjugated Linoleic Acid"),      # 227855
    ("Boron Complex", "Boron"),                                # 213448
    ("Citrus Bioflavonoid Complex", "Citrus Bioflavonoids"),   # 201803 / 66380
]


@pytest.mark.parametrize("name,standard_name", SINGLE_ACTIVE_CASES)
def test_branded_complex_single_active_not_emitted_as_opaque_blend(
    enricher, name, standard_name
):
    product = _single_active_product(name, standard_name)
    proprietary_data = enricher._collect_proprietary_data(product)

    opaque = _opaque_blend_entries(proprietary_data)
    assert opaque == [], (
        f"{name!r} resolves to one canonical ingredient ({standard_name!r}) with a "
        f"disclosed dose and no sub-ingredients — it hides nothing and must NOT be "
        f"emitted as an opaque proprietary blend. Got: {opaque!r}"
    )
    assert proprietary_data.get("has_proprietary_blends") is False


def test_curcumin_c3_complex_still_scores_as_a_real_active(enricher):
    """The fix must suppress the spurious opacity penalty WITHOUT dropping the
    ingredient from quality scoring — it is still a real, scorable active."""
    product = _single_active_product("Curcumin C3 Complex", "Curcumin")
    iqd = enricher._collect_ingredient_quality_data(product)
    rows = iqd.get("ingredients") or []
    canon = {(r.get("canonical_id") or r.get("standard_name")) for r in rows}
    assert "curcumin" in canon, (
        "Curcumin C3 Complex must remain a scorable active (canonical_id=curcumin); "
        f"got scorable canonicals {canon!r}"
    )


# ---------------------------------------------------------------------------
# Genuine opaque blends — must STAY penalized (control)
# ---------------------------------------------------------------------------


def test_generic_proprietary_blend_total_only_stays_opaque(enricher):
    """"Proprietary Blend" discloses only a total and resolves to NO single
    canonical ingredient — it is genuinely opaque and keeps the penalty."""
    product = _single_active_product("Proprietary Blend", "")
    proprietary_data = enricher._collect_proprietary_data(product)

    assert proprietary_data.get("has_proprietary_blends") is True
    assert _opaque_blend_entries(proprietary_data), (
        "A generic 'Proprietary Blend' that discloses only a total must remain a "
        "B5-scoreable opaque blend (it does not resolve to a single canonical ingredient)."
    )


def test_superfood_blend_total_only_stays_opaque(enricher):
    product = _single_active_product("Super Greens Blend", "")
    proprietary_data = enricher._collect_proprietary_data(product)

    assert proprietary_data.get("has_proprietary_blends") is True
    assert _opaque_blend_entries(proprietary_data)


def test_blend_with_undisclosed_nested_children_stays_opaque(enricher):
    """A multi-ingredient blend with named-but-undosed children is structurally
    opaque regardless of any canonical name match — keep the penalty."""
    product = {
        "id": "999998",
        "fullName": "Joint Support Product",
        "brandName": "Test Brand",
        "activeIngredients": [
            {
                "name": "Joint Support Blend",
                "standardName": "",
                "quantity": 1500,
                "unit": "mg",
                "proprietaryBlend": True,
                "disclosureLevel": "none",
                "nestedIngredients": [
                    {"name": "Glucosamine", "quantity": 0, "unit": "NP"},
                    {"name": "Chondroitin", "quantity": 0, "unit": "NP"},
                    {"name": "MSM", "quantity": 0, "unit": "NP"},
                ],
            }
        ],
        "inactiveIngredients": [],
    }
    proprietary_data = enricher._collect_proprietary_data(product)

    assert proprietary_data.get("has_proprietary_blends") is True
    opaque = _opaque_blend_entries(proprietary_data)
    assert opaque, "A blend with undisclosed nested children must stay opaque."
    assert any((b.get("hidden_count") or 0) >= 1 for b in opaque)
