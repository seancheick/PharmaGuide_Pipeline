"""
Regression Delta Tests

Tests for the regression snapshot generator and comparison functionality.
Used in CI to detect drift between commits.

Run with: pytest tests/test_regression_deltas.py -v
"""

import json
import os
import tempfile
import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from regression_snapshot import RegressionSnapshotGenerator


class TestSnapshotGeneration:
    """Tests for snapshot generation."""

    @pytest.fixture
    def sample_products(self):
        """Sample products with match_ledger and scores."""
        return [
            {
                "id": "10001",
                "dsld_id": "10001",
                "score_100_equivalent": 75.5,
                "safety_verdict": "SAFE",
                "match_ledger": {
                    "domains": {
                        "ingredients": {
                            "total_raw": 5,
                            "matched": 4,
                            "unmatched": 1,
                            "entries": [
                                {"decision": "unmatched", "normalized_key": "mystery_extract"}
                            ]
                        },
                        "additives": {"total_raw": 2, "matched": 2, "unmatched": 0, "entries": []},
                    }
                },
                "unmatched_ingredients": [{"normalized_key": "mystery_extract"}],
            },
            {
                "id": "10002",
                "dsld_id": "10002",
                "score_100_equivalent": 85.0,
                "safety_verdict": "SAFE",
                "match_ledger": {
                    "domains": {
                        "ingredients": {"total_raw": 3, "matched": 3, "unmatched": 0, "entries": []},
                        "additives": {"total_raw": 1, "matched": 1, "unmatched": 0, "entries": []},
                    }
                },
            },
            {
                "id": "10003",
                "dsld_id": "10003",
                "score_100_equivalent": 45.0,
                "safety_verdict": "CAUTION",
                "match_ledger": {
                    "domains": {
                        "ingredients": {"total_raw": 4, "matched": 4, "unmatched": 0, "entries": []},
                    }
                },
            },
        ]

    @pytest.fixture
    def generator(self, sample_products):
        """Generator with sample products loaded."""
        gen = RegressionSnapshotGenerator()
        gen.products = sample_products
        return gen

    def test_coverage_summary_calculation(self, generator):
        """Coverage summary should calculate domain percentages correctly."""
        summary = generator.generate_coverage_summary()

        assert summary["total_products"] == 3
        # ingredients: 5+3+4=12 total, 4+3+4=11 matched = 91.67%
        assert summary["domain_coverage"]["ingredients"] == pytest.approx(91.67, rel=0.1)
        # additives: 2+1=3 total, 2+1=3 matched = 100%
        assert summary["domain_coverage"]["additives"] == 100.0

    def test_unmatched_top50_extraction(self, generator):
        """Unmatched top 50 should extract from ledger and lists."""
        unmatched = generator.generate_unmatched_top50()

        assert unmatched["total_products"] == 3
        # mystery_extract should appear twice (once from ledger, once from list)
        ing_top = unmatched["top_50_by_domain"].get("ingredients", [])
        assert len(ing_top) > 0
        assert ing_top[0][0] == "mystery_extract"

    def test_score_distribution_histogram(self, generator):
        """Score distribution should bucket scores correctly."""
        dist = generator.generate_score_distribution()

        assert dist["total_scored"] == 3
        # 75.5 -> B, 85.0 -> A, 45.0 -> C
        assert dist["histogram"]["A"] == 1
        assert dist["histogram"]["B"] == 1
        assert dist["histogram"]["C"] == 1
        assert dist["histogram"]["D"] == 0
        assert dist["histogram"]["F"] == 0

    def test_score_distribution_stats(self, generator):
        """Score distribution stats should be calculated correctly."""
        dist = generator.generate_score_distribution()

        assert dist["stats"]["min"] == 45.0
        assert dist["stats"]["max"] == 85.0
        # mean: (75.5 + 85.0 + 45.0) / 3 = 68.5
        assert dist["stats"]["mean"] == pytest.approx(68.5, rel=0.1)

    def test_verdicts_count(self, generator):
        """Verdicts should be counted correctly."""
        dist = generator.generate_score_distribution()

        assert dist["verdicts"]["SAFE"] == 2
        assert dist["verdicts"]["CAUTION"] == 1

    def test_manifest_hashes_ignore_generation_timestamps(self, generator):
        first = generator.generate_coverage_summary()
        second = dict(first)
        second["generated_at"] = "2099-01-01T00:00:00Z"

        hash1 = generator._generate_manifest({"coverage": first})["file_hashes"]["coverage"]
        hash2 = generator._generate_manifest({"coverage": second})["file_hashes"]["coverage"]

        assert hash1 == hash2

    def test_v4_score_field_is_authoritative(self, generator):
        generator.products = [{
            "id": "v4",
            "quality_score_v4_100": 0,
            "score_100_equivalent": 88,
            "quality_score_status": "suppressed_safety",
        }]

        baseline = generator.generate_product_baseline()["products"]["v4"]

        assert baseline["score"] == 0
        assert baseline["quality_score_status"] == "suppressed_safety"

    def test_load_products_ignores_stage_manifest_dotfile(self, tmp_path):
        (tmp_path / "scored.json").write_text(
            json.dumps({"id": "visible", "quality_score_v4_100": 50}),
            encoding="utf-8",
        )
        (tmp_path / ".stage_manifest.json").write_text(
            json.dumps({"stage": "score", "processing_complete": True}),
            encoding="utf-8",
        )

        generator = RegressionSnapshotGenerator()
        assert generator.load_products(str(tmp_path)) == 1
        assert generator.products[0]["id"] == "visible"

    def test_product_baseline_reads_current_compliance_allergens(self, generator):
        generator.products = [{
            "id": "allergen",
            "quality_score_v4_100": 50,
            "compliance_data": {
                "allergens_detected": [{"allergen_type": "milk"}]
            },
        }]

        baseline = generator.generate_product_baseline()["products"]["allergen"]

        assert baseline["allergen_findings"] == ["milk"]


