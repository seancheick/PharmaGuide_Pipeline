#!/usr/bin/env python3
"""Sync pipeline build output to Supabase Storage + PostgreSQL manifest.

Usage:
    python scripts/sync_to_supabase.py <build_output_dir>

The build_output_dir should contain:
    - export_manifest.json
    - detail_index.json
    - pharmaguide_core.db
    - detail_blobs/{dsld_id}.json (local per-product build output)

Environment variables (from .env):
    - SUPABASE_URL
    - SUPABASE_SERVICE_ROLE_KEY
"""

import argparse
import glob
import hashlib
import json
import math
import os
import sqlite3
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed, wait, FIRST_COMPLETED

DEFAULT_MAX_WORKERS = 8
DEFAULT_DISCOVERY_WORKERS = 8
DEFAULT_UPLOAD_RETRIES = 3
DEFAULT_RETRY_BASE_DELAY = 1.0
DEFAULT_PROGRESS_EVERY = 500

# Ensure scripts/ is on the path for sibling imports (supabase_client)
sys.path.insert(0, os.path.dirname(__file__))
import env_loader  # noqa: F401
from supabase_client import CACHE_CONTROL_IMMUTABLE, STORAGE_BUCKET, core_db_remote_path
from audit_source_of_truth_contract import check_v4_pillar_contract

# A catalog version is single-use. Version-stamped objects are immutable once
# present; retries may repair a missing object but never replace different
# bytes beneath an existing URL.
CATALOG_MUTABLE_CACHE_SECONDS = 60
DETAIL_BLOB_STORAGE_PREFIX = "shared/details/sha256"
SHARE_INDEX_DIRNAME = "share_index"
#: v3 adds the "assessment_incomplete" catalogDisposition. A v2 reader that
#: does not know the value must treat it as non-scored, never as scored.
SHARE_INDEX_SCHEMA_VERSION = 3
SHARE_INDEX_SHARD_PREFIX_LENGTH = 2
SHARE_INDEX_SHARDS = tuple(f"{value:02x}" for value in range(256))


def _share_tier_id(name: str) -> str:
    """The stable id a tier travels under in the share index: the configured
    tier name, lower-cased, spaces as underscores ("Very good" -> "very_good")."""
    return "_".join(str(name or "").strip().lower().split())


def _load_share_tier_ids() -> frozenset:
    """Tier ids the share index may carry, read from the scorer's own tier
    table so this exporter never keeps a second list of tier names."""
    config_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "scoring_v4", "config", "quality_score.json"
    )
    with open(config_path, "r", encoding="utf-8") as handle:
        bands = json.load(handle)["tiers"]
    return frozenset(_share_tier_id(band["name"]) for band in bands)


SHARE_TIER_IDS = _load_share_tier_ids()
SHARE_HIGHLIGHT_COLUMNS = (
    ("has_third_party_testing", "Third-Party Tested"),
    ("is_trusted_manufacturer", "Trusted Manufacturer"),
    ("is_vegan", "Vegan"),
    ("is_gluten_free", "Gluten-Free"),
    ("is_dairy_free", "Dairy-Free"),
    ("is_soy_free", "Soy-Free"),
    ("is_organic", "Organic"),
    ("is_non_gmo", "Non-GMO"),
)


def _share_disposition(row):
    """Classify a row for the public share projection.

    Three facts, three questions, and they are NOT the same question:

      product_safety_status      is the product unsafe to use?
      quality_score_status       did the engine produce a usable number?
      quality_assessment_status  did PharmaGuide finish the assessment?

    A product can be honestly ``scored`` and honestly ``partial``: the engine
    computed a total while one required rubric dimension was never reviewed.
    Folding that into "not_scored" told the public two false things at once -
    that we have no analysis (we have five assessed pillars) and that the gap is
    a data problem (it is a review we have not performed). It is its own
    disposition.

    ``assessment_incomplete`` is shareable and discoverable, carries its
    highlights, and - exactly like ``not_scored`` - publishes NO quality score
    and NO tier. An unfinished assessment may not advertise a verdict.
    """
    safety = (row["product_safety_status"] or "").strip().lower()
    if safety in {"blocked", "unsafe"}:
        return "blocked"

    assessment = (row["quality_assessment_status"] or "").strip().lower()
    score_status = (row["quality_score_status"] or "").strip().lower()
    if score_status != "scored" or row["quality_score_v4_100"] is None:
        return "not_scored"
    if assessment != "complete":
        return "assessment_incomplete"
    return "scored"


def write_share_index(*, db_path, output_dir, catalog_version):
    """Write the server-owned public-share projection for one catalog release.

    The checksum-verified SQLite catalog remains the source of truth. The
    website reads this compact catalog projection instead of accepting a
    product name, score, safety disposition, or trust claim from the app.
    """
    columns = [
        "dsld_id",
        "product_name",
        "brand_name",
        "product_safety_status",
        "quality_assessment_status",
        "quality_score_status",
        "quality_score_v4_100",
        "quality_tier",
        "v4_confidence",
        *(column for column, _ in SHARE_HIGHLIGHT_COLUMNS),
    ]
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            f"SELECT {', '.join(columns)} FROM products_core ORDER BY dsld_id"
        ).fetchall()
    finally:
        conn.close()

    products_by_shard = {shard: {} for shard in SHARE_INDEX_SHARDS}
    for row in rows:
        dsld_id = str(row["dsld_id"] or "").strip()
        product_name = str(row["product_name"] or "").strip()
        brand_name = str(row["brand_name"] or "").strip() or None
        if not dsld_id or len(dsld_id) > 64:
            raise ValueError(f"Invalid share dsld_id: {dsld_id!r}")
        if not product_name or len(product_name) > 200:
            raise ValueError(f"Invalid share product_name for {dsld_id!r}")
        if brand_name is not None and len(brand_name) > 200:
            raise ValueError(f"Invalid share brand_name for {dsld_id!r}")

        disposition = _share_disposition(row)
        quality_score = None
        quality_tier = None
        confidence = None
        highlights = []

        if disposition == "scored":
            quality_score = int(round(float(row["quality_score_v4_100"])))
            if quality_score < 0 or quality_score > 100:
                raise ValueError(f"Invalid share score for {dsld_id!r}: {quality_score}")
            quality_tier = _share_tier_id(row["quality_tier"])
            if quality_tier not in SHARE_TIER_IDS:
                raise ValueError(
                    f"Invalid share quality_tier for {dsld_id!r}: {quality_tier!r}"
                )
            raw_confidence = str(row["v4_confidence"] or "").strip().lower()
            if raw_confidence and raw_confidence not in {"high", "moderate", "medium"}:
                confidence = "Limited"

        if disposition != "blocked":
            highlights = [
                label
                for column, label in SHARE_HIGHLIGHT_COLUMNS
                if row[column] == 1
            ][:3]

        shard = hashlib.sha256(dsld_id.encode("utf-8")).hexdigest()[
            :SHARE_INDEX_SHARD_PREFIX_LENGTH
        ]
        products_by_shard[shard][dsld_id] = {
            "productName": product_name,
            "brandName": brand_name,
            "catalogDisposition": disposition,
            "qualityScore": quality_score,
            "qualityTier": quality_tier,
            "confidence": confidence,
            "highlights": highlights,
        }

    os.makedirs(output_dir, exist_ok=True)
    for shard, products in products_by_shard.items():
        payload = {
            "schemaVersion": SHARE_INDEX_SCHEMA_VERSION,
            "shardPrefixLength": SHARE_INDEX_SHARD_PREFIX_LENGTH,
            "catalogVersion": str(catalog_version),
            "products": products,
        }
        output_path = os.path.join(output_dir, f"{shard}.json")
        temp_path = f"{output_path}.tmp"
        with open(temp_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, separators=(",", ":"), sort_keys=True)
        os.replace(temp_path, output_path)
    return sum(len(products) for products in products_by_shard.values())


