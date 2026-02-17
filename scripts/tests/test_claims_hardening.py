"""
Test Claims Hardening System

Tests for the evidence-based claim detection system including:
- Positive pattern matching
- Negative pattern rejection
- Scope validation
- Proximity conflict detection
- Feature gate behavior
- Shadow preview mode

Run with: pytest tests/test_claims_hardening.py -v
"""

import pytest
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from enrich_supplements_v3 import SupplementEnricherV3
from score_supplements import SupplementScorer
from enrichment_contract_validator import EnrichmentContractValidator, ContractViolation


class TestClaimsRulesDatabase:
    """Test cert_claim_rules.json structure and content."""

    @pytest.fixture
    def rules_db(self):
        """Load the rules database."""
        rules_path = Path(__file__).parent.parent / "data" / "cert_claim_rules.json"
        with open(rules_path) as f:
            return json.load(f)

    def test_database_has_version(self, rules_db):
        """Database must have version information."""
        assert "_metadata" in rules_db
        assert "schema_version" in rules_db["_metadata"]
        assert rules_db["_metadata"]["schema_version"] == "4.0.0"

    def test_database_has_source_field_groups(self, rules_db):
        """Database must have centralized field groups."""
        assert "config" in rules_db
        groups = rules_db["config"]["source_field_groups"]
        assert "product_level_fields" in groups
        assert "ingredient_fields" in groups
        assert "any_field" in groups

    def test_third_party_programs_structure(self, rules_db):
        """Third-party programs must have required fields."""
        programs = rules_db.get("rules", {}).get("third_party_programs", {})
        assert "usp_verified" in programs

        usp = programs["usp_verified"]
        assert "id" in usp
        assert "display_name" in usp
        assert "dedupe_key" in usp
        assert "positive_patterns" in usp
        assert "negative_patterns" in usp
        assert "evidence_strength" in usp
        assert "points_if_eligible" in usp

    def test_usp_verified_has_required_tokens(self, rules_db):
        """USP Verified must require 'verified' or 'verification' token."""
        usp = rules_db["rules"]["third_party_programs"]["usp_verified"]
        assert "required_tokens" in usp
        assert "verified" in usp["required_tokens"] or "verification" in usp["required_tokens"]

    def test_allergen_claims_have_conflict_allergens(self, rules_db):
        """Allergen-free claims must specify conflict allergens."""
        allergen_claims = rules_db.get("rules", {}).get("allergen_free_claims", {})
        gluten_free = allergen_claims.get("gluten_free", {})

        assert "conflict_allergens" in gluten_free
        assert "wheat" in gluten_free["conflict_allergens"]
        assert "gluten" in gluten_free["conflict_allergens"]


