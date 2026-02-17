#!/usr/bin/env python3
"""Tests for v3.0 scoring engine behavior."""

from copy import deepcopy
from pathlib import Path
import sys

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from score_supplements import SupplementScorer, generate_impact_report


def make_base_product():
    return {
        "dsld_id": "p1",
        "product_name": "Test Product",
        "enrichment_version": "3.4.0",
        "supplement_type": {"type": "targeted", "active_count": 2},
        "ingredient_quality_data": {
            "total_active": 2,
            "unmapped_count": 0,
            "ingredients": [
                {
                    "name": "Magnesium Glycinate",
                    "standard_name": "Magnesium",
                    "score": 18,
                    "dosage_importance": 1.0,
                    "mapped": True,
                    "quantity": 200,
                    "unit": "mg",
                    "has_dose": True,
                },
                {
                    "name": "Vitamin D3",
                    "standard_name": "Vitamin D",
                    "score": 15,
                    "dosage_importance": 1.5,
                    "mapped": True,
                    "quantity": 1000,
                    "unit": "IU",
                    "has_dose": True,
                },
            ],
            "ingredients_scorable": [
                {
                    "name": "Magnesium Glycinate",
                    "standard_name": "Magnesium",
                    "score": 18,
                    "dosage_importance": 1.0,
                    "mapped": True,
                    "quantity": 200,
                    "unit": "mg",
                    "has_dose": True,
                },
                {
                    "name": "Vitamin D3",
                    "standard_name": "Vitamin D",
                    "score": 15,
                    "dosage_importance": 1.5,
                    "mapped": True,
                    "quantity": 1000,
                    "unit": "IU",
                    "has_dose": True,
                },
            ],
        },
        "delivery_data": {"highest_tier": None},
        "absorption_data": {"qualifies_for_bonus": False},
        "formulation_data": {
            "organic": {"claimed": False, "usda_verified": False},
            "standardized_botanicals": [],
            "synergy_clusters": [],
        },
        "contaminant_data": {
            "banned_substances": {"found": False, "substances": []},
            "harmful_additives": {"found": False, "additives": []},
            "allergens": {"found": False, "allergens": []},
        },
        "compliance_data": {
            "allergen_free_claims": [],
            "gluten_free": False,
            "vegan": False,
            "vegetarian": False,
            "conflicts": [],
            "has_may_contain_warning": False,
        },
        "certification_data": {
            "third_party_programs": {"programs": []},
            "gmp": {"claimed": False, "fda_registered": False, "nsf_gmp": False},
            "batch_traceability": {"has_coa": False, "has_batch_lookup": False, "has_qr_code": False},
        },
        "proprietary_data": {
            "has_proprietary_blends": False,
            "blends": [],
            "total_active_ingredients": 2,
        },
        "evidence_data": {"clinical_matches": []},
        "manufacturer_data": {
            "top_manufacturer": {"found": False},
            "violations": {"found": False, "violations": []},
            "bonus_features": {"physician_formulated": False, "sustainability_claim": False},
            "country_of_origin": {"high_regulation_country": False, "country": ""},
        },
        "match_ledger": {
            "domains": {
                "ingredients": {
                    "entries": []
                }
            }
        },
    }


class TestValidation:
    def test_validate_valid(self):
        product = make_base_product()
        ok, issues = SupplementScorer.validate_enriched_product(product)
        assert ok is True
        assert isinstance(issues, list)

    def test_validate_missing_name(self):
        product = {"dsld_id": "x"}
        ok, issues = SupplementScorer.validate_enriched_product(product)
        assert ok is False
        assert any("Missing product name" in x for x in issues)


