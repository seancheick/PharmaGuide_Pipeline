"""Quarantine primitive — soft-delete + recovery for orphaned detail blobs.

Implements ADR-0001 P2 (the quarantine half — sweeper lives in
``quarantine_sweeper.py``). This module provides the move-to-quarantine
operation that replaces hard-delete in cleanup_orphan_blobs_with_gates,
plus the recovery operation that restores quarantined blobs to active
storage within the 30-day TTL window.

Why quarantine
==============
P1 prevents the 2026-05-12 failure mode by gating destructive cleanup
behind release-safety checks. Quarantine adds the second-line defense:
even if a future logic bug slips through the gates, the deletion is
reversible for 30 days. ADR HR-5 + HR-9.

Storage layout
==============
Active blobs live at:
    shared/details/sha256/{shard}/{hash}.json

Quarantined blobs live at:
    shared/quarantine/{YYYY-MM-DD}/{shard}/{hash}.json

The date prefix is the cleanup-run date (so the sweeper can hard-delete
after TTL); the shard structure underneath is preserved so recovery is
a clean inverse MOVE without metadata reconstruction.

Atomicity model
===============
Supabase storage doesn't expose an atomic move primitive that we trust
across client versions. The COPY + verify + DELETE pattern below has
this guarantee: on any failure between COPY and DELETE source, the
source is preserved (the blob is recoverable from EITHER active OR
quarantine path). The next cleanup run reconciles the duplicate by
re-quarantining (idempotent — see ``quarantine_blob`` semantics).

Idempotency (HR-9)
==================
Every operation is a no-op when applied to its end state:
  - quarantine_blob on (source missing AND quarantine target present)
    returns success without re-doing the move.
  - recover_blob on (active path present AND quarantine missing) returns
    success without re-doing the restore.

Public API
==========
    quarantine_target_path(source_path, *, run_date=None) -> str
        Pure helper: compute the destination path.

    parse_quarantine_path(path) -> ParsedQuarantinePath | None
        Pure helper: extract (date_str, shard, hash, leaf) or None.

    quarantine_blob(client, source_path, *, run_date=None,
                    quarantine_root=QUARANTINE_PREFIX,
                    bucket=DEFAULT_BUCKET)
        -> tuple[bool, Optional[str]]

    recover_blob(client, blob_hash, *, search_dates=None,
                 quarantine_root=QUARANTINE_PREFIX,
                 active_root=ACTIVE_PREFIX,
                 bucket=DEFAULT_BUCKET)
        -> tuple[bool, Optional[str]]

    list_quarantine_dates(client, *, quarantine_root=QUARANTINE_PREFIX,
                          bucket=DEFAULT_BUCKET) -> list[str]
        Pulled in here too because the sweeper needs it; importable from
        either module.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants — paths/buckets are configurable for tests but match the
# pipeline defaults in production.
# ---------------------------------------------------------------------------

DEFAULT_BUCKET = "pharmaguide"
ACTIVE_PREFIX = "shared/details/sha256"
QUARANTINE_PREFIX = "shared/quarantine"

# Active blob path: shared/details/sha256/{2-char shard}/{64-hex hash}.json
_ACTIVE_PATH_RE = re.compile(
    r"^(?P<root>shared/details/sha256)/"
    r"(?P<shard>[0-9a-f]{2})/"
    r"(?P<hash>[0-9a-f]{64})\.json$"
)

# Quarantine path: shared/quarantine/{YYYY-MM-DD}/{shard}/{hash}.json
_QUARANTINE_PATH_RE = re.compile(
    r"^(?P<root>shared/quarantine)/"
    r"(?P<date>\d{4}-\d{2}-\d{2})/"
    r"(?P<shard>[0-9a-f]{2})/"
    r"(?P<hash>[0-9a-f]{64})\.json$"
)


# ---------------------------------------------------------------------------
# Result / parse types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ParsedActivePath:
    root: str
    shard: str
    hash: str
    leaf: str


@dataclass(frozen=True)
class ParsedQuarantinePath:
    root: str
    date_str: str          # "YYYY-MM-DD"
    shard: str
    hash: str
    leaf: str              # "{hash}.json"


def parse_active_path(path: str) -> Optional[ParsedActivePath]:
    """Parse an active storage path; None on shape mismatch."""
    m = _ACTIVE_PATH_RE.match(path)
    if not m:
        return None
    return ParsedActivePath(
        root=m.group("root"),
        shard=m.group("shard"),
        hash=m.group("hash"),
        leaf=f"{m.group('hash')}.json",
    )


def parse_quarantine_path(path: str) -> Optional[ParsedQuarantinePath]:
    """Parse a quarantine storage path; None on shape mismatch."""
    m = _QUARANTINE_PATH_RE.match(path)
    if not m:
        return None
    return ParsedQuarantinePath(
        root=m.group("root"),
        date_str=m.group("date"),
        shard=m.group("shard"),
        hash=m.group("hash"),
        leaf=f"{m.group('hash')}.json",
    )


# ---------------------------------------------------------------------------
# Pure path computations
# ---------------------------------------------------------------------------


def quarantine_target_path(
    source_path: str,
    *,
    run_date: Optional[str] = None,
    quarantine_root: str = QUARANTINE_PREFIX,
) -> str:
    """Compute the quarantine destination for an active storage path.

    Args:
        source_path: must match the active-path shape
            ``shared/details/sha256/{shard}/{hash}.json``.
        run_date: ISO date string ``YYYY-MM-DD``. Defaults to today UTC.
            Tests pass an explicit value for determinism.
        quarantine_root: top-level prefix; default ``shared/quarantine``.

    Returns:
        ``{quarantine_root}/{run_date}/{shard}/{hash}.json``

    Raises:
        ValueError: source_path does not match the active-path shape.
    """
    parsed = parse_active_path(source_path)
    if parsed is None:
        raise ValueError(
            f"Source path does not match active storage shape "
            f"(shared/details/sha256/{{shard}}/{{hash}}.json): {source_path!r}"
        )
    if run_date is None:
        run_date = _today_utc_iso()
    _validate_run_date(run_date)
    return f"{quarantine_root}/{run_date}/{parsed.shard}/{parsed.leaf}"


def _today_utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _validate_run_date(run_date: str) -> None:
    """Defensive: a malformed run_date would create unsweepable orphans
    in quarantine that the date-prefix sweeper can't reach."""
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", run_date):
        raise ValueError(
            f"run_date must be ISO YYYY-MM-DD, got {run_date!r}"
        )


