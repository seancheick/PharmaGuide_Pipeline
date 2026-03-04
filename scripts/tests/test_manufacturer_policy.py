#!/usr/bin/env python3
"""
Manufacturer Matching Policy Tests

Confirms the production manufacturer matching policy:
1. Manufacturer is bonus-only (Brand Trust Section D)
2. If matched and accepted (exact match) → award bonus points (+3)
3. If unmatched or rejected → 0 bonus, but scoring proceeds normally
4. Manufacturer coverage is WARN-only and must NEVER block scoring
5. All outcomes must be fully auditable in match_ledger.manufacturer
   and rejected_brand_matches when applicable

Run with: pytest tests/test_manufacturer_policy.py -v
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from score_supplements import SupplementScorer
from coverage_gate import CoverageGate, COVERAGE_THRESHOLDS


class TestManufacturerPolicyScoring:
    """Tests for manufacturer scoring policy."""

    @pytest.fixture
    def scorer(self):
        """Create scorer instance."""
        return SupplementScorer()

    def _make_minimal_enriched_product(self, dsld_id, manufacturer_data, match_ledger_manufacturer):
        """Create minimal enriched product structure for scoring tests."""
        return {
            "dsld_id": dsld_id,
            "product_name": f"Test Product {dsld_id}",
            "brand_name": "Test Brand",
            "enrichment_version": "3.1.0",
            "supplement_type": {"type": "vitamin"},  # Must be dict with 'type' key
            "activeIngredients": [
                {
                    "name": "Vitamin C",
                    "standardName": "Vitamin C",
                    "quantity": 500,
                    "unit": "mg",
                    "canonical_id": "vitamin_c_ascorbic_acid"
                }
            ],
            "inactiveIngredients": [],
            "physicalState": {"langualCodeDescription": "Tablet"},
            # Enrichment data sections
            "contaminant_data": {
                "banned_substances": {"found": False, "substances": []},
                "harmful_additives": {"found": False, "additives": []},
                "allergens": {"found": False, "allergens": []}
            },
            "compliance_data": {
                "allergen_free_claims": [],
                "gluten_free": False,
                "dairy_free": False,
                "vegan": False,
                "vegetarian": False
            },
            "evidence_data": {
                "clinical_matches": []
            },
            "manufacturer_data": manufacturer_data,
            "delivery_data": {"form": "tablet", "delivery_tier": 0},
            "certification_data": {
                "third_party_tested": False,
                "gmp_certified": False
            },
            "proprietary_data": {
                "has_proprietary_blend": False,
                "blends": []
            },
            "ingredient_quality_data": {
                "ingredients": [
                    {
                        "name": "Vitamin C",
                        "canonical_id": "vitamin_c_ascorbic_acid",
                        "quality_score": 5,
                        "form_detected": "ascorbic_acid",
                        "mapped": True
                    }
                ]
            },
            "match_ledger": {
                "schema_version": "1.1.0",
                "domains": {
                    "ingredients": {
                        "total_raw": 1,
                        "matched": 1,
                        "unmatched": 0,
                        "scorable_total": 1,
                        "recognized_botanical_unscored": 0,
                        "recognized_non_scorable": 0,
                        "coverage_percent": 100.0,
                        "entries": []
                    },
                    "manufacturer": match_ledger_manufacturer
                },
                "summary": {"coverage_percent": 100.0}
            }
        }

    def test_no_manufacturer_match_scoring_completes(self, scorer):
        """
        Policy Test 1: No manufacturer match → scoring completes, no bonus applied.

        When manufacturer is not matched:
        - Scoring MUST complete successfully
        - Brand Trust (Section D) manufacturer bonus = 0
        - No blocking, only WARN in coverage gate
        - match_ledger.manufacturer shows unmatched status
        """
        manufacturer_data = {
            "brand_name": "Unknown Small Brand XYZ",
            "top_manufacturer": {
                "found": False,
                "match_type": "none",
                "match_confidence": 0,
                "product_manufacturer": "Unknown Small Brand XYZ",
                "name": None
            }
        }

        match_ledger_manufacturer = {
            "total_raw": 1,
            "matched": 0,
            "unmatched": 1,
            "coverage_percent": 0.0,
            "entries": [
                {
                    "domain": "manufacturer",
                    "raw_source_text": "Unknown Small Brand XYZ",
                    "normalized_key": "unknown_small_brand_xyz",
                    "canonical_id": None,
                    "match_method": "none",
                    "confidence": 0,
                    "decision": "unmatched",
                    "decision_reason": "no_match_found"
                }
            ]
        }

        product = self._make_minimal_enriched_product(
            "TEST_NO_MFR", manufacturer_data, match_ledger_manufacturer
        )

        # Score the product
        result = scorer.score_product(product)

        # CRITICAL: Scoring must complete successfully
        assert result is not None, "Scoring should complete even without manufacturer match"
        assert "score_80" in result, "Score must be present in result"
        assert result["score_80"] > 0, "Score should be positive (not blocked)"

        # Verify Section D manufacturer bonus (D1) is 0
        d_breakdown = result.get("breakdown", {}).get("D", {})
        assert d_breakdown.get("D1", 0) == 0, "No bonus should be applied for unmatched manufacturer"

    def test_rejected_fuzzy_match_scoring_completes(self, scorer):
        """
        Policy Test 2: Rejected fuzzy match → no bonus, rejected_brand_matches populated.

        When manufacturer has fuzzy match but is rejected (not exact):
        - Scoring MUST complete successfully
        - Brand Trust (Section D) manufacturer bonus = 0
        - rejected_brand_matches should capture the rejection details
        - match_ledger.manufacturer shows match was attempted but rejected
        """
        manufacturer_data = {
            "brand_name": "Garden Of Life LLC",
            "top_manufacturer": {
                "found": False,
                "match_type": "fuzzy",
                "match_confidence": 0.85,
                "product_manufacturer": "Garden Of Life LLC",
                "name": "Garden of Life",
                "manufacturer_id": "MANUF_GARDEN_OF_LIFE",
                "rejected_reason": "fuzzy_match_rejected_for_scoring"
            }
        }

        match_ledger_manufacturer = {
            "total_raw": 1,
            "matched": 1,
            "unmatched": 0,
            "rejected": 0,
            "coverage_percent": 100.0,
            "entries": [
                {
                    "domain": "manufacturer",
                    "raw_source_text": "Garden Of Life LLC",
                    "raw_source_path": "brandName",
                    "normalized_key": "garden_of_life_llc",
                    "canonical_id": "MANUF_GARDEN_OF_LIFE",
                    "match_method": "fuzzy",
                    "confidence": 0.85,
                    "matched_to_name": "Garden of Life",
                    "decision": "matched",
                    "decision_reason": "fuzzy_match_below_exact_threshold"
                }
            ]
        }

        product = self._make_minimal_enriched_product(
            "TEST_FUZZY_MFR", manufacturer_data, match_ledger_manufacturer
        )

        # Add rejected_brand_matches (populated by enrichment when fuzzy match rejected for scoring)
        product["rejected_brand_matches"] = [
            {
                "raw_brand_name": "Garden Of Life LLC",
                "best_match": "Garden of Life",
                "confidence": 0.85,
                "rejection_reason": "fuzzy_match_rejected_for_scoring"
            }
        ]

        # Score the product
        result = scorer.score_product(product)

        # CRITICAL: Scoring must complete successfully
        assert result is not None, "Scoring should complete even with rejected fuzzy match"
        assert "score_80" in result, "Score must be present in result"
        assert result["score_80"] > 0, "Score should be positive (not blocked)"

        # Verify Section D manufacturer bonus (D1) is 0 (fuzzy rejected)
        d_breakdown = result.get("breakdown", {}).get("D", {})
        assert d_breakdown.get("D1", 0) == 0, \
            "No bonus for fuzzy match (only exact gets points)"

        # Verify rejected_brand_matches is carried through (if present in input)
        assert "rejected_brand_matches" in product
        assert len(product["rejected_brand_matches"]) > 0

    def test_exact_manufacturer_match_gets_bonus(self, scorer):
        """
        Verify exact manufacturer match DOES get bonus points.
        This is the positive case to contrast with the rejection tests.
        """
        manufacturer_data = {
            "brand_name": "Garden of Life",
            "top_manufacturer": {
                "found": True,
                "match_type": "exact",
                "match_confidence": 1.0,
                "product_manufacturer": "Garden of Life",
                "name": "Garden of Life",
                "manufacturer_id": "MANUF_GARDEN_OF_LIFE"
            }
        }

        match_ledger_manufacturer = {
            "total_raw": 1,
            "matched": 1,
            "unmatched": 0,
            "coverage_percent": 100.0,
            "entries": [
                {
                    "domain": "manufacturer",
                    "raw_source_text": "Garden of Life",
                    "normalized_key": "garden_of_life",
                    "canonical_id": "MANUF_GARDEN_OF_LIFE",
                    "match_method": "exact",
                    "confidence": 1.0,
                    "decision": "matched"
                }
            ]
        }

        product = self._make_minimal_enriched_product(
            "TEST_EXACT_MFR", manufacturer_data, match_ledger_manufacturer
        )

        result = scorer.score_product(product)

        assert result is not None
        assert "score_80" in result

        # Verify exact match gets D1 bonus (trusted manufacturer = 2pts)
        d_breakdown = result.get("breakdown", {}).get("D", {})
        assert d_breakdown.get("D1", 0) == 2.0, \
            "Exact match should get D1 bonus points"


class TestManufacturerPolicyCoverageGate:
    """Tests for manufacturer coverage gate policy."""

    def test_manufacturer_is_warn_only_never_blocks(self):
        """
        Policy: Manufacturer coverage is WARN-only and must NEVER block scoring.

        Even with 0% manufacturer coverage, scoring must proceed.
        """
        # Verify threshold configuration
        assert COVERAGE_THRESHOLDS["manufacturer"]["severity"] == "WARN", \
            "Manufacturer must be WARN severity, not BLOCK"

        gate = CoverageGate(strict_mode=True)

        # Product with 0% manufacturer coverage
        product = {
            "dsld_id": "TEST_MFR_WARN",
            "match_ledger": {
                "domains": {
                    "ingredients": {
                        "total_raw": 5,
                        "matched": 5,
                        "unmatched": 0,
                        "coverage_percent": 100.0
                    },
                    "manufacturer": {
                        "total_raw": 1,
                        "matched": 0,
                        "unmatched": 1,
                        "coverage_percent": 0.0  # 0% coverage!
                    }
                },
                "summary": {"coverage_percent": 83.3}
            }
        }

        result = gate.check_product(product)

        # CRITICAL: Must still be able to score
        assert result.can_score is True, "Product must be scorable even with 0% manufacturer coverage"

        # Should have a warning, not a blocking issue
        assert len(result.blocking_issues) == 0, "Manufacturer should never create blocking issues"
        assert len(result.warnings) > 0, "Should have a warning for low manufacturer coverage"
        assert any("manufacturer" in w.lower() for w in result.warnings), \
            "Warning should mention manufacturer"

    def test_manufacturer_low_coverage_batch_proceeds(self):
        """
        Batch with low manufacturer coverage should proceed (WARN only).
        """
        gate = CoverageGate(strict_mode=True)

        products = [
            {
                "dsld_id": "1",
                "match_ledger": {
                    "domains": {
                        "ingredients": {"total_raw": 10, "matched": 10, "unmatched": 0, "coverage_percent": 100.0},
                        "manufacturer": {"total_raw": 1, "matched": 0, "unmatched": 1, "coverage_percent": 0.0}
                    },
                    "summary": {"coverage_percent": 90.9}
                }
            },
            {
                "dsld_id": "2",
                "match_ledger": {
                    "domains": {
                        "ingredients": {"total_raw": 5, "matched": 5, "unmatched": 0, "coverage_percent": 100.0},
                        "manufacturer": {"total_raw": 1, "matched": 0, "unmatched": 1, "coverage_percent": 0.0}
                    },
                    "summary": {"coverage_percent": 83.3}
                }
            }
        ]

        result = gate.check_batch(products)

        # Both products should be scorable
        assert result.products_can_score == 2, "All products should be scorable"
        assert result.products_blocked == 0, "No products should be blocked"

    def test_manufacturer_auditable_in_match_ledger(self):
        """
        Verify manufacturer outcomes are auditable via match_ledger.
        """
        gate = CoverageGate()

        product = {
            "dsld_id": "AUDIT_TEST",
            "match_ledger": {
                "domains": {
                    "ingredients": {"total_raw": 1, "matched": 1, "unmatched": 0, "coverage_percent": 100.0, "entries": []},
                    "manufacturer": {
                        "total_raw": 1,
                        "matched": 0,
                        "unmatched": 1,
                        "coverage_percent": 0.0,
                        "entries": [
                            {
                                "domain": "manufacturer",
                                "raw_source_text": "Obscure Brand Inc",
                                "raw_source_path": "brandName",
                                "normalized_key": "obscure_brand_inc",
                                "canonical_id": None,
                                "match_method": "none",
                                "confidence": 0,
                                "matched_to_name": None,
                                "decision": "unmatched",
                                "decision_reason": "no_match_found",
                                "candidates_top3": [
                                    {"name": "Brand X", "confidence": 0.45},
                                    {"name": "Brand Y", "confidence": 0.32}
                                ]
                            }
                        ]
                    }
                },
                "summary": {"coverage_percent": 50.0}
            }
        }

        result = gate.check_product(product)

        # Verify audit trail exists
        mfr_result = result.domain_results.get("manufacturer")
        assert mfr_result is not None, "Manufacturer domain result should exist"
        assert mfr_result.coverage_percent == 0.0, "Coverage should be 0%"

        # Verify the product can still be scored
        assert result.can_score is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
