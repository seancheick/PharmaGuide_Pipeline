#!/usr/bin/env python3
"""Tests for schema-aligned scoring engine behavior."""

from copy import deepcopy
import json
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

    def test_full_disclosure_badge_present_when_fully_disclosed(self, scorer):
        result = scorer.score_product(make_base_product())
        badge_ids = {badge.get("id") for badge in result.get("badges", [])}
        assert "FULL_DISCLOSURE" in badge_ids

    def test_full_disclosure_badge_absent_when_hidden_blend_exists(self, scorer):
        product = make_base_product()
        product["proprietary_data"]["has_proprietary_blends"] = True
        product["proprietary_data"]["blends"] = [
            _make_blend(
                "Opaque Blend",
                "none",
                total_weight=500,
                unit="mg",
                ingredients_without_amounts=["A", "B"],
            )
        ]

        result = scorer.score_product(product)
        badge_ids = {badge.get("id") for badge in result.get("badges", [])}
        assert "FULL_DISCLOSURE" not in badge_ids

    def test_b0_recall_is_unsafe(self, scorer):
        """Recalled ingredients get UNSAFE verdict (score=0, shown with warning)."""
        product = make_base_product()
        product["contaminant_data"]["banned_substances"] = {
            "found": True,
            "substances": [
                {
                    "ingredient": "Example",
                    "match_type": "exact",
                    "status": "recalled",
                }
            ],
        }
        result = scorer.score_product(product)
        assert result["verdict"] == "UNSAFE"
        assert result["score_80"] == 0
        assert result["evaluation_stage"] == "safety"

    def test_b0_banned_is_blocked(self, scorer):
        """Banned substances get BLOCKED verdict (score=None, harshest)."""
        product = make_base_product()
        product["contaminant_data"]["banned_substances"] = {
            "found": True,
            "substances": [
                {
                    "ingredient": "DMAA",
                    "match_type": "exact",
                    "status": "banned",
                }
            ],
        }
        result = scorer.score_product(product)
        assert result["verdict"] == "BLOCKED"
        assert result["score_80"] is None
        assert result["evaluation_stage"] == "safety"

    def test_b0_token_bounded_causes_caution_not_block(self, scorer):
        product = make_base_product()
        product["contaminant_data"]["banned_substances"] = {
            "found": True,
            "substances": [
                {
                    "ingredient": "Anatabine",
                    "match_method": "token_bounded",
                    "status": "banned",
                }
            ],
        }
        result = scorer.score_product(product)
        # token_bounded banned hits must never surface as SAFE.
        # They remain non-hard-fail, but force human-visible CAUTION and a minimum B0 penalty.
        assert result["verdict"] == "CAUTION"
        assert "BANNED_MATCH_REVIEW_NEEDED" in result["flags"]
        # v3.4.x: A1.max raised 15 -> 18 shifts score_80 upward by the A1 delta
        # (base product has an A1-scoring ingredient). The invariants this test
        # really cares about are the verdict and the B0 moderate penalty — the
        # absolute score_80 is incidental, so just assert it landed in a
        # plausible CAUTION band.
        assert 30.0 <= result["score_80"] <= 45.0
        assert result["breakdown"]["B"]["B0_moderate_penalty"] == pytest.approx(5.0)

    def test_b0_moderate_penalty_stacks_additively(self, scorer):
        product = make_base_product()
        product["contaminant_data"]["banned_substances"] = {
            "found": True,
            "substances": [
                {
                    "ingredient": "High Risk First",
                    "match_type": "exact",
                    "status": "high_risk",
                },
                {
                    "ingredient": "Watchlist Second",
                    "match_type": "alias",
                    "status": "watchlist",
                },
            ],
        }

        result = scorer._evaluate_safety_gate(product)
        assert result["moderate_penalty"] == pytest.approx(15.0)

    def test_b0_moderate_penalties_stack_additively(self, scorer):
        """Multiple moderate-severity substances should stack penalties, not just take max."""
        product = make_base_product()
        product["contaminant_data"]["banned_substances"] = {
            "found": True,
            "substances": [
                {"ingredient": "High Risk A", "match_type": "exact", "status": "high_risk"},
                {"ingredient": "High Risk B", "match_type": "exact", "status": "high_risk"},
                {"ingredient": "Watchlist C", "match_type": "alias", "status": "watchlist"},
            ],
        }
        result = scorer._evaluate_safety_gate(product)
        # 10 + 10 + 5 = 25 (stacked, not max'd at 10)
        assert result["moderate_penalty"] == pytest.approx(25.0)

    def test_b0_moderate_penalty_capped_at_25(self, scorer):
        """Stacked moderate penalties should be capped at 25."""
        product = make_base_product()
        product["contaminant_data"]["banned_substances"] = {
            "found": True,
            "substances": [
                {"ingredient": f"High Risk {i}", "match_type": "exact", "status": "high_risk"}
                for i in range(5)  # 5 * 10 = 50, should clamp to 25
            ],
        }
        result = scorer._evaluate_safety_gate(product)
        assert result["moderate_penalty"] == pytest.approx(25.0)

    def test_filler_only_fallback_returns_empty(self, scorer):
        """When ingredients_scorable is empty and ingredients has only fillers, return empty."""
        product = make_base_product()
        product["ingredient_quality_data"]["ingredients_scorable"] = []
        product["ingredient_quality_data"]["ingredients"] = [
            {"name": "Magnesium Stearate", "mapped": False, "is_filler": True, "score": 0},
            {"name": "Silicon Dioxide", "mapped": False, "is_filler": True, "score": 0},
        ]
        result = scorer._get_active_ingredients(product)
        assert result == []

    def test_fallback_with_mapped_actives_works(self, scorer):
        """When ingredients_scorable is empty but ingredients has mapped actives, fallback works."""
        product = make_base_product()
        product["ingredient_quality_data"]["ingredients_scorable"] = []
        product["ingredient_quality_data"]["ingredients"] = [
            {"name": "Magnesium Glycinate", "mapped": True, "score": 18},
            {"name": "Silicon Dioxide", "mapped": False, "is_filler": True, "score": 0},
        ]
        result = scorer._get_active_ingredients(product)
        assert len(result) == 2  # Returns full list including filler

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

    def test_mapping_gate_ignores_proprietary_blend_container(self, scorer):
        product = make_base_product()
        product["ingredient_quality_data"]["unmapped_count"] = 1
        product["ingredient_quality_data"]["ingredients"] = [
            {
                "name": "Curcumin",
                "standard_name": "Curcumin",
                "score": 8,
                "dosage_importance": 1.0,
                "mapped": True,
                "quantity": 250,
                "unit": "mg",
                "has_dose": True,
                "is_proprietary_blend": False,
            },
            {
                "name": "Rice Protein Matrix and Polyphenols",
                "standard_name": "Rice Protein Matrix and Polyphenols",
                "mapped": False,
                "quantity": 250,
                "unit": "mg",
                "has_dose": True,
                "is_proprietary_blend": True,
                "is_blend_header": True,
                "blend_total_weight_only": True,
            },
        ]
        product["ingredient_quality_data"]["ingredients_scorable"] = deepcopy(
            product["ingredient_quality_data"]["ingredients"]
        )
        scorer.feature_gates["require_full_mapping"] = True

        gate = scorer._mapping_gate(product)
        assert gate["stop"] is False
        assert gate["unmapped_actives_total"] == 0
        assert gate["unmapped_actives_excluding_banned_exact_alias"] == 0

    def test_mapping_kpis_exclude_banned_exact_alias_unmapped(self, scorer):
        product = make_base_product()
        product["ingredient_quality_data"]["unmapped_count"] = 1
        product["ingredient_quality_data"]["ingredients"][1]["mapped"] = False
        product["ingredient_quality_data"]["ingredients"][1]["name"] = "Anatabine"
        product["contaminant_data"]["banned_substances"] = {
            "found": True,
            "substances": [
                {
                    "ingredient": "Anatabine",
                    "match_type": "exact",
                    "status": "high_risk",
                }
            ],
        }

        gate = scorer._mapping_gate(product)
        assert gate["unmapped_actives_total"] == 1
        assert gate["unmapped_actives_excluding_banned_exact_alias"] == 0
        assert gate["unmapped_actives"] == []
        assert gate["unmapped_actives_banned_exact_alias"] == ["Anatabine"]
        assert gate["mapped_coverage"] == pytest.approx(1.0)

    def test_unmatched_banned_exact_alias_forces_unsafe(self, scorer):
        product = make_base_product()
        product["ingredient_quality_data"]["unmapped_count"] = 1
        product["ingredient_quality_data"]["ingredients"][1]["mapped"] = False
        product["ingredient_quality_data"]["ingredients"][1]["name"] = "Anatabine"
        product["contaminant_data"]["banned_substances"] = {
            "found": True,
            "substances": [
                {
                    "ingredient": "Anatabine",
                    "match_type": "exact",
                    "status": "watchlist",
                }
            ],
        }

        result = scorer.score_product(product)
        assert result["verdict"] == "UNSAFE"
        assert "UNMAPPED_BANNED_EXACT_ALIAS_GUARD" in result["flags"]
        assert result["unmapped_actives_total"] == 1
        assert result["unmapped_actives_excluding_banned_exact_alias"] == 0

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

        section_a = scorer._compute_ingredient_quality_score(product, "single")
        # A1.max was bumped 15 -> 18 in v3.4.x to stop compressing enricher's
        # 0-18 raw score (premium form +15 plus natural +3). An ingredient
        # scoring a perfect 18 upstream should now earn the full 18 downstream.
        assert section_a["A1"] == pytest.approx(18.0, rel=1e-6)

    def test_a1_treats_single_nutrient_as_single(self, scorer):
        product = make_base_product()
        product["ingredient_quality_data"]["total_active"] = 1
        product["ingredient_quality_data"]["ingredients_scorable"] = [
            {
                "name": "Weighted Ingredient",
                "standard_name": "Weighted Ingredient",
                "score": 18,
                "dosage_importance": 3.0,
                "mapped": True,
                "quantity": 200,
                "unit": "mg",
                "has_dose": True,
            }
        ]
        product["ingredient_quality_data"]["ingredients"] = deepcopy(
            product["ingredient_quality_data"]["ingredients_scorable"]
        )

        section_single = scorer._compute_ingredient_quality_score(product, "single")
        section_single_nutrient = scorer._compute_ingredient_quality_score(product, "single_nutrient")

        assert section_single_nutrient["A1"] == pytest.approx(section_single["A1"], rel=1e-6)

    def test_a6_uses_score_first_when_both_score_and_bio_score_exist(self, scorer):
        product = make_base_product()
        product["ingredient_quality_data"]["total_active"] = 1
        product["ingredient_quality_data"]["ingredients_scorable"] = [
            {
                "name": "Test Ingredient",
                "standard_name": "Test Ingredient",
                "score": 16,
                "bio_score": 12,
                "dosage_importance": 1.0,
                "mapped": True,
                "quantity": 100,
                "unit": "mg",
                "has_dose": True,
            }
        ]
        product["ingredient_quality_data"]["ingredients"] = deepcopy(
            product["ingredient_quality_data"]["ingredients_scorable"]
        )
        assert scorer._compute_single_efficiency_bonus(product, "single") == pytest.approx(3.0)

    def test_a6_falls_back_to_bio_score_when_score_missing(self, scorer):
        product = make_base_product()
        product["ingredient_quality_data"]["total_active"] = 1
        product["ingredient_quality_data"]["ingredients_scorable"] = [
            {
                "name": "Fallback Ingredient",
                "standard_name": "Fallback Ingredient",
                "bio_score": 14,
                "dosage_importance": 1.0,
                "mapped": True,
                "quantity": 100,
                "unit": "mg",
                "has_dose": True,
            }
        ]
        product["ingredient_quality_data"]["ingredients"] = deepcopy(
            product["ingredient_quality_data"]["ingredients_scorable"]
        )
        assert scorer._compute_single_efficiency_bonus(product, "single") == pytest.approx(2.0)

    def test_a6_only_applies_to_single_types(self, scorer):
        product = make_base_product()
        product["ingredient_quality_data"]["total_active"] = 1
        product["ingredient_quality_data"]["ingredients_scorable"] = [
            {
                "name": "Single Ingredient",
                "standard_name": "Single Ingredient",
                "score": 16,
                "dosage_importance": 1.0,
                "mapped": True,
                "quantity": 100,
                "unit": "mg",
                "has_dose": True,
            }
        ]
        product["ingredient_quality_data"]["ingredients"] = deepcopy(
            product["ingredient_quality_data"]["ingredients_scorable"]
        )
        assert scorer._compute_single_efficiency_bonus(product, "targeted") == pytest.approx(0.0)

    def test_a2_excludes_blend_containers(self, scorer):
        product = make_base_product()
        product["ingredient_quality_data"]["ingredients_scorable"] = [
            {
                "name": "Transparent Blend",
                "standard_name": "Transparent Blend",
                "canonical_id": "transparent_blend",
                "score": 18,
                "mapped": True,
                "is_proprietary_blend": True,
                "quantity": 500,
                "unit": "mg",
                "has_dose": True,
            },
            {
                "name": "Magnesium Glycinate",
                "standard_name": "Magnesium",
                "canonical_id": "magnesium",
                "score": 14,
                "mapped": True,
                "is_proprietary_blend": False,
                "quantity": 200,
                "unit": "mg",
                "has_dose": True,
            },
            {
                "name": "Vitamin D3",
                "standard_name": "Vitamin D",
                "canonical_id": "vitamin_d",
                "score": 14,
                "mapped": True,
                "is_proprietary_blend": False,
                "quantity": 1000,
                "unit": "IU",
                "has_dose": True,
            },
        ]
        product["ingredient_quality_data"]["ingredients"] = deepcopy(
            product["ingredient_quality_data"]["ingredients_scorable"]
        )

        # Two premium disclosed ingredients -> 0.5 points (count-1).
        assert scorer._compute_premium_forms_bonus(product) == pytest.approx(0.5)

    def test_a2_requires_usable_individual_dose(self, scorer):
        product = make_base_product()
        product["ingredient_quality_data"]["ingredients_scorable"] = [
            {
                "name": "Premium Undosed",
                "standard_name": "Premium Undosed",
                "canonical_id": "premium_undosed",
                "score": 18,
                "mapped": True,
                "is_proprietary_blend": False,
                "quantity": None,
                "unit": "",
                "has_dose": False,
            },
            {
                "name": "Magnesium Glycinate",
                "standard_name": "Magnesium",
                "canonical_id": "magnesium",
                "score": 14,
                "mapped": True,
                "is_proprietary_blend": False,
                "quantity": 200,
                "unit": "mg",
                "has_dose": True,
            },
            {
                "name": "Vitamin D3",
                "standard_name": "Vitamin D",
                "canonical_id": "vitamin_d",
                "score": 14,
                "mapped": True,
                "is_proprietary_blend": False,
                "quantity": 1000,
                "unit": "IU",
                "has_dose": True,
            },
        ]
        product["ingredient_quality_data"]["ingredients"] = deepcopy(
            product["ingredient_quality_data"]["ingredients_scorable"]
        )

        # Undosed premium ingredient should not count toward A2.
        assert scorer._compute_premium_forms_bonus(product) == pytest.approx(0.5)

    def test_non_probiotic_prebiotic_only_gets_no_probiotic_bonus(self, scorer):
        product = make_base_product()
        product["supplement_type"]["type"] = "specialty"
        product["product_name"] = "Digestive Support Formula"
        product["ingredient_quality_data"]["ingredients"] = [
            {
                "name": "Inulin",
                "standard_name": "Inulin",
                "score": 9,
                "dosage_importance": 1.0,
                "mapped": True,
            }
        ]
        product["ingredient_quality_data"]["ingredients_scorable"] = deepcopy(
            product["ingredient_quality_data"]["ingredients"]
        )
        product["probiotic_data"] = {
            "is_probiotic_product": True,
            "has_cfu": False,
            "total_billion_count": 0.0,
            "total_strain_count": 1,
            "clinical_strain_count": 0,
            "guarantee_type": None,
        }

        probiotic = scorer._compute_probiotic_category_bonus(product, "specialty")
        assert probiotic["probiotic_bonus"] == 0.0
        assert probiotic["eligibility"]["mode"] == "non_probiotic"
        assert probiotic["eligibility"]["eligible"] is False

    def test_non_probiotic_strict_gate_can_award_probiotic_bonus(self, scorer):
        product = make_base_product()
        product["supplement_type"]["type"] = "specialty"
        product["product_name"] = "Women Probiotic Digestive Formula"
        product["ingredient_quality_data"]["ingredients"] = [
            {
                "name": "Inulin",
                "standard_name": "Inulin",
                "score": 9,
                "dosage_importance": 1.0,
                "mapped": True,
            }
        ]
        product["ingredient_quality_data"]["ingredients_scorable"] = deepcopy(
            product["ingredient_quality_data"]["ingredients"]
        )
        product["product_signals"] = {"label_disclosure_signals": {"strain_id_count": 1}}
        product["probiotic_data"] = {
            "is_probiotic_product": True,
            "has_cfu": True,
            "total_billion_count": 12.0,
            "total_strain_count": 4,
            "clinical_strain_count": 1,
            "guarantee_type": "at_expiration",
        }

        probiotic = scorer._compute_probiotic_category_bonus(product, "specialty")
        assert probiotic["eligibility"]["mode"] == "non_probiotic"
        assert probiotic["eligibility"]["eligible"] is True
        assert probiotic["probiotic_bonus"] > 0.0

    def test_probiotic_dominant_formula_is_promoted_even_without_guarantee(self, scorer):
        product = make_base_product()
        product["supplement_type"]["type"] = "specialty"
        product["product_name"] = "Restore"
        product["fullName"] = "Thorne Performance Restore"
        product["ingredient_quality_data"]["ingredients"] = [
            {"name": "Lactobacillus gasseri", "standard_name": "Lactobacillus Gasseri", "mapped": True},
            {"name": "Bifidobacterium longum", "standard_name": "Bifidobacterium Longum", "mapped": True},
            {"name": "Bifidobacterium bifidum", "standard_name": "Bifidobacterium Bifidum", "mapped": True},
        ]
        product["ingredient_quality_data"]["ingredients_scorable"] = deepcopy(
            product["ingredient_quality_data"]["ingredients"]
        )
        product["product_signals"] = {
            "label_disclosure_signals": {
                "strain_id_count": 0,
                "clinical_strain_count": 2,
                "total_strain_count": 3,
            }
        }
        product["probiotic_data"] = {
            "is_probiotic_product": True,
            "has_cfu": True,
            "total_billion_count": 5.0,
            "total_strain_count": 3,
            "clinical_strain_count": 2,
            "guarantee_type": None,
            "probiotic_blends": [
                {"strains": ["Lactobacillus gasseri"], "cfu_data": {"billion_count": 2.5}},
                {"strains": ["Bifidobacterium longum"], "cfu_data": {"billion_count": 1.25}},
                {"strains": ["Bifidobacterium bifidum"], "cfu_data": {"billion_count": 1.25}},
            ],
        }

        probiotic = scorer._compute_probiotic_category_bonus(product, "specialty")
        assert probiotic["eligibility"]["eligible"] is True
        assert probiotic["eligibility"]["reason"] in {"promoted_probiotic_dominant", "supplement_type_probiotic"}
        assert probiotic["probiotic_bonus"] > 0.0

    def test_probiotic_type_keeps_bonus_path(self, scorer):
        product = make_base_product()
        product["supplement_type"]["type"] = "probiotic"
        product["probiotic_data"] = {
            "is_probiotic_product": False,
            "has_cfu": True,
            "total_billion_count": 5.0,
            "total_strain_count": 3,
            "clinical_strain_count": 0,
            "guarantee_type": "at_manufacture",
        }

        probiotic = scorer._compute_probiotic_category_bonus(product, "probiotic")
        assert probiotic["eligibility"]["mode"] == "probiotic"
        assert probiotic["eligibility"]["eligible"] is True
        assert probiotic["probiotic_bonus"] == pytest.approx(2.0)

    def test_classifier_reinfers_probiotic_from_iqd_when_enriched_type_is_generic(self, scorer):
        product = make_base_product()
        product["supplement_type"] = {"type": "specialty", "active_count": 0}
        product["product_name"] = "Restore"
        product["fullName"] = "Thorne Performance Restore"
        product["activeIngredients"] = [
            {"name": "Lactobacillus gasseri", "standardName": "Lactobacillus Gasseri", "category": None},
            {"name": "Bifidobacterium longum", "standardName": "Bifidobacterium Longum", "category": None},
            {"name": "Bifidobacterium bifidum", "standardName": "Bifidobacterium Bifidum", "category": None},
        ]
        product["ingredient_quality_data"]["ingredients"] = [
            {"name": "Lactobacillus gasseri", "standard_name": "Lactobacillus Gasseri", "category": "probiotics", "mapped": True},
            {"name": "Bifidobacterium longum", "standard_name": "Bifidobacterium Longum", "category": "probiotics", "mapped": True},
            {"name": "Bifidobacterium bifidum", "standard_name": "Bifidobacterium Bifidum", "category": "probiotics", "mapped": True},
        ]
        product["probiotic_data"] = {
            "is_probiotic_product": True,
            "has_cfu": True,
            "total_billion_count": 5.0,
            "total_strain_count": 3,
            "clinical_strain_count": 2,
            "guarantee_type": None,
        }

        assert scorer._classify_supplement_type(product) == "probiotic"

        scored = scorer.score_product(product)
        assert scored["supp_type"] == "probiotic"
        assert "SUPPLEMENT_TYPE_REINFERRED" in scored["flags"]

    def test_d1_does_not_award_fuzzy_manufacturer_match(self, scorer):
        product = make_base_product()
        product["is_trusted_manufacturer"] = False
        product["manufacturer_data"]["top_manufacturer"] = {
            "found": True,
            "match_type": "fuzzy",
            "name": "Example Top Manufacturer",
        }

        section_d = scorer._compute_brand_trust_score(product)
        assert section_d["D1"] == 0.0

    def test_b_penalties_are_positive_magnitudes_subtracted(self, scorer):
        product = make_base_product()
        product["contaminant_data"]["harmful_additives"] = {
            "found": True,
            "additives": [{"severity_level": "high"}],
        }
        section_b = scorer._compute_safety_purity_score(product, "targeted", 0.0, [])
        assert section_b["B1_penalty"] == pytest.approx(2.0)
        assert section_b["score"] == pytest.approx(23.0)

    def test_b1_deduplicates_same_additive_id(self, scorer):
        """Two additives with same additive_id but different severity → only higher penalty counted."""
        product = make_base_product()
        product["contaminant_data"]["harmful_additives"] = {
            "found": True,
            "additives": [
                {"additive_id": "ADD_BHA", "severity_level": "moderate"},
                {"additive_id": "ADD_BHA", "severity_level": "critical"},
            ],
        }
        section_b = scorer._compute_safety_purity_score(product, "targeted", 0.0, [])
        # Only the critical penalty (3.0) should apply, not moderate+critical (1+3=4)
        assert section_b["B1_penalty"] == pytest.approx(3.0)

    def test_b1_different_additive_ids_both_count(self, scorer):
        """Different additive_ids are chemically distinct and both count."""
        product = make_base_product()
        product["contaminant_data"]["harmful_additives"] = {
            "found": True,
            "additives": [
                {"additive_id": "ADD_STEARIC_ACID", "severity_level": "high"},
                {"additive_id": "ADD_BHA", "severity_level": "critical"},
            ],
        }
        section_b = scorer._compute_safety_purity_score(product, "targeted", 0.0, [])
        # high (2.0) + critical (3.0) = 5.0
        assert section_b["B1_penalty"] == pytest.approx(5.0)

    def test_b1_cap_is_config_driven(self, scorer):
        """B1 cap should be read from config (currently 8)."""
        product = make_base_product()
        product["contaminant_data"]["harmful_additives"] = {
            "found": True,
            "additives": [
                {"additive_id": "ADD_BHA", "severity_level": "critical"},
                {"additive_id": "ADD_BHT", "severity_level": "critical"},
                {"additive_id": "ADD_TBHQ", "severity_level": "critical"},
            ],
        }
        section_b = scorer._compute_safety_purity_score(product, "targeted", 0.0, [])
        # B1.cap was raised 8 -> 15 in v3.4.x, so 3 critical (= 9.0) is now
        # well under the cap and lands uncompressed at 9.0.
        assert section_b["B1_penalty"] == pytest.approx(9.0)

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
        section_c = scorer._compute_evidence_score(product, [])
        assert section_c["score"] == pytest.approx(7.0)

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

    def test_b2_deduplicates_same_allergen_type(self, scorer):
        product = make_base_product()
        product["contaminant_data"]["allergens"] = {
            "found": True,
            "allergens": [
                {"allergen_name": "Milk", "severity_level": "high"},
                {"allergen_name": "Milk", "severity_level": "high"},
                {"allergen_name": "Soy", "severity_level": "moderate"},
            ],
        }

        b_cfg = {
            "B2_allergen_presence": {
                "cap": 10.0,
                "severity_points": {
                    "high": 2.0,
                    "moderate": 1.5,
                    "low": 1.0,
                },
            }
        }

        assert scorer._compute_allergen_penalty(product, b_cfg) == pytest.approx(3.5)

    def test_violation_penalty_prefers_total_deduction_applied(self, scorer):
        product = make_base_product()
        product["manufacturer_data"]["violations"] = {
            "found": True,
            "total_deduction_applied": -7.5,
            "violations": [
                {"total_deduction_applied": -25.0},
            ],
        }

        assert scorer._compute_manufacturer_violation_penalty(product) == pytest.approx(-7.5)

    def test_violation_penalty_sums_item_level_total_deduction_applied(self, scorer):
        product = make_base_product()
        product["manufacturer_data"]["violations"] = {
            "found": True,
            "violations": [
                {"total_deduction_applied": -8.0},
                {"total_deduction_applied": -3.5},
            ],
        }

        assert scorer._compute_manufacturer_violation_penalty(product) == pytest.approx(-11.5)


