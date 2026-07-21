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
from audit_identity_integrity import audit_product


def _complete_label_ledger_audit(
    meaningful_source_rows,
    displayed_rows,
    omitted_rows=0,
):
    return {
        "support_status": "supported",
        "source_structure": "flat_supplement_facts",
        "meaningful_source_rows": meaningful_source_rows,
        "displayed_rows": displayed_rows,
        "omitted_rows": omitted_rows,
        "completeness_percentage": 100.0,
        "completeness_status": "complete",
    }


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


class TestIdentitySafetySeparationContract:
    """Rule I: identity fields and safety fields remain separate."""

    @pytest.fixture
    def validator(self):
        return EnrichmentContractValidator()

    def test_standard_name_alias_drift_is_error(self, validator):
        product = {
            "id": "test_identity_alias",
            "activeIngredients": [{
                "name": "Chromium",
                "standard_name": "Chromium",
                "standardName": "Chromium (VI) — Hexavalent Chromium",
            }],
        }

        violations = validator.validate(product)
        assert any(v.rule == "I.1" for v in violations)

    def test_safety_source_cannot_own_identity(self, validator):
        product = {
            "id": "test_safety_source_identity",
            "activeIngredients": [{
                "name": "Chromium",
                "standard_name": "Chromium",
                "standardName": "Chromium",
                "canonical_source_db": "banned_recalled_ingredients",
            }],
        }

        violations = validator.validate(product)
        assert any(v.rule == "I.2" for v in violations)

    def test_legacy_safety_projection_requires_safety_flag(self, validator):
        product = {
            "id": "test_legacy_safety_without_flag",
            "activeIngredients": [{
                "name": "Chromium",
                "standard_name": "Chromium",
                "standardName": "Chromium",
                "matched_source": "banned_recalled",
                "matched_rule_id": "HM_CHROMIUM_HEXAVALENT",
                "safety_flags": [],
            }],
        }

        violations = validator.validate(product)
        assert any(v.rule == "I.3" for v in violations)

    def test_legacy_safety_projection_requires_matching_safety_flag(self, validator):
        product = {
            "id": "test_legacy_safety_with_wrong_flag",
            "activeIngredients": [{
                "name": "Chromium",
                "standard_name": "Chromium",
                "standardName": "Chromium",
                "matched_source": "banned_recalled",
                "matched_rule_id": "HM_CHROMIUM_HEXAVALENT",
                "safety_flags": [{
                    "entry_id": "BANNED_DHEA",
                    "source_db": "banned_recalled_ingredients",
                    "status": "high_risk",
                    "severity": "high",
                    "match_type": "exact",
                    "matched_variant": "DHEA",
                    "evidence_text": "DHEA",
                    "confidence": "high",
                }],
            }],
        }

        violations = validator.validate(product)
        assert any(v.rule == "I.3" for v in violations)

    def test_safety_flag_shape_requires_evidence_fields(self, validator):
        product = {
            "id": "test_bad_safety_flag",
            "activeIngredients": [{
                "name": "Chromium",
                "standard_name": "Chromium",
                "standardName": "Chromium",
                "safety_flags": [{"entry_id": "HM_CHROMIUM_HEXAVALENT"}],
            }],
        }

        violations = validator.validate(product)
        assert any(v.rule == "I.4" for v in violations)

    def test_reference_negative_match_terms_accept_object_exact_mode(self, validator):
        doc = {
            "ingredients": [{
                "id": "HM_CHROMIUM_HEXAVALENT",
                "standard_name": "Chromium (VI) — Hexavalent Chromium",
                "negative_match_terms": [
                    {"term": "chromium", "match_mode": "exact"},
                    "chromium picolinate",
                ],
                "requires_explicit_form_evidence": True,
                "form_evidence_patterns": [r"\bhexavalent\b"],
            }],
        }

        violations = validator.validate_banned_recalled_reference(doc)
        assert not [v for v in violations if v.rule in {"I.5", "I.6"}]

    def test_reference_negative_match_terms_reject_bad_mode(self, validator):
        doc = {
            "ingredients": [{
                "id": "BAD_MODE",
                "standard_name": "Chromium (VI) — Hexavalent Chromium",
                "negative_match_terms": [{"term": "chromium", "match_mode": "contains"}],
            }],
        }

        violations = validator.validate_banned_recalled_reference(doc)
        assert any(v.rule == "I.5" for v in violations)

    def test_reference_explicit_evidence_requires_patterns(self, validator):
        doc = {
            "ingredients": [{
                "id": "MISSING_PATTERNS",
                "standard_name": "Chromium (VI) — Hexavalent Chromium",
                "requires_explicit_form_evidence": True,
            }],
        }

        violations = validator.validate_banned_recalled_reference(doc)
        assert any(v.rule == "I.6" for v in violations)

    def test_reference_qualified_entry_without_guard_warns(self, validator):
        doc = {
            "ingredients": [{
                "id": "QUALIFIED_NO_GUARD",
                "standard_name": "Green Tea Extract (High Dose)",
                "negative_match_terms": [],
            }],
        }

        violations = validator.validate_banned_recalled_reference(doc)
        assert any(v.rule == "I.7" and v.severity == "warning" for v in violations)


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


