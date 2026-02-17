"""
Contract Validation Tests

Tests for the EnrichmentContractValidator that enforces minimum consistency rules.
"""

import pytest
import sys
import os

# Add parent directory to path for imports (normalized to avoid ".." in __file__)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from enrichment_contract_validator import EnrichmentContractValidator, ContractViolation


class TestSugarConsistencyContract:
    """Rule A: Sugar consistency validation"""

    @pytest.fixture
    def validator(self):
        return EnrichmentContractValidator()

    def test_A1a_sugar_amount_requires_contains_sugar_true(self, validator):
        """A.1a: If amount_g > 0, contains_sugar must be true"""
        product = {
            "id": "test_sugar_1",
            "dietary_sensitivity_data": {
                "sugar": {
                    "amount_g": 4,
                    "contains_sugar": False,  # VIOLATION
                    "level": "moderate"
                }
            }
        }

        violations = validator.validate(product)
        rule_violations = [v for v in violations if v.rule == "A.1a"]

        assert len(rule_violations) == 1
        assert rule_violations[0].severity == "error"
        assert "contains_sugar" in rule_violations[0].message

    def test_A1a_has_added_sugar_requires_contains_sugar_true(self, validator):
        """A.1a: If has_added_sugar, contains_sugar must be true"""
        product = {
            "id": "test_sugar_2",
            "dietary_sensitivity_data": {
                "sugar": {
                    "amount_g": 0,
                    "has_added_sugar": True,
                    "contains_sugar": False,  # VIOLATION
                    "level": "low"
                }
            }
        }

        violations = validator.validate(product)
        rule_violations = [v for v in violations if v.rule == "A.1a"]

        assert len(rule_violations) == 1

    def test_A1b_sugar_amount_cannot_be_sugar_free(self, validator):
        """A.1b: If amount_g > 0, level cannot be 'sugar_free'"""
        product = {
            "id": "test_sugar_3",
            "dietary_sensitivity_data": {
                "sugar": {
                    "amount_g": 4,
                    "contains_sugar": True,
                    "level": "sugar_free"  # VIOLATION
                }
            }
        }

        violations = validator.validate(product)
        rule_violations = [v for v in violations if v.rule == "A.1b"]

        assert len(rule_violations) == 1
        assert rule_violations[0].severity == "error"
        assert "sugar_free" in rule_violations[0].message

    def test_A2_sugar_sources_requires_contains_sugar(self, validator):
        """A.2: If sugar_sources non-empty, contains_sugar must be true"""
        product = {
            "id": "test_sugar_4",
            "dietary_sensitivity_data": {
                "sugar": {
                    "amount_g": 0,
                    "contains_sugar": False,  # VIOLATION
                    "sugar_sources": ["corn syrup", "sugar"]
                }
            }
        }

        violations = validator.validate(product)
        rule_violations = [v for v in violations if v.rule == "A.2"]

        assert len(rule_violations) == 1

    def test_valid_sugar_data_no_violations(self, validator):
        """Valid sugar data should not trigger violations"""
        product = {
            "id": "test_sugar_valid",
            "dietary_sensitivity_data": {
                "sugar": {
                    "amount_g": 4,
                    "has_added_sugar": True,
                    "contains_sugar": True,
                    "level": "moderate",
                    "sugar_sources": ["sugar", "corn syrup"]
                }
            }
        }

        violations = validator.validate(product)
        sugar_violations = [v for v in violations if v.rule.startswith("A.")]

        assert len(sugar_violations) == 0

    def test_sugar_free_valid_when_no_sugar(self, validator):
        """sugar_free level is valid when amount_g is 0"""
        product = {
            "id": "test_sugar_free_valid",
            "dietary_sensitivity_data": {
                "sugar": {
                    "amount_g": 0,
                    "has_added_sugar": False,
                    "contains_sugar": False,
                    "level": "sugar_free"
                }
            }
        }

        violations = validator.validate(product)
        sugar_violations = [v for v in violations if v.rule.startswith("A.")]

        assert len(sugar_violations) == 0


