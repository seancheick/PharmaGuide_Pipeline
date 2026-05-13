"""Tests for scripts/release_safety/backfill_catalog_releases.py (P3.3).

Mocks both the Supabase storage namespace AND the table namespace so the
backfill flow can be exercised end-to-end without network. Also injects
a fake ``read_flutter_bundle_manifest`` to cover bundled-side detection
without needing a real Flutter repo.

Required scenarios (per ADR-0001 P3.3 sign-off):
  1. bundled == current OTA  -> dedupes to ONE bundled-channel row
  2. bundled != current OTA  -> creates two rows (bundled + ota_stable)
  3. rollback row with surviving v{ver}/ -> protected ACTIVE row created
  4. missing v{ver}/ for rollback -> reported under skipped_missing_storage
  5. missing v{ver}/detail_index.json for OTA/rollback -> reported under
     skipped_missing_index, NO row inserted
  6. dry-run writes nothing
  7. execute writes rows
  8. rerun is idempotent (rows already exist -> [skip], no errors)

Plus defensive coverage:
  - flutter_repo not provided  -> bundled candidate skipped with reason
  - flutter manifest absent on branch  -> bundled candidate skipped (NOT a hard fail)
  - flutter manifest malformed -> hard fail (refusing to backfill from corruption)
  - manifest with multiple is_current=true rows -> hard fail
  - bundled candidate w/o supabase index -> still inserted, detail_index_url=None
  - per-candidate insert error -> isolated; other candidates still inserted
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from typing import Any, Optional
import pytest

_scripts_dir = os.path.join(os.path.dirname(__file__), "..")
if _scripts_dir not in sys.path:
    sys.path.insert(0, os.path.abspath(_scripts_dir))

from release_safety import backfill_catalog_releases as bcr
from release_safety.backfill_catalog_releases import (
    BackfillCandidate,
    BackfillPlan,
    BackfillResult,
    InvalidBackfillEnvironmentError,
    compute_backfill_plan,
    execute_backfill_plan,
    format_plan_text,
)
from release_safety.bundle_alignment import (
    BranchNotFoundError,
    BundleManifestNotFoundError,
    BundleManifestSnapshot,
    FlutterRepoNotFoundError,
    MalformedBundleManifestError,
)
from release_safety.registry import (
    DEFAULT_TABLE as REGISTRY_TABLE,
    CatalogRelease,
    ReleaseChannel,
    ReleaseState,
)


# ---------------------------------------------------------------------------
# Test doubles — Supabase client (storage + table)
# ---------------------------------------------------------------------------


class _Response:
    def __init__(self, data: list[dict]) -> None:
        self.data = data


class FakeBucket:
    """Subset of supabase storage bucket: list(path, options={limit, offset})."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put(self, path: str, content: bytes = b"x") -> None:
        self.objects[path] = content

    def list(self, path: str = "", options: Optional[dict] = None):
        opts = options or {}
        limit = opts.get("limit")
        offset = opts.get("offset", 0)
        prefix = path.rstrip("/") + "/" if path else ""
        results: list[dict] = []
        seen_dirs: set[str] = set()
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


class FakeStorage:
    def __init__(self) -> None:
        self.buckets: dict[str, FakeBucket] = {}

    def from_(self, bucket: str) -> FakeBucket:
        return self.buckets.setdefault(bucket, FakeBucket())


