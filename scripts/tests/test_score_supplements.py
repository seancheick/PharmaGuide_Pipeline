#!/usr/bin/env python3
"""
Unit tests for DSLD Supplement Scoring System
=============================================
Tests core scoring functionality, edge cases, and validation.

Run with: python -m pytest tests/test_score_supplements.py -v
"""

import pytest
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from score_supplements import SupplementScorer


class TestSupplementScorerValidation:
    """Test input validation functionality."""

    def test_validate_enriched_product_valid(self):
        """Test validation passes for valid product."""
        product = {
            "id": "12345",
            "fullName": "Test Supplement",
            "ingredient_quality_data": {},
            "safety_data": {},
        }
        is_valid, issues = SupplementScorer.validate_enriched_product(product)
        assert is_valid is True

    def test_validate_enriched_product_with_dsld_id(self):
        """Test validation passes for product with dsld_id."""
        product = {
            "dsld_id": "12345",
            "product_name": "Test Supplement",
        }
        is_valid, issues = SupplementScorer.validate_enriched_product(product)
        assert is_valid is True

    def test_validate_enriched_product_missing_id(self):
        """Test validation fails for missing ID."""
        product = {"fullName": "Test Supplement"}
        is_valid, issues = SupplementScorer.validate_enriched_product(product)
        assert is_valid is False
        assert any("ID" in issue for issue in issues)

    def test_validate_enriched_product_missing_name(self):
        """Test validation fails for missing name."""
        product = {"id": "12345"}
        is_valid, issues = SupplementScorer.validate_enriched_product(product)
        assert is_valid is False
        assert any("name" in issue for issue in issues)

    def test_validate_enriched_product_not_dict(self):
        """Test validation fails for non-dict input."""
        is_valid, issues = SupplementScorer.validate_enriched_product("not a dict")
        assert is_valid is False


class TestSectionAScoring:
    """Test Section A: Ingredient Quality scoring."""

    @pytest.fixture
    def scorer(self):
        """Create scorer instance with default config."""
        return SupplementScorer()

    def test_score_a1_bioavailability_empty_ingredients(self, scorer):
        """Test A1 returns 0 for empty ingredients."""
        score, notes = scorer._score_a1_bioavailability([], "generic", {})
        assert score == 0
        assert "No ingredients" in notes[0]

    def test_score_a1_bioavailability_with_ingredients(self, scorer):
        """Test A1 calculates weighted average correctly."""
        ingredients = [
            {"score": 10, "dosage_importance": 1.0},
            {"score": 8, "dosage_importance": 0.5},
        ]
        config = {"max": 15}
        score, notes = scorer._score_a1_bioavailability(ingredients, "generic", config)
        # Weighted avg: (10*1 + 8*0.5) / (1 + 0.5) = 14/1.5 = 9.33
        assert 9 <= score <= 10

    def test_score_a1_multivitamin_floor(self, scorer):
        """Test A1 applies floor multiplier for multivitamins."""
        ingredients = [{"score": 5, "dosage_importance": 1.0}]
        config = {"max": 15, "floor_multiplier_for_multis": 0.7}
        score, notes = scorer._score_a1_bioavailability(ingredients, "multivitamin", config)
        # Floor should be 15 * 0.7 = 10.5
        assert score >= 10.5

    def test_score_a2_premium_forms(self, scorer):
        """Test A2 counts premium forms correctly."""
        ingredients = [
            {"bio_score": 15},  # Premium
            {"bio_score": 10},  # Not premium
            {"bio_score": 14},  # Premium
        ]
        config = {"max": 3, "threshold_bio_score": 12, "points_per_form": 0.5}
        score, notes, count = scorer._score_a2_premium_forms(ingredients, config)
        assert count == 2
        assert score == 1.0

    def test_score_a3_delivery_no_match(self, scorer):
        """Test A3 returns 0 when no delivery system matched."""
        score, notes = scorer._score_a3_delivery({"matched": False}, {})
        assert score == 0
        assert "No enhanced delivery" in notes[0]

    def test_score_a4_absorption_qualifies(self, scorer):
        """Test A4 awards points when absorption enhancer qualifies."""
        absorption_data = {
            "qualifies_for_bonus": True,
            "enhancers": [{"name": "BioPerine"}],
            "enhanced_nutrients_present": ["Curcumin"],
        }
        config = {"max": 3, "points_if_qualifies": 3}
        score, notes = scorer._score_a4_absorption(absorption_data, config)
        assert score == 3


class TestSectionBScoring:
    """Test Section B: Safety & Purity scoring."""

    @pytest.fixture
    def scorer(self):
        return SupplementScorer()

    def test_score_b1_contaminants_none_found(self, scorer):
        """Test B1 returns no penalty when no contaminants found."""
        contaminant_data = {"banned_substances": {"found": False}}
        penalty, notes, immediate_fail, details = scorer._score_b1_contaminants(
            contaminant_data, {}
        )
        assert penalty == 0
        assert immediate_fail is False

    def test_score_b1_critical_substance_immediate_fail(self, scorer):
        """Test B1 triggers immediate fail for critical substances."""
        contaminant_data = {
            "banned_substances": {
                "found": True,
                "substances": [{"severity_level": "critical", "banned_name": "Ephedra"}],
            }
        }
        config = {"banned_recalled": {"critical": -15}}
        penalty, notes, immediate_fail, details = scorer._score_b1_contaminants(
            contaminant_data, config
        )
        assert immediate_fail is True
        assert penalty < 0

    def test_score_b2_certifications_bonus(self, scorer):
        """Test B2 awards certification bonus."""
        cert_data = {
            "has_certifications": True,
            "certifications": [{"tier": "gold", "name": "NSF"}],
        }
        config = {
            "third_party": {
                "points_per_cert": 5,
                "max_total": 10,
                "recognized_certs": ["NSF"],
            }
        }
        pts, notes = scorer._score_b2_certifications(cert_data, config)
        assert pts > 0


