"""Shard-listing guards for cleanup_old_versions.

Most of this file's original coverage moved when the inventory was extracted
into ``release_safety.blob_inventory``. The helpers it tested
(``list_all_blob_shard_dirs``, ``detect_orphan_blobs``, ``cleanup_orphan_blobs``,
``list_blobs_in_shard``) no longer exist. Equivalent assertions now live in:

  * shard enumeration never touches the root prefix
      -> test_release_safety_blob_inventory.test_inventory_never_lists_the_shard_root
  * a shard that keeps failing does not silently truncate the listing
      -> test_release_safety_blob_inventory
         .test_inventory_marks_itself_incomplete_when_a_shard_never_succeeds
         .test_incomplete_inventory_raises_when_completeness_is_required
  * dry-run orphan reporting
      -> test_release_safety_orphan_reconcile (now retained-version aware)

What stays here is the guard at THIS layer: the gated cleanup entry point must
never issue a listing of ``shared/details/sha256`` itself. That call returns
HTTP 544 DatabaseTimeout deterministically in production (~134k objects), and
it is the specific regression this file was created to prevent.
"""

from __future__ import annotations

import json
import os
import sys

_scripts_dir = os.path.join(os.path.dirname(__file__), "..")
if _scripts_dir not in sys.path:
    sys.path.insert(0, os.path.abspath(_scripts_dir))

PREFIX = "shared/details/sha256"


class _Bucket:
    def __init__(self, objects):
        self.objects = set(objects)
        self.listed_paths: list[str] = []

    def list(self, path="", options=None):
        self.listed_paths.append(path)
        if path == PREFIX:
            raise RuntimeError("root shard listing timed out (HTTP 544)")
        base = path.rstrip("/") + "/" if path else ""
        opts = options or {}
        limit = int(opts.get("limit", 1000))
        offset = int(opts.get("offset", 0))
        names = sorted(
            full[len(base):]
            for full in self.objects
            if full.startswith(base) and "/" not in full[len(base):]
        )
        return [{"name": n, "metadata": {"size": 10}}
                for n in names[offset:offset + limit]]

    def download(self, path):
        raise RuntimeError(f"not found: {path}")


class _EmptyTable:
    """Registry with no ACTIVE/VALIDATING rows — the gate still runs, and the
    listing assertions below happen before it decides anything."""

    def select(self, *_a, **_k):
        return self

    def eq(self, *_a, **_k):
        return self

    def order(self, *_a, **_k):
        return self

    def execute(self):
        return type("_Resp", (), {"data": []})()


class _Client:
    def __init__(self, objects):
        self.bucket = _Bucket(objects)
        self.storage = self

    def from_(self, name):
        assert name == "pharmaguide"
        return self.bucket

    def table(self, _name):
        return _EmptyTable()


def test_gated_cleanup_never_lists_the_shard_root(tmp_path):
    """The root prefix 544s at production scale — enumerate 00..ff instead."""
    from cleanup_old_versions import cleanup_orphan_blobs_with_gates

    kept = "aa" * 32
    client = _Client({f"{PREFIX}/aa/{kept}.json"})

    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    (dist_dir / "detail_index.json").write_text(json.dumps({
        "_meta": {"db_version": "2026.08.26.141540"},
        "1": {
            "blob_sha256": kept,
            "storage_path": f"{PREFIX}/aa/{kept}.json",
            "blob_version": 1,
        },
    }))

    cleanup_orphan_blobs_with_gates(
        client,
        "2026.08.26.141540",
        flutter_repo_path=str(tmp_path / "flutter"),
        dist_dir=str(dist_dir),
        retained_versions=("2026.08.26.141540",),
    )

    assert PREFIX not in client.bucket.listed_paths
    assert f"{PREFIX}/aa" in client.bucket.listed_paths
    assert f"{PREFIX}/ff" in client.bucket.listed_paths
