"""Catalog release registry — Python API for the catalog_releases table.

Implements ADR-0001 P3.2. Single source of truth for the live multi-version
release registry. Replaces direct SQL scattered across pipeline scripts
(P3.5 swaps protected_blobs from interim bundled∪dist to registry-driven).

Trust model
===========
- Strict state machine. Only these transitions are allowed:

    PENDING ──> VALIDATING ──> ACTIVE ──> RETIRED
                  │
                  └────> PENDING   (rollback after failed validation)

- No direct PENDING → ACTIVE (even for ``dev`` channel). VALIDATING is an
  explicit "protected but not yet live" phase; convenience does not justify
  weakening the state machine.
- No rollback from ACTIVE except → RETIRED. ACTIVE rows are visible to
  consumers; the only way "out" is a recorded retirement with reason.
- Client-side validation **mirrors** the DB CHECK constraints in
  ``supabase_schema.sql`` Section 8. Callers get a clear ``ValueError``
  before the DB rejects the row, but if a caller ever bypasses this layer
  the DB still enforces correctness.

Concurrency
===========
State-transition writes use an optimistic lock: every UPDATE filters on
both ``db_version`` and the *expected* current ``state``. If a concurrent
transition slipped in, the UPDATE affects 0 rows; we re-fetch and raise
``IllegalStateTransitionError`` with the actual current state.

Dependency injection
====================
All public functions take an opaque ``client`` (the Supabase Python
client). The module never constructs a client itself. This matches the
DI pattern in ``quarantine.py`` and ``delete_stale_version_dirs.py`` —
keeps the module unit-testable with a fake table double, and lets the
caller (release_full.sh wrapper) own credentials and connection lifecycle.

Public API
==========
    # Read
    list_active_releases(client) -> list[CatalogRelease]
    list_releases_by_state(client, state) -> list[CatalogRelease]
    get_release(client, db_version) -> CatalogRelease | None

    # Write (state transitions)
    insert_pending_release(client, *, db_version, release_channel, ...) -> CatalogRelease
    transition_to_validating(client, db_version) -> CatalogRelease
    activate_release(client, db_version, *, now=None) -> CatalogRelease
    rollback_to_pending(client, db_version, *, notes=None) -> CatalogRelease
    retire_release(client, db_version, *, reason, now=None) -> CatalogRelease

    # Errors
    RegistryError
    ReleaseNotFoundError
    DuplicateReleaseError
    IllegalStateTransitionError
    InvalidReleaseFieldError
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


DEFAULT_TABLE = "catalog_releases"


class ReleaseState(str, Enum):
    PENDING = "PENDING"
    VALIDATING = "VALIDATING"
    ACTIVE = "ACTIVE"
    RETIRED = "RETIRED"


class ReleaseChannel(str, Enum):
    BUNDLED = "bundled"
    OTA_STABLE = "ota_stable"
    DEV = "dev"


# Allowed state transitions. Anything not listed here is rejected
# client-side by ``_check_transition_allowed`` BEFORE the UPDATE fires.
_ALLOWED_TRANSITIONS: dict[ReleaseState, frozenset[ReleaseState]] = {
    ReleaseState.PENDING:    frozenset({ReleaseState.VALIDATING}),
    ReleaseState.VALIDATING: frozenset({ReleaseState.ACTIVE, ReleaseState.PENDING}),
    ReleaseState.ACTIVE:     frozenset({ReleaseState.RETIRED}),
    ReleaseState.RETIRED:    frozenset(),
}


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class RegistryError(Exception):
    """Base class for catalog_releases registry errors."""


class ReleaseNotFoundError(RegistryError):
    """Raised when a db_version is referenced that does not exist in the registry."""


class DuplicateReleaseError(RegistryError):
    """Raised when ``insert_pending_release`` is called for an existing db_version."""


class IllegalStateTransitionError(RegistryError):
    """Raised when a transition violates the state machine, OR when a
    concurrent transition won the optimistic-lock race."""


class InvalidReleaseFieldError(RegistryError, ValueError):
    """Raised when a field fails client-side validation that mirrors a DB CHECK
    constraint (e.g. empty retired_reason, bundled-without-flutter_repo_commit)."""


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CatalogRelease:
    """In-memory representation of one catalog_releases row.

    Frozen so callers can pass it around without mutation surprises.
    Use ``from_row`` to construct from Supabase response dicts (handles
    enum + timestamp parsing). Use ``to_insert_payload`` to serialize back
    to a dict the Supabase client will accept.
    """

    db_version: str
    state: ReleaseState
    release_channel: ReleaseChannel
    released_at: datetime
    activated_at: Optional[datetime]
    retired_at: Optional[datetime]
    retired_reason: Optional[str]
    bundled_in_app_versions: tuple[str, ...]
    flutter_repo_commit: Optional[str]
    detail_index_url: Optional[str]
    notes: Optional[str]

    @classmethod
    def from_row(cls, row: dict) -> "CatalogRelease":
        """Parse a Supabase row dict into a CatalogRelease.

        Raises ``InvalidReleaseFieldError`` if a required field is missing
        or has an unparseable type. This is a defensive parser — Supabase
        should always return well-formed rows for a healthy schema, but if
        the schema drifts we want a clear error, not an obscure KeyError.
        """
        if not isinstance(row, dict):
            raise InvalidReleaseFieldError(f"row is not a dict: {type(row).__name__}")

        try:
            db_version = row["db_version"]
            state_raw = row["state"]
            channel_raw = row["release_channel"]
            released_at_raw = row["released_at"]
        except KeyError as exc:
            raise InvalidReleaseFieldError(f"row missing required field: {exc.args[0]}") from None

        if not isinstance(db_version, str) or not db_version:
            raise InvalidReleaseFieldError(f"db_version must be non-empty str, got {db_version!r}")

        try:
            state = ReleaseState(state_raw)
        except ValueError:
            raise InvalidReleaseFieldError(f"unknown state {state_raw!r}") from None
        try:
            channel = ReleaseChannel(channel_raw)
        except ValueError:
            raise InvalidReleaseFieldError(f"unknown release_channel {channel_raw!r}") from None

        released_at = _parse_timestamp(released_at_raw, "released_at")
        activated_at = _parse_timestamp(row.get("activated_at"), "activated_at", allow_none=True)
        retired_at = _parse_timestamp(row.get("retired_at"), "retired_at", allow_none=True)

        bundled_versions_raw = row.get("bundled_in_app_versions") or []
        if not isinstance(bundled_versions_raw, (list, tuple)):
            raise InvalidReleaseFieldError(
                f"bundled_in_app_versions must be list/tuple, got {type(bundled_versions_raw).__name__}"
            )
        bundled_versions = tuple(str(v) for v in bundled_versions_raw)

        return cls(
            db_version=db_version,
            state=state,
            release_channel=channel,
            released_at=released_at,
            activated_at=activated_at,
            retired_at=retired_at,
            retired_reason=row.get("retired_reason"),
            bundled_in_app_versions=bundled_versions,
            flutter_repo_commit=row.get("flutter_repo_commit"),
            detail_index_url=row.get("detail_index_url"),
            notes=row.get("notes"),
        )


def _parse_timestamp(value: Any, field_name: str, *, allow_none: bool = False) -> Optional[datetime]:
    """Parse a Supabase timestamp value into a tz-aware datetime.

    Supabase returns ISO-8601 strings (often with 'Z' suffix). Accepts a
    ``datetime`` directly too (test doubles may pass one through).
    """
    if value is None:
        if allow_none:
            return None
        raise InvalidReleaseFieldError(f"{field_name} is required, got None")
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        normalized = value.replace("Z", "+00:00") if value.endswith("Z") else value
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            raise InvalidReleaseFieldError(f"{field_name} is not ISO-8601: {value!r}") from None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    raise InvalidReleaseFieldError(f"{field_name} has unsupported type {type(value).__name__}")


# ---------------------------------------------------------------------------
# Read API
# ---------------------------------------------------------------------------


def list_active_releases(client, *, table: str = DEFAULT_TABLE) -> list[CatalogRelease]:
    """Return every row whose state == ACTIVE. Hot path for protected-set
    computation (P3.5). Backed by ``idx_catalog_releases_active`` partial index."""
    return list_releases_by_state(client, ReleaseState.ACTIVE, table=table)


def list_releases_by_state(
    client, state: ReleaseState, *, table: str = DEFAULT_TABLE
) -> list[CatalogRelease]:
    """Return every row matching ``state``. Order is unspecified."""
    if not isinstance(state, ReleaseState):
        raise InvalidReleaseFieldError(f"state must be ReleaseState, got {type(state).__name__}")
    response = (
        client.table(table)
        .select("*")
        .eq("state", state.value)
        .execute()
    )
    rows = getattr(response, "data", None) or []
    return [CatalogRelease.from_row(r) for r in rows]


def get_release(
    client, db_version: str, *, table: str = DEFAULT_TABLE
) -> Optional[CatalogRelease]:
    """Return the row for ``db_version`` or ``None`` if it does not exist."""
    if not isinstance(db_version, str) or not db_version:
        raise InvalidReleaseFieldError(f"db_version must be non-empty str, got {db_version!r}")
    response = (
        client.table(table)
        .select("*")
        .eq("db_version", db_version)
        .execute()
    )
    rows = getattr(response, "data", None) or []
    if not rows:
        return None
    if len(rows) > 1:
        raise RegistryError(
            f"db_version={db_version!r} returned {len(rows)} rows — primary key violation"
        )
    return CatalogRelease.from_row(rows[0])


# ---------------------------------------------------------------------------
# Write API — state transitions
# ---------------------------------------------------------------------------


def insert_pending_release(
    client,
    *,
    db_version: str,
    release_channel: ReleaseChannel,
    bundled_in_app_versions: Optional[list[str]] = None,
    flutter_repo_commit: Optional[str] = None,
    detail_index_url: Optional[str] = None,
    notes: Optional[str] = None,
    table: str = DEFAULT_TABLE,
) -> CatalogRelease:
    """Insert a new row in PENDING state.

    Client-side validation mirrors the DB CHECK constraints:
      - ``db_version`` must be non-empty
      - ``release_channel`` must be a ``ReleaseChannel`` enum member
      - if channel == bundled, ``flutter_repo_commit`` is REQUIRED
        (mirrors CHECK ``bundled_requires_flutter_commit``)
      - duplicate db_version raises ``DuplicateReleaseError`` (TOCTOU-tolerated;
        the DB primary key is the authoritative guard)
    """
    if not isinstance(db_version, str) or not db_version:
        raise InvalidReleaseFieldError(f"db_version must be non-empty str, got {db_version!r}")
    if not isinstance(release_channel, ReleaseChannel):
        raise InvalidReleaseFieldError(
            f"release_channel must be ReleaseChannel, got {type(release_channel).__name__}"
        )
    if release_channel == ReleaseChannel.BUNDLED and not flutter_repo_commit:
        raise InvalidReleaseFieldError(
            "release_channel='bundled' requires flutter_repo_commit (mirrors DB CHECK)"
        )

    existing = get_release(client, db_version, table=table)
    if existing is not None:
        raise DuplicateReleaseError(
            f"db_version={db_version!r} already exists (state={existing.state.value})"
        )

    payload: dict[str, Any] = {
        "db_version": db_version,
        "state": ReleaseState.PENDING.value,
        "release_channel": release_channel.value,
        "bundled_in_app_versions": list(bundled_in_app_versions or []),
    }
    if flutter_repo_commit is not None:
        payload["flutter_repo_commit"] = flutter_repo_commit
    if detail_index_url is not None:
        payload["detail_index_url"] = detail_index_url
    if notes is not None:
        payload["notes"] = notes

    response = client.table(table).insert(payload).execute()
    rows = getattr(response, "data", None) or []
    if not rows:
        raise RegistryError(f"insert for db_version={db_version!r} returned no rows")
    return CatalogRelease.from_row(rows[0])


def transition_to_validating(
    client, db_version: str, *, table: str = DEFAULT_TABLE
) -> CatalogRelease:
    """Transition PENDING → VALIDATING. No timestamp change.

    Use VALIDATING as the explicit 'protected but not yet live' phase
    while the activation pipeline does its work.
    """
    return _transition(
        client,
        db_version=db_version,
        from_state=ReleaseState.PENDING,
        to_state=ReleaseState.VALIDATING,
        extra_fields={},
        table=table,
    )


def activate_release(
    client,
    db_version: str,
    *,
    now: Optional[datetime] = None,
    table: str = DEFAULT_TABLE,
) -> CatalogRelease:
    """Transition VALIDATING → ACTIVE and set ``activated_at``.

    The DB CHECK ``activated_at_set_iff_active_or_retired`` requires
    activated_at to be NOT NULL once state ∈ {ACTIVE, RETIRED}. We set
    it client-side (not via DB default) so the timestamp recorded matches
    the operator's clock used by the rest of the release pipeline.

    ``now`` parameter exists for deterministic tests; production callers
    should leave it as None.
    """
    activation_ts = (now or datetime.now(timezone.utc))
    return _transition(
        client,
        db_version=db_version,
        from_state=ReleaseState.VALIDATING,
        to_state=ReleaseState.ACTIVE,
        extra_fields={"activated_at": _format_timestamp(activation_ts)},
        table=table,
    )


def rollback_to_pending(
    client,
    db_version: str,
    *,
    notes: Optional[str] = None,
    table: str = DEFAULT_TABLE,
) -> CatalogRelease:
    """Transition VALIDATING → PENDING. The only allowed rollback.

    Use when a release fails validation. ``notes``, if provided, OVERWRITES
    the existing ``notes`` column (we don't append — read-modify-write is
    not atomic, and the audit_log is the source of truth for sequence).
    """
    extra: dict[str, Any] = {}
    if notes is not None:
        if not isinstance(notes, str):
            raise InvalidReleaseFieldError(f"notes must be str, got {type(notes).__name__}")
        extra["notes"] = notes
    return _transition(
        client,
        db_version=db_version,
        from_state=ReleaseState.VALIDATING,
        to_state=ReleaseState.PENDING,
        extra_fields=extra,
        table=table,
    )


def retire_release(
    client,
    db_version: str,
    *,
    reason: str,
    now: Optional[datetime] = None,
    table: str = DEFAULT_TABLE,
) -> CatalogRelease:
    """Transition ACTIVE → RETIRED. Sets ``retired_at`` + ``retired_reason``.

    ``reason`` is REQUIRED and must be non-empty after stripping. This
    mirrors the DB CHECK ``retired_fields_consistent``: a RETIRED row must
    record WHY it was retired (audit-grade evidence). We reject empty
    reasons before the DB call so callers get a clear error path.
    """
    if not isinstance(reason, str) or not reason.strip():
        raise InvalidReleaseFieldError(
            "retire_release requires non-empty reason (mirrors DB CHECK retired_fields_consistent)"
        )
    retirement_ts = (now or datetime.now(timezone.utc))
    return _transition(
        client,
        db_version=db_version,
        from_state=ReleaseState.ACTIVE,
        to_state=ReleaseState.RETIRED,
        extra_fields={
            "retired_at": _format_timestamp(retirement_ts),
            "retired_reason": reason.strip(),
        },
        table=table,
    )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _transition(
    client,
    *,
    db_version: str,
    from_state: ReleaseState,
    to_state: ReleaseState,
    extra_fields: dict[str, Any],
    table: str,
) -> CatalogRelease:
    """Optimistic-lock state transition.

    UPDATE filters on (db_version, current_state). If 0 rows updated, we
    re-fetch to disambiguate "row missing" from "lost the optimistic-lock
    race" and raise the corresponding error.
    """
    if not isinstance(db_version, str) or not db_version:
        raise InvalidReleaseFieldError(f"db_version must be non-empty str, got {db_version!r}")
    _check_transition_allowed(from_state, to_state)

    payload = {"state": to_state.value, **extra_fields}
    response = (
        client.table(table)
        .update(payload)
        .eq("db_version", db_version)
        .eq("state", from_state.value)
        .execute()
    )
    rows = getattr(response, "data", None) or []
    if not rows:
        # Row was missing OR state changed under us. Re-fetch to disambiguate.
        current = get_release(client, db_version, table=table)
        if current is None:
            raise ReleaseNotFoundError(f"db_version={db_version!r} does not exist")
        raise IllegalStateTransitionError(
            f"db_version={db_version!r}: expected state={from_state.value}, "
            f"found state={current.state.value} — concurrent transition?"
        )
    return CatalogRelease.from_row(rows[0])


def _check_transition_allowed(from_state: ReleaseState, to_state: ReleaseState) -> None:
    """Raise IllegalStateTransitionError if the transition is not in the allow-list."""
    allowed = _ALLOWED_TRANSITIONS.get(from_state, frozenset())
    if to_state not in allowed:
        raise IllegalStateTransitionError(
            f"transition {from_state.value} → {to_state.value} is not allowed; "
            f"from {from_state.value}, only {sorted(s.value for s in allowed) or '(none)'} permitted"
        )


def _format_timestamp(ts: datetime) -> str:
    """Serialize datetime to ISO-8601 with 'Z' UTC suffix.

    Supabase accepts ISO-8601 strings for timestamptz columns. We always
    coerce to UTC to avoid surprises from caller-local timezones.
    """
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


__all__ = [
    "DEFAULT_TABLE",
    "ReleaseState",
    "ReleaseChannel",
    "CatalogRelease",
    "RegistryError",
    "ReleaseNotFoundError",
    "DuplicateReleaseError",
    "IllegalStateTransitionError",
    "InvalidReleaseFieldError",
    "list_active_releases",
    "list_releases_by_state",
    "get_release",
    "insert_pending_release",
    "transition_to_validating",
    "activate_release",
    "rollback_to_pending",
    "retire_release",
]
