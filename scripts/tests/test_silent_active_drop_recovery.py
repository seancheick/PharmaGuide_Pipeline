#!/usr/bin/env python3
"""Regression tests for the 2026-05-14 / 2026-05-15 Bucket-1 closure work
on silent active-row drops in `enhanced_normalizer`.

Background: A catalog audit across 13,746 cleaned products surfaced 49
silent drops (raw_actives_count > 0 but activeIngredients == []). After
filtering out genuine DSLD authoring gaps (products whose ingredientRows
contain ONLY nutrition-panel macros), 24 were real cleaner-side bugs in
2 clusters:

  - PEG-Creatine cluster (14 GNC products): `PEG-Creatine System` row
    was being skip-listed via `BLEND_HEADER_EXACT_NAMES` even though
    it has no nestedRows[] / no forms[] — i.e., it IS the product's
    leaf identity, not a structural header.

  - Fish Oil cluster (6 GNC products): `Total Omega-3 Fatty Acids` row
    with `forms=[DHA, EPA]` was being dropped via the nutrition-fact
    rollup-prefix check WITHOUT extracting the real-bioactive form
    children, so DHA / EPA disappeared along with the parent.

Two surgical fixes:
  1. Remove `peg-creatine system` from `BLEND_HEADER_EXACT_NAMES`.
     `arginine, peg-micronized system` retained (only 2 raw rows, no
     IQM alias yet, and the host product has 4 other mapped actives —
     not silently failing).
  2. Modify `_process_single_ingredient_enhanced` so the
     nutrition-fact drop path extracts `forms[]` children before
     returning None. Re-runs the per-row classifier on each form so
     summary-name children (e.g., "Other Omega-3 Fatty Acids") still
     get filtered.

Known remaining limitation: products whose entire active chain is a
sequence of nested rollups with no discrete chemical leaf (e.g., dsld
212518 — Total Fish Oil → Total Omega-3 Fatty Acids → Total EPA + DHA,
all rollups, no concrete DHA/EPA breakdown) still NOT_SCORED. Deferred
to a follow-up — requires a smarter chain-recovery heuristic.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))


# ---------------------------------------------------------------------------
# Fix A — BLEND_HEADER_EXACT_NAMES no longer skips PEG-Creatine System
# ---------------------------------------------------------------------------

def test_blend_header_exact_names_no_longer_skips_peg_creatine_system() -> None:
    """`peg-creatine system` must NOT be in BLEND_HEADER_EXACT_NAMES.
    It is a leaf product identity (no nestedRows, no forms), not a
    structural header. Listing it caused 14 GNC products to silently
    lose their only active in the cleaner."""
    from constants import BLEND_HEADER_EXACT_NAMES
    assert "peg-creatine system" not in BLEND_HEADER_EXACT_NAMES, (
        "'peg-creatine system' was re-added to BLEND_HEADER_EXACT_NAMES — "
        "this regresses Bucket-1 Cluster B-creatine, silently dropping "
        "PEG-Creatine from 14 GNC products. PEG-Creatine has a dedicated "
        "IQM form at ingredient_quality_map.json::creatine_monohydrate."
        "forms['peg-creatine system'] — let the row flow to the matcher."
    )


def test_cleaner_keeps_peg_creatine_system_as_active() -> None:
    """End-to-end: a DSLD row matching the GNC Amplified Creatine 189
    shape must survive the cleaner as a real active routed to the
    creatine_monohydrate canonical."""
    from enhanced_normalizer import EnhancedDSLDNormalizer
    n = EnhancedDSLDNormalizer()
    raw_product = {
        "id": "TEST-PEG-CREATINE",
        "fullName": "Test Amplified Creatine 189",
        "ingredientRows": [
            {
                "order": 1,
                "name": "PEG-Creatine System",
                "category": "non-nutrient/non-botanical",
                "ingredientGroup": "Creatine",
                "quantity": [{"servingSizeOrder": 1, "quantity": 189, "unit": "mg",
                              "servingSizeUnit": "Capsule(s)"}],
                "nestedRows": [],
                "forms": [],
            }
        ],
        "otheringredients": {"text": None, "ingredients": []},
    }
    cleaned = n.normalize_product(raw_product)
    actives = cleaned.get("activeIngredients") or []
    assert len(actives) == 1, (
        f"Expected 1 active for PEG-Creatine System leaf row; got {len(actives)}. "
        f"Cleaner is dropping the row again — check BLEND_HEADER_EXACT_NAMES."
    )
    assert actives[0]["name"] == "PEG-Creatine System"
    assert actives[0].get("canonical_id") == "creatine_monohydrate", (
        f"PEG-Creatine System must route to creatine_monohydrate canonical; "
        f"got canonical_id={actives[0].get('canonical_id')!r}. Verify the "
        f"dedicated 'peg-creatine system' form exists in IQM."
    )
    assert actives[0].get("mapped") is True


# ---------------------------------------------------------------------------
# Fix B — Nutrition-fact drop extracts forms[] before returning None
# ---------------------------------------------------------------------------

def test_nutrition_fact_with_real_bioactive_forms_extracts_children() -> None:
    """A `Total Omega-3 Fatty Acids` row with `forms=[DHA, EPA]` must
    yield DHA + EPA as active rows even though the parent is itself
    dropped as a nutrition-fact rollup. Fixes the Fish Oil cluster
    (dsld_ids 1056, 11587, 33527, 75188, 75291, 243713)."""
    from enhanced_normalizer import EnhancedDSLDNormalizer
    n = EnhancedDSLDNormalizer()
    raw_product = {
        "id": "TEST-FISH-OIL",
        "fullName": "Test Fish Oil 1000",
        "ingredientRows": [
            {
                "order": 1,
                "name": "Calories",
                "category": "other",
                "ingredientGroup": "Calories",
                "quantity": [{"servingSizeOrder": 1, "quantity": 10,
                              "unit": "Calorie(s)", "servingSizeUnit": "Softgel(s)"}],
            },
            {
                "order": 2,
                "name": "Total Omega-3 Fatty Acids",
                "category": "fatty acid",
                "ingredientGroup": "Omega-3",
                "quantity": [{"servingSizeOrder": 1, "quantity": 300,
                              "unit": "mg", "servingSizeUnit": "Softgel(s)"}],
                "forms": [
                    {"order": 1, "name": "Docosahexaenoic Acid",
                     "ingredientGroup": "DHA"},
                    {"order": 2, "name": "Eicosapentaenoic Acid",
                     "ingredientGroup": "EPA"},
                ],
                "nestedRows": [],
            },
        ],
        "otheringredients": {"text": None, "ingredients": []},
    }
    cleaned = n.normalize_product(raw_product)
    actives = cleaned.get("activeIngredients") or []
    active_names = {a["name"] for a in actives}
    assert "Docosahexaenoic Acid" in active_names, (
        f"DHA was lost when parent 'Total Omega-3 Fatty Acids' was dropped. "
        f"Got active names: {active_names}. Fix B should extract forms[] "
        f"children before returning None on nutrition-fact rows."
    )
    assert "Eicosapentaenoic Acid" in active_names, (
        f"EPA was lost when parent was dropped. Got: {active_names}"
    )


def test_nutrition_fact_with_summary_forms_still_filters_correctly() -> None:
    """A `Total Omega-3 Fatty Acids` row whose forms contain ONLY
    summary children (e.g., 'Other Omega-3 Fatty Acids') must still
    leak nothing — the extracted child must itself be filtered by the
    nutrition-fact gate.

    Guards against the Fix B path turning into a back-door for label-
    rollup leakage."""
    from enhanced_normalizer import EnhancedDSLDNormalizer
    n = EnhancedDSLDNormalizer()
    raw_product = {
        "id": "TEST-ROLLUP-ONLY",
        "fullName": "Test Rollup Cascade",
        "ingredientRows": [
            {
                "order": 1,
                "name": "Total Omega-3 Fatty Acids",
                "category": "fatty acid",
                "ingredientGroup": "Omega-3",
                "quantity": [{"servingSizeOrder": 1, "quantity": 100,
                              "unit": "mg", "servingSizeUnit": "Capsule(s)"}],
                "forms": [
                    # Only summary/rollup forms — should ALL be filtered
                    {"order": 1, "name": "Other Omega-3 Fatty Acids",
                     "ingredientGroup": "Omega-3"},
                ],
                "nestedRows": [],
            },
        ],
        "otheringredients": {"text": None, "ingredients": []},
    }
    cleaned = n.normalize_product(raw_product)
    actives = cleaned.get("activeIngredients") or []
    rollup_names = {"total omega-3 fatty acids", "other omega-3 fatty acids"}
    for a in actives:
        assert a["name"].lower() not in rollup_names, (
            f"Rollup-name {a['name']!r} leaked through Fix B's forms[] "
            f"extraction path. The extracted child must re-run through "
            f"the nutrition-fact classifier."
        )


def test_nutrition_fact_with_no_forms_still_returns_none() -> None:
    """Back-compat: a nutrition-fact row with no forms[] must still be
    silently dropped. Fix B only activates the extraction branch when
    forms[] is non-empty — pure nutrition-fact rows (Calories, Total
    Fat alone) must keep their existing behavior."""
    from enhanced_normalizer import EnhancedDSLDNormalizer
    n = EnhancedDSLDNormalizer()
    raw_product = {
        "id": "TEST-PURE-NUTRITION",
        "fullName": "Test Pure Nutrition Panel",
        "ingredientRows": [
            {
                "order": 1,
                "name": "Calories",
                "category": "other",
                "ingredientGroup": "Calories",
                "quantity": [{"servingSizeOrder": 1, "quantity": 10,
                              "unit": "Calorie(s)", "servingSizeUnit": "Softgel(s)"}],
                "forms": [],
                "nestedRows": [],
            },
            {
                "order": 2,
                "name": "Total Fat",
                "category": "fat",
                "ingredientGroup": "Fat (unspecified)",
                "quantity": [{"servingSizeOrder": 1, "quantity": 1,
                              "unit": "g", "servingSizeUnit": "Softgel(s)"}],
                "forms": [],
                "nestedRows": [],
            },
        ],
        "otheringredients": {"text": None, "ingredients": []},
    }
    cleaned = n.normalize_product(raw_product)
    actives = cleaned.get("activeIngredients") or []
    assert len(actives) == 0, (
        f"Pure macros-only product (Calories + Total Fat) should have 0 "
        f"actives; got {len(actives)}: {[a['name'] for a in actives]}. "
        f"Fix B regression — extraction branch fired when it shouldn't have."
    )
