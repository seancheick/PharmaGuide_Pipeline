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


# ---------------------------------------------------------------------------
# ADR-0001 / P1.0 — destructive orphan-cleanup freeze
#
# Regression guards proving that `sync_to_supabase.py` no longer invokes
# `--cleanup-orphan-blobs` against `cleanup_old_versions.py` unless the
# operator explicitly opts in via `--allow-destructive-orphan-cleanup`.
#
# This is the mechanically-enforced version of ADR-0001 HR-8 (operational
# freeze on destructive cleanup until P1+P2 release-safety gates land).
#
# These tests are pure-function tests on `_build_cleanup_args` plus
# `parse_args` defaults — no Supabase client, no network, no mocks needed.
# ---------------------------------------------------------------------------

def test_p1_0_build_cleanup_args_omits_orphan_cleanup_by_default():
    """ADR-0001 P1.0: orphan-blob cleanup is FROZEN by default.

    The argv passed to cleanup_old_versions.main MUST NOT include
    `--cleanup-orphan-blobs` unless the operator passes the explicit
    `--allow-destructive-orphan-cleanup` opt-in flag.

    This is the regression guard for the 2026-05-12 incident: the existing
    cleanup logic deletes blobs still referenced by the bundled Flutter
    catalog whenever bundle-on-main lags dist. Until P1+P2 safety gates
    land, the destructive step stays mechanically suppressed.
    """
    from sync_to_supabase import _build_cleanup_args

    argv = _build_cleanup_args(
        cleanup_keep=2,
        allow_destructive_orphan_cleanup=False,
    )

    # The destructive step is omitted by default.
    assert "--cleanup-orphan-blobs" not in argv, (
        "P1.0 freeze breach: --cleanup-orphan-blobs leaked into cleanup argv "
        "even though allow_destructive_orphan_cleanup=False. This re-opens "
        "the 2026-05-12 failure mode (see ADR-0001)."
    )

    # Non-destructive cleanup steps still run during the freeze.
    assert "--keep" in argv
    assert "2" in argv
    assert "--execute" in argv
    assert "--cleanup-db" in argv


def test_p1_0_build_cleanup_args_includes_orphan_cleanup_when_explicitly_opted_in():
    """The explicit `--allow-destructive-orphan-cleanup` flag re-enables it.

    NOTE: this opt-in path will only be SAFE to use once P1+P2 land and the
    safety gates wrap the destructive step. Until then, operators must
    leave it OFF (the default). This test guards the wiring, not the policy.
    """
    from sync_to_supabase import _build_cleanup_args

    argv = _build_cleanup_args(
        cleanup_keep=3,
        allow_destructive_orphan_cleanup=True,
    )

    assert "--cleanup-orphan-blobs" in argv
    assert "--keep" in argv
    assert "3" in argv
    assert "--execute" in argv
    assert "--cleanup-db" in argv


def test_p1_6_commit_2_parse_args_allow_destructive_orphan_cleanup_defaults_ON():
    """ADR-0001 P1.6 commit 2 (2026-05-13): orphan-blob cleanup is now
    INCLUDED by default.

    The P1+P2+P3 release-safety stack is in place — every destructive
    deletion runs behind the lock + index validation + bundle alignment
    + blast-radius + registry-backed protected set, and "delete" is a
    move-to-quarantine with 30-day recovery. The freeze that protected
    us during the stack's build-out is no longer load-bearing; lifting
    it returns the pipeline to the intended end state.

    This test is the regression guard for any well-meaning future PR
    that re-flips the default to False without an ADR amendment.
    """
    from sync_to_supabase import parse_args

    args = parse_args(["/tmp/build"])

    assert args.allow_destructive_orphan_cleanup is True, (
        "P1.6 commit 2 regression: orphan cleanup default should be ON "
        "now that P1+P2+P3 safety gates wrap the destructive step. "
        "If you intend to re-freeze, amend ADR-0001 first."
    )