class TestSnapshotComparison:
    """Tests for snapshot comparison."""

    @pytest.fixture
    def baseline_snapshot(self, tmp_path):
        """Create baseline snapshot directory."""
        snapshot_dir = tmp_path / "baseline"
        snapshot_dir.mkdir()

        # Coverage summary
        with open(snapshot_dir / "coverage_summary.json", "w") as f:
            json.dump({
                "domain_coverage": {
                    "ingredients": 95.0,
                    "additives": 98.0,
                    "allergens": 100.0,
                }
            }, f)

        # Score distribution
        with open(snapshot_dir / "score_distribution.json", "w") as f:
            json.dump({
                "histogram": {"A": 50, "B": 30, "C": 15, "D": 4, "F": 1},
                "stats": {"mean": 72.5}
            }, f)

        # Contradictions
        with open(snapshot_dir / "contradictions_top20.json", "w") as f:
            json.dump({"total_contradictions": 5}, f)

        with open(snapshot_dir / "product_baseline.json", "w") as f:
            json.dump({"products": {"same": {"score": 70, "verdict": "SAFE"}}}, f)

        return str(snapshot_dir)

    @pytest.fixture
    def current_snapshot_no_change(self, tmp_path):
        """Create current snapshot with no significant changes."""
        snapshot_dir = tmp_path / "current_no_change"
        snapshot_dir.mkdir()

        with open(snapshot_dir / "coverage_summary.json", "w") as f:
            json.dump({
                "domain_coverage": {
                    "ingredients": 95.5,  # +0.5% - no alert
                    "additives": 97.5,    # -0.5% - no alert
                    "allergens": 100.0,
                }
            }, f)

        with open(snapshot_dir / "score_distribution.json", "w") as f:
            json.dump({
                "histogram": {"A": 52, "B": 29, "C": 14, "D": 4, "F": 1},  # Small changes
                "stats": {"mean": 73.0}  # +0.5 - no alert
            }, f)

        with open(snapshot_dir / "contradictions_top20.json", "w") as f:
            json.dump({"total_contradictions": 6}, f)  # +1 - no alert

        with open(snapshot_dir / "product_baseline.json", "w") as f:
            json.dump({"products": {"same": {"score": 70, "verdict": "SAFE"}}}, f)

        return str(snapshot_dir)

    @pytest.fixture
    def current_snapshot_with_drift(self, tmp_path):
        """Create current snapshot with significant drift."""
        snapshot_dir = tmp_path / "current_drift"
        snapshot_dir.mkdir()

        with open(snapshot_dir / "coverage_summary.json", "w") as f:
            json.dump({
                "domain_coverage": {
                    "ingredients": 88.0,  # -7% - ALERT
                    "additives": 98.0,
                    "allergens": 100.0,
                }
            }, f)

        with open(snapshot_dir / "score_distribution.json", "w") as f:
            json.dump({
                "histogram": {"A": 30, "B": 40, "C": 20, "D": 8, "F": 2},  # A dropped by 20 - ALERT
                "stats": {"mean": 65.0}  # -7.5 - ALERT
            }, f)

        with open(snapshot_dir / "contradictions_top20.json", "w") as f:
            json.dump({"total_contradictions": 15}, f)  # +10 - ALERT

        with open(snapshot_dir / "product_baseline.json", "w") as f:
            json.dump({"products": {"same": {"score": 70, "verdict": "SAFE"}}}, f)

        return str(snapshot_dir)

    def test_comparison_no_alerts_when_stable(self, baseline_snapshot, current_snapshot_no_change):
        """Comparison should pass when changes are within thresholds."""
        comparison = RegressionSnapshotGenerator.compare_snapshots(
            baseline_snapshot, current_snapshot_no_change
        )

        assert comparison["passed"] is True
        assert len(comparison["alerts"]) == 0

    def test_comparison_alerts_on_coverage_drift(self, baseline_snapshot, current_snapshot_with_drift):
        """Comparison should alert on significant coverage drift."""
        comparison = RegressionSnapshotGenerator.compare_snapshots(
            baseline_snapshot, current_snapshot_with_drift
        )

        assert comparison["passed"] is False
        assert any("ingredients" in alert for alert in comparison["alerts"])
        assert comparison["deltas"]["coverage"]["ingredients"]["delta"] == -7.0

    def test_comparison_alerts_on_score_drift(self, baseline_snapshot, current_snapshot_with_drift):
        """Comparison should alert on significant score distribution changes."""
        comparison = RegressionSnapshotGenerator.compare_snapshots(
            baseline_snapshot, current_snapshot_with_drift
        )

        assert any("grade A" in alert for alert in comparison["alerts"])
        assert any("Mean score" in alert for alert in comparison["alerts"])

    def test_comparison_alerts_on_contradiction_increase(self, baseline_snapshot, current_snapshot_with_drift):
        """Comparison should alert on significant contradiction increases."""
        comparison = RegressionSnapshotGenerator.compare_snapshots(
            baseline_snapshot, current_snapshot_with_drift
        )

        assert any("Contradiction" in alert for alert in comparison["alerts"])
        assert comparison["deltas"]["contradictions"]["delta"] == 10

    def test_missing_or_corrupt_snapshot_is_blocking(self, baseline_snapshot, tmp_path):
        corrupt = tmp_path / "corrupt"
        corrupt.mkdir()
        (corrupt / "coverage_summary.json").write_text("{", encoding="utf-8")

        comparison = RegressionSnapshotGenerator.compare_snapshots(
            baseline_snapshot, str(corrupt)
        )

        assert comparison["passed"] is False
        assert any("Snapshot read error" in alert for alert in comparison["alerts"])

    def test_offsetting_product_score_changes_and_missing_product_are_blocking(self, tmp_path):
        baseline = tmp_path / "baseline_products"
        current = tmp_path / "current_products"
        baseline.mkdir()
        current.mkdir()
        stable_files = {
            "coverage_summary.json": {"domain_coverage": {}},
            "score_distribution.json": {"histogram": {}, "stats": {"mean": 50}},
            "contradictions_top20.json": {"total_contradictions": 0},
        }
        for filename, payload in stable_files.items():
            (baseline / filename).write_text(json.dumps(payload), encoding="utf-8")
            (current / filename).write_text(json.dumps(payload), encoding="utf-8")
        (baseline / "product_baseline.json").write_text(json.dumps({"products": {
            "up": {"score": 40}, "down": {"score": 60}, "missing": {"score": 50},
        }}), encoding="utf-8")
        (current / "product_baseline.json").write_text(json.dumps({"products": {
            "up": {"score": 60}, "down": {"score": 40},
        }}), encoding="utf-8")

        comparison = RegressionSnapshotGenerator.compare_snapshots(str(baseline), str(current))

        assert comparison["passed"] is False
        assert comparison["deltas"]["products"]["missing"] == ["missing"]
        assert set(comparison["deltas"]["products"]["changed"]) == {"up", "down"}


