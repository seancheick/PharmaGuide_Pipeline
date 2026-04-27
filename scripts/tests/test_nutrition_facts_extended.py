"""
Sprint D1.3 regression tests — Nutrition Facts panel leak.

Context: prior to Sprint D1.3, DSLD rows carrying sugars, sweeteners, fats,
or calorie disclosures were leaking into activeIngredients and picking up
full B1 harmful-additive penalties even when the row was a Nutrition
Facts panel disclosure (e.g., "Sugar Alcohols 2.0 Gram(s)" on a gummy).
~150 rows across the 20-brand corpus were affected.

Fix (two layers):
1. Cleaner: ``_is_nutrition_fact`` now recognises
   - panel-explicit units (``{Gram(s)}`` or bare ``Gram(s)``/``Calories``)
   - DSLD categories ``sugar`` / ``fat`` / ``complex carbohydrate`` /
     ``cholesterol`` / ``total sugars`` / ``total fat`` etc.
   - protein and fiber are INTENTIONALLY excluded from the auto-filter
     because both can be genuine supplement ingredients (whey protein,
     psyllium husk). Bare "Protein" name gets caught by the name-based
     exclusion list.
2. Data: sugar / sweetener / fat formulation additives in
   harmful_additives.json carry ``severity_level: "low"`` so the scorer
   applies a reduced B1 penalty to formulation-use rows (e.g., Xylitol
   in a gummy) while still flagging them as quality signals.

These tests guard both layers.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from enhanced_normalizer import EnhancedDSLDNormalizer


@pytest.fixture(scope="module")
def normalizer() -> EnhancedDSLDNormalizer:
    return EnhancedDSLDNormalizer()


HARMFUL_PATH = (
    Path(__file__).parent.parent / "data" / "harmful_additives.json"
)


# ---------------------------------------------------------------------------
# Nutrition Facts panel filter — rows that MUST be excluded from actives
# ---------------------------------------------------------------------------


class TestNutritionFactsPanelExcludedFromActives:
    """Panel-rendered sugar/fat/carb/calorie rows no longer route to actives."""

    @pytest.mark.parametrize("name,group,unit,cat", [
        # Sugar alcohols with Gram(s) panel unit (the top-offending leak)
        ("Sugar Alcohols",  "Sugar Alcohol",  "Gram(s)", "non-nutrient/non-botanical"),
        ("Sugar Alcohol",   "Sugar Alcohol",  "Gram(s)", "non-nutrient/non-botanical"),
        # Sugar-category rows (any unit — category alone qualifies)
        ("Dextrose",        "Glucose",        "mg",      "sugar"),
        ("Cane Sugar",      "Sucrose",        "NP",      "sugar"),
        ("Total Sugars",    "Sugar",          "Gram(s)", "sugar"),
        # Fat-category rows
        ("Palm Oil",        "Palm oil",       "NP",      "fat"),
        ("Total Fat",       "Fat",            "Gram(s)", "fat"),
        # Carb-category rows
        ("Maltodextrin",    "Maltodextrin",   "NP",      "complex carbohydrate"),
        # Cholesterol category
        ("Cholesterol",     "Cholesterol",    "mg",      "cholesterol"),
        # Calorie panel
        ("Calories",        "Calories",       "Calories","calorie"),
    ])
    def test_excluded_from_actives(self, normalizer, name, group, unit, cat) -> None:
        assert normalizer._is_nutrition_fact(
            name, ingredient_group=group, unit=unit, dsld_category=cat,
        ) is True, (
            f"D1.3 regression: {name!r} (cat={cat!r}, unit={unit!r}) must be "
            f"excluded from actives as a Nutrition Facts panel disclosure."
        )


# ---------------------------------------------------------------------------
# Real supplement ingredients — must NOT be caught by the NF filter
# ---------------------------------------------------------------------------


class TestRealSupplementIngredientsStillRoute:
    """Fiber / protein / MCT supplements keep routing as actives."""

    @pytest.mark.parametrize("name,group,unit,cat", [
        # Real vitamins / minerals unaffected
        ("Vitamin C",       "Vitamin C",     "mg", "vitamin"),
        ("Calcium",         "Calcium",       "mg", "mineral"),
        # MCT / fatty acids are real actives (fatty acid category bypass)
        ("Caprylic Acid",   "Caprylic Acid", "mg", "fatty acid"),
        ("MCT Oil",         "MCT",           "g",  "fatty acid"),
        # Fiber is a real supplement (Psyllium, Inulin) — NOT auto-filtered
        ("Psyllium Husk",   "Psyllium",      "g",  "fiber"),
        ("Inulin",          "Inulin",        "g",  "fiber"),
        # Specific protein sources — NOT auto-filtered (bare "Protein" IS)
        ("Whey Protein",    "Whey Protein",  "g",  "protein"),
        ("Pea Protein",     "Pea Protein",   "g",  "protein"),
        # Xylitol used as formulation additive (unit=NP, not panel cat)
        # — passes through cleaner, routes to harmful_additives with
        # severity_level="low" for small B1 penalty
        ("Xylitol",         "Xylitol",       "NP", "non-nutrient/non-botanical"),
    ])
    def test_not_excluded(self, normalizer, name, group, unit, cat) -> None:
        assert normalizer._is_nutrition_fact(
            name, ingredient_group=group, unit=unit, dsld_category=cat,
        ) is False, (
            f"D1.3 regression: {name!r} (cat={cat!r}, unit={unit!r}) is a real "
            f"supplement ingredient and must NOT be filtered as Nutrition Facts."
        )


class TestFatCategoryRealActivesNotFiltered:
    """E1.6 regression — DSLD category=fat with mg-scale unit and a
    specific ingredientGroup (Phosphatidylserine, Krill Oil, etc.) is a
    REAL active, not a Nutrition Facts panel disclosure.

    The earlier D1.3 logic (line 6730) treated ANY category=fat row as
    nutrition-panel exclusion regardless of unit, which silently dropped
    ~186 single-active products (Phosphatidyl Serine, Krill Oil, EPO,
    Flaxseed Oil, Phytosterols, etc.) from scoring entirely.

    The fix requires THREE conditions to exclude as panel disclosure:
        1. category in nutrition-facts set (fat, sugar, carb, …)
        2. unit is gram-scale (g, gram, grams) — NOT mg
        3. ingredientGroup matches a generic panel term
           ("Fat (unspecified)", "Saturated Fat", "Cholesterol", …)

    Anything else routes to actives.
    """

    @pytest.mark.parametrize("name,group,unit,cat,reason", [
        # Real Bucket-B examples from production data (DSLD IDs verified):
        ("Phosphatidyl Serine",     "Phosphatidylserine",         "mg", "fat",  "DSLD 1037 — phospholipid supplement, 300 mg/day"),
        ("Neptune Krill Oil",       "Krill Oil",                  "mg", "fat",  "DSLD 1072 — marine phospholipid concentrate"),
        ("CardioAid Phytosterols",  "Phytosterols (unspecified)", "mg", "fat",  "DSLD 11531 — plant sterols for cholesterol"),
        ("Evening Primrose Oil",    "Evening Primrose Oil",       "mg", "fat",  "DSLD 11588 — GLA omega-6"),
        ("Organic Flax Seed Oil",   "Flaxseed Oil",               "mg", "fat",  "DSLD 12859 — ALA omega-3"),
    ])
    def test_specific_fat_supplements_are_actives(
        self, normalizer, name, group, unit, cat, reason
    ) -> None:
        assert normalizer._is_nutrition_fact(
            name, ingredient_group=group, unit=unit, dsld_category=cat,
        ) is False, (
            f"E1.6 regression: {name!r} (group={group!r}, cat={cat!r}, "
            f"unit={unit!r}) is a real active supplement — must route to "
            f"activeIngredients, NOT be filtered as a Nutrition Facts row.\n"
            f"Source: {reason}"
        )

    @pytest.mark.parametrize("name,group,unit,cat", [
        # These ARE genuine Nutrition Facts panel disclosures:
        ("Total Fat",         "Fat (unspecified)",   "g", "fat"),
        ("Saturated Fat",     "Saturated Fat",       "g", "fat"),
        ("Trans Fat",         "Trans Fat",           "g", "fat"),
        ("Cholesterol",       "Cholesterol",         "mg", "fat"),
        ("Polyunsaturated Fat", "Polyunsaturated Fat","g", "fat"),
        ("Monounsaturated Fat", "Monounsaturated Fat","g", "fat"),
    ])
    def test_panel_fat_rows_still_excluded(
        self, normalizer, name, group, unit, cat
    ) -> None:
        assert normalizer._is_nutrition_fact(
            name, ingredient_group=group, unit=unit, dsld_category=cat,
        ) is True, (
            f"{name!r} (group={group!r}) is a Nutrition Facts panel "
            f"disclosure and MUST still be filtered out."
        )


# ---------------------------------------------------------------------------
# Braced vs bare unit rendering — both must work
# ---------------------------------------------------------------------------


class TestBracedAndBareUnits:
    """DSLD is inconsistent about {Gram(s)} vs Gram(s); both must match."""

    @pytest.mark.parametrize("unit", ["{Gram(s)}", "Gram(s)", "gram(s)", "grams"])
    def test_braced_and_bare_gram_panel_units(self, normalizer, unit) -> None:
        assert normalizer._is_nutrition_fact(
            "Sugar Alcohols", ingredient_group="Sugar Alcohol",
            unit=unit, dsld_category="non-nutrient/non-botanical",
        ) is True, f"Unit {unit!r} must be recognised as a panel unit."

    @pytest.mark.parametrize("unit", ["{Calories}", "Calories", "kcal"])
    def test_calorie_unit_variants(self, normalizer, unit) -> None:
        assert normalizer._is_nutrition_fact(
            "Calories", ingredient_group="Calories",
            unit=unit, dsld_category="calorie",
        ) is True


# ---------------------------------------------------------------------------
# Data invariants — severity_level="low" on formulation sugar/fat entries
# ---------------------------------------------------------------------------


LOW_SEVERITY_IDS = {
    "ADD_CANE_SUGAR",
    "ADD_DEXTROSE",
    "ADD_ERYTHRITOL",
    "ADD_FRUCTOSE",
    "ADD_HFCS",
    "ADD_MALTITOL_MALITOL",
    "ADD_MALTODEXTRIN",
    "ADD_PALM_OIL",
    "ADD_POLYDEXTROSE",
    "ADD_SORBITOL",
    "ADD_SUGAR_ALCOHOLS",
    "ADD_SYRUPS",
    "ADD_XYLITOL",
    "ADD_CASSAVA_DEXTRIN",
    "ADD_MICROCRYSTALLINE_CELLULOSE",
}


class TestFormulationSugarFatLowSeverity:
    """Every sugar/sweetener/fat/MCC formulation additive carries severity_level=low."""

    def test_low_severity_on_formulation_additives(self) -> None:
        harmful = json.loads(HARMFUL_PATH.read_text())
        found = {}
        for section, value in harmful.items():
            if section.startswith("_") or not isinstance(value, list):
                continue
            for entry in value:
                if isinstance(entry, dict) and entry.get("id") in LOW_SEVERITY_IDS:
                    found[entry["id"]] = entry.get("severity_level")

        missing = LOW_SEVERITY_IDS - set(found.keys())
        assert not missing, (
            f"Regression: sugar/fat IDs expected in harmful_additives.json but "
            f"missing: {sorted(missing)}. If renamed, update LOW_SEVERITY_IDS."
        )

        not_low = {k: v for k, v in found.items() if v != "low"}
        assert not not_low, (
            f"D1.3 regression: these sugar/fat/MCC entries must carry "
            f"severity_level='low' so they receive a small B1 penalty (not "
            f"the full harmful-additive hammer). Got: {not_low}"
        )