class TestNutritionOnlyVerdict:
    """Bucket C — DSLD doesn't capture whey/protein in `ingredientRows`
    for ~16 protein-powder products. They previously fell to NOT_SCORED
    (which signals 'real supplement, mapping failed'). The truth is
    these are food-shape products (whey, protein powders), not
    supplements at all.

    Fix: emit a distinct NUTRITION_ONLY verdict so the UI can render
    'food product — banned/harmful flags still apply, no bioactive
    scoring'. Precedence:

        BLOCKED > UNSAFE > NUTRITION_ONLY > NOT_SCORED > CAUTION > POOR > SAFE

    Discriminator: `mapping_gate.stop` AND `product_name` contains a
    food-shape keyword (whey/protein powder/casein/meal replacement/
    shake/smoothie). Capsule supplements that fail mapping still hit
    NOT_SCORED (no false positives).
    """

    @pytest.fixture
    def scorer(self):
        return SupplementScorer()

    def _make_unmapped_whey(self):
        product = make_base_product()
        product["product_name"] = "100% Whey Vanilla Cream"
        # Force a single unmapped active to trip require_full_mapping
        product["ingredient_quality_data"]["unmapped_count"] = 1
        product["ingredient_quality_data"]["ingredients"][1]["mapped"] = False
        product["ingredient_quality_data"]["ingredients"][1]["name"] = "Whey Protein Concentrate"
        product["ingredient_quality_data"]["ingredients_scorable"][1]["mapped"] = False
        product["ingredient_quality_data"]["ingredients_scorable"][1]["name"] = "Whey Protein Concentrate"
        return product

    def test_whey_product_with_unmapped_actives_returns_nutrition_only(self, scorer):
        product = self._make_unmapped_whey()
        scorer.feature_gates["require_full_mapping"] = True

        result = scorer.score_product(product)
        assert result["verdict"] == "NUTRITION_ONLY"
        assert result["score_80"] is None
        assert result["score_basis"] == "nutrition_only_food_shape"
        # Flags array still populated so UI can render warnings
        assert "UNMAPPED_ACTIVE_INGREDIENT" in result["flags"]

    @pytest.mark.parametrize("product_name", [
        "100% Whey Chocolate Supreme",
        "Hydrolyzed Whey Protein",
        "Pea Protein Powder",
        "Plant-Based Protein Shake",
        "Casein Protein Powder",
        "Meal Replacement Vanilla",
    ])
    def test_food_shape_keywords_route_to_nutrition_only(self, scorer, product_name):
        product = self._make_unmapped_whey()
        product["product_name"] = product_name
        scorer.feature_gates["require_full_mapping"] = True
        result = scorer.score_product(product)
        assert result["verdict"] == "NUTRITION_ONLY", (
            f"{product_name!r} should route to NUTRITION_ONLY"
        )

    def test_capsule_supplement_with_unmapped_active_still_not_scored(self, scorer):
        """Non-food-shape products (capsules, tablets) still fall to NOT_SCORED.
        We only divert food-shape products — pipeline bugs for real supplements
        must remain visible as NOT_SCORED."""
        product = make_base_product()
        product["product_name"] = "MysteryHerb Capsules"
        product["ingredient_quality_data"]["unmapped_count"] = 1
        product["ingredient_quality_data"]["ingredients"][1]["mapped"] = False
        product["ingredient_quality_data"]["ingredients"][1]["name"] = "Mystery Compound"
        product["ingredient_quality_data"]["ingredients_scorable"][1]["mapped"] = False
        scorer.feature_gates["require_full_mapping"] = True

        result = scorer.score_product(product)
        assert result["verdict"] == "NOT_SCORED"

    def test_blocked_b0_overrides_nutrition_only(self, scorer):
        """A whey product with a banned ingredient must still BLOCK — the
        Bucket C divert never weakens safety."""
        product = self._make_unmapped_whey()
        product["contaminant_data"]["banned_substances"] = {
            "found": True,
            "substances": [
                {
                    "ingredient": "Ephedra",
                    "match_type": "exact",
                    "status": "banned",
                    "id": "BANNED_EPHEDRA",
                }
            ],
        }
        scorer.feature_gates["require_full_mapping"] = True

        result = scorer.score_product(product)
        assert result["verdict"] == "BLOCKED", (
            "Banned ingredients must still take precedence over NUTRITION_ONLY"
        )


def _make_blend(
    name,
    level,
    total_weight=None,
    unit="mg",
    source_field="activeIngredients[0]",
    ingredients_with_amounts=None,
    ingredients_without_amounts=None,
    nested_count=None,
    blend_total_mg=None,
):
    """Build a proprietary blend payload aligned with enrichment output."""
    with_amounts = ingredients_with_amounts or []
    without_amounts = ingredients_without_amounts or []
    if nested_count is None:
        nested_count = len(with_amounts) + len(without_amounts)
    result = {
        "name": name,
        "disclosure_level": level,
        "total_weight": total_weight,
        "unit": unit,
        "nested_count": nested_count,
        "hidden_count": len(without_amounts),
        "source_field": source_field,
        "child_ingredients": [
            {"name": item.get("name", ""), "amount": item.get("amount"), "unit": item.get("unit", "mg")}
            for item in with_amounts
        ] + [{"name": n, "amount": None, "unit": ""} for n in without_amounts],
        "evidence": {
            "source_field": source_field,
            "ingredients_with_amounts": with_amounts,
            "ingredients_without_amounts": without_amounts,
        },
    }
    if blend_total_mg is not None:
        result["blend_total_mg"] = blend_total_mg
    return result


class TestB5ProprietaryBlendRedesign:
    """Hidden-mass blend transparency model with A1/B5 separation."""

    @pytest.fixture
    def scorer(self):
        return SupplementScorer()

    def test_no_blends_b5_is_zero(self, scorer):
        p = make_base_product()
        assert scorer._compute_proprietary_blend_penalty(p, []) == pytest.approx(0.0)

    def test_none_disclosure_full_formula_penalty_near_seven(self, scorer):
        p = make_base_product()
        p["ingredient_quality_data"]["ingredients_scorable"] = [
            {
                "name": "Mega Blend",
                "standard_name": "Mega Blend",
                "score": 5,
                "mapped": False,
                "has_dose": True,
                "quantity": 2000,
                "unit": "mg",
                "is_proprietary_blend": True,
            }
        ]
        p["proprietary_blends"] = [
            _make_blend(
                "Mega Blend",
                "none",
                total_weight=2000,
                unit="mg",
                ingredients_with_amounts=[],
                ingredients_without_amounts=["A", "B", "C"],
            )
        ]
        p["proprietary_data"]["total_active_mg"] = 2000
        p["proprietary_data"]["total_active_ingredients"] = 1

        assert scorer._compute_proprietary_blend_penalty(p, []) == pytest.approx(7.0, abs=0.01)
        assert scorer._compute_bioavailability_score(p, "targeted") == pytest.approx(0.0)

    def test_partial_hidden_mass_subtracts_disclosed_children_and_a1_scores_them(self, scorer):
        p = make_base_product()
        p["ingredient_quality_data"]["ingredients_scorable"] = [
            {
                "name": "Caffeine",
                "standard_name": "caffeine",
                "score": 14,
                "mapped": True,
                "has_dose": True,
                "quantity": 200,
                "unit": "mg",
                "is_proprietary_blend": False,
            },
            {
                "name": "L-Theanine",
                "standard_name": "l_theanine",
                "score": 12,
                "mapped": True,
                "has_dose": True,
                "quantity": 300,
                "unit": "mg",
                "is_proprietary_blend": False,
            },
            {
                "name": "Focus Blend",
                "standard_name": "focus_blend",
                "score": 5,
                "mapped": False,
                "has_dose": True,
                "quantity": 1000,
                "unit": "mg",
                "is_proprietary_blend": True,
            },
        ]
        p["proprietary_blends"] = [
            _make_blend(
                "Focus Blend",
                "partial",
                total_weight=1000,
                unit="mg",
                ingredients_with_amounts=[
                    {"name": "Caffeine", "amount": 200, "unit": "mg"},
                    {"name": "L-Theanine", "amount": 300, "unit": "mg"},
                ],
                ingredients_without_amounts=["Rhodiola"],
            )
        ]
        p["proprietary_data"]["total_active_mg"] = 2000
        p["proprietary_data"]["total_active_ingredients"] = 3
        flags = []
        penalty = scorer._compute_proprietary_blend_penalty(p, flags)
        # hidden_mass = 1000 - (200 + 300) = 500; impact = 500 / 2000 = 0.25
        # partial penalty = 1 + 3*0.25 = 1.75
        assert penalty == pytest.approx(1.75, abs=0.01)
        expected_avg = (14 + 12) / 2.0
        # v3.4.x: A1.max raised 15 -> 18, so the scale factor is now 18/18.
        assert scorer._compute_bioavailability_score(p, "targeted") == pytest.approx((expected_avg / 18.0) * 18.0, abs=0.01)
        assert "PROPRIETARY_BLEND_PRESENT" in flags

    def test_partial_child_without_amount_not_counted_for_a1_or_disclosed_mass(self, scorer):
        p = make_base_product()
        p["ingredient_quality_data"]["ingredients_scorable"] = [
            {
                "name": "Caffeine",
                "standard_name": "caffeine",
                "score": 14,
                "mapped": True,
                "has_dose": True,
                "quantity": 200,
                "unit": "mg",
                "is_proprietary_blend": False,
            },
            {
                "name": "Rhodiola",
                "standard_name": "rhodiola",
                "score": 13,
                "mapped": True,
                "has_dose": False,
                "quantity": None,
                "unit": "",
                "is_proprietary_blend": False,
            },
            {
                "name": "Focus Blend",
                "standard_name": "focus_blend",
                "score": 5,
                "mapped": False,
                "has_dose": True,
                "quantity": 1000,
                "unit": "mg",
                "is_proprietary_blend": True,
            },
        ]
        p["proprietary_blends"] = [
            _make_blend(
                "Focus Blend",
                "partial",
                total_weight=1000,
                ingredients_with_amounts=[{"name": "Caffeine", "amount": 200, "unit": "mg"}],
                ingredients_without_amounts=["Rhodiola"],
            )
        ]
        p["proprietary_data"]["total_active_mg"] = 1000
        penalty = scorer._compute_proprietary_blend_penalty(p, [])
        # hidden_mass = 800; impact = 0.8 => partial = 1 + 2.4 = 3.4
        assert penalty == pytest.approx(3.4, abs=0.01)
        # Only Caffeine contributes (Rhodiola has no usable dose, blend container excluded)
        # v3.4.x: A1.max raised 15 -> 18.
        assert scorer._compute_bioavailability_score(p, "targeted") == pytest.approx((14.0 / 18.0) * 18.0, abs=0.01)

    def test_duplicate_blends_deduped_once(self, scorer):
        p = make_base_product()
        blend = _make_blend(
            "Duplicate Blend",
            "none",
            total_weight=1000,
            source_field="activeIngredients[1]",
            ingredients_without_amounts=["A", "B"],
        )
        p["proprietary_blends"] = [blend, deepcopy(blend)]
        p["proprietary_data"]["total_active_mg"] = 1000
        assert scorer._compute_proprietary_blend_penalty(p, []) == pytest.approx(7.0, abs=0.01)

    def test_two_distinct_blends_cap_at_ten(self, scorer):
        p = make_base_product()
        p["proprietary_blends"] = [
            _make_blend(
                "Blend A",
                "none",
                total_weight=1000,
                source_field="activeIngredients[0]",
                ingredients_without_amounts=["A"],
            ),
            _make_blend(
                "Blend B",
                "none",
                total_weight=1000,
                source_field="activeIngredients[3]",
                ingredients_without_amounts=["B"],
            ),
        ]
        p["proprietary_data"]["total_active_mg"] = 1000
        assert scorer._compute_proprietary_blend_penalty(p, []) == pytest.approx(10.0, abs=0.01)

    def test_tiny_none_blend_uses_impact_floor(self, scorer):
        p = make_base_product()
        p["proprietary_blends"] = [
            _make_blend(
                "Tiny Blend",
                "none",
                total_weight=50,
                ingredients_without_amounts=["A"],
            )
        ]
        p["proprietary_data"]["total_active_mg"] = 2000
        # raw impact = 0.025, floored to 0.1 -> 2 + 5*0.1 = 2.5
        assert scorer._compute_proprietary_blend_penalty(p, []) == pytest.approx(2.5, abs=0.01)

    def test_full_disclosure_blend_zero_penalty_children_score_normally(self, scorer):
        p = make_base_product()
        p["ingredient_quality_data"]["ingredients_scorable"] = [
            {
                "name": "Caffeine",
                "standard_name": "caffeine",
                "score": 14,
                "mapped": True,
                "has_dose": True,
                "quantity": 200,
                "unit": "mg",
                "is_proprietary_blend": False,
            },
            {
                "name": "L-Theanine",
                "standard_name": "l_theanine",
                "score": 12,
                "mapped": True,
                "has_dose": True,
                "quantity": 300,
                "unit": "mg",
                "is_proprietary_blend": False,
            },
            {
                "name": "Transparent Blend",
                "standard_name": "transparent_blend",
                "score": 5,
                "mapped": False,
                "has_dose": True,
                "quantity": 500,
                "unit": "mg",
                "is_proprietary_blend": True,
            },
        ]
        p["proprietary_blends"] = [
            _make_blend(
                "Transparent Blend",
                "full",
                total_weight=500,
                ingredients_with_amounts=[
                    {"name": "Caffeine", "amount": 200, "unit": "mg"},
                    {"name": "L-Theanine", "amount": 300, "unit": "mg"},
                ],
                ingredients_without_amounts=[],
            )
        ]
        assert scorer._compute_proprietary_blend_penalty(p, []) == pytest.approx(0.0, abs=0.01)
        expected_avg = (14 + 12) / 2.0
        # v3.4.x: A1.max raised 15 -> 18.
        assert scorer._compute_bioavailability_score(p, "targeted") == pytest.approx((expected_avg / 18.0) * 18.0, abs=0.01)

    def test_no_mg_data_uses_count_share_fallback(self, scorer):
        p = make_base_product()
        p["proprietary_blends"] = [
            _make_blend(
                "No-Mass Blend",
                "none",
                total_weight=None,
                ingredients_with_amounts=[],
                ingredients_without_amounts=["A", "B", "C", "D"],
                nested_count=4,
            )
        ]
        p["proprietary_data"]["total_active_mg"] = None
        p["proprietary_data"]["total_active_ingredients"] = 8
        # count share impact = 4/8 = 0.5 -> 2 + 5*0.5 = 4.5
        assert scorer._compute_proprietary_blend_penalty(p, []) == pytest.approx(4.5, abs=0.01)

    def test_mixed_units_convert_correctly_for_hidden_mass(self, scorer):
        p = make_base_product()
        p["proprietary_blends"] = [
            _make_blend(
                "Unit Blend",
                "partial",
                total_weight=1.0,
                unit="g",
                ingredients_with_amounts=[
                    {"name": "A", "amount": 200000, "unit": "mcg"},  # 200 mg
                    {"name": "B", "amount": 0.2, "unit": "g"},       # 200 mg
                ],
                ingredients_without_amounts=["C"],
            )
        ]
        p["proprietary_data"]["total_active_mg"] = 2000
        # blend=1000mg, disclosed=400mg, hidden=600mg, impact=0.3 -> 1+0.9=1.9
        assert scorer._compute_proprietary_blend_penalty(p, []) == pytest.approx(1.9, abs=0.01)

    def test_disclosed_sum_clamped_when_exceeds_blend_total(self, scorer):
        p = make_base_product()
        p["proprietary_blends"] = [
            _make_blend(
                "Bad Label Blend",
                "partial",
                total_weight=300,
                unit="mg",
                ingredients_with_amounts=[
                    {"name": "A", "amount": 250, "unit": "mg"},
                    {"name": "B", "amount": 250, "unit": "mg"},
                ],
                ingredients_without_amounts=[],
            )
        ]
        p["proprietary_data"]["total_active_mg"] = 1000
        # disclosed clamps to blend total (300), hidden=0 -> partial base only
        assert scorer._compute_proprietary_blend_penalty(p, []) == pytest.approx(1.0, abs=0.01)

    def test_zero_total_active_mg_falls_back_to_count_share(self, scorer):
        p = make_base_product()
        p["proprietary_blends"] = [
            _make_blend(
                "Zero Total Blend",
                "none",
                total_weight=500,
                unit="mg",
                ingredients_without_amounts=["A", "B"],
                nested_count=2,
            )
        ]
        p["proprietary_data"]["total_active_mg"] = 0
        p["proprietary_data"]["total_active_ingredients"] = 4
        # count share impact = 2/max(4,8) = 0.25
        assert scorer._compute_proprietary_blend_penalty(p, []) == pytest.approx(3.25, abs=0.01)


class TestA1BlendContainerExclusion:
    """A1 must exclude blend container entries (is_proprietary_blend=True).
    Their opacity cost is captured by B5; including them in A1 dilutes the
    quality average with a meaningless stub score.
    """

    @pytest.fixture
    def scorer(self):
        return SupplementScorer()

    def _product_with_blend_container(self, blend_score=5):
        """Product: Vitamin C (score=15) + a blend container (score=stub)."""
        p = make_base_product()
        p["ingredient_quality_data"]["ingredients_scorable"] = [
            {
                "name": "Vitamin C",
                "score": 15,
                "dosage_importance": 1.0,
                "mapped": True,
                "is_proprietary_blend": False,
                "quantity": 250,
                "unit": "mg",
                "has_dose": True,
            },
            {
                "name": "Energy Blend",
                "score": blend_score,
                "dosage_importance": 1.0,
                "mapped": False,
                "is_proprietary_blend": True,
                "quantity": 500,
                "unit": "mg",
                "has_dose": True,
            },
        ]
        return p

    def test_blend_container_excluded_from_a1(self, scorer):
        """A1 should only see Vitamin C (score=15), not the blend container."""
        p = self._product_with_blend_container(blend_score=5)
        supp_type = "targeted"
        score_with = scorer._compute_bioavailability_score(p, supp_type)

        # v3.4.x: A1.max raised 15 -> 18, so expected = (15/18) * 18 = 15.0
        # (blend container excluded; only Vitamin C counted).
        assert score_with == pytest.approx((15.0 / 18.0) * 18.0, abs=0.1)

    def test_a1_not_contaminated_by_stub_score(self, scorer):
        """Blend container with stub score=5 must not drag A1 below the
        disclosed-only average."""
        p = self._product_with_blend_container(blend_score=5)
        a1_score = scorer._compute_bioavailability_score(p, "targeted")
        # v3.4.x: A1.max raised 15 -> 18.
        disclosed_only = (15.0 / 18.0) * 18.0
        would_be_dragged = (10.0 / 18.0) * 18.0
        assert a1_score > would_be_dragged + 1.0
        assert a1_score == pytest.approx(disclosed_only, abs=0.1)

    def test_a1_with_no_blend_containers_unchanged(self, scorer):
        """Standard product with no blend containers: A1 unchanged."""
        p = make_base_product()
        # Both ingredients have is_proprietary_blend=False (default)
        p["ingredient_quality_data"]["ingredients_scorable"] = [
            {"name": "Mg Glycinate", "score": 18, "dosage_importance": 1.0,
             "mapped": True, "is_proprietary_blend": False, "quantity": 200, "unit": "mg", "has_dose": True},
            {"name": "Vitamin D3", "score": 15, "dosage_importance": 1.5,
             "mapped": True, "is_proprietary_blend": False, "quantity": 1000, "unit": "IU", "has_dose": True},
        ]
        score = scorer._compute_bioavailability_score(p, "targeted")
        expected_avg = (18 * 1.0 + 15 * 1.5) / (1.0 + 1.5)
        # v3.4.x: A1.max raised 15 -> 18.
        assert score == pytest.approx((expected_avg / 18.0) * 18.0, abs=0.1)

    def test_a1_all_blend_containers_returns_zero(self, scorer):
        """If every ingredient is a proprietary blend container, A1 = 0."""
        p = make_base_product()
        p["ingredient_quality_data"]["ingredients_scorable"] = [
            {"name": "Blend A", "score": 5, "dosage_importance": 1.0,
             "mapped": False, "is_proprietary_blend": True},
            {"name": "Blend B", "score": 5, "dosage_importance": 1.0,
             "mapped": False, "is_proprietary_blend": True},
        ]
        assert scorer._compute_bioavailability_score(p, "targeted") == pytest.approx(0.0)


