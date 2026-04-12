"""
T0: Report overwrite hygiene.

Pipeline report artifacts (enrichment_summary, scoring_summary, impact_report,
coverage_report) must use stable filenames without timestamps so re-running the
pipeline overwrites the previous artifact instead of accumulating stale reports.

Run logs (clean_dsld_data, batch_processor) intentionally keep timestamps and
are out of scope.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class TestStableFilenames:
    """Source-level contract: the report writer lines must not inject a timestamp."""

    def test_enrichment_summary_filename_has_no_timestamp(self):
        src = _read(SCRIPTS_DIR / "enrich_supplements_v3.py")
        # Match the enrichment_summary write site (report_prefix with f-string)
        matches = re.findall(
            r'f"\{report_prefix\}[^"]*"',
            src,
        )
        assert matches, "Could not locate enrichment_summary filename construction"
        for m in matches:
            assert "strftime" not in m and "{datetime" not in m, (
                f"enrichment_summary filename must not embed a timestamp, got: {m}"
            )

    def test_scoring_summary_filename_has_no_timestamp(self):
        src = _read(SCRIPTS_DIR / "score_supplements.py")
        # Match both f"scoring_summary_{ts}.json" and "scoring_summary.json"
        match = re.search(
            r'f?["\']scoring_summary[^"\']*["\']',
            src,
        )
        assert match, "Could not locate scoring_summary filename construction"
        assert "strftime" not in match.group(0) and "{" not in match.group(0), (
            f"scoring_summary filename must not embed a timestamp, got: {match.group(0)}"
        )

    def test_impact_report_filename_has_no_timestamp(self):
        src = _read(SCRIPTS_DIR / "score_supplements.py")
        match = re.search(
            r'f?["\']impact_report[^"\']*["\']',
            src,
        )
        assert match, "Could not locate impact_report filename construction"
        assert "strftime" not in match.group(0) and "{" not in match.group(0), (
            f"impact_report filename must not embed a timestamp, got: {match.group(0)}"
        )

    def test_coverage_gate_filename_has_no_timestamp(self):
        src = _read(SCRIPTS_DIR / "coverage_gate.py")
        # coverage_gate uses {filename_prefix}_{timestamp}.{ext}
        matches = re.findall(
            r'f"\{filename_prefix\}[^"]*\.(json|md)"',
            src,
        )
        # The regex above only captures the extension group; use finditer instead
        writer_lines = re.findall(
            r'f"\{filename_prefix\}[^"]*"',
            src,
        )
        assert writer_lines, "Could not locate coverage_report filename construction"
        for line in writer_lines:
            assert "{timestamp}" not in line and "strftime" not in line, (
                f"coverage_report filename must not embed a timestamp, got: {line}"
            )


class TestCoverageGateOverwritesOnRerun:
    """Integration check: calling generate_report twice must not create duplicates."""

    def test_coverage_report_overwrites_on_second_call(self, tmp_path):
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

        # First run
        json1, md1 = gate.generate_report(batch, out)
        assert json1.exists()
        assert md1.exists()

        # Second run — same output dir, same inputs
        json2, md2 = gate.generate_report(batch, out)

        # Must be the SAME paths (overwrite), not new ones
        assert json1 == json2, (
            f"Re-run produced a new JSON path instead of overwriting: {json1} vs {json2}"
        )
        assert md1 == md2, (
            f"Re-run produced a new MD path instead of overwriting: {md1} vs {md2}"
        )

        # Exactly one of each in the dir
        json_files = sorted(out.glob("coverage_report*.json"))
        md_files = sorted(out.glob("coverage_report*.md"))
        assert len(json_files) == 1, f"Expected 1 coverage_report JSON, got {json_files}"
        assert len(md_files) == 1, f"Expected 1 coverage_report MD, got {md_files}"

        # Stable names
        assert json_files[0].name == "coverage_report.json"
        assert md_files[0].name == "coverage_report.md"
