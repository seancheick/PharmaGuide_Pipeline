"""
Permanent regression guards: the inactive-safety + active-parity audits
must exit clean on every build.

These tests wrap the two CI-grade audit scripts so they fire on every
pytest invocation. Without this gate, a regression in the resolver or
the blob builder could silently re-introduce the TiO2/Talc/Yohimbe gap
class and not be caught until next manual audit run.

Tests:
  - test_audit_inactive_safety_passes_on_current_build
      → wraps scripts/audit_inactive_safety.py against any available build
      → fails on banned-in-inactives signal gaps or notes-only FPs
  - test_audit_active_banned_recalled_parity_passes_on_current_build
      → wraps scripts/audit_active_banned_recalled_parity.py
      → fails on BLOCKER per-ingredient flag gaps or notes-only FPs
      → HIGH warnings-array gaps are tracked separately (audit exits 0)

Each test skips cleanly when no build directory is available — does not
turn into a noisy false-positive in a fresh checkout.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"

_BUILD_CANDIDATES = (
    # Prefer the canonical current build (scripts/dist via symlink) so the
    # gate runs against the latest pipeline output. Older scratch dirs in
    # /tmp/pharmaguide_release_build_* are kept as fall-backs in case the
    # canonical link is missing in a CI runner without recent pipeline run.
    Path("/tmp/pharmaguide_release_build"),
    SCRIPTS / "dist",
    SCRIPTS / "final_db_output",
    Path("/tmp/pharmaguide_release_build_v6"),
    Path("/tmp/pharmaguide_release_build_v5"),
    Path("/tmp/pharmaguide_release_build_v4"),
    Path("/tmp/pharmaguide_release_build_v3"),
    Path("/tmp/pharmaguide_release_build_canonical_id"),
    Path("/tmp/pharmaguide_release_build_inactives"),
)


def _first_available_build() -> Path | None:
    for c in _BUILD_CANDIDATES:
        if (c / "detail_blobs").is_dir():
            return c
    return None


def _run_audit(script_name: str, build_dir: Path, out_path: Path) -> subprocess.CompletedProcess:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    return subprocess.run(
        [sys.executable, str(SCRIPTS / script_name),
         "--build-dir", str(build_dir),
         "--out", str(out_path)],
        capture_output=True,
        text=True,
    )


def test_audit_inactive_safety_passes_on_current_build() -> None:
    """The inactive-safety audit must exit 0. Exit code 1 means banned
    inactives are shipping without safety signal — that's the TiO2/Talc
    contract regression."""
    base = _first_available_build()
    if base is None:
        pytest.skip("no build directory available — skip safety-audit CI gate")
    out = ROOT / "reports" / "ci_gate_inactive_safety.json"
    r = _run_audit("audit_inactive_safety.py", base, out)
    if r.returncode == 0:
        return
    # Surface specific gaps in the failure message
    try:
        report = json.loads(out.read_text())
    except Exception:
        pytest.fail(
            f"audit_inactive_safety.py exited {r.returncode} but report unreadable. "
            f"stderr: {r.stderr[:400]}"
        )
    summary = report.get("summary", {})
    sample_violations = report.get("check_1_banned_signal_violations", [])[:3]
    notes_fps = report.get("check_2_notes_only_false_positives", [])
    pytest.fail(
        "audit_inactive_safety.py FAILED (banned inactives shipping without "
        "safety signal OR notes-only matches detected).\n"
        f"  summary: {summary}\n"
        f"  first 3 violations: {sample_violations}\n"
        f"  notes-only FPs: {notes_fps}\n"
        f"  full report at: {out}"
    )


def test_audit_active_banned_recalled_parity_passes_on_current_build() -> None:
    """The active-side parity audit must exit 0. Exit code 1 means a
    banned/high_risk/recalled active is shipping without is_safety_concern
    — that's the Yohimbe/Cannabidiol/Garcinia regression."""
    base = _first_available_build()
    if base is None:
        pytest.skip("no build directory available — skip active-parity CI gate")
    out = ROOT / "reports" / "ci_gate_active_parity.json"
    r = _run_audit("audit_active_banned_recalled_parity.py", base, out)
    if r.returncode == 0:
        return
    try:
        report = json.loads(out.read_text())
    except Exception:
        pytest.fail(
            f"audit_active_banned_recalled_parity.py exited {r.returncode} but report unreadable. "
            f"stderr: {r.stderr[:400]}"
        )
    summary = report.get("summary", {})
    blocker_examples = (report.get("examples_by_severity") or {}).get("BLOCKER", [])[:3]
    notes_fps = report.get("notes_only_violations", [])
    pytest.fail(
        "audit_active_banned_recalled_parity.py FAILED (BLOCKER per-ingredient "
        "safety-flag gaps OR notes-only matches detected).\n"
        f"  summary: {summary}\n"
        f"  first 3 BLOCKER examples: {blocker_examples}\n"
        f"  notes-only FPs: {notes_fps}\n"
        f"  full report at: {out}"
    )
