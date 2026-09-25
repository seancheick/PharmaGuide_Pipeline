import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from constants import SKIP_REASON_BLEND_HEADER_NO_DOSE, SKIP_REASON_BLEND_HEADER_WITH_WEIGHT
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

        # "PreticX Xylooligosacharides" became a DIRECT IQM alias in d1c0148a, so
        # it now matches directly (matched_alias = the full alias) and no longer
        # exercises the branded-token fallback. Use a non-aliased PreticX variant
        # here so this test keeps covering the FALLBACK path (matched_alias=="preticx").
        match = enricher._match_quality_map(
            "PreticX Fiber",
            "PreticX Fiber",
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

    def test_proprietary_parent_stays_skipped_even_if_db_lookup_would_match(self, enricher, monkeypatch):
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

        monkeypatch.setattr(enricher, "_is_known_therapeutic", lambda *args, **kwargs: True)

        skip_reason = enricher._should_skip_from_scoring(
            ingredient,
            enricher.databases["ingredient_quality_map"],
            enricher.databases["standardized_botanicals"],
        )

        assert skip_reason == SKIP_REASON_BLEND_HEADER_NO_DOSE

    def test_single_child_wrapper_parent_is_skipped_from_scoring(self, enricher):
        ingredient = {
            "name": "SunButyrate Butyrate-Triglyceride",
            "standardName": "SunButyrate Butyrate-Triglyceride",
            "ingredientGroup": "Butyric acid",
            "quantity": 4.5,
            "unit": "Gram(s)",
            "nestedIngredients": [
                {
                    "name": "Butyric Acid",
                    "standardName": "Butyric Acid",
                    "ingredientGroup": "Butyric acid",
                    "quantity": 875.0,
                    "unit": "mg",
                    "isNestedIngredient": True,
                    "parentBlend": "SunButyrate Butyrate-Triglyceride",
                }
            ],
        }

        skip_reason = enricher._should_skip_from_scoring(
            ingredient,
            enricher.databases["ingredient_quality_map"],
            enricher.databases["standardized_botanicals"],
        )

        assert skip_reason == SKIP_REASON_BLEND_HEADER_WITH_WEIGHT

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
            ("Pumpkin (Cucurbita pepo) Oil", "pumpkin_seed_oil", "pumpkin seed oil"),
            ("Rye (Secale cereale) extract", "rye_pollen", "rye pollen extract (unspecified)"),
        ],
    )
    def test_capsule_label_maps_to_expected_target(self, enricher, label, expected_canonical, expected_form):
        quality_map = enricher.databases["ingredient_quality_map"]

        match = enricher._match_quality_map(label, label, quality_map)

        assert match is not None
        assert match["canonical_id"] == expected_canonical
        assert match["form_id"] == expected_form

    def test_hytolive_olive_fruit_extract_prefers_fruit_canonical_with_cleaned_form(self, enricher):
        quality_map = enricher.databases["ingredient_quality_map"]

        match = enricher._match_quality_map(
            "Hytolive Olive (Olea europaea l.) extract",
            "Hytolive",
            quality_map,
            cleaned_forms=[
                {
                    "name": "Hydroxytyrosol",
                    "prefix": "standardized to contain a minimum of",
                    "percent": 7,
                }
            ],
        )

        assert match is not None
        assert match["canonical_id"] == "olive_fruit_extract"
        assert match["form_id"] == "hydroxytyrosol (olive fruit phenolic)"

    @pytest.mark.parametrize(
        ("label", "std_name", "cleaned_forms", "expected_canonical", "expected_form"),
        [
            (
                "Iron",
                "Iron",
                [{"name": "Iron Tris-Glycinate"}],
                "iron",
                "iron bisglycinate",
            ),
            (
                "Iron",
                "Iron",
                [{"name": "Iron Bis-Glycinate"}],
                "iron",
                "iron bisglycinate",
            ),
            (
                "Iron",
                "Iron",
                [{"name": "Iron Ferric Pyrophosphate"}],
                "iron",
                "ferric iron",
            ),
            (
                "Selenium",
                "Selenium",
                [{"name": "Selenium Citrate"}],
                "selenium",
                "selenium citrate",
            ),
            (
                "Berberine Sulfate",
                "Berberine",
                [{"name": "sulfate"}],
                "berberine_supplement",
                "berberine sulfate",
            ),
            (
                "Coenzyme Q10",
                "Coenzyme Q10",
                [{"name": "MicroActive Q10-Cyclodextrin Complex", "prefix": "from"}],
                "coq10",
                "ubiquinone crystal-dispersed",
            ),
            (
                "Protease",
                "Digestive Enzymes",
                [{"name": "Endopeptidase"}, {"name": "Exopeptidase"}],
                "digestive_enzymes",
                "specific enzymes",
            ),
        ],
    )
    def test_form_gap_candidates_map_to_validated_targets(
        self,
        enricher,
        label,
        std_name,
        cleaned_forms,
        expected_canonical,
        expected_form,
    ):
        quality_map = enricher.databases["ingredient_quality_map"]

        match = enricher._match_quality_map(
            label,
            std_name,
            quality_map,
            cleaned_forms=cleaned_forms,
        )

        assert match is not None
        assert match["canonical_id"] == expected_canonical
        assert match["form_id"] == expected_form


class TestCapsuleStructuralRows:
    def test_gelatin_caplique_capsule_is_treated_as_header(self, normalizer):
        assert normalizer._is_label_header("Gelatin Caplique Capsule") is True


class TestFormTokenContext:
    """A label form token no IQM form recognizes is either context (it names
    no form) or a disclosed form IQM lacks, which stays unmapped and holds the
    product. enrich_supplements_v3._form_token_context owns the split."""

    @pytest.mark.parametrize("token, parent_names, expected", [
        ("extract", set(), "preparation"),
        ("Shrimp", set(), "source"),
        ("8-Prenylnaringenin", set(), "marker"),
        ("Selenium Citrate", {"selenium"}, None),
    ])
    def test_context_or_unmapped(self, enricher, token, parent_names, expected):
        form_data = {"raw_form_text": token, "dsld_category": None,
                     "dsld_prefix": None, "dsld_ingredient_group": None}
        assert enricher._form_token_context(form_data, parent_names) == expected