def test_p1_6_commit_2_parse_args_explicit_allow_flag_still_works():
    """Backward compat — operators or CI scripts that pass the explicit
    --allow-destructive-orphan-cleanup flag (now redundant with the default)
    must still parse to True. No silent rejection."""
    from sync_to_supabase import parse_args

    args = parse_args(["/tmp/build", "--allow-destructive-orphan-cleanup"])

    assert args.allow_destructive_orphan_cleanup is True


def test_p1_6_commit_2_operator_can_opt_out_via_no_allow_flag():
    """The escape hatch: --no-allow-destructive-orphan-cleanup flips
    the default OFF.

    Provided by argparse.BooleanOptionalAction for free. Operators use
    this during incident response or when explicitly deferring cleanup
    to a later run.
    """
    from sync_to_supabase import parse_args

    args = parse_args(["/tmp/build", "--no-allow-destructive-orphan-cleanup"])

    assert args.allow_destructive_orphan_cleanup is False


def test_p1_6_commit_2_build_cleanup_args_default_now_includes_orphan_cleanup():
    """End-to-end of the freeze flip: parse_args() with default settings
    feeds _build_cleanup_args() which now produces a cleanup argv
    containing --cleanup-orphan-blobs. This is the load-bearing flip
    that re-arms the destructive sweep behind all the safety gates."""
    from sync_to_supabase import _build_cleanup_args, parse_args

    args = parse_args(["/tmp/build"])
    argv = _build_cleanup_args(
        cleanup_keep=args.cleanup_keep,
        allow_destructive_orphan_cleanup=args.allow_destructive_orphan_cleanup,
    )

    assert "--cleanup-orphan-blobs" in argv, (
        "P1.6 commit 2 regression: parse_args defaults no longer produce "
        "an argv that includes --cleanup-orphan-blobs. The freeze flip "
        "may have been silently reverted."
    )
    # Non-destructive cleanup is still present
    assert "--keep" in argv
    assert "--cleanup-db" in argv
    assert "--execute" in argv


def test_p1_6_commit_2_operator_opt_out_suppresses_orphan_cleanup():
    """The full chain: operator passes --no-allow-destructive-orphan-cleanup,
    parse_args → False, _build_cleanup_args → no --cleanup-orphan-blobs flag.
    Other cleanup steps still run."""
    from sync_to_supabase import _build_cleanup_args, parse_args

    args = parse_args([
        "/tmp/build", "--no-allow-destructive-orphan-cleanup",
    ])
    argv = _build_cleanup_args(
        cleanup_keep=args.cleanup_keep,
        allow_destructive_orphan_cleanup=args.allow_destructive_orphan_cleanup,
    )

    assert "--cleanup-orphan-blobs" not in argv
    assert "--keep" in argv          # non-destructive cleanup still happens
    assert "--cleanup-db" in argv
    assert "--execute" in argv


def test_p1_6_commit_2_gates_and_quarantine_still_active_when_opted_in():
    """Confirm the freeze flip does NOT bypass the safety gates. When
    cleanup is included (default), _build_cleanup_args forwards the gate
    inputs (flutter-repo, branch, override knobs) to cleanup_old_versions
    where they drive evaluate_cleanup_gates. The flag itself only controls
    inclusion — not whether the gates run."""
    from sync_to_supabase import _build_cleanup_args

    argv = _build_cleanup_args(
        cleanup_keep=2,
        allow_destructive_orphan_cleanup=True,
        flutter_repo="/path/to/flutter",
        dist_dir="/path/to/build",
        branch="release-2026-05",     # non-default so it's forwarded
        bundle_mismatch_reason="hotfix per incident #42",
        expected_count=12,
    )

    # Gate inputs are forwarded so cleanup_old_versions can evaluate
    # P1.5 gates (lock, index validation, bundle alignment, blast radius)
    # before any quarantine move. (--branch only forwarded when non-default.)
    assert "--flutter-repo" in argv
    assert "/path/to/flutter" in argv
    assert "--dist-dir" in argv
    assert "/path/to/build" in argv
    assert "--branch" in argv
    assert "release-2026-05" in argv
    assert "--override-bundle-mismatch" in argv
    assert "--expected-count" in argv
    assert "12" in argv


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
    # len(page) < page_size triggered the break)
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