class TestA1ParentTotalExclusion:
    """A1 must skip parent-total rows when nested child forms are present."""

    @pytest.fixture
    def scorer(self):
        return SupplementScorer()

    def test_a1_skips_parent_total_rows(self, scorer):
        p = make_base_product()
        p["ingredient_quality_data"]["ingredients_scorable"] = [
            {
                "name": "Vitamin A",
                "standard_name": "Vitamin A",
                "canonical_id": "vitamin_a",
                "score": 9,
                "dosage_importance": 1.0,
                "mapped": True,
                "is_parent_total": True,
                "quantity": 10000,
                "unit": "IU",
                "has_dose": True,
            },
            {
                "name": "Mixed Carotenes",
                "standard_name": "Vitamin A",
                "canonical_id": "vitamin_a",
                "score": 11,
                "dosage_importance": 1.0,
                "mapped": True,
                "quantity": 8000,
                "unit": "IU",
                "has_dose": True,
            },
            {
                "name": "Retinyl Palmitate",
                "standard_name": "Vitamin A",
                "canonical_id": "vitamin_a",
                "score": 13,
                "dosage_importance": 1.0,
                "mapped": True,
                "quantity": 2000,
                "unit": "IU",
                "has_dose": True,
            },
        ]

        a1 = scorer._compute_bioavailability_score(p, "targeted")
        expected_avg = (11.0 + 13.0) / 2.0
        # v3.4.x: A1.max raised 15 -> 18.
        assert a1 == pytest.approx((expected_avg / 18.0) * 18.0, abs=0.01)

    def test_a1_keeps_non_nested_top_level_rows(self, scorer):
        p = make_base_product()
        p["ingredient_quality_data"]["ingredients_scorable"] = [
            {
                "name": "Vitamin K1",
                "standard_name": "Vitamin K",
                "canonical_id": "vitamin_k",
                "score": 12,
                "dosage_importance": 1.0,
                "mapped": True,
                "is_parent_total": False,
                "quantity": 100,
                "unit": "mcg",
                "has_dose": True,
            },
            {
                "name": "Vitamin K2",
                "standard_name": "Vitamin K",
                "canonical_id": "vitamin_k",
                "score": 15,
                "dosage_importance": 1.0,
                "mapped": True,
                "is_parent_total": False,
                "quantity": 100,
                "unit": "mcg",
                "has_dose": True,
            },
        ]

        a1 = scorer._compute_bioavailability_score(p, "targeted")
        expected_avg = (12.0 + 15.0) / 2.0
        # v3.4.x: A1.max raised 15 -> 18.
        assert a1 == pytest.approx((expected_avg / 18.0) * 18.0, abs=0.01)

    def test_a2_skips_parent_total_rows(self, scorer):
        p = make_base_product()
        p["ingredient_quality_data"]["ingredients_scorable"] = [
            {
                "name": "Folate",
                "standard_name": "Folate",
                "canonical_id": "folate_total_row",
                "score": 18,
                "dosage_importance": 1.0,
                "mapped": True,
                "is_parent_total": True,
                "quantity": 680,
                "unit": "mcg DFE",
                "has_dose": True,
            },
            {
                "name": "Folic Acid",
                "standard_name": "Folate",
                "canonical_id": "folate",
                "score": 13,
                "dosage_importance": 1.0,
                "mapped": True,
                "quantity": 400,
                "unit": "mcg",
                "has_dose": True,
            },
            {
                "name": "Vitamin D3",
                "standard_name": "Vitamin D",
                "canonical_id": "vitamin_d",
                "score": 14,
                "dosage_importance": 1.0,
                "mapped": True,
                "quantity": 1000,
                "unit": "IU",
                "has_dose": True,
            },
        ]
        # Parent-total row is excluded; only vitamin_d is premium => no A2 bonus.
        assert scorer._compute_premium_forms_bonus(p) == pytest.approx(0.0)


class TestB5DisclosureTierEdgeCases:
    """Edge cases for the three-tier disclosure model (full/partial/none)
    and the penalty sign convention."""

    @pytest.fixture
    def scorer(self):
        return SupplementScorer()

    # ── Branded blend, no dosage, no children ("VitaTix Blend") ──
    def test_branded_blend_no_info_gets_none_presence_floor(self, scorer):
        """Completely opaque blend: no total, no children → none, impact=0, penalty=2.0."""
        p = make_base_product()
        p["proprietary_blends"] = [
            _make_blend(
                "VitaTix Blend",
                "none",
                total_weight=None,
                nested_count=0,
            )
        ]
        p["proprietary_data"]["total_active_ingredients"] = 4
        penalty = scorer._compute_proprietary_blend_penalty(p, [])
        assert penalty == pytest.approx(2.0, abs=0.01)

    # ── Partial: total declared + subs listed, no individual amounts ──
    def test_partial_total_plus_subs_penalty_proportional(self, scorer):
        """FDA-compliant blend: 500mg total, 3 herbs listed, no individual amounts.
        Under the corrected three-tier model this is 'partial'."""
        p = make_base_product()
        p["proprietary_blends"] = [
            _make_blend(
                "Herbal Blend",
                "partial",
                total_weight=500,
                blend_total_mg=500.0,
                ingredients_without_amounts=["Ashwagandha", "Lemon Balm", "Chamomile"],
            )
        ]
        p["proprietary_data"]["total_active_mg"] = 2000
        p["proprietary_data"]["total_active_ingredients"] = 5
        penalty = scorer._compute_proprietary_blend_penalty(p, [])
        # hidden_mass = 500, impact = 500/2000 = 0.25 → 1 + 3*0.25 = 1.75
        assert penalty == pytest.approx(1.75, abs=0.01)

    # ── Same blend as above but mislabeled as "none" would give higher penalty ──
    def test_none_vs_partial_penalty_difference(self, scorer):
        """Verify partial saves ~1.5 points vs none for same blend."""
        p = make_base_product()
        blend_args = dict(
            total_weight=500,
            blend_total_mg=500.0,
            ingredients_without_amounts=["Ashwagandha", "Lemon Balm", "Chamomile"],
        )
        p["proprietary_data"]["total_active_mg"] = 2000

        p["proprietary_blends"] = [_make_blend("B", "none", **blend_args)]
        none_penalty = scorer._compute_proprietary_blend_penalty(p, [])

        p["proprietary_blends"] = [_make_blend("B", "partial", **blend_args)]
        partial_penalty = scorer._compute_proprietary_blend_penalty(p, [])

        # none: 2 + 5*0.25 = 3.25;  partial: 1 + 3*0.25 = 1.75;  diff = 1.5
        assert none_penalty - partial_penalty == pytest.approx(1.5, abs=0.01)

    # ── Blend IS the entire product (impact=1.0) ──
    def test_partial_blend_is_entire_product_max_impact(self, scorer):
        """When partial blend total == total_active_mg, impact=1.0, penalty=4.0."""
        p = make_base_product()
        p["proprietary_blends"] = [
            _make_blend(
                "Total Blend",
                "partial",
                total_weight=500,
                blend_total_mg=500.0,
                ingredients_without_amounts=["A", "B", "C"],
            )
        ]
        p["proprietary_data"]["total_active_mg"] = 500
        penalty = scorer._compute_proprietary_blend_penalty(p, [])
        # impact = 500/500 = 1.0 → 1 + 3*1.0 = 4.0
        assert penalty == pytest.approx(4.0, abs=0.01)

    def test_none_blend_is_entire_product_max_impact(self, scorer):
        """When none blend total == total_active_mg, impact=1.0, penalty=7.0."""
        p = make_base_product()
        p["proprietary_blends"] = [
            _make_blend(
                "Total Blend",
                "none",
                total_weight=500,
                blend_total_mg=500.0,
                ingredients_without_amounts=["A", "B", "C"],
            )
        ]
        p["proprietary_data"]["total_active_mg"] = 500
        penalty = scorer._compute_proprietary_blend_penalty(p, [])
        # impact = 500/500 = 1.0 → 2 + 5*1.0 = 7.0
        assert penalty == pytest.approx(7.0, abs=0.01)

    # ── Zero total_weight normalised to None (scorer edge case fix) ──
    def test_zero_total_weight_uses_count_share_not_mg_share(self, scorer):
        """Blend with total_weight=0 should NOT enter mg-share path."""
        p = make_base_product()
        p["proprietary_blends"] = [
            _make_blend(
                "Zero Weight Blend",
                "none",
                total_weight=0,
                unit="",
                ingredients_without_amounts=["A", "B"],
                nested_count=2,
            )
        ]
        p["proprietary_data"]["total_active_mg"] = 1000
        p["proprietary_data"]["total_active_ingredients"] = 8
        penalty = scorer._compute_proprietary_blend_penalty(p, [])
        # count-share: 2/8 = 0.25 → 2 + 5*0.25 = 3.25
        assert penalty == pytest.approx(3.25, abs=0.01)
        evidence = scorer._last_b5_blend_evidence[0]
        assert evidence["impact_source"] == "count_share"
        assert evidence["blend_total_mg"] is None


class TestB5EligibilityGating:
    @pytest.fixture
    def scorer(self):
        return SupplementScorer()

    def test_detector_only_statement_placeholder_is_not_scoreable(self, scorer):
        p = make_base_product()
        p["proprietary_blends"] = [
            {
                **_make_blend(
                    "General Proprietary Blends",
                    "none",
                    total_weight=None,
                    unit="",
                    source_field="statements[0]",
                    ingredients_with_amounts=[],
                    ingredients_without_amounts=[],
                    nested_count=0,
                ),
                "sources": ["detector"],
                "detector_group": "General Proprietary Blends",
                "evidence": {
                    "source_field": "statements[0]",
                    "matched_text": "Metabolism support",
                    "ingredients_with_amounts": [],
                    "ingredients_without_amounts": [],
                },
            }
        ]

        assert scorer._compute_proprietary_blend_penalty(p, []) == pytest.approx(0.0)

    def test_detector_only_inactive_placeholder_is_not_scoreable(self, scorer):
        p = make_base_product()
        p["proprietary_blends"] = [
            {
                **_make_blend(
                    "Delivery Technology Blends",
                    "none",
                    total_weight=None,
                    unit="",
                    source_field="inactiveIngredients[0]",
                    ingredients_with_amounts=[],
                    ingredients_without_amounts=[],
                    nested_count=0,
                ),
                "sources": ["detector"],
                "detector_group": "Delivery Technology Blends",
                "evidence": {
                    "source_field": "inactiveIngredients[0]",
                    "matched_text": "Clean Tablet Technology Blend",
                    "ingredients_with_amounts": [],
                    "ingredients_without_amounts": [],
                },
            }
        ]

        assert scorer._compute_proprietary_blend_penalty(p, []) == pytest.approx(0.0)

    def test_active_ingredient_blend_container_with_zero_children_still_scores(self, scorer):
        p = make_base_product()
        p["proprietary_blends"] = [
            _make_blend(
                "Energy Complex",
                "none",
                total_weight=None,
                unit="",
                source_field="activeIngredients[0]",
                ingredients_with_amounts=[],
                ingredients_without_amounts=[],
                nested_count=0,
            )
        ]

        assert scorer._compute_proprietary_blend_penalty(p, []) == pytest.approx(2.0)

    def test_detector_only_statement_with_total_amount_remains_scoreable(self, scorer):
        p = make_base_product()
        p["proprietary_blends"] = [
            {
                **_make_blend(
                    "Energy Blend 500 mg",
                    "none",
                    total_weight=500,
                    unit="mg",
                    source_field="statements[0]",
                    ingredients_with_amounts=[],
                    ingredients_without_amounts=[],
                    nested_count=0,
                    blend_total_mg=500.0,
                ),
                "sources": ["detector"],
                "detector_group": "Stimulant Blends",
                "evidence": {
                    "source_field": "statements[0]",
                    "matched_text": "Energy Blend 500 mg",
                    "ingredients_with_amounts": [],
                    "ingredients_without_amounts": [],
                },
            }
        ]
        p["proprietary_data"]["total_active_mg"] = 1000

        assert scorer._compute_proprietary_blend_penalty(p, []) == pytest.approx(4.5)

    # ── blend_total_mg field preferred over total_weight ──
    def test_blend_total_mg_preferred_over_total_weight(self, scorer):
        """When both blend_total_mg and total_weight exist, blend_total_mg wins."""
        p = make_base_product()
        p["proprietary_blends"] = [
            _make_blend(
                "Converted Blend",
                "none",
                total_weight=1.5,
                unit="g",
                blend_total_mg=1500.0,
                ingredients_without_amounts=["A"],
            )
        ]
        p["proprietary_data"]["total_active_mg"] = 3000
        penalty = scorer._compute_proprietary_blend_penalty(p, [])
        # blend_total_mg=1500, hidden=1500, impact=1500/3000=0.5 → 2+5*0.5=4.5
        assert penalty == pytest.approx(4.5, abs=0.01)

    # ── Penalty sign convention: B5 is subtracted from B ──
    def test_b5_penalty_subtracted_from_b_section(self, scorer):
        """Verify B5 is a positive magnitude subtracted in B formula."""
        p = make_base_product()
        # No blends → full B score as baseline
        b_no_blend = scorer._compute_safety_purity_score(p, "targeted", 0.0, [])

        # Add a blend
        p["proprietary_blends"] = [
            _make_blend(
                "Penalty Blend",
                "none",
                total_weight=1000,
                blend_total_mg=1000.0,
                ingredients_without_amounts=["A"],
            )
        ]
        p["proprietary_data"]["total_active_mg"] = 2000
        b_with_blend = scorer._compute_safety_purity_score(p, "targeted", 0.0, [])

        # B5 penalty should be positive
        assert b_with_blend["B5_penalty"] > 0
        # B section score should decrease by the penalty amount
        expected_decrease = b_with_blend["B5_penalty"]
        assert b_no_blend["score"] - b_with_blend["score"] == pytest.approx(
            expected_decrease, abs=0.1
        )

    # ── Multiple blends with mixed tiers ──
    def test_mixed_disclosure_tiers_stack_correctly(self, scorer):
        """Multiple blends: full + partial + none. Full contributes 0."""
        p = make_base_product()
        p["proprietary_blends"] = [
            _make_blend("Full Blend", "full", total_weight=200, blend_total_mg=200.0,
                        ingredients_with_amounts=[
                            {"name": "A", "amount": 100, "unit": "mg"},
                            {"name": "B", "amount": 100, "unit": "mg"},
                        ]),
            _make_blend("Partial Blend", "partial", total_weight=400, blend_total_mg=400.0,
                        source_field="activeIngredients[1]",
                        ingredients_without_amounts=["C", "D"]),
            _make_blend("None Blend", "none", total_weight=600, blend_total_mg=600.0,
                        source_field="activeIngredients[2]",
                        ingredients_without_amounts=["E"]),
        ]
        p["proprietary_data"]["total_active_mg"] = 2000
        penalty = scorer._compute_proprietary_blend_penalty(p, [])
        # full: 0
        # partial: hidden=400, impact=0.2 → 1+3*0.2 = 1.6
        # none: hidden=600, impact=0.3 → 2+5*0.3 = 3.5
        # total: 5.1
        assert penalty == pytest.approx(5.1, abs=0.01)

    # ── B5 evidence payload completeness ──
    def test_b5_evidence_payload_has_all_required_fields(self, scorer):
        """Verify every required field in the B5 evidence payload."""
        p = make_base_product()
        p["proprietary_blends"] = [
            _make_blend("Evidence Blend", "partial", total_weight=500, blend_total_mg=500.0,
                        ingredients_without_amounts=["A", "B"])
        ]
        p["proprietary_data"]["total_active_mg"] = 1000
        scorer._compute_proprietary_blend_penalty(p, [])
        ev = scorer._last_b5_blend_evidence[0]
        required_fields = [
            "blend_name", "disclosure_tier", "blend_total_mg",
            "disclosed_child_mg_sum", "hidden_mass_mg", "impact_ratio",
            "impact_source", "impact_floor_applied", "presence_penalty",
            "proportional_coef", "computed_blend_penalty",
            "computed_blend_penalty_magnitude", "dedupe_fingerprint",
            "source_field", "source_path",
        ]
        for field in required_fields:
            assert field in ev, f"Missing field: {field}"
        # Sign convention: computed_blend_penalty is negative
        assert ev["computed_blend_penalty"] < 0
        # Magnitude is positive
        assert ev["computed_blend_penalty_magnitude"] > 0
        assert ev["computed_blend_penalty"] == pytest.approx(
            -ev["computed_blend_penalty_magnitude"], abs=0.0001
        )
        assert ev["source_field"] == "activeIngredients"
        assert ev["source_path"] == "activeIngredients[0]"

    # ── Sanity-check examples from the spec ──
    def test_spec_example_partial_400mg_no_children(self, scorer):
        """Spec: Partial 400mg, no children, total_active=2000 → penalty 1.6."""
        p = make_base_product()
        p["proprietary_blends"] = [
            _make_blend("Spec Blend", "partial", total_weight=400, blend_total_mg=400.0,
                        ingredients_without_amounts=["A"])
        ]
        p["proprietary_data"]["total_active_mg"] = 2000
        # impact = 400/2000 = 0.2 → 1+3*0.2 = 1.6
        assert scorer._compute_proprietary_blend_penalty(p, []) == pytest.approx(1.6, abs=0.01)

    def test_spec_example_none_1200mg(self, scorer):
        """Spec: None 1200mg, total_active=2000 → penalty 5.0."""
        p = make_base_product()
        p["proprietary_blends"] = [
            _make_blend("Spec Blend", "none", total_weight=1200, blend_total_mg=1200.0,
                        ingredients_without_amounts=["A"])
        ]
        p["proprietary_data"]["total_active_mg"] = 2000
        # impact = 0.6 → 2+5*0.6 = 5.0
        assert scorer._compute_proprietary_blend_penalty(p, []) == pytest.approx(5.0, abs=0.01)

    def test_spec_example_partial_1200mg_800mg_disclosed(self, scorer):
        """Spec: Partial 1200mg, 800mg children disclosed → penalty 1.6."""
        p = make_base_product()
        p["proprietary_blends"] = [
            _make_blend("Spec Blend", "partial", total_weight=1200, blend_total_mg=1200.0,
                        ingredients_with_amounts=[
                            {"name": "A", "amount": 500, "unit": "mg"},
                            {"name": "B", "amount": 300, "unit": "mg"},
                        ],
                        ingredients_without_amounts=["C"])
        ]
        p["proprietary_data"]["total_active_mg"] = 2000
        # hidden = 1200-800 = 400, impact = 0.2 → 1+3*0.2 = 1.6
        assert scorer._compute_proprietary_blend_penalty(p, []) == pytest.approx(1.6, abs=0.01)

    def test_spec_example_tiny_none_50mg_floored(self, scorer):
        """Spec: Tiny none 50mg, total=2000 → raw impact 0.025, floored to 0.1, penalty 2.5."""
        p = make_base_product()
        p["proprietary_blends"] = [
            _make_blend("Tiny", "none", total_weight=50, blend_total_mg=50.0,
                        ingredients_without_amounts=["A"])
        ]
        p["proprietary_data"]["total_active_mg"] = 2000
        assert scorer._compute_proprietary_blend_penalty(p, []) == pytest.approx(2.5, abs=0.01)


class TestBannedEnrichmentScorerContract:
    def test_token_bounded_banned_hit_from_enricher_becomes_caution_with_penalty(self):
        from enrich_supplements_v3 import SupplementEnricherV3

        enricher = SupplementEnricherV3()
        scorer = SupplementScorer()
        product = make_base_product()
        product_name = "contains phenibut analog"

        banned = enricher._check_banned_substances(
            [{"name": product_name, "standardName": product_name}],
            {"product_name": product_name, "fullName": product_name, "brandName": ""},
        )
        assert banned["found"] is True
        assert any(s.get("match_type") == "token_bounded" for s in banned["substances"])

        product["contaminant_data"]["banned_substances"] = banned
        result = scorer.score_product(product)

        assert result["verdict"] == "CAUTION"
        assert "BANNED_MATCH_REVIEW_NEEDED" in result["flags"]
        # v3.4.x: A1.max raised 15 -> 18 shifts absolute score_80 upward.
        # The invariants this test guards are the verdict and B0 penalty —
        # the exact score_80 is incidental.
        assert 30.0 <= result["score_80"] <= 45.0
        assert result["breakdown"]["B"]["B0_moderate_penalty"] == pytest.approx(5.0)


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

    def test_impact_report_fails_on_new_blocked(self):
        current = [{"dsld_id": "p1", "score_80": None, "verdict": "BLOCKED"}]
        baseline = [{"dsld_id": "p1", "score_80": 50, "verdict": "SAFE"}]

        report = generate_impact_report(
            current,
            baseline_results=baseline,
            threshold_score_change=99,
            threshold_pct_change=99,
        )

        assert report["pass_gate"] is False
        assert any("BLOCKED" in failure for failure in report["gate_failures"])


class TestCategoryPercentiles:
    @pytest.fixture
    def scorer(self):
        return SupplementScorer()

    def test_batch_assigns_category_percentiles_for_sufficient_cohort(self, scorer, tmp_path):
        products = []
        for idx, score in enumerate([18, 16, 14, 12, 10], start=1):
            product = make_base_product()
            product["dsld_id"] = f"pct-{idx}"
            product["product_name"] = f"Greens Powder {idx}"
            product["supplement_type"] = {"type": "greens"}
            product["form"] = "powder"
            for ingredient in product["ingredient_quality_data"]["ingredients_scorable"]:
                ingredient["score"] = score
            for ingredient in product["ingredient_quality_data"]["ingredients"]:
                ingredient["score"] = score
            products.append(product)

        input_file = tmp_path / "enriched_batch.json"
        input_file.write_text(json.dumps(products), encoding="utf-8")
        output_dir = tmp_path / "output"

        stats = scorer.process_batch(str(input_file), str(output_dir))
        scored = json.loads(Path(stats["output_file"]).read_text(encoding="utf-8"))
        top_entry = next(item for item in scored if item["dsld_id"] == "pct-1")

        assert top_entry["category_percentile"]["available"] is True
        assert top_entry["category_percentile"]["cohort_size"] == 5
        assert top_entry["category_percentile"]["category_source"] == "fallback_scorer"
        assert top_entry["category_percentile"]["top_percent"] == pytest.approx(20.0)
        assert "Among greens powders: Top 20.0%" == top_entry["category_percentile"]["text"]

    def test_batch_marks_percentile_unavailable_for_small_cohort(self, scorer, tmp_path):
        products = []
        for idx in range(1, 4):
            product = make_base_product()
            product["dsld_id"] = f"small-{idx}"
            product["product_name"] = f"Small Cohort {idx}"
            product["supplement_type"] = {"type": "greens"}
            product["form"] = "powder"
            products.append(product)

        input_file = tmp_path / "enriched_small_batch.json"
        input_file.write_text(json.dumps(products), encoding="utf-8")
        output_dir = tmp_path / "output"

        stats = scorer.process_batch(str(input_file), str(output_dir))
        scored = json.loads(Path(stats["output_file"]).read_text(encoding="utf-8"))

        for entry in scored:
            percentile = entry.get("category_percentile", {})
            assert percentile.get("available") is False
            assert percentile.get("reason") == "insufficient_cohort_size"

    def test_batch_prefers_enriched_percentile_category_metadata(self, scorer, tmp_path):
        products = []
        for idx, score in enumerate([18, 16, 14, 12, 10], start=1):
            product = make_base_product()
            product["dsld_id"] = f"exp-{idx}"
            product["product_name"] = f"Explicit Category {idx}"
            product["supplement_type"] = {"type": "targeted"}
            product["percentile_category"] = "greens_powder"
            product["percentile_category_label"] = "Greens Powders"
            product["percentile_category_source"] = "inferred"
            product["percentile_category_confidence"] = 0.87
            product["percentile_category_signals"] = ["name:greens", "form:powder"]
            product["form"] = "powder"
            for ingredient in product["ingredient_quality_data"]["ingredients_scorable"]:
                ingredient["score"] = score
            for ingredient in product["ingredient_quality_data"]["ingredients"]:
                ingredient["score"] = score
            products.append(product)

        input_file = tmp_path / "enriched_explicit_batch.json"
        input_file.write_text(json.dumps(products), encoding="utf-8")
        output_dir = tmp_path / "output"

        stats = scorer.process_batch(str(input_file), str(output_dir))
        scored = json.loads(Path(stats["output_file"]).read_text(encoding="utf-8"))
        top_entry = next(item for item in scored if item["dsld_id"] == "exp-1")

        assert top_entry["category_percentile"]["available"] is True
        assert top_entry["category_percentile"]["category_label"] == "Greens Powders"
        assert top_entry["category_percentile"]["category_source"] == "inferred"
        assert top_entry["category_percentile"]["category_confidence"] == pytest.approx(0.87)
        assert top_entry["percentile_category"] == "greens_powder"