class TestClaimValidationLogic:
    """Test the _check_claim_with_validation helper method."""

    @pytest.fixture
    def enricher(self):
        """Create enricher instance with mocked databases."""
        with patch.object(SupplementEnricherV3, '_load_all_databases'):
            with patch.object(SupplementEnricherV3, '_compile_patterns'):
                enricher = SupplementEnricherV3.__new__(SupplementEnricherV3)
                enricher.logger = MagicMock()
                enricher.databases = {}
                enricher.reference_versions = {}
                enricher.compiled_patterns = {}

                # Load actual rules database
                rules_path = Path(__file__).parent.parent / "data" / "cert_claim_rules.json"
                with open(rules_path) as f:
                    enricher.databases['cert_claim_rules'] = json.load(f)

                return enricher

    def test_usp_verified_positive_match(self, enricher):
        """Test that 'USP Verified' matches correctly."""
        field_groups = enricher._get_field_groups()
        rule = enricher.databases['cert_claim_rules']['rules']['third_party_programs']['usp_verified']

        text = "This product is USP Verified for quality"
        # Use 'statements' as source_field (in product_level_fields group)
        evidence = enricher._check_claim_with_validation(text, "statements", rule, field_groups)

        assert evidence is not None
        assert evidence['rule_id'] == 'CERT_USP_VERIFIED'
        assert evidence['score_eligible'] is True
        assert 'USP Verified' in evidence['matched_text']

    def test_usp_standards_negative_match(self, enricher):
        """Test that 'USP standards' is rejected (negative pattern)."""
        field_groups = enricher._get_field_groups()
        rule = enricher.databases['cert_claim_rules']['rules']['third_party_programs']['usp_verified']

        # Text with USP standards but NOT USP Verified
        text = "Made according to USP standards for purity"
        evidence = enricher._check_claim_with_validation(text, "all_text", rule, field_groups)

        # Should NOT match because 'verified' token is required
        if evidence:
            assert evidence['score_eligible'] is False
            assert 'required_tokens_missing' in (evidence.get('ineligibility_reason') or '')

    def test_gluten_free_with_conflict(self, enricher):
        """Test that gluten-free claim with wheat nearby gets conflict flagged."""
        field_groups = enricher._get_field_groups()
        rule = enricher.databases['cert_claim_rules']['rules']['allergen_free_claims']['gluten_free']

        # Text with gluten-free claim near wheat mention
        text = "gluten-free formula. Contains wheat germ extract."
        evidence = enricher._check_claim_with_validation(text, "all_text", rule, field_groups)

        assert evidence is not None
        assert evidence['rule_id'] == 'CLAIM_GLUTEN_FREE'
        # Should have proximity conflict
        assert len(evidence['proximity_conflicts']) > 0 or evidence['score_eligible'] is False

    def test_weak_evidence_not_scoreable(self, enricher):
        """Test that weak evidence claims are not score_eligible."""
        field_groups = enricher._get_field_groups()
        rule = enricher.databases['cert_claim_rules']['rules']['third_party_programs']['third_party_generic']

        text = "This product is third-party tested"
        # Use 'statements' as source_field (in product_level_fields group for this rule)
        evidence = enricher._check_claim_with_validation(text, "statements", rule, field_groups)

        if evidence:
            assert evidence['score_eligible'] is False
            assert evidence['ineligibility_reason'] == 'weak_evidence'


