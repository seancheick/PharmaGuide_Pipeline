"""Scalable, honest detail-blob inventory.

Two production facts drive this module (both measured 2026-08-26 against the
live ``pharmaguide`` bucket, ~134,283 blobs):

  * Listing the shard ROOT ``shared/details/sha256`` returns HTTP 544
    ``DatabaseTimeout`` deterministically — the inventory must stay sharded.
  * Each of the 256 shard listings costs ~1.5-19s. Done serially that is the
    6+ minute stall that made a release wait on maintenance work.

The correctness requirement that outranks both: an inventory that could not
read every shard must NEVER present itself as complete. Orphan detection is
"storage minus protected"; a shard silently missing from `storage` cannot
create a false orphan, but a shard silently missing from a *protected* source
can — and the same partial-listing habit is what makes that dangerous. So the
contract here is: partial is always labelled partial, and callers fail closed.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time

import pytest

_scripts_dir = os.path.join(os.path.dirname(__file__), "..")
if _scripts_dir not in sys.path:
    sys.path.insert(0, os.path.abspath(_scripts_dir))

PREFIX = "shared/details/sha256"

#: Captured before the autouse fixture neuters ``time.sleep`` for backoff, so
#: the fake bucket can still simulate real request latency.
_REAL_SLEEP = time.sleep


def _storage_error(status=544, code="DatabaseTimeout",
                   message="The connection to the database timed out"):
    from storage3.exceptions import StorageApiError

    return StorageApiError(message, code, status)


class _FakeBucket:
    """Minimal stand-in for a Supabase bucket proxy.

    Deliberately exposes only the public ``list`` API (no ``_request``/``id``)
    so the module under test takes its test-double fallback path.
    """

    def __init__(self, objects, *, sizes=None, fail_plan=None, latency=0.0):
        self.objects = set(objects)
        self.sizes = sizes or {}
        self.fail_plan = dict(fail_plan or {})
        self.latency = latency
        self.listed = []
        self._lock = threading.Lock()
        self._active = 0
        self.max_concurrent = 0

    def list(self, path="", options=None):
        with self._lock:
            self._active += 1
            self.max_concurrent = max(self.max_concurrent, self._active)
            self.listed.append(path)
        try:
            if self.latency:
                _REAL_SLEEP(self.latency)
            remaining = self.fail_plan.get(path, 0)
            if remaining:
                self.fail_plan[path] = remaining - 1
                raise _storage_error()
            opts = options or {}
            limit = int(opts.get("limit", 1000))
            offset = int(opts.get("offset", 0))
            base = path.rstrip("/") + "/"
            names = sorted(
                full[len(base):]
                for full in self.objects
                if full.startswith(base) and "/" not in full[len(base):]
            )
            page = names[offset:offset + limit]
            return [
                {"name": n, "metadata": {"size": self.sizes.get(base + n, 10)}}
                for n in page
            ]
        finally:
            with self._lock:
                self._active -= 1


class _FakeClient:
    def __init__(self, bucket):
        self._bucket = bucket
        self.storage = self

    def from_(self, name):
        return self._bucket


def _blob(shard, n):
    return f"{PREFIX}/{shard}/{shard}{'%062x' % n}.json"


def _client_with(objects, **kw):
    bucket = _FakeBucket(objects, **kw)
    return _FakeClient(bucket), bucket


@pytest.fixture(autouse=True)
def _no_real_backoff_sleeps(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda _s: None)


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------


def test_inventory_paginates_beyond_a_single_page():
    """A shard larger than one page must be listed in full, not truncated."""
    from release_safety.blob_inventory import inventory_detail_blobs

    objects = {_blob("00", i) for i in range(2500)}
    client, bucket = _client_with(objects)

    inv = inventory_detail_blobs(client, shards=("00",), page_limit=1000)

    assert inv.complete is True
    assert len(inv.hashes) == 2500
    assert inv.total_objects == 2500


def test_inventory_stops_paginating_on_a_short_page():
    from release_safety.blob_inventory import inventory_detail_blobs

    objects = {_blob("00", i) for i in range(1500)}
    client, bucket = _client_with(objects)

    inv = inventory_detail_blobs(client, shards=("00",), page_limit=1000)

    assert len(inv.hashes) == 1500
    # 2 pages of data; a 3rd call only if the 2nd came back full.
    assert bucket.listed.count(f"{PREFIX}/00") == 2


def test_inventory_never_lists_the_shard_root():
    """The root prefix 544s deterministically in production."""
    from release_safety.blob_inventory import inventory_detail_blobs

    client, bucket = _client_with({_blob("0a", 1)})

    inventory_detail_blobs(client, shards=("0a",))

    assert PREFIX not in bucket.listed


# ---------------------------------------------------------------------------
# Sizes / categories — feed the dry-run report
# ---------------------------------------------------------------------------


def test_inventory_totals_bytes_from_listing_metadata():
    """metadata.size comes back with the listing — no extra round trips."""
    from release_safety.blob_inventory import inventory_detail_blobs

    a, b = _blob("00", 1), _blob("00", 2)
    client, _ = _client_with({a, b}, sizes={a: 1000, b: 2500})

    inv = inventory_detail_blobs(client, shards=("00",))

    assert inv.total_bytes == 3500
    assert inv.bytes_for(sorted(inv.hashes)[0]) in (1000, 2500)


def test_inventory_separates_blob_leaves_from_other_objects():
    from release_safety.blob_inventory import inventory_detail_blobs

    good = _blob("00", 1)
    junk = f"{PREFIX}/00/README.txt"
    client, _ = _client_with({good, junk})

    inv = inventory_detail_blobs(client, shards=("00",))

    assert len(inv.hashes) == 1
    assert inv.categories["detail_blob"] == 1
    assert inv.categories["unrecognized"] == 1


# ---------------------------------------------------------------------------
# Transient failure handling
# ---------------------------------------------------------------------------


def test_inventory_retries_transient_shard_failures_and_counts_them():
    from release_safety.blob_inventory import inventory_detail_blobs

    client, bucket = _client_with(
        {_blob("00", 1)}, fail_plan={f"{PREFIX}/00": 2},
    )

    inv = inventory_detail_blobs(client, shards=("00",), max_attempts=5)

    assert inv.complete is True
    assert len(inv.hashes) == 1
    assert inv.retries == 2


def test_inventory_marks_itself_incomplete_when_a_shard_never_succeeds():
    """The whole point: a partial inventory must announce that it is partial."""
    from release_safety.blob_inventory import inventory_detail_blobs

    client, _ = _client_with(
        {_blob("00", 1), _blob("0a", 1)},
        fail_plan={f"{PREFIX}/0a": 10_000},
    )

    inv = inventory_detail_blobs(client, shards=("00", "0a"), max_attempts=3)

    assert inv.complete is False
    assert [f.shard for f in inv.failures] == ["0a"]
    assert inv.shards_completed == 1
    assert inv.shards_total == 2
    # The successfully-listed shard is still reported — but the inventory as a
    # whole is not usable for deletion decisions.
    assert len(inv.hashes) == 1


def test_incomplete_inventory_raises_when_completeness_is_required():
    """Callers that will act destructively ask for the strict form."""
    from release_safety.blob_inventory import (
        IncompleteInventoryError,
        inventory_detail_blobs,
    )

    client, _ = _client_with(
        {_blob("00", 1)}, fail_plan={f"{PREFIX}/00": 10_000},
    )

    inv = inventory_detail_blobs(client, shards=("00",), max_attempts=2)
    with pytest.raises(IncompleteInventoryError):
        inv.require_complete()


def test_inventory_does_not_retry_permanent_errors():
    from release_safety.blob_inventory import inventory_detail_blobs

    bucket = _FakeBucket({_blob("00", 1)})

    def permanent(path="", options=None):
        bucket.listed.append(path)
        raise _storage_error(status=403, code="Unauthorized",
                             message="permission denied")

    bucket.list = permanent
    client = _FakeClient(bucket)

    inv = inventory_detail_blobs(client, shards=("00",), max_attempts=5)

    assert inv.complete is False
    assert bucket.listed.count(f"{PREFIX}/00") == 1


# ---------------------------------------------------------------------------
# Bounded parallelism
# ---------------------------------------------------------------------------


def test_inventory_lists_shards_in_bounded_parallel():
    from release_safety.blob_inventory import inventory_detail_blobs

    shards = tuple(f"{i:02x}" for i in range(16))
    objects = {_blob(s, 1) for s in shards}
    client, bucket = _client_with(objects, latency=0.02)

    inv = inventory_detail_blobs(
        client, shards=shards, max_workers=4,
        client_factory=lambda: client,
    )

    assert inv.complete is True
    assert len(inv.hashes) == 16
    assert bucket.max_concurrent > 1, "expected parallel shard listing"
    assert bucket.max_concurrent <= 4, "must respect max_workers"


def test_inventory_is_serial_without_a_client_factory():
    """Mirrors quarantine_orphan_blob_batch: no factory means no thread fan-out,
    because a Supabase client's HTTP transport is not shared across threads."""
    from release_safety.blob_inventory import inventory_detail_blobs

    shards = tuple(f"{i:02x}" for i in range(8))
    client, bucket = _client_with({_blob(s, 1) for s in shards}, latency=0.02)

    inventory_detail_blobs(client, shards=shards, max_workers=8)

    assert bucket.max_concurrent == 1