# ---------------------------------------------------------------------------
# Storage operation seams (single-point monkeypatch for tests)
# ---------------------------------------------------------------------------


def _copy_storage_object(client, bucket: str, src: str, dst: str) -> Tuple[bool, Optional[str]]:
    """COPY one object inside a bucket. Returns (success, error)."""
    try:
        client.storage.from_(bucket).copy(src, dst)
        return True, None
    except Exception as e:  # noqa: BLE001 — pass-through error reporting
        return False, f"{type(e).__name__}: {e}"


def _remove_storage_object(client, bucket: str, path: str) -> Tuple[bool, Optional[str]]:
    """DELETE one object from a bucket. Returns (success, error)."""
    try:
        client.storage.from_(bucket).remove([path])
        return True, None
    except Exception as e:  # noqa: BLE001
        return False, f"{type(e).__name__}: {e}"


def _object_exists(client, bucket: str, path: str) -> bool:
    """Return True iff the named object exists in the bucket.

    Uses storage.list() on the parent directory and checks for the leaf.
    Cheaper than download() and works regardless of the object's content
    type.
    """
    parent, _, leaf = path.rpartition("/")
    try:
        items = client.storage.from_(bucket).list(
            path=parent,
            options={"limit": 1000, "offset": 0},
        )
    except Exception:  # noqa: BLE001 — treat list errors as "unknown"; caller decides
        return False
    if not items:
        return False
    for item in items:
        if (item or {}).get("name") == leaf:
            return True
    return False