class FakeTable:
    def __init__(self, name: str, store: list[dict]) -> None:
        self._name = name
        self._store = store
        self._mode: Optional[str] = None
        self._payload: Optional[dict] = None
        self._select_cols: Optional[list[str]] = None
        self._filters: list[tuple[str, Any]] = []
        self._fail_insert_for: set[str] = set()  # populated externally

    def select(self, cols: str = "*") -> "FakeTable":
        new = self._fresh()
        new._mode = "select"
        new._select_cols = None if cols == "*" else [c.strip() for c in cols.split(",")]
        return new

    def insert(self, payload: dict) -> "FakeTable":
        new = self._fresh()
        new._mode = "insert"
        new._payload = dict(payload)
        return new

    def eq(self, col: str, val: Any) -> "FakeTable":
        self._filters.append((col, val))
        return self

    def execute(self) -> _Response:
        if self._mode == "select":
            matched = [r for r in self._store
                       if all(r.get(c) == v for c, v in self._filters)]
            if self._select_cols is None:
                return _Response([dict(r) for r in matched])
            return _Response([
                {c: r.get(c) for c in self._select_cols} for r in matched
            ])
        if self._mode == "insert":
            assert self._payload is not None
            db_ver = self._payload.get("db_version")
            if db_ver in self._fail_insert_for:
                raise RuntimeError(f"injected insert failure for {db_ver}")
            new_row = dict(self._payload)
            new_row.setdefault("released_at", datetime.now(timezone.utc).isoformat())
            new_row.setdefault("activated_at", None)
            new_row.setdefault("retired_at", None)
            new_row.setdefault("retired_reason", None)
            new_row.setdefault("flutter_repo_commit", None)
            new_row.setdefault("detail_index_url", None)
            new_row.setdefault("notes", None)
            new_row.setdefault("bundled_in_app_versions", [])
            self._store.append(new_row)
            return _Response([dict(new_row)])
        raise AssertionError("execute() called with no mode set")

    def _fresh(self) -> "FakeTable":
        new = FakeTable(self._name, self._store)
        new._fail_insert_for = self._fail_insert_for
        return new


class FakeClient:
    def __init__(self) -> None:
        self.storage = FakeStorage()
        self._tables: dict[str, list[dict]] = {}
        self._fail_insert_for: dict[str, set[str]] = {}

    def table(self, name: str) -> FakeTable:
        store = self._tables.setdefault(name, [])
        t = FakeTable(name, store)
        t._fail_insert_for = self._fail_insert_for.setdefault(name, set())
        return t

    def rows(self, table: str = REGISTRY_TABLE) -> list[dict]:
        return self._tables.setdefault(table, [])

    def seed_manifest(
        self, rows: list[dict], *, table: str = bcr.DEFAULT_MANIFEST_TABLE
    ) -> "FakeClient":
        store = self._tables.setdefault(table, [])
        store.extend(dict(r) for r in rows)
        return self

    def seed_registry(
        self, rows: list[dict], *, table: str = REGISTRY_TABLE
    ) -> "FakeClient":
        store = self._tables.setdefault(table, [])
        store.extend(dict(r) for r in rows)
        return self

    def seed_v_dir(
        self, db_version: str, *, files: Optional[list[str]] = None,
        bucket: str = bcr.DEFAULT_BUCKET,
    ) -> "FakeClient":
        b = self.storage.from_(bucket)
        files = files or ["pharmaguide_core.db", "detail_index.json"]
        for fname in files:
            b.put(f"v{db_version}/{fname}", b"data")
        return self

    def fail_insert(
        self, db_version: str, *, table: str = REGISTRY_TABLE
    ) -> "FakeClient":
        self._fail_insert_for.setdefault(table, set()).add(db_version)
        return self


# ---------------------------------------------------------------------------
# Bundle-manifest fake (patches read_flutter_bundle_manifest)
# ---------------------------------------------------------------------------


def _patch_bundle(monkeypatch, *, snapshot=None, exception=None) -> None:
    def fake_reader(*, flutter_repo_path, branch=bcr.DEFAULT_BRANCH, **kwargs):
        if exception is not None:
            raise exception
        return snapshot
    monkeypatch.setattr(bcr, "read_flutter_bundle_manifest", fake_reader)


