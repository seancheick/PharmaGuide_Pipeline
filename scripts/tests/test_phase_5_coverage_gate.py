#!/usr/bin/env python3
"""
Phase 5 — Coverage Gate contract test.

Locks the Phase 5 invariant: every entry across the 3 reference files
either has at least one role from the locked vocab, OR is in an
explicit architectural exclusion class.

If this test breaks in the future, either:
  (a) the data file has a new entry that needs a Phase 3-style backfill,
  (b) a new architectural exclusion needs to be added to the gate
      (requires clinician sign-off — update CLINICIAN_REVIEW.md), OR
  (c) someone introduced a typo / unauthorized vocab drift.

Don't loosen this test silently.
"""

import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent
GATE_SCRIPT = SCRIPTS_DIR / "coverage_gate_functional_roles.py"


def test_coverage_gate_passes():
    """The gate must report 0 missing roles and 0 invalid role-ids."""
    result = subprocess.run(
        [sys.executable, str(GATE_SCRIPT)],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, (
        f"coverage gate FAILED (exit {result.returncode}):\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )
    assert "GATE PASS" in result.stdout
    assert "100.0%" in result.stdout


def test_coverage_gate_with_verbose_flag():
    """--verbose flag works without crashing."""
    result = subprocess.run(
        [sys.executable, str(GATE_SCRIPT), "--verbose"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0