# ---------------------------------------------------------------------------
# quarantine_blob — move-to-quarantine with COPY + verify + DELETE pattern
# ---------------------------------------------------------------------------


def quarantine_blob(
    client,
    source_path: str,
    *,
    run_date: Optional[str] = None,
    quarantine_root: str = QUARANTINE_PREFIX,
    bucket: str = DEFAULT_BUCKET,
) -> Tuple[bool, Optional[str]]:
    """Move a blob from active storage to quarantine.

    Implementation: COPY source → quarantine target, verify target exists,
    DELETE source. On any failure between COPY and DELETE source, the
    source is preserved — the blob is recoverable from EITHER path. The
    next cleanup run reconciles via the idempotency check.

    Idempotency:
      - source missing + target present → returns (True, None)
        (already quarantined; safe to re-run cleanup)
      - source present + target present (rare race) → re-COPY then
        DELETE source

    Args:
        client: Supabase storage client.
        source_path: active storage path
            (``shared/details/sha256/{shard}/{hash}.json``).
        run_date: ISO ``YYYY-MM-DD`` (defaults to today UTC; pass
            explicit value for tests).
        quarantine_root: override for tests.
        bucket: override for tests.

    Returns:
        ``(success, error_message_or_None)``. False return means caller
        should NOT consider the blob safely-quarantined; recovery from
        the partial state requires operator inspection per the error
        message.

    Raises:
        ValueError: source_path doesn't match active-path shape, or
            run_date is malformed. These are caller-side bugs and surface
            as exceptions rather than ``(False, ...)`` so they fail loud
            in test/dev.
    """
    target_path = quarantine_target_path(
        source_path, run_date=run_date, quarantine_root=quarantine_root,
    )

    source_exists = _object_exists(client, bucket, source_path)
    target_exists = _object_exists(client, bucket, target_path)

    # Idempotent: already quarantined.
    if not source_exists and target_exists:
        return True, None

    if not source_exists and not target_exists:
        return False, (
            f"Source not present and no quarantine copy exists: "
            f"{source_path}. Nothing to quarantine."
        )

    # Source exists; copy + verify + delete.
    if not target_exists:
        ok, err = _copy_storage_object(client, bucket, source_path, target_path)
        if not ok:
            return False, (
                f"COPY {source_path} -> {target_path} failed: {err}; "
                "source preserved."
            )
        if not _object_exists(client, bucket, target_path):
            return False, (
                f"COPY reported success but {target_path} not visible after; "
                "source preserved. Inspect storage state."
            )

    ok, err = _remove_storage_object(client, bucket, source_path)
    if not ok:
        return False, (
            f"COPY succeeded but DELETE {source_path} failed: {err}. "
            f"Blob is now duplicated at active AND quarantine paths; "
            "next cleanup pass will retry the DELETE."
        )

    return True, None


# ---------------------------------------------------------------------------
# recover_blob — restore from quarantine to active path
# ---------------------------------------------------------------------------