class TestAllergenPrecedenceContract:
    """Rule B: Allergen precedence validation"""

    @pytest.fixture
    def validator(self):
        return EnrichmentContractValidator()

    def test_B1_duplicate_allergen_with_weaker_type(self, validator):
        """B.1: No duplicate allergens with conflicting presence_types"""
        product = {
            "id": "test_allergen_1",
            "dietary_sensitivity_data": {
                "allergens": [
                    {"allergen_id": "ALLERGEN_MILK", "presence_type": "contains"},
                    {"allergen_id": "ALLERGEN_MILK", "presence_type": "may_contain"}  # VIOLATION - weaker
                ]
            }
        }

        violations = validator.validate(product)
        rule_violations = [v for v in violations if v.rule == "B.1"]

        assert len(rule_violations) == 1
        assert "ALLERGEN_MILK" in rule_violations[0].message
        assert "weaker" in rule_violations[0].message.lower()

    def test_B2_may_contain_warning_requires_allergen(self, validator):
        """B.2: has_may_contain_warning requires at least one may_contain allergen"""
        product = {
            "id": "test_allergen_2",
            "dietary_sensitivity_data": {
                "has_may_contain_warning": True,
                "allergens": [
                    {"allergen_id": "ALLERGEN_MILK", "presence_type": "contains"}
                    # No may_contain or facility_warning - VIOLATION
                ]
            }
        }

        violations = validator.validate(product)
        rule_violations = [v for v in violations if v.rule == "B.2"]

        assert len(rule_violations) == 1

    def test_B2_valid_with_may_contain_allergen(self, validator):
        """B.2: has_may_contain_warning is valid with may_contain allergen"""
        product = {
            "id": "test_allergen_valid",
            "dietary_sensitivity_data": {
                "has_may_contain_warning": True,
                "allergens": [
                    {"allergen_id": "ALLERGEN_PEANUTS", "presence_type": "may_contain"}
                ]
            }
        }

        violations = validator.validate(product)
        rule_violations = [v for v in violations if v.rule == "B.2"]

        assert len(rule_violations) == 0

    def test_B2_valid_with_facility_warning_allergen(self, validator):
        """B.2: has_may_contain_warning is valid with facility_warning allergen"""
        product = {
            "id": "test_allergen_valid_2",
            "dietary_sensitivity_data": {
                "has_may_contain_warning": True,
                "allergens": [
                    {"allergen_id": "ALLERGEN_TREE_NUTS", "presence_type": "facility_warning"}
                ]
            }
        }

        violations = validator.validate(product)
        rule_violations = [v for v in violations if v.rule == "B.2"]

        assert len(rule_violations) == 0


