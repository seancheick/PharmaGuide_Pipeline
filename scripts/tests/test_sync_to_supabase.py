"""Tests for sync_to_supabase.py."""

import hashlib
import json
import os
import sqlite3
import sys
import tempfile
import pytest

_scripts_dir = os.path.join(os.path.dirname(__file__), "..")
if _scripts_dir not in sys.path:
    sys.path.insert(0, os.path.abspath(_scripts_dir))


@pytest.fixture(autouse=True)
def simulated_historical_manifest(monkeypatch):
    # Individual sync tests opt into explicit historical rows as needed.
    import supabase_client
    monkeypatch.setattr(supabase_client, "fetch_manifest_version", lambda *a: None)
    monkeypatch.setattr(supabase_client, "list_storage_paths", lambda *a, **k: [])


def test_remote_preflight_checks_access_without_catalog_or_mutations(monkeypatch):
    import sync_to_supabase as syncer
    import supabase_client
    calls = []
    class Storage:
        def get_bucket(self, bucket):
            calls.append(('bucket', bucket))
            return {'id': bucket}
    class Client:
        storage = Storage()
    monkeypatch.setattr(supabase_client, 'get_supabase_client', lambda: Client())
    monkeypatch.setattr(supabase_client, 'fetch_current_manifest', lambda client: calls.append(('manifest', None)))
    assert syncer.main(['--preflight-only']) == 0
    assert calls == [('manifest', None), ('bucket', supabase_client.STORAGE_BUCKET)]


def test_remote_preflight_failure_is_not_success(monkeypatch):
    import sync_to_supabase as syncer
    import supabase_client
    calls = []
    def fail():
        calls.append('client')
        raise ValueError('missing credential')
    monkeypatch.setattr(supabase_client, 'get_supabase_client', fail)
    with pytest.raises(SystemExit) as error:
        syncer.main(['--preflight-only'])
    assert error.value.code != 0
    assert calls == ['client']


def test_sync_still_requires_build_dir_outside_read_only_preflight():
    from sync_to_supabase import parse_args
    with pytest.raises(SystemExit):
        parse_args([])


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


