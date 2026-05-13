"""Tests for scripts/release_safety/registry.py (P3.2 catalog_releases API).

No real Supabase. No network. A FakeSupabaseTable test double models the
subset of the supabase-py client surface registry.py uses:
    .table(name).select("*").eq(col, val).execute()
    .table(name).insert(payload).execute()
    .table(name).update(payload).eq(col, val).eq(col, val).execute()

Coverage targets:
  - parse: from_row happy path, missing field, unknown enum, bad timestamp
  - insert: happy path, duplicate, bundled-without-flutter_repo_commit,
    invalid db_version, invalid release_channel
  - read: get_release present/absent, list_active_releases, list_by_state
  - transitions: every legal transition, every illegal transition,
    activate sets activated_at, retire sets retired_at + retired_reason,
    rollback overwrites notes, retire rejects empty/whitespace reason
  - concurrency: optimistic-lock loss → IllegalStateTransitionError;
    re-fetch returns the racing-winner's state
  - missing-row: transitions on absent db_version → ReleaseNotFoundError
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

from release_safety.registry import (
    DEFAULT_TABLE,
    CatalogRelease,
    DuplicateReleaseError,
    IllegalStateTransitionError,
    InvalidReleaseFieldError,
    RegistryError,
    ReleaseChannel,
    ReleaseNotFoundError,
    ReleaseState,
    activate_release,
    get_release,
    insert_pending_release,
    list_active_releases,
    list_releases_by_state,
    retire_release,
    rollback_to_pending,
    transition_to_validating,
)


# ---------------------------------------------------------------------------
# Test double — Supabase table client (insert/select/update with eq filters)
# ---------------------------------------------------------------------------


class _Response:
    def __init__(self, data: list[dict]) -> None:
        self.data = data


class FakeTable:
    """Minimal stand-in for supabase-py's table builder. The chained-call
    pattern (.select(...).eq(...).execute()) mirrors the real client surface
    used by registry.py — nothing more, nothing less."""

    def __init__(self, name: str, store: list[dict]) -> None:
        self._name = name
        self._store = store
        self._mode: Optional[str] = None
        self._payload: Optional[dict] = None
        self._select_cols: Optional[list[str]] = None
        self._filters: list[tuple[str, Any]] = []

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

    def update(self, payload: dict) -> "FakeTable":
        new = self._fresh()
        new._mode = "update"
        new._payload = dict(payload)
        return new

    def eq(self, col: str, val: Any) -> "FakeTable":
        self._filters.append((col, val))
        return self

    def execute(self) -> _Response:
        if self._mode == "select":
            matched = self._matching_rows()
            if self._select_cols is None:
                return _Response([dict(r) for r in matched])
            return _Response([{c: r.get(c) for c in self._select_cols} for r in matched])

        if self._mode == "insert":
            assert self._payload is not None
            new_row = dict(self._payload)
            # Mirror DB defaults
            new_row.setdefault("released_at", datetime.now(timezone.utc).isoformat())
            new_row.setdefault("activated_at", None)
            new_row.setdefault("retired_at", None)
            new_row.setdefault("retired_reason", None)
            new_row.setdefault("flutter_repo_commit", None)
            new_row.setdefault("detail_index_url", None)
            new_row.setdefault("notes", None)
            self._store.append(new_row)
            return _Response([dict(new_row)])

        if self._mode == "update":
            assert self._payload is not None
            matched = self._matching_rows()
            for row in matched:
                row.update(self._payload)
            return _Response([dict(r) for r in matched])

        raise AssertionError("execute() called with no mode set")

    # --- helpers ---

    def _fresh(self) -> "FakeTable":
        # New chained-call object, sharing the underlying store
        return FakeTable(self._name, self._store)

    def _matching_rows(self) -> list[dict]:
        return [
            row for row in self._store
            if all(row.get(c) == v for c, v in self._filters)
        ]


class FakeClient:
    def __init__(self) -> None:
        self._tables: dict[str, list[dict]] = {}

    def table(self, name: str) -> FakeTable:
        store = self._tables.setdefault(name, [])
        return FakeTable(name, store)

    # Convenience for tests — direct access to the underlying rows
    def rows(self, name: str = DEFAULT_TABLE) -> list[dict]:
        return self._tables.setdefault(name, [])

    def seed(self, rows: list[dict], *, name: str = DEFAULT_TABLE) -> "FakeClient":
        store = self._tables.setdefault(name, [])
        store.extend(dict(r) for r in rows)
        return self


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client() -> FakeClient:
    return FakeClient()


@pytest.fixture
def fixed_now() -> datetime:
    return datetime(2026, 5, 13, 12, 0, 0, tzinfo=timezone.utc)


def _row(
    *,
    db_version: str = "2026.05.13.120000",
    state: str = "PENDING",
    channel: str = "ota_stable",
    flutter_repo_commit: Optional[str] = None,
    activated_at: Optional[str] = None,
    retired_at: Optional[str] = None,
    retired_reason: Optional[str] = None,
    bundled_in_app_versions: Optional[list[str]] = None,
    notes: Optional[str] = None,
    detail_index_url: Optional[str] = None,
    released_at: str = "2026-05-13T12:00:00Z",
) -> dict:
    return {
        "db_version": db_version,
        "state": state,
        "release_channel": channel,
        "released_at": released_at,
        "activated_at": activated_at,
        "retired_at": retired_at,
        "retired_reason": retired_reason,
        "bundled_in_app_versions": list(bundled_in_app_versions or []),
        "flutter_repo_commit": flutter_repo_commit,
        "detail_index_url": detail_index_url,
        "notes": notes,
    }


# ===========================================================================
# Parsing — CatalogRelease.from_row
# ===========================================================================


def test_from_row_parses_minimal_pending_row():
    rel = CatalogRelease.from_row(_row())
    assert rel.db_version == "2026.05.13.120000"
    assert rel.state == ReleaseState.PENDING
    assert rel.release_channel == ReleaseChannel.OTA_STABLE
    assert rel.released_at.tzinfo is not None
    assert rel.activated_at is None
    assert rel.bundled_in_app_versions == ()


def test_from_row_parses_iso_with_z_suffix_to_utc():
    rel = CatalogRelease.from_row(_row(released_at="2026-05-13T12:34:56Z"))
    assert rel.released_at == datetime(2026, 5, 13, 12, 34, 56, tzinfo=timezone.utc)


def test_from_row_rejects_missing_required_field():
    bad = _row()
    del bad["state"]
    with pytest.raises(InvalidReleaseFieldError, match="state"):
        CatalogRelease.from_row(bad)


def test_from_row_rejects_unknown_state():
    with pytest.raises(InvalidReleaseFieldError, match="state"):
        CatalogRelease.from_row(_row(state="ARCHIVED"))


def test_from_row_rejects_unknown_channel():
    with pytest.raises(InvalidReleaseFieldError, match="release_channel"):
        CatalogRelease.from_row(_row(channel="ota_beta"))


def test_from_row_rejects_unparseable_timestamp():
    with pytest.raises(InvalidReleaseFieldError, match="released_at"):
        CatalogRelease.from_row(_row(released_at="not-a-timestamp"))


def test_from_row_rejects_non_dict():
    with pytest.raises(InvalidReleaseFieldError):
        CatalogRelease.from_row("not a dict")  # type: ignore[arg-type]


def test_from_row_coerces_naive_datetime_to_utc():
    naive = datetime(2026, 5, 13, 12, 0, 0)  # no tz
    rel = CatalogRelease.from_row(_row(released_at=naive))  # type: ignore[arg-type]
    assert rel.released_at.tzinfo is timezone.utc


# ===========================================================================
# Read — get_release / list_active_releases / list_releases_by_state
# ===========================================================================


def test_get_release_returns_none_when_absent(client: FakeClient):
    assert get_release(client, "missing.version") is None


def test_get_release_returns_parsed_row(client: FakeClient):
    client.seed([_row(db_version="v1", state="ACTIVE",
                      activated_at="2026-05-13T12:00:00Z")])
    rel = get_release(client, "v1")
    assert rel is not None
    assert rel.state == ReleaseState.ACTIVE


def test_get_release_rejects_empty_db_version(client: FakeClient):
    with pytest.raises(InvalidReleaseFieldError):
        get_release(client, "")


def test_list_active_releases_filters_to_active_only(client: FakeClient):
    client.seed([
        _row(db_version="v_active", state="ACTIVE",
             activated_at="2026-05-13T12:00:00Z"),
        _row(db_version="v_pending", state="PENDING"),
        _row(db_version="v_retired", state="RETIRED",
             activated_at="2026-05-12T12:00:00Z",
             retired_at="2026-05-13T08:00:00Z",
             retired_reason="superseded"),
    ])
    actives = list_active_releases(client)
    assert {r.db_version for r in actives} == {"v_active"}


def test_list_releases_by_state_returns_empty_for_no_matches(client: FakeClient):
    client.seed([_row(db_version="v_pending", state="PENDING")])
    assert list_releases_by_state(client, ReleaseState.ACTIVE) == []


def test_list_releases_by_state_rejects_non_enum(client: FakeClient):
    with pytest.raises(InvalidReleaseFieldError):
        list_releases_by_state(client, "ACTIVE")  # type: ignore[arg-type]


# ===========================================================================
# Insert — insert_pending_release
# ===========================================================================


def test_insert_creates_row_in_pending_state(client: FakeClient):
    rel = insert_pending_release(
        client,
        db_version="v_new",
        release_channel=ReleaseChannel.OTA_STABLE,
    )
    assert rel.state == ReleaseState.PENDING
    assert rel.release_channel == ReleaseChannel.OTA_STABLE
    assert rel.db_version == "v_new"
    assert len(client.rows()) == 1


def test_insert_bundled_without_flutter_commit_raises(client: FakeClient):
    with pytest.raises(InvalidReleaseFieldError, match="flutter_repo_commit"):
        insert_pending_release(
            client,
            db_version="v_new",
            release_channel=ReleaseChannel.BUNDLED,
        )
    assert len(client.rows()) == 0  # no row written when validation fails


def test_insert_bundled_with_flutter_commit_succeeds(client: FakeClient):
    rel = insert_pending_release(
        client,
        db_version="v_bundled",
        release_channel=ReleaseChannel.BUNDLED,
        flutter_repo_commit="abc1234",
        bundled_in_app_versions=["1.0.0", "1.0.1"],
    )
    assert rel.flutter_repo_commit == "abc1234"
    assert rel.bundled_in_app_versions == ("1.0.0", "1.0.1")


def test_insert_duplicate_db_version_raises(client: FakeClient):
    client.seed([_row(db_version="v_dup", state="PENDING")])
    with pytest.raises(DuplicateReleaseError, match="v_dup"):
        insert_pending_release(
            client,
            db_version="v_dup",
            release_channel=ReleaseChannel.OTA_STABLE,
        )


def test_insert_rejects_empty_db_version(client: FakeClient):
    with pytest.raises(InvalidReleaseFieldError):
        insert_pending_release(
            client,
            db_version="",
            release_channel=ReleaseChannel.OTA_STABLE,
        )


def test_insert_rejects_non_enum_channel(client: FakeClient):
    with pytest.raises(InvalidReleaseFieldError):
        insert_pending_release(
            client,
            db_version="v",
            release_channel="ota_stable",  # type: ignore[arg-type]
        )


def test_insert_passes_optional_fields_through(client: FakeClient):
    rel = insert_pending_release(
        client,
        db_version="v",
        release_channel=ReleaseChannel.DEV,
        detail_index_url="shared/release_indexes/v/detail_index.json",
        notes="dev build #42",
    )
    assert rel.detail_index_url == "shared/release_indexes/v/detail_index.json"
    assert rel.notes == "dev build #42"


# ===========================================================================
# Transitions — happy paths
# ===========================================================================


def test_pending_to_validating(client: FakeClient):
    client.seed([_row(db_version="v", state="PENDING")])
    rel = transition_to_validating(client, "v")
    assert rel.state == ReleaseState.VALIDATING


def test_validating_to_active_sets_activated_at(client: FakeClient, fixed_now: datetime):
    client.seed([_row(db_version="v", state="VALIDATING")])
    rel = activate_release(client, "v", now=fixed_now)
    assert rel.state == ReleaseState.ACTIVE
    assert rel.activated_at == fixed_now


def test_validating_to_pending_rollback_no_notes(client: FakeClient):
    client.seed([_row(db_version="v", state="VALIDATING", notes="prior")])
    rel = rollback_to_pending(client, "v")
    assert rel.state == ReleaseState.PENDING
    # notes unchanged when not provided (we don't clear; we don't append)
    assert rel.notes == "prior"


def test_validating_to_pending_rollback_overwrites_notes(client: FakeClient):
    client.seed([_row(db_version="v", state="VALIDATING", notes="prior")])
    rel = rollback_to_pending(client, "v", notes="checksum mismatch in detail_index")
    assert rel.state == ReleaseState.PENDING
    assert rel.notes == "checksum mismatch in detail_index"


def test_active_to_retired_sets_retired_at_and_reason(
    client: FakeClient, fixed_now: datetime
):
    client.seed([_row(db_version="v", state="ACTIVE",
                      activated_at="2026-05-12T12:00:00Z")])
    rel = retire_release(client, "v", reason="superseded by v2", now=fixed_now)
    assert rel.state == ReleaseState.RETIRED
    assert rel.retired_at == fixed_now
    assert rel.retired_reason == "superseded by v2"


def test_retire_release_strips_whitespace_from_reason(
    client: FakeClient, fixed_now: datetime
):
    client.seed([_row(db_version="v", state="ACTIVE",
                      activated_at="2026-05-12T12:00:00Z")])
    rel = retire_release(client, "v", reason="  trimmed  ", now=fixed_now)
    assert rel.retired_reason == "trimmed"


# ===========================================================================
# Transitions — illegal paths (state machine guard fires BEFORE DB)
# ===========================================================================


def test_pending_to_active_directly_is_illegal(client: FakeClient):
    """Even for dev channel: no PENDING→ACTIVE shortcut. VALIDATING is mandatory."""
    client.seed([_row(db_version="v", state="PENDING")])
    with pytest.raises(IllegalStateTransitionError, match="VALIDATING"):
        activate_release(client, "v")
    # Row state unchanged
    assert client.rows()[0]["state"] == "PENDING"


def test_active_to_pending_is_illegal(client: FakeClient):
    """No rollback from ACTIVE. The only way out is RETIRED."""
    client.seed([_row(db_version="v", state="ACTIVE",
                      activated_at="2026-05-13T12:00:00Z")])
    with pytest.raises(IllegalStateTransitionError):
        rollback_to_pending(client, "v")


def test_retired_to_anything_is_illegal(client: FakeClient):
    """RETIRED is terminal. No revivals."""
    client.seed([_row(db_version="v", state="RETIRED",
                      activated_at="2026-05-12T12:00:00Z",
                      retired_at="2026-05-13T08:00:00Z",
                      retired_reason="end of life")])
    with pytest.raises(IllegalStateTransitionError):
        transition_to_validating(client, "v")
    with pytest.raises(IllegalStateTransitionError):
        activate_release(client, "v")
    with pytest.raises(IllegalStateTransitionError):
        retire_release(client, "v", reason="again")


def test_pending_to_retired_directly_is_illegal(client: FakeClient):
    client.seed([_row(db_version="v", state="PENDING")])
    with pytest.raises(IllegalStateTransitionError):
        retire_release(client, "v", reason="never validated")


def test_validating_to_retired_directly_is_illegal(client: FakeClient):
    client.seed([_row(db_version="v", state="VALIDATING")])
    with pytest.raises(IllegalStateTransitionError):
        retire_release(client, "v", reason="abandoned mid-validation")


# ===========================================================================
# Transitions — input validation
# ===========================================================================


def test_retire_rejects_empty_reason(client: FakeClient):
    client.seed([_row(db_version="v", state="ACTIVE",
                      activated_at="2026-05-13T12:00:00Z")])
    with pytest.raises(InvalidReleaseFieldError, match="reason"):
        retire_release(client, "v", reason="")
    # Row state unchanged — validation fired before DB call
    assert client.rows()[0]["state"] == "ACTIVE"


def test_retire_rejects_whitespace_only_reason(client: FakeClient):
    client.seed([_row(db_version="v", state="ACTIVE",
                      activated_at="2026-05-13T12:00:00Z")])
    with pytest.raises(InvalidReleaseFieldError):
        retire_release(client, "v", reason="   ")


def test_retire_rejects_non_string_reason(client: FakeClient):
    client.seed([_row(db_version="v", state="ACTIVE",
                      activated_at="2026-05-13T12:00:00Z")])
    with pytest.raises(InvalidReleaseFieldError):
        retire_release(client, "v", reason=None)  # type: ignore[arg-type]


def test_rollback_rejects_non_string_notes(client: FakeClient):
    client.seed([_row(db_version="v", state="VALIDATING")])
    with pytest.raises(InvalidReleaseFieldError):
        rollback_to_pending(client, "v", notes=42)  # type: ignore[arg-type]


# ===========================================================================
# Transitions — missing row → ReleaseNotFoundError
# ===========================================================================


def test_transition_on_missing_row_raises_not_found(client: FakeClient):
    """When the optimistic-lock UPDATE matches 0 rows AND the row truly
    doesn't exist, we raise ReleaseNotFoundError (not IllegalStateTransition)."""
    with pytest.raises(ReleaseNotFoundError):
        transition_to_validating(client, "ghost")


