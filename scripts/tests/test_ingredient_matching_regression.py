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
        ("Silymarin 80% (Milk Thistle Extract)", "milk_thistle", True),
        ("Milk Thistle Seed Extract", "milk_thistle", True),
        ("Boswellic Acids 65%", "boswellia", True),
        ("Boswellia Serrata Extract", "boswellia", True),
        ("Allicin (from Garlic)", "garlic", True),
        ("Aged Garlic Extract", "garlic", True),

        # Specific forms vs generic
        ("5-HTP (from Griffonia simplicifolia)", "5_htp", True),
        ("L-Tryptophan 500mg", "l_tryptophan", True),
        ("Acetyl-L-Carnitine HCl", "l_carnitine", True),
        ("L-Carnitine Tartrate", "l_carnitine", True),

        # Bioflavonoids vs specific compounds
        ("Quercetin Dihydrate 500mg", "quercetin", True),
        ("Citrus Bioflavonoid Complex", "citrus_bioflavonoids", True),

        # Creatine forms
        ("Creatine Monohydrate 5g", "creatine_monohydrate", True),
        ("Creatine HCl (Con-Cret)", "creatine_monohydrate", True),
        ("Buffered Creatine (Kre-Alkalyn)", "creatine_monohydrate", True),

        # Magnolia compounds
        ("Honokiol 98%", "magnolia_bark", True),
        ("Magnolia Bark Extract", "magnolia_bark", True),

        # Vitamin forms
        ("Vitamin K1 (Phylloquinone)", "vitamin_k1", True),
        ("Vitamin K2 (MK-7)", "vitamin_k2", True),
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
        # Use correct field names expected by enricher (camelCase)
        product = {
            "id": "TEST_001",
            "product_name": "Test Product",
            "activeIngredients": [{"name": label_text, "quantity": 100, "unit": "mg"}]
        }

        # Run enrichment (returns tuple of enriched_product, issues)
        enriched, issues = enricher.enrich_product(product)

        # Check if expected ingredient was matched
        # Scorable ingredients are in ingredient_quality_data.ingredients_scorable
        quality_data = enriched.get('ingredient_quality_data', {})
        matched_ingredients = quality_data.get('ingredients_scorable', [])
        matched_keys = [ing.get('canonical_id') for ing in matched_ingredients if ing.get('canonical_id')]

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
            "id": "TEST_002",
            "product_name": "Curcumin Supplement",
            "activeIngredients": [{"name": "Curcumin C3 Complex", "quantity": 500, "unit": "mg"}]
        }

        enriched, issues = enricher.enrich_product(product)
        quality_data = enriched.get('ingredient_quality_data', {})
        matched_keys = [
            ing.get('canonical_id')
            for ing in quality_data.get('ingredients_scorable', [])
            if ing.get('canonical_id')
        ]

        # Should match curcumin but NOT also turmeric
        assert 'curcumin' in matched_keys or len(matched_keys) == 0
        if 'curcumin' in matched_keys:
            assert 'turmeric' not in matched_keys, (
                "Curcumin C3 Complex matched both curcumin AND turmeric - double match!"
            )

    def test_liposomal_curcumin_has_one_owner_and_keeps_reviewed_form_score(
        self,
        enricher,
        iqm_data,
    ):
        assert "liposomal curcumin" in iqm_data["curcumin"]["forms"]
        assert "liposomal curcumin" not in iqm_data["turmeric"]["forms"]

        product = {
            "id": "TEST_LIPOSOMAL_CURCUMIN",
            "product_name": "Liposomal Curcumin",
            "activeIngredients": [
                {
                    "name": "Liposomal Curcumin",
                    "quantity": 500,
                    "unit": "mg",
                }
            ],
        }

        enriched, _ = enricher.enrich_product(product)
        rows = enriched["ingredient_quality_data"]["ingredients_scorable"]
        assert len(rows) == 1
        assert rows[0]["canonical_id"] == "curcumin"
        assert rows[0]["matched_form"] == "liposomal curcumin"
        assert rows[0]["bio_score"] == 7


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
        ("EPA from fish oil", "fish_oil"),  # EPA alone should match EPA, not fish_oil

        # Category words that shouldn't cause matches
        ("Probiotic blend", "lactobacillus_acidophilus"),  # Generic "probiotic" shouldn't match specific strain
        ("Prebiotic fiber", "inulin"),  # Generic "prebiotic" shouldn't match specific
    ]

    @pytest.mark.parametrize("label_text,should_not_match", FALSE_POSITIVE_TESTS)
    def test_no_false_positive_match(self, enricher, label_text, should_not_match):
        """Test that generic/substring terms don't cause false matches."""
        product = {
            "id": "TEST_FP",
            "product_name": "Test Product",
            "activeIngredients": [{"name": label_text, "quantity": 100, "unit": "mg"}]
        }

        enriched, issues = enricher.enrich_product(product)
        quality_data = enriched.get('ingredient_quality_data', {})
        matched_keys = [
            ing.get('canonical_id')
            for ing in quality_data.get('ingredients_scorable', [])
            if ing.get('canonical_id')
        ]

        if should_not_match is None:
            assert len(matched_keys) == 0, (
                f"'{label_text}' should not map to any scorable canonical_id, got {matched_keys}"
            )
        else:
            assert should_not_match not in matched_keys, (
                f"'{label_text}' should NOT match '{should_not_match}' but it did!"
            )

    # Substring priority tests - specific should win over generic
    PRIORITY_TESTS = [
        # (label, should_match, should_not_match)
        ("Vitamin K1", "vitamin_k1", "vitamin_a"),
        ("Nicotinamide Riboside", "nicotinamide_riboside", "vitamin_b3_niacin"),  # NR > B3
        ("Lactobacillus acidophilus", "lactobacillus_acidophilus", "probiotics"),  # Specific > category
        ("Silymarin extract", "milk_thistle", "silymarin"),  # silymarin merged into milk_thistle
        ("5-HTP", "5_htp", "l_tryptophan"),  # Metabolite > precursor
    ]

    @pytest.mark.parametrize("label_text,should_match,should_not_match", PRIORITY_TESTS)
    def test_specific_matches_over_generic(self, enricher, label_text, should_match, should_not_match):
        """Test that specific ingredients match over generic categories."""
        product = {
            "id": "TEST_PRIO",
            "product_name": "Test Product",
            "activeIngredients": [{"name": label_text, "quantity": 100, "unit": "mg"}]
        }

        enriched, issues = enricher.enrich_product(product)
        quality_data = enriched.get('ingredient_quality_data', {})
        matched_keys = [
            ing.get('canonical_id')
            for ing in quality_data.get('ingredients_scorable', [])
            if ing.get('canonical_id')
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

    def test_vitamin_k1_keeps_identity_with_explicit_display_group(self, enricher, iqm_data):
        """K1 stays canonical K1 and rolls up only through nutrient_group_id."""
        assert iqm_data["vitamin_k1"].get("nutrient_group_id") == "vitamin_k"
        assert "target_id" not in iqm_data["vitamin_k1"].get("match_rules", {})

        product = {
            "id": "TEST_VITAMIN_K1_TARGET",
            "product_name": "Test K1",
            "activeIngredients": [
                {"name": "Vitamin K1 (Phylloquinone)", "quantity": 100, "unit": "mcg"}
            ],
        }

        enriched, issues = enricher.enrich_product(product)
        quality_data = enriched.get("ingredient_quality_data", {})
        scorable = quality_data.get("ingredients_scorable", [])

        k_rows = [row for row in scorable if row.get("canonical_id") == "vitamin_k1"]
        assert len(k_rows) == 1, f"Expected one vitamin_k1 row, got {scorable}"

        row = k_rows[0]
        assert row.get("canonical_redirect_from") is None
        assert row.get("standard_name") == "Vitamin K1"
        assert row.get("matched_form") == "phylloquinone"
        assert row.get("quantity") == 100
        assert row.get("unit") == "mcg"

    def test_vitamin_k2_menaquinone_7_keeps_mk7_form(self, enricher):
        """A spelled-out MK-7 label should not fall back to generic K2."""
        product = {
            "id": "TEST_VITAMIN_K2_MK7",
            "product_name": "Test K2",
            "activeIngredients": [
                {"name": "Vitamin K2 (Menaquinone-7)", "quantity": 30, "unit": "mcg"}
            ],
        }

        enriched, issues = enricher.enrich_product(product)
        quality_data = enriched.get("ingredient_quality_data", {})
        scorable = quality_data.get("ingredients_scorable", [])

        k_rows = [row for row in scorable if row.get("canonical_id") == "vitamin_k2"]
        assert len(k_rows) == 1, f"Expected one vitamin_k2 row, got {scorable}"

        row = k_rows[0]
        assert row.get("matched_form") == "menaquinone-7 (MK-7)"
        assert row.get("form_id") == "menaquinone-7 (MK-7)"
        assert row.get("bio_score") == 12.0


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

        for i in range(3):
            product = {
                "id": f"TEST_DET_{i}",
                "product_name": "Test Product",
                "activeIngredients": [{"name": label_text, "quantity": 100, "unit": "mg"}]
            }
            enriched, issues = enricher.enrich_product(product)
            quality_data = enriched.get('ingredient_quality_data', {})
            matched_keys = tuple(sorted([
                ing.get('canonical_id', '')
                for ing in quality_data.get('ingredients_scorable', [])
                if ing.get('canonical_id')
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
        ("silymarin", "milk_thistle"),
        ("5-htp", "5_htp"),
        ("alcar", "l_carnitine"),
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


# =============================================================================
# MULTI-FORM MATCHING TESTS
# =============================================================================

class TestMultiFormMatching:
    """
    Tests for multi-form ingredient matching with weighted averaging.

    These tests verify the contract for handling complex labels like:
    - "Vitamin B12 (as adenosylcobalamin and methylcobalamin)"
    - "Vitamin A (as retinyl palmitate and 50% B-carotene)"
    - "Folate (as MAGNAFOLATE® PRO methylfolate [L-5-MTHF Ca])"
    """

    def test_dual_form_uses_average_not_first_only(self, enricher):
        """
        B12 (adenosyl + methyl) should use average of both forms, not first-only.

        Contract: When multiple forms are specified without explicit percentages,
        use equal-weight average of all matched forms' bio_scores.
        """
        label = "Vitamin B12 (as adenosylcobalamin and methylcobalamin)"

        product = {
            "id": "TEST_DUAL",
            "product_name": "Test Dual Form B12",
            "activeIngredients": [{"name": label, "quantity": 1000, "unit": "mcg"}]
        }

        enriched, issues = enricher.enrich_product(product)
        quality_data = enriched.get('ingredient_quality_data', {})
        scorable = quality_data.get('ingredients_scorable', [])

        assert len(scorable) >= 1, "Should have at least one scorable ingredient"

        # Find the B12 entry
        b12_entry = None
        for ing in scorable:
            if ing.get('canonical_id') == 'vitamin_b12_cobalamin':
                b12_entry = ing
                break

        assert b12_entry is not None, "Should match vitamin_b12_cobalamin"

        # Verify multi-form contract
        assert b12_entry.get('form_extraction_used') == True, "Should use form extraction"
        assert b12_entry.get('is_dual_form') == True, "Should be marked as dual form"

        matched_forms = b12_entry.get('matched_forms', [])
        assert len(matched_forms) == 2, f"Should match both forms, got {len(matched_forms)}"

        # Per Dr Pham C2 (2026-04-25): adenosylcobalamin and methylcobalamin
        # downgraded from 14 → 8 (sublingual-only PK premium retained on the
        # 'methylcobalamin sublingual' form). Plain forms now bio=8.
        # Average should be 8.0.
        bio_score = b12_entry.get('bio_score')
        assert bio_score == 8.0, f"Expected bio_score 8.0 (average post-Dr-Pham C2), got {bio_score}"

        # Verify aggregation method
        assert b12_entry.get('aggregation_method') == 'equal', \
            "Should use equal aggregation for dual forms without explicit percentages"

    def test_percent_share_applies_weighting(self, enricher):
        """
        Vitamin A (retinyl palmitate and 50% B-carotene) should apply percentage weighting.

        Contract: When explicit percentages are provided (e.g., "50%"), use weighted
        average. Remaining percentage goes to forms without explicit percentages.
        """
        label = "Vitamin A (as retinyl palmitate and 50% B-carotene)"

        product = {
            "id": "TEST_WEIGHTED",
            "product_name": "Test Weighted Vitamin A",
            "activeIngredients": [{"name": label, "quantity": 5000, "unit": "IU"}]
        }

        enriched, issues = enricher.enrich_product(product)
        quality_data = enriched.get('ingredient_quality_data', {})
        scorable = quality_data.get('ingredients_scorable', [])

        assert len(scorable) >= 1, "Should have at least one scorable ingredient"

        # Find the Vitamin A entry
        vit_a_entry = None
        for ing in scorable:
            if ing.get('canonical_id') == 'vitamin_a':
                vit_a_entry = ing
                break

        assert vit_a_entry is not None, "Should match vitamin_a"

        # Verify multi-form contract
        assert vit_a_entry.get('form_extraction_used') == True, "Should use form extraction"
        assert vit_a_entry.get('is_dual_form') == True, "Should be marked as dual form"

        matched_forms = vit_a_entry.get('matched_forms', [])
        assert len(matched_forms) == 2, f"Should match both forms, got {len(matched_forms)}"

        # retinyl palmitate: bio_score 14, share 0.50
        # beta-carotene from mixed carotenoids: bio_score 7, share 0.50
        #   (beta-carotene is a weak provitamin-A source — poor, variable
        #    conversion to retinol — so it scores well below preformed
        #    retinyl esters; this is the IQM-calibrated value.)
        # Weighted average: (14 * 0.5 + 7 * 0.5) / 1.0 = 10.5
        bio_score = vit_a_entry.get('bio_score')
        assert bio_score == 10.5, f"Expected weighted bio_score 10.5, got {bio_score}"

        # Verify shares were parsed correctly
        for mf in matched_forms:
            assert mf.get('percent_share') == 0.5, \
                f"Each form should have 50% share, got {mf.get('percent_share')}"

    def test_bracket_token_preserved_for_matching(self, enricher):
        """
        Folate (... [L-5-MTHF Ca]) should match correctly even with complex brackets.

        Contract: Bracket tokens like [L-5-MTHF Ca], [P-5-P], [D3] are valuable
        matching signals and must be preserved as match candidates, not stripped.
        """
        label = "Folate [Vitamin B9] (as MAGNAFOLATE® PRO methylfolate [L-5-MTHF Ca])"

        product = {
            "id": "TEST_BRACKET",
            "product_name": "Test Bracket Folate",
            "activeIngredients": [{"name": label, "quantity": 400, "unit": "mcg DFE"}]
        }

        enriched, issues = enricher.enrich_product(product)
        quality_data = enriched.get('ingredient_quality_data', {})
        scorable = quality_data.get('ingredients_scorable', [])

        assert len(scorable) >= 1, "Should have at least one scorable ingredient"

        # Find the Folate entry
        folate_entry = None
        for ing in scorable:
            if ing.get('canonical_id') == 'vitamin_b9_folate':
                folate_entry = ing
                break

        assert folate_entry is not None, "Should match vitamin_b9_folate"

        # Verify form extraction captured bracket tokens
        assert folate_entry.get('form_extraction_used') == True, "Should use form extraction"

        # Should match to the 5-MTHF form (bio_score 14 after B9 cleanup merged
        # the duplicate "5-MTHF (L-methylfolate)" into the base form)
        form_id = folate_entry.get('form_id')
        assert '5-MTHF' in form_id or 'methylfolate' in form_id.lower(), \
            f"Should match 5-MTHF form, got {form_id}"

        bio_score = folate_entry.get('bio_score')
        assert bio_score == 14.0, f"Expected bio_score 14.0 for 5-MTHF form, got {bio_score}"

        # Verify the extracted_forms captured the bracket token
        extracted = folate_entry.get('extracted_forms', [])
        if extracted:
            # Check that L-5-MTHF Ca was captured as a match candidate
            all_candidates = []
            for ef in extracted:
                all_candidates.extend(ef.get('match_candidates', []))

            bracket_found = any('L-5-MTHF' in c or 'L5MTHF' in c for c in all_candidates)
            assert bracket_found, \
                f"Bracket token 'L-5-MTHF Ca' should be in match candidates: {all_candidates}"

    def test_form_unmapped_when_evidence_but_no_match(self, enricher):
        """
        If form evidence exists but mapping fails, status should be FORM_UNMAPPED.

        Contract: Don't fall back to "unspecified" if the label explicitly provides
        form information that we couldn't match. Mark as FORM_UNMAPPED for database
        expansion tracking.
        """
        # Use a fake form that won't match anything
        label = "Vitamin X (as totally_fake_form_xyz123)"

        quality_map = enricher.databases.get('ingredient_quality_map', {})
        result = enricher._match_quality_map(label, label, quality_map)

        # Should return FORM_UNMAPPED, not None or unspecified match
        assert result is not None, "Should return result (not None)"
        assert result.get('match_status') == 'FORM_UNMAPPED', \
            f"Should be FORM_UNMAPPED when form evidence exists but no match, got {result.get('match_status')}"
        assert result.get('has_form_evidence') == True, "Should flag form evidence exists"
        assert 'totally_fake_form_xyz123' in str(result.get('unmapped_forms', [])), \
            "Should include unmapped form in result"


def test_synonym_forms_of_one_form_key_are_not_dual(enricher):
    """'Cholecalciferol' and 'Vitamin D3' name one form; only distinct form keys make a dual form."""
    product = {"id": "TEST_SYNONYM_FORMS", "product_name": "Test D3",
               "activeIngredients": [{"name": "Vitamin D (as cholecalciferol and vitamin D3)", "quantity": 25, "unit": "mcg"}]}
    enriched, _ = enricher.enrich_product(product)
    entry = next(i for i in enriched['ingredient_quality_data']['ingredients_scorable']
                 if i.get('canonical_id') == 'vitamin_d')
    assert {f['form_key'] for f in entry['matched_forms']} == {'cholecalciferol (D3)'}
    assert len(entry['matched_forms']) == 2  # both label synonyms stay as evidence
    assert entry['is_dual_form'] is False
    assert entry['additional_forms'] == []


@pytest.mark.parametrize("label,expected", [
    ("Vitamin B12 (as Vitamin B12)", "b12 (unspecified)"),
    ("Vitamin B12 (as cyanocobalamin)", "cyanocobalamin"),
])
def test_generic_b12_form_text_does_not_claim_cyanocobalamin(enricher, label, expected):
    product = {"id": "TEST_B12_FORM", "product_name": "Test B12",
               "activeIngredients": [{"name": label, "quantity": 500, "unit": "mcg"}]}
    enriched, _ = enricher.enrich_product(product)
    entry = next(i for i in enriched['ingredient_quality_data']['ingredients_scorable']
                 if i.get('canonical_id') == 'vitamin_b12_cobalamin')
    assert entry['matched_form'] == expected


def test_natural_vitamin_d_does_not_claim_cholecalciferol(iqm_data):
    # UV-exposed mushroom vitamin D is D2; "natural" does not establish D3.
    forms = iqm_data['vitamin_d']['forms']
    d3 = {a.lower() for a in forms['cholecalciferol (D3)']['aliases']}
    assert not d3 & {'natural vitamin d', 'natural vitamin d supplement', 'natural vit d'}
    assert 'natural vitamin d' in {a.lower() for a in forms['vitamin d (unspecified)']['aliases']}


GENERIC_VITAMIN_C = {'standard vitamin c', 'vitc', 'vitamin c supplement', 'standard vitamin c supplement',
                     'standard vit c', 'vit c supplement', 'vitc supplement', 'vitamin c, natural'}


def test_generic_vitamin_c_names_do_not_claim_ascorbic_acid(iqm_data):
    forms = iqm_data['vitamin_c']['forms']
    assert not {a.lower() for a in forms['ascorbic acid']['aliases']} & GENERIC_VITAMIN_C
    assert GENERIC_VITAMIN_C <= {a.lower() for a in forms['vitamin c (unspecified)']['aliases']}


def test_magnesium_biotinate_is_not_d_biotin(iqm_data):
    # Distinct compound (PubChem CID 139593965, C20H30MgN4O6S2): no reviewed IQM form yet.
    forms = iqm_data['vitamin_b7_biotin']['forms']
    assert all('magnesium biotinate' not in {a.lower() for a in f.get('aliases') or []} for f in forms.values())


def _biotin_row(form):
    # Cleaned-row shape of DSLD 299744's biotin line (portable copy of its fields).
    row = {"name": "Biotin", "standardName": "Vitamin B7 (Biotin)", "canonical_id": "vitamin_b7_biotin",
           "canonical_source_db": "ingredient_quality_map", "mapped": True, "quantity": 10000.0, "unit": "mcg",
           "dailyValue": 33333.0, "raw_source_text": "Biotin", "raw_source_path": "ingredientRows[0]",
           "source_section": "active", "cleaner_row_role": "active_scorable", "score_eligible_by_cleaner": True,
           "dose_class": "therapeutic_mass", "ingredientGroup": "Biotin", "raw_category": "vitamin",
           "hierarchyType": None, "order": 1, "forms": [form]}
    return {"id": "TEST_BIOTINATE", "product_name": "Test Biotin", "activeIngredients": [row]}


def test_declared_but_unresolved_form_is_recorded_not_dropped(enricher):
    # DSLD 299744: "Biotin (as Magnesium Biotinate)". The salt matches no IQM
    # form; the row name still selects the parent, but the declared form is kept
    # as unresolved provenance instead of silently vanishing.
    form = {"name": "Magnesium Biotinate", "order": 1, "prefix": None, "percent": None,
            "category": "mineral", "ingredientGroup": "Magnesium", "uniiCode": None}
    enriched, _ = enricher.enrich_product(_biotin_row(form))
    row = next(r for r in enriched['ingredient_quality_data']['ingredients_scorable']
               if r.get('canonical_id') == 'vitamin_b7_biotin')
    assert row['unresolved_form_tokens'] == ['Magnesium Biotinate']


def test_generic_alias_form_text_is_not_unresolved(enricher):
    form = {"name": "Vitamin B7", "order": 1, "prefix": None, "percent": None,
            "category": "vitamin", "ingredientGroup": "Biotin", "uniiCode": None}
    enriched, _ = enricher.enrich_product(_biotin_row(form))
    row = next(r for r in enriched['ingredient_quality_data']['ingredients_scorable']
               if r.get('canonical_id') == 'vitamin_b7_biotin')
    assert not row.get('unresolved_form_tokens')


def test_animal_based_vitamin_d_does_not_claim_cholecalciferol(iqm_data):
    # Origin is not a compound identifier (animal foods also carry 25(OH)D).
    forms = iqm_data['vitamin_d']['forms']
    animal = {'animal-based vitamin d', 'animal-based vitamin d supplement', 'animal-based vit d'}
    assert not {a.lower() for a in forms['cholecalciferol (D3)']['aliases']} & animal
    assert animal <= {a.lower() for a in forms['vitamin d (unspecified)']['aliases']}


def test_generic_thiamine_names_do_not_claim_thiamine_hydrochloride(iqm_data):
    forms = iqm_data['vitamin_b1_thiamine']['forms']
    generic = {'thiamine supplement', 'vitamin b1 supplement', 'b1 supplement'}
    assert not {a.lower() for a in forms['thiamine hydrochloride']['aliases']} & generic
    assert generic <= {a.lower() for a in forms['vitamin b1 (unspecified)']['aliases']}


def test_generic_b6_names_do_not_claim_pyridoxine_hydrochloride(iqm_data):
    forms = iqm_data['vitamin_b6_pyridoxine']['forms']
    generic = {'standard b6', 'standard b6 supplement', 'vitamin b6 supplement', 'vitamin b-6 supplement'}
    assert not {a.lower() for a in forms['pyridoxine hydrochloride']['aliases']} & generic
    assert generic <= {a.lower() for a in forms['vitamin b6 (unspecified)']['aliases']}


@pytest.mark.parametrize("label,expected", [
    ("Niacin", "vitamin b3 (unspecified)"),               # US label nutrient name, any form
    ("Niacin (as niacinamide)", "niacinamide"),
    ("Niacin (as nicotinic acid)", "nicotinic acid"),
])
def test_niacin_nutrient_name_does_not_claim_nicotinic_acid(enricher, label, expected):
    product = {"id": "TEST_NIACIN", "product_name": "Test B3",
               "activeIngredients": [{"name": label, "quantity": 20, "unit": "mg"}]}
    enriched, _ = enricher.enrich_product(product)
    entry = next(i for i in enriched['ingredient_quality_data']['ingredients_scorable']
                 if i.get('canonical_id') == 'vitamin_b3_niacin')
    assert entry['matched_form'] == expected


@pytest.mark.parametrize("parent,form,unspecified,names", [
    ("vitamin_b3_niacin", "niacinamide", "vitamin b3 (unspecified)",
     {"niacin/niacinamide", "niacinamide/niacin", "non-flushing niacin"}),
    ("vitamin_b5_pantothenic", "calcium pantothenate", "vitamin b5 (unspecified)", {"pantothenate"}),
    ("vitamin_b9_folate", "folic acid", "vitamin b9 (unspecified)", {"folacin"}),
    ("vitamin_b9_folate", "5-methyltetrahydrofolate (5-MTHF)", "vitamin b9 (unspecified)", {"active folate"}),
    ("vitamin_k2", "menaquinone-7 (MK-7)", "vitamin k2 (unspecified subtype)", {"long-chain k2"}),
])
def test_names_that_do_not_establish_the_form_live_on_the_unspecified_form(iqm_data, parent, form, unspecified, names):
    # Mixtures, bare anions, legacy generic terms, marketing and chain-length
    # classes do not identify one compound.
    forms = iqm_data[parent]['forms']
    assert not {a.lower() for a in forms[form]['aliases']} & names
    assert names <= {a.lower() for a in forms[unspecified]['aliases']}


@pytest.mark.parametrize("parent,form,unspecified,names", [
    ("selenium", "selenomethionine", "selenium (unspecified)", {"organic selenium supplement"}),
    ("selenium", "sodium selenite", "selenium (unspecified)", {"selenite", "selenite supplement"}),
    ("selenium", "sodium selenate", "selenium (unspecified)", {"selenate", "selenate supplement"}),
    ("molybdenum", "sodium molybdate", "molybdenum (unspecified)", {"molybdate salt"}),
    ("iodine", "potassium iodide", "iodine (unspecified)", {"iodine tablets", "thyroid iodine"}),
])
def test_trace_mineral_generic_names_live_on_the_unspecified_form(iqm_data, parent, form, unspecified, names):
    forms = iqm_data[parent]['forms']
    assert not {a.lower() for a in forms[form]['aliases']} & names
    assert names <= {a.lower() for a in forms[unspecified]['aliases']}