class TestColorsConsistencyContract:
    """Rule C: Colors consistency validation"""

    @pytest.fixture
    def validator(self):
        return EnrichmentContractValidator()

    def test_C1_natural_colors_not_flagged_artificial(self, validator):
        """C.1: Natural colors should not be flagged as artificial"""
        product = {
            "id": "test_colors_1",
            "inactiveIngredients": [
                {"name": "Colors", "standardName": "natural colors"}
            ],
            "contaminant_data": {
                "harmful_additives": {
                    "additives": [
                        {"ingredient": "Colors", "additive_id": "ADD_ARTIFICIAL_COLORS"}  # VIOLATION
                    ]
                }
            }
        }

        violations = validator.validate(product)
        rule_violations = [v for v in violations if v.rule == "C.1"]

        assert len(rule_violations) == 1
        assert "natural colors" in rule_violations[0].message
        assert "flagged as artificial" in rule_violations[0].message

    def test_C1_valid_natural_colors_not_flagged(self, validator):
        """C.1: Natural colors without artificial flag is valid"""
        product = {
            "id": "test_colors_valid",
            "inactiveIngredients": [
                {"name": "Colors", "standardName": "natural colors"}
            ],
            "contaminant_data": {
                "harmful_additives": {
                    "additives": []  # No artificial color flag
                }
            }
        }

        violations = validator.validate(product)
        rule_violations = [v for v in violations if v.rule == "C.1"]

        assert len(rule_violations) == 0

    def test_C2_artificial_flag_needs_evidence(self, validator):
        """C.2: Artificial dye flag should have evidence"""
        product = {
            "id": "test_colors_2",
            "inactiveIngredients": [
                {"name": "Mystery Color", "standardName": "mystery color"}  # Not explicit dye
            ],
            "contaminant_data": {
                "harmful_additives": {
                    "additives": [
                        {"ingredient": "Mystery Color", "additive_id": "ADD_ARTIFICIAL_COLORS"}
                    ]
                }
            }
        }

        violations = validator.validate(product)
        rule_violations = [v for v in violations if v.rule == "C.2"]

        assert len(rule_violations) == 1
        assert rule_violations[0].severity == "warning"  # Warning, not error

    def test_C2_valid_artificial_with_explicit_dye(self, validator):
        """C.2: Artificial flag with explicit dye token is valid"""
        product = {
            "id": "test_colors_valid_2",
            "inactiveIngredients": [
                {"name": "Red 40", "standardName": "red 40"}
            ],
            "contaminant_data": {
                "harmful_additives": {
                    "additives": [
                        {"ingredient": "Red 40", "additive_id": "ADD_RED40"}
                    ]
                }
            }
        }

        violations = validator.validate(product)
        rule_violations = [v for v in violations if v.rule == "C.2"]

        assert len(rule_violations) == 0


class TestServingBasisIntegrityContract:
    """Rule D: Serving basis integrity validation"""

    @pytest.fixture
    def validator(self):
        return EnrichmentContractValidator()

    def test_D1a_gummy_unit_not_truncated(self, validator):
        """D.1a: Gummy form_factor should not have truncated basis_unit"""
        product = {
            "id": "test_serving_1",
            "serving_basis": {
                "form_factor": "gummy",
                "basis_unit": "gummy(ie"  # VIOLATION - truncated
            }
        }

        violations = validator.validate(product)
        rule_violations = [v for v in violations if v.rule == "D.1a"]

        assert len(rule_violations) == 1
        assert "truncated" in rule_violations[0].message

    def test_D1b_gummy_unit_normalized(self, validator):
        """D.1b: Gummy form_factor with non-standard unit triggers warning"""
        product = {
            "id": "test_serving_2",
            "serving_basis": {
                "form_factor": "gummy",
                "basis_unit": "piece"  # Not a standard gummy unit
            }
        }

        violations = validator.validate(product)
        rule_violations = [v for v in violations if v.rule == "D.1b"]

        assert len(rule_violations) == 1
        assert rule_violations[0].severity == "warning"

    def test_D1_valid_gummy_units(self, validator):
        """D.1: Valid gummy units should not trigger violations"""
        valid_units = ["gummy", "gummies", "gummy(ies)"]

        for unit in valid_units:
            product = {
                "id": f"test_serving_valid_{unit}",
                "serving_basis": {
                    "form_factor": "gummy",
                    "basis_unit": unit
                }
            }

            violations = validator.validate(product)
            rule_violations = [v for v in violations if v.rule.startswith("D.1")]

            assert len(rule_violations) == 0, f"Unit '{unit}' should be valid"

    def test_D2_null_canonical_quantity_warning(self, validator):
        """D.2: Null canonical_serving_size_quantity triggers warning"""
        product = {
            "id": "test_serving_3",
            "serving_basis": {
                "canonical_serving_size_quantity": None
            },
            "servingSizes": []  # Empty - reason for null
        }

        violations = validator.validate(product)
        rule_violations = [v for v in violations if v.rule == "D.2"]

        assert len(rule_violations) == 1
        assert rule_violations[0].severity == "warning"
        assert "missing servingSizes" in rule_violations[0].evidence.get("reason", "")

    def test_D2_valid_with_canonical_quantity(self, validator):
        """D.2: Valid canonical_serving_size_quantity should not trigger"""
        product = {
            "id": "test_serving_valid",
            "serving_basis": {
                "canonical_serving_size_quantity": 2,
                "form_factor": "gummy",
                "basis_unit": "gummies"
            }
        }

        violations = validator.validate(product)
        rule_violations = [v for v in violations if v.rule == "D.2"]

        assert len(rule_violations) == 0


