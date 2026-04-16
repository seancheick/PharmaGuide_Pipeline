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
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

DEFAULT_MAX_WORKERS = 8
DEFAULT_DISCOVERY_WORKERS = 8
DEFAULT_UPLOAD_RETRIES = 3
DEFAULT_RETRY_BASE_DELAY = 1.0
DEFAULT_PROGRESS_EVERY = 500

# Ensure scripts/ is on the path for sibling imports (supabase_client)
sys.path.insert(0, os.path.dirname(__file__))
import env_loader  # noqa: F401

DETAIL_BLOB_STORAGE_PREFIX = "shared/details/sha256"


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


def collect_detail_blobs(build_dir):
    """Return sorted list of detail blob file paths."""
    detail_dir = os.path.join(build_dir, "detail_blobs")
    if not os.path.isdir(detail_dir):
        return []
    blobs = sorted(glob.glob(os.path.join(detail_dir, "*.json")))
    return blobs


def remote_blob_storage_path(blob_sha256):
    shard = blob_sha256[:2]
    return f"{DETAIL_BLOB_STORAGE_PREFIX}/{shard}/{blob_sha256}.json"


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


def _discover_existing_remote_paths_for_directory(client, bucket, directory, expected_paths, list_fn, page_size):
    existing = set()
    offset = 0
    while True:
        page = list_fn(client, bucket, directory, limit=page_size, offset=offset)
        if not page:
            break
        for item in page:
            name = item.get("name")
            if not name:
                continue
            remote_path = f"{directory}/{name}"
            if remote_path in expected_paths:
                existing.add(remote_path)
        if len(page) < page_size:
            break
        offset += page_size
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
        return existing

    client_getter = make_thread_local_client_factory(client_factory) if client_factory else (lambda: client)
    existing = set()
    with ThreadPoolExecutor(max_workers=min(max_workers, len(grouped))) as executor:
        futures = [
            executor.submit(
                _discover_existing_remote_paths_for_directory_with_factory,
                client_getter,
                bucket,
                directory,
                expected_paths,
                list_fn,
                page_size,
            )
            for directory, expected_paths in grouped.items()
        ]
        for future in as_completed(futures):
            existing.update(future.result())
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
            futures = []
            for upload in pending_uploads:
                futures.append(
                    executor.submit(
                        _upload_blob_task_with_factory,
                        client_getter,
                        upload_fn,
                        bucket,
                        upload["local_path"],
                        upload["remote_path"],
                        retries,
                        base_delay,
                        upload["blob_sha256"],
                    )
                )
            for future in as_completed(futures):
                completed += 1
                error = future.result()
                if error:
                    errors.append(error)
                if (completed + skipped) % progress_every == 0 or (completed + skipped) == total:
                    elapsed = time.time() - start
                    print(f"  {completed + skipped}/{total} ({elapsed:.1f}s)")

    return time.time() - start, errors, len(pending_uploads) - len(errors), skipped