class TestFeatureGates:
    """Test feature gate behavior in scoring."""

    @pytest.fixture
    def scorer_gates_off(self):
        """Create scorer with all gates OFF."""
        with patch.object(SupplementScorer, '_load_config') as mock_config:
            mock_config.return_value = {
                "section_maximums": {"B_safety_purity": 45},
                "section_B_safety_purity": {
                    "B3_quality_certifications": {
                        "max": 16,
                        "third_party_testing": {"per_program": 5, "max_programs": 2, "max_total": 10},
                        "gmp_certified": {"points": 4},
                        "batch_traceability": {"points": 2}
                    }
                },
                "feature_gates": {
                    "enable_claims_scoring": False,
                    "enable_certification_scoring": False,
                    "enable_gmp_scoring": False,
                    "enable_batch_traceability_scoring": False,
                    "shadow_mode": True
                }
            }
            scorer = SupplementScorer.__new__(SupplementScorer)
            scorer.logger = MagicMock()
            scorer.config = mock_config.return_value
            scorer.feature_gates = scorer.config.get('feature_gates', {})
            scorer.section_b_config = scorer.config.get('section_B_safety_purity', {})
            return scorer

    @pytest.fixture
    def scorer_gates_on(self):
        """Create scorer with gates ON."""
        with patch.object(SupplementScorer, '_load_config') as mock_config:
            mock_config.return_value = {
                "section_maximums": {"B_safety_purity": 45},
                "section_B_safety_purity": {
                    "B3_quality_certifications": {
                        "max": 16,
                        "third_party_testing": {"per_program": 5, "max_programs": 2, "max_total": 10},
                        "gmp_certified": {"points": 4},
                        "batch_traceability": {"points": 2}
                    }
                },
                "feature_gates": {
                    "enable_claims_scoring": True,
                    "enable_certification_scoring": True,
                    "enable_gmp_scoring": True,
                    "enable_batch_traceability_scoring": True,
                    "shadow_mode": True
                }
            }
            scorer = SupplementScorer.__new__(SupplementScorer)
            scorer.logger = MagicMock()
            scorer.config = mock_config.return_value
            scorer.feature_gates = scorer.config.get('feature_gates', {})
            scorer.section_b_config = scorer.config.get('section_B_safety_purity', {})
            return scorer

    @pytest.mark.skip(reason="Scorer rewritten: _score_b3_certifications removed in v3.0 scorer")
    def test_gates_off_uses_legacy(self, scorer_gates_off):
        """When gates OFF, B3 scoring uses legacy detection."""
        cert_data = {
            "third_party_programs": {
                "programs": [{"name": "USP Verified", "verified": True}],
                "count": 1
            },
            "gmp": {"claimed": True},
            "batch_traceability": {"qualifies": True},
            "evidence_based": {
                "third_party_programs": [{"score_eligible": True, "points_if_eligible": 5}],
                "gmp_certifications": [],
                "batch_traceability": []
            }
        }
        b3_config = scorer_gates_off.section_b_config.get('B3_quality_certifications', {})

        score, notes, tp_programs = scorer_gates_off._score_b3_certifications(cert_data, b3_config)

        # Should use legacy data, not evidence-based
        assert score > 0
        assert any("Third-party" in n and "[evidence-based]" not in n for n in notes)

    @pytest.mark.skip(reason="Scorer rewritten: _score_b3_certifications removed in v3.0 scorer")
    def test_gates_on_uses_evidence(self, scorer_gates_on):
        """When gates ON, B3 scoring uses evidence-based detection."""
        cert_data = {
            "third_party_programs": {"programs": [], "count": 0},
            "gmp": {"claimed": False},
            "batch_traceability": {"qualifies": False},
            "evidence_based": {
                "third_party_programs": [{
                    "score_eligible": True,
                    "points_if_eligible": 5,
                    "display_name": "USP Verified",
                    "dedupe_key": "third_party_program:usp_verified",
                    "rule_id": "CERT_USP_VERIFIED"
                }],
                "gmp_certifications": [],
                "batch_traceability": []
            }
        }
        b3_config = scorer_gates_on.section_b_config.get('B3_quality_certifications', {})

        score, notes, tp_programs = scorer_gates_on._score_b3_certifications(cert_data, b3_config)

        # Should use evidence-based data
        assert score == 5
        assert any("[evidence-based]" in n for n in notes)


class TestContractValidation:
    """Test contract validation rules for claims."""

    @pytest.fixture
    def validator(self):
        return EnrichmentContractValidator()

    def test_e1_usp_verified_strength(self, validator):
        """E.1: USP Verified must have strong evidence to be score_eligible."""
        product = {
            "id": "test-123",
            "certification_data": {
                "evidence_based": {
                    "third_party_programs": [{
                        "rule_id": "CERT_USP_VERIFIED",
                        "score_eligible": True,
                        "evidence_strength": "medium",  # Should be 'strong'
                        "matched_text": "USP Verified"
                    }]
                }
            }
        }

        violations = validator._validate_claims_consistency(product, "test-123")

        assert len(violations) > 0
        assert any(v.rule == "E.1" for v in violations)

    def test_e2_allergen_conflict_blocks_scoring(self, validator):
        """E.2: Allergen-free claim with conflicts cannot be score_eligible."""
        product = {
            "id": "test-123",
            "certification_data": {"evidence_based": {}},
            "compliance_data": {
                "evidence_based": {
                    "allergen_free_claims": [{
                        "rule_id": "CLAIM_GLUTEN_FREE",
                        "score_eligible": True,
                        "proximity_conflicts": ["wheat detected"],  # Has conflict!
                        "display_name": "Gluten-Free",
                        "matched_text": "gluten-free"
                    }]
                }
            }
        }

        violations = validator._validate_claims_consistency(product, "test-123")

        assert len(violations) > 0
        assert any(v.rule == "E.2" for v in violations)

    def test_e5_missing_rule_id(self, validator):
        """E.5: Evidence objects must have valid rule_id."""
        product = {
            "id": "test-123",
            "certification_data": {
                "evidence_based": {
                    "third_party_programs": [{
                        "rule_id": "",  # Missing!
                        "score_eligible": False,
                        "display_name": "Unknown Cert",
                        "matched_text": "certified"
                    }],
                    "gmp_certifications": [],
                    "batch_traceability": []
                }
            },
            "compliance_data": {"evidence_based": {"allergen_free_claims": []}},
            "organic": {"evidence_based": {"organic_certifications": []}}
        }

        violations = validator._validate_claims_consistency(product, "test-123")

        assert len(violations) > 0
        assert any(v.rule == "E.5" for v in violations)