class TestV30Scoring:
    @pytest.fixture
    def scorer(self):
        return SupplementScorer()

    def test_score_product_safe_basic(self, scorer):
        result = scorer.score_product(make_base_product())
        assert result["verdict"] == "SAFE"
        assert result["score_80"] is not None
        assert result["score_80"] > 0
        assert result["quality_score"] == result["score_80"]

    def test_b0_recall_blocks(self, scorer):
        product = make_base_product()
        product["contaminant_data"]["banned_substances"] = {
            "found": True,
            "substances": [
                {
                    "ingredient": "Example",
                    "match_type": "exact",
                    "status": "recalled",
                    "severity_level": "moderate",
                }
            ],
        }
        result = scorer.score_product(product)
        assert result["verdict"] == "BLOCKED"
        assert result["score_80"] is None

    def test_b0_critical_unsafe(self, scorer):
        product = make_base_product()
        product["contaminant_data"]["banned_substances"] = {
            "found": True,
            "substances": [
                {
                    "ingredient": "DMAA",
                    "match_type": "exact",
                    "status": "banned",
                    "severity_level": "critical",
                }
            ],
        }
        result = scorer.score_product(product)
        assert result["verdict"] == "UNSAFE"
        assert result["score_80"] == 0

    def test_b0_token_bounded_causes_caution_not_block(self, scorer):
        product = make_base_product()
        product["contaminant_data"]["banned_substances"] = {
            "found": True,
            "substances": [
                {
                    "ingredient": "Anatabine",
                    "match_method": "token_bounded",
                    "severity_level": "high",
                }
            ],
        }
        result = scorer.score_product(product)
        assert result["verdict"] == "CAUTION"
        assert "BANNED_MATCH_REVIEW_NEEDED" in result["flags"]
        assert result["score_80"] is not None

    def test_mapping_gate_not_scored_when_full_mapping_required(self, scorer):
        product = make_base_product()
        product["ingredient_quality_data"]["unmapped_count"] = 1
        product["ingredient_quality_data"]["ingredients"][1]["mapped"] = False
        product["ingredient_quality_data"]["ingredients"][1]["name"] = "Unknown Active"
        scorer.feature_gates["require_full_mapping"] = True

        result = scorer.score_product(product)
        assert result["verdict"] == "NOT_SCORED"
        assert result["score_80"] is None
        assert "UNMAPPED_ACTIVE_INGREDIENT" in result["flags"]

    def test_a1_uses_precomputed_score_field(self, scorer):
        product = make_base_product()
        product["supplement_type"]["type"] = "single"
        product["ingredient_quality_data"]["total_active"] = 1
        product["ingredient_quality_data"]["ingredients_scorable"] = [
            {
                "name": "Magnesium",
                "standard_name": "Magnesium",
                "score": 18,
                "dosage_importance": 0.5,
                "mapped": True,
                "quantity": 200,
                "unit": "mg",
                "has_dose": True,
            }
        ]
        product["ingredient_quality_data"]["ingredients"] = deepcopy(product["ingredient_quality_data"]["ingredients_scorable"])

        section_a = scorer._score_section_a(product, "single")
        assert section_a["A1"] == pytest.approx(13.0, rel=1e-6)

    def test_b_penalties_are_positive_magnitudes_subtracted(self, scorer):
        product = make_base_product()
        product["contaminant_data"]["harmful_additives"] = {
            "found": True,
            "additives": [{"severity_level": "high"}],
        }
        section_b = scorer._score_section_b(product, "targeted", 0.0, [])
        assert section_b["B1_penalty"] == pytest.approx(2.0)
        assert section_b["score"] == pytest.approx(33.0)

    def test_c_per_ingredient_cap_by_canonical_name(self, scorer):
        product = make_base_product()
        product["evidence_data"] = {
            "clinical_matches": [
                {
                    "id": "E1",
                    "standard_name": "Magnesium",
                    "study_type": "systematic_review_meta",
                    "evidence_level": "product-human",
                },
                {
                    "id": "E2",
                    "standard_name": "Magnesium",
                    "study_type": "rct_multiple",
                    "evidence_level": "product-human",
                },
            ]
        }
        section_c = scorer._score_section_c(product, [])
        assert section_c["score"] == pytest.approx(5.0)

    def test_low_quality_is_poor_not_unsafe(self, scorer):
        product = make_base_product()
        # Minimize A/C/D and force heavy penalties without B0 hazard.
        product["ingredient_quality_data"]["ingredients"] = [
            {
                "name": "Weak Ingredient",
                "score": 0,
                "dosage_importance": 1.0,
                "mapped": True,
                "quantity": 1,
                "unit": "mg",
                "has_dose": False,
            }
        ]
        product["ingredient_quality_data"]["ingredients_scorable"] = deepcopy(product["ingredient_quality_data"]["ingredients"])
        product["ingredient_quality_data"]["total_active"] = 1

        product["contaminant_data"]["harmful_additives"] = {
            "found": True,
            "additives": [{"severity_level": "high"}, {"severity_level": "high"}, {"severity_level": "high"}],
        }
        product["contaminant_data"]["allergens"] = {
            "found": True,
            "allergens": [{"severity_level": "high"}],
        }
        product["proprietary_data"] = {
            "has_proprietary_blends": True,
            "total_active_ingredients": 1,
            "blends": [{"name": "Blend", "disclosure_level": "none", "nested_count": 1}],
        }
        product["has_disease_claims"] = True
        product["manufacturer_data"]["violations"] = {
            "found": True,
            "total_deduction_applied": -25,
        }

        result = scorer.score_product(product)
        assert result["verdict"] == "POOR"
        assert result["safety_verdict"] == "SAFE"
        assert result["score_80"] is not None and result["score_80"] < 32

    def test_violation_penalty_prefers_total_deduction_applied(self, scorer):
        product = make_base_product()
        product["manufacturer_data"]["violations"] = {
            "found": True,
            "total_deduction_applied": -7.5,
            "violations": [
                {"total_deduction_applied": -25.0},
            ],
        }

        assert scorer._manufacturer_violation_penalty(product) == pytest.approx(-7.5)

    def test_violation_penalty_sums_item_level_total_deduction_applied(self, scorer):
        product = make_base_product()
        product["manufacturer_data"]["violations"] = {
            "found": True,
            "violations": [
                {"total_deduction_applied": -8.0},
                {"total_deduction_applied": -3.5},
            ],
        }

        assert scorer._manufacturer_violation_penalty(product) == pytest.approx(-11.5)


class TestImpactReport:
    def test_impact_report_fails_on_new_unsafe(self):
        current = [{"dsld_id": "p1", "score_80": 50, "verdict": "UNSAFE"}]
        baseline = [{"dsld_id": "p1", "score_80": 50, "verdict": "SAFE"}]

        report = generate_impact_report(
            current,
            baseline_results=baseline,
            threshold_score_change=99,
            threshold_pct_change=99,
        )

        assert report["pass_gate"] is False
        assert report["summary_statistics"]["changes"]["new_unsafe_verdicts"] == 1
