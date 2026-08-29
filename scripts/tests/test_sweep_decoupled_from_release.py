"""Catalog releases must never hard-delete quarantine as a side effect.

Every real release calls ``cleanup_old_versions.py --execute``, which swept
expired quarantine automatically — an irreversible delete riding along with
catalog publishing, unattended. The release path now only REPORTS eligible
sweep work; the hard delete lives exclusively in the dedicated, gated
``scripts/sweep_quarantine.py`` maintenance command.
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
EXPIRED_DATE = "2026-07-17"


@pytest.fixture(autouse=True)
def _no_real_backoff_sleeps(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda _s: None)


class _Bucket:
    def __init__(self, objects):
        self.objects = dict(objects)
        self.removed = []

    def list(self, path="", options=None):
        opts = options or {}
        limit = int(opts.get("limit", 1000))
        offset = int(opts.get("offset", 0))
        base = path.rstrip("/") + "/" if path else ""
        names, seen = [], set()
        for full in sorted(self.objects):
            if not full.startswith(base):
                continue
            rest = full[len(base):]
            head = rest.split("/", 1)[0]
            if head in seen:
                continue
            seen.add(head)
            if "/" in rest:
                names.append({"name": head})
            else:
                names.append({"name": head, "metadata": {
                    "size": len(self.objects[full]), "eTag": '"et"',
                }})
        return names[offset:offset + limit]

    def remove(self, paths):
        self.removed.extend(paths)
        for p in paths:
            self.objects.pop(p, None)
        return [{"name": p} for p in paths]


class _Table:
    def __init__(self, rows):
        self._rows = rows

    def select(self, *_a, **_k):
        return self

    def order(self, *_a, **_k):
        return self

    def eq(self, *_a, **_k):
        return self

    def delete(self):
        return self

    def execute(self):
        return type("_R", (), {"data": list(self._rows)})()


class _Client:
    def __init__(self, bucket, manifest_rows):
        self.bucket = bucket
        self.storage = self
        self._manifest_rows = manifest_rows

    def from_(self, _name):
        return self.bucket

    def table(self, name):
        if name == "export_manifest":
            return _Table(self._manifest_rows)
        return _Table([])


def _expired_path(n):
    h = f"{n:064x}"
    return f"{QROOT}/{EXPIRED_DATE}/{h[:2]}/{h}.json"


def test_release_execute_reports_but_never_hard_deletes_quarantine(
    monkeypatch, capsys, tmp_path,
):
    import cleanup_old_versions as cov

    objects = {_expired_path(i): b"x" for i in range(3)}
    rows = [
        {"db_version": "2026.08.27.162958", "created_at": "2026-08-27",
         "is_current": True},
        {"db_version": "2026.08.26.141540", "created_at": "2026-08-26",
         "is_current": False},
    ]
    client = _Client(_Bucket(objects), rows)
    monkeypatch.setattr(cov, "get_supabase_client", lambda: client)

    try:
        result = cov.main([
            "--execute", "--keep", "2",
            "--lock-path", str(tmp_path / "release.lock"),
        ])
    except SystemExit as exc:  # some paths exit, some return — both fine
        result = exc.code

    out = capsys.readouterr().out
    assert result in (0, None)
    for path in objects:
        assert path in client.bucket.objects, (
            "a catalog release must never hard-delete quarantine"
        )
    assert client.bucket.removed == []
    assert "sweep_quarantine.py" in out, (
        "the release must point at the dedicated maintenance command"
    )
    assert EXPIRED_DATE in out, "eligible sweep work must be reported"


def test_release_execute_stays_quiet_when_nothing_is_eligible(
    monkeypatch, capsys, tmp_path,
):
    import cleanup_old_versions as cov

    rows = [
        {"db_version": "2026.08.27.162958", "created_at": "2026-08-27",
         "is_current": True},
    ]
    client = _Client(_Bucket({}), rows)
    monkeypatch.setattr(cov, "get_supabase_client", lambda: client)

    try:
        result = cov.main([
            "--execute", "--keep", "2",
            "--lock-path", str(tmp_path / "release.lock"),
        ])
    except SystemExit as exc:
        result = exc.code

    assert result in (0, None)
    assert client.bucket.removed == []
