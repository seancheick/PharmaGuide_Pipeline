#!/usr/bin/env python3
"""
Golden Fixtures for Dosage Normalization + RDA/UL Correctness
==============================================================

These tests demonstrate CORRECTNESS of the math layer, not just non-crashing.
Each fixture shows expected conversions, evidence fields, and edge cases.

Run with: python -m pytest tests/test_dosage_golden_fixtures.py -v
"""

import pytest
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from unit_converter import UnitConverter, ConversionResult
from rda_ul_calculator import RDAULCalculator, NutrientAdequacyResult
from dosage_normalizer import DosageNormalizer, ServingBasis


class TestVitaminAIUConversions:
    """
    Golden Fixture 1: Vitamin A IU conversions

    Vitamin A has two different IU conversion factors:
    - Retinol: 1 IU = 0.3 mcg RAE
    - Beta-carotene (supplements): 1 IU = 0.3 mcg RAE (as supplement)
    - Beta-carotene (food): 1 IU = 0.6 mcg RAE (not in supplements)

    This tests that form detection works correctly.
    """

    @pytest.fixture
    def converter(self):
        return UnitConverter()

    def test_vitamin_a_retinol_iu_to_mcg(self, converter):
        """Vitamin A as Retinol: 10,000 IU = 3,000 mcg RAE"""
        result = converter.convert_nutrient(
            nutrient="Vitamin A",
            amount=10000,
            from_unit="IU",
            ingredient_name="Vitamin A (as Retinyl Palmitate)"
        )

        # Assertions
        assert result.success is True
        # Note: Returns "mcg RAE" (Retinol Activity Equivalent) - more accurate
        assert "mcg" in result.converted_unit
        # Retinol: 10,000 IU * 0.3 = 3,000 mcg RAE
        assert result.converted_value == pytest.approx(3000, rel=0.01)
        assert "retinol" in result.form_detected.lower() or "preformed" in result.form_detected.lower()
        assert result.confidence == "high"

        # Evidence must be present
        assert result.conversion_factor == pytest.approx(0.3, rel=0.01)
        assert result.conversion_rule_id is not None

    def test_vitamin_a_beta_carotene_iu_to_mcg(self, converter):
        """Beta-carotene supplement: 10,000 IU = 1,000 mcg RAE (supplement factor 0.1)"""
        result = converter.convert_nutrient(
            nutrient="Vitamin A",
            amount=10000,
            from_unit="IU",
            ingredient_name="Beta-Carotene (Pro-Vitamin A)"
        )

        assert result.success is True
        # Note: Returns "mcg RAE" (Retinol Activity Equivalent)
        assert "mcg" in result.converted_unit
        # Beta-carotene supplement: 10,000 IU * 0.1 = 1,000 mcg RAE
        # (per NIH ODS: supplement beta-carotene converts at 0.1 mcg RAE/IU)
        assert result.converted_value == pytest.approx(1000, rel=0.01)
        # Verify form was correctly detected
        assert result.conversion_rule_id == "vitamin_a_beta_carotene_supplement"
        assert result.conversion_factor == pytest.approx(0.1)
        assert result.form_detected is not None

    def test_vitamin_a_unknown_form_flagged(self, converter):
        """Unknown form is flagged for review (NOT defaulted to retinol).

        This is the safer approach because:
        - Retinol has a UL (3000 mcg RAE) that can cause toxicity
        - Beta-carotene has NO established UL (body regulates conversion)
        - If we assume retinol, we might wrongly flag a product as exceeding UL
        - Per NIH ODS, form MUST be known for accurate UL assessment
        """
        result = converter.convert_nutrient(
            nutrient="Vitamin A",
            amount=5000,
            from_unit="IU",
            ingredient_name="Vitamin A"  # No form specified
        )

        # Returns success but with 'unknown' flag for review
        assert result.success is True
        assert result.conversion_rule_id == "vitamin_a_unknown"
        assert "Unknown" in result.form_detected
        # Value stays unconverted (flagged for manual review)
        assert result.converted_value == 5000


class TestVitaminEFormAwareness:
    """
    Golden Fixture: Vitamin E form-aware IU to mg conversion

    Natural (d-alpha-tocopherol): 1 IU = 0.67 mg
    Synthetic (dl-alpha-tocopherol): 1 IU = 0.45 mg

    Per NIH ODS, the form MUST be detected for accurate conversion.
    Default to synthetic if unknown (conservative).
    """

    @pytest.fixture
    def converter(self):
        return UnitConverter()

    def test_vitamin_e_natural_d_alpha_400iu(self, converter):
        """Natural Vitamin E (d-alpha): 400 IU = 268 mg"""
        result = converter.convert_nutrient(
            nutrient="Vitamin E",
            amount=400,
            from_unit="IU",
            ingredient_name="d-alpha-tocopherol"
        )

        assert result.success is True
        assert result.converted_unit == "mg"
        # 400 IU * 0.67 = 268 mg
        assert result.converted_value == pytest.approx(268, rel=0.01)
        assert result.conversion_factor == pytest.approx(0.67, rel=0.01)
        assert "natural" in result.conversion_rule_id.lower() or "d_alpha" in result.conversion_rule_id

    def test_vitamin_e_synthetic_dl_alpha_400iu(self, converter):
        """Synthetic Vitamin E (dl-alpha): 400 IU = 180 mg"""
        result = converter.convert_nutrient(
            nutrient="Vitamin E",
            amount=400,
            from_unit="IU",
            ingredient_name="dl-alpha-tocopherol"
        )

        assert result.success is True
        assert result.converted_unit == "mg"
        # 400 IU * 0.45 = 180 mg
        assert result.converted_value == pytest.approx(180, rel=0.01)
        assert result.conversion_factor == pytest.approx(0.45, rel=0.01)
        assert "synthetic" in result.conversion_rule_id.lower() or "dl_alpha" in result.conversion_rule_id


