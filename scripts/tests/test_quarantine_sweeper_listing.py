"""The quarantine sweeper must not mistake an unlistable prefix for an empty one.

Measured on the live bucket 2026-08-26: BOTH existing quarantine date
directories (``shared/quarantine/2026-07-17`` and ``.../2026-08-06``) return
HTTP 544 ``DatabaseTimeout`` when listed, after 4 retries. Same shape as the
shard root — storage-api has to roll ~100k objects up into folder entries and
the query times out.

``_list_blobs_under_quarantine_date`` caught that with ``except: return []``,
so ``sweep_quarantine`` reported "no expired quarantine entries" on every
release. The 2026-07-17 batch is long past its 30-day TTL and has never been
swept. That silence also breaks the promise made to anyone approving a
quarantine: "recoverable for 30 days, then reclaimed" is only true if the
reclaim step can actually see the blobs.

Fewer hard-deletes is always safe here (TTL housekeeping). Reporting success
for work that did not happen is not.
"""

from __future__ import annotations

import os
import sys
import time
from datetime import date

import pytest

_scripts_dir = os.path.join(os.path.dirname(__file__), "..")
if _scripts_dir not in sys.path:
    sys.path.insert(0, os.path.abspath(_scripts_dir))

QROOT = "shared/quarantine"
OLD_DATE = "2026-07-17"
NOW = date(2026, 8, 26)


@pytest.fixture(autouse=True)
def _no_real_backoff_sleeps(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda _s: None)


def _storage_error():
    from storage3.exceptions import StorageApiError

    return StorageApiError(
        "The connection to the database timed out", "DatabaseTimeout", 544,
    )


class _Bucket:
    """Date roots 544 (as in production); shard dirs list fine."""

    def __init__(self, objects, *, unlistable=()):
        self.objects = set(objects)
        self.unlistable = set(unlistable)
        self.listed = []
        self.removed = []

    def list(self, path="", options=None):
        self.listed.append(path)
        if path in self.unlistable:
            raise _storage_error()
        base = path.rstrip("/") + "/" if path else ""
        opts = options or {}
        limit = int(opts.get("limit", 1000))
        offset = int(opts.get("offset", 0))
        names, seen = [], set()
        for full in self.objects:
            if not full.startswith(base):
                continue
            rest = full[len(base):]
            head = rest.split("/", 1)[0]
            if head in seen:
                continue
            seen.add(head)
            names.append(head)
        names.sort()
        return [{"name": n} for n in names[offset:offset + limit]]

    def remove(self, paths):
        self.removed.extend(paths)
        for p in paths:
            self.objects.discard(p)
        return [{"name": p} for p in paths]


class _Client:
    def __init__(self, bucket):
        self.bucket = bucket
        self.storage = self

    def from_(self, name):
        return self.bucket


def _quarantined(date_str, shard, tag):
    blob = (tag * 32)[:64]
    return f"{QROOT}/{date_str}/{shard}/{blob}.json"


def test_sweeper_finds_blobs_even_when_the_date_root_is_unlistable():
    """The exact live condition: date root 544s, shard dirs are fine."""
    from release_safety.quarantine_sweeper import sweep_quarantine

    objects = {
        _quarantined(OLD_DATE, "aa", "aa"),
        _quarantined(OLD_DATE, "ff", "ff"),
    }
    bucket = _Bucket(objects, unlistable={f"{QROOT}/{OLD_DATE}"})
    client = _Client(bucket)

    result = sweep_quarantine(
        client, ttl_days=30, dry_run=True, now=NOW,
    )

    assert result.eligible_dates == [OLD_DATE]
    assert result.total_eligible == 2, (
        "an unlistable date root must not be reported as an empty one"
    )


def test_sweeper_does_not_list_the_unlistable_date_root():
    from release_safety.quarantine_sweeper import sweep_quarantine

    bucket = _Bucket({_quarantined(OLD_DATE, "aa", "aa")})
    client = _Client(bucket)

    sweep_quarantine(client, ttl_days=30, dry_run=True, now=NOW)

    assert f"{QROOT}/{OLD_DATE}" not in bucket.listed
    assert f"{QROOT}/{OLD_DATE}/aa" in bucket.listed
    assert f"{QROOT}/{OLD_DATE}/ff" in bucket.listed


def test_sweeper_surfaces_shard_listing_failures_rather_than_silently_skipping():
    """A shard we could not read is unswept work, not finished work."""
    from release_safety.quarantine_sweeper import sweep_quarantine

    bucket = _Bucket(
        {_quarantined(OLD_DATE, "aa", "aa")},
        unlistable={f"{QROOT}/{OLD_DATE}", f"{QROOT}/{OLD_DATE}/aa"},
    )
    client = _Client(bucket)

    result = sweep_quarantine(client, ttl_days=30, dry_run=True, now=NOW)

    assert result.listing_failures, (
        "the sweep must report shards it could not read"
    )
    assert result.complete is False


def test_a_fully_readable_sweep_reports_itself_complete():
    from release_safety.quarantine_sweeper import sweep_quarantine

    bucket = _Bucket({_quarantined(OLD_DATE, "aa", "aa")})
    client = _Client(bucket)

    result = sweep_quarantine(client, ttl_days=30, dry_run=True, now=NOW)

    assert result.complete is True
    assert result.listing_failures == []


