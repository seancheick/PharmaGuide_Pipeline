"""A protein powder is typed by its protein identity (2026-10-19).

Its protein total is a Nutrition Facts row, correctly excluded from scoring rows, so the taxonomy
never saw it. A Potassium (mg) panel row then typed GNC whey powders as single_mineral (DSLD
16839-16866), and 16730 "Isolated Soy Protein" had no row left (general_supplement). The protein
identity comes from the same pair the router uses: protein title intent
(route_features.has_protein_product_intent) plus declared Nutrition Facts protein grams
(nutrition_summary.protein_g). Nutrition Facts macros never become actives.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from enhanced_normalizer import EnhancedDSLDNormalizer
from enrich_supplements_v3 import SupplementEnricherV3


def _qty(amount, unit, percent=None):
    groups = [] if percent is None else [{"name": "Adults and children 4 or more years of age",
                                          "operator": "=", "percent": percent, "footnote": None}]
    return [{"servingSizeOrder": 1, "servingSizeQuantity": 28, "operator": "=", "quantity": amount,
             "unit": unit, "dailyValueTargetGroup": groups, "servingSizeUnit": "Gram(s)"}]


def _row(order, name, category, group, amount, unit, percent=None):
    return {"order": order, "name": name, "category": category, "ingredientGroup": group,
            "quantity": _qty(amount, unit, percent), "forms": [], "nestedRows": []}


def _label(label_id, name, rows, product_type="Amino acid/Protein"):
    return {"id": label_id, "fullName": name, "brandName": "GNC", "productVersionCode": "1",
            "productType": {"langualCode": "A1305", "langualCodeDescription": product_type},
            "servingSizes": [{"order": 1, "minQuantity": 28, "maxQuantity": 28, "minDailyServings": 1,
                              "maxDailyServings": 3, "unit": "Gram(s)", "inSFB": True}],
            "ingredientRows": rows, "otheringredients": {"ingredients": []}}


@pytest.fixture(scope="module")
def pipeline():
    normalizer, enricher = EnhancedDSLDNormalizer(), SupplementEnricherV3()

    def run(label):
        enriched, _ = enricher.enrich_product(normalizer.normalize_product(label))
        return enriched["supplement_taxonomy"]

    return run


def _panel(protein_g, mineral_name="Potassium", mineral_mg=400):
    return [
        _row(1, "Calories", "other", "Calories", 100, "{Calories}"),
        _row(2, "Total Fat", "fat", "Fat (unspecified)", 1.5, "g", 2),
        _row(3, "Sodium", "mineral", "Sodium", 250, "mg", 10),
        _row(4, mineral_name, "mineral", mineral_name, mineral_mg, "mg", 12),
        _row(5, "Total Carbohydrates", "sugar", "Carbohydrate", 6, "g", 11),
        _row(6, "Protein", "protein", "Protein (unspecified)", protein_g, "g"),
        _row(7, "Calcium", "mineral", "Calcium", 6, "%"),
        _row(8, "Iron", "mineral", "Iron", 10, "%"),
    ]


def test_whey_powder_with_a_potassium_panel_row_is_a_protein_powder(pipeline):
    # DSLD 16839 "Whey Protein Complex Powdered Drink Mix Chocolate" (DSLD productType says MVM).
    taxonomy = pipeline(_label("16839", "Whey Protein Complex Powdered Drink Mix Chocolate",
                               _panel(17), product_type="Multi-Vitamin and Mineral (MVM)"))
    assert taxonomy["primary_type"] == "protein_powder"
    assert "declared_nutrition_protein_product" in taxonomy["classification_reason_codes"]


def test_soy_protein_with_no_quantified_active_is_a_protein_powder(pipeline):
    # DSLD 16730 "Isolated Soy Protein 95 Chocolate": Protein 25 g, %DV-only micronutrients.
    taxonomy = pipeline(_label("16730", "Isolated Soy Protein 95 Chocolate", [
        _row(1, "Calories", "other", "Calories", 130, "{Calories}"),
        _row(2, "Protein", "protein", "Protein (unspecified)", 25, "g", 50),
        _row(3, "Vitamin A", "vitamin", "Vitamin A", 10, "%"),
        _row(4, "Calcium", "mineral", "Calcium", 6, "%"),
        _row(5, "Iron", "mineral", "Iron", 30, "%"),
    ]))
    assert taxonomy["primary_type"] == "protein_powder"


def test_protein_in_the_title_without_declared_protein_grams_does_not_retype(pipeline):
    # Title intent alone never selects the type (route_features contract).
    taxonomy = pipeline(_label("rc_ctl_1", "Protein Support Magnesium",
                               [_row(1, "Magnesium", "mineral", "Magnesium", 400, "mg", 95)],
                               product_type="Mineral"))
    assert taxonomy["primary_type"] == "single_mineral"


def test_panel_protein_without_protein_title_intent_does_not_retype(pipeline):
    # A mineral product whose panel shows incidental protein stays a mineral.
    taxonomy = pipeline(_label("rc_ctl_2", "Potassium 99 mg", _panel(1), product_type="Mineral"))
    assert taxonomy["primary_type"] == "single_mineral"


# Audit F1 (2026-10-20): the declared-protein identity never overrides another identity the
# title or rows name. Real titles, each with protein title intent and declared protein grams.
@pytest.mark.parametrize("label_id,title,protein_g,rows,expected", [
    ("12054", "Calcium + Vitamin D with Collagen Protein", 2,
     [_row(1, "Calcium", "mineral", "Calcium", 600, "mg", 46),
      _row(2, "Vitamin D3", "vitamin", "Vitamin D", 25, "mcg", 125)], None),
    ("230141", "Collagen Protein Peptides", 9,
     [_row(1, "Hydrolyzed Collagen", "protein", "Collagen", 10, "g")], "collagen"),
    ("17226", "Super Greens + Plant Protein", 5,
     [_row(1, "Spirulina", "botanical", "Spirulina", 1, "g"),
      _row(2, "Wheat Grass", "botanical", "Wheat Grass", 1, "g")], None),
    ("1024", "Fish Oil with Whey", 1,
     [_row(1, "EPA (Eicosapentaenoic Acid)", "fatty acid", "EPA (Eicosapentaenoic Acid)", 180, "mg"),
      _row(2, "DHA (Docosahexaenoic Acid)", "fatty acid", "DHA (Docosahexaenoic Acid)", 120, "mg")], None),
    ("2722", "Pre-Workout Protein", 3,
     [_row(1, "Caffeine", "non-nutrient/non-botanical", "Caffeine", 150, "mg"),
      _row(2, "Beta-Alanine", "amino acid", "Beta-Alanine", 2, "g")], None),
    ("12052", "Prenatal with Protein", 1,
     [_row(1, "Folate", "vitamin", "Folate", 400, "mcg", 100),
      _row(2, "Iron", "mineral", "Iron", 27, "mg", 150),
      _row(3, "Iodine", "mineral", "Iodine", 150, "mcg", 100)], None),
    ("259374", "Organic Hemp Powder Protein & Fiber", 11,
     [_row(1, "Hemp Seed Powder", "botanical", "Hemp", 30, "g")], None),
    ("327398", "Grass Fed Collagen Protein", 9,
     [_row(1, "Bovine Collagen Peptides", "protein", "Collagen", 10, "g")], "collagen"),
])
def test_declared_protein_never_overrides_another_identity(pipeline, label_id, title, protein_g, rows, expected):
    taxonomy = pipeline(_label(label_id, title,
                               [_row(0, "Protein", "protein", "Protein (unspecified)", protein_g, "g")] + rows,
                               product_type="Other"))
    assert taxonomy["primary_type"] != "protein_powder", taxonomy["classification_reasons"]
    assert "declared_nutrition_protein_product" not in taxonomy["classification_reason_codes"]
    if expected:
        assert taxonomy["primary_type"] == expected


def test_gainer_with_a_vitamin_panel_is_typed_like_other_gainers(pipeline):
    # Audit F5: "Dynamic Gainer" (50 g) stayed multivitamin through the B-complex-extras rule while
    # "Complete Vegan Gainer" moved. The declared-protein identity is an R5 specialized panel and
    # runs before B-complex/multivitamin, like the pre-workout and electrolyte panels.
    vitamins = [
        _row(i + 1, name, "vitamin", group, amount, unit, 100)
        for i, (name, group, amount, unit) in enumerate([
            ("Thiamin", "Thiamin", 1.5, "mg"), ("Riboflavin", "Riboflavin", 1.7, "mg"),
            ("Niacin", "Niacin", 20, "mg"), ("Vitamin B6", "Vitamin B6", 2, "mg"),
            ("Vitamin B12", "Vitamin B12", 6, "mcg"), ("Pantothenic Acid", "Pantothenic Acid", 10, "mg"),
            ("Vitamin C", "Vitamin C", 60, "mg"),
        ])
    ]
    # The real label's protein blend also lists collagen; one blend ingredient is not the identity.
    collagen = [_row(20, "Collagen", "protein", "Collagen", 1, "g")]
    taxonomy = pipeline(_label("318103", "Dynamic Gainer Chocolate",
                               [_row(0, "Protein", "protein", "Protein (unspecified)", 50, "g")] + vitamins + collagen))
    assert taxonomy["primary_type"] == "protein_powder"