class TestDisplayLedgerContract:
    """Rule H: display ledger additive contract validation."""

    @pytest.fixture
    def validator(self):
        return EnrichmentContractValidator()

    def test_H_display_ledger_optional_when_absent(self, validator):
        product = {
            "id": "test_display_optional",
            "activeIngredients": [
                {
                    "name": "Vitamin C",
                    "canonical_id": "ING_VITAMIN_C",
                    "raw_source_text": "Vitamin C",
                    "normalized_key": "vitamin_c",
                }
            ],
        }

        violations = validator.validate(product)
        rule_violations = [v for v in violations if v.rule.startswith("H.")]
        assert len(rule_violations) == 0

    def test_H_valid_display_ledger_no_violations(self, validator):
        product = {
            "id": "test_display_valid",
            "label_ledger_audit": _complete_label_ledger_audit(2, 2),
            "display_ingredients": [
                {
                    "raw_source_path": "activeIngredients[0]",
                    "raw_source_text": "Vitamin C",
                    "display_name": "Vitamin C",
                    "label_display_name": "Vitamin C",
                    "label_order": 0,
                    "nested_depth": 0,
                    "source_section": "activeIngredients",
                    "display_type": "mapped_ingredient",
                    "resolution_type": "direct_mapped",
                    "score_included": True,
                    "display_disposition": "scored",
                    "form_display_state": "not_disclosed",
                    "identity_integrity_state": "clean",
                    "ledger_fingerprint": "vitamin-c",
                    "mapped_to": {
                        "standard_name": "Vitamin C",
                        "source_section": "active",
                        "raw_source_path": "activeIngredients",
                    },
                },
                {
                    "raw_source_path": "activeIngredients[1]",
                    "raw_source_text": "Other Omega-3's",
                    "display_name": "Other Omega-3's",
                    "label_display_name": "Other Omega-3's",
                    "label_order": 1,
                    "nested_depth": 0,
                    "source_section": "activeIngredients",
                    "display_type": "summary_wrapper",
                    "resolution_type": "suppressed_parent",
                    "score_included": False,
                    "display_disposition": "label_context",
                    "form_display_state": "not_applicable",
                    "identity_integrity_state": "taxonomy_only",
                    "ledger_fingerprint": "other-omega-3",
                    "children": [],
                },
            ],
        }

        violations = validator.validate(product)
        rule_violations = [v for v in violations if v.rule.startswith("H.")]
        assert len(rule_violations) == 0

    def test_H_product_name_fallback_is_a_valid_display_source(self, validator):
        product = {
            "id": "test_display_product_name",
            "label_ledger_audit": _complete_label_ledger_audit(1, 1),
            "display_ingredients": [
                {
                    "raw_source_path": "product_name",
                    "raw_source_text": "Vitamin D3 1000 IU",
                    "display_name": "Vitamin D3",
                    "label_display_name": "Vitamin D3",
                    "label_order": 0,
                    "nested_depth": 0,
                    "source_section": "product_name",
                    "display_type": "inferred_from_name",
                    "resolution_type": "product_name_fallback",
                    "score_included": False,
                    "display_disposition": "label_context",
                    "form_display_state": "listed_not_assessed",
                    "identity_integrity_state": "taxonomy_only",
                    "ledger_fingerprint": "vitamin-d3-product-name",
                    "mapped_to": {
                        "standard_name": "Vitamin D3",
                        "source_section": "inferred",
                        "raw_source_path": "product_name",
                    },
                }
            ],
        }

        violations = validator.validate(product)

        assert [v for v in violations if v.rule.startswith("H.")] == []

    def test_H_invalid_display_row_missing_required_field(self, validator):
        product = {
            "id": "test_display_invalid_missing",
            "display_ingredients": [
                {
                    "raw_source_path": "activeIngredients[0]",
                    "raw_source_text": "Vitamin C",
                    "display_name": "Vitamin C",
                    "label_display_name": "Vitamin C",
                    "label_order": 0,
                    "nested_depth": 0,
                    "source_section": "activeIngredients",
                    "display_type": "mapped_ingredient",
                    # resolution_type missing
                    "score_included": True,
                    "display_disposition": "scored",
                    "form_display_state": "not_disclosed",
                    "identity_integrity_state": "clean",
                    "ledger_fingerprint": "vitamin-c-missing-resolution",
                }
            ],
        }

        violations = validator.validate(product)
        rule_violations = [v for v in violations if v.rule == "H.1"]
        assert len(rule_violations) == 1
        assert "resolution_type" in rule_violations[0].message

    def test_H_invalid_mapped_to_missing_standard_name(self, validator):
        product = {
            "id": "test_display_invalid_mapped_to",
            "display_ingredients": [
                {
                    "raw_source_path": "activeIngredients[0]",
                    "raw_source_text": "Vitamin C",
                    "display_name": "Vitamin C",
                    "label_display_name": "Vitamin C",
                    "label_order": 0,
                    "nested_depth": 0,
                    "source_section": "activeIngredients",
                    "display_type": "mapped_ingredient",
                    "resolution_type": "direct_mapped",
                    "score_included": True,
                    "display_disposition": "scored",
                    "form_display_state": "not_disclosed",
                    "identity_integrity_state": "clean",
                    "ledger_fingerprint": "vitamin-c-invalid-map",
                    "mapped_to": {
                        "source_section": "active",
                        "raw_source_path": "activeIngredients",
                    },
                }
            ],
        }

        violations = validator.validate(product)
        rule_violations = [v for v in violations if v.rule == "H.2"]
        assert len(rule_violations) == 1
        assert "standard_name" in rule_violations[0].message

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