def validate_build_output(build_dir, manifest):
    """Validate local build output before any upload begins."""
    build_errors = manifest.get("errors") or []
    if build_errors:
        raise ValueError(
            f"Build output contains {len(build_errors)} export errors; refusing to sync partial artifact"
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


def _upload_image_task(client, upload_fn, bucket, local_path, remote_path, retries, base_delay):
    """Upload a single .webp image to Supabase Storage."""
    try:
        upload_with_retries(
            lambda: upload_fn(client, bucket, remote_path, local_path, content_type="image/webp"),
            retries=retries,
            base_delay=base_delay,
        )
        return None
    except Exception as exc:
        return {"remote_path": remote_path, "error": str(exc)}


def _upload_image_task_with_factory(client_getter, upload_fn, bucket, local_path, remote_path, retries, base_delay):
    return _upload_image_task(
        client_getter(), upload_fn, bucket, local_path, remote_path, retries, base_delay,
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
):
    """Upload product_images/*.webp to Supabase Storage bucket.

    Skips files that already exist remotely with matching size.
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
        page = list_fn(client, PRODUCT_IMAGE_BUCKET, "", limit=10000, offset=0)
        if page:
            for item in page:
                name = item.get("name", "")
                metadata = item.get("metadata", {}) or {}
                size = metadata.get("size") or metadata.get("contentLength") or 0
                if name:
                    existing_sizes[name] = int(size) if size else 0
    except Exception:
        pass  # Bucket may not exist yet — upload all

    # Build upload list
    uploads = []
    skipped = 0
    for dsld_id, entry in sorted(index.items()):
        filename = entry["filename"]
        local_path = os.path.join(image_dir, filename)
        remote_path = filename  # flat: {dsld_id}.webp
        local_size = entry.get("size_bytes", 0)

        if not os.path.exists(local_path):
            continue

        if filename in existing_sizes and existing_sizes[filename] > 0 and abs(existing_sizes[filename] - local_size) < 1024:
            skipped += 1
            continue

        uploads.append({"local_path": local_path, "remote_path": remote_path})

    errors = []
    uploaded = 0
    start = time.time()

    if not uploads:
        print(f"  All {skipped} images already uploaded — nothing to do")
        return {"uploaded": 0, "skipped": skipped, "failed": 0}

    client_getter = make_thread_local_client_factory(client_factory) if client_factory else (lambda: client)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(
                _upload_image_task_with_factory,
                client_getter, upload_fn, PRODUCT_IMAGE_BUCKET,
                u["local_path"], u["remote_path"], retries, base_delay,
            )
            for u in uploads
        ]
        for future in as_completed(futures):
            error = future.result()
            if error:
                errors.append(error)
            else:
                uploaded += 1
            done = uploaded + len(errors)
            if done % 500 == 0 or done == len(uploads):
                elapsed = time.time() - start
                print(f"  Images: {done + skipped}/{total} ({elapsed:.1f}s)")

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

def sync(
    build_dir,
    dry_run=False,
    force=False,
    max_workers=DEFAULT_MAX_WORKERS,
    retry_count=DEFAULT_UPLOAD_RETRIES,
    retry_base_delay=DEFAULT_RETRY_BASE_DELAY,
):
    """Main sync workflow.

    1. Load local manifest
    2. Compare to remote manifest
    3. Upload .db file to Storage
    4. Upload detail blobs to Storage
    5. Insert new manifest row
    """
    from supabase_client import (
        get_supabase_client,
        fetch_current_manifest,
        insert_manifest,
        list_storage_paths,
        upload_file,
    )

    print(f"Loading manifest from {build_dir}...")
    local = load_local_manifest(build_dir)
    version = local["db_version"]
    product_count = local["product_count"]
    checksum = local["checksum"]
    build_stats = validate_build_output(build_dir, local)

    print(f"  Version:  {version}")
    print(f"  Products: {product_count}")
    print(f"  Checksum: {checksum[:20]}...")

    if dry_run:
        print(f"\n[DRY RUN] Would upload:")
        print(f"  - pharmaguide_core.db ({build_stats['db_size_mb']:.1f} MB)")
        print(f"  - detail_index.json")
        print(f"  - {build_stats['unique_blob_count']} unique detail blobs ({build_stats['blob_count']} product mappings)")
        img_index, _ = load_product_image_index(build_dir)
        if img_index:
            print(f"  - {len(img_index)} product images to {PRODUCT_IMAGE_BUCKET}")
        print(f"  - New manifest row (version {version})")
        return {"status": "dry_run", "version": version, "blob_count": build_stats["blob_count"]}

    client = get_supabase_client()
    print("Checking Supabase for current version...")
    remote = fetch_current_manifest(client)

    if remote:
        print(f"  Remote version: {remote['db_version']}")
    else:
        print("  No remote version found (first push)")

    if not needs_update(local, remote, force=force):
        print("Already up to date. Nothing to do.")
        return {"status": "up_to_date", "version": version}

    # Upload SQLite DB
    db_path = build_stats["db_path"]

    bucket = "pharmaguide"
    remote_db_path = f"v{version}/pharmaguide_core.db"
    print(f"\nUploading {remote_db_path}...")
    start = time.time()
    upload_file(client, bucket, remote_db_path, db_path)
    db_time = time.time() - start
    db_size_mb = build_stats["db_size_mb"]
    print(f"  Done ({db_size_mb:.1f} MB in {db_time:.1f}s)")

    detail_index_path = build_stats["detail_index_path"]
    remote_detail_index_path = f"v{version}/detail_index.json"
    print(f"\nUploading {remote_detail_index_path}...")
    start = time.time()
    upload_file(client, bucket, remote_detail_index_path, detail_index_path, content_type="application/json")
    detail_index_time = time.time() - start
    print(f"  Done ({detail_index_time:.1f}s)")

    # Upload unique detail blobs with bounded concurrency, retry logic, and remote dedupe.
    uploads = build_stats["unique_blob_uploads"]
    blob_count = build_stats["blob_count"]
    unique_blob_count = build_stats["unique_blob_count"]
    print("\nDiscovering existing remote hashed blobs...")
    start = time.time()
    existing_remote_paths = discover_existing_remote_blob_paths(
        client,
        bucket,
        uploads,
        list_storage_paths,
        max_workers=min(max_workers, DEFAULT_DISCOVERY_WORKERS),
        client_factory=get_supabase_client,
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

    # Upload product images (non-blocking — image failures don't abort sync)
    print("\nUploading product images...")
    image_result = upload_product_images(
        client=client,
        build_dir=build_dir,
        upload_fn=upload_file,
        list_fn=list_storage_paths,
        max_workers=max_workers,
        retries=retry_count,
        base_delay=retry_base_delay,
        client_factory=get_supabase_client,
    )

    # Abort manifest rotation if any blobs failed — prevents clients from
    # seeing the new version and getting 404s on missing detail blobs.
    if errors:
        failure_report = write_failure_report(build_dir, version, errors)
        print(f"\nAborting manifest rotation: {len(errors)} unique blob uploads failed.")
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
            "time_seconds": round(db_time + detail_index_time + discover_time + blob_time, 1),
        }

    # Insert manifest (only if all blobs uploaded successfully)
    print(f"\nUpdating manifest (version {version})...")
    insert_manifest(client, local)
    print("  Done")

    # Summary
    total_time = db_time + detail_index_time + discover_time + blob_time
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
    parser.add_argument("build_dir", help="Build output directory containing manifest, DB, and detail_blobs")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be uploaded without uploading")
    parser.add_argument("--force", action="store_true", help="Upload and rotate manifest even if version/checksum match")
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
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

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
        )
        if result["status"] == "partial_failure":
            sys.exit(2)
        elif result["status"] in ("synced", "up_to_date", "dry_run"):
            if args.cleanup and result["status"] == "synced":
                print(f"\nRunning post-sync cleanup (keeping last {args.cleanup_keep} versions)...")
                import importlib, sys as _sys
                from pathlib import Path as _Path
                # Ensure cleanup_old_versions is importable regardless of cwd
                _script_dir = str(_Path(__file__).parent)
                if _script_dir not in _sys.path:
                    _sys.path.insert(0, _script_dir)
                cleanup_mod = importlib.import_module("cleanup_old_versions")
                cleanup_mod.main(["--keep", str(args.cleanup_keep), "--execute", "--cleanup-orphan-blobs"])
            sys.exit(0)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"Configuration error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Sync failed: {e}")
        sys.exit(2)


if __name__ == "__main__":
    main()
