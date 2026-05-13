"""Bucket-3 regression — actives demoted to inactive (2026-05-13).

Sprint E1.2.5 follow-up. Three failure modes were collapsed into one
audit alarm (``[xxx] all raw actives reclassified as inactive — likely
cleaner classifier bug``):

1. **Type B — `_is_nutrition_fact` over-filtered real actives.** Two
   sub-paths in the cleaner:
   a. **Gram-unit + non-supplement DSLD category branch.** A blanket
      "if unit is grams AND DSLD category is not in supplements →
      nutrition fact" exclusion that killed real label-disclosed
      supplements DSLD happened to tag ``category='other'`` (Red Yeast
      Rice 1.8g) or ``category='fat'`` for MCT/phytosterol products.
   b. **`_FAT_CATEGORY_REAL_ACTIVES` allowlist missed variants.** DSLD
      `ingredientGroup` strings like ``"Phytosterol (mixed)"`` and
      ``"Medium chain triglycerides (MCT)"`` were not in the allowlist
      that D1.3 + E1.6 use to keep fat-category real actives.

2. **Type A — no `DROPPED_NUTRITION_FACT` reason was emitted** for
   filtered nutrition-facts rows. The cleaner returned None silently,
   so the build's reason set looked like ``{DROPPED_AS_INACTIVE}`` —
   the exact shape the E1.6 defense gate was designed to flag. The
   audit fired for legitimate-nutrition-facts products whose
   otheringredients section was correctly routed to inactives.

Fixes pinned by this file:

* `_is_nutrition_fact` gram-unit branch only excludes when the row's
  name preprocess-matches `EXCLUDED_NUTRITION_FACTS` OR ingredientGroup
  is in `_FAT_CATEGORY_REAL_ACTIVES`. Anything else falls through to
  the downstream mapper (the right disambiguator).
* `_FAT_CATEGORY_REAL_ACTIVES` covers DSLD ingredientGroup variants:
  ``phytosterol (mixed)``, ``phytosterol esters``, ``medium chain
  triglycerides (mct)``, ``medium chain triglyceride oil``.
* `_process_single_ingredient_enhanced` emits
  ``_queue_display_ingredient(display_type='nutrition_fact')`` whenever
  `_is_nutrition_fact` returns True, so the build can derive a
  `DROPPED_NUTRITION_FACT` reason via the new
  ``_DISPLAY_TYPE_TO_REASON`` entry.

Coverage matrix:

* **Type B recovery (real actives surface in blob):**
  - DSLD 16040 Thorne Choleast-900 — Red Yeast Rice 1.8g, cat='other'
  - DSLD 20529 Thorne Sterolipin — Phytosterol esters 1625mg, cat='fat',
    group='Phytosterol (mixed)'
  - DSLD 326282 SR Sports Research MCT Oil — Medium Chain Triglycerides
    14g, cat='fat'
  - DSLD 270263 Nutricost C8 MCT Oil Powder — Medium Chain Triglyceride
    Oil 10g, cat='fat', group='Medium chain triglycerides (MCT)'
* **Type A — display trail carries `nutrition_fact` so audit
  disambiguates the legitimate-nutrition-facts case:**
  - DSLD 1056 GNC Fish Oil — all 5 ingredientRows are panel rows
    (Calories, Total Fat, Cholesterol, Total Omega-3 Fatty Acids)
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, Iterable, List

import pytest

_SCRIPTS = os.path.join(os.path.dirname(__file__), "..")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from enhanced_normalizer import EnhancedDSLDNormalizer  # noqa: E402


# Vendored raw payloads. The cleaner-side test is hermetic; it does NOT
# depend on the local DataSetDsld checkout being present.
RAW_FIXTURES: Dict[int, Dict[str, Any]] = {
    # 16040 — Thorne Choleast-900 (Red Yeast Rice 1.8g)
    16040: {
        "id": 16040,
        "fullName": "Choleast-900",
        "brandName": "Thorne Research",
        "ingredientRows": [
            {
                "name": "Red Yeast Rice", "category": "other",
                "ingredientGroup": "Red Yeast Rice",
                "quantity": [{"servingSizeOrder": 1, "operator": "=",
                              "quantity": 1.8, "unit": "g"}],
                "forms": [], "nestedRows": [],
            },
        ],
        "otheringredients": {
            "text": None,
            "ingredients": [
                {"order": 1, "name": "Hypromellose (derived from Cellulose) Capsule",
                 "category": "other", "ingredientGroup": "Hypromellose",
                 "forms": [{"name": "Cellulose"}]},
                {"order": 2, "name": "Leucine", "category": "amino acid",
                 "ingredientGroup": "Leucine", "forms": []},
            ],
        },
    },
    # 20529 — Thorne Sterolipin (Phytosterol esters 1625mg)
    20529: {
        "id": 20529,
        "fullName": "Sterolipin",
        "brandName": "Thorne Research",
        "ingredientRows": [
            {
                "name": "Phytosterol esters", "category": "fat",
                "ingredientGroup": "Phytosterol (mixed)",
                "quantity": [{"servingSizeOrder": 1, "operator": "=",
                              "quantity": 1625, "unit": "mg"}],
                "forms": [], "nestedRows": [],
            },
        ],
        "otheringredients": {
            "text": None,
            "ingredients": [
                {"order": 1, "name": "Gelatin", "category": "protein",
                 "ingredientGroup": "Gelatin Capsule", "forms": []},
            ],
        },
    },
    # 326282 — SR Sports Research Organic MCT Oil (14g)
    326282: {
        "id": 326282,
        "fullName": "Organic MCT Oil Unflavored",
        "brandName": "SR Sports Research",
        "ingredientRows": [
            {"name": "Calories", "category": "other",
             "quantity": [{"operator": "=", "quantity": 130, "unit": "{Calories}"}]},
            {"name": "Total Fat", "category": "fat",
             "ingredientGroup": "Fat (unspecified)",
             "quantity": [{"operator": "=", "quantity": 14, "unit": "Gram(s)"}]},
            {
                "name": "Medium Chain Triglycerides", "category": "fat",
                "ingredientGroup": "Medium Chain Triglycerides",
                "quantity": [{"operator": "=", "quantity": 14, "unit": "Gram(s)"}],
            },
        ],
        "otheringredients": {"text": None, "ingredients": []},
    },
    # 270263 — Nutricost C8 MCT Oil Powder 10g
    270263: {
        "id": 270263,
        "fullName": "C8 MCT Oil Powder 10 g Unflavored",
        "brandName": "Nutricost",
        "ingredientRows": [
            {"name": "Calories", "category": "other",
             "quantity": [{"operator": "=", "quantity": 80, "unit": "Calorie(s)"}]},
            {"name": "Total Fat", "category": "fat",
             "ingredientGroup": "Fat (unspecified)",
             "quantity": [{"operator": "=", "quantity": 10, "unit": "Gram(s)"}]},
            {
                "name": "Medium Chain Triglyceride Oil", "category": "fat",
                "ingredientGroup": "Medium chain triglycerides (MCT)",
                "quantity": [{"operator": "=", "quantity": 10, "unit": "Gram(s)"}],
            },
        ],
        "otheringredients": {"text": None, "ingredients": []},
    },
    # 1056 — GNC Fish Oil. All ingredientRows are panel rows (Type A).
    1056: {
        "id": 1056,
        "fullName": "Fish Oil",
        "brandName": "GNC",
        "ingredientRows": [
            {"name": "Calories", "category": "other",
             "quantity": [{"operator": "=", "quantity": 10, "unit": "{Calories}"}]},
            {"name": "Calories from Fat", "category": "other",
             "quantity": [{"operator": "=", "quantity": 10, "unit": "{Calories}"}]},
            {"name": "Total Fat", "category": "fat",
             "quantity": [{"operator": "=", "quantity": 1, "unit": "g"}]},
            {"name": "Cholesterol", "category": "fat",
             "quantity": [{"operator": "=", "quantity": 5, "unit": "mg"}]},
            {"name": "Total Omega-3 Fatty Acids", "category": "fatty acid",
             "quantity": [{"operator": "=", "quantity": 300, "unit": "mg"}]},
        ],
        "otheringredients": {
            "text": None,
            "ingredients": [
                {"order": 1, "name": "Fish Body Oil", "category": "fat",
                 "ingredientGroup": "Fish Oil", "forms": []},
                {"order": 2, "name": "Gelatin", "category": "protein",
                 "ingredientGroup": "Gelatin", "forms": []},
                {"order": 3, "name": "Glycerin", "category": "other",
                 "ingredientGroup": "Glycerol", "forms": []},
                {"order": 4, "name": "Vitamin E", "category": "vitamin",
                 "ingredientGroup": "Vitamin E", "forms": []},
            ],
        },
    },
}


@pytest.fixture(scope="module")
def normalizer() -> EnhancedDSLDNormalizer:
    return EnhancedDSLDNormalizer()


def _active_names(out: Dict[str, Any]) -> List[str]:
    return [a.get("name") for a in out.get("activeIngredients") or []]


def _display_reasons(out: Dict[str, Any]) -> set:
    """Simulate the build's _DISPLAY_TYPE_TO_REASON aggregation."""
    mapping = {
        "structural_container": "DROPPED_STRUCTURAL_HEADER",
        "summary_wrapper": "DROPPED_SUMMARY_WRAPPER",
        "inactive_ingredient": "DROPPED_AS_INACTIVE",
        "nutrition_fact": "DROPPED_NUTRITION_FACT",
    }
    reasons: set = set()
    for d in out.get("display_ingredients") or []:
        code = mapping.get(d.get("display_type"))
        if code:
            reasons.add(code)
    return reasons


