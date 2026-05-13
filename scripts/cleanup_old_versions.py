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
# Gated orphan-blob cleanup (ADR-0001 P1.6 + P2.2 — gated + quarantined)
# ---------------------------------------------------------------------------


def cleanup_orphan_blobs_with_gates(
    client,
    current_version,
    *,
    flutter_repo_path,
    dist_dir,
    branch="main",
    bundle_mismatch_reason=None,
    expected_count=None,
    audit_log=None,
    lock_path=None,
    run_date=None,
):
    """Run release-safety gates THEN move orphaned detail blobs to quarantine.

    This is the production wire-in for ADR-0001's release-safety stack
    (P1.6) plus the P2.2 quarantine layer. Unlike the legacy
    ``cleanup_orphan_blobs`` (single-version protection + hard-delete,
    the path that caused the 2026-05-12 incident), this function:

      1. Lists all blobs in storage.
      2. Reads dist/detail_index.json to compute initial orphan candidates
         (storage hashes NOT in dist's index).
      3. Calls ``evaluate_cleanup_gates(...)`` in EXECUTE mode with those
         candidates + storage_total. The gate enforces:
           - lock acquisition (HR-12)
           - dist index validation (HR-11)
           - bundled∪dist protected-set computation (HR-1, HR-2)
           - bundle alignment with Flutter main HEAD (HR-13)
           - blast-radius (HR-4)
           - non-empty protected set (HR-2)
      4. If gates fail, prints failure_summary, returns (0, 0). NO action.
      5. If gates pass, MOVES (not deletes) only the candidates that
         survive the protected-set filter into shared/quarantine/{run_date}/.
         Quarantined blobs are recoverable for 30 days via
         ``release_safety.recover_blob(...)``; the sweeper hard-deletes
         them after the TTL.

    Per P2.2 sign-off: per-blob quarantine failures DO NOT abort the
    cleanup. The function continues across remaining eligible blobs and
    reports the failure count in the return tuple.

    Args:
        client: Supabase client.
        current_version: most-recent db_version (for legacy log compatibility).
        flutter_repo_path: REQUIRED. Path to the Flutter repo root.
        dist_dir: REQUIRED. Path to the freshly-built dist/ directory.
        branch: Flutter branch to read bundled manifest from. Default ``"main"``.
        bundle_mismatch_reason: optional override for the bundle-alignment gate.
        expected_count: optional override for the blast-radius gate.
        audit_log: optional explicit AuditLog. None creates a fresh one.
        lock_path: optional explicit lock file path.
        run_date: optional ISO YYYY-MM-DD for the quarantine date directory.
            Defaults to today UTC. All blobs quarantined by THIS call land
            under the same date, so the sweeper can drain them as a unit
            after TTL. Tests pass an explicit value for determinism.

    Returns:
        ``(quarantined_count, failed_count)``. Both 0 if gates rejected.

    Never raises in normal use — gate failures and per-blob quarantine
    errors are caught and reported. Unexpected exceptions from the gate
    machinery propagate; callers should wrap in try/except + return
    (0, 0) per ADR-0001 P1.6 fail-closed requirement.
    """
    # Imported here so the module remains importable even when
    # release_safety package isn't on sys.path (legacy direct invocation).
    from release_safety import (
        evaluate_cleanup_gates,
        GateMode,
        GateOverrides,
        validate_detail_index,
        quarantine_blob,
        DEFAULT_QUARANTINE_TTL_DAYS,
    )
    from datetime import datetime as _datetime, timezone as _timezone
    from pathlib import Path as _Path

    # One run_date per cleanup run — every quarantined blob lands under
    # the same date directory so the sweeper can drain them as a unit.
    if run_date is None:
        run_date = _datetime.now(_timezone.utc).strftime("%Y-%m-%d")

    print("\n=== Gated orphan-blob cleanup (ADR-0001 P1.6 + P2.2) ===")
    print(f"  flutter_repo:     {flutter_repo_path}")
    print(f"  dist_dir:         {dist_dir}")
    print(f"  branch:           {branch}")
    print(f"  run_date:         {run_date}")

    # Step 1: list all blobs in storage (we need both the candidate set
    # and the total for blast-radius). Cheaper to do this once here than
    # twice (here + inside the gate).
    print("\nListing all blobs in Supabase storage...")
    shards = list_all_blob_shard_dirs(client)
    storage_paths = []
    for shard in shards:
        storage_paths.extend(list_blobs_in_shard(client, shard))
    storage_hashes = set()
    for path in storage_paths:
        leaf = path.rsplit("/", 1)[-1]
        if leaf.endswith(".json"):
            storage_hashes.add(leaf[:-5])
    storage_total = len(storage_hashes)
    print(f"  {storage_total} unique blobs in storage")

    # Step 2: compute initial orphan candidates (storage − dist.index).
    # The gate will further filter against the bundled∪dist protected set.
    try:
        dist_index = validate_detail_index(_Path(dist_dir) / "detail_index.json")
    except Exception as exc:
        print(f"\n[release-safety] Could not validate dist detail_index: {exc}")
        print("  Refusing destructive cleanup. No blobs quarantined.")
        return 0, 0
    candidate_hashes = storage_hashes - dist_index.blob_hashes
    print(f"  {len(candidate_hashes)} candidates pre-gate (storage \\ dist.index)")

    # Step 3: run the gate in EXECUTE mode.
    overrides = GateOverrides(
        bundle_mismatch_reason=bundle_mismatch_reason,
        expected_count=expected_count,
    )
    result = evaluate_cleanup_gates(
        flutter_repo_path=flutter_repo_path,
        dist_dir=dist_dir,
        candidate_blobs=candidate_hashes,
        storage_total=storage_total,
        mode=GateMode.EXECUTE,
        branch=branch,
        overrides=overrides,
        audit_log=audit_log,
        lock_path=lock_path,
    )

    if not result.passed:
        print("\n" + result.failure_summary())
        print("\n[release-safety] Orphan cleanup REJECTED — no blobs quarantined.")
        return 0, 0

    # Step 4: quarantine only candidates surviving the protected-set filter.
    # P2.2 — the destructive step is now a MOVE-to-quarantine, not a
    # hard delete. Recoverable for DEFAULT_QUARANTINE_TTL_DAYS (30) days
    # via release_safety.recover_blob(client, blob_hash).
    actual_orphans = result.deletion_candidates
    print(
        f"\n[release-safety] Gates passed. "
        f"Quarantining {len(actual_orphans)} blob(s) "
        f"to shared/quarantine/{run_date}/ "
        f"(of {len(candidate_hashes)} pre-gate candidates; "
        f"{len(candidate_hashes) - len(actual_orphans)} protected by bundled∪dist). "
        f"Recoverable for {DEFAULT_QUARANTINE_TTL_DAYS} days."
    )

    quarantined = 0
    failed = 0
    failed_paths: list = []
    for blob_hash in sorted(actual_orphans):
        shard = blob_hash[:2]
        path = f"shared/details/sha256/{shard}/{blob_hash}.json"
        ok, err = quarantine_blob(client, path, run_date=run_date)
        if ok:
            quarantined += 1
        else:
            # P2.2 sign-off: per-blob failures DO NOT abort the cleanup.
            # Count + report; continue across remaining candidates.
            print(f"  [ERROR] Failed to quarantine orphan {path}: {err}")
            failed += 1
            failed_paths.append(path)

    print(
        f"\n[release-safety] Quarantine complete: "
        f"{quarantined} moved, {failed} failed. "
        f"Recover via: from release_safety import recover_blob; "
        f"recover_blob(client, '<hash>')"
    )

    if audit_log is not None:
        audit_log.event(
            "quarantine_completed",
            quarantined_count=quarantined,
            failed_count=failed,
            run_date=run_date,
            failed_paths=failed_paths,
        )

    return quarantined, failed


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
    # ADR-0001 P1.6 — release-safety gate inputs.
    # These are REQUIRED when --cleanup-orphan-blobs --execute is given.
    # They are unused in dry-run mode (read-only ops do not need gates).
    parser.add_argument(
        "--flutter-repo",
        type=str,
        default=None,
        dest="flutter_repo",
        help="Path to the Flutter repo root (required for --cleanup-orphan-blobs --execute).",
    )
    parser.add_argument(
        "--dist-dir",
        type=str,
        default=None,
        dest="dist_dir",
        help="Path to dist/ directory (required for --cleanup-orphan-blobs --execute).",
    )
    parser.add_argument(
        "--branch",
        type=str,
        default="main",
        help="Flutter branch whose committed manifest is the trust anchor (default: main).",
    )
    parser.add_argument(
        "--override-bundle-mismatch",
        type=str,
        default=None,
        dest="override_bundle_mismatch",
        help=(
            "Override the bundle-alignment gate with a written reason. "
            "Captured verbatim in the audit log."
        ),
    )
    parser.add_argument(
        "--expected-count",
        type=int,
        default=None,
        dest="expected_count",
        help=(
            "Override the blast-radius gate by stating the exact expected "
            "deletion count. Must equal the actual count or the gate fails."
        ),
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
    total_orphans_quarantined = 0
    total_orphans_failed = 0
    if args.cleanup_orphan_blobs:
        current_row = next((r for r in rows if r.get("is_current")), rows[0] if rows else None)
        if current_row:
            if dry_run:
                # Dry-run path is read-only; no destructive gates required
                # per ADR-0001 HR-12 (read-only ops bypass the lock + gates).
                # Single-version protection is fine here because nothing is
                # actually deleted — the output just shows what WOULD be.
                total_orphans_quarantined, total_orphans_failed = cleanup_orphan_blobs(
                    client, current_row["db_version"], dry_run,
                )
            else:
                # EXECUTE path — gated per ADR-0001 P1.6.
                # Required inputs MUST be present; fail closed if missing.
                if not args.flutter_repo or not args.dist_dir:
                    print(
                        "\n[ERROR] --cleanup-orphan-blobs --execute requires "
                        "--flutter-repo AND --dist-dir."
                    )
                    print(
                        "        These are needed to compute the bundled∪dist "
                        "protected blob set per ADR-0001 HR-2."
                    )
                    print(
                        "        Refusing destructive cleanup. Run with "
                        "--flutter-repo PATH --dist-dir PATH or omit --execute."
                    )
                    sys.exit(2)

                # Wrap in try/except so any unexpected gate-machinery error
                # fails closed (no deletions) rather than crashing the
                # cleanup mid-run. Per ADR-0001 P1.6 sign-off.
                try:
                    total_orphans_quarantined, total_orphans_failed = (
                        cleanup_orphan_blobs_with_gates(
                            client,
                            current_row["db_version"],
                            flutter_repo_path=args.flutter_repo,
                            dist_dir=args.dist_dir,
                            branch=args.branch,
                            bundle_mismatch_reason=args.override_bundle_mismatch,
                            expected_count=args.expected_count,
                        )
                    )
                except Exception as exc:
                    print(
                        f"\n[release-safety] Unexpected error during gated "
                        f"orphan cleanup: {type(exc).__name__}: {exc}"
                    )
                    print(
                        "  Refusing destructive cleanup. No blobs deleted. "
                        "Investigate the error before re-running."
                    )
                    total_orphans_quarantined, total_orphans_failed = 0, 0
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
        if dry_run:
            # Dry-run uses the legacy cleanup_orphan_blobs (single-version
            # protection) for backwards compat; nothing is touched, the
            # count reflects what WOULD have been deleted.
            print(f"  Orphan blobs would delete:      {total_orphans_quarantined}")
        else:
            # Execute path (P2.2): orphans were MOVED to quarantine, not
            # deleted. Recoverable for 30 days via release_safety.recover_blob.
            print(f"  Orphan blobs quarantined:       {total_orphans_quarantined}")
        if total_orphans_failed:
            verb = "delete" if dry_run else "quarantine"
            print(f"  Orphan blob {verb} failures:  {total_orphans_failed}")
    print()
    if dry_run:
        print("Dry-run complete. Re-run with --execute to apply deletions.")
    else:
        # Categorize failures by data-integrity impact:
        #
        #   • storage version deletes  → strict. Intentional version retirements
        #                                are user-initiated; if they fail, the
        #                                user wants to know.
        #   • manifest DB row deletes  → strict. Data integrity gate; a row
        #                                pointing at deleted storage is a
        #                                real inconsistency.
        #   • orphan blob deletes      → ALWAYS non-blocking. This is pure
        #                                housekeeping — the blobs are unreferenced
        #                                garbage. Whether we delete them today
        #                                or next run does not affect any user.
        #                                Failures here are most often transient
        #                                (HTTP/2 stream limit at ~20K calls per
        #                                connection, supabase-py response parsing
        #                                issues on success responses, etc.) and
        #                                always self-heal on the next cleanup.
        #                                Blocking the release on housekeeping
        #                                failures is the wrong call.
        if total_orphans_failed > 0:
            orphan_total = total_orphans_quarantined + total_orphans_failed
            print(
                f"  Note: {total_orphans_failed}/{orphan_total} orphan-blob "
                f"quarantine moves failed — typically transient HTTP/2 stream-limit "
                f"or response-parse issues. Treating as non-blocking; the "
                f"stragglers retry on the next cleanup run (idempotent)."
            )

        blocking_failures = total_failed + total_db_failed
        if blocking_failures == 0:
            print("Cleanup complete.")
        else:
            print("Cleanup finished with errors (see above).")
            sys.exit(1)


if __name__ == "__main__":
    main()