# ---------------------------------------------------------------------------
# P3.6b — catalog_releases registry activation (auto-create + state walk)
# ---------------------------------------------------------------------------
#
# A successful release walks the registry through:
#     missing -> PENDING -> VALIDATING -> (manifest flip) -> ACTIVE
#
# This module owns two helpers that the sync() function calls at the right
# moments:
#
#   _ensure_registry_validating(client, db_version, detail_index_url)
#       Stage 1. Called AFTER all uploads succeed, BEFORE manifest flip.
#       Brings the registry row to VALIDATING-or-later. The row's blobs
#       are protected by P3.5 once the state is VALIDATING.
#
#   _promote_registry_release(client, db_version)
#       Stage 2. Called AFTER manifest flip, BEFORE reporting sync success.
#       Atomically retires an older active release in the target channel and
#       promotes this VALIDATING row to ACTIVE.
#
# Re-entry behavior (per ADR-0001 P3.6b sign-off):
#
#   row state on entry to Stage 1   -> action
#   -----------------------------------------------------------
#   missing                         -> insert PENDING, advance VALIDATING
#   PENDING                         -> advance VALIDATING
#   VALIDATING                      -> no-op (already there)
#   ACTIVE                          -> no-op (already past)
#   RETIRED                         -> RAISE (never resurrect)
#
#   Stage 2 state handling is owned by public.promote_catalog_release. This
#   avoids client-side sequencing that could violate the one-ACTIVE-row-per-
#   channel invariant or expose a no-ACTIVE gap.
#
# Partial-failure policy:
#   - Stage 1 failure: sync aborts BEFORE manifest flip. Registry may be
#     left in PENDING or VALIDATING; rerun is safe (preflight resumes).
#   - Stage 2 failure: manifest has already flipped (consumers see new
#     version). Registry is in VALIDATING (protected). Rerun completes
#     the transition. Sync reports failure so the operator knows.


def _ensure_registry_validating(client, *, db_version, detail_index_url):
    """Stage 1: bring the registry row for db_version to VALIDATING-or-later.

    Idempotent and re-entry-safe per the table above.

    Returns the CatalogRelease in its final state after this stage.
    Raises RuntimeError on RETIRED (a retired version must never be
    silently resurrected — operator must create a new db_version).
    """
    from release_safety import (
        ReleaseChannel,
        ReleaseState,
        get_release,
        insert_pending_release,
        transition_to_validating,
    )

    existing = get_release(client, db_version)

    if existing is None:
        print(f"  [registry] {db_version}: no row found, inserting PENDING…")
        insert_pending_release(
            client,
            db_version=db_version,
            release_channel=ReleaseChannel.OTA_STABLE,
            detail_index_url=detail_index_url,
            notes="auto-created by sync_to_supabase",
        )
        print(f"  [registry] {db_version}: PENDING -> VALIDATING")
        return transition_to_validating(client, db_version)

    if existing.state == ReleaseState.PENDING:
        print(f"  [registry] {db_version}: row exists as PENDING; advancing -> VALIDATING")
        return transition_to_validating(client, db_version)

    if existing.state == ReleaseState.VALIDATING:
        print(f"  [registry] {db_version}: row already VALIDATING (idempotent re-entry)")
        return existing

    if existing.state == ReleaseState.ACTIVE:
        print(f"  [registry] {db_version}: row already ACTIVE (idempotent re-entry)")
        return existing

    if existing.state == ReleaseState.RETIRED:
        raise RuntimeError(
            f"[registry] refusing to activate RETIRED release {db_version!r}. "
            f"A retired release must never be silently resurrected. If this "
            f"is a legitimate re-release, create a new db_version instead."
        )

    # Defensive — registry.ReleaseState only has 4 members.
    raise RuntimeError(
        f"[registry] {db_version}: unexpected state {existing.state.value!r}"
    )


def _promote_registry_release(client, *, db_version):
    """Stage 2: atomically promote a VALIDATING release through the registry.

    The database function retires any older ACTIVE release in the same
    channel before activating this release, within one transaction. The
    client never sequences those state changes itself.
    """
    from release_safety import (
        ReleaseState,
        get_release,
    )

    print(f"  [registry] {db_version}: promoting atomically through database RPC")
    response = client.rpc(
        "promote_catalog_release",
        {"p_db_version": db_version},
    ).execute()
    if getattr(response, "data", None) is None:
        raise RuntimeError(
            "promote_catalog_release RPC returned no result; registry promotion "
            "may not have completed. Check Supabase logs before retrying."
        )

    promoted = get_release(client, db_version)
    if promoted is None or promoted.state != ReleaseState.ACTIVE:
        actual_state = "missing" if promoted is None else promoted.state.value
        raise RuntimeError(
            f"[registry] {db_version}: promotion RPC returned without an ACTIVE "
            f"registry row (observed {actual_state!r})."
        )

    print(f"  [registry] {db_version} is ACTIVE (idempotent promotion confirmed)")
    return promoted


# ---------------------------------------------------------------------------
# Pure functions (testable without Supabase)
# ---------------------------------------------------------------------------

def load_local_manifest(build_dir):
    """Read export_manifest.json from build output directory.

    Raises FileNotFoundError if the manifest is missing.
    """
    manifest_path = os.path.join(build_dir, "export_manifest.json")
    if not os.path.exists(manifest_path):
        raise FileNotFoundError(
            f"export_manifest.json not found in {build_dir}. "
            "Run build_final_db.py first."
        )
    with open(manifest_path) as f:
        return json.load(f)


def load_detail_index(build_dir):
    """Read detail_index.json from build output directory."""
    detail_index_path = os.path.join(build_dir, "detail_index.json")
    if not os.path.exists(detail_index_path):
        raise FileNotFoundError(
            f"detail_index.json not found in {build_dir}. "
            "Run build_final_db.py first."
        )
    with open(detail_index_path) as f:
        return json.load(f)


def needs_update(local_manifest, remote_manifest, force=False):
    """Determine if Supabase needs updating.

    Returns True if:
    - remote_manifest is None (first push ever)
    - db_version differs
    - checksum differs
    - force is explicitly enabled
    """
    if force:
        return True
    if remote_manifest is None:
        return True
    if local_manifest["db_version"] != remote_manifest["db_version"]:
        return True
    if local_manifest.get("checksum") != remote_manifest.get("checksum"):
        return True
    return False


def validate_bucket_upload_capacity(client, *, bucket, object_size_bytes):
    """Fail before upload when a Storage bucket policy rejects the core DB."""
    bucket_config = client.storage.get_bucket(bucket)
    if isinstance(bucket_config, dict):
        file_size_limit = bucket_config.get("file_size_limit")
    else:
        file_size_limit = getattr(bucket_config, "file_size_limit", None)

    if file_size_limit is None:
        return

    limit_bytes = int(file_size_limit)
    if object_size_bytes <= limit_bytes:
        return

    object_mib = object_size_bytes / (1024 * 1024)
    limit_mib = limit_bytes / (1024 * 1024)
    raise ValueError(
        f"Core catalog upload is {object_mib:.1f} MiB, which exceeds "
        f"Supabase bucket {bucket!r} file_size_limit {limit_mib:.1f} MiB. "
        "Raise the bucket limit before release; no upload was attempted."
    )


