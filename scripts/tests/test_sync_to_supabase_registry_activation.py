"""Tests for P3.6b — registry activation in sync_to_supabase.py.

Covers the two-stage helper functions that bring a catalog_releases row
through PENDING -> VALIDATING (before manifest flip) -> ACTIVE (after).

Required scenarios (per ADR-0001 P3.6b sign-off):
  - Stage 1 retry from PENDING (row exists as PENDING) -> VALIDATING
  - Stage 1 retry from VALIDATING (already there) -> no-op
  - Stage 1 retry from ACTIVE (already past) -> no-op
  - Stage 1 from RETIRED -> LOUD FAILURE (do not resurrect)
  - Stage 1 happy path (row missing) -> insert PENDING -> VALIDATING
  - Stage 2 from VALIDATING -> ACTIVE
  - Stage 2 from ACTIVE -> no-op (idempotent)
  - Stage 2 from any other state -> raise (between-stage inconsistency)
  - Stage 2 row disappeared between stages -> raise
  - Log/print output makes state transitions visible
"""

from __future__ import annotations

import io
import os
import sys
from contextlib import redirect_stdout
from datetime import datetime, timezone
from typing import Any, Optional
import pytest

_scripts_dir = os.path.join(os.path.dirname(__file__), "..")
if _scripts_dir not in sys.path:
    sys.path.insert(0, os.path.abspath(_scripts_dir))

from sync_to_supabase import (
    _ensure_registry_active,
    _ensure_registry_validating,
)
from release_safety.registry import (
    DEFAULT_TABLE as REGISTRY_TABLE,
    ReleaseChannel,
    ReleaseState,
)


# ---------------------------------------------------------------------------
# Test double — minimal Supabase table client (insert/select/update with eq)
# ---------------------------------------------------------------------------


class _Response:
    def __init__(self, data: list[dict]) -> None:
        self.data = data


class FakeTable:
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
            matched = [r for r in self._store
                       if all(r.get(c) == v for c, v in self._filters)]
            if self._select_cols is None:
                return _Response([dict(r) for r in matched])
            return _Response([
                {c: r.get(c) for c in self._select_cols} for r in matched
            ])
        if self._mode == "insert":
            assert self._payload is not None
            new_row = dict(self._payload)
            new_row.setdefault("released_at", datetime.now(timezone.utc).isoformat())
            for nullable in ("activated_at", "retired_at", "retired_reason",
                             "flutter_repo_commit", "detail_index_url", "notes"):
                new_row.setdefault(nullable, None)
            new_row.setdefault("bundled_in_app_versions", [])
            self._store.append(new_row)
            return _Response([dict(new_row)])
        if self._mode == "update":
            assert self._payload is not None
            matched = [r for r in self._store
                       if all(r.get(c) == v for c, v in self._filters)]
            for row in matched:
                row.update(self._payload)
            return _Response([dict(r) for r in matched])
        raise AssertionError("execute() called with no mode set")

    def _fresh(self) -> "FakeTable":
        return FakeTable(self._name, self._store)


class FakeClient:
    def __init__(self) -> None:
        self._tables: dict[str, list[dict]] = {}

    def table(self, name: str) -> FakeTable:
        store = self._tables.setdefault(name, [])
        return FakeTable(name, store)

    def rows(self, table: str = REGISTRY_TABLE) -> list[dict]:
        return self._tables.setdefault(table, [])

    def seed(self, rows: list[dict], *, table: str = REGISTRY_TABLE) -> "FakeClient":
        store = self._tables.setdefault(table, [])
        store.extend(dict(r) for r in rows)
        return self


def _row(*, db_version: str, state: str,
         channel: str = "ota_stable",
         detail_index_url: Optional[str] = None,
         activated_at: Optional[str] = None,
         retired_at: Optional[str] = None,
         retired_reason: Optional[str] = None) -> dict:
    return {
        "db_version": db_version,
        "state": state,
        "release_channel": channel,
        "released_at": "2026-05-12T00:00:00Z",
        "activated_at": activated_at or (
            "2026-05-12T00:00:00Z" if state in ("ACTIVE", "RETIRED") else None
        ),
        "retired_at": retired_at,
        "retired_reason": retired_reason,
        "bundled_in_app_versions": [],
        "flutter_repo_commit": "abc" if channel == "bundled" else None,
        "detail_index_url": detail_index_url or f"v{db_version}/detail_index.json",
        "notes": None,
    }


@pytest.fixture
def client() -> FakeClient:
    return FakeClient()


# ===========================================================================
# Stage 1 — happy path: row missing -> insert PENDING -> VALIDATING
# ===========================================================================


