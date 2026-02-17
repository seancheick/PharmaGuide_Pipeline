"""
Test normalization stability and determinism.

These tests ensure that:
1. normalize_text() produces consistent output
2. make_normalized_key() produces stable keys that never change
3. All normalization functions handle edge cases correctly

CRITICAL: If any golden fixture test fails, it indicates a breaking change
to the normalization contract. This would invalidate all existing normalized_keys
in the pipeline and cause match failures.
"""

import pytest
from normalization import (
    VERSION,
    normalize_text,
    make_normalized_key,
    normalize_company_name,
    normalize_for_skip_matching,
    preprocess_text,
    normalize_exact_text,
    validate_normalized_key,
    clear_caches,
)


class TestNormalizationVersion:
    """Ensure version is tracked for migration purposes."""

    def test_version_exists(self):
        assert VERSION == "1.0.0"


class TestNormalizeTextGoldenFixtures:
    """
    Golden fixtures for normalize_text().
    These MUST NOT change - they define the normalization contract.
    """

    @pytest.fixture(autouse=True)
    def clear_cache(self):
        clear_caches()
        yield
        clear_caches()

    @pytest.mark.parametrize("input_text,expected", [
        # Basic cases
        ("Vitamin B12", "vitamin b12"),
        ("VITAMIN B12", "vitamin b12"),
        ("  Vitamin B12  ", "vitamin b12"),

        # Greek beta handling
        ("β-Glucan", "beta-glucan"),
        ("β-carotene", "beta-carotene"),
        ("β-sitosterol", "beta-sitosterol"),
        ("β-alanine", "beta-alanine"),
        ("1,3/1,6 β-glucan", "1 3 1 6 beta-glucan"),

        # Micro sign handling
        ("500 µg", "500 mcg"),
        ("1000µg", "1000mcg"),

        # Dash normalization
        ("omega–3", "omega-3"),  # en-dash
        ("omega—3", "omega-3"),  # em-dash

        # Numeric slash normalization (only between digits)
        ("1/2 tablet", "1 2 tablet"),
        ("EPA/DHA", "epa/dha"),  # Non-numeric slashes preserved

        # Trademark removal
        ("Vitamin C™", "vitamin c"),
        ("CoQ10®", "coq10"),
        ("Zinc©", "zinc"),

        # Whitespace collapse
        ("Vitamin   B12", "vitamin b12"),
        ("Vitamin\tB12", "vitamin b12"),
        ("Vitamin\nB12", "vitamin b12"),

        # Comma/middle dot normalization
        ("1,000 mg", "1 000 mg"),
        ("vitamin·b12", "vitamin b12"),

        # Empty and edge cases
        ("", ""),
        ("   ", ""),
        (None, ""),
    ])
    def test_normalize_text_golden(self, input_text, expected):
        """Golden fixture tests - these define the contract."""
        result = normalize_text(input_text) if input_text is not None else normalize_text("")
        assert result == expected, f"normalize_text({input_text!r}) = {result!r}, expected {expected!r}"


class TestMakeNormalizedKeyGoldenFixtures:
    """
    Golden fixtures for make_normalized_key().
    These MUST NOT change - existing keys in the database depend on this.
    """

    @pytest.fixture(autouse=True)
    def clear_cache(self):
        clear_caches()
        yield
        clear_caches()

    @pytest.mark.parametrize("input_text,expected_key", [
        # Basic ingredient names
        ("Vitamin B12", "vitamin_b12"),
        ("Vitamin D3", "vitamin_d3"),
        ("Omega-3 Fatty Acids", "omega_3_fatty_acids"),
        ("Coenzyme Q10", "coenzyme_q10"),

        # With form specifiers
        ("Vitamin B12 (as Methylcobalamin)", "vitamin_b12_as_methylcobalamin"),
        ("Folate (as L-Methylfolate)", "folate_as_l_methylfolate"),
        ("Vitamin D (as Cholecalciferol)", "vitamin_d_as_cholecalciferol"),

        # Greek beta
        ("β-Glucan", "beta_glucan"),
        ("β-Carotene", "beta_carotene"),

        # Numbers and units
        ("1,000 mcg", "1_000_mcg"),
        ("500 mg", "500_mg"),

        # Special characters
        ("DL-Alpha Tocopherol", "dl_alpha_tocopherol"),
        ("L-Theanine", "l_theanine"),
        ("5-HTP", "5_htp"),

        # Complex cases
        ("Omega-3 Fatty Acids (EPA/DHA)", "omega_3_fatty_acids_epadha"),  # Slash removed by punctuation filter
        ("Vitamin B-Complex", "vitamin_b_complex"),
        ("N-Acetyl Cysteine (NAC)", "n_acetyl_cysteine_nac"),

        # Whitespace handling
        ("  Extra  Spaces  ", "extra_spaces"),
        ("Multiple   Internal   Spaces", "multiple_internal_spaces"),

        # Empty and edge cases
        ("", ""),
        ("   ", ""),
    ])
    def test_make_normalized_key_golden(self, input_text, expected_key):
        """Golden fixture tests - keys must be stable forever."""
        result = make_normalized_key(input_text)
        assert result == expected_key, f"make_normalized_key({input_text!r}) = {result!r}, expected {expected_key!r}"