def recover_blob(
    client,
    blob_hash: str,
    *,
    search_dates: Optional[List[str]] = None,
    quarantine_root: str = QUARANTINE_PREFIX,
    active_root: str = ACTIVE_PREFIX,
    bucket: str = DEFAULT_BUCKET,
) -> Tuple[bool, Optional[str]]:
    """Find ``blob_hash`` in quarantine and restore it to active storage.

    Args:
        client: Supabase storage client.
        blob_hash: 64-char lowercase hex hash to recover.
        search_dates: optional list of ``YYYY-MM-DD`` date directories to
            search. None = search all dates returned by
            ``list_quarantine_dates``.
        quarantine_root / active_root / bucket: overrides for tests.

    Returns:
        ``(success, error_message_or_None)``. Idempotent: if the active
        path already exists and quarantine is empty, returns ``(True, None)``.

    Raises:
        ValueError: ``blob_hash`` is not a valid 64-char lowercase hex.
    """
    if not re.match(r"^[0-9a-f]{64}$", blob_hash):
        raise ValueError(
            f"blob_hash must be 64-char lowercase hex, got {blob_hash!r}"
        )

    shard = blob_hash[:2]
    leaf = f"{blob_hash}.json"
    active_path = f"{active_root}/{shard}/{leaf}"

    if _object_exists(client, bucket, active_path):
        # Already at active path. Sweep up any leftover quarantine copies
        # opportunistically so the recovery is fully reverse-MOVE.
        _cleanup_leftover_quarantine_copies(
            client, bucket, blob_hash, search_dates,
            quarantine_root=quarantine_root,
        )
        return True, None

    # Search quarantine for this hash.
    if search_dates is None:
        search_dates = list_quarantine_dates(
            client, quarantine_root=quarantine_root, bucket=bucket,
        )

    found_at: Optional[str] = None
    for date_str in search_dates:
        candidate = f"{quarantine_root}/{date_str}/{shard}/{leaf}"
        if _object_exists(client, bucket, candidate):
            found_at = candidate
            break

    if found_at is None:
        return False, (
            f"Blob {blob_hash[:16]}... not found in quarantine "
            f"(searched {len(search_dates)} date directories under "
            f"{quarantine_root}). May be past the 30-day TTL; "
            "recovery is no longer possible."
        )

    # Restore: COPY found_at -> active_path, verify, DELETE quarantine copy.
    ok, err = _copy_storage_object(client, bucket, found_at, active_path)
    if not ok:
        return False, (
            f"COPY {found_at} -> {active_path} failed: {err}; "
            "quarantine copy preserved."
        )
    if not _object_exists(client, bucket, active_path):
        return False, (
            f"COPY reported success but {active_path} not visible after; "
            "quarantine copy preserved. Inspect storage state."
        )

    ok, err = _remove_storage_object(client, bucket, found_at)
    if not ok:
        # Restoration succeeded; quarantine cleanup is best-effort.
        # Returning success because the active blob is back in place.
        return True, (
            f"Restored to active, but failed to remove quarantine copy "
            f"at {found_at}: {err}. Sweeper will collect it on TTL."
        )

    # Opportunistically clean up any other quarantine copies (e.g., if
    # the same hash got quarantined on multiple dates).
    _cleanup_leftover_quarantine_copies(
        client, bucket, blob_hash, search_dates,
        quarantine_root=quarantine_root,
    )

    return True, None


def _cleanup_leftover_quarantine_copies(
    client,
    bucket: str,
    blob_hash: str,
    search_dates: Optional[List[str]],
    *,
    quarantine_root: str,
) -> None:
    """Best-effort: remove any quarantine copies of this hash beyond the
    one we just restored from. Failures are logged via the storage seam
    but not propagated — the recovery itself already succeeded."""
    if search_dates is None:
        try:
            search_dates = list_quarantine_dates(
                client, quarantine_root=quarantine_root, bucket=bucket,
            )
        except Exception:  # noqa: BLE001
            return
    shard = blob_hash[:2]
    leaf = f"{blob_hash}.json"
    for date_str in search_dates:
        path = f"{quarantine_root}/{date_str}/{shard}/{leaf}"
        if _object_exists(client, bucket, path):
            _remove_storage_object(client, bucket, path)


# ---------------------------------------------------------------------------
# Date-directory listing — used by sweeper AND recover_blob
# ---------------------------------------------------------------------------


def list_quarantine_dates(
    client,
    *,
    quarantine_root: str = QUARANTINE_PREFIX,
    bucket: str = DEFAULT_BUCKET,
) -> List[str]:
    """List date directories under the quarantine root, sorted ascending.

    Returns valid ``YYYY-MM-DD`` strings only — anything that doesn't
    match the format is skipped silently (defensive against hand-edits).
    """
    try:
        items = client.storage.from_(bucket).list(
            path=quarantine_root,
            options={"limit": 1000, "offset": 0},
        )
    except Exception:  # noqa: BLE001
        return []
    if not items:
        return []
    dates: List[str] = []
    for item in items:
        name = (item or {}).get("name")
        if isinstance(name, str) and re.match(r"^\d{4}-\d{2}-\d{2}$", name):
            dates.append(name)
    dates.sort()
    return dates