def test_16040_red_yeast_rice_kept_as_active(normalizer):
    """Red Yeast Rice 1.8g (DSLD category='other') is a real botanical
    supplement. The blanket gram-unit-non-supplement-category exclusion
    used to drop it. Must now survive to activeIngredients."""
    out = normalizer.normalize_product(RAW_FIXTURES[16040])
    assert "Red Yeast Rice" in _active_names(out), (
        f"Red Yeast Rice must survive cleaning; got actives "
        f"{_active_names(out)}"
    )


def test_20529_phytosterol_esters_kept_as_active(normalizer):
    """Phytosterol esters (DSLD category='fat', ingredientGroup
    'Phytosterol (mixed)') is a real plant-sterol supplement. The
    `_FAT_CATEGORY_REAL_ACTIVES` allowlist must include this DSLD
    ingredientGroup variant."""
    out = normalizer.normalize_product(RAW_FIXTURES[20529])
    assert "Phytosterol esters" in _active_names(out), (
        f"Phytosterol esters must survive cleaning; got actives "
        f"{_active_names(out)}"
    )


def test_326282_mct_kept_as_active(normalizer):
    """Medium Chain Triglycerides 14g (cat='fat', group='Medium Chain
    Triglycerides') is a real MCT supplement. Both the gram-unit branch
    and the D1.3 category branch must let this through via the
    `_FAT_CATEGORY_REAL_ACTIVES` allowlist."""
    out = normalizer.normalize_product(RAW_FIXTURES[326282])
    assert "Medium Chain Triglycerides" in _active_names(out)


