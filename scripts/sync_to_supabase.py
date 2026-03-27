#!/usr/bin/env python3
"""Sync pipeline build output to Supabase Storage + PostgreSQL manifest.

Usage:
    python scripts/sync_to_supabase.py <build_output_dir>

The build_output_dir should contain:
    - export_manifest.json
    - pharmaguide_core.db
    - detail_blobs/{dsld_id}.json (one per product)

Environment variables (from .env):
    - SUPABASE_URL
    - SUPABASE_SERVICE_ROLE_KEY
"""

import json
import os
import sys
import time
import glob

# Ensure scripts/ is on the path for sibling imports (supabase_client)
sys.path.insert(0, os.path.dirname(__file__))
import env_loader  # noqa: F401


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


def needs_update(local_manifest, remote_manifest):
    """Determine if Supabase needs updating.

    Returns True if:
    - remote_manifest is None (first push ever)
    - db_version differs
    - checksum differs (same version but different content)
    """
    if remote_manifest is None:
        return True
    if local_manifest["db_version"] != remote_manifest["db_version"]:
        return True
    if local_manifest["checksum"] != remote_manifest["checksum"]:
        return True
    return False


def collect_detail_blobs(build_dir):
    """Return sorted list of detail blob file paths."""
    detail_dir = os.path.join(build_dir, "detail_blobs")
    if not os.path.isdir(detail_dir):
        return []
    blobs = sorted(glob.glob(os.path.join(detail_dir, "*.json")))
    return blobs


# ---------------------------------------------------------------------------
# Supabase operations (require real client)
# ---------------------------------------------------------------------------

def sync(build_dir, dry_run=False):
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
        upload_file,
    )

    print(f"Loading manifest from {build_dir}...")
    local = load_local_manifest(build_dir)
    version = local["db_version"]
    product_count = local["product_count"]
    checksum = local["checksum"]

    print(f"  Version:  {version}")
    print(f"  Products: {product_count}")
    print(f"  Checksum: {checksum[:20]}...")

    if dry_run:
        blobs = collect_detail_blobs(build_dir)
        db_path = os.path.join(build_dir, "pharmaguide_core.db")
        db_size = os.path.getsize(db_path) / (1024 * 1024) if os.path.exists(db_path) else 0
        print(f"\n[DRY RUN] Would upload:")
        print(f"  - pharmaguide_core.db ({db_size:.1f} MB)")
        print(f"  - {len(blobs)} detail blobs")
        print(f"  - New manifest row (version {version})")
        return {"status": "dry_run", "version": version, "blob_count": len(blobs)}

    client = get_supabase_client()
    print("Checking Supabase for current version...")
    remote = fetch_current_manifest(client)

    if remote:
        print(f"  Remote version: {remote['db_version']}")
    else:
        print("  No remote version found (first push)")

    if not needs_update(local, remote):
        print("Already up to date. Nothing to do.")
        return {"status": "up_to_date", "version": version}

    # Upload SQLite DB
    db_path = os.path.join(build_dir, "pharmaguide_core.db")
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"pharmaguide_core.db not found in {build_dir}")

    bucket = "pharmaguide"
    remote_db_path = f"v{version}/pharmaguide_core.db"
    print(f"\nUploading {remote_db_path}...")
    start = time.time()
    upload_file(client, bucket, remote_db_path, db_path)
    db_time = time.time() - start
    db_size_mb = os.path.getsize(db_path) / (1024 * 1024)
    print(f"  Done ({db_size_mb:.1f} MB in {db_time:.1f}s)")

    # Upload detail blobs
    # NOTE: Sequential uploads are fine for MVP (<10K products, ~15 min).
    # When product count exceeds ~10K, add concurrent.futures.ThreadPoolExecutor
    # with max_workers=10 to parallelize uploads (~10x speedup).
    blobs = collect_detail_blobs(build_dir)
    blob_count = len(blobs)
    print(f"\nUploading {blob_count} detail blobs...")
    start = time.time()
    errors = []
    for i, blob_path in enumerate(blobs, 1):
        dsld_id = os.path.splitext(os.path.basename(blob_path))[0]
        remote_blob_path = f"v{version}/details/{dsld_id}.json"
        try:
            upload_file(
                client, bucket, remote_blob_path, blob_path,
                content_type="application/json",
            )
        except Exception as e:
            errors.append({"dsld_id": dsld_id, "error": str(e)})
        if i % 500 == 0 or i == blob_count:
            elapsed = time.time() - start
            print(f"  {i}/{blob_count} ({elapsed:.1f}s)")

    blob_time = time.time() - start
    print(f"  Done ({blob_count} blobs in {blob_time:.1f}s, {len(errors)} errors)")

    # Abort manifest rotation if any blobs failed — prevents clients from
    # seeing the new version and getting 404s on missing detail blobs.
    if errors:
        print(f"\nAborting manifest rotation: {len(errors)} blob uploads failed.")
        print("Fix the errors and re-run. The DB file was uploaded (upsert safe).")
        return {
            "status": "partial_failure",
            "version": version,
            "product_count": int(product_count),
            "blob_count": blob_count,
            "error_count": len(errors),
            "time_seconds": round(db_time + blob_time, 1),
        }

    # Insert manifest (only if all blobs uploaded successfully)
    print(f"\nUpdating manifest (version {version})...")
    insert_manifest(client, local)
    print("  Done")

    # Summary
    total_time = db_time + blob_time
    print(f"\n{'=' * 50}")
    print(f"Sync complete: v{version}")
    print(f"  Products:    {product_count}")
    print(f"  DB size:     {db_size_mb:.1f} MB")
    print(f"  Blobs:       {blob_count}")
    print(f"  Errors:      {len(errors)}")
    print(f"  Total time:  {total_time:.1f}s")
    print(f"{'=' * 50}")

    if errors:
        print(f"\nFailed uploads ({len(errors)}):")
        for err in errors[:10]:
            print(f"  - {err['dsld_id']}: {err['error']}")
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

def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/sync_to_supabase.py <build_output_dir> [--dry-run]")
        print()
        print("Options:")
        print("  --dry-run    Show what would be uploaded without actually uploading")
        sys.exit(1)

    build_dir = sys.argv[1]
    dry_run = "--dry-run" in sys.argv

    if not os.path.isdir(build_dir):
        print(f"Error: {build_dir} is not a directory")
        sys.exit(1)

    try:
        result = sync(build_dir, dry_run=dry_run)
        if result["status"] == "partial_failure":
            sys.exit(2)
        elif result["status"] in ("synced", "up_to_date", "dry_run"):
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
