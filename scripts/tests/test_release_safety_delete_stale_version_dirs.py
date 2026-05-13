"""Tests for scripts/release_safety/delete_stale_version_dirs.py
(Bucket-2 cleanup tool — deletes stale pharmaguide/v.../ dirs).

Mock Supabase client supports BOTH storage list/remove AND table
select/execute. No real Supabase. No network.
"""

from __future__ import annotations

import json
import os
import socket
import sys
from pathlib import Path
from typing import List, Optional, Set
import pytest

_scripts_dir = os.path.join(os.path.dirname(__file__), "..")
if _scripts_dir not in sys.path:
    sys.path.insert(0, os.path.abspath(_scripts_dir))


# ---------------------------------------------------------------------------
# Mock Supabase client (storage + table)
# ---------------------------------------------------------------------------


class MockBucket:
    def __init__(self):
        self.objects: dict = {}                  # path -> bytes
        self.removed_paths: List[str] = []
        self.fail_remove: Set[str] = set()

    def put(self, path: str, content: bytes) -> None:
        self.objects[path] = content

    def remove(self, paths):
        for p in paths:
            if p in self.fail_remove:
                raise RuntimeError(f"injected DELETE failure (path={p})")
            self.objects.pop(p, None)
            self.removed_paths.append(p)
        return [{"name": p} for p in paths]

    def list(self, path: str, options=None):
        opts = options or {}
        limit = opts.get("limit")
        offset = opts.get("offset", 0)
        prefix = path.rstrip("/") + "/" if path else ""
        results = []
        seen_dirs: Set[str] = set()
        for full, data in self.objects.items():
            if not full.startswith(prefix):
                continue
            rest = full[len(prefix):]
            if "/" not in rest:
                results.append({"name": rest, "metadata": {"size": len(data)}})
            else:
                first = rest.split("/", 1)[0]
                if first not in seen_dirs:
                    seen_dirs.add(first)
                    results.append({"name": first})
        if limit is None:
            return results[offset:]
        return results[offset:offset + limit]


class MockStorageNamespace:
    def __init__(self):
        self.buckets: dict = {}

    def from_(self, bucket: str) -> MockBucket:
        return self.buckets.setdefault(bucket, MockBucket())


class _Response:
    def __init__(self, data):
        self.data = data


class MockTable:
    def __init__(self, rows):
        self._rows = list(rows)
        self._select_cols: Optional[List[str]] = None

    def set_rows(self, rows):
        self._rows = list(rows)

    def select(self, cols="*"):
        if cols == "*":
            self._select_cols = None
        else:
            self._select_cols = [c.strip() for c in cols.split(",")]
        return self

    def execute(self):
        if self._select_cols is None:
            return _Response([dict(r) for r in self._rows])
        return _Response([
            {c: r.get(c) for c in self._select_cols}
            for r in self._rows
        ])


class MockSupabaseClient:
    def __init__(self):
        self.storage = MockStorageNamespace()
        self._tables: dict = {}

    def table(self, name: str) -> MockTable:
        return self._tables.setdefault(name, MockTable([]))

    def with_manifest_rows(self, rows: List[dict]) -> "MockSupabaseClient":
        self.table("export_manifest").set_rows(rows)
        return self


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _populate_v_dir(bucket: MockBucket, db_version: str, files: List[tuple]) -> None:
    """Add files under pharmaguide/v{db_version}/. Each file is (relpath, size)."""
    for relpath, size in files:
        bucket.put(f"v{db_version}/{relpath}", b"x" * size)


def _make_client_with_versions(
    *,
    storage_versions_with_files: dict,
    manifest_versions: List[str],
) -> MockSupabaseClient:
    """Build a client with storage v-dirs and a manifest table populated."""
    client = MockSupabaseClient()
    bucket = client.storage.from_("pharmaguide")
    for db_version, files in storage_versions_with_files.items():
        _populate_v_dir(bucket, db_version, files)
    client.with_manifest_rows([{"db_version": v} for v in manifest_versions])
    return client


