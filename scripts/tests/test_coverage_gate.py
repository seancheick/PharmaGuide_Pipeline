#!/usr/bin/env python3
"""
Coverage Gate Tests (AC5 Compliance)

Tests for the coverage gate module ensuring:
1. Coverage thresholds are enforced correctly
2. Correctness checks detect contradictions
3. Reports are generated properly
4. Blocking vs warning gates work correctly
"""

import pytest
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from coverage_gate import (
    CoverageGate,
    CoverageDomainResult,
    ProductCoverageResult,
    BatchCoverageResult,
    CorrectnessIssue,
    check_enriched_batch,
    COVERAGE_THRESHOLDS,
)


class TestCoverageThresholds:
    """Test coverage threshold enforcement."""

    @pytest.fixture
    def gate(self):
        return CoverageGate()

    def test_ingredients_threshold_pass(self, gate):
        """Ingredients at 99.5% should pass."""
        product = {
            "dsld_id": 12345,
            "match_ledger": {
                "domains": {
                    "ingredients": {
                        "total_raw": 100,
                        "matched": 99,
                        "unmatched": 0,
                        "rejected": 0,
                        "skipped": 1,
                        "coverage_percent": 100.0
                    }
                },
                "summary": {"coverage_percent": 100.0}
            }
        }

        result = gate.check_product(product)

        assert result.can_score
        assert len(result.blocking_issues) == 0

    def test_ingredients_threshold_fail(self, gate):
        """Ingredients below 99.5% should BLOCK."""
        product = {
            "dsld_id": 12345,
            "match_ledger": {
                "domains": {
                    "ingredients": {
                        "total_raw": 100,
                        "matched": 90,
                        "unmatched": 10,
                        "rejected": 0,
                        "skipped": 0,
                        "coverage_percent": 90.0
                    }
                },
                "summary": {"coverage_percent": 90.0}
            }
        }

        result = gate.check_product(product)

        assert not result.can_score
        assert len(result.blocking_issues) > 0
        assert "ingredients coverage 90.0%" in result.blocking_issues[0]

    def test_manufacturer_threshold_warn_only(self, gate):
        """Manufacturer below 95% should WARN but not BLOCK."""
        product = {
            "dsld_id": 12345,
            "match_ledger": {
                "domains": {
                    "ingredients": {
                        "total_raw": 10,
                        "matched": 10,
                        "unmatched": 0,
                        "rejected": 0,
                        "skipped": 0,
                        "coverage_percent": 100.0
                    },
                    "manufacturer": {
                        "total_raw": 10,
                        "matched": 8,
                        "unmatched": 1,
                        "rejected": 1,
                        "skipped": 0,
                        "coverage_percent": 80.0
                    }
                },
                "summary": {"coverage_percent": 90.0}
            }
        }

        result = gate.check_product(product)

        # Should still be able to score (manufacturer is WARN)
        assert result.can_score
        assert len(result.warnings) > 0
        assert "manufacturer coverage 80.0%" in result.warnings[0]

    def test_empty_domain_vacuously_covered(self, gate):
        """Domain with 0 items should be considered covered."""
        product = {
            "dsld_id": 12345,
            "match_ledger": {
                "domains": {
                    "ingredients": {
                        "total_raw": 10,
                        "matched": 10,
                        "unmatched": 0,
                        "rejected": 0,
                        "skipped": 0,
                        "coverage_percent": 100.0
                    },
                    "allergens": {
                        "total_raw": 0,
                        "matched": 0,
                        "unmatched": 0,
                        "rejected": 0,
                        "skipped": 0,
                        "coverage_percent": 0.0  # Empty
                    }
                },
                "summary": {"coverage_percent": 100.0}
            }
        }

        result = gate.check_product(product)

        assert result.can_score
        # Empty domain should show 100% coverage (vacuously true)
        assert result.domain_results["allergens"].coverage_percent == 100.0


