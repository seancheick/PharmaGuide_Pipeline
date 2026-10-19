"""Nutrition-fact status follows nutrient role, not DSLD category exceptions (cleaner audit RC2).

- Macronutrient vocabulary (energy, fats, carbohydrates, sugars, fiber, protein, cholesterol,
  sodium) is Nutrition Facts.
- Every vitamin/mineral row goes to the RDA/UL owner. A %DV-only amount converts only through
  the Daily Value equation owner; without a Daily Value target group it stays explicitly
  unresolved there (never guessed), exactly as %DV-only vitamins already do.
- Label totals ("Total Omega-3 Fatty Acids", "Total Curcuminoids", culture totals) are summary
  wrappers in the row ledger, not nutrition facts.

Row shapes are the real DSLD labels named in each test.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from constants import EXCLUDED_NUTRITION_FACTS, LABEL_ROLLUP_NAMES
from enhanced_normalizer import EnhancedDSLDNormalizer
from enrich_supplements_v3 import SupplementEnricherV3


def _qty(amount, unit, percent=None):
    groups = [] if percent is None else [{"name": "Adults and children 4 or more years of age",
                                          "operator": "=", "percent": percent, "footnote": None}]
    return [{"servingSizeOrder": 1, "servingSizeQuantity": 1, "operator": "=", "quantity": amount,
             "unit": unit, "dailyValueTargetGroup": groups, "servingSizeUnit": "Scoop(s)"}]


def _row(order, name, category, group, amount, unit, percent=None, nested=None, forms=None):
    return {"order": order, "name": name, "category": category, "ingredientGroup": group,
            "quantity": _qty(amount, unit, percent), "forms": forms or [], "nestedRows": nested or []}


def _label(label_id, name, rows):
    return {"id": label_id, "fullName": name, "brandName": "GNC", "productVersionCode": "1",
            "servingSizes": [{"order": 1, "minQuantity": 1, "maxQuantity": 1, "minDailyServings": 1,
                              "maxDailyServings": 1, "unit": "Scoop(s)", "inSFB": True}],
            "ingredientRows": rows, "otheringredients": {"ingredients": []}}


@pytest.fixture(scope="module")
def normalizer():
    return EnhancedDSLDNormalizer()


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3()


def _display(cleaned):
    return {row["raw_source_text"]: row for row in cleaned["display_ingredients"]}


def test_percent_only_minerals_reach_the_rda_ul_owner_unresolved(normalizer, enricher):
    # DSLD 16730 "Isolated Soy Protein 95 Chocolate": Nutrition Facts panel, Calcium 6 % and
    # Iron 30 % with no Daily Value target group; Vitamin A 10 % is the same shape.
    cleaned = normalizer.normalize_product(_label("16730", "Isolated Soy Protein 95 Chocolate", [
        _row(1, "Calories", "other", "Calories", 130, "{Calories}"),
        _row(2, "Sodium", "mineral", "Sodium", 310, "mg", 13),
        _row(3, "Protein", "protein", "Protein (unspecified)", 25, "g", 50),
        _row(4, "Vitamin A", "vitamin", "Vitamin A", 10, "%"),
        _row(5, "Calcium", "mineral", "Calcium", 6, "%"),
        _row(6, "Iron", "mineral", "Iron", 30, "%"),
    ]))
    actives = {row["name"]: row for row in cleaned["activeIngredients"]}
    assert {"Vitamin A", "Calcium", "Iron"} <= set(actives)
    assert (actives["Iron"]["quantity"], actives["Iron"]["unit"]) == (30, "%")  # printed, not converted
    display = _display(cleaned)
    assert display["Sodium"]["display_type"] == "nutrition_fact"
    assert display["Calories"]["display_type"] == "nutrition_fact"
    assert display["Iron"]["display_type"] != "nutrition_fact"

    enriched, _ = enricher.enrich_product(cleaned)
    assessments = {row["canonical_id"]: row for row in enriched["rda_ul_data"]["dose_assessments"]}
    for nutrient in ("iron", "calcium"):
        assert assessments[nutrient]["pct_ul"] is None  # no amount to compare: unresolved, not "safe"
        assert assessments[nutrient]["readiness"] != "complete"
    assert not enriched["rda_ul_data"].get("has_over_ul")


def test_chloride_mineral_row_stays_on_the_safety_path(normalizer):
    # DSLD 1060 "Sport Milk Chocolate": Chloride 150 mg (4 %), category mineral, no forms.
    cleaned = normalizer.normalize_product(_label("1060", "Sport Milk Chocolate", [
        _row(1, "Calories", "other", "Calories", 130, "{Calories}"),
        _row(2, "Vitamin C", "vitamin", "Vitamin C", 300, "mg", 500),
        _row(3, "Chloride", "mineral", "Chloride", 150, "mg", 4),
    ]))
    assert "Chloride" in {row["name"] for row in cleaned["activeIngredients"]}
    assert _display(cleaned)["Chloride"]["display_type"] != "nutrition_fact"


def test_label_totals_are_summary_wrappers(normalizer):
    # DSLD 252496 "Fish Oil Softgels 1000 mg" and 307577 "Curcumin 95 500 mg".
    fish = normalizer.normalize_product(_label("252496", "Fish Oil Softgels 1000 mg", [
        _row(1, "Calories", "other", "Calories", 10, "Calorie(s)"),
        _row(2, "Total Fat", "fat", "Fat (unspecified)", 1, "Gram(s)", 1),
        _row(3, "Fish Oil", "fat", "Fish Oil", 1, "Gram(s)"),
        _row(4, "Total Omega-3 Fatty Acids", "fatty acid", "Omega-3", 300, "mg", nested=[
            _row(1, "Eicosapentaenoic Acid", "fatty acid", "EPA (Eicosapentaenoic Acid)", 0, "NP"),
            _row(2, "Docosahexaenoic Acid", "fatty acid", "DHA (Docosahexaenoic Acid)", 0, "NP"),
        ]),
    ]))
    display = _display(fish)
    assert display["Total Omega-3 Fatty Acids"]["display_type"] == "summary_wrapper"
    assert display["Total Fat"]["display_type"] == "nutrition_fact"
    assert display["Calories"]["display_type"] == "nutrition_fact"

    curcumin = normalizer.normalize_product(_label("307577", "Curcumin 95 500 mg", [
        _row(1, "Turmeric Rhizome Extract", "botanical", "Turmeric", 500, "mg", nested=[
            _row(1, "Total Curcuminoids", "non-nutrient/non-botanical", "Curcuminoids", 475, "mg"),
        ]),
    ]))
    assert _display(curcumin)["Total Curcuminoids"]["display_type"] == "summary_wrapper"
    # A total is not a proprietary blend.
    assert curcumin["label_ledger_audit"]["source_structure"] == "botanical_plant_part_extract"


def test_fat_category_supplements_stay_actives(normalizer):
    # The fat-category allowlist was a no-op: these rows survive on their names alone.
    cleaned = normalizer.normalize_product(_label("rc2_fat_actives", "Fat-class actives", [
        _row(1, "Phosphatidylserine", "fat", "Phosphatidylserine", 300, "mg"),
        _row(2, "MCT Oil", "fat", "Medium Chain Triglycerides (MCT)", 10, "Gram(s)"),
        _row(3, "Krill Oil", "fat", "Krill Oil", 1, "Gram(s)"),
    ]))
    assert {row["name"] for row in cleaned["activeIngredients"]} >= {"Phosphatidylserine", "MCT Oil", "Krill Oil"}


def test_rollups_are_a_subset_of_the_exclusions_and_exclude_panel_totals():
    assert LABEL_ROLLUP_NAMES < EXCLUDED_NUTRITION_FACTS
    for panel_total in ("total fat", "total carbohydrates", "total sugars", "total protein", "total calories"):
        assert panel_total in EXCLUDED_NUTRITION_FACTS and panel_total not in LABEL_ROLLUP_NAMES
    assert {"total omega-3 fatty acids", "total lacto cultures", "total curcuminoids", "epa + dha"} <= LABEL_ROLLUP_NAMES