def test_activate_on_missing_row_raises_not_found(client: FakeClient):
    with pytest.raises(ReleaseNotFoundError):
        activate_release(client, "ghost")


def test_retire_on_missing_row_raises_not_found(client: FakeClient):
    with pytest.raises(ReleaseNotFoundError):
        retire_release(client, "ghost", reason="x")


# ===========================================================================
# Concurrency — optimistic-lock loss
# ===========================================================================


def test_transition_lost_race_raises_illegal_with_actual_state(client: FakeClient):
    """Row exists but state != expected from_state → IllegalStateTransitionError
    with the *actual* current state in the message (not the expected one).
    This is the disambiguation path that distinguishes 'row gone' from 'someone
    else moved it under us'."""
    # Row is already ACTIVE — but the caller assumes it's still VALIDATING
    client.seed([_row(db_version="v", state="ACTIVE",
                      activated_at="2026-05-13T12:00:00Z")])
    with pytest.raises(IllegalStateTransitionError, match="found state=ACTIVE"):
        activate_release(client, "v")


# ===========================================================================
# End-to-end — full happy lifecycle
# ===========================================================================


def test_full_lifecycle_pending_to_retired(client: FakeClient, fixed_now: datetime):
    """A single release walks the entire allowed path: PENDING → VALIDATING
    → ACTIVE → RETIRED. Each step persists; the final state is queryable."""
    rel = insert_pending_release(
        client,
        db_version="v_lifecycle",
        release_channel=ReleaseChannel.OTA_STABLE,
        notes="initial",
    )
    assert rel.state == ReleaseState.PENDING

    rel = transition_to_validating(client, "v_lifecycle")
    assert rel.state == ReleaseState.VALIDATING

    rel = activate_release(client, "v_lifecycle", now=fixed_now)
    assert rel.state == ReleaseState.ACTIVE
    assert rel.activated_at == fixed_now

    later = datetime(2026, 5, 14, 12, 0, 0, tzinfo=timezone.utc)
    rel = retire_release(client, "v_lifecycle", reason="superseded", now=later)
    assert rel.state == ReleaseState.RETIRED
    assert rel.retired_at == later
    assert rel.retired_reason == "superseded"

    # The retired row is still queryable
    fetched = get_release(client, "v_lifecycle")
    assert fetched is not None
    assert fetched.state == ReleaseState.RETIRED


def test_rollback_then_re_validate_works(client: FakeClient, fixed_now: datetime):
    """A failed validation goes back to PENDING, then can be re-validated
    and activated normally. Confirms the rollback path doesn't poison the row."""
    insert_pending_release(
        client,
        db_version="v_retry",
        release_channel=ReleaseChannel.OTA_STABLE,
    )
    transition_to_validating(client, "v_retry")
    rollback_to_pending(client, "v_retry", notes="dist checksum mismatch — retrying")

    fetched = get_release(client, "v_retry")
    assert fetched is not None
    assert fetched.state == ReleaseState.PENDING
    assert fetched.notes == "dist checksum mismatch — retrying"

    # Second attempt
    transition_to_validating(client, "v_retry")
    rel = activate_release(client, "v_retry", now=fixed_now)
    assert rel.state == ReleaseState.ACTIVE