def collect_detail_blobs(build_dir):
    """Return sorted list of detail blob file paths."""
    detail_dir = os.path.join(build_dir, "detail_blobs")
    if not os.path.isdir(detail_dir):
        return []
    blobs = sorted(glob.glob(os.path.join(detail_dir, "*.json")))
    return blobs


def remote_blob_directory_for_path(remote_path):
    return os.path.dirname(remote_path)


def collect_unique_blob_uploads(build_dir, detail_index):
    """Collapse product-keyed local blobs into unique hash-keyed remote uploads."""
    uploads = {}
    for dsld_id, entry in detail_index.items():
        blob_sha256 = entry["blob_sha256"]
        remote_path = entry["storage_path"]
        local_path = os.path.join(build_dir, "detail_blobs", f"{dsld_id}.json")
        if not os.path.exists(local_path):
            raise FileNotFoundError(
                f"Local detail blob missing for dsld_id={dsld_id}: {local_path}"
            )
        uploads.setdefault(blob_sha256, {
            "blob_sha256": blob_sha256,
            "remote_path": remote_path,
            "local_path": local_path,
        })
    return [uploads[key] for key in sorted(uploads.keys())]


def partition_remote_paths_by_directory(uploads):
    grouped = {}
    for upload in uploads:
        grouped.setdefault(remote_blob_directory_for_path(upload["remote_path"]), set()).add(upload["remote_path"])
    return grouped


def filter_pending_blob_uploads(uploads, existing_remote_paths):
    pending = [upload for upload in uploads if upload["remote_path"] not in existing_remote_paths]
    skipped = len(uploads) - len(pending)
    return pending, skipped


# Transient errors worth retrying when listing remote storage. Narrow on
# purpose — a real bug (KeyError, TypeError, AttributeError) must still
# crash loudly; we are only papering over network/API hiccups.
#   - JSONDecodeError: Supabase Storage occasionally returns a non-JSON
#     body (empty response, HTML 5xx page, rate-limit page). The SDK
#     calls response.json() and raises JSONDecodeError. This is the
#     specific failure mode that killed the 2026-05-15 release.
#   - OSError: parent of ConnectionError, TimeoutError, socket errors.
_TRANSIENT_DISCOVERY_ERRORS = (json.JSONDecodeError, OSError)


def _list_with_retries(
    list_fn,
    client,
    bucket,
    directory,
    limit,
    offset,
    *,
    retries,
    base_delay,
    sleep_fn=time.sleep,
):
    """Call list_fn with bounded retry on transient API failures.

    Returns the page on success. Re-raises the last transient error after
    exhausting retries, or any non-transient error immediately.
    """
    last_error = None
    for attempt in range(retries + 1):
        try:
            return list_fn(client, bucket, directory, limit=limit, offset=offset)
        except _TRANSIENT_DISCOVERY_ERRORS as exc:
            last_error = exc
            if attempt >= retries:
                raise
            sleep_fn(base_delay * (2 ** attempt))
    raise last_error  # pragma: no cover - defensive; loop always returns or raises


def _discover_existing_remote_paths_for_directory(
    client,
    bucket,
    directory,
    expected_paths,
    list_fn,
    page_size,
    retries=DEFAULT_UPLOAD_RETRIES,
    base_delay=DEFAULT_RETRY_BASE_DELAY,
):
    existing = set()
    offset = 0
    while True:
        page = _list_with_retries(
            list_fn,
            client,
            bucket,
            directory,
            limit=page_size,
            offset=offset,
            retries=retries,
            base_delay=base_delay,
        )
        if not page:
            break
        for item in page:
            name = item.get("name")
            if not name:
                continue
            remote_path = f"{directory}/{name}"
            if remote_path in expected_paths:
                existing.add(remote_path)
        if existing == expected_paths:
            break
        offset += len(page)
    return existing


def _discover_existing_remote_paths_for_directory_with_factory(
    client_getter,
    bucket,
    directory,
    expected_paths,
    list_fn,
    page_size,
):
    return _discover_existing_remote_paths_for_directory(
        client_getter(),
        bucket,
        directory,
        expected_paths,
        list_fn,
        page_size,
    )


def discover_existing_remote_blob_paths(
    client,
    bucket,
    uploads,
    list_fn,
    page_size=1000,
    max_workers=DEFAULT_DISCOVERY_WORKERS,
    client_factory=None,
):
    """List existing remote blob objects in shard directories instead of per-blob exists() calls."""
    grouped = partition_remote_paths_by_directory(uploads)
    if not grouped:
        return set()

    if max_workers <= 1 or len(grouped) == 1:
        existing = set()
        for directory, expected_paths in grouped.items():
            try:
                existing.update(
                    _discover_existing_remote_paths_for_directory(
                        client,
                        bucket,
                        directory,
                        expected_paths,
                        list_fn,
                        page_size,
                    )
                )
            except Exception as exc:
                raise RuntimeError(
                    "Failed listing remote detail-blob shard "
                    f"{directory}: {type(exc).__name__}: {exc}"
                ) from exc
        return existing

    client_getter = make_thread_local_client_factory(client_factory) if client_factory else (lambda: client)
    existing = set()
    with ThreadPoolExecutor(max_workers=min(max_workers, len(grouped))) as executor:
        futures = {}
        for directory, expected_paths in grouped.items():
            future = executor.submit(
                _discover_existing_remote_paths_for_directory_with_factory,
                client_getter,
                bucket,
                directory,
                expected_paths,
                list_fn,
                page_size,
            )
            futures[future] = directory
        for future in as_completed(futures):
            directory = futures[future]
            try:
                existing.update(future.result())
            except Exception as exc:
                raise RuntimeError(
                    "Failed listing remote detail-blob shard "
                    f"{directory}: {type(exc).__name__}: {exc}"
                ) from exc
    return existing


def _compute_file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def upload_with_retries(upload_operation, retries, base_delay, sleep_fn=time.sleep):
    """Run an upload operation with exponential backoff."""
    last_error = None
    for attempt in range(retries + 1):
        try:
            return upload_operation()
        except Exception as exc:  # pragma: no cover - exercised via tests
            last_error = exc
            if attempt >= retries:
                raise
            sleep_fn(base_delay * (2 ** attempt))
    raise last_error  # pragma: no cover


def write_failure_report(build_dir, version, errors):
    """Persist failed uploads for resume/debugging."""
    report_path = os.path.join(build_dir, f"sync_failures_{version}.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "version": version,
                "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "error_count": len(errors),
                "errors": errors,
            },
            f,
            indent=2,
        )
    return report_path


def _upload_blob_task(client, upload_fn, bucket, local_path, remote_blob_path, retries, base_delay, error_key):
    try:
        upload_with_retries(
            lambda: upload_fn(
                client,
                bucket,
                remote_blob_path,
                local_path,
                content_type="application/json",
                # sha256-addressed path — content never changes; let the
                # CDN serve it from edge forever.
                cache_control=CACHE_CONTROL_IMMUTABLE,
            ),
            retries=retries,
            base_delay=base_delay,
        )
        return None
    except Exception as exc:
        return {"blob_sha256": error_key, "error": str(exc)}


def _upload_blob_task_with_factory(client_getter, upload_fn, bucket, local_path, remote_blob_path, retries, base_delay, error_key):
    """Resolve the client inside the worker thread, then upload."""
    return _upload_blob_task(
        client_getter(),
        upload_fn,
        bucket,
        local_path,
        remote_blob_path,
        retries,
        base_delay,
        error_key,
    )


def make_thread_local_client_factory(client_factory):
    """Return a thread-local client getter for concurrent upload workers."""
    local = threading.local()

    def get_client():
        client = getattr(local, "client", None)
        if client is None:
            client = client_factory()
            local.client = client
        return client

    return get_client


