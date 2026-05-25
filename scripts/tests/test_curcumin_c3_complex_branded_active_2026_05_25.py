#!/usr/bin/env python3
"""Sabinsa Curcumin C3 Complex must NOT be classified as a structural blend
total when the only blend signal is the generic substring "complex".

Bug discovered 2026-05-25 by Wave 6.Z research (orchestrator) on
Sports_Research DSLD 317006 "Turmeric Curcumin C3 Complex":

Raw DSLD shape:
  Row 0  Curcumin C3 Complex      500 mg   category='non-nutrient/non-botanical'
                                            ingredientGroup='Curcumin'
    └── Curcuminoids                475 mg   (95% standardization disclosure)
  Row 1  Bioperine                  5 mg

The cleaner's `_is_dsld_active_blend_total_row` classifier evaluates a row
as a blend total when ANY of three signals fires:
  (a) raw_category == 'blend'                              [STRONG]
  (b) 'blend' in ingredientGroup                            [STRONG]
  (c) `_is_proprietary_blend_name(name)`                    [WEAK — substring]

For "Curcumin C3 Complex" only signal (c) fires, via substring match on
"complex" in PROPRIETARY_BLEND_INDICATORS. The cleaner then stamps:
  cleaner_row_role        = 'blend_header_total'
  score_eligible_by_cleaner = False
  hierarchyType           = 'blend_header'

…which the enricher's `_cleaner_skip_reason` honors with
SKIP_REASON_BLEND_HEADER_WITH_WEIGHT, before the IQM-known-therapeutic
override at line 4133 of `_should_skip_from_scoring` can rescue it.

End result: 0 scorable ingredients. Verdict = NOT_SCORED. The product silently
disappears from quality assessment despite Sabinsa Curcumin C3 Complex being
the most widely sold standardized curcumin extract on the market and
recognized as IQM form `curcumin c3 complex with bioperine` (bio_score=7).

The same shape applies to 10 IQM forms ending in "complex" (polysaccharide-
iron complex, crominex 3+ chromium complex, plant-based enzyme complex, etc.)
— all real branded single-active ingredients that the weak substring match
would silently demote.

FIX CONTRACT
============

When the ONLY blend signal is the weak `_is_proprietary_blend_name` substring
match (no `raw_category == 'blend'` and no `'blend' in ingredientGroup`), and
the row's name (or standardName) matches a known IQM branded form (excluding
the generic '(unspecified)' catch-all forms), the row is a STANDARDIZED
EXTRACT, not a structural blend total. It must remain `active_scorable`.

This pin protects:
  - Sabinsa Curcumin C3 Complex (Sports_Research, Doctors Best, …)
  - Crominex 3+ Chromium Complex
  - Polysaccharide-Iron Complex (Niferex, etc.)
  - Plant-based Enzyme Complex, Citrus Bioflavonoids Complex, …

And preserves these existing contracts:
  - RC-4 Natures_Bounty Chondroitin Sulfate Complex sub-blend
    (not in IQM forms, still classified as blend total — see
    test_rc4_blend_header_total_contract.py)
  - True proprietary blends with raw_category='blend' or
    'blend' in ingredientGroup (strong signals untouched)
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any, Dict, List

import pytest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(_ROOT, "scripts"))
logging.disable(logging.CRITICAL)

try:
    from enhanced_normalizer import EnhancedDSLDNormalizer  # type: ignore
    _NORMALIZER_AVAILABLE = True
except Exception as _e:  # pragma: no cover
    EnhancedDSLDNormalizer = None  # type: ignore
    _NORMALIZER_AVAILABLE = False
    _IMPORT_ERR = _e


@pytest.fixture(scope="module")
def normalizer():
    if not _NORMALIZER_AVAILABLE:
        pytest.skip(f"EnhancedDSLDNormalizer not importable: {_IMPORT_ERR}")
    return EnhancedDSLDNormalizer()


def _qty_block(qty_mg: float, ssq: int = 1, unit: str = "Softgel(s)") -> List[Dict[str, Any]]:
    return [{
        "servingSizeOrder": 1,
        "servingSizeQuantity": ssq,
        "operator": "=",
        "quantity": qty_mg,
        "unit": "mg",
        "dailyValueTargetGroup": [{
            "name": "Adults and children 4 or more years of age",
            "operator": None,
            "percent": None,
            "footnote": "Daily Value (DV) Not Established",
        }],
        "servingSizeUnit": unit,
    }]


def _row(name: str, qty_mg: float, *, category: str = None,
         ingredient_group: str = None, nested: List[Dict[str, Any]] = None,
         ssq: int = 1) -> Dict[str, Any]:
    row = {
        "name": name,
        "order": 1,
        "ingredientId": 0,
        "uniiCode": "0",
        "quantity": _qty_block(qty_mg, ssq=ssq),
    }
    if category:
        row["category"] = category
    if ingredient_group:
        row["ingredientGroup"] = ingredient_group
    if nested is not None:
        row["nestedRows"] = nested
    return row


# Synthetic raw DSLD shape mirroring the actual file at
# /Users/seancheick/Documents/DataSetDsld/staging/brands/Sports_Research/317006.json
# (verified 2026-05-25). The 500mg parent + 475mg Curcuminoids child shape
# is the standardized 95%-curcuminoid disclosure pattern.
RAW_317006 = {
    "id": 317006,
    "fullName": "Turmeric Curcumin C3 Complex",
    "brandName": "Sports Research",
    "status": "active",
    "offMarket": 0,
    "ingredientRows": [
        _row(
            "Curcumin C3 Complex",
            qty_mg=500,
            category="non-nutrient/non-botanical",
            ingredient_group="Curcumin",
            nested=[_row("Curcuminoids", 475, ingredient_group="Curcuminoids")],
        ),
        _row(
            "Bioperine",
            qty_mg=5,
            category="botanical",
            ingredient_group="Black Pepper",
            nested=[_row("Piperine", 4.75, ingredient_group="Piperine")],
        ),
    ],
    "otherIngredients": {"ingredients": []},
}


def _walk_rows(d, found):
    if isinstance(d, dict):
        if isinstance(d.get("name"), str):
            found.append(d)
        for v in d.values():
            _walk_rows(v, found)
    elif isinstance(d, list):
        for v in d:
            _walk_rows(v, found)


def _find_curcumin_c3_row(rows):
    for r in rows:
        nm = (r.get("name") or "").lower()
        if "curcumin c3 complex" in nm and "curcuminoids" not in nm:
            return r
        rst = (r.get("raw_source_text") or "").lower()
        if "curcumin c3 complex" in rst and "curcuminoids" not in rst:
            return r
    return None


# ---------------------------------------------------------------------------
# Unit tests: _is_dsld_active_blend_total_row direct classifier behavior
# ---------------------------------------------------------------------------

def test_curcumin_c3_complex_is_not_structural_blend_total(normalizer):
    """The Sabinsa Curcumin C3 Complex row matches the WEAK
    `_is_proprietary_blend_name` substring ("complex") but no STRONG blend
    signal (no category='blend', no 'blend' in ingredientGroup). The classifier
    must not treat this as a structural blend total."""
    ing = _row(
        "Curcumin C3 Complex",
        qty_mg=500,
        category="non-nutrient/non-botanical",
        ingredient_group="Curcumin",
        nested=[_row("Curcuminoids", 475)],
    )
    is_blend_total = normalizer._is_dsld_active_blend_total_row(ing)
    assert is_blend_total is False, (
        "Curcumin C3 Complex (IQM-known Sabinsa branded form) must NOT be "
        "classified as blend_total. Only the weak _is_proprietary_blend_name "
        "substring fires here; the row name matches an IQM branded form, so "
        "it is a standardized extract, not a structural blend header."
    )


def test_polysaccharide_iron_complex_is_not_structural_blend_total(normalizer):
    """polysaccharide-iron complex is an IQM-known iron form (Niferex shape)
    — same protection as Curcumin C3 Complex."""
    ing = _row(
        "Polysaccharide-Iron Complex",
        qty_mg=150,
        category="mineral",
        ingredient_group="Iron",
    )
    assert normalizer._is_dsld_active_blend_total_row(ing) is False


def test_crominex_3_plus_chromium_complex_is_not_structural_blend_total(normalizer):
    """Crominex 3+ Chromium Complex is an IQM-known chromium form."""
    ing = _row(
        "Crominex 3+ Chromium Complex",
        qty_mg=200,
        category="mineral",
        ingredient_group="Chromium",
    )
    assert normalizer._is_dsld_active_blend_total_row(ing) is False


# ---------------------------------------------------------------------------
# Negative regressions: real blend totals MUST still be classified
# ---------------------------------------------------------------------------

def test_chondroitin_sulfate_complex_still_blend_total_when_no_iqm_form(normalizer):
    """RC-4 contract preservation. 'Chondroitin Sulfate Complex' (Natures_Bounty
    Flex-A-Min) is NOT in IQM forms — it remains a sub-blend marketing name
    that the weak signal correctly catches."""
    ing = _row(
        "Chondroitin Sulfate Complex",
        qty_mg=1139,
    )
    # Without category/ingredient_group, only the weak signal fires. Since
    # this name is NOT in IQM forms, the row must STILL be classified as
    # blend_total to preserve the RC-4 safety boundary.
    assert normalizer._is_dsld_active_blend_total_row(ing) is True


def test_proprietary_blend_with_blend_category_still_blend_total(normalizer):
    """Strong signal: raw_category='blend'. Must be blend_total regardless
    of IQM form lookup."""
    ing = _row(
        "Flex-a-min Joint Flex Proprietary Blend",
        qty_mg=1239,
        category="blend",
        ingredient_group="Blend (Combination)",
    )
    assert normalizer._is_dsld_active_blend_total_row(ing) is True


def test_ingredient_group_blend_still_blend_total(normalizer):
    """Strong signal: 'blend' in ingredientGroup."""
    ing = _row(
        "Energy Boost Proprietary Blend",
        qty_mg=500,
        ingredient_group="Proprietary Blend",
    )
    assert normalizer._is_dsld_active_blend_total_row(ing) is True


# ---------------------------------------------------------------------------
# End-to-end: full normalize_product on synthetic 317006 raw shape
# ---------------------------------------------------------------------------

def test_normalized_317006_curcumin_row_is_score_eligible(normalizer):
    """End-to-end through normalize_product: the cleaner must emit
    cleaner_row_role='active_scorable' and score_eligible_by_cleaner=True for
    the Curcumin C3 Complex row, resolved to canonical_id='curcumin' via the
    IQM. The downstream enricher then matches form 'curcumin c3 complex'
    (bio_score=6 unpaired, or upgrades to bio_score=7 if downstream
    bioperine-pairing logic is wired)."""
    normalized = normalizer.normalize_product(RAW_317006)
    rows = []
    _walk_rows(normalized, rows)
    curcumin_row = _find_curcumin_c3_row(rows)
    assert curcumin_row is not None, (
        f"Curcumin C3 Complex row not found in normalized output. "
        f"Sample names: {[r.get('name') for r in rows[:10]]}"
    )
    assert curcumin_row.get("cleaner_row_role") == "active_scorable", (
        f"Curcumin C3 Complex must be cleaner_row_role='active_scorable'. "
        f"Got: {curcumin_row.get('cleaner_row_role')!r}"
    )
    assert curcumin_row.get("score_eligible_by_cleaner") is True, (
        f"Curcumin C3 Complex must have score_eligible_by_cleaner=True. "
        f"Got: {curcumin_row.get('score_eligible_by_cleaner')!r}"
    )
    assert curcumin_row.get("canonical_id") == "curcumin", (
        f"Curcumin C3 Complex must resolve canonical_id='curcumin'. "
        f"Got: {curcumin_row.get('canonical_id')!r}"
    )
    assert curcumin_row.get("canonical_source_db") == "ingredient_quality_map", (
        f"Curcumin C3 Complex must resolve via ingredient_quality_map. "
        f"Got: {curcumin_row.get('canonical_source_db')!r}"
    )
