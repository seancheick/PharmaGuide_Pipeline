#!/usr/bin/env python3
"""
IQM coverage: Acacia Catechu (Batch 5 IQM gap fill #3).

Acacia catechu (Senegalia catechu) wood-and-bark extract is used in 5+
supplement formulations (joint-health blends like Univestin/5-Loxin
combinations). It was previously skipped as `recognized_non_scorable`
because the botanical identity lived in `botanical_ingredients.json`
(`cutch_tree`, `khadeer` — both reference the same plant) but no IQM
scoring entry existed.

Identifiers verified via:
- FDA GSRS: UNII TJ6XA84OQF ("SENEGALIA CATECHU WHOLE"), RxCUI 1650239
- UMLS: CUI C0949533 (Senegalia catechu / Acacia catechu — MTH consolidated)
"""

import json
import logging
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
logging.disable(logging.CRITICAL)


@pytest.fixture(scope="module")
def iqm():
    return json.load(open(os.path.join(
        os.path.dirname(__file__), "..", "data", "ingredient_quality_map.json"
    )))


def test_acacia_catechu_iqm_entry_exists(iqm):
    assert "acacia_catechu" in iqm


def test_acacia_catechu_identifiers(iqm):
    e = iqm["acacia_catechu"]
    assert e.get("cui") == "C0949533", f"Expected CUI C0949533, got {e.get('cui')}"
    assert e.get("external_ids", {}).get("unii") == "TJ6XA84OQF"


def test_acacia_catechu_score_formula(iqm):
    e = iqm["acacia_catechu"]
    for form_key, form in e.get("forms", {}).items():
        if not isinstance(form, dict):
            continue
        bio = form.get("bio_score")
        score = form.get("score")
        natural = bool(form.get("natural", False))
        if isinstance(bio, (int, float)) and isinstance(score, (int, float)):
            expected = bio + (3 if natural else 0)
            assert score == expected, f"{form_key}: score formula violated"


def test_acacia_catechu_aliases_cover_label_form(iqm):
    e = iqm["acacia_catechu"]
    all_aliases = set()
    for f in e.get("forms", {}).values():
        if isinstance(f, dict):
            all_aliases |= {a.lower().strip() for a in f.get("aliases", []) or []}
    needed = {
        "acacia catechu",
        "acacia catechu wood & bark extract",
        "senegalia catechu",
    }
    missing = needed - all_aliases
    assert not missing, f"Missing aliases: {missing}"


def test_acacia_catechu_category_botanical(iqm):
    e = iqm["acacia_catechu"]
    cat = e.get("category", "").lower()
    assert cat in {"herbs", "bark", "botanical"}
    assert e.get("category_enum") == cat


def test_acacia_catechu_does_not_duplicate_botanical_recognition():
    """Pre-existing botanical_ingredients.json:cutch_tree and :khadeer
    must remain — they're recognition records. The new IQM entry adds
    scoring without removing recognition."""
    bot = json.load(open(os.path.join(
        os.path.dirname(__file__), "..", "data", "botanical_ingredients.json"
    )))
    ids = {b.get("id") for b in bot.get("botanical_ingredients", []) if isinstance(b, dict)}
    assert "cutch_tree" in ids, "Existing cutch_tree recognition must remain"
    assert "khadeer" in ids, "Existing khadeer recognition must remain"