class TestNormalizeCompanyNameGoldenFixtures:
    """Golden fixtures for company name normalization."""

    @pytest.fixture(autouse=True)
    def clear_cache(self):
        clear_caches()
        yield
        clear_caches()

    @pytest.mark.parametrize("input_name,expected", [
        # Common suffixes
        ("Garden of Life LLC", "garden of life"),
        ("Garden of Life, LLC", "garden of life"),
        ("NOW Foods, Inc.", "now foods"),
        ("NOW Foods Inc", "now foods"),
        ("Thorne Research Corporation", "thorne research"),
        ("Thorne Research Corp.", "thorne research"),
        ("Nature Made Co.", "nature made"),
        ("Solgar Ltd.", "solgar"),
        ("Douglas Laboratories Limited", "douglas laboratories"),

        # International suffixes
        ("Some Company GmbH", "some company"),
        ("Another Company AG", "another company"),
        ("Third Company SA", "third company"),

        # No suffix
        ("Pure Encapsulations", "pure encapsulations"),

        # Edge cases
        ("", ""),
        ("   ", ""),
    ])
    def test_normalize_company_name_golden(self, input_name, expected):
        result = normalize_company_name(input_name)
        assert result == expected, f"normalize_company_name({input_name!r}) = {result!r}, expected {expected!r}"


class TestNormalizeForSkipMatchingGoldenFixtures:
    """Golden fixtures for skip set matching normalization (Tier B)."""

    @pytest.fixture(autouse=True)
    def clear_cache(self):
        clear_caches()
        yield
        clear_caches()

    @pytest.mark.parametrize("input_text,expected", [
        # Preserves case
        ("Vitamin B12", "Vitamin B12"),
        ("VITAMIN B12", "VITAMIN B12"),

        # Preserves punctuation
        ("Vitamin B-12", "Vitamin B-12"),
        ("N-Acetyl Cysteine", "N-Acetyl Cysteine"),

        # Whitespace handling
        ("  Vitamin B12  ", "Vitamin B12"),
        ("Vitamin   B12", "Vitamin B12"),
        ("Vitamin\tB12", "Vitamin B12"),

        # Unicode normalization (NFC)
        ("café", "café"),

        # Empty cases
        ("", ""),
        ("   ", ""),
    ])
    def test_normalize_for_skip_matching_golden(self, input_text, expected):
        result = normalize_for_skip_matching(input_text)
        assert result == expected


class TestPreprocessTextGoldenFixtures:
    """Golden fixtures for comprehensive preprocessing."""

    @pytest.fixture(autouse=True)
    def clear_cache(self):
        clear_caches()
        yield
        clear_caches()

    @pytest.mark.parametrize("input_text,expected", [
        # Parenthetical removal
        ("Vitamin B12 (as Methylcobalamin)", "vitamin b12"),
        ("Folate (400 mcg)", "folate"),

        # Bracket removal
        ("Vitamin D [from lanolin]", "vitamin d"),

        # Prefix removal
        ("DL-Alpha Tocopherol", "alpha tocopherol"),
        ("D-Calcium Pantothenate", "calcium pantothenate"),
        ("L-Theanine", "theanine"),
        ("Natural Vitamin E", "vitamin e"),
        ("Organic Turmeric", "turmeric"),

        # Suffix removal
        ("Turmeric Extract", "turmeric"),
        ("Green Tea Extract, Powder", "green tea"),
        ("Fish Oil Concentrate", "fish"),

        # Trademark removal
        ("MegaFood™", "megafood"),

        # Complex cases - only one prefix removed per call
        ("Natural D-Alpha Tocopherol Extract", "d-alpha tocopherol"),

        # Empty cases
        ("", ""),
        ("   ", ""),
    ])
    def test_preprocess_text_golden(self, input_text, expected):
        result = preprocess_text(input_text)
        assert result == expected, f"preprocess_text({input_text!r}) = {result!r}, expected {expected!r}"


