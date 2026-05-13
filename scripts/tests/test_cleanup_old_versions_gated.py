"""Tests for the P1.6 production wire-in: cleanup_old_versions.py +
sync_to_supabase.py integration with the release-safety gate stack.

Per ADR-0001 P1.6 sign-off:
  - Real Flutter repo + real dist directory fixtures (HR-13 trust model
    requires committed-state validation; mocking that would defeat the
    test).
  - Mock Supabase storage at the module-function level — list/delete
    are stubbed against an in-memory ``set`` so no network/real Supabase
    is touched.
  - End-to-end 2026-05-12 regression through the production cleanup
    entry point: bundled-only hashes must NOT be deleted.
  - CLI flag validation: --cleanup-orphan-blobs --execute refuses to
    proceed without --flutter-repo and --dist-dir.
  - sync_to_supabase passthrough: gate flags appear in the cleanup
    invocation only when --allow-destructive-orphan-cleanup is set.
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
# Real-Flutter-repo fixture helpers (mirror P1.4 / P1.5b for self-containment)
# ---------------------------------------------------------------------------


def _h(idx: int) -> str:
    """Deterministic 64-char lowercase hex hash."""
    return f"{idx:064x}"


def _git_init(repo_path: Path) -> None:
    subprocess.run(["git", "init", "-b", "main"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@p1-6.local"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "P1.6 Test"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=repo_path, check=True, capture_output=True)


def _make_catalog_db(path: Path, hashes: list) -> str:
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(str(path))
    try:
        conn.execute(
            "CREATE TABLE products_core ("
            "  dsld_id TEXT PRIMARY KEY,"
            "  detail_blob_sha256 TEXT)"
        )
        for i, h in enumerate(hashes):
            conn.execute("INSERT INTO products_core VALUES (?, ?)", (str(1000 + i), h))
        conn.commit()
    finally:
        conn.close()
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(64 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest()


def _commit_bundle(repo: Path, hashes: list, db_version: str) -> None:
    assets_db = repo / "assets" / "db"
    assets_db.mkdir(parents=True, exist_ok=True)
    catalog = assets_db / "pharmaguide_core.db"
    checksum = _make_catalog_db(catalog, hashes)
    (assets_db / "export_manifest.json").write_text(json.dumps({
        "db_version": db_version,
        "checksum_sha256": checksum,
        "product_count": len(hashes),
    }))
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", f"bundle {db_version}"],
                   cwd=repo, check=True, capture_output=True)


def _make_dist(dist_dir: Path, hashes: list, db_version: str) -> None:
    dist_dir.mkdir(parents=True, exist_ok=True)
    detail_index = {}
    for i, h in enumerate(hashes):
        detail_index[str(1000 + i)] = {
            "blob_sha256": h,
            "storage_path": f"shared/details/sha256/{h[:2]}/{h}.json",
            "blob_version": 1,
        }
    (dist_dir / "detail_index.json").write_text(json.dumps(detail_index))
    (dist_dir / "export_manifest.json").write_text(json.dumps({
        "db_version": db_version,
        "checksum_sha256": "irrelevant_for_p1_6",
    }))


# ---------------------------------------------------------------------------
# In-memory Supabase storage mock
# ---------------------------------------------------------------------------


def _install_mock_storage(monkeypatch, storage_hashes: set) -> list:
    """Patch cleanup_old_versions' list_all_blob_shard_dirs /
    list_blobs_in_shard / delete_storage_path to operate on an in-memory
    ``storage_hashes`` set.

    Returns the ``removed`` list which the test can inspect to confirm
    which paths were deleted.
    """
    import cleanup_old_versions as cov

    removed: list = []

    def mock_list_shards(client):
        return sorted({h[:2] for h in storage_hashes})

    def mock_list_blobs_in_shard(client, shard):
        return [
            f"shared/details/sha256/{shard}/{h}.json"
            for h in sorted(storage_hashes) if h[:2] == shard
        ]

    def mock_delete(client, path):
        leaf = path.rsplit("/", 1)[-1]
        h = leaf[:-5] if leaf.endswith(".json") else leaf
        if h in storage_hashes:
            storage_hashes.discard(h)
            removed.append(path)
            return True, None
        return False, "not found"

    monkeypatch.setattr(cov, "list_all_blob_shard_dirs", mock_list_shards)
    monkeypatch.setattr(cov, "list_blobs_in_shard", mock_list_blobs_in_shard)
    monkeypatch.setattr(cov, "delete_storage_path", mock_delete)

    return removed


# ===========================================================================
# Test 1 — happy path: gates pass, only non-protected blobs deleted
# ===========================================================================


def test_p1_6_gated_cleanup_passing_gates_deletes_only_unprotected(tmp_path, monkeypatch):
    """Aligned bundle + dist (same version, same hashes). Storage has the
    union plus a few extra orphan hashes that aren't in either side.
    Gates pass → only the extras get deleted; the protected union stays.

    Storage is sized large enough that the few orphaned deletions stay
    under the 5% blast-radius threshold (Gate 2 default). A more
    realistic test of blast-radius override lives in P1.5b's gates
    suite; this test focuses on the wire-in glue."""
    from cleanup_old_versions import cleanup_orphan_blobs_with_gates
    from release_safety import AuditLog

    # 100 protected blobs + 3 orphans → 3/103 ≈ 2.9% (under 5% threshold).
    bundled_and_dist = [_h(i) for i in range(100)]               # 0..99
    extra_orphans    = [_h(i) for i in range(1000, 1003)]        # 1000..1002

    flutter_repo = tmp_path / "flutter"
    flutter_repo.mkdir()
    _git_init(flutter_repo)
    _commit_bundle(flutter_repo, bundled_and_dist, db_version="vMATCHED")

    dist_dir = tmp_path / "dist"
    _make_dist(dist_dir, bundled_and_dist, db_version="vMATCHED")

    # Storage = union + extras
    storage_hashes = set(bundled_and_dist) | set(extra_orphans)
    removed = _install_mock_storage(monkeypatch, storage_hashes)

    audit = AuditLog(tmp_path / "audit.jsonl", release_id="t1")
    deleted, failed = cleanup_orphan_blobs_with_gates(
        client=None,
        current_version="vMATCHED",
        flutter_repo_path=flutter_repo,
        dist_dir=dist_dir,
        audit_log=audit,
        lock_path=tmp_path / ".release.lock",
    )

    assert deleted == 3
    assert failed == 0

    # Only the extras were deleted; every protected hash survived.
    deleted_hashes = {p.rsplit("/", 1)[-1][:-5] for p in removed}
    assert deleted_hashes == set(extra_orphans)
    for h in bundled_and_dist:
        assert h in storage_hashes, f"protected hash {h[:8]}... was deleted"


# ===========================================================================
# Test 2 — failing gates: returns (0, 0), NO deletions
# ===========================================================================


def test_p1_6_gated_cleanup_failing_gates_deletes_nothing(tmp_path, monkeypatch):
    """Misaligned bundle vs dist. Gate 1 fails → cleanup must return (0, 0)
    and the storage state must be UNCHANGED."""
    from cleanup_old_versions import cleanup_orphan_blobs_with_gates
    from release_safety import AuditLog

    bundled = [_h(i) for i in range(5)]
    dist    = [_h(i) for i in range(5)]

    flutter_repo = tmp_path / "flutter"
    flutter_repo.mkdir()
    _git_init(flutter_repo)
    _commit_bundle(flutter_repo, bundled, db_version="vBUNDLED_OLD")

    dist_dir = tmp_path / "dist"
    _make_dist(dist_dir, dist, db_version="vDIST_NEW")

    storage_hashes = set(bundled) | {_h(i) for i in range(100, 105)}    # 5 extras
    storage_snapshot = set(storage_hashes)
    removed = _install_mock_storage(monkeypatch, storage_hashes)

    audit = AuditLog(tmp_path / "audit.jsonl", release_id="t2")
    deleted, failed = cleanup_orphan_blobs_with_gates(
        client=None,
        current_version="vDIST_NEW",
        flutter_repo_path=flutter_repo,
        dist_dir=dist_dir,
        audit_log=audit,
        lock_path=tmp_path / ".release.lock",
    )

    assert deleted == 0
    assert failed == 0
    assert removed == [], "cleanup deleted blobs despite gate failure"
    assert storage_hashes == storage_snapshot, "storage state was modified"


# ===========================================================================
# Test 3 — THE 2026-05-12 END-TO-END REGRESSION (production wire-in)
# ===========================================================================


def test_p1_6_2026_05_12_end_to_end_regression(tmp_path, monkeypatch):
    """The complete production-path proof.

    Replays the May 12 conditions through the actual cleanup function
    that release_full.sh / batch_run_all_datasets.sh would invoke:

      - bundled main: v2026.05.11.bundled with hashes [A..J]
      - dist:         v2026.05.12.dist    with hashes [F..O]
      - storage has the union [A..O] (the realistic state right after
        dist's blobs got uploaded but before cleanup)
      - cleanup is asked to remove orphans

    Without P1.6 (today's broken cleanup): A..E (bundled-only) would be
    deleted because dist-only protection treats them as orphans.

    With P1.6: gate fails (bundle misalignment) → deleted=0, failed=0,
    A..E remain in storage.

    If THIS test fails, P1.6 has not closed the production failure mode.
    """
    from cleanup_old_versions import cleanup_orphan_blobs_with_gates
    from release_safety import AuditLog, read_audit_log

    bundled = [_h(i) for i in range(0, 10)]                # A..J
    dist    = [_h(i) for i in range(5, 15)]                # F..O (overlap with bundled F-J)
    bundled_only_victims = [_h(i) for i in range(0, 5)]    # A..E

    flutter_repo = tmp_path / "flutter"
    flutter_repo.mkdir()
    _git_init(flutter_repo)
    _commit_bundle(flutter_repo, bundled, db_version="2026.05.11.bundled")

    dist_dir = tmp_path / "dist"
    _make_dist(dist_dir, dist, db_version="2026.05.12.dist")

    # Storage state matches the May 12 reality: contains the union of
    # both versions' blobs (15 unique hashes).
    storage_hashes = set(bundled) | set(dist)
    storage_snapshot = set(storage_hashes)
    removed = _install_mock_storage(monkeypatch, storage_hashes)

    audit = AuditLog(tmp_path / "audit.jsonl", release_id="may_12_regression")
    lock_path = tmp_path / ".release.lock"

    deleted, failed = cleanup_orphan_blobs_with_gates(
        client=None,
        current_version="2026.05.12.dist",
        flutter_repo_path=flutter_repo,
        dist_dir=dist_dir,
        audit_log=audit,
        lock_path=lock_path,
    )

    # === HEADLINE ASSERTIONS ===

    # 1. Zero destructive action on the May 12 conditions.
    assert deleted == 0, (
        f"P1.6 REGRESSION — production cleanup deleted {deleted} blobs "
        "under May 12 conditions. The failure mode CAN STILL RECUR through "
        "the production entry point."
    )
    assert failed == 0
    assert removed == [], (
        f"P1.6 REGRESSION — {len(removed)} delete calls were made: {removed[:5]}..."
    )

    # 2. Storage state UNCHANGED — every blob still present.
    assert storage_hashes == storage_snapshot

    # 3. Specifically the bundled-only victims (A..E) survived.
    for h in bundled_only_victims:
        assert h in storage_hashes, (
            f"P1.6 REGRESSION — bundled-only hash {h[:16]}... was deleted. "
            "The exact 2026-05-12 victim class is unprotected."
        )

    # 4. Lock acquired AND released cleanly (no stale lock).
    assert not lock_path.exists()

    # 5. Audit log captures the rejection — operator-grade evidence.
    events = read_audit_log(audit.path)
    failed_events = [e for e in events if e["event_type"] == "gate_failed"]
    assert any(e.get("gate_name") == "bundle_alignment" for e in failed_events), (
        "Audit log does not record bundle_alignment gate failure"
    )


# ===========================================================================
# Test 4 — unparseable dist index returns (0, 0) without partial deletion
# ===========================================================================


def test_p1_6_dist_index_unparseable_returns_zero(tmp_path, monkeypatch):
    """If validate_detail_index raises during pre-gate setup, cleanup
    must return (0, 0). The fail-closed wrapper inside the function
    catches the exception."""
    from cleanup_old_versions import cleanup_orphan_blobs_with_gates
    from release_safety import AuditLog

    flutter_repo = tmp_path / "flutter"
    flutter_repo.mkdir()
    _git_init(flutter_repo)
    _commit_bundle(flutter_repo, [_h(0)], db_version="v1")

    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    (dist_dir / "detail_index.json").write_text("THIS IS NOT JSON {{")

    storage_hashes = {_h(i) for i in range(10)}
    snapshot = set(storage_hashes)
    removed = _install_mock_storage(monkeypatch, storage_hashes)

    audit = AuditLog(tmp_path / "audit.jsonl", release_id="t4")
    deleted, failed = cleanup_orphan_blobs_with_gates(
        client=None,
        current_version="v1",
        flutter_repo_path=flutter_repo,
        dist_dir=dist_dir,
        audit_log=audit,
        lock_path=tmp_path / ".release.lock",
    )

    assert deleted == 0
    assert failed == 0
    assert removed == []
    assert storage_hashes == snapshot


# ===========================================================================
# Test 5 — main() exits with error if --flutter-repo missing
# ===========================================================================


def test_p1_6_cli_missing_flutter_repo_exits_with_error(monkeypatch, capsys):
    """``cleanup_old_versions.main(['--cleanup-orphan-blobs', '--execute'])``
    without --flutter-repo must exit non-zero with a clear remediation
    message. Fail-closed at CLI parse / validation time."""
    import cleanup_old_versions as cov

    # Stub out Supabase client + version fetch so we get to the validation
    monkeypatch.setattr(cov, "get_supabase_client", lambda: object())
    monkeypatch.setattr(cov, "fetch_all_versions", lambda client: [
        {"db_version": "vTEST", "created_at": "2026-05-12T00:00:00Z", "is_current": True},
        {"db_version": "vOLD",  "created_at": "2026-05-11T00:00:00Z", "is_current": False},
    ])
    # Stub the version-directory cleanup so it doesn't try real I/O before
    # we reach the orphan-blob block.
    monkeypatch.setattr(cov, "delete_version_directory", lambda c, v, dr: (0, 0))
    monkeypatch.setattr(cov, "delete_manifest_row", lambda c, v, dr: (True, None))

    with pytest.raises(SystemExit) as excinfo:
        cov.main([
            "--execute",
            "--cleanup-orphan-blobs",
            "--keep", "1",
            # NB: --flutter-repo and --dist-dir intentionally omitted
        ])

    assert excinfo.value.code == 2
    captured = capsys.readouterr()
    assert "--flutter-repo" in captured.out
    assert "--dist-dir" in captured.out
    assert "Refusing destructive cleanup" in captured.out


# ===========================================================================
# Test 6 — main() exits with error if --dist-dir missing
# ===========================================================================


def test_p1_6_cli_missing_dist_dir_exits_with_error(tmp_path, monkeypatch, capsys):
    """Same fail-closed behavior for missing --dist-dir."""
    import cleanup_old_versions as cov

    monkeypatch.setattr(cov, "get_supabase_client", lambda: object())
    monkeypatch.setattr(cov, "fetch_all_versions", lambda client: [
        {"db_version": "vTEST", "created_at": "2026-05-12T00:00:00Z", "is_current": True},
        {"db_version": "vOLD",  "created_at": "2026-05-11T00:00:00Z", "is_current": False},
    ])
    monkeypatch.setattr(cov, "delete_version_directory", lambda c, v, dr: (0, 0))
    monkeypatch.setattr(cov, "delete_manifest_row", lambda c, v, dr: (True, None))

    with pytest.raises(SystemExit) as excinfo:
        cov.main([
            "--execute",
            "--cleanup-orphan-blobs",
            "--keep", "1",
            "--flutter-repo", str(tmp_path / "flutter"),
            # --dist-dir intentionally omitted
        ])

    assert excinfo.value.code == 2
    assert "--dist-dir" in capsys.readouterr().out


# ===========================================================================
# Test 7 — unexpected exception in gated path returns (0, 0) at main() level
# ===========================================================================


def test_p1_6_unexpected_exception_in_gated_path_blocks_deletion(tmp_path, monkeypatch, capsys):
    """If cleanup_orphan_blobs_with_gates raises unexpectedly, main()'s
    try/except catches it and the script reports zero deletions instead
    of crashing mid-cleanup. Fail-closed per ADR-0001 P1.6."""
    import cleanup_old_versions as cov

    # Two rows so old_rows is non-empty and main() reaches the orphan-
    # blob branch (with one row + keep=1, the script exits early with
    # "Nothing to delete" before reaching cleanup_orphan_blobs).
    monkeypatch.setattr(cov, "get_supabase_client", lambda: object())
    monkeypatch.setattr(cov, "fetch_all_versions", lambda client: [
        {"db_version": "vTEST", "created_at": "2026-05-12T00:00:00Z", "is_current": True},
        {"db_version": "vOLD",  "created_at": "2026-05-11T00:00:00Z", "is_current": False},
    ])
    monkeypatch.setattr(cov, "delete_version_directory", lambda c, v, dr: (0, 0))
    monkeypatch.setattr(cov, "delete_manifest_row", lambda c, v, dr: (True, None))

    # Force the gated function to blow up
    def boom(*args, **kwargs):
        raise RuntimeError("simulated gate machinery explosion")
    monkeypatch.setattr(cov, "cleanup_orphan_blobs_with_gates", boom)

    # Should NOT raise; should NOT exit with non-zero (this is a recoverable
    # error class — the script reports the failure and continues to summary).
    cov.main([
        "--execute",
        "--cleanup-orphan-blobs",
        "--keep", "1",
        "--flutter-repo", str(tmp_path / "flutter"),
        "--dist-dir", str(tmp_path / "dist"),
    ])

    out = capsys.readouterr().out
    assert "Unexpected error" in out
    assert "Refusing destructive cleanup" in out
    assert "simulated gate machinery explosion" in out


# ===========================================================================
# Test 8 — sync_to_supabase passthrough WHEN opted in
# ===========================================================================


def test_p1_6_sync_to_supabase_passes_gate_flags_through_when_opted_in():
    """When --allow-destructive-orphan-cleanup is True, _build_cleanup_args
    forwards --flutter-repo, --dist-dir, --branch, and override flags."""
    from sync_to_supabase import _build_cleanup_args

    argv = _build_cleanup_args(
        cleanup_keep=2,
        allow_destructive_orphan_cleanup=True,
        flutter_repo="/path/to/Flutter app",
        dist_dir="/path/to/dist",
        branch="develop",
        bundle_mismatch_reason="hotfix; bundle commit deferred",
        expected_count=42,
    )

    assert "--cleanup-orphan-blobs" in argv
    assert "--flutter-repo" in argv
    assert "/path/to/Flutter app" in argv
    assert "--dist-dir" in argv
    assert "/path/to/dist" in argv
    assert "--branch" in argv
    assert "develop" in argv
    assert "--override-bundle-mismatch" in argv
    assert "hotfix; bundle commit deferred" in argv
    assert "--expected-count" in argv
    assert "42" in argv


# ===========================================================================
# Test 9 — sync_to_supabase OMITS gate flags when not opted in
# ===========================================================================


def test_p1_6_sync_to_supabase_omits_gate_flags_when_not_opted_in():
    """When --allow-destructive-orphan-cleanup is False (the default),
    the gate-passthrough flags MUST NOT appear in the cleanup argv —
    the destructive path itself is suppressed, so passing gate flags
    would be confusing."""
    from sync_to_supabase import _build_cleanup_args

    argv = _build_cleanup_args(
        cleanup_keep=2,
        allow_destructive_orphan_cleanup=False,
        flutter_repo="/path/to/Flutter app",   # provided but should be ignored
        dist_dir="/path/to/dist",
        branch="main",
        bundle_mismatch_reason="should not appear",
        expected_count=99,
    )

    assert "--cleanup-orphan-blobs" not in argv
    assert "--flutter-repo" not in argv
    assert "--dist-dir" not in argv
    assert "--override-bundle-mismatch" not in argv
    assert "--expected-count" not in argv


# ===========================================================================
# Test 10 — sync_to_supabase passthrough OMITS optional flags when None
# ===========================================================================


def test_p1_6_sync_to_supabase_omits_optional_overrides_when_none():
    """When opted in but no override values are supplied, the override
    flags are omitted (cleanup will use its own defaults)."""
    from sync_to_supabase import _build_cleanup_args

    argv = _build_cleanup_args(
        cleanup_keep=2,
        allow_destructive_orphan_cleanup=True,
        flutter_repo="/repo",
        dist_dir="/dist",
        # branch defaults to "main" — should NOT be passed
        bundle_mismatch_reason=None,
        expected_count=None,
    )

    # Required flags present
    assert "--cleanup-orphan-blobs" in argv
    assert "--flutter-repo" in argv
    assert "--dist-dir" in argv
    # main is the default; passing it is redundant
    assert "--branch" not in argv
    # No overrides supplied
    assert "--override-bundle-mismatch" not in argv
    assert "--expected-count" not in argv
