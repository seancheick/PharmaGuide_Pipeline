"""Pipeline reports are isolated by one shared, path-safe run ID."""

from __future__ import annotations

from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]

class TestCoverageGateRunIsolation:
    def test_coverage_reports_from_distinct_runs_do_not_overwrite(self, tmp_path):
        import sys

        if str(SCRIPTS_DIR) not in sys.path:
            sys.path.insert(0, str(SCRIPTS_DIR))

        from coverage_gate import BatchCoverageResult, CoverageGate  # noqa: E402

        # Minimal synthetic batch result
        batch = BatchCoverageResult(
            total_products=1,
            products_can_score=1,
            products_blocked=0,
            average_coverage=100.0,
            domain_coverage_summary={},
            total_correctness_issues=0,
            total_blocking_issues=0,
            total_warnings=0,
            product_results=[],
            blocked_product_ids=[],
            issues_by_type={},
        )

        gate = CoverageGate()
        out = tmp_path / "reports"

        json1, md1 = gate.generate_report(batch, out, run_id="run-a")
        assert json1.exists()
        assert md1.exists()

        json2, md2 = gate.generate_report(batch, out, run_id="run-b")

        assert json1 != json2
        assert md1 != md2
        assert json1.parent.name == "run-a"
        assert json2.parent.name == "run-b"
        assert len(list(out.glob("runs/*/coverage_report.json"))) == 2
        assert len(list(out.glob("runs/*/coverage_report.md"))) == 2


def test_report_run_id_rejects_path_traversal(tmp_path):
    import sys

    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    from run_artifacts import report_run_directory

    with pytest.raises(ValueError):
        report_run_directory(tmp_path, "../escape")
