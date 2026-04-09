#!/usr/bin/env python3
"""Clean up old PharmaGuide versions from Supabase Storage.

Keeps the last N versions (default 2) and deletes older version directories.
Dry-run by default — pass --execute to actually delete.

Usage:
    python scripts/cleanup_old_versions.py              # dry-run, keep 2
    python scripts/cleanup_old_versions.py --execute     # actually delete
    python scripts/cleanup_old_versions.py --keep 3      # keep 3 versions
    python scripts/cleanup_old_versions.py --execute --cleanup-db  # also prune manifest rows
"""

import argparse
import sys
import os

# Ensure scripts/ is on the path for sibling imports (supabase_client, env_loader)
sys.path.insert(0, os.path.dirname(__file__))
import env_loader  # noqa: F401

from supabase_client import get_supabase_client  # noqa: E402

BUCKET = "pharmaguide"


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def fetch_all_versions(client):
    """Return all export_manifest rows ordered by created_at DESC.

    Each row is a dict with at least: db_version, created_at, is_current.
    """
    response = (
        client.table("export_manifest")
        .select("db_version, created_at, is_current")
        .order("created_at", desc=True)
        .execute()
    )
    return response.data or []


def partition_versions(rows, keep):
    """Split manifest rows into (keep_rows, old_rows).

    The first `keep` rows (newest) are retained; the rest are candidates for deletion.
    """
    keep_rows = rows[:keep]
    old_rows = rows[keep:]
    return keep_rows, old_rows


# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------

def list_version_directory(client, db_version):
    """List all objects inside pharmaguide/v{db_version}/.

    Returns a list of full storage paths (str).
    """
    prefix = f"pharmaguide/v{db_version}"
    try:
        items = client.storage.from_(BUCKET).list(
            path=prefix,
            options={"limit": 1000, "offset": 0},
        )
    except Exception as exc:
        print(f"  [WARN] Could not list storage path {prefix}: {exc}")
        return []

    if not items:
        return []

    paths = []
    for item in items:
        name = item.get("name")
        if name:
            paths.append(f"{prefix}/{name}")
    return paths


def delete_storage_path(client, path):
    """Delete a single object from storage.  Returns (success, error_message)."""
    try:
        client.storage.from_(BUCKET).remove([path])
        return True, None
    except Exception as exc:
        return False, str(exc)


def delete_version_directory(client, db_version, dry_run):
    """Delete all objects under pharmaguide/v{db_version}/.

    Returns (deleted_count, failed_count).
    """
    paths = list_version_directory(client, db_version)
    prefix = f"pharmaguide/v{db_version}"

    if not paths:
        print(f"  No objects found under {prefix}/ — skipping.")
        return 0, 0

    deleted = 0
    failed = 0
    for path in paths:
        if dry_run:
            print(f"  [DRY-RUN] Would delete: {path}")
        else:
            ok, err = delete_storage_path(client, path)
            if ok:
                print(f"  Deleted: {path}")
                deleted += 1
            else:
                print(f"  [ERROR] Failed to delete {path}: {err}")
                failed += 1

    if dry_run:
        deleted = len(paths)  # report as "would delete" count

    return deleted, failed


# ---------------------------------------------------------------------------
# Database cleanup helpers
# ---------------------------------------------------------------------------

def delete_manifest_row(client, db_version, dry_run):
    """Delete the export_manifest row for a given db_version.

    Returns (success, error_message).
    """
    if dry_run:
        print(f"  [DRY-RUN] Would delete manifest row: db_version={db_version}")
        return True, None
    try:
        client.table("export_manifest").delete().eq("db_version", db_version).execute()
        print(f"  Deleted manifest row: db_version={db_version}")
        return True, None
    except Exception as exc:
        print(f"  [ERROR] Failed to delete manifest row db_version={db_version}: {exc}")
        return False, str(exc)


# ---------------------------------------------------------------------------
# Orphan blob detection
# ---------------------------------------------------------------------------

BLOB_STORAGE_PREFIX = "shared/details/sha256"