def _bounded_results(executor, operation, items, max_pending):
    """Keep only a small window of tasks alive, including completed futures."""
    items = iter(items)
    pending = set()
    exhausted = False
    while pending or not exhausted:
        while not exhausted and len(pending) < max_pending:
            try:
                item = next(items)
            except StopIteration:
                exhausted = True
                break
            pending.add(executor.submit(operation, item))
        if pending:
            done, pending = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                yield future.result()


def upload_detail_blobs(
    client,
    bucket,
    uploads,
    upload_fn,
    max_workers,
    retries,
    base_delay,
    progress_every=DEFAULT_PROGRESS_EVERY,
    client_factory=None,
    preexisting_remote_paths=None,
):
    """Upload detail blobs with bounded concurrency and retry logic."""
    start = time.time()
    errors = []
    completed = 0
    pending_uploads, skipped = filter_pending_blob_uploads(uploads, preexisting_remote_paths or set())
    total = len(uploads)

    if max_workers <= 1:
        for upload in pending_uploads:
            error = _upload_blob_task(
                client,
                upload_fn,
                bucket,
                upload["local_path"],
                upload["remote_path"],
                retries,
                base_delay,
                upload["blob_sha256"],
            )
            completed += 1
            if error:
                errors.append(error)
            if completed % progress_every == 0 or completed == total:
                elapsed = time.time() - start
                print(f"  {completed + skipped}/{total} ({elapsed:.1f}s)")
    else:
        client_getter = make_thread_local_client_factory(client_factory) if client_factory else (lambda: client)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            def one(upload):
                return _upload_blob_task_with_factory(
                    client_getter, upload_fn, bucket, upload["local_path"],
                    upload["remote_path"], retries, base_delay, upload["blob_sha256"],
                )
            for error in _bounded_results(executor, one, pending_uploads, max_workers * 2):
                completed += 1
                if error:
                    errors.append(error)
                if (completed + skipped) % progress_every == 0 or (completed + skipped) == total:
                    elapsed = time.time() - start
                    print(f"  {completed + skipped}/{total} ({elapsed:.1f}s)")

    return time.time() - start, errors, len(pending_uploads) - len(errors), skipped


def validate_build_output(build_dir, manifest):
    """Validate local build output before any upload begins."""
    # Sprint E1.5 — gate reads the BLOCKING bucket only. The build tool
    # now splits export failures into three manifest lists:
    #   errors[]             — catastrophic (schema drift, unknown enum,
    #                          column mismatch). BLOCKS sync.
    #   excluded_by_gate[]   — by-design coverage gate (E1.2.5). Logged.
    #   warnings[]           — authoring backlog (tone sweep). Logged.
    # See build_final_db.py _EXPORT_ERROR_TAXONOMY for the classifier.
    build_errors = manifest.get("errors") or []
    if build_errors:
        raise ValueError(
            f"Build output contains {len(build_errors)} export errors; "
            f"refusing to sync partial artifact"
        )
    excluded = manifest.get("excluded_by_gate") or []
    warnings = manifest.get("warnings") or []
    if excluded or warnings:
        # Surface non-blocking classification counts so the operator sees
        # what the gate consciously let through.
        print(
            f"  [info] non-blocking exclusions: "
            f"excluded_by_gate={len(excluded)}, "
            f"warnings={len(warnings)} "
            f"(see export_manifest.json for per-product detail)"
        )

    db_path = os.path.join(build_dir, "pharmaguide_core.db")
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"pharmaguide_core.db not found in {build_dir}")

    detail_index_path = os.path.join(build_dir, "detail_index.json")
    if not os.path.exists(detail_index_path):
        raise FileNotFoundError(f"detail_index.json not found in {build_dir}")

    expected_checksum = manifest.get("checksum")
    actual_checksum = f"sha256:{_compute_file_sha256(db_path)}"
    if expected_checksum != actual_checksum:
        raise ValueError(
            "Build output checksum mismatch: "
            f"manifest={expected_checksum}, actual={actual_checksum}"
        )

    # V4 six-pillar contract on the checksum-verified DB. Defense-in-depth for the
    # 2026-06-14 stale-DB incident: blocks a sync of a dist built before the
    # pillar-projection commit even if it never went through the rebuild gate.
    pillar_findings = check_v4_pillar_contract(db_path)
    if pillar_findings:
        raise ValueError(
            "Build output violates the V4 pillar contract; refusing to sync: "
            + "; ".join(f.render() for f in pillar_findings[:5])
        )

    blobs = collect_detail_blobs(build_dir)
    detail_index = load_detail_index(build_dir)
    expected_products = int(manifest["product_count"])
    if len(blobs) != expected_products:
        raise ValueError(
            "Build output blob mismatch: "
            f"manifest product_count={expected_products}, blobs={len(blobs)}"
        )
    if len(detail_index) != expected_products:
        raise ValueError(
            "Build output detail index mismatch: "
            f"manifest product_count={expected_products}, detail_index={len(detail_index)}"
        )
    unique_blob_uploads = collect_unique_blob_uploads(build_dir, detail_index)

    expected_unique = manifest.get("detail_blob_unique_count")
    if expected_unique is not None and len(unique_blob_uploads) != int(expected_unique):
        raise ValueError(
            "Build output unique blob mismatch: "
            f"manifest detail_blob_unique_count={expected_unique}, unique_blobs={len(unique_blob_uploads)}"
        )

    expected_detail_index_checksum = manifest.get("detail_index_checksum")
    if expected_detail_index_checksum:
        actual_detail_index_checksum = f"sha256:{_compute_file_sha256(detail_index_path)}"
        if expected_detail_index_checksum != actual_detail_index_checksum:
            raise ValueError(
                "Build output detail index checksum mismatch: "
                f"manifest={expected_detail_index_checksum}, actual={actual_detail_index_checksum}"
            )

    return {
        "db_path": db_path,
        "detail_index_path": detail_index_path,
        "blob_count": len(blobs),
        "unique_blob_count": len(unique_blob_uploads),
        "detail_index": detail_index,
        "unique_blob_uploads": unique_blob_uploads,
        "db_size_mb": os.path.getsize(db_path) / (1024 * 1024),
    }


# ---------------------------------------------------------------------------
# Product image upload
# ---------------------------------------------------------------------------

PRODUCT_IMAGE_BUCKET = "product-images"


def load_product_image_index(build_dir):
    """Load product_image_index.json from the product_images subdirectory."""
    for candidate in [
        os.path.join(build_dir, "product_images", "product_image_index.json"),
        os.path.join(build_dir, "product_image_index.json"),
    ]:
        if os.path.exists(candidate):
            with open(candidate) as f:
                return json.load(f), os.path.dirname(candidate)
    return None, None


def _upload_image_task(client, upload_fn, bucket, local_path, remote_path, retries,
                       base_delay, immutable=False):
    """Upload a single .webp image to Supabase Storage."""
    try:
        upload_with_retries(
            lambda: upload_fn(
                client, bucket, remote_path, local_path,
                content_type="image/webp",
                upsert=not immutable,
                cache_control=CACHE_CONTROL_IMMUTABLE if immutable else None,
            ),
            retries=retries,
            base_delay=base_delay,
        )
        return None
    except Exception as exc:
        return {"remote_path": remote_path, "error": str(exc)}


