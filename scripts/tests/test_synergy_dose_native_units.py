"""Synergy dose floors compare against each threshold's NATIVE unit.

Regression: the "unit-aware" refactor forced the product amount to **mg**
before comparing to a cluster's ``min_effective_dose``, but the thresholds in
``synergy_cluster.json`` are authored in each nutrient's conventional unit
(methylcobalamin 500 **mcg**, vitamin d 1000 **IU**, probiotics 1e10 **CFU**).
Forcing mg mis-scaled every non-mg threshold, so ~19/58 clusters silently lost
their synergy bonus (under-credit).

Each threshold now carries its unit (default ``mg``; overrides in a shared
``min_effective_dose_units`` map) and the product amount is converted **to that
unit** before the comparison. Melatonin (0.5 mg, no override) still converts a
mcg-listed product to mg — preserving test_synergy_unit_aware.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from enrich_supplements_v3 import SupplementEnricherV3


def _enricher_with(clusters, units):
    e = SupplementEnricherV3()
    e.databases["synergy_cluster"] = {
        "synergy_clusters": clusters,
        "min_effective_dose_units": units,
    }
    return e


def _cluster(cid, ingredient, dose):
    return {
        "id": cid,
        "standard_name": cid,
        "ingredients": [ingredient],
        "canonical_ids": [ingredient],
        "min_effective_doses": {ingredient: dose},
        "allow_single_ingredient": True,
        "primary_ingredients": [ingredient],
    }


def _product(name, qty, unit):
    return {
        "name": "t",
        "activeIngredients": [
            {"name": name, "standardName": name, "quantity": qty, "unit": unit}
        ],
    }


def _meets(enricher, product):
    clusters = enricher._collect_synergy_data(product)
    return clusters[0]["matched_ingredients"][0]["meets_minimum"]


class TestMcgThresholdNoLongerMisScaled:
    """methylcobalamin floor = 500 mcg (was forced to mg → 0.5 ≥ 500 = False)."""

    def test_500_mcg_meets_500_mcg_floor(self):
        e = _enricher_with([_cluster("methyl", "methylcobalamin", 500)], {"methylcobalamin": "mcg"})
        assert _meets(e, _product("Methylcobalamin", 500, "mcg")) is True

    def test_300_mcg_does_not_meet_500_mcg_floor(self):
        e = _enricher_with([_cluster("methyl", "methylcobalamin", 500)], {"methylcobalamin": "mcg"})
        assert _meets(e, _product("Methylcobalamin", 300, "mcg")) is False

    def test_product_in_mg_converts_to_mcg(self):
        # 0.5 mg == 500 mcg → meets the 500 mcg floor
        e = _enricher_with([_cluster("methyl", "methylcobalamin", 500)], {"methylcobalamin": "mcg"})
        assert _meets(e, _product("Methylcobalamin", 0.5, "mg")) is True


class TestIuThreshold:
    def test_1000_iu_meets_1000_iu_floor(self):
        e = _enricher_with([_cluster("d", "vitamin d", 1000)], {"vitamin d": "iu"})
        assert _meets(e, _product("Vitamin D", 1000, "IU")) is True


class TestCfuThreshold:
    def test_1e10_cfu_meets_1e10_floor(self):
        e = _enricher_with([_cluster("pro", "probiotics", 10_000_000_000)], {"probiotics": "cfu"})
        assert _meets(e, _product("Probiotics", 10_000_000_000, "CFU")) is True


class TestMgDefaultPreserved:
    """No override → mg (the dominant convention); Codex's melatonin cases hold."""

    def test_melatonin_500_mcg_meets_half_mg(self):
        e = _enricher_with([_cluster("mel", "melatonin", 0.5)], {})
        assert _meets(e, _product("Melatonin", 500, "mcg")) is True

    def test_melatonin_300_mcg_does_not_meet_half_mg(self):
        e = _enricher_with([_cluster("mel", "melatonin", 0.5)], {})
        assert _meets(e, _product("Melatonin", 300, "mcg")) is False

    def test_mg_threshold_native(self):
        e = _enricher_with([_cluster("cur", "curcumin", 500)], {})
        assert _meets(e, _product("Curcumin", 500, "mg")) is True


class TestUnconvertibleThresholds:
    def test_cross_dimensional_unit_does_not_false_positive_a_solo_cluster(self):
        e = _enricher_with([_cluster("pro", "probiotics", 100)], {"probiotics": "cfu"})
        assert e._collect_synergy_data(_product("Probiotics", 500, "mg")) == []

    def test_unsupported_unit_does_not_false_positive_a_solo_cluster(self):
        e = _enricher_with([_cluster("cur", "curcumin", 500)], {})
        assert e._collect_synergy_data(_product("Curcumin", 600, "spoon")) == []

    def test_multi_ingredient_cluster_keeps_unconvertible_match_but_marks_it_unevaluable(self):
        e = _enricher_with([{
            "id": "mixed",
            "standard_name": "mixed",
            "ingredients": ["curcumin", "probiotics"],
            "canonical_ids": ["curcumin", "probiotics"],
            "min_effective_doses": {"curcumin": 500, "probiotics": 100},
            "allow_single_ingredient": False,
            "primary_ingredients": ["curcumin", "probiotics"],
        }], {"probiotics": "cfu"})
        product = {
            "name": "t",
            "activeIngredients": [
                {"name": "Curcumin", "standardName": "Curcumin", "quantity": 500, "unit": "mg"},
                {"name": "Probiotics", "standardName": "Probiotics", "quantity": 500, "unit": "mg"},
            ],
        }

        clusters = e._collect_synergy_data(product)

        assert len(clusters) == 1
        assert clusters[0]["all_adequate"] is False
        matched = {row["cluster_ingredient"]: row for row in clusters[0]["matched_ingredients"]}
        assert matched["curcumin"]["meets_minimum"] is True
        assert matched["curcumin"]["dose_evaluable"] is True
        assert matched["probiotics"]["evaluated_quantity"] is None
        assert matched["probiotics"]["evaluated_unit"] is None
        assert matched["probiotics"]["dose_evaluable"] is False
        assert matched["probiotics"]["meets_minimum"] is False
