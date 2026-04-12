#!/usr/bin/env python3
"""
Coverage Gate Module (AC5 Compliance)

Provides coverage threshold enforcement and correctness checks before scoring.
This module implements the Phase 6 requirements from the pipeline hardening plan.

Features:
1. Coverage threshold checks per domain (ingredients, additives, allergens, manufacturer)
2. Correctness checks (contradictions, missing conversions)
3. Report generation (JSON + Markdown)
4. Blocking vs warning gates

Usage:
    from coverage_gate import CoverageGate

    gate = CoverageGate()
    result = gate.check_product(enriched_product)
    if not result.can_score:
        print(f"Blocked: {result.blocking_issues}")

    # Or check entire batch
    batch_result = gate.check_batch(enriched_products)
    gate.generate_report(batch_result, output_dir)
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, UTC
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

logger = logging.getLogger(__name__)


# =============================================================================
# COVERAGE THRESHOLDS CONFIGURATION
# =============================================================================
# Default thresholds per domain. Can be overridden via:
# 1. Constructor parameter (per-run override)
# 2. Category-specific overrides (future: botanicals vs vitamins)
# 3. Region-specific overrides (future: DSLD data quality variations)
#
# Example per-run override:
#   gate = CoverageGate(thresholds={"ingredients": {"threshold": 95.0, "severity": "WARN"}})
#
# Example future category override structure (not yet implemented):
#   CATEGORY_OVERRIDES = {
#       "botanical": {"ingredients": {"threshold": 95.0, "severity": "WARN"}},
#       "probiotic": {"ingredients": {"threshold": 98.0, "severity": "BLOCK"}},
#   }
# =============================================================================
COVERAGE_THRESHOLDS = {
    # ==========================================================================
    # CORE SCORING DOMAINS (severity=BLOCK)
    # These domains directly affect the score. Low coverage blocks scoring.
    # ==========================================================================
    "ingredients": {
        "threshold": 99.5,
        "severity": "BLOCK",
        "scoring_impact": "penalty",  # Unmapped ingredients penalized in Section A
    },
    "additives": {
        "threshold": 98.0,
        "severity": "BLOCK",
        "scoring_impact": "penalty",  # Harmful additives penalized in Section B
    },
    "allergens": {
        "threshold": 98.0,
        "severity": "BLOCK",
        "scoring_impact": "penalty",  # Allergens penalized in Section B
    },

    # ==========================================================================
    # BONUS-ONLY / OPTIONAL DOMAINS (severity=WARN)
    # These domains provide bonus points if matched, but NEVER block scoring.
    # Low coverage generates warnings only.
    # ==========================================================================
    "manufacturer": {
        "threshold": 95.0,
        "severity": "WARN",
        "scoring_impact": "bonus",  # +3 points in Section D if exact match
        # POLICY: Manufacturer is BONUS-ONLY
        # - Exact match → +3 bonus points (Section D: Brand Trust)
        # - Fuzzy match → 0 points (rejected for scoring)
        # - No match → 0 points, scoring proceeds normally
        # - Coverage severity is WARN-only, NEVER blocks scoring
        # - All outcomes auditable via match_ledger.manufacturer
    },
    "delivery": {
        "threshold": 90.0,
        "severity": "WARN",
        "scoring_impact": "bonus",  # Delivery form affects bioavailability tier
    },
    "claims": {
        "threshold": 90.0,
        "severity": "WARN",
        "scoring_impact": "none",  # Claims are informational, no score impact
    },
}

# Future: Category-specific threshold overrides (structure reserved, not active)
# To enable: pass category_overrides to CoverageGate constructor
CATEGORY_THRESHOLD_OVERRIDES: Dict[str, Dict[str, Dict[str, Any]]] = {
    # "botanical": {
    #     "ingredients": {"threshold": 95.0, "severity": "WARN"},
    # },
    # "probiotic": {
    #     "allergens": {"threshold": 95.0, "severity": "WARN"},
    # },
}


# =============================================================================
# FAIL-CLOSED DEFAULT FOR FUTURE DOMAINS
# =============================================================================
# When a new domain is encountered that is NOT in COVERAGE_THRESHOLDS, we apply
# fail-closed behavior: the domain defaults to BLOCK severity with 95% threshold.
#
# To add a new domain properly, developers MUST:
# 1. Add entry to COVERAGE_THRESHOLDS with explicit threshold and severity
# 2. Document the scoring_impact (bonus/penalty/none) in comments
# 3. Add tests for the new domain in tests/test_coverage_gate.py
#
# This prevents silent failures where new domains pass through with no validation.
#
# Domain configuration requirements:
# - severity: "BLOCK" (blocks scoring) or "WARN" (allows scoring with warning)
# - scoring_impact: "bonus" (extra points), "penalty" (point deduction), "none" (no effect)
# - threshold: float 0-100 representing minimum coverage percent
# =============================================================================
FAIL_CLOSED_DEFAULT = {
    "threshold": 95.0,
    "severity": "BLOCK",
    "scoring_impact": "unknown",  # Forces developer to explicitly declare
}


def get_domain_threshold(domain: str, custom_thresholds: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Get threshold configuration for a domain with fail-closed default.

    Args:
        domain: The domain name (e.g., "ingredients", "manufacturer")
        custom_thresholds: Optional custom thresholds to override defaults

    Returns:
        Dict with keys: threshold, severity, (optionally scoring_impact)

    Note:
        Unknown domains will trigger a warning and use FAIL_CLOSED_DEFAULT.
        This ensures new domains cannot silently bypass validation.
    """
    # Check custom thresholds first
    if custom_thresholds and domain in custom_thresholds:
        return custom_thresholds[domain]

    # Check known domains
    if domain in COVERAGE_THRESHOLDS:
        return COVERAGE_THRESHOLDS[domain]

    # Fail-closed: unknown domain gets strict default
    logger.warning(
        f"Unknown domain '{domain}' encountered - applying fail-closed default "
        f"(threshold={FAIL_CLOSED_DEFAULT['threshold']}%, severity={FAIL_CLOSED_DEFAULT['severity']}). "
        f"Add '{domain}' to COVERAGE_THRESHOLDS with explicit configuration."
    )
    return FAIL_CLOSED_DEFAULT.copy()


