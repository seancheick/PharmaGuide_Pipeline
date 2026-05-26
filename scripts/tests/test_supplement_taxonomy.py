"""
Regression tests for supplement_taxonomy.py

Tests use real-world product patterns from Paradise, Nature Made, Thorne, etc.
to verify classification accuracy for the canonical taxonomy.

Key invariants:
  - NP/zero-potency ingredients MUST NOT influence primary_type
  - Single-ingredient products MUST NOT be classified as herbal_blend
  - Multivitamins with 3+ vitamins + 3+ minerals MUST be multivitamin
  - B-Complex products MUST be b_complex, not multivitamin
  - percentile_category MUST derive from primary_type
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from supplement_taxonomy import classify_supplement, _is_non_quantified


# ============================================================================
# NP / Zero-Potency Filtering
# ============================================================================

class TestNPFiltering:
    """NP and zero-potency ingredients must be excluded from classification."""

    def test_zero_quantity_is_non_quantified(self):
        assert _is_non_quantified({"quantity": 0, "unit": "mg"}) is True

    def test_zero_float_is_non_quantified(self):
        assert _is_non_quantified({"quantity": 0.0, "unit": "mg"}) is True

    def test_np_unit_is_non_quantified(self):
        assert _is_non_quantified({"quantity": 100, "unit": "NP"}) is True

    def test_empty_unit_no_qty_is_non_quantified(self):
        assert _is_non_quantified({"unit": ""}) is True

    def test_normal_ingredient_is_quantified(self):
        assert _is_non_quantified({"quantity": 30, "unit": "mg"}) is False

    def test_mcg_ingredient_is_quantified(self):
        assert _is_non_quantified({"quantity": 300, "unit": "mcg"}) is False


# ============================================================================
# Paradise Brand — NP base filtering + correct classification
# ============================================================================

class TestParadisePatterns:
    """Paradise Herbs products with 40+ NP base ingredients."""

    @staticmethod
    def _paradise_product(name, quantified_actives, np_herbs=40):
        """Build a Paradise-like product with NP base."""
        iqd_rows = []
        for active in quantified_actives:
            iqd_rows.append({
                "name": active["name"],
                "canonical_id": active.get("cid", ""),
                "category": active.get("cat", ""),
                "quantity": active.get("qty", 30),
                "unit": active.get("unit", "mg"),
                "role_classification": "active_scorable",
            })
        # Add NP herbs (Paradise whole-food base pattern)
        herb_names = [
            "Ashwagandha Root Extract", "Rhodiola Root Extract",
            "Holy Basil Leaf Extract", "Astragalus Root Extract",
            "Schisandra Berry Extract", "Licorice Root Extract",
            "Ginger Rhizome Extract", "Reishi Extract",
            "Cordyceps Extract", "Maitake Extract",
        ]
        for i in range(np_herbs):
            iqd_rows.append({
                "name": herb_names[i % len(herb_names)],
                "canonical_id": "",
                "category": "herb",
                "quantity": 0,
                "unit": "NP",
                "role_classification": "active_scorable",
            })
        return {
            "product_name": name,
            "fullName": name,
            "ingredient_quality_data": {"ingredients": iqd_rows},
            "activeIngredients": [],
        }

    def test_zinc_picolinate_not_herbal_blend(self):
        """Paradise Zinc Picolinate 30mg must be single_mineral, not herbal_blend."""
        p = self._paradise_product("Zinc Picolinate 30 mg", [
            {"name": "Zinc", "cid": "zinc", "cat": "mineral", "qty": 30, "unit": "mg"},
        ])
        result = classify_supplement(p)
        assert result["primary_type"] == "single_mineral"
        assert result["secondary_type"] == "zinc"
        assert result["percentile_category"] == "single_mineral"
        assert result["non_quantified_base_count"] == 40

    def test_biotin_is_single_vitamin(self):
        """Paradise Biotin 10,000 mcg must be single_vitamin."""
        p = self._paradise_product("Biotin 10,000 mcg", [
            {"name": "Biotin", "cid": "biotin", "cat": "vitamin", "qty": 10000, "unit": "mcg"},
        ])
        result = classify_supplement(p)
        assert result["primary_type"] == "single_vitamin"
        assert result["secondary_type"] == "biotin"

    def test_quercetin_is_herbal_botanical(self):
        """Paradise Quercetin must be herbal_botanical (antioxidant flavonoid)."""
        p = self._paradise_product("Quercetin", [
            {"name": "Quercetin", "cid": "quercetin", "cat": "antioxidant", "qty": 500, "unit": "mg"},
        ])
        result = classify_supplement(p)
        assert result["primary_type"] == "herbal_botanical"
        assert result["secondary_type"] == "quercetin"

    def test_vitamin_d3_k2_is_single_vitamin(self):
        """Paradise Vitamin D3 + K2 is a vitamin combo."""
        p = self._paradise_product("Vitamin D3 + K2", [
            {"name": "Vitamin D3", "cid": "vitamin_d", "cat": "vitamin", "qty": 5000, "unit": "IU"},
            {"name": "Vitamin K2", "cid": "vitamin_k", "cat": "vitamin", "qty": 90, "unit": "mcg"},
        ])
        result = classify_supplement(p)
        assert result["primary_type"] == "single_vitamin"
        assert result["secondary_type"] == "vitamin_d"


# ============================================================================
# Single Vitamin Products
# ============================================================================

class TestSingleVitamins:
    """Single-vitamin products must classify correctly."""

    def test_vitamin_d3_1000iu(self):
        p = {
            "product_name": "Vitamin D3 1000 IU",
            "ingredient_quality_data": {"ingredients": [
                {"name": "Vitamin D3", "canonical_id": "vitamin_d", "category": "vitamin",
                 "quantity": 1000, "unit": "IU"},
            ]},
        }
        result = classify_supplement(p)
        assert result["primary_type"] == "single_vitamin"
        assert result["secondary_type"] == "vitamin_d"
        assert result["percentile_category"] == "single_vitamin"

    def test_vitamin_c_500mg(self):
        p = {
            "product_name": "Vitamin C 500 mg",
            "ingredient_quality_data": {"ingredients": [
                {"name": "Vitamin C", "canonical_id": "vitamin_c", "category": "vitamin",
                 "quantity": 500, "unit": "mg"},
            ]},
        }
        result = classify_supplement(p)
        assert result["primary_type"] == "single_vitamin"
        assert result["secondary_type"] == "vitamin_c"


# ============================================================================
# Single Mineral Products
# ============================================================================

class TestSingleMinerals:
    """Single-mineral products must not be herbal_blend or multivitamin."""

    def test_magnesium_glycinate(self):
        p = {
            "product_name": "Magnesium Glycinate 400 mg",
            "ingredient_quality_data": {"ingredients": [
                {"name": "Magnesium", "canonical_id": "magnesium", "category": "mineral",
                 "quantity": 400, "unit": "mg"},
            ]},
        }
        result = classify_supplement(p)
        assert result["primary_type"] == "single_mineral"
        assert result["secondary_type"] == "magnesium"

    def test_iron_bisglycinate(self):
        p = {
            "product_name": "Iron Bisglycinate 25 mg",
            "ingredient_quality_data": {"ingredients": [
                {"name": "Iron", "canonical_id": "iron", "category": "mineral",
                 "quantity": 25, "unit": "mg"},
            ]},
        }
        result = classify_supplement(p)
        assert result["primary_type"] == "single_mineral"
        assert result["secondary_type"] == "iron"


# ============================================================================
# B-Complex
# ============================================================================

class TestBComplex:
    """B-complex products must not be classified as multivitamin."""

    def test_b_complex_basic(self):
        p = {
            "product_name": "B-Complex",
            "ingredient_quality_data": {"ingredients": [
                {"name": "Vitamin B1", "canonical_id": "vitamin_b1", "category": "vitamin", "quantity": 25, "unit": "mg"},
                {"name": "Vitamin B2", "canonical_id": "vitamin_b2", "category": "vitamin", "quantity": 25, "unit": "mg"},
                {"name": "Vitamin B3", "canonical_id": "vitamin_b3", "category": "vitamin", "quantity": 50, "unit": "mg"},
                {"name": "Vitamin B5", "canonical_id": "vitamin_b5", "category": "vitamin", "quantity": 25, "unit": "mg"},
                {"name": "Vitamin B6", "canonical_id": "vitamin_b6", "category": "vitamin", "quantity": 25, "unit": "mg"},
                {"name": "Vitamin B12", "canonical_id": "vitamin_b12", "category": "vitamin", "quantity": 1000, "unit": "mcg"},
                {"name": "Folate", "canonical_id": "folate", "category": "vitamin", "quantity": 400, "unit": "mcg"},
                {"name": "Biotin", "canonical_id": "biotin", "category": "vitamin", "quantity": 300, "unit": "mcg"},
            ]},
        }
        result = classify_supplement(p)
        assert result["primary_type"] == "b_complex"
        assert result["percentile_category"] == "b_complex"


# ============================================================================
# Multivitamin
# ============================================================================

class TestMultivitamin:
    """Multivitamins with vitamins + minerals must classify correctly."""

    def test_multivitamin_with_name_signal(self):
        p = {
            "product_name": "One Daily Superfood Multi-Vitamin with Iron",
            "ingredient_quality_data": {"ingredients": [
                {"name": "Vitamin A", "canonical_id": "vitamin_a", "category": "vitamin", "quantity": 5000, "unit": "IU"},
                {"name": "Vitamin C", "canonical_id": "vitamin_c", "category": "vitamin", "quantity": 100, "unit": "mg"},
                {"name": "Vitamin D3", "canonical_id": "vitamin_d", "category": "vitamin", "quantity": 1000, "unit": "IU"},
                {"name": "Vitamin E", "canonical_id": "vitamin_e", "category": "vitamin", "quantity": 30, "unit": "IU"},
                {"name": "Vitamin B6", "canonical_id": "vitamin_b6", "category": "vitamin", "quantity": 10, "unit": "mg"},
                {"name": "Folate", "canonical_id": "folate", "category": "vitamin", "quantity": 400, "unit": "mcg"},
                {"name": "Calcium", "canonical_id": "calcium", "category": "mineral", "quantity": 10, "unit": "mg"},
                {"name": "Iron", "canonical_id": "iron", "category": "mineral", "quantity": 6, "unit": "mg"},
                {"name": "Magnesium", "canonical_id": "magnesium", "category": "mineral", "quantity": 10, "unit": "mg"},
                {"name": "Zinc", "canonical_id": "zinc", "category": "mineral", "quantity": 10, "unit": "mg"},
                {"name": "Selenium", "canonical_id": "selenium", "category": "mineral", "quantity": 70, "unit": "mcg"},
                {"name": "Copper", "canonical_id": "copper", "category": "mineral", "quantity": 500, "unit": "mcg"},
            ]},
        }
        result = classify_supplement(p)
        assert result["primary_type"] == "multivitamin"
        assert result["classification_confidence"] >= 0.9

    def test_multivitamin_with_current_iqd_scorable_canonical_ids(self):
        """Current IQD emits suffixed B-vitamin IDs; taxonomy must consume them."""
        p = {
            "product_name": "One Daily Superfood Multi-Vitamin with Iron",
            "ingredient_quality_data": {"ingredients_scorable": [
                {"name": "Vitamin A", "canonical_id": "vitamin_a", "category": "vitamin", "quantity": 5000, "unit": "IU", "score_eligible_by_cleaner": True, "cleaner_row_role": "active_scorable", "role_classification": "active_scorable"},
                {"name": "Vitamin C", "canonical_id": "vitamin_c", "category": "vitamin", "quantity": 100, "unit": "mg", "score_eligible_by_cleaner": True, "cleaner_row_role": "active_scorable", "role_classification": "active_scorable"},
                {"name": "Vitamin D3", "canonical_id": "vitamin_d", "category": "vitamin", "quantity": 1000, "unit": "IU", "score_eligible_by_cleaner": True, "cleaner_row_role": "active_scorable", "role_classification": "active_scorable"},
                {"name": "Vitamin E", "canonical_id": "vitamin_e", "category": "vitamin", "quantity": 30, "unit": "IU", "score_eligible_by_cleaner": True, "cleaner_row_role": "active_scorable", "role_classification": "active_scorable"},
                {"name": "Vitamin K-2", "canonical_id": "vitamin_k", "category": "vitamin", "quantity": 80, "unit": "mcg", "score_eligible_by_cleaner": True, "cleaner_row_role": "active_scorable", "role_classification": "active_scorable"},
                {"name": "Vitamin B1", "canonical_id": "vitamin_b1_thiamine", "category": "vitamin", "quantity": 10, "unit": "mg", "score_eligible_by_cleaner": True, "cleaner_row_role": "active_scorable", "role_classification": "active_scorable"},
                {"name": "Vitamin B2", "canonical_id": "vitamin_b2_riboflavin", "category": "vitamin", "quantity": 10, "unit": "mg", "score_eligible_by_cleaner": True, "cleaner_row_role": "active_scorable", "role_classification": "active_scorable"},
                {"name": "Vitamin B-3", "canonical_id": "vitamin_b3_niacin", "category": "vitamin", "quantity": 20, "unit": "mg", "score_eligible_by_cleaner": True, "cleaner_row_role": "active_scorable", "role_classification": "active_scorable"},
                {"name": "Vitamin B-6", "canonical_id": "vitamin_b6_pyridoxine", "category": "vitamin", "quantity": 10, "unit": "mg", "score_eligible_by_cleaner": True, "cleaner_row_role": "active_scorable", "role_classification": "active_scorable"},
                {"name": "Folate", "canonical_id": "vitamin_b9_folate", "category": "vitamin", "quantity": 400, "unit": "mcg", "score_eligible_by_cleaner": True, "cleaner_row_role": "active_scorable", "role_classification": "active_scorable"},
                {"name": "Vitamin B12", "canonical_id": "vitamin_b12_cobalamin", "category": "vitamin", "quantity": 100, "unit": "mcg", "score_eligible_by_cleaner": True, "cleaner_row_role": "active_scorable", "role_classification": "active_scorable"},
                {"name": "Biotin", "canonical_id": "vitamin_b7_biotin", "category": "vitamin", "quantity": 300, "unit": "mcg", "score_eligible_by_cleaner": True, "cleaner_row_role": "active_scorable", "role_classification": "active_scorable"},
                {"name": "Calcium", "canonical_id": "calcium", "category": "mineral", "quantity": 10, "unit": "mg", "score_eligible_by_cleaner": True, "cleaner_row_role": "active_scorable", "role_classification": "active_scorable"},
                {"name": "Iron", "canonical_id": "iron", "category": "mineral", "quantity": 6, "unit": "mg", "score_eligible_by_cleaner": True, "cleaner_row_role": "active_scorable", "role_classification": "active_scorable"},
                {"name": "Magnesium", "canonical_id": "magnesium", "category": "mineral", "quantity": 10, "unit": "mg", "score_eligible_by_cleaner": True, "cleaner_row_role": "active_scorable", "role_classification": "active_scorable"},
                {"name": "Zinc", "canonical_id": "zinc", "category": "mineral", "quantity": 10, "unit": "mg", "score_eligible_by_cleaner": True, "cleaner_row_role": "active_scorable", "role_classification": "active_scorable"},
                {"name": "Selenium", "canonical_id": "selenium", "category": "mineral", "quantity": 70, "unit": "mcg", "score_eligible_by_cleaner": True, "cleaner_row_role": "active_scorable", "role_classification": "active_scorable"},
                {"name": "Copper", "canonical_id": "copper", "category": "mineral", "quantity": 500, "unit": "mcg", "score_eligible_by_cleaner": True, "cleaner_row_role": "active_scorable", "role_classification": "active_scorable"},
            ]},
        }
        result = classify_supplement(p)
        assert result["primary_type"] == "multivitamin"
        assert result["classification_input_source"] == "ingredient_quality_data.ingredients_scorable"


# ============================================================================
# Herbal / Botanical
# ============================================================================

class TestHerbalBotanical:
    """Herbal products must classify as herbal_botanical."""

    def test_ashwagandha_single(self):
        p = {
            "product_name": "Ashwagandha KSM-66",
            "ingredient_quality_data": {"ingredients": [
                {"name": "Ashwagandha", "canonical_id": "ashwagandha", "category": "herb",
                 "quantity": 600, "unit": "mg"},
            ]},
        }
        result = classify_supplement(p)
        assert result["primary_type"] == "herbal_botanical"
        assert result["secondary_type"] == "ashwagandha"

    def test_turmeric_curcumin(self):
        p = {
            "product_name": "Turmeric Curcumin 500 mg",
            "ingredient_quality_data": {"ingredients": [
                {"name": "Turmeric", "canonical_id": "turmeric", "category": "herb",
                 "quantity": 500, "unit": "mg"},
            ]},
        }
        result = classify_supplement(p)
        assert result["primary_type"] == "herbal_botanical"
        assert result["secondary_type"] == "turmeric_curcumin"


# ============================================================================
# Omega-3 / Fish Oil
# ============================================================================

class TestOmega3:
    """Fish oil and omega-3 products must classify correctly."""

    def test_fish_oil_epa_dha(self):
        p = {
            "product_name": "Ultimate Omega Fish Oil",
            "ingredient_quality_data": {"ingredients": [
                {"name": "EPA", "canonical_id": "epa", "category": "fatty_acid", "quantity": 650, "unit": "mg"},
                {"name": "DHA", "canonical_id": "dha", "category": "fatty_acid", "quantity": 450, "unit": "mg"},
            ]},
        }
        result = classify_supplement(p)
        assert result["primary_type"] == "omega_3"
        assert result["secondary_type"] == "fish_oil_epa_dha"
        assert result["percentile_category"] == "fish_oil"

    def test_algal_dha(self):
        p = {
            "product_name": "Algal-900 DHA",
            "ingredient_quality_data": {"ingredients": [
                {"name": "DHA", "canonical_id": "dha", "category": "fatty_acid", "quantity": 900, "unit": "mg"},
            ]},
        }
        result = classify_supplement(p)
        assert result["primary_type"] == "omega_3"


# ============================================================================
# Functional Categories (name-driven)
# ============================================================================

class TestFunctionalCategories:
    """Name-driven functional categories like sleep, immune, beauty."""

    def test_sleep_support(self):
        p = {
            "product_name": "Sleep Support Formula",
            "ingredient_quality_data": {"ingredients": [
                {"name": "Melatonin", "canonical_id": "melatonin", "category": "herb", "quantity": 3, "unit": "mg"},
                {"name": "L-Theanine", "canonical_id": "l_theanine", "category": "amino_acid", "quantity": 200, "unit": "mg"},
                {"name": "Magnesium", "canonical_id": "magnesium", "category": "mineral", "quantity": 200, "unit": "mg"},
            ]},
        }
        result = classify_supplement(p)
        assert result["primary_type"] == "sleep_support"

    def test_beauty_hair_skin_nails_biotin(self):
        p = {
            "product_name": "Hair Skin & Nails with Biotin",
            "ingredient_quality_data": {"ingredients": [
                {"name": "Biotin", "canonical_id": "biotin", "category": "vitamin", "quantity": 5000, "unit": "mcg"},
                {"name": "Vitamin C", "canonical_id": "vitamin_c", "category": "vitamin", "quantity": 60, "unit": "mg"},
                {"name": "Zinc", "canonical_id": "zinc", "category": "mineral", "quantity": 15, "unit": "mg"},
            ]},
        }
        result = classify_supplement(p)
        assert result["primary_type"] == "beauty_hair_skin_nails"


# ============================================================================
# Vitamin Mineral Combo
# ============================================================================

class TestVitaminMineralCombo:
    """Small combos like Cal-Mag-Zinc should not be multivitamin."""

    def test_cal_mag_zinc_d3(self):
        p = {
            "product_name": "Cal-Mag Zinc + D3",
            "ingredient_quality_data": {"ingredients": [
                {"name": "Calcium", "canonical_id": "calcium", "category": "mineral", "quantity": 500, "unit": "mg"},
                {"name": "Magnesium", "canonical_id": "magnesium", "category": "mineral", "quantity": 250, "unit": "mg"},
                {"name": "Zinc", "canonical_id": "zinc", "category": "mineral", "quantity": 15, "unit": "mg"},
                {"name": "Vitamin D3", "canonical_id": "vitamin_d", "category": "vitamin", "quantity": 600, "unit": "IU"},
            ]},
        }
        result = classify_supplement(p)
        assert result["primary_type"] == "vitamin_mineral_combo"
        assert result["percentile_category"] == "vitamin_mineral_combo"


def test_product_level_probiotic_metadata_does_not_hijack_non_probiotic_scorable_active():
    """Paradise-style base probiotic metadata must not classify Quercetin as probiotic."""
    product = {
        "product_name": "Quercetin",
        "probiotic_data": {
            "is_probiotic_product": True,
            "total_cfu": 90000000,
        },
        "ingredient_quality_data": {
            "ingredients_scorable": [
                {
                    "name": "Quercetin",
                    "canonical_id": "quercetin",
                    "category": "antioxidant",
                    "quantity": 500,
                    "unit": "mg",
                    "score_eligible_by_cleaner": True,
                    "cleaner_row_role": "active_scorable",
                    "role_classification": "active_scorable",
                }
            ],
            "ingredients_skipped": [
                {
                    "name": "Lactobacillus acidophilus",
                    "category": "probiotic",
                    "quantity": 0,
                    "unit": "NP",
                    "score_eligible_by_cleaner": False,
                    "cleaner_row_role": "nested_display_only",
                }
            ],
        },
    }
    result = classify_supplement(product)
    assert result["primary_type"] == "herbal_botanical"
    assert result["secondary_type"] == "quercetin"


def test_real_cfu_probiotic_with_no_scorable_strain_rows_is_still_probiotic():
    """A product-level CFU total is valid probiotic dose evidence for taxonomy."""
    product = {
        "product_name": "Daily Digestive Microbiome 20 Billion",
        "probiotic_data": {
            "is_probiotic_product": True,
            "total_cfu": 20000000000,
            "total_strain_count": 2,
        },
        "ingredient_quality_data": {
            "ingredients_scorable": [],
            "ingredients_skipped": [
                {
                    "name": "Proprietary Probiotic Blend",
                    "category": "probiotics",
                    "quantity": 95,
                    "unit": "mg",
                    "score_eligible_by_cleaner": False,
                    "cleaner_row_role": "blend_header_total",
                }
            ],
        },
    }
    result = classify_supplement(product)
    assert result["primary_type"] == "probiotic"
    assert "probiotic row identity + product-level CFU evidence" in result["classification_reasons"]


def test_real_cfu_probiotic_with_prebiotic_support_row_is_still_probiotic():
    """Prebiotic/fiber rows are support ingredients in probiotic formulas.
    They must not demote a product with real probiotic row identity + CFU
    evidence into general_supplement, because scoreable CFU evidence is only
    valid in the probiotic taxonomy peer class."""
    product = {
        "product_name": "Fortify Women's Probiotic 50 Billion",
        "fullName": "Fortify Women's Probiotic 50 Billion",
        "probiotic_data": {
            "is_probiotic_product": True,
            "total_cfu": 50_000_000_000,
            "total_strain_count": 10,
        },
        "ingredient_quality_data": {
            "ingredients_scorable": [
                {
                    "name": "Chicory root Fiber inulin",
                    "canonical_id": "prebiotics",
                    "category": "fiber",
                    "quantity": 100,
                    "unit": "mg",
                    "score_eligible_by_cleaner": True,
                    "cleaner_row_role": "active_scorable",
                }
            ],
            "ingredients_skipped": [
                {
                    "name": "Fortify Women's 50 Billion CFU Proprietary Probiotic Blend",
                    "category": "probiotics",
                    "quantity": 550,
                    "unit": "mg",
                    "score_eligible_by_cleaner": False,
                    "cleaner_row_role": "blend_header_total",
                },
                {
                    "name": "Lactobacillus rhamnosus GG",
                    "category": "probiotics",
                    "quantity": 0,
                    "unit": "NP",
                    "score_eligible_by_cleaner": False,
                    "cleaner_row_role": "nested_display_only",
                },
            ],
        },
        "activeIngredients": [
            {
                "name": "Fortify Women's 50 Billion CFU Proprietary Probiotic Blend",
                "standardName": "Probiotic Blend",
                "cleaner_row_role": "blend_header_total",
                "score_eligible_by_cleaner": False,
                "quantity": 550,
                "unit": "mg",
            },
            {
                "name": "Chicory root Fiber inulin",
                "standardName": "Inulin",
                "canonical_id": "prebiotics",
                "cleaner_row_role": "active_scorable",
                "score_eligible_by_cleaner": True,
                "quantity": 100,
                "unit": "mg",
            },
        ],
    }

    result = classify_supplement(product)

    assert result["primary_type"] == "probiotic"
    assert any(
        reason in result["classification_reasons"]
        for reason in (
            "probiotic name + product-level CFU evidence",
            "probiotic row identity + product-level CFU evidence",
        )
    )


def test_product_level_cfu_does_not_hijack_non_probiotic_cleaner_active_without_iqd_rows():
    """Accessory CFU metadata must not override a cleaner-eligible CBD active."""
    product = {
        "product_name": "CBD Immune Support",
        "probiotic_data": {
            "is_probiotic_product": True,
            "total_cfu": 5000000000,
            "total_strain_count": 1,
        },
        "activeIngredients": [
            {
                "name": "Cannabidiol",
                "canonical_id": "cbd_cannabidiol",
                "quantity": 25,
                "unit": "mg",
                "score_eligible_by_cleaner": True,
                "cleaner_row_role": "active_scorable",
            }
        ],
        "ingredient_quality_data": {
            "ingredients_scorable": [],
            "ingredients_skipped": [
                {
                    "name": "Probiotic Base",
                    "category": "probiotics",
                    "quantity": 0,
                    "unit": "NP",
                    "score_eligible_by_cleaner": False,
                    "cleaner_row_role": "nested_display_only",
                }
            ],
        },
    }
    result = classify_supplement(product)
    assert result["primary_type"] != "probiotic"


def test_minority_probiotic_row_does_not_hijack_collagen_mct_product():
    product = {
        "product_name": "Grass Fed Collagen Coconut MCT Chocolate",
        "probiotic_data": {
            "is_probiotic_product": True,
            "total_cfu": 500000000,
            "total_strain_count": 1,
        },
        "ingredient_quality_data": {"ingredients_scorable": [
            {"name": "Collagen", "canonical_id": "collagen", "category": "proteins", "quantity": 10, "unit": "g", "score_eligible_by_cleaner": True, "cleaner_row_role": "active_scorable", "role_classification": "active_scorable"},
            {"name": "MCT Oil", "canonical_id": "mct_oil", "category": "fatty_acids", "quantity": 3, "unit": "g", "score_eligible_by_cleaner": True, "cleaner_row_role": "active_scorable", "role_classification": "active_scorable"},
            {"name": "Bacillus subtilis", "canonical_id": "bacillus_subtilis", "category": "probiotics", "quantity": 5, "unit": "mg", "score_eligible_by_cleaner": True, "cleaner_row_role": "active_scorable", "role_classification": "active_scorable"},
        ]},
    }
    result = classify_supplement(product)
    assert result["primary_type"] != "probiotic"


def test_prenatal_with_b_vitamins_and_dha_is_not_b_complex():
    product = {
        "product_name": "Prenatal Essentials",
        "ingredient_quality_data": {"ingredients_scorable": [
            {"name": "Folate", "canonical_id": "vitamin_b9_folate", "category": "vitamins", "quantity": 600, "unit": "mcg DFE", "score_eligible_by_cleaner": True, "cleaner_row_role": "active_scorable", "role_classification": "active_scorable"},
            {"name": "Folic Acid", "canonical_id": "vitamin_b9_folate", "category": "vitamins", "quantity": 360, "unit": "mcg", "score_eligible_by_cleaner": True, "cleaner_row_role": "active_scorable", "role_classification": "active_scorable"},
            {"name": "Vitamin B12", "canonical_id": "vitamin_b12_cobalamin", "category": "vitamins", "quantity": 2.8, "unit": "mcg", "score_eligible_by_cleaner": True, "cleaner_row_role": "active_scorable", "role_classification": "active_scorable"},
            {"name": "Choline", "canonical_id": "choline", "category": "amino_acids", "quantity": 550, "unit": "mg", "score_eligible_by_cleaner": True, "cleaner_row_role": "active_scorable", "role_classification": "active_scorable"},
            {"name": "Iron", "canonical_id": "iron", "category": "minerals", "quantity": 27, "unit": "mg", "score_eligible_by_cleaner": True, "cleaner_row_role": "active_scorable", "role_classification": "active_scorable"},
            {"name": "DHA", "canonical_id": "dha", "category": "fatty_acids", "quantity": 250, "unit": "mg", "score_eligible_by_cleaner": True, "cleaner_row_role": "active_scorable", "role_classification": "active_scorable"},
        ]},
    }
    result = classify_supplement(product)
    assert result["primary_type"] == "multivitamin"


def test_named_amino_acid_with_vitamin_cofactors_is_amino_acid():
    product = {
        "product_name": "Best L-Tryptophan 500 mg",
        "ingredient_quality_data": {"ingredients_scorable": [
            {"name": "Niacin", "canonical_id": "vitamin_b3_niacin", "category": "vitamins", "quantity": 20, "unit": "mg", "score_eligible_by_cleaner": True, "cleaner_row_role": "active_scorable", "role_classification": "active_scorable"},
            {"name": "Vitamin B6", "canonical_id": "vitamin_b6_pyridoxine", "category": "vitamins", "quantity": 10, "unit": "mg", "score_eligible_by_cleaner": True, "cleaner_row_role": "active_scorable", "role_classification": "active_scorable"},
            {"name": "L-Tryptophan", "canonical_id": "l_tryptophan", "category": "amino_acids", "quantity": 500, "unit": "mg", "score_eligible_by_cleaner": True, "cleaner_row_role": "active_scorable", "role_classification": "active_scorable"},
        ]},
    }
    result = classify_supplement(product)
    assert result["primary_type"] == "amino_acid"


def test_5htp_with_vitamin_cofactors_stays_sleep_support():
    product = {
        "product_name": "5-HTP Enhanced with Vitamins B6 and C",
        "ingredient_quality_data": {"ingredients_scorable": [
            {"name": "Vitamin C", "canonical_id": "vitamin_c", "category": "vitamins", "quantity": 60, "unit": "mg", "score_eligible_by_cleaner": True, "cleaner_row_role": "active_scorable", "role_classification": "active_scorable"},
            {"name": "Vitamin B6", "canonical_id": "vitamin_b6_pyridoxine", "category": "vitamins", "quantity": 10, "unit": "mg", "score_eligible_by_cleaner": True, "cleaner_row_role": "active_scorable", "role_classification": "active_scorable"},
            {"name": "5-HTP", "canonical_id": "5_htp", "category": "amino_acids", "quantity": 100, "unit": "mg", "score_eligible_by_cleaner": True, "cleaner_row_role": "active_scorable", "role_classification": "active_scorable"},
        ]},
    }
    result = classify_supplement(product)
    assert result["primary_type"] == "sleep_support"


# ============================================================================
# Taxonomy Output Structure
# ============================================================================

class TestTaxonomyOutputStructure:
    """Verify the output dict has all required fields."""

    def test_all_fields_present(self):
        p = {
            "product_name": "Test Product",
            "ingredient_quality_data": {"ingredients": [
                {"name": "Vitamin C", "canonical_id": "vitamin_c", "category": "vitamin",
                 "quantity": 500, "unit": "mg"},
            ]},
        }
        result = classify_supplement(p)
        assert "primary_type" in result
        assert "secondary_type" in result
        assert "percentile_category" in result
        assert "classification_confidence" in result
        assert "classification_reasons" in result
        assert "quantified_active_count" in result
        assert "non_quantified_base_count" in result
        assert "category_breakdown" in result
        assert isinstance(result["classification_reasons"], list)
        assert 0.0 <= result["classification_confidence"] <= 1.0

    def test_primary_type_in_valid_set(self):
        from supplement_taxonomy import PRIMARY_TYPES
        p = {
            "product_name": "Test",
            "ingredient_quality_data": {"ingredients": [
                {"name": "Something", "category": "herb", "quantity": 100, "unit": "mg"},
            ]},
        }
        result = classify_supplement(p)
        assert result["primary_type"] in PRIMARY_TYPES


# ============================================================================
# Vocab Sync — PRIMARY_TYPES must match product_type_vocab.json
# ============================================================================

class TestVocabSync:
    """Ensure the classifier and the vocab file never drift."""

    def test_primary_types_match_vocab_json(self):
        import json
        from supplement_taxonomy import PRIMARY_TYPES
        vocab_path = os.path.join(
            os.path.dirname(__file__), "..", "data", "product_type_vocab.json"
        )
        with open(vocab_path) as fh:
            data = json.load(fh)
        vocab_ids = [e["id"] for e in data["product_types"]]
        assert PRIMARY_TYPES == vocab_ids, (
            f"PRIMARY_TYPES drifted from product_type_vocab.json.\n"
            f"  In code but not vocab: {set(PRIMARY_TYPES) - set(vocab_ids)}\n"
            f"  In vocab but not code: {set(vocab_ids) - set(PRIMARY_TYPES)}"
        )

    def test_vocab_entry_count_matches_metadata(self):
        import json
        vocab_path = os.path.join(
            os.path.dirname(__file__), "..", "data", "product_type_vocab.json"
        )
        with open(vocab_path) as fh:
            data = json.load(fh)
        declared = data["_metadata"]["total_entries"]
        actual = len(data["product_types"])
        assert declared == actual, f"Metadata says {declared}, actual {actual}"


# ============================================================================
# Substring Collision Guards
# ============================================================================

class TestSubstringCollisionGuards:
    """Prevent short name tokens from matching inside unrelated words.

    Each test encodes a real false-positive that was found and fixed.
    If a new token is added that reintroduces a substring collision,
    these tests will catch it before it ships.
    """

    @staticmethod
    def _classify(name, category="herbs"):
        p = {
            "product_name": name,
            "ingredient_quality_data": {"ingredients": [
                {"name": "A", "category": category, "quantity": 100, "unit": "mg"},
                {"name": "B", "category": category, "quantity": 100, "unit": "mg"},
            ]},
        }
        return classify_supplement(p)["primary_type"]

    # --- Sleep tokens: "rest", "pm", "night" must not match substrings ---

    def test_forest_not_sleep(self):
        """'rest' in 'forest' must not trigger sleep_support."""
        assert self._classify("Forest Mushroom Complex") != "sleep_support"

    def test_rpm_not_sleep(self):
        """'pm' in 'rpm' must not trigger sleep_support."""
        assert self._classify("RPM Energy Booster") != "sleep_support"

    def test_overnight_not_sleep(self):
        """'night' in 'overnight' must not trigger sleep_support."""
        assert self._classify("Overnight Collagen Repair") != "sleep_support"

    def test_restore_not_sleep(self):
        """'rest' in 'restore' must not trigger sleep_support."""
        assert self._classify("Restore Balance Formula") != "sleep_support"

    def test_good_night_is_sleep(self):
        """'night' as a standalone word should still match."""
        assert self._classify("Good Night Melatonin") == "sleep_support"

    def test_pm_standalone_without_sleep_evidence_is_not_sleep(self):
        """'pm' alone is not clinical sleep evidence."""
        assert self._classify("PM Calm Support") != "sleep_support"

    # --- Beauty tokens: "hair" must not match substrings ---

    def test_chairman_not_beauty(self):
        """'hair' in 'chairman' must not trigger beauty."""
        assert self._classify("Chairman Select Vitamin D") != "beauty_hair_skin_nails"

    def test_mohair_not_beauty(self):
        """'hair' in 'mohair' must not trigger beauty."""
        assert self._classify("Mohair Fiber Blend") != "beauty_hair_skin_nails"

    def test_hair_skin_nails_is_beauty(self):
        """Actual hair product must still match."""
        assert self._classify("Hair Skin & Nails with Biotin") == "beauty_hair_skin_nails"

    def test_hairfluence_is_beauty(self):
        """'hair' at start of word should match (Hairfluence is a real brand)."""
        assert self._classify("Hairfluence Growth Formula") == "beauty_hair_skin_nails"

    # --- Greens: "superfood" alone must not catch mushroom blends ---

    def test_superfood_mushroom_not_greens(self):
        """Mushroom adaptogens labeled 'superfood' are not greens powders."""
        assert self._classify("Superfood Mushroom Complex") != "greens_powder"

    def test_super_greens_is_greens(self):
        """Actual greens product must still match."""
        assert self._classify("Super Greens Powder") == "greens_powder"

    def test_fortified_super_greens_stays_greens_not_multivitamin(self):
        """Greens product identity beats vitamin/mineral fortification."""
        product = {
            "product_name": "Super Greens",
            "ingredient_quality_data": {"ingredients_scorable": [
                {"name": "Vitamin A", "canonical_id": "vitamin_a", "category": "vitamins", "quantity": 2033, "unit": "IU"},
                {"name": "Vitamin C", "canonical_id": "vitamin_c", "category": "vitamins", "quantity": 60, "unit": "mg"},
                {"name": "Vitamin D", "canonical_id": "vitamin_d", "category": "vitamins", "quantity": 400, "unit": "IU"},
                {"name": "Calcium", "canonical_id": "calcium", "category": "minerals", "quantity": 50, "unit": "mg"},
                {"name": "Iron", "canonical_id": "iron", "category": "minerals", "quantity": 5, "unit": "mg"},
                {"name": "Potassium", "canonical_id": "potassium", "category": "minerals", "quantity": 100, "unit": "mg"},
                {"name": "Lactobacillus acidophilus", "canonical_id": "lactobacillus_acidophilus", "category": "probiotics", "quantity": 5, "unit": "mg"},
                {"name": "Lactobacillus bulgaricus", "canonical_id": "lactobacillus_bulgaricus", "category": "probiotics", "quantity": 5, "unit": "mg"},
                {"name": "Bifidobacterium bifidum", "canonical_id": "bifidobacterium_bifidum", "category": "probiotics", "quantity": 5, "unit": "mg"},
            ]},
        }

        result = classify_supplement(product)

        assert result["primary_type"] == "greens_powder"
        assert result["percentile_category"] == "greens_powder"
        assert any("greens/superfood" in r for r in result["classification_reasons"])

    def test_greens_name_without_greens_content_does_not_override_multivitamin(self):
        """The generic word 'greens' alone is not enough to override a
        vitamin/mineral panel when no greens/botanical content is present.
        """
        product = {
            "product_name": "Daily Greens Multivitamin",
            "ingredient_quality_data": {"ingredients_scorable": [
                {"name": "Vitamin A", "canonical_id": "vitamin_a", "category": "vitamins", "quantity": 2033, "unit": "IU"},
                {"name": "Vitamin C", "canonical_id": "vitamin_c", "category": "vitamins", "quantity": 60, "unit": "mg"},
                {"name": "Vitamin D", "canonical_id": "vitamin_d", "category": "vitamins", "quantity": 400, "unit": "IU"},
                {"name": "Vitamin B6", "canonical_id": "vitamin_b6", "category": "vitamins", "quantity": 2, "unit": "mg"},
                {"name": "Folate", "canonical_id": "folate", "category": "vitamins", "quantity": 400, "unit": "mcg"},
                {"name": "Calcium", "canonical_id": "calcium", "category": "minerals", "quantity": 50, "unit": "mg"},
                {"name": "Iron", "canonical_id": "iron", "category": "minerals", "quantity": 5, "unit": "mg"},
            ]},
        }

        result = classify_supplement(product)

        assert result["primary_type"] == "multivitamin"
        assert result["percentile_category"] == "multivitamin"

    # --- Fiber/digestive: canonical vocab includes digestive enzymes ---

    def test_digestive_enzymes_are_digestive(self):
        """Digestive enzymes belong in the fiber_digestive vocab bucket."""
        assert self._classify("Digestive Enzymes Complex", category="enzymes") == "fiber_digestive"

    def test_digestive_fiber_is_fiber(self):
        """Actual fiber product must still match."""
        assert self._classify("Digestive Fiber Supplement") == "fiber_digestive"

    # --- Secondary type: negation awareness + multivitamin guard ---

    def test_no_iron_multivitamin_secondary_is_none(self):
        """'No Iron' multivitamins must not get secondary_type='iron'."""
        p = {
            "product_name": "One Daily Multi-Vitamin No Iron",
            "ingredient_quality_data": {"ingredients": [
                {"name": "A", "canonical_id": "vitamin_a", "category": "vitamins", "quantity": 5000, "unit": "IU"},
                {"name": "C", "canonical_id": "vitamin_c", "category": "vitamins", "quantity": 60, "unit": "mg"},
                {"name": "D", "canonical_id": "vitamin_d", "category": "vitamins", "quantity": 400, "unit": "IU"},
                {"name": "B6", "canonical_id": "vitamin_b6", "category": "vitamins", "quantity": 10, "unit": "mg"},
                {"name": "Folate", "canonical_id": "folate", "category": "vitamins", "quantity": 400, "unit": "mcg"},
                {"name": "Ca", "canonical_id": "calcium", "category": "minerals", "quantity": 200, "unit": "mg"},
                {"name": "Mg", "canonical_id": "magnesium", "category": "minerals", "quantity": 100, "unit": "mg"},
                {"name": "Zn", "canonical_id": "zinc", "category": "minerals", "quantity": 15, "unit": "mg"},
            ]},
        }
        result = classify_supplement(p)
        assert result["primary_type"] == "multivitamin"
        assert result["secondary_type"] is None

    def test_negated_iron_not_secondary(self):
        """'no iron' / 'without iron' / 'iron-free' must not set secondary_type='iron'."""
        for name in ["No Iron Formula", "Without Iron Daily", "Iron-Free Prenatal"]:
            p = {
                "product_name": name,
                "ingredient_quality_data": {"ingredients": [
                    {"name": "X", "canonical_id": "maca", "category": "herbs", "quantity": 500, "unit": "mg"},
                ]},
            }
            result = classify_supplement(p)
            assert result["secondary_type"] != "iron", f"{name} got secondary_type=iron"


# ============================================================================
# Bug Regression Tests — found via 150-product spot-check audit
# ============================================================================

class TestBugRegressions:
    """Each test encodes a real bug found during the 150-product audit."""

    # Bug #4: CoQ10 is a lipid coenzyme, not a botanical
    def test_coq10_not_herbal_botanical(self):
        p = {
            "product_name": "CoQ10 400 mg",
            "ingredient_quality_data": {"ingredients": [
                {"name": "CoQ10", "canonical_id": "coq10", "category": "antioxidants",
                 "quantity": 400, "unit": "mg"},
            ]},
        }
        result = classify_supplement(p)
        assert result["primary_type"] != "herbal_botanical", \
            "CoQ10 is a lipid coenzyme, not a botanical"
        assert result["secondary_type"] == "coq10"

    def test_alpha_lipoic_acid_not_herbal(self):
        p = {
            "product_name": "Alpha-Lipoic Acid 600 mg",
            "ingredient_quality_data": {"ingredients": [
                {"name": "Alpha-Lipoic Acid", "canonical_id": "alpha_lipoic_acid",
                 "category": "antioxidants", "quantity": 600, "unit": "mg"},
            ]},
        }
        result = classify_supplement(p)
        assert result["primary_type"] != "herbal_botanical"

    # Bug #5: B12 + calcium excipient → should be single_vitamin not combo
    def test_b12_with_calcium_excipient_is_single_vitamin(self):
        """B12 1000mcg + Calcium 50mg (excipient) → single_vitamin, not combo."""
        p = {
            "product_name": "Vitamin B12 1000 mcg",
            "ingredient_quality_data": {"ingredients": [
                {"name": "Vitamin B12", "canonical_id": "vitamin_b12", "category": "vitamins",
                 "quantity": 1000, "unit": "mcg"},
                {"name": "Calcium", "canonical_id": "calcium", "category": "minerals",
                 "quantity": 50, "unit": "mg"},
            ]},
        }
        result = classify_supplement(p)
        assert result["primary_type"] == "single_vitamin", \
            f"B12+excipient calcium should be single_vitamin, got {result['primary_type']}"

    # Bug #6: Fortified protein powder classified as multivitamin
    def test_fortified_protein_powder_not_multivitamin(self):
        """Whey protein + added vitamins → protein_powder, not multivitamin."""
        p = {
            "product_name": "Whey Protein Powder Chocolate",
            "ingredient_quality_data": {"ingredients": [
                {"name": "Whey Protein", "canonical_id": "whey_protein", "category": "proteins",
                 "quantity": 25000, "unit": "mg"},
                {"name": "Vitamin A", "canonical_id": "vitamin_a", "category": "vitamins",
                 "quantity": 500, "unit": "IU"},
                {"name": "Vitamin C", "canonical_id": "vitamin_c", "category": "vitamins",
                 "quantity": 60, "unit": "mg"},
                {"name": "Calcium", "canonical_id": "calcium", "category": "minerals",
                 "quantity": 200, "unit": "mg"},
                {"name": "Iron", "canonical_id": "iron", "category": "minerals",
                 "quantity": 4, "unit": "mg"},
                {"name": "Magnesium", "canonical_id": "magnesium", "category": "minerals",
                 "quantity": 50, "unit": "mg"},
                {"name": "Zinc", "canonical_id": "zinc", "category": "minerals",
                 "quantity": 5, "unit": "mg"},
            ]},
        }
        result = classify_supplement(p)
        assert result["primary_type"] == "protein_powder", \
            f"Whey protein with fortification should be protein_powder, got {result['primary_type']}"

    # Bug #7: Sleep gummies with all-NP ingredients → general_supplement
    def test_sleep_gummies_all_np_still_classified(self):
        """Products named 'Sleep' with all NP ingredients should be sleep_support."""
        p = {
            "product_name": "Kids Sleep Gummies Berry Flavor",
            "ingredient_quality_data": {"ingredients": [
                {"name": "L-Theanine", "canonical_id": "l_theanine", "category": "amino_acids",
                 "quantity": 0, "unit": "NP"},
                {"name": "Chamomile", "canonical_id": "chamomile", "category": "herbs",
                 "quantity": 0, "unit": "NP"},
                {"name": "Lemon Balm", "canonical_id": "lemon_balm", "category": "herbs",
                 "quantity": 0, "unit": "NP"},
            ]},
        }
        result = classify_supplement(p)
        assert result["primary_type"] == "sleep_support", \
            f"Sleep-named product with NP ingredients should be sleep_support, got {result['primary_type']}"


def test_mixed_named_formula_not_pulled_into_amino_by_one_named_amino():
    product = {
        "product_name": "CoQ10 L-Carnitine Magnesium",
        "ingredient_quality_data": {"ingredients_scorable": [
            {"name": "Magnesium", "canonical_id": "magnesium", "category": "minerals", "quantity": 200, "unit": "mg"},
            {"name": "Magnesium Bisglycinate Chelate", "canonical_id": "magnesium", "category": "minerals", "quantity": 1112, "unit": "mg"},
            {"name": "L-Carnitine Fumarate", "canonical_id": "l_carnitine", "category": "amino_acids", "quantity": 855, "unit": "mg"},
            {"name": "L-Carnitine", "canonical_id": "l_carnitine", "category": "amino_acids", "quantity": 500, "unit": "mg"},
            {"name": "Coenzyme Q10", "canonical_id": "coq10", "category": "antioxidants", "quantity": 200, "unit": "mg"},
        ]},
    }
    result = classify_supplement(product)
    assert result["primary_type"] == "general_supplement"


def test_digestive_enzyme_with_calcium_carrier_is_fiber_digestive_not_mineral():
    product = {
        "product_name": "High Potency Serrapeptase 120,000 SPU",
        "ingredient_quality_data": {"ingredients_scorable": [
            {"name": "Calcium", "canonical_id": "calcium", "category": "minerals", "quantity": 35, "unit": "mg"},
            {
                "name": "Serrapeptase",
                "canonical_id": "digestive_enzymes",
                "category": "enzymes",
                "quantity": 0,
                "unit": "NP",
                "dose_class": "enzyme_activity",
            },
        ]},
    }
    result = classify_supplement(product)
    assert result["primary_type"] == "fiber_digestive"
    assert result["secondary_type"] == "serrapeptase"
    assert result["primary_type"] != "single_mineral"


def test_betaine_pepsin_bitters_is_digestive_not_amino_acid():
    product = {
        "product_name": "Betaine HCl Pepsin and Gentian Bitters",
        "ingredient_quality_data": {"ingredients_scorable": [
            {"name": "Betaine HCl", "canonical_id": "tmg_betaine", "category": "amino_acids", "quantity": 650, "unit": "mg"},
            {"name": "Pepsin", "canonical_id": "pepsin", "category": "enzymes", "quantity": 0, "unit": "NP"},
        ]},
    }
    result = classify_supplement(product)
    assert result["primary_type"] == "fiber_digestive"
    assert result["secondary_type"] == "pepsin"


def test_mixed_herb_enzyme_formula_does_not_get_enzyme_secondary_by_default():
    product = {
        "product_name": "Bladder Support Complex with Go-Less",
        "ingredient_quality_data": {"ingredients_scorable": [
            {"name": "Horsetail", "canonical_id": "horsetail", "category": "herbs", "quantity": 450, "unit": "mg"},
            {"name": "Bromelain", "canonical_id": "digestive_enzymes", "category": "enzymes", "quantity": 400, "unit": "mg"},
        ]},
    }
    result = classify_supplement(product)
    assert result["primary_type"] == "general_supplement"
    assert result["secondary_type"] is None


def test_digestive_enzyme_name_without_scorable_rows_stays_general():
    product = {
        "product_name": "Digestive Enzymes",
        "ingredient_quality_data": {"ingredients_scorable": []},
    }
    result = classify_supplement(product)
    assert result["primary_type"] == "general_supplement"
