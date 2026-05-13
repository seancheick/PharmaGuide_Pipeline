"""Quarantine sweeper — TTL-based hard-delete of expired quarantined blobs.

Pairs with ``quarantine.py``: that module moves blobs into quarantine
(soft-delete with a 30-day recovery window); this module drains the
window by hard-deleting blobs whose quarantine date is older than the
TTL.

Implements the second half of ADR-0001 P2 (HR-5 + HR-9).

Behavior summary
================
- Default ``dry_run=True`` (per HR-3 — destructive ops opt-in).
- TTL default 30 days. **Exactly 30 days old is NOT eligible**; 31+ days
  is eligible. Boundary is strict ``> ttl_days``, not ``>= ttl_days``,
  so a blob quarantined at midnight on day N survives until midnight on
  day N + (ttl_days + 1).
- Non-ISO date directories under ``shared/quarantine/`` are skipped
  defensively (operator-edited dirs, garbage entries, etc.).
- Idempotent: re-running after a partial sweep completes the remaining
  work; 404s on already-deleted blobs are treated as success.
- Partial deletion failures are counted in the result, NOT silently
  swallowed. The sweep continues across the remaining blobs even when
  one delete fails (per P2.1b sign-off).

What this module does NOT do
============================
- No CLI. The sweeper is operator-invoked from a wrapper script (added
  in a follow-up) or from a cron entry that constructs a script around
  the public ``sweep_quarantine`` function.
- No automatic scheduling — explicit operator action only, until P3
  ships and we know the right cadence.

Public API
==========
    DEFAULT_QUARANTINE_TTL_DAYS = 30

    is_eligible_for_hard_delete(date_str, *, ttl_days=30, now=None) -> bool
        Pure function. ``date_str`` must be ``YYYY-MM-DD`` or ValueError.

    sweep_quarantine(client, *, ttl_days=30, dry_run=True, now=None,
                     quarantine_root=QUARANTINE_PREFIX,
                     bucket=DEFAULT_BUCKET) -> SweepResult
        Walk eligible quarantine date directories and (if not dry_run)
        hard-delete every blob inside.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional, Union

from .quarantine import (
    DEFAULT_BUCKET,
    QUARANTINE_PREFIX,
    _remove_storage_object,    # reused for hard-delete
    list_quarantine_dates,
)

DEFAULT_QUARANTINE_TTL_DAYS = 30

_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SHARD_NAME_RE = re.compile(r"^[0-9a-f]{2}$")


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SweepResult:
    """Result of a sweep_quarantine call.

    Attributes:
        eligible_dates: date strings (YYYY-MM-DD) that were past TTL,
            sorted ascending.
        candidates_per_date: per-date count of quarantined blobs found
            under that date directory.
        deleted_per_date: per-date count of blobs successfully deleted
            (always 0 in dry_run; equals candidates when no failures).
        failed_per_date: per-date count of delete failures. Sweep
            continues across remaining blobs on failure.
        dry_run: True if no destructive action was taken.
        ttl_days: the TTL value used for eligibility.
    """

    eligible_dates: List[str]
    candidates_per_date: Dict[str, int]
    deleted_per_date: Dict[str, int]
    failed_per_date: Dict[str, int]
    dry_run: bool
    ttl_days: int

    @property
    def total_eligible(self) -> int:
        return sum(self.candidates_per_date.values())

    @property
    def total_deleted(self) -> int:
        return sum(self.deleted_per_date.values())

    @property
    def total_failed(self) -> int:
        return sum(self.failed_per_date.values())


# ---------------------------------------------------------------------------
# Pure eligibility check
# ---------------------------------------------------------------------------


def is_eligible_for_hard_delete(
    quarantine_date_str: str,
    *,
    ttl_days: int = DEFAULT_QUARANTINE_TTL_DAYS,
    now: Optional[Union[date, datetime]] = None,
) -> bool:
    """True iff ``quarantine_date_str`` is older than ``now - ttl_days``.

    Boundary is strict ``>``, so a date exactly ``ttl_days`` old is NOT
    eligible (still inside the recovery window). 31+ days old → eligible
    when ``ttl_days=30``. Future dates and today are never eligible.

    Args:
        quarantine_date_str: ISO ``YYYY-MM-DD``.
        ttl_days: recovery-window length in days (default 30).
        now: anchor for "today" (date or datetime). Default UTC today.
            Tests pass an explicit value for determinism.

    Raises:
        ValueError: ``quarantine_date_str`` is not ISO ``YYYY-MM-DD`` or
            ``ttl_days`` is negative.
    """
    if not isinstance(quarantine_date_str, str) or not _ISO_DATE_RE.match(quarantine_date_str):
        raise ValueError(
            f"quarantine_date_str must be ISO YYYY-MM-DD, got "
            f"{quarantine_date_str!r}"
        )
    if not isinstance(ttl_days, int) or ttl_days < 0:
        raise ValueError(f"ttl_days must be a non-negative int, got {ttl_days!r}")

    quar_date = datetime.strptime(quarantine_date_str, "%Y-%m-%d").date()

    if now is None:
        now_date = datetime.now(timezone.utc).date()
    elif isinstance(now, datetime):
        now_date = now.date()
    elif isinstance(now, date):
        now_date = now
    else:
        raise ValueError(f"now must be date | datetime | None, got {type(now).__name__}")

    age_days = (now_date - quar_date).days
    return age_days > ttl_days


# ---------------------------------------------------------------------------
# Internal: list quarantined blobs under one date directory
# ---------------------------------------------------------------------------


def _list_blobs_under_quarantine_date(
    client,
    date_str: str,
    *,
    quarantine_root: str = QUARANTINE_PREFIX,
    bucket: str = DEFAULT_BUCKET,
) -> List[str]:
    """List every blob path under ``shared/quarantine/{date_str}/``.

    Walks the shard subdirectories. Returns a sorted list of full storage
    paths so the result is deterministic across runs (idempotency tests
    rely on this).

    Defensive: ignores entries whose name doesn't match the expected
    shape (2-char shard, ``{hash}.json`` leaf).
    """
    date_root = f"{quarantine_root}/{date_str}"
    try:
        items = client.storage.from_(bucket).list(
            path=date_root,
            options={"limit": 1000, "offset": 0},
        )
    except Exception:  # noqa: BLE001 — list errors → treat as empty
        return []
    if not items:
        return []

    blob_paths: List[str] = []
    for item in items:
        name = (item or {}).get("name")
        if not isinstance(name, str) or not _SHARD_NAME_RE.match(name):
            continue
        shard_root = f"{date_root}/{name}"
        try:
            shard_items = client.storage.from_(bucket).list(
                path=shard_root,
                options={"limit": 1000, "offset": 0},
            )
        except Exception:  # noqa: BLE001
            continue
        if not shard_items:
            continue
        for sitem in shard_items:
            sname = (sitem or {}).get("name")
            if not isinstance(sname, str):
                continue
            if not sname.endswith(".json"):
                continue
            blob_paths.append(f"{shard_root}/{sname}")

    blob_paths.sort()
    return blob_paths


# ---------------------------------------------------------------------------
# Public sweeper
# ---------------------------------------------------------------------------


def sweep_quarantine(
    client,
    *,
    ttl_days: int = DEFAULT_QUARANTINE_TTL_DAYS,
    dry_run: bool = True,
    now: Optional[Union[date, datetime]] = None,
    quarantine_root: str = QUARANTINE_PREFIX,
    bucket: str = DEFAULT_BUCKET,
) -> SweepResult:
    """Hard-delete quarantined blobs older than ``ttl_days``.

    Args:
        client: Supabase storage client.
        ttl_days: recovery-window length. Default 30.
        dry_run: if True (the default), report eligible dates and counts
            without deleting. Set False to actually delete.
        now: anchor "today" for eligibility (date or datetime). Default
            UTC today. Tests pass explicit values for determinism.
        quarantine_root, bucket: overrides for tests.

    Returns:
        ``SweepResult`` with per-date counts. ``total_failed > 0``
        indicates partial-delete failures; the sweep continues across
        remaining blobs in those cases (does NOT abort).

    Idempotent: re-running after a partial sweep completes the remaining
    work without errors. 404s on already-deleted blobs are treated as
    success by the storage seam.
    """
    if not isinstance(ttl_days, int) or ttl_days < 0:
        raise ValueError(f"ttl_days must be a non-negative int, got {ttl_days!r}")

    all_dates = list_quarantine_dates(
        client, quarantine_root=quarantine_root, bucket=bucket,
    )

    eligible_dates = sorted(
        d for d in all_dates
        if is_eligible_for_hard_delete(d, ttl_days=ttl_days, now=now)
    )

    candidates_per_date: Dict[str, int] = {}
    deleted_per_date: Dict[str, int] = {}
    failed_per_date: Dict[str, int] = {}

    for date_str in eligible_dates:
        blobs = _list_blobs_under_quarantine_date(
            client, date_str,
            quarantine_root=quarantine_root, bucket=bucket,
        )
        candidates_per_date[date_str] = len(blobs)

        if dry_run:
            deleted_per_date[date_str] = 0
            failed_per_date[date_str] = 0
            continue

        deleted = 0
        failed = 0
        for blob_path in blobs:
            ok, _err = _remove_storage_object(client, bucket, blob_path)
            if ok:
                deleted += 1
            else:
                failed += 1
        deleted_per_date[date_str] = deleted
        failed_per_date[date_str] = failed

    return SweepResult(
        eligible_dates=eligible_dates,
        candidates_per_date=candidates_per_date,
        deleted_per_date=deleted_per_date,
        failed_per_date=failed_per_date,
        dry_run=dry_run,
        ttl_days=ttl_days,
    )
