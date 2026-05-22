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

    # --- Fiber: "digestive" alone must not catch enzyme products ---

    def test_digestive_enzymes_not_fiber(self):
        """Digestive enzymes are not fiber supplements."""
        assert self._classify("Digestive Enzymes Complex", category="enzymes") != "fiber_digestive"

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
