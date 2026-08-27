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
