"""
Scoring Invariants Regression Tests

Verifies three hard invariants that must hold after each pipeline run:
  1. fuzzy && found=True must never produce is_trusted_manufacturer=True
  2. Botanicals with DSLD standardName="natural colors" must score as actives
  3. Siddha Ghruta / fatty-acid-profile label phrases must be excluded
"""

import json
import os
import pytest
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from enrich_supplements_v3 import SupplementEnricherV3

_DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data'))


# ---------------------------------------------------------------------------
# 1. Fuzzy manufacturer / found=True invariant
# ---------------------------------------------------------------------------

class TestFuzzyManufacturerFoundInvariant:
    """
    Regression: fuzzy match_type must never set is_trusted_manufacturer=True.

    The invariant: is_trusted_manufacturer=True only when match_type="exact".
    Fuzzy matches may set found=True but must not grant trusted status.
    This prevents wrong manufacturer attributions from inflating quality scores.
    """

    @pytest.fixture
    def enricher(self):
        return SupplementEnricherV3()

    def _base_enriched(self, top_manufacturer):
        return {
            "delivery_data": {},
            "absorption_data": {},
            "formulation_data": {},
            "contaminant_data": {},
            "compliance_data": {},
            "certification_data": {},
            "proprietary_data": {},
            "evidence_data": {},
            "ingredient_quality_data": {},
            "manufacturer_data": {
                "top_manufacturer": top_manufacturer,
                "bonus_features": {},
                "country_of_origin": {},
            },
        }

    def test_fuzzy_match_is_not_trusted(self, enricher):
        """fuzzy match_type does NOT grant is_trusted_manufacturer=True."""
        enriched = self._base_enriched(
            {"found": True, "match_type": "fuzzy",
             "similarity_score": 0.92, "name": "Example Supplement Co"}
        )
        enricher._project_scoring_fields(enriched)
        assert enriched["is_trusted_manufacturer"] is False, (
            "fuzzy match must never grant trusted manufacturer status"
        )

    def test_exact_match_is_trusted(self, enricher):
        """exact match_type grants is_trusted_manufacturer=True."""
        enriched = self._base_enriched(
            {"found": True, "match_type": "exact", "name": "Thorne Research"}
        )
        enricher._project_scoring_fields(enriched)
        assert enriched["is_trusted_manufacturer"] is True

    def test_not_found_is_not_trusted(self, enricher):
        """found=False means is_trusted_manufacturer=False regardless."""
        enriched = self._base_enriched({"found": False})
        enricher._project_scoring_fields(enriched)
        assert enriched["is_trusted_manufacturer"] is False


# ---------------------------------------------------------------------------
# 2. natural-colors standardName botanical case
# ---------------------------------------------------------------------------

class TestNaturalColorsStdNameBotanicalCase:
    """
    Regression: botanicals with DSLD standardName="natural colors" must score as actives.

    DSLD sometimes assigns standardName="natural colors" to botanical actives
    (e.g., Sambucus Black Elderberry in product 306642). The enricher must NOT
    classify these as recognized_non_scorable just because std_name is a colorant
    category descriptor. The _is_recognized_non_scorable guard must exclude
    std_name from candidates when it is in EXCIPIENT_NEVER_PROMOTE.
    """

    @pytest.fixture
    def enricher(self):
        return SupplementEnricherV3()

    @pytest.fixture
    def iqm(self):
        with open(os.path.join(_DATA_DIR, 'ingredient_quality_map.json'),
                  encoding='utf-8') as f:
            return json.load(f)

    @pytest.fixture
    def botanicals(self):
        bot_path = os.path.join(_DATA_DIR, 'standardized_botanicals.json')
        if not os.path.exists(bot_path):
            return {}
        with open(bot_path, encoding='utf-8') as f:
            return json.load(f)

    def test_elderberry_with_natural_colors_stdname_not_non_scorable(self, enricher):
        """Elderberry with standardName='natural colors' is NOT recognized as non-scorable."""
        result = enricher._is_recognized_non_scorable(
            "Sambucus Black Elderberry", "natural colors"
        )
        assert result is None, (
            f"Elderberry with std_name='natural colors' was incorrectly classified as "
            f"recognized_non_scorable: {result}. std_name must not contaminate "
            "candidates when it is a known excipient/category descriptor."
        )

    def test_elderberry_fruit_extract_with_natural_colors_stdname(self, enricher):
        """Elderberry Fruit Extract with standardName='natural colors' is NOT non-scorable."""
        result = enricher._is_recognized_non_scorable(
            "Sambucus Black Elderberry Fruit Extract", "natural colors"
        )
        assert result is None, (
            f"Elderberry extract with std_name='natural colors' was incorrectly "
            f"classified: {result}"
        )

    def test_actual_natural_colors_ingredient_is_non_scorable(self, enricher):
        """An ingredient literally named 'natural colors' IS recognized as non-scorable."""
        result = enricher._is_recognized_non_scorable("natural colors", "natural colors")
        assert result is not None, (
            "An ingredient literally named 'natural colors' should be "
            "recognized as non-scorable"
        )

    def test_elderberry_maps_to_iqm_not_skipped(self, enricher, iqm, botanicals):
        """Elderberry with standardName='natural colors' resolves as known-therapeutic."""
        result = enricher._is_known_therapeutic(
            "Sambucus Black Elderberry", "natural colors", iqm, botanicals
        )
        assert result is True, (
            "Elderberry should be recognized as a known therapeutic even when "
            "standardName='natural colors', preventing false "
            "recognized_non_scorable classification"
        )