# ---------------------------------------------------------------------------
# Test 1 — empty bucket → empty plan
# ---------------------------------------------------------------------------


def test_p_b2_empty_bucket_returns_empty_plan():
    from release_safety.delete_stale_version_dirs import compute_delete_plan

    client = MockSupabaseClient()
    plan = compute_delete_plan(client)

    assert plan.total_versions == 0
    assert plan.total_objects == 0
    assert plan.total_bytes == 0
    assert plan.candidates == ()
    assert plan.excluded_versions_in_manifest == ()


# ---------------------------------------------------------------------------
# Test 2 — all v-dirs in manifest → no candidates, all excluded
# ---------------------------------------------------------------------------


def test_p_b2_all_dirs_in_manifest_no_candidates():
    from release_safety.delete_stale_version_dirs import compute_delete_plan

    client = _make_client_with_versions(
        storage_versions_with_files={
            "2026.05.12.203133": [("pharmaguide_core.db", 1000)],
            "2026.05.11.164208": [("pharmaguide_core.db", 1000)],
        },
        manifest_versions=["2026.05.12.203133", "2026.05.11.164208"],
    )

    plan = compute_delete_plan(client)

    assert plan.candidates == ()
    assert set(plan.excluded_versions_in_manifest) == {
        "2026.05.12.203133", "2026.05.11.164208",
    }


# ---------------------------------------------------------------------------
# Test 3 — partition: some dirs in manifest, some not
# ---------------------------------------------------------------------------


def test_p_b2_partitions_by_manifest_membership():
    from release_safety.delete_stale_version_dirs import compute_delete_plan

    client = _make_client_with_versions(
        storage_versions_with_files={
            # Stale (not in manifest) — should be candidates:
            "2026.03.30.013948": [("pharmaguide_core.db", 1000)],
            "2026.04.27.063145": [("pharmaguide_core.db", 2000)],
            # In manifest — should be excluded:
            "2026.05.12.203133": [("pharmaguide_core.db", 1500)],
        },
        manifest_versions=["2026.05.12.203133"],
    )

    plan = compute_delete_plan(client)

    assert plan.total_versions == 2
    candidate_versions = {c.db_version for c in plan.candidates}
    assert candidate_versions == {"2026.03.30.013948", "2026.04.27.063145"}
    assert plan.excluded_versions_in_manifest == ("2026.05.12.203133",)


# ---------------------------------------------------------------------------
# Test 4 — sorted output + accurate counts
# ---------------------------------------------------------------------------


def test_p_b2_candidates_sorted_and_counts_accurate():
    from release_safety.delete_stale_version_dirs import compute_delete_plan

    client = _make_client_with_versions(
        storage_versions_with_files={
            "2026.04.27.063145": [
                ("pharmaguide_core.db", 1000),
                ("export_manifest.json", 200),
            ],
            "2026.03.30.013948": [
                ("pharmaguide_core.db", 500),
                ("details/blob1.json", 300),
                ("details/blob2.json", 400),
            ],
        },
        manifest_versions=[],
    )

    plan = compute_delete_plan(client)

    # Sorted ascending by db_version
    assert [c.db_version for c in plan.candidates] == [
        "2026.03.30.013948", "2026.04.27.063145",
    ]

    # First candidate: 3 files = 1200 bytes
    c0 = plan.candidates[0]
    assert c0.object_count == 3
    assert c0.total_bytes == 1200
    assert c0.dir_path == "v2026.03.30.013948"

    # Second candidate: 2 files = 1200 bytes
    c1 = plan.candidates[1]
    assert c1.object_count == 2
    assert c1.total_bytes == 1200

    # Plan totals
    assert plan.total_objects == 5
    assert plan.total_bytes == 2400


# ---------------------------------------------------------------------------
# Test 5 — execute without expected counts → fails
# ---------------------------------------------------------------------------