# ---------------------------------------------------------------------------
# Checkpoint / resume
# ---------------------------------------------------------------------------


def test_inventory_resumes_completed_shards_from_checkpoint(tmp_path):
    from release_safety.blob_inventory import inventory_detail_blobs

    ckpt = tmp_path / "inv.json"
    client, bucket = _client_with(
        {_blob("00", 1), _blob("0a", 1)},
        fail_plan={f"{PREFIX}/0a": 10_000},
    )

    first = inventory_detail_blobs(
        client, shards=("00", "0a"), max_attempts=2, checkpoint_path=ckpt,
    )
    assert first.complete is False

    # Second run: 0a now healthy. 00 must be served from the checkpoint.
    bucket.fail_plan.clear()
    bucket.listed.clear()
    second = inventory_detail_blobs(
        client, shards=("00", "0a"), max_attempts=2, checkpoint_path=ckpt,
    )

    assert second.complete is True
    assert len(second.hashes) == 2
    assert f"{PREFIX}/00" not in bucket.listed, "completed shard must not be re-listed"
    assert f"{PREFIX}/0a" in bucket.listed


def test_checkpoint_does_not_record_failed_shards(tmp_path):
    from release_safety.blob_inventory import inventory_detail_blobs

    ckpt = tmp_path / "inv.json"
    client, _ = _client_with(
        {_blob("00", 1), _blob("0a", 1)},
        fail_plan={f"{PREFIX}/0a": 10_000},
    )

    inventory_detail_blobs(
        client, shards=("00", "0a"), max_attempts=2, checkpoint_path=ckpt,
    )

    saved = json.loads(ckpt.read_text())
    assert "00" in saved["shards"]
    assert "0a" not in saved["shards"], (
        "a failed shard must never be checkpointed as done"
    )


