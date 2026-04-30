#!/usr/bin/env python3
"""
IQM coverage: Phosphatidylcholine (Batch 5 IQM gap fill #4).

Phosphatidylcholine (PC) — the most abundant cell-membrane phospholipid and
the major lecithin component — was missing from IQM despite three sibling
phospholipids being present (phosphatidylserine, phosphatidylinositol,
phosphatidylethanolamine). 5+ supplement products use PC as a key active
(brain/liver/choline support) and were skipped as `recognized_non_scorable`.

Identifiers verified via:
- FDA GSRS (soybean form): UNII 1T6N4D9YV6, CAS 97281-47-5, RxCUI 2109751
- UMLS: CUI C1959616 (Phosphatidylcholines, MTH)
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


def test_phosphatidylcholine_iqm_entry_exists(iqm):
    assert "phosphatidylcholine" in iqm


def test_phosphatidylcholine_identifiers(iqm):
    e = iqm["phosphatidylcholine"]
    assert e.get("cui") == "C1959616"
    assert e.get("external_ids", {}).get("unii") == "1T6N4D9YV6"


def test_phosphatidylcholine_score_formula(iqm):
    e = iqm["phosphatidylcholine"]
    for form_key, form in e.get("forms", {}).items():
        if not isinstance(form, dict):
            continue
        bio = form.get("bio_score")
        score = form.get("score")
        natural = bool(form.get("natural", False))
        if isinstance(bio, (int, float)) and isinstance(score, (int, float)):
            expected = bio + (3 if natural else 0)
            assert score == expected, f"{form_key}: schema rule violated"


def test_phosphatidylcholine_aliases_cover_supplement_forms(iqm):
    e = iqm["phosphatidylcholine"]
    all_aliases = set()
    for f in e.get("forms", {}).values():
        if isinstance(f, dict):
            all_aliases |= {a.lower().strip() for a in f.get("aliases", []) or []}
    needed = {
        "phosphatidylcholine",
        "soy phosphatidylcholine",
        "sunflower phosphatidylcholine",
        "phosphatidyl choline complex",
    }
    missing = needed - all_aliases
    assert not missing, f"Missing aliases: {missing}"
    # "phosphatidyl choline" (with space) intentionally NOT claimed by this
    # entry — it is owned by the simple `choline` IQM entry as a label-
    # rendering alias for "Choline (as Phosphatidyl Choline)" disclosures.
    # Cross-ingredient alias collision must be avoided.
    assert "phosphatidyl choline" not in all_aliases


def test_phosphatidylcholine_category_matches_siblings(iqm):
    """Sibling phospholipids use category=fatty_acids; PC must match."""
    e = iqm["phosphatidylcholine"]
    sibling_cats = {iqm[k].get("category") for k in
                    ("phosphatidylserine", "phosphatidylinositol",
                     "phosphatidylethanolamine")}
    assert e.get("category") in sibling_cats, (
        f"PC category {e.get('category')!r} should match sibling phospholipids: "
        f"{sibling_cats}"
    )
    assert e.get("category_enum") == e.get("category")


def test_phosphatidylcholine_score_in_sibling_range(iqm):
    """PC bioavailability is well-established. Score should sit between
    phosphatidylinositol (bio=8, score=11 — limited evidence) and
    phosphatidylserine (bio=12, score=15 — best-evidenced)."""
    e = iqm["phosphatidylcholine"]
    found_in_range = False
    for form in e.get("forms", {}).values():
        if not isinstance(form, dict):
            continue
        bio = form.get("bio_score")
        if isinstance(bio, (int, float)) and 9 <= bio <= 13:
            found_in_range = True
            break
    assert found_in_range, "PC bio_score must sit in 9-13 range"