class TestEndToEndSnapshot:
    """End-to-end tests for snapshot generation and comparison."""

    def test_generate_and_compare_workflow(self, tmp_path):
        """Full workflow: generate snapshot, modify data, generate again, compare."""
        # Create two sets of products
        products_v1 = [
            {
                "dsld_id": "1",
                "score_100_equivalent": 80.0,
                "safety_verdict": "SAFE",
                "match_ledger": {
                    "domains": {
                        "ingredients": {"total_raw": 10, "matched": 10, "unmatched": 0, "entries": []}
                    }
                }
            }
            for _ in range(100)
        ]

        products_v2 = [
            {
                "dsld_id": str(i),
                "score_100_equivalent": 70.0 if i < 20 else 80.0,  # 20 products dropped
                "safety_verdict": "SAFE",
                "match_ledger": {
                    "domains": {
                        "ingredients": {
                            "total_raw": 10,
                            "matched": 9 if i < 10 else 10,  # 10 products have unmatched
                            "unmatched": 1 if i < 10 else 0,
                            "entries": []
                        }
                    }
                }
            }
            for i in range(100)
        ]

        # Generate snapshots
        v1_dir = tmp_path / "v1"
        v2_dir = tmp_path / "v2"

        gen1 = RegressionSnapshotGenerator()
        gen1.products = products_v1
        gen1.generate_all_snapshots(str(v1_dir))

        gen2 = RegressionSnapshotGenerator()
        gen2.products = products_v2
        gen2.generate_all_snapshots(str(v2_dir))

        # Compare
        comparison = RegressionSnapshotGenerator.compare_snapshots(str(v1_dir), str(v2_dir))

        # v2 has lower coverage and some score drops
        assert comparison["passed"] is False or len(comparison["alerts"]) > 0
        assert comparison["deltas"]["score_mean"]["delta"] < 0  # Mean dropped


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