# ---------------------------------------------------------------------------
# 3. Siddha Ghruta / fatty-acid-profile descriptor exclusion
# ---------------------------------------------------------------------------

class TestSiddhaDescriptorExclusion:
    """
    Regression: Siddha Ghruta processing descriptors must be excluded from
    ingredient processing.

    DSLD Ayurvedic products sometimes include processing notes like
    'Processed by the method of Siddha Ghruta in' as pseudo-ingredients.
    These must be excluded via EXCLUDED_LABEL_PHRASES so they do not inflate
    the unmapped ingredient count or trigger coverage failures.
    """

    @pytest.fixture
    def enricher(self):
        return SupplementEnricherV3()

    def test_siddha_ghruta_phrase_is_excluded(self, enricher):
        """'Processed by the method of Siddha Ghruta in' is treated as excluded label text."""
        phrases = [
            "Processed by the method of Siddha Ghruta in",
            "Processed by the method of Siddha Ghruta",
            "Processed by Siddha Ghruta",
        ]
        for phrase in phrases:
            result = enricher._excluded_text_reason(phrase)
            assert result is not None, (
                f"Siddha Ghruta phrase not excluded: {phrase!r}. "
                "Add it to EXCLUDED_LABEL_PHRASES in constants.py."
            )

    def test_fatty_acid_profile_header_is_excluded(self, enricher):
        """'Typical Fatty Acid Profile' and similar section headers are excluded."""
        headers = [
            "Typical Fatty Acid Profile",
            "Fatty Acid Profile",
            "Amino Acid Profile",
        ]
        for header in headers:
            result = enricher._excluded_text_reason(header)
            assert result is not None, (
                f"Fatty/amino acid profile header not excluded: {header!r}. "
                "Add it to EXCLUDED_LABEL_PHRASES in constants.py."
            )

    def test_siddha_ghruta_not_in_unmapped(self, enricher):
        """A product with a Siddha Ghruta note has it excluded, not counted as unmapped."""
        product = {
            "id": "test_siddha",
            "dsld_id": "test_siddha",
            "fullName": "Ayurvedic Test Product",
            "brandName": "Test Brand",
            "activeIngredients": [
                {
                    "name": "Processed by the method of Siddha Ghruta in",
                    "standardName": "Processed by the method of Siddha Ghruta in",
                    "quantity": None,
                    "unit": "",
                    "forms": [],
                    "ingredientGroup": "",
                    "normalized_key": "processed_by_method",
                    "raw_source_text": "Processed by the method of Siddha Ghruta in",
                }
            ],
            "inactiveIngredients": [],
            "contacts": [],
            "events": [],
        }

        enriched, _ = enricher.enrich_product(product)
        unmatched = enriched.get("unmatched_ingredients", [])

        siddha_phrase = "Processed by the method of Siddha Ghruta in"
        assert siddha_phrase not in unmatched, (
            "Siddha Ghruta processing note should be excluded, not counted as unmapped"
        )


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
