#!/usr/bin/env python3
"""
IQM coverage: Black Cherry (Batch 5 IQM gap fill #6).

Black cherry concentrate is Prunus serotina in FDA/GSRS and in
botanical_ingredients.json. Sweet/dark sweet cherry (Prunus avium) is a
separate parent (`dark_sweet_cherry`) so sweet-cherry labels remain scoreable
without corrupting black_cherry identifiers.

Identifiers verified via:
- FDA GSRS: UNII A77056YJ4K ("BLACK CHERRY"), CAS 84604-07-9
- UMLS: CUI C0330655 (Prunus serotina, MTH; classification=Plant)
- DSLD: 3 product references under "botanical|Black cherry"

Distinct from `tart_cherry` (Prunus cerasus / Montmorency) and
`dark_sweet_cherry` (Prunus avium).
"""

import json
import os

import pytest


@pytest.fixture(scope="module")
def iqm():
    return json.load(open(os.path.join(
        os.path.dirname(__file__), "..", "data", "ingredient_quality_map.json"
    )))


def test_black_cherry_iqm_entry_exists(iqm):
    assert "black_cherry" in iqm


def test_black_cherry_identifiers(iqm):
    e = iqm["black_cherry"]
    assert e.get("cui") == "C0330655"
    assert e.get("external_ids", {}).get("unii") == "A77056YJ4K"
    assert e.get("external_ids", {}).get("cas") == "84604-07-9"


def test_dark_sweet_cherry_identifiers(iqm):
    e = iqm["dark_sweet_cherry"]
    assert e.get("cui") == "C0946748"
    assert e.get("rxcui") == "901303"
    assert e.get("external_ids", {}).get("unii") == "93T4562ZI3"


def test_black_cherry_score_formula(iqm):
    e = iqm["black_cherry"]
    for form_key, form in e.get("forms", {}).items():
        if not isinstance(form, dict):
            continue
        bio = form.get("bio_score")
        score = form.get("score")
        natural = bool(form.get("natural", False))
        if isinstance(bio, (int, float)) and isinstance(score, (int, float)):
            assert score == bio + (3 if natural else 0)


def test_black_cherry_aliases(iqm):
    e = iqm["black_cherry"]
    all_aliases = set()
    for f in e.get("forms", {}).values():
        if isinstance(f, dict):
            all_aliases |= {a.lower().strip() for a in f.get("aliases", []) or []}
    needed = {
        "black cherry",
        "black cherry concentrate",
        "black cherry extract",
        "prunus serotina",
    }
    missing = needed - all_aliases
    assert not missing, f"Missing aliases: {missing}"
    assert "prunus avium" not in all_aliases
    assert "sweet cherry extract" not in all_aliases


def test_dark_sweet_cherry_aliases(iqm):
    e = iqm["dark_sweet_cherry"]
    all_aliases = set()
    for f in e.get("forms", {}).values():
        if isinstance(f, dict):
            all_aliases |= {a.lower().strip() for a in f.get("aliases", []) or []}
    needed = {
        "dark sweet cherry",
        "sweet cherry powder",
        "sweet cherry extract",
        "prunus avium",
    }
    missing = needed - all_aliases
    assert not missing, f"Missing aliases: {missing}"
    assert "black cherry" not in all_aliases


def test_black_cherry_does_not_collide_with_tart_cherry(iqm):
    """Cherry species entries must not share form aliases."""
    parents = ("black_cherry", "dark_sweet_cherry", "tart_cherry")

    alias_sets = {}
    for parent in parents:
        aliases = set()
        for f in iqm[parent].get("forms", {}).values():
            if isinstance(f, dict):
                aliases |= {a.lower().strip() for a in f.get("aliases", []) or []}
        alias_sets[parent] = aliases

    for left in parents:
        for right in parents:
            if left >= right:
                continue
            overlap = alias_sets[left] & alias_sets[right]
            assert not overlap, f"{left} and {right} aliases overlap: {overlap}"


def test_black_cherry_category_matches_tart(iqm):
    """Both cherry entries should sit in the same category for consistency."""
    bc = iqm["black_cherry"]
    tc = iqm.get("tart_cherry", {})
    assert bc.get("category") == tc.get("category")
    assert bc.get("category_enum") == bc.get("category")
