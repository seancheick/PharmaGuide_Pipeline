#!/usr/bin/env python3
"""
IQM coverage: Phellodendron Amurense (Batch 5 IQM gap fill #2).

Phellodendron amurense bark (Huang Bai) is a TCM botanical containing
berberine, jatrorrhizine, and magnoflorine. Used in 9 supplement products
that previously fell through to `recognized_non_scorable` because
botanical_ingredients.json only had the dual-herb blend entry
(`magnolia_phellodendron_blend`), not the single botanical.

Identifiers verified via:
- FDA GSRS: UNII PBG27B754G ("PHELLODENDRON AMURENSE BARK")
- RxNorm: RxCUI 1307947
- UMLS: CUI C1027031 (Phellodendron amurense species)
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


def test_phellodendron_iqm_entry_exists(iqm):
    assert "phellodendron_amurense" in iqm or "phellodendron" in iqm


def test_phellodendron_iqm_identifiers(iqm):
    e = iqm.get("phellodendron_amurense") or iqm.get("phellodendron")
    assert e.get("cui") == "C1027031", f"Expected CUI C1027031, got {e.get('cui')}"
    assert e.get("external_ids", {}).get("unii") == "PBG27B754G"


def test_phellodendron_has_scorable_form(iqm):
    e = iqm.get("phellodendron_amurense") or iqm.get("phellodendron")
    forms = e.get("forms", {})
    assert forms, "Must have at least one form"
    has_score = any(
        isinstance(f, dict)
        and isinstance(f.get("score"), (int, float))
        and isinstance(f.get("bio_score"), (int, float))
        for f in forms.values()
    )
    assert has_score


def test_phellodendron_score_formula_consistent(iqm):
    """Schema rule: score = bio_score + (3 if natural else 0)."""
    e = iqm.get("phellodendron_amurense") or iqm.get("phellodendron")
    for form_key, form in e.get("forms", {}).items():
        if not isinstance(form, dict):
            continue
        bio = form.get("bio_score")
        score = form.get("score")
        natural = bool(form.get("natural", False))
        if isinstance(bio, (int, float)) and isinstance(score, (int, float)):
            expected = bio + (3 if natural else 0)
            assert score == expected, (
                f"{form_key}: score={score} != bio_score({bio}) + natural({natural})*3"
            )


def test_phellodendron_aliases_cover_label_renderings(iqm):
    e = iqm.get("phellodendron_amurense") or iqm.get("phellodendron")
    all_aliases = set()
    for f in e.get("forms", {}).values():
        if isinstance(f, dict):
            all_aliases |= {a.lower().strip() for a in f.get("aliases", []) or []}
    needed = {
        "phellodendron",
        "phellodendron amurense",
        "phellodendron amurense bark extract",
        "huang bai",
    }
    missing = needed - all_aliases
    assert not missing, f"Missing aliases: {missing}"


def test_phellodendron_category_botanical(iqm):
    e = iqm.get("phellodendron_amurense") or iqm.get("phellodendron")
    cat = e.get("category", "").lower()
    # Acceptable categories per existing IQM convention for herbs:
    # ashwagandha/rhodiola/astragalus/ginseng/holy_basil/curcumin all use "herbs"
    assert cat in {"herbs", "botanical", "bark"}, (
        f"Phellodendron should be a botanical/herb category, got {cat!r}"
    )
    # category_enum must match category (schema rule)
    assert e.get("category_enum") == cat


def test_phellodendron_does_not_duplicate_blend_entry():
    """The single-botanical IQM entry must not collide with the existing
    magnolia_phellodendron_blend in botanical_ingredients.json."""
    bot = json.load(open(os.path.join(
        os.path.dirname(__file__), "..", "data", "botanical_ingredients.json"
    )))
    iqm_data = json.load(open(os.path.join(
        os.path.dirname(__file__), "..", "data", "ingredient_quality_map.json"
    )))
    blend = next(
        (b for b in bot.get("botanical_ingredients", [])
         if b.get("id") == "magnolia_phellodendron_blend"),
        None,
    )
    assert blend, "Pre-existing magnolia_phellodendron_blend must remain"
    # The single-botanical IQM entry's aliases must not include
    # the blend-specific names
    e = iqm_data.get("phellodendron_amurense") or iqm_data.get("phellodendron")
    if e:
        all_aliases = set()
        for f in e.get("forms", {}).values():
            if isinstance(f, dict):
                all_aliases |= {a.lower().strip() for a in f.get("aliases", []) or []}
        forbidden = {
            "magnolia officinalis and phellodendron amurense",
            "relora",  # blend-specific brand
        }
        collision = forbidden & all_aliases
        assert not collision, (
            f"IQM phellodendron entry must not claim blend-specific aliases: {collision}"
        )
