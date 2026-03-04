#!/usr/bin/env python3
"""Interaction tracker and score-neutrality regression tests."""

from copy import deepcopy
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from db_integrity_sanity_check import check_ingredient_interaction_rules
from enrich_supplements_v3 import SupplementEnricherV3
from score_supplements import SupplementScorer


def _make_scoring_base_product():
    return {
        "dsld_id": "p_interaction_1",
        "product_name": "Interaction Test Product",
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
        "match_ledger": {"domains": {"ingredients": {"entries": []}}},
    }


class TestInteractionProfile:
    @pytest.fixture
    def enricher(self):
        return SupplementEnricherV3()

    def test_iqm_rule_maps_and_emits_alerts(self, enricher):
        enriched = {
            "ingredient_quality_data": {
                "ingredients": [
                    {
                        "name": "Vitamin K2",
                        "raw_source_text": "Vitamin K2",
                        "standard_name": "Vitamin K",
                        "canonical_id": "vitamin_k",
                        "form_id": "phylloquinone",
                    }
                ],
                "ingredients_skipped": [],
            }
        }

        profile = enricher._collect_interaction_profile(enriched)

        assert enriched["ingredient_quality_data"]["ingredients"][0]["safety_hits"]
        assert profile["ingredient_alerts"]
        assert "anticoagulants" in profile["drug_class_summary"]

    def test_non_iqm_sources_are_supported(self, enricher):
        enriched = {
            "ingredient_quality_data": {
                "ingredients": [
                    {
                        "name": "Ginger Extract",
                        "raw_source_text": "Ginger Extract",
                        "recognition_source": "other_ingredients",
                        "matched_entry_id": "NHA_GINGER_EXTRACT",
                    },
                    {
                        "name": "Propylene Glycol",
                        "raw_source_text": "Propylene Glycol",
                        "recognition_source": "harmful_additives",
                        "matched_entry_id": "ADD_PROPYLENE_GLYCOL",
                    },
                    {
                        "name": "Yohimbe",
                        "raw_source_text": "Yohimbe",
                        "recognition_source": "banned_recalled_ingredients",
                        "matched_entry_id": "RISK_YOHIMBE",
                    },
                ],
                "ingredients_skipped": [],
            }
        }

        profile = enricher._collect_interaction_profile(enriched)

        assert "surgery_scheduled" in profile["condition_summary"]
        assert "kidney_disease" in profile["condition_summary"]
        assert "hypertension" in profile["condition_summary"]

    def test_form_scoped_rule_applies_only_on_matching_form(self, enricher):
        enriched = {
            "ingredient_quality_data": {
                "ingredients": [
                    {
                        "name": "Vitamin K1",
                        "raw_source_text": "Vitamin K1",
                        "standard_name": "Vitamin K",
                        "canonical_id": "vitamin_k",
                        "form_id": "phylloquinone",
                    }
                ],
                "ingredients_skipped": [],
            }
        }

        profile = enricher._collect_interaction_profile(enriched)
        hit_rule_ids = {
            hit.get("rule_id")
            for hit in enriched["ingredient_quality_data"]["ingredients"][0].get("safety_hits", [])
        }
        assert "RULE_IQM_VITAMIN_K_MK7_FORM_ONLY" not in hit_rule_ids

        enriched["ingredient_quality_data"]["ingredients"][0]["form_id"] = "menaquinone_7_mk7"
        profile = enricher._collect_interaction_profile(enriched)
        hit_rule_ids = {
            hit.get("rule_id")
            for hit in enriched["ingredient_quality_data"]["ingredients"][0].get("safety_hits", [])
        }
        assert "RULE_IQM_VITAMIN_K_MK7_FORM_ONLY" in hit_rule_ids
        assert profile["ingredient_alerts"]

    def test_user_profile_filter_returns_relevant_alerts(self, enricher):
        enriched = {
            "ingredient_quality_data": {
                "ingredients": [
                    {
                        "name": "Yohimbe",
                        "raw_source_text": "Yohimbe",
                        "recognition_source": "banned_recalled_ingredients",
                        "matched_entry_id": "RISK_YOHIMBE",
                    }
                ],
                "ingredients_skipped": [],
            }
        }

        profile = enricher._collect_interaction_profile(
            enriched,
            user_profile={
                "conditions": ["pregnancy"],
                "drug_classes": ["antihypertensives"],
            },
        )

        user_alerts = profile["user_condition_alerts"]
        assert user_alerts["enabled"] is True
        assert any(a.get("type") == "condition" and a.get("condition_id") == "pregnancy" for a in user_alerts["alerts"])
        assert any(a.get("type") == "drug_class" and a.get("drug_class_id") == "antihypertensives" for a in user_alerts["alerts"])

    def test_caffeine_pregnancy_threshold_uses_max_daily_servings(self, enricher):
        enriched = {
            "serving_basis": {"max_servings_per_day": 3},
            "ingredient_quality_data": {
                "ingredients": [
                    {
                        "name": "Caffeine",
                        "raw_source_text": "Caffeine",
                        "standard_name": "Caffeine",
                        "canonical_id": "caffeine",
                        "quantity": 100,
                        "unit": "mg",
                    }
                ],
                "ingredients_skipped": [],
            }
        }

        profile = enricher._collect_interaction_profile(enriched)
        pregnancy = profile["condition_summary"].get("pregnancy")
        assert pregnancy is not None
        assert pregnancy["highest_severity"] == "avoid"

    def test_caffeine_pregnancy_threshold_below_limit_is_monitor(self, enricher):
        enriched = {
            "serving_basis": {"max_servings_per_day": 1},
            "ingredient_quality_data": {
                "ingredients": [
                    {
                        "name": "Caffeine",
                        "raw_source_text": "Caffeine",
                        "standard_name": "Caffeine",
                        "canonical_id": "caffeine",
                        "quantity": 150,
                        "unit": "mg",
                    }
                ],
                "ingredients_skipped": [],
            }
        }

        profile = enricher._collect_interaction_profile(enriched)
        pregnancy = profile["condition_summary"].get("pregnancy")
        assert pregnancy is not None
        assert pregnancy["highest_severity"] == "monitor"

    def test_vitamin_a_pregnancy_threshold_preformed_forms(self, enricher):
        enriched_high = {
            "serving_basis": {"max_servings_per_day": 1},
            "ingredient_quality_data": {
                "ingredients": [
                    {
                        "name": "Vitamin A",
                        "raw_source_text": "Vitamin A",
                        "standard_name": "Vitamin A",
                        "canonical_id": "vitamin_a",
                        "form_id": "retinol",
                        "quantity": 12000,
                        "unit": "iu",
                    }
                ],
                "ingredients_skipped": [],
            }
        }
        profile_high = enricher._collect_interaction_profile(enriched_high)
        assert profile_high["condition_summary"]["pregnancy"]["highest_severity"] == "contraindicated"

        enriched_low = deepcopy(enriched_high)
        enriched_low["ingredient_quality_data"]["ingredients"][0]["quantity"] = 5000
        profile_low = enricher._collect_interaction_profile(enriched_low)
        assert profile_low["condition_summary"]["pregnancy"]["highest_severity"] == "caution"

    def test_threshold_not_evaluable_falls_back_to_base_severity(self, enricher):
        enriched = {
            "serving_basis": {"max_servings_per_day": 1},
            "ingredient_quality_data": {
                "ingredients": [
                    {
                        "name": "Caffeine",
                        "raw_source_text": "Caffeine",
                        "standard_name": "Caffeine",
                        "canonical_id": "caffeine",
                        "quantity": 1,
                        "unit": "capsule",
                    }
                ],
                "ingredients_skipped": [],
            }
        }
        profile = enricher._collect_interaction_profile(enriched)
        pregnancy = profile["condition_summary"].get("pregnancy")
        assert pregnancy is not None
        assert pregnancy["highest_severity"] == "monitor"