def _write_minimal_catalog_db(db_path, product_count=1):
    """Write a tiny valid, clean products_core honoring the V4 pillar contract,
    so validate_build_output's pillar preflight passes on a realistic catalog."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "CREATE TABLE products_core ("
            "dsld_id TEXT, product_name TEXT, brand_name TEXT, "
            "product_safety_status TEXT, quality_assessment_status TEXT, "
            "quality_score_status TEXT, quality_score_v4_100 REAL, quality_tier TEXT, "
            "v4_confidence TEXT, has_third_party_testing INTEGER, "
            "is_trusted_manufacturer INTEGER, is_vegan INTEGER, "
            "is_gluten_free INTEGER, is_dairy_free INTEGER, is_soy_free INTEGER, "
            "is_organic INTEGER, is_non_gmo INTEGER, "
            "pillar_formulation_v4 REAL, pillar_dose_v4 REAL, pillar_evidence_v4 REAL, "
            "pillar_transparency_v4 REAL, pillar_verification_v4 REAL, pillar_safety_hygiene_v4 REAL)"
        )
        # 11.2+20+18.9+15+6+10 = 81.1, exported half-up as 81.
        conn.executemany(
            "INSERT INTO products_core VALUES "
            "(?, ?, 'Example', 'no_known_catalog_concern', 'complete', "
            "'scored', 81, 'Very good', 'high', 1, 1, 0, 1, 0, 0, 0, 0, "
            "11.2, 20.0, 18.9, 15.0, 6.0, 10.0)",
            [
                (str(index), f"Product {index}")
                for index in range(1, product_count + 1)
            ],
        )
        conn.commit()
    finally:
        conn.close()


def _make_build_output(tmp_dir, db_version="2026.03.27.5", product_count=3):
    """Helper: create a fake build output directory with manifest, db, and blobs."""
    db_path = os.path.join(tmp_dir, "pharmaguide_core.db")
    _write_minimal_catalog_db(db_path, product_count=product_count)

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

    with open(db_path, "rb") as f:
        checksum = "sha256:" + hashlib.sha256(f.read()).hexdigest()
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


def test_validate_bucket_upload_capacity_rejects_oversized_catalog():
    """Fail before upload when the core DB exceeds the bucket policy."""
    from sync_to_supabase import validate_bucket_upload_capacity

    class Storage:
        @staticmethod
        def get_bucket(_bucket):
            return type("Bucket", (), {"file_size_limit": 50 * 1024 * 1024})()

    client = type("Client", (), {"storage": Storage()})()

    with pytest.raises(ValueError, match=r"50\.5 MiB.*50\.0 MiB"):
        validate_bucket_upload_capacity(
            client,
            bucket="pharmaguide",
            object_size_bytes=52_920_320,
        )


def test_validate_bucket_upload_capacity_accepts_unlimited_or_larger_bucket():
    """No bucket limit, or a limit above the object size, is upload-safe."""
    from sync_to_supabase import validate_bucket_upload_capacity

    class Storage:
        file_size_limit = None

        def get_bucket(self, _bucket):
            return type(
                "Bucket",
                (),
                {"file_size_limit": self.file_size_limit},
            )()

    storage = Storage()
    client = type("Client", (), {"storage": storage})()

    validate_bucket_upload_capacity(
        client,
        bucket="pharmaguide",
        object_size_bytes=52_920_320,
    )
    storage.file_size_limit = 100 * 1024 * 1024
    validate_bucket_upload_capacity(
        client,
        bucket="pharmaguide",
        object_size_bytes=52_920_320,
    )


def test_sync_skips_bucket_capacity_check_when_catalog_is_already_current(
    tmp_path,
    monkeypatch,
):
    """An up-to-date sync repairs the share index without re-uploading the DB."""
    import supabase_client
    import sync_to_supabase

    _make_build_output(str(tmp_path), product_count=3)
    local = sync_to_supabase.load_local_manifest(str(tmp_path))
    client = object()
    uploaded_paths = []
    uploaded_cache_controls = []

    def capture_upload(_client, _bucket, remote_path, *_args, **_kwargs):
        uploaded_paths.append(remote_path)
        uploaded_cache_controls.append(_kwargs["cache_control"])

    monkeypatch.setattr(supabase_client, "get_supabase_client", lambda: client)
    monkeypatch.setattr(
        supabase_client,
        "fetch_current_manifest",
        lambda _client: {
            "db_version": local["db_version"],
            "checksum": local["checksum"],
        },
    )
    monkeypatch.setattr(
        supabase_client,
        "upload_file",
        capture_upload,
    )
    monkeypatch.setattr(
        sync_to_supabase,
        "validate_bucket_upload_capacity",
        lambda *_args, **_kwargs: pytest.fail(
            "capacity check ran even though no upload was needed"
        ),
    )
    monkeypatch.setattr(
        sync_to_supabase,
        "_ensure_registry_validating",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        sync_to_supabase,
        "_promote_registry_release",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(supabase_client, "list_storage_paths", lambda *a, **kw:
                        [{"name": "pharmaguide_core.db"}] if kw.get("offset", 0) == 0 else [])
    catalog_search_versions = []
    monkeypatch.setattr(
        sync_to_supabase,
        "_publish_catalog_search_step",
        lambda _client, **kwargs: catalog_search_versions.append(kwargs["version"]),
    )

    monkeypatch.setattr(sync_to_supabase, "discover_existing_remote_blob_paths",
                        lambda *a, **kw: set())
    monkeypatch.setattr(sync_to_supabase, "upload_detail_blobs",
                        lambda **kw: (0, [], 0, 3))
    def download(_c, _b, path):
        if path.endswith("/pharmaguide_core.db"):
            return (tmp_path / "pharmaguide_core.db").read_bytes()
        if path.endswith("/detail_index.json"):
            return (tmp_path / "detail_index.json").read_bytes()
        raise FileNotFoundError(path)
    monkeypatch.setattr(supabase_client, "download_file", download)
    result = sync_to_supabase.sync(str(tmp_path))

    assert result == {
        "status": "up_to_date",
        "version": local["db_version"],
    }
    # An already-current release still (re)publishes its idempotent search rows.
    assert catalog_search_versions == [local["db_version"]]
    assert uploaded_paths == [
        f"v{local['db_version']}/share_index/{shard}.json"
        for shard in (f"{value:02x}" for value in range(256))
    ]
    assert all(0 <= int(ttl) <= 60 for ttl in uploaded_cache_controls)


def test_sync_bounds_release_cache_but_keeps_hashed_blobs_immutable(
    tmp_path, monkeypatch,
):
    """A fresh immutable version stages its objects before activation."""
    import supabase_client
    import sync_to_supabase as sync
    import product_submission_import

    _make_build_output(str(tmp_path), product_count=2)
    local = sync.load_local_manifest(str(tmp_path))
    client = object()
    uploads = {}
    manifests = []
    approvals = [{"submission_id": "018f4c79-7c7e-4c70-9d62-7fc3b9ce6a11"}]
    monkeypatch.setattr(supabase_client, "get_supabase_client", lambda: client)
    monkeypatch.setattr(supabase_client, "fetch_current_manifest", lambda _client: None)
    monkeypatch.setattr(supabase_client, "upload_file", lambda _c, _b, path, _file, **kw: uploads.update({path: kw}))
    monkeypatch.setattr(
        supabase_client,
        "insert_manifest",
        lambda _c, manifest, **kw: manifests.append((manifest, kw)),
    )
    monkeypatch.setattr(
        product_submission_import,
        "build_release_activation_approvals",
        lambda **_kw: approvals,
    )
    monkeypatch.setattr(sync, "validate_bucket_upload_capacity", lambda *_a, **_kw: None)
    monkeypatch.setattr(sync, "discover_existing_remote_blob_paths", lambda *_a, **_kw: set())
    monkeypatch.setattr(sync, "_publish_catalog_search_step", lambda *_a, **_kw: None)
    monkeypatch.setattr(sync, "_ensure_registry_validating", lambda *_a, **_kw: None)
    monkeypatch.setattr(sync, "_promote_registry_release", lambda *_a, **_kw: None)

    result = sync.sync(
        str(tmp_path), max_workers=1, submission_output_dir=str(tmp_path)
    )
    assert result["status"] == "synced"
    assert manifests == [(local, {"submission_approvals": approvals})]
    prefix = f"v{local['db_version']}/"
    mutable = {path: opts for path, opts in uploads.items() if path.startswith(prefix)}
    assert set(mutable) == {
        prefix + "pharmaguide_core.db", prefix + "detail_index.json",
        *(prefix + f"share_index/{shard}.json" for shard in sync.SHARE_INDEX_SHARDS),
    }
    assert all(0 <= int(opts["cache_control"]) <= 60 for opts in mutable.values())
    hashed = {path: opts for path, opts in uploads.items() if path.startswith("shared/details/sha256/")}
    assert len(hashed) == 2
    assert all(opts["cache_control"] == supabase_client.CACHE_CONTROL_IMMUTABLE for opts in hashed.values())


def test_sync_refuses_changed_bytes_under_the_active_version(tmp_path, monkeypatch):
    import supabase_client
    import sync_to_supabase as sync

    _make_build_output(str(tmp_path), product_count=1)
    local = sync.load_local_manifest(str(tmp_path))
    monkeypatch.setattr(supabase_client, "get_supabase_client", lambda: object())
    monkeypatch.setattr(supabase_client, "fetch_current_manifest", lambda _client: {
        "db_version": local["db_version"],
        "checksum": "sha256:different",
    })
    with pytest.raises(ValueError, match="fresh db_version"):
        sync.sync(str(tmp_path), max_workers=1)


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


def test_validate_build_output_refuses_a_cap_adjusted_public_total():
    """The upload preflight must validate reviewed score caps through the same
    detail-blob adjustment contract as the release export gate."""
    from sync_to_supabase import load_local_manifest, validate_build_output

    with tempfile.TemporaryDirectory() as tmp:
        _make_build_output(tmp, product_count=3)
        db_path = os.path.join(tmp, "pharmaguide_core.db")
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "UPDATE products_core SET quality_score_v4_100 = 85, "
                "pillar_formulation_v4 = 20, pillar_dose_v4 = 20, "
                "pillar_evidence_v4 = 18.8, pillar_transparency_v4 = 15, "
                "pillar_verification_v4 = 7, pillar_safety_hygiene_v4 = 10 "
                "WHERE dsld_id = '1'"
            )
            conn.execute("UPDATE products_core SET dsld_id = '1000' WHERE dsld_id = '1'")

        cap_detail = {
            "quality_score_cap_v4": {
                "id": "reviewed_cap",
                "cap": 85.0,
                "reason": "Reviewed category ceiling.",
                "applied": True,
                "score_before_cap": 90.8,
                "score_after_cap": 85.0,
                "adjustment": -5.8,
                "presentation": "explicit_adjustment",
            }
        }
        with open(os.path.join(tmp, "detail_blobs", "1000.json"), "w") as f:
            json.dump(cap_detail, f)

        detail_index_path = os.path.join(tmp, "detail_index.json")
        with open(detail_index_path) as f:
            detail_index = json.load(f)
        cap_sha = hashlib.sha256(
            json.dumps(cap_detail).encode("utf-8")
        ).hexdigest()
        detail_index["1000"].update(
            {
                "blob_sha256": cap_sha,
                "storage_path": (
                    f"shared/details/sha256/{cap_sha[:2]}/{cap_sha}.json"
                ),
            }
        )
        with open(detail_index_path, "w") as f:
            json.dump(detail_index, f)

        manifest = load_local_manifest(tmp)
        with open(db_path, "rb") as f:
            manifest["checksum"] = "sha256:" + hashlib.sha256(f.read()).hexdigest()
        with open(detail_index_path, "rb") as f:
            manifest["detail_index_checksum"] = (
                "sha256:" + hashlib.sha256(f.read()).hexdigest()
            )

        # Locked 2026-09-21: a total below the six-pillar sum never syncs, even
        # when a detail blob carries a category-cap record.
        with pytest.raises(ValueError, match="V4 pillar contract"):
            validate_build_output(tmp, manifest)


def test_validate_build_output_rejects_pillar_contract_violation():
    """A DB missing the V4 pillar columns must block the sync (the 2026-06-14
    stale-DB shape), even when the manifest checksum matches the bad DB."""
    from sync_to_supabase import load_local_manifest, validate_build_output

    with tempfile.TemporaryDirectory() as tmp:
        _make_build_output(tmp, product_count=3)
        db_path = os.path.join(tmp, "pharmaguide_core.db")
        # Simulate a stale DB built before the pillar-projection commit.
        conn = sqlite3.connect(db_path)
        try:
            for col in ("pillar_formulation_v4", "pillar_dose_v4", "pillar_evidence_v4",
                        "pillar_transparency_v4", "pillar_verification_v4", "pillar_safety_hygiene_v4"):
                conn.execute(f"ALTER TABLE products_core DROP COLUMN {col}")
            conn.commit()
        finally:
            conn.close()
        # Re-stamp the checksum so the checksum gate passes and the pillar gate fires.
        manifest_path = os.path.join(tmp, "export_manifest.json")
        manifest = load_local_manifest(tmp)
        with open(db_path, "rb") as f:
            manifest["checksum"] = "sha256:" + hashlib.sha256(f.read()).hexdigest()
        with open(manifest_path, "w") as f:
            json.dump(manifest, f)
        with pytest.raises(ValueError, match="pillar"):
            validate_build_output(tmp, manifest)


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


def test_discover_existing_remote_blob_paths_reports_failed_shard():
    """Shard-list failures include the exact remote directory for release debugging."""
    from sync_to_supabase import discover_existing_remote_blob_paths

    uploads = [
        {"remote_path": "shared/details/sha256/aa/" + ("a" * 64) + ".json"},
    ]

    def fake_list(_client, _bucket, _prefix, limit=1000, offset=0):
        raise RuntimeError("storage list failed")

    with pytest.raises(RuntimeError, match=r"shared/details/sha256/aa.*storage list failed"):
        discover_existing_remote_blob_paths(
            client=object(),
            bucket="pharmaguide",
            uploads=uploads,
            list_fn=fake_list,
            page_size=1000,
            max_workers=1,
        )


# ---------------------------------------------------------------------------
# Orphan reconciliation has one explicit, frozen-artifact entry point.
# Post-sync cleanup owns version directories and manifest rows only.
# ---------------------------------------------------------------------------

def test_post_sync_cleanup_is_version_only():
    from sync_to_supabase import _build_cleanup_args

    assert _build_cleanup_args(cleanup_keep=2) == [
        "--keep", "2", "--execute", "--cleanup-db",
    ]


def test_sync_cli_has_no_destructive_orphan_toggle():
    from sync_to_supabase import parse_args

    args = parse_args(["/tmp/build"])
    assert not hasattr(args, "allow_destructive_orphan_cleanup")


def test_sync_cli_rejects_retired_orphan_toggle():
    from sync_to_supabase import parse_args

    with pytest.raises(SystemExit):
        parse_args(["/tmp/build", "--allow-destructive-orphan-cleanup"])


# ---------------------------------------------------------------------------
# Discovery retry on transient API failures (regression: 2026-05-15)
#
# Supabase Storage occasionally returns a non-JSON body (empty response,
# HTML 5xx page, rate-limit page) to the list() endpoint. The SDK does
# response.json() internally and raises JSONDecodeError. Before this
# fix, a single such response from any of the parallelized list() calls
# killed the entire sync and surfaced as a misleading "Configuration
# error". Discovery now retries transient failures with exponential
# backoff, exactly like upload_with_retries already does for uploads.
# ---------------------------------------------------------------------------


def test_list_with_retries_recovers_after_transient_jsondecodeerror():
    """A single JSON parse failure must not kill discovery — it must retry."""
    from sync_to_supabase import _list_with_retries

    attempts = {"count": 0}

    def list_fn(_client, _bucket, _directory, limit, offset):
        attempts["count"] += 1
        if attempts["count"] == 1:
            # First call simulates Supabase returning an empty body that
            # the SDK tries to json.loads() and fails on.
            raise json.JSONDecodeError("Expecting value", doc="", pos=0)
        return [{"name": "blob1.json"}]

    sleeps: list = []
    page = _list_with_retries(
        list_fn,
        client=None,
        bucket="b",
        directory="shared/details/sha256/ab",
        limit=1000,
        offset=0,
        retries=3,
        base_delay=0.5,
        sleep_fn=sleeps.append,
    )
    assert page == [{"name": "blob1.json"}]
    assert attempts["count"] == 2
    assert sleeps == [0.5]  # one backoff between attempt 1 and 2


def test_list_with_retries_recovers_after_transient_oserror():
    """OSError (parent of ConnectionError/TimeoutError) is also transient."""
    from sync_to_supabase import _list_with_retries

    attempts = {"count": 0}

    def list_fn(_client, _bucket, _directory, limit, offset):
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise ConnectionError("dropped")
        return []

    page = _list_with_retries(
        list_fn,
        client=None,
        bucket="b",
        directory="d",
        limit=1000,
        offset=0,
        retries=3,
        base_delay=0.1,
        sleep_fn=lambda _: None,
    )
    assert page == []
    assert attempts["count"] == 3


def test_list_with_retries_raises_after_exhausting_retries():
    """Persistent transient errors must surface as the real exception, not
    a misleading 'Configuration error' or silent empty result."""
    from sync_to_supabase import _list_with_retries

    attempts = {"count": 0}

    def always_jsondecodeerror(_client, _bucket, _directory, limit, offset):
        attempts["count"] += 1
        raise json.JSONDecodeError("still broken", doc="", pos=0)

    with pytest.raises(json.JSONDecodeError, match="still broken"):
        _list_with_retries(
            always_jsondecodeerror,
            client=None,
            bucket="b",
            directory="d",
            limit=1000,
            offset=0,
            retries=2,
            base_delay=0.1,
            sleep_fn=lambda _: None,
        )
    # Initial attempt + 2 retries == 3 calls
    assert attempts["count"] == 3


def test_list_with_retries_does_not_retry_non_transient_errors():
    """Real bugs (KeyError, TypeError, AttributeError) must crash loudly
    on first occurrence — retrying would hide them from the developer."""
    from sync_to_supabase import _list_with_retries

    attempts = {"count": 0}

    def list_fn(_client, _bucket, _directory, limit, offset):
        attempts["count"] += 1
        raise KeyError("missing-field")

    with pytest.raises(KeyError, match="missing-field"):
        _list_with_retries(
            list_fn,
            client=None,
            bucket="b",
            directory="d",
            limit=1000,
            offset=0,
            retries=5,
            base_delay=0.1,
            sleep_fn=lambda _: None,
        )
    # No retry on non-transient error — single call only
    assert attempts["count"] == 1


def test_discover_existing_remote_paths_for_directory_recovers_from_transient_jsondecodeerror():
    """Integration test: the discovery loop survives a single Supabase
    list() returning non-JSON. This is the exact scenario that killed
    the 2026-05-15 release before the retry layer was added."""
    from sync_to_supabase import _discover_existing_remote_paths_for_directory

    call_log = []

    def flaky_list_fn(_client, _bucket, directory, limit, offset):
        call_log.append((directory, offset))
        # First call to this directory simulates a Supabase API hiccup
        if len(call_log) == 1:
            raise json.JSONDecodeError("Expecting value", doc="", pos=0)
        # On retry, return the actual page
        if offset == 0:
            return [{"name": "abc.json"}, {"name": "def.json"}]
        return []  # no more pages

    expected = {
        "shared/details/sha256/ab/abc.json",
        "shared/details/sha256/ab/def.json",
    }
    existing = _discover_existing_remote_paths_for_directory(
        client=None,
        bucket="b",
        directory="shared/details/sha256/ab",
        expected_paths=expected,
        list_fn=flaky_list_fn,
        page_size=1000,
        retries=3,
        base_delay=0.01,
    )
    assert existing == expected
    # 1 failed attempt + 1 successful = 2 calls (no extra pages since
    # all requested paths have been found)
    assert len(call_log) == 2


# ---------------------------------------------------------------------------
# Single-owner invariant for dist/ staging (regression: 2026-05-15)
#
# release_catalog_artifact.py is the sole owner of populating
# scripts/dist/ with detail_index.json + detail_blobs/. Earlier,
# rebuild_dashboard_snapshot.sh had a manual `cp` workaround that
# duplicated this responsibility. The workaround was removed; this
# test pins the invariant so it cannot drift back.
# ---------------------------------------------------------------------------


def test_rebuild_dashboard_snapshot_has_no_manual_detail_artifact_copies():
    """rebuild_dashboard_snapshot.sh must NOT manually copy detail_index.json
    or detail_blobs/ — release_catalog_artifact.py owns that.

    If a future commit reintroduces the workaround, this test fails and
    forces the author to acknowledge the duplicate ownership.
    """
    import re
    from pathlib import Path

    script = (Path(__file__).resolve().parent.parent /
              "rebuild_dashboard_snapshot.sh").read_text()

    # Lines we explicitly forbid. Match patterns that copy these specific
    # artifacts from staging/anywhere into scripts/dist/.
    forbidden = [
        r"^\s*cp\s+.*detail_index\.json\s+scripts/dist",
        r"^\s*cp\s+-r?\s+.*detail_blobs.*scripts/dist",
        r"^\s*rm\s+-rf\s+scripts/dist/detail_blobs",
    ]
    for pattern in forbidden:
        match = re.search(pattern, script, flags=re.MULTILINE)
        assert match is None, (
            f"rebuild_dashboard_snapshot.sh contains forbidden manual copy "
            f"of detail artifacts (matched pattern {pattern!r}). "
            f"release_catalog_artifact.py is the single owner — remove the "
            f"workaround."
        )


@pytest.mark.parametrize("existing_count,page_cap", [
    (0, 1500), (1500, 1500), (1501, 1500), (10000, None), (10001, None),
])
def test_product_images_reuse_all_remote_pages_and_upload_changes(tmp_path, existing_count, page_cap):
    from sync_to_supabase import upload_product_images

    image_dir = tmp_path / "product_images"
    image_dir.mkdir()
    index = {}
    remote = []
    for i in range(existing_count):
        name = f"{i:05d}.webp"
        (image_dir / name).write_bytes(b"x" * 2048)
        index[str(i)] = {"filename": name, "size_bytes": 2048}
        remote.append({"name": name, "metadata": {"size": 2048}})
    for name in ("changed.webp", "new.webp"):
        (image_dir / name).write_bytes(b"x" * 4096)
        index[name] = {"filename": name, "size_bytes": 4096}
    remote.append({"name": "changed.webp", "metadata": {"size": 100}})
    (image_dir / "product_image_index.json").write_text(json.dumps(index))
    calls, uploaded = [], []

    def listing(client, bucket, prefix, limit, offset):
        calls.append(offset)
        assert bucket == "product-images"
        assert prefix == ""
        returned_limit = min(limit, page_cap) if page_cap else limit
        return remote[offset:offset + returned_limit]

    def upload(client, bucket, remote_path, local_path, **kwargs):
        uploaded.append(remote_path)

    result = upload_product_images(
        object(), str(tmp_path), upload, listing, max_workers=1, retries=0,
        download_fn=lambda *_args: b"x" * 2048,
    )
    assert sorted(uploaded) == ["changed.webp", "new.webp"]
    assert result == {"uploaded": 2, "skipped": existing_count, "failed": 0}


@pytest.mark.parametrize("blob_failed", [False, True])
def test_sync_elapsed_time_includes_images_and_publication(tmp_path, monkeypatch, capsys, blob_failed):
    import supabase_client
    import sync_to_supabase as syncer

    _make_build_output(str(tmp_path), product_count=1)
    client = object()
    clock = {"now": 100.0}
    monkeypatch.setattr(syncer.time, "monotonic", lambda: clock["now"])
    monkeypatch.setattr(supabase_client, "get_supabase_client", lambda: client)
    monkeypatch.setattr(supabase_client, "fetch_current_manifest", lambda _c: None)
    monkeypatch.setattr(syncer, "validate_bucket_upload_capacity", lambda *_a, **_k: None)
    monkeypatch.setattr(syncer, "discover_existing_remote_blob_paths", lambda *_a, **_k: set())

    def advance(*_args, **_kwargs):
        clock["now"] += 10.0

    def upload(_client, _bucket, path, _file, **_kwargs):
        clock["now"] += 1.0
        if blob_failed and path.startswith("shared/details/"):
            raise RuntimeError("simulated detail upload failure")

    def images(**_kwargs):
        assert _kwargs["catalog_version"] == syncer.load_local_manifest(str(tmp_path))["db_version"]
        clock["now"] += 60.0
        return {"uploaded": 1, "skipped": 0, "failed": 0}

    monkeypatch.setattr(supabase_client, "upload_file", upload)
    monkeypatch.setattr(syncer, "upload_product_images", images)
    monkeypatch.setattr(syncer, "_publish_catalog_search_step", advance)
    monkeypatch.setattr(syncer, "_ensure_registry_validating", advance)
    monkeypatch.setattr(syncer, "_promote_registry_release", advance)
    monkeypatch.setattr(supabase_client, "insert_manifest", advance)
    result = syncer.sync(str(tmp_path), max_workers=1, retry_count=0)
    assert result["status"] == ("partial_failure" if blob_failed else "synced")
    assert result["time_seconds"] == clock["now"] - 100.0
    if not blob_failed:
        assert f"Total time:  {result['time_seconds']:.1f}s" in capsys.readouterr().out


def test_images_do_not_confuse_equal_sizes_with_equal_bytes(tmp_path):
    from sync_to_supabase import upload_product_images
    (tmp_path / 'image.webp').write_bytes(b'new')
    (tmp_path / 'product_image_index.json').write_text(json.dumps({
        '1': {'filename': 'image.webp', 'size_bytes': 3}}))
    uploaded = []
    result = upload_product_images(
        object(), str(tmp_path), lambda *a, **kw: uploaded.append(a[2]),
        lambda *a, **kw: [{'name': 'image.webp', 'metadata': {'size': 3}}]
        if kw['offset'] == 0 else [], max_workers=1, retries=0)
    assert uploaded == ['image.webp']
    assert result['uploaded'] == 1


def test_images_missing_local_file_is_failure(tmp_path):
    from sync_to_supabase import upload_product_images
    (tmp_path / 'product_image_index.json').write_text(json.dumps({
        '1': {'filename': 'missing.webp', 'size_bytes': 3}}))
    result = upload_product_images(object(), str(tmp_path), lambda *a, **kw: None,
                                   lambda *a, **kw: [], max_workers=1, retries=0)
    assert result['failed'] == 1


def test_release_images_are_staged_under_the_immutable_catalog_version(tmp_path):
    from sync_to_supabase import upload_product_images
    (tmp_path / 'image.webp').write_bytes(b'new')
    (tmp_path / 'product_image_index.json').write_text(json.dumps({
        '1': {
            'filename': 'image.webp',
            'remote_path': 'vrelease-2/image.webp',
            'size_bytes': 3,
        },
    }))
    uploaded = []
    result = upload_product_images(
        object(), str(tmp_path), lambda *a, **kw: uploaded.append(a[2]),
        lambda *a, **kw: [], max_workers=1, retries=0,
        catalog_version='release-2',
    )
    assert result['failed'] == 0
    assert uploaded == ['vrelease-2/image.webp']


def test_release_images_refuse_different_bytes_at_an_existing_versioned_path(tmp_path):
    from sync_to_supabase import upload_product_images
    (tmp_path / 'image.webp').write_bytes(b'new')
    (tmp_path / 'product_image_index.json').write_text(json.dumps({
        '1': {
            'filename': 'image.webp',
            'remote_path': 'vrelease-2/image.webp',
            'size_bytes': 3,
        },
    }))
    uploaded = []
    result = upload_product_images(
        object(), str(tmp_path), lambda *a, **kw: uploaded.append(a[2]),
        lambda *a, **kw: [{'name': 'image.webp', 'metadata': {'size': 3}}]
        if kw['offset'] == 0 else [], max_workers=1, retries=0,
        download_fn=lambda *_a: b'old', catalog_version='release-2',
    )
    assert uploaded == []
    assert result == {'uploaded': 0, 'skipped': 0, 'failed': 1}


@pytest.mark.parametrize('same_catalog,image_failed,core_missing', [
    (False, True, False), (True, True, False), (True, False, False), (True, False, True)])
def test_sync_repairs_independent_phases_before_activation(tmp_path, monkeypatch, same_catalog, image_failed, core_missing):
    import supabase_client
    import sync_to_supabase as syncer
    _make_build_output(str(tmp_path), product_count=2)
    local = syncer.load_local_manifest(str(tmp_path))
    detail_index = syncer.load_detail_index(str(tmp_path))
    blob_paths = [entry['storage_path'] for entry in detail_index.values()]
    writes, events = [], []
    monkeypatch.setattr(supabase_client, 'list_storage_paths', lambda *a, **kw:
                        [] if core_missing or kw.get('offset', 0) or a[2].endswith('/share_index') else [{'name': 'pharmaguide_core.db'}])
    monkeypatch.setattr(supabase_client, 'get_supabase_client', lambda: object())
    remote = dict(local) if same_catalog else {**local, 'db_version': 'older'}
    monkeypatch.setattr(supabase_client, 'fetch_current_manifest', lambda _c: remote)
    monkeypatch.setattr(supabase_client, 'download_file', lambda _c, _b, path:
                        (tmp_path / path.split('/', 1)[1]).read_bytes())
    monkeypatch.setattr(supabase_client, 'upload_file', lambda _c, _b, path, *_a, **_k: writes.append(path))
    monkeypatch.setattr(supabase_client, 'insert_manifest', lambda *_a: events.append('manifest'))
    monkeypatch.setattr(syncer, 'validate_bucket_upload_capacity', lambda *_a, **_k: None)
    def discover(*_a, **_kw):
        events.append('discover')
        return {blob_paths[0]}  # One existing retry blob, one missing object.
    monkeypatch.setattr(syncer, 'discover_existing_remote_blob_paths', discover)
    def images(**_kw):
        events.append('images')
        return {'uploaded': 0, 'skipped': 0, 'failed': int(image_failed)}
    monkeypatch.setattr(syncer, 'upload_product_images', images)
    monkeypatch.setattr(syncer, '_publish_catalog_search_step', lambda *_a, **_k: events.append('search'))
    monkeypatch.setattr(syncer, '_ensure_registry_validating', lambda *_a, **_k: events.append('validating'))
    monkeypatch.setattr(syncer, '_promote_registry_release', lambda *_a, **_k: events.append('active'))
    result = syncer.sync(str(tmp_path), max_workers=1, retry_count=0)
    assert blob_paths[0] not in writes
    assert blob_paths[1] in writes
    assert not any('/share_index/' in path or path.endswith('/detail_index.json') for path in writes)
    assert events[:2] == ['discover', 'images']
    if image_failed:
        assert result['status'] == 'partial_failure'
        assert not any(step in events for step in ['search', 'validating', 'manifest', 'active'])
    else:
        assert result['status'] == 'up_to_date'
        assert events == ['discover', 'images', 'search', 'validating', 'active']
        assert any(path.endswith('.db') for path in writes) == core_missing


def test_detail_upload_queue_is_bounded(monkeypatch):
    import sync_to_supabase as syncer
    from concurrent.futures import Future
    state = {'submitted': 0, 'consumed': 0}
    class Result(Future):
        def result(self, *args, **kwargs):
            state['consumed'] += 1
            return super().result(*args, **kwargs)
    class Pool:
        def __init__(self, max_workers): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def submit(self, fn, *args):
            state['submitted'] += 1
            assert state['submitted'] - state['consumed'] <= 8
            future = Result()
            future.set_result(fn(*args))
            return future
    monkeypatch.setattr(syncer, 'ThreadPoolExecutor', Pool)
    uploads = [{'local_path': str(i), 'remote_path': str(i), 'blob_sha256': str(i)} for i in range(100)]
    _, errors, uploaded, skipped = syncer.upload_detail_blobs(
        None, 'bucket', uploads, lambda *a, **kw: None, 4, 0, 0)
    assert (errors, uploaded, skipped) == ([], 100, 0)


def test_complete_sync_uses_real_discovery_and_create_only_versioned_paths(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import sync_to_supabase as syncer
    import supabase_client
    _make_build_output(str(tmp_path), product_count=1)
    objects = {}
    calls = []
    class Storage:
        def list(self, path, options):
            prefix = path.rstrip('/') + '/'
            return [{'name': key[len(prefix):]} for key in objects
                    if key.startswith(prefix) and '/' not in key[len(prefix):]]
        def download(self, path):
            if path not in objects:
                raise FileNotFoundError(path)
            return objects[path]
        def upload(self, path, file, file_options):
            calls.append((path, file_options['upsert']))
            if path in objects:
                raise RuntimeError('already exists')
            objects[path] = file.read()
    client = SimpleNamespace(storage=SimpleNamespace(from_=lambda bucket: Storage()))
    monkeypatch.setattr(supabase_client, 'list_storage_paths',
                        lambda client, bucket, prefix, limit=1000, offset=0:
                        Storage().list(prefix, {'limit': limit, 'offset': offset}))
    monkeypatch.setattr(supabase_client, 'get_supabase_client', lambda: client)
    monkeypatch.setattr(supabase_client, 'fetch_current_manifest', lambda client: None)
    monkeypatch.setattr(syncer, 'validate_bucket_upload_capacity', lambda *a, **k: None)
    monkeypatch.setattr(syncer, '_publish_catalog_search_step', lambda *a, **k: None)
    monkeypatch.setattr(syncer, '_ensure_registry_validating', lambda *a, **k: None)
    monkeypatch.setattr(syncer, '_promote_registry_release', lambda *a, **k: None)
    activated = []
    monkeypatch.setattr(supabase_client, 'insert_manifest', lambda *a, **k: activated.append(True))
    result = syncer.sync(str(tmp_path), max_workers=1, retry_count=0)
    assert result['status'] == 'synced'
    assert activated == [True]
    assert all(upsert == 'false' for path, upsert in calls if path.startswith('v'))

@pytest.mark.parametrize('collision', ['manifest', 'database', 'detail_index', 'share_index'])
def test_historical_version_collision_refused_before_any_storage_write(tmp_path, monkeypatch, collision):
    import supabase_client
    import sync_to_supabase as syncer
    _make_build_output(str(tmp_path), product_count=1)
    local = syncer.load_local_manifest(str(tmp_path))
    monkeypatch.setattr(supabase_client, 'get_supabase_client', lambda: object())
    monkeypatch.setattr(supabase_client, 'fetch_current_manifest', lambda c: {'db_version': 'newer', 'checksum': 'newer'})
    monkeypatch.setattr(supabase_client, 'fetch_manifest_version', lambda c, v:
                        {'checksum': 'old'} if collision == 'manifest' else None)
    suffix = {'database': 'pharmaguide_core.db', 'detail_index': 'detail_index.json',
              'share_index': 'share_index/00.json', 'manifest': 'none'}[collision]
    remote_path = f"v{local['db_version']}/{suffix}"
    def listing(c, b, prefix, limit=1000, offset=0):
        return [{'name': remote_path.rsplit('/', 1)[1]}] if remote_path.rsplit('/', 1)[0] == prefix and offset == 0 else []
    monkeypatch.setattr(supabase_client, 'list_storage_paths', listing)
    monkeypatch.setattr(supabase_client, 'download_file', lambda *a: b'old different bytes')
    writes = []
    monkeypatch.setattr(supabase_client, 'upload_file', lambda *a, **k: writes.append(a))
    with pytest.raises(ValueError, match='mutate'):
        syncer.sync(str(tmp_path), max_workers=1, retry_count=0)
    assert writes == []
