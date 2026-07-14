"""
Regression Snapshot Generator

Generates reproducible regression snapshots from pipeline runs.
Used to detect drift between commits.

Outputs:
- coverage_summary.json - Domain coverage percentages
- unmatched_top50.json - Top 50 unmatched keys per domain
- score_distribution.json - Score histogram buckets
- contradictions_top20.json - Top claim↔allergen contradictions

Usage:
    python regression_snapshot.py --input enriched_dir --output snapshots/
    python regression_snapshot.py --compare snapshots/v1/ snapshots/v2/
"""

import json
import os
import argparse
import hashlib
from datetime import datetime, timezone
from typing import Dict, List, Tuple, Optional
from collections import Counter, defaultdict
from pathlib import Path


class RegressionSnapshotGenerator:
    """Generates regression snapshots from pipeline outputs."""

    SCHEMA_VERSION = "1.0.0"

    # Score histogram buckets
    SCORE_BUCKETS = [
        (0, 20, "F"),
        (20, 40, "D"),
        (40, 60, "C"),
        (60, 80, "B"),
        (80, 100, "A"),
    ]

    # ==========================================================================
    # DEFAULT ALERT THRESHOLDS
    # ==========================================================================
    # These thresholds control when alerts are triggered during snapshot comparison.
    # Can be overridden via:
    # 1. Constructor parameter (per-run override)
    # 2. JSON config file (--thresholds-config CLI option)
    #
    # As database expansion occurs, these may need tuning to avoid false alerts.
    # ==========================================================================
    DEFAULT_ALERT_THRESHOLDS = {
        # Coverage drift threshold (percentage points)
        "coverage_drift_percent": 5.0,
        # Mean score change threshold (points)
        "mean_score_drift_points": 5.0,
        # Grade histogram shift threshold (number of products)
        "grade_shift_count": 10,
        # Contradiction increase threshold (count)
        "contradiction_increase_count": 5,
        # Per-product changes cannot be hidden by offsetting aggregate shifts.
        "per_product_score_drift_points": 0.01,
    }

    def __init__(self, alert_thresholds: Optional[Dict] = None):
        self.products = []
        self.alert_thresholds = {
            **self.DEFAULT_ALERT_THRESHOLDS,
            **(alert_thresholds or {})
        }

    @classmethod
    def load_thresholds_from_config(cls, config_path: str) -> Dict:
        """Load alert thresholds from JSON config file."""
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                return config.get("alert_thresholds", {})
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Warning: Could not load thresholds config from {config_path}: {e}")
            return {}

    def load_products(self, input_dir: str) -> int:
        """Load products from enriched or scored directory."""
        self.products = []
        input_path = Path(input_dir)

        if not input_path.is_dir():
            raise FileNotFoundError(f"Snapshot input directory does not exist: {input_path}")

        json_files = sorted(
            path for path in input_path.glob("*.json")
            if path.is_file() and not path.name.startswith(".")
        )
        if not json_files:
            raise FileNotFoundError(f"Snapshot input contains no JSON files: {input_path}")
        for json_file in json_files:
            try:
                with open(json_file, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self.products.extend(data)
                    elif isinstance(data, dict):
                        self.products.append(data)
            except (json.JSONDecodeError, IOError) as e:
                raise ValueError(f"Could not load snapshot input {json_file}: {e}") from e

        ids = [self._product_id(product) for product in self.products]
        if any(product_id == "unknown" for product_id in ids):
            raise ValueError("Snapshot input contains a product without id/dsld_id")
        duplicates = sorted(product_id for product_id, count in Counter(ids).items() if count > 1)
        if duplicates:
            raise ValueError(f"Snapshot input contains duplicate product IDs: {duplicates[:10]}")

        return len(self.products)

    @staticmethod
    def _product_id(product: Dict) -> str:
        return str(product.get("dsld_id") or product.get("id") or "unknown")

    @staticmethod
    def _product_score(product: Dict) -> Optional[float]:
        for field in ("quality_score_v4_100", "score_100_equivalent", "score_display_100_equivalent"):
            value = product.get(field)
            if value is not None:
                try:
                    return float(value)
                except (TypeError, ValueError):
                    return None
        return None

    def generate_product_baseline(self) -> Dict:
        """Capture the minimum auditable contract for every product."""
        products: Dict[str, Dict] = {}
        for product in self.products:
            product_id = self._product_id(product)
            ledger_domains = (product.get("match_ledger") or {}).get("domains") or {}
            unmatched_counts = {
                name: int(data.get("unmatched", 0) or 0)
                for name, data in sorted(ledger_domains.items())
                if isinstance(data, dict)
            }
            iqd = product.get("ingredient_quality_data") or {}
            canonical_ids = sorted({
                str(row.get("canonical_id"))
                for row in (iqd.get("ingredients_scorable") or iqd.get("ingredients") or [])
                if isinstance(row, dict) and row.get("canonical_id")
            })
            compliance = product.get("compliance_data") or {}
            allergen_rows = compliance.get("allergens_detected") or []
            if not allergen_rows:
                contaminant = product.get("contaminant_data") or {}
                allergen_payload = contaminant.get("allergens") or {}
                allergen_rows = (
                    allergen_payload.get("allergens") or []
                    if isinstance(allergen_payload, dict)
                    else []
                )
            allergen_findings = sorted({
                str(
                    row.get("allergen_type")
                    or row.get("allergen")
                    or row.get("name")
                    or row.get("type")
                )
                for row in allergen_rows
                if isinstance(row, dict) and (
                    row.get("allergen_type")
                    or row.get("allergen")
                    or row.get("name")
                    or row.get("type")
                )
            })
            products[product_id] = {
                "score": self._product_score(product),
                "quality_score_status": product.get("quality_score_status"),
                "verdict": product.get("verdict")
                or product.get("safety_verdict")
                or (product.get("scoring_metadata") or {}).get("safety_verdict"),
                "safety_flags": sorted(
                    json.dumps(flag, sort_keys=True) if isinstance(flag, dict) else str(flag)
                    for flag in (product.get("flags") or [])
                ),
                "allergen_findings": allergen_findings,
                "canonical_ids": canonical_ids,
                "unmatched_counts": unmatched_counts,
            }
        return {
            "schema_version": self.SCHEMA_VERSION,
            "generated_at": datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            "total_products": len(products),
            "products": products,
        }

    def generate_coverage_summary(self) -> Dict:
        """Generate domain coverage summary with dual metrics."""
        domain_totals = defaultdict(lambda: {
            "total": 0,
            "matched": 0,
            "skipped": 0,
            "unmatched": 0,
            "recognized_non_scorable": 0,
            "recognized_botanical_unscored": 0,
        })

        for product in self.products:
            ledger = product.get("match_ledger", {})
            domains = ledger.get("domains", {})

            for domain_name, domain_data in domains.items():
                domain_totals[domain_name]["total"] += domain_data.get("total_raw", 0)
                domain_totals[domain_name]["matched"] += domain_data.get("matched", 0)
                domain_totals[domain_name]["skipped"] += domain_data.get("skipped", 0)
                domain_totals[domain_name]["unmatched"] += domain_data.get("unmatched", 0)
                domain_totals[domain_name]["recognized_non_scorable"] += domain_data.get(
                    "recognized_non_scorable", 0
                )
                domain_totals[domain_name]["recognized_botanical_unscored"] += domain_data.get(
                    "recognized_botanical_unscored", 0
                )

        # Calculate both coverage metrics per domain
        coverage_scorable = {}
        coverage_recognition = {}
        for domain, data in domain_totals.items():
            # Scorable coverage (gate metric)
            # Botanicals EXCLUDED from scorable_total per policy:
            # - Botanicals do not contribute to core quality score
            # - They are bonus-only (standardization evidence awards capped bonus)
            scorable_total = (
                data["total"] -
                data["skipped"] -
                data["recognized_non_scorable"] -
                data["recognized_botanical_unscored"]  # Botanicals excluded
            )
            if scorable_total > 0:
                coverage_scorable[domain] = round(data["matched"] / scorable_total * 100, 2)
            else:
                coverage_scorable[domain] = 100.0

            # Recognition coverage
            if data["total"] > 0:
                recognized = (
                    data["matched"] +
                    data["skipped"] +
                    data["recognized_non_scorable"] +
                    data["recognized_botanical_unscored"]
                )
                coverage_recognition[domain] = round(recognized / data["total"] * 100, 2)
            else:
                coverage_recognition[domain] = 100.0

        return {
            "schema_version": self.SCHEMA_VERSION,
            "generated_at": datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            "total_products": len(self.products),
            # Dual coverage metrics
            "domain_scorable_coverage": coverage_scorable,
            "domain_recognition_coverage": coverage_recognition,
            # Legacy (for backward compat) - maps to scorable
            "domain_coverage": coverage_scorable,
            "domain_totals": dict(domain_totals),
        }

    def generate_unmatched_top50(self) -> Dict:
        """Generate top 50 unmatched keys per domain."""
        unmatched_by_domain = defaultdict(Counter)

        for product in self.products:
            # Check match_ledger for unmatched entries
            ledger = product.get("match_ledger", {})
            for domain_name, domain_data in ledger.get("domains", {}).items():
                for entry in domain_data.get("entries", []):
                    if entry.get("decision") == "unmatched":
                        key = entry.get("normalized_key") or entry.get("raw_source_text", "unknown")
                        unmatched_by_domain[domain_name][key] += 1

            # Also check unmatched_* lists
            for list_name in ["unmatched_ingredients", "unmatched_additives", "unmatched_allergens"]:
                domain = list_name.replace("unmatched_", "")
                for item in product.get(list_name, []):
                    key = item.get("normalized_key") or item.get("raw_source_text", "unknown")
                    unmatched_by_domain[domain][key] += 1

        # Get top 50 per domain
        top50 = {}
        for domain, counter in unmatched_by_domain.items():
            top50[domain] = counter.most_common(50)

        return {
            "schema_version": self.SCHEMA_VERSION,
            "generated_at": datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            "total_products": len(self.products),
            "top_50_by_domain": top50,
        }

    def generate_score_distribution(self) -> Dict:
        """Generate score distribution histogram."""
        histogram = {bucket[2]: 0 for bucket in self.SCORE_BUCKETS}
        scores = []
        verdicts = Counter()

        for product in self.products:
            # Production v4 score first; compatibility fields are fallback only.
            score = self._product_score(product)
            if score is not None:
                scores.append(score)

                # Categorize into bucket
                for low, high, grade in self.SCORE_BUCKETS:
                    if low <= score < high:
                        histogram[grade] += 1
                        break
                else:
                    histogram["A"] += 1  # 100 goes to A

            # Count verdicts
            verdict = product.get("safety_verdict") or product.get("scoring_metadata", {}).get("safety_verdict")
            if verdict:
                verdicts[verdict] += 1

        return {
            "schema_version": self.SCHEMA_VERSION,
            "generated_at": datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            "total_products": len(self.products),
            "total_scored": len(scores),
            "histogram": histogram,
            "verdicts": dict(verdicts),
            "stats": {
                "mean": round(sum(scores) / len(scores), 2) if scores else 0,
                "min": round(min(scores), 2) if scores else 0,
                "max": round(max(scores), 2) if scores else 0,
            },
        }

    def generate_contradictions_top20(self) -> Dict:
        """Generate top claim↔allergen contradictions."""
        contradictions = Counter()

        for product in self.products:
            product_id = product.get("dsld_id") or product.get("id", "unknown")

            # Get claims
            claims = product.get("claims_data", {}).get("claims", [])
            allergen_free_claims = []
            for claim in claims:
                claim_type = claim.get("claim_type", "")
                if "free" in claim_type.lower():
                    allergen_free_claims.append(claim_type)

            # Get detected allergens
            allergens = product.get("dietary_sensitivity_data", {}).get("allergens", {})
            detected_allergens = []
            for allergen_name, allergen_data in allergens.items():
                if allergen_data.get("presence_type") == "contains":
                    detected_allergens.append(allergen_name)

            # Check for contradictions
            for claim in allergen_free_claims:
                claim_lower = claim.lower()
                for allergen in detected_allergens:
                    allergen_lower = allergen.lower()
                    # Check if claim and allergen contradict
                    if allergen_lower in claim_lower or any(
                        x in claim_lower for x in [allergen_lower.split("_")[0]]
                    ):
                        key = f"{claim} vs {allergen}"
                        contradictions[key] += 1

        return {
            "schema_version": self.SCHEMA_VERSION,
            "generated_at": datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            "total_products": len(self.products),
            "total_contradictions": sum(contradictions.values()),
            "top_20": contradictions.most_common(20),
        }

    def generate_all_snapshots(self, output_dir: str) -> Dict:
        """Generate all snapshot files."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        snapshots = {}

        # Coverage summary
        coverage = self.generate_coverage_summary()
        with open(output_path / "coverage_summary.json", "w") as f:
            json.dump(coverage, f, indent=2)
        snapshots["coverage_summary"] = coverage

        # Unmatched top 50
        unmatched = self.generate_unmatched_top50()
        with open(output_path / "unmatched_top50.json", "w") as f:
            json.dump(unmatched, f, indent=2)
        snapshots["unmatched_top50"] = unmatched

        # Score distribution
        scores = self.generate_score_distribution()
        with open(output_path / "score_distribution.json", "w") as f:
            json.dump(scores, f, indent=2)
        snapshots["score_distribution"] = scores

        # Contradictions
        contradictions = self.generate_contradictions_top20()
        with open(output_path / "contradictions_top20.json", "w") as f:
            json.dump(contradictions, f, indent=2)
        snapshots["contradictions_top20"] = contradictions

        product_baseline = self.generate_product_baseline()
        with open(output_path / "product_baseline.json", "w") as f:
            json.dump(product_baseline, f, indent=2)
        snapshots["product_baseline"] = product_baseline

        # Generate manifest with hashes
        manifest = self._generate_manifest(snapshots)
        with open(output_path / "manifest.json", "w") as f:
            json.dump(manifest, f, indent=2)

        return manifest

    def _generate_manifest(self, snapshots: Dict) -> Dict:
        """Generate manifest with content hashes for comparison."""
        def stable_content(value):
            if isinstance(value, dict):
                return {
                    key: stable_content(item)
                    for key, item in value.items()
                    if key not in {"generated_at", "compared_at", "timestamp"}
                }
            if isinstance(value, list):
                return [stable_content(item) for item in value]
            return value

        hashes = {}
        for name, data in snapshots.items():
            content = json.dumps(stable_content(data), sort_keys=True)
            hashes[name] = hashlib.sha256(content.encode()).hexdigest()[:16]

        return {
            "schema_version": self.SCHEMA_VERSION,
            "generated_at": datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            "total_products": len(self.products),
            "file_hashes": hashes,
        }

    @classmethod
    def compare_snapshots(cls, dir1: str, dir2: str, thresholds: Optional[Dict] = None) -> Dict:
        """
        Compare two snapshot directories and return deltas.

        Args:
            dir1: Baseline snapshot directory
            dir2: Current snapshot directory
            thresholds: Optional alert thresholds override. If not provided,
                        uses DEFAULT_ALERT_THRESHOLDS.

        Returns:
            Dict with comparison results, deltas, and alerts
        """
        path1, path2 = Path(dir1), Path(dir2)

        # Use provided thresholds or defaults
        alert_config = {**cls.DEFAULT_ALERT_THRESHOLDS, **(thresholds or {})}
        coverage_threshold = alert_config["coverage_drift_percent"]
        mean_threshold = alert_config["mean_score_drift_points"]
        grade_threshold = alert_config["grade_shift_count"]
        contradiction_threshold = alert_config["contradiction_increase_count"]
        product_score_threshold = alert_config["per_product_score_drift_points"]

        comparison = {
            "schema_version": "4.0.0",
            "compared_at": datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            "baseline": str(path1),
            "current": str(path2),
            "deltas": {},
            "alerts": [],
            "thresholds_used": alert_config,
        }

        # Compare coverage
        try:
            with open(path1 / "coverage_summary.json") as f:
                cov1 = json.load(f)
            with open(path2 / "coverage_summary.json") as f:
                cov2 = json.load(f)

            cov_deltas = {}
            for domain in set(cov1.get("domain_coverage", {}).keys()) | set(cov2.get("domain_coverage", {}).keys()):
                v1 = cov1.get("domain_coverage", {}).get(domain, 0)
                v2 = cov2.get("domain_coverage", {}).get(domain, 0)
                delta = v2 - v1
                cov_deltas[domain] = {"baseline": v1, "current": v2, "delta": round(delta, 2)}
                if abs(delta) > coverage_threshold:
                    comparison["alerts"].append(f"Coverage delta for {domain}: {delta:+.1f}%")

            comparison["deltas"]["coverage"] = cov_deltas
        except (FileNotFoundError, json.JSONDecodeError) as e:
            comparison["deltas"]["coverage"] = {"error": str(e)}
            comparison["alerts"].append(f"Snapshot read error (coverage): {e}")

        # Compare score distribution
        try:
            with open(path1 / "score_distribution.json") as f:
                scores1 = json.load(f)
            with open(path2 / "score_distribution.json") as f:
                scores2 = json.load(f)

            hist1 = scores1.get("histogram", {})
            hist2 = scores2.get("histogram", {})

            hist_deltas = {}
            for grade in ["A", "B", "C", "D", "F"]:
                v1 = hist1.get(grade, 0)
                v2 = hist2.get(grade, 0)
                delta = v2 - v1
                hist_deltas[grade] = {"baseline": v1, "current": v2, "delta": delta}
                if abs(delta) > grade_threshold:
                    comparison["alerts"].append(f"Score distribution delta for grade {grade}: {delta:+d}")

            comparison["deltas"]["score_histogram"] = hist_deltas

            # Compare mean scores
            mean1 = scores1.get("stats", {}).get("mean", 0)
            mean2 = scores2.get("stats", {}).get("mean", 0)
            mean_delta = mean2 - mean1
            comparison["deltas"]["score_mean"] = {
                "baseline": mean1,
                "current": mean2,
                "delta": round(mean_delta, 2),
            }
            if abs(mean_delta) > mean_threshold:
                comparison["alerts"].append(f"Mean score delta: {mean_delta:+.1f}")

        except (FileNotFoundError, json.JSONDecodeError) as e:
            comparison["deltas"]["score_distribution"] = {"error": str(e)}
            comparison["alerts"].append(f"Snapshot read error (score distribution): {e}")

        # Compare contradiction counts
        try:
            with open(path1 / "contradictions_top20.json") as f:
                cont1 = json.load(f)
            with open(path2 / "contradictions_top20.json") as f:
                cont2 = json.load(f)

            c1 = cont1.get("total_contradictions", 0)
            c2 = cont2.get("total_contradictions", 0)
            delta = c2 - c1

            comparison["deltas"]["contradictions"] = {
                "baseline": c1,
                "current": c2,
                "delta": delta,
            }
            if delta > contradiction_threshold:
                comparison["alerts"].append(f"Contradiction count increased by {delta}")

        except (FileNotFoundError, json.JSONDecodeError) as e:
            comparison["deltas"]["contradictions"] = {"error": str(e)}
            comparison["alerts"].append(f"Snapshot read error (contradictions): {e}")

        # Per-product comparison is required: aggregate means can hide equal
        # and opposite score changes or a product silently disappearing.
        try:
            with open(path1 / "product_baseline.json") as f:
                products1 = (json.load(f).get("products") or {})
            with open(path2 / "product_baseline.json") as f:
                products2 = (json.load(f).get("products") or {})
            missing = sorted(set(products1) - set(products2))
            added = sorted(set(products2) - set(products1))
            changed = {}
            for product_id in sorted(set(products1) & set(products2)):
                before = products1[product_id]
                after = products2[product_id]
                fields = {}
                score1, score2 = before.get("score"), after.get("score")
                if score1 is None or score2 is None:
                    if score1 != score2:
                        fields["score"] = {"baseline": score1, "current": score2}
                elif abs(float(score2) - float(score1)) > product_score_threshold:
                    fields["score"] = {
                        "baseline": score1,
                        "current": score2,
                        "delta": round(float(score2) - float(score1), 4),
                    }
                for field in (
                    "quality_score_status", "verdict", "safety_flags",
                    "allergen_findings", "canonical_ids", "unmatched_counts",
                ):
                    if before.get(field) != after.get(field):
                        fields[field] = {
                            "baseline": before.get(field),
                            "current": after.get(field),
                        }
                if fields:
                    changed[product_id] = fields
            comparison["deltas"]["products"] = {
                "missing": missing,
                "added": added,
                "changed": changed,
            }
            if missing:
                comparison["alerts"].append(f"Missing products: {missing[:10]}")
            if added:
                comparison["alerts"].append(f"Unexpected added products: {added[:10]}")
            if changed:
                comparison["alerts"].append(
                    f"Per-product contract changed for {len(changed)} product(s)"
                )
        except (FileNotFoundError, json.JSONDecodeError, AttributeError) as e:
            comparison["deltas"]["products"] = {"error": str(e)}
            comparison["alerts"].append(f"Snapshot read error (products): {e}")

        comparison["passed"] = len(comparison["alerts"]) == 0
        return comparison


def main():
    parser = argparse.ArgumentParser(description="Generate or compare regression snapshots")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Generate command
    gen_parser = subparsers.add_parser("generate", help="Generate snapshot from pipeline output")
    gen_parser.add_argument("--input", required=True, help="Input directory (enriched or scored)")
    gen_parser.add_argument("--output", required=True, help="Output directory for snapshots")

    # Compare command
    cmp_parser = subparsers.add_parser("compare", help="Compare two snapshots")
    cmp_parser.add_argument("--baseline", required=True, help="Baseline snapshot directory")
    cmp_parser.add_argument("--current", required=True, help="Current snapshot directory")
    cmp_parser.add_argument("--output", help="Output file for comparison results")
    cmp_parser.add_argument("--fail-on-alerts", action="store_true", help="Exit with code 1 if alerts found")
    cmp_parser.add_argument("--thresholds-config", help="JSON config file with custom alert thresholds")

    args = parser.parse_args()

    if args.command == "generate":
        generator = RegressionSnapshotGenerator()
        count = generator.load_products(args.input)
        print(f"Loaded {count} products")

        manifest = generator.generate_all_snapshots(args.output)
        print(f"Generated snapshots in {args.output}")
        print(f"Files: {list(manifest['file_hashes'].keys())}")

    elif args.command == "compare":
        # Load custom thresholds if provided
        thresholds = None
        if hasattr(args, 'thresholds_config') and args.thresholds_config:
            thresholds = RegressionSnapshotGenerator.load_thresholds_from_config(args.thresholds_config)
            print(f"Using custom thresholds from {args.thresholds_config}")

        comparison = RegressionSnapshotGenerator.compare_snapshots(args.baseline, args.current, thresholds)

        if args.output:
            with open(args.output, "w") as f:
                json.dump(comparison, f, indent=2)
            print(f"Comparison saved to {args.output}")
        else:
            print(json.dumps(comparison, indent=2))

        if comparison["alerts"]:
            print("\nALERTS:")
            for alert in comparison["alerts"]:
                print(f"  ⚠️  {alert}")

        if args.fail_on_alerts and not comparison["passed"]:
            exit(1)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