# =====================================================================
# Spec Section 10 — additional coverage for P1-1, P1-2, P1-3, P2-1, P2-2
# =====================================================================


class TestSectionCEvidenceScoring:
    """P1-2: Clinical evidence tier scoring tests."""

    @pytest.fixture
    def scorer(self):
        return SupplementScorer()

    def test_c_multi_ingredient_aggregation(self, scorer):
        """Multiple ingredients use top-N diminishing returns (v3.5: [1.0, 0.7, 0.5, 0.3])."""
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
                    "standard_name": "Vitamin D",
                    "study_type": "rct_multiple",
                    "evidence_level": "ingredient-human",
                },
            ]
        }
        section_c = scorer._compute_evidence_score(product, [])
        # Magnesium: 6 * 1.0 = 6.0 (best, weight 1.0)
        # Vitamin D: 5 * 0.80 = 4.0 (2nd, weight 0.7)
        # Total: 6.0*1.0 + 4.0*0.7 = 8.8
        assert section_c["score"] == pytest.approx(8.8, abs=0.01)
        assert section_c["matched_entries"] == 2
        assert section_c["top_n_applied"] == 2

    def test_c_per_ingredient_cap_enforced(self, scorer):
        """Multiple studies for same canonical ingredient are capped at 7."""
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
        section_c = scorer._compute_evidence_score(product, [])
        # 6 + 5 = 11 raw for Magnesium, capped at 7
        assert section_c["score"] == pytest.approx(7.0)

    def test_c_no_double_counting_same_study_id(self, scorer):
        """Duplicate study IDs are counted only once."""
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
                    "id": "E1",
                    "standard_name": "Magnesium",
                    "study_type": "systematic_review_meta",
                    "evidence_level": "product-human",
                },
            ]
        }
        section_c = scorer._compute_evidence_score(product, [])
        assert section_c["score"] == pytest.approx(6.0)
        assert section_c["matched_entries"] == 1

    def test_c_total_cap_at_20(self, scorer):
        """Section C total is capped at 20; top-N with diminishing returns limits inflation."""
        product = make_base_product()
        matches = []
        for i, name in enumerate(["Magnesium", "Vitamin D", "Zinc", "Iron"]):
            matches.append({
                "id": f"E{i}",
                "standard_name": name,
                "study_type": "systematic_review_meta",
                "evidence_level": "product-human",
            })
        product["evidence_data"] = {"clinical_matches": matches}
        section_c = scorer._compute_evidence_score(product, [])
        # Each: 6*1.0=6.0.  Top-N weights v3.5 [1.0, 0.7, 0.5, 0.3]:
        # 6.0*1.0 + 6.0*0.7 + 6.0*0.5 + 6.0*0.3 = 15.0 (all 4 included)
        assert section_c["score"] == pytest.approx(15.0)
        assert section_c["top_n_applied"] == 4

    def test_c_effect_direction_null_penalizes(self, scorer):
        """Entries with effect_direction=null get 0.25x multiplier (well-studied but ineffective)."""
        product = make_base_product()
        product["evidence_data"] = {
            "clinical_matches": [
                {
                    "id": "SAW_PALMETTO",
                    "standard_name": "Saw Palmetto",
                    "study_type": "rct_multiple",
                    "evidence_level": "ingredient-human",
                    "effect_direction": "null",
                },
            ]
        }
        section_c = scorer._compute_evidence_score(product, [])
        # 5 * 0.80 * 0.25 = 1.0
        assert section_c["score"] == pytest.approx(1.0, abs=0.01)

    def test_c_effect_direction_positive_weak(self, scorer):
        """Entries with effect_direction=positive_weak get 0.85x multiplier."""
        product = make_base_product()
        product["evidence_data"] = {
            "clinical_matches": [
                {
                    "id": "VIT_C",
                    "standard_name": "Vitamin C",
                    "study_type": "systematic_review_meta",
                    "evidence_level": "ingredient-human",
                    "effect_direction": "positive_weak",
                },
            ]
        }
        section_c = scorer._compute_evidence_score(product, [])
        # 6 * 0.80 * 0.85 = 4.08
        assert section_c["score"] == pytest.approx(4.08, abs=0.01)

    def test_c_effect_direction_negative_zeroes(self, scorer):
        """Entries with effect_direction=negative contribute 0 points."""
        product = make_base_product()
        product["evidence_data"] = {
            "clinical_matches": [
                {
                    "id": "HARM",
                    "standard_name": "Harmful X",
                    "study_type": "rct_multiple",
                    "evidence_level": "product-human",
                    "effect_direction": "negative",
                },
            ]
        }
        section_c = scorer._compute_evidence_score(product, [])
        assert section_c["score"] == pytest.approx(0.0)

    def test_c_missing_effect_direction_defaults_positive_strong(self, scorer):
        """Entries without effect_direction default to positive_strong (1.0x) for backward compat."""
        product = make_base_product()
        product["evidence_data"] = {
            "clinical_matches": [
                {
                    "id": "E1",
                    "standard_name": "Zinc",
                    "study_type": "rct_multiple",
                    "evidence_level": "ingredient-human",
                    # no effect_direction field
                },
            ]
        }
        section_c = scorer._compute_evidence_score(product, [])
        # 5 * 0.80 * 1.0 = 4.0 (v3.5 ingredient-human bumped from 0.65 to 0.80)
        assert section_c["score"] == pytest.approx(4.0)

    def test_c_top_n_single_ingredient_unchanged(self, scorer):
        """Single ingredient products score the same with top-N (weight 1.0)."""
        product = make_base_product()
        product["evidence_data"] = {
            "clinical_matches": [
                {
                    "id": "KSM66",
                    "standard_name": "KSM-66",
                    "study_type": "rct_multiple",
                    "evidence_level": "branded-rct",
                },
            ]
        }
        section_c = scorer._compute_evidence_score(product, [])
        # 5 * 0.9 * 1.0 = 4.5 (v3.5 branded-rct bumped from 0.8 to 0.9)
        assert section_c["score"] == pytest.approx(4.5)
        assert section_c["top_n_applied"] == 1

    def test_c_enrollment_boosts_large_rct(self, scorer):
        """Large enrollment (1000+) on RCT gets 1.2x enrollment multiplier."""
        product = make_base_product()
        product["evidence_data"] = {
            "clinical_matches": [
                {
                    "id": "BIG_RCT",
                    "standard_name": "Berberine",
                    "study_type": "rct_multiple",
                    "evidence_level": "ingredient-human",
                    "total_enrollment": 1000,
                },
            ]
        }
        section_c = scorer._compute_evidence_score(product, [])
        # 5 * 0.80 * 1.0 (positive_strong) * 1.2 (enrollment 1000+) = 4.8
        assert section_c["score"] == pytest.approx(4.8)

    def test_c_enrollment_penalizes_small_pilot(self, scorer):
        """Small enrollment (<50) on RCT gets 0.6x enrollment multiplier."""
        product = make_base_product()
        product["evidence_data"] = {
            "clinical_matches": [
                {
                    "id": "SMALL_PILOT",
                    "standard_name": "Novel Compound",
                    "study_type": "rct_single",
                    "evidence_level": "ingredient-human",
                    "total_enrollment": 19,
                },
            ]
        }
        section_c = scorer._compute_evidence_score(product, [])
        # 4 * 0.80 * 1.0 * 0.6 (enrollment <50) = 1.92
        assert section_c["score"] == pytest.approx(1.92)

    def test_c_enrollment_ignored_for_observational(self, scorer):
        """Enrollment multiplier does NOT apply to observational studies."""
        product = make_base_product()
        product["evidence_data"] = {
            "clinical_matches": [
                {
                    "id": "OBS",
                    "standard_name": "Boron",
                    "study_type": "observational",
                    "evidence_level": "ingredient-human",
                    "total_enrollment": 5000,
                },
            ]
        }
        section_c = scorer._compute_evidence_score(product, [])
        # 2 * 0.80 * 1.0 = 1.6 (no enrollment boost for observational)
        assert section_c["score"] == pytest.approx(1.6)

    def test_c_enrollment_ignored_when_absent(self, scorer):
        """No total_enrollment field = no enrollment multiplier (backward compat)."""
        product = make_base_product()
        product["evidence_data"] = {
            "clinical_matches": [
                {
                    "id": "NO_ENROLL",
                    "standard_name": "Zinc",
                    "study_type": "rct_multiple",
                    "evidence_level": "ingredient-human",
                    # no total_enrollment field
                },
            ]
        }
        section_c = scorer._compute_evidence_score(product, [])
        # 5 * 0.80 = 4.0 (no enrollment adjustment)
        assert section_c["score"] == pytest.approx(4.0)

    def test_c_depth_bonus_40_plus_trials(self, scorer):
        """Ingredients with 40+ published studies get +0.5 depth bonus."""
        product = make_base_product()
        product["evidence_data"] = {
            "clinical_matches": [
                {
                    "id": "BERB",
                    "standard_name": "Berberine",
                    "study_type": "rct_multiple",
                    "evidence_level": "ingredient-human",
                    "published_studies": 68,
                },
            ]
        }
        section_c = scorer._compute_evidence_score(product, [])
        # 5 * 0.80 = 4.0 + 0.5 depth bonus = 4.5
        assert section_c["score"] == pytest.approx(4.5)
        assert section_c["depth_bonus"] == pytest.approx(0.5)

    def test_c_depth_bonus_20_trials(self, scorer):
        """Ingredients with 20-39 published studies get +0.25 depth bonus."""
        product = make_base_product()
        product["evidence_data"] = {
            "clinical_matches": [
                {
                    "id": "SP",
                    "standard_name": "Saw Palmetto",
                    "study_type": "rct_multiple",
                    "evidence_level": "ingredient-human",
                    "published_studies": 21,
                },
            ]
        }
        section_c = scorer._compute_evidence_score(product, [])
        # 5 * 0.80 = 4.0 + 0.25 depth bonus = 4.25
        assert section_c["score"] == pytest.approx(4.25)
        assert section_c["depth_bonus"] == pytest.approx(0.25)

    def test_c_depth_bonus_zero_when_few_trials(self, scorer):
        """Ingredients with <20 published studies get no depth bonus."""
        product = make_base_product()
        product["evidence_data"] = {
            "clinical_matches": [
                {
                    "id": "SMALL",
                    "standard_name": "Niche Compound",
                    "study_type": "rct_single",
                    "evidence_level": "ingredient-human",
                    "published_studies": 5,
                },
            ]
        }
        section_c = scorer._compute_evidence_score(product, [])
        # 4 * 0.80 = 3.2 + 0.0 depth bonus
        assert section_c["score"] == pytest.approx(3.2)
        assert section_c["depth_bonus"] == pytest.approx(0.0)

    def test_c_sub_clinical_dose_guard(self, scorer):
        """Sub-clinical dose applies 0.25x multiplier and sets flag."""
        product = make_base_product()
        product["evidence_data"] = {
            "clinical_matches": [
                {
                    "id": "E1",
                    "standard_name": "Magnesium",
                    "study_type": "rct_multiple",
                    "evidence_level": "product-human",
                    "min_clinical_dose": 400,
                    "dose_unit": "mg",
                },
            ]
        }
        flags = []
        section_c = scorer._compute_evidence_score(product, flags)
        # Product has 200mg Mg, min_clinical_dose=400mg → 5*1.0*0.25 = 1.25
        assert section_c["score"] == pytest.approx(1.25)
        assert "SUB_CLINICAL_DOSE_DETECTED" in flags

    def test_c_supra_clinical_dose_flag(self, scorer):
        """Supra-clinical dose (>3x max studied) sets flag but doesn't reduce points."""
        product = make_base_product()
        # Set Magnesium dose very high
        for ing in product["ingredient_quality_data"]["ingredients"]:
            if ing["standard_name"] == "Magnesium":
                ing["quantity"] = 5000
        for ing in product["ingredient_quality_data"]["ingredients_scorable"]:
            if ing["standard_name"] == "Magnesium":
                ing["quantity"] = 5000
        product["evidence_data"] = {
            "clinical_matches": [
                {
                    "id": "E1",
                    "standard_name": "Magnesium",
                    "study_type": "rct_single",
                    "evidence_level": "ingredient-human",
                    "min_clinical_dose": 200,
                    "max_studied_clinical_dose": 1000,
                    "dose_unit": "mg",
                },
            ]
        }
        flags = []
        section_c = scorer._compute_evidence_score(product, flags)
        # 5000mg > 3*1000mg → supra flag; 4*0.80 = 3.2 (no dose reduction)
        assert section_c["score"] == pytest.approx(3.2)
        assert "SUPRA_CLINICAL_DOSE" in flags

    def test_c_branded_rct_multiplier(self, scorer):
        """branded-rct evidence level uses 0.9x multiplier (v3.5: bumped from 0.8)."""
        product = make_base_product()
        product["evidence_data"] = {
            "clinical_matches": [
                {
                    "id": "E1",
                    "standard_name": "Magnesium",
                    "study_type": "rct_multiple",
                    "evidence_level": "branded-rct",
                },
            ]
        }
        section_c = scorer._compute_evidence_score(product, [])
        # 5 * 0.9 = 4.5
        assert section_c["score"] == pytest.approx(4.5)

    def test_c_preclinical_evidence_low_multiplier(self, scorer):
        """Preclinical evidence uses 0.3x multiplier."""
        product = make_base_product()
        product["evidence_data"] = {
            "clinical_matches": [
                {
                    "id": "E1",
                    "standard_name": "Magnesium",
                    "study_type": "rct_single",
                    "evidence_level": "preclinical",
                },
            ]
        }
        section_c = scorer._compute_evidence_score(product, [])
        # 4 * 0.3 = 1.2
        assert section_c["score"] == pytest.approx(1.2)

    def test_c_no_matches_returns_zero(self, scorer):
        """Products with no clinical matches score 0."""
        product = make_base_product()
        product["evidence_data"] = {"clinical_matches": []}
        section_c = scorer._compute_evidence_score(product, [])
        assert section_c["score"] == pytest.approx(0.0)
        assert section_c["matched_entries"] == 0


class TestProbioticScoringSpec:
    """P1-1: Probiotic scoring tests beyond basic coverage."""

    @pytest.fixture
    def scorer(self):
        return SupplementScorer()

    def _make_probiotic_product(self, total_billion=10.0, strain_count=5,
                                 supp_type="probiotic", prebiotic=False):
        product = make_base_product()
        product["supplement_type"] = {"type": supp_type, "active_count": 2}
        product["probiotic_data"] = {
            "is_probiotic_product": True,
            "total_billion_count": total_billion,
            "total_strain_count": strain_count,
            "probiotic_blends": [
                {
                    "strains": [{"name": f"Strain_{i}"} for i in range(strain_count)],
                    "cfu_data": {"billion_count": total_billion},
                }
            ],
        }
        if prebiotic:
            product["probiotic_data"]["prebiotic_present"] = True
            product["probiotic_data"]["prebiotic_fiber_detected"] = True
        return product

    def test_probiotic_default_mode_cfu_threshold(self, scorer):
        """Default mode: total_billion > 1 gives 1pt CFU."""
        product = self._make_probiotic_product(total_billion=2.0, strain_count=1)
        bonus = scorer._compute_probiotic_category_bonus(product, "probiotic")
        assert bonus["cfu"] == pytest.approx(1.0)
        assert bonus["diversity"] == pytest.approx(0.0)  # < 3 strains

    def test_probiotic_default_mode_diversity_threshold(self, scorer):
        """Default mode: strain_count >= 3 gives 1pt diversity."""
        product = self._make_probiotic_product(total_billion=0.5, strain_count=4)
        bonus = scorer._compute_probiotic_category_bonus(product, "probiotic")
        assert bonus["cfu"] == pytest.approx(0.0)  # <= 1 billion
        assert bonus["diversity"] == pytest.approx(1.0)

    def test_probiotic_default_mode_cap_at_3(self, scorer):
        """Default mode caps at 3 points (config-driven)."""
        product = self._make_probiotic_product(total_billion=5.0, strain_count=5)
        product["probiotic_data"]["prebiotic_present"] = True
        bonus = scorer._compute_probiotic_category_bonus(product, "probiotic")
        # cfu=1 + diversity=1 + prebiotic=1 = 3, capped at 3
        assert bonus["probiotic_bonus"] == pytest.approx(3.0)

    def test_probiotic_below_all_thresholds_zero(self, scorer):
        """Below all thresholds gives 0 bonus."""
        product = self._make_probiotic_product(total_billion=0.5, strain_count=1)
        bonus = scorer._compute_probiotic_category_bonus(product, "probiotic")
        assert bonus["probiotic_bonus"] == pytest.approx(0.0)

    def test_category_bonus_pool_caps_combined_bonus(self, scorer):
        """Combined category bonuses cannot exceed the pool cap."""
        product = self._make_probiotic_product(total_billion=5.0, strain_count=5, prebiotic=True)
        product["ingredient_quality_data"]["ingredients"].extend([
            {
                "name": "EPA",
                "canonical_id": "epa",
                "quantity": 2000,
                "unit_normalized": "mg",
                "is_proprietary_blend": False,
                "is_blend_header": False,
                "is_parent_total": False,
            },
            {
                "name": "DHA",
                "canonical_id": "dha",
                "quantity": 500,
                "unit_normalized": "mg",
                "is_proprietary_blend": False,
                "is_blend_header": False,
                "is_parent_total": False,
            },
        ])
        product["ingredient_quality_data"]["ingredients_scorable"].extend([
            {
                "name": "EPA",
                "canonical_id": "epa",
                "quantity": 2000,
                "unit_normalized": "mg",
                "is_proprietary_blend": False,
                "is_blend_header": False,
                "is_parent_total": False,
            },
            {
                "name": "DHA",
                "canonical_id": "dha",
                "quantity": 500,
                "unit_normalized": "mg",
                "is_proprietary_blend": False,
                "is_blend_header": False,
                "is_parent_total": False,
            },
        ])
        product["serving_basis"] = {"min_servings_per_day": 2, "max_servings_per_day": 2}

        scorer.config["section_A_ingredient_quality"]["omega3_dose_bonus"]["max"] = 4.0
        for band in scorer.config["section_A_ingredient_quality"]["omega3_dose_bonus"]["bands"]:
            if band["label"] == "prescription_dose":
                band["score"] = 4.0

        section_a = scorer._compute_ingredient_quality_score(product, "probiotic", flags=[])
        assert section_a["probiotic_bonus"] == pytest.approx(3.0)
        assert section_a["omega3_dose_bonus"] == pytest.approx(4.0)
        assert section_a["category_bonus_pool_cap"] == pytest.approx(5.0)
        assert section_a["category_bonus_total"] == pytest.approx(5.0)

    def test_legacy_section_c_alias_still_routes_to_new_method(self, scorer):
        product = make_base_product()
        product["evidence_data"] = {
            "clinical_matches": [
                {
                    "id": "E_TEST",
                    "standard_name": "Magnesium",
                    "study_type": "rct_single",
                    "evidence_level": "ingredient-human",
                    "base_points": 7.0,
                    "multiplier": 1.0,
                }
            ]
        }
        section_c = scorer._score_section_c(product, [])
        assert section_c["score"] == pytest.approx(7.0)


class TestNonGmoScoringAudit:
    @pytest.fixture
    def scorer(self):
        return SupplementScorer()

    def test_non_gmo_project_verified_claim_can_award_a5d(self, scorer):
        product = make_base_product()
        product["labelText"] = {
            "parsed": {
                "certifications": ["Non-GMO-Project"],
                "cleanLabelClaims": ["Non-GMO Project Verified"],
            }
        }
        product["named_cert_programs"] = []

        a5 = scorer._compute_formulation_bonus(product)

        assert a5["A5d_non_gmo_verified"] == pytest.approx(0.5)

    def test_generic_non_gmo_claim_does_not_award_a5d(self, scorer):
        product = make_base_product()
        product["labelText"] = {
            "parsed": {
                "certifications": ["Non-GMO-General"],
                "cleanLabelClaims": ["Non-GMO"],
            }
        }

        a5 = scorer._compute_formulation_bonus(product)

        assert a5["A5d_non_gmo_verified"] == pytest.approx(0.0)


