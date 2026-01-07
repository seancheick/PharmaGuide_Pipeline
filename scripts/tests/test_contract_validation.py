"""
Contract Validation Tests

Tests for the EnrichmentContractValidator that enforces minimum consistency rules.
"""

import pytest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

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
        products = [
            {
                "id": "valid_1",
                "dietary_sensitivity_data": {},
                "serving_basis": {"canonical_serving_size_quantity": 2}
            },
            {
                "id": "invalid_1",
                "dietary_sensitivity_data": {"sugar": {"amount_g": 4, "contains_sugar": False}},
                "serving_basis": {"canonical_serving_size_quantity": 2}
            },
            {
                "id": "valid_2",
                "dietary_sensitivity_data": {},
                "serving_basis": {"canonical_serving_size_quantity": 2}
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