def test_checkpoint_is_ignored_when_the_shard_set_changes(tmp_path):
    """A checkpoint keyed to a different prefix/shard set must not be trusted."""
    from release_safety.blob_inventory import inventory_detail_blobs

    ckpt = tmp_path / "inv.json"
    client, bucket = _client_with({_blob("00", 1)})
    inventory_detail_blobs(client, shards=("00",), checkpoint_path=ckpt)

    saved = json.loads(ckpt.read_text())
    saved["prefix"] = "shared/details/OTHER"
    ckpt.write_text(json.dumps(saved))

    bucket.listed.clear()
    inventory_detail_blobs(client, shards=("00",), checkpoint_path=ckpt)

    assert f"{PREFIX}/00" in bucket.listed


def test_checkpoint_is_ignored_when_only_middle_shards_change(tmp_path):
    """Equal-sized shard sets with equal endpoints are still different sets."""
    from release_safety.blob_inventory import inventory_detail_blobs

    ckpt = tmp_path / "inv.json"
    client, bucket = _client_with(
        {_blob("00", 1), _blob("0a", 1), _blob("80", 1), _blob("ff", 1)}
    )
    inventory_detail_blobs(
        client, shards=("00", "0a", "ff"), checkpoint_path=ckpt,
    )

    bucket.listed.clear()
    second = inventory_detail_blobs(
        client, shards=("00", "80", "ff"), checkpoint_path=ckpt,
    )

    assert second.resumed_shards == 0
    assert f"{PREFIX}/80" in bucket.listed


# ---------------------------------------------------------------------------
# Progress + determinism
# ---------------------------------------------------------------------------


def test_inventory_reports_progress_per_completed_shard():
    from release_safety.blob_inventory import inventory_detail_blobs

    seen = []
    client, _ = _client_with({_blob("00", 1), _blob("0a", 1)})

    inventory_detail_blobs(
        client, shards=("00", "0a"), progress=lambda done, total, objs: seen.append(done),
    )

    assert seen == [1, 2]


def test_inventory_failures_are_sorted_for_reproducible_reports():
    """Sets iterated into a shipped report make the report non-reproducible."""
    from release_safety.blob_inventory import inventory_detail_blobs

    shards = ("00", "0a", "ff")
    client, _ = _client_with(
        {_blob(s, 1) for s in shards},
        fail_plan={f"{PREFIX}/ff": 10_000, f"{PREFIX}/00": 10_000},
    )

    inv = inventory_detail_blobs(client, shards=shards, max_attempts=2)

    assert [f.shard for f in inv.failures] == ["00", "ff"]


def test_inventory_records_elapsed_time():
    from release_safety.blob_inventory import inventory_detail_blobs

    client, _ = _client_with({_blob("00", 1)})
    inv = inventory_detail_blobs(client, shards=("00",))

    assert inv.elapsed_seconds >= 0.0