class TestValidatorUtilities:
    """Test validator utility methods"""

    @pytest.fixture
    def validator(self):
        return EnrichmentContractValidator()

    def test_get_summary(self, validator):
        """Test summary generation"""
        product = {
            "id": "test_summary",
            "dietary_sensitivity_data": {
                "sugar": {
                    "amount_g": 4,
                    "contains_sugar": False,  # A.1a violation
                    "level": "sugar_free"  # A.1b violation
                }
            }
        }

        violations = validator.validate(product)
        summary = validator.get_summary(violations)

        assert summary["total_violations"] >= 2
        assert summary["errors"] >= 2
        assert "A.1a" in summary["by_rule"]
        assert "A.1b" in summary["by_rule"]

    def test_validate_batch(self, validator):
        """Test batch validation"""
        # Products need match_ledger to avoid G.1 warning
        valid_ledger = {
            "domains": {},
            "summary": {"total_entities": 0, "total_matched": 0, "coverage_percent": 0}
        }
        products = [
            {
                "id": "valid_1",
                "dietary_sensitivity_data": {},
                "serving_basis": {"canonical_serving_size_quantity": 2},
                "match_ledger": valid_ledger
            },
            {
                "id": "invalid_1",
                "dietary_sensitivity_data": {"sugar": {"amount_g": 4, "contains_sugar": False}},
                "serving_basis": {"canonical_serving_size_quantity": 2},
                "match_ledger": valid_ledger
            },
            {
                "id": "valid_2",
                "dietary_sensitivity_data": {},
                "serving_basis": {"canonical_serving_size_quantity": 2},
                "match_ledger": valid_ledger
            }
        ]

        results = validator.validate_batch(products)

        assert "invalid_1" in results
        assert "valid_1" not in results
        assert "valid_2" not in results

    def test_to_dict(self, validator):
        """Test violation serialization to dict"""
        violation = ContractViolation(
            rule="A.1a",
            rule_name="Sugar Consistency",
            severity="error",
            message="Test message",
            product_id="test_123",
            field_path="sugar.contains_sugar",
            expected=True,
            actual=False
        )

        result = validator.to_dict(violation)

        assert result["rule"] == "A.1a"
        assert result["severity"] == "error"
        assert result["product_id"] == "test_123"
        assert result["expected"] == True
        assert result["actual"] == False


