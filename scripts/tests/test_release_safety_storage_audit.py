"""Tests for scripts/release_safety/storage_audit.py — read-only
Supabase storage inventory.

Mock Supabase storage where each object has size metadata. The audit
itself only calls ``list()`` so the mock just supports list with
``{"name": ..., "metadata": {"size": N}}`` for files and
``{"name": ...}`` (no metadata) for subdirectories.

No network. No real Supabase. No deletion or movement of any kind.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Optional, Set
import pytest

_scripts_dir = os.path.join(os.path.dirname(__file__), "..")
if _scripts_dir not in sys.path:
    sys.path.insert(0, os.path.abspath(_scripts_dir))


# ---------------------------------------------------------------------------
# MockSupabaseClient (extended with size metadata)
# ---------------------------------------------------------------------------


class MockBucket:
    def __init__(self):
        # path -> bytes (length acts as size)
        self.objects: dict = {}

    def put(self, path: str, content: bytes) -> None:
        self.objects[path] = content

    def list(self, path: str, options=None):
        opts = options or {}
        limit = opts.get("limit")
        offset = opts.get("offset", 0)

        prefix = path.rstrip("/") + "/" if path else ""
        results = []
        seen_dirs: Set[str] = set()
        for full, data in self.objects.items():
            if not full.startswith(prefix):
                continue
            rest = full[len(prefix):]
            if "/" not in rest:
                # File leaf — include size metadata
                results.append({
                    "name": rest,
                    "metadata": {"size": len(data)},
                })
            else:
                # Subdirectory — name only, no metadata
                first = rest.split("/", 1)[0]
                if first not in seen_dirs:
                    seen_dirs.add(first)
                    results.append({"name": first})

        # Pagination — honor limit + offset so the audit's _list_paginated
        # loop terminates correctly. Without this, a population larger than
        # the production page size deadlocks the test.
        if limit is None:
            return results[offset:]
        return results[offset:offset + limit]


class MockStorageNamespace:
    def __init__(self):
        self.buckets: dict = {}

    def from_(self, bucket: str) -> MockBucket:
        return self.buckets.setdefault(bucket, MockBucket())


class MockSupabaseClient:
    def __init__(self):
        self.storage = MockStorageNamespace()


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _h(idx: int) -> str:
    return f"{idx:064x}"


def _put_active_blob(bucket, blob_hash: str, size: int) -> None:
    bucket.put(
        f"shared/details/sha256/{blob_hash[:2]}/{blob_hash}.json",
        b"x" * size,
    )


def _put_quarantine_blob(bucket, date_str: str, blob_hash: str, size: int) -> None:
    bucket.put(
        f"shared/quarantine/{date_str}/{blob_hash[:2]}/{blob_hash}.json",
        b"q" * size,
    )


def _put_per_version(bucket, db_version: str, leaf: str, size: int) -> None:
    bucket.put(f"v{db_version}/{leaf}", b"v" * size)


def _make_flutter_repo(tmp_path: Path, *, hashes: list, db_version: str) -> Path:
    """Create a fake Flutter repo with assets/db/{export_manifest.json,
    pharmaguide_core.db}. The catalog has the given blob hashes."""
    repo = tmp_path / "flutter"
    assets = repo / "assets" / "db"
    assets.mkdir(parents=True, exist_ok=True)

    catalog = assets / "pharmaguide_core.db"
    if catalog.exists():
        catalog.unlink()
    conn = sqlite3.connect(str(catalog))
    try:
        conn.execute(
            "CREATE TABLE products_core ("
            "  dsld_id TEXT PRIMARY KEY, detail_blob_sha256 TEXT)",
        )
        for i, h in enumerate(hashes):
            conn.execute("INSERT INTO products_core VALUES (?, ?)",
                         (str(1000 + i), h))
        conn.commit()
    finally:
        conn.close()

    sha = hashlib.sha256()
    with open(catalog, "rb") as f:
        sha.update(f.read())

    (assets / "export_manifest.json").write_text(json.dumps({
        "db_version": db_version,
        "checksum_sha256": sha.hexdigest(),
        "product_count": len(hashes),
    }))
    return repo


def _make_dist(tmp_path: Path, *, hashes: list, db_version: str) -> Path:
    dist = tmp_path / "dist"
    dist.mkdir(parents=True, exist_ok=True)
    detail_index = {}
    for i, h in enumerate(hashes):
        detail_index[str(1000 + i)] = {
            "blob_sha256": h,
            "storage_path": f"shared/details/sha256/{h[:2]}/{h}.json",
            "blob_version": 1,
        }
    (dist / "detail_index.json").write_text(json.dumps(detail_index))
    (dist / "export_manifest.json").write_text(json.dumps({
        "db_version": db_version,
        "checksum_sha256": "irrelevant",
    }))
    return dist


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_audit_empty_bucket_reports_zeros(tmp_path):
    """An empty bucket + empty bundled/dist returns a zeroed report."""
    from release_safety.storage_audit import run_storage_audit

    flutter = _make_flutter_repo(tmp_path, hashes=[], db_version="vEMPTY")
    dist = _make_dist(tmp_path, hashes=[], db_version="vEMPTY")
    client = MockSupabaseClient()

    report = run_storage_audit(
        client, flutter_repo_path=flutter, dist_dir=dist,
    )

    assert report.bucket_total_bytes == 0
    assert report.bucket_total_objects == 0
    assert report.details_total_objects == 0
    assert report.bundled_hash_count == 0
    assert report.dist_hash_count == 0
    assert report.union_hash_count == 0
    assert report.orphan_count == 0
    assert report.quarantine_total_objects == 0
    assert report.per_version_total_bytes == 0


def test_audit_aligned_bundled_dist_zero_orphans(tmp_path):
    """When bundled and dist agree and storage matches, orphan count is 0."""
    from release_safety.storage_audit import run_storage_audit

    aligned = [_h(i) for i in range(10)]
    flutter = _make_flutter_repo(tmp_path, hashes=aligned, db_version="vMATCH")
    dist = _make_dist(tmp_path, hashes=aligned, db_version="vMATCH")
    client = MockSupabaseClient()
    bucket = client.storage.from_("pharmaguide")
    for h in aligned:
        _put_active_blob(bucket, h, size=1024)

    report = run_storage_audit(
        client, flutter_repo_path=flutter, dist_dir=dist,
    )

    assert report.bundled_hash_count == 10
    assert report.dist_hash_count == 10
    assert report.union_hash_count == 10
    assert report.bundled_in_storage_count == 10
    assert report.dist_in_storage_count == 10
    assert report.union_in_storage_count == 10
    assert report.orphan_count == 0
    assert report.orphan_total_bytes == 0
    assert report.bundled_missing_from_storage_count == 0
    assert report.dist_missing_from_storage_count == 0


def test_audit_identifies_orphans_in_active_storage(tmp_path):
    """Storage has bundled+dist blobs PLUS extras that aren't in either.
    Audit identifies the extras as orphans."""
    from release_safety.storage_audit import run_storage_audit

    bundled_dist = [_h(i) for i in range(5)]
    extras = [_h(i) for i in range(100, 103)]
    flutter = _make_flutter_repo(tmp_path, hashes=bundled_dist, db_version="v1")
    dist = _make_dist(tmp_path, hashes=bundled_dist, db_version="v1")

    client = MockSupabaseClient()
    bucket = client.storage.from_("pharmaguide")
    for h in bundled_dist:
        _put_active_blob(bucket, h, size=1024)
    for h in extras:
        _put_active_blob(bucket, h, size=2048)

    report = run_storage_audit(
        client, flutter_repo_path=flutter, dist_dir=dist,
    )

    assert report.orphan_count == 3
    assert report.orphan_total_bytes == 3 * 2048
    assert set(report.orphan_sample_hashes) == set(extras)


def test_audit_identifies_quarantined_blobs(tmp_path):
    """Quarantine blobs are categorized separately and counted by date."""
    from release_safety.storage_audit import run_storage_audit

    flutter = _make_flutter_repo(tmp_path, hashes=[_h(0)], db_version="v1")
    dist = _make_dist(tmp_path, hashes=[_h(0)], db_version="v1")

    client = MockSupabaseClient()
    bucket = client.storage.from_("pharmaguide")
    _put_active_blob(bucket, _h(0), 100)
    # 3 quarantined under one date, 2 under another
    for i in range(3):
        _put_quarantine_blob(bucket, "2026-04-01", _h(200 + i), 500)
    for i in range(2):
        _put_quarantine_blob(bucket, "2026-04-15", _h(300 + i), 700)

    report = run_storage_audit(
        client, flutter_repo_path=flutter, dist_dir=dist,
    )

    assert report.quarantine_total_objects == 5
    assert report.quarantine_total_bytes == 3 * 500 + 2 * 700
    assert "2026-04-01" in report.quarantine_dates
    assert "2026-04-15" in report.quarantine_dates
    assert report.quarantine_dates["2026-04-01"].object_count == 3
    assert report.quarantine_dates["2026-04-01"].total_bytes == 3 * 500


def test_audit_categorizes_per_version_legacy_dirs(tmp_path):
    """pharmaguide/v{version}/ directories are surfaced under per_version_dirs."""
    from release_safety.storage_audit import run_storage_audit

    flutter = _make_flutter_repo(tmp_path, hashes=[], db_version="vEMPTY")
    dist = _make_dist(tmp_path, hashes=[], db_version="vEMPTY")

    client = MockSupabaseClient()
    bucket = client.storage.from_("pharmaguide")
    # Two legacy version dirs
    bucket.put("v2026.03.01.5/manifest.json", b"x" * 200)
    bucket.put("v2026.03.01.5/db.sqlite", b"x" * 8000)
    bucket.put("v2026.04.10.42/manifest.json", b"y" * 300)

    report = run_storage_audit(
        client, flutter_repo_path=flutter, dist_dir=dist,
    )

    assert "v2026.03.01.5" in report.per_version_dirs
    assert "v2026.04.10.42" in report.per_version_dirs
    assert report.per_version_dirs["v2026.03.01.5"].object_count == 2
    assert report.per_version_dirs["v2026.03.01.5"].total_bytes == 200 + 8000
    assert report.per_version_total_objects == 3
    assert report.per_version_total_bytes == 200 + 8000 + 300


def test_audit_categorizes_unknown_top_prefixes(tmp_path):
    """Top-level prefixes that aren't shared/, pharmaguide/, etc.
    surface in other_top_prefixes."""
    from release_safety.storage_audit import run_storage_audit

    flutter = _make_flutter_repo(tmp_path, hashes=[], db_version="vEMPTY")
    dist = _make_dist(tmp_path, hashes=[], db_version="vEMPTY")

    client = MockSupabaseClient()
    bucket = client.storage.from_("pharmaguide")
    bucket.put("unexpected_prefix/file.txt", b"hello")

    report = run_storage_audit(
        client, flutter_repo_path=flutter, dist_dir=dist,
    )

    assert "unexpected_prefix" in report.other_top_prefixes


def test_audit_warns_on_lfs_pointer_bundled_catalog(tmp_path):
    """When the bundled catalog file is the Git LFS pointer text (not the
    real SQLite content), the audit returns the report with a clear
    warning instead of crashing."""
    from release_safety.storage_audit import run_storage_audit

    repo = tmp_path / "flutter"
    assets = repo / "assets" / "db"
    assets.mkdir(parents=True)
    (assets / "pharmaguide_core.db").write_bytes(
        b"version https://git-lfs.github.com/spec/v1\n"
        b"oid sha256:deadbeef\nsize 12345\n"
    )
    (assets / "export_manifest.json").write_text(json.dumps({
        "db_version": "vLFS",
        "checksum_sha256": "doesnt_matter",
    }))

    dist = _make_dist(tmp_path, hashes=[_h(0)], db_version="vDIST")

    client = MockSupabaseClient()
    bucket = client.storage.from_("pharmaguide")
    _put_active_blob(bucket, _h(0), 100)

    report = run_storage_audit(
        client, flutter_repo_path=repo, dist_dir=dist,
    )

    assert report.bundled_load_warning is not None
    assert "Git LFS pointer" in report.bundled_load_warning
    assert report.bundled_db_version == "vLFS"  # manifest still readable
    assert report.bundled_hash_count == 0       # but couldn't query catalog


def test_audit_cleanup_projections_math(tmp_path):
    """Projection math is correct:
       full cleanup = current − orphans − per_version − quarantine."""
    from release_safety.storage_audit import run_storage_audit

    bundled_dist = [_h(0), _h(1)]
    flutter = _make_flutter_repo(tmp_path, hashes=bundled_dist, db_version="v1")
    dist = _make_dist(tmp_path, hashes=bundled_dist, db_version="v1")

    client = MockSupabaseClient()
    bucket = client.storage.from_("pharmaguide")
    # Active: 2 blobs * 1000 bytes = 2000 (protected — survive cleanup)
    for h in bundled_dist:
        _put_active_blob(bucket, h, 1000)
    # Active orphans: 2 blobs * 500 bytes = 1000 (orphaned — quarantine then sweep)
    for i in range(2):
        _put_active_blob(bucket, _h(100 + i), 500)
    # Quarantine: 1 blob * 300 bytes = 300 (existing — sweep eligible)
    _put_quarantine_blob(bucket, "2026-04-01", _h(200), 300)
    # Per-version legacy: 800 bytes (delete-eligible)
    bucket.put("v2026.03.01.5/db.sqlite", b"x" * 800)

    report = run_storage_audit(
        client, flutter_repo_path=flutter, dist_dir=dist,
    )

    expected_total = 2000 + 1000 + 300 + 800
    assert report.bucket_total_bytes == expected_total
    assert report.orphan_total_bytes == 1000
    assert report.quarantine_total_bytes == 300
    assert report.per_version_total_bytes == 800

    assert report.projection_quarantine_orphans_then_sweep() == \
           expected_total - 1000
    assert report.projection_delete_per_version_dirs() == \
           expected_total - 800
    assert report.projection_full_cleanup() == 2000  # only protected remain


def test_audit_text_report_contains_headlined_sections(tmp_path):
    """text_report() output contains the operator-facing headlines so a
    human can scan it. Spot-check the expected section anchors."""
    from release_safety.storage_audit import run_storage_audit

    flutter = _make_flutter_repo(tmp_path, hashes=[_h(0)], db_version="v1")
    dist = _make_dist(tmp_path, hashes=[_h(0)], db_version="v1")
    client = MockSupabaseClient()
    bucket = client.storage.from_("pharmaguide")
    _put_active_blob(bucket, _h(0), 100)

    report = run_storage_audit(
        client, flutter_repo_path=flutter, dist_dir=dist,
    )
    text = report.text_report()

    assert "WHAT IS USING THE BYTES" in text
    assert "ACTIVE / PROTECTED" in text
    assert "ORPHANS" in text
    assert "ALREADY QUARANTINED" in text
    assert "LEGACY PER-VERSION" in text
    assert "CLEANUP PROJECTIONS" in text
    assert "v1" in text  # db_version surfaces


def test_audit_to_dict_round_trips_key_metrics(tmp_path):
    """to_dict() exposes the metrics needed by downstream tooling."""
    from release_safety.storage_audit import run_storage_audit

    flutter = _make_flutter_repo(tmp_path, hashes=[_h(0)], db_version="v1")
    dist = _make_dist(tmp_path, hashes=[_h(0), _h(1)], db_version="v2")
    client = MockSupabaseClient()
    bucket = client.storage.from_("pharmaguide")
    _put_active_blob(bucket, _h(0), 100)
    _put_active_blob(bucket, _h(1), 200)
    _put_active_blob(bucket, _h(99), 50)  # orphan

    report = run_storage_audit(
        client, flutter_repo_path=flutter, dist_dir=dist,
    )
    d = report.to_dict()

    assert d["bucket"] == "pharmaguide"
    assert d["totals"]["bytes"] == 350
    assert d["bundled"]["db_version"] == "v1"
    assert d["dist"]["db_version"] == "v2"
    assert d["bundled"]["hash_count"] == 1
    assert d["dist"]["hash_count"] == 2
    assert d["union"]["hash_count"] == 2  # _h(0) is shared
    assert d["orphans"]["count"] == 1
    assert d["orphans"]["total_bytes"] == 50
    assert d["projections"]["after_full_cleanup_bytes"] == 350 - 50


def test_audit_handles_pagination_past_1000_objects(tmp_path):
    """The mock auto-pages because list() returns everything; this test
    confirms the audit's _list_paginated keeps reading until exhausted."""
    from release_safety.storage_audit import run_storage_audit

    flutter = _make_flutter_repo(tmp_path, hashes=[], db_version="vEMPTY")
    dist = _make_dist(tmp_path, hashes=[], db_version="vEMPTY")

    client = MockSupabaseClient()
    bucket = client.storage.from_("pharmaguide")
    # 1500 orphans across one shard — exceeds the 1000-per-page assumption
    for i in range(1500):
        _put_active_blob(bucket, _h(i), 10)

    report = run_storage_audit(
        client, flutter_repo_path=flutter, dist_dir=dist,
    )

    # The mock's list() returns ALL items in one go regardless of options,
    # so this test mainly proves the walker doesn't trip on a larger set.
    # (The real Supabase pagination loop is exercised in production.)
    assert report.orphan_count == 1500
    assert report.orphan_total_bytes == 1500 * 10


def test_audit_orphan_sample_size_caps_returned_hashes(tmp_path):
    """orphan_sample_hashes is capped at the requested sample size."""
    from release_safety.storage_audit import run_storage_audit

    flutter = _make_flutter_repo(tmp_path, hashes=[], db_version="vEMPTY")
    dist = _make_dist(tmp_path, hashes=[], db_version="vEMPTY")

    client = MockSupabaseClient()
    bucket = client.storage.from_("pharmaguide")
    for i in range(50):
        _put_active_blob(bucket, _h(i), 10)

    report = run_storage_audit(
        client, flutter_repo_path=flutter, dist_dir=dist,
        orphan_sample_size=5,
    )

    assert report.orphan_count == 50
    assert len(report.orphan_sample_hashes) == 5
