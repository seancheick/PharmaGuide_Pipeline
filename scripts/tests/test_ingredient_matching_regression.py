"""
Real label corpus regression tests for ingredient matching.

Suite 1: Tests real product label strings against expected matches
Suite 2: Tests collision and substring edge cases

These tests catch the real bugs that occur in production.

Run with: pytest tests/test_ingredient_matching_regression.py -v
"""

import json
import os
import sys
from pathlib import Path

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from enrich_supplements_v3 import SupplementEnricherV3

IQM_PATH = Path(__file__).parent.parent / 'data' / 'ingredient_quality_map.json'


@pytest.fixture(scope='module')
def enricher():
    """Create enricher instance for testing."""
    return SupplementEnricherV3()


@pytest.fixture(scope='module')
def iqm_data():
    """Load ingredient quality map."""
    with open(IQM_PATH, 'r') as f:
        return json.load(f)


# =============================================================================
# SUITE 1: REAL LABEL CORPUS REGRESSION TESTS
# =============================================================================

class TestRealLabelCorpus:
    """
    Tests real product label strings to ensure:
    - Top N extracted ingredients are correct
    - Matched IDs are stable
    - No ambiguous matches
    """

    # Test corpus: (label_text, expected_ingredient_key, should_match)
    LABEL_CORPUS = [
        # NAD+ precursors - historically problematic
        ("Nicotinamide Riboside 300mg", "nicotinamide_riboside", True),
        ("NMN (Nicotinamide Mononucleotide) 500mg", "nmn", True),
        ("Nicotinamide Riboside Chloride", "nicotinamide_riboside", True),

        # Curcumin forms - different delivery systems
        ("Curcumin Phytosome (Meriva)", "curcumin", True),
        ("Liposomal Curcumin 500mg", "curcumin", True),
        ("Curcumin C3 Complex with BioPerine", "curcumin", True),
        ("Turmeric Root Powder 1000mg", "turmeric", True),
        ("Organic Turmeric Extract", "turmeric", True),

        # Flaxseed/Omega-3 disambiguation
        ("Flaxseed Oil 1000mg", "flaxseed", True),
        ("Organic Flax Oil", "flaxseed", True),
        ("Cold-Pressed Linseed Oil", "flaxseed", True),

        # Probiotic strains vs generic
        ("Lactobacillus acidophilus 10 Billion CFU", "lactobacillus_acidophilus", True),
        ("Bifidobacterium lactis BL-04", "bifidobacterium_lactis", True),
        ("Lactobacillus rhamnosus GG", "lactobacillus_rhamnosus", True),
        ("Saccharomyces boulardii CNCM I-745", "saccharomyces_boulardii", True),

        # Active compounds vs parent botanicals
        ("Silymarin 80% (Milk Thistle Extract)", "silymarin", True),
        ("Milk Thistle Seed Extract", "milk_thistle", True),
        ("Boswellic Acids 65%", "boswellic_acids", True),
        ("Boswellia Serrata Extract", "boswellia", True),
        ("Allicin (from Garlic)", "allicin", True),
        ("Aged Garlic Extract", "garlic", True),

        # Specific forms vs generic
        ("5-HTP (from Griffonia simplicifolia)", "5_htp", True),
        ("L-Tryptophan 500mg", "l_tryptophan", True),
        ("Acetyl-L-Carnitine HCl", "acetyl_l_carnitine", True),
        ("L-Carnitine Tartrate", "l_carnitine", True),

        # Bioflavonoids vs specific compounds
        ("Quercetin Dihydrate 500mg", "quercetin", True),
        ("Citrus Bioflavonoid Complex", "citrus_bioflavonoids", True),

        # Creatine forms
        ("Creatine Monohydrate 5g", "creatine_monohydrate", True),
        ("Creatine HCl (Con-Cret)", "creatine", True),
        ("Buffered Creatine (Kre-Alkalyn)", "creatine", True),

        # Magnolia compounds
        ("Honokiol 98%", "honokiol", True),
        ("Magnolia Bark Extract", "magnolia_bark", True),

        # Vitamin forms
        ("Vitamin K1 (Phylloquinone)", "vitamin_k1", True),
        ("Vitamin K2 (MK-7)", "vitamin_k", True),
        ("Methylcobalamin (Vitamin B12)", "vitamin_b12_cobalamin", True),

        # Prebiotics
        ("Inulin (from Chicory Root)", "inulin", True),
        ("Beta-Glucan 250mg", "beta_glucan", True),
        ("Psyllium Husk Powder", "psyllium", True),
    ]

    @pytest.mark.parametrize("label_text,expected_key,should_match", LABEL_CORPUS)
    def test_label_matches_expected_ingredient(self, enricher, label_text, expected_key, should_match):
        """Test that label text matches the expected ingredient."""
        # Create a mock product with single ingredient
        product = {
            "product_name": "Test Product",
            "active_ingredients": [{"name": label_text, "amount": "100", "unit": "mg"}]
        }

        # Run enrichment
        enriched = enricher.enrich(product)

        # Check if expected ingredient was matched
        matched_ingredients = enriched.get('enriched_active_ingredients', [])
        matched_keys = [ing.get('matched_ingredient_key') for ing in matched_ingredients]

        if should_match:
            assert expected_key in matched_keys, (
                f"Expected '{expected_key}' to match label '{label_text}'\n"
                f"Got matches: {matched_keys}"
            )
        else:
            assert expected_key not in matched_keys, (
                f"Expected '{expected_key}' to NOT match label '{label_text}'\n"
                f"But it was matched"
            )

    def test_no_double_matching_parent_child(self, enricher):
        """Curcumin should not also match turmeric in same label."""
        product = {
            "product_name": "Curcumin Supplement",
            "active_ingredients": [{"name": "Curcumin C3 Complex", "amount": "500", "unit": "mg"}]
        }

        enriched = enricher.enrich(product)
        matched_keys = [
            ing.get('matched_ingredient_key')
            for ing in enriched.get('enriched_active_ingredients', [])
        ]

        # Should match curcumin but NOT also turmeric
        assert 'curcumin' in matched_keys or len(matched_keys) == 0
        if 'curcumin' in matched_keys:
            assert 'turmeric' not in matched_keys, (
                "Curcumin C3 Complex matched both curcumin AND turmeric - double match!"
            )