class TestInteractionRuleIntegrity:
    def test_unknown_subject_ref_fails_validation(self):
        bad = {
            "interaction_rules": [
                {
                    "id": "RULE_BAD_REF",
                    "subject_ref": {
                        "db": "ingredient_quality_map",
                        "canonical_id": "not_a_real_parent"
                    },
                    "condition_rules": [
                        {
                            "condition_id": "pregnancy",
                            "severity": "avoid",
                            "evidence_level": "probable",
                            "action": "Avoid",
                            "sources": ["https://example.com/ref"]
                        }
                    ],
                    "drug_class_rules": [],
                    "pregnancy_lactation": None,
                    "last_reviewed": "2026-02-28",
                    "review_owner": "test"
                }
            ]
        }

        findings = []
        check_ingredient_interaction_rules(findings, bad, "tmp_interaction_rules.json")
        assert any(f.issue == "unresolved_subject_ref" for f in findings)

    def test_missing_taxonomy_enum_fails_validation(self):
        bad = {
            "interaction_rules": [
                {
                    "id": "RULE_BAD_ENUM",
                    "subject_ref": {
                        "db": "ingredient_quality_map",
                        "canonical_id": "vitamin_k"
                    },
                    "condition_rules": [
                        {
                            "condition_id": "unknown_condition",
                            "severity": "avoid",
                            "evidence_level": "probable",
                            "action": "Avoid",
                            "sources": ["https://example.com/ref"]
                        }
                    ],
                    "drug_class_rules": [],
                    "pregnancy_lactation": None,
                    "last_reviewed": "2026-02-28",
                    "review_owner": "test"
                }
            ]
        }

        findings = []
        check_ingredient_interaction_rules(findings, bad, "tmp_interaction_rules.json")
        assert any(
            f.issue == "enum_value_not_supported" and "condition_id" in f.path
            for f in findings
        )