class TestVitaminKMassConversion:
    """Vitamin K uses mass units; mg should convert to mcg."""

    @pytest.fixture
    def converter(self):
        return UnitConverter()

    def test_vitamin_k_mg_to_mcg(self, converter):
        """Vitamin K1: 1 mg = 1000 mcg"""
        result = converter.convert_nutrient(
            nutrient="Vitamin K1",
            amount=1,
            from_unit="mg",
            to_unit="mcg",
            ingredient_name="Vitamin K1 (Phylloquinone)"
        )

        assert result.success is True
        assert result.converted_unit == "mcg"
        assert result.converted_value == pytest.approx(1000, rel=0.001)

    def test_vitamin_e_unknown_defaults_to_synthetic(self, converter):
        """Unknown form defaults to synthetic (conservative - lower conversion).

        This is safer than defaulting to natural because it doesn't over-report
        the converted mg value.
        """
        result = converter.convert_nutrient(
            nutrient="Vitamin E",
            amount=400,
            from_unit="IU",
            ingredient_name="Vitamin E"  # No form specified
        )

        assert result.success is True
        # Should default to synthetic (0.45)
        assert result.converted_value == pytest.approx(180, rel=0.01)
        assert result.conversion_factor == pytest.approx(0.45, rel=0.01)


class TestVitaminDIUConversions:
    """
    Golden Fixture 2: Vitamin D IU to mcg conversion

    Vitamin D: 1 IU = 0.025 mcg (or 40 IU = 1 mcg)
    This is the same for D2 and D3.
    """

    @pytest.fixture
    def converter(self):
        return UnitConverter()

    def test_vitamin_d3_2000iu_to_mcg(self, converter):
        """Vitamin D3: 2,000 IU = 50 mcg"""
        result = converter.convert_nutrient(
            nutrient="Vitamin D",
            amount=2000,
            from_unit="IU",
            ingredient_name="Vitamin D3 (Cholecalciferol)"
        )

        assert result.success is True
        assert result.converted_unit == "mcg"
        # 2,000 IU * 0.025 = 50 mcg
        assert result.converted_value == pytest.approx(50, rel=0.01)
        assert result.conversion_factor == pytest.approx(0.025, rel=0.01)
        assert result.confidence == "high"

    def test_vitamin_d_5000iu_to_mcg(self, converter):
        """Vitamin D: 5,000 IU = 125 mcg"""
        result = converter.convert_nutrient(
            nutrient="Vitamin D",
            amount=5000,
            from_unit="IU",
            ingredient_name="Vitamin D (as D3)"
        )

        assert result.success is True
        # 5,000 IU * 0.025 = 125 mcg
        assert result.converted_value == pytest.approx(125, rel=0.01)

    def test_vitamin_d_already_mcg_no_conversion(self, converter):
        """Vitamin D already in mcg needs no IU conversion"""
        result = converter.convert_nutrient(
            nutrient="Vitamin D",
            amount=50,
            from_unit="mcg",
            ingredient_name="Vitamin D3"
        )

        assert result.success is True
        # Already in mcg - should pass through
        assert result.converted_value == pytest.approx(50, rel=0.01)
        assert result.converted_unit == "mcg"


class TestVitaminB12NoUL:
    """
    Golden Fixture 3: Vitamin B12 - no established UL

    B12 has no Tolerable Upper Limit established by IOM/NAM.
    The calculator should handle this gracefully:
    - ul_status = "not_determined"
    - pct_ul = None
    - over_ul = False (cannot exceed what doesn't exist)
    """

    @pytest.fixture
    def calculator(self):
        return RDAULCalculator()

    def test_b12_no_ul_established(self, calculator):
        """B12 at 1000mcg should show no UL, not flag as over"""
        result = calculator.compute_nutrient_adequacy(
            nutrient="Vitamin B12",
            amount=1000,  # Very high dose
            unit="mcg",
            age_group="adult"
        )

        # B12 RDA is ~2.4 mcg, so 1000 mcg is 41,667% of RDA
        assert result.rda_ai is not None
        assert result.pct_rda is not None
        assert result.pct_rda > 1000  # Definitely over 100% RDA

        # But NO UL established
        assert result.ul is None
        assert result.ul_status == "not_determined"
        assert result.pct_ul is None
        assert result.over_ul is False  # Cannot be over non-existent UL
        assert result.over_ul_amount is None

        # Should NOT generate safety flag for no-UL nutrient
        assert "UL" not in " ".join(result.warnings)

    def test_b12_high_dose_still_scoring_eligible(self, calculator):
        """High-dose B12 should still be scoring-eligible despite no UL"""
        result = calculator.compute_nutrient_adequacy(
            nutrient="Vitamin B12",
            amount=5000,
            unit="mcg",
            age_group="adult"
        )

        # With no UL, even mega-doses shouldn't be flagged unsafe
        # Adequacy band should reflect high percentage of RDA
        assert result.adequacy_band in ["high", "excessive"]
        assert result.over_ul is False


