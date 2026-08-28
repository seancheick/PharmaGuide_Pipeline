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
- No standalone CLI. ``cleanup_old_versions.py`` invokes it after version
  cleanup, and callers may use the public function for an explicit run.

Public API
==========
    DEFAULT_QUARANTINE_TTL_DAYS = 30

    is_eligible_for_hard_delete(date_str, *, ttl_days=30, now=None) -> bool
        Pure function. ``date_str`` must be ``YYYY-MM-DD`` or ValueError.

    sweep_quarantine(client, *, ttl_days=30, dry_run=True, now=None,
                     quarantine_root=QUARANTINE_PREFIX,
                     bucket=DEFAULT_BUCKET, lock_path=None) -> SweepResult
        Walk eligible quarantine date directories and (if not dry_run)
        hard-delete every blob inside under the global release lock.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field as dataclass_field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from .blob_inventory import HEX_BLOB_SHARDS, PAGE_LIMIT, list_storage_page
from .transient import retry_transient
from .quarantine import (
    DEFAULT_REMOVE_BATCH_SIZE,
    remove_storage_batch,
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


#: Attempts per quarantine shard listing. Transient 544s are routine on this
#: bucket; a give-up is recorded as a listing failure, never as "empty".
SWEEP_LIST_MAX_ATTEMPTS = 4


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
    #: "{date}/{shard}" entries that could not be listed. Non-empty means the
    #: sweep saw only part of the quarantine and must not be called done.
    listing_failures: List[str] = dataclass_field(default_factory=list)
    #: Full paths whose delete REQUEST failed (exception from the batch call).
    deletion_failures: List[str] = dataclass_field(default_factory=list)
    #: Full paths whose delete was claimed successful but which the absence
    #: proof still found listed. The listing is the authority, not remove().
    residual_paths: List[str] = dataclass_field(default_factory=list)

    @property
    def complete(self) -> bool:
        """Done means: saw everything, every delete succeeded, nothing left."""
        return (
            not self.listing_failures
            and not self.deletion_failures
            and not self.residual_paths
        )

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
) -> Tuple[List[str], List[str]]:
    """List every blob under ``shared/quarantine/{date_str}/``.

    Returns ``(sorted_paths, failed_shards)``.

    Enumerates the 00..ff shard directories deterministically rather than
    listing the date root. Measured 2026-08-26: both live quarantine date
    roots return HTTP 544 DatabaseTimeout, because storage-api has to roll
    ~100k objects up into folder entries. Listing the root and catching the
    error returned [], which the sweeper reported as "nothing expired" — so
    the 2026-07-17 batch sat unswept long past its TTL.

    A shard that cannot be read is returned in ``failed_shards``, never
    silently dropped: unread is unswept work, not finished work.
    """
    date_root = f"{quarantine_root}/{date_str}"
    blob_paths: List[str] = []
    failed_shards: List[str] = []

    for shard in HEX_BLOB_SHARDS:
        shard_root = f"{date_root}/{shard}"
        try:
            blob_paths.extend(_list_one_quarantine_shard(client, bucket, shard_root))
        except Exception:  # noqa: BLE001 — recorded, not swallowed.
            failed_shards.append(shard)
            continue

    blob_paths.sort()
    return blob_paths, failed_shards


def _list_one_quarantine_shard(client, bucket: str, shard_root: str) -> List[str]:
    """Paginated, retried listing of one quarantine shard. Raises on give-up."""
    paths: List[str] = []
    offset = 0
    while True:
        shard_items = retry_transient(
            lambda offset=offset: list_storage_page(
                client.storage.from_(bucket),
                shard_root,
                offset,
                limit=PAGE_LIMIT,
            ),
            max_attempts=SWEEP_LIST_MAX_ATTEMPTS,
        )
        for sitem in shard_items or []:
            sname = (sitem or {}).get("name")
            if not isinstance(sname, str) or not sname.endswith(".json"):
                continue
            paths.append(f"{shard_root}/{sname}")
        if len(shard_items or []) < PAGE_LIMIT:
            break
        offset += PAGE_LIMIT
    return paths


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
    lock_path: Optional[Path] = None,
) -> SweepResult:
    """Run a read-only preview or a globally locked destructive sweep."""
    if dry_run:
        return _sweep_quarantine_unlocked(
            client,
            ttl_days=ttl_days,
            dry_run=True,
            now=now,
            quarantine_root=quarantine_root,
            bucket=bucket,
        )

    from .lock import acquire_release_lock

    with acquire_release_lock(
        lock_path, initial_step="sweep_expired_quarantine",
    ):
        return _sweep_quarantine_unlocked(
            client,
            ttl_days=ttl_days,
            dry_run=False,
            now=now,
            quarantine_root=quarantine_root,
            bucket=bucket,
        )