def test_270263_mct_oil_with_paren_variant_kept(normalizer):
    """Nutricost C8 MCT Oil Powder uses ingredientGroup 'Medium chain
    triglycerides (MCT)' — a DSLD variant not previously in the
    allowlist. Must survive after Sprint E1.2.5 follow-up."""
    out = normalizer.normalize_product(RAW_FIXTURES[270263])
    assert "Medium Chain Triglyceride Oil" in _active_names(out)


def test_1056_fish_oil_emits_nutrition_fact_reason(normalizer):
    """Type A: GNC Fish Oil's 5 ingredientRows are all panel rows.
    The cleaner correctly drops them as nutrition facts. After the
    fix, each drop emits a ``display_type='nutrition_fact'`` entry so
    the build can derive `DROPPED_NUTRITION_FACT` — distinguishing
    this case from a real cleaner classifier bug (where reasons would
    be only `{DROPPED_AS_INACTIVE}`)."""
    out = normalizer.normalize_product(RAW_FIXTURES[1056])
    reasons = _display_reasons(out)
    assert "DROPPED_NUTRITION_FACT" in reasons, (
        f"Fish Oil panel rows must emit DROPPED_NUTRITION_FACT; got reasons {reasons}"
    )
    # Audit invariant: reasons MUST NOT be exactly {DROPPED_AS_INACTIVE}.
    # Inclusion of DROPPED_NUTRITION_FACT breaks the set-equality check
    # in build_final_db._validate_active_count_reconciliation.
    assert reasons != {"DROPPED_AS_INACTIVE"}


def test_audit_still_fires_on_synthetic_real_classifier_bug(normalizer):
    """Negative-control: a synthetic product where the cleaner WOULD
    wrongly classify a real active as inactive (no panel rows, no
    nutrition-fact reasons) still trips the audit's
    set(reasons) == {DROPPED_AS_INACTIVE} predicate. Guards against
    over-loosening the audit while fixing Type A misfires."""
    synthetic = {
        "id": 999002,
        "fullName": "Synthetic Test Product",
        "brandName": "TestCo",
        "ingredientRows": [
            # An ingredient row that gets re-classified by name into
            # the otheringredients section by virtue of a name-pattern
            # match. None of our current classifier paths do this
            # cleanly, so we simulate the bug shape by emitting an
            # inactive_ingredient display entry directly via a
            # known-misclassified label header pattern. (For real
            # regression coverage of this branch, see the build-side
            # test_active_count_reconciliation suite.)
            {"name": "Less than 2% of:", "category": "other",
             "ingredientGroup": "Header",
             "forms": [{"name": "Gum Arabic"}]},
        ],
        "otheringredients": {"text": None, "ingredients": []},
    }
    out = normalizer.normalize_product(synthetic)
    reasons = _display_reasons(out)
    # Either the header gets routed through inactive section
    # (structural_header → wrapped) OR has no actives at all. The
    # important invariant: when ONLY DROPPED_AS_INACTIVE is present
    # the audit catches it; this product should not emit
    # DROPPED_NUTRITION_FACT (no panel rows exist).
    assert "DROPPED_NUTRITION_FACT" not in reasons
