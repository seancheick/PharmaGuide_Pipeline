"""Safety-critical regression: nested counter-ion / blend-leaf must not
be elevated to active ingredients.

Two real, distinct DSLD shapes that the cleaner historically mishandled:

1. **Quatrefolic / methylfolate counter-ion (Doctor's Best B Complex with
   Quatrefolic, DSLD id 209368).** The branded ingredient ``Quatrefolic``
   (category=vitamin, group=Folate) declares its full chemical name on a
   nested row ``"(6S)-5-Methyltetrahydrofolic Acid, Glucosamine Salt"``
   (category=non-nutrient/non-botanical, group=5-methyltetrahydrofolate
   glucosamine). Beneath that, two leaf rows describe the constituent
   atoms:

     - ``"(6S)-5-Methyltetrahydrofolic Acid"`` (category=vitamin) — the
       active molecule
     - ``"Glucosamine Salt"`` (category=non-nutrient/non-botanical,
       group=Glucosamine (unspecified)) — the COUNTER-ION descriptor

   The historical cleaner descended into the leaves and surfaced
   ``"Glucosamine Salt"`` as a standalone active ingredient. If that name
   were aliased to IQM glucosamine, the product (a methylfolate B
   complex) would be silently mis-scored as a joint supplement —
   patient-safety risk.

2. **Fish-oil DSLD-tagged blend leaf (Spring Valley Omega-3 Fish Oil,
   DSLD id 178317).** The nested structure has::

       Fish Oil concentrate (cat=fat, group=Fish Oil)
       └── Omega-3 Fatty Acid Ethyl Ester (cat=fatty acid, group=Omega-3)
           ├── DHA, EPA (cat=blend, group=Blend, qty=285mg)
           └── Other Omega-3 Fatty Acids (cat=fatty acid)

   The leaf ``"DHA, EPA"`` has DSLD category=``blend``. The historical
   cleaner surfaced it as a single active ingredient name; the enricher
   then could not match ``"dha epa"`` to either the EPA or DHA IQM parent
   (it is neither molecule on its own — it's a combined disclosure). The
   right behavior is to treat the leaf as a non-scoring blend disclosure
   and preserve the parent fatty-acid scoring path.

The regressions below pin both behaviors with the smallest possible
DSLD-shape fixtures.
"""
from __future__ import annotations

import logging
import os
import sys
from typing import Any, Dict, List

import pytest

_SCRIPTS = os.path.join(os.path.dirname(__file__), "..")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

logging.disable(logging.CRITICAL)

from enhanced_normalizer import EnhancedDSLDNormalizer  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures — minimal DSLD-shape products
# ---------------------------------------------------------------------------

QUATREFOLIC_RAW: Dict[str, Any] = {
    "id": 209368,
    "fullName": "Fully Active B Complex with Quatrefolic",
    "brandName": "Doctor's Best",
    "ingredientRows": [
        {
            "order": 6,
            "ingredientId": 278932,
            "name": "Quatrefolic",
            "category": "vitamin",
            "ingredientGroup": "Folate",
            "uniiCode": "Q65PL71Q1A",
            "quantity": [{"servingSizeOrder": 1, "operator": "=",
                          "quantity": 400, "unit": "mcg"}],
            "forms": [{"order": 1, "ingredientId": 278757, "name": "Folate",
                       "category": "vitamin", "ingredientGroup": "Folate",
                       "uniiCode": "935E97BOY8"}],
            "nestedRows": [
                {
                    "order": 7,
                    "ingredientId": 194543,
                    "name": "(6S)-5-Methyltetrahydrofolic Acid, Glucosamine Salt",
                    "category": "non-nutrient/non-botanical",
                    "ingredientGroup": "5-methyltetrahydrofolate glucosamine",
                    "quantity": [{"servingSizeOrder": 1, "operator": "=",
                                  "quantity": 0, "unit": "NP"}],
                    "forms": [],
                    "nestedRows": [
                        {
                            "order": 8,
                            "ingredientId": 102747,
                            "name": "(6S)-5-Methyltetrahydrofolic Acid",
                            "category": "vitamin",
                            "ingredientGroup": "Vitamin B9 (5-Methyltetrahydrofolate)",
                            "quantity": [{"servingSizeOrder": 1, "operator": "=",
                                          "quantity": 0, "unit": "NP"}],
                            "forms": [], "nestedRows": [],
                        },
                        {
                            "order": 9,
                            "ingredientId": 57378,
                            "name": "Glucosamine Salt",
                            "category": "non-nutrient/non-botanical",
                            "ingredientGroup": "Glucosamine (unspecified)",
                            "quantity": [{"servingSizeOrder": 1, "operator": "=",
                                          "quantity": 0, "unit": "NP"}],
                            "forms": [], "nestedRows": [],
                        },
                    ],
                },
            ],
        },
    ],
    "otheringredients": {"text": None, "ingredients": []},
}