def fetch_current_detail_index(client, current_version):
    """Download the current detail_index.json and return the set of referenced blob paths."""
    import json
    remote_path = f"v{current_version}/detail_index.json"
    try:
        data = client.storage.from_(BUCKET).download(remote_path)
        index = json.loads(data)
        return {entry["storage_path"] for entry in index.values()}
    except Exception as exc:
        print(f"  [ERROR] Could not download detail_index.json for v{current_version}: {exc}")
        print(f"  Orphan blob cleanup will be SKIPPED — cannot determine which blobs are active.")
        return None


def list_all_blob_shard_dirs(client):
    """List shard directories under shared/details/sha256/."""
    try:
        items = client.storage.from_(BUCKET).list(
            path=BLOB_STORAGE_PREFIX,
            options={"limit": 1000, "offset": 0},
        )
        return [item["name"] for item in (items or []) if item.get("name")]
    except Exception as exc:
        print(f"  [WARN] Could not list blob shard directories: {exc}")
        return []


def list_blobs_in_shard(client, shard):
    """List all blob paths in a shard directory."""
    prefix = f"{BLOB_STORAGE_PREFIX}/{shard}"
    paths = []
    offset = 0
    while True:
        try:
            items = client.storage.from_(BUCKET).list(
                path=prefix,
                options={"limit": 1000, "offset": offset},
            )
        except Exception as exc:
            print(f"  [WARN] Blob listing failed at offset {offset} in shard {shard}: {exc}")
            print(f"  Returning {len(paths)} blobs found so far (listing may be incomplete).")
            break
        if not items:
            break
        for item in items:
            name = item.get("name")
            if name:
                paths.append(f"{prefix}/{name}")
        if len(items) < 1000:
            break
        offset += 1000
    return paths


def detect_orphan_blobs(client, referenced_paths):
    """Find all blobs in storage not referenced by the current detail_index."""
    print("  Scanning shard directories...")
    shards = list_all_blob_shard_dirs(client)
    if not shards:
        print("  No shard directories found.")
        return []

    all_remote = []
    for shard in shards:
        all_remote.extend(list_blobs_in_shard(client, shard))

    orphans = [p for p in all_remote if p not in referenced_paths]
    print(f"  Total blobs in storage: {len(all_remote)}")
    print(f"  Referenced by current index: {len(referenced_paths)}")
    print(f"  Orphaned blobs: {len(orphans)}")
    return orphans