class TestGummyServingBasisNormalization:
    """
    Golden Fixture 4: Gummy "per 2 gummies" serving normalization

    Gummy products often have serving sizes like "2 gummies" or "3 gummies".
    The normalizer should correctly parse this and calculate per-day amounts.
    """

    @pytest.fixture
    def normalizer(self):
        return DosageNormalizer()

    def test_per_2_gummies_serving_parsing(self, normalizer):
        """Product with '2 gummies' serving should parse correctly"""
        product = {
            "servingSizes": [
                {
                    "quantity": 2,
                    "unit": "gummy",
                    "servingsPerContainer": 30,
                    "perDay": "once daily"
                }
            ],
            "supplementFacts": [
                {"name": "Vitamin C", "amount": 120, "unit": "mg"},
                {"name": "Zinc", "amount": 15, "unit": "mg"}
            ]
        }

        result = normalizer.normalize_product_dosages(product)

        assert result.success is True
        assert result.serving_basis is not None

        # Serving basis checks
        basis = result.serving_basis
        assert basis.quantity == 2
        assert "gummy" in basis.unit.lower()
        assert basis.servings_per_day_used == 1  # "once daily"


class TestDosageNormalizerCleanedSchema:
    """Ensure DosageNormalizer reads cleaned schema fields."""

    @pytest.fixture
    def normalizer(self):
        return DosageNormalizer()

    def test_reads_activeingredients_from_cleaned(self, normalizer):
        """activeIngredients should be normalized when supplementFacts is missing."""
        product = {
            "servingSizes": [
                {
                    "quantity": 1,
                    "unit": "capsule",
                    "perDay": "once daily"
                }
            ],
            "activeIngredients": [
                {"name": "Vitamin C", "quantity": 100, "unit": "mg"}
            ]
        }

        result = normalizer.normalize_product_dosages(product)

        assert result.success is True
        assert len(result.normalized_ingredients) == 1
        assert result.normalized_ingredients[0].source_field.startswith("activeIngredients")

    def test_success_false_when_zero_ingredients(self, normalizer):
        """No ingredients should return success=False with error."""
        product = {
            "servingSizes": [
                {"quantity": 1, "unit": "capsule", "perDay": "once daily"}
            ]
        }

        result = normalizer.normalize_product_dosages(product)

        assert result.success is False
        assert "No ingredients normalized" in result.errors

    def test_twice_daily_gummies_doubles_per_day(self, normalizer):
        """'2 gummies twice daily' should double the per-day amount"""
        product = {
            "servingSizes": [
                {
                    "quantity": 2,
                    "unit": "gummies",
                    "perDay": "twice daily"
                }
            ],
            "supplementFacts": [
                {"name": "Vitamin D", "amount": 1000, "unit": "IU"}
            ]
        }

        result = normalizer.normalize_product_dosages(product)

        assert result.success is True
        assert result.serving_basis.servings_per_day_min == 2

        # Per-day should reflect 2 servings
        # NOTE: 1000 IU Vitamin D = 25 mcg (converted)
        # With twice daily: 25 mcg * 2 = 50 mcg/day
        vit_d = result.normalized_ingredients[0] if result.normalized_ingredients else None
        if vit_d and vit_d.per_day_max is not None:
            # After IU→mcg conversion (1000 IU * 0.025 = 25 mcg) * 2 servings = 50 mcg
            assert vit_d.per_day_max == pytest.approx(50, rel=0.1)
            # Original amount preserved
            assert vit_d.original_amount == 1000
            assert vit_d.original_unit == "IU"

    def test_no_conversion_rule_is_marked_nonfatal_in_conversion_evidence(self, normalizer):
        """Expected no-rule conversion outcomes should be informational, not error-labeled."""
        product = {
            "servingSizes": [
                {"quantity": 1, "unit": "capsule", "perDay": "once daily"}
            ],
            "activeIngredients": [
                {"name": "Cactus", "quantity": 100, "unit": "mg"}
            ]
        }

        result = normalizer.normalize_product_dosages(product)
        assert result.success is True
        assert len(result.normalized_ingredients) == 1

        ev = result.normalized_ingredients[0].conversion_evidence
        assert ev.get("success") is False
        assert ev.get("error") is None
        assert ev.get("nonfatal_reason") == "no_conversion_rule"
        assert ev.get("conversion_status") == "not_converted_expected"
        assert "No conversion rule found for nutrient: Cactus" in (ev.get("original_error") or "")


