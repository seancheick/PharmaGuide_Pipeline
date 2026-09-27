"""A printed 0% Daily Value survives cleaning (register Q23, Sean 2026-09-26).

The cleaner dropped a printed 0% (`if dv:` skipped 0.0) and turned a missing
percent into 0.0, so a nutrition-panel "Vitamin A 0%" row looked like an
ingredient listed without an amount. dailyValue now keeps the three states apart:
a printed percent (0 included), or None when the label printed none. The shared
presence rule reads it instead of guessing from the nutrient category.
"""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from enhanced_normalizer import EnhancedDSLDNormalizer  # noqa: E402
from identity.interaction import label_row_establishes_presence  # noqa: E402


def _row(order, name, category, dv_groups):
    return {"order": order, "ingredientId": 1000 + order, "name": name, "category": category,
            "ingredientGroup": name, "nestedRows": [], "alternateNames": [], "forms": [],
            "quantity": [{"servingSizeOrder": 1, "servingSizeQuantity": 35.5, "operator": "=",
                          "quantity": 0, "unit": "NP", "dailyValueTargetGroup": dv_groups,
                          "servingSizeUnit": "Gram(s)"}]}


def _group(percent):
    return [{"name": "Adults and children 4 or more years of age", "operator": "=",
             "percent": percent, "footnote": None}]


def test_printed_zero_percent_is_kept_and_reads_as_absent():
    raw = {"id": 990001, "fullName": "Test Protein", "brandName": "Test",
           "ingredientRows": [
               _row(1, "Vitamin A", "vitamin", _group(0)),
               _row(2, "Calcium", "mineral", _group(13)),
               _row(3, "Vitamin B12", "vitamin", []),
               _row(4, "Vitamin K", "vitamin", _group(None)),
           ],
           "otheringredients": {"text": None, "ingredients": []},
           "servingSizes": [{"order": 1, "minQuantity": 35.5, "maxQuantity": 35.5,
                             "minDailyServings": 1, "maxDailyServings": 1, "unit": "Gram(s)"}]}
    cleaned = EnhancedDSLDNormalizer().normalize_product(raw)
    rows = {r["name"]: r for r in cleaned["activeIngredients"]}
    assert rows["Vitamin A"]["dailyValue"] == 0.0
    assert rows["Calcium"]["dailyValue"] == 13.0
    assert rows["Vitamin B12"]["dailyValue"] is None
    assert rows["Vitamin K"]["dailyValue"] is None
    assert label_row_establishes_presence(rows["Vitamin A"]) is False
    assert label_row_establishes_presence(rows["Vitamin B12"]) is True


def test_enriched_rows_carry_daily_value_to_the_fingerprint():
    from enrich_supplements_v3 import SupplementEnricherV3
    from build_final_db import generate_ingredient_fingerprint

    raw = {"id": 990002, "fullName": "Test Protein", "brandName": "Test",
           "ingredientRows": [
               {"order": 1, "ingredientId": 2001, "name": "Protein", "category": "protein",
                "ingredientGroup": "Protein (unspecified)", "nestedRows": [], "alternateNames": [], "forms": [],
                "quantity": [{"servingSizeOrder": 1, "servingSizeQuantity": 35.5, "operator": "=",
                              "quantity": 24, "unit": "Gram(s)", "dailyValueTargetGroup": [],
                              "servingSizeUnit": "Gram(s)"}]},
               _row(2, "Vitamin A", "vitamin", _group(0)),
               _row(3, "Vitamin B12", "vitamin", []),
           ],
           "otheringredients": {"text": None, "ingredients": []},
           "servingSizes": [{"order": 1, "minQuantity": 35.5, "maxQuantity": 35.5,
                             "minDailyServings": 1, "maxDailyServings": 1, "unit": "Gram(s)"}]}
    cleaned = EnhancedDSLDNormalizer().normalize_product(raw)
    enriched, _ = SupplementEnricherV3().enrich_product(cleaned)
    rows = {r.get("name"): r for r in enriched["ingredient_quality_data"]["ingredients"]}
    assert rows["Vitamin A"]["dailyValue"] == 0.0
    fp = generate_ingredient_fingerprint(enriched)
    ids = set(fp["nutrients"]) | set(fp["herbs"])
    assert not any(i.startswith("vitamin_a") for i in ids)
    assert any(i.startswith("vitamin_b12") for i in ids)