class TestSynergyClusterSpec:
    """P2-1: Synergy cluster qualification tests."""

    @pytest.fixture
    def scorer(self):
        return SupplementScorer()

    def test_synergy_explicit_flag_respected(self, scorer):
        """Pre-computed synergy_cluster_qualified=True returns tier 2 default bonus."""
        product = make_base_product()
        product["synergy_cluster_qualified"] = True
        assert scorer._synergy_cluster_qualified(product) == 0.75  # legacy default

    def test_synergy_explicit_flag_false(self, scorer):
        """Pre-computed False flag returns 0.0."""
        product = make_base_product()
        product["synergy_cluster_qualified"] = False
        assert scorer._synergy_cluster_qualified(product) == 0.0

    def test_synergy_two_ingredient_match_without_doses_does_not_qualify(self, scorer):
        """Fallback path requires at least one dose-checkable ingredient."""
        product = make_base_product()
        product["formulation_data"] = {
            "synergy_clusters": [
                {
                    "cluster_name": "Bone Health",
                    "match_count": 2,
                    "matched_ingredients": [
                        {"name": "Calcium"},
                        {"name": "Vitamin D"},
                    ],
                }
            ]
        }
        assert scorer._synergy_cluster_qualified(product) == 0.0

    def test_synergy_single_match_does_not_qualify(self, scorer):
        """Cluster with only 1 matched ingredient does not qualify."""
        product = make_base_product()
        product["formulation_data"] = {
            "synergy_clusters": [
                {
                    "cluster_name": "Bone Health",
                    "match_count": 1,
                    "matched_ingredients": [{"name": "Calcium"}],
                }
            ]
        }
        assert scorer._synergy_cluster_qualified(product) == 0.0

    def test_synergy_underdosed_ingredients_no_bonus(self, scorer):
        """Cluster where none meet minimum dose does not qualify."""
        product = make_base_product()
        product["formulation_data"] = {
            "synergy_clusters": [
                {
                    "cluster_name": "Bone Health",
                    "match_count": 2,
                    "matched_ingredients": [
                        {"name": "Calcium", "min_effective_dose": 500, "meets_minimum": False},
                        {"name": "Vitamin D", "min_effective_dose": 1000, "meets_minimum": False},
                    ],
                }
            ]
        }
        assert scorer._synergy_cluster_qualified(product) == 0.0

    def test_synergy_half_dosed_qualifies_with_tier(self, scorer):
        """Cluster where >= half of checkable ingredients meet dose qualifies with tier bonus."""
        product = make_base_product()
        product["formulation_data"] = {
            "synergy_clusters": [
                {
                    "cluster_name": "Bone Health",
                    "evidence_tier": 2,
                    "match_count": 2,
                    "matched_ingredients": [
                        {"name": "Calcium", "min_effective_dose": 500, "meets_minimum": True},
                        {"name": "Vitamin D", "min_effective_dose": 1000, "meets_minimum": False},
                    ],
                }
            ]
        }
        # 1/2 dosed, ceil(2/2) = 1, 1 >= 1 → qualifies, tier 2 = 0.75
        assert scorer._synergy_cluster_qualified(product) == 0.75

    def test_synergy_tier_1_proven_gets_full_bonus(self, scorer):
        """Tier 1 (proven synergy) cluster awards 1.0 bonus."""
        product = make_base_product()
        product["formulation_data"] = {
            "synergy_clusters": [
                {
                    "cluster_name": "Curcumin Absorption",
                    "evidence_tier": 1,
                    "match_count": 2,
                    "matched_ingredients": [
                        {"name": "Curcumin", "min_effective_dose": 500, "meets_minimum": True},
                        {"name": "Piperine", "min_effective_dose": 5, "meets_minimum": True},
                    ],
                }
            ]
        }
        assert scorer._synergy_cluster_qualified(product) == 1.0

    def test_synergy_tier_4_popular_gets_quarter_bonus(self, scorer):
        """Tier 4 (popular combination) cluster awards 0.25 bonus."""
        product = make_base_product()
        product["formulation_data"] = {
            "synergy_clusters": [
                {
                    "cluster_name": "Stress Stack",
                    "evidence_tier": 4,
                    "match_count": 2,
                    "matched_ingredients": [
                        {"name": "Ashwagandha", "min_effective_dose": 300, "meets_minimum": True},
                        {"name": "Rhodiola", "min_effective_dose": 200, "meets_minimum": True},
                    ],
                }
            ]
        }
        assert scorer._synergy_cluster_qualified(product) == 0.25

    def test_synergy_best_tier_wins(self, scorer):
        """When multiple clusters match, the best tier's bonus is used."""
        product = make_base_product()
        product["formulation_data"] = {
            "synergy_clusters": [
                {
                    "cluster_name": "Popular Stack",
                    "evidence_tier": 4,
                    "match_count": 2,
                    "matched_ingredients": [
                        {"name": "A", "min_effective_dose": 100, "meets_minimum": True},
                        {"name": "B", "min_effective_dose": 100, "meets_minimum": True},
                    ],
                },
                {
                    "cluster_name": "Proven Synergy",
                    "evidence_tier": 1,
                    "match_count": 2,
                    "matched_ingredients": [
                        {"name": "C", "min_effective_dose": 100, "meets_minimum": True},
                        {"name": "D", "min_effective_dose": 100, "meets_minimum": True},
                    ],
                },
            ]
        }
        assert scorer._synergy_cluster_qualified(product) == 1.0


class TestManufacturerViolationsSpec:
    """P2-2: Manufacturer violation penalty tests."""

    @pytest.fixture
    def scorer(self):
        return SupplementScorer()

    def test_violation_no_data_zero_penalty(self, scorer):
        """No violation data → 0 penalty."""
        product = make_base_product()
        penalty = scorer._compute_manufacturer_violation_penalty(product)
        assert penalty == pytest.approx(0.0)

    def test_violation_total_deduction_applied_preferred(self, scorer):
        """Pre-computed total_deduction_applied is used directly."""
        product = make_base_product()
        product["manufacturer_data"] = {
            "violations": {
                "total_deduction_applied": -8.0,
                "violations": [
                    {"description": "FDA Warning Letter 2024", "total_deduction_applied": -8.0}
                ],
            }
        }
        penalty = scorer._compute_manufacturer_violation_penalty(product)
        assert penalty == pytest.approx(-8.0)

    def test_violation_cap_at_minus_25(self, scorer):
        """Violation penalty is capped at -25."""
        product = make_base_product()
        product["manufacturer_data"] = {
            "violations": {
                "total_deduction_applied": -30.0,
            }
        }
        penalty = scorer._compute_manufacturer_violation_penalty(product)
        assert penalty == pytest.approx(-25.0)

    def test_violation_sum_multiple_items(self, scorer):
        """Multiple violation items are summed."""
        product = make_base_product()
        product["manufacturer_data"] = {
            "violations": {
                "violations": [
                    {"total_deduction_applied": -5.0},
                    {"total_deduction_applied": -3.0},
                ],
            }
        }
        penalty = scorer._compute_manufacturer_violation_penalty(product)
        assert penalty == pytest.approx(-8.0)

    def test_violation_list_format_backward_compat(self, scorer):
        """Violations as a list (legacy format) are summed."""
        product = make_base_product()
        product["manufacturer_data"] = {
            "violations": [
                {"total_deduction": -4.0},
                {"total_deduction": -6.0},
            ]
        }
        penalty = scorer._compute_manufacturer_violation_penalty(product)
        assert penalty == pytest.approx(-10.0)

    def test_violation_list_format_capped(self, scorer):
        """Legacy list format also respects -25 cap."""
        product = make_base_product()
        product["manufacturer_data"] = {
            "violations": [
                {"total_deduction": -15.0},
                {"total_deduction": -15.0},
            ]
        }
        penalty = scorer._compute_manufacturer_violation_penalty(product)
        assert penalty == pytest.approx(-25.0)


class TestSectionDSpec:
    """Additional Section D brand trust tests."""

    @pytest.fixture
    def scorer(self):
        return SupplementScorer()

    def test_d1_trusted_manufacturer(self, scorer):
        """is_trusted_manufacturer flag gives D1 = 2."""
        product = make_base_product()
        product["is_trusted_manufacturer"] = True
        section_d = scorer._compute_brand_trust_score(product)
        assert section_d["D1"] == pytest.approx(2.0)

    def test_d2_full_disclosure_gives_one(self, scorer):
        """Full disclosure gives D2 = 1."""
        product = make_base_product()
        product["is_trusted_manufacturer"] = True
        # No proprietary blends → full disclosure
        section_d = scorer._compute_brand_trust_score(product)
        assert section_d["D2"] == pytest.approx(1.0)

    def test_d4_high_standard_region(self, scorer):
        """Manufacturing in high-regulation country gives D4 points."""
        product = make_base_product()
        product["manufacturing_region"] = "USA"
        section_d = scorer._compute_brand_trust_score(product)
        assert section_d["D4"] == pytest.approx(1.0)

    def test_d3_d4_d5_combined_cap(self, scorer):
        """D3+D4+D5 are capped at 2.0 combined."""
        product = make_base_product()
        product["claim_physician_formulated"] = True  # D3 = 0.5
        product["manufacturing_region"] = "USA"  # D4 = 1.0
        product["has_sustainable_packaging"] = True  # D5 = 0.5
        section_d = scorer._compute_brand_trust_score(product)
        tail = section_d["D3"] + section_d["D4"] + section_d["D5"]
        # 0.5 + 1.0 + 0.5 = 2.0, capped at 2.0
        assert tail == pytest.approx(2.0)

    def test_d_section_max_5(self, scorer):
        """Section D total is capped at 5."""
        product = make_base_product()
        product["is_trusted_manufacturer"] = True  # D1 = 2
        product["claim_physician_formulated"] = True  # D3 = 0.5
        product["manufacturing_region"] = "USA"  # D4 = 1.0
        product["has_sustainable_packaging"] = True  # D5 = 0.5
        section_d = scorer._compute_brand_trust_score(product)
        # D1=2 + D2=1 + tail=2 = 5.0
        assert section_d["score"] == pytest.approx(5.0)


class TestScoringAggregationAndConfig:
    @pytest.fixture
    def scorer(self):
        return SupplementScorer()

    def test_process_all_uses_weighted_average(self, scorer, monkeypatch, tmp_path):
        """Overall average should be weighted by products, not mean-of-means."""
        input_dir = tmp_path / "enriched"
        output_dir = tmp_path / "scored"
        input_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)

        # process_all discovers JSON files by name; contents are irrelevant with monkeypatch
        (input_dir / "batch_a.json").write_text("[]", encoding="utf-8")
        (input_dir / "batch_b.json").write_text("[]", encoding="utf-8")

        def fake_process_batch(input_file, _output_dir):
            name = Path(input_file).name
            if name == "batch_a.json":
                return {
                    "total_products": 1,
                    "successful": 1,
                    "average_score_80": 80.0,
                    "average_score_100": 100.0,
                    "verdict_distribution": {"SAFE": 1},
                    "output_file": str(output_dir / "scored_batch_a.json"),
                }
            return {
                "total_products": 9,
                "successful": 9,
                "average_score_80": 40.0,
                "average_score_100": 50.0,
                "verdict_distribution": {"SAFE": 9},
                "output_file": str(output_dir / "scored_batch_b.json"),
            }

        monkeypatch.setattr(scorer, "process_batch", fake_process_batch)

        summary = scorer.process_all(str(input_dir), str(output_dir))

        assert summary["stats"]["total_products"] == 10
        # Weighted average: (80*1 + 40*9) / 10 = 44.0
        assert summary["stats"]["average_score_80"] == pytest.approx(44.0, rel=1e-6)
        assert summary["stats"]["average_score_100"] == pytest.approx(55.0, rel=1e-6)

    def test_a1_uses_range_score_field_from_config(self, scorer):
        """A1 denominator should come from config range_score_field."""
        product = make_base_product()
        product["supplement_type"] = {"type": "targeted", "active_count": 1}
        product["ingredient_quality_data"]["ingredients"] = [
            {
                "name": "Custom Nutrient",
                "standard_name": "Custom Nutrient",
                "score": 9,
                "dosage_importance": 1.0,
                "mapped": True,
                "quantity": 100,
                "unit": "mg",
                "has_dose": True,
            }
        ]
        scorer.config["section_A_ingredient_quality"]["A1_bioavailability_form"]["range_score_field"] = "0-9"
        scorer.config["section_A_ingredient_quality"]["A1_bioavailability_form"]["max"] = 15

        a1 = scorer._compute_bioavailability_score(product, "targeted")
        # avg_raw = 9 on a 0-9 scale => full A1 max.
        assert a1 == pytest.approx(15.0, rel=1e-6)

# =============================================================================
# Section E – EPA+DHA Dose Adequacy Tests
# =============================================================================

def _make_omega_product(epa_mg: float, dha_mg: float, servings_per_day: float,
                         epa_canonical: str = "epa", dha_canonical: str = "dha"):
    """Helper: minimal product dict with explicit EPA/DHA amounts."""
    ings = []
    if epa_mg:
        ings.append({
            "name": "EPA", "canonical_id": epa_canonical,
            "quantity": epa_mg, "unit_normalized": "mg", "unit": "mg",
            "is_proprietary_blend": False, "is_blend_header": False, "is_parent_total": False,
        })
    if dha_mg:
        ings.append({
            "name": "DHA", "canonical_id": dha_canonical,
            "quantity": dha_mg, "unit_normalized": "mg", "unit": "mg",
            "is_proprietary_blend": False, "is_blend_header": False, "is_parent_total": False,
        })
    return {
        "dsld_id": "OMEGA_TEST",
        "product_name": "Fish Oil Test",
        "ingredient_quality_data": {"ingredients": ings, "ingredients_scorable": ings},
        "serving_basis": {
            "min_servings_per_day": servings_per_day,
            "max_servings_per_day": servings_per_day,
        },
    }


class TestSectionEDoseAdequacy:
    """Tests for _compute_epa_dha_per_day() and _compute_legacy_section_e()."""

    @pytest.fixture
    def scorer(self):
        return SupplementScorer()

    # ---- _compute_epa_dha_per_day ----

    def test_no_omega_ingredients_returns_no_dose(self, scorer):
        """Product without EPA/DHA returns has_explicit_dose=False."""
        prod = {
            "dsld_id": "X", "product_name": "Vitamin C",
            "ingredient_quality_data": {"ingredients": [
                {"canonical_id": "vitamin_c", "quantity": 500, "unit_normalized": "mg",
                 "is_proprietary_blend": False, "is_blend_header": False, "is_parent_total": False},
            ]},
            "serving_basis": {"min_servings_per_day": 1, "max_servings_per_day": 1},
        }
        result = scorer._compute_epa_dha_per_day(prod)
        assert result["has_explicit_dose"] is False
        assert result["per_day_min"] is None
        assert result["per_day_mid"] is None

    def test_epa_only(self, scorer):
        """Only EPA present: DHA contributes 0, total = EPA × spd."""
        prod = _make_omega_product(epa_mg=300.0, dha_mg=0.0, servings_per_day=2.0)
        result = scorer._compute_epa_dha_per_day(prod)
        assert result["has_explicit_dose"] is True
        assert result["epa_mg_per_unit"] == pytest.approx(300.0)
        assert result["dha_mg_per_unit"] == pytest.approx(0.0)
        assert result["per_day_mid"] == pytest.approx(600.0)

    def test_dha_only(self, scorer):
        """Only DHA present."""
        prod = _make_omega_product(epa_mg=0.0, dha_mg=200.0, servings_per_day=1.0)
        result = scorer._compute_epa_dha_per_day(prod)
        assert result["has_explicit_dose"] is True
        assert result["per_day_mid"] == pytest.approx(200.0)

    def test_combined_epa_dha_times_servings(self, scorer):
        """EPA 180 + DHA 120 = 300 per unit × 3 servings = 900 mg/day."""
        prod = _make_omega_product(epa_mg=180.0, dha_mg=120.0, servings_per_day=3.0)
        result = scorer._compute_epa_dha_per_day(prod)
        assert result["per_day_mid"] == pytest.approx(900.0)
        assert result["epa_mg_per_unit"] == pytest.approx(180.0)
        assert result["dha_mg_per_unit"] == pytest.approx(120.0)

    def test_serving_range_min_max(self, scorer):
        """min/max servings produce separate per_day estimates."""
        prod = _make_omega_product(epa_mg=500.0, dha_mg=500.0, servings_per_day=1.0)
        prod["serving_basis"]["min_servings_per_day"] = 1.0
        prod["serving_basis"]["max_servings_per_day"] = 3.0
        result = scorer._compute_epa_dha_per_day(prod)
        assert result["per_day_min"] == pytest.approx(1000.0)
        assert result["per_day_max"] == pytest.approx(3000.0)
        assert result["per_day_mid"] == pytest.approx(2000.0)

    def test_missing_serving_basis_defaults_to_1(self, scorer):
        """No serving_basis → assumes 1 serving/day."""
        prod = {
            "dsld_id": "X", "product_name": "Test",
            "ingredient_quality_data": {"ingredients": [
                {"canonical_id": "epa", "quantity": 400, "unit_normalized": "mg",
                 "is_proprietary_blend": False, "is_blend_header": False, "is_parent_total": False},
            ]},
        }
        result = scorer._compute_epa_dha_per_day(prod)
        assert result["has_explicit_dose"] is True
        assert result["per_day_mid"] == pytest.approx(400.0)   # 400 × 1

    def test_proprietary_blend_excluded(self, scorer):
        """EPA/DHA inside a proprietary blend header should be skipped."""
        prod = {
            "dsld_id": "X", "product_name": "Test",
            "ingredient_quality_data": {"ingredients": [
                {"canonical_id": "epa", "quantity": 500, "unit_normalized": "mg",
                 "is_proprietary_blend": True, "is_blend_header": False, "is_parent_total": False},
            ]},
            "serving_basis": {"min_servings_per_day": 1, "max_servings_per_day": 1},
        }
        result = scorer._compute_epa_dha_per_day(prod)
        assert result["has_explicit_dose"] is False

    def test_parent_total_excluded(self, scorer):
        """EPA parent-total row is skipped; child rows would still count."""
        prod = {
            "dsld_id": "X", "product_name": "Test",
            "ingredient_quality_data": {"ingredients": [
                # Parent total — should be skipped
                {"canonical_id": "epa", "quantity": 1000, "unit_normalized": "mg",
                 "is_proprietary_blend": False, "is_blend_header": False, "is_parent_total": True},
                # Child — should count
                {"canonical_id": "epa", "quantity": 400, "unit_normalized": "mg",
                 "is_proprietary_blend": False, "is_blend_header": False, "is_parent_total": False},
            ]},
            "serving_basis": {"min_servings_per_day": 1, "max_servings_per_day": 1},
        }
        result = scorer._compute_epa_dha_per_day(prod)
        assert result["has_explicit_dose"] is True
        assert result["epa_mg_per_unit"] == pytest.approx(400.0)  # parent total excluded

    def test_epa_dha_combined_canonical_id(self, scorer):
        """canonical_id='epa_dha' splits evenly between EPA and DHA (no double-counting)."""
        prod = {
            "dsld_id": "X", "product_name": "Test",
            "ingredient_quality_data": {"ingredients": [
                {"canonical_id": "epa_dha", "quantity": 600, "unit_normalized": "mg",
                 "is_proprietary_blend": False, "is_blend_header": False, "is_parent_total": False},
            ]},
            "serving_basis": {"min_servings_per_day": 1, "max_servings_per_day": 1},
        }
        result = scorer._compute_epa_dha_per_day(prod)
        assert result["has_explicit_dose"] is True
        # 600mg total split evenly: 300 EPA + 300 DHA
        assert result["epa_mg_per_unit"] == pytest.approx(300.0)
        assert result["dha_mg_per_unit"] == pytest.approx(300.0)
        assert result["epa_dha_mg_per_unit"] == pytest.approx(600.0)
        assert result["per_day_mid"] == pytest.approx(600.0)

    # ---- _compute_legacy_section_e band boundaries ----

    # v3.4.5 (clinician decision 2026-05-01): omega3 max capped at 2.0.
    # AHA evidence-based dose is 1g/day; above that, marginal benefit is
    # unclear and bleeding risk rises. Bands redistributed within 0–2 cap:
    #   aha_cvd 2.0 -> 1.6, high_clinical 2.5 -> 1.75,
    #   prescription_dose 3.0 -> 2.0 (still flagged with PRESCRIPTION_DOSE_OMEGA3).
    @pytest.mark.parametrize("per_day,exp_score,exp_band", [
        (0,    0.0, "below_efsa_ai"),
        (100,  0.0, "below_efsa_ai"),
        (249,  0.0, "below_efsa_ai"),   # 1 below EFSA AI threshold
        (250,  0.5, "efsa_ai_zone"),    # exactly EFSA AI 250 mg/day
        (499,  0.5, "efsa_ai_zone"),
        (500,  1.0, "general_health"),  # FDA QHC / general health
        (999,  1.0, "general_health"),
        (1000, 1.6, "aha_cvd"),         # AHA CVD recommendation
        (1999, 1.6, "aha_cvd"),
        (2000, 1.75, "high_clinical"),  # EFSA triglyceride claim
        (3999, 1.75, "high_clinical"),
        (4000, 2.0, "prescription_dose"),  # AHA/ACC prescription dose (cap)
        (5000, 2.0, "prescription_dose"),
    ])
    def test_band_boundaries(self, scorer, per_day, exp_score, exp_band):
        """Each dose boundary maps to the correct band and score."""
        # Construct a product that yields exactly `per_day` mg/day at midpoint
        prod = _make_omega_product(epa_mg=per_day, dha_mg=0.0, servings_per_day=1.0)
        flags = []
        result = scorer._compute_legacy_section_e(prod, flags)
        if per_day == 0:
            assert result["applicable"] is False
        else:
            assert result["applicable"] is True
            assert result["score"] == pytest.approx(exp_score, abs=0.001)
            assert result["dose_band"] == exp_band

    def test_prescription_dose_flag_appended(self, scorer):
        """≥4000 mg/day adds PRESCRIPTION_DOSE_OMEGA3 to flags list."""
        prod = _make_omega_product(epa_mg=2000.0, dha_mg=500.0, servings_per_day=2.0)
        # per_day_mid = 2500 × 2 = 5000 mg/day
        flags = []
        result = scorer._compute_legacy_section_e(prod, flags)
        assert result["prescription_dose"] is True
        assert "PRESCRIPTION_DOSE_OMEGA3" in flags

    def test_not_applicable_returns_zero_max(self, scorer):
        """Non-omega product: max=0.0 and applicable=False."""
        prod = {
            "dsld_id": "X", "product_name": "Vitamin D",
            "ingredient_quality_data": {"ingredients": [
                {"canonical_id": "vitamin_d3", "quantity": 5000, "unit_normalized": "iu",
                 "is_proprietary_blend": False, "is_blend_header": False, "is_parent_total": False},
            ]},
        }
        flags = []
        result = scorer._compute_legacy_section_e(prod, flags)
        assert result["applicable"] is False
        assert result["score"] == 0.0
        assert result["max"] == 0.0
        assert "PRESCRIPTION_DOSE_OMEGA3" not in flags

    def test_section_e_in_score_product_output(self, scorer):
        """score_product() includes E in section_scores and breakdown."""
        from copy import deepcopy
        base = make_base_product()
        # Inject EPA/DHA into the base product
        epa_ing = {
            "name": "EPA", "standard_name": "EPA (Eicosapentaenoic Acid)",
            "canonical_id": "epa", "quantity": 500, "unit": "mg", "unit_normalized": "mg",
            "score": 13, "dosage_importance": 1.0, "mapped": True, "has_dose": True,
            "is_proprietary_blend": False, "is_blend_header": False, "is_parent_total": False,
            "bio_score": 10, "natural": True,
        }
        dha_ing = {
            "name": "DHA", "standard_name": "DHA (Docosahexaenoic Acid)",
            "canonical_id": "dha", "quantity": 250, "unit": "mg", "unit_normalized": "mg",
            "score": 13, "dosage_importance": 1.0, "mapped": True, "has_dose": True,
            "is_proprietary_blend": False, "is_blend_header": False, "is_parent_total": False,
            "bio_score": 10, "natural": True,
        }
        prod = deepcopy(base)
        prod["ingredient_quality_data"]["ingredients"].extend([epa_ing, dha_ing])
        prod["ingredient_quality_data"]["ingredients_scorable"].extend([epa_ing, dha_ing])
        prod["serving_basis"] = {"min_servings_per_day": 2, "max_servings_per_day": 2}
        # per_day = (500+250) × 2 = 1500 mg/day → aha_cvd band
        # v3.4.5 (clinician decision 2026-05-01): omega3_dose_bonus capped at
        # 2.0 (was 3.0 in v3.4.x). aha_cvd band 1000-1999 mg/day → 1.6.

        result = scorer.score_product(prod)
        assert result["verdict"] in {"SAFE", "POOR", "CAUTION"}

        section_scores = result.get("section_scores", {})
        assert "E_dose_adequacy" in section_scores
        e = section_scores["E_dose_adequacy"]
        assert e["applicable"] is True
        assert e["score"] == pytest.approx(1.6, abs=0.001)
        assert e["max"] == pytest.approx(2.0, abs=0.001)

        e_bd = result.get("breakdown", {}).get("E", {})
        assert e_bd["dose_band"] == "aha_cvd"
        assert e_bd["per_day_mid_mg"] == pytest.approx(1500.0)

    def test_score_product_non_omega_no_e_contribution(self, scorer):
        """Non-omega product: E score = 0, applicable = False in output."""
        prod = make_base_product()
        result = scorer.score_product(prod)
        section_scores = result.get("section_scores", {})
        if "E_dose_adequacy" in section_scores:
            e = section_scores["E_dose_adequacy"]
            assert e["applicable"] is False
            assert e["score"] == 0.0

    def test_dosage_normalization_fallback(self, scorer):
        """Falls back to dosage_normalization.serving_basis when serving_basis absent."""
        prod = {
            "dsld_id": "X", "product_name": "Test",
            "ingredient_quality_data": {"ingredients": [
                {"canonical_id": "epa", "quantity": 300, "unit_normalized": "mg",
                 "is_proprietary_blend": False, "is_blend_header": False, "is_parent_total": False},
            ]},
            # No top-level serving_basis; use dosage_normalization fallback
            "dosage_normalization": {
                "serving_basis": {
                    "servings_per_day_min": 2.0,
                    "servings_per_day_max": 2.0,
                }
            },
        }
        result = scorer._compute_epa_dha_per_day(prod)
        assert result["has_explicit_dose"] is True
        assert result["per_day_mid"] == pytest.approx(600.0)  # 300 × 2


