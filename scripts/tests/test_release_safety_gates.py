"""Tests for scripts/release_safety/gates.py — cleanup gates orchestrator
(ADR-0001 P1.5b).

This is the integration test layer for P1.1-P1.5a. Real git repos +
real on-disk fixtures throughout — the orchestrator is the safety
primitive's single point of truth, so we test against real I/O instead
of mocks wherever feasible.

Test coverage map:
  - Preconditions: lock acquisition, index validation, protected-set
    hard failure (each short-circuits)
  - Aggregation: degenerate-in-execute, Gate 1, Gate 2, Gate 3 all
    aggregate failures into one GateResult
  - Override semantics: bundle_mismatch override, expected_count override
  - Mode semantics: DRY_RUN does not require lock; EXECUTE rejects degenerate
  - Idempotency: two consecutive runs produce identical decision content
  - **2026-05-12 full-stack regression**: the complete failure-mode
    proof — running gates against the May 12 conditions in EXECUTE
    mode rejects the cleanup with no destructive deletions queued.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
import pytest

_scripts_dir = os.path.join(os.path.dirname(__file__), "..")
if _scripts_dir not in sys.path:
    sys.path.insert(0, os.path.abspath(_scripts_dir))


# ---------------------------------------------------------------------------
# Fixture helpers — same shape as P1.4 tests for consistency
# ---------------------------------------------------------------------------


def _h(idx: int) -> str:
    """64-char lowercase hex hash, deterministic from idx."""
    return f"{idx:064x}"


def _git_init(repo_path: Path, default_branch: str = "main") -> None:
    subprocess.run(["git", "init", "-b", default_branch], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@release-safety.local"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Release-Safety Test"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=repo_path, check=True, capture_output=True)


def _make_catalog_db(path: Path, blob_hashes: list) -> str:
    """Build a minimal SQLite catalog with products_core schema. Returns
    its SHA256."""
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(str(path))
    try:
        conn.execute(
            "CREATE TABLE products_core ("
            "  dsld_id TEXT PRIMARY KEY, "
            "  detail_blob_sha256 TEXT)"
        )
        for i, h in enumerate(blob_hashes):
            conn.execute("INSERT INTO products_core VALUES (?, ?)", (str(1000 + i), h))
        conn.commit()
    finally:
        conn.close()
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(64 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest()


def _commit_bundle(repo_path: Path, blob_hashes: list, db_version: str = "vBUNDLED") -> dict:
    assets_db = repo_path / "assets" / "db"
    assets_db.mkdir(parents=True, exist_ok=True)
    catalog_path = assets_db / "pharmaguide_core.db"
    checksum = _make_catalog_db(catalog_path, blob_hashes)
    manifest = {
        "db_version": db_version,
        "checksum_sha256": checksum,
        "product_count": len(blob_hashes),
    }
    (assets_db / "export_manifest.json").write_text(json.dumps(manifest))
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", f"bundle {db_version}"], cwd=repo_path, check=True, capture_output=True)
    return manifest


def _make_dist(dist_dir: Path, blob_hashes: list, db_version: str = "vDIST") -> None:
    dist_dir.mkdir(parents=True, exist_ok=True)
    detail_index = {}
    for i, h in enumerate(blob_hashes):
        dsld_id = str(1000 + i)
        detail_index[dsld_id] = {
            "blob_sha256": h,
            "storage_path": f"shared/details/sha256/{h[:2]}/{h}.json",
            "blob_version": 1,
        }
    (dist_dir / "detail_index.json").write_text(json.dumps(detail_index))
    (dist_dir / "export_manifest.json").write_text(json.dumps({
        "db_version": db_version,
        "checksum_sha256": "dist_irrelevant_for_p1_5b",
    }))


def _setup_aligned_environment(
    tmp_path: Path,
    *,
    hashes,
    db_version: str = "vALIGNED",
):
    """Build a Flutter repo + dist where bundled and dist agree completely."""
    flutter_repo = tmp_path / "flutter"
    flutter_repo.mkdir()
    _git_init(flutter_repo)
    _commit_bundle(flutter_repo, hashes, db_version=db_version)
    dist_dir = tmp_path / "dist"
    _make_dist(dist_dir, hashes, db_version=db_version)
    return flutter_repo, dist_dir


def _setup_misaligned_environment(
    tmp_path: Path,
    *,
    bundled_hashes,
    dist_hashes,
    bundled_version: str,
    dist_version: str,
):
    """Build a Flutter repo + dist with deliberately differing versions/hashes."""
    flutter_repo = tmp_path / "flutter"
    flutter_repo.mkdir()
    _git_init(flutter_repo)
    _commit_bundle(flutter_repo, bundled_hashes, db_version=bundled_version)
    dist_dir = tmp_path / "dist"
    _make_dist(dist_dir, dist_hashes, db_version=dist_version)
    return flutter_repo, dist_dir


def _make_test_audit_log(tmp_path: Path, name: str = "audit") -> "AuditLog":
    """Audit log with a known path + stable release_id for test assertions."""
    from release_safety.audit_log import AuditLog
    return AuditLog(tmp_path / f"{name}.jsonl", release_id=f"test_{name}")


# ---------------------------------------------------------------------------
# Test 1 — happy path DRY_RUN (default mode; lock not required)
# ---------------------------------------------------------------------------


def test_p1_5b_happy_path_dry_run_passes_all_gates(tmp_path):
    from release_safety.gates import (
        evaluate_cleanup_gates, GateMode,
    )

    hashes = [_h(i) for i in range(10)]
    flutter_repo, dist_dir = _setup_aligned_environment(tmp_path, hashes=hashes)
    audit = _make_test_audit_log(tmp_path)

    result = evaluate_cleanup_gates(
        flutter_repo, dist_dir,
        candidate_blobs=[],          # nothing to delete; trivial pass on Gate 2
        storage_total=10,
        mode=GateMode.DRY_RUN,
        audit_log=audit,
    )

    assert result.passed is True
    assert result.failures == []
    assert result.mode == GateMode.DRY_RUN
    assert result.protected_set is not None
    assert not result.protected_set.degenerate
    assert result.would_delete_count == 0


# ---------------------------------------------------------------------------
# Test 2 — happy path EXECUTE
# ---------------------------------------------------------------------------


def test_p1_5b_happy_path_execute_passes_all_gates(tmp_path):
    from release_safety.gates import (
        evaluate_cleanup_gates, GateMode,
    )

    hashes = [_h(i) for i in range(10)]
    flutter_repo, dist_dir = _setup_aligned_environment(tmp_path, hashes=hashes)
    audit = _make_test_audit_log(tmp_path)
    lock_path = tmp_path / ".release.lock"

    result = evaluate_cleanup_gates(
        flutter_repo, dist_dir,
        candidate_blobs=[],
        storage_total=10,
        mode=GateMode.EXECUTE,
        audit_log=audit,
        lock_path=lock_path,
    )

    assert result.passed is True
    assert result.failures == []
    assert result.mode == GateMode.EXECUTE
    # Lock was acquired and released — file must NOT exist post-call.
    assert not lock_path.exists()


# ---------------------------------------------------------------------------
# Test 3 — DRY_RUN does NOT require the lock (read-only operation)
# ---------------------------------------------------------------------------


def test_p1_5b_dry_run_does_not_require_lock(tmp_path):
    """Per HR-12, read-only operations do not need the pipeline lock.
    Even if a lock is currently held by another process, DRY_RUN proceeds."""
    from release_safety.gates import evaluate_cleanup_gates, GateMode
    from release_safety.lock import acquire_release_lock

    hashes = [_h(i) for i in range(5)]
    flutter_repo, dist_dir = _setup_aligned_environment(tmp_path, hashes=hashes)
    audit = _make_test_audit_log(tmp_path)
    lock_path = tmp_path / ".release.lock"

    # Hold the lock from "another process" (this same Python process; the
    # same-process re-entry protection means an EXECUTE run from this
    # PID could re-enter, but DRY_RUN doesn't even check).
    with acquire_release_lock(lock_path) as _holder:
        assert lock_path.exists()
        result = evaluate_cleanup_gates(
            flutter_repo, dist_dir,
            candidate_blobs=[], storage_total=5,
            mode=GateMode.DRY_RUN,
            audit_log=audit,
            lock_path=lock_path,
        )
        # Gates passed without touching the lock.
        assert result.passed is True
    # Lock file removed by the holder's exit.
    assert not lock_path.exists()


# ---------------------------------------------------------------------------
# Test 4 — EXECUTE lock contention short-circuits with no other gate run
# ---------------------------------------------------------------------------


def test_p1_5b_lock_contention_short_circuits(tmp_path):
    """Per the user's adjustment: lock acquisition failure is a true
    precondition — short-circuit, no aggregation. Subsequent gates can't
    safely run without the lock."""
    from release_safety.gates import evaluate_cleanup_gates, GateMode
    from release_safety.audit_log import read_audit_log

    hashes = [_h(i) for i in range(5)]
    flutter_repo, dist_dir = _setup_aligned_environment(tmp_path, hashes=hashes)
    audit = _make_test_audit_log(tmp_path)
    lock_path = tmp_path / ".release.lock"

    # Pre-write a lock file claiming the current PID (definitely live) so
    # the gate's acquisition fails with LockContentionError.
    import socket
    lock_path.write_text(json.dumps({
        "pid": os.getpid(),
        "host": socket.gethostname(),
        "started_at": "2026-05-12T20:00:00+00:00",
        "current_step": "blocked_step",
    }))

    result = evaluate_cleanup_gates(
        flutter_repo, dist_dir,
        candidate_blobs=[], storage_total=5,
        mode=GateMode.EXECUTE,
        audit_log=audit,
        lock_path=lock_path,
    )

    assert result.passed is False
    assert len(result.failures) == 1, "lock contention must short-circuit (single failure)"
    assert result.failures[0].gate_name == "lock_acquisition"
    assert result.failures[0].overridable is False
    # The pre-existing lock file must remain untouched (we didn't acquire it).
    assert lock_path.exists()
    # Audit log captured the failure.
    events = read_audit_log(audit.path)
    assert any(e["event_type"] == "gate_failed" and
               e.get("gate_name") == "lock_acquisition" for e in events)


# ---------------------------------------------------------------------------
# Test 5 — index validation failure short-circuits
# ---------------------------------------------------------------------------


def test_p1_5b_index_validation_failure_short_circuits(tmp_path):
    """Malformed dist/detail_index.json is a precondition failure: cannot
    safely compute any subsequent gate. Short-circuit with a single failure."""
    from release_safety.gates import evaluate_cleanup_gates, GateMode

    flutter_repo, dist_dir = _setup_aligned_environment(tmp_path, hashes=[_h(0)])
    # Corrupt the dist detail_index AFTER setup
    (dist_dir / "detail_index.json").write_text("THIS IS NOT JSON {{")

    audit = _make_test_audit_log(tmp_path)
    result = evaluate_cleanup_gates(
        flutter_repo, dist_dir,
        candidate_blobs=[], storage_total=1,
        mode=GateMode.DRY_RUN,
        audit_log=audit,
    )

    assert result.passed is False
    assert len(result.failures) == 1
    assert result.failures[0].gate_name == "index_validation"
    assert result.protected_set is None       # never computed


# ---------------------------------------------------------------------------
# Test 6 — protected-set HARD failure short-circuits
# ---------------------------------------------------------------------------


def test_p1_5b_protected_set_hard_failure_short_circuits(tmp_path):
    """Working-tree catalog SHA256 mismatch (LFS-pointer scenario or local
    edit) is a HARD failure from compute_protected_blob_set — short-circuit."""
    from release_safety.gates import evaluate_cleanup_gates, GateMode

    hashes = [_h(i) for i in range(3)]
    flutter_repo, dist_dir = _setup_aligned_environment(tmp_path, hashes=hashes)

    # Poison the working-tree catalog (simulates LFS pointer / local edit).
    wt_catalog = flutter_repo / "assets" / "db" / "pharmaguide_core.db"
    wt_catalog.write_bytes(b"version https://git-lfs.github.com/spec/v1\noid sha256:deadbeef\nsize 12345\n")

    audit = _make_test_audit_log(tmp_path)
    result = evaluate_cleanup_gates(
        flutter_repo, dist_dir,
        candidate_blobs=[], storage_total=3,
        mode=GateMode.DRY_RUN,
        audit_log=audit,
    )

    assert result.passed is False
    assert len(result.failures) == 1
    assert result.failures[0].gate_name == "protected_set_computation"
    assert result.failures[0].overridable is False


# ---------------------------------------------------------------------------
# Test 7 — degenerate protected set in DRY_RUN passes with audit event
# ---------------------------------------------------------------------------


def test_p1_5b_degenerate_protection_dry_run_passes(tmp_path):
    """When bundled side is unavailable (no manifest on main), DRY_RUN
    permits the run with degenerate protection (audit-only event).
    Useful for visualization / dry-run in fresh environments."""
    from release_safety.gates import evaluate_cleanup_gates, GateMode
    from release_safety.audit_log import read_audit_log

    # Fresh Flutter repo with NO bundle commit — only an unrelated commit.
    flutter_repo = tmp_path / "flutter"
    flutter_repo.mkdir()
    _git_init(flutter_repo)
    (flutter_repo / "README").write_text("hello")
    subprocess.run(["git", "add", "."], cwd=flutter_repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=flutter_repo, check=True, capture_output=True)

    dist_dir = tmp_path / "dist"
    _make_dist(dist_dir, [_h(0), _h(1)], db_version="vDIST")

    audit = _make_test_audit_log(tmp_path)
    result = evaluate_cleanup_gates(
        flutter_repo, dist_dir,
        candidate_blobs=[], storage_total=2,
        mode=GateMode.DRY_RUN,
        audit_log=audit,
    )

    assert result.passed is True
    assert result.failures == []
    assert result.protected_set is not None
    assert result.protected_set.degenerate is True
    # Audit event for the degenerate-allowed informational record
    events = read_audit_log(audit.path)
    assert any(e["event_type"] == "degenerate_protection_allowed_dry_run" for e in events)


# ---------------------------------------------------------------------------
# Test 8 — degenerate protected set in EXECUTE FAILS, AGGREGATING with
#          other failures (per P1.5b sign-off)
# ---------------------------------------------------------------------------


def test_p1_5b_degenerate_protection_execute_fails_aggregated(tmp_path):
    """When bundled is unavailable AND mode=EXECUTE, the degenerate
    protection is a non-overridable failure — but it AGGREGATES with
    other gate failures rather than short-circuiting."""
    from release_safety.gates import evaluate_cleanup_gates, GateMode

    # Fresh repo, no bundle (degenerate) AND we'll hit Gate 3 too if
    # protected set is empty. Let's craft so degenerate + Gate 3 both fire.
    flutter_repo = tmp_path / "flutter"
    flutter_repo.mkdir()
    _git_init(flutter_repo)
    (flutter_repo / "README").write_text("hello")
    subprocess.run(["git", "add", "."], cwd=flutter_repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=flutter_repo, check=True, capture_output=True)

    dist_dir = tmp_path / "dist"
    # Empty dist index → Gate 3 (empty protected set) ALSO fires
    _make_dist(dist_dir, [], db_version="vDIST_EMPTY")

    audit = _make_test_audit_log(tmp_path)
    result = evaluate_cleanup_gates(
        flutter_repo, dist_dir,
        candidate_blobs=[], storage_total=0,
        mode=GateMode.EXECUTE,
        audit_log=audit,
        lock_path=tmp_path / ".release.lock",
    )

    assert result.passed is False
    failure_names = [f.gate_name for f in result.failures]
    # AGGREGATION: both failures present in the same result
    assert "degenerate_protection" in failure_names
    assert "live_version_sanity" in failure_names
    # degenerate failure is non-overridable
    deg = next(f for f in result.failures if f.gate_name == "degenerate_protection")
    assert deg.overridable is False


# ---------------------------------------------------------------------------
# Test 9 — Gate 1 misalignment, no override → fails
# ---------------------------------------------------------------------------


def test_p1_5b_gate_1_misalignment_no_override_fails(tmp_path):
    from release_safety.gates import evaluate_cleanup_gates, GateMode

    hashes = [_h(i) for i in range(5)]
    flutter_repo, dist_dir = _setup_misaligned_environment(
        tmp_path,
        bundled_hashes=hashes, dist_hashes=hashes,
        bundled_version="vBUNDLED_OLD",
        dist_version="vDIST_NEW",
    )
    audit = _make_test_audit_log(tmp_path)

    result = evaluate_cleanup_gates(
        flutter_repo, dist_dir,
        candidate_blobs=[], storage_total=5,
        mode=GateMode.EXECUTE,
        audit_log=audit,
        lock_path=tmp_path / ".release.lock",
    )

    assert result.passed is False
    failure = next((f for f in result.failures if f.gate_name == "bundle_alignment"), None)
    assert failure is not None
    assert failure.overridable is True
    assert failure.override_used is False
    assert "vBUNDLED_OLD" in failure.reason
    assert "vDIST_NEW" in failure.reason


# ---------------------------------------------------------------------------
# Test 10 — Gate 1 misalignment WITH override reason → passes
# ---------------------------------------------------------------------------


def test_p1_5b_gate_1_misalignment_with_override_passes(tmp_path):
    from release_safety.gates import (
        evaluate_cleanup_gates, GateMode, GateOverrides,
    )
    from release_safety.audit_log import read_audit_log

    hashes = [_h(i) for i in range(5)]
    flutter_repo, dist_dir = _setup_misaligned_environment(
        tmp_path,
        bundled_hashes=hashes, dist_hashes=hashes,
        bundled_version="vBUNDLED_OLD",
        dist_version="vDIST_NEW",
    )
    audit = _make_test_audit_log(tmp_path)

    override_reason = "Intentional rebuild after data fix; bundle commit deferred to next release."
    result = evaluate_cleanup_gates(
        flutter_repo, dist_dir,
        candidate_blobs=[], storage_total=5,
        mode=GateMode.EXECUTE,
        overrides=GateOverrides(bundle_mismatch_reason=override_reason),
        audit_log=audit,
        lock_path=tmp_path / ".release.lock",
    )

    assert result.passed is True
    # Override reason captured in audit
    events = read_audit_log(audit.path)
    bundle_event = next(
        e for e in events
        if e.get("event_type") == "gate_passed"
        and e.get("gate_name") == "bundle_alignment"
        and e.get("overridden") is True
    )
    assert bundle_event["override_reason"] == override_reason


# ---------------------------------------------------------------------------
# Test 11 — Gate 2 blast-radius exceeded, no expected-count → fails
# ---------------------------------------------------------------------------


def test_p1_5b_gate_2_blast_radius_exceeded_no_count_fails(tmp_path):
    from release_safety.gates import evaluate_cleanup_gates, GateMode

    bundled = [_h(i) for i in range(20)]
    flutter_repo, dist_dir = _setup_aligned_environment(
        tmp_path, hashes=bundled, db_version="vMATCH"
    )
    audit = _make_test_audit_log(tmp_path)

    # Storage_total = 100; threshold = 5%; would-delete = 10 > 5
    # candidate_blobs are NOT in protected set (they're new orphans)
    candidates = [_h(i) for i in range(100, 110)]
    result = evaluate_cleanup_gates(
        flutter_repo, dist_dir,
        candidate_blobs=candidates,
        storage_total=100,
        mode=GateMode.EXECUTE,
        audit_log=audit,
        lock_path=tmp_path / ".release.lock",
    )

    assert result.passed is False
    failure = next((f for f in result.failures if f.gate_name == "blast_radius"), None)
    assert failure is not None
    assert failure.overridable is True
    assert failure.override_used is False
    assert "10" in failure.reason
    assert "5" in failure.reason  # threshold


# ---------------------------------------------------------------------------
# Test 12 — Gate 2 blast-radius exceeded WITH matching expected-count → passes
# ---------------------------------------------------------------------------


def test_p1_5b_gate_2_blast_radius_exceeded_with_matching_count_passes(tmp_path):
    from release_safety.gates import (
        evaluate_cleanup_gates, GateMode, GateOverrides,
    )

    bundled = [_h(i) for i in range(20)]
    flutter_repo, dist_dir = _setup_aligned_environment(
        tmp_path, hashes=bundled, db_version="vMATCH"
    )
    audit = _make_test_audit_log(tmp_path)

    candidates = [_h(i) for i in range(100, 110)]
    result = evaluate_cleanup_gates(
        flutter_repo, dist_dir,
        candidate_blobs=candidates,
        storage_total=100,
        mode=GateMode.EXECUTE,
        overrides=GateOverrides(expected_count=10),     # matches actual
        audit_log=audit,
        lock_path=tmp_path / ".release.lock",
    )

    assert result.passed is True


# ---------------------------------------------------------------------------
# Test 13 — Gate 2 exceeded WITH WRONG expected-count → fails
# ---------------------------------------------------------------------------


def test_p1_5b_gate_2_blast_radius_exceeded_with_wrong_count_fails(tmp_path):
    """The override must EXACTLY equal would_delete_count. A close-but-
    wrong value still fails (the override is a sanity check, not a
    permission slip)."""
    from release_safety.gates import (
        evaluate_cleanup_gates, GateMode, GateOverrides,
    )

    bundled = [_h(i) for i in range(20)]
    flutter_repo, dist_dir = _setup_aligned_environment(
        tmp_path, hashes=bundled, db_version="vMATCH"
    )
    audit = _make_test_audit_log(tmp_path)

    candidates = [_h(i) for i in range(100, 110)]      # 10 candidates
    result = evaluate_cleanup_gates(
        flutter_repo, dist_dir,
        candidate_blobs=candidates,
        storage_total=100,
        mode=GateMode.EXECUTE,
        overrides=GateOverrides(expected_count=5),      # WRONG — actual is 10
        audit_log=audit,
        lock_path=tmp_path / ".release.lock",
    )

    assert result.passed is False
    failure = next((f for f in result.failures if f.gate_name == "blast_radius"), None)
    assert failure is not None
    assert failure.override_used is True
    assert "does not match actual" in failure.reason


# ---------------------------------------------------------------------------
# Test 14 — Gate 3 empty protected set → fails
# ---------------------------------------------------------------------------


def test_p1_5b_gate_3_empty_protected_set_fails(tmp_path):
    """Gate 3: refuses to permit deletion when protected set is empty
    (would otherwise allow deleting EVERYTHING)."""
    from release_safety.gates import evaluate_cleanup_gates, GateMode

    # Bundled with 0 rows (empty catalog) AND dist with 0 entries
    flutter_repo, dist_dir = _setup_aligned_environment(
        tmp_path, hashes=[], db_version="vEMPTY"
    )
    audit = _make_test_audit_log(tmp_path)

    result = evaluate_cleanup_gates(
        flutter_repo, dist_dir,
        candidate_blobs=[], storage_total=0,
        mode=GateMode.DRY_RUN,
        audit_log=audit,
    )

    assert result.passed is False
    failure = next((f for f in result.failures if f.gate_name == "live_version_sanity"), None)
    assert failure is not None
    assert failure.overridable is False
    assert "empty" in failure.reason


# ---------------------------------------------------------------------------
# Test 15 — multiple failures aggregate deterministically
# ---------------------------------------------------------------------------


def test_p1_5b_multiple_failures_aggregate_deterministically(tmp_path):
    """Misaligned versions (Gate 1 fail) AND large deletion (Gate 2 fail)
    in one run produce one GateResult with BOTH failures. Failure ordering
    is deterministic (Gate 1 → Gate 2 → Gate 3 by gate sequence)."""
    from release_safety.gates import evaluate_cleanup_gates, GateMode

    bundled = [_h(i) for i in range(20)]
    flutter_repo, dist_dir = _setup_misaligned_environment(
        tmp_path,
        bundled_hashes=bundled, dist_hashes=bundled,
        bundled_version="vBUNDLED_OLD",
        dist_version="vDIST_NEW",
    )
    audit = _make_test_audit_log(tmp_path)

    candidates = [_h(i) for i in range(100, 110)]
    result = evaluate_cleanup_gates(
        flutter_repo, dist_dir,
        candidate_blobs=candidates,
        storage_total=100,
        mode=GateMode.EXECUTE,
        audit_log=audit,
        lock_path=tmp_path / ".release.lock",
    )

    assert result.passed is False
    failure_names = [f.gate_name for f in result.failures]
    assert "bundle_alignment" in failure_names
    assert "blast_radius" in failure_names
    # Deterministic ordering: bundle_alignment evaluated before blast_radius
    assert failure_names.index("bundle_alignment") < failure_names.index("blast_radius")


# ---------------------------------------------------------------------------
# Test 16 — idempotency: two consecutive DRY_RUNs produce identical decisions
# ---------------------------------------------------------------------------


def test_p1_5b_idempotency_two_consecutive_dry_runs(tmp_path):
    """Running gates twice on identical inputs produces identical decision
    content in the audit log (modulo timestamps and per-call release_ids).
    Required by HR-9 — pipeline retries are inevitable."""
    from release_safety.gates import evaluate_cleanup_gates, GateMode
    from release_safety.audit_log import read_audit_log

    hashes = [_h(i) for i in range(5)]
    flutter_repo, dist_dir = _setup_aligned_environment(tmp_path, hashes=hashes)

    audit_a = _make_test_audit_log(tmp_path, name="run_a")
    audit_b = _make_test_audit_log(tmp_path, name="run_b")

    r_a = evaluate_cleanup_gates(
        flutter_repo, dist_dir,
        candidate_blobs=[], storage_total=5,
        mode=GateMode.DRY_RUN,
        audit_log=audit_a,
    )
    r_b = evaluate_cleanup_gates(
        flutter_repo, dist_dir,
        candidate_blobs=[], storage_total=5,
        mode=GateMode.DRY_RUN,
        audit_log=audit_b,
    )

    assert r_a.passed == r_b.passed
    assert r_a.failures == r_b.failures
    assert r_a.would_delete_count == r_b.would_delete_count
    assert r_a.protected_set.protected == r_b.protected_set.protected

    # Compare the audit-log decision events with timestamp + release_id stripped.
    def normalize(event: dict) -> dict:
        e = dict(event)
        e.pop("timestamp", None)
        e.pop("release_id", None)
        return e

    events_a = [normalize(e) for e in read_audit_log(audit_a.path)]
    events_b = [normalize(e) for e in read_audit_log(audit_b.path)]

    assert events_a == events_b, (
        "Idempotency breach: two identical DRY_RUNs produced different "
        "audit-log decision sequences."
    )


# ---------------------------------------------------------------------------
# Test 17 — audit log is written even on gate failure
# ---------------------------------------------------------------------------


def test_p1_5b_audit_log_written_on_failure(tmp_path):
    """The audit log is the evidence that the safety primitive worked. It
    must be written on failures, not just on passes."""
    from release_safety.gates import evaluate_cleanup_gates, GateMode
    from release_safety.audit_log import read_audit_log

    flutter_repo, dist_dir = _setup_misaligned_environment(
        tmp_path,
        bundled_hashes=[_h(0)], dist_hashes=[_h(1)],
        bundled_version="vA", dist_version="vB",
    )
    audit = _make_test_audit_log(tmp_path)

    result = evaluate_cleanup_gates(
        flutter_repo, dist_dir,
        candidate_blobs=[], storage_total=2,
        mode=GateMode.EXECUTE,
        audit_log=audit,
        lock_path=tmp_path / ".release.lock",
    )

    assert result.passed is False
    # Audit log file exists and has events
    assert audit.path.exists()
    events = read_audit_log(audit.path)
    assert any(e["event_type"] == "gate_failed" for e in events)
    assert any(e["event_type"] == "gate_evaluation_complete" for e in events)


# ---------------------------------------------------------------------------
# Test 18 — failure_summary() formats human-readable output
# ---------------------------------------------------------------------------


def test_p1_5b_failure_summary_formatting(tmp_path):
    """failure_summary() produces operator-readable output naming each
    failed gate, its overridability, and the audit log path."""
    from release_safety.gates import evaluate_cleanup_gates, GateMode

    flutter_repo, dist_dir = _setup_misaligned_environment(
        tmp_path,
        bundled_hashes=[_h(0)], dist_hashes=[_h(1)],
        bundled_version="vA", dist_version="vB",
    )
    audit = _make_test_audit_log(tmp_path)
    result = evaluate_cleanup_gates(
        flutter_repo, dist_dir,
        candidate_blobs=[], storage_total=2,
        mode=GateMode.EXECUTE,
        audit_log=audit,
        lock_path=tmp_path / ".release.lock",
    )

    summary = result.failure_summary()

    assert "REJECTED" in summary
    assert "bundle_alignment" in summary
    assert "overridable" in summary.lower()
    assert str(audit.path) in summary


# ---------------------------------------------------------------------------
# Test 19 — THE 2026-05-12 FULL-STACK REGRESSION
# ---------------------------------------------------------------------------


def test_p1_5b_2026_05_12_full_stack_regression(tmp_path):
    """The complete failure-mode proof.

    Replays the 2026-05-12 scenario:
      - bundled-on-main: v2026.05.11.bundled with hashes [A..J] (10)
      - dist:            v2026.05.12.dist    with hashes [F..O] (10)
      - cleanup proposes to delete: bundled-only hashes [A..E] (the
        "orphans" per dist-only logic — exactly what the May 12 cleanup
        nuked)
      - storage_total: 15 (the union)

    Run gates in EXECUTE mode. Required outcome:
      1. result.passed = False
      2. failures includes "bundle_alignment" (versions differ)
      3. would_delete_count = 0 — even though the caller proposed deleting
         A..E, those are protected by P1.4's bundled∪dist union, so they
         are filtered OUT of the actual deletion candidates
      4. The audit log captures every gate decision

    If THIS test fails, the failure mode can recur. P1 is not safe to ship.
    """
    from release_safety.gates import evaluate_cleanup_gates, GateMode
    from release_safety.audit_log import read_audit_log

    bundled_hashes = [_h(i) for i in range(0, 10)]   # A..J
    dist_hashes    = [_h(i) for i in range(5, 15)]   # F..O (5 overlap)
    bundled_only   = [_h(i) for i in range(0, 5)]    # A..E (the May 12 victims)

    flutter_repo, dist_dir = _setup_misaligned_environment(
        tmp_path,
        bundled_hashes=bundled_hashes,
        dist_hashes=dist_hashes,
        bundled_version="2026.05.11.bundled",
        dist_version="2026.05.12.dist",
    )

    audit = _make_test_audit_log(tmp_path)
    lock_path = tmp_path / ".release.lock"

    result = evaluate_cleanup_gates(
        flutter_repo, dist_dir,
        candidate_blobs=bundled_only,             # what cleanup proposed to delete
        storage_total=15,                          # the union
        mode=GateMode.EXECUTE,
        audit_log=audit,
        lock_path=lock_path,
    )

    # === HEADLINE ASSERTIONS ===

    # 1. Run is REJECTED — cleanup must not proceed.
    assert result.passed is False, (
        "P1.5b REGRESSION — gates allowed cleanup under May 12 conditions. "
        "The failure mode can recur."
    )

    # 2. Bundle alignment is named in the failures.
    failure_names = [f.gate_name for f in result.failures]
    assert "bundle_alignment" in failure_names, (
        "Bundle-alignment gate did not fire on May 12 conditions; "
        "Gate 1 (HR-13) is not enforcing committed-state validation."
    )

    # 3. EVEN IF Gate 1 had been overridden, no destructive action would
    #    be queued — bundled-only hashes A..E are protected by P1.4's
    #    bundled∪dist union, so the candidate→deletion filter excludes them.
    assert result.would_delete_count == 0, (
        f"P1.4 REGRESSION via P1.5b — would_delete_count={result.would_delete_count}; "
        f"bundled-only hashes are NOT filtered out of deletion candidates. "
        f"Cleanup would still nuke them. The protected-set computation is broken."
    )
    assert result.deletion_candidates == frozenset(), (
        "deletion_candidates is non-empty under May 12 conditions — "
        "the bundled-only hashes were not protected."
    )

    # 4. Protected set carries the full union (bundled∪dist).
    assert result.protected_set is not None
    assert not result.protected_set.degenerate
    assert result.protected_set.union_count == 15
    for h in bundled_only:
        assert h in result.protected_set.protected, (
            f"bundled-only hash {h[:16]}... is NOT in the protected set."
        )

    # 5. Audit log captures the rejection — operator-grade evidence.
    events = read_audit_log(audit.path)
    failed_events = [e for e in events if e["event_type"] == "gate_failed"]
    assert any(e.get("gate_name") == "bundle_alignment" for e in failed_events)

    # 6. The lock file was acquired AND released — no stale lock left.
    assert not lock_path.exists()