class TestValidateNormalizedKey:
    """Test normalized_key validation."""

    @pytest.mark.parametrize("key,expected_valid", [
        # Valid keys
        ("vitamin_b12", True),
        ("omega_3_fatty_acids", True),
        ("coenzyme_q10", True),
        ("5_htp", True),

        # Invalid keys
        ("", False),
        ("Vitamin_B12", False),  # uppercase
        ("vitamin-b12", False),  # hyphen
        ("vitamin b12", False),  # space
        ("_vitamin_b12", False),  # leading underscore
        ("vitamin_b12_", False),  # trailing underscore
        ("vitamin__b12", False),  # double underscore
        ("vitamin.b12", False),  # dot
    ])
    def test_validate_normalized_key(self, key, expected_valid):
        is_valid, error = validate_normalized_key(key)
        assert is_valid == expected_valid, f"validate_normalized_key({key!r}) = ({is_valid}, {error!r})"


class TestNormalizeExactText:
    """Test minimal normalization for exact matching."""

    @pytest.mark.parametrize("input_text,expected", [
        ("Vitamin B12", "vitamin b12"),
        ("  Vitamin B12  ", "vitamin b12"),
        ("Vitamin B-12", "vitamin b-12"),  # preserves hyphen
        ("Vitamin (B12)", "vitamin (b12)"),  # preserves parens
        ("", ""),
    ])
    def test_normalize_exact_text(self, input_text, expected):
        result = normalize_exact_text(input_text)
        assert result == expected


class TestNormalizationDeterminism:
    """Ensure normalization is deterministic across multiple calls."""

    def test_normalize_text_deterministic(self):
        """Same input should always produce same output."""
        inputs = [
            "Vitamin B12",
            "β-Glucan",
            "1,000 mcg",
            "Omega-3 Fatty Acids (EPA/DHA)",
        ]
        for inp in inputs:
            result1 = normalize_text(inp)
            result2 = normalize_text(inp)
            assert result1 == result2, f"Non-deterministic: {inp}"

    def test_make_normalized_key_deterministic(self):
        """Same input should always produce same key."""
        inputs = [
            "Vitamin B12 (as Methylcobalamin)",
            "β-Glucan",
            "Omega-3 Fatty Acids",
        ]
        for inp in inputs:
            key1 = make_normalized_key(inp)
            key2 = make_normalized_key(inp)
            assert key1 == key2, f"Non-deterministic key: {inp}"


class TestNormalizationCaching:
    """Test that caching works correctly."""

    def test_cache_hit(self):
        """Repeated calls should hit cache."""
        clear_caches()
        text = "Vitamin B12"

        # First call
        result1 = normalize_text(text)
        info1 = normalize_text.cache_info()

        # Second call (should hit cache)
        result2 = normalize_text(text)
        info2 = normalize_text.cache_info()

        assert result1 == result2
        assert info2.hits > info1.hits

    def test_clear_caches(self):
        """clear_caches() should reset all caches."""
        normalize_text("test")
        make_normalized_key("test")
        normalize_company_name("test")

        clear_caches()

        assert normalize_text.cache_info().currsize == 0
        assert make_normalized_key.cache_info().currsize == 0
        assert normalize_company_name.cache_info().currsize == 0


class TestNoneAndEmptyHandling:
    """Ensure None and empty inputs are handled consistently."""

    def test_empty_string_handling(self):
        assert normalize_text("") == ""
        assert make_normalized_key("") == ""
        assert normalize_company_name("") == ""
        assert normalize_for_skip_matching("") == ""
        assert preprocess_text("") == ""
        assert normalize_exact_text("") == ""

    def test_whitespace_only_handling(self):
        assert normalize_text("   ") == ""
        assert make_normalized_key("   ") == ""
        assert normalize_company_name("   ") == ""
        assert normalize_for_skip_matching("   ") == ""
        assert preprocess_text("   ") == ""
        assert normalize_exact_text("   ") == ""