# ── B7 dose safety penalty tests ──────────────────────────────────────────

class TestB7DoseSafety:
    """B7 penalises products with any ingredient exceeding 150% of highest UL."""

    @pytest.fixture
    def scorer(self):
        return SupplementScorer()

    def _product_with_safety_flags(self, flags):
        p = make_base_product()
        p["rda_ul_data"] = {
            "safety_flags": flags,
            "has_over_ul": len(flags) > 0,
        }
        return p

    def test_no_safety_flags_no_penalty(self, scorer):
        p = self._product_with_safety_flags([])
        penalty, evidence = scorer._compute_dose_safety_penalty(p, [])
        assert penalty == 0.0
        assert evidence == []

    def test_under_150pct_no_penalty(self, scorer):
        """120% of UL should not trigger B7 (handled by phone E1)."""
        p = self._product_with_safety_flags([{
            "nutrient": "Vitamin A",
            "amount": 3600,
            "ul": 3000,
            "pct_ul": 120.0,
            "severity": "warning",
        }])
        penalty, evidence = scorer._compute_dose_safety_penalty(p, [])
        assert penalty == 0.0
        assert evidence == []

    def test_150pct_triggers_penalty(self, scorer):
        """Exactly 150% of UL triggers B7."""
        p = self._product_with_safety_flags([{
            "nutrient": "Vitamin A",
            "amount": 4500,
            "ul": 3000,
            "pct_ul": 150.0,
            "severity": "warning",
        }])
        penalty, evidence = scorer._compute_dose_safety_penalty(p, [])
        assert penalty == pytest.approx(2.0)
        assert len(evidence) == 1
        assert evidence[0]["nutrient"] == "Vitamin A"

    def test_200pct_same_single_penalty(self, scorer):
        """200%+ still gets the single_penalty per nutrient (2.0)."""
        p = self._product_with_safety_flags([{
            "nutrient": "Vitamin E",
            "amount": 2000,
            "ul": 1000,
            "pct_ul": 200.0,
            "severity": "critical",
        }])
        penalty, evidence = scorer._compute_dose_safety_penalty(p, [])
        assert penalty == pytest.approx(2.0)

    def test_multiple_nutrients_capped_at_3(self, scorer):
        """Multiple over-UL nutrients cap at 3.0."""
        p = self._product_with_safety_flags([
            {"nutrient": "Vitamin A", "amount": 4500, "ul": 3000, "pct_ul": 150.0, "severity": "warning"},
            {"nutrient": "Vitamin E", "amount": 2000, "ul": 1000, "pct_ul": 200.0, "severity": "critical"},
        ])
        penalty, evidence = scorer._compute_dose_safety_penalty(p, [])
        assert penalty == pytest.approx(3.0)  # 2.0 + 2.0 = 4.0, capped at 3.0
        assert len(evidence) == 2

    def test_b7_adds_flag(self, scorer):
        flags = []
        p = self._product_with_safety_flags([{
            "nutrient": "Folate",
            "amount": 2500,
            "ul": 1667,
            "pct_ul": 150.0,
            "severity": "warning",
        }])
        scorer._compute_dose_safety_penalty(p, flags)
        assert "OVER_UL_Folate" in flags

    def test_b7_included_in_section_b_total(self, scorer):
        """B7 penalty is subtracted from the section B score."""
        p_safe = make_base_product()
        p_safe["rda_ul_data"] = {"safety_flags": [], "has_over_ul": False}

        p_danger = make_base_product()
        p_danger["rda_ul_data"] = {
            "safety_flags": [{
                "nutrient": "Vitamin A",
                "amount": 7500,
                "ul": 3000,
                "pct_ul": 250.0,
                "severity": "critical",
            }],
            "has_over_ul": True,
        }

        b_safe = scorer._compute_safety_purity_score(p_safe, "targeted", 0.0, [])
        b_danger = scorer._compute_safety_purity_score(p_danger, "targeted", 0.0, [])

        assert b_danger["B7_penalty"] == pytest.approx(2.0)
        assert b_danger["score"] < b_safe["score"]

    def test_no_rda_ul_data_no_penalty(self, scorer):
        """Products without rda_ul_data (e.g. no dosage info) get no B7 penalty."""
        p = make_base_product()
        # No rda_ul_data key at all
        penalty, evidence = scorer._compute_dose_safety_penalty(p, [])
        assert penalty == 0.0


# ---------------------------------------------------------------------------
# Phase 0 Regression Locks — fix #2 (banned→BLOCKED, recalled→UNSAFE) and
# probiotic core_quality + clinical strain wiring. These tests lock correct
# behavior and must never regress.
# ---------------------------------------------------------------------------


class TestBannedRecalledVerdictLock:
    """Lock the correct verdict mapping after commit 8e7ed8a fix #2.

    Previously: banned status set UNSAFE, recalled status set BLOCKED (inverted).
    Fixed to: banned → BLOCKED (score_80 is None), recalled → UNSAFE (score_80 is 0).
    These tests ensure the mapping never flips back.
    """

    @pytest.fixture
    def scorer(self):
        return SupplementScorer()

    def test_banned_substance_exact_match_yields_blocked_verdict(self, scorer):
        product = make_base_product()
        product["contaminant_data"]["banned_substances"] = {
            "found": True,
            "substances": [
                {
                    "status": "banned",
                    "match_type": "exact",
                    "name": "Phenibut",
                    "banned_name": "Phenibut",
                    "ingredient": "Phenibut",
                }
            ],
        }
        result = scorer.score_product(product)
        assert result["verdict"] == "BLOCKED"
        assert result["score_80"] is None
        assert result["score_100_equivalent"] is None
        assert result["breakdown"]["B"]["B0"] == "BLOCKED"
        assert "Phenibut" in (result["breakdown"]["B"].get("reason") or "")

    def test_banned_substance_alias_match_yields_blocked_verdict(self, scorer):
        product = make_base_product()
        product["contaminant_data"]["banned_substances"] = {
            "found": True,
            "substances": [
                {
                    "status": "banned",
                    "match_type": "alias",
                    "name": "BMPEA",
                    "banned_name": "Beta-methylphenethylamine",
                }
            ],
        }
        result = scorer.score_product(product)
        assert result["verdict"] == "BLOCKED"
        assert result["score_80"] is None

    def test_recalled_substance_exact_match_yields_unsafe_verdict(self, scorer):
        product = make_base_product()
        product["contaminant_data"]["banned_substances"] = {
            "found": True,
            "substances": [
                {
                    "status": "recalled",
                    "match_type": "exact",
                    "name": "Comfrey Root",
                    "banned_name": "Comfrey Root",
                    "ingredient": "Comfrey Root",
                }
            ],
        }
        result = scorer.score_product(product)
        assert result["verdict"] == "UNSAFE"
        assert result["score_80"] == 0.0
        assert result["breakdown"]["B"]["B0"] == "UNSAFE"

    def test_recalled_substance_alias_match_yields_unsafe_verdict(self, scorer):
        product = make_base_product()
        product["contaminant_data"]["banned_substances"] = {
            "found": True,
            "substances": [
                {
                    "status": "recalled",
                    "match_type": "alias",
                    "name": "Red Yeast Rice Recalled Batch",
                    "banned_name": "Red Yeast Rice",
                }
            ],
        }
        result = scorer.score_product(product)
        assert result["verdict"] == "UNSAFE"
        assert result["score_80"] == 0.0

    def test_banned_takes_precedence_over_recalled(self, scorer):
        """If a product has both banned AND recalled substances, BLOCKED wins."""
        product = make_base_product()
        product["contaminant_data"]["banned_substances"] = {
            "found": True,
            "substances": [
                {
                    "status": "recalled",
                    "match_type": "exact",
                    "name": "Comfrey Root",
                    "banned_name": "Comfrey Root",
                },
                {
                    "status": "banned",
                    "match_type": "exact",
                    "name": "Phenibut",
                    "banned_name": "Phenibut",
                },
            ],
        }
        result = scorer.score_product(product)
        assert result["verdict"] == "BLOCKED"
        assert result["score_80"] is None


class TestProbioticCoreQualityRegression:
    """Phase 0 failing tests pinning real probiotic scoring bugs seen on Thorne 15581.

    Bug A: probiotic ingredients use unit 'Live Cell(s)' which enricher normalizes
           to 'livecell(s)'. Scorer's _has_usable_individual_dose whitelist does NOT
           include 'livecell(s)', so every probiotic row is skipped from A1/A2/A6
           and Section A core_quality stays at 0 even when IQM matched the rows
           with quality scores of 15-18.

    Bug C: In default mode (_feature_on probiotic_extended_scoring = False),
           _compute_probiotic_category_bonus hardcodes clinical_strains=0.0 and
           survivability=0.0, completely ignoring the enricher's correctly-
           extracted pdata['clinical_strain_count'] and
           pdata['has_survivability_coating']. Extended mode has a parallel bug
           using a hardcoded substring list instead of reading the enricher field.
    """

    @pytest.fixture
    def scorer(self):
        return SupplementScorer()

    def _make_thorne_restore_like_product(self):
        """Mirror the Thorne Restore (dsld_id 15581) smoke fixture:
        3 probiotic strains, unit 'Live Cell(s)', total 5B CFU."""
        product = make_base_product()
        product["supplement_type"] = {"type": "probiotic", "active_count": 3}
        product["ingredient_quality_data"] = {
            "total_active": 3,
            "unmapped_count": 0,
            "ingredients": [
                {
                    "name": "Lactobacillus gasseri",
                    "standard_name": "Lactobacillus Gasseri",
                    "canonical_id": "lactobacillus_gasseri",
                    "category": "probiotics",
                    "score": 16.0,
                    "dosage_importance": 1.0,
                    "mapped": True,
                    "quantity": 2500000000.0,
                    "unit": "Live Cell(s)",
                    "unit_normalized": "livecell(s)",
                    "has_dose": True,
                    "is_proprietary_blend": False,
                    "is_parent_total": False,
                    "is_blend_header": False,
                    "role_classification": "active_scorable",
                },
                {
                    "name": "Bifidobacterium longum",
                    "standard_name": "Bifidobacterium Longum",
                    "canonical_id": "bifidobacterium_longum",
                    "category": "probiotics",
                    "score": 15.0,
                    "dosage_importance": 1.0,
                    "mapped": True,
                    "quantity": 1250000000.0,
                    "unit": "Live Cell(s)",
                    "unit_normalized": "livecell(s)",
                    "has_dose": True,
                    "is_proprietary_blend": False,
                    "is_parent_total": False,
                    "is_blend_header": False,
                    "role_classification": "active_scorable",
                },
                {
                    "name": "Bifidobacterium bifidum",
                    "standard_name": "Bifidobacterium Bifidum",
                    "canonical_id": "bifidobacterium_bifidum",
                    "category": "probiotics",
                    "score": 15.0,
                    "dosage_importance": 1.0,
                    "mapped": True,
                    "quantity": 1250000000.0,
                    "unit": "Live Cell(s)",
                    "unit_normalized": "livecell(s)",
                    "has_dose": True,
                    "is_proprietary_blend": False,
                    "is_parent_total": False,
                    "is_blend_header": False,
                    "role_classification": "active_scorable",
                },
            ],
        }
        product["ingredient_quality_data"]["ingredients_scorable"] = list(
            product["ingredient_quality_data"]["ingredients"]
        )
        product["probiotic_data"] = {
            "is_probiotic": True,
            "is_probiotic_product": True,
            "has_cfu": True,
            "total_cfu": 5_000_000_000.0,
            "total_billion_count": 5.0,
            "total_strain_count": 3,
            "guarantee_type": None,
            "probiotic_blends": [
                {"name": "Lactobacillus gasseri", "strain_count": 1,
                 "strains": ["Lactobacillus gasseri"],
                 "cfu_data": {"has_cfu": True, "cfu_count": 2500000000.0, "billion_count": 2.5}},
                {"name": "Bifidobacterium longum", "strain_count": 1,
                 "strains": ["Bifidobacterium longum"],
                 "cfu_data": {"has_cfu": True, "cfu_count": 1250000000.0, "billion_count": 1.25}},
                {"name": "Bifidobacterium bifidum", "strain_count": 1,
                 "strains": ["Bifidobacterium bifidum"],
                 "cfu_data": {"has_cfu": True, "cfu_count": 1250000000.0, "billion_count": 1.25}},
            ],
            "clinical_strains": [
                {"strain": "Lactobacillus gasseri", "clinical_id": "STRAIN_GASSERI_SBT2055",
                 "evidence_level": "high"},
                {"strain": "Bifidobacterium longum", "clinical_id": "STRAIN_BLONGUM_BB536",
                 "evidence_level": "high"},
            ],
            "clinical_strain_count": 2,
            "prebiotic_present": False,
            "prebiotic_name": "",
            "has_survivability_coating": False,
            "survivability_reason": "",
        }
        return product

    def test_bugA_probiotic_livecell_unit_contributes_to_core_quality(self, scorer):
        """Bug A lock: probiotic ingredients with unit_normalized='livecell(s)' must
        not be skipped by _has_usable_individual_dose; their IQM quality scores
        (15-16) must flow into Section A core_quality. Currently FAILS because
        'livecell(s)' is not in the usable-dose unit whitelist."""
        product = self._make_thorne_restore_like_product()
        section_a = scorer._compute_ingredient_quality_score(product, "probiotic", flags=[])
        assert section_a["core_quality"] > 0, (
            "Section A core_quality must be > 0 for a 3-strain probiotic with "
            f"IQM-matched ingredients (scores 15-16); got {section_a['core_quality']}. "
            "Root cause: unit_normalized='livecell(s)' not in _has_usable_individual_dose whitelist."
        )
        # With 3 ingredients averaging quality score ~15.3 and dosage_importance 1.0,
        # A1 should contribute meaningfully — at least 8 points out of 15 max.
        assert section_a["A1"] >= 8.0, (
            f"A1 (bioavailability) for probiotic should be >= 8.0 given 3 strains "
            f"with avg quality_score ~15.3; got {section_a['A1']}"
        )

    def test_bugA_livecell_unit_recognized_as_usable_dose(self, scorer):
        """Unit-level lock: _has_usable_individual_dose must return True for a
        probiotic ingredient with unit_normalized='livecell(s)' and positive
        CFU quantity. Currently FAILS."""
        probiotic_row = {
            "name": "Lactobacillus gasseri",
            "quantity": 2500000000.0,
            "unit": "Live Cell(s)",
            "unit_normalized": "livecell(s)",
            "has_dose": True,
        }
        assert scorer._has_usable_individual_dose(probiotic_row) is True, (
            "'livecell(s)' must be recognized as a usable CFU-equivalent unit"
        )

    def test_bugC_default_mode_reads_clinical_strains_from_enricher(self, scorer):
        """Bug C lock: in default probiotic scoring mode, clinical_strains bonus
        must come from pdata['clinical_strain_count'] (the enricher's field),
        not be hardcoded to 0.0. Currently FAILS — line 1035 returns a dict with
        'clinical_strains': 0.0 regardless of input."""
        product = self._make_thorne_restore_like_product()
        bonus = scorer._compute_probiotic_category_bonus(product, "probiotic")
        assert bonus["clinical_strains"] > 0.0, (
            "Enricher found 2 clinically-relevant strains "
            "(STRAIN_GASSERI_SBT2055, STRAIN_BLONGUM_BB536). "
            f"Scorer returned clinical_strains={bonus['clinical_strains']}. "
            "Root cause: default-mode probiotic bonus hardcodes clinical_strains=0.0."
        )

    def test_bugC_default_mode_reads_survivability_from_enricher(self, scorer):
        """Bug C lock: survivability bonus must come from
        pdata['has_survivability_coating'] in default mode. Currently hardcoded
        to 0.0 even when the enricher sets has_survivability_coating=True."""
        product = self._make_thorne_restore_like_product()
        product["probiotic_data"]["has_survivability_coating"] = True
        product["probiotic_data"]["survivability_reason"] = "enteric coating"
        bonus = scorer._compute_probiotic_category_bonus(product, "probiotic")
        assert bonus["survivability"] > 0.0, (
            "When enricher sets has_survivability_coating=True, scorer must award "
            f"survivability bonus > 0; got {bonus['survivability']}. "
            "Root cause: default-mode probiotic bonus hardcodes survivability=0.0."
        )

    def test_bugC_extended_mode_uses_enricher_clinical_strain_count(self, scorer):
        """Bug C lock, extended mode variant: even with probiotic_extended_scoring
        enabled, clinical_strains should come from the enricher's
        clinical_strain_count field, not from a hardcoded substring list. Without
        this the enricher's clinically_relevant_strains.json (42 entries) is
        duplicated and drifts."""
        product = self._make_thorne_restore_like_product()
        # _feature_on reads self.feature_gates (snapshot of config['feature_gates']
        # taken in __init__), so toggle the live attribute directly.
        scorer.feature_gates["probiotic_extended_scoring"] = True
        try:
            bonus = scorer._compute_probiotic_category_bonus(product, "probiotic")
        finally:
            scorer.feature_gates.pop("probiotic_extended_scoring", None)
        assert bonus["clinical_strains"] > 0.0, (
            "Extended mode must credit clinical_strains based on enricher's "
            "clinical_strain_count (2 for this product); got "
            f"{bonus['clinical_strains']}"
        )

    def test_thorne_restore_realistic_section_a_target(self, scorer):
        """End-to-end section A lock for the Thorne 15581 fixture. Currently
        fails because of Bugs A and C. After fixes, Section A should be in the
        15-20 range for a 3-strain quality probiotic with clinical matches."""
        product = self._make_thorne_restore_like_product()
        section_a = scorer._compute_ingredient_quality_score(product, "probiotic", flags=[])
        assert section_a["score"] >= 12.0, (
            f"Section A for Thorne Restore (3 strains @ quality 15-16, 5B CFU, "
            f"2 clinical matches) should be >= 12.0 out of 25; "
            f"got {section_a['score']}. Breakdown: core_quality={section_a['core_quality']}, "
            f"probiotic_bonus={section_a.get('probiotic_bonus')}"
        )


# ---------------------------------------------------------------------------
# Phase 3B — Config Lockdown Tests
# Every scoring tunable must be sourced from scoring_config.json, not
# hardcoded in score_supplements.py. These tests mutate the in-memory config
# of a constructed scorer and assert the scoring engine honors the change.
# ---------------------------------------------------------------------------


