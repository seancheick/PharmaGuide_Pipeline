"""Verification receipts bind a real process result to its preserved log."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from audits.run_verification_gate import run_gate  # noqa: E402


def test_success_receipt_binds_exit_code_command_and_log(tmp_path: Path) -> None:
    log = tmp_path / "gate.log"
    receipt = tmp_path / "gate.receipt.json"

    exit_code = run_gate(
        name="pipeline_fast_suite",
        command=[sys.executable, "-c", "print('all green')"],
        log_path=log,
        receipt_path=receipt,
        cwd=tmp_path,
    )

    assert exit_code == 0
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    assert payload["gate_name"] == "pipeline_fast_suite"
    assert payload["exit_code"] == 0
    assert payload["command"] == [sys.executable, "-c", "print('all green')"]
    assert payload["log_sha256"] == hashlib.sha256(log.read_bytes()).hexdigest()
    assert "all green" in log.read_text(encoding="utf-8")


def test_failed_command_still_writes_nonzero_receipt(tmp_path: Path) -> None:
    log = tmp_path / "gate.log"
    receipt = tmp_path / "gate.receipt.json"

    exit_code = run_gate(
        name="pipeline_release_suite",
        command=[sys.executable, "-c", "print('failed'); raise SystemExit(7)"],
        log_path=log,
        receipt_path=receipt,
        cwd=tmp_path,
    )

    assert exit_code == 7
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    assert payload["exit_code"] == 7
    assert payload["completed_at"]