def test_stage1_missing_row_inserts_pending_then_advances_to_validating(
    client: FakeClient,
):
    captured = io.StringIO()
    with redirect_stdout(captured):
        result = _ensure_registry_validating(
            client,
            db_version="2026.05.13.new",
            detail_index_url="v2026.05.13.new/detail_index.json",
        )

    assert result.state == ReleaseState.VALIDATING
    assert result.db_version == "2026.05.13.new"
    assert result.release_channel == ReleaseChannel.OTA_STABLE
    # Bundled_in_app_versions stays [] for ota_stable per sign-off
    assert result.bundled_in_app_versions == ()
    # detail_index_url propagated
    assert result.detail_index_url == "v2026.05.13.new/detail_index.json"

    # One row exists, now in VALIDATING
    assert len(client.rows()) == 1
    assert client.rows()[0]["state"] == "VALIDATING"

    # Log output shows the state transitions
    out = captured.getvalue()
    assert "no row found" in out
    assert "PENDING -> VALIDATING" in out
    assert "2026.05.13.new" in out


# ===========================================================================
# Stage 1 re-entry — row exists as PENDING
# ===========================================================================


def test_stage1_retry_from_pending_advances_to_validating(client: FakeClient):
    client.seed([_row(db_version="v1", state="PENDING")])

    captured = io.StringIO()
    with redirect_stdout(captured):
        result = _ensure_registry_validating(
            client, db_version="v1",
            detail_index_url="v1/detail_index.json",
        )

    assert result.state == ReleaseState.VALIDATING
    # Still one row (no duplicate insert)
    assert len(client.rows()) == 1
    out = captured.getvalue()
    assert "row exists as PENDING" in out
    assert "VALIDATING" in out


# ===========================================================================
# Stage 1 re-entry — row exists as VALIDATING (idempotent no-op)
# ===========================================================================


def test_stage1_retry_from_validating_is_noop(client: FakeClient):
    client.seed([_row(db_version="v1", state="VALIDATING")])

    captured = io.StringIO()
    with redirect_stdout(captured):
        result = _ensure_registry_validating(
            client, db_version="v1",
            detail_index_url="v1/detail_index.json",
        )

    assert result.state == ReleaseState.VALIDATING
    out = captured.getvalue()
    assert "already VALIDATING" in out
    assert "idempotent" in out.lower()


# ===========================================================================
# Stage 1 re-entry — row already ACTIVE (Stage 1 is no-op, Stage 2 will handle)
# ===========================================================================


def test_stage1_retry_from_active_is_noop(client: FakeClient):
    client.seed([_row(db_version="v1", state="ACTIVE")])

    captured = io.StringIO()
    with redirect_stdout(captured):
        result = _ensure_registry_validating(
            client, db_version="v1",
            detail_index_url="v1/detail_index.json",
        )

    assert result.state == ReleaseState.ACTIVE
    out = captured.getvalue()
    assert "already ACTIVE" in out


# ===========================================================================
# Stage 1 — RETIRED row -> LOUD FAILURE (do not resurrect)
# ===========================================================================


def test_stage1_retired_row_raises_loudly(client: FakeClient):
    """A RETIRED row must NEVER be silently revived. The audit trail recorded
    the retirement reason; bringing it back invisibly would erase that signal."""
    client.seed([
        _row(db_version="v_retired", state="RETIRED",
             activated_at="2026-05-01T00:00:00Z",
             retired_at="2026-05-10T00:00:00Z",
             retired_reason="end of life"),
    ])

    with pytest.raises(RuntimeError, match="RETIRED"):
        _ensure_registry_validating(
            client, db_version="v_retired",
            detail_index_url="v_retired/detail_index.json",
        )

    # Row state unchanged — we did NOT touch a RETIRED row
    assert client.rows()[0]["state"] == "RETIRED"


def test_stage1_retired_row_error_mentions_create_new_version_remedy(
    client: FakeClient,
):
    """The error message must point operators to the correct fix (new
    db_version), not just say 'no'."""
    client.seed([
        _row(db_version="v_retired", state="RETIRED",
             retired_at="2026-05-10T00:00:00Z",
             retired_reason="x"),
    ])
    with pytest.raises(RuntimeError, match="create a new db_version"):
        _ensure_registry_validating(
            client, db_version="v_retired",
            detail_index_url="v_retired/detail_index.json",
        )


# ===========================================================================
# Stage 2 — happy path: VALIDATING -> ACTIVE
# ===========================================================================


def test_stage2_validating_to_active(client: FakeClient):
    client.seed([_row(db_version="v1", state="VALIDATING")])

    captured = io.StringIO()
    with redirect_stdout(captured):
        result = _ensure_registry_active(client, db_version="v1")

    assert result.state == ReleaseState.ACTIVE
    assert result.activated_at is not None
    assert client.rows()[0]["state"] == "ACTIVE"
    out = captured.getvalue()
    assert "VALIDATING -> ACTIVE" in out


# ===========================================================================
# Stage 2 idempotency — ACTIVE row stays ACTIVE
# ===========================================================================