def test_p_b2_execute_without_expected_count_raises(tmp_path):
    from release_safety.delete_stale_version_dirs import (
        compute_delete_plan, execute_delete_plan, ExpectedCountMismatch,
    )
    from release_safety.audit_log import AuditLog

    client = _make_client_with_versions(
        storage_versions_with_files={
            "2026.03.30.013948": [("file.json", 100)],
        },
        manifest_versions=[],
    )
    plan = compute_delete_plan(client)
    audit = AuditLog(tmp_path / "audit.jsonl", release_id="t5")

    with pytest.raises(ExpectedCountMismatch):
        execute_delete_plan(
            client, plan,
            expected_count=999, expected_bytes=plan.total_bytes,
            audit_log=audit, lock_path=tmp_path / ".release.lock",
        )


def test_p_b2_execute_with_wrong_expected_bytes_raises(tmp_path):
    from release_safety.delete_stale_version_dirs import (
        compute_delete_plan, execute_delete_plan, ExpectedCountMismatch,
    )
    from release_safety.audit_log import AuditLog

    client = _make_client_with_versions(
        storage_versions_with_files={
            "2026.03.30.013948": [("file.json", 100)],
        },
        manifest_versions=[],
    )
    plan = compute_delete_plan(client)
    audit = AuditLog(tmp_path / "audit.jsonl", release_id="t6")

    with pytest.raises(ExpectedCountMismatch):
        execute_delete_plan(
            client, plan,
            expected_count=plan.total_objects, expected_bytes=999,
            audit_log=audit, lock_path=tmp_path / ".release.lock",
        )


# ---------------------------------------------------------------------------
# Test 7 — execute matching expected → deletes all listed objects
# ---------------------------------------------------------------------------


def test_p_b2_execute_with_matching_expected_deletes_objects(tmp_path):
    from release_safety.delete_stale_version_dirs import (
        compute_delete_plan, execute_delete_plan,
    )
    from release_safety.audit_log import AuditLog

    client = _make_client_with_versions(
        storage_versions_with_files={
            "2026.03.30.013948": [
                ("pharmaguide_core.db", 1000),
                ("export_manifest.json", 200),
            ],
            "2026.04.27.063145": [
                ("pharmaguide_core.db", 1500),
            ],
            # Protected (in manifest) — must NOT be touched
            "2026.05.12.203133": [
                ("pharmaguide_core.db", 2000),
            ],
        },
        manifest_versions=["2026.05.12.203133"],
    )
    bucket = client.storage.from_("pharmaguide")
    plan = compute_delete_plan(client)

    audit = AuditLog(tmp_path / "audit.jsonl", release_id="t7")
    result = execute_delete_plan(
        client, plan,
        expected_count=plan.total_objects,
        expected_bytes=plan.total_bytes,
        audit_log=audit, lock_path=tmp_path / ".release.lock",
    )

    assert result.passed is True
    assert result.deleted_objects_count == 3
    assert result.deleted_bytes == 1000 + 200 + 1500
    assert set(result.deleted_versions) == {
        "2026.03.30.013948", "2026.04.27.063145",
    }

    # Stale dirs gone from storage
    assert "v2026.03.30.013948/pharmaguide_core.db" not in bucket.objects
    assert "v2026.03.30.013948/export_manifest.json" not in bucket.objects
    assert "v2026.04.27.063145/pharmaguide_core.db" not in bucket.objects
    # Protected version UNTOUCHED
    assert "v2026.05.12.203133/pharmaguide_core.db" in bucket.objects


# ---------------------------------------------------------------------------
# Test 8 — race condition: manifest changes between plan and execute
# ---------------------------------------------------------------------------


