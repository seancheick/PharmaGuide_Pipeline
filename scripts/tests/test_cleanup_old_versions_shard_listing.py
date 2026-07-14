"""Regression tests for detail-blob shard listing in cleanup_old_versions.py."""

from __future__ import annotations

import os
import sys
import json
import pytest

_scripts_dir = os.path.join(os.path.dirname(__file__), "..")
if _scripts_dir not in sys.path:
    sys.path.insert(0, os.path.abspath(_scripts_dir))


class _Bucket:
    def __init__(self, objects: set[str], downloads: dict[str, bytes] | None = None) -> None:
        self.objects = objects
        self.downloads = downloads or {}
        self.listed_paths: list[str] = []

    def list(self, path: str, options=None):
        self.listed_paths.append(path)
        if path == "shared/details/sha256":
            raise RuntimeError("root shard listing timed out")

        prefix = path.rstrip("/") + "/"
        offset = int((options or {}).get("offset", 0))
        limit = int((options or {}).get("limit", 1000))
        names = sorted(
            full[len(prefix):]
            for full in self.objects
            if full.startswith(prefix) and "/" not in full[len(prefix):]
        )
        return [{"name": name} for name in names[offset:offset + limit]]

    def download(self, path: str) -> bytes:
        if path not in self.downloads:
            raise RuntimeError(f"not found: {path}")
        return self.downloads[path]


class _Storage:
    def __init__(self, bucket: _Bucket) -> None:
        self.bucket = bucket

    def from_(self, bucket_name: str) -> _Bucket:
        assert bucket_name == "pharmaguide"
        return self.bucket


class _Client:
    def __init__(self, objects: set[str], downloads: dict[str, bytes] | None = None) -> None:
        self.bucket = _Bucket(objects, downloads=downloads)
        self.storage = _Storage(self.bucket)


def test_list_all_blob_shard_dirs_is_deterministic_and_does_not_touch_storage():
    from cleanup_old_versions import list_all_blob_shard_dirs

    client = _Client(set())
    shards = list_all_blob_shard_dirs(client)

    assert len(shards) == 256
    assert shards[0] == "00"
    assert shards[-1] == "ff"
    assert client.bucket.listed_paths == []


def test_detect_orphan_blobs_no_longer_depends_on_root_shard_listing():
    from cleanup_old_versions import detect_orphan_blobs

    kept = "0a" * 32
    orphan = "ff" * 32
    objects = {
        f"shared/details/sha256/{kept[:2]}/{kept}.json",
        f"shared/details/sha256/{orphan[:2]}/{orphan}.json",
    }
    client = _Client(objects)

    orphans = detect_orphan_blobs(
        client,
        referenced_paths={f"shared/details/sha256/{kept[:2]}/{kept}.json"},
    )

    assert orphans == [f"shared/details/sha256/{orphan[:2]}/{orphan}.json"]
    assert "shared/details/sha256" not in client.bucket.listed_paths
    assert "shared/details/sha256/0a" in client.bucket.listed_paths
    assert "shared/details/sha256/ff" in client.bucket.listed_paths


def test_cleanup_orphan_blobs_dry_run_suppresses_large_path_listing(capsys):
    from cleanup_old_versions import (
        ORPHAN_DRY_RUN_SAMPLE_LIMIT,
        cleanup_orphan_blobs,
    )

    kept = "0a" * 32
    orphan_hashes = [f"{idx:064x}" for idx in range(100, 100 + ORPHAN_DRY_RUN_SAMPLE_LIMIT + 5)]
    objects = {f"shared/details/sha256/{kept[:2]}/{kept}.json"}
    objects.update(
        f"shared/details/sha256/{h[:2]}/{h}.json"
        for h in orphan_hashes
    )
    index = {
        "kept": {
            "storage_path": f"shared/details/sha256/{kept[:2]}/{kept}.json",
        },
    }
    client = _Client(
        objects,
        downloads={"vTEST/detail_index.json": json.dumps(index).encode("utf-8")},
    )

    deleted, failed = cleanup_orphan_blobs(client, "TEST", dry_run=True)
    out = capsys.readouterr().out

    assert deleted == len(orphan_hashes)
    assert failed == 0
    assert out.count("[DRY-RUN] Would delete orphan") == ORPHAN_DRY_RUN_SAMPLE_LIMIT
    assert "more orphan blob(s)" in out
    assert "exact count preserved" in out


def test_list_blobs_in_shard_strict_raises_on_repeated_page_failure(monkeypatch):
    import cleanup_old_versions as cov

    client = _Client(set())
    attempts = []

    def fail_page(_bucket, prefix, offset, timeout_seconds=None):
        attempts.append((prefix, offset))
        raise cov.StorageListPageTimeout("injected storage timeout")

    monkeypatch.setattr(cov, "_list_storage_page", fail_page)
    monkeypatch.setattr(cov.time, "sleep", lambda _seconds: None)

    with pytest.raises(RuntimeError, match="Blob listing failed"):
        cov.list_blobs_in_shard(client, "ab", max_retries=3, strict=True)

    assert attempts == [
        ("shared/details/sha256/ab", 0),
        ("shared/details/sha256/ab", 0),
        ("shared/details/sha256/ab", 0),
    ]
