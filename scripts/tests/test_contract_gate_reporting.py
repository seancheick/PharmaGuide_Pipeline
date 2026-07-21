"""Tests for the enrichment contract gate's failure diagnostics.

When the gate blocks a release it must (a) leave the returned summary contract
UNCHANGED — callers and guardrail wiring depend on its exact shape — and
(b) persist a full JSON violation report under a run-specific directory so the
block is diagnosable without re-running the validator by hand.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from run_pipeline import PipelineRunner

# A product whose display ledger is present but incomplete → contract errors
# (missing audit + missing required display-row fields).
_FAILING_PRODUCT = {
    "dsld_id": "GATE-REPORT-TEST",
    "display_ingredients": [
        {"raw_source_path": "ingredientRows[0]", "raw_source_text": "Vitamin C"}
    ],
}

_SUMMARY_KEYS = {"products_checked", "products_with_violations", "errors", "warnings"}


def test_gate_writes_run_specific_report_and_keeps_summary_shape(tmp_path):
    runner = PipelineRunner()
    ok, summary = runner.run_enrichment_contract_gate(
        [dict(_FAILING_PRODUCT)],
        report_dir=str(tmp_path),
        run_id="RUN-123",
    )

    assert ok is False
    # Diagnostics must NOT leak into the returned summary contract.
    assert set(summary) == _SUMMARY_KEYS
    assert summary["errors"] > 0

    report = (
        tmp_path / "reports" / "runs" / "RUN-123"
        / "enrichment_contract_gate_violations.json"
    )
    assert report.exists(), "gate must persist a run-specific violation report"
    data = json.loads(report.read_text())
    assert "errors_by_rule" in data and data["errors_by_rule"]
    assert data["products"], "report must enumerate per-product violations"


def test_gate_report_is_skipped_when_no_report_dir(tmp_path):
    runner = PipelineRunner()
    ok, summary = runner.run_enrichment_contract_gate([dict(_FAILING_PRODUCT)])

    assert ok is False
    assert set(summary) == _SUMMARY_KEYS
    # Nothing written when no report_dir is provided.
    assert not list(tmp_path.rglob("enrichment_contract_gate_violations.json"))


def test_gate_falls_back_to_flat_report_dir_without_run_id(tmp_path):
    runner = PipelineRunner()
    ok, _summary = runner.run_enrichment_contract_gate(
        [dict(_FAILING_PRODUCT)],
        report_dir=str(tmp_path),
    )
    assert ok is False
    report = tmp_path / "reports" / "enrichment_contract_gate_violations.json"
    assert report.exists(), "without run_id the report writes to reports/ directly"
