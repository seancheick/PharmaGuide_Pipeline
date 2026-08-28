"""One canary recovery is explicit, locked, and byte-verified."""

from __future__ import annotations

import hashlib
import importlib.util


class _Bucket:
    def __init__(self, objects, lock_path):
        self.objects = dict(objects)
        self.lock_path = lock_path
        self.lock_seen_during_copy = []

    def download(self, path):
        if path not in self.objects:
            raise RuntimeError(f"not found: {path}")
        return self.objects[path]

    def list(self, path="", options=None):
        base = path.rstrip("/") + "/" if path else ""
        names = sorted(
            full[len(base):]
            for full in self.objects
            if full.startswith(base) and "/" not in full[len(base):]
        )
        return [{"name": name} for name in names]

    def copy(self, src, dst):
        self.lock_seen_during_copy.append(self.lock_path.exists())
        self.objects[dst] = self.objects[src]
        return {"ok": True}

    def remove(self, paths):
        for path in paths:
            self.objects.pop(path, None)
        return [{"name": path} for path in paths]


class _Client:
    def __init__(self, bucket):
        self.bucket = bucket
        self.storage = self

    def from_(self, _name):
        return self.bucket


def test_execute_restores_one_blob_under_lock_and_proves_exact_bytes(tmp_path):
    spec = importlib.util.find_spec("recover_quarantined_blob")
    assert spec is not None, "the canary needs a reviewed recovery command"

    import recover_quarantined_blob as cli

    payload = b'{"verified":"canary"}'
    blob_hash = hashlib.sha256(payload).hexdigest()
    run_date = "2026-08-28"
    quarantine = (
        f"shared/quarantine/{run_date}/{blob_hash[:2]}/{blob_hash}.json"
    )
    active = f"shared/details/sha256/{blob_hash[:2]}/{blob_hash}.json"
    lock_path = tmp_path / "release.lock"
    bucket = _Bucket({quarantine: payload}, lock_path)

    exit_code = cli.main([
        "--blob-hash", blob_hash,
        "--expected-sha256", blob_hash,
        "--quarantine-date", run_date,
        "--execute",
        "--lock-path", str(lock_path),
    ], client=_Client(bucket))

    assert exit_code == 0
    assert bucket.objects[active] == payload
    assert quarantine not in bucket.objects
    assert bucket.lock_seen_during_copy == [True]
    assert not lock_path.exists()


def test_wrong_expected_hash_refuses_without_touching_storage(tmp_path):
    spec = importlib.util.find_spec("recover_quarantined_blob")
    assert spec is not None, "the canary needs a reviewed recovery command"

    import recover_quarantined_blob as cli

    payload = b"canary"
    blob_hash = hashlib.sha256(payload).hexdigest()
    run_date = "2026-08-28"
    quarantine = (
        f"shared/quarantine/{run_date}/{blob_hash[:2]}/{blob_hash}.json"
    )
    lock_path = tmp_path / "release.lock"
    bucket = _Bucket({quarantine: payload}, lock_path)
    before = dict(bucket.objects)

    exit_code = cli.main([
        "--blob-hash", blob_hash,
        "--expected-sha256", "0" * 64,
        "--quarantine-date", run_date,
        "--execute",
        "--lock-path", str(lock_path),
    ], client=_Client(bucket))

    assert exit_code != 0
    assert bucket.objects == before
    assert bucket.lock_seen_during_copy == []
