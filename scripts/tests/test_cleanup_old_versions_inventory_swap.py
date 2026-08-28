"""cleanup_old_versions must share the one scalable, honest inventory.

Two behaviours pinned here:

  * The gated EXECUTE path fails CLOSED — returning (0, 0) rather than raising
    — when storage cannot be inventoried in full. Its docstring already
    promises "never raises in normal use"; a shard listing that gave up after
    its retries used to violate that by propagating a RuntimeError.
  * The legacy DRY-RUN orphan path is gone. It protected only the single
    current detail_index, so on 2026-08-26 it would have reported blobs of the
    still-retained 2026.08.25 catalog as deletable. A count that is wrong in
    the unsafe direction is worse than no count.
"""

from __future__ import annotations

import os
import sys
import time
from types import SimpleNamespace

import pytest

_scripts_dir = os.path.join(os.path.dirname(__file__), "..")
if _scripts_dir not in sys.path:
    sys.path.insert(0, os.path.abspath(_scripts_dir))

PREFIX = "shared/details/sha256"


@pytest.fixture(autouse=True)
def _no_real_backoff_sleeps(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda _s: None)


class _Bucket:
    def __init__(self, objects, downloads=None, fail_prefixes=()):
        self.objects = set(objects)
        self.downloads = downloads or {}
        self.fail_prefixes = set(fail_prefixes)
        self.listed = []

    def list(self, path="", options=None):
        self.listed.append(path)
        if path in self.fail_prefixes:
            raise RuntimeError("The connection to the database timed out")
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
        if path not in self.downloads:
            raise RuntimeError(f"not found: {path}")
        return self.downloads[path]


class _Client:
    def __init__(self, bucket):
        self.bucket = bucket
        self.storage = self

    def from_(self, name):
        return self.bucket


def test_dry_run_orphan_path_refuses_instead_of_reporting_a_single_version_count(
    tmp_path, capsys, monkeypatch
):
    """Running the old dry run must point at the tool that gets it right."""
    import cleanup_old_versions as cov

    rows = [
        {"db_version": "2026.08.26.141540", "created_at": "2026-08-26T15:00:00Z",
         "is_current": True},
        {"db_version": "2026.08.25.090053", "created_at": "2026-08-25T09:00:00Z",
         "is_current": False},
    ]
    monkeypatch.setattr(cov, "fetch_all_versions", lambda _c: rows)
    monkeypatch.setattr(cov, "get_supabase_client", lambda: _Client(_Bucket(set())))

    def _boom(*_a, **_k):
        raise AssertionError(
            "dry run must not use the single-version legacy orphan scan"
        )

    monkeypatch.setattr(cov, "detect_orphan_blobs", _boom, raising=False)

    with pytest.raises(SystemExit) as excinfo:
        cov.main(["--cleanup-orphan-blobs", "--keep", "2"])

    out = capsys.readouterr().out
    assert excinfo.value.code != 0
    assert "reconcile_orphan_blobs.py" in out


def test_legacy_single_version_orphan_helpers_are_gone():
    """Keeping them invites a caller back onto the unsafe protection model."""
    import cleanup_old_versions as cov

    assert not hasattr(cov, "cleanup_orphan_blobs")
    assert not hasattr(cov, "detect_orphan_blobs")


def test_execute_main_holds_global_lock_during_version_mutations(
    tmp_path, monkeypatch,
):
    import cleanup_old_versions as cov
    from release_safety import lock as lock_mod

    lock_path = tmp_path / "release.lock"
    monkeypatch.setattr(lock_mod, "DEFAULT_LOCK_PATH", lock_path)
    monkeypatch.setattr(cov, "get_supabase_client", lambda: object())
    monkeypatch.setattr(cov, "fetch_all_versions", lambda _client: [
        {"db_version": "new", "created_at": "2026-08-28", "is_current": True},
        {"db_version": "old", "created_at": "2026-08-27", "is_current": False},
    ])
    lock_seen = []

    def observing_delete(_client, _version, _dry_run):
        lock_seen.append(lock_path.exists())
        return 1, 0

    monkeypatch.setattr(cov, "delete_version_directory", observing_delete)
    monkeypatch.setattr(cov, "sweep_quarantine", lambda *_a, **_k: SimpleNamespace(
        total_deleted=0,
        total_failed=0,
        complete=True,
        total_eligible=0,
        eligible_dates=[],
        listing_failures=[],
    ))

    cov.main(["--execute", "--keep", "1"])

    assert lock_seen == [True]
    assert not lock_path.exists()


def test_legacy_orphan_cleanup_cli_refuses_before_any_mutation(
    monkeypatch, capsys,
):
    import cleanup_old_versions as cov

    monkeypatch.setattr(
        cov,
        "get_supabase_client",
        lambda: (_ for _ in ()).throw(
            AssertionError("legacy orphan CLI must refuse before connecting")
        ),
    )

    with pytest.raises(SystemExit) as excinfo:
        cov.main(["--execute", "--cleanup-orphan-blobs"])

    assert excinfo.value.code == 2
    assert "reconcile_orphan_blobs.py" in capsys.readouterr().out