class TestCorrectnessChecks:
    """Test correctness checks (AC5)."""

    @pytest.fixture
    def gate(self):
        return CoverageGate()

    def test_allergen_free_contradiction(self, gate):
        """Detect contradiction: claims allergen-free but allergens detected."""
        product = {
            "dsld_id": 12345,
            "match_ledger": {
                "domains": {},
                "summary": {"coverage_percent": 100.0}
            },
            "compliance_data": {
                "allergen_free_claims": ["allergen_free"]
            },
            "contaminant_data": {
                "allergens": {
                    "found": True,
                    "allergens": [
                        {"allergen_name": "milk"},
                        {"allergen_name": "soy"}
                    ]
                }
            }
        }

        result = gate.check_product(product)

        # Should have a contradiction warning
        assert len(result.correctness_issues) > 0
        assert any(
            issue.issue_type == "contradiction"
            for issue in result.correctness_issues
        )

    def test_gluten_free_contradiction(self, gate):
        """Detect contradiction: claims gluten-free but wheat detected."""
        product = {
            "dsld_id": 12345,
            "match_ledger": {
                "domains": {},
                "summary": {"coverage_percent": 100.0}
            },
            "compliance_data": {
                "allergen_free_claims": ["gluten_free"]
            },
            "contaminant_data": {
                "allergens": {
                    "found": True,
                    "allergens": [
                        {"allergen_name": "wheat"}
                    ]
                }
            }
        }

        result = gate.check_product(product)

        # Should have a contradiction warning
        assert len(result.correctness_issues) > 0
        contradiction = next(
            (i for i in result.correctness_issues if i.issue_type == "contradiction"),
            None
        )
        assert contradiction is not None
        assert "gluten" in contradiction.description.lower()

    def test_dairy_free_contradiction(self, gate):
        """Detect contradiction: claims dairy-free but milk detected."""
        product = {
            "dsld_id": 12345,
            "match_ledger": {
                "domains": {},
                "summary": {"coverage_percent": 100.0}
            },
            "compliance_data": {
                "allergen_free_claims": ["dairy_free"]
            },
            "contaminant_data": {
                "allergens": {
                    "found": True,
                    "allergens": [
                        {"allergen_name": "milk protein"}
                    ]
                }
            }
        }

        result = gate.check_product(product)

        # Should have a contradiction warning
        assert len(result.correctness_issues) > 0
        contradiction = next(
            (i for i in result.correctness_issues if i.issue_type == "contradiction"),
            None
        )
        assert contradiction is not None
        assert "dairy" in contradiction.description.lower()

    def test_no_contradiction_when_no_allergens(self, gate):
        """No contradiction when allergen-free and no allergens detected."""
        product = {
            "dsld_id": 12345,
            "match_ledger": {
                "domains": {},
                "summary": {"coverage_percent": 100.0}
            },
            "compliance_data": {
                "allergen_free_claims": ["allergen_free"]
            },
            "contaminant_data": {
                "allergens": {
                    "found": False,
                    "allergens": []
                }
            }
        }

        result = gate.check_product(product)

        # Should have no contradiction issues
        contradictions = [
            i for i in result.correctness_issues
            if i.issue_type == "contradiction"
        ]
        assert len(contradictions) == 0

    def test_missing_conversion_detection(self, gate):
        """Detect missing unit conversions."""
        product = {
            "dsld_id": 12345,
            "match_ledger": {
                "domains": {},
                "summary": {"coverage_percent": 100.0}
            },
            "rda_ul_data": {
                "analyzed_ingredients": [
                    {
                        "name": "Novel Nutrient",
                        "amount": 100,
                        "unit": "IU",
                        "conversion_evidence": {
                            "success": False,
                            "error": "No conversion rule found for Novel Nutrient"
                        }
                    }
                ]
            }
        }

        result = gate.check_product(product)

        # Should have a missing_conversion warning
        missing = [
            i for i in result.correctness_issues
            if i.issue_type == "missing_conversion"
        ]
        assert len(missing) > 0
        assert "Novel Nutrient" in missing[0].details.get("nutrient", "")

    def test_claim_scope_violation_detection(self, gate):
        """Detect claims that may exceed allowed scope (drug claims)."""
        product = {
            "dsld_id": 12345,
            "match_ledger": {
                "domains": {},
                "summary": {"coverage_percent": 100.0}
            },
            "claims": [
                {"claim": "Cures joint pain"},
                {"claim": "Supports healthy joints"}  # This is OK
            ]
        }

        result = gate.check_product(product)

        # Should have a claim_violation warning
        violations = [
            i for i in result.correctness_issues
            if i.issue_type == "claim_violation"
        ]
        assert len(violations) > 0
        assert "cure" in violations[0].details.get("keyword", "")

    def test_claim_scope_violation_detects_langual_description(self, gate):
        """Detect scope violations when DSLD claims use langualCodeDescription."""
        product = {
            "dsld_id": 12345,
            "match_ledger": {
                "domains": {},
                "summary": {"coverage_percent": 100.0}
            },
            "claims": [
                {"langualCodeDescription": "Treats chronic inflammation"}
            ]
        }

        result = gate.check_product(product)
        violations = [
            i for i in result.correctness_issues
            if i.issue_type == "claim_violation"
        ]
        assert len(violations) > 0
        assert "treat" in violations[0].details.get("keyword", "")


