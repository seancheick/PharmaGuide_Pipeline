#!/usr/bin/env python3
"""
Claims & Certification Audit Tool

Audits claim detection across enriched products to identify:
- False positive rates by claim type
- Evidence strength distribution
- Scope violations
- Potential false positives for manual review

Usage:
    python claims_audit.py
    python claims_audit.py --input-dir output_Gummies_enriched/enriched
    python claims_audit.py --output-report reports/claims_audit.md
    python claims_audit.py --sample-size 100

Output: Markdown report with audit findings
"""

import json
import os
import sys
import argparse
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional
from collections import defaultdict

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))

from constants import LOG_FORMAT, LOG_DATE_FORMAT

logger = logging.getLogger(__name__)


class ClaimsAuditor:
    """
    Audit tool for claims/certification detection.

    Generates evidence reports for all detected claims across a batch of products.
    """

    def __init__(self, enriched_dir: str):
        """
        Initialize auditor.

        Args:
            enriched_dir: Path to directory containing enriched JSON files
        """
        self.enriched_dir = Path(enriched_dir)
        self.results = {
            "summary": {},
            "by_claim_type": {},
            "potential_false_positives": [],
            "evidence_samples": [],
            "ineligible_breakdown": defaultdict(list),
            "scope_violations": [],
            # New diagnostic tracking
            "source_field_distribution": defaultdict(int),
            "scope_violations_by_field": defaultdict(int),
            "scope_violations_by_rule": defaultdict(int),
            "scope_violations_by_scope_rule": defaultdict(int)
        }
        self.products_audited = 0
        self.all_text_count = 0  # Track regression to all_text

    def audit_batch(self, sample_size: int = 0) -> Dict:
        """
        Audit all enriched products in directory.

        Args:
            sample_size: If > 0, only audit this many products

        Returns:
            Audit results dictionary
        """
        enriched_files = list(self.enriched_dir.glob("*.json"))

        if sample_size > 0:
            enriched_files = enriched_files[:sample_size]

        logger.info(f"Auditing {len(enriched_files)} enriched files from {self.enriched_dir}")

        for file_path in enriched_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Handle both single products and batches
                products = data if isinstance(data, list) else [data]

                for product in products:
                    self._audit_product(product)

            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to read {file_path}: {e}")
                continue

        self._compute_summary()
        return self.results

    def _audit_product(self, product: Dict) -> None:
        """Audit a single product's claims."""
        self.products_audited += 1
        product_id = product.get("dsld_id", product.get("id", "unknown"))
        product_name = product.get("product_name", "Unknown")

        # Audit certification_data.evidence_based
        cert_data = product.get("certification_data", {})
        evidence_based = cert_data.get("evidence_based", {})

        self._audit_claim_category(
            evidence_based.get("third_party_programs", []),
            "third_party_certifications",
            product_id,
            product_name
        )

        self._audit_claim_category(
            evidence_based.get("gmp_certifications", []),
            "gmp_certifications",
            product_id,
            product_name
        )

        self._audit_claim_category(
            evidence_based.get("batch_traceability", []),
            "batch_traceability",
            product_id,
            product_name
        )

        # Audit compliance_data.evidence_based
        compliance_data = product.get("compliance_data", {})
        compliance_evidence = compliance_data.get("evidence_based", {})

        self._audit_claim_category(
            compliance_evidence.get("allergen_free_claims", []),
            "allergen_free_claims",
            product_id,
            product_name
        )

        # Audit formulation_data.organic.evidence_based
        formulation_data = product.get("formulation_data", {})
        organic_data = formulation_data.get("organic", {})
        organic_evidence = organic_data.get("evidence_based", {})

        self._audit_claim_category(
            organic_evidence.get("organic_certifications", []),
            "organic_certifications",
            product_id,
            product_name
        )

    def _audit_claim_category(self, evidence_list: List[Dict], category: str,
                               product_id: str, product_name: str) -> None:
        """Audit claims in a specific category."""
        if category not in self.results["by_claim_type"]:
            self.results["by_claim_type"][category] = {
                "total_detected": 0,
                "score_eligible": 0,
                "ineligible": 0,
                "strong_evidence": 0,
                "medium_evidence": 0,
                "weak_evidence": 0,
                "negated": 0,
                "scope_violations": 0,
                "proximity_conflicts": 0,
                "by_rule_id": defaultdict(int)
            }

        stats = self.results["by_claim_type"][category]

        for evidence in evidence_list:
            stats["total_detected"] += 1
            stats["by_rule_id"][evidence.get("rule_id", "UNKNOWN")] += 1

            # Track source_field distribution
            source_field = evidence.get("source_field", "unknown")
            self.results["source_field_distribution"][source_field] += 1

            # Track all_text regression (should be near zero after fix)
            if source_field == "all_text":
                self.all_text_count += 1

            # Track evidence strength
            strength = evidence.get("evidence_strength", "unknown")
            if strength == "strong":
                stats["strong_evidence"] += 1
            elif strength == "medium":
                stats["medium_evidence"] += 1
            elif strength == "weak":
                stats["weak_evidence"] += 1

            # Track score eligibility
            if evidence.get("score_eligible", False):
                stats["score_eligible"] += 1
            else:
                stats["ineligible"] += 1

                # Track ineligibility reasons
                reason = evidence.get("ineligibility_reason", "unknown")
                self.results["ineligible_breakdown"][reason].append({
                    "product_id": product_id,
                    "category": category,
                    "rule_id": evidence.get("rule_id"),
                    "matched_text": evidence.get("matched_text")
                })

            # Track negations
            negation = evidence.get("negation", {})
            if negation.get("negated", False):
                stats["negated"] += 1

            # Track scope violations with detailed diagnostics
            if evidence.get("scope_violation", False):
                stats["scope_violations"] += 1
                rule_id = evidence.get("rule_id", "UNKNOWN")
                scope_rule = evidence.get("scope_rule", "unknown")

                # Track by source_field, rule, and scope_rule
                self.results["scope_violations_by_field"][source_field] += 1
                self.results["scope_violations_by_rule"][rule_id] += 1
                self.results["scope_violations_by_scope_rule"][scope_rule] += 1

                self.results["scope_violations"].append({
                    "product_id": product_id,
                    "product_name": product_name,
                    "category": category,
                    "rule_id": rule_id,
                    "source_field": source_field,
                    "scope_rule": scope_rule
                })

            # Track proximity conflicts
            conflicts = evidence.get("proximity_conflicts", [])
            if conflicts:
                stats["proximity_conflicts"] += 1

            # Flag potential false positives
            self._flag_potential_false_positive(evidence, category, product_id, product_name)

            # Sample evidence for manual review
            if stats["total_detected"] <= 20:  # First 20 per category
                self.results["evidence_samples"].append({
                    "category": category,
                    "product_id": product_id,
                    "product_name": product_name[:50],  # Truncate
                    "rule_id": evidence.get("rule_id"),
                    "display_name": evidence.get("display_name"),
                    "matched_text": evidence.get("matched_text"),
                    "source_field": evidence.get("source_field"),
                    "evidence_strength": evidence.get("evidence_strength"),
                    "score_eligible": evidence.get("score_eligible"),
                    "ineligibility_reason": evidence.get("ineligibility_reason")
                })

    def _flag_potential_false_positive(self, evidence: Dict, category: str,
                                        product_id: str, product_name: str) -> None:
        """Flag potential false positives for manual review."""
        flags = []
        rule_id = evidence.get("rule_id", "")
        matched_text = evidence.get("matched_text", "")

        # USP: Check if "standards" without "Verified"
        if "USP" in rule_id and evidence.get("score_eligible"):
            text_lower = matched_text.lower()
            if "standard" in text_lower and "verified" not in text_lower:
                flags.append("USP pattern may be too broad")

        # GMP: Check if vague marketing
        if "GMP" in rule_id and evidence.get("score_eligible"):
            weak_patterns = ["follows", "practices", "guidelines"]
            text_lower = matched_text.lower()
            if any(p in text_lower for p in weak_patterns):
                flags.append("GMP claim may be vague marketing")

        # Batch: Check if not actionable
        if "TRACE" in rule_id and evidence.get("score_eligible"):
            actionable = ["available", "request", "qr", "download", "scan"]
            text_lower = matched_text.lower()
            if not any(a in text_lower for a in actionable):
                flags.append("Batch traceability may lack actionable evidence")

        if flags:
            self.results["potential_false_positives"].append({
                "product_id": product_id,
                "product_name": product_name[:50],
                "category": category,
                "rule_id": rule_id,
                "matched_text": matched_text,
                "flags": flags
            })

    def _compute_summary(self) -> None:
        """Compute summary statistics."""
        total_claims = sum(
            cat["total_detected"]
            for cat in self.results["by_claim_type"].values()
        )
        total_eligible = sum(
            cat["score_eligible"]
            for cat in self.results["by_claim_type"].values()
        )
        total_strong = sum(
            cat["strong_evidence"]
            for cat in self.results["by_claim_type"].values()
        )
        total_medium = sum(
            cat["medium_evidence"]
            for cat in self.results["by_claim_type"].values()
        )
        total_weak = sum(
            cat["weak_evidence"]
            for cat in self.results["by_claim_type"].values()
        )
        total_scope_violations = len(self.results["scope_violations"])

        self.results["summary"] = {
            "products_audited": self.products_audited,
            "total_claims_detected": total_claims,
            "total_score_eligible": total_eligible,
            "eligible_rate": f"{(total_eligible / total_claims * 100):.1f}%" if total_claims > 0 else "N/A",
            # Renamed: "false_positive_rate" -> "manual_review_rate"
            "manual_review_flagged": len(self.results["potential_false_positives"]),
            "manual_review_rate": f"{(len(self.results['potential_false_positives']) / total_claims * 100):.1f}%" if total_claims > 0 else "N/A",
            "evidence_strength_distribution": {
                "strong": total_strong,
                "medium": total_medium,
                "weak": total_weak,
                "strong_pct": f"{(total_strong / total_claims * 100):.1f}%" if total_claims > 0 else "N/A",
                "medium_pct": f"{(total_medium / total_claims * 100):.1f}%" if total_claims > 0 else "N/A",
                "weak_pct": f"{(total_weak / total_claims * 100):.1f}%" if total_claims > 0 else "N/A"
            },
            "scope_violation_count": total_scope_violations,
            # Rollout health metrics
            "rollout_health": {
                "scope_violation_rate": f"{(total_scope_violations / total_claims * 100):.1f}%" if total_claims > 0 else "N/A",
                "pct_source_field_all_text": f"{(self.all_text_count / total_claims * 100):.1f}%" if total_claims > 0 else "N/A",
                "all_text_count": self.all_text_count,
                "health_status": "HEALTHY" if self.all_text_count == 0 and total_scope_violations < total_claims * 0.2 else "NEEDS_REVIEW"
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    def generate_report(self) -> str:
        """Generate markdown audit report."""
        lines = []
        summary = self.results["summary"]

        lines.append(f"# Claims Audit Report - {datetime.now().strftime('%Y-%m-%d')}")
        lines.append("")
        lines.append("## Summary")
        lines.append("")
        lines.append(f"- **Products audited:** {summary.get('products_audited', 0)}")
        lines.append(f"- **Claims detected:** {summary.get('total_claims_detected', 0)}")
        lines.append(f"- **Score eligible:** {summary.get('total_score_eligible', 0)} ({summary.get('eligible_rate', 'N/A')})")
        lines.append(f"- **Flagged for manual review:** {summary.get('manual_review_flagged', 0)} ({summary.get('manual_review_rate', 'N/A')})")
        lines.append(f"- **Scope violations:** {summary.get('scope_violation_count', 0)}")
        lines.append("")

        # Rollout health metrics
        health = summary.get('rollout_health', {})
        lines.append("### Rollout Health Metrics")
        lines.append("")
        lines.append("| Metric | Value | Status |")
        lines.append("|--------|-------|--------|")

        # Parse scope violation rate safely
        scope_rate_str = health.get('scope_violation_rate', 'N/A')
        try:
            scope_rate = float(scope_rate_str.rstrip('%'))
            scope_status = '✅' if scope_rate < 20 else '⚠️'
        except (ValueError, AttributeError):
            scope_status = '❓'

        all_text_ct = health.get('all_text_count', 1)
        all_text_status = '✅' if all_text_ct == 0 else '🔴 REGRESSION'

        lines.append(f"| Scope violation rate | {scope_rate_str} | {scope_status} |")
        pct_all_text = health.get('pct_source_field_all_text', 'N/A')
        lines.append(f"| % source_field=all_text | {pct_all_text} | {all_text_status} |")
        lines.append(f"| Overall health | {health.get('health_status', 'UNKNOWN')} | |")
        lines.append("")

        # Evidence strength
        strength = summary.get('evidence_strength_distribution', {})
        lines.append("### Evidence Strength Distribution")
        lines.append("")
        lines.append(f"| Strength | Count | Percentage |")
        lines.append(f"|----------|-------|------------|")
        lines.append(f"| Strong | {strength.get('strong', 0)} | {strength.get('strong_pct', 'N/A')} |")
        lines.append(f"| Medium | {strength.get('medium', 0)} | {strength.get('medium_pct', 'N/A')} |")
        lines.append(f"| Weak | {strength.get('weak', 0)} | {strength.get('weak_pct', 'N/A')} |")
        lines.append("")

        # By claim type
        lines.append("## By Claim Type")
        lines.append("")
        lines.append("| Category | Detected | Eligible | Negated | Scope Viol. | Conflicts |")
        lines.append("|----------|----------|----------|---------|-------------|-----------|")

        for category, stats in self.results["by_claim_type"].items():
            lines.append(
                f"| {category} | {stats['total_detected']} | {stats['score_eligible']} | "
                f"{stats['negated']} | {stats['scope_violations']} | {stats['proximity_conflicts']} |"
            )
        lines.append("")

        # Ineligibility reasons
        lines.append("## Ineligibility Breakdown")
        lines.append("")
        for reason, items in self.results["ineligible_breakdown"].items():
            lines.append(f"- **{reason}:** {len(items)} claims")
        lines.append("")

        # Potential false positives (top 20)
        lines.append("## Potential False Positives (Top 20)")
        lines.append("")
        if self.results["potential_false_positives"]:
            for i, fp in enumerate(self.results["potential_false_positives"][:20], 1):
                lines.append(f"### {i}. {fp.get('product_name', 'Unknown')}")
                lines.append(f"- **Product ID:** {fp.get('product_id')}")
                lines.append(f"- **Category:** {fp.get('category')}")
                lines.append(f"- **Rule ID:** {fp.get('rule_id')}")
                lines.append(f"- **Matched:** `{fp.get('matched_text')}`")
                lines.append(f"- **Flags:** {', '.join(fp.get('flags', []))}")
                lines.append("")
        else:
            lines.append("*No potential false positives identified.*")
            lines.append("")

        # Evidence samples (grouped by category)
        lines.append("## Evidence Samples (First 20 per Category)")
        lines.append("")

        samples_by_cat = defaultdict(list)
        for sample in self.results["evidence_samples"]:
            samples_by_cat[sample["category"]].append(sample)

        for category, samples in samples_by_cat.items():
            lines.append(f"### {category}")
            lines.append("")
            for i, s in enumerate(samples[:5], 1):  # Show first 5
                eligible_str = "YES" if s.get("score_eligible") else f"NO ({s.get('ineligibility_reason', 'unknown')})"
                lines.append(f"{i}. **{s.get('display_name')}** - {s.get('product_id')}")
                lines.append(f"   - Matched: `{s.get('matched_text')}`")
                lines.append(f"   - Strength: {s.get('evidence_strength')} | Eligible: {eligible_str}")
            lines.append("")

        # Scope violations
        if self.results["scope_violations"]:
            lines.append("## Scope Violations")
            lines.append("")
            for sv in self.results["scope_violations"][:10]:
                lines.append(f"- **{sv.get('product_id')}** - {sv.get('rule_id')}")
                lines.append(f"  - Source: {sv.get('source_field')}")
                lines.append(f"  - Rule: {sv.get('scope_rule')}")
            lines.append("")

        # Source field distribution
        if self.results["source_field_distribution"]:
            lines.append("## Source Field Distribution")
            lines.append("")
            lines.append("| Source Field | Count |")
            lines.append("|--------------|-------|")
            sorted_fields = sorted(
                self.results["source_field_distribution"].items(),
                key=lambda x: x[1],
                reverse=True
            )
            for field, count in sorted_fields[:15]:
                lines.append(f"| {field[:50]} | {count} |")
            lines.append("")

        # Scope violations by field
        if self.results["scope_violations_by_field"]:
            lines.append("## Scope Violations by Source Field")
            lines.append("")
            lines.append("| Source Field | Violations |")
            lines.append("|--------------|------------|")
            sorted_by_field = sorted(
                self.results["scope_violations_by_field"].items(),
                key=lambda x: x[1],
                reverse=True
            )
            for field, count in sorted_by_field:
                lines.append(f"| {field[:50]} | {count} |")
            lines.append("")

        # Scope violations by rule
        if self.results["scope_violations_by_rule"]:
            lines.append("## Scope Violations by Rule ID")
            lines.append("")
            lines.append("| Rule ID | Violations |")
            lines.append("|---------|------------|")
            sorted_by_rule = sorted(
                self.results["scope_violations_by_rule"].items(),
                key=lambda x: x[1],
                reverse=True
            )
            for rule, count in sorted_by_rule:
                lines.append(f"| {rule} | {count} |")
            lines.append("")

        return "\n".join(lines)


def main():
    """Main entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
        datefmt=LOG_DATE_FORMAT
    )

    parser = argparse.ArgumentParser(description="Claims & Certification Audit Tool")
    parser.add_argument(
        "--input-dir",
        default="output_Gummies_enriched/enriched",
        help="Directory containing enriched JSON files"
    )
    parser.add_argument(
        "--output-report",
        default="reports/claims_audit.md",
        help="Path for output markdown report"
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=0,
        help="Limit audit to this many files (0 = all)"
    )
    parser.add_argument(
        "--json-output",
        help="Also output raw results as JSON"
    )

    args = parser.parse_args()

    # Run audit
    auditor = ClaimsAuditor(args.input_dir)
    results = auditor.audit_batch(sample_size=args.sample_size)

    # Generate report
    report = auditor.generate_report()

    # Write report
    report_path = Path(args.output_report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)

    logger.info("Audit report written to %s", report_path)

    # Optionally write JSON
    if args.json_output:
        with open(args.json_output, 'w', encoding='utf-8') as f:
            # Convert defaultdicts to regular dicts for JSON serialization
            json_results = {
                "summary": results["summary"],
                "by_claim_type": {
                    k: {k2: (dict(v2) if isinstance(v2, defaultdict) else v2)
                        for k2, v2 in v.items()}
                    for k, v in results["by_claim_type"].items()
                },
                "potential_false_positives": results["potential_false_positives"],
                "scope_violations": results["scope_violations"],
                "ineligible_breakdown": dict(results["ineligible_breakdown"]),
                "source_field_distribution": dict(
                    results.get("source_field_distribution", {})
                ),
                "scope_violations_by_field": dict(
                    results.get("scope_violations_by_field", {})
                ),
                "scope_violations_by_rule": dict(
                    results.get("scope_violations_by_rule", {})
                ),
                "scope_violations_by_scope_rule": dict(
                    results.get("scope_violations_by_scope_rule", {})
                )
            }
            json.dump(json_results, f, indent=2)
        logger.info("JSON results written to %s", args.json_output)

    # Print summary
    print("\n" + "=" * 60)
    print("CLAIMS AUDIT SUMMARY")
    print("=" * 60)
    summary = results['summary']
    health = summary.get('rollout_health', {})
    print(f"Products audited: {summary.get('products_audited', 0)}")
    print(f"Claims detected: {summary.get('total_claims_detected', 0)}")
    print(f"Score eligible: {summary.get('total_score_eligible', 0)}", end="")
    print(f" ({summary.get('eligible_rate', 'N/A')})")
    print(f"Manual review flagged: {summary.get('manual_review_flagged', 0)}", end="")
    print(f" ({summary.get('manual_review_rate', 'N/A')})")
    print(f"Scope violations: {summary.get('scope_violation_count', 0)}", end="")
    print(f" ({health.get('scope_violation_rate', 'N/A')})")
    print(f"all_text regression: {health.get('all_text_count', 0)}", end="")
    print(f" ({health.get('pct_source_field_all_text', 'N/A')})")
    print(f"Health status: {health.get('health_status', 'UNKNOWN')}")
    print(f"Report: {report_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