def _upload_image_task_with_factory(client_getter, upload_fn, bucket, local_path, remote_path,
                                    retries, base_delay, download_fn=None,
                                    remote_exists=False, immutable=False):
    client = client_getter()
    if remote_exists:
        if download_fn is None:
            if immutable:
                return {
                    "remote_path": remote_path,
                    "error": "Existing versioned image could not be identity-checked",
                }
        else:
            try:
                remote_bytes = upload_with_retries(
                    lambda: download_fn(client, bucket, remote_path), retries, base_delay,
                )
                if hashlib.sha256(remote_bytes).hexdigest() == _compute_file_sha256(local_path):
                    return "skipped"
                if immutable:
                    return {
                        "remote_path": remote_path,
                        "error": "Existing versioned image bytes differ",
                    }
            except Exception as exc:
                if immutable:
                    return {
                        "remote_path": remote_path,
                        "error": f"Existing versioned image could not be verified: {exc}",
                    }
    return _upload_image_task(
        client, upload_fn, bucket, local_path, remote_path, retries, base_delay,
        immutable=immutable,
    )


def upload_product_images(
    client,
    build_dir,
    upload_fn,
    list_fn,
    max_workers=DEFAULT_MAX_WORKERS,
    retries=DEFAULT_UPLOAD_RETRIES,
    base_delay=DEFAULT_RETRY_BASE_DELAY,
    client_factory=None,
    dry_run=False,
    download_fn=None,
    catalog_version=None,
):
    """Upload product_images/*.webp to Supabase Storage bucket.

    Skips only files whose remote bytes match, when a downloader is supplied.
    Returns dict with uploaded, skipped, failed counts.
    """
    index, image_dir = load_product_image_index(build_dir)
    if index is None:
        print("  No product_image_index.json found — skipping image upload")
        return {"uploaded": 0, "skipped": 0, "failed": 0}

    total = len(index)
    print(f"  Found {total} images in index")

    if dry_run:
        print(f"  [DRY RUN] Would upload {total} product images to {PRODUCT_IMAGE_BUCKET}")
        return {"uploaded": 0, "skipped": total, "failed": 0}

    # Discover existing remote images to skip re-uploads
    existing_sizes = {}
    try:
        image_prefix = f"v{catalog_version}" if catalog_version is not None else ""
        page_size = 1000
        offset = 0
        while True:
            page = list_fn(
                client, PRODUCT_IMAGE_BUCKET, image_prefix,
                limit=page_size, offset=offset,
            )
            for item in page or []:
                name = item.get("name", "")
                metadata = item.get("metadata", {}) or {}
                size = metadata.get("size") or metadata.get("contentLength") or 0
                if name:
                    remote_name = f"{image_prefix}/{name}" if image_prefix else name
                    existing_sizes[remote_name] = int(size) if size else 0
            if not page:
                break
            offset += len(page)
    except Exception:
        pass  # Bucket may not exist yet — upload all

    # Build upload list
    uploads = []
    skipped = 0
    errors = []
    for dsld_id, entry in sorted(index.items()):
        filename = entry["filename"]
        local_path = os.path.join(image_dir, filename)
        declared_remote_path = entry.get("remote_path")
        remote_path = declared_remote_path or filename
        if catalog_version is not None and declared_remote_path is not None:
            expected_prefix = f"v{catalog_version}/"
            if (
                not isinstance(remote_path, str)
                or not remote_path.startswith(expected_prefix)
                or os.path.basename(remote_path) != filename
                or ".." in remote_path.split("/")
            ):
                errors.append({
                    "remote_path": str(remote_path),
                    "error": "Indexed product image is not version-bound",
                })
                continue
        if not os.path.isfile(local_path):
            errors.append({"remote_path": remote_path, "error": "Indexed local image is missing"})
            continue
        local_size = os.path.getsize(local_path)
        uploads.append({
            "local_path": local_path,
            "remote_path": remote_path,
            "remote_exists": remote_path in existing_sizes,
        })

    uploaded = 0
    start = time.time()

    if not uploads:
        print(f"  Images: {skipped} unchanged, {len(errors)} missing local files")
        return {"uploaded": 0, "skipped": skipped, "failed": len(errors)}

    client_getter = make_thread_local_client_factory(client_factory) if client_factory else (lambda: client)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        def one(upload):
            return _upload_image_task_with_factory(
                client_getter, upload_fn, PRODUCT_IMAGE_BUCKET,
                upload["local_path"], upload["remote_path"], retries, base_delay,
                download_fn, upload["remote_exists"], catalog_version is not None,
            )
        for error in _bounded_results(executor, one, uploads, max_workers * 2):
            if error == "skipped":
                skipped += 1
            elif error:
                errors.append(error)
            else:
                uploaded += 1
            done = uploaded + skipped + len(errors)
            if done % 500 == 0 or done == total:
                elapsed = time.time() - start
                print(f"  Images: {done}/{total} ({elapsed:.1f}s)")

    elapsed = time.time() - start
    print(
        f"  Image upload done: {uploaded} uploaded, {skipped} skipped, "
        f"{len(errors)} failed ({elapsed:.1f}s)"
    )

    if errors:
        for err in errors[:5]:
            print(f"    FAIL: {err['remote_path']}: {err['error']}")
        if len(errors) > 5:
            print(f"    ... and {len(errors) - 5} more")

    return {"uploaded": uploaded, "skipped": skipped, "failed": len(errors)}


# ---------------------------------------------------------------------------
# Supabase operations (require real client)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Public catalog search table (read by the app repo's public MCP function)
# ---------------------------------------------------------------------------

CATALOG_SEARCH_TABLE = "catalog_search"
CATALOG_SEARCH_BATCH_SIZE = 500
#: Retain this many versions, always including the release and current manifest.
CATALOG_SEARCH_KEEP_VERSIONS = 2
#: products_core columns copied into catalog_search (scripts/sql/supabase_schema.sql
#: section 9). Values pass through unchanged except: blank text -> NULL, and
#: upc_sku normalized like the app's CoreDatabase.upcNormalizeSql.
CATALOG_SEARCH_COLUMNS = (
    "dsld_id",
    "product_name",
    "brand_name",
    "brand_family",
    "product_line",
    "upc_sku",
    "form_factor",
    "supplement_type",
    "product_status",
    "quality_tier",
    "quality_score_status",
    "quality_score_v4_100",
    "product_safety_status",
    "mapped_coverage",
    "quality_score_confidence",
    "quality_assessment_status",
)
_CATALOG_UPC_SEPARATORS = (" ", "-", ".", "/")


def _catalog_text(value):
    if value is None:
        return None
    text = str(value)
    return text if text.strip() else None


def normalize_catalog_upc(value):
    """Mirror Flutter ``CoreDatabase.upcNormalizeSql`` (drop ' ', '-', '.', '/')."""
    text = _catalog_text(value)
    if text is None:
        return None
    for separator in _CATALOG_UPC_SEPARATORS:
        text = text.replace(separator, "")
    return text or None


def catalog_search_rows_from_connection(conn, catalog_version):
    """Map every products_core row to one catalog_search upsert payload."""
    if not catalog_version:
        raise ValueError("catalog_search: catalog_version is required")
    columns = ", ".join(CATALOG_SEARCH_COLUMNS)
    rows = []
    for record in conn.execute(f"SELECT {columns} FROM products_core ORDER BY dsld_id"):
        raw = dict(zip(CATALOG_SEARCH_COLUMNS, record))
        row = {"catalog_version": catalog_version}
        for column in CATALOG_SEARCH_COLUMNS:
            row[column] = _catalog_text(raw[column])
        row["upc_sku"] = normalize_catalog_upc(raw["upc_sku"])
        coverage = raw["mapped_coverage"]
        if coverage is not None:
            coverage = float(coverage)
            if math.isnan(coverage) or not 0.0 <= coverage <= 1.0:
                raise ValueError(
                    f"catalog_search: dsld_id {raw['dsld_id']!r} has mapped_coverage "
                    f"{raw['mapped_coverage']!r} outside [0, 1]"
                )
        row["mapped_coverage"] = coverage
        score = raw["quality_score_v4_100"]
        if score is not None:
            score = float(score)
            if not math.isfinite(score) or not 0 <= score <= 100:
                raise ValueError("catalog_search: quality_score_v4_100 outside [0, 100]")
        row["quality_score_v4_100"] = score
        if row["dsld_id"] is None or row["product_name"] is None:
            raise ValueError(
                "catalog_search: products_core row without dsld_id/product_name: "
                f"{raw['dsld_id']!r}"
            )
        rows.append(row)
    return rows


