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


def test_a_real_blend_wrapper_still_marks_a_proprietary_blend(normalizer):
    # DSLD 232129 "Pomegranate Complete": the blend parent is a summary wrapper too, but it
    # is a proprietary blend; only label totals stop counting as one.
    cleaned = normalizer.normalize_product(_label("232129", "Pomegranate Complete", [
        _row(1, "Pomella Pomegranate extract", "botanical", "Pomegranate", 400, "mg",
             forms=[{"order": 1, "name": "Punicalagins"}]),
        _row(2, "Proprietary Pomegranate Blend", "botanical", "Pomegranate", 137.5, "mg",
             forms=[{"order": 1, "name": "Punicic Acid"}], nested=[
                 _row(1, "Pomegranate flower extract", "botanical", "Pomegranate", 0, "NP"),
                 _row(2, "Pomegranate seed Oil", "fat", "Pomegranate Oil", 0, "NP"),
             ]),
    ]))
    assert _display(cleaned)["Proprietary Pomegranate Blend"]["display_type"] == "summary_wrapper"
    assert cleaned["label_ledger_audit"]["source_structure"] == "proprietary_blend"


def test_percent_only_mineral_does_not_type_a_protein_powder_as_a_mineral(normalizer, enricher):
    # DSLD 16872 "100% Casein Protein Vanilla": Calcium "50 %" is its only %DV mineral; with no
    # mass amount it is not a quantified dose, so it cannot make the product a single mineral.
    cleaned = normalizer.normalize_product(_label("16872", "100% Casein Protein Vanilla", [
        _row(1, "Calories", "other", "Calories", 150, "{Calories}"),
        _row(2, "Total Fat", "fat", "Fat (unspecified)", 1, "g", 2),
        _row(3, "Sodium", "mineral", "Sodium", 200, "mg", 8),
        _row(4, "Total Carbohydrates", "sugar", "Carbohydrate", 10, "g", 3),
        _row(5, "Protein", "protein", "Protein (unspecified)", 25, "g", 50),
        _row(6, "Vitamin A", "vitamin", "Vitamin A", 0, "%"),
        _row(7, "Calcium", "mineral", "Calcium", 50, "%"),
        _row(8, "Iron", "mineral", "Iron", 0, "%"),
    ]))
    enriched, _ = enricher.enrich_product(cleaned)
    assert "Calcium" in {row["name"] for row in enriched["activeIngredients"]}
    assert enriched["supplement_taxonomy"]["primary_type"] != "single_mineral"


def _alert_hits(enriched, canonical_id):
    for alert in enriched["interaction_profile"]["ingredient_alerts"]:
        if (alert.get("subject_ref") or {}).get("canonical_id") == canonical_id:
            return alert
    raise AssertionError(f"no interaction alert for {canonical_id}")


def _calcium_label(amount, unit):
    return _label("rc2_calcium", "Calcium Test Powder", [
        _row(1, "Protein", "protein", "Protein (unspecified)", 25, "g", 50),
        _row(2, "Calcium", "mineral", "Calcium", amount, unit),
    ])


def test_unknown_calcium_amount_reads_as_cannot_assess_not_the_heart_risk(normalizer, enricher):
    # Sean, 2026-10-19: an unknown amount means "review / can't assess", never an asserted
    # risk. The heart-disease caution is dose-dependent (> 1,000 mg/day).
    enriched, _ = enricher.enrich_product(normalizer.normalize_product(_calcium_label(6, "%")))
    heart = next(hit for hit in _alert_hits(enriched, "calcium")["condition_hits"]
                 if hit["condition_id"] == "heart_disease")
    assert heart["dose_decision"]["evaluation_status"] == "amount_unknown"
    assert heart["dose_decision"]["consumer_disposition"] == "review"
    assert heart["alert_headline"] == "Calcium amount unclear — check with your clinician"
    assert "can't tell whether" in heart["alert_body"]
    assert "modest increase in cardiovascular events" not in heart["alert_body"]


def test_known_calcium_amounts_keep_their_threshold_outcome(normalizer, enricher):
    high, _ = enricher.enrich_product(normalizer.normalize_product(_calcium_label(1200, "mg")))
    heart = next(hit for hit in _alert_hits(high, "calcium")["condition_hits"]
                 if hit["condition_id"] == "heart_disease")
    assert heart["alert_headline"] == "Supplemental calcium — review with clinician"
    low, _ = enricher.enrich_product(normalizer.normalize_product(_calcium_label(200, "mg")))
    heart = next(hit for hit in _alert_hits(low, "calcium")["condition_hits"]
                 if hit["condition_id"] == "heart_disease")
    assert heart["dose_decision"]["consumer_disposition"] == "suppress"


def test_iron_pregnancy_entry_is_sourced_not_limited_data():
    # NIH ODS Iron fact sheet (updated 2025-09-04): pregnancy RDA 27 mg, lactation 9-10 mg,
    # adult UL 45 mg including pregnancy and lactation. "Limited safety data" was wrong.
    import json
    rules = json.loads((Path(__file__).parent.parent / "data" / "ingredient_interaction_rules.json").read_text())
    block = next(rule for rule in rules["interaction_rules"]
                 if rule["id"] == "RULE_IQM_IRON_HYPERTENSION")["pregnancy_lactation"]
    assert (block["pregnancy_category"], block["lactation_category"], block["evidence_level"]) == (
        "monitor", "monitor", "established")
    assert block["sources"] == ["https://ods.od.nih.gov/factsheets/Iron-HealthProfessional/"]
    assert "Limited safety data" not in json.dumps(block)
    assert block["profile_gate"]["requires"]["profile_flags_any"] == ["pregnant", "breastfeeding"]