class TestProvenanceIntegrityContract:
    """Rule F: Provenance integrity validation"""

    @pytest.fixture
    def validator(self):
        return EnrichmentContractValidator()

    def test_F1_matched_ingredient_missing_raw_source_text(self, validator):
        """F.1: Matched ingredient missing raw_source_text triggers error"""
        product = {
            "id": "test_provenance_1",
            "activeIngredients": [
                {
                    "name": "Vitamin C",
                    "canonical_id": "ING_VITAMIN_C",  # Has canonical_id = matched
                    # Missing raw_source_text - VIOLATION
                    "normalized_key": "vitamin_c"
                }
            ]
        }

        violations = validator.validate(product)
        rule_violations = [v for v in violations if v.rule == "F.1"]

        assert len(rule_violations) == 1
        assert rule_violations[0].severity == "error"
        assert "raw_source_text" in rule_violations[0].message

    def test_F2_matched_ingredient_missing_normalized_key(self, validator):
        """F.2: Matched ingredient missing normalized_key triggers error"""
        product = {
            "id": "test_provenance_2",
            "activeIngredients": [
                {
                    "name": "Vitamin D",
                    "db_id": "ING_VITAMIN_D",  # Has db_id = matched
                    "raw_source_text": "Vitamin D3"
                    # Missing normalized_key - VIOLATION
                }
            ]
        }

        violations = validator.validate(product)
        rule_violations = [v for v in violations if v.rule == "F.2"]

        assert len(rule_violations) == 1
        assert rule_violations[0].severity == "error"
        assert "normalized_key" in rule_violations[0].message

    def test_F3_ledger_matched_without_canonical_id(self, validator):
        """F.3: Ledger entry marked 'matched' but missing canonical_id"""
        product = {
            "id": "test_provenance_3",
            "match_ledger": {
                "domains": {
                    "ingredients": {
                        "total_raw": 1,
                        "matched": 1,
                        "unmatched": 0,
                        "entries": [
                            {
                                "raw_source_text": "Vitamin C",
                                "decision": "matched",
                                "canonical_id": None  # VIOLATION
                            }
                        ]
                    }
                },
                "summary": {
                    "total_entities": 1,
                    "total_matched": 1,
                    "coverage_percent": 100.0
                }
            }
        }

        violations = validator.validate(product)
        rule_violations = [v for v in violations if v.rule == "F.3"]

        assert len(rule_violations) == 1
        assert "canonical_id" in rule_violations[0].message

    def test_F_valid_provenance_no_violations(self, validator):
        """Valid provenance fields should not trigger violations"""
        product = {
            "id": "test_provenance_valid",
            "activeIngredients": [
                {
                    "name": "Vitamin C",
                    "canonical_id": "ING_VITAMIN_C",
                    "raw_source_text": "Vitamin C (Ascorbic Acid)",
                    "normalized_key": "vitamin_c_ascorbic_acid"
                }
            ],
            "inactiveIngredients": [
                {
                    "name": "Cellulose",
                    "db_id": "ING_CELLULOSE",
                    "raw_source_text": "Microcrystalline Cellulose",
                    "normalized_key": "microcrystalline_cellulose"
                }
            ],
            "match_ledger": {
                "domains": {
                    "ingredients": {
                        "total_raw": 2,
                        "matched": 2,
                        "unmatched": 0,
                        "entries": [
                            {
                                "raw_source_text": "Vitamin C (Ascorbic Acid)",
                                "decision": "matched",
                                "canonical_id": "ING_VITAMIN_C"
                            },
                            {
                                "raw_source_text": "Microcrystalline Cellulose",
                                "decision": "matched",
                                "canonical_id": "ING_CELLULOSE"
                            }
                        ]
                    }
                },
                "summary": {
                    "total_entities": 2,
                    "total_matched": 2,
                    "coverage_percent": 100.0
                }
            }
        }

        violations = validator.validate(product)
        rule_violations = [v for v in violations if v.rule.startswith("F.")]

        assert len(rule_violations) == 0

    def test_F_unmatched_ingredient_no_provenance_ok(self, validator):
        """Unmatched ingredients (no canonical_id) don't require provenance"""
        product = {
            "id": "test_provenance_unmatched",
            "activeIngredients": [
                {
                    "name": "Mystery Extract",
                    # No canonical_id/db_id = unmatched, so no provenance required
                }
            ]
        }

        violations = validator.validate(product)
        rule_violations = [v for v in violations if v.rule.startswith("F.")]

        assert len(rule_violations) == 0