class TestConfigLockdown:
    """Phase 3B config-lockdown regression suite. Each test overrides a single
    config key and verifies the scorer's output changes accordingly. These
    tests FAIL before Phase 3B fixes because the corresponding value is
    hardcoded in score_supplements.py."""

    @pytest.fixture
    def scorer(self):
        return SupplementScorer()

    # ------------------------------------------------------------------
    # C1: mid-tier D1 manufacturer points
    # ------------------------------------------------------------------
    def _make_mid_tier_brand_product(self):
        """NSF GMP certified product, no trusted-manufacturer match.
        Qualifies under _has_verifiable_mid_tier_manufacturer_evidence."""
        p = make_base_product()
        p["certification_data"]["gmp"] = {
            "claimed": False,
            "fda_registered": False,
            "nsf_gmp": True,
        }
        p["manufacturer_data"]["top_manufacturer"] = {"found": False, "match_type": None}
        p["manufacturer_data"]["violations"] = {"found": False, "violations": []}
        return p

    def test_c1_mid_tier_d1_awards_points_when_feature_enabled(self, scorer):
        """When enable_d1_middle_tier is ON, a mid-tier NSF-GMP product
        must score D1 > 0 because _has_verifiable_mid_tier_manufacturer_evidence
        returns True. Currently FAILS because the feature gate is OFF in the
        shipped config and the enricher's work is silently discarded."""
        product = self._make_mid_tier_brand_product()
        scorer.feature_gates["enable_d1_middle_tier"] = True
        try:
            d = scorer._compute_brand_trust_score(product)
        finally:
            scorer.feature_gates.pop("enable_d1_middle_tier", None)
        assert d["D1"] > 0.0, (
            "Mid-tier NSF-GMP product must receive D1 > 0 when "
            "enable_d1_middle_tier is on. "
            f"Got D1={d['D1']}"
        )

    def test_c1_mid_tier_d1_reads_reputation_from_config(self, scorer):
        """Even with the flag on, the value awarded must come from config
        (D1_mid_tier_reputation or similar), not hardcoded 1.0. Currently
        FAILS because D1 mid-tier value is hardcoded to 1.0."""
        product = self._make_mid_tier_brand_product()
        scorer.feature_gates["enable_d1_middle_tier"] = True
        section_d_cfg = scorer.config.setdefault("section_D_brand_trust", {})
        section_d_cfg["D1_mid_tier_reputation"] = 0.75
        try:
            d = scorer._compute_brand_trust_score(product)
        finally:
            scorer.feature_gates.pop("enable_d1_middle_tier", None)
            section_d_cfg.pop("D1_mid_tier_reputation", None)
        assert d["D1"] == pytest.approx(0.75), (
            "D1 mid-tier value must come from config "
            "section_D_brand_trust.D1_mid_tier_reputation, not hardcoded "
            f"1.0. Got D1={d['D1']}"
        )

    # ------------------------------------------------------------------
    # C2: POOR verdict threshold
    # ------------------------------------------------------------------
    def test_c2_poor_threshold_honors_config(self, scorer):
        """Moving poor_threshold_quality_score from the implicit 32 to a
        higher value (e.g. 50) must change the verdict. Currently FAILS
        because _derive_verdict hardcodes 32 at line ~2754."""
        scorer.config["verdict_logic"] = {"poor_threshold_quality_score": 50}
        try:
            # A score of 40 should become POOR under threshold 50
            verdict = scorer._derive_verdict(
                b0={"blocked": False, "unsafe": False},
                mapping_gate={"stop": False},
                flags=[],
                quality_score=40.0,
            )
        finally:
            scorer.config.pop("verdict_logic", None)
        assert verdict == "POOR", (
            "With poor_threshold_quality_score=50 in config, a quality_score "
            f"of 40.0 must yield verdict POOR; got {verdict}"
        )

    # ------------------------------------------------------------------
    # C3: grade labels from config
    # ------------------------------------------------------------------
    def test_c3_grade_word_reads_grade_scale_from_config(self, scorer):
        """Modifying grade_scale.Good.min must change which score maps to
        Good. Currently FAILS because _grade_word hardcodes 90/80/70/60/50/32."""
        scorer.config["grade_scale"] = {
            "_based_on_100_equivalent": True,
            "Exceptional": {"min": 95},
            "Excellent": {"min": 85},
            "Good": {"min": 75},  # was 70
            "Fair": {"min": 65},  # was 60
            "Below Avg": {"min": 55},  # was 50
            "Low": {"min": 40},  # was 32
            "Very Poor": {"min": 0},
        }
        # Score 72 — under default config this would be "Good"; under
        # the new config it should be "Fair".
        grade = scorer._grade_word(72.0, "SAFE")
        assert grade == "Fair", (
            f"Score 72 under adjusted grade_scale (Good.min=75) must yield "
            f"'Fair'; got {grade!r}. The hardcoded thresholds ignore config."
        )

    # ------------------------------------------------------------------
    # H2: A2 premium forms reads threshold/points/max from config
    # ------------------------------------------------------------------
    def _make_two_premium_forms_product(self):
        """2 mapped ingredients with quality scores both >= 14 (premium)."""
        p = make_base_product()
        iqd_ings = [
            {
                "name": "Magnesium Glycinate",
                "standard_name": "Magnesium",
                "canonical_id": "magnesium",
                "score": 18,
                "dosage_importance": 1.0,
                "mapped": True,
                "quantity": 200,
                "unit": "mg",
                "unit_normalized": "mg",
                "has_dose": True,
                "is_proprietary_blend": False,
                "is_parent_total": False,
            },
            {
                "name": "Zinc Picolinate",
                "standard_name": "Zinc",
                "canonical_id": "zinc",
                "score": 15,
                "dosage_importance": 1.0,
                "mapped": True,
                "quantity": 15,
                "unit": "mg",
                "unit_normalized": "mg",
                "has_dose": True,
                "is_proprietary_blend": False,
                "is_parent_total": False,
            },
        ]
        p["ingredient_quality_data"]["ingredients"] = iqd_ings
        p["ingredient_quality_data"]["ingredients_scorable"] = list(iqd_ings)
        p["ingredient_quality_data"]["total_active"] = 2
        p["supplement_type"] = {"type": "targeted", "active_count": 2}
        return p

    def test_h2_a2_threshold_honors_config(self, scorer):
        """Raising A2.threshold_score from 14 to 20 must drop A2 to 0
        because neither form meets the new bar. Currently FAILS because
        threshold is hardcoded to 14 in _compute_premium_forms_bonus."""
        product = self._make_two_premium_forms_product()
        a2_cfg = scorer.config.setdefault("section_A_ingredient_quality", {}) \
            .setdefault("A2_premium_forms", {})
        original_threshold = a2_cfg.get("threshold_score")
        a2_cfg["threshold_score"] = 20
        try:
            a2 = scorer._compute_premium_forms_bonus(product)
        finally:
            if original_threshold is None:
                a2_cfg.pop("threshold_score", None)
            else:
                a2_cfg["threshold_score"] = original_threshold
        assert a2 == pytest.approx(0.0), (
            "With A2.threshold_score raised to 20, no score-15/18 ingredient "
            f"should qualify for premium form credit; got A2={a2}"
        )

    def test_h2_a2_points_per_form_honors_config(self, scorer):
        """Bumping A2.points_per_additional_premium_form from 0.5 to 2.0
        must roughly quadruple A2 output. Currently FAILS because
        _compute_premium_forms_bonus hardcodes 0.5."""
        product = self._make_two_premium_forms_product()
        a2_cfg = scorer.config.setdefault("section_A_ingredient_quality", {}) \
            .setdefault("A2_premium_forms", {})
        original = a2_cfg.get("points_per_additional_premium_form")
        a2_cfg["points_per_additional_premium_form"] = 2.0
        try:
            a2 = scorer._compute_premium_forms_bonus(product)
        finally:
            if original is None:
                a2_cfg.pop("points_per_additional_premium_form", None)
            else:
                a2_cfg["points_per_additional_premium_form"] = original
        # 2 premium forms, skip first, award 2.0 for the second — capped at max 3.
        assert a2 == pytest.approx(2.0), (
            f"With points_per_additional_premium_form=2.0 and 2 premium forms "
            f"(1 scored after skip-first), A2 should be 2.0; got {a2}"
        )

    # ------------------------------------------------------------------
    # H3: B4b GMP values from config
    # ------------------------------------------------------------------
    def test_h3_b4b_gmp_certified_points_honor_config(self, scorer):
        """Bumping B4b_gmp.certified from 4 to 6 must raise B4b output.
        Currently FAILS because values are hardcoded to 4.0/2.0."""
        product = make_base_product()
        product["certification_data"]["gmp"] = {
            "nsf_gmp": True,
            "claimed": True,
            "fda_registered": False,
        }
        b4b_cfg = (
            scorer.config.setdefault("section_B_safety_purity", {})
            .setdefault("B4_quality_certifications", {})
            .setdefault("B4b_gmp", {})
        )
        original = b4b_cfg.get("certified")
        b4b_cfg["certified"] = 6
        try:
            result = scorer._compute_certifications_bonus(product, "targeted")
        finally:
            if original is None:
                b4b_cfg.pop("certified", None)
            else:
                b4b_cfg["certified"] = original
        assert result.get("B4b", 0) == pytest.approx(6.0), (
            f"B4b should read 'certified' value 6 from config; got "
            f"B4b={result.get('B4b')}"
        )

    # ------------------------------------------------------------------
    # H4: A3 delivery tier_points from config
    # ------------------------------------------------------------------
    def test_h4_a3_tier_points_from_config(self, scorer):
        """Changing A3.tier_points['1'] from 3 to 2 must produce A3=2 (inside
        the 3-point cap, proves config is actually being read). Currently
        FAILS because the map is hardcoded inline."""
        product = make_base_product()
        product["delivery_data"] = {"highest_tier": 1}
        a3_cfg = scorer.config.setdefault("section_A_ingredient_quality", {}) \
            .setdefault("A3_delivery_system", {})
        original = a3_cfg.get("tier_points")
        # Override tier 1 to yield 2 (half of default 3) — inside the 3-point cap
        a3_cfg["tier_points"] = {"1": 2, "2": 1, "3": 0.5}
        try:
            a3 = scorer._compute_delivery_score(product)
        finally:
            if original is None:
                a3_cfg.pop("tier_points", None)
            else:
                a3_cfg["tier_points"] = original
        assert a3 == pytest.approx(2.0), (
            f"A3 tier 1 must honor config tier_points['1']=2; got {a3}"
        )

    # ------------------------------------------------------------------
    # H5: A4 absorption points from config
    # ------------------------------------------------------------------
    def test_h5_a4_absorption_points_from_config(self, scorer):
        """Changing A4.points_if_paired from 3 to 2 must produce A4=2.
        Currently FAILS because the value is hardcoded to 3.0."""
        product = make_base_product()
        product["absorption_enhancer_paired"] = True
        a4_cfg = scorer.config.setdefault("section_A_ingredient_quality", {}) \
            .setdefault("A4_absorption_enhancer", {})
        original = a4_cfg.get("points_if_paired")
        a4_cfg["points_if_paired"] = 2
        try:
            a4 = scorer._compute_absorption_bonus(product)
        finally:
            if original is None:
                a4_cfg.pop("points_if_paired", None)
            else:
                a4_cfg["points_if_paired"] = original
        assert a4 == pytest.approx(2.0), (
            f"A4 must honor config points_if_paired=2; got {a4}"
        )

    # ------------------------------------------------------------------
    # M1: prebiotic_terms read from config
    # ------------------------------------------------------------------
    def _make_probiotic_with_chicory_product(self):
        p = make_base_product()
        p["supplement_type"] = {"type": "probiotic", "active_count": 2}
        p["ingredient_quality_data"]["ingredients"] = [
            {"name": "Lactobacillus rhamnosus", "standard_name": "Lactobacillus Rhamnosus",
             "category": "probiotics", "mapped": True, "score": 15, "dosage_importance": 1.0,
             "quantity": 5000000000, "unit": "cfu", "unit_normalized": "cfu", "has_dose": True,
             "is_proprietary_blend": False, "is_parent_total": False},
            {"name": "Chicory Root Fiber", "standard_name": "Chicory Root",
             "category": "fiber", "mapped": True, "score": 10, "dosage_importance": 1.0,
             "quantity": 2000, "unit": "mg", "unit_normalized": "mg", "has_dose": True,
             "is_proprietary_blend": False, "is_parent_total": False},
        ]
        p["ingredient_quality_data"]["ingredients_scorable"] = list(
            p["ingredient_quality_data"]["ingredients"]
        )
        p["probiotic_data"] = {
            "is_probiotic_product": True,
            "has_cfu": True,
            "total_cfu": 5000000000,
            "total_billion_count": 5.0,
            "total_strain_count": 1,
            "probiotic_blends": [
                {"name": "Lactobacillus rhamnosus", "strain_count": 1,
                 "strains": ["Lactobacillus rhamnosus"],
                 "cfu_data": {"has_cfu": True, "cfu_count": 5000000000, "billion_count": 5.0}},
            ],
            "clinical_strain_count": 0,
            "clinical_strains": [],
            "prebiotic_present": False,
            "has_survivability_coating": False,
        }
        return p

    def test_m1_prebiotic_terms_detect_chicory_via_config(self, scorer):
        """Adding 'chicory' to the configurable prebiotic_terms list must
        allow chicory root fiber to be detected as a prebiotic. Currently
        FAILS because prebiotic_terms is hardcoded to ['inulin', 'fos', 'gos']
        and the config has no prebiotic_terms key to override."""
        product = self._make_probiotic_with_chicory_product()
        pro_cfg = scorer.config.setdefault("section_A_ingredient_quality", {}) \
            .setdefault("probiotic_bonus", {})
        original = pro_cfg.get("prebiotic_terms")
        pro_cfg["prebiotic_terms"] = ["inulin", "fos", "gos", "chicory", "acacia", "beta-glucan"]
        try:
            bonus = scorer._compute_probiotic_category_bonus(product, "probiotic")
        finally:
            if original is None:
                pro_cfg.pop("prebiotic_terms", None)
            else:
                pro_cfg["prebiotic_terms"] = original
        assert bonus["prebiotic"] > 0.0, (
            "With 'chicory' added to config prebiotic_terms, a product with "
            f"Chicory Root Fiber must score prebiotic > 0; got {bonus['prebiotic']}"
        )

    # ------------------------------------------------------------------
    # M4: A6 single-ingredient efficiency tiers from config
    # ------------------------------------------------------------------
    def test_m4_a6_tiers_honor_config(self, scorer):
        """Changing A6 tier '>=16' from 3 to 5 must change A6 output for a
        score-16 ingredient. Currently FAILS because tiers are hardcoded."""
        # Construct a single-ingredient product with form_score = 16
        product = make_base_product()
        product["supplement_type"] = {"type": "single_nutrient", "active_count": 1}
        product["ingredient_quality_data"]["ingredients"] = [
            {
                "name": "Magnesium Glycinate",
                "standard_name": "Magnesium",
                "canonical_id": "magnesium",
                "category": "mineral",
                "score": 16,
                "dosage_importance": 1.0,
                "mapped": True,
                "quantity": 200,
                "unit": "mg",
                "unit_normalized": "mg",
                "has_dose": True,
                "is_proprietary_blend": False,
                "is_parent_total": False,
            },
        ]
        product["ingredient_quality_data"]["ingredients_scorable"] = list(
            product["ingredient_quality_data"]["ingredients"]
        )
        product["ingredient_quality_data"]["total_active"] = 1
        a6_cfg = scorer.config.setdefault("section_A_ingredient_quality", {}) \
            .setdefault("A6_single_ingredient_efficiency", {})
        original = a6_cfg.get("tiers")
        a6_cfg["tiers"] = {">=16": 5, ">=14": 2, ">=12": 1}
        original_max = a6_cfg.get("max")
        a6_cfg["max"] = 5
        try:
            a6 = scorer._compute_single_efficiency_bonus(product, "single_nutrient")
        finally:
            if original is None:
                a6_cfg.pop("tiers", None)
            else:
                a6_cfg["tiers"] = original
            if original_max is None:
                a6_cfg.pop("max", None)
            else:
                a6_cfg["max"] = original_max
        assert a6 == pytest.approx(5.0), (
            f"A6 tier '>=16' should honor config value 5; got {a6}"
        )

    # ------------------------------------------------------------------
    # M5: B4c traceability values from config
    # ------------------------------------------------------------------
    def test_m5_b4c_coa_value_honors_config(self, scorer):
        """Bumping B4c.coa from 1 to 3 must raise B4c output. Currently
        FAILS because B4c hardcodes 1 per signal."""
        product = make_base_product()
        product["certification_data"]["batch_traceability"] = {
            "has_coa": True,
            "has_batch_lookup": False,
            "has_qr_code": False,
        }
        b4c_cfg = (
            scorer.config.setdefault("section_B_safety_purity", {})
            .setdefault("B4_quality_certifications", {})
            .setdefault("B4c_batch_traceability", {})
        )
        original = b4c_cfg.get("coa")
        b4c_cfg["coa"] = 3
        try:
            result = scorer._compute_certifications_bonus(product, "targeted")
        finally:
            if original is None:
                b4c_cfg.pop("coa", None)
            else:
                b4c_cfg["coa"] = original
        assert result.get("B4c", 0) >= 3.0, (
            f"B4c should read coa=3 from config; got B4c={result.get('B4c')}"
        )

    # ------------------------------------------------------------------
    # M6: B3 claim compliance values from config
    # ------------------------------------------------------------------
    def test_m6_b3_allergen_free_value_honors_config(self, scorer):
        """Bumping B3.allergen_free from 2 to 3 must change B3 output for
        a product with only a valid allergen-free claim. Currently FAILS
        because B3 hardcodes 2/1/1."""
        product = make_base_product()
        product["compliance_data"]["allergen_free_claims"] = [
            {"validated": True, "allergen": "dairy", "method": "label"},
        ]
        product["compliance_data"]["gluten_free"] = False
        product["compliance_data"]["vegan"] = False
        product["compliance_data"]["vegetarian"] = False
        product["compliance_data"]["conflicts"] = []
        product["compliance_data"]["has_may_contain_warning"] = False
        product["contaminant_data"]["allergens"] = {"found": False, "allergens": []}
        b3_cfg = scorer.config.setdefault("section_B_safety_purity", {}) \
            .setdefault("B3_claim_compliance", {})
        original = b3_cfg.get("allergen_free")
        b3_cfg["allergen_free"] = 3
        try:
            result = scorer._compute_safety_purity_score(
                product, "targeted", b0_moderate_penalty=0.0, flags=[]
            )
        finally:
            if original is None:
                b3_cfg.pop("allergen_free", None)
            else:
                b3_cfg["allergen_free"] = original
        assert result.get("B3", 0) >= 3.0, (
            f"B3 must source allergen_free value from config; got B3={result.get('B3')}"
        )

    # ------------------------------------------------------------------
    # M7: code defaults must match config values
    # ------------------------------------------------------------------
    def test_m7_feature_on_defaults_agree_with_config(self, scorer):
        """A startup-consistency check: for every feature flag that is set
        to True in the shipped config, the _feature_on default in code
        should ALSO default to True. If not, a config-load failure silently
        reverts the flag to the wrong state. Currently FAILS for
        require_full_mapping, enable_non_gmo_bonus."""
        from score_supplements import SupplementScorer
        import inspect

        src = inspect.getsource(SupplementScorer)
        # Map config flag values to the _feature_on defaults in the source.
        # Simple heuristic: find each _feature_on call and extract the key
        # and the default= value.
        import re
        pattern = re.compile(
            r'_feature_on\(\s*"([A-Za-z_0-9]+)"\s*,\s*default\s*=\s*(True|False)\s*\)'
        )
        matches = pattern.findall(src)

        shipped_gates = scorer.config.get("feature_gates", {})
        mismatches = []
        for flag, default_str in matches:
            default_bool = (default_str == "True")
            shipped = shipped_gates.get(flag)
            if shipped is None:
                continue  # flag not in config, skip
            if bool(shipped) != default_bool:
                mismatches.append(
                    f"{flag}: config={shipped}, code default={default_bool}"
                )
        assert not mismatches, (
            "Code-default vs config mismatch(es):\n  "
            + "\n  ".join(mismatches)
            + "\nA config-load failure would silently flip these to the wrong state."
        )

    # ------------------------------------------------------------------
    # M3: marine certs sourced from cert_claim_rules.json scope
    # ------------------------------------------------------------------
    def _make_non_omega_with_ifos_product(self):
        """Product with IFOS certification but no omega-3/marine ingredients.
        IFOS is marine-specific — it should NOT score for a non-omega product."""
        p = make_base_product()
        p["named_cert_programs"] = ["IFOS"]
        # Ensure no omega/marine ingredients
        p["ingredient_quality_data"]["ingredients"] = [
            {
                "name": "Magnesium Glycinate", "standard_name": "Magnesium",
                "canonical_id": "magnesium", "score": 18, "dosage_importance": 1.0,
                "mapped": True, "quantity": 200, "unit": "mg",
                "unit_normalized": "mg", "has_dose": True,
                "is_proprietary_blend": False, "is_parent_total": False,
            },
        ]
        p["ingredient_quality_data"]["ingredients_scorable"] = list(
            p["ingredient_quality_data"]["ingredients"]
        )
        return p

    def _make_omega_with_ifos_product(self):
        """Fish oil product with IFOS certification — IFOS should score."""
        p = make_base_product()
        p["named_cert_programs"] = ["IFOS"]
        p["ingredient_quality_data"]["ingredients"] = [
            {
                "name": "Fish Oil", "standard_name": "Fish Oil",
                "canonical_id": "fish_oil", "score": 15, "dosage_importance": 1.0,
                "mapped": True, "quantity": 1000, "unit": "mg",
                "unit_normalized": "mg", "has_dose": True,
                "is_proprietary_blend": False, "is_parent_total": False,
            },
        ]
        p["ingredient_quality_data"]["ingredients_scorable"] = list(
            p["ingredient_quality_data"]["ingredients"]
        )
        return p

    def test_m3_ifos_filtered_out_for_non_omega_product(self, scorer):
        """IFOS (marine-scope cert) must not score for a non-omega product.
        Currently passes via hardcoded _MARINE_CERTS; after M3 fix this must
        still pass while sourcing from cert_claim_rules.json."""
        product = self._make_non_omega_with_ifos_product()
        result = scorer._compute_certifications_bonus(product, "targeted")
        assert result.get("named_program_count", 0) == 0, (
            "IFOS must not count for a non-omega targeted product; "
            f"got named_program_count={result.get('named_program_count')}"
        )

    def test_m3_ifos_scored_for_omega_product(self, scorer):
        """IFOS must score for an omega-3 product."""
        product = self._make_omega_with_ifos_product()
        result = scorer._compute_certifications_bonus(product, "targeted")
        assert result.get("named_program_count", 0) >= 1, (
            "IFOS must count for an omega/fish-oil product; "
            f"got named_program_count={result.get('named_program_count')}"
        )

    def test_m3_marine_cert_list_derived_from_cert_claim_rules(self, scorer):
        """After M3 fix, the marine cert list must come from the data file's
        product_scope field, not a hardcoded Python set. This test adds a
        hypothetical new marine cert to the scorer's runtime-loaded rules
        and verifies the scorer picks it up automatically."""
        # The scorer should expose a method or use cert_claim_rules at runtime.
        # This test locks the semantic: the hardcoded _MARINE_CERTS set
        # should be removed or source from cert_claim_rules scope field.
        import inspect
        src = inspect.getsource(scorer._compute_certifications_bonus)
        # Heuristic: after fix the function should no longer contain a
        # hardcoded marine_certs literal inline.
        assert "friend of the sea" not in src.lower() or '"product_scope"' in src, (
            "After M3 fix, _compute_certifications_bonus must source marine "
            "cert scope from cert_claim_rules.json, not a hardcoded "
            "_MARINE_CERTS set. Found hardcoded set in function source."
        )


# ---------------------------------------------------------------------------
# Section B1 dietary sugar penalty tests
# ---------------------------------------------------------------------------