def test_stage2_active_row_is_idempotent_noop(client: FakeClient):
    """Re-running a successful sync should NOT touch an already-ACTIVE row."""
    client.seed([_row(db_version="v1", state="ACTIVE")])

    captured = io.StringIO()
    with redirect_stdout(captured):
        result = _ensure_registry_active(client, db_version="v1")

    assert result.state == ReleaseState.ACTIVE
    out = captured.getvalue()
    assert "already ACTIVE" in out
    assert "idempotent" in out.lower()


# ===========================================================================
# Stage 2 — between-stage inconsistencies raise loudly
# ===========================================================================


def test_stage2_row_disappeared_between_stages_raises(client: FakeClient):
    """If something deletes the row between Stage 1 and Stage 2, fail loudly."""
    # Note: row NOT seeded
    with pytest.raises(RuntimeError, match="disappeared"):
        _ensure_registry_active(client, db_version="v_gone")


def test_stage2_row_in_pending_raises(client: FakeClient):
    """Stage 2 should never see PENDING — Stage 1 would have advanced past
    it. A row in PENDING at Stage 2 = something went very wrong."""
    client.seed([_row(db_version="v1", state="PENDING")])
    with pytest.raises(RuntimeError, match="unexpected state"):
        _ensure_registry_active(client, db_version="v1")


def test_stage2_row_in_retired_raises(client: FakeClient):
    """Defensive: if the row was retired between Stage 1 and Stage 2,
    refuse to activate."""
    client.seed([
        _row(db_version="v1", state="RETIRED",
             retired_at="2026-05-10T00:00:00Z",
             retired_reason="x"),
    ])
    with pytest.raises(RuntimeError, match="unexpected state"):
        _ensure_registry_active(client, db_version="v1")


# ===========================================================================
# End-to-end — full happy walk through both stages
# ===========================================================================


def test_full_e2e_stage1_then_stage2_from_scratch(client: FakeClient):
    """Simulates the sync()-call sequence: Stage 1 (before manifest flip),
    then (manifest flip happens externally), then Stage 2."""
    # Stage 1: missing -> VALIDATING
    s1_result = _ensure_registry_validating(
        client, db_version="2026.05.14.fresh",
        detail_index_url="v2026.05.14.fresh/detail_index.json",
    )
    assert s1_result.state == ReleaseState.VALIDATING

    # (manifest flip would happen here in production)

    # Stage 2: VALIDATING -> ACTIVE
    s2_result = _ensure_registry_active(client, db_version="2026.05.14.fresh")
    assert s2_result.state == ReleaseState.ACTIVE
    assert s2_result.activated_at is not None


def test_full_e2e_re_run_after_stage1_completed(client: FakeClient):
    """Operator partially succeeded: Stage 1 finished, manifest didn't flip
    (network blip), operator re-runs. Stage 1 sees VALIDATING (no-op),
    manifest flips, Stage 2 advances. End state ACTIVE."""
    # Simulate prior partial run
    client.seed([_row(db_version="v1", state="VALIDATING")])

    # Second run
    s1 = _ensure_registry_validating(
        client, db_version="v1",
        detail_index_url="v1/detail_index.json",
    )
    assert s1.state == ReleaseState.VALIDATING  # no-op

    # Manifest flip happens here

    s2 = _ensure_registry_active(client, db_version="v1")
    assert s2.state == ReleaseState.ACTIVE


def test_full_e2e_re_run_after_full_success_is_pure_noop(client: FakeClient):
    """Operator re-runs sync on a fully-completed release. Both stages
    are no-ops; the row stays ACTIVE; no errors."""
    client.seed([_row(db_version="v1", state="ACTIVE")])

    s1 = _ensure_registry_validating(
        client, db_version="v1",
        detail_index_url="v1/detail_index.json",
    )
    assert s1.state == ReleaseState.ACTIVE  # Stage 1 detects ACTIVE -> no-op

    s2 = _ensure_registry_active(client, db_version="v1")
    assert s2.state == ReleaseState.ACTIVE  # Stage 2 detects ACTIVE -> no-op

    # DB row unchanged from seed (state still ACTIVE)
    assert client.rows()[0]["state"] == "ACTIVE"


# ===========================================================================
# Output requirements — clear state transition logging
# ===========================================================================


def test_log_output_includes_db_version_and_transition_arrow(client: FakeClient):
    """Per sign-off: audit/log output should clearly show registry state
    transitions. Each transition emits a line with the db_version + arrow."""
    captured = io.StringIO()
    with redirect_stdout(captured):
        _ensure_registry_validating(
            client, db_version="2026.05.14.log_test",
            detail_index_url="v.json",
        )
        _ensure_registry_active(client, db_version="2026.05.14.log_test")

    out = captured.getvalue()
    assert "2026.05.14.log_test" in out
    assert "PENDING -> VALIDATING" in out
    assert "VALIDATING -> ACTIVE" in out
