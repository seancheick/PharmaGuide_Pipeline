"""Tests for sync_to_supabase.py."""

import hashlib
import json
import os
import sys
import tempfile
import pytest

_scripts_dir = os.path.join(os.path.dirname(__file__), "..")
if _scripts_dir not in sys.path:
    sys.path.insert(0, os.path.abspath(_scripts_dir))


def _make_manifest(tmp_dir, db_version="2026.03.27.5", product_count=100, checksum="sha256:abc123def456"):
    """Helper: write a fake export_manifest.json and return its path."""
    manifest = {
        "db_version": db_version,
        "pipeline_version": "3.2.0",
        "scoring_version": "3.1.0",
        "generated_at": "2026-03-27T12:00:00Z",
        "product_count": product_count,
        "checksum": checksum,
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
    # Fake SQLite file
    db_path = os.path.join(tmp_dir, "pharmaguide_core.db")
    with open(db_path, "wb") as f:
        f.write(b"FAKE_SQLITE_DATA")

    # Fake detail blobs
    detail_dir = os.path.join(tmp_dir, "detail_blobs")
    os.makedirs(detail_dir, exist_ok=True)
    detail_index = {}
    for i in range(product_count):
        dsld_id = str(1000 + i)
        blob_path = os.path.join(detail_dir, f"{1000 + i}.json")
        blob_payload = {"dsld_id": dsld_id, "blob_version": 1}
        with open(blob_path, "w") as f:
            json.dump(blob_payload, f)
        blob_sha = hashlib.sha256(json.dumps(blob_payload).encode("utf-8")).hexdigest()
        detail_index[dsld_id] = {
            "blob_sha256": blob_sha,
            "storage_path": f"shared/details/sha256/{blob_sha[:2]}/{blob_sha}.json",
            "blob_version": 1,
        }

    detail_index_path = os.path.join(tmp_dir, "detail_index.json")
    with open(detail_index_path, "w") as f:
        json.dump(detail_index, f)

    checksum = "sha256:" + hashlib.sha256(b"FAKE_SQLITE_DATA").hexdigest()
    _make_manifest(tmp_dir, db_version, product_count, checksum=checksum)
    manifest_path = os.path.join(tmp_dir, "export_manifest.json")
    with open(manifest_path) as f:
        manifest = json.load(f)
    manifest["detail_blob_count"] = product_count
    manifest["detail_blob_unique_count"] = product_count
    with open(detail_index_path, "rb") as f:
        manifest["detail_index_checksum"] = "sha256:" + hashlib.sha256(f.read()).hexdigest()
    with open(manifest_path, "w") as f:
        json.dump(manifest, f)

    return tmp_dir


def test_load_local_manifest():
    """load_local_manifest reads and parses export_manifest.json."""
    from sync_to_supabase import load_local_manifest

    with tempfile.TemporaryDirectory() as tmp:
        _make_manifest(tmp, db_version="2026.03.27.5", product_count=500)
        manifest = load_local_manifest(tmp)
        assert manifest["db_version"] == "2026.03.27.5"
        assert manifest["product_count"] == 500


def test_load_local_manifest_missing_file():
    """load_local_manifest raises FileNotFoundError for missing manifest."""
    from sync_to_supabase import load_local_manifest

    with tempfile.TemporaryDirectory() as tmp:
        with pytest.raises(FileNotFoundError, match="export_manifest.json"):
            load_local_manifest(tmp)


def test_needs_update_true_when_versions_differ():
    """needs_update returns True when local version differs from remote."""
    from sync_to_supabase import needs_update

    local = {"db_version": "2026.03.27.5", "checksum": "sha256:new"}
    remote = {"db_version": "2026.03.17.5", "checksum": "sha256:old"}
    assert needs_update(local, remote) is True


def test_needs_update_false_when_same():
    """needs_update returns False when versions match."""
    from sync_to_supabase import needs_update

    local = {"db_version": "2026.03.27.5", "checksum": "sha256:new"}
    remote = {"db_version": "2026.03.27.5", "checksum": "sha256:new"}
    assert needs_update(local, remote) is False


def test_needs_update_true_when_no_remote():
    """needs_update returns True when remote manifest is None (first push)."""
    from sync_to_supabase import needs_update

    local = {"db_version": "2026.03.27.5", "checksum": "sha256:new"}
    assert needs_update(local, None) is True


def test_needs_update_true_when_checksum_differs_same_version():
    """needs_update returns True when checksum differs, even if db_version matches."""
    from sync_to_supabase import needs_update

    local = {"db_version": "2026.03.27.5", "checksum": "sha256:new"}
    remote = {"db_version": "2026.03.27.5", "checksum": "sha256:old"}
    assert needs_update(local, remote) is True


def test_needs_update_true_when_forced():
    """needs_update returns True when force is enabled."""
    from sync_to_supabase import needs_update

    local = {"db_version": "2026.03.27.5", "checksum": "sha256:new"}
    remote = {"db_version": "2026.03.27.5", "checksum": "sha256:new"}
    assert needs_update(local, remote, force=True) is True


def test_collect_detail_blobs():
    """collect_detail_blobs returns sorted list of blob file paths."""
    from sync_to_supabase import collect_detail_blobs

    with tempfile.TemporaryDirectory() as tmp:
        _make_build_output(tmp, product_count=3)
        blobs = collect_detail_blobs(tmp)
        assert len(blobs) == 3
        assert all(b.endswith(".json") for b in blobs)
        # Sorted by filename
        names = [os.path.basename(b) for b in blobs]
        assert names == sorted(names)


def test_validate_build_output_accepts_matching_manifest():
    """validate_build_output accepts a checksum/product_count match."""
    from sync_to_supabase import load_local_manifest, validate_build_output

    with tempfile.TemporaryDirectory() as tmp:
        _make_build_output(tmp, product_count=3)
        manifest = load_local_manifest(tmp)
        stats = validate_build_output(tmp, manifest)
        assert stats["blob_count"] == 3
        assert os.path.basename(stats["db_path"]) == "pharmaguide_core.db"


def test_validate_build_output_rejects_checksum_mismatch():
    """validate_build_output rejects a manifest checksum that does not match the DB."""
    from sync_to_supabase import load_local_manifest, validate_build_output

    with tempfile.TemporaryDirectory() as tmp:
        _make_build_output(tmp, product_count=3)
        manifest_path = os.path.join(tmp, "export_manifest.json")
        manifest = load_local_manifest(tmp)
        manifest["checksum"] = "sha256:not-the-real-hash"
        with open(manifest_path, "w") as f:
            json.dump(manifest, f)
        with pytest.raises(ValueError, match="checksum mismatch"):
            validate_build_output(tmp, manifest)


def test_validate_build_output_rejects_blob_count_mismatch():
    """validate_build_output rejects missing detail blobs."""
    from sync_to_supabase import load_local_manifest, validate_build_output

    with tempfile.TemporaryDirectory() as tmp:
        _make_build_output(tmp, product_count=3)
        os.remove(os.path.join(tmp, "detail_blobs", "1002.json"))
        manifest = load_local_manifest(tmp)
        with pytest.raises(ValueError, match="blob mismatch"):
            validate_build_output(tmp, manifest)


def test_validate_build_output_rejects_missing_detail_index():
    """validate_build_output rejects a build missing detail_index.json."""
    from sync_to_supabase import load_local_manifest, validate_build_output

    with tempfile.TemporaryDirectory() as tmp:
        _make_build_output(tmp, product_count=3)
        os.remove(os.path.join(tmp, "detail_index.json"))
        manifest = load_local_manifest(tmp)
        with pytest.raises(FileNotFoundError, match="detail_index.json"):
            validate_build_output(tmp, manifest)


def test_validate_build_output_rejects_partial_build_manifest():
    """validate_build_output rejects build outputs that already recorded export errors."""
    from sync_to_supabase import load_local_manifest, validate_build_output

    with tempfile.TemporaryDirectory() as tmp:
        _make_build_output(tmp, product_count=3)
        manifest_path = os.path.join(tmp, "export_manifest.json")
        manifest = load_local_manifest(tmp)
        manifest["errors"] = [{"dsld_id": "1001", "error": "blob write failed"}]
        with open(manifest_path, "w") as f:
            json.dump(manifest, f)

        with pytest.raises(ValueError, match="partial artifact"):
            validate_build_output(tmp, manifest)


def test_upload_with_retries_retries_then_succeeds():
    """upload_with_retries retries transient failures and then returns."""
    from sync_to_supabase import upload_with_retries

    attempts = {"count": 0}
    sleeps = []

    def flaky_upload():
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise RuntimeError("temporary failure")
        return "ok"

    result = upload_with_retries(
        flaky_upload,
        retries=3,
        base_delay=0.5,
        sleep_fn=sleeps.append,
    )

    assert result == "ok"
    assert attempts["count"] == 3
    assert sleeps == [0.5, 1.0]


def test_upload_with_retries_raises_after_exhausting_retries():
    """upload_with_retries re-raises once retries are exhausted."""
    from sync_to_supabase import upload_with_retries

    attempts = {"count": 0}

    def always_fail():
        attempts["count"] += 1
        raise RuntimeError("still broken")

    with pytest.raises(RuntimeError, match="still broken"):
        upload_with_retries(
            always_fail,
            retries=2,
            base_delay=0.1,
            sleep_fn=lambda _: None,
        )

    assert attempts["count"] == 3


def test_write_failure_report_persists_errors():
    """write_failure_report writes a JSON artifact for resume/debugging."""
    from sync_to_supabase import write_failure_report

    with tempfile.TemporaryDirectory() as tmp:
        errors = [{"dsld_id": "123", "error": "network timeout"}]
        path = write_failure_report(tmp, "2026.03.29.120000", errors)

        assert os.path.exists(path)
        with open(path) as f:
            data = json.load(f)

        assert data["version"] == "2026.03.29.120000"
        assert data["error_count"] == 1
        assert data["errors"] == errors


def test_parse_args_supports_scaling_flags():
    """parse_args parses the supported sync scaling flags."""
    from sync_to_supabase import parse_args

    args = parse_args([
        "/tmp/build",
        "--dry-run",
        "--max-workers",
        "12",
        "--retry-count",
        "5",
        "--retry-base-delay",
        "0.25",
    ])

    assert args.build_dir == "/tmp/build"
    assert args.dry_run is True
    assert args.max_workers == 12
    assert args.retry_count == 5
    assert args.retry_base_delay == 0.25


def test_collect_unique_blob_uploads_deduplicates_by_hash():
    """collect_unique_blob_uploads collapses repeated blob hashes to one remote upload."""
    from sync_to_supabase import collect_unique_blob_uploads, remote_blob_directory_for_path

    with tempfile.TemporaryDirectory() as tmp:
        detail_dir = os.path.join(tmp, "detail_blobs")
        os.makedirs(detail_dir, exist_ok=True)

        shared_payload = {"hello": "world"}
        shared_bytes = json.dumps(shared_payload).encode("utf-8")
        shared_sha = hashlib.sha256(shared_bytes).hexdigest()

        for dsld_id in ("1001", "1002"):
            with open(os.path.join(detail_dir, f"{dsld_id}.json"), "w") as f:
                json.dump(shared_payload, f)

        detail_index = {
            "1001": {"blob_sha256": shared_sha, "storage_path": f"shared/details/sha256/{shared_sha[:2]}/{shared_sha}.json"},
            "1002": {"blob_sha256": shared_sha, "storage_path": f"shared/details/sha256/{shared_sha[:2]}/{shared_sha}.json"},
        }

        uploads = collect_unique_blob_uploads(tmp, detail_index)

        assert len(uploads) == 1
        assert uploads[0]["blob_sha256"] == shared_sha
        assert uploads[0]["remote_path"] == f"shared/details/sha256/{shared_sha[:2]}/{shared_sha}.json"
        assert remote_blob_directory_for_path(uploads[0]["remote_path"]) == f"shared/details/sha256/{shared_sha[:2]}"


def test_partition_remote_paths_by_directory_groups_uploads():
    """partition_remote_paths_by_directory groups remote paths for batched listing."""
    from sync_to_supabase import partition_remote_paths_by_directory

    uploads = [
        {"remote_path": "shared/details/sha256/aa/aa123.json"},
        {"remote_path": "shared/details/sha256/aa/aa999.json"},
        {"remote_path": "shared/details/sha256/bb/bb123.json"},
    ]

    grouped = partition_remote_paths_by_directory(uploads)

    assert grouped == {
        "shared/details/sha256/aa": {
            "shared/details/sha256/aa/aa123.json",
            "shared/details/sha256/aa/aa999.json",
        },
        "shared/details/sha256/bb": {
            "shared/details/sha256/bb/bb123.json",
        },
    }


def test_filter_pending_blob_uploads_skips_existing_remote_paths():
    """filter_pending_blob_uploads keeps only uploads that are not already remote."""
    from sync_to_supabase import filter_pending_blob_uploads

    uploads = [
        {"blob_sha256": "a" * 64, "remote_path": "shared/details/sha256/aa/" + ("a" * 64) + ".json"},
        {"blob_sha256": "b" * 64, "remote_path": "shared/details/sha256/bb/" + ("b" * 64) + ".json"},
    ]

    pending, skipped = filter_pending_blob_uploads(
        uploads,
        {"shared/details/sha256/aa/" + ("a" * 64) + ".json"},
    )

    assert [item["blob_sha256"] for item in pending] == ["b" * 64]
    assert skipped == 1


def test_discover_existing_remote_blob_paths_lists_by_directory():
    """discover_existing_remote_blob_paths batches remote discovery by shard directory."""
    from sync_to_supabase import discover_existing_remote_blob_paths

    uploads = [
        {"remote_path": "shared/details/sha256/aa/" + ("a" * 64) + ".json"},
        {"remote_path": "shared/details/sha256/bb/" + ("b" * 64) + ".json"},
    ]
    calls = []

    def fake_list(_client, _bucket, prefix, limit=1000, offset=0):
        calls.append((prefix, limit, offset))
        if prefix.endswith("/aa"):
            return [{"name": ("a" * 64) + ".json"}]
        if prefix.endswith("/bb"):
            return []
        return []

    existing = discover_existing_remote_blob_paths(
        client=object(),
        bucket="pharmaguide",
        uploads=uploads,
        list_fn=fake_list,
        page_size=1000,
    )

    assert existing == {"shared/details/sha256/aa/" + ("a" * 64) + ".json"}
    assert ("shared/details/sha256/aa", 1000, 0) in calls
    assert ("shared/details/sha256/bb", 1000, 0) in calls