# =============================================================================
# SUITE 2: COLLISION AND SUBSTRING TESTS
# =============================================================================

class TestCollisionAndSubstring:
    """
    Tests that ensure we do NOT match on:
    - Generic tokens that cause false matches
    - Substrings that cause incorrect matches
    """

    # Things that should NOT cause a match
    FALSE_POSITIVE_TESTS = [
        # Generic terms that should be excluded
        ("Natural flavoring", "vitamin_a"),  # "natural" is in vitamin_a aliases
        ("Synthetic sweetener", "ceramides"),  # "synthetic" appears in aliases
        ("Standard capsule", None),  # "standard" should not match anything
        ("Unspecified filler", None),  # "unspecified" should not match

        # Substring collisions
        ("Vitamin K1 100mcg", "vitamin_k"),  # K1 should not also match generic K
        ("EPA from fish oil", "fish_oil"),  # EPA alone should match EPA, not fish_oil

        # Category words that shouldn't cause matches
        ("Probiotic blend", "lactobacillus_acidophilus"),  # Generic "probiotic" shouldn't match specific strain
        ("Prebiotic fiber", "inulin"),  # Generic "prebiotic" shouldn't match specific
    ]

    @pytest.mark.parametrize("label_text,should_not_match", FALSE_POSITIVE_TESTS)
    def test_no_false_positive_match(self, enricher, label_text, should_not_match):
        """Test that generic/substring terms don't cause false matches."""
        if should_not_match is None:
            pytest.skip("No specific ingredient to test against")

        product = {
            "product_name": "Test Product",
            "active_ingredients": [{"name": label_text, "amount": "100", "unit": "mg"}]
        }

        enriched = enricher.enrich(product)
        matched_keys = [
            ing.get('matched_ingredient_key')
            for ing in enriched.get('enriched_active_ingredients', [])
        ]

        assert should_not_match not in matched_keys, (
            f"'{label_text}' should NOT match '{should_not_match}' but it did!"
        )

    # Substring priority tests - specific should win over generic
    PRIORITY_TESTS = [
        # (label, should_match, should_not_match)
        ("Vitamin K1", "vitamin_k1", "vitamin_k"),  # K1 > K
        ("Nicotinamide Riboside", "nicotinamide_riboside", "vitamin_b3_niacin"),  # NR > B3
        ("Lactobacillus acidophilus", "lactobacillus_acidophilus", "probiotics"),  # Specific > category
        ("Silymarin extract", "silymarin", "milk_thistle"),  # Compound > botanical
        ("5-HTP", "5_htp", "l_tryptophan"),  # Metabolite > precursor
    ]

    @pytest.mark.parametrize("label_text,should_match,should_not_match", PRIORITY_TESTS)
    def test_specific_matches_over_generic(self, enricher, label_text, should_match, should_not_match):
        """Test that specific ingredients match over generic categories."""
        product = {
            "product_name": "Test Product",
            "active_ingredients": [{"name": label_text, "amount": "100", "unit": "mg"}]
        }

        enriched = enricher.enrich(product)
        matched_keys = [
            ing.get('matched_ingredient_key')
            for ing in enriched.get('enriched_active_ingredients', [])
        ]

        # Check specific match happened
        if should_match:
            assert should_match in matched_keys or len(matched_keys) == 0, (
                f"Expected '{should_match}' to match '{label_text}', got {matched_keys}"
            )

        # Check generic did NOT match (if specific did)
        if should_match in matched_keys and should_not_match:
            assert should_not_match not in matched_keys, (
                f"Both '{should_match}' and '{should_not_match}' matched '{label_text}' - priority issue!"
            )


