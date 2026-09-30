"""A printed 0% Daily Value survives cleaning (register Q23, Sean 2026-09-26).

The cleaner dropped a printed 0% (`if dv:` skipped 0.0) and turned a missing
percent into 0.0, so a nutrition-panel "Vitamin A 0%" row looked like an
ingredient listed without an amount. dailyValue now keeps the three states apart:
a printed percent (0 included), or None when the label printed none. The shared
presence rule reads it instead of guessing from the nutrient category.
"""

from __future__ import annotations

import copy
import json
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


def _serving_variant(order, serving_quantity, amount, percent):
    groups = [] if percent is None else _group(percent)
    return {
        "servingSizeOrder": order,
        "servingSizeQuantity": serving_quantity,
        "operator": "=",
        "quantity": amount,
        "unit": "mg",
        "dailyValueTargetGroup": groups,
        "servingSizeUnit": "Tablet(s)",
    }


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


def test_daily_value_reaches_the_canonical_display_ledger_without_changing_scores(tmp_path):
    """Printed numeric and zero %DV survive the production export boundary."""
    from build_final_db import build_final_db
    from enrich_supplements_v3 import SupplementEnricherV3
    from scoring_v4.scored_artifact import build_scored_artifact

    raw = {
        "id": 990003,
        "fullName": "Test Protein",
        "brandName": "Test",
        "productVersionCode": "1",
        "productType": {"langualCodeDescription": "Dietary Supplement"},
        "ingredientRows": [
            {
                "order": 1,
                "ingredientId": 2001,
                "name": "Protein",
                "category": "protein",
                "ingredientGroup": "Protein (unspecified)",
                "nestedRows": [],
                "alternateNames": [],
                "forms": [],
                "quantity": [{
                    "servingSizeOrder": 1,
                    "servingSizeQuantity": 35.5,
                    "operator": "=",
                    "quantity": 24,
                    "unit": "Gram(s)",
                    "dailyValueTargetGroup": [],
                    "servingSizeUnit": "Gram(s)",
                }],
            },
            _row(2, "Vitamin A", "vitamin", _group(0)),
            _row(3, "Calcium", "mineral", _group(13)),
            _row(4, "Sodium", "Amount Per Serving", _group(50)),
            _row(5, "Total Carbohydrate", "Amount Per Serving", _group(0)),
        ],
        "otheringredients": {"text": None, "ingredients": []},
        "servingSizes": [{
            "order": 1,
            "minQuantity": 35.5,
            "maxQuantity": 35.5,
            "minDailyServings": 1,
            "maxDailyServings": 1,
            "unit": "Gram(s)",
        }],
        "statements": [{"text": "Mix one serving daily."}],
    }

    cleaned = EnhancedDSLDNormalizer().normalize_product(raw)
    cleaned_display = {
        row["label_display_name"]: row
        for row in cleaned["display_ingredients"]
    }
    assert cleaned_display["Vitamin A"]["dailyValue"] == 0.0
    assert cleaned_display["Calcium"]["dailyValue"] == 13.0
    assert cleaned_display["Vitamin A"]["source_section"] == "activeIngredients"
    assert cleaned_display["Vitamin A"]["score_included"] is True
    assert "dailyValue" not in cleaned_display["Protein"]
    assert cleaned_display["Sodium"]["display_type"] == "nutrition_fact"
    assert cleaned_display["Sodium"]["dailyValue"] == 50.0
    assert cleaned_display["Sodium"]["source_section"] == "activeIngredients"
    assert cleaned_display["Sodium"]["score_included"] is False
    assert cleaned_display["Total Carbohydrate"]["display_type"] == "nutrition_fact"
    assert cleaned_display["Total Carbohydrate"]["dailyValue"] == 0.0
    assert not any(row["name"] == "Sodium" for row in cleaned["activeIngredients"])

    enriched, warnings = SupplementEnricherV3().enrich_product(cleaned)
    assert warnings == []
    scored = build_scored_artifact(enriched)

    without_display_dv = copy.deepcopy(cleaned)
    for row in without_display_dv["display_ingredients"]:
        row.pop("dailyValue", None)
    baseline_enriched, baseline_warnings = SupplementEnricherV3().enrich_product(
        without_display_dv
    )
    assert baseline_warnings == []
    baseline_scored = build_scored_artifact(baseline_enriched)
    scored["scoring_metadata"].pop("scored_date")
    baseline_scored["scoring_metadata"].pop("scored_date")
    assert scored == baseline_scored

    enriched_dir = tmp_path / "enriched"
    scored_dir = tmp_path / "scored"
    output_dir = tmp_path / "output"
    enriched_dir.mkdir()
    scored_dir.mkdir()
    (enriched_dir / "batch.json").write_text(
        json.dumps([enriched]), encoding="utf-8"
    )
    (scored_dir / "batch.json").write_text(
        json.dumps([scored]), encoding="utf-8"
    )

    result = build_final_db(
        [str(enriched_dir)],
        [str(scored_dir)],
        str(output_dir),
        str(SCRIPTS),
    )
    assert result["product_count"] == 1
    assert result["error_count"] == 0

    blob = json.loads(
        (output_dir / "detail_blobs" / "990003.json").read_text(encoding="utf-8")
    )
    exported_display = {
        row["label_display_name"]: row
        for row in blob["display_ingredients"]
    }
    assert exported_display["Vitamin A"]["dailyValue"] == 0.0
    assert exported_display["Calcium"]["dailyValue"] == 13.0
    assert exported_display["Sodium"]["dailyValue"] == 50.0
    assert exported_display["Total Carbohydrate"]["dailyValue"] == 0.0