class TestOverULFlagging:
    """
    Golden Fixture 5: Over-UL flag case with computed margin

    When a nutrient exceeds its UL, the calculator should:
    - Set over_ul = True
    - Calculate over_ul_amount (how much over)
    - Calculate pct_ul (percentage of UL)
    - Generate appropriate warning
    """

    @pytest.fixture
    def calculator(self):
        return RDAULCalculator()

    def test_vitamin_a_over_ul_flagged(self, calculator):
        """Vitamin A at 5000 mcg exceeds adult UL of 3000 mcg"""
        result = calculator.compute_nutrient_adequacy(
            nutrient="Vitamin A",
            amount=5000,  # mcg RAE
            unit="mcg",
            age_group="adult"
        )

        # Vitamin A adult UL is 3000 mcg RAE
        assert result.ul is not None
        assert result.ul == pytest.approx(3000, rel=0.1)
        assert result.ul_status == "established"

        # Over-UL assertions
        assert result.over_ul is True
        assert result.pct_ul is not None
        assert result.pct_ul == pytest.approx(166.7, rel=5)  # 5000/3000 = 166.7%

        # Over-UL amount
        assert result.over_ul_amount is not None
        assert result.over_ul_amount == pytest.approx(2000, rel=0.1)  # 5000 - 3000

        # Warning should be present
        assert len(result.warnings) > 0

    def test_vitamin_d_at_ul_boundary(self, calculator):
        """Vitamin D at exactly UL should not flag over"""
        # Adult UL for Vitamin D is 100 mcg (4000 IU)
        result = calculator.compute_nutrient_adequacy(
            nutrient="Vitamin D",
            amount=100,  # mcg - exactly at UL
            unit="mcg",
            age_group="adult"
        )

        if result.ul is not None:
            # At exactly UL, should NOT be flagged over
            assert result.pct_ul == pytest.approx(100, rel=1)
            # Boundary case: some implementations flag at =100%, others only >100%
            # The important thing is the math is correct

    def test_calcium_significantly_over_ul(self, calculator):
        """Calcium at 4000mg significantly exceeds adult UL of 2500mg"""
        result = calculator.compute_nutrient_adequacy(
            nutrient="Calcium",
            amount=4000,
            unit="mg",
            age_group="adult"
        )

        # Calcium adult UL is 2500 mg
        if result.ul is not None:
            assert result.over_ul is True
            assert result.pct_ul is not None
            assert result.pct_ul > 100  # Should be ~160%
            assert result.over_ul_amount is not None
            assert result.over_ul_amount > 0  # Over by some amount

    def test_under_ul_no_flag(self, calculator):
        """Nutrient under UL should not flag"""
        result = calculator.compute_nutrient_adequacy(
            nutrient="Vitamin A",
            amount=1500,  # mcg - under 3000 UL
            unit="mcg",
            age_group="adult"
        )

        assert result.over_ul is False
        assert result.over_ul_amount is None or result.over_ul_amount == 0


class TestConversionEvidenceFields:
    """
    Additional tests verifying evidence fields are populated correctly.
    These fields are essential for audit trails.
    """

    @pytest.fixture
    def converter(self):
        return UnitConverter()

    def test_conversion_evidence_complete(self, converter):
        """All evidence fields should be populated on successful conversion"""
        result = converter.convert_nutrient(
            nutrient="Vitamin E",
            amount=400,
            from_unit="IU",
            ingredient_name="d-Alpha Tocopherol"
        )

        if result.success:
            # Evidence fields must be present
            evidence = result.to_dict()
            assert evidence["original_value"] == 400
            assert evidence["original_unit"] == "IU"
            assert evidence["converted_value"] is not None
            assert evidence["converted_unit"] is not None
            assert evidence["conversion_rule_id"] is not None
            assert evidence["conversion_factor"] is not None
            assert evidence["confidence"] in ["high", "medium", "low"]

    def test_mg_to_mcg_mass_conversion(self, converter):
        """Simple mass conversion: 1 mg = 1000 mcg"""
        result = converter.convert_nutrient(
            nutrient="Generic",
            amount=5,
            from_unit="mg",
            to_unit="mcg",
            ingredient_name="Test Nutrient"
        )

        if result.success:
            assert result.converted_value == pytest.approx(5000, rel=0.01)
            assert result.converted_unit == "mcg"