# Small batch handling configuration
SMALL_BATCH_CONFIG = {
    # Minimum products to enforce percentage thresholds strictly
    "min_products_for_strict": 50,
    # Minimum entities per domain to enforce percentage thresholds
    "min_entities_for_percentage": 10,
    # Absolute count thresholds (allow up to N unmatched regardless of percentage)
    "max_unmatched_absolute": {
        "ingredients": 2,  # Allow up to 2 unmatched ingredients in small batches
        "additives": 1,
        "allergens": 1,
        "manufacturer": 2,
        "delivery": 2,
        "claims": 3,
    },
}

# Contradictory claim patterns
ALLERGEN_FREE_CLAIMS = [
    "allergen-free",
    "allergen free",
    "hypoallergenic",
    "no known allergens",
]

GLUTEN_FREE_CLAIMS = [
    "gluten-free",
    "gluten free",
    "certified gluten-free",
]

DAIRY_FREE_CLAIMS = [
    "dairy-free",
    "dairy free",
    "lactose-free",
    "lactose free",
    "no dairy",
]


@dataclass
class CorrectnessIssue:
    """A detected correctness issue."""
    issue_type: str  # "contradiction", "missing_conversion", "claim_violation"
    severity: str  # "WARN", "ERROR"
    description: str
    details: Dict[str, Any] = field(default_factory=dict)
    raw_source_text: Optional[str] = None
    raw_source_path: Optional[str] = None


@dataclass
class CoverageDomainResult:
    """Coverage result for a single domain."""
    domain: str
    total: int
    matched: int
    unmatched: int
    coverage_percent: float
    threshold: float
    passes: bool
    severity: str  # "BLOCK" or "WARN"
    # Additional fields for detailed breakdown (optional, default to 0)
    skipped: int = 0
    recognized_non_scorable: int = 0
    recognized_botanical_unscored: int = 0
    scorable_total: int = 0
    scorable_coverage_percent: float = 0.0


@dataclass
class ProductCoverageResult:
    """Coverage check result for a single product."""
    product_id: str
    can_score: bool
    overall_coverage: float
    domain_results: Dict[str, CoverageDomainResult]
    correctness_issues: List[CorrectnessIssue]
    blocking_issues: List[str]
    warnings: List[str]


@dataclass
class BatchCoverageResult:
    """Coverage check result for an entire batch."""
    total_products: int
    products_can_score: int
    products_blocked: int
    average_coverage: float
    domain_coverage_summary: Dict[str, float]
    total_correctness_issues: int
    total_blocking_issues: int
    total_warnings: int
    product_results: List[ProductCoverageResult]
    blocked_product_ids: List[str]
    issues_by_type: Dict[str, int]