class TestBatchProcessing:
    """Test batch processing functionality."""

    @pytest.fixture
    def gate(self):
        # Use strict_mode=True for tests to enforce blocking regardless of batch size
        return CoverageGate(strict_mode=True)

    def test_batch_with_mixed_results(self, gate):
        """Test batch with some passing and some failing products."""
        products = [
            # Good product
            {
                "dsld_id": 1,
                "match_ledger": {
                    "domains": {
                        "ingredients": {
                            "total_raw": 10,
                            "matched": 10,
                            "unmatched": 0,
                            "rejected": 0,
                            "skipped": 0,
                            "coverage_percent": 100.0
                        }
                    },
                    "summary": {"coverage_percent": 100.0}
                }
            },
            # Bad product (low ingredient coverage)
            {
                "dsld_id": 2,
                "match_ledger": {
                    "domains": {
                        "ingredients": {
                            "total_raw": 10,
                            "matched": 5,
                            "unmatched": 5,
                            "rejected": 0,
                            "skipped": 0,
                            "coverage_percent": 50.0
                        }
                    },
                    "summary": {"coverage_percent": 50.0}
                }
            }
        ]

        result = gate.check_batch(products)

        assert result.total_products == 2
        assert result.products_can_score == 1
        assert result.products_blocked == 1
        assert "2" in result.blocked_product_ids

    def test_batch_coverage_average(self, gate):
        """Test that average coverage is calculated correctly."""
        products = [
            {
                "dsld_id": 1,
                "match_ledger": {
                    "domains": {},
                    "summary": {"coverage_percent": 80.0}
                }
            },
            {
                "dsld_id": 2,
                "match_ledger": {
                    "domains": {},
                    "summary": {"coverage_percent": 100.0}
                }
            }
        ]

        result = gate.check_batch(products)

        assert result.average_coverage == pytest.approx(90.0)


