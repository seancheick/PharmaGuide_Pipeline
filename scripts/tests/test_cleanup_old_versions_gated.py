"""Tests for the production wire-in: cleanup_old_versions.py +
sync_to_supabase.py integration with the release-safety stack
(ADR-0001 P1.6 + P2.2).

P1.6 added the gate evaluation in front of the destructive cleanup.
P2.2 changed the destructive step itself: orphan blobs are now MOVED
to quarantine (recoverable for 30 days) instead of being hard-deleted.

Test infrastructure:
  - Real Flutter repo + real dist directory fixtures (HR-13 trust
    model requires committed-state validation).
  - Real-ish in-memory Supabase storage mock (MockSupabaseClient with
    copy/remove/list support). The mock is passed AS the client to
    cleanup_orphan_blobs_with_gates; no module-level monkeypatching of
    storage operations is needed any more.
  - End-to-end 2026-05-12 regression through the production cleanup
    entry point.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Set
import pytest

_scripts_dir = os.path.join(os.path.dirname(__file__), "..")
if _scripts_dir not in sys.path:
    sys.path.insert(0, os.path.abspath(_scripts_dir))


# ---------------------------------------------------------------------------
# Real-Flutter-repo fixture helpers (mirror P1.4 / P1.5b)
# ---------------------------------------------------------------------------


def _h(idx: int) -> str:
    """Deterministic 64-char lowercase hex hash."""
    return f"{idx:064x}"


def _git_init(repo_path: Path) -> None:
    subprocess.run(["git", "init", "-b", "main"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@p2-2.local"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "P2.2 Test"], cwd=repo_path, check=True, capture_output=True)
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
        "checksum_sha256": "irrelevant",
    }))


# ---------------------------------------------------------------------------
# In-memory Supabase storage mock (real-ish — supports copy/remove/list)
# ---------------------------------------------------------------------------


class MockBucket:
    def __init__(self):
        self.objects: dict = {}
        self.fail_copy_to: Set[str] = set()
        self.fail_remove: Set[str] = set()

    def copy(self, src: str, dst: str):
        if dst in self.fail_copy_to:
            raise RuntimeError(f"injected COPY failure (dst={dst})")
        if src not in self.objects:
            raise RuntimeError(f"source not found: {src}")
        self.objects[dst] = self.objects[src]
        return {"ok": True}

    def remove(self, paths):
        for p in paths:
            if p in self.fail_remove:
                raise RuntimeError(f"injected DELETE failure (path={p})")
            self.objects.pop(p, None)
        return [{"name": p} for p in paths]

    def list(self, path: str, options=None):
        prefix = path.rstrip("/") + "/" if path else ""
        results = []
        seen_dirs: Set[str] = set()
        for full in self.objects:
            if not full.startswith(prefix):
                continue
            rest = full[len(prefix):]
            if "/" not in rest:
                results.append({"name": rest})
            else:
                first = rest.split("/", 1)[0]
                if first not in seen_dirs:
                    seen_dirs.add(first)
                    results.append({"name": first})
        return results

    def download(self, path: str) -> bytes:
        """Match supabase-py's storage download contract. Used by P3.5
        registry side to fetch v{ver}/detail_index.json for protected
        set computation."""
        if path not in self.objects:
            raise RuntimeError(f"not found: {path}")
        return self.objects[path]


class MockStorageNamespace:
    def __init__(self):
        self.buckets: dict = {}

    def from_(self, bucket: str) -> MockBucket:
        return self.buckets.setdefault(bucket, MockBucket())


class _MockTableResponse:
    def __init__(self, data):
        self.data = data


class MockTable:
    """Minimal Supabase table double for the registry select() pattern
    used by P3.5 protected_blobs._fetch_registry_blob_hashes."""
    def __init__(self, name: str, store: list):
        self._name = name
        self._store = store
        self._select_cols = None
        self._filters: list = []

    def select(self, cols: str = "*") -> "MockTable":
        new = MockTable(self._name, self._store)
        new._select_cols = None if cols == "*" else [c.strip() for c in cols.split(",")]
        return new

    def eq(self, col, val) -> "MockTable":
        self._filters.append((col, val))
        return self

    def execute(self) -> _MockTableResponse:
        matched = [r for r in self._store
                   if all(r.get(c) == v for c, v in self._filters)]
        if self._select_cols is None:
            return _MockTableResponse([dict(r) for r in matched])
        return _MockTableResponse([
            {c: r.get(c) for c in self._select_cols} for r in matched
        ])


class MockSupabaseClient:
    def __init__(self):
        self.storage = MockStorageNamespace()
        self._tables: dict = {}

    def table(self, name: str) -> MockTable:
        store = self._tables.setdefault(name, [])
        return MockTable(name, store)

    def seed_catalog_releases(self, rows: list) -> "MockSupabaseClient":
        store = self._tables.setdefault("catalog_releases", [])
        store.extend(dict(r) for r in rows)
        return self


def _make_mock_client_with_active_storage(storage_hashes):
    """Build a MockSupabaseClient pre-populated with active-path blobs.

    Returns (client, bucket). Tests inspect bucket.objects to verify
    quarantine moves and remaining storage state.
    """
    client = MockSupabaseClient()
    bucket = client.storage.from_("pharmaguide")
    for h in storage_hashes:
        bucket.objects[f"shared/details/sha256/{h[:2]}/{h}.json"] = b"blob_data_" + h[:8].encode()
    return client, bucket


def _active_path(blob_hash: str) -> str:
    return f"shared/details/sha256/{blob_hash[:2]}/{blob_hash}.json"


def _quarantine_path(date_str: str, blob_hash: str) -> str:
    return f"shared/quarantine/{date_str}/{blob_hash[:2]}/{blob_hash}.json"


# ===========================================================================
# Test 1 — happy path: gates pass, only non-protected blobs MOVED to quarantine
# ===========================================================================


def test_p2_2_gated_cleanup_passing_gates_quarantines_only_unprotected(tmp_path):
    """Aligned bundle + dist (same version, same hashes). Storage has the
    union plus a few extra orphan hashes that aren't in either side.
    Gates pass → only the extras are MOVED to quarantine; the protected
    union stays in active storage.

    Storage is sized large enough (100 protected + 3 orphans = 2.9%)
    that the orphan deletions stay under the 5% blast-radius threshold.
    """
    from cleanup_old_versions import cleanup_orphan_blobs_with_gates
    from release_safety import AuditLog

    bundled_and_dist = [_h(i) for i in range(100)]              # 0..99
    extra_orphans    = [_h(i) for i in range(1000, 1003)]       # 1000..1002

    flutter_repo = tmp_path / "flutter"
    flutter_repo.mkdir()
    _git_init(flutter_repo)
    _commit_bundle(flutter_repo, bundled_and_dist, db_version="vMATCHED")

    dist_dir = tmp_path / "dist"
    _make_dist(dist_dir, bundled_and_dist, db_version="vMATCHED")

    storage_hashes = set(bundled_and_dist) | set(extra_orphans)
    client, bucket = _make_mock_client_with_active_storage(storage_hashes)

    audit = AuditLog(tmp_path / "audit.jsonl", release_id="t1")
    quarantined, failed = cleanup_orphan_blobs_with_gates(
        client=client,
        current_version="vMATCHED",
        flutter_repo_path=flutter_repo,
        dist_dir=dist_dir,
        audit_log=audit,
        lock_path=tmp_path / ".release.lock",
        run_date="2026-05-12",
    )

    assert quarantined == 3
    assert failed == 0

    # Each extra orphan was MOVED, not deleted: removed from active path
    # AND now present at the quarantine path under run_date.
    for orphan in extra_orphans:
        assert _active_path(orphan) not in bucket.objects, \
            f"orphan {orphan[:8]}... is still in active storage (not moved)"
        assert _quarantine_path("2026-05-12", orphan) in bucket.objects, \
            f"orphan {orphan[:8]}... is not in quarantine"

    # Every protected blob is STILL in active storage.
    for h in bundled_and_dist:
        assert _active_path(h) in bucket.objects, \
            f"protected hash {h[:8]}... was moved/deleted"


# ===========================================================================
# Test 2 — failing gates: returns (0, 0), NO quarantine activity
# ===========================================================================


def test_p2_2_gated_cleanup_failing_gates_quarantines_nothing(tmp_path):
    """Misaligned bundle vs dist. Gate 1 fails → no quarantine activity
    AND no deletions. Storage state UNCHANGED."""
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

    storage_hashes = set(bundled) | {_h(i) for i in range(100, 105)}
    client, bucket = _make_mock_client_with_active_storage(storage_hashes)
    snapshot = dict(bucket.objects)

    audit = AuditLog(tmp_path / "audit.jsonl", release_id="t2")
    quarantined, failed = cleanup_orphan_blobs_with_gates(
        client=client,
        current_version="vDIST_NEW",
        flutter_repo_path=flutter_repo,
        dist_dir=dist_dir,
        audit_log=audit,
        lock_path=tmp_path / ".release.lock",
        run_date="2026-05-12",
    )

    assert quarantined == 0
    assert failed == 0
    # No quarantine paths created.
    assert not any(p.startswith("shared/quarantine/") for p in bucket.objects)
    # Active storage UNCHANGED — every blob still exactly where it was.
    assert bucket.objects == snapshot


# ===========================================================================
# Test 3 — THE 2026-05-12 END-TO-END REGRESSION (production wire-in + P2.2)
# ===========================================================================


def test_p2_2_2026_05_12_end_to_end_regression(tmp_path):
    """The complete production-path proof.

    Replays the May 12 conditions through the production cleanup function:
      - bundled main: v2026.05.11.bundled with hashes [A..J]
      - dist:         v2026.05.12.dist    with hashes [F..O]
      - storage has the union [A..O]
      - cleanup is asked to remove orphans

    With P1.6 + P2.2: gate fails (bundle misalignment) →
      - quarantined = 0, failed = 0
      - NO blobs moved to quarantine (degenerate state)
      - NO blobs deleted from active storage
      - bundled-only victims [A..E] remain in active storage

    If THIS test fails, P1.6 + P2.2 have not closed the production
    failure mode.
    """
    from cleanup_old_versions import cleanup_orphan_blobs_with_gates
    from release_safety import AuditLog, read_audit_log

    bundled = [_h(i) for i in range(0, 10)]                 # A..J
    dist    = [_h(i) for i in range(5, 15)]                 # F..O
    bundled_only_victims = [_h(i) for i in range(0, 5)]     # A..E

    flutter_repo = tmp_path / "flutter"
    flutter_repo.mkdir()
    _git_init(flutter_repo)
    _commit_bundle(flutter_repo, bundled, db_version="2026.05.11.bundled")

    dist_dir = tmp_path / "dist"
    _make_dist(dist_dir, dist, db_version="2026.05.12.dist")

    storage_hashes = set(bundled) | set(dist)
    client, bucket = _make_mock_client_with_active_storage(storage_hashes)
    snapshot = dict(bucket.objects)

    audit = AuditLog(tmp_path / "audit.jsonl", release_id="may_12_regression")
    lock_path = tmp_path / ".release.lock"

    quarantined, failed = cleanup_orphan_blobs_with_gates(
        client=client,
        current_version="2026.05.12.dist",
        flutter_repo_path=flutter_repo,
        dist_dir=dist_dir,
        audit_log=audit,
        lock_path=lock_path,
        run_date="2026-05-12",
    )

    # === HEADLINE ASSERTIONS ===

    # 1. Zero destructive AND zero quarantine action.
    assert quarantined == 0, (
        f"P2.2 REGRESSION — production cleanup quarantined {quarantined} "
        "blobs under May 12 conditions. Gates failed to reject the run."
    )
    assert failed == 0

    # 2. NO quarantine paths exist at all.
    quarantine_keys = [p for p in bucket.objects if p.startswith("shared/quarantine/")]
    assert quarantine_keys == [], (
        f"P2.2 REGRESSION — quarantine activity occurred despite gate "
        f"rejection: {quarantine_keys[:5]}"
    )

    # 3. Active storage UNCHANGED — every blob still exactly where it was.
    assert bucket.objects == snapshot

    # 4. Bundled-only victims (A..E) survived in active storage.
    for h in bundled_only_victims:
        assert _active_path(h) in bucket.objects, (
            f"P2.2 REGRESSION — bundled-only hash {h[:16]}... is missing "
            "from active storage. The May 12 victim class is unprotected."
        )

    # 5. Lock cleanly acquired AND released.
    assert not lock_path.exists()

    # 6. Audit log captures the rejection.
    events = read_audit_log(audit.path)
    failed_events = [e for e in events if e["event_type"] == "gate_failed"]
    assert any(e.get("gate_name") == "bundle_alignment" for e in failed_events)


# ===========================================================================
# Test 4 — unparseable dist index returns (0, 0); no quarantine activity
# ===========================================================================


def test_p2_2_dist_index_unparseable_returns_zero(tmp_path):
    """If validate_detail_index raises during pre-gate setup, cleanup
    must return (0, 0). No quarantine activity. Storage UNCHANGED."""
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
    client, bucket = _make_mock_client_with_active_storage(storage_hashes)
    snapshot = dict(bucket.objects)

    audit = AuditLog(tmp_path / "audit.jsonl", release_id="t4")
    quarantined, failed = cleanup_orphan_blobs_with_gates(
        client=client,
        current_version="v1",
        flutter_repo_path=flutter_repo,
        dist_dir=dist_dir,
        audit_log=audit,
        lock_path=tmp_path / ".release.lock",
        run_date="2026-05-12",
    )

    assert quarantined == 0
    assert failed == 0
    assert bucket.objects == snapshot
    assert not any(p.startswith("shared/quarantine/") for p in bucket.objects)


# ===========================================================================
# Test 5 — main() exits with error if --flutter-repo missing
# ===========================================================================


def test_p1_6_cli_missing_flutter_repo_exits_with_error(monkeypatch, capsys):
    """``cleanup_old_versions.main(['--cleanup-orphan-blobs', '--execute'])``
    without --flutter-repo must exit non-zero with a clear remediation
    message. Fail-closed at CLI parse / validation time."""
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

    monkeypatch.setattr(cov, "get_supabase_client", lambda: object())
    monkeypatch.setattr(cov, "fetch_all_versions", lambda client: [
        {"db_version": "vTEST", "created_at": "2026-05-12T00:00:00Z", "is_current": True},
        {"db_version": "vOLD",  "created_at": "2026-05-11T00:00:00Z", "is_current": False},
    ])
    monkeypatch.setattr(cov, "delete_version_directory", lambda c, v, dr: (0, 0))
    monkeypatch.setattr(cov, "delete_manifest_row", lambda c, v, dr: (True, None))

    def boom(*args, **kwargs):
        raise RuntimeError("simulated gate machinery explosion")
    monkeypatch.setattr(cov, "cleanup_orphan_blobs_with_gates", boom)

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
    """When --allow-destructive-orphan-cleanup is False (default), the
    gate-passthrough flags MUST NOT appear in the cleanup argv."""
    from sync_to_supabase import _build_cleanup_args

    argv = _build_cleanup_args(
        cleanup_keep=2,
        allow_destructive_orphan_cleanup=False,
        flutter_repo="/path/to/Flutter app",
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
    """When opted in but no override values supplied, the override flags
    are omitted; only required passthroughs appear."""
    from sync_to_supabase import _build_cleanup_args

    argv = _build_cleanup_args(
        cleanup_keep=2,
        allow_destructive_orphan_cleanup=True,
        flutter_repo="/repo",
        dist_dir="/dist",
        bundle_mismatch_reason=None,
        expected_count=None,
    )

    assert "--cleanup-orphan-blobs" in argv
    assert "--flutter-repo" in argv
    assert "--dist-dir" in argv
    assert "--branch" not in argv          # default "main" is redundant
    assert "--override-bundle-mismatch" not in argv
    assert "--expected-count" not in argv


# ===========================================================================
# Test 11 (P2.2 NEW) — recovery sanity: quarantined blob can be restored
# ===========================================================================


def test_p2_2_quarantined_blob_can_be_recovered_after_cleanup(tmp_path):
    """End-to-end recovery test:
      1. Run cleanup → 3 orphans get quarantined
      2. Call recover_blob on one of them → it's restored to active path
      3. Assert active storage has the recovered blob with original bytes
      4. Assert quarantine no longer has it

    Proves the move-then-recover flow works through the production
    cleanup path. Required by P2.2 sign-off ("quarantined blobs can
    be restored")."""
    from cleanup_old_versions import cleanup_orphan_blobs_with_gates
    from release_safety import AuditLog, recover_blob

    bundled_and_dist = [_h(i) for i in range(100)]
    extra_orphans    = [_h(i) for i in range(1000, 1003)]

    flutter_repo = tmp_path / "flutter"
    flutter_repo.mkdir()
    _git_init(flutter_repo)
    _commit_bundle(flutter_repo, bundled_and_dist, db_version="vMATCHED")
    dist_dir = tmp_path / "dist"
    _make_dist(dist_dir, bundled_and_dist, db_version="vMATCHED")

    storage_hashes = set(bundled_and_dist) | set(extra_orphans)
    client, bucket = _make_mock_client_with_active_storage(storage_hashes)

    # Capture original bytes for the orphan we'll later recover.
    target_orphan = extra_orphans[1]
    original_bytes = bucket.objects[_active_path(target_orphan)]

    audit = AuditLog(tmp_path / "audit.jsonl", release_id="recovery_test")
    quarantined, failed = cleanup_orphan_blobs_with_gates(
        client=client,
        current_version="vMATCHED",
        flutter_repo_path=flutter_repo,
        dist_dir=dist_dir,
        audit_log=audit,
        lock_path=tmp_path / ".release.lock",
        run_date="2026-05-12",
    )

    assert quarantined == 3
    assert failed == 0
    # Sanity: the orphan is now in quarantine, not active.
    assert _active_path(target_orphan) not in bucket.objects
    assert _quarantine_path("2026-05-12", target_orphan) in bucket.objects

    # Now recover that one blob.
    ok, err = recover_blob(client, target_orphan, search_dates=["2026-05-12"])
    assert ok is True, f"recovery failed: {err}"

    # Active path has the original bytes back.
    assert _active_path(target_orphan) in bucket.objects
    assert bucket.objects[_active_path(target_orphan)] == original_bytes
    # Quarantine no longer has it.
    assert _quarantine_path("2026-05-12", target_orphan) not in bucket.objects

    # Other orphans STILL in quarantine (recovery is single-blob).
    for other in (extra_orphans[0], extra_orphans[2]):
        assert _quarantine_path("2026-05-12", other) in bucket.objects
        assert _active_path(other) not in bucket.objects


# ===========================================================================
# Test 12 (P2.2 NEW) — partial quarantine failure: continues + reports
# ===========================================================================


def test_p2_2_partial_quarantine_failure_continues_and_reports(tmp_path):
    """Per P2.2 sign-off: when quarantine_blob fails for ONE blob, the
    cleanup MUST continue across the remaining eligible blobs and
    report the failure count. Failures are NOT swallowed silently and
    do NOT abort the entire cleanup."""
    from cleanup_old_versions import cleanup_orphan_blobs_with_gates
    from release_safety import AuditLog

    bundled_and_dist = [_h(i) for i in range(100)]
    extra_orphans    = [_h(i) for i in range(1000, 1003)]    # 3 orphans

    flutter_repo = tmp_path / "flutter"
    flutter_repo.mkdir()
    _git_init(flutter_repo)
    _commit_bundle(flutter_repo, bundled_and_dist, db_version="vMATCHED")
    dist_dir = tmp_path / "dist"
    _make_dist(dist_dir, bundled_and_dist, db_version="vMATCHED")

    storage_hashes = set(bundled_and_dist) | set(extra_orphans)
    client, bucket = _make_mock_client_with_active_storage(storage_hashes)

    # Inject failure on the COPY for the second orphan's quarantine target.
    failing_orphan = extra_orphans[1]
    failing_target = _quarantine_path("2026-05-12", failing_orphan)
    bucket.fail_copy_to.add(failing_target)

    audit = AuditLog(tmp_path / "audit.jsonl", release_id="partial_failure")
    quarantined, failed = cleanup_orphan_blobs_with_gates(
        client=client,
        current_version="vMATCHED",
        flutter_repo_path=flutter_repo,
        dist_dir=dist_dir,
        audit_log=audit,
        lock_path=tmp_path / ".release.lock",
        run_date="2026-05-12",
    )

    # 2 quarantined, 1 failed — the cleanup MUST continue past the failure.
    assert quarantined == 2
    assert failed == 1

    # The two non-failing orphans are now in quarantine.
    for ok_orphan in (extra_orphans[0], extra_orphans[2]):
        assert _active_path(ok_orphan) not in bucket.objects
        assert _quarantine_path("2026-05-12", ok_orphan) in bucket.objects

    # The failing orphan is STILL in active storage (COPY failed,
    # source preserved by quarantine_blob's atomicity contract).
    assert _active_path(failing_orphan) in bucket.objects
    # And NOT in quarantine.
    assert _quarantine_path("2026-05-12", failing_orphan) not in bucket.objects

    # Audit log records the per-quarantine outcome with failed_paths.
    from release_safety import read_audit_log
    events = read_audit_log(audit.path)
    completion = next(
        (e for e in events if e["event_type"] == "quarantine_completed"),
        None,
    )
    assert completion is not None
    assert completion["quarantined_count"] == 2
    assert completion["failed_count"] == 1
    assert _active_path(failing_orphan) in completion["failed_paths"]


# ===========================================================================
# P3.6a — integration test: registry-backed protection covers cleanup gates
# ===========================================================================
#
# Proves the load-bearing flip: the supabase_client now passed through
# cleanup_old_versions.py -> evaluate_cleanup_gates -> compute_protected_blob_set
# actually folds catalog_releases rows into the protected set BEFORE the
# gate runs. A blob referenced ONLY by a rollback registry row (not in
# bundled, not in dist) must survive cleanup.
#
# This is the end-to-end version of test_p3_5_rollback_row_protected_even_*,
# exercised through the real cleanup_orphan_blobs_with_gates entry point.


def test_p3_6a_registry_rollback_row_protects_blobs_in_full_cleanup_path(tmp_path):
    """The integration test the sign-off called out.

    Setup:
      - Flutter bundled catalog references hashes {A1, A2, A3}.
      - dist's detail_index references the same {A1, A2, A3} (post-bundle steady state).
      - Storage holds {A1, A2, A3, R1, R2, R3, X1, X2, X3} — 9 blobs total.
        * A* are in bundled∪dist.
        * R* are referenced ONLY by a rollback registry row.
        * X* are genuine orphans (nothing references them).
      - catalog_releases registry holds:
        * one ACTIVE row matching bundled (channel=bundled, references A*)
        * one ACTIVE row for the rollback (channel=ota_stable, references R*)

    Expected:
      - A* preserved (bundled, dist, and registry all protect them).
      - R* preserved (ONLY registry protects them — proves the wire-in).
      - X* quarantined (nothing protects them, gates pass blast-radius).
    """
    from cleanup_old_versions import cleanup_orphan_blobs_with_gates
    from release_safety import make_audit_log

    # --- Bundled + dist: 94 shared hashes (padding to keep blast radius low) ---
    # We need storage to be ≥100 so 3 orphans = 3% < 5% blast-radius threshold.
    # The 94 "shared" hashes are in BOTH bundled and dist — typical steady state.
    bundled = [_h(i) for i in range(0, 94)]                # A* (94 hashes)
    flutter_repo = tmp_path / "flutter"
    flutter_repo.mkdir()
    _git_init(flutter_repo)
    _commit_bundle(flutter_repo, bundled, db_version="2026.05.13.bundled")

    dist_dir = tmp_path / "dist"
    _make_dist(dist_dir, bundled, db_version="2026.05.13.bundled")

    # --- Storage: bundled∪dist (A*) + rollback-only (R*) + orphans (X*) ---
    rollback_only = [_h(i) for i in range(100, 103)]    # R1, R2, R3
    orphans       = [_h(i) for i in range(200, 203)]    # X1, X2, X3
    all_storage_hashes = bundled + rollback_only + orphans
    client, bucket = _make_mock_client_with_active_storage(all_storage_hashes)

    # --- Registry: bundled ACTIVE row + rollback ACTIVE row ---
    bundled_index_payload: dict = {"_meta": {"db_version": "2026.05.13.bundled"}}
    for i, h in enumerate(bundled):
        bundled_index_payload[str(10000 + i)] = {
            "blob_sha256": h,
            "storage_path": f"shared/details/sha256/{h[:2]}/{h}.json",
            "blob_version": 1,
        }
    rollback_index_payload: dict = {"_meta": {"db_version": "2026.05.11.rollback"}}
    for i, h in enumerate(rollback_only):
        rollback_index_payload[str(20000 + i)] = {
            "blob_sha256": h,
            "storage_path": f"shared/details/sha256/{h[:2]}/{h}.json",
            "blob_version": 1,
        }

    bucket.objects["v2026.05.13.bundled/detail_index.json"] = \
        json.dumps(bundled_index_payload).encode("utf-8")
    bucket.objects["v2026.05.11.rollback/detail_index.json"] = \
        json.dumps(rollback_index_payload).encode("utf-8")

    client.seed_catalog_releases([
        {
            "db_version": "2026.05.13.bundled",
            "state": "ACTIVE",
            "release_channel": "bundled",
            "released_at": "2026-05-13T00:00:00Z",
            "activated_at": "2026-05-13T00:00:00Z",
            "retired_at": None, "retired_reason": None,
            "bundled_in_app_versions": [],
            "flutter_repo_commit": "abc123",
            "detail_index_url": "v2026.05.13.bundled/detail_index.json",
            "notes": None,
        },
        {
            "db_version": "2026.05.11.rollback",
            "state": "ACTIVE",
            "release_channel": "ota_stable",
            "released_at": "2026-05-11T00:00:00Z",
            "activated_at": "2026-05-11T00:00:00Z",
            "retired_at": None, "retired_reason": None,
            "bundled_in_app_versions": [],
            "flutter_repo_commit": None,
            "detail_index_url": "v2026.05.11.rollback/detail_index.json",
            "notes": None,
        },
    ])

    audit = make_audit_log(audit_dir=tmp_path / "audit",
                           release_id="p3_6a_registry_integration")

    quarantined, failed = cleanup_orphan_blobs_with_gates(
        client=client,
        current_version="2026.05.13.bundled",
        flutter_repo_path=flutter_repo,
        dist_dir=dist_dir,
        branch="main",
        audit_log=audit,
        lock_path=tmp_path / ".release.lock",
        run_date="2026-05-13",
    )

    # --- Outcomes ---
    assert failed == 0, "no per-blob quarantine failures expected"
    assert quarantined == len(orphans), (
        f"expected exactly {len(orphans)} orphans quarantined, got {quarantined}"
    )

    # A* (bundled∪dist∪registry) - all preserved in active storage
    for h in bundled:
        assert _active_path(h) in bucket.objects, (
            f"bundled hash {h[:16]}... was incorrectly removed from active storage"
        )

    # R* (registry-only protection - THE LOAD-BEARING CASE) - all preserved
    for h in rollback_only:
        assert _active_path(h) in bucket.objects, (
            f"P3.6a REGRESSION: rollback hash {h[:16]}... was deleted from "
            f"active storage. The registry-backed protection wire-in is broken; "
            f"compute_protected_blob_set was called without supabase_client."
        )
        # Sanity: NOT in quarantine either
        assert _quarantine_path("2026-05-13", h) not in bucket.objects

    # X* (genuine orphans) - all moved to quarantine
    for h in orphans:
        assert _active_path(h) not in bucket.objects
        assert _quarantine_path("2026-05-13", h) in bucket.objects

    # Audit event surfaces registry metrics (per ADR-0001 P3.5 sign-off)
    from release_safety import read_audit_log
    events = read_audit_log(audit.path)
    protected_set_event = next(
        (e for e in events if e["event_type"] == "protected_set_computed"),
        None,
    )
    assert protected_set_event is not None
    assert protected_set_event["registry_version_count"] == 2
    assert set(protected_set_event["registry_versions"]) == {
        "2026.05.13.bundled", "2026.05.11.rollback",
    }
    # Registry contributed len(bundled)+len(rollback_only) entries
    expected_registry_entries = len(bundled) + len(rollback_only)
    assert protected_set_event["registry_total_entry_count"] == expected_registry_entries
    # Unique hashes contributed by registry. Bundled side fully overlaps with
    # dist; rollback hashes are new. The exact precision is exercised in unit
    # tests — here we just check the registry covers at least the rollback set.
    assert protected_set_event["registry_protected_blob_count"] >= len(rollback_only)
