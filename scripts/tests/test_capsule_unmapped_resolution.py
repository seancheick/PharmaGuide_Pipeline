import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from constants import SKIP_REASON_BLEND_HEADER_NO_DOSE
from enrich_supplements_v3 import SupplementEnricherV3
from enhanced_normalizer import EnhancedDSLDNormalizer


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3()


@pytest.fixture
def normalizer():
    return EnhancedDSLDNormalizer()


class TestCapsuleRoutingRegressions:
    def test_preticx_branded_token_fallback_resolves_xos(self, enricher):
        quality_map = enricher.databases["ingredient_quality_map"]

        match = enricher._match_quality_map(
            "PreticX Xylooligosacharides",
            "PreticX Xylooligosacharides",
            quality_map,
            branded_token="PreticX",
        )

        assert match is not None
        assert match["canonical_id"] == "prebiotics"
        assert match["form_id"] == "xylooligosaccharides (XOS)"
        assert match["matched_alias"] == "preticx"

    def test_proprietary_parent_with_nested_children_and_no_dose_is_skipped(self, enricher):
        ingredient = {
            "name": "BreastHealth Plus",
            "standardName": "BreastHealth Plus",
            "ingredientGroup": "Header",
            "quantity": 0.0,
            "unit": "NP",
            "proprietaryBlend": True,
            "nestedIngredients": [
                {"name": "HMRlignan"},
                {"name": "Green Tea"},
            ],
        }

        skip_reason = enricher._should_skip_from_scoring(
            ingredient,
            enricher.databases["ingredient_quality_map"],
            enricher.databases["standardized_botanicals"],
        )

        assert skip_reason == SKIP_REASON_BLEND_HEADER_NO_DOSE

    def test_whole_adrenal_is_recognized_non_scorable(self, enricher):
        recognition = enricher._is_recognized_non_scorable("whole Adrenal", "whole Adrenal")

        assert recognition is not None
        assert recognition["recognition_source"] == "other_ingredients"
        assert recognition["matched_entry_name"] == "Whole Adrenal"

    def test_pepsin_pure_is_recognized_non_scorable(self, enricher):
        recognition = enricher._is_recognized_non_scorable("Pepsin, Pure", "Pepsin, Pure")

        assert recognition is not None
        assert recognition["recognition_source"] == "other_ingredients"
        assert recognition["matched_entry_name"] == "Pepsin"

    def test_rice_bran_oil_is_recognized_non_scorable(self, enricher):
        recognition = enricher._is_recognized_non_scorable("Rice Bran Oil", "Rice Bran Oil")

        assert recognition is not None
        assert recognition["recognition_source"] == "other_ingredients"
        assert recognition["matched_entry_name"] == "Rice Bran Oil"

    def test_natural_mint_oil_is_recognized_non_scorable(self, enricher):
        recognition = enricher._is_recognized_non_scorable("natural Mint Oil", "natural Mint Oil")

        assert recognition is not None
        assert recognition["recognition_source"] == "other_ingredients"
        assert recognition["matched_entry_name"] in {"Natural Mint Flavor", "Natural Mint Flavors"}


class TestCapsuleAliasCoverage:
    @pytest.mark.parametrize(
        ("label", "expected_canonical", "expected_form"),
        [
            ("Flax (Linum usitatissimum) powder", "flaxseed", "flaxseed meal/powder"),
            ("Black Currant (Ribes nigrum) oil", "black_currant", "black currant extract"),
            ("Perilla Seed Extract", "perilla_oil", "perilla seed oil"),
            ("Grape Whole Fruit Extract", "grape_seed_extract", "whole grape extract"),
            ("Mixed Tocotrienols/Tocopherols", "vitamin_e", "tocotrienols"),
            ("BioEcolians A-Glucooligosaccharide", "prebiotics", "alpha-glucooligosaccharides (alpha-GOS)"),
        ],
    )
    def test_capsule_label_maps_to_expected_target(self, enricher, label, expected_canonical, expected_form):
        quality_map = enricher.databases["ingredient_quality_map"]

        match = enricher._match_quality_map(label, label, quality_map)

        assert match is not None
        assert match["canonical_id"] == expected_canonical
        assert match["form_id"] == expected_form


class TestCapsuleStructuralRows:
    def test_gelatin_caplique_capsule_is_treated_as_header(self, normalizer):
        assert normalizer._is_label_header("Gelatin Caplique Capsule") is True