def test_p_b2_manifest_race_condition_aborts_execute(tmp_path):
    """If a candidate db_version appears in the manifest between
    compute_delete_plan and execute_delete_plan (concurrent release),
    execute MUST abort with ManifestRaceConditionError. No deletions."""
    from release_safety.delete_stale_version_dirs import (
        compute_delete_plan, execute_delete_plan, ManifestRaceConditionError,
    )
    from release_safety.audit_log import AuditLog

    client = _make_client_with_versions(
        storage_versions_with_files={
            "2026.03.30.013948": [("file.json", 100)],
        },
        manifest_versions=[],
    )
    bucket = client.storage.from_("pharmaguide")
    plan = compute_delete_plan(client)

    # Race: the candidate version now appears in the manifest.
    client.with_manifest_rows([{"db_version": "2026.03.30.013948"}])

    audit = AuditLog(tmp_path / "audit.jsonl", release_id="t8")
    with pytest.raises(ManifestRaceConditionError):
        execute_delete_plan(
            client, plan,
            expected_count=plan.total_objects,
            expected_bytes=plan.total_bytes,
            audit_log=audit, lock_path=tmp_path / ".release.lock",
        )

    # Storage UNTOUCHED.
    assert "v2026.03.30.013948/file.json" in bucket.objects
    assert bucket.removed_paths == []


# ---------------------------------------------------------------------------
# Test 9 — lock contention aborts execute
# ---------------------------------------------------------------------------


def test_p_b2_lock_contention_aborts_execute(tmp_path):
    from release_safety.delete_stale_version_dirs import (
        compute_delete_plan, execute_delete_plan,
    )
    from release_safety.lock import LockContentionError
    from release_safety.audit_log import AuditLog

    client = _make_client_with_versions(
        storage_versions_with_files={
            "2026.03.30.013948": [("file.json", 100)],
        },
        manifest_versions=[],
    )
    bucket = client.storage.from_("pharmaguide")
    plan = compute_delete_plan(client)

    # Pre-write a live lock file
    lock_path = tmp_path / ".release.lock"
    lock_path.write_text(json.dumps({
        "pid": os.getpid(),
        "host": socket.gethostname(),
        "started_at": "2026-05-12T20:00:00+00:00",
        "current_step": "blocked_step",
    }))

    audit = AuditLog(tmp_path / "audit.jsonl", release_id="t9")
    with pytest.raises(LockContentionError):
        execute_delete_plan(
            client, plan,
            expected_count=plan.total_objects,
            expected_bytes=plan.total_bytes,
            audit_log=audit, lock_path=lock_path,
        )

    assert "v2026.03.30.013948/file.json" in bucket.objects
    assert bucket.removed_paths == []


# ---------------------------------------------------------------------------
# Test 10 — partial delete failure: continues + reports
# ---------------------------------------------------------------------------


def test_p_b2_partial_delete_failure_continues_and_reports(tmp_path):
    from release_safety.delete_stale_version_dirs import (
        compute_delete_plan, execute_delete_plan,
    )
    from release_safety.audit_log import AuditLog

    client = _make_client_with_versions(
        storage_versions_with_files={
            "2026.03.30.013948": [
                ("file_a.json", 100),
                ("file_b.json", 200),
                ("file_c.json", 300),
            ],
        },
        manifest_versions=[],
    )
    bucket = client.storage.from_("pharmaguide")
    # Inject failure on the middle file
    bucket.fail_remove.add("v2026.03.30.013948/file_b.json")

    plan = compute_delete_plan(client)

    audit = AuditLog(tmp_path / "audit.jsonl", release_id="t10")
    result = execute_delete_plan(
        client, plan,
        expected_count=plan.total_objects,
        expected_bytes=plan.total_bytes,
        audit_log=audit, lock_path=tmp_path / ".release.lock",
    )

    assert result.passed is False
    assert result.deleted_objects_count == 2
    assert result.deleted_bytes == 100 + 300
    assert len(result.failed_objects) == 1
    assert result.failed_objects[0][0] == "v2026.03.30.013948/file_b.json"
    # Failing version is NOT recorded as fully-deleted
    assert "2026.03.30.013948" not in result.deleted_versions
    # Two files actually removed; one preserved
    assert "v2026.03.30.013948/file_a.json" not in bucket.objects
    assert "v2026.03.30.013948/file_b.json" in bucket.objects
    assert "v2026.03.30.013948/file_c.json" not in bucket.objects