SPRING_VALLEY_OMEGA_RAW: Dict[str, Any] = {
    "id": 178317,
    "fullName": "Omega-3 Fish Oil",
    "brandName": "Spring Valley",
    "ingredientRows": [
        {
            "order": 1,
            "ingredientId": 1001,
            "name": "Fish Oil concentrate",
            "category": "fat",
            "ingredientGroup": "Fish Oil",
            "quantity": [{"servingSizeOrder": 1, "operator": "=",
                          "quantity": 1000, "unit": "mg"}],
            "forms": [],
            "nestedRows": [
                {
                    "order": 2,
                    "ingredientId": 1002,
                    "name": "Omega-3 Fatty Acid Ethyl Ester",
                    "category": "fatty acid",
                    "ingredientGroup": "Omega-3",
                    "quantity": [{"servingSizeOrder": 1, "operator": "=",
                                  "quantity": 300, "unit": "mg"}],
                    "forms": [],
                    "nestedRows": [
                        {
                            "order": 3,
                            "ingredientId": 1003,
                            "name": "DHA, EPA",
                            "category": "blend",
                            "ingredientGroup": "Blend",
                            "quantity": [{"servingSizeOrder": 1, "operator": "=",
                                          "quantity": 285, "unit": "mg"}],
                            "forms": [], "nestedRows": [],
                        },
                        {
                            "order": 4,
                            "ingredientId": 1004,
                            "name": "Other Omega-3 Fatty Acids",
                            "category": "fatty acid",
                            "ingredientGroup": "Omega-3",
                            "quantity": [{"servingSizeOrder": 1, "operator": "=",
                                          "quantity": 15, "unit": "mg"}],
                            "forms": [], "nestedRows": [],
                        },
                    ],
                },
            ],
        },
    ],
    "otheringredients": {"text": None, "ingredients": []},
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def normalizer() -> EnhancedDSLDNormalizer:
    return EnhancedDSLDNormalizer()


def _active_names(out: Dict[str, Any]) -> List[str]:
    return [a.get("name") for a in out.get("activeIngredients") or []]


# ---------------------------------------------------------------------------
# Tests — Quatrefolic methylfolate counter-ion
# ---------------------------------------------------------------------------

def test_quatrefolic_counter_ion_not_active(normalizer) -> None:
    """SAFETY: 'Glucosamine Salt' is the counter-ion of methylfolate.
    Must NOT appear as an active ingredient. Aliasing it to glucosamine
    would mis-score a folate B complex as a joint supplement."""
    out = normalizer.normalize_product(QUATREFOLIC_RAW)
    names = _active_names(out)
    assert "Glucosamine Salt" not in names, (
        f"SAFETY: 'Glucosamine Salt' counter-ion must not be elevated to "
        f"active. Got actives: {names}"
    )


def test_quatrefolic_methylfolate_preserved(normalizer) -> None:
    """The actual methylfolate active must be preserved — either as the
    branded parent ``Quatrefolic`` or the chemical name ``(6S)-5-MTHF``.
    Whichever the cleaner picks, the FOLATE identity must survive."""
    out = normalizer.normalize_product(QUATREFOLIC_RAW)
    names = _active_names(out)
    folate_signal_present = any(
        "quatrefolic" in (n or "").lower()
        or "methyltetrahydrofolic" in (n or "").lower()
        or "folate" in (n or "").lower()
        or "folic" in (n or "").lower()
        for n in names
    )
    assert folate_signal_present, (
        f"The folate active must survive. Got actives: {names}"
    )


# ---------------------------------------------------------------------------
# Tests — DSLD-tagged blend leaf "DHA, EPA"
# ---------------------------------------------------------------------------

def test_dha_epa_blend_leaf_not_active_name(normalizer) -> None:
    """A DSLD nested leaf with category='blend' and a comma-joined marker
    name (e.g. 'DHA, EPA') must NOT become a single active ingredient
    named literally 'DHA, EPA'. That string is unscoreable (matches
    neither EPA nor DHA IQM parents)."""
    out = normalizer.normalize_product(SPRING_VALLEY_OMEGA_RAW)
    names = _active_names(out)
    assert "DHA, EPA" not in names, (
        f"DSLD-tagged 'blend' leaf 'DHA, EPA' must not become a single "
        f"active ingredient. Got actives: {names}"
    )


def test_fish_oil_omega_parent_preserved(normalizer) -> None:
    """The fish-oil / omega-3 parent identity must remain scoreable so
    downstream EPA+DHA dose recovery (parent_blend_mass propagation) can
    still apply."""
    out = normalizer.normalize_product(SPRING_VALLEY_OMEGA_RAW)
    names = _active_names(out)
    omega_signal_present = any(
        "fish oil" in (n or "").lower()
        or "omega" in (n or "").lower()
        or "epa" in (n or "").lower()
        or "dha" in (n or "").lower()
        for n in names
    )
    assert omega_signal_present, (
        f"Omega-3 / fish-oil identity must survive. Got actives: {names}"
    )