class TestSectionDScoring:
    """Test Section D: Brand Trust scoring."""

    @pytest.fixture
    def scorer(self):
        return SupplementScorer()

    def test_score_d_top_manufacturer_exact_match(self, scorer):
        """Test D awards points for exact manufacturer match."""
        top_mfr = {"found": True, "match_type": "exact", "name": "NOW Foods"}
        pts, notes = scorer._score_d_top_manufacturer(top_mfr)
        assert pts > 0
        assert "NOW Foods" in notes[0]

    def test_score_d_top_manufacturer_fuzzy_low_confidence(self, scorer):
        """Test D doesn't award points for low-confidence fuzzy match."""
        top_mfr = {"found": True, "match_type": "fuzzy", "match_confidence": 0.5}
        pts, notes = scorer._score_d_top_manufacturer(top_mfr)
        assert pts == 0

    def test_score_d_violations_capped(self, scorer):
        """Test D caps violation deductions."""
        violations = {
            "found": True,
            "violations": [
                {"total_deduction": -10},
                {"total_deduction": -15},
                {"total_deduction": -10},
            ],
        }
        pts, notes = scorer._score_d_violations(violations)
        # Total would be -35, but should be capped at -20
        assert pts >= -20


class TestProbioticBonus:
    """Test probiotic bonus scoring."""

    @pytest.fixture
    def scorer(self):
        return SupplementScorer()

    def test_probiotic_bonus_not_probiotic(self, scorer):
        """Test probiotic bonus returns 0 for non-probiotic products."""
        product = {"probiotic_data": {"is_probiotic_product": False}}
        result = scorer._score_probiotic_bonus(product)
        assert result["score"] == 0
        assert result["applied"] is False

    def test_probiotic_cfu_bonus_at_expiration(self, scorer):
        """Test CFU bonus requires expiration guarantee."""
        probiotic_data = {
            "probiotic_blends": [
                {"cfu_data": {"has_cfu": True, "billion_count": 15, "guarantee_type": "expiration"}}
            ]
        }
        pts, notes, details = scorer._score_probiotic_cfu(probiotic_data)
        assert pts > 0
        assert "expiration" in details["note"]

    def test_probiotic_cfu_no_bonus_without_expiration(self, scorer):
        """Test CFU bonus not awarded without expiration guarantee."""
        probiotic_data = {
            "probiotic_blends": [
                {"cfu_data": {"has_cfu": True, "billion_count": 15, "guarantee_type": "manufacture"}}
            ]
        }
        pts, notes, details = scorer._score_probiotic_cfu(probiotic_data)
        assert pts == 0

    def test_probiotic_strain_diversity_tiered(self, scorer):
        """Test strain diversity uses tiered scoring."""
        # 4-7 strains = tier 1
        data_4 = {"total_strain_count": 5}
        pts_4, _, _ = scorer._score_probiotic_strain_diversity(data_4)

        # 8+ strains = tier 2
        data_8 = {"total_strain_count": 10}
        pts_8, _, _ = scorer._score_probiotic_strain_diversity(data_8)

        assert pts_8 > pts_4


class TestScoreProduct:
    """Test main score_product method."""

    @pytest.fixture
    def scorer(self):
        return SupplementScorer()

    def test_score_product_complete(self, scorer):
        """Test scoring a complete product returns all sections."""
        product = {
            "id": "12345",
            "fullName": "Test Supplement",
            "ingredient_quality_data": {"ingredients": []},
            "safety_data": {"contaminant_data": {}, "certification_data": {}},
            "evidence_data": {},
            "manufacturer_data": {},
            "probiotic_data": {"is_probiotic_product": False},
        }
        result = scorer.score_product(product)

        # Check required output keys
        assert "score_80" in result
        assert "grade" in result
        assert "detailed_breakdown" in result
        assert "section_scores" in result

    def test_score_product_applies_ceiling(self, scorer):
        """Test scoring applies 80-point ceiling."""
        # Even with perfect scores, total shouldn't exceed 80
        product = {
            "id": "12345",
            "fullName": "Perfect Supplement",
            "ingredient_quality_data": {"ingredients": [{"score": 18} for _ in range(10)]},
            "safety_data": {"contaminant_data": {}, "certification_data": {"has_certifications": True}},
            "evidence_data": {"clinical_studies": {"has_studies": True}},
            "manufacturer_data": {"top_manufacturer": {"found": True, "match_type": "exact"}},
            "probiotic_data": {"is_probiotic_product": False},
        }
        result = scorer.score_product(product)
        assert result["score_80"] <= 80


class TestLetterGrades:
    """Test letter grade assignment."""

    @pytest.fixture
    def scorer(self):
        return SupplementScorer()

    def test_letter_grade_boundaries(self, scorer):
        """Test letter grade boundaries are correct."""
        # These are based on 0-100 equivalent scale
        assert scorer._calculate_grade(95) == "A+"
        assert scorer._calculate_grade(90) == "A+"
        assert scorer._calculate_grade(89) == "A"
        assert scorer._calculate_grade(85) == "A"
        assert scorer._calculate_grade(80) == "A-"
        assert scorer._calculate_grade(77) == "B+"
        assert scorer._calculate_grade(73) == "B"
        assert scorer._calculate_grade(70) == "B-"
        assert scorer._calculate_grade(67) == "C+"
        assert scorer._calculate_grade(63) == "C"
        assert scorer._calculate_grade(60) == "C-"
        assert scorer._calculate_grade(50) == "D"
        assert scorer._calculate_grade(40) == "F"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
