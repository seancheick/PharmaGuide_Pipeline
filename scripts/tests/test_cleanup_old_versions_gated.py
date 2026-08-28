"""Integration guards for the shared quarantine shard engine."""

from __future__ import annotations

import hashlib
import os
import sys
import threading
import time

_scripts_dir = os.path.join(os.path.dirname(__file__), "..")
if _scripts_dir not in sys.path:
    sys.path.insert(0, os.path.abspath(_scripts_dir))


def _hash(shard: int, index: int) -> str:
    return f"{shard:02x}{index:062x}"


class _Bucket:
    def __init__(self):
        self.objects: dict[str, bytes] = {}
        self.lock = threading.Lock()
        self.copy_clients_by_thread: dict[int, set[int]] = {}
        self.owner = None
        self.copy_delay = 0.0

    @staticmethod
    def _etag(data: bytes) -> str:
        return f'"{hashlib.md5(data).hexdigest()}"'

    def list(self, path="", options=None):
        options = options or {}
        limit = int(options.get("limit", 1000))
        offset = int(options.get("offset", 0))
        base = path.rstrip("/") + "/" if path else ""
        names = sorted(
            full[len(base):]
            for full in self.objects
            if full.startswith(base) and "/" not in full[len(base):]
        )
        return [
            {
                "name": name,
                "metadata": {
                    "size": len(self.objects[base + name]),
                    "eTag": self._etag(self.objects[base + name]),
                },
            }
            for name in names[offset:offset + limit]
        ]

    def copy(self, source, target):
        with self.lock:
            self.copy_clients_by_thread.setdefault(
                threading.get_ident(), set()
            ).add(id(self.owner))
        time.sleep(self.copy_delay)
        self.objects[target] = self.objects[source]
        return {"ok": True}

    def remove(self, paths):
        for path in paths:
            self.objects.pop(path, None)
        return [{"name": path} for path in paths]


class _Client:
    def __init__(self, bucket: _Bucket):
        self.bucket = bucket

    @property
    def storage(self):
        return self

    def from_(self, _name):
        self.bucket.owner = self
        return self.bucket


def _seed(bucket: _Bucket, count: int):
    from release_safety.blob_inventory import ObjectFingerprint

    hashes = {_hash(0, index) for index in range(count)}
    for blob_hash in hashes:
        bucket.objects[
            f"shared/details/sha256/{blob_hash[:2]}/{blob_hash}.json"
        ] = b"data-" + blob_hash[:8].encode()
    fingerprints = {
        blob_hash: ObjectFingerprint(
            size=len(b"data-" + blob_hash[:8].encode()),
            etag=bucket._etag(b"data-" + blob_hash[:8].encode()),
        )
        for blob_hash in hashes
    }
    return hashes, fingerprints


def test_quarantine_batch_uses_one_client_per_copy_thread():
    import cleanup_old_versions as cleanup

    bucket = _Bucket()
    bucket.copy_delay = 0.01
    hashes, fingerprints = _seed(bucket, 12)
    created: list[_Client] = []

    def client_factory():
        client = _Client(bucket)
        created.append(client)
        return client

    moved, failed, _ = cleanup.quarantine_orphan_blob_batch(
        _Client(bucket),
        hashes,
        run_date="2026-08-28",
        source_fingerprints=fingerprints,
        max_workers=4,
        client_factory=client_factory,
    )

    assert (moved, failed) == (12, 0)
    assert created
    assert all(
        len(client_ids) == 1
        for client_ids in bucket.copy_clients_by_thread.values()
    )


def test_quarantine_batch_without_factory_stays_serial():
    import cleanup_old_versions as cleanup

    bucket = _Bucket()
    bucket.copy_delay = 0.005
    hashes, fingerprints = _seed(bucket, 6)

    moved, failed, _ = cleanup.quarantine_orphan_blob_batch(
        _Client(bucket),
        hashes,
        run_date="2026-08-28",
        source_fingerprints=fingerprints,
        max_workers=8,
    )

    assert (moved, failed) == (6, 0)
    assert len(bucket.copy_clients_by_thread) == 1


def test_sync_cleanup_owns_version_rows_only():
    from sync_to_supabase import _build_cleanup_args

    assert _build_cleanup_args(cleanup_keep=2) == [
        "--keep", "2", "--execute", "--cleanup-db",
    ]