class TestMatchLedgerConsistencyContract:
    """Rule G: Match ledger consistency validation"""

    @pytest.fixture
    def validator(self):
        return EnrichmentContractValidator()

    def test_G1_missing_match_ledger_warning(self, validator):
        """G.1: Missing match_ledger triggers warning"""
        product = {
            "id": "test_ledger_1"
            # No match_ledger - VIOLATION (warning)
        }

        violations = validator.validate(product)
        rule_violations = [v for v in violations if v.rule == "G.1"]

        assert len(rule_violations) == 1
        assert rule_violations[0].severity == "warning"

    def test_G2a_summary_total_mismatch(self, validator):
        """G.2a: summary.total_entities != sum of domain totals"""
        product = {
            "id": "test_ledger_2",
            "match_ledger": {
                "domains": {
                    "ingredients": {"total_raw": 5, "matched": 4, "unmatched": 1},
                    "additives": {"total_raw": 2, "matched": 2, "unmatched": 0}
                },
                "summary": {
                    "total_entities": 10,  # Should be 7 - VIOLATION
                    "total_matched": 6,
                    "coverage_percent": 85.7
                }
            }
        }

        violations = validator.validate(product)
        rule_violations = [v for v in violations if v.rule == "G.2a"]

        assert len(rule_violations) == 1
        assert "total_entities" in rule_violations[0].message

    def test_G2b_summary_matched_mismatch(self, validator):
        """G.2b: summary.total_matched != sum of domain matched"""
        product = {
            "id": "test_ledger_3",
            "match_ledger": {
                "domains": {
                    "ingredients": {"total_raw": 5, "matched": 4, "unmatched": 1},
                    "additives": {"total_raw": 2, "matched": 2, "unmatched": 0}
                },
                "summary": {
                    "total_entities": 7,
                    "total_matched": 10,  # Should be 6 - VIOLATION
                    "coverage_percent": 85.7
                }
            }
        }

        violations = validator.validate(product)
        rule_violations = [v for v in violations if v.rule == "G.2b"]

        assert len(rule_violations) == 1
        assert "total_matched" in rule_violations[0].message

    def test_G3_unmatched_list_count_mismatch(self, validator):
        """G.3: unmatched_* list count != ledger unmatched count"""
        product = {
            "id": "test_ledger_4",
            "match_ledger": {
                "domains": {
                    "ingredients": {"total_raw": 5, "matched": 4, "unmatched": 1}
                },
                "summary": {
                    "total_entities": 5,
                    "total_matched": 4,
                    "coverage_percent": 80.0
                }
            },
            "unmatched_ingredients": [
                {"raw_source_text": "Mystery 1"},
                {"raw_source_text": "Mystery 2"},
                {"raw_source_text": "Mystery 3"}
                # 3 items but ledger says 1 - VIOLATION
            ]
        }

        violations = validator.validate(product)
        rule_violations = [v for v in violations if v.rule == "G.3"]

        assert len(rule_violations) == 1
        assert "unmatched_ingredients" in rule_violations[0].message

    def test_G4_coverage_percent_calculation_error(self, validator):
        """G.4: coverage_percent != calculated value"""
        product = {
            "id": "test_ledger_5",
            "match_ledger": {
                "domains": {
                    "ingredients": {"total_raw": 10, "matched": 8, "unmatched": 2}
                },
                "summary": {
                    "total_entities": 10,
                    "total_matched": 8,
                    "coverage_percent": 90.0  # Should be 80.0 - VIOLATION
                }
            }
        }

        violations = validator.validate(product)
        rule_violations = [v for v in violations if v.rule == "G.4"]

        assert len(rule_violations) == 1
        assert "coverage_percent" in rule_violations[0].message

    def test_G_valid_ledger_no_violations(self, validator):
        """Valid match ledger should not trigger violations"""
        product = {
            "id": "test_ledger_valid",
            "match_ledger": {
                "domains": {
                    "ingredients": {"total_raw": 5, "matched": 4, "unmatched": 1},
                    "additives": {"total_raw": 2, "matched": 2, "unmatched": 0},
                    "allergens": {"total_raw": 1, "matched": 1, "unmatched": 0}
                },
                "summary": {
                    "total_entities": 8,
                    "total_matched": 7,
                    "coverage_percent": 87.5
                }
            },
            "unmatched_ingredients": [{"raw_source_text": "Mystery Extract"}],
            "unmatched_additives": [],
            "unmatched_allergens": []
        }

        violations = validator.validate(product)
        rule_violations = [v for v in violations if v.rule.startswith("G.")]

        assert len(rule_violations) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