# ---------------------------------------------------------------------------
# Test 11 — format_plan_text contains key fields
# ---------------------------------------------------------------------------


def test_p_b2_format_plan_text_contains_required_fields():
    from release_safety.delete_stale_version_dirs import (
        compute_delete_plan, format_plan_text,
    )

    client = _make_client_with_versions(
        storage_versions_with_files={
            "2026.03.30.013948": [("file.json", 1000)],
            "2026.05.12.203133": [("file.json", 2000)],
        },
        manifest_versions=["2026.05.12.203133"],
    )
    plan = compute_delete_plan(client)
    text = format_plan_text(plan)

    # Headlines
    assert "DRY-RUN" in text
    assert "2026.03.30.013948" in text
    assert "v2026.03.30.013948" in text
    assert "Excluded" in text
    assert "2026.05.12.203133" in text
    # Re-run instructions
    assert "--execute" in text
    assert f"--expected-count {plan.total_objects}" in text
    assert f"--expected-bytes {plan.total_bytes}" in text


# ---------------------------------------------------------------------------
# Test 12 — audit log captures lifecycle events
# ---------------------------------------------------------------------------


def test_p_b2_audit_log_records_full_lifecycle(tmp_path):
    from release_safety.delete_stale_version_dirs import (
        compute_delete_plan, execute_delete_plan,
    )
    from release_safety.audit_log import AuditLog, read_audit_log

    client = _make_client_with_versions(
        storage_versions_with_files={
            "2026.03.30.013948": [("file.json", 100)],
        },
        manifest_versions=[],
    )
    plan = compute_delete_plan(client)

    audit = AuditLog(tmp_path / "audit.jsonl", release_id="t12")
    execute_delete_plan(
        client, plan,
        expected_count=plan.total_objects,
        expected_bytes=plan.total_bytes,
        audit_log=audit, lock_path=tmp_path / ".release.lock",
    )

    events = read_audit_log(audit.path)
    event_types = [e["event_type"] for e in events]
    assert "delete_stale_version_dirs_started" in event_types
    assert "lock_acquired" in event_types
    assert "version_dir_deleted" in event_types
    assert "lock_released" in event_types
    assert "delete_complete" in event_types

    # The version_dir_deleted event captures the right counts
    vd = next(e for e in events if e["event_type"] == "version_dir_deleted")
    assert vd["db_version"] == "2026.03.30.013948"
    assert vd["deleted"] == 1
    assert vd["failed"] == 0
    assert vd["deleted_bytes"] == 100


# ---------------------------------------------------------------------------
# Test 13 — non-version top-level dirs are ignored (only v* matched)
# ---------------------------------------------------------------------------


def test_p_b2_non_version_top_level_dirs_ignored():
    from release_safety.delete_stale_version_dirs import compute_delete_plan

    client = MockSupabaseClient()
    bucket = client.storage.from_("pharmaguide")
    # Stale v-dir → candidate
    bucket.put("v2026.03.30.013948/file.json", b"x" * 100)
    # Other top-level dirs → must NOT appear
    bucket.put("shared/details/sha256/aa/" + "a" * 64 + ".json", b"x" * 50)
    bucket.put("user_avatars/123.png", b"x" * 200)
    bucket.put("random_dir/file.txt", b"x" * 30)

    plan = compute_delete_plan(client)

    # Only the v-dir is a candidate
    assert len(plan.candidates) == 1
    assert plan.candidates[0].db_version == "2026.03.30.013948"
    # Non-version files are NOT enumerated in the plan
    for c in plan.candidates:
        for path, _size in c.objects:
            assert path.startswith("v2026.03.30.013948/")