def catalog_search_rows(db_path, catalog_version):
    """Read the release's core DB (read-only, stdlib sqlite3) into upsert payloads."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        return catalog_search_rows_from_connection(conn, catalog_version)
    finally:
        conn.close()


def catalog_search_keep_versions(client, catalog_version, keep=CATALOG_SEARCH_KEEP_VERSIONS):
    """Keep the published and current versions before filling recent-history slots."""
    current = (
        client.table("export_manifest")
        .select("db_version")
        .eq("is_current", True)
        .limit(1)
        .execute()
    )
    kept = [catalog_version]
    for record in current.data or []:
        version = (record or {}).get("db_version")
        if version and version not in kept:
            kept.append(version)
    response = (
        client.table("export_manifest")
        .select("db_version")
        .order("created_at", desc=True)
        .limit(10)
        .execute()
    )
    for record in response.data or []:
        if len(kept) >= keep:
            break
        version = (record or {}).get("db_version")
        if version and version not in kept:
            kept.append(version)
    return kept


def publish_catalog_search(
    client,
    *,
    db_path,
    catalog_version,
    batch_size=CATALOG_SEARCH_BATCH_SIZE,
    keep_versions=CATALOG_SEARCH_KEEP_VERSIONS,
    retries=DEFAULT_UPLOAD_RETRIES,
    base_delay=DEFAULT_RETRY_BASE_DELAY,
    sleep_fn=time.sleep,
):
    """Upsert this release's catalog_search rows, then prune older versions.

    New versions become visible with the manifest rotation. A same-version
    correction updates the current view batch by batch; it is not atomic.
    Reconcile removed IDs only after every upsert succeeds. Retrying either
    phase is idempotent, including an interrupted deletion batch.
    """
    rows = catalog_search_rows(db_path, catalog_version)
    if not rows:
        raise ValueError("catalog_search: core DB has no products to publish")
    # Read every existing ID before deleting: offset pagination during deletion
    # can skip rows, and the server may cap a page below the requested limit.
    desired = {row["dsld_id"]: row for row in rows}
    unchanged = set()
    stale_ids = []
    last_id = None
    while True:
        query = (
            client.table(CATALOG_SEARCH_TABLE)
            .select(",".join(rows[0]))
            .eq("catalog_version", catalog_version)
            .order("dsld_id")
            .limit(CATALOG_SEARCH_BATCH_SIZE)
        )
        if last_id is not None:
            query = query.gt("dsld_id", last_id)
        response = upload_with_retries(query.execute, retries, base_delay, sleep_fn)
        existing = response.data or []
        if not existing:
            break
        for row in existing:
            key = row["dsld_id"]
            if key not in desired:
                stale_ids.append(key)
            elif all(column in row and row[column] == value
                     for column, value in desired[key].items()):
                unchanged.add(key)
        last_id = existing[-1]["dsld_id"]
    changed_rows = [row for row in rows if row["dsld_id"] not in unchanged]
    for start in range(0, len(changed_rows), batch_size):
        batch = changed_rows[start:start + batch_size]
        upload_with_retries(
            lambda batch=batch: client.table(CATALOG_SEARCH_TABLE)
            .upsert(batch, on_conflict="catalog_version,dsld_id")
            .execute(),
            retries,
            base_delay,
            sleep_fn,
        )
    for start in range(0, len(stale_ids), CATALOG_SEARCH_BATCH_SIZE):
        obsolete = stale_ids[start:start + CATALOG_SEARCH_BATCH_SIZE]
        upload_with_retries(
            lambda obsolete=obsolete: client.table(CATALOG_SEARCH_TABLE)
            .delete()
            .eq("catalog_version", catalog_version)
            .in_("dsld_id", obsolete)
            .execute(),
            retries,
            base_delay,
            sleep_fn,
        )
    kept = catalog_search_keep_versions(client, catalog_version, keep_versions)
    upload_with_retries(
        lambda: client.table(CATALOG_SEARCH_TABLE)
        .delete()
        .not_.in_("catalog_version", kept)
        .execute(),
        retries,
        base_delay,
        sleep_fn,
    )
    return {"row_count": len(rows), "kept_versions": kept}


def _publish_catalog_search_step(client, *, db_path, version, retries, base_delay):
    print(f"\nPublishing {CATALOG_SEARCH_TABLE} rows for {version}...")
    start = time.time()
    result = publish_catalog_search(
        client,
        db_path=db_path,
        catalog_version=version,
        retries=retries,
        base_delay=base_delay,
    )
    print(
        f"  Done ({result['row_count']} rows in {time.time() - start:.1f}s; "
        f"kept versions: {', '.join(result['kept_versions'])})"
    )
    return result


def is_v4_manifest(manifest):
    """Return True for the production v4 export schema."""
    schema = str((manifest or {}).get("schema_version") or "")
    score_model = str((manifest or {}).get("score_model") or "")
    try:
        major = int(schema.split(".")[0])
    except (ValueError, IndexError, AttributeError):
        major = 0
    return (score_model == "v4") or (major >= 2)


def v4_manifest_sync_message(manifest):
    """Describe the exact export schema being synchronized."""
    schema = str((manifest or {}).get("schema_version") or "unknown")
    return (
        f"  [v4] schema {schema} build — syncing as the production "
        "catalog contract."
    )


def sync(
    build_dir,
    dry_run=False,
    force=False,
    max_workers=DEFAULT_MAX_WORKERS,
    retry_count=DEFAULT_UPLOAD_RETRIES,
    retry_base_delay=DEFAULT_RETRY_BASE_DELAY,
    submission_output_dir=None,
):
    """Main sync workflow.

    1. Load local manifest
    2. Compare to remote manifest
    3. Upload .db file to Storage
    4. Upload detail blobs to Storage
    5. Publish catalog_search rows (public MCP search); prune old versions
    6. Insert new manifest row
    """
    sync_started_at = time.monotonic()

    from supabase_client import (
        download_file,
        get_supabase_client,
        fetch_current_manifest,
        insert_manifest,
        list_storage_paths,
        upload_file,
    )

    print(f"Loading manifest from {build_dir}...")
    local = load_local_manifest(build_dir)
    if is_v4_manifest(local):
        print(v4_manifest_sync_message(local))
    version = local["db_version"]
    product_count = local["product_count"]
    checksum = local["checksum"]
    build_stats = validate_build_output(build_dir, local)
    share_index_dir = os.path.join(build_dir, SHARE_INDEX_DIRNAME)
    share_product_count = write_share_index(
        db_path=build_stats["db_path"],
        output_dir=share_index_dir,
        catalog_version=version,
    )
    if share_product_count != int(product_count):
        raise ValueError(
            "Share index product count mismatch: "
            f"manifest={product_count}, share_index={share_product_count}"
        )
    build_stats["share_index_dir"] = share_index_dir

    print(f"  Version:  {version}")
    print(f"  Products: {product_count}")
    print(f"  Checksum: {checksum[:20]}...")

    if dry_run:
        print(f"\n[DRY RUN] Would upload:")
        print(f"  - pharmaguide_core.db ({build_stats['db_size_mb']:.1f} MB)")
        print(f"  - detail_index.json")
        print(f"  - {len(SHARE_INDEX_SHARDS)} canonical share-index shards")
        print(f"  - {build_stats['unique_blob_count']} unique detail blobs ({build_stats['blob_count']} product mappings)")
        img_index, _ = load_product_image_index(build_dir)
        if img_index:
            print(f"  - {len(img_index)} product images to {PRODUCT_IMAGE_BUCKET}")
        catalog_search_count = len(catalog_search_rows(build_stats["db_path"], version))
        print(
            f"  - {catalog_search_count} {CATALOG_SEARCH_TABLE} rows (public MCP search); "
            f"keep the last {CATALOG_SEARCH_KEEP_VERSIONS} versions"
        )
        print(f"  - New manifest row (version {version})")
        return {"status": "dry_run", "version": version, "blob_count": build_stats["blob_count"]}

    client = get_supabase_client()
    bucket = STORAGE_BUCKET
    print("Checking Supabase for current version...")
    remote = fetch_current_manifest(client)

    if remote:
        print(f"  Remote version: {remote['db_version']}")
    else:
        print("  No remote version found (first push)")

    catalog_changed = needs_update(local, remote, force=force)
    same_catalog_identity = bool(
        remote
        and local["db_version"] == remote.get("db_version")
        and local.get("checksum") == remote.get("checksum")
    )
    if (
        remote
        and local["db_version"] == remote.get("db_version")
        and local.get("checksum") != remote.get("checksum")
    ):
        raise ValueError(
            "Refusing to mutate the active catalog version; rebuild with a fresh db_version"
        )
    if same_catalog_identity:
        catalog_changed = False
    remote_db_path = core_db_remote_path(version)
    catalog_upload_needed = catalog_changed or force
    if not catalog_changed:
        # The current manifest owns byte identity, but does not prove the object
        # survived storage deletion. Check its exact path without downloading DB.
        present = _discover_existing_remote_paths_for_directory(
            client, bucket, f"v{version}", {remote_db_path}, list_storage_paths, 1000,
        )
        catalog_upload_needed = remote_db_path not in present
    if catalog_upload_needed:
        validate_bucket_upload_capacity(
            client, bucket=bucket,
            object_size_bytes=os.path.getsize(build_stats["db_path"]),
        )

    def sync_mutable(remote_path, local_path, content_type="application/json"):
        # These paths are mutable, so neither existence nor size proves identity.
        # A failed read never authorizes a skip; upload with the same retry policy.
        try:
            remote_bytes = download_file(client, bucket, remote_path)
            unchanged = hashlib.sha256(remote_bytes).hexdigest() == _compute_file_sha256(local_path)
        except Exception:
            unchanged = False
        if unchanged and not force:
            return
        upload_with_retries(
            lambda: upload_file(
                client, bucket, remote_path, local_path, content_type=content_type,
                cache_control=CATALOG_MUTABLE_CACHE_SECONDS,
            ), retry_count, retry_base_delay,
        )

    # Upload SQLite DB
    db_path = build_stats["db_path"]

    print(f"\n{'Uploading' if catalog_upload_needed else 'Reusing current'} {remote_db_path}...")
    start = time.time()
    if catalog_upload_needed:
        upload_with_retries(
            lambda: upload_file(client, bucket, remote_db_path, db_path,
                                cache_control=CATALOG_MUTABLE_CACHE_SECONDS),
            retry_count, retry_base_delay,
        )
    db_time = time.time() - start
    db_size_mb = build_stats["db_size_mb"]
    print(f"  Done ({db_size_mb:.1f} MB in {db_time:.1f}s)")

    # Upload unique detail blobs with bounded concurrency, retry logic, and remote dedupe.
    uploads = build_stats["unique_blob_uploads"]
    blob_count = build_stats["blob_count"]
    unique_blob_count = build_stats["unique_blob_count"]
    # An index reference is not proof that an object still exists, and ignores
    # objects already uploaded by a failed attempt. Discover every target shard.
    print("\nDiscovering existing remote hashed blobs...")
    start = time.time()
    existing_remote_paths = discover_existing_remote_blob_paths(
        client, bucket, uploads, list_storage_paths,
        max_workers=min(max_workers, DEFAULT_DISCOVERY_WORKERS),
        client_factory=get_supabase_client,
        catalog_version=version,
    )
    discover_time = time.time() - start
    print(f"  Found {len(existing_remote_paths)} existing hashed blobs in {discover_time:.1f}s")
    print(
        f"\nUploading {unique_blob_count} unique detail blobs "
        f"(from {blob_count} product mappings) with max_workers={max_workers}, retries={retry_count}..."
    )
    blob_time, errors, uploaded_count, skipped_count = upload_detail_blobs(
        client=client,
        bucket=bucket,
        uploads=uploads,
        upload_fn=upload_file,
        max_workers=max_workers,
        retries=retry_count,
        base_delay=retry_base_delay,
        client_factory=get_supabase_client,
        preexisting_remote_paths=existing_remote_paths,
    )
    print(
        f"  Done ({unique_blob_count} unique blobs in {blob_time:.1f}s, "
        f"{uploaded_count} uploaded, {skipped_count} skipped, {len(errors)} errors)"
    )

    # Indexed images are an independent required upload phase.
    print("\nUploading product images...")
    image_result = upload_product_images(
        client=client,
        build_dir=build_dir,
        upload_fn=upload_file,
        list_fn=list_storage_paths,
        download_fn=download_file,
        max_workers=max_workers,
        retries=retry_count,
        base_delay=retry_base_delay,
        client_factory=get_supabase_client,
        catalog_version=version,
    )

    if image_result["failed"]:
        errors.append({"blob_sha256": "product-images", "error":
                       f"{image_result['failed']} indexed image uploads failed"})

    # Abort publication if required objects failed — prevents activating an
    # incomplete release or publishing indexes for missing detail/image objects.
    if errors:
        failure_report = write_failure_report(build_dir, version, errors)
        print(f"\nAborting manifest rotation: {len(errors)} required upload failures.")
        for err in errors[:10]:
            print(f"  - {err['blob_sha256']}: {err['error']}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more")
        print(f"Failure report: {failure_report}")
        print("Fix the errors and re-run. The DB file was uploaded (upsert safe).")
        return {
            "status": "partial_failure",
            "version": version,
            "product_count": int(product_count),
            "blob_count": blob_count,
            "unique_blob_count": unique_blob_count,
            "error_count": len(errors),
            "time_seconds": round(time.monotonic() - sync_started_at, 1),
        }

    # Publish mutable indexes only once their referenced detail/image objects
    # succeeded, including same-version repairs of an already visible catalog.
    detail_index_path = build_stats["detail_index_path"]
    remote_detail_index_path = f"v{version}/detail_index.json"
    print(f"\nUploading {remote_detail_index_path}...")
    start = time.time()
    sync_mutable(remote_detail_index_path, detail_index_path)
    detail_index_time = time.time() - start
    print(f"  Done ({detail_index_time:.1f}s)")

    print(f"\nUploading canonical share-index shards for {version}...")
    start = time.time()
    for shard in SHARE_INDEX_SHARDS:
        sync_mutable(
            f"v{version}/{SHARE_INDEX_DIRNAME}/{shard}.json",
            os.path.join(build_stats["share_index_dir"], f"{shard}.json"),
        )
    share_index_time = time.time() - start
    print(f"  Done ({share_index_time:.1f}s)")

    # Public MCP search rows for this release go in BEFORE the manifest flip;
    # catalog_search_current exposes them only once rotate_manifest runs.
    _publish_catalog_search_step(
        client,
        db_path=db_path,
        version=version,
        retries=retry_count,
        base_delay=retry_base_delay,
    )

    # P3.6b Stage 1: bring catalog_releases registry row to VALIDATING
    # BEFORE the manifest flip. Once VALIDATING, P3.5 protected-set
    # computation will fold this version's blobs into the protected union,
    # so any orphan cleanup that runs (after the lock is released) cannot
    # touch them. Stage 1 failure aborts the sync — manifest stays at the
    # previous version, no consumer-visible change.
    print(f"\n[registry] Stage 1: ensuring {version} is VALIDATING...")
    _ensure_registry_validating(
        client,
        db_version=version,
        detail_index_url=remote_detail_index_path,
    )

    submission_approvals = []
    if submission_output_dir:
        from product_submission_import import build_release_activation_approvals
        submission_approvals = build_release_activation_approvals(
            output_dir=submission_output_dir,
            catalog_db=db_path,
            detail_blobs_dir=os.path.join(build_dir, "detail_blobs"),
        )

    # Insert manifest and stamp locally proven submission promotions in the
    # same transaction (only after every immutable object is staged).
    # is at least VALIDATING — see P3.6b above).
    print(f"\nUpdating manifest (version {version})...")
    if catalog_changed:
        insert_manifest(
            client, local, submission_approvals=submission_approvals,
        )
    print("  Done")

    # P3.6b Stage 2: bring catalog_releases to ACTIVE AFTER manifest flip.
    # Manifest is already updated (consumers see new version). Stage 2
    # failure leaves the row in VALIDATING — still fully protected,
    # operator re-run will resume from VALIDATING and complete ACTIVE.
    print(f"\n[registry] Stage 2: promoting {version} atomically...")
    _promote_registry_release(client, db_version=version)
    print(f"  [registry] {version} is ACTIVE; release fully visible to cleanup gates")

    # Summary
    total_time = time.monotonic() - sync_started_at
    print(f"\n{'=' * 50}")
    print(f"Sync complete: v{version}")
    print(f"  Products:    {product_count}")
    print(f"  DB size:     {db_size_mb:.1f} MB")
    print(f"  Blob refs:   {blob_count}")
    print(f"  Unique blobs:{unique_blob_count} ({uploaded_count} uploaded, {skipped_count} skipped)")
    print(f"  Errors:      {len(errors)}")
    print(f"  Total time:  {total_time:.1f}s")
    print(f"{'=' * 50}")

    if errors:
        print(f"\nFailed uploads ({len(errors)}):")
        for err in errors[:10]:
            print(f"  - {err['blob_sha256']}: {err['error']}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more")

    if not catalog_changed:
        return {"status": "up_to_date", "version": version}
    return {
        "status": "synced",
        "version": version,
        "product_count": int(product_count),
        "blob_count": blob_count,
        "error_count": len(errors),
        "time_seconds": round(total_time, 1),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Sync PharmaGuide build output to Supabase Storage and manifest."
    )
    parser.add_argument("build_dir", nargs='?', help="Build output directory containing manifest, DB, and detail_blobs")
    parser.add_argument("--preflight-only", action='store_true',
                        help='Read-only credential/manifest/bucket access check; no catalog required')
    parser.add_argument("--dry-run", action="store_true", help="Show what would be uploaded without uploading")
    parser.add_argument("--force", action="store_true", help="Upload and rotate manifest even if version/checksum match")
    parser.add_argument(
        "--submission-output-dir",
        help="Private approval receipt directory for atomic activation fencing",
    )
    parser.add_argument("--max-workers", type=int, default=DEFAULT_MAX_WORKERS,
                        help=f"Max concurrent detail-blob uploads (default: {DEFAULT_MAX_WORKERS})")
    parser.add_argument("--retry-count", type=int, default=DEFAULT_UPLOAD_RETRIES,
                        help=f"Retries per upload after the first attempt (default: {DEFAULT_UPLOAD_RETRIES})")
    parser.add_argument("--retry-base-delay", type=float, default=DEFAULT_RETRY_BASE_DELAY,
                        help=f"Base seconds for exponential retry backoff (default: {DEFAULT_RETRY_BASE_DELAY})")
    parser.add_argument("--cleanup", action="store_true",
                        help="After successful sync, clean up old versions (keep last 2)")
    parser.add_argument("--cleanup-keep", type=int, default=2,
                        help="Number of versions to keep during cleanup (default: 2)")
    args = parser.parse_args(argv)
    if not args.preflight_only and not args.build_dir:
        parser.error('build_dir is required outside --preflight-only')
    if args.preflight_only and (args.cleanup or args.force):
        parser.error('--preflight-only cannot be combined with --cleanup or --force')
    return args


def _build_cleanup_args(cleanup_keep):
    """Build version-only cleanup argv; orphans use the frozen-artifact CLI."""
    return [
        "--keep", str(cleanup_keep),
        "--execute",
        "--cleanup-db",
    ]


def main(argv=None):
    args = parse_args(argv)

    if args.preflight_only:
        from supabase_client import get_supabase_client, fetch_current_manifest, require_publication_contract
        try:
            client = get_supabase_client()
            fetch_current_manifest(client)
            client.storage.get_bucket(STORAGE_BUCKET)
            require_publication_contract()
        except Exception:
            print('Error: Supabase preflight could not verify manifest/bucket or publication RPC contract; check deployed migration, credentials, network and access', file=sys.stderr)
            raise SystemExit(1)
        print('Supabase manifest/bucket access and publication RPC contract passed; no uploads or writes attempted')
        return 0

    if not os.path.isdir(args.build_dir):
        print(f"Error: {args.build_dir} is not a directory")
        sys.exit(1)

    try:
        result = sync(
            args.build_dir,
            dry_run=args.dry_run,
            force=args.force,
            max_workers=args.max_workers,
            retry_count=args.retry_count,
            retry_base_delay=args.retry_base_delay,
            submission_output_dir=args.submission_output_dir,
        )
        if result["status"] == "partial_failure":
            sys.exit(2)
        elif result["status"] in ("synced", "up_to_date", "dry_run"):
            if args.cleanup and result["status"] == "synced":
                print(
                    "\n[release-safety] Orphan reconciliation is a separate "
                    "frozen-artifact maintenance command; post-sync cleanup "
                    "will remove version directories and manifest rows only."
                )
                print(f"\nRunning post-sync cleanup (keeping last {args.cleanup_keep} versions)...")
                import importlib, sys as _sys
                from pathlib import Path as _Path
                # Ensure cleanup_old_versions is importable regardless of cwd
                _script_dir = str(_Path(__file__).parent)
                if _script_dir not in _sys.path:
                    _sys.path.insert(0, _script_dir)
                cleanup_mod = importlib.import_module("cleanup_old_versions")
                cleanup_mod.main(_build_cleanup_args(args.cleanup_keep))
            sys.exit(0)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        # JSONDecodeError is a ValueError subclass, so the order matters:
        # this branch must come BEFORE the generic ValueError handler.
        # Bubbles up when Supabase Storage returns a non-JSON response
        # (empty body, HTML error page, rate-limit page) and the SDK's
        # internal response.json() call fails. Discovery has bounded
        # retry-on-transient (see _list_with_retries) — reaching here
        # means the API was persistently broken across N+1 attempts,
        # not a single hiccup. Action: rerun the sync; if it persists,
        # check Supabase status / project quotas.
        print(f"API response error (non-JSON body from Supabase): {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        # Genuine config errors (missing SUPABASE_URL / SERVICE_ROLE_KEY
        # raised by get_supabase_client, malformed manifest fields, etc.)
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Sync failed: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
