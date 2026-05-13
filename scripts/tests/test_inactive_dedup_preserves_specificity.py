"""Bucket-2 regression — inactive ingredients silently dropped (2026-05-13).

Sprint E1.2.4 follow-up: the cleaner used to dedup an inactive against an
active whenever their mapped ``standardName`` collided. This silently
erased label specificity (e.g. "Hydrolyzed lactalbumin protein" was
dropped because it mapped to standardName="Protein" and the product also
had a "Protein" nutrition-facts row). Downstream allergen / banned /
harmful-additive detection then never ran on the dropped row.

Two invariants are pinned here:

1. **Specificity preservation.** When an inactive's raw label name differs
   from any active row's raw name (and is not contained in any active
   row's name/standardName as a preprocessed token), the inactive MUST
   survive into ``inactiveIngredients[]``. The shared ``standardName`` of
   the inactive is never sufficient to drive dedup.

2. **Count truthfulness.** ``raw_inactives_count`` reflects the count of
   real, non-redundant raw inactives the cleaner expects to ship. It
   excludes DSLD's "None" placeholder, header rows
   (``ingredientGroup="Header"`` and structural label-header phrases),
   skip-list entries, and rows whose preprocessed raw name matches an
   active. This makes the audit ``raw_inactives_count > 0 ⇒
   blob.inactive_ingredients[] non-empty`` fire only on a true filter
   regression.

Representative DSLD products covered:

* 16202 — Thorne Hydrolyzed Whey Protein. Inactive "Hydrolyzed
  lactalbumin protein" (std=Protein) must NOT be dropped by the active
  "Protein" nutrition-facts row. Carries milk-allergen signal.
* 268535 — SR Sports Research MCT C8 Oil. Mixed case: actives
  ("Caprylic Acid", "MCT Oil") legitimately consume the same-named
  inactives; the inactive "Coconuts" is specificity-bearing and MUST
  ship.
* 242312 — SR Sports Research Collagen Peptides. Full legitimate dedup:
  the only inactive "hydrolyzed Bovine Collagen Peptides" has the same
  raw name as an active, so the count adjusts to 0 and the audit does
  not fire.
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


# Real raw DSLD payloads, vendored here so the test is hermetic and does
# not depend on the local DataSetDsld checkout.
RAW_FIXTURES: Dict[int, Dict[str, Any]] = {
    # 16202 — Thorne Hydrolyzed Whey Protein
    16202: {
        "id": 16202,
        "fullName": "Hydrolyzed Whey Protein",
        "brandName": "Thorne Research",
        "ingredientRows": [
            {"name": "Calories", "category": "other",
             "quantity": [{"servingSizeOrder": 1, "operator": "=", "quantity": 120, "unit": "{Calories}"}]},
            {"name": "Total Fat", "category": "fat",
             "quantity": [{"servingSizeOrder": 1, "operator": "=", "quantity": 2, "unit": "g"}]},
            {"name": "Total Carbohydrates", "category": "sugar",
             "quantity": [{"servingSizeOrder": 1, "operator": "=", "quantity": 2, "unit": "g"}]},
            {"name": "Protein", "category": "protein",
             "quantity": [{"servingSizeOrder": 1, "operator": "=", "quantity": 23, "unit": "g"}]},
        ],
        "otheringredients": {
            "text": None,
            "ingredients": [
                {"order": 1, "ingredientId": 61300, "name": "Hydrolyzed lactalbumin protein",
                 "category": "protein", "ingredientGroup": "Lactalbumin", "forms": []},
            ],
        },
    },
    # 268535 — SR Sports Research Organic MCT C8 Oil Unflavored
    268535: {
        "id": 268535,
        "fullName": "Organic MCT C8 Oil Unflavored",
        "brandName": "SR Sports Research",
        "ingredientRows": [
            {"name": "Calories", "category": "other",
             "quantity": [{"servingSizeOrder": 1, "operator": "=", "quantity": 130, "unit": "{Calories}"}]},
            {"name": "Total Fat", "category": "fat",
             "quantity": [{"servingSizeOrder": 1, "operator": "=", "quantity": 14, "unit": "g"}]},
            {"name": "Caprylic Acid", "category": "fatty acid",
             "quantity": [{"servingSizeOrder": 1, "operator": "=", "quantity": 14, "unit": "g"}]},
        ],
        "otheringredients": {
            "text": None,
            "ingredients": [
                {"order": 1, "name": "Caprylic Acid", "category": "fatty acid",
                 "ingredientGroup": "Caprylic Acid", "forms": []},
                {"order": 2, "name": "MCT Oil", "category": "fat",
                 "ingredientGroup": "Medium chain triglycerides (MCT)", "forms": []},
                {"order": 3, "name": "Coconuts", "category": "botanical",
                 "ingredientGroup": "Coconut", "forms": []},
            ],
        },
    },
    # 242312 — SR Sports Research Collagen Peptides (full legit dedup)
    242312: {
        "id": 242312,
        "fullName": "Collagen Peptides Unflavored",
        "brandName": "SR Sports Research",
        "ingredientRows": [
            {"name": "Calories", "category": "other",
             "quantity": [{"servingSizeOrder": 1, "operator": "=", "quantity": 40, "unit": "{Calories}"}]},
            {"name": "Protein", "category": "protein",
             "quantity": [{"servingSizeOrder": 1, "operator": "=", "quantity": 11, "unit": "g"}]},
            {"name": "hydrolyzed Bovine Collagen Peptides", "category": "protein",
             "quantity": [{"servingSizeOrder": 1, "operator": "=", "quantity": 12000, "unit": "mg"}]},
        ],
        "otheringredients": {
            "text": None,
            "ingredients": [
                {"order": 1, "name": "hydrolyzed Bovine Collagen Peptides",
                 "category": "protein", "ingredientGroup": "Collagen Peptides", "forms": []},
            ],
        },
    },
    # 178677 — Spring Valley Gelatin 1300 mg
    # Exercises ingredientGroup="Header" exclusion: headers
    # "Contains <2%:" and "May contain:" are emitted by DSLD as
    # otheringredients rows but must NOT count as real raw inactives.
    178677: {
        "id": 178677,
        "fullName": "Gelatin 1300 mg",
        "brandName": "Spring Valley",
        "ingredientRows": [
            {"name": "Gelatin", "category": "protein",
             "quantity": [{"servingSizeOrder": 1, "operator": "=", "quantity": 1300, "unit": "mg"}]},
        ],
        "otheringredients": {
            "text": None,
            "ingredients": [
                {"order": 1, "name": "Gelatin", "category": "protein",
                 "ingredientGroup": "Gelatin Capsule", "forms": []},
                {"order": 2, "name": "Contains <2%:", "category": "other",
                 "ingredientGroup": "Header", "forms": []},
                {"order": 3, "name": "May contain:", "category": "other",
                 "ingredientGroup": "Header", "forms": []},
            ],
        },
    },
}


@pytest.fixture(scope="module")
def normalizer() -> EnhancedDSLDNormalizer:
    return EnhancedDSLDNormalizer()


def _names(items: Iterable[Dict[str, Any]]) -> List[str]:
    return [i.get("name") for i in items]


def test_16202_lactalbumin_specificity_preserved(normalizer):
    """Whey protein's "Hydrolyzed lactalbumin protein" inactive must NOT
    be dropped by the active "Protein" nutrition-facts row. It carries
    milk-allergen signal — dropping it is silent under-protection."""
    out = normalizer.normalize_product(RAW_FIXTURES[16202])
    inactives = out.get("inactiveIngredients", [])
    actives_names = _names(out.get("activeIngredients", []))
    inactive_names = _names(inactives)

    assert len(inactives) == 1, (
        f"expected 1 inactive (Hydrolyzed lactalbumin protein); "
        f"got {inactive_names}. actives were {actives_names}"
    )
    assert "Hydrolyzed lactalbumin protein" in inactive_names
    # Audit invariant must not fire.
    assert out.get("raw_inactives_count", 0) >= 1


def test_268535_mct_oil_preserves_coconut_botanical(normalizer):
    """MCT C8 Oil: actives "Caprylic Acid" and "MCT Oil" legitimately
    consume the same-named inactives, but the inactive "Coconuts"
    (botanical source descriptor) must ship — it carries
    allergen-relevant specificity."""
    out = normalizer.normalize_product(RAW_FIXTURES[268535])
    inactive_names = _names(out.get("inactiveIngredients", []))

    assert "Coconuts" in inactive_names, (
        f"Coconuts inactive must survive; got {inactive_names}"
    )
    # Caprylic Acid / MCT Oil are duplicates of active rows by raw name
    # and are correctly removed by dedup; their raw-name match is the
    # legitimate dedup case.
    assert "Caprylic Acid" not in inactive_names
    assert "MCT Oil" not in inactive_names
    assert out.get("raw_inactives_count", 0) == 1


def test_242312_collagen_full_legitimate_dedupe(normalizer):
    """When the only inactive has the same raw name as an active, the
    blob's inactive list is correctly empty AND ``raw_inactives_count``
    is 0 (legitimate dedup, not filter regression). The audit
    invariant in ``build_final_db._validate_inactive_preservation``
    must not fire."""
    out = normalizer.normalize_product(RAW_FIXTURES[242312])
    inactives = out.get("inactiveIngredients", [])
    assert len(inactives) == 0
    # Count must NOT trip the audit.
    assert out.get("raw_inactives_count", 0) == 0


def test_178677_dsld_header_rows_excluded_from_count(normalizer):
    """DSLD emits "Contains <2%:" and "May contain:" as otheringredients
    rows with ``ingredientGroup="Header"``. These are not real raw
    inactives; ``raw_inactives_count`` must exclude them, and the audit
    must not fire on a label that only contains a deduped real inactive
    plus header rows."""
    out = normalizer.normalize_product(RAW_FIXTURES[178677])
    inactives = out.get("inactiveIngredients", [])
    # Gelatin appears in both active and inactive — legit dedup. Headers
    # excluded from count. Net: count=0, list=[].
    assert len(inactives) == 0
    assert out.get("raw_inactives_count", 0) == 0


def test_dedupe_does_not_rely_on_inactive_standardname_alone(normalizer):
    """Synthetic case: an inactive whose ``standardName`` (via mapper)
    collides with a nutrition-facts active's ``standardName``, but whose
    raw name differs, must survive. This is the invariant Sprint E1.2.4
    follow-up restores."""
    payload = {
        "id": 999001,
        "fullName": "Synthetic Whey Test",
        "brandName": "TestCo",
        "ingredientRows": [
            {"name": "Protein", "category": "protein",
             "quantity": [{"servingSizeOrder": 1, "operator": "=",
                           "quantity": 25, "unit": "g"}]},
        ],
        "otheringredients": {
            "text": None,
            "ingredients": [
                {"order": 1, "name": "Whey Protein Isolate",
                 "category": "protein", "ingredientGroup": "Whey",
                 "forms": []},
            ],
        },
    }
    out = normalizer.normalize_product(payload)
    inactive_names = _names(out.get("inactiveIngredients", []))
    assert "Whey Protein Isolate" in inactive_names, (
        f"Specific inactive 'Whey Protein Isolate' must not be dropped by "
        f"standardName collision with the generic 'Protein' active. "
        f"Got: {inactive_names}"
    )
