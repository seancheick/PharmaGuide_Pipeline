"""A manifest row may die only after its storage directory is PROVEN empty.

The stranding machine, reproduced live (9 stale dirs / 1,288 objects):
``list_version_directory`` swallowed listing failures into ``[]`` and listed
only the top level (no recursion, no pagination), and ``main`` deleted the
manifest row unconditionally — so a partial or failed storage deletion still
lost its row, making the directory invisible to every future manifest-driven
run. ``v2026.08.25.090053`` was stranded exactly this way at the 08.27
publish.

New contract: enumerate recursively (raise on listing failure), batch-delete,
re-enumerate as the absence proof, and delete the manifest row ONLY when the
directory is verified empty. Partial work keeps the row so the next run
resumes. Storage-driven reconciliation reports manifest-less directories so
they can never become permanently invisible.
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


class _Bucket:
    def __init__(self, objects):
        self.objects = dict(objects)
        self.removed = []
        self.fail_remove_containing = set()
        self.silently_keep_on_remove = set()
        self.list_raises_for = set()

    def list(self, path="", options=None):
        if path in self.list_raises_for:
            raise RuntimeError("The connection to the database timed out")
        opts = options or {}
        limit = int(opts.get("limit", 1000))
        offset = int(opts.get("offset", 0))
        base = path.rstrip("/") + "/" if path else ""
        results, seen = [], set()
        for full in sorted(self.objects):
            if not full.startswith(base):
                continue
            rest = full[len(base):]
            if "/" in rest:
                head = rest.split("/", 1)[0]
                if head not in seen:
                    seen.add(head)
                    results.append({"name": head})
            else:
                results.append({"name": rest, "metadata": {
                    "size": len(self.objects[full]), "eTag": '"et"',
                }})
        return results[offset:offset + limit]

    def remove(self, paths):
        for p in paths:
            if any(tag in p for tag in self.fail_remove_containing):
                raise RuntimeError(f"injected DELETE failure ({p})")
        for p in paths:
            self.removed.append(p)
            if p not in self.silently_keep_on_remove:
                self.objects.pop(p, None)
        return [{"name": p} for p in paths]


class _ManifestTable:
    def __init__(self, rows):
        self.rows = rows
        self.deleted_versions = []
        self._filters = []
        self._mode = None

    def select(self, *_a, **_k):
        self._mode = "select"
        return self

    def order(self, *_a, **_k):
        return self

    def eq(self, col, val):
        self._filters.append((col, val))
        return self

    def delete(self):
        self._mode = "delete"
        return self

    def execute(self):
        if self._mode == "delete":
            version = dict(self._filters).get("db_version")
            self.deleted_versions.append(version)
            self.rows[:] = [r for r in self.rows if r.get("db_version") != version]
            return type("_R", (), {"data": []})()
        return type("_R", (), {"data": [dict(r) for r in self.rows]})()


class _Client:
    def __init__(self, bucket, manifest_rows):
        self.bucket = bucket
        self.storage = self
        self.manifest = _ManifestTable(manifest_rows)

    def from_(self, _name):
        return self.bucket

    def table(self, name):
        if name == "export_manifest":
            # fresh filter state per call, shared row store
            table = _ManifestTable(self.manifest.rows)
            table.deleted_versions = self.manifest.deleted_versions
            return table
        return _ManifestTable([])


OLD = "2026.08.20.000000"
KEEP1 = "2026.08.27.162958"
KEEP2 = "2026.08.26.141540"


def _world(old_objects):
    rows = [
        {"db_version": KEEP1, "created_at": "3", "is_current": True},
        {"db_version": KEEP2, "created_at": "2", "is_current": False},
        {"db_version": OLD, "created_at": "1", "is_current": False},
    ]
    objects = dict(old_objects)
    client = _Client(_Bucket(objects), rows)
    return client


def _run(client, monkeypatch, tmp_path, *extra):
    import cleanup_old_versions as cov

    monkeypatch.setattr(cov, "get_supabase_client", lambda: client)
    try:
        result = cov.main([
            "--execute", "--cleanup-db", "--keep", "2",
            "--lock-path", str(tmp_path / "release.lock"),
            *extra,
        ])
    except SystemExit as exc:
        result = exc.code
    return result


def test_nested_objects_are_enumerated_and_fully_deleted(monkeypatch, tmp_path):
    """The live 9-dir drift is partial deletions: top-level files went, nested
    product_images/ survived. Enumeration must recurse."""
    client = _world({
        f"v{OLD}/pharmaguide_core.db": b"db",
        f"v{OLD}/detail_index.json": b"idx",
        f"v{OLD}/product_images/product_image_index.json": b"imgidx",
        f"v{OLD}/product_images/123.webp": b"img",
    })

    _run(client, monkeypatch, tmp_path)

    assert not any(p.startswith(f"v{OLD}/") for p in client.bucket.objects), (
        "every object incl. nested ones must be deleted"
    )
    assert OLD in client.manifest.deleted_versions


def test_manifest_row_survives_when_listing_fails(monkeypatch, tmp_path):
    client = _world({f"v{OLD}/pharmaguide_core.db": b"db"})
    client.bucket.list_raises_for.add(f"v{OLD}")

    _run(client, monkeypatch, tmp_path)

    assert f"v{OLD}/pharmaguide_core.db" in client.bucket.objects
    assert OLD not in client.manifest.deleted_versions, (
        "an unlistable directory must keep its manifest row"
    )


def test_manifest_row_survives_partial_deletion_and_next_run_finishes(
    monkeypatch, tmp_path,
):
    client = _world({
        f"v{OLD}/pharmaguide_core.db": b"db",
        f"v{OLD}/detail_index.json": b"idx",
    })
    client.bucket.fail_remove_containing.add("detail_index.json")

    _run(client, monkeypatch, tmp_path)

    assert OLD not in client.manifest.deleted_versions, (
        "a partially-deleted directory must keep its manifest row"
    )
    assert f"v{OLD}/detail_index.json" in client.bucket.objects

    client.bucket.fail_remove_containing.clear()
    _run(client, monkeypatch, tmp_path)

    assert not any(p.startswith(f"v{OLD}/") for p in client.bucket.objects)
    assert OLD in client.manifest.deleted_versions, "resume completes the row"


def test_manifest_row_survives_when_absence_proof_finds_residue(
    monkeypatch, tmp_path,
):
    client = _world({f"v{OLD}/pharmaguide_core.db": b"db"})
    client.bucket.silently_keep_on_remove.add(f"v{OLD}/pharmaguide_core.db")

    _run(client, monkeypatch, tmp_path)

    assert OLD not in client.manifest.deleted_versions, (
        "remove() claiming success is not proof; the listing is"
    )


def test_current_version_is_never_deleted_even_beyond_keep(monkeypatch, tmp_path):
    import cleanup_old_versions as cov

    client = _world({f"v{KEEP1}/pharmaguide_core.db": b"db"})
    # Force the current version beyond the keep window.
    monkeypatch.setattr(cov, "get_supabase_client", lambda: client)
    try:
        cov.main([
            "--execute", "--cleanup-db", "--keep", "0",
            "--lock-path", str(tmp_path / "release.lock"),
        ])
    except SystemExit:
        pass

    assert f"v{KEEP1}/pharmaguide_core.db" in client.bucket.objects
    assert KEEP1 not in client.manifest.deleted_versions


def test_reconciliation_reports_manifest_less_directories(
    monkeypatch, tmp_path, capsys,
):
    """A directory whose row is already gone must be SURFACED, never silently
    invisible — pointing at the gated stale-dir tool, not auto-deleted."""
    stranded = "2026.08.24.165613"
    client = _world({f"v{stranded}/leftover.bin": b"x"})

    _run(client, monkeypatch, tmp_path)

    out = capsys.readouterr().out
    assert stranded in out
    assert f"v{stranded}/leftover.bin" in client.bucket.objects, (
        "reconciliation reports; it never deletes"
    )