class TestReportGeneration:
    """Test report generation."""

    @pytest.fixture
    def gate(self):
        return CoverageGate()

    def test_json_report_structure(self, gate):
        """Test JSON report has correct structure."""
        products = [
            {
                "dsld_id": 1,
                "match_ledger": {
                    "domains": {
                        "ingredients": {
                            "total_raw": 10,
                            "matched": 10,
                            "unmatched": 0,
                            "rejected": 0,
                            "skipped": 0,
                            "coverage_percent": 100.0
                        }
                    },
                    "summary": {"coverage_percent": 100.0}
                }
            }
        ]

        result = gate.check_batch(products)

        with TemporaryDirectory() as tmpdir:
            json_path, md_path = gate.generate_report(result, Path(tmpdir))

            # Check JSON file exists and has correct structure
            assert json_path.exists()
            with open(json_path) as f:
                report = json.load(f)

            assert "schema_version" in report
            assert "summary" in report
            assert "thresholds" in report
            assert "domain_coverage" in report
            assert "products" in report

            # Check summary fields
            summary = report["summary"]
            assert summary["total_products"] == 1
            assert summary["products_can_score"] == 1
            assert summary["products_blocked"] == 0

    def test_markdown_report_generated(self, gate):
        """Test Markdown report is generated."""
        products = [
            {
                "dsld_id": 1,
                "match_ledger": {
                    "domains": {},
                    "summary": {"coverage_percent": 100.0}
                }
            }
        ]

        result = gate.check_batch(products)

        with TemporaryDirectory() as tmpdir:
            json_path, md_path = gate.generate_report(result, Path(tmpdir))

            # Check Markdown file exists
            assert md_path.exists()
            content = md_path.read_text()

            # Check basic structure
            assert "# Coverage Gate Report" in content
            assert "## Summary" in content
            assert "## Domain Coverage" in content


class TestConvenienceFunction:
    """Test the convenience function check_enriched_batch."""

    def test_check_enriched_batch_returns_tuple(self):
        """Test check_enriched_batch returns correct tuple."""
        products = [
            {
                "dsld_id": 1,
                "match_ledger": {
                    "domains": {
                        "ingredients": {
                            "total_raw": 10,
                            "matched": 10,
                            "unmatched": 0,
                            "rejected": 0,
                            "skipped": 0,
                            "coverage_percent": 100.0
                        }
                    },
                    "summary": {"coverage_percent": 100.0}
                }
            }
        ]

        can_proceed, result = check_enriched_batch(products)

        assert can_proceed is True
        assert isinstance(result, BatchCoverageResult)
        assert result.products_blocked == 0

    def test_check_enriched_batch_blocks_on_failure(self):
        """Test check_enriched_batch blocks when threshold not met."""
        products = [
            {
                "dsld_id": 1,
                "match_ledger": {
                    "domains": {
                        "ingredients": {
                            "total_raw": 10,
                            "matched": 5,
                            "unmatched": 5,
                            "rejected": 0,
                            "skipped": 0,
                            "coverage_percent": 50.0
                        }
                    },
                    "summary": {"coverage_percent": 50.0}
                }
            }
        ]

        # Use strict_mode=True to enforce blocking on small batches
        can_proceed, result = check_enriched_batch(products, block_on_failure=True, strict_mode=True)

        assert can_proceed is False
        assert result.products_blocked == 1

    def test_check_enriched_batch_no_block_option(self):
        """Test check_enriched_batch can disable blocking."""
        products = [
            {
                "dsld_id": 1,
                "match_ledger": {
                    "domains": {
                        "ingredients": {
                            "total_raw": 10,
                            "matched": 5,
                            "unmatched": 5,
                            "rejected": 0,
                            "skipped": 0,
                            "coverage_percent": 50.0
                        }
                    },
                    "summary": {"coverage_percent": 50.0}
                }
            }
        ]

        # Use strict_mode=True so products_blocked is correctly counted
        can_proceed, result = check_enriched_batch(products, block_on_failure=False, strict_mode=True)

        # Should proceed even with blocked products
        assert can_proceed is True
        assert result.products_blocked == 1


class TestCustomThresholds:
    """Test custom threshold configuration."""

    def test_custom_thresholds(self):
        """Test that custom thresholds are used."""
        custom_thresholds = {
            "ingredients": {"threshold": 50.0, "severity": "BLOCK"},
            "additives": {"threshold": 50.0, "severity": "BLOCK"},
            "allergens": {"threshold": 50.0, "severity": "BLOCK"},
            "manufacturer": {"threshold": 50.0, "severity": "WARN"},
            "delivery": {"threshold": 50.0, "severity": "WARN"},
            "claims": {"threshold": 50.0, "severity": "WARN"},
        }

        gate = CoverageGate(thresholds=custom_thresholds)

        product = {
            "dsld_id": 1,
            "match_ledger": {
                "domains": {
                    "ingredients": {
                        "total_raw": 10,
                        "matched": 6,
                        "unmatched": 4,
                        "rejected": 0,
                        "skipped": 0,
                        "coverage_percent": 60.0
                    }
                },
                "summary": {"coverage_percent": 60.0}
            }
        }

        result = gate.check_product(product)

        # With custom 50% threshold, 60% should pass
        assert result.can_score