class TestScoreNeutrality:
    def test_interaction_payload_does_not_change_score(self):
        scorer = SupplementScorer()
        baseline = _make_scoring_base_product()
        with_interactions = deepcopy(baseline)
        with_interactions["ingredient_quality_data"]["ingredients"][0]["safety_hits"] = [
            {
                "rule_id": "RULE_SAMPLE",
                "subject_ref": {"db": "ingredient_quality_map", "canonical_id": "magnesium"},
                "condition_hits": [
                    {"condition_id": "kidney_disease", "severity": "monitor"}
                ],
                "drug_class_hits": [],
            }
        ]
        with_interactions["interaction_profile"] = {
            "ingredient_alerts": [
                {
                    "ingredient_name": "Magnesium Glycinate",
                    "rule_id": "RULE_SAMPLE"
                }
            ],
            "condition_summary": {
                "kidney_disease": {
                    "highest_severity": "monitor",
                    "ingredient_count": 1,
                    "ingredients": ["Magnesium Glycinate"]
                }
            },
            "drug_class_summary": {},
            "highest_severity": "monitor",
            "data_sources": ["https://example.com/ref"],
            "rules_version": "5.0.0",
            "taxonomy_version": "5.0.0"
        }

        base_result = scorer.score_product(baseline)
        new_result = scorer.score_product(with_interactions)

        assert new_result["score_80"] == base_result["score_80"]
        assert new_result["quality_score"] == base_result["quality_score"]
        assert new_result["verdict"] == base_result["verdict"]
        assert new_result["breakdown"]["A"]["score"] == base_result["breakdown"]["A"]["score"]
        assert new_result["breakdown"]["B"]["score"] == base_result["breakdown"]["B"]["score"]
        assert new_result["breakdown"]["C"]["score"] == base_result["breakdown"]["C"]["score"]
        assert new_result["breakdown"]["D"]["score"] == base_result["breakdown"]["D"]["score"]