def _snap(db_version: str, commit: str = "abc1234") -> BundleManifestSnapshot:
    """Construct a BundleManifestSnapshot with the minimum fields the
    backfill script reads. Other fields default per the P1.3 dataclass."""
    from pathlib import Path
    return BundleManifestSnapshot(
        flutter_repo_path=Path("/fake/path"),
        branch="main",
        commit_sha=commit,
        manifest_path="assets/db/export_manifest.json",
        db_version=db_version,
        db_checksum_sha256="0" * 64,
        raw={"db_version": db_version, "checksum_sha256": "0" * 64},
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client() -> FakeClient:
    return FakeClient()


@pytest.fixture
def fixed_now() -> datetime:
    return datetime(2026, 5, 13, 12, 0, 0, tzinfo=timezone.utc)


# ===========================================================================
# Scenario 1 — bundled == current OTA dedupes to ONE bundled-channel row
# ===========================================================================


def test_bundled_equals_current_ota_dedupes_to_one_bundled_row(
    client: FakeClient, monkeypatch
):
    """If the bundled catalog is also the current OTA, we get ONE row,
    channel=bundled, with notes mentioning OTA. flutter_repo_commit is set."""
    db_version = "2026.05.12.203133"
    _patch_bundle(monkeypatch, snapshot=_snap(db_version, commit="bundlesha"))
    client.seed_manifest([{"db_version": db_version, "is_current": True}])
    client.seed_v_dir(db_version)

    plan = compute_backfill_plan(
        client,
        flutter_repo="/fake/path",
        bundled_app_version="1.0.0",
    )

    assert len(plan.candidates) == 1
    c = plan.candidates[0]
    assert c.db_version == db_version
    assert c.release_channel == ReleaseChannel.BUNDLED
    assert c.flutter_repo_commit == "bundlesha"
    assert c.bundled_in_app_versions == ("1.0.0",)
    assert c.notes is not None and "OTA" in c.notes
    assert "ota-current" in c.sources and "flutter-bundled" in c.sources
    assert plan.bundled_degenerate_reason is None
    assert plan.rows_already_exist == ()


# ===========================================================================
# Scenario 2 — bundled and current OTA differ -> two rows
# ===========================================================================


def test_bundled_and_ota_different_creates_two_rows(
    client: FakeClient, monkeypatch
):
    bundled_version = "2026.05.10.130000"
    ota_version = "2026.05.12.203133"
    _patch_bundle(monkeypatch, snapshot=_snap(bundled_version, commit="bundlesha"))
    client.seed_manifest([{"db_version": ota_version, "is_current": True}])
    client.seed_v_dir(bundled_version)
    client.seed_v_dir(ota_version)

    plan = compute_backfill_plan(client, flutter_repo="/fake/path")

    versions = {c.db_version: c for c in plan.candidates}
    assert set(versions) == {bundled_version, ota_version}
    assert versions[bundled_version].release_channel == ReleaseChannel.BUNDLED
    assert versions[bundled_version].flutter_repo_commit == "bundlesha"
    assert versions[ota_version].release_channel == ReleaseChannel.OTA_STABLE
    assert versions[ota_version].flutter_repo_commit is None


# ===========================================================================
# Scenario 3 — rollback row with surviving v{ver}/ creates ACTIVE row
# ===========================================================================


def test_rollback_with_surviving_v_dir_creates_protected_row(
    client: FakeClient, monkeypatch
):
    bundled_version = "bundled.1"
    ota_current = "ota.current"
    rollback = "ota.rollback"
    _patch_bundle(monkeypatch, snapshot=_snap(bundled_version))
    client.seed_manifest([
        {"db_version": ota_current, "is_current": True},
        {"db_version": rollback, "is_current": False},
    ])
    client.seed_v_dir(bundled_version)
    client.seed_v_dir(ota_current)
    client.seed_v_dir(rollback)

    plan = compute_backfill_plan(client, flutter_repo="/fake/path")

    versions = {c.db_version: c for c in plan.candidates}
    assert rollback in versions
    rollback_candidate = versions[rollback]
    assert rollback_candidate.release_channel == ReleaseChannel.OTA_STABLE
    assert rollback_candidate.detail_index_url == f"v{rollback}/detail_index.json"
    assert "rollback" in (rollback_candidate.notes or "")


# ===========================================================================
# Scenario 4 — missing v{ver}/ for rollback -> skipped_missing_storage
# ===========================================================================


def test_rollback_without_storage_dir_is_skipped(
    client: FakeClient, monkeypatch
):
    """Rollback rows whose v{ver}/ no longer exists in storage are reported
    under skipped_missing_storage and NOT inserted. (Real-world: Bucket-2
    cleanup may have removed the v-dir.)"""
    _patch_bundle(monkeypatch, snapshot=_snap("bundled.1"))
    client.seed_manifest([
        {"db_version": "ota.current", "is_current": True},
        {"db_version": "ota.gone", "is_current": False},  # no v-dir for this one
    ])
    client.seed_v_dir("bundled.1")
    client.seed_v_dir("ota.current")
    # NOTE: not seeding v-dir for "ota.gone"

    plan = compute_backfill_plan(client, flutter_repo="/fake/path")

    candidate_versions = {c.db_version for c in plan.candidates}
    assert "ota.gone" not in candidate_versions
    assert "ota.gone" in plan.rows_skipped_missing_storage


# ===========================================================================
# Scenario 5 — missing detail_index.json -> skipped_missing_index
# ===========================================================================


def test_ota_without_detail_index_is_skipped(client: FakeClient, monkeypatch):
    """v{ver}/ exists but detail_index.json is missing -> skipped, NOT inserted."""
    _patch_bundle(monkeypatch, snapshot=_snap("bundled.1"))
    client.seed_manifest([{"db_version": "ota.current", "is_current": True}])
    client.seed_v_dir("bundled.1")
    # Seed v-dir without detail_index.json
    client.seed_v_dir("ota.current", files=["pharmaguide_core.db"])

    plan = compute_backfill_plan(client, flutter_repo="/fake/path")

    versions = {c.db_version for c in plan.candidates}
    assert "ota.current" not in versions
    assert "ota.current" in plan.rows_skipped_missing_index


def test_rollback_without_detail_index_is_skipped(
    client: FakeClient, monkeypatch
):
    _patch_bundle(monkeypatch, snapshot=_snap("bundled.1"))
    client.seed_manifest([
        {"db_version": "ota.current", "is_current": True},
        {"db_version": "ota.rollback", "is_current": False},
    ])
    client.seed_v_dir("bundled.1")
    client.seed_v_dir("ota.current")
    # rollback v-dir exists but no detail_index
    client.seed_v_dir("ota.rollback", files=["pharmaguide_core.db"])

    plan = compute_backfill_plan(client, flutter_repo="/fake/path")

    versions = {c.db_version for c in plan.candidates}
    assert "ota.rollback" not in versions
    assert "ota.rollback" in plan.rows_skipped_missing_index


# ===========================================================================
# Scenario 6 — dry-run writes nothing
# ===========================================================================


def test_dry_run_writes_nothing(client: FakeClient, monkeypatch):
    _patch_bundle(monkeypatch, snapshot=_snap("v1"))
    client.seed_manifest([{"db_version": "v2", "is_current": True}])
    client.seed_v_dir("v1")
    client.seed_v_dir("v2")

    plan = compute_backfill_plan(client, flutter_repo="/fake/path")
    assert len(plan.candidates) == 2  # sanity

    result = execute_backfill_plan(client, plan, dry_run=True)
    assert result.dry_run is True
    assert result.inserted == ()
    assert client.rows() == []  # no rows in catalog_releases


# ===========================================================================
# Scenario 7 — execute writes rows
# ===========================================================================


def test_execute_writes_active_rows(
    client: FakeClient, monkeypatch, fixed_now: datetime
):
    _patch_bundle(monkeypatch, snapshot=_snap("v1", commit="commitsha"))
    client.seed_manifest([{"db_version": "v2", "is_current": True}])
    client.seed_v_dir("v1")
    client.seed_v_dir("v2")

    plan = compute_backfill_plan(client, flutter_repo="/fake/path")
    result = execute_backfill_plan(client, plan, dry_run=False, now=fixed_now)

    assert result.dry_run is False
    assert len(result.inserted) == 2
    assert all(r.state == ReleaseState.ACTIVE for r in result.inserted)
    assert all(r.activated_at == fixed_now for r in result.inserted)
    rows_in_db = {r["db_version"]: r for r in client.rows()}
    assert set(rows_in_db) == {"v1", "v2"}
    assert rows_in_db["v1"]["release_channel"] == "bundled"
    assert rows_in_db["v1"]["flutter_repo_commit"] == "commitsha"
    assert rows_in_db["v2"]["release_channel"] == "ota_stable"


# ===========================================================================
# Scenario 8 — rerun is idempotent (rows already exist -> [skip])
# ===========================================================================


def test_rerun_is_idempotent(client: FakeClient, monkeypatch, fixed_now: datetime):
    _patch_bundle(monkeypatch, snapshot=_snap("v1", commit="cs"))
    client.seed_manifest([{"db_version": "v2", "is_current": True}])
    client.seed_v_dir("v1")
    client.seed_v_dir("v2")

    # First execute: writes 2 rows
    plan_1 = compute_backfill_plan(client, flutter_repo="/fake/path")
    res_1 = execute_backfill_plan(client, plan_1, dry_run=False, now=fixed_now)
    assert len(res_1.inserted) == 2
    assert len(client.rows()) == 2

    # Second compute: candidates is empty (both already exist)
    plan_2 = compute_backfill_plan(client, flutter_repo="/fake/path")
    assert plan_2.candidates == ()
    assert set(plan_2.rows_already_exist) == {"v1", "v2"}

    # Second execute: no inserts, no errors
    res_2 = execute_backfill_plan(client, plan_2, dry_run=False, now=fixed_now)
    assert res_2.inserted == ()
    assert res_2.errors == ()
    assert set(res_2.skipped_already_exist) == {"v1", "v2"}
    assert len(client.rows()) == 2  # unchanged


# ===========================================================================
# Defensive — bundled side degenerate paths
# ===========================================================================


def test_no_flutter_repo_means_bundled_degenerate(client: FakeClient):
    """No --flutter-repo -> bundled candidate skipped with reason; OTA still works."""
    client.seed_manifest([{"db_version": "ota.current", "is_current": True}])
    client.seed_v_dir("ota.current")

    plan = compute_backfill_plan(client, flutter_repo=None)

    assert plan.bundled_degenerate_reason is not None
    assert "flutter_repo not provided" in plan.bundled_degenerate_reason
    assert {c.db_version for c in plan.candidates} == {"ota.current"}


def test_bundled_manifest_absent_on_branch_is_degenerate(
    client: FakeClient, monkeypatch
):
    """Branch exists but no manifest committed -> bundled skipped, OTA proceeds."""
    _patch_bundle(monkeypatch, exception=BundleManifestNotFoundError("no manifest"))
    client.seed_manifest([{"db_version": "ota.current", "is_current": True}])
    client.seed_v_dir("ota.current")

    plan = compute_backfill_plan(client, flutter_repo="/fake/path")

    assert plan.bundled_degenerate_reason is not None
    assert "manifest absent" in plan.bundled_degenerate_reason
    assert {c.db_version for c in plan.candidates} == {"ota.current"}


def test_flutter_repo_not_found_is_degenerate(client: FakeClient, monkeypatch):
    _patch_bundle(monkeypatch, exception=FlutterRepoNotFoundError("nope"))
    plan = compute_backfill_plan(client, flutter_repo="/nonexistent")
    assert plan.bundled_degenerate_reason is not None
    assert "unreadable" in plan.bundled_degenerate_reason


def test_branch_not_found_is_degenerate(client: FakeClient, monkeypatch):
    _patch_bundle(monkeypatch, exception=BranchNotFoundError("master"))
    plan = compute_backfill_plan(client, flutter_repo="/fake")
    assert plan.bundled_degenerate_reason is not None
    assert "branch" in plan.bundled_degenerate_reason


def test_malformed_bundle_manifest_is_hard_fail(client: FakeClient, monkeypatch):
    """Corruption in the bundled manifest is a HARD FAIL (refusing to backfill
    from a malformed source). NOT degenerate-tolerant."""
    _patch_bundle(monkeypatch, exception=MalformedBundleManifestError("bad json"))
    with pytest.raises(InvalidBackfillEnvironmentError, match="malformed"):
        compute_backfill_plan(client, flutter_repo="/fake")


# ===========================================================================
# Defensive — manifest with multiple is_current=true rows is hard fail
# ===========================================================================


def test_multiple_is_current_rows_is_hard_fail(client: FakeClient, monkeypatch):
    _patch_bundle(monkeypatch, snapshot=_snap("v1"))
    client.seed_manifest([
        {"db_version": "ota.a", "is_current": True},
        {"db_version": "ota.b", "is_current": True},
    ])
    client.seed_v_dir("v1")
    client.seed_v_dir("ota.a")
    client.seed_v_dir("ota.b")

    with pytest.raises(InvalidBackfillEnvironmentError, match="is_current"):
        compute_backfill_plan(client, flutter_repo="/fake/path")


# ===========================================================================
# Defensive — bundled w/o supabase index still inserted (detail_index_url=None)
# ===========================================================================


def test_bundled_without_supabase_index_still_inserted(
    client: FakeClient, monkeypatch, fixed_now: datetime
):
    """Bundled rows tolerate absent v{ver}/detail_index.json — the bundled
    catalog's blob references come from the Flutter LFS catalog DB, not from
    a Supabase-hosted index."""
    _patch_bundle(monkeypatch, snapshot=_snap("v_bundled", commit="cs"))
    # NOTE: no v-dir at all for v_bundled
    plan = compute_backfill_plan(client, flutter_repo="/fake/path")

    assert len(plan.candidates) == 1
    assert plan.candidates[0].db_version == "v_bundled"
    assert plan.candidates[0].detail_index_url is None

    res = execute_backfill_plan(client, plan, dry_run=False, now=fixed_now)
    assert len(res.inserted) == 1
    assert res.inserted[0].detail_index_url is None
    assert res.inserted[0].state == ReleaseState.ACTIVE


# ===========================================================================
# Defensive — per-candidate insert error doesn't block other candidates
# ===========================================================================


def test_per_candidate_error_isolated(
    client: FakeClient, monkeypatch, fixed_now: datetime
):
    _patch_bundle(monkeypatch, snapshot=_snap("v1", commit="cs"))
    client.seed_manifest([{"db_version": "v2", "is_current": True}])
    client.seed_v_dir("v1")
    client.seed_v_dir("v2")
    client.fail_insert("v1")  # bundled insert blows up

    plan = compute_backfill_plan(client, flutter_repo="/fake/path")
    res = execute_backfill_plan(client, plan, dry_run=False, now=fixed_now)

    inserted_versions = {r.db_version for r in res.inserted}
    error_versions = {db_v for db_v, _ in res.errors}
    assert inserted_versions == {"v2"}
    assert error_versions == {"v1"}


# ===========================================================================
# Empty / no-op cases
# ===========================================================================


def test_empty_manifest_and_no_flutter_repo_is_empty_plan(client: FakeClient):
    plan = compute_backfill_plan(client, flutter_repo=None)
    assert plan.candidates == ()
    assert plan.rows_already_exist == ()
    assert plan.bundled_degenerate_reason is not None


def test_format_plan_text_renders_all_sections(client: FakeClient, monkeypatch):
    _patch_bundle(monkeypatch, snapshot=_snap("v1", commit="cs"))
    client.seed_manifest([
        {"db_version": "v2", "is_current": True},
        {"db_version": "v3_gone", "is_current": False},   # no storage
        {"db_version": "v4_no_idx", "is_current": False}, # no index
    ])
    client.seed_v_dir("v1")
    client.seed_v_dir("v2")
    client.seed_v_dir("v4_no_idx", files=["pharmaguide_core.db"])
    client.seed_registry([{
        "db_version": "v_existing",
        "state": "ACTIVE",
        "release_channel": "ota_stable",
        "released_at": "2026-05-01T00:00:00Z",
        "activated_at": "2026-05-01T00:00:00Z",
        "retired_at": None,
        "retired_reason": None,
        "bundled_in_app_versions": [],
        "flutter_repo_commit": None,
        "detail_index_url": None,
        "notes": None,
    }])
    # Force "v2" to be already-existing so it shows in the [skip] section
    client.seed_registry([{
        "db_version": "v2",
        "state": "ACTIVE",
        "release_channel": "ota_stable",
        "released_at": "2026-05-12T00:00:00Z",
        "activated_at": "2026-05-12T00:00:00Z",
        "retired_at": None,
        "retired_reason": None,
        "bundled_in_app_versions": [],
        "flutter_repo_commit": None,
        "detail_index_url": "v2/detail_index.json",
        "notes": None,
    }])

    plan = compute_backfill_plan(client, flutter_repo="/fake/path")
    text = format_plan_text(plan)

    assert "Catalog Releases Backfill Plan" in text
    assert "v1" in text                            # candidate (bundled)
    assert "v2" in text                            # already-exists skip
    assert "v3_gone" in text                       # missing storage
    assert "v4_no_idx" in text                     # missing index
