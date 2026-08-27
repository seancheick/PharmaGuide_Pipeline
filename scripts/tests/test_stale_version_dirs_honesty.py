"""Version-directory listings must fail closed, never truncate silently.

Both ``delete_stale_version_dirs._list_paginated`` and
``storage_audit._list_paginated`` caught every listing exception with
``break`` — a mid-listing failure returned the partial accumulation as if it
were the complete answer. Downstream that becomes a deletion plan built on an
undercount ("one ReadTimeout silently reports 0 blobs in storage"), and a
partially-enumerated directory deleted partially then reported done — the
likely origin of the 1-object residue dirs such as ``v2026.08.24.165613``.

Same disease the quarantine sweeper had; same cure: retry transient blips,
raise on give-up, and carry completeness explicitly in the new
version-directory inventory.
"""

from __future__ import annotations

import os
import sys
import time

import pytest

_scripts_dir = os.path.join(os.path.dirname(__file__), "..")
if _scripts_dir not in sys.path:
    sys.path.insert(0, os.path.abspath(_scripts_dir))


@pytest.fixture(autouse=True)
def _no_real_backoff_sleeps(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda _s: None)


def _storage_error():
    from storage3.exceptions import StorageApiError

    return StorageApiError(
        "The connection to the database timed out", "DatabaseTimeout", 544,
    )


class _Bucket:
    def __init__(self, objects, *, fail_prefix_after_page=None, fail_always=()):
        self.objects = dict(objects)
        self.fail_prefix_after_page = dict(fail_prefix_after_page or {})
        self.fail_always = set(fail_always)
        self.calls = {}

    def list(self, path="", options=None):
        opts = options or {}
        limit = int(opts.get("limit", 1000))
        offset = int(opts.get("offset", 0))
        self.calls[path] = self.calls.get(path, 0) + 1
        if path in self.fail_always:
            raise _storage_error()
        threshold = self.fail_prefix_after_page.get(path)
        if threshold is not None and offset >= threshold:
            raise _storage_error()
        base = path.rstrip("/") + "/" if path else ""
        names, seen = [], set()
        for full in sorted(self.objects):
            if not full.startswith(base):
                continue
            rest = full[len(base):]
            if "/" not in rest:
                names.append((rest, {"size": len(self.objects[full])}))
            else:
                head = rest.split("/", 1)[0]
                if head not in seen:
                    seen.add(head)
                    names.append((head, None))
        page = names[offset:offset + limit]
        return [
            {"name": n, "metadata": md} if md else {"name": n}
            for n, md in page
        ]


class _Client:
    def __init__(self, bucket):
        self.bucket = bucket
        self.storage = self

    def from_(self, _name):
        return self.bucket


def _dir_objects(version, count, prefix=""):
    return {
        f"v{version}/{prefix}obj{i:05d}.bin": b"x" * 10 for i in range(count)
    }


# ---------------------------------------------------------------------------
# The raw helpers must raise, not truncate
# ---------------------------------------------------------------------------


def test_stale_dirs_list_paginated_raises_instead_of_returning_partial():
    from release_safety.delete_stale_version_dirs import _list_paginated

    objects = _dir_objects("2026.08.24.165613", 1500)
    bucket = _Bucket(
        objects,
        fail_prefix_after_page={"v2026.08.24.165613": 1000},
    )

    with pytest.raises(Exception):
        _list_paginated(_Client(bucket), "pharmaguide", "v2026.08.24.165613")


def test_stale_dirs_list_paginated_retries_transient_blips():
    from release_safety.delete_stale_version_dirs import _list_paginated

    objects = _dir_objects("2026.08.24.165613", 5)
    bucket = _Bucket(objects)
    real_list = bucket.list
    state = {"n": 0}

    def flaky(path="", options=None):
        state["n"] += 1
        if state["n"] == 1:
            raise _storage_error()
        return real_list(path=path, options=options)

    bucket.list = flaky

    items = _list_paginated(_Client(bucket), "pharmaguide", "v2026.08.24.165613")

    assert len(items) == 5


def test_storage_audit_list_paginated_raises_instead_of_returning_empty():
    """The audit's 'valid: 0 blobs in storage' failure mode."""
    from release_safety.storage_audit import _list_paginated

    bucket = _Bucket({}, fail_always={"shared/details/sha256/aa"})

    with pytest.raises(Exception):
        _list_paginated(_Client(bucket), "pharmaguide", "shared/details/sha256/aa")


def test_compute_delete_plan_fails_closed_when_a_dir_cannot_be_enumerated():
    """A plan built on a truncated enumeration deletes part of a directory and
    calls the directory done. Refuse to produce a plan at all."""
    from release_safety.delete_stale_version_dirs import compute_delete_plan

    version = "2026.08.24.165613"
    bucket = _Bucket(
        _dir_objects(version, 3),
        fail_always={f"v{version}"},
    )
    client = _Client(bucket)
    client._tables = {"export_manifest": []}

    def table(name):
        class _T:
            def select(self, *_a, **_k):
                return self

            def execute(self):
                return type("_R", (), {"data": []})()

        return _T()

    client.table = table

    with pytest.raises(Exception):
        compute_delete_plan(client)


# ---------------------------------------------------------------------------
# Completeness-bearing version-directory inventory
# ---------------------------------------------------------------------------


def _manifest_client(bucket, versions=()):
    client = _Client(bucket)

    def table(name):
        class _T:
            def select(self, *_a, **_k):
                return self

            def execute(self):
                rows = [{"db_version": v} for v in versions]
                return type("_R", (), {"data": rows})()

        return _T()

    client.table = table
    return client


def test_version_dir_inventory_reports_objects_bytes_and_manifest_link():
    from release_safety.delete_stale_version_dirs import inventory_version_dirs

    keep = "2026.08.27.162958"
    stale = "2026.08.24.165613"
    objects = {**_dir_objects(keep, 3), **_dir_objects(stale, 2)}
    bucket = _Bucket(objects)
    client = _manifest_client(bucket, versions=(keep,))

    inv = inventory_version_dirs(client)

    assert inv.complete is True
    by_name = {d.version: d for d in inv.dirs}
    assert by_name[keep].in_manifest is True
    assert by_name[stale].in_manifest is False
    assert by_name[stale].object_count == 2
    assert by_name[stale].total_bytes == 20


def test_version_dir_inventory_marks_unlistable_dirs_and_is_incomplete():
    from release_safety.delete_stale_version_dirs import inventory_version_dirs

    good = "2026.08.27.162958"
    bad = "2026.08.24.165613"
    objects = {**_dir_objects(good, 1), **_dir_objects(bad, 1)}
    bucket = _Bucket(objects, fail_always={f"v{bad}"})
    client = _manifest_client(bucket, versions=(good,))

    inv = inventory_version_dirs(client)

    assert inv.complete is False
    by_name = {d.version: d for d in inv.dirs}
    assert by_name[bad].complete is False
    assert by_name[good].complete is True
    assert inv.failures, "the unlistable dir must be reported, not omitted"


def test_version_dir_inventory_text_report_shows_exact_expectations():
    from release_safety.delete_stale_version_dirs import inventory_version_dirs

    stale = "2026.08.24.165613"
    bucket = _Bucket(_dir_objects(stale, 2))
    client = _manifest_client(bucket, versions=())

    inv = inventory_version_dirs(client)
    text = inv.text_report()

    assert stale in text
    assert "2" in text  # exact object expectation
    assert "COMPLETE" in text.upper() or "complete" in text
