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

    def test_b0_recall_blocks(self, scorer):
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
        assert result["verdict"] == "BLOCKED"
        assert result["score_80"] is None
        assert result["evaluation_stage"] == "safety"

    def test_b0_critical_unsafe(self, scorer):
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
        assert result["verdict"] == "UNSAFE"
        assert result["score_80"] == 0
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
        assert result["score_80"] == pytest.approx(35.0)
        assert result["breakdown"]["B"]["B0_moderate_penalty"] == pytest.approx(5.0)

    def test_b0_moderate_penalty_uses_max_not_last_write_wins(self, scorer):
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
        assert result["moderate_penalty"] == pytest.approx(10.0)

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
        assert section_a["A1"] == pytest.approx(15.0, rel=1e-6)

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
        # 3 critical = 9.0, capped at config cap of 8
        assert section_b["B1_penalty"] == pytest.approx(8.0)

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
        assert scorer._compute_bioavailability_score(p, "targeted") == pytest.approx((expected_avg / 18.0) * 15.0, abs=0.01)
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
        assert scorer._compute_bioavailability_score(p, "targeted") == pytest.approx((14.0 / 18.0) * 15.0, abs=0.01)

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
        assert scorer._compute_bioavailability_score(p, "targeted") == pytest.approx((expected_avg / 18.0) * 15.0, abs=0.01)

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

        # For reference: what it would be if blend IS included
        # (15×1 + 5×1) / 2 = 10  →  (10/18)×15 ≈ 8.33
        # Correct (blend excluded): 15/1 = 15  →  (15/18)×15 = 12.5
        assert score_with == pytest.approx((15.0 / 18.0) * 15.0, abs=0.1)

    def test_a1_not_contaminated_by_stub_score(self, scorer):
        """Blend container with stub score=5 must not drag A1 below the
        disclosed-only average."""
        p = self._product_with_blend_container(blend_score=5)
        a1_score = scorer._compute_bioavailability_score(p, "targeted")
        # Score from disclosed ingredients only (score=15): 12.5
        disclosed_only = (15.0 / 18.0) * 15.0
        # Score if blend were included (score average 10): ≈8.33
        would_be_dragged = (10.0 / 18.0) * 15.0
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
        assert score == pytest.approx((expected_avg / 18.0) * 15.0, abs=0.1)

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
        assert a1 == pytest.approx((expected_avg / 18.0) * 15.0, abs=0.01)

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
        assert a1 == pytest.approx((expected_avg / 18.0) * 15.0, abs=0.01)

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
        assert result["score_80"] == pytest.approx(35.0)
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
        """Multiple ingredients use top-N diminishing returns (default: [1.0, 0.5, 0.25])."""
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
        # Vitamin D: 5 * 0.65 = 3.25 (2nd, weight 0.5)
        # Total: 6.0*1.0 + 3.25*0.5 = 7.625
        assert section_c["score"] == pytest.approx(7.62, abs=0.01)
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
        # Each: 6*1.0=6.0.  Top-N weights [1.0, 0.5, 0.25]:
        # 6.0*1.0 + 6.0*0.5 + 6.0*0.25 = 10.5 (4th ingredient ignored)
        assert section_c["score"] == pytest.approx(10.5)
        assert section_c["top_n_applied"] == 3

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
        # 5 * 0.65 * 0.25 = 0.8125
        assert section_c["score"] == pytest.approx(0.81, abs=0.01)

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
        # 6 * 0.65 * 0.85 = 3.315
        assert section_c["score"] == pytest.approx(3.32, abs=0.01)

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
        # 5 * 0.65 * 1.0 = 3.25 (same as before the change)
        assert section_c["score"] == pytest.approx(3.25)

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
        # 5 * 0.8 * 1.0 = 4.0 — unchanged from old model
        assert section_c["score"] == pytest.approx(4.0)
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
        # 5 * 0.65 * 1.0 (positive_strong) * 1.2 (enrollment 1000+) = 3.9
        assert section_c["score"] == pytest.approx(3.9)

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
        # 4 * 0.65 * 1.0 * 0.6 (enrollment <50) = 1.56
        assert section_c["score"] == pytest.approx(1.56)

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
        # 2 * 0.65 * 1.0 = 1.3 (no enrollment boost for observational)
        assert section_c["score"] == pytest.approx(1.3)

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
        # 5 * 0.65 = 3.25 (no enrollment adjustment)
        assert section_c["score"] == pytest.approx(3.25)

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
        # 5 * 0.65 = 3.25 + 0.5 depth bonus = 3.75
        assert section_c["score"] == pytest.approx(3.75)
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
        # 5 * 0.65 = 3.25 + 0.25 depth bonus = 3.5
        assert section_c["score"] == pytest.approx(3.5)
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
        # 4 * 0.65 = 2.6 + 0.0 depth bonus
        assert section_c["score"] == pytest.approx(2.6)
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
        # 5000mg > 3*1000mg → supra flag; 4*0.65 = 2.6 (no dose reduction)
        assert section_c["score"] == pytest.approx(2.6)
        assert "SUPRA_CLINICAL_DOSE" in flags

    def test_c_branded_rct_multiplier(self, scorer):
        """branded-rct evidence level uses 0.8x multiplier."""
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
        # 5 * 0.8 = 4.0
        assert section_c["score"] == pytest.approx(4.0)

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