def cleanup_orphan_blobs(client, current_version, dry_run):
    """Detect and optionally delete orphaned blobs."""
    print(f"\nFetching current detail_index.json (v{current_version})...")
    referenced = fetch_current_detail_index(client, current_version)
    if referenced is None:
        print("  Cannot determine referenced blobs — skipping orphan cleanup.")
        return 0, 0

    orphans = detect_orphan_blobs(client, referenced)
    if not orphans:
        print("  No orphaned blobs found.")
        return 0, 0

    deleted = 0
    failed = 0
    for path in orphans:
        if dry_run:
            print(f"  [DRY-RUN] Would delete orphan: {path}")
        else:
            ok, err = delete_storage_path(client, path)
            if ok:
                deleted += 1
            else:
                print(f"  [ERROR] Failed to delete orphan {path}: {err}")
                failed += 1

    if dry_run:
        deleted = len(orphans)

    return deleted, failed


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "Clean up old PharmaGuide versions from Supabase Storage. "
            "Dry-run by default."
        )
    )
    parser.add_argument(
        "--keep",
        type=int,
        default=2,
        metavar="N",
        help="Number of most-recent versions to keep (default: 2).",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        default=False,
        help="Actually delete files. Without this flag the script is a dry-run.",
    )
    parser.add_argument(
        "--cleanup-db",
        action="store_true",
        default=False,
        dest="cleanup_db",
        help="Also delete old rows from the export_manifest table (default: false).",
    )
    parser.add_argument(
        "--cleanup-orphan-blobs",
        action="store_true",
        default=False,
        dest="cleanup_orphan_blobs",
        help="Detect and delete orphaned detail blobs not referenced by the current detail_index (default: false).",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    dry_run = not args.execute

    print("=" * 60)
    print("PharmaGuide — Storage Version Cleanup")
    print("=" * 60)
    if dry_run:
        print("MODE: DRY-RUN  (pass --execute to actually delete)")
    else:
        print("MODE: EXECUTE  (deleting for real)")
    print(f"Keep last {args.keep} version(s)")
    if args.cleanup_db:
        print("Manifest DB rows will also be cleaned up")
    print()

    # Connect
    try:
        client = get_supabase_client()
    except ValueError as exc:
        print(f"[ERROR] Cannot connect to Supabase: {exc}")
        sys.exit(1)

    # Fetch version list
    print("Fetching version list from export_manifest...")
    rows = fetch_all_versions(client)

    if not rows:
        print("No versions found in export_manifest. Nothing to clean up.")
        sys.exit(0)

    print(f"Found {len(rows)} version(s) in manifest:")
    for i, row in enumerate(rows):
        marker = "(current)" if row.get("is_current") else ""
        keep_marker = "[KEEP]" if i < args.keep else "[DELETE]"
        print(f"  {keep_marker}  v{row['db_version']}  created_at={row['created_at']}  {marker}")
    print()

    keep_rows, old_rows = partition_versions(rows, args.keep)

    if not old_rows:
        print(f"Nothing to delete — only {len(rows)} version(s) exist, keep threshold is {args.keep}.")
        sys.exit(0)

    print(f"Versions to clean up: {len(old_rows)}")
    print()

    # Safety: never delete a version marked is_current
    safe_old_rows = []
    for row in old_rows:
        if row.get("is_current"):
            print(f"  [SKIP] v{row['db_version']} is marked is_current=true — will not delete.")
        else:
            safe_old_rows.append(row)

    if not safe_old_rows:
        print("All candidate versions are marked is_current. Nothing deleted.")
        sys.exit(0)

    # Delete storage objects
    total_deleted = 0
    total_failed = 0
    total_db_deleted = 0
    total_db_failed = 0

    for row in safe_old_rows:
        db_version = row["db_version"]
        print(f"--- Cleaning up v{db_version} ---")

        deleted, failed = delete_version_directory(client, db_version, dry_run)
        total_deleted += deleted
        total_failed += failed

        if args.cleanup_db:
            ok, _ = delete_manifest_row(client, db_version, dry_run)
            if ok:
                total_db_deleted += 1
            else:
                total_db_failed += 1

        print()

    # Orphan blob cleanup
    total_orphans_deleted = 0
    total_orphans_failed = 0
    if args.cleanup_orphan_blobs:
        current_row = next((r for r in rows if r.get("is_current")), rows[0] if rows else None)
        if current_row:
            total_orphans_deleted, total_orphans_failed = cleanup_orphan_blobs(
                client, current_row["db_version"], dry_run,
            )
        else:
            print("\n  [WARN] No current version found — skipping orphan blob cleanup.")

    # Summary
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    action = "Would delete" if dry_run else "Deleted"
    print(f"  Storage objects {action.lower()}: {total_deleted}")
    if total_failed:
        print(f"  Storage delete failures:        {total_failed}")
    if args.cleanup_db:
        print(f"  Manifest rows {action.lower()}:   {total_db_deleted}")
        if total_db_failed:
            print(f"  Manifest row failures:          {total_db_failed}")
    if args.cleanup_orphan_blobs:
        print(f"  Orphan blobs {action.lower()}:    {total_orphans_deleted}")
        if total_orphans_failed:
            print(f"  Orphan blob failures:           {total_orphans_failed}")
    print()
    if dry_run:
        print("Dry-run complete. Re-run with --execute to apply deletions.")
    else:
        all_failures = total_failed + total_db_failed + total_orphans_failed
        if all_failures == 0:
            print("Cleanup complete.")
        else:
            print("Cleanup finished with errors (see above).")
            sys.exit(1)


if __name__ == "__main__":
    main()