def test_sweeper_paginates_each_quarantine_shard():
    """Large quarantine shards must not be silently truncated at 1,000."""
    from release_safety.quarantine_sweeper import sweep_quarantine

    objects = {
        _quarantined(OLD_DATE, "aa", f"{i:064x}")
        for i in range(1500)
    }
    bucket = _Bucket(objects)
    client = _Client(bucket)

    result = sweep_quarantine(client, ttl_days=30, dry_run=True, now=NOW)

    assert result.complete is True
    assert result.total_eligible == 1500
    assert bucket.listed.count(f"{QROOT}/{OLD_DATE}/aa") == 2


def test_sweeper_fails_closed_when_quarantine_root_cannot_be_listed():
    """An unreadable root is an error, never proof that quarantine is empty."""
    from release_safety.quarantine_sweeper import sweep_quarantine

    bucket = _Bucket(
        {_quarantined(OLD_DATE, "aa", "aa")},
        unlistable={QROOT},
    )
    client = _Client(bucket)

    with pytest.raises(Exception, match="timed out"):
        sweep_quarantine(client, ttl_days=30, dry_run=True, now=NOW)


def test_dry_run_sweep_deletes_nothing():
    from release_safety.quarantine_sweeper import sweep_quarantine

    bucket = _Bucket({_quarantined(OLD_DATE, "aa", "aa")})
    client = _Client(bucket)

    sweep_quarantine(client, ttl_days=30, dry_run=True, now=NOW)

    assert bucket.removed == []


# ---------------------------------------------------------------------------
# Phase 2 — batched deletes, absence proof, honest three-way completeness
# ---------------------------------------------------------------------------


def test_execute_sweep_batch_deletes_in_groups_of_500():
    from release_safety.quarantine_sweeper import sweep_quarantine

    objects = {
        _quarantined(OLD_DATE, "aa", f"{i:064x}")
        for i in range(1200)
    }
    bucket = _Bucket(objects)
    client = _Client(bucket)
    remove_batches = []
    real_remove = bucket.remove

    def recording_remove(paths):
        remove_batches.append(len(paths))
        return real_remove(paths)

    bucket.remove = recording_remove

    result = sweep_quarantine(client, ttl_days=30, dry_run=False, now=NOW)

    assert result.total_deleted == 1200
    assert result.complete is True
    assert remove_batches == [500, 500, 200]
    assert not bucket.objects, "every expired object must be gone"


def test_execute_sweep_proves_absence_and_reports_residuals():
    """remove() claiming success while the object survives is a residual —
    reported as incomplete, never as deleted."""
    from release_safety.quarantine_sweeper import sweep_quarantine

    survivor = _quarantined(OLD_DATE, "aa", "aa")
    bucket = _Bucket({survivor, _quarantined(OLD_DATE, "ff", "ff")})
    client = _Client(bucket)
    real_remove = bucket.remove

    def lying_remove(paths):
        result = real_remove(paths)
        if survivor in paths:
            bucket.objects.add(survivor)  # storage silently kept it
        return result

    bucket.remove = lying_remove

    result = sweep_quarantine(client, ttl_days=30, dry_run=False, now=NOW)

    assert result.complete is False
    assert result.residual_paths == [survivor]
    assert result.total_deleted == 1, "only the proven-absent delete counts"


def test_execute_sweep_records_deletion_failures_separately():
    from release_safety.quarantine_sweeper import sweep_quarantine

    failing = _quarantined(OLD_DATE, "aa", "aa")
    bucket = _Bucket({failing, _quarantined(OLD_DATE, "ff", "ff")})
    client = _Client(bucket)
    real_remove = bucket.remove

    def failing_remove(paths):
        if failing in paths:
            raise _storage_error()
        return real_remove(paths)

    bucket.remove = failing_remove

    result = sweep_quarantine(client, ttl_days=30, dry_run=False, now=NOW)

    assert result.complete is False
    assert result.deletion_failures, "delete errors must be recorded distinctly"
    assert result.listing_failures == [], (
        "a delete error is not a listing failure — do not overload the field"
    )
    assert result.total_deleted == 1


def test_already_absent_objects_are_idempotent_success():
    """A re-run after a partial sweep converges without errors."""
    from release_safety.quarantine_sweeper import sweep_quarantine

    kept = _quarantined(OLD_DATE, "aa", "aa")
    bucket = _Bucket({kept})
    client = _Client(bucket)
    real_remove = bucket.remove

    def racing_remove(paths):
        # Someone else deleted it between listing and remove.
        bucket.objects.discard(kept)
        return real_remove(paths)

    bucket.remove = racing_remove

    result = sweep_quarantine(client, ttl_days=30, dry_run=False, now=NOW)

    assert result.complete is True
    assert result.total_deleted == 1
    assert result.deletion_failures == []
    assert result.residual_paths == []


def test_incomplete_because_of_listing_failure_still_reports_distinctly():
    from release_safety.quarantine_sweeper import sweep_quarantine

    bucket = _Bucket(
        {_quarantined(OLD_DATE, "aa", "aa")},
        unlistable={f"{QROOT}/{OLD_DATE}/aa"},
    )
    client = _Client(bucket)

    result = sweep_quarantine(client, ttl_days=30, dry_run=False, now=NOW)

    assert result.complete is False
    assert result.listing_failures
    assert result.deletion_failures == []
    assert result.residual_paths == []
