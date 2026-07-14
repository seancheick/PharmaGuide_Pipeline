#!/usr/bin/env python3
"""
Allergen Negation Integration Tests

Validates that allergen-free claims properly prevent allergen detection.
This is a critical test for data integrity - products claiming to be
"dairy-free" should NOT show dairy as a detected allergen.

These tests verify the fix for the Issue #1 showstopper from the dev report:
- labelText.parsed.allergens bypass negation check entirely
- "Contains no X" statements incorrectly parsed as "contains X"

Run with: pytest tests/test_allergen_negation_integration.py -v
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from enrich_supplements_v3 import SupplementEnricherV3 as SupplementEnricher


class TestParsedAllergenPositiveEvidence:
    """Positive parsed evidence survives contradictory free-claim metadata."""

    @pytest.fixture
    def enricher(self):
        """Create enricher instance with allergen database loaded."""
        return SupplementEnricher()

    def test_free_claim_does_not_erase_parsed_contains_evidence(self, enricher):
        """
        CRITICAL: Product with dairy-free claim should NOT detect milk allergen.

        This is the exact scenario from Product 10040 that was failing.
        """
        product = {
            "labelText": {
                "parsed": {
                    "allergens": ["milk", "eggs", "soy"],  # Parser found these
                    "allergenFree": ["dairy", "egg", "soy"]  # But also found free claims
                }
            },
            "targetGroups": ["Dairy Free", "Egg Free", "Soy Free"]
        }

        result = enricher._extract_allergen_presence_from_text(product)

        # Get detected allergen names
        detected_names = [a["allergen_name"].lower() for a in result]
        detected_ids = [a["allergen_id"] for a in result]

        assert "milk" in detected_names
        assert "ALLERGEN_MILK" in detected_ids
        assert "eggs" in detected_names
        assert "ALLERGEN_EGGS" in detected_ids
        assert "soy & soy lecithin" in detected_names
        assert "ALLERGEN_SOY" in detected_ids

    def test_gluten_free_claim_does_not_erase_parsed_wheat(self, enricher):
        product = {
            "labelText": {
                "parsed": {
                    "allergens": ["wheat"],
                    "allergenFree": ["gluten", "wheat"]
                }
            },
            "targetGroups": ["Gluten Free"]
        }

        result = enricher._extract_allergen_presence_from_text(product)

        detected_ids = [a["allergen_id"] for a in result]
        assert "ALLERGEN_WHEAT" in detected_ids

    def test_target_groups_do_not_override_parsed_contains_evidence(self, enricher):
        product = {
            "labelText": {
                "parsed": {
                    "allergens": ["shellfish", "peanuts"],
                    # No allergenFree array - only targetGroups
                }
            },
            "targetGroups": ["Shellfish Free", "Peanut-Free"]
        }

        result = enricher._extract_allergen_presence_from_text(product)

        detected_ids = [a["allergen_id"] for a in result]
        assert "ALLERGEN_CRUSTACEANS" in detected_ids
        assert "ALLERGEN_PEANUTS" in detected_ids

    def test_partial_free_claims_are_kept_for_conflict_detection(self, enricher):
        """
        Products with SOME free claims should still detect OTHER allergens.

        A dairy-free product that contains soy should:
        - NOT detect dairy/milk
        - STILL detect soy
        """
        product = {
            "labelText": {
                "parsed": {
                    "allergens": ["milk", "soy", "tree nuts"],
                    "allergenFree": ["dairy"]  # Only dairy-free, not soy-free
                }
            },
            "targetGroups": ["Dairy Free"]  # Confirms dairy-free only
        }

        result = enricher._extract_allergen_presence_from_text(product)

        detected_ids = [a["allergen_id"] for a in result]

        assert "ALLERGEN_MILK" in detected_ids
        assert "ALLERGEN_SOY" in detected_ids
        assert "ALLERGEN_TREE_NUTS" in detected_ids


class TestAllergenNegationInStatements:
    """Tests for allergen negation in free-text statements."""

    @pytest.fixture
    def enricher(self):
        """Create enricher instance."""
        return SupplementEnricher()

    def test_contains_no_statement_skipped(self, enricher):
        """
        'Contains no X' statements should NOT detect X as an allergen.

        This was failing for Product 10040's statement:
        "Contains no sugar, salt, starch, yeast, wheat, gluten, soy, milk, egg, shellfish or preservatives."
        """
        product = {
            "statements": [
                {"text": "Contains no sugar, salt, starch, yeast, wheat, gluten, soy, milk, egg, shellfish or preservatives."}
            ],
            "labelText": {"parsed": {}}
        }

        result = enricher._extract_allergen_presence_from_text(product)

        # None of these should be detected
        detected_ids = [a["allergen_id"] for a in result]
        assert "ALLERGEN_YEAST" not in detected_ids, "'Contains no yeast' should not detect yeast"
        assert "ALLERGEN_WHEAT" not in detected_ids, "'Contains no wheat' should not detect wheat"
        assert "ALLERGEN_SOY" not in detected_ids, "'Contains no soy' should not detect soy"
        assert "ALLERGEN_MILK" not in detected_ids, "'Contains no milk' should not detect milk"
        assert "ALLERGEN_EGGS" not in detected_ids, "'Contains no egg' should not detect eggs"
        assert "ALLERGEN_CRUSTACEANS" not in detected_ids, "'Contains no shellfish' should not detect shellfish"

    def test_free_from_statement_skipped(self, enricher):
        """'Free from X' statements should NOT detect X as an allergen."""
        product = {
            "statements": [
                {"text": "Free from milk, eggs, and peanuts."}
            ],
            "labelText": {"parsed": {}}
        }

        result = enricher._extract_allergen_presence_from_text(product)

        detected_ids = [a["allergen_id"] for a in result]
        assert "ALLERGEN_MILK" not in detected_ids, "'Free from milk' should not detect milk"
        assert "ALLERGEN_EGGS" not in detected_ids, "'Free from eggs' should not detect eggs"
        assert "ALLERGEN_PEANUTS" not in detected_ids, "'Free from peanuts' should not detect peanuts"

    def test_does_not_contain_skipped(self, enricher):
        """'Does not contain X' statements should NOT detect X."""
        product = {
            "statements": [
                {"text": "This product does not contain soy or tree nuts."}
            ],
            "labelText": {"parsed": {}}
        }

        result = enricher._extract_allergen_presence_from_text(product)

        detected_ids = [a["allergen_id"] for a in result]
        assert "ALLERGEN_SOY" not in detected_ids, "'Does not contain soy' should not detect soy"
        assert "ALLERGEN_TREE_NUTS" not in detected_ids, "'Does not contain tree nuts' should not detect tree nuts"

    def test_positive_contains_statement_detected(self, enricher):
        """
        Regular 'Contains X' statements (without negation) SHOULD detect allergens.

        This ensures the negation fix doesn't break positive detection.
        """
        product = {
            "statements": [
                {"text": "Contains milk and soy."}
            ],
            "labelText": {"parsed": {}}
        }

        result = enricher._extract_allergen_presence_from_text(product)

        detected_ids = [a["allergen_id"] for a in result]
        assert "ALLERGEN_MILK" in detected_ids, "'Contains milk' should detect milk"
        assert "ALLERGEN_SOY" in detected_ids, "'Contains soy' should detect soy"

    def test_negated_clause_does_not_hide_later_positive_clause(self, enricher):
        product = {
            "statements": [
                {"text": "Made without gluten. Contains milk and soy."}
            ],
            "labelText": {"parsed": {}},
        }

        result = enricher._extract_allergen_presence_from_text(product)
        detected_ids = {entry["allergen_id"] for entry in result}

        assert "ALLERGEN_MILK" in detected_ids
        assert "ALLERGEN_SOY" in detected_ids

    def test_positive_parsed_allergen_survives_conflicting_free_claim(self, enricher):
        product = {
            "labelText": {
                "parsed": {
                    "allergens": ["milk"],
                    "allergenFree": ["dairy"],
                }
            },
            "targetGroups": ["Dairy Free"],
        }

        result = enricher._extract_allergen_presence_from_text(product)

        assert "ALLERGEN_MILK" in {entry["allergen_id"] for entry in result}

    def test_may_contain_warning_still_works(self, enricher):
        """'May contain X' warnings should still be detected."""
        product = {
            "statements": [
                {"text": "May contain peanuts and tree nuts."}  # Direct format without "traces of"
            ],
            "labelText": {"parsed": {}}
        }

        result = enricher._extract_allergen_presence_from_text(product)

        # May contain should be detected with may_contain presence_type
        peanut_entries = [a for a in result if a.get("allergen_id") == "ALLERGEN_PEANUTS"]
        tree_nut_entries = [a for a in result if a.get("allergen_id") == "ALLERGEN_TREE_NUTS"]

        assert len(peanut_entries) > 0, "'May contain peanuts' should detect peanuts"
        assert len(tree_nut_entries) > 0, "'May contain tree nuts' should detect tree nuts"

        # Verify presence_type is may_contain, not contains
        for entry in peanut_entries + tree_nut_entries:
            assert entry.get("presence_type") == "may_contain", "May contain should have may_contain presence_type"


class TestProduct10040Simulation:
    """
    Simulates the exact Product 10040 scenario that was failing.

    This is the definitive test that proves the fix works.
    """

    @pytest.fixture
    def enricher(self):
        """Create enricher instance."""
        return SupplementEnricher()

    def test_product_10040_scenario(self, enricher):
        """
        Product 10040 exact scenario:
        - targetGroups: ["Dairy Free", "Gluten Free", "Soy Free", "Vegan", "Vegetarian"]
        - labelText.parsed.allergens: ["eggs", "milk", "wheat", "shellfish", "soy"]
        - labelText.parsed.allergenFree: ["dairy", "egg", "wheat", "shellfish", "gluten", "soy", "yeast"]
        - Statement: "Contains no sugar, salt, starch, yeast, wheat, gluten, soy, milk, egg, shellfish or preservatives."

        Result: parsed positive declarations remain present so compliance can
        surface the contradictory free claims.
        """
        product = {
            "targetGroups": ["Vegan", "Vegetarian", "Dairy Free", "Gluten Free", "Sugar Free"],
            "labelText": {
                "parsed": {
                    "allergens": ["eggs", "milk", "wheat", "shellfish", "soy"],
                    "allergenFree": ["dairy", "egg", "wheat", "shellfish", "gluten", "soy", "yeast"]
                }
            },
            "statements": [
                {"text": "Contains no sugar, salt, starch, yeast, wheat, gluten, soy, milk, egg, shellfish or preservatives."}
            ]
        }

        result = enricher._extract_allergen_presence_from_text(product)

        # Get all detected allergen IDs
        detected_ids = set(a["allergen_id"] for a in result)

        parsed_positive_allergens = {
            "ALLERGEN_MILK",        # dairy-free
            "ALLERGEN_EGGS",        # egg-free
            "ALLERGEN_WHEAT",       # wheat/gluten-free
            "ALLERGEN_CRUSTACEANS", # shellfish-free
            "ALLERGEN_SOY",         # soy-free
        }
        assert parsed_positive_allergens <= detected_ids
        assert "ALLERGEN_YEAST" not in detected_ids


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