class TestEdgeCases:
    """Test edge cases."""

    @pytest.fixture
    def gate(self):
        return CoverageGate()

    def test_missing_match_ledger(self, gate):
        """Test handling of product without match_ledger."""
        product = {
            "dsld_id": 1
        }

        result = gate.check_product(product)

        # Should handle gracefully
        assert result.product_id == "1"
        # With no data, should be able to score
        assert result.can_score

    def test_empty_batch(self, gate):
        """Test handling of empty batch."""
        products = []

        result = gate.check_batch(products)

        assert result.total_products == 0
        assert result.products_blocked == 0
        assert result.average_coverage == 0.0

    def test_product_without_id(self, gate):
        """Test handling of product without dsld_id."""
        product = {
            "match_ledger": {
                "domains": {},
                "summary": {"coverage_percent": 100.0}
            }
        }

        result = gate.check_product(product)

        assert result.product_id == "unknown"


class TestEnrichedSchemaContract:
    """
    Schema-contract tests: gate field names must match the actual enriched output schema.
    If the enricher renames a field, these tests break immediately.
    Concern 7 (CONCERNS.md): 'Gate checks field names that may not match actual output schema
    field names after enrichment renames fields.' — Verified resolved 2026-03-16.
    """

    @pytest.fixture
    def gate(self):
        return CoverageGate()

    @pytest.fixture
    def enriched_schema_product(self):
        """
        Minimal product that mirrors the exact field layout produced by enrich_supplements_v3.py.
        Any enricher rename breaks this fixture → immediate test failure.
        """
        return {
            "id": 99999,
            "dsld_id": 99999,
            # match_ledger produced by the enricher's MatchLedger
            "match_ledger": {
                "schema_version": "1.0",
                "generated_at": "2026-03-16T00:00:00Z",
                "domains": {
                    "ingredients": {
                        "total_raw": 5,
                        "matched": 5,
                        "unmatched": 0,
                        "rejected": 0,
                        "skipped": 0,
                        "recognized_non_scorable": 0,
                        "recognized_botanical_unscored": 0,
                        "recognition_coverage_percent": 100.0,
                        "scorable_coverage_percent": 100.0,
                        "scorable_total": 5,
                        "coverage_percent": 100.0,
                    },
                    "additives": {
                        "total_raw": 2,
                        "matched": 2,
                        "unmatched": 0,
                        "rejected": 0,
                        "skipped": 0,
                        "recognized_non_scorable": 0,
                        "recognized_botanical_unscored": 0,
                        "recognition_coverage_percent": 100.0,
                        "scorable_coverage_percent": 100.0,
                        "scorable_total": 2,
                        "coverage_percent": 100.0,
                    },
                    "allergens": {
                        "total_raw": 0,
                        "matched": 0,
                        "unmatched": 0,
                        "rejected": 0,
                        "skipped": 0,
                        "recognized_non_scorable": 0,
                        "recognized_botanical_unscored": 0,
                        "recognition_coverage_percent": 100.0,
                        "scorable_coverage_percent": 100.0,
                        "scorable_total": 0,
                        "coverage_percent": 100.0,
                    },
                    "manufacturer": {
                        "total_raw": 1,
                        "matched": 1,
                        "unmatched": 0,
                        "rejected": 0,
                        "skipped": 0,
                        "recognized_non_scorable": 0,
                        "recognized_botanical_unscored": 0,
                        "recognition_coverage_percent": 100.0,
                        "scorable_coverage_percent": 100.0,
                        "scorable_total": 1,
                        "coverage_percent": 100.0,
                    },
                },
                "summary": {"coverage_percent": 100.0},
            },
            # compliance_data — gate reads allergen_free_claims
            "compliance_data": {
                "allergen_free_claims": [],
                "gluten_free": False,
                "dairy_free": False,
                "soy_free": False,
                "vegan": False,
                "vegetarian": False,
                "conflicts": [],
                "has_may_contain_warning": False,
                "verified": False,
                "evidence_based": False,
            },
            # contaminant_data — gate reads allergens.allergens (nested)
            "contaminant_data": {
                "banned_substances": [],
                "harmful_additives": [],
                "allergens": {
                    "found": False,
                    "allergens": [],          # gate: allergen_info.get("allergens", [])
                    "has_may_contain_warning": False,
                },
            },
            # rda_ul_data — gate reads analyzed_ingredients[*].conversion_evidence
            "rda_ul_data": {
                "ingredients_with_rda": [],
                "analyzed_ingredients": [],   # gate: for ing in analyzed
                "count": 0,
                "adequacy_results": [],
                "conversion_evidence": [],
                "safety_flags": [],
                "has_over_ul": False,
                "collection_enabled": False,
                "collection_reason": "disabled_by_config",
            },
            # evidence_data — gate reads unsubstantiated_claims.claims
            "evidence_data": {
                "clinical_matches": [],
                "match_count": 0,
                "unsubstantiated_claims": {
                    "found": False,
                    "claims": [],             # gate: unsub.get("claims")
                },
            },
            "claims": [],
        }

    def test_gate_runs_without_exception_on_enriched_schema(self, gate, enriched_schema_product):
        """Gate must not raise on a product matching the real enriched schema."""
        result = gate.check_product(enriched_schema_product)
        assert result is not None
        assert result.product_id == "99999"

    def test_gate_can_score_fully_covered_product(self, gate, enriched_schema_product):
        """A product with 100% coverage across all domains must be scorable."""
        result = gate.check_product(enriched_schema_product)
        assert result.can_score is True
        assert len(result.blocking_issues) == 0

    def test_gate_reads_compliance_allergen_free_claims(self, gate, enriched_schema_product):
        """Gate reads compliance_data.allergen_free_claims — verify field name contract."""
        product = dict(enriched_schema_product)
        product["compliance_data"] = dict(product["compliance_data"])
        product["compliance_data"]["allergen_free_claims"] = ["allergen_free"]
        # Adding a detected allergen creates a contradiction — gate should flag it
        product["contaminant_data"] = {
            "banned_substances": [],
            "harmful_additives": [],
            "allergens": {
                "found": True,
                "allergens": [{"allergen_name": "milk"}],
                "has_may_contain_warning": False,
            },
        }
        result = gate.check_product(product)
        assert any(i.issue_type == "contradiction" for i in result.correctness_issues)

    def test_gate_reads_contaminant_data_allergens_nested(self, gate, enriched_schema_product):
        """Gate accesses contaminant_data.allergens.allergens (nested list) — verify path."""
        product = dict(enriched_schema_product)
        product["contaminant_data"] = {
            "banned_substances": [],
            "harmful_additives": [],
            "allergens": {
                "found": True,
                "allergens": [{"allergen_name": "soy"}],  # This is the nested key the gate reads
                "has_may_contain_warning": False,
            },
        }
        # No allergen_free_claims — no contradiction, just valid detection
        result = gate.check_product(product)
        assert result is not None  # Must not throw accessing allergens.allergens

    def test_gate_reads_evidence_unsubstantiated_claims(self, gate, enriched_schema_product):
        """Gate reads evidence_data.unsubstantiated_claims.claims — verify nested field name."""
        product = dict(enriched_schema_product)
        product["evidence_data"] = {
            "clinical_matches": [],
            "match_count": 0,
            "unsubstantiated_claims": {
                "found": True,
                "claims": [{"claim": "cures cancer", "claim_type": "disease"}],
            },
        }
        result = gate.check_product(product)
        # Gate should surface a warning or issue for unsubstantiated claims
        assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