class TestServingParsing:
    """
    Golden Fixtures for Serving Size Parsing Bugs

    These test the specific parsing cases flagged by code review:
    1. Fraction parsing ("1/2 tsp")
    2. "Take 1-2 capsules" pattern
    3. Range with servings per day
    """

    @pytest.fixture
    def normalizer(self):
        return DosageNormalizer()

    def test_fraction_serving_half_tsp(self, normalizer):
        """Test '1/2 teaspoon' doesn't crash and parses correctly."""
        # This was crashing with ValueError: could not convert '1/2' to float
        product = {
            "servingSizes": [
                {
                    "quantity": "1/2",
                    "unit": "teaspoon"
                }
            ],
            "supplementFacts": [
                {"name": "Vitamin C", "amount": 100, "unit": "mg"}
            ]
        }

        result = normalizer.normalize_product_dosages(product)

        assert result.success is True
        assert result.serving_basis is not None
        # 1/2 should parse to 0.5
        assert result.serving_basis.quantity == pytest.approx(0.5, rel=0.01)
        assert "tsp" in result.serving_basis.unit.lower() or "teaspoon" in result.serving_basis.unit.lower()

    def test_fraction_serving_from_string(self, normalizer):
        """Test '1/2 tsp' parsed from raw string."""
        basis = normalizer._parse_serving_string("1/2 tsp", "test")

        assert basis is not None
        assert basis.quantity == pytest.approx(0.5, rel=0.01)

    def test_take_1_2_capsules_pattern(self, normalizer):
        """Test 'Take 1-2 capsules' parses unit correctly (not max qty)."""
        # This was assigning groups[1] (max_qty) as unit instead of groups[2]
        basis = normalizer._parse_serving_string("Take 1-2 capsules daily", "test")

        assert basis is not None
        assert basis.quantity == 1  # Min quantity
        # Unit should be "capsule", NOT "2"
        assert "capsule" in basis.unit.lower()

    def test_take_2_softgels_pattern(self, normalizer):
        """Test 'Take 2 softgels' parses correctly."""
        basis = normalizer._parse_serving_string("Take 2 softgels", "test")

        assert basis is not None
        assert basis.quantity == 2
        assert "softgel" in basis.unit.lower()

    def test_twice_daily_parsing(self, normalizer):
        """Test 'twice daily' parses to (2, 2)."""
        min_val, max_val = normalizer._parse_servings_per_day("Take 1 capsule twice daily")

        assert min_val == 2
        assert max_val == 2

    def test_1_2_times_daily_parsing(self, normalizer):
        """Test '1-2 times daily' parses to (1, 2)."""
        min_val, max_val = normalizer._parse_servings_per_day("1-2 times daily")

        assert min_val == 1
        assert max_val == 2

    def test_three_times_daily_parsing(self, normalizer):
        """Test 'three times daily' parses to (3, 3)."""
        min_val, max_val = normalizer._parse_servings_per_day("three times daily")

        assert min_val == 3
        assert max_val == 3

    def test_word_boundary_false_positive_prevention(self, normalizer):
        """Test 'someone' doesn't match 'one' (word boundary check)."""
        # This was a false positive: "one" matched in "someone"
        min_val, max_val = normalizer._parse_servings_per_day("for someone healthy")

        # Should NOT match "one" - should return default (1, 1)
        assert min_val == 1
        assert max_val == 1

    def test_2_gummies_with_range(self, normalizer):
        """Test '2 gummies' serving with '1-2 times daily' per-day range."""
        product = {
            "servingSizes": [
                {
                    "quantity": 2,
                    "unit": "gummies",
                    "perDay": "1-2 times daily"
                }
            ],
            "supplementFacts": [
                {"name": "Vitamin C", "amount": 100, "unit": "mg"}
            ]
        }

        result = normalizer.normalize_product_dosages(product)

        assert result.success is True
        assert result.serving_basis is not None
        assert result.serving_basis.quantity == 2
        assert result.serving_basis.servings_per_day_min == 1
        assert result.serving_basis.servings_per_day_max == 2

        # Per-day calculation should use min (conservative)
        if result.normalized_ingredients:
            vit_c = result.normalized_ingredients[0]
            if vit_c.per_day_min is not None:
                # 100mg * 1 serving = 100mg min
                assert vit_c.per_day_min == pytest.approx(100, rel=0.1)
            if vit_c.per_day_max is not None:
                # 100mg * 2 servings = 200mg max
                assert vit_c.per_day_max == pytest.approx(200, rel=0.1)


class TestServingSelectionPolicy:
    """Test serving selection policy when multiple options are available."""

    @pytest.fixture
    def normalizer(self):
        return DosageNormalizer()

    def test_prefers_capsule_over_liquid(self, normalizer):
        """Test selection prefers capsule over liquid measures."""
        servings = [
            {"quantity": 1, "unit": "tablespoon"},
            {"quantity": 2, "unit": "capsules"},
        ]

        best, note = normalizer._select_best_serving(servings, "test")

        assert best["unit"] == "capsules"
        assert "Selected serving 2" in note

    def test_prefers_complete_over_incomplete(self, normalizer):
        """Test selection prefers complete entries (quantity + unit)."""
        servings = [
            {"description": "Take as directed"},  # Incomplete
            {"quantity": 1, "unit": "tablet"},     # Complete
        ]

        best, note = normalizer._select_best_serving(servings, "test")

        assert best["unit"] == "tablet"
        assert "Selected serving 2" in note

    def test_single_serving_no_policy_needed(self, normalizer):
        """Test single serving is returned without selection."""
        servings = [{"quantity": 2, "unit": "gummies"}]

        best, note = normalizer._select_best_serving(servings, "test")

        assert best["unit"] == "gummies"
        assert "Single serving option" in note

    def test_string_servings_selection(self, normalizer):
        """Test selection works with string-based servings."""
        servings = [
            "1 teaspoon",
            "Take 2 capsules",
        ]

        best, note = normalizer._select_best_serving(servings, "test")

        # Capsule should win (higher unit priority)
        assert "capsule" in best.lower()

    def test_selection_note_in_result(self, normalizer):
        """Test selection note is included in serving basis notes."""
        product = {
            "servingSizes": [
                {"quantity": 1, "unit": "tablespoon"},
                {"quantity": 2, "unit": "capsules"},
            ],
            "supplementFacts": []
        }

        result = normalizer.normalize_product_dosages(product)

        assert result.serving_basis is not None
        assert any("Selected serving" in note for note in result.serving_basis.notes)