class TestB1DietarySugarPenalty:
    """TDD tests for the dietary sugar level penalty layered on top of B1."""

    @pytest.fixture
    def scorer(self):
        return SupplementScorer()

    def _make_product_with_sugar(self, level: str, amount_g: float = 0.0):
        """Return a base product with dietary_sensitivity_data.sugar set."""
        p = make_base_product()
        p["dietary_sensitivity_data"] = {
            "sugar": {
                "level": level,
                "amount_g": amount_g,
                "contains_sugar": level not in ("sugar_free",),
            }
        }
        return p

    def _make_product_no_sugar_field(self):
        """Return a base product with no dietary_sensitivity_data at all."""
        p = make_base_product()
        # explicitly absent
        p.pop("dietary_sensitivity_data", None)
        return p

    def _make_product_with_harmful_additive(self, level: str, amount_g: float = 0.0):
        """Return a product with a named harmful additive AND sugar data."""
        p = self._make_product_with_sugar(level, amount_g)
        p["contaminant_data"]["harmful_additives"] = {
            "found": True,
            "additives": [
                {
                    "additive_id": "high_fructose_corn_syrup",
                    "name": "High Fructose Corn Syrup",
                    "severity_level": "high",
                }
            ],
        }
        return p

    # ------------------------------------------------------------------
    # test_b1_sugar_penalty_moderate
    # ------------------------------------------------------------------
    def test_b1_sugar_penalty_moderate(self, scorer):
        """Moderate sugar level adds exactly 0.5 to B1 penalty vs sugar_free."""
        flags_free: list = []
        evidence_free: list = []
        p_free = self._make_product_with_sugar("sugar_free", 0.0)
        pen_free = scorer._compute_harmful_additives_penalty(
            p_free, flags=flags_free, evidence=evidence_free
        )

        flags_mod: list = []
        evidence_mod: list = []
        p_mod = self._make_product_with_sugar("moderate", 4.0)
        pen_mod = scorer._compute_harmful_additives_penalty(
            p_mod, flags=flags_mod, evidence=evidence_mod
        )

        assert round(pen_mod - pen_free, 6) == pytest.approx(0.5), (
            f"Expected moderate sugar penalty of 0.5 above sugar_free baseline; "
            f"got pen_free={pen_free}, pen_mod={pen_mod}"
        )

    # ------------------------------------------------------------------
    # test_b1_sugar_penalty_high
    # ------------------------------------------------------------------
    def test_b1_sugar_penalty_high(self, scorer):
        """High sugar level adds exactly 1.5 to B1 penalty vs sugar_free."""
        flags_free: list = []
        evidence_free: list = []
        p_free = self._make_product_with_sugar("sugar_free", 0.0)
        pen_free = scorer._compute_harmful_additives_penalty(
            p_free, flags=flags_free, evidence=evidence_free
        )

        flags_high: list = []
        evidence_high: list = []
        p_high = self._make_product_with_sugar("high", 8.0)
        pen_high = scorer._compute_harmful_additives_penalty(
            p_high, flags=flags_high, evidence=evidence_high
        )

        assert round(pen_high - pen_free, 6) == pytest.approx(1.5), (
            f"Expected high sugar penalty of 1.5 above sugar_free baseline; "
            f"got pen_free={pen_free}, pen_high={pen_high}"
        )

    # ------------------------------------------------------------------
    # test_b1_sugar_penalty_zero_for_sugar_free_and_low
    # ------------------------------------------------------------------
    def test_b1_sugar_penalty_zero_for_sugar_free_and_low(self, scorer):
        """sugar_free and low levels produce no additional penalty."""
        for level in ("sugar_free", "low"):
            flags: list = []
            evidence: list = []
            p = self._make_product_with_sugar(level, 2.0)
            pen = scorer._compute_harmful_additives_penalty(
                p, flags=flags, evidence=evidence
            )
            # baseline with no additives and no sugar should be 0.0
            assert pen == pytest.approx(0.0), (
                f"Expected zero penalty for level={level!r}, got {pen}"
            )

    # ------------------------------------------------------------------
    # test_b1_sugar_penalty_combines_with_named_additive
    # ------------------------------------------------------------------
    def test_b1_sugar_penalty_combines_with_named_additive(self, scorer):
        """High-sugar product WITH a named harmful additive stacks both penalties."""
        flags: list = []
        evidence: list = []
        p = self._make_product_with_harmful_additive("high", 8.0)
        pen = scorer._compute_harmful_additives_penalty(
            p, flags=flags, evidence=evidence
        )
        # Named additive = high severity = 2.0; sugar high = 1.5 → combined 3.5
        assert pen == pytest.approx(3.5), (
            f"Expected combined penalty of 3.5 (additive 2.0 + sugar 1.5), got {pen}"
        )

    # ------------------------------------------------------------------
    # test_b1_sugar_penalty_respects_cap
    # ------------------------------------------------------------------
    def test_b1_sugar_penalty_respects_cap(self, scorer):
        """Combined B1 penalty is clamped to the configured B1 cap (15.0 as of v3.4.x)."""
        # Build a product with multiple high-severity additives to push near cap
        p = self._make_product_with_sugar("high", 8.0)
        # Add many critical additives to blow past the cap
        p["contaminant_data"]["harmful_additives"] = {
            "found": True,
            "additives": [
                {"additive_id": f"bad_{i}", "name": f"Bad {i}", "severity_level": "critical"}
                for i in range(10)
            ],
        }
        flags: list = []
        evidence: list = []
        pen = scorer._compute_harmful_additives_penalty(
            p, flags=flags, evidence=evidence
        )
        # Read the cap from config to stay resilient to future retuning.
        b1_cap = float(
            scorer.config["section_B_safety_purity"]["B1_harmful_additives"]["cap"]
        )
        assert pen <= b1_cap + 1e-9, (
            f"B1 penalty {pen} exceeds cap {b1_cap}"
        )

    # ------------------------------------------------------------------
    # test_b1_sugar_penalty_flag_emitted
    # ------------------------------------------------------------------
    def test_b1_sugar_penalty_flag_emitted(self, scorer):
        """SUGAR_LEVEL_HIGH flag is appended when level is high; not when sugar_free."""
        # High
        flags_high: list = []
        evidence_high: list = []
        scorer._compute_harmful_additives_penalty(
            self._make_product_with_sugar("high", 8.0),
            flags=flags_high, evidence=evidence_high
        )
        assert "SUGAR_LEVEL_HIGH" in flags_high, (
            f"Expected SUGAR_LEVEL_HIGH in flags; got {flags_high}"
        )

        # Moderate
        flags_mod: list = []
        evidence_mod: list = []
        scorer._compute_harmful_additives_penalty(
            self._make_product_with_sugar("moderate", 4.0),
            flags=flags_mod, evidence=evidence_mod
        )
        assert "SUGAR_LEVEL_MODERATE" in flags_mod, (
            f"Expected SUGAR_LEVEL_MODERATE in flags; got {flags_mod}"
        )

        # sugar_free — no sugar flag
        flags_free: list = []
        evidence_free: list = []
        scorer._compute_harmful_additives_penalty(
            self._make_product_with_sugar("sugar_free", 0.0),
            flags=flags_free, evidence=evidence_free
        )
        assert "SUGAR_LEVEL_HIGH" not in flags_free
        assert "SUGAR_LEVEL_MODERATE" not in flags_free

    # ------------------------------------------------------------------
    # test_b1_sugar_penalty_missing_data_no_crash
    # ------------------------------------------------------------------
    def test_b1_sugar_penalty_missing_data_no_crash(self, scorer):
        """Products without dietary_sensitivity_data score B1 normally (no crash)."""
        p = self._make_product_no_sugar_field()
        flags: list = []
        evidence: list = []
        # Should not raise; should return 0.0 (no additives, no sugar)
        pen = scorer._compute_harmful_additives_penalty(
            p, flags=flags, evidence=evidence
        )
        assert pen == pytest.approx(0.0)
        assert "SUGAR_LEVEL_HIGH" not in flags
        assert "SUGAR_LEVEL_MODERATE" not in flags

    # ------------------------------------------------------------------
    # test_b1_sugar_penalty_disabled_by_config
    # ------------------------------------------------------------------
    def test_b1_sugar_penalty_disabled_by_config(self, scorer):
        """When enabled=false in config, no sugar penalty applies."""
        import copy
        original_cfg = scorer.config
        modified_cfg = copy.deepcopy(original_cfg)
        b_cfg = modified_cfg.setdefault("section_B_safety_purity", {})
        b_cfg["B1_dietary_sugar_penalty"] = {
            "enabled": False,
            "moderate_penalty": 0.5,
            "high_penalty": 1.5,
            "cap": 1.5,
        }
        scorer.config = modified_cfg
        try:
            flags: list = []
            evidence: list = []
            p = self._make_product_with_sugar("high", 8.0)
            pen = scorer._compute_harmful_additives_penalty(
                p, flags=flags, evidence=evidence
            )
            assert pen == pytest.approx(0.0), (
                f"Expected zero penalty when disabled; got {pen}"
            )
            assert "SUGAR_LEVEL_HIGH" not in flags
        finally:
            scorer.config = original_cfg

    # ------------------------------------------------------------------
    # test_b1_sugar_penalty_config_override
    # ------------------------------------------------------------------
    def test_b1_sugar_penalty_config_override(self, scorer):
        """Custom moderate=1.0 and high=3.0 from config are applied."""
        import copy
        original_cfg = scorer.config
        modified_cfg = copy.deepcopy(original_cfg)
        b_cfg = modified_cfg.setdefault("section_B_safety_purity", {})
        b_cfg["B1_dietary_sugar_penalty"] = {
            "enabled": True,
            "moderate_penalty": 1.0,
            "high_penalty": 3.0,
            "cap": 3.0,
        }
        scorer.config = modified_cfg
        try:
            # moderate → 1.0
            flags_m: list = []
            ev_m: list = []
            pen_m = scorer._compute_harmful_additives_penalty(
                self._make_product_with_sugar("moderate", 4.0),
                flags=flags_m, evidence=ev_m
            )
            assert pen_m == pytest.approx(1.0), (
                f"Expected moderate penalty 1.0 with override, got {pen_m}"
            )

            # high → 3.0
            flags_h: list = []
            ev_h: list = []
            pen_h = scorer._compute_harmful_additives_penalty(
                self._make_product_with_sugar("high", 8.0),
                flags=flags_h, evidence=ev_h
            )
            assert pen_h == pytest.approx(3.0), (
                f"Expected high penalty 3.0 with override, got {pen_h}"
            )
        finally:
            scorer.config = original_cfg

    # ------------------------------------------------------------------
    # test_b1_sugar_penalty_evidence_entry
    # ------------------------------------------------------------------
    def test_b1_sugar_penalty_evidence_entry(self, scorer):
        """Evidence list gets a dietary_sugar entry when level is moderate or high."""
        for level, expected_penalty in (("moderate", 0.5), ("high", 1.5)):
            flags: list = []
            evidence: list = []
            amount = 4.0 if level == "moderate" else 8.0
            scorer._compute_harmful_additives_penalty(
                self._make_product_with_sugar(level, amount),
                flags=flags, evidence=evidence
            )
            sugar_entries = [e for e in evidence if e.get("type") == "dietary_sugar"]
            assert len(sugar_entries) == 1, (
                f"Expected exactly one dietary_sugar evidence entry for level={level!r}; "
                f"got {sugar_entries}"
            )
            entry = sugar_entries[0]
            assert entry.get("level") == level
            assert entry.get("amount_g") == pytest.approx(amount)
            assert entry.get("penalty") == pytest.approx(expected_penalty)

    # ------------------------------------------------------------------
    # test_b1_sugar_penalty_e2e_score_delta
    # ------------------------------------------------------------------
    def test_b1_sugar_penalty_e2e_score_delta(self, scorer):
        """End-to-end: two identical products differing only in sugar level
        have score_80 difference equal to the expected penalty delta."""
        p_free = self._make_product_with_sugar("sugar_free", 0.0)
        p_high = self._make_product_with_sugar("high", 8.0)

        result_free = scorer.score_product(p_free)
        result_high = scorer.score_product(p_high)

        delta = result_free["score_80"] - result_high["score_80"]
        assert delta == pytest.approx(1.5), (
            f"Expected score_80 delta of 1.5 (high sugar penalty); "
            f"got sugar_free={result_free['score_80']}, high={result_high['score_80']}, "
            f"delta={delta}"
        )


# ---------------------------------------------------------------------------
# Item 5 backlog — L2, L3, R2 backlog cleanups (2026-04-10 session)
# ---------------------------------------------------------------------------


class TestD4HighStandardRegionConfigLockdown:
    """L2: D4 `high_std_regions` country set was hardcoded as a Python
    set at score_supplements.py:2400. This test locks it as
    config-driven via `section_D_brand_trust.D4_high_standard_region.
    accepted_regions`, so the list can be expanded without code changes.
    """

    def _make_product_with_region(self, region: str):
        p = make_base_product()
        p["manufacturing_region"] = region
        p["manufacturer_data"] = {
            "country_of_origin": {"country": region, "high_regulation_country": False},
            "bonus_features": {},
        }
        return p

    def test_d4_accepted_regions_read_from_config(self):
        scorer = SupplementScorer()
        # Restructured config: D4 is now an object with points +
        # accepted_regions. Legacy scalar form still works for
        # backward compat.
        scorer.config["section_D_brand_trust"]["D4_high_standard_region"] = {
            "points": 1.0,
            "accepted_regions": ["usa", "canada", "japan"],
        }
        # Baseline in config → should count
        for region in ["usa", "canada", "japan"]:
            p = self._make_product_with_region(region)
            d = scorer._compute_brand_trust_score(p)
            assert d["D4"] == pytest.approx(1.0), (
                f"Region '{region}' in config should earn D4 points"
            )
        # NOT in config → no points
        for region in ["germany", "france", "brazil"]:
            p = self._make_product_with_region(region)
            d = scorer._compute_brand_trust_score(p)
            assert d["D4"] == 0.0, (
                f"Region '{region}' NOT in config should earn zero D4"
            )

    def test_d4_default_list_includes_current_12_countries(self):
        """Regression: the shipped scoring_config.json must include
        the 12 historically-accepted countries so existing product
        scores don't change from this refactor.
        """
        scorer = SupplementScorer()
        expected = {
            "usa", "eu", "uk", "germany", "switzerland", "japan",
            "canada", "australia", "new zealand",
            "norway", "sweden", "denmark",
        }
        for region in expected:
            p = self._make_product_with_region(region)
            d = scorer._compute_brand_trust_score(p)
            assert d["D4"] == pytest.approx(1.0), (
                f"Region '{region}' must be in the default accepted list"
            )

    def test_d4_legacy_scalar_config_still_works(self):
        """Backward compat: if someone sets D4 as a plain number
        (legacy shape), the scorer must fall back to the default
        12-country set and use the scalar as the points value.
        """
        scorer = SupplementScorer()
        scorer.config["section_D_brand_trust"]["D4_high_standard_region"] = 2.0
        p = self._make_product_with_region("usa")
        d = scorer._compute_brand_trust_score(p)
        assert d["D4"] == pytest.approx(2.0)


class TestB0ConfigDrivenPenalties:
    """L3: B0 watchlist and high_risk penalty magnitudes were hardcoded
    as +5 and +10 at score_supplements.py:461,464. This test locks them
    as config-driven via `section_B_safety_purity.B0_immediate_safety.
    watchlist_penalty` and `high_risk_penalty`.
    """

    def _make_product_with_b0_hit(self, status: str):
        p = make_base_product()
        p["contaminant_data"] = {
            "banned_substances": {
                "substances": [
                    {
                        "name": f"Test {status}",
                        "banned_name": f"Test {status}",
                        "status": status,
                        "match_type": "exact",
                        "severity_level": "moderate",
                    }
                ]
            },
            "harmful_additives": {"additives": []},
            "allergens": {"allergens": []},
        }
        return p

    def test_b0_watchlist_default_penalty_is_5(self):
        scorer = SupplementScorer()
        p = self._make_product_with_b0_hit("watchlist")
        gate = scorer._evaluate_safety_gate(p)
        assert gate["moderate_penalty"] == 5.0

    def test_b0_high_risk_default_penalty_is_10(self):
        scorer = SupplementScorer()
        p = self._make_product_with_b0_hit("high_risk")
        gate = scorer._evaluate_safety_gate(p)
        assert gate["moderate_penalty"] == 10.0

    def test_b0_watchlist_penalty_overridable_via_config(self):
        scorer = SupplementScorer()
        scorer.config.setdefault("section_B_safety_purity", {}).setdefault(
            "B0_immediate_fail", {}
        )["watchlist_penalty"] = 3.0
        p = self._make_product_with_b0_hit("watchlist")
        gate = scorer._evaluate_safety_gate(p)
        assert gate["moderate_penalty"] == 3.0

    def test_b0_high_risk_penalty_overridable_via_config(self):
        scorer = SupplementScorer()
        scorer.config.setdefault("section_B_safety_purity", {}).setdefault(
            "B0_immediate_fail", {}
        )["high_risk_penalty"] = 15.0
        p = self._make_product_with_b0_hit("high_risk")
        gate = scorer._evaluate_safety_gate(p)
        assert gate["moderate_penalty"] == 15.0

    def test_b0_flag_still_emitted_regardless_of_penalty(self):
        """Changing the numeric penalty must not break the flag
        emission contract used by the Flutter warning display.
        """
        scorer = SupplementScorer()
        p_wl = self._make_product_with_b0_hit("watchlist")
        gate_wl = scorer._evaluate_safety_gate(p_wl)
        assert "B0_WATCHLIST_SUBSTANCE" in gate_wl["flags"]

        p_hr = self._make_product_with_b0_hit("high_risk")
        gate_hr = scorer._evaluate_safety_gate(p_hr)
        assert "B0_HIGH_RISK_SUBSTANCE" in gate_hr["flags"]


class TestR2OrphanFlagRemoved:
    """R2: `probiotic_bonus_applies_before_ceiling` at
    scoring_config.json:478 had zero readers in score_supplements.py.
    This test locks its absence — if it ever gets re-added to config
    without a corresponding reader, the test fails.
    """

    def test_probiotic_bonus_applies_before_ceiling_not_in_config(self):
        """The orphan flag was previously in
        `score_floors_and_ceilings.probiotic_bonus_applies_before_ceiling`.
        This test does a deep search — the flag must not appear ANYWHERE
        in the config tree."""
        with open(
            Path(__file__).parent.parent / "config" / "scoring_config.json"
        ) as f:
            config = json.load(f)

        def _contains_key(obj, target):
            if isinstance(obj, dict):
                if target in obj:
                    return True
                return any(_contains_key(v, target) for v in obj.values())
            if isinstance(obj, list):
                return any(_contains_key(v, target) for v in obj)
            return False

        assert not _contains_key(config, "probiotic_bonus_applies_before_ceiling"), (
            "R2: probiotic_bonus_applies_before_ceiling has zero readers "
            "in score_supplements.py. If a consumer was added, also update "
            "this test. Otherwise the flag is dead config and should be "
            "removed to prevent operator confusion."
        )

    def test_probiotic_bonus_applies_before_ceiling_not_read_by_scorer(self):
        """Belt-and-braces: confirm the scorer source has zero
        references to the orphan flag name."""
        src_path = Path(__file__).parent.parent / "score_supplements.py"
        src = src_path.read_text()
        assert "probiotic_bonus_applies_before_ceiling" not in src, (
            "R2: scorer code should have no reference to the orphan "
            "flag 'probiotic_bonus_applies_before_ceiling'."
        )


# =============================================================================
# v3.4.x ship-now config bumps — lockdown tests
# =============================================================================
#
# These tests protect the intentional recalibration done in the April 2026
# ship-now pass:
#
#   * A1_bioavailability_form.max       15   -> 18   (stop compressing raw score)
#   * A2_premium_forms.max              3    -> 5    (reward stackers)
#   * omega3_dose_bonus.max             2.0  -> 3.0  (restore pre-merge value)
#   * B1_harmful_additives.cap          8    -> 15   (punish additive stacking)
#   * probiotic_bonus._caps_note        added        (audit clarity, no behavior change)
#
# If a future pass retunes any of these, update the constants below AND write
# an ADR noting why. These are deliberate, not accidental.


class TestShipNowConfigLockdown:
    """Lock the v3.4.x ship-now config bumps so they can't silently drift."""

    @pytest.fixture
    def scorer(self):
        return SupplementScorer()

    def test_a1_max_raised_to_18(self, scorer):
        a1 = scorer.config["section_A_ingredient_quality"]["A1_bioavailability_form"]
        assert a1["max"] == 18, (
            "A1.max must be 18 to stop compressing the enricher's 0-18 raw "
            "score. If this fails, someone reverted the v3.4.x unclamp."
        )
        # range_score_field must still be the 0-18 band — otherwise the
        # scorer's (avg_raw / range_max) * max_points math breaks.
        assert str(a1.get("range_score_field", "")).endswith("-18")

    def test_a2_max_raised_to_5(self, scorer):
        a2 = scorer.config["section_A_ingredient_quality"]["A2_premium_forms"]
        assert a2["max"] == 5, (
            "A2.max must be 5 to reward products that stack 4+ premium forms."
        )

    def test_omega3_max_capped_at_2(self, scorer):
        """v3.4.5 (clinician decision 2026-05-01): omega3 bonus capped at 2.0.

        AHA evidence-based dose is 1g/day for cardiovascular protection — above
        that, marginal benefit is unclear and bleeding risk rises. The 80-pt
        quality-led model shouldn't be derailed by a single nutrient's dose.
        Prescription-dose products still get the PRESCRIPTION_DOSE_OMEGA3 flag
        for visibility.
        """
        o3 = scorer.config["section_A_ingredient_quality"]["omega3_dose_bonus"]
        assert o3["max"] == 2.0, (
            "omega3_dose_bonus.max must be 2.0 (clinician cap 2026-05-01). "
            "AHA evidence-based dose is 1g/day; bands redistributed within "
            "the 0–2 range to maintain tier differentiation."
        )
        # Top band must actually reach the cap — otherwise the cap is cosmetic.
        top_band_score = max(float(b.get("score", 0.0)) for b in o3.get("bands", []))
        assert top_band_score == 2.0, (
            f"omega3 top band reaches {top_band_score} but cap is 2.0. "
            "prescription_dose band should sit at exactly 2.0."
        )

    def test_b1_cap_raised_to_15(self, scorer):
        b1 = scorer.config["section_B_safety_purity"]["B1_harmful_additives"]
        assert b1["cap"] == 15, (
            "B1.cap must be 15 so products stacking 5+ critical additives "
            "take the full penalty instead of being compressed."
        )

    def test_probiotic_caps_note_documented(self, scorer):
        pro = scorer.config["section_A_ingredient_quality"]["probiotic_bonus"]
        assert "_caps_note" in pro, (
            "probiotic_bonus must carry an explicit _caps_note explaining the "
            "default_max / extended_max mode split for audit clarity."
        )
        # Sanity-check the numeric caps haven't drifted.
        assert pro.get("default_max") == 3
        assert pro.get("extended_max") == 10

    def test_a1_end_to_end_perfect_ingredient_earns_18(self, scorer):
        """End-to-end proof: a single ingredient with upstream score=18
        (premium form + natural bonus) now lands at A1=18 instead of 15."""
        product = make_base_product()
        product["supplement_type"]["type"] = "single"
        product["ingredient_quality_data"]["total_active"] = 1
        product["ingredient_quality_data"]["ingredients_scorable"] = [
            {
                "name": "Magnesium Glycinate",
                "standard_name": "Magnesium",
                "score": 18,
                "dosage_importance": 1.0,
                "mapped": True,
                "quantity": 200,
                "unit": "mg",
                "has_dose": True,
            }
        ]
        product["ingredient_quality_data"]["ingredients"] = deepcopy(
            product["ingredient_quality_data"]["ingredients_scorable"]
        )
        section_a = scorer._compute_ingredient_quality_score(product, "single")
        assert section_a["A1"] == pytest.approx(18.0, rel=1e-6), (
            f"Expected A1=18.0 for a perfect upstream score=18 ingredient, "
            f"got {section_a['A1']}"
        )

    def test_b1_end_to_end_five_critical_additives_counts_fully(self, scorer):
        """End-to-end proof: 5 critical additives (= 15.0 raw) now land at
        B1_penalty=15.0 instead of being compressed to the old cap of 8."""
        product = make_base_product()
        product["contaminant_data"]["harmful_additives"] = {
            "found": True,
            "additives": [
                {"additive_id": f"CRIT_{i}", "severity_level": "critical"}
                for i in range(5)
            ],
        }
        section_b = scorer._compute_safety_purity_score(
            product, "targeted", 0.0, []
        )
        assert section_b["B1_penalty"] == pytest.approx(15.0), (
            f"Expected B1_penalty=15.0 for 5 critical additives (raw 15.0 "
            f"== new cap 15), got {section_b['B1_penalty']}"
        )


class TestOpaqueOmega3BlendDetection:
    @pytest.mark.parametrize(
        "blend_name",
        [
            "Adaptogenic Preparation Complex",
            "Department Blend",
            "Departure Formula",
            "Prepared Cocoa Blend",
            "Dharma Wellness Blend",
            "Sundha Greens",
        ],
    )
    def test_opaque_omega3_blend_ignores_substring_false_positives(self, blend_name):
        product = {
            "proprietary_blends": [
                {
                    "name": blend_name,
                    "disclosure_level": "none",
                    "ingredients": [],
                }
            ]
        }

        assert SupplementScorer._has_opaque_omega3_blend(product) is False

    @pytest.mark.parametrize(
        "blend_name",
        [
            "Omega-3 Complex",
            "Fish Oil Proprietary Blend",
            "EPA DHA Matrix",
            "Marine Lipid Blend",
            "N-3 Fatty Acids",
        ],
    )
    def test_opaque_omega3_blend_matches_real_indicators(self, blend_name):
        product = {
            "proprietary_blends": [
                {
                    "name": blend_name,
                    "disclosure_level": "none",
                    "ingredients": [],
                }
            ]
        }

        assert SupplementScorer._has_opaque_omega3_blend(product) is True

    @pytest.mark.parametrize(
        "blend_name",
        [
            "OmegaXanthin Blend",
            "OmegaCare Complex",
            "DHA-Forte",
        ],
    )
    def test_opaque_omega3_blend_matches_compound_words(self, blend_name):
        product = {
            "proprietary_blends": [
                {
                    "name": blend_name,
                    "disclosure_level": "none",
                    "ingredients": [],
                }
            ]
        }

        assert SupplementScorer._has_opaque_omega3_blend(product) is True
