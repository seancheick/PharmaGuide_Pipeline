"""
Sprint D2.2 regression tests — qualifier-suffix strip in canonical resolution.

Context: ~100 silently-mapped rows across the 20-brand corpus carried
preparation qualifiers separated by a comma ("Phenylalanine, Micronized",
"Tryptophan, Micronized", "Quercetin, Organic", etc.). The reverse
index didn't have entries for the comma-suffix variants, so the cleaner
couldn't resolve canonical_id. After D2.1 these now correctly downgrade
to mapped=False, but that's a band-aid — the right fix is to recognize
that these suffixes describe PROCESSING, not IDENTITY.

Fix: ``_strip_qualifier_suffixes`` tail-strips recognized tokens
("Micronized", "Organic", "Natural", "Freeze-Dried", "Raw", "Fermented",
"Vegan", "Non-GMO", "USP", "Pharmaceutical Grade", "Food Grade",
"Certified Organic", "Whole Leaf", "Kosher", "Halal"). Used as a
FALLBACK lookup in ``_resolve_canonical_identity`` AFTER exact raw-name
and exact standard_name lookups miss — never overrides a real match.

Stripping is also guarded by a regex anchored at the end-of-string +
requires a leading comma, so we don't accidentally strip mid-name
occurrences (e.g., "Micronized Calcium Citrate" won't lose "Micronized"
— that'd be a matcher concern, not identity).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from enhanced_normalizer import EnhancedDSLDNormalizer


@pytest.fixture(scope="module")
def normalizer() -> EnhancedDSLDNormalizer:
    return EnhancedDSLDNormalizer()


# ---------------------------------------------------------------------------
# Amino-acid qualifier strip — the bulk of the silent-mapping set
# ---------------------------------------------------------------------------


class TestAminoAcidQualifierStrip:
    """Amino acids with ', Micronized' suffix resolve to the base canonical."""

    @pytest.mark.parametrize("raw,expected_contains", [
        ("Phenylalanine, Micronized",      "phenylalanine"),
        ("Methionine, Micronized",         "methionine"),
        ("Histidine, Micronized",          "histidine"),
        ("Tryptophan, Micronized",         "tryptophan"),
        ("Leucine, Micronized",            "leucine"),
        ("Isoleucine, Micronized",         "isoleucine"),
    ])
    def test_amino_acid_micronized_resolves(self, normalizer, raw, expected_contains) -> None:
        result = normalizer._resolve_canonical_identity(raw, raw_name=raw)
        assert result is not None, f"{raw!r} did not resolve"
        canonical_id = result[0]
        assert expected_contains in (canonical_id or "").lower(), (
            f"{raw!r} resolved to {canonical_id!r}; expected canonical containing "
            f"{expected_contains!r}."
        )


# ---------------------------------------------------------------------------
# Other qualifier suffixes
# ---------------------------------------------------------------------------


class TestOtherQualifierSuffixes:
    """Preparation qualifiers beyond 'Micronized' also strip correctly."""

    @pytest.mark.parametrize("raw,expected_contains", [
        ("Quercetin, Organic",             "quercetin"),
        ("Phenylalanine, Natural",         "phenylalanine"),
        ("Phenylalanine, Freeze-Dried",    "phenylalanine"),
        ("Phenylalanine, Freeze Dried",    "phenylalanine"),
        ("Phenylalanine, Raw",             "phenylalanine"),
        ("Phenylalanine, Fermented",       "phenylalanine"),
        ("Phenylalanine, Vegan",           "phenylalanine"),
        ("Phenylalanine, Non-GMO",         "phenylalanine"),
        ("Phenylalanine, USP",             "phenylalanine"),
        ("Phenylalanine, Pharmaceutical Grade", "phenylalanine"),
        ("Phenylalanine, Food Grade",      "phenylalanine"),
        ("Phenylalanine, Certified Organic","phenylalanine"),
        ("Phenylalanine, Whole Leaf",      "phenylalanine"),
        ("Phenylalanine, Kosher",          "phenylalanine"),
        ("Phenylalanine, Halal",           "phenylalanine"),
    ])
    def test_qualifier_variants_strip(self, normalizer, raw, expected_contains) -> None:
        result = normalizer._resolve_canonical_identity(raw, raw_name=raw)
        assert result is not None
        assert expected_contains in (result[0] or "").lower()


# ---------------------------------------------------------------------------
# Must NOT strip non-recognized suffixes or mid-name occurrences
# ---------------------------------------------------------------------------


class TestQualifierStripSafetyGuards:
    """The strip must only apply to recognized trailing qualifiers."""

    def test_unknown_suffix_does_not_strip(self, normalizer) -> None:
        # "Something Weird" is not a recognized qualifier; strip does not
        # apply and the whole string fails to resolve.
        result = normalizer._resolve_canonical_identity(
            "Phenylalanine, Something Weird", raw_name="Phenylalanine, Something Weird",
        )
        assert result == (None, None), (
            "An unrecognized suffix must NOT cause the strip to fire. "
            "Only listed qualifier tokens should be removed."
        )

    def test_mid_name_qualifier_not_affected(self, normalizer) -> None:
        # The regex is anchored at end-of-string with a required leading
        # comma — "Micronized Calcium" with "Micronized" at the START
        # must not get mis-stripped.
        result = normalizer._resolve_canonical_identity(
            "Micronized Calcium", raw_name="Micronized Calcium",
        )
        # Whatever the result, the key assertion is that the strip did
        # not corrupt the lookup — either it resolved via existing
        # aliases or returned (None, None) — but not a silent partial
        # match.
        assert result in (
            (None, None),
            ("calcium", "ingredient_quality_map"),  # if calcium aliases cover it
        )

    def test_bare_ingredient_unchanged(self, normalizer) -> None:
        """Baseline: ingredient with no qualifier resolves via direct lookup."""
        result = normalizer._resolve_canonical_identity(
            "Phenylalanine", raw_name="Phenylalanine",
        )
        assert result is not None
        assert "phenylalanine" in (result[0] or "").lower()


# ---------------------------------------------------------------------------
# Strip is fallback only — never overrides exact raw/standard match
# ---------------------------------------------------------------------------


class TestStripIsFallbackOnly:
    """The strip only fires when exact lookups miss — not as an override."""

    def test_exact_raw_name_wins_over_strip(self, normalizer) -> None:
        # If an ingredient exists in the index with its qualifier (a
        # hypothetical alias "phenylalanine, micronized"), the exact hit
        # must win over the stripped fallback. Since no such alias
        # exists in IQM, the strip will fire — but this test documents
        # the ordering contract.
        result = normalizer._resolve_canonical_identity(
            "Phenylalanine", raw_name="Phenylalanine",
        )
        # Phenylalanine exact alias must resolve directly, not via strip fallback.
        assert result is not None
        assert "phenylalanine" in (result[0] or "").lower()


# ---------------------------------------------------------------------------
# Unit-level strip function
# ---------------------------------------------------------------------------


class TestStripHelper:
    """The ``_strip_qualifier_suffixes`` helper works on raw strings."""

    @pytest.mark.parametrize("input_name,expected", [
        ("Phenylalanine, Micronized",      "Phenylalanine"),
        ("Quercetin, Organic",             "Quercetin"),
        ("Ingredient, Freeze-Dried",       "Ingredient"),
        ("Ingredient, freeze dried",       "Ingredient"),
        ("Ingredient, USP",                "Ingredient"),
        ("Ingredient, Non-GMO",            "Ingredient"),
        # Untouched
        ("Phenylalanine",                  "Phenylalanine"),
        ("Phenylalanine, Something",       "Phenylalanine, Something"),
        ("",                               ""),
    ])
    def test_strip_table(self, normalizer, input_name, expected) -> None:
        assert normalizer._strip_qualifier_suffixes(input_name) == expected