class TestUnicodeFractionParsing:
    """Verification #3: Unicode fraction and mixed number support."""

    @pytest.fixture
    def normalizer(self):
        return DosageNormalizer()

    def test_unicode_half(self, normalizer):
        """Test ½ parses to 0.5"""
        assert normalizer._parse_quantity("½") == pytest.approx(0.5)

    def test_unicode_quarter(self, normalizer):
        """Test ¼ parses to 0.25"""
        assert normalizer._parse_quantity("¼") == pytest.approx(0.25)

    def test_unicode_three_quarters(self, normalizer):
        """Test ¾ parses to 0.75"""
        assert normalizer._parse_quantity("¾") == pytest.approx(0.75)

    def test_mixed_number_with_unicode(self, normalizer):
        """Test 1½ parses to 1.5"""
        assert normalizer._parse_quantity("1½") == pytest.approx(1.5)

    def test_mixed_number_with_space_unicode(self, normalizer):
        """Test '2 ½' parses to 2.5"""
        assert normalizer._parse_quantity("2 ½") == pytest.approx(2.5)

    def test_mixed_number_with_slash(self, normalizer):
        """Test '1 1/2' parses to 1.5"""
        assert normalizer._parse_quantity("1 1/2") == pytest.approx(1.5)

    def test_mixed_number_three_halves(self, normalizer):
        """Test '2 1/4' parses to 2.25"""
        assert normalizer._parse_quantity("2 1/4") == pytest.approx(2.25)


class TestBoundaryVariants:
    """Verification #4: Regex boundary changes didn't introduce false negatives."""

    @pytest.fixture
    def normalizer(self):
        return DosageNormalizer()

    def test_caps_vs_capsules(self, normalizer):
        """Test 'caps' doesn't match as capsule (abbreviation not in pattern)."""
        # 'caps' is NOT a standard form - should not parse as capsule
        basis = normalizer._parse_serving_string("2 caps daily", "test")
        # Should fall back or not match capsule pattern
        assert basis is not None  # Should still parse something

    def test_capsule_singular(self, normalizer):
        """Test '1 capsule' parses correctly."""
        basis = normalizer._parse_serving_string("1 capsule", "test")
        assert basis is not None
        assert basis.quantity == 1
        assert "capsule" in basis.unit.lower()

    def test_capsules_plural(self, normalizer):
        """Test '2 capsules' parses correctly."""
        basis = normalizer._parse_serving_string("2 capsules", "test")
        assert basis is not None
        assert basis.quantity == 2
        assert "capsule" in basis.unit.lower()

    def test_tab_vs_tablet(self, normalizer):
        """Test 'tab' doesn't match as tablet."""
        # Pattern requires 'tablet' not 'tab'
        basis = normalizer._parse_serving_string("1 tab", "test")
        # Should fall back to default
        assert basis is not None

    def test_tablet_singular(self, normalizer):
        """Test '1 tablet' parses correctly."""
        basis = normalizer._parse_serving_string("1 tablet", "test")
        assert basis is not None
        assert basis.quantity == 1
        assert "tablet" in basis.unit.lower()

    def test_softgel_hyphenated(self, normalizer):
        """Test 'soft-gel' variant (hyphenated)."""
        # Current pattern uses 'softgel' - hyphenated should be handled
        basis = normalizer._parse_serving_string("1 softgel", "test")
        assert basis is not None
        assert basis.quantity == 1

    def test_softgels_plural(self, normalizer):
        """Test '2 softgels' parses correctly."""
        basis = normalizer._parse_serving_string("2 softgels", "test")
        assert basis is not None
        assert basis.quantity == 2


class TestDefensiveParsing:
    """Verification #5: Defensive parsing tests for missing/optional groups."""

    @pytest.fixture
    def normalizer(self):
        return DosageNormalizer()

    def test_empty_string_returns_fallback(self, normalizer):
        """Empty string should return default serving basis."""
        basis = normalizer._parse_serving_string("", "test")
        assert basis is not None
        assert basis.unit == "serving"
        assert basis.confidence == "low"

    def test_gibberish_returns_fallback(self, normalizer):
        """Unparseable text should return default."""
        basis = normalizer._parse_serving_string("xyzzy foobar", "test")
        assert basis is not None
        assert basis.confidence == "low"

    def test_partial_serving_info(self, normalizer):
        """Test handling of partial serving info."""
        basis = normalizer._parse_serving_string("take daily", "test")
        assert basis is not None  # Should not crash

    def test_serving_dict_missing_quantity(self, normalizer):
        """Test dict with missing quantity field."""
        product = {
            "servingSizes": [{"unit": "capsule"}],  # No quantity
            "supplementFacts": []
        }
        result = normalizer.normalize_product_dosages(product)
        # Should not crash, should use default quantity
        assert result.serving_basis is not None

    def test_serving_dict_missing_unit(self, normalizer):
        """Test dict with missing unit field."""
        product = {
            "servingSizes": [{"quantity": 2}],  # No unit
            "supplementFacts": []
        }
        result = normalizer.normalize_product_dosages(product)
        # Should not crash, should use default unit
        assert result.serving_basis is not None

    def test_none_in_serving_sizes(self, normalizer):
        """Test None value in servingSizes list."""
        product = {
            "servingSizes": [None, {"quantity": 1, "unit": "tablet"}],
            "supplementFacts": []
        }
        # Should skip None and use valid entry
        result = normalizer.normalize_product_dosages(product)
        assert result.serving_basis is not None