class TestSynergyClusterSpec:
    """P2-1: Synergy cluster qualification tests."""

    @pytest.fixture
    def scorer(self):
        return SupplementScorer()

    def test_synergy_explicit_flag_respected(self, scorer):
        """Pre-computed synergy_cluster_qualified is used when present."""
        product = make_base_product()
        product["synergy_cluster_qualified"] = True
        assert scorer._synergy_cluster_qualified(product) is True

    def test_synergy_explicit_flag_false(self, scorer):
        """Pre-computed False flag is respected."""
        product = make_base_product()
        product["synergy_cluster_qualified"] = False
        assert scorer._synergy_cluster_qualified(product) is False

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
        assert scorer._synergy_cluster_qualified(product) is False

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
        assert scorer._synergy_cluster_qualified(product) is False

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
        assert scorer._synergy_cluster_qualified(product) is False

    def test_synergy_half_dosed_qualifies(self, scorer):
        """Cluster where >= half of checkable ingredients meet dose qualifies."""
        product = make_base_product()
        product["formulation_data"] = {
            "synergy_clusters": [
                {
                    "cluster_name": "Bone Health",
                    "match_count": 2,
                    "matched_ingredients": [
                        {"name": "Calcium", "min_effective_dose": 500, "meets_minimum": True},
                        {"name": "Vitamin D", "min_effective_dose": 1000, "meets_minimum": False},
                    ],
                }
            ]
        }
        # 1/2 dosed, ceil(2/2) = 1, 1 >= 1 → qualifies
        assert scorer._synergy_cluster_qualified(product) is True


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
        """canonical_id='epa_dha' contributes to both EPA and DHA buckets."""
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
        assert result["epa_mg_per_unit"] == pytest.approx(600.0)
        assert result["dha_mg_per_unit"] == pytest.approx(600.0)
        assert result["epa_dha_mg_per_unit"] == pytest.approx(1200.0)
        assert result["per_day_mid"] == pytest.approx(1200.0)

    # ---- _compute_legacy_section_e band boundaries ----

    @pytest.mark.parametrize("per_day,exp_score,exp_band", [
        (0,    0.0, "below_efsa_ai"),
        (100,  0.0, "below_efsa_ai"),
        (249,  0.0, "below_efsa_ai"),   # 1 below EFSA AI threshold
        (250,  0.5, "efsa_ai_zone"),    # exactly EFSA AI 250 mg/day
        (499,  0.5, "efsa_ai_zone"),
        (500,  1.0, "general_health"),  # FDA QHC / general health
        (999,  1.0, "general_health"),
        (1000, 1.5, "aha_cvd"),         # AHA CVD recommendation
        (1999, 1.5, "aha_cvd"),
        (2000, 2.0, "high_clinical"),   # EFSA triglyceride claim
        (3999, 2.0, "high_clinical"),
        (4000, 2.0, "prescription_dose"),  # AHA/ACC prescription dose
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
        # per_day = (500+250) × 2 = 1500 mg/day → aha_cvd band → 1.5 pts

        result = scorer.score_product(prod)
        assert result["verdict"] in {"SAFE", "POOR", "CAUTION"}

        section_scores = result.get("section_scores", {})
        assert "E_dose_adequacy" in section_scores
        e = section_scores["E_dose_adequacy"]
        assert e["applicable"] is True
        assert e["score"] == pytest.approx(1.5, abs=0.001)
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
