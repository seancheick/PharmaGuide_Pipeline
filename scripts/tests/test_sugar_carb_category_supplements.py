"""Bucket-1 recovery — sugar-class / complex-carbohydrate supplements
silently filtered (2026-05-13).

Sprint E1.2.5 follow-up to ``_is_nutrition_fact``. The D1.3 + E1.6
sugar/fat/carb branch used to filter every row whose DSLD category was
``sugar`` / ``complex carbohydrate`` UNLESS the ingredientGroup matched
the curated fat-class active allowlist. That predicate dropped real
single-active sugar-supplements: D-Mannose, D-Ribose, BiMuno B-GOS
Galactooligosaccharides, and similar. Those products surfaced
downstream as ``verdict='NOT_SCORED'`` because the scorer had nothing
to score against.

The fix uses the curated nutrition-facts NAME list as the
disambiguator: when the row's preprocessed name is NOT in
``EXCLUDED_NUTRITION_FACTS`` (and the ingredientGroup is not a known
fat-class active either), trust DSLD's row and let downstream mapping
resolve. This:

* Recovers sugar-class supplements (D-Mannose, D-Ribose, GOS) without a
  separate ``_SUGAR_CATEGORY_REAL_ACTIVES`` allowlist.
* Keeps panel rows filtered — names like ``Total Carbohydrates``,
  ``Total Sugars``, ``Sugars``, ``Total Fat``, ``Cholesterol``,
  ``Calories``, ``Saturated Fat`` are all in EXCLUDED_NUTRITION_FACTS
  and continue to filter.
* Symmetric to the gram-unit branch's narrowing in the same sprint.

Coverage:
* DSLD 219734 Pure Encapsulations D-Mannose — cat='sugar', 0.9g
* DSLD 270400 Nutricost D-Ribose 5g Unflavored — cat='sugar', 5g
* DSLD 304444 GNC GOS — cat='complex carbohydrate', 1.37g
* DSLD 27191 GNC Phytosterols 800 MG — cat='fat', mg dose
* Negative-control: bare ``Total Carbohydrates`` 5g cat='sugar' must
  still filter.
"""
from __future__ import annotations

import os
import sys
from typing import Any, Dict, List

import pytest

_SCRIPTS = os.path.join(os.path.dirname(__file__), "..")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from enhanced_normalizer import EnhancedDSLDNormalizer  # noqa: E402


@pytest.fixture(scope="module")
def normalizer() -> EnhancedDSLDNormalizer:
    return EnhancedDSLDNormalizer()


def _names(items) -> List[str]:
    return [i.get("name") for i in items or []]


def _make_product(pid: int, name: str, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "id": pid,
        "fullName": name,
        "brandName": "TestCo",
        "ingredientRows": rows,
        "otheringredients": {"text": None, "ingredients": []},
    }


def test_d_mannose_sugar_category_kept_as_active(normalizer):
    """D-Mannose 2g (DSLD category='sugar') is a real single-active
    supplement, not a Nutrition-Facts panel row. The D1.3 branch's
    name-based exemption must keep it."""
    out = normalizer.normalize_product(_make_product(
        999101, "D-Mannose 2g",
        [{"name": "D-Mannose", "category": "sugar",
          "ingredientGroup": "D-Mannose",
          "quantity": [{"operator": "=", "quantity": 2, "unit": "Gram(s)"}]}],
    ))
    assert "D-Mannose" in _names(out.get("activeIngredients")), (
        f"D-Mannose must survive cleaning; got {_names(out.get('activeIngredients'))}"
    )


def test_d_ribose_sugar_category_kept_as_active(normalizer):
    """D-Ribose 5g (DSLD category='sugar') is a real sports-nutrition
    supplement. Must survive."""
    out = normalizer.normalize_product(_make_product(
        999102, "D-Ribose 5g",
        [{"name": "D-Ribose", "category": "sugar",
          "ingredientGroup": "D-Ribose",
          "quantity": [{"operator": "=", "quantity": 5, "unit": "Gram(s)"}]}],
    ))
    assert "D-Ribose" in _names(out.get("activeIngredients"))


def test_galactooligosaccharides_complex_carb_kept(normalizer):
    """GOS / B-GOS / inulin family — DSLD category='complex
    carbohydrate'. Real prebiotic supplements. Must survive."""
    out = normalizer.normalize_product(_make_product(
        999103, "GOS Prebiotic",
        [{"name": "BiMuno B-GOS Galactooligosaccharides",
          "category": "complex carbohydrate", "ingredientGroup": None,
          "quantity": [{"operator": "=", "quantity": 1.37, "unit": "Gram(s)"}]}],
    ))
    assert "BiMuno B-GOS Galactooligosaccharides" in _names(out.get("activeIngredients"))


def test_phytosterols_fat_category_with_mg_unit_kept(normalizer):
    """Pure Encapsulations Beta-Sitosterol / GNC Phytosterols 800mg —
    cat='fat', mg unit. Real fat-soluble actives. Must survive."""
    out = normalizer.normalize_product(_make_product(
        999104, "Phytosterols 800mg",
        [{"name": "Phytosterols", "category": "fat",
          "ingredientGroup": "Phytosterols",
          "quantity": [{"operator": "=", "quantity": 800, "unit": "mg"}]}],
    ))
    assert "Phytosterols" in _names(out.get("activeIngredients"))


def test_total_carbohydrates_still_filtered(normalizer):
    """Negative-control: bare ``Total Carbohydrates`` 5g cat='sugar' is
    a Nutrition-Facts panel row and MUST still be filtered after the
    sprint E1.2.5 follow-up loosening."""
    out = normalizer.normalize_product(_make_product(
        999105, "Mixed panel test",
        [{"name": "Total Carbohydrates", "category": "sugar",
          "quantity": [{"operator": "=", "quantity": 5, "unit": "Gram(s)"}]},
         {"name": "D-Mannose", "category": "sugar",
          "ingredientGroup": "D-Mannose",
          "quantity": [{"operator": "=", "quantity": 2, "unit": "Gram(s)"}]}],
    ))
    active_names = _names(out.get("activeIngredients"))
    assert "Total Carbohydrates" not in active_names, (
        f"Total Carbohydrates is a panel row and must filter; got {active_names}"
    )
    assert "D-Mannose" in active_names, (
        f"D-Mannose must survive alongside panel filtering; got {active_names}"
    )


def test_bare_sugars_still_filtered(normalizer):
    """Bare ``Sugars`` and ``Total Sugars`` are panel rows. Must filter."""
    out = normalizer.normalize_product(_make_product(
        999106, "Panel-only test",
        [{"name": "Sugars", "category": "sugar",
          "quantity": [{"operator": "=", "quantity": 2, "unit": "Gram(s)"}]},
         {"name": "Total Sugars", "category": "sugar",
          "quantity": [{"operator": "=", "quantity": 2, "unit": "Gram(s)"}]}],
    ))
    active_names = _names(out.get("activeIngredients"))
    assert "Sugars" not in active_names
    assert "Total Sugars" not in active_names