class TestNegativePatterns:
    """Test specific negative pattern rejections."""

    @pytest.fixture
    def enricher(self):
        """Create enricher with rules database."""
        with patch.object(SupplementEnricherV3, '_load_all_databases'):
            with patch.object(SupplementEnricherV3, '_compile_patterns'):
                enricher = SupplementEnricherV3.__new__(SupplementEnricherV3)
                enricher.logger = MagicMock()
                enricher.databases = {}
                enricher.reference_versions = {}
                enricher.compiled_patterns = {}

                rules_path = Path(__file__).parent.parent / "data" / "cert_claim_rules.json"
                with open(rules_path) as f:
                    enricher.databases['cert_claim_rules'] = json.load(f)

                return enricher

    def test_usp_grade_not_usp_verified(self, enricher):
        """'USP grade' should not match as USP Verified."""
        field_groups = enricher._get_field_groups()
        rule = enricher.databases['cert_claim_rules']['rules']['third_party_programs']['usp_verified']

        text = "Contains USP grade vitamin D3"
        evidence = enricher._check_claim_with_validation(text, "all_text", rule, field_groups)

        # Should either not match or be negated
        if evidence:
            assert evidence['score_eligible'] is False

    def test_not_gluten_free_rejected(self, enricher):
        """'not gluten-free' should be rejected."""
        field_groups = enricher._get_field_groups()
        rule = enricher.databases['cert_claim_rules']['rules']['allergen_free_claims']['gluten_free']

        text = "This product is not gluten-free"
        evidence = enricher._check_claim_with_validation(text, "all_text", rule, field_groups)

        if evidence:
            assert evidence['negation']['negated'] is True or evidence['score_eligible'] is False

    def test_may_contain_gluten_rejected(self, enricher):
        """'may contain gluten' should reject gluten-free claim."""
        field_groups = enricher._get_field_groups()
        rule = enricher.databases['cert_claim_rules']['rules']['allergen_free_claims']['gluten_free']

        text = "Gluten-free product. May contain gluten from shared equipment."
        evidence = enricher._check_claim_with_validation(text, "all_text", rule, field_groups)

        if evidence:
            # Should be negated or have proximity conflict
            assert evidence['negation']['negated'] is True or evidence['score_eligible'] is False


class TestDeduplication:
    """Test dedupe_key functionality."""

    def test_nsf_programs_have_distinct_dedupe_keys(self):
        """NSF Sport, NSF Certified, NSF GMP should have different dedupe_keys."""
        rules_path = Path(__file__).parent.parent / "data" / "cert_claim_rules.json"
        with open(rules_path) as f:
            rules = json.load(f)

        nsf_sport = rules['rules']['third_party_programs']['nsf_sport']
        nsf_contents = rules['rules']['third_party_programs']['nsf_contents_certified']
        nsf_gmp = rules['rules']['gmp_certifications']['nsf_gmp']

        # All should have different dedupe_keys
        dedupe_keys = {
            nsf_sport.get('dedupe_key'),
            nsf_contents.get('dedupe_key'),
            nsf_gmp.get('dedupe_key')
        }

        assert len(dedupe_keys) == 3  # All unique


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