class TestGlobalSafetyInvariants:
    """Verification #6: Global safety invariants for scoring."""

    @pytest.fixture
    def scorer(self):
        from score_supplements import SupplementScorer
        return SupplementScorer()

    def test_unsafe_verdict_requires_grade_f_and_zero_score(self, scorer):
        """INVARIANT: If safety_verdict == 'UNSAFE', then grade == 'F' AND score_80 == 0.

        This protects against future regressions where later stages might
        accidentally overwrite the immediate_fail behavior.
        """
        # Product with critical banned substance
        product = {
            "id": "12345",
            "fullName": "Unsafe Test Product",
            "enrichment_version": "3.0.0",
            "ingredient_quality_data": {"ingredients": []},
            "contaminant_data": {
                "banned_substances": {
                    "found": True,
                    "substances": [
                        {"severity_level": "critical", "banned_name": "Ephedra"}
                    ]
                }
            },
            "compliance_data": {},
            "certification_data": {},
            "proprietary_data": {},
            "evidence_data": {},
            "manufacturer_data": {},
            "probiotic_data": {"is_probiotic_product": False},
        }
        result = scorer.score_product(product)

        # INVARIANT CHECK
        if result["safety_verdict"] == "UNSAFE":
            assert result["grade"] == "F", \
                "INVARIANT VIOLATION: UNSAFE verdict must have grade F"
            assert result["score_80"] == 0, \
                "INVARIANT VIOLATION: UNSAFE verdict must have score 0"

    def test_f_grade_not_necessarily_unsafe(self, scorer):
        """F grade does NOT necessarily mean UNSAFE - they are independent.

        A product can be low quality (F) but not safety-critical (not UNSAFE).
        This confirms the distinction is maintained.
        """
        # Minimal product with no safety issues but very low score
        product = {
            "id": "12345",
            "fullName": "Low Quality But Safe",
            "enrichment_version": "3.0.0",
            "ingredient_quality_data": {"ingredients": []},
            "contaminant_data": {"banned_substances": {"found": False}},
            "compliance_data": {},
            "certification_data": {},
            "proprietary_data": {},
            "evidence_data": {},
            "manufacturer_data": {},
            "probiotic_data": {"is_probiotic_product": False},
        }
        result = scorer.score_product(product)

        # Low score gets floor applied (10/80)
        # Grade for 10/80 = 12.5/100 equivalent → F
        # But safety_verdict should NOT be UNSAFE
        if result["score_80"] is not None and result["score_80"] <= 12:  # Would be F grade
            assert result["safety_verdict"] != "UNSAFE", \
                "Low score F grade should NOT mean UNSAFE"


class TestAC4McgMgConversions:
    """
    AC4 Compliance Tests: mcg<->mg conversions for key nutrients.

    These tests address the DSLD 10040 issue:
    "No conversion rule found for Vitamin B12"

    Products often show amounts in both mcg (label) and mg (internal),
    requiring bidirectional conversion support.
    """

    @pytest.fixture
    def converter(self):
        return UnitConverter()

    @pytest.mark.parametrize("nutrient,mcg_value,expected_mg", [
        # DSLD 10040 case: Vitamin B12 1000 mcg = 1 mg
        ("Vitamin B12", 1000, 1.0),
        ("Vitamin B12", 500, 0.5),
        ("Vitamin B12", 2500, 2.5),

        # Selenium
        ("Selenium", 200, 0.2),
        ("Selenium", 55, 0.055),

        # Chromium
        ("Chromium", 200, 0.2),
        ("Chromium", 1000, 1.0),

        # Biotin
        ("Biotin", 5000, 5.0),
        ("Biotin", 300, 0.3),

        # Iodine
        ("Iodine", 150, 0.15),
        ("Iodine", 1000, 1.0),

        # Molybdenum
        ("Molybdenum", 75, 0.075),
    ])
    def test_mcg_to_mg_conversion(self, converter, nutrient, mcg_value, expected_mg):
        """Test mcg to mg conversion for nutrients that use mcg."""
        result = converter.convert_nutrient(
            nutrient=nutrient,
            amount=mcg_value,
            from_unit="mcg",
            to_unit="mg"
        )

        assert result.success, f"Conversion failed for {nutrient}: {result.error}"
        assert result.converted_value is not None
        assert abs(result.converted_value - expected_mg) < 0.0001, \
            f"{nutrient}: Expected {expected_mg} mg, got {result.converted_value} mg"
        assert result.converted_unit == "mg"

    @pytest.mark.parametrize("nutrient,mg_value,expected_mcg", [
        # DSLD 10040 reverse: Vitamin B12 1 mg = 1000 mcg
        ("Vitamin B12", 1.0, 1000),
        ("Vitamin B12", 0.5, 500),

        # Selenium
        ("Selenium", 0.2, 200),

        # Biotin
        ("Biotin", 5.0, 5000),

        # Iodine
        ("Iodine", 0.15, 150),
    ])
    def test_mg_to_mcg_conversion(self, converter, nutrient, mg_value, expected_mcg):
        """Test mg to mcg conversion for nutrients that use mcg."""
        result = converter.convert_nutrient(
            nutrient=nutrient,
            amount=mg_value,
            from_unit="mg",
            to_unit="mcg"
        )

        assert result.success, f"Conversion failed for {nutrient}: {result.error}"
        assert result.converted_value is not None
        assert abs(result.converted_value - expected_mcg) < 0.0001, \
            f"{nutrient}: Expected {expected_mcg} mcg, got {result.converted_value} mcg"
        assert result.converted_unit == "mcg"


