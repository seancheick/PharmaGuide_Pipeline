"""Test that cleanup_old_versions uses bucket-relative storage paths.

Regression guard for the 2026-05-13 double-prefix bug.

Background
==========
``client.storage.from_("pharmaguide").list(path=X)`` is bucket-relative —
``X`` should be ``v2026.05.13.162119``, NOT ``pharmaguide/v2026.05.13.162119``.

The buggy version of ``list_version_directory`` passed the double-prefixed
path, which caused the list call to return zero items silently. The
manifest-row delete then ran but the storage v-dir delete became a no-op
("No objects found — skipping"), leaving v-dirs orphaned in storage.

This was masked downstream by Bucket-2 (``delete_stale_version_dirs.py``)
which has its own correctly-prefixed listing — Bucket-2 would eventually
reap the orphan v-dirs in a separate run. But the bug meant the primary
cleanup path silently lied about its work.

These tests pin the path-shape contract so future refactors can't
re-introduce the double prefix.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any
import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))


# ---------------------------------------------------------------------------
# Spy: a bucket double that records every path it sees.
# ---------------------------------------------------------------------------


class _SpyBucket:
    """Records every path argument passed to list() and remove(). Tests
    assert the path is bucket-relative (no leading 'pharmaguide/' segment)."""

    def __init__(self):
        self.list_calls: list[str] = []
        self.remove_calls: list[list[str]] = []
        self._objects: dict[str, bytes] = {}

    def seed(self, path: str, content: bytes = b"x") -> None:
        self._objects[path] = content

    def list(self, path: str = "", options: dict | None = None):
        self.list_calls.append(path)
        prefix = (path.rstrip("/") + "/") if path else ""
        results = []
        seen_dirs: set[str] = set()
        for full in self._objects:
            if not full.startswith(prefix):
                continue
            rest = full[len(prefix):]
            if "/" not in rest:
                results.append({"name": rest, "metadata": {"size": len(self._objects[full])}})
            else:
                first = rest.split("/", 1)[0]
                if first not in seen_dirs:
                    seen_dirs.add(first)
                    results.append({"name": first})
        return results

    def remove(self, paths: list[str]):
        self.remove_calls.append(list(paths))
        for p in paths:
            self._objects.pop(p, None)
        return [{"name": p} for p in paths]

    def download(self, path: str) -> bytes:
        if path not in self._objects:
            raise RuntimeError(f"not found: {path}")
        return self._objects[path]


class _SpyStorage:
    def __init__(self):
        self.buckets: dict[str, _SpyBucket] = {}

    def from_(self, bucket: str) -> _SpyBucket:
        return self.buckets.setdefault(bucket, _SpyBucket())


class _SpyClient:
    def __init__(self):
        self.storage = _SpyStorage()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def _no_double_prefix(path: str) -> bool:
    """A bucket-relative path within the ``pharmaguide`` bucket must NOT
    itself start with ``pharmaguide/``. That would be the double-prefix bug.

    Empty path (= bucket root listing) is also accepted.
    """
    return not path.startswith("pharmaguide/")


def test_list_version_directory_uses_bucket_relative_path():
    """list_version_directory must call client.storage.from_('pharmaguide').list(path='v{ver}'),
    not path='pharmaguide/v{ver}'. The latter is the double-prefix bug."""
    from cleanup_old_versions import list_version_directory

    client = _SpyClient()
    bucket = client.storage.from_("pharmaguide")
    # Seed a realistic v-dir layout
    bucket.seed("v2026.05.13.162119/pharmaguide_core.db", b"db")
    bucket.seed("v2026.05.13.162119/detail_index.json", b"idx")

    paths = list_version_directory(client, "2026.05.13.162119")

    assert bucket.list_calls, "list() never called"
    for call_path in bucket.list_calls:
        assert _no_double_prefix(call_path), (
            f"list_version_directory called list(path={call_path!r}) — "
            f"that's the double-prefix bug. Bucket-relative path must be "
            f"'v...' not 'pharmaguide/v...'."
        )

    # Returned paths should also be bucket-relative (so remove() can use them)
    assert len(paths) == 2
    for p in paths:
        assert _no_double_prefix(p), (
            f"list_version_directory returned path {p!r} with 'pharmaguide/' "
            f"prefix. Subsequent remove() would fail silently."
        )


def test_delete_version_directory_deletes_actual_storage():
    """End-to-end: delete_version_directory must actually clear the v-dir
    from storage when given a populated v-dir. Pre-fix, this returned
    (0, 0) "skipping — no objects found" because the list path was wrong."""
    from cleanup_old_versions import delete_version_directory

    client = _SpyClient()
    bucket = client.storage.from_("pharmaguide")
    bucket.seed("v2026.05.13.162119/pharmaguide_core.db", b"db")
    bucket.seed("v2026.05.13.162119/detail_index.json", b"idx")

    deleted, failed = delete_version_directory(
        client, "2026.05.13.162119", dry_run=False,
    )

    assert deleted == 2, (
        f"Expected 2 objects deleted, got deleted={deleted} failed={failed}. "
        f"Pre-fix this returned 0 because the list path was wrong."
    )
    assert failed == 0
    # Storage should now be empty for this v-dir
    assert bucket._objects == {}, (
        f"v-dir not actually emptied; objects remain: {list(bucket._objects)}"
    )

    # Every remove call should have used bucket-relative paths
    for rm_batch in bucket.remove_calls:
        for p in rm_batch:
            assert _no_double_prefix(p), (
                f"remove() called with double-prefixed path {p!r}"
            )


def test_list_version_directory_returns_empty_when_dir_truly_empty():
    """Sanity: if the v-dir genuinely doesn't exist in storage, return []."""
    from cleanup_old_versions import list_version_directory

    client = _SpyClient()
    # No seeds — bucket is empty
    paths = list_version_directory(client, "v_does_not_exist")
    assert paths == []