def _sweep_quarantine_unlocked(
    client,
    *,
    ttl_days: int,
    dry_run: bool,
    now: Optional[Union[date, datetime]],
    quarantine_root: str,
    bucket: str,
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
    listing_failures: List[str] = []
    deletion_failures: List[str] = []
    residual_paths: List[str] = []

    for date_str in eligible_dates:
        blobs, failed_shards = _list_blobs_under_quarantine_date(
            client, date_str,
            quarantine_root=quarantine_root, bucket=bucket,
        )
        listing_failures.extend(f"{date_str}/{s}" for s in failed_shards)
        candidates_per_date[date_str] = len(blobs)

        if dry_run:
            deleted_per_date[date_str] = 0
            failed_per_date[date_str] = 0
            continue

        # Batched deletes (500/request, under Supabase's 1,000 cap), then ONE
        # absence-proof listing per affected shard. The listing is the
        # authority on what was deleted; remove()'s response is not believed.
        date_deletion_failures: List[str] = []
        for start in range(0, len(blobs), DEFAULT_REMOVE_BATCH_SIZE):
            batch = blobs[start:start + DEFAULT_REMOVE_BATCH_SIZE]
            try:
                retry_transient(
                    lambda batch=batch: remove_storage_batch(
                        client, bucket, batch,
                    ),
                    max_attempts=SWEEP_LIST_MAX_ATTEMPTS,
                )
            except Exception:  # noqa: BLE001 — isolate the poison pill.
                # One bad path must not sink its 500 batch-mates (P2.1b: the
                # sweep continues past individual failures). Degrade to
                # per-path removes for THIS batch only.
                for blob_path in batch:
                    ok, _err = _remove_storage_object(client, bucket, blob_path)
                    if not ok:
                        date_deletion_failures.append(blob_path)

        affected_shards = sorted({p.rsplit("/", 2)[-2] for p in blobs})
        date_root = f"{quarantine_root}/{date_str}"
        still_present: set = set()
        unlistable_after: List[str] = []
        for shard in affected_shards:
            shard_root = f"{date_root}/{shard}"
            try:
                still_present.update(
                    _list_one_quarantine_shard(client, bucket, shard_root)
                )
            except Exception:  # noqa: BLE001
                unlistable_after.append(shard)

        deleted = 0
        failed = 0
        failure_set = set(date_deletion_failures)
        for blob_path in blobs:
            shard = blob_path.rsplit("/", 2)[-2]
            if shard in unlistable_after:
                # Unknown final state — count as unswept, surface as a
                # listing failure so complete=False.
                failed += 1
                continue
            if blob_path in still_present:
                failed += 1
                if blob_path in failure_set:
                    deletion_failures.append(blob_path)
                else:
                    residual_paths.append(blob_path)
            else:
                # Absent — goal state reached, whoever got it there.
                deleted += 1
        listing_failures.extend(
            f"{date_str}/{shard} (post-delete)" for shard in unlistable_after
        )
        deleted_per_date[date_str] = deleted
        failed_per_date[date_str] = failed

    return SweepResult(
        eligible_dates=eligible_dates,
        candidates_per_date=candidates_per_date,
        deleted_per_date=deleted_per_date,
        failed_per_date=failed_per_date,
        dry_run=dry_run,
        ttl_days=ttl_days,
        listing_failures=listing_failures,
        deletion_failures=deletion_failures,
        residual_paths=residual_paths,
    )