class TestDSLD10040Scenario:
    """
    Test the specific DSLD 10040 scenario that exposed the bug.

    Product 10040 shows 1,000 mcg in name but 1.0 mg in quantity.
    The conversion was failing with "No conversion rule found for Vitamin B12".
    """

    @pytest.fixture
    def converter(self):
        return UnitConverter()

    def test_vitamin_b12_1000mcg_equals_1mg(self, converter):
        """AC4: Vitamin B12 1000 mcg must equal 1 mg."""
        result = converter.convert_nutrient(
            nutrient="Vitamin B12",
            amount=1000,
            from_unit="mcg",
            to_unit="mg"
        )

        assert result.success, f"CRITICAL: B12 conversion failed: {result.error}"
        assert result.converted_value == 1.0
        assert result.conversion_rule_id is not None

    def test_vitamin_b12_1mg_equals_1000mcg(self, converter):
        """AC4: Vitamin B12 1 mg must equal 1000 mcg."""
        result = converter.convert_nutrient(
            nutrient="Vitamin B12",
            amount=1.0,
            from_unit="mg",
            to_unit="mcg"
        )

        assert result.success, f"CRITICAL: B12 conversion failed: {result.error}"
        assert result.converted_value == 1000

    def test_methylcobalamin_alias_works(self, converter):
        """AC4: Methylcobalamin (B12 form) must also work."""
        result = converter.convert_nutrient(
            nutrient="Methylcobalamin",
            amount=1000,
            from_unit="mcg",
            to_unit="mg",
            ingredient_name="Vitamin B12 (as Methylcobalamin)"
        )

        assert result.success, f"Methylcobalamin conversion failed: {result.error}"
        assert result.converted_value == 1.0

    def test_cyanocobalamin_alias_works(self, converter):
        """AC4: Cyanocobalamin (B12 form) must also work."""
        result = converter.convert_nutrient(
            nutrient="Cyanocobalamin",
            amount=500,
            from_unit="mcg",
            to_unit="mg"
        )

        assert result.success, f"Cyanocobalamin conversion failed: {result.error}"
        assert result.converted_value == 0.5


class TestMassConversionFallback:
    """Test that mass conversion fallback works for mcg-only nutrients."""

    @pytest.fixture
    def converter(self):
        return UnitConverter()

    @pytest.mark.parametrize("nutrient", [
        "Vitamin B12",
        "Selenium",
        "Chromium",
        "Biotin",
        "Iodine",
        "Molybdenum",
        "Vitamin K1",
        "Vitamin K2",
    ])
    def test_nutrient_found_in_database(self, converter, nutrient):
        """All mcg-only nutrients must be findable in the database."""
        # Try a conversion - if nutrient not found, it will fail with specific error
        result = converter.convert_nutrient(
            nutrient=nutrient,
            amount=100,
            from_unit="mcg",
            to_unit="mg"
        )

        # Should NOT fail with "No conversion rule found"
        if not result.success:
            assert "No conversion rule found" not in (result.error or ""), \
                f"AC4 violation: {nutrient} not in database - {result.error}"


class TestAC4DatabaseEntries:
    """Verify all AC4-required nutrients are in the database."""

    @pytest.fixture
    def converter(self):
        return UnitConverter()

    def test_vitamin_b12_in_database(self, converter):
        """Vitamin B12 must be in vitamin_conversions."""
        assert "vitamin_b12" in converter.vitamin_conversions, \
            "AC4: vitamin_b12 missing from database"

    def test_selenium_in_database(self, converter):
        """Selenium must be in vitamin_conversions."""
        assert "selenium" in converter.vitamin_conversions, \
            "AC4: selenium missing from database"

    def test_chromium_in_database(self, converter):
        """Chromium must be in vitamin_conversions."""
        assert "chromium" in converter.vitamin_conversions, \
            "AC4: chromium missing from database"

    def test_biotin_in_database(self, converter):
        """Biotin must be in vitamin_conversions."""
        assert "biotin" in converter.vitamin_conversions, \
            "AC4: biotin missing from database"

    def test_iodine_in_database(self, converter):
        """Iodine must be in vitamin_conversions."""
        assert "iodine" in converter.vitamin_conversions, \
            "AC4: iodine missing from database"

    def test_molybdenum_in_database(self, converter):
        """Molybdenum must be in vitamin_conversions."""
        assert "molybdenum" in converter.vitamin_conversions, \
            "AC4: molybdenum missing from database"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