def test_queued_daily_value_uses_the_same_canonical_serving_as_its_dose(tmp_path):
    """A canonical two-tablet DV cannot ship beside the one-tablet dose."""
    from build_final_db import build_final_db
    from enrich_supplements_v3 import SupplementEnricherV3
    from scoring_v4.scored_artifact import build_scored_artifact

    def nutrition_row(order, name, first_percent, canonical_percent):
        return {
            "order": order,
            "ingredientId": 3000 + order,
            "name": name,
            "category": "Amount Per Serving",
            "ingredientGroup": name,
            "nestedRows": [],
            "alternateNames": [],
            "forms": [],
            "quantity": [
                _serving_variant(1, 1, 100, first_percent),
                _serving_variant(2, 2, 200, canonical_percent),
            ],
        }

    raw = {
        "id": 990004,
        "fullName": "Test Protein",
        "brandName": "Test",
        "productVersionCode": "1",
        "productType": {"langualCodeDescription": "Dietary Supplement"},
        "ingredientRows": [
            {
                "order": 0,
                "ingredientId": 3000,
                "name": "Protein",
                "category": "protein",
                "ingredientGroup": "Protein (unspecified)",
                "nestedRows": [],
                "alternateNames": [],
                "forms": [],
                "quantity": [{
                    "servingSizeOrder": 2,
                    "servingSizeQuantity": 2,
                    "operator": "=",
                    "quantity": 24,
                    "unit": "Gram(s)",
                    "dailyValueTargetGroup": [],
                    "servingSizeUnit": "Tablet(s)",
                }],
            },
            nutrition_row(1, "Sodium", 4, 9),
            nutrition_row(2, "Cholesterol", 2, 0),
            nutrition_row(3, "Total Carbohydrate", 1, None),
        ],
        "otheringredients": {"text": None, "ingredients": []},
        "servingSizes": [{
            "order": 2,
            "minQuantity": 2,
            "maxQuantity": 2,
            "minDailyServings": 1,
            "maxDailyServings": 1,
            "unit": "Tablet(s)",
        }],
        "statements": [{"text": "Take two tablets daily."}],
    }

    cleaned = EnhancedDSLDNormalizer().normalize_product(raw)
    rows = {
        row["label_display_name"]: row
        for row in cleaned["display_ingredients"]
    }
    sodium = rows["Sodium"]
    assert sodium["display_type"] == "nutrition_fact"
    assert sodium["dailyValue"] == 9.0
    assert sodium["exact_dose_text"] == ""
    assert sodium["serving_variants"] == [
        {
            "serving_size_order": 1,
            "serving_size_quantity": 1,
            "serving_size_unit": "tablets",
            "exact_dose_text": "100 mg",
            "is_canonical": False,
        },
        {
            "serving_size_order": 2,
            "serving_size_quantity": 2,
            "serving_size_unit": "tablets",
            "exact_dose_text": "200 mg",
            "is_canonical": True,
        },
    ]
    assert rows["Cholesterol"]["dailyValue"] == 0.0
    assert "dailyValue" not in rows["Total Carbohydrate"]

    enriched, warnings = SupplementEnricherV3().enrich_product(cleaned)
    assert warnings == []
    scored = build_scored_artifact(enriched)

    enriched_dir = tmp_path / "enriched"
    scored_dir = tmp_path / "scored"
    output_dir = tmp_path / "output"
    enriched_dir.mkdir()
    scored_dir.mkdir()
    (enriched_dir / "batch.json").write_text(
        json.dumps([enriched]), encoding="utf-8"
    )
    (scored_dir / "batch.json").write_text(
        json.dumps([scored]), encoding="utf-8"
    )
    result = build_final_db(
        [str(enriched_dir)],
        [str(scored_dir)],
        str(output_dir),
        str(SCRIPTS),
    )
    assert result["product_count"] == 1
    assert result["error_count"] == 0

    blob = json.loads(
        (output_dir / "detail_blobs" / "990004.json").read_text(encoding="utf-8")
    )
    exported = {
        row["label_display_name"]: row
        for row in blob["display_ingredients"]
    }
    assert exported["Sodium"]["dailyValue"] == 9.0
    assert exported["Sodium"]["exact_dose_text"] == ""
    assert exported["Sodium"]["serving_variants"][1]["exact_dose_text"] == "200 mg"
    assert exported["Sodium"]["serving_variants"][1]["is_canonical"] is True
    assert exported["Cholesterol"]["dailyValue"] == 0.0
    assert "dailyValue" not in exported["Total Carbohydrate"]
