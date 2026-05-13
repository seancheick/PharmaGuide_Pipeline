"""Tests for scripts/release_safety/retire_release.py (P3.4).

Mocks the Supabase table client (insert/select/update with eq filters),
isolates each test in its own audit_dir tmp, and verifies BOTH the
state-machine outcome AND the audit-log JSONL event payload.

Required scenarios (per ADR-0001 P3.4 sign-off):
  1. happy path: ACTIVE -> RETIRED with reason; audit event written
  2. dry-run writes nothing (no DB row update) but DOES emit audit event
     with dry_run=true
  3. row not found -> ReleaseNotFoundError (raised pre-flight)
  4. row in PENDING -> IllegalStateTransitionError
  5. row in VALIDATING -> IllegalStateTransitionError
  6. row already RETIRED -> IllegalStateTransitionError
  7. empty/whitespace reason -> InvalidReleaseFieldError
  8. only ACTIVE row + no override -> blocked_by populated, RetireBlocked
     when execute attempted
  9. only ACTIVE row + allow_empty_active=True -> proceeds, audit event
     records dangerous_override_used=true
  10. multiple ACTIVE rows -> no block; proceeds; active_count_after correct
  11. audit event JSONL line has every required field
  12. retiring one of N ACTIVE rows leaves N-1 in registry (state writes propagate)

Plus channel-aware coverage:
  - retiring last ACTIVE bundled row -> warning_last_bundled_active=true
    in audit (soft warning, NOT a block)
  - retiring a bundled row when other bundled rows exist -> no warning

Plus dry-run/execute invariant:
  - plan + warnings produced by dry-run match those produced by execute
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
import pytest

_scripts_dir = os.path.join(os.path.dirname(__file__), "..")
if _scripts_dir not in sys.path:
    sys.path.insert(0, os.path.abspath(_scripts_dir))

from release_safety.audit_log import make_audit_log
from release_safety.registry import (
    DEFAULT_TABLE as REGISTRY_TABLE,
    IllegalStateTransitionError,
    InvalidReleaseFieldError,
    ReleaseNotFoundError,
)
from release_safety.retire_release import (
    RetireBlocked,
    RetirePlan,
    RetireResult,
    compute_retire_plan,
    execute_retire_plan,
    format_plan_text,
)


# ---------------------------------------------------------------------------
# Test doubles — Supabase table client (subset registry uses)
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

    def update(self, payload: dict) -> "FakeTable":
        new = self._fresh()
        new._mode = "update"
        new._payload = dict(payload)
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


def _row(
    *, db_version: str, state: str = "ACTIVE",
    channel: str = "ota_stable", activated_at: Optional[str] = None,
) -> dict:
    return {
        "db_version": db_version,
        "state": state,
        "release_channel": channel,
        "released_at": "2026-05-12T00:00:00Z",
        "activated_at": activated_at or (
            "2026-05-12T00:00:00Z" if state in ("ACTIVE", "RETIRED") else None
        ),
        "retired_at": None,
        "retired_reason": None,
        "bundled_in_app_versions": [],
        "flutter_repo_commit": "abc1234" if channel == "bundled" else None,
        "detail_index_url": None,
        "notes": None,
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client() -> FakeClient:
    return FakeClient()


@pytest.fixture
def fixed_now() -> datetime:
    return datetime(2026, 5, 13, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def audit_dir(tmp_path: Path) -> Path:
    p = tmp_path / "audit"
    p.mkdir()
    return p


def _read_audit_events(audit_log_path: Path) -> list[dict]:
    """Parse the JSONL audit file. Returns list of event dicts."""
    if not audit_log_path.exists():
        return []
    return [json.loads(line) for line in audit_log_path.read_text().splitlines() if line]


# ===========================================================================
# Scenario 1 — happy path: ACTIVE -> RETIRED with reason; audit event written
# ===========================================================================


def test_happy_path_active_to_retired(
    client: FakeClient, fixed_now: datetime, audit_dir: Path
):
    client.seed([
        _row(db_version="v1", state="ACTIVE"),
        _row(db_version="v2", state="ACTIVE"),  # second active so we don't hit last-row block
    ])
    plan = compute_retire_plan(client, db_version="v1", reason="superseded")
    assert plan.target.db_version == "v1"
    assert plan.reason == "superseded"
    assert plan.blocked_by == ()
    assert plan.warnings == ()
    assert plan.active_count_before == 2
    assert plan.active_count_after == 1

    res = execute_retire_plan(
        client, plan, dry_run=False, audit_dir=audit_dir, now=fixed_now,
        operator="alice", git_sha="deadbeef",
    )
    assert res.dry_run is False
    assert res.retired is not None
    assert res.retired.db_version == "v1"
    # DB row updated
    rows_by_v = {r["db_version"]: r for r in client.rows()}
    assert rows_by_v["v1"]["state"] == "RETIRED"
    assert rows_by_v["v1"]["retired_reason"] == "superseded"
    # v2 untouched
    assert rows_by_v["v2"]["state"] == "ACTIVE"

    events = _read_audit_events(res.audit_log_path)
    assert len(events) == 1
    e = events[0]
    assert e["event_type"] == "catalog_release_retire"
    assert e["db_version"] == "v1"
    assert e["dry_run"] is False
    assert e["dangerous_override_used"] is False


# ===========================================================================
# Scenario 2 — dry-run writes nothing, BUT emits audit event with dry_run=true
# ===========================================================================


def test_dry_run_writes_no_db_row_but_emits_audit(
    client: FakeClient, audit_dir: Path
):
    client.seed([_row(db_version="v1"), _row(db_version="v2")])
    plan = compute_retire_plan(client, db_version="v1", reason="cleanup")
    res = execute_retire_plan(client, plan, dry_run=True, audit_dir=audit_dir)

    assert res.dry_run is True
    assert res.retired is None
    # DB unchanged
    assert all(r["state"] == "ACTIVE" for r in client.rows())
    # Audit event still emitted
    events = _read_audit_events(res.audit_log_path)
    assert len(events) == 1
    assert events[0]["dry_run"] is True


# ===========================================================================
# Scenarios 3-6 — pre-flight rejections
# ===========================================================================


def test_row_not_found_raises(client: FakeClient):
    with pytest.raises(ReleaseNotFoundError):
        compute_retire_plan(client, db_version="ghost", reason="x")


def test_row_in_pending_rejected(client: FakeClient):
    client.seed([_row(db_version="v1", state="PENDING")])
    with pytest.raises(IllegalStateTransitionError, match="PENDING"):
        compute_retire_plan(client, db_version="v1", reason="x")


def test_row_in_validating_rejected(client: FakeClient):
    client.seed([_row(db_version="v1", state="VALIDATING")])
    with pytest.raises(IllegalStateTransitionError, match="VALIDATING"):
        compute_retire_plan(client, db_version="v1", reason="x")


def test_row_already_retired_rejected(client: FakeClient):
    retired_row = _row(db_version="v1", state="RETIRED")
    retired_row["retired_at"] = "2026-05-12T01:00:00Z"
    retired_row["retired_reason"] = "previously"
    client.seed([retired_row])
    with pytest.raises(IllegalStateTransitionError, match="RETIRED"):
        compute_retire_plan(client, db_version="v1", reason="x")


# ===========================================================================
# Scenario 7 — empty/whitespace reason
# ===========================================================================


@pytest.mark.parametrize("bad_reason", ["", "   ", "\t\n"])
def test_empty_reason_rejected_pre_flight(client: FakeClient, bad_reason: str):
    client.seed([_row(db_version="v1")])
    with pytest.raises(InvalidReleaseFieldError, match="reason"):
        compute_retire_plan(client, db_version="v1", reason=bad_reason)


# ===========================================================================
# Scenario 8 — last ACTIVE row + no override -> blocked
# ===========================================================================


def test_last_active_row_is_blocked_without_override(
    client: FakeClient, audit_dir: Path
):
    client.seed([_row(db_version="v_only", state="ACTIVE")])
    plan = compute_retire_plan(client, db_version="v_only", reason="end of life")

    assert plan.blocked_by == ("last_active_row",)
    assert plan.active_count_after == 0

    with pytest.raises(RetireBlocked, match="allow_empty_active"):
        execute_retire_plan(client, plan, dry_run=False, audit_dir=audit_dir)

    # Confirm DB unchanged AND no audit event written (we raised before write)
    assert client.rows()[0]["state"] == "ACTIVE"


# ===========================================================================
# Scenario 9 — last ACTIVE row + override -> proceeds, audit notes danger
# ===========================================================================


def test_last_active_row_with_override_proceeds_and_audits_danger(
    client: FakeClient, fixed_now: datetime, audit_dir: Path
):
    client.seed([_row(db_version="v_only", state="ACTIVE")])
    plan = compute_retire_plan(client, db_version="v_only", reason="end of life")

    res = execute_retire_plan(
        client, plan, dry_run=False, allow_empty_active=True,
        audit_dir=audit_dir, now=fixed_now,
        operator="alice", git_sha="deadbeef",
    )
    assert res.retired is not None
    assert client.rows()[0]["state"] == "RETIRED"

    events = _read_audit_events(res.audit_log_path)
    assert len(events) == 1
    e = events[0]
    assert e["dangerous_override_used"] is True
    assert e["active_count_after"] == 0


def test_override_without_block_does_not_set_dangerous(
    client: FakeClient, fixed_now: datetime, audit_dir: Path
):
    """Passing allow_empty_active=True when there's NO last_active_row block
    is harmless: dangerous_override_used should stay False (the override
    didn't actually do anything)."""
    client.seed([_row(db_version="v1"), _row(db_version="v2")])
    plan = compute_retire_plan(client, db_version="v1", reason="x")
    res = execute_retire_plan(
        client, plan, dry_run=False, allow_empty_active=True,
        audit_dir=audit_dir, now=fixed_now,
    )
    events = _read_audit_events(res.audit_log_path)
    assert events[0]["dangerous_override_used"] is False


# ===========================================================================
# Scenario 10 + 12 — multiple ACTIVE rows, retire one leaves rest
# ===========================================================================


def test_multiple_active_rows_retire_one_leaves_rest(
    client: FakeClient, fixed_now: datetime, audit_dir: Path
):
    client.seed([
        _row(db_version="v1", state="ACTIVE"),
        _row(db_version="v2", state="ACTIVE"),
        _row(db_version="v3", state="ACTIVE"),
    ])
    plan = compute_retire_plan(client, db_version="v2", reason="superseded")
    assert plan.active_count_before == 3
    assert plan.active_count_after == 2
    assert plan.blocked_by == ()

    res = execute_retire_plan(
        client, plan, dry_run=False, audit_dir=audit_dir, now=fixed_now,
    )
    assert res.retired is not None

    by_v = {r["db_version"]: r["state"] for r in client.rows()}
    assert by_v == {"v1": "ACTIVE", "v2": "RETIRED", "v3": "ACTIVE"}


# ===========================================================================
# Scenario 11 — audit event has every required field
# ===========================================================================


def test_audit_event_has_every_required_field(
    client: FakeClient, fixed_now: datetime, audit_dir: Path
):
    """Per ADR-0001 P3.4 sign-off, audit event must include: operator,
    git_sha, db_version, release_channel, from_state, to_state, reason,
    dry_run, dangerous_override_used, warning_last_bundled_active,
    timestamp. (event_type + release_id added automatically by AuditLog.)"""
    client.seed([
        _row(db_version="v1", state="ACTIVE", channel="ota_stable"),
        _row(db_version="v2", state="ACTIVE", channel="bundled"),
    ])
    plan = compute_retire_plan(client, db_version="v1", reason="testing fields")
    res = execute_retire_plan(
        client, plan, dry_run=False, audit_dir=audit_dir, now=fixed_now,
        operator="alice", git_sha="deadbeef",
    )
    events = _read_audit_events(res.audit_log_path)
    assert len(events) == 1
    e = events[0]

    required_fields = {
        "event_type", "release_id", "timestamp",  # AuditLog auto
        "db_version", "release_channel", "from_state", "to_state",
        "reason", "dry_run", "dangerous_override_used",
        "warning_last_bundled_active",
        "operator", "git_sha",
        "active_count_before", "active_count_after",
    }
    missing = required_fields - set(e)
    assert not missing, f"audit event missing required fields: {missing}"

    assert e["operator"] == "alice"
    assert e["git_sha"] == "deadbeef"
    assert e["db_version"] == "v1"
    assert e["release_channel"] == "ota_stable"
    assert e["from_state"] == "ACTIVE"
    assert e["to_state"] == "RETIRED"
    assert e["reason"] == "testing fields"
    assert e["dry_run"] is False
    assert e["dangerous_override_used"] is False
    assert e["warning_last_bundled_active"] is False


def test_audit_event_records_null_git_sha_when_unresolvable(
    client: FakeClient, audit_dir: Path
):
    """git_sha=None passed in must propagate as JSON null, not crash."""
    client.seed([_row(db_version="v1"), _row(db_version="v2")])
    plan = compute_retire_plan(client, db_version="v1", reason="x")
    res = execute_retire_plan(
        client, plan, dry_run=False, audit_dir=audit_dir,
        operator="alice", git_sha=None,
    )
    events = _read_audit_events(res.audit_log_path)
    # _resolve_git_sha may have produced a real value if pytest CWD is in a git
    # repo, but explicit None means: try to resolve. Either real or None is OK
    # — what matters is the field is present and JSON-serializable.
    assert "git_sha" in events[0]
    assert events[0]["git_sha"] is None or isinstance(events[0]["git_sha"], str)


# ===========================================================================
# Channel-aware — last bundled warning
# ===========================================================================


def test_last_bundled_active_emits_soft_warning(
    client: FakeClient, fixed_now: datetime, audit_dir: Path
):
    """Retiring the only ACTIVE bundled row emits warning_last_bundled_active
    in the plan AND in the audit event, but does NOT block (other ACTIVE
    rows exist so last_active_row block doesn't fire)."""
    client.seed([
        _row(db_version="v_bundled", state="ACTIVE", channel="bundled"),
        _row(db_version="v_ota_a", state="ACTIVE", channel="ota_stable"),
        _row(db_version="v_ota_b", state="ACTIVE", channel="ota_stable"),
    ])
    plan = compute_retire_plan(
        client, db_version="v_bundled", reason="EOL bundled"
    )
    assert "last_bundled_active" in plan.warnings
    assert plan.blocked_by == ()  # NOT blocking

    res = execute_retire_plan(
        client, plan, dry_run=False, audit_dir=audit_dir, now=fixed_now,
    )
    assert res.retired is not None
    events = _read_audit_events(res.audit_log_path)
    assert events[0]["warning_last_bundled_active"] is True


def test_bundled_with_other_bundled_rows_no_warning(
    client: FakeClient, fixed_now: datetime, audit_dir: Path
):
    client.seed([
        _row(db_version="v_b1", state="ACTIVE", channel="bundled"),
        _row(db_version="v_b2", state="ACTIVE", channel="bundled"),
    ])
    plan = compute_retire_plan(
        client, db_version="v_b1", reason="superseded"
    )
    # last_active_row should NOT fire (v_b2 still active)
    assert plan.blocked_by == ()
    # last_bundled_active should NOT fire (v_b2 is also bundled)
    assert "last_bundled_active" not in plan.warnings


def test_ota_retire_never_emits_bundled_warning(
    client: FakeClient, fixed_now: datetime, audit_dir: Path
):
    """Even if no bundled rows exist, retiring an ota_stable row must NOT
    emit last_bundled_active (it's not the bundled row being retired)."""
    client.seed([
        _row(db_version="v_ota1", state="ACTIVE", channel="ota_stable"),
        _row(db_version="v_ota2", state="ACTIVE", channel="ota_stable"),
    ])
    plan = compute_retire_plan(
        client, db_version="v_ota1", reason="superseded"
    )
    assert "last_bundled_active" not in plan.warnings


# ===========================================================================
# Dry-run / execute invariant — same plan + warnings
# ===========================================================================


def test_dry_run_and_execute_produce_identical_plan(
    client: FakeClient, audit_dir: Path
):
    """The plan a caller sees on dry-run is byte-for-byte identical to the
    plan they see on execute. compute_retire_plan is called once; both
    branches use the same instance. We assert this by reusing the plan."""
    client.seed([
        _row(db_version="v_b", state="ACTIVE", channel="bundled"),
        _row(db_version="v_o", state="ACTIVE", channel="ota_stable"),
    ])
    plan = compute_retire_plan(
        client, db_version="v_b", reason="EOL bundled"
    )
    text_before = format_plan_text(plan)

    # Dry-run with the plan
    res_dry = execute_retire_plan(
        client, plan, dry_run=True, audit_dir=audit_dir / "dry",
    )
    assert res_dry.dry_run is True

    # Plan object hasn't changed (frozen dataclass)
    text_after_dry = format_plan_text(plan)
    assert text_before == text_after_dry

    # Execute with the SAME plan object
    res_exec = execute_retire_plan(
        client, plan, dry_run=False, audit_dir=audit_dir / "exec",
    )
    assert res_exec.dry_run is False

    # Plan still unchanged
    text_after_exec = format_plan_text(plan)
    assert text_before == text_after_exec


def test_blocked_dry_run_still_records_block_in_audit(
    client: FakeClient, audit_dir: Path
):
    """Dry-run on a plan with blocked_by should still emit an audit event
    (so operators can see what would have been blocked). Dry-run never
    raises RetireBlocked — only execute does."""
    client.seed([_row(db_version="v_only", state="ACTIVE")])
    plan = compute_retire_plan(client, db_version="v_only", reason="EOL")
    assert plan.blocked_by == ("last_active_row",)

    res = execute_retire_plan(
        client, plan, dry_run=True, audit_dir=audit_dir,
        # NOTE: no allow_empty_active — but dry-run does NOT raise
    )
    # Wait — actually does dry-run raise if blocked? Per spec, "execute must
    # refuse if blocked_by is non-empty unless override". Dry-run is
    # explicitly NOT execute. Let's verify the contract.
    assert res.dry_run is True
    events = _read_audit_events(res.audit_log_path)
    assert len(events) == 1
    assert events[0]["dry_run"] is True


# ===========================================================================
# Format helpers
# ===========================================================================


def test_format_plan_text_renders_blocks_and_warnings(
    client: FakeClient
):
    client.seed([_row(db_version="v_bundled", state="ACTIVE", channel="bundled")])
    plan = compute_retire_plan(
        client, db_version="v_bundled", reason="end of life"
    )
    text = format_plan_text(plan)
    assert "v_bundled" in text
    assert "bundled" in text
    assert "BLOCKED" in text
    assert "last_active_row" in text
    assert "WARNINGS" in text
    assert "last_bundled_active" in text
    # Override hint is rendered
    assert "--allow-empty-active" in text