class CoverageGate:
    """
    Coverage gate for enrichment output validation.

    Ensures coverage thresholds are met before scoring and
    detects correctness issues like contradictions.

    Small Batch Handling:
    - For batches < min_products_for_strict, BLOCK is downgraded to WARN
    - For domains with < min_entities_for_percentage, uses absolute count threshold
    - This prevents frustrating failures on small test runs while maintaining
      strictness for production batches
    """

    def __init__(
        self,
        thresholds: Dict = None,
        small_batch_config: Dict = None,
        strict_mode: bool = False
    ):
        """
        Initialize coverage gate.

        Args:
            thresholds: Custom thresholds dict (uses defaults if None)
            small_batch_config: Small batch handling config (uses defaults if None)
            strict_mode: If True, always enforce strict thresholds regardless of batch size
        """
        self.thresholds = thresholds or COVERAGE_THRESHOLDS
        self.small_batch_config = small_batch_config or SMALL_BATCH_CONFIG
        self.strict_mode = strict_mode
        self._batch_size = 0  # Set during check_batch

    def check_product(self, product: Dict) -> ProductCoverageResult:
        """
        Check coverage and correctness for a single product.

        Args:
            product: Enriched product dict with match_ledger

        Returns:
            ProductCoverageResult with coverage metrics and issues
        """
        product_id = str(product.get("dsld_id", product.get("id", "unknown")))

        # Get match ledger
        match_ledger = product.get("match_ledger", {})
        domains = match_ledger.get("domains", {})

        # Check each domain
        domain_results = {}
        blocking_issues = []
        warnings = []

        for domain_name, config in self.thresholds.items():
            domain_data = domains.get(domain_name, {})

            total = domain_data.get("total_raw", 0)
            matched = domain_data.get("matched", 0)
            unmatched = domain_data.get("unmatched", 0)
            skipped = domain_data.get("skipped", 0)
            coverage = domain_data.get("coverage_percent", 0.0)

            # Extract additional breakdown fields
            recognized_non_scorable = domain_data.get("recognized_non_scorable", 0)
            recognized_botanical_unscored = domain_data.get("recognized_botanical_unscored", 0)
            scorable_total = domain_data.get("scorable_total", 0)
            # Use scorable_coverage_percent if available, fallback to coverage_percent
            # (the ledger sets coverage_percent = scorable_coverage_percent for compatibility)
            scorable_coverage = domain_data.get("scorable_coverage_percent", coverage)

            # If no data for this domain, skip
            if total == 0:
                domain_results[domain_name] = CoverageDomainResult(
                    domain=domain_name,
                    total=0,
                    matched=0,
                    unmatched=0,
                    coverage_percent=100.0,  # No data = vacuously covered
                    threshold=config["threshold"],
                    passes=True,
                    severity=config["severity"],
                    skipped=skipped,
                    recognized_non_scorable=0,
                    recognized_botanical_unscored=0,
                    scorable_total=0,
                    scorable_coverage_percent=100.0,  # Vacuously covered
                )
                continue

            unmatched = domain_data.get("unmatched", 0) + domain_data.get("rejected", 0)
            # GATE uses scorable_coverage_percent, NOT recognition_coverage_percent
            # Note: coverage_percent is a legacy alias for scorable_coverage_percent (see match_ledger.py:598)
            # This ensures botanical-heavy products pass gate when bioactives are fully matched
            passes = scorable_coverage >= config["threshold"]

            domain_result = CoverageDomainResult(
                domain=domain_name,
                total=total,
                matched=matched,
                unmatched=unmatched,
                coverage_percent=coverage,
                threshold=config["threshold"],
                passes=passes,
                severity=config["severity"],
                skipped=skipped,
                recognized_non_scorable=recognized_non_scorable,
                recognized_botanical_unscored=recognized_botanical_unscored,
                scorable_total=scorable_total,
                scorable_coverage_percent=scorable_coverage,
            )
            domain_results[domain_name] = domain_result

            if not passes:
                msg = f"{domain_name} coverage {coverage:.1f}% < {config['threshold']}%"
                effective_severity = self._get_effective_severity(
                    domain_name, config["severity"], total, unmatched
                )
                if effective_severity == "BLOCK":
                    blocking_issues.append(msg)
                else:
                    warnings.append(msg)

        # Run correctness checks
        correctness_issues = self._check_correctness(product)

        # Add correctness issues to warnings
        for issue in correctness_issues:
            if issue.severity == "ERROR":
                blocking_issues.append(f"[{issue.issue_type}] {issue.description}")
            else:
                warnings.append(f"[{issue.issue_type}] {issue.description}")

        # Calculate overall coverage
        summary = match_ledger.get("summary", {})
        overall_coverage = summary.get("coverage_percent", 0.0)

        can_score = len(blocking_issues) == 0

        return ProductCoverageResult(
            product_id=product_id,
            can_score=can_score,
            overall_coverage=overall_coverage,
            domain_results=domain_results,
            correctness_issues=correctness_issues,
            blocking_issues=blocking_issues,
            warnings=warnings
        )

    def _get_effective_severity(
        self,
        domain: str,
        base_severity: str,
        total_entities: int,
        unmatched_count: int
    ) -> str:
        """
        Determine effective severity considering small batch handling.

        For small batches or domains with few entities, BLOCK may be
        downgraded to WARN to prevent frustrating failures on test runs.

        Args:
            domain: Domain name (ingredients, additives, etc.)
            base_severity: Original severity from thresholds config
            total_entities: Total entities in this domain
            unmatched_count: Number of unmatched entities

        Returns:
            Effective severity: "BLOCK" or "WARN"
        """
        # If strict mode, always use base severity
        if self.strict_mode:
            return base_severity

        # Only potentially downgrade BLOCK to WARN
        if base_severity != "BLOCK":
            return base_severity

        # Check if this is a small batch
        min_products = self.small_batch_config.get("min_products_for_strict", 50)
        min_entities = self.small_batch_config.get("min_entities_for_percentage", 10)
        max_unmatched = self.small_batch_config.get("max_unmatched_absolute", {}).get(domain, 2)

        # Small batch: downgrade BLOCK to WARN
        if self._batch_size > 0 and self._batch_size < min_products:
            logger.info(
                f"Small batch ({self._batch_size} products): downgrading {domain} "
                f"severity from BLOCK to WARN"
            )
            return "WARN"

        # Few entities in domain: use absolute threshold
        if total_entities < min_entities:
            if unmatched_count <= max_unmatched:
                logger.info(
                    f"Small domain ({total_entities} entities in {domain}): "
                    f"{unmatched_count} unmatched <= {max_unmatched} allowed, "
                    f"downgrading to WARN"
                )
                return "WARN"

        return base_severity

    def _check_correctness(self, product: Dict) -> List[CorrectnessIssue]:
        """
        Run correctness checks on an enriched product.

        Checks:
        1. Claim ↔ allergen contradictions
        2. Missing expected conversions
        3. Claim scope violations

        Returns:
            List of CorrectnessIssue
        """
        issues = []

        # Check claim ↔ allergen contradictions
        issues.extend(self._check_claim_allergen_contradictions(product))

        # Check missing conversions
        issues.extend(self._check_missing_conversions(product))

        # Check claim scope violations
        issues.extend(self._check_claim_scope_violations(product))

        return issues

    def _check_claim_allergen_contradictions(self, product: Dict) -> List[CorrectnessIssue]:
        """Check for contradictions between claims and detected allergens."""
        issues = []

        # Get claims from enricher's compliance_data (not "claims_data")
        compliance = product.get("compliance_data", {})
        # allergen_free_claims is a list of strings (e.g. ["gluten_free", "dairy_free"])
        allergen_free_claims = compliance.get("allergen_free_claims", [])
        # Normalize identifiers: "allergen_free" → "allergen free" for pattern matching
        claim_texts = [str(c).lower().replace('_', ' ').replace('-', ' ') for c in allergen_free_claims if c]

        # Get allergens from enricher's contaminant_data (not "allergen_data")
        contaminant = product.get("contaminant_data", {})
        allergen_info = contaminant.get("allergens", {})
        detected_allergens = allergen_info.get("allergens", [])
        allergen_names = [a.get("allergen_name", "").lower() for a in detected_allergens if a.get("allergen_name")]

        # Check "allergen-free" claims when allergens detected
        for claim in claim_texts:
            if any(pattern in claim for pattern in ALLERGEN_FREE_CLAIMS):
                if allergen_names:
                    issues.append(CorrectnessIssue(
                        issue_type="contradiction",
                        severity="WARN",
                        description=f"Claims 'allergen-free' but allergens detected: {allergen_names}",
                        details={
                            "claim": claim,
                            "detected_allergens": allergen_names
                        }
                    ))

            # Check "gluten-free" with gluten detected
            if any(pattern in claim for pattern in GLUTEN_FREE_CLAIMS):
                gluten_allergens = [a for a in allergen_names if "gluten" in a or "wheat" in a]
                if gluten_allergens:
                    issues.append(CorrectnessIssue(
                        issue_type="contradiction",
                        severity="WARN",
                        description=f"Claims 'gluten-free' but gluten allergens detected: {gluten_allergens}",
                        details={
                            "claim": claim,
                            "gluten_allergens": gluten_allergens
                        }
                    ))

            # Check "dairy-free" with dairy detected
            if any(pattern in claim for pattern in DAIRY_FREE_CLAIMS):
                dairy_allergens = [a for a in allergen_names if "milk" in a or "dairy" in a or "lactose" in a]
                if dairy_allergens:
                    issues.append(CorrectnessIssue(
                        issue_type="contradiction",
                        severity="WARN",
                        description=f"Claims 'dairy-free' but dairy allergens detected: {dairy_allergens}",
                        details={
                            "claim": claim,
                            "dairy_allergens": dairy_allergens
                        }
                    ))

        return issues

    def _check_missing_conversions(self, product: Dict) -> List[CorrectnessIssue]:
        """Check for ingredients that failed unit conversion."""
        issues = []

        # Check RDA/UL data for conversion failures
        rda_data = product.get("rda_ul_data", {})
        analyzed = rda_data.get("analyzed_ingredients", [])

        for ing in analyzed:
            conversion = ing.get("conversion_evidence", {})
            if conversion and not conversion.get("success", True):
                error = conversion.get("error", "Unknown conversion error")
                if "No conversion rule found" in error or "No conversion" in error:
                    issues.append(CorrectnessIssue(
                        issue_type="missing_conversion",
                        severity="WARN",
                        description=f"Unit conversion failed: {error}",
                        details={
                            "nutrient": ing.get("name", "unknown"),
                            "original_amount": ing.get("amount"),
                            "original_unit": ing.get("unit"),
                            "error": error
                        },
                        raw_source_text=ing.get("raw_source_text"),
                        raw_source_path=ing.get("raw_source_path")
                    ))

        return issues

    def _check_claim_scope_violations(self, product: Dict) -> List[CorrectnessIssue]:
        """Check for claims that exceed allowed scope."""
        issues = []

        # Check claims from multiple sources:
        # 1. Root-level DSLD claims (structure/function claims from label)
        # 2. Enricher's unsubstantiated_claims detection
        claims = list(product.get("claims", []))
        unsub = product.get("evidence_data", {}).get("unsubstantiated_claims", {})
        if unsub.get("claims"):
            claims.extend(unsub["claims"])

        # Check for structure/function claims that might be drug claims
        drug_claim_keywords = [
            "cure", "treat", "prevent disease", "diagnose",
            "mitigate", "therapeutic"
        ]

        def _extract_claim_text(claim: Any) -> Tuple[str, Optional[str]]:
            """Normalize heterogeneous claim payloads into text + type."""
            if isinstance(claim, str):
                return claim, None
            if isinstance(claim, dict):
                text = (
                    claim.get("claim")
                    or claim.get("text")
                    or claim.get("langualCodeDescription")
                    or claim.get("notes")
                    or claim.get("type")
                    or ""
                )
                claim_type = claim.get("claim_type") or claim.get("type")
                return str(text), str(claim_type) if claim_type else None
            return "", None

        for claim in claims:
            claim_text_raw, claim_type = _extract_claim_text(claim)
            claim_text = claim_text_raw.lower()
            if not claim_text:
                continue

            for keyword in drug_claim_keywords:
                if keyword in claim_text:
                    issues.append(CorrectnessIssue(
                        issue_type="claim_violation",
                        severity="WARN",
                        description=f"Claim may exceed allowed scope (potential drug claim): '{keyword}' found",
                        details={
                            "claim": claim_text_raw,
                            "keyword": keyword,
                            "claim_type": claim_type
                        }
                    ))
                    break  # One warning per claim

        return issues

    def check_batch(self, products: List[Dict]) -> BatchCoverageResult:
        """
        Check coverage for an entire batch of products.

        Args:
            products: List of enriched product dicts

        Returns:
            BatchCoverageResult with aggregate metrics
        """
        # Set batch size for small-batch handling
        self._batch_size = len(products)

        # Log small batch warning if applicable
        min_products = self.small_batch_config.get("min_products_for_strict", 50)
        if self._batch_size < min_products and not self.strict_mode:
            logger.warning(
                f"Small batch detected ({self._batch_size} < {min_products} products). "
                f"BLOCK severities may be downgraded to WARN. "
                f"Use strict_mode=True to enforce strict thresholds."
            )

        product_results = []
        blocked_ids = []
        total_coverage = 0.0
        domain_coverages = {d: [] for d in self.thresholds.keys()}
        issues_by_type = {}

        for product in products:
            result = self.check_product(product)
            product_results.append(result)

            total_coverage += result.overall_coverage

            if not result.can_score:
                blocked_ids.append(result.product_id)

            for domain, domain_result in result.domain_results.items():
                if domain_result.total > 0:
                    domain_coverages[domain].append(domain_result.coverage_percent)

            for issue in result.correctness_issues:
                issues_by_type[issue.issue_type] = issues_by_type.get(issue.issue_type, 0) + 1

        # Calculate averages
        avg_coverage = total_coverage / len(products) if products else 0.0

        domain_summary = {}
        for domain, coverages in domain_coverages.items():
            if coverages:
                domain_summary[domain] = sum(coverages) / len(coverages)
            else:
                domain_summary[domain] = 100.0  # No data

        # Count issues
        total_issues = sum(len(r.correctness_issues) for r in product_results)
        total_blocking = sum(len(r.blocking_issues) for r in product_results)
        total_warnings = sum(len(r.warnings) for r in product_results)

        return BatchCoverageResult(
            total_products=len(products),
            products_can_score=len(products) - len(blocked_ids),
            products_blocked=len(blocked_ids),
            average_coverage=avg_coverage,
            domain_coverage_summary=domain_summary,
            total_correctness_issues=total_issues,
            total_blocking_issues=total_blocking,
            total_warnings=total_warnings,
            product_results=product_results,
            blocked_product_ids=blocked_ids,
            issues_by_type=issues_by_type
        )

    def generate_report(
        self,
        batch_result: BatchCoverageResult,
        output_dir: Path,
        filename_prefix: str = "coverage_report"
    ) -> Tuple[Path, Path]:
        """
        Generate coverage report files (JSON and Markdown).

        Args:
            batch_result: BatchCoverageResult from check_batch
            output_dir: Directory to write reports
            filename_prefix: Prefix for report files

        Returns:
            Tuple of (json_path, markdown_path)
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate JSON report
        json_report = self._build_json_report(batch_result)
        json_path = output_dir / f"{filename_prefix}.json"
        with open(json_path, 'w') as f:
            json.dump(json_report, f, indent=2)

        # Generate Markdown report
        md_report = self._build_markdown_report(batch_result)
        md_path = output_dir / f"{filename_prefix}.md"
        with open(md_path, 'w') as f:
            f.write(md_report)

        logger.info(f"Generated coverage reports: {json_path}, {md_path}")
        return json_path, md_path

    def _build_domain_breakdown_section(self, result: BatchCoverageResult) -> List[str]:
        """
        Build detailed per-domain count breakdown section.

        Aggregates counts across all products to show:
        - Total items per domain
        - Matched, unmatched, skipped, recognized_non_scorable counts
        - Recognition vs scorable coverage distinction
        """
        lines = []

        # Aggregate counts across all products
        domain_totals: Dict[str, Dict[str, Any]] = {}

        for pr in result.product_results:
            for domain_name, domain_result in pr.domain_results.items():
                if domain_name not in domain_totals:
                    domain_totals[domain_name] = {
                        "total": 0,
                        "matched": 0,
                        "unmatched": 0,
                        "skipped": 0,
                        "recognized_non_scorable": 0,
                        "recognized_botanical_unscored": 0,
                        "scorable_total": 0,
                    }

                domain_totals[domain_name]["total"] += domain_result.total
                domain_totals[domain_name]["matched"] += domain_result.matched
                domain_totals[domain_name]["unmatched"] += domain_result.unmatched
                domain_totals[domain_name]["skipped"] += domain_result.skipped
                domain_totals[domain_name]["recognized_non_scorable"] += domain_result.recognized_non_scorable
                domain_totals[domain_name]["recognized_botanical_unscored"] += domain_result.recognized_botanical_unscored
                domain_totals[domain_name]["scorable_total"] += domain_result.scorable_total

        # Only add section if we have meaningful data
        if not domain_totals or all(
            totals["total"] == 0 for totals in domain_totals.values()
        ):
            return lines

        lines.extend([
            "",
            "### Domain Count Breakdown (Aggregated)",
            "",
            "> **Coverage gate uses Scorable Coverage only.** Botanicals and excipients do not affect the gate.",
            "",
            "| Domain | Total | Matched | Unmatched | Skipped | Excipients | Botanicals | Scorable Total | Scorable Coverage |",
            "|--------|-------|---------|-----------|---------|------------|------------|----------------|-------------------|",
        ])

        for domain_name in self.thresholds.keys():
            if domain_name not in domain_totals:
                continue

            totals = domain_totals[domain_name]
            if totals["total"] == 0:
                continue

            # Calculate scorable coverage
            scorable_total = totals["scorable_total"]
            if scorable_total == 0:
                scorable_coverage_str = "100.0% (N/A)"  # Vacuously covered
            else:
                scorable_coverage = (totals["matched"] / scorable_total) * 100 if scorable_total > 0 else 100.0
                scorable_coverage_str = f"{scorable_coverage:.1f}%"

            lines.append(
                f"| {domain_name} | {totals['total']} | {totals['matched']} | "
                f"{totals['unmatched']} | {totals['skipped']} | "
                f"{totals['recognized_non_scorable']} | "
                f"{totals['recognized_botanical_unscored']} | "
                f"{scorable_total} | {scorable_coverage_str} |"
            )

        # Add explanation with split categories
        lines.extend([
            "",
            "**Non-Scorable Categories (excluded from scorable_total):**",
            "- *Excipients*: carriers, oils, food powders - never therapeutically scored",
            "- *Botanicals*: recognized herbs - bonus-only with standardization evidence",
            "",
            "**Botanical Policy:** Botanical ingredients are recognized for transparency and potential "
            "bonus credit when standardized (marker %, mg, branded extract), but they do not contribute "
            "to the core quality score. This prevents gate failures for botanical-heavy products while "
            "still tracking recognition progress.",
            "",
            "**Bonus Guardrails:**",
            "- Bonus points capped per product to prevent greens blends inflating scores",
            "- Bonus only applied when standardization evidence exists (marker %, mg of marker, branded extract)",
            "- Simple name matches (e.g., 'Ginger Root 1000mg') remain recognized but receive no bonus",
        ])

        return lines

    def _build_json_report(self, result: BatchCoverageResult) -> Dict:
        """Build JSON report structure."""
        return {
            "schema_version": "4.0.0",
            "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "summary": {
                "total_products": result.total_products,
                "products_can_score": result.products_can_score,
                "products_blocked": result.products_blocked,
                "average_coverage_percent": round(result.average_coverage, 2),
                "total_correctness_issues": result.total_correctness_issues,
                "total_blocking_issues": result.total_blocking_issues,
                "total_warnings": result.total_warnings
            },
            "thresholds": self.thresholds,
            "domain_coverage": {
                domain: round(cov, 2)
                for domain, cov in result.domain_coverage_summary.items()
            },
            "issues_by_type": result.issues_by_type,
            "blocked_products": result.blocked_product_ids,
            "products": [
                {
                    "product_id": pr.product_id,
                    "can_score": pr.can_score,
                    "overall_coverage": round(pr.overall_coverage, 2),
                    "blocking_issues": pr.blocking_issues,
                    "warnings": pr.warnings,
                    "domain_coverage": {
                        d: round(dr.coverage_percent, 2)
                        for d, dr in pr.domain_results.items()
                        if dr.total > 0
                    },
                    "correctness_issues": [
                        {
                            "type": ci.issue_type,
                            "severity": ci.severity,
                            "description": ci.description,
                            "details": ci.details
                        }
                        for ci in pr.correctness_issues
                    ]
                }
                for pr in result.product_results
            ]
        }

    def _build_markdown_report(self, result: BatchCoverageResult) -> str:
        """Build Markdown report."""
        lines = [
            "# Coverage Gate Report",
            "",
            f"Generated: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S')} UTC",
            "",
            "## Summary",
            "",
            f"- **Total Products:** {result.total_products}",
            f"- **Can Score:** {result.products_can_score}",
            f"- **Blocked:** {result.products_blocked}",
            f"- **Average Coverage:** {result.average_coverage:.1f}%",
            "",
            "## Domain Coverage",
            "",
            "**Legend:**",
            "- BLOCK domains: Low coverage prevents scoring (quality gates)",
            "- WARN domains: Low coverage logged but scoring proceeds (bonus-only)",
            "- **Scorable Coverage**: % of items that SHOULD be scored that were matched",
            "- **Recognition Coverage**: % of items we can identify (includes non-scorable carriers/oils)",
            "",
            "| Domain | Scorable Cov | Threshold | Type | Status |",
            "|--------|--------------|-----------|------|--------|",
        ]

        for domain, threshold_config in self.thresholds.items():
            coverage = result.domain_coverage_summary.get(domain, 100.0)
            threshold = threshold_config["threshold"]
            severity = threshold_config["severity"]
            passes = coverage >= threshold

            # Clear, non-confusing status text
            if passes:
                status = "PASS"
            elif severity == "WARN":
                # Non-blocking failure - use clearer language than "FAIL (warn only)"
                status = "Below threshold (non-blocking)"
            else:
                # Blocking failure
                status = "BLOCKED"

            # Show type as descriptive rather than just severity code
            type_desc = "bonus-only" if severity == "WARN" else "required"

            lines.append(
                f"| {domain} | {coverage:.1f}% | {threshold}% | {type_desc} | {status} |"
            )

        # Add per-domain count breakdown if we have product results
        lines.extend(self._build_domain_breakdown_section(result))

        lines.extend([
            "",
            "## Correctness Issues",
            "",
        ])

        if result.issues_by_type:
            lines.append("| Issue Type | Count |")
            lines.append("|------------|-------|")
            for issue_type, count in result.issues_by_type.items():
                lines.append(f"| {issue_type} | {count} |")
        else:
            lines.append("*No correctness issues detected.*")

        lines.extend([
            "",
            "## Blocked Products",
            "",
        ])

        if result.blocked_product_ids:
            # Explicit "scoring skipped" message per dev feedback
            lines.append(
                f"**Scoring intentionally skipped for {result.products_blocked} products** "
                f"because coverage gate failed. These products need ingredient database "
                f"expansion before they can be scored."
            )
            lines.append("")
            lines.append("Blocked product IDs:")
            for pid in result.blocked_product_ids[:20]:  # Limit to 20
                lines.append(f"- {pid}")
            if len(result.blocked_product_ids) > 20:
                lines.append(f"- ... and {len(result.blocked_product_ids) - 20} more")
        else:
            lines.append("*No products blocked. All products eligible for scoring.*")

        # Detail section for first 10 products with issues
        products_with_issues = [
            pr for pr in result.product_results
            if pr.blocking_issues or pr.warnings
        ][:10]

        if products_with_issues:
            lines.extend([
                "",
                "## Sample Issues (First 10 Products)",
                "",
            ])

            for pr in products_with_issues:
                lines.append(f"### Product: {pr.product_id}")
                lines.append("")

                if pr.blocking_issues:
                    lines.append("**Blocking Issues:**")
                    for issue in pr.blocking_issues:
                        lines.append(f"- {issue}")

                if pr.warnings:
                    lines.append("**Warnings:**")
                    for warn in pr.warnings:
                        lines.append(f"- {warn}")

                lines.append("")

        return "\n".join(lines)


def check_enriched_batch(
    enriched_products: List[Dict],
    output_dir: Optional[Path] = None,
    block_on_failure: bool = True,
    strict_mode: bool = False
) -> Tuple[bool, BatchCoverageResult]:
    """
    Convenience function to check a batch and optionally generate reports.

    Args:
        enriched_products: List of enriched product dicts
        output_dir: Optional output directory for reports
        block_on_failure: If True, returns False when products are blocked
        strict_mode: If True, enforce strict thresholds regardless of batch size

    Returns:
        Tuple of (can_proceed, BatchCoverageResult)
    """
    gate = CoverageGate(strict_mode=strict_mode)
    result = gate.check_batch(enriched_products)

    if output_dir:
        gate.generate_report(result, output_dir)

    can_proceed = (result.products_blocked == 0) if block_on_failure else True

    return can_proceed, result


if __name__ == "__main__":
    import sys

    # Example usage
    if len(sys.argv) < 2:
        print("Usage: python coverage_gate.py <enriched_json_dir> [output_dir]")
        sys.exit(1)

    input_dir = Path(sys.argv[1])
    output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else input_dir / "reports"

    # Load enriched products. A single corrupt file must not kill the gate —
    # match the min_success_rate pattern used by clean_dsld_data.py. Default
    # threshold: the load success rate must be >= MIN_LOAD_SUCCESS_RATE of the
    # discovered files. Individual failures are logged and surfaced but do
    # not hard-exit unless the fraction exceeds the threshold.
    MIN_LOAD_SUCCESS_RATE = 0.95

    discovered_files = list(input_dir.glob("*.json"))
    products = []
    skipped_files = []
    for json_file in discovered_files:
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
                if isinstance(data, list):
                    products.extend(data)
                else:
                    products.append(data)
        except Exception as e:
            logger.error(f"Failed to load {json_file}: {e}")
            skipped_files.append(str(json_file))

    total_files = len(discovered_files)
    if skipped_files:
        load_success_rate = (
            (total_files - len(skipped_files)) / total_files if total_files else 0.0
        )
        print(
            f"WARNING: {len(skipped_files)}/{total_files} file(s) failed to load: "
            f"{skipped_files[:5]}{'...' if len(skipped_files) > 5 else ''}",
            file=sys.stderr,
        )
        if load_success_rate < MIN_LOAD_SUCCESS_RATE:
            print(
                f"ERROR: load success rate {load_success_rate:.1%} below "
                f"threshold {MIN_LOAD_SUCCESS_RATE:.0%} — aborting.",
                file=sys.stderr,
            )
            sys.exit(1)
        print(
            f"Proceeding with {len(products)} valid product(s); "
            f"load success rate {load_success_rate:.1%} ≥ {MIN_LOAD_SUCCESS_RATE:.0%}",
            file=sys.stderr,
        )

    if not products:
        print(f"No products found in {input_dir}")
        sys.exit(1)

    print(f"Checking {len(products)} products...")

    can_proceed, result = check_enriched_batch(products, output_dir)

    print(f"\nResults:")
    print(f"  Can score: {result.products_can_score}/{result.total_products}")
    print(f"  Blocked: {result.products_blocked}")
    print(f"  Average coverage: {result.average_coverage:.1f}%")

    if result.issues_by_type:
        print(f"  Issues by type: {result.issues_by_type}")

    sys.exit(0 if can_proceed else 1)
