"""Tests for sync_to_supabase.py."""

import json
import os
import tempfile
import pytest


def _make_manifest(tmp_dir, db_version="2026.03.27.5", product_count=100):
    """Helper: write a fake export_manifest.json and return its path."""
    manifest = {
        "db_version": db_version,
        "pipeline_version": "3.2.0",
        "scoring_version": "3.1.0",
        "generated_at": "2026-03-27T12:00:00Z",
        "product_count": str(product_count),
        "checksum": "sha256:abc123def456",
        "min_app_version": "1.0.0",
        "schema_version": 5,
        "errors": [],
    }
    path = os.path.join(tmp_dir, "export_manifest.json")
    with open(path, "w") as f:
        json.dump(manifest, f)
    return path


def _make_build_output(tmp_dir, db_version="2026.03.27.5", product_count=3):
    """Helper: create a fake build output directory with manifest, db, and blobs."""
    _make_manifest(tmp_dir, db_version, product_count)

    # Fake SQLite file
    db_path = os.path.join(tmp_dir, "pharmaguide_core.db")
    with open(db_path, "wb") as f:
        f.write(b"FAKE_SQLITE_DATA")

    # Fake detail blobs
    detail_dir = os.path.join(tmp_dir, "detail_blobs")
    os.makedirs(detail_dir, exist_ok=True)
    for i in range(product_count):
        blob_path = os.path.join(detail_dir, f"{1000 + i}.json")
        with open(blob_path, "w") as f:
            json.dump({"dsld_id": str(1000 + i), "blob_version": 1}, f)

    return tmp_dir


def test_load_local_manifest():
    """load_local_manifest reads and parses export_manifest.json."""
    from scripts.sync_to_supabase import load_local_manifest

    with tempfile.TemporaryDirectory() as tmp:
        _make_manifest(tmp, db_version="2026.03.27.5", product_count=500)
        manifest = load_local_manifest(tmp)
        assert manifest["db_version"] == "2026.03.27.5"
        assert manifest["product_count"] == "500"


def test_load_local_manifest_missing_file():
    """load_local_manifest raises FileNotFoundError for missing manifest."""
    from scripts.sync_to_supabase import load_local_manifest

    with tempfile.TemporaryDirectory() as tmp:
        with pytest.raises(FileNotFoundError, match="export_manifest.json"):
            load_local_manifest(tmp)


def test_needs_update_true_when_versions_differ():
    """needs_update returns True when local version differs from remote."""
    from scripts.sync_to_supabase import needs_update

    local = {"db_version": "2026.03.27.5", "checksum": "sha256:new"}
    remote = {"db_version": "2026.03.17.5", "checksum": "sha256:old"}
    assert needs_update(local, remote) is True


def test_needs_update_false_when_same():
    """needs_update returns False when versions and checksums match."""
    from scripts.sync_to_supabase import needs_update

    local = {"db_version": "2026.03.27.5", "checksum": "sha256:same"}
    remote = {"db_version": "2026.03.27.5", "checksum": "sha256:same"}
    assert needs_update(local, remote) is False


def test_needs_update_true_when_no_remote():
    """needs_update returns True when remote manifest is None (first push)."""
    from scripts.sync_to_supabase import needs_update

    local = {"db_version": "2026.03.27.5", "checksum": "sha256:new"}
    assert needs_update(local, None) is True


def test_collect_detail_blobs():
    """collect_detail_blobs returns sorted list of blob file paths."""
    from scripts.sync_to_supabase import collect_detail_blobs

    with tempfile.TemporaryDirectory() as tmp:
        _make_build_output(tmp, product_count=3)
        blobs = collect_detail_blobs(tmp)
        assert len(blobs) == 3
        assert all(b.endswith(".json") for b in blobs)
        # Sorted by filename
        names = [os.path.basename(b) for b in blobs]
        assert names == sorted(names)