class TestArtificialColorEvidenceAcceptsHashDyeNames:
    """C.2: a dye's own name IS the explicit-dye evidence.

    Labels write dyes as "Red #40" / "Blue #1". The token set stores them
    unhashed ("red 40"), so ``"red 40" in "red #40"`` was False and a literal
    FD&C dye was reported as "lacking evidence" that it is a dye.
    """

    @pytest.fixture
    def validator(self):
        return EnrichmentContractValidator()

    @pytest.mark.parametrize("dye_name,additive_id", [
        ("red #40", "ADD_RED40"),
        ("blue #1", "ADD_BLUE1"),
        ("yellow #5", "ADD_YELLOW5"),
        ("red 40", "ADD_RED40"),      # unhashed form must keep working
        ("FD&C Red #40", "ADD_RED40"),
    ])
    def test_dye_name_counts_as_explicit_evidence(self, validator, dye_name, additive_id):
        product = {
            "dsld_id": "TEST_C2",
            "contaminant_data": {
                "harmful_additives": {
                    "additives": [
                        {"ingredient": dye_name, "additive_id": additive_id}
                    ]
                }
            },
        }

        violations = validator.validate(product)

        assert not [v for v in violations if v.rule == "C.2"], (
            f"{dye_name!r} is an explicit dye token; must not warn 'lacks evidence'"
        )


class TestGummyBasisUnitAcceptsLabelFaithfulUnits:
    """D.1b: basis_unit is label-faithful; form_factor is canonical.

    DSLD labels declare gummy servings by shape/marketing name ("1 Jelly Bean",
    "Nordic Berries") and sometimes by mass ("2.2 Gram(s)" for 2 gummies).
    Both are legitimate label data, not normalization failures. D.1a (truncated
    unit -> error) remains the rule that catches genuine parse garbage.
    """

    @pytest.fixture
    def validator(self):
        return EnrichmentContractValidator()

    @pytest.mark.parametrize("basis_unit", [
        "jelly bean",     # CVS 239580, Natures_Bounty 308199 ("Immune Jelly Beans")
        "swirly bear",    # CVS 25945 ("Gummy Swirls")
        "chewable bear",  # Garden_of_life 321386
        "chew",           # GNC 228076
        "nordic berry",   # nordic-naturals 221659 ("Nordic Berries")
        "gram",           # Pure_Encapsulations 278384: label declares 2.2 Gram(s)
        "gummy",          # canonical form must keep passing
    ])
    def test_legitimate_label_gummy_units_do_not_warn(self, validator, basis_unit):
        product = {
            "dsld_id": "TEST_D1B",
            "form_factor_canonical": "gummy",
            "serving_basis": {
                "basis_unit": basis_unit,
                "canonical_serving_size_quantity": 2,
            },
        }

        violations = validator.validate(product)

        assert not [v for v in violations if v.rule == "D.1b"], (
            f"{basis_unit!r} is a legitimate label-declared gummy unit"
        )

    def test_truncated_gummy_unit_still_errors(self, validator):
        """Guard: relaxing D.1b must not blind D.1a to real parse garbage."""
        product = {
            "dsld_id": "TEST_D1A",
            "form_factor_canonical": "gummy",
            "serving_basis": {
                "basis_unit": "gummy(ie",
                "canonical_serving_size_quantity": 2,
            },
        }

        violations = validator.validate(product)

        assert [
            v for v in violations if v.rule == "D.1a" and v.severity == "error"
        ], "truncated basis_unit must still be a hard error"