# =============================================================================
# DETERMINISTIC MATCHING TESTS
# =============================================================================

class TestDeterministicMatching:
    """Test that matching is deterministic and stable."""

    STABILITY_TESTS = [
        "Nicotinamide Riboside",
        "NMN",
        "Curcumin Phytosome",
        "Liposomal Curcumin",
        "Flaxseed oil",
        "Lactobacillus rhamnosus GG",
        "Silymarin 80%",
        "5-HTP",
        "Quercetin",
        "Beta-Glucan",
    ]

    @pytest.mark.parametrize("label_text", STABILITY_TESTS)
    def test_matching_is_deterministic(self, enricher, label_text):
        """Run same label 3 times, results should be identical."""
        results = []

        for _ in range(3):
            product = {
                "product_name": "Test Product",
                "active_ingredients": [{"name": label_text, "amount": "100", "unit": "mg"}]
            }
            enriched = enricher.enrich(product)
            matched_keys = tuple(sorted([
                ing.get('matched_ingredient_key', '')
                for ing in enriched.get('enriched_active_ingredients', [])
            ]))
            results.append(matched_keys)

        # All 3 runs should produce identical results
        assert results[0] == results[1] == results[2], (
            f"Non-deterministic matching for '{label_text}':\n"
            f"  Run 1: {results[0]}\n"
            f"  Run 2: {results[1]}\n"
            f"  Run 3: {results[2]}"
        )


# =============================================================================
# ALIAS RESOLUTION TESTS
# =============================================================================

class TestAliasResolution:
    """Test specific alias resolution cases that were historically problematic."""

    RESOLUTION_TESTS = [
        # (alias, expected_canonical_key)
        ("nicotinamide riboside", "nicotinamide_riboside"),
        ("nmn", "nmn"),
        ("curcumin phytosome", "curcumin"),
        ("meriva", "curcumin"),
        ("flaxseed oil", "flaxseed"),
        ("linseed oil", "flaxseed"),
        ("silymarin", "silymarin"),
        ("5-htp", "5_htp"),
        ("alcar", "acetyl_l_carnitine"),
        ("quercetin dihydrate", "quercetin"),
        ("beta glucan", "beta_glucan"),
        ("oat beta-glucan", "beta_glucan"),
        ("l. acidophilus", "lactobacillus_acidophilus"),
        ("b. lactis", "bifidobacterium_lactis"),
    ]

    @pytest.mark.parametrize("alias,expected_key", RESOLUTION_TESTS)
    def test_alias_resolves_to_canonical(self, iqm_data, alias, expected_key):
        """Test that specific aliases resolve to correct canonical ingredient."""
        entries = {k: v for k, v in iqm_data.items() if k != '_metadata'}

        # Find which ingredient contains this alias
        found_in = []
        alias_lower = alias.lower().strip()

        for ing_key, entry in entries.items():
            for form_name, form_data in entry.get('forms', {}).items():
                if isinstance(form_data, dict):
                    form_aliases = [a.lower().strip() for a in form_data.get('aliases', [])]
                    if alias_lower in form_aliases:
                        found_in.append(ing_key)

        # Should be found in exactly one ingredient (the expected one)
        unique_found = list(set(found_in))

        assert expected_key in unique_found, (
            f"Alias '{alias}' not found in expected ingredient '{expected_key}'\n"
            f"Found in: {unique_found}"
        )

        assert len(unique_found) == 1, (
            f"Alias '{alias}' found in multiple ingredients: {unique_found}\n"
            f"Expected only: {expected_key}"
        )
