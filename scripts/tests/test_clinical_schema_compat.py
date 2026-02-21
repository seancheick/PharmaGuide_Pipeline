import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from enrich_supplements_v3 import SupplementEnricherV3
from score_supplements import SupplementScorer


class TestClinicalSchemaCompatibility:
    @pytest.fixture
    def enricher(self):
        return SupplementEnricherV3()

    @pytest.fixture
    def scorer(self):
        return SupplementScorer()

    def test_enrichment_passthroughs_optional_clinical_fields(self, enricher):
        enricher.databases["backed_clinical_studies"] = {
            "backed_clinical_studies": [
                {
                    "id": "INGR_TEST_DOSING",
                    "standard_name": "Test Ingredient",
                    "aliases": ["test ingredient alias"],
                    "evidence_level": "ingredient-human",
                    "study_type": "rct_single",
                    "min_clinical_dose": 500,
                    "dose_unit": "mg",
                    "typical_effective_dose": "500-1000 mg/day",
                    "dose_range": {"min": 500, "max": 1000, "unit": "mg"},
                    "base_points": 4,
                    "multiplier": 0.65,
                    "computed_score": 2.6,
                }
            ]
        }

        product = {
            "activeIngredients": [
                {"name": "Test Ingredient", "standardName": "Test Ingredient", "quantity": 600, "unit": "mg"}
            ]
        }

        result = enricher._collect_evidence_data(product)
        assert result["match_count"] == 1
        match = result["clinical_matches"][0]
        assert match["min_clinical_dose"] == 500
        assert match["dose_unit"] == "mg"
        assert match["typical_effective_dose"] == "500-1000 mg/day"
        assert match["dose_range"]["max"] == 1000
        assert match["base_points"] == 4
        assert match["multiplier"] == 0.65
        assert match["computed_score"] == 2.6

    def test_enrichment_respects_exclude_aliases(self, enricher):
        enricher.databases["backed_clinical_studies"] = {
            "backed_clinical_studies": [
                {
                    "id": "INGR_MAGNESIUM_GENERIC",
                    "standard_name": "Magnesium (Generic)",
                    "aliases": ["magnesium"],
                    "aliases_normalized": ["magnesium"],
                    "exclude_aliases": ["magnesium stearate"],
                    "evidence_level": "ingredient-human",
                    "study_type": "rct_single",
                }
            ]
        }

        product = {
            "activeIngredients": [
                {"name": "Magnesium Stearate", "standardName": "Magnesium"}
            ]
        }

        result = enricher._collect_evidence_data(product)
        assert result["match_count"] == 0
        assert result["clinical_matches"] == []

    def test_scorer_uses_optional_base_points_and_multiplier(self, scorer):
        scorer.config.setdefault("section_C_evidence_research", {})
        scorer.config["section_C_evidence_research"]["cap_per_ingredient"] = 10
        scorer.config["section_C_evidence_research"]["cap_total"] = 20

        product = {
            "activeIngredients": [{"name": "Test", "quantity": 1, "unit": "mg"}],
            "evidence_data": {
                "clinical_matches": [
                    {
                        "id": "E_TEST",
                        "standard_name": "Test",
                        "study_type": "rct_single",
                        "evidence_level": "ingredient-human",
                        "base_points": 7.0,
                        "multiplier": 1.0,
                    }
                ]
            },
        }
        section_c = scorer._score_section_c(product, [])
        assert section_c["score"] == pytest.approx(7.0)
        assert section_c["max"] == pytest.approx(20.0)