class TestLabelLedgerReleaseContract:
    """P0 label-truth integrity gates fail closed without repairing data."""

    @pytest.fixture
    def validator(self):
        return EnrichmentContractValidator()

    @staticmethod
    def _row(**overrides):
        row = {
            "raw_source_text": "Magnesium",
            "display_name": "Magnesium",
            "label_display_name": "Magnesium",
            "raw_source_path": "activeIngredients[0]",
            "label_order": 0,
            "nested_depth": 0,
            "source_section": "activeIngredients",
            "display_type": "mapped_ingredient",
            "resolution_type": "direct_mapped",
            "score_included": True,
            "display_disposition": "scored",
            "form_display_state": "not_disclosed",
            "identity_integrity_state": "clean",
            "ledger_fingerprint": "test-ledger-fingerprint",
        }
        row.update(overrides)
        return row

    @staticmethod
    def _identity_audit_row():
        return {
            "raw_source_path": "activeIngredients[0]",
            "source_label_key": "label:magnesium:magnesium:200:mg",
            "source_label_name": "Magnesium",
            "label_display_name": "Magnesium",
            "canonical_id_before": "magnesium",
            "canonical_id_after": "magnesium",
            "canonical_id": "magnesium",
            "identity_disposition": "clean",
            "scoreable_identity": True,
            "identity_resolution_rationale": "test fixture",
        }

    @pytest.mark.parametrize("state", ["unknown", "pending", ""])
    def test_H3_form_display_state_is_closed(self, validator, state):
        product = {
            "id": "invalid-form-state",
            "display_ingredients": [self._row(form_display_state=state)],
        }

        violations = validator.validate(product)

        assert [v for v in violations if v.rule == "H.3"]
        assert any(
            v.field_path == "display_ingredients[0].form_display_state"
            and v.evidence.get("audit_code") == "invalid_form_display_state"
            for v in violations
        )

    @pytest.mark.parametrize("state", ["unknown", "pending", ""])
    def test_H3_identity_integrity_state_is_closed(self, validator, state):
        product = {
            "id": "invalid-identity-state",
            "display_ingredients": [self._row(identity_integrity_state=state)],
        }

        violations = validator.validate(product)

        assert [v for v in violations if v.rule == "H.3"]
        assert any(
            v.field_path == "display_ingredients[0].identity_integrity_state"
            and v.evidence.get("audit_code") == "invalid_identity_integrity_state"
            for v in violations
        )

    @pytest.mark.parametrize("form_field", ["label_display_form", "source_label_form"])
    def test_H4_disclosed_form_cannot_be_not_disclosed(
        self, validator, form_field
    ):
        product = {
            "id": "false-not-disclosed",
            "display_ingredients": [
                self._row(**{form_field: "as Magnesium Glycinate"})
            ],
        }

        violations = validator.validate(product)

        assert any(
            v.rule == "H.4"
            and v.field_path == "display_ingredients[0].form_display_state"
            and v.evidence.get("audit_code")
            == "disclosed_form_marked_not_disclosed"
            for v in violations
        )

    def test_H5_score_included_identity_conflict_blocks_release(self, validator):
        product = {
            "id": "scored-conflict",
            "display_ingredients": [
                self._row(identity_integrity_state="identity_conflict")
            ],
        }

        violations = validator.validate(product)

        assert any(
            v.rule == "H.5"
            and v.evidence.get("audit_code") == "score_included_identity_conflict"
            for v in violations
        )

    def test_H5_any_active_missing_display_label_blocks_release(self, validator):
        product = {
            "id": "active-missing-label",
            "display_ingredients": [
                self._row(
                    score_included=False,
                    display_disposition="needs_review",
                    form_display_state="needs_review",
                    identity_integrity_state="missing_display_label",
                )
            ],
        }

        violations = validator.validate(product)

        assert any(
            v.rule == "H.5"
            and v.evidence.get("audit_code") == "active_missing_display_label"
            for v in violations
        )

    def test_release_audit_blocks_published_score_for_identity_failure(self):
        product = {
            "id": "published-conflict",
            "label_record": {},
            "quality_score_status": "scored",
            "quality_score_v4_100": 82.0,
            "activeIngredients": [
                {
                    "name": "Magnesium",
                    "raw_source_text": "Magnesium",
                    "raw_source_path": "activeIngredients[0]",
                }
            ],
            "ingredient_quality_data": {
                "ingredients": [self._identity_audit_row()]
            },
            "display_ingredients": [
                self._row(identity_integrity_state="identity_conflict")
            ],
        }

        records = audit_product(product, classify=lambda _: "generic")

        assert any(
            record.violation == "score_publication_blocked_by_identity_integrity"
            for record in records
        )

    @pytest.mark.parametrize(
        "claim_fields,expected_path",
        [
            ({"exact_dose_text": "200 mg"}, "exact_dose_text"),
            (
                {"analysis": {"form_quality_claim": "Excellent"}},
                "analysis.form_quality_claim",
            ),
            (
                {"analysis": {"safety_claim": "Safe"}},
                "analysis.safety_claim",
            ),
        ],
    )
    def test_release_audit_blocks_needs_review_rows_with_claims(
        self, claim_fields, expected_path
    ):
        row = self._row(
            display_disposition="needs_review",
            form_display_state="needs_review",
            score_included=False,
        )
        row.update(claim_fields)
        product = {
            "id": "review-claim",
            "label_record": {},
            "activeIngredients": [
                {
                    "name": "Magnesium",
                    "raw_source_text": "Magnesium",
                    "raw_source_path": "activeIngredients[0]",
                }
            ],
            "ingredient_quality_data": {
                "ingredients": [self._identity_audit_row()]
            },
            "display_ingredients": [row],
        }

        records = audit_product(product, classify=lambda _: "generic")

        assert any(
            record.violation == f"needs_review_claim_present:{expected_path}"
            for record in records
        )

    def test_H7_meaningful_source_row_requires_ledger_or_omission_evidence(
        self, validator
    ):
        product = {
            "id": "missing-ledger-source",
            "activeIngredients": [
                {
                    "name": "Magnesium",
                    "raw_source_text": "Magnesium",
                    "raw_source_path": "activeIngredients[0]",
                }
            ],
            "display_ingredients": [],
            "label_ledger_omissions": [],
        }

        violations = validator.validate(product)

        assert any(
            v.rule == "H.7"
            and v.field_path == "activeIngredients[0].raw_source_path"
            and v.evidence.get("audit_code") == "missing_label_ledger_omission"
            for v in violations
        )

    @pytest.mark.parametrize(
        "reason",
        [
            "nutrition_fact_not_applicable",
            "decorative_or_header_text",
            "duplicate_source_line",
            "empty_source_text",
            "unsupported_source_structure",
        ],
    )
    def test_H7_omission_reason_closed_set_accepts_exact_values(
        self, validator, reason
    ):
        product = {
            "id": "allowed-omission",
            "display_ingredients": [],
            "label_ledger_omissions": [
                {
                    "raw_source_path": "label[0]",
                    "raw_source_text": "Header",
                    "omission_reason": reason,
                }
            ],
        }

        violations = validator.validate(product)

        assert not [v for v in violations if v.rule == "H.7"]

    def test_H7_omission_reason_outside_closed_set_is_error(self, validator):
        product = {
            "id": "bad-omission",
            "display_ingredients": [],
            "label_ledger_omissions": [
                {
                    "raw_source_path": "label[0]",
                    "raw_source_text": "Mystery",
                    "omission_reason": "not_useful",
                }
            ],
        }

        violations = validator.validate(product)

        assert any(
            v.rule == "H.7"
            and v.field_path == "label_ledger_omissions[0].omission_reason"
            and v.evidence.get("audit_code")
            == "invalid_label_ledger_omission_reason"
            for v in violations
        )

    def test_H8_unsupported_structure_forbids_completeness_claim(self, validator):
        product = {
            "id": "unsupported-complete",
            "display_ingredients": [],
            "label_ledger_omissions": [
                {
                    "raw_source_path": "label[0]",
                    "raw_source_text": "Two-column panel",
                    "omission_reason": "unsupported_source_structure",
                }
            ],
            "label_ledger_audit": {
                "support_status": "unsupported",
                "source_structure": "unsupported_source_structure",
                "meaningful_source_rows": 1,
                "displayed_rows": 0,
                "omitted_rows": 1,
                "completeness_percentage": 100.0,
                "completeness_status": "complete",
            },
        }

        violations = validator.validate(product)

        assert any(
            v.rule == "H.8"
            and v.evidence.get("audit_code")
            == "unsupported_structure_completeness_claim"
            for v in violations
        )

    def test_H8_strict_release_blocks_unsupported_source_structure(self):
        product = {
            "id": "unsupported-unavailable",
            "display_ingredients": [],
            "label_source_rows": [
                {
                    "raw_source_path": "label[0]",
                    "raw_source_text": "Two-column panel",
                    "source_section": "activeIngredients",
                }
            ],
            "label_ledger_omissions": [
                {
                    "raw_source_path": "label[0]",
                    "raw_source_text": "Two-column panel",
                    "omission_reason": "unsupported_source_structure",
                }
            ],
            "label_ledger_audit": {
                "support_status": "unsupported",
                "source_structure": "unsupported_source_structure",
                "meaningful_source_rows": 0,
                "displayed_rows": 0,
                "omitted_rows": 1,
                "completeness_percentage": None,
                "completeness_status": "unavailable",
            },
        }

        diagnostic_violations = EnrichmentContractValidator(
            strict_mode=False
        ).validate(product)
        release_violations = EnrichmentContractValidator(
            strict_mode=True
        ).validate(product)

        assert not any(
            v.evidence.get("audit_code") == "unsupported_structure_release_block"
            for v in diagnostic_violations
        )
        assert any(
            v.severity == "error"
            and v.evidence.get("audit_code")
            == "unsupported_structure_release_block"
            for v in release_violations
        )

    def test_H8_supported_archetype_below_full_completeness_is_error(
        self, validator
    ):
        product = {
            "id": "supported-incomplete",
            "display_ingredients": [self._row()],
            "label_ledger_audit": {
                "support_status": "supported",
                "source_structure": "flat_supplement_facts",
                "meaningful_source_rows": 2,
                "displayed_rows": 1,
                "omitted_rows": 0,
                "completeness_percentage": 50.0,
                "completeness_status": "incomplete",
            },
        }

        violations = validator.validate(product)

        assert any(
            v.rule == "H.8"
            and v.evidence.get("audit_code") == "supported_archetype_incomplete"
            for v in violations
        )

    def test_H8_supported_full_completeness_and_low_analysis_coverage_pass(
        self, validator
    ):
        product = {
            "id": "supported-complete",
            "mapped_coverage": 0.2,
            "display_ingredients": [self._row()],
            "label_ledger_audit": {
                "support_status": "supported",
                "source_structure": "flat_supplement_facts",
                "meaningful_source_rows": 1,
                "displayed_rows": 1,
                "omitted_rows": 0,
                "completeness_percentage": 100.0,
                "completeness_status": "complete",
            },
        }

        violations = validator.validate(product)

        assert not [v for v in violations if v.rule.startswith("H.")]

    @pytest.mark.parametrize(
        "ledger_field,ledger_value",
        [
            ("display_ingredients", []),
            ("label_ledger_omissions", []),
            (
                "label_source_rows",
                [
                    {
                        "raw_source_path": "nutritionFacts[0]",
                        "raw_source_text": "Calories",
                        "source_section": "nutritionFacts",
                    }
                ],
            ),
        ],
    )
    def test_H8_label_ledger_fields_require_label_ledger_audit(
        self, validator, ledger_field, ledger_value
    ):
        product = {"id": "missing-ledger-audit", ledger_field: ledger_value}

        violations = validator.validate(product)

        assert any(
            v.rule == "H.8"
            and v.field_path == "label_ledger_audit"
            and v.evidence.get("audit_code") == "missing_label_ledger_audit"
            for v in violations
        )

    def test_H7_reconciles_non_active_canonical_label_source_row(self, validator):
        product = {
            "id": "missing-nutrition-source-row",
            "label_source_rows": [
                {
                    "raw_source_path": "nutritionFacts[0]",
                    "raw_source_text": "Calories 10",
                    "source_section": "nutritionFacts",
                }
            ],
            "display_ingredients": [],
            "label_ledger_omissions": [],
            "label_ledger_audit": _complete_label_ledger_audit(1, 0),
        }

        violations = validator.validate(product)

        assert any(
            v.rule == "H.7"
            and v.field_path == "label_source_rows[0].raw_source_path"
            and v.evidence.get("audit_code") == "missing_label_ledger_omission"
            for v in violations
        )

    def test_H7_label_source_rows_replace_active_inactive_fallback(self, validator):
        displayed = self._row(
            raw_source_path="labelSourceRows[0]",
            source_section="product_name",
            score_included=False,
            display_disposition="label_context",
            form_display_state="not_applicable",
            identity_integrity_state="taxonomy_only",
        )
        product = {
            "id": "canonical-source-precedence",
            "label_source_rows": [
                {
                    "raw_source_path": "labelSourceRows[0]",
                    "raw_source_text": "Magnesium Gummies",
                    "source_section": "product_name",
                }
            ],
            "activeIngredients": [
                {
                    "raw_source_path": "legacyActive[0]",
                    "raw_source_text": "Legacy duplicate",
                }
            ],
            "display_ingredients": [displayed],
            "label_ledger_omissions": [],
            "label_ledger_audit": _complete_label_ledger_audit(1, 1),
        }

        violations = validator.validate(product)

        assert not [
            v
            for v in violations
            if v.rule == "H.7"
            and v.evidence.get("audit_code") == "missing_label_ledger_omission"
        ]

    def test_H8_supported_counts_cannot_claim_complete_when_rows_are_missing(
        self, validator
    ):
        audit = _complete_label_ledger_audit(2, 1)
        product = {
            "id": "contradictory-supported-counts",
            "display_ingredients": [self._row()],
            "label_ledger_omissions": [],
            "label_ledger_audit": audit,
        }

        violations = validator.validate(product)
        audit_codes = {v.evidence.get("audit_code") for v in violations}

        assert "supported_meaningful_display_count_mismatch" in audit_codes
        assert "label_completeness_percentage_mismatch" in audit_codes

    def test_H8_displayed_rows_matches_actual_display_ledger_length(self, validator):
        product = {
            "id": "declared-display-count-drift",
            "display_ingredients": [self._row()],
            "label_ledger_omissions": [],
            "label_ledger_audit": _complete_label_ledger_audit(2, 2),
        }

        violations = validator.validate(product)

        assert any(
            v.rule == "H.8"
            and v.field_path == "label_ledger_audit.displayed_rows"
            and v.evidence.get("audit_code") == "displayed_rows_count_mismatch"
            for v in violations
        )

    def test_H8_omitted_rows_matches_actual_omission_list_length(self, validator):
        product = {
            "id": "declared-omission-count-drift",
            "display_ingredients": [self._row()],
            "label_ledger_omissions": [
                {
                    "raw_source_path": "label[1]",
                    "raw_source_text": "Supplement Facts",
                    "omission_reason": "decorative_or_header_text",
                }
            ],
            "label_ledger_audit": {
                **_complete_label_ledger_audit(1, 1),
                "omitted_rows": 2,
            },
        }

        violations = validator.validate(product)

        assert any(
            v.rule == "H.8"
            and v.field_path == "label_ledger_audit.omitted_rows"
            and v.evidence.get("audit_code") == "omitted_rows_count_mismatch"
            for v in violations
        )

    def test_H8_percentage_must_equal_displayed_over_meaningful(self, validator):
        product = {
            "id": "declared-percentage-drift",
            "display_ingredients": [self._row()],
            "label_ledger_omissions": [],
            "label_ledger_audit": {
                **_complete_label_ledger_audit(1, 1),
                "completeness_percentage": 99.0,
            },
        }

        violations = validator.validate(product)

        assert any(
            v.rule == "H.8"
            and v.field_path == "label_ledger_audit.completeness_percentage"
            and v.expected == 100.0
            and v.evidence.get("audit_code")
            == "label_completeness_percentage_mismatch"
            for v in violations
        )

    def test_H8_zero_rows_require_explicit_supported_empty_panel(self, validator):
        product = {
            "id": "implicit-empty-panel",
            "display_ingredients": [],
            "label_ledger_omissions": [],
            "label_ledger_audit": _complete_label_ledger_audit(0, 0),
        }

        violations = validator.validate(product)

        assert any(
            v.rule == "H.8"
            and v.evidence.get("audit_code")
            == "supported_empty_panel_not_declared"
            for v in violations
        )

    def test_H8_explicit_supported_empty_panel_may_be_complete(self, validator):
        product = {
            "id": "explicit-empty-panel",
            "display_ingredients": [],
            "label_ledger_omissions": [],
            "label_ledger_audit": {
                **_complete_label_ledger_audit(0, 0),
                "source_structure": "empty_panel",
            },
        }

        violations = validator.validate(product)

        assert not [v for v in violations if v.rule.startswith("H.")]

    def test_H8_nonmeaningful_omissions_do_not_reduce_completeness(
        self, validator
    ):
        product = {
            "id": "complete-with-header-omission",
            "display_ingredients": [self._row()],
            "label_ledger_omissions": [
                {
                    "raw_source_path": "label[1]",
                    "raw_source_text": "Supplement Facts",
                    "omission_reason": "decorative_or_header_text",
                }
            ],
            "label_ledger_audit": _complete_label_ledger_audit(1, 1, 1),
        }

        violations = validator.validate(product)

        assert not [v for v in violations if v.rule.startswith("H.")]

    @pytest.mark.parametrize(
        "required_field",
        [
            "raw_source_path",
            "label_display_name",
            "label_order",
            "nested_depth",
            "score_included",
            "display_disposition",
            "form_display_state",
            "identity_integrity_state",
            "ledger_fingerprint",
        ],
    )
    def test_H1_canonical_display_fields_are_mandatory(
        self, validator, required_field
    ):
        row = self._row()
        row.pop(required_field)
        product = {
            "id": f"missing-{required_field}",
            "display_ingredients": [row],
            "label_ledger_audit": _complete_label_ledger_audit(1, 1),
        }

        violations = validator.validate(product)

        assert any(
            v.rule == "H.1"
            and v.field_path == "display_ingredients[0]"
            and required_field in v.expected
            for v in violations
        )

    def test_H7_duplicate_display_paths_cannot_fake_complete_audit(
        self, validator
    ):
        product = {
            "id": "duplicate-display-path",
            "label_source_rows": [
                {
                    "raw_source_path": "activeIngredients[0]",
                    "raw_source_text": "Magnesium",
                    "source_section": "activeIngredients",
                }
            ],
            "display_ingredients": [
                self._row(),
                self._row(
                    label_order=1,
                    ledger_fingerprint="duplicate-logical-row",
                ),
            ],
            "label_ledger_omissions": [],
            "label_ledger_audit": _complete_label_ledger_audit(2, 2),
        }

        violations = validator.validate(product)
        audit_codes = {v.evidence.get("audit_code") for v in violations}

        assert "duplicate_display_source_path" in audit_codes
        assert "meaningful_source_rows_inventory_mismatch" in audit_codes

    def test_H7_duplicate_canonical_source_paths_are_rejected(self, validator):
        source_row = {
            "raw_source_path": "activeIngredients[0]",
            "raw_source_text": "Magnesium",
            "source_section": "activeIngredients",
        }
        product = {
            "id": "duplicate-source-inventory",
            "label_source_rows": [dict(source_row), dict(source_row)],
            "display_ingredients": [self._row()],
            "label_ledger_omissions": [],
            "label_ledger_audit": _complete_label_ledger_audit(1, 1),
        }

        violations = validator.validate(product)

        assert any(
            v.rule == "H.7"
            and v.evidence.get("audit_code")
            == "duplicate_label_source_path"
            for v in violations
        )

    def test_H7_display_and_omission_paths_are_disjoint(self, validator):
        product = {
            "id": "display-omission-overlap",
            "label_source_rows": [
                {
                    "raw_source_path": "activeIngredients[0]",
                    "raw_source_text": "Magnesium",
                    "source_section": "activeIngredients",
                }
            ],
            "display_ingredients": [self._row()],
            "label_ledger_omissions": [
                {
                    "raw_source_path": "activeIngredients[0]",
                    "raw_source_text": "Magnesium",
                    "omission_reason": "duplicate_source_line",
                }
            ],
            "label_ledger_audit": _complete_label_ledger_audit(0, 1, 1),
        }

        violations = validator.validate(product)

        assert any(
            v.rule == "H.7"
            and v.evidence.get("audit_code")
            == "display_omission_source_path_overlap"
            for v in violations
        )

    def test_H7_folded_component_path_is_unique_and_omitted_as_duplicate(
        self, validator
    ):
        parent = self._row(
            raw_source_text="Folate 665 mcg DFE (400 mcg Folic Acid)",
            display_name="Folate",
            label_display_name="Folate",
            raw_source_path="activeIngredients[0]",
            ledger_fingerprint="folate-parent",
            folded_label_components=[
                {
                    "raw_source_path": "activeIngredients[0].children[0]",
                    "raw_source_text": "Folic Acid 400 mcg",
                    "label_display_name": "Folic Acid",
                }
            ],
        )
        product = {
            "id": "folded-folate-traceability",
            "label_source_rows": [
                {
                    "raw_source_path": "activeIngredients[0]",
                    "raw_source_text": parent["raw_source_text"],
                    "source_section": "activeIngredients",
                },
                {
                    "raw_source_path": "activeIngredients[0].children[0]",
                    "raw_source_text": "Folic Acid 400 mcg",
                    "source_section": "activeIngredients",
                },
            ],
            "display_ingredients": [parent],
            "label_ledger_omissions": [
                {
                    "raw_source_path": "activeIngredients[0].children[0]",
                    "raw_source_text": "Folic Acid 400 mcg",
                    "omission_reason": "duplicate_source_line",
                }
            ],
            "label_ledger_audit": _complete_label_ledger_audit(1, 1, 1),
        }

        violations = validator.validate(product)

        assert not [v for v in violations if v.rule.startswith("H.")]

    def test_H7_duplicate_folded_component_paths_are_rejected(self, validator):
        folded = {
            "raw_source_path": "activeIngredients[0].children[0]",
            "raw_source_text": "Folic Acid 400 mcg",
            "label_display_name": "Folic Acid",
        }
        row = self._row(folded_label_components=[dict(folded), dict(folded)])
        product = {
            "id": "duplicate-folded-path",
            "display_ingredients": [row],
            "label_ledger_omissions": [
                {
                    **folded,
                    "omission_reason": "duplicate_source_line",
                }
            ],
            "label_ledger_audit": _complete_label_ledger_audit(1, 1, 1),
        }

        violations = validator.validate(product)

        assert any(
            v.rule == "H.7"
            and v.evidence.get("audit_code")
            == "duplicate_folded_source_path"
            for v in violations
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
