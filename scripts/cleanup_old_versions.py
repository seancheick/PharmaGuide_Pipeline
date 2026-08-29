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
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
import hashlib
import json
import sys
import os
import threading
import time
from pathlib import Path

# Ensure scripts/ is on the path for sibling imports (supabase_client, env_loader)
sys.path.insert(0, os.path.dirname(__file__))
import env_loader  # noqa: F401

from supabase_client import get_supabase_client  # noqa: E402
from release_safety import sweep_quarantine  # noqa: E402
from release_safety.quarantine import (  # noqa: E402
    DEFAULT_REMOVE_BATCH_SIZE,
    remove_storage_batch,
)

BUCKET = "pharmaguide"
CHECKPOINT_REVERIFY_UNAVAILABLE = (
    "verification unavailable for previously completed shard"
)

# Supabase storage list calls can hang in SSL reads at production scale.
# Keep page reads bounded so cleanup either progresses visibly or fails closed.
# Page timeout and list-retry budget now live in release_safety.blob_inventory
# (PG_STORAGE_LIST_PAGE_TIMEOUT_SECONDS / PG_STORAGE_LIST_MAX_RETRIES). They
# were redeclared here with a DIFFERENT default for the same env var, which is
# how two knobs that look like one drift apart.
SUPABASE_TABLE_MAX_RETRIES = int(
    os.environ.get("PG_SUPABASE_TABLE_MAX_RETRIES", "5")
)
QUARANTINE_MAX_WORKERS = int(
    os.environ.get("PG_QUARANTINE_MAX_WORKERS", "4")
)


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def fetch_all_versions(client):
    """Return all export_manifest rows ordered by created_at DESC.

    Each row is a dict with at least: db_version, created_at, is_current.
    """
    last_exc = None
    for attempt in range(SUPABASE_TABLE_MAX_RETRIES):
        try:
            response = (
                client.table("export_manifest")
                .select("db_version, created_at, is_current")
                .order("created_at", desc=True)
                .execute()
            )
            return response.data or []
        except Exception as exc:  # noqa: BLE001 — transient API failures.
            last_exc = exc
            if attempt == SUPABASE_TABLE_MAX_RETRIES - 1:
                break
            print(
                f"  [WARN] export_manifest fetch failed "
                f"({type(exc).__name__}: {exc}); retrying..."
            )
            time.sleep(min(0.5 * (2 ** attempt), 5.0))
    raise RuntimeError(
        f"Could not fetch export_manifest after "
        f"{SUPABASE_TABLE_MAX_RETRIES} attempts: {last_exc}"
    ) from last_exc


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
    """List all objects inside v{db_version}/ within the pharmaguide bucket.

    Returns a list of bucket-relative storage paths (str), e.g.
    ``v2026.05.13.162119/pharmaguide_core.db``.

    Bug-fix 2026-05-13: the prefix here was previously ``pharmaguide/v{ver}``
    which double-prefixed the bucket name (Supabase storage `.list(path=...)`
    is bucket-relative). The buggy prefix caused list() to return zero items
    silently, which meant the cleanup THOUGHT it had nothing to delete and
    deleted only the manifest row — leaving the v-dir orphaned in storage.
    This is exactly the failure mode test_p3_6a_registry_rollback_row_*
    was designed to catch downstream, but at the wrong layer.
    """
    prefix = f"v{db_version}"
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
    """Delete all objects under v{db_version}/ within the pharmaguide bucket.

    Returns (deleted_count, failed_count). See list_version_directory above
    for the path-shape contract (bucket-relative).
    """
    paths = list_version_directory(client, db_version)
    prefix = f"v{db_version}"

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


def _list_prefix_fingerprints(bucket_proxy, prefix, *, page_limit, max_attempts):
    """Return {leaf_name: (size, etag)} for every object under ``prefix``.

    Paginated, transient-retried. Raises after retries are exhausted — the
    caller decides whether that blocks a shard or the whole run.
    """
    from release_safety.blob_inventory import list_storage_page
    from release_safety.transient import retry_transient

    out = {}
    offset = 0
    while True:
        items = retry_transient(
            lambda offset=offset: list_storage_page(
                bucket_proxy, prefix, offset, limit=page_limit,
            ),
            max_attempts=max_attempts,
        )
        if not items:
            break
        for item in items:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            if not name:
                continue
            metadata = item.get("metadata") or {}
            size = metadata.get("size") if isinstance(metadata.get("size"), int) else None
            etag = metadata.get("eTag") if isinstance(metadata.get("eTag"), str) else None
            out[name] = (size, etag)
        if len(items) < page_limit:
            break
        offset += page_limit
    return out


def quarantine_orphan_blob_batch(
    client,
    blob_hashes,
    *,
    run_date,
    source_fingerprints,
    max_workers=None,
    client_factory=None,
    checkpoint_path=None,
    page_limit=None,
    max_attempts=None,
):
    """Move approved orphans to quarantine via a per-shard state machine.

    The previous engine interrogated every blob individually (2 existence
    listings + copy + visibility poll + delete ≈ 5 requests, 3+ of them the
    expensive server-side shard listings) — ~311k listing calls at 103k blobs,
    degrading as the quarantine prefix filled. This engine's listing count is
    a function of SHARD count (≤4 per shard), never of blob count.

    Per shard: classify from one active + one target listing against the
    FROZEN ``source_fingerprints`` an operator approved; copy what is missing
    (bounded parallel, one client per thread via ``client_factory``); verify
    every target fingerprint with one listing; batch-delete verified sources
    (``DEFAULT_REMOVE_BATCH_SIZE`` per call); prove with one final listing that
    candidates are absent and bystanders unchanged.

    Fail-closed semantics:
      - identity-model violations (fingerprint drift since approval, corrupted
        target, candidate missing everywhere, missing/unproven source
        fingerprint) block the WHOLE shard — nothing is deleted there;
      - operational failures (copy error, delete error) fail only the affected
        blobs; a delete failure leaves the recoverable duplicate;
      - ``moved`` counts only candidates whose target is fingerprint-verified
        AND whose source is proven absent by the final listing.

    Checkpoint: shard-level ``{count, digest}`` entries, recorded only for
    fully-clean shards, keyed to the exact candidate set (sha256 of the
    newline-joined sorted hashes — same construction as the dry-run report's
    ``candidate_digest``). A checkpoint for a different candidate set or an
    older format raises ``ValueError``. A fully successful run removes its
    checkpoint.
    """
    hashes = sorted(blob_hashes)
    total = len(hashes)
    if total == 0:
        return 0, 0, []

    from release_safety.blob_inventory import PAGE_LIMIT, MAX_ATTEMPTS
    from release_safety.quarantine import _copy_storage_object
    from release_safety.transient import retry_transient

    page_limit = PAGE_LIMIT if page_limit is None else int(page_limit)
    max_attempts = MAX_ATTEMPTS if max_attempts is None else int(max_attempts)

    checkpoint_path = Path(checkpoint_path) if checkpoint_path else None
    candidate_fingerprint = hashlib.sha256(
        "\n".join(hashes).encode("ascii")
    ).hexdigest()
    checkpoint_identity = {
        "version": 2,
        "run_date": run_date,
        "candidate_fingerprint": candidate_fingerprint,
        "candidate_count": total,
    }
    completed_shards = {}
    if checkpoint_path is not None and checkpoint_path.exists():
        try:
            saved = json.loads(checkpoint_path.read_text())
        except (OSError, ValueError) as exc:
            raise ValueError(
                f"Cannot read quarantine checkpoint {checkpoint_path}: {exc}"
            ) from exc
        for key, expected in checkpoint_identity.items():
            if saved.get(key) != expected:
                raise ValueError(
                    f"Quarantine checkpoint {checkpoint_path} belongs to a "
                    "different candidate set, run, or checkpoint format. "
                    "Use a new checkpoint path (or delete the stale file)."
                )
        raw_shards = saved.get("shards", {})
        if isinstance(raw_shards, dict):
            completed_shards = {
                shard: entry for shard, entry in raw_shards.items()
                if isinstance(entry, dict) and isinstance(entry.get("count"), int)
            }

    def _save_checkpoint():
        if checkpoint_path is None:
            return
        payload = {
            **checkpoint_identity,
            "shards": {k: completed_shards[k] for k in sorted(completed_shards)},
        }
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = checkpoint_path.with_suffix(checkpoint_path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, sort_keys=True))
        tmp.replace(checkpoint_path)

    hashes_by_shard = defaultdict(list)
    for blob_hash in hashes:
        hashes_by_shard[blob_hash[:2]].append(blob_hash)

    def _checkpoint_entry_matches(shard, shard_hashes):
        entry = completed_shards.get(shard)
        if not isinstance(entry, dict):
            return False
        expected_digest = hashlib.sha256(
            "\n".join(sorted(shard_hashes)).encode("ascii")
        ).hexdigest()
        return (
            entry.get("count") == len(shard_hashes)
            and entry.get("digest") == expected_digest
        )

    # Resume the work that still needs mutation before spending Storage API
    # requests re-verifying shards that were already proven by an earlier
    # attempt. Checkpointed shards are still re-proven below; the checkpoint
    # only changes order and never fabricates completion.
    shard_order = sorted(
        hashes_by_shard,
        key=lambda shard: (
            _checkpoint_entry_matches(shard, hashes_by_shard[shard]),
            shard,
        ),
    )

    workers = QUARANTINE_MAX_WORKERS if max_workers is None else int(max_workers)
    if client_factory is None:
        workers = 1
    workers = max(1, workers)
    thread_local = threading.local()

    def _worker_client():
        if client_factory is None:
            return client
        if not hasattr(thread_local, "client"):
            thread_local.client = client_factory()
        return thread_local.client

    def _copy_one(blob_hash):
        src = f"{BLOB_STORAGE_PREFIX}/{blob_hash[:2]}/{blob_hash}.json"
        dst = f"shared/quarantine/{run_date}/{blob_hash[:2]}/{blob_hash}.json"
        try:
            retry_transient(
                lambda: _raise_on_copy_failure(
                    _copy_storage_object(_worker_client(), BUCKET, src, dst)
                ),
                max_attempts=max_attempts,
            )
            return blob_hash, None
        except Exception as exc:  # noqa: BLE001 — per-blob operational failure.
            return blob_hash, f"{type(exc).__name__}: {exc}"

    moved = 0
    failed = 0
    failed_paths = []
    shard_index = 0
    shard_total = len(hashes_by_shard)

    for shard in shard_order:
        shard_hashes = hashes_by_shard[shard]
        shard_index += 1
        shard_hash_set = set(shard_hashes)
        # A checkpoint entry is a HINT for the operator, never a source of
        # truth: every shard — checkpointed or not — is re-proven from live
        # storage below, and `moved` only ever counts proven state. A recorded
        # digest that disagrees with this run's candidate slice means the file
        # was forged or belongs to different work; say so and re-prove.
        recorded_is_valid = _checkpoint_entry_matches(shard, shard_hashes)
        recorded = completed_shards.get(shard)
        if recorded is not None:
            expected_digest = hashlib.sha256(
                "\n".join(sorted(shard_hashes)).encode("ascii")
            ).hexdigest()
            if (
                recorded.get("count") != len(shard_hashes)
                or recorded.get("digest") != expected_digest
            ):
                print(
                    f"  [WARN] checkpoint entry for shard {shard} does not "
                    "match this run's candidates (forged or stale) — "
                    "ignoring it and re-proving from storage."
                )

        active_prefix = f"{BLOB_STORAGE_PREFIX}/{shard}"
        target_prefix = f"shared/quarantine/{run_date}/{shard}"
        bucket_proxy = client.storage.from_(BUCKET)

        # One failure record per candidate, first reason wins. `failed` and
        # `failed_paths` are derived from this exactly once, at shard end.
        shard_failures: dict = {}

        def _fail(blob_hash, reason):
            shard_failures.setdefault(blob_hash, reason)

        def _fail_all(reason, *, verification_only=False):
            if verification_only:
                reason = (
                    f"{CHECKPOINT_REVERIFY_UNAVAILABLE}: {reason}"
                )
            for blob_hash in shard_hashes:
                _fail(blob_hash, reason)
            label = "VERIFY" if verification_only else "ERROR"
            print(f"  [{label}] shard {shard} blocked: {reason}")

        def _finish_shard():
            nonlocal failed
            failed += len(shard_failures)
            failed_paths.extend(
                f"{active_prefix}/{h}.json ({reason})"
                for h, reason in sorted(shard_failures.items())
            )

        try:
            active = _list_prefix_fingerprints(
                bucket_proxy, active_prefix,
                page_limit=page_limit, max_attempts=max_attempts,
            )
            target = _list_prefix_fingerprints(
                bucket_proxy, target_prefix,
                page_limit=page_limit, max_attempts=max_attempts,
            )
        except Exception as exc:  # noqa: BLE001 — cannot see, cannot act.
            _fail_all(
                f"listing failed: {type(exc).__name__}: {exc}",
                verification_only=recorded_is_valid,
            )
            _finish_shard()
            continue

        # --- classify against the frozen approved fingerprints -----------
        to_copy = []
        delete_only = []
        already_complete = []
        block_reason = None
        for blob_hash in shard_hashes:
            leaf = f"{blob_hash}.json"
            frozen = source_fingerprints.get(blob_hash)
            frozen_fp = (
                (frozen.size, frozen.etag)
                if frozen is not None and getattr(frozen, "etag", None)
                else None
            )
            if frozen_fp is None:
                block_reason = (
                    f"candidate {blob_hash} has no proven source fingerprint"
                )
                break
            in_active = active.get(leaf)
            in_target = target.get(leaf)
            if in_active is not None:
                if in_active != frozen_fp:
                    block_reason = (
                        f"candidate {blob_hash} drifted since approval "
                        f"(active {in_active} != frozen {frozen_fp})"
                    )
                    break
                if in_target is None:
                    to_copy.append(blob_hash)
                elif in_target == frozen_fp:
                    delete_only.append(blob_hash)
                else:
                    block_reason = (
                        f"candidate {blob_hash} has a MISMATCHED quarantine "
                        f"copy (target {in_target} != frozen {frozen_fp})"
                    )
                    break
            else:
                if in_target == frozen_fp:
                    already_complete.append(blob_hash)
                elif in_target is not None:
                    block_reason = (
                        f"candidate {blob_hash} is gone from active and its "
                        f"quarantine copy does not match the approved "
                        f"fingerprint"
                    )
                    break
                else:
                    block_reason = (
                        f"candidate {blob_hash} exists at neither the active "
                        f"nor the quarantine path"
                    )
                    break
        if block_reason is not None:
            _fail_all(block_reason)
            _finish_shard()
            continue

        # A resumed shard whose candidates are all absent from active storage
        # and fingerprint-matched in quarantine is already fully proven by
        # the two classification listings above. No mutation occurred, so a
        # second target listing and a second active listing add load without
        # strengthening the proof.
        if len(already_complete) == len(shard_hashes):
            moved += len(already_complete)
            completed_shards[shard] = {
                "count": len(already_complete),
                "digest": hashlib.sha256(
                    "\n".join(sorted(already_complete)).encode("ascii")
                ).hexdigest(),
            }
            _save_checkpoint()
            print(
                f"  shard {shard} [{shard_index}/{shard_total}]: "
                f"0 newly moved, {len(already_complete)} already verified, "
                f"0 failed; total {moved}/{total}."
            )
            continue

        bystanders = {
            leaf: fp for leaf, fp in active.items()
            if leaf.removesuffix(".json") not in shard_hash_set
        }

        # --- copy phase (the only per-blob requests, bounded parallel) ----
        if to_copy:
            if workers == 1 or len(to_copy) == 1:
                results = [_copy_one(h) for h in to_copy]
            else:
                with ThreadPoolExecutor(
                    max_workers=min(workers, len(to_copy)),
                    thread_name_prefix="orphan-copy",
                ) as pool:
                    results = list(pool.map(_copy_one, to_copy))
            for blob_hash, err in results:
                if err is not None:
                    _fail(blob_hash, f"copy failed: {err}")

        # --- verify every needed target with ONE listing ------------------
        try:
            target_after = _list_prefix_fingerprints(
                bucket_proxy, target_prefix,
                page_limit=page_limit, max_attempts=max_attempts,
            )
        except Exception as exc:  # noqa: BLE001
            _fail_all(
                f"target verification listing failed: "
                f"{type(exc).__name__}: {exc}"
            )
            _finish_shard()
            continue

        deletable = []
        for blob_hash in to_copy + delete_only:
            if blob_hash in shard_failures:
                continue
            frozen = source_fingerprints[blob_hash]
            observed = target_after.get(f"{blob_hash}.json")
            if observed != (frozen.size, frozen.etag):
                _fail(
                    blob_hash,
                    f"target verification failed: observed {observed}",
                )
                continue
            deletable.append(blob_hash)

        # --- batched source deletion --------------------------------------
        for start_idx in range(0, len(deletable), DEFAULT_REMOVE_BATCH_SIZE):
            batch = deletable[start_idx:start_idx + DEFAULT_REMOVE_BATCH_SIZE]
            batch_paths = [f"{active_prefix}/{h}.json" for h in batch]
            try:
                retry_transient(
                    lambda batch_paths=batch_paths: remove_storage_batch(
                        client, BUCKET, batch_paths,
                    ),
                    max_attempts=max_attempts,
                )
            except Exception as exc:  # noqa: BLE001 — recoverable duplicates.
                for blob_hash in batch:
                    _fail(
                        blob_hash,
                        f"delete failed, recoverable duplicate remains: "
                        f"{type(exc).__name__}: {exc}",
                    )

        # --- absence + bystander proof with ONE listing -------------------
        try:
            active_after = _list_prefix_fingerprints(
                bucket_proxy, active_prefix,
                page_limit=page_limit, max_attempts=max_attempts,
            )
        except Exception as exc:  # noqa: BLE001
            _fail_all(
                f"absence-proof listing failed: {type(exc).__name__}: {exc}"
            )
            _finish_shard()
            continue

        shard_moved = []
        for blob_hash in deletable:
            if blob_hash in shard_failures:
                continue
            if f"{blob_hash}.json" in active_after:
                _fail(
                    blob_hash,
                    "residual: delete reported success but the object is "
                    "still listed",
                )
                continue
            shard_moved.append(blob_hash)
        shard_moved.extend(already_complete)

        postcondition_violations = []
        for leaf, fp in bystanders.items():
            observed = active_after.get(leaf)
            if observed != fp:
                postcondition_violations.append(
                    f"postcondition: non-candidate {active_prefix}/{leaf} "
                    f"changed during the shard window "
                    f"(before {fp}, after {observed})"
                )

        if postcondition_violations:
            for blob_hash in shard_hashes:
                _fail(
                    blob_hash,
                    "shard postcondition violated: a non-candidate changed "
                    "during the mutation window",
                )
            shard_moved = []
            failed_paths.extend(postcondition_violations)

        moved += len(shard_moved)
        _finish_shard()

        if not shard_failures and not postcondition_violations and (
            len(shard_moved) == len(shard_hashes)
        ):
            completed_shards[shard] = {
                "count": len(shard_moved),
                "digest": hashlib.sha256(
                    "\n".join(sorted(shard_moved)).encode("ascii")
                ).hexdigest(),
            }
            _save_checkpoint()

        shard_moved_set = set(shard_moved)
        already_verified_count = sum(
            blob_hash in shard_moved_set for blob_hash in already_complete
        )
        newly_moved_count = len(shard_moved) - already_verified_count
        print(
            f"  shard {shard} [{shard_index}/{shard_total}]: "
            f"{newly_moved_count} newly moved, "
            f"{already_verified_count} already verified, "
            f"{len(shard_hashes) - len(shard_moved)} failed; "
            f"total {moved}/{total}."
        )

    if failed == 0 and checkpoint_path is not None:
        checkpoint_path.unlink(missing_ok=True)
    return moved, failed, failed_paths


def _raise_on_copy_failure(result):
    """Adapter: ``_copy_storage_object`` returns (ok, err) and swallows the
    exception, which defeats transient retry. Re-raise so retry_transient can
    classify the cause; permanent failures surface immediately."""
    ok, err = result
    if not ok:
        raise RuntimeError(err or "copy failed")
    return result


# ---------------------------------------------------------------------------
# Orphan blob detection
# ---------------------------------------------------------------------------

from release_safety.blob_inventory import BLOB_STORAGE_PREFIX  # noqa: E402


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
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--lock-path",
        type=str,
        default=None,
        dest="lock_path",
        help="Release-lock file path (default: the pipeline's .release.lock).",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if args.cleanup_orphan_blobs:
        print(
            "\n[refused] Orphan reconciliation has one production entrypoint: "
            "scripts/reconcile_orphan_blobs.py."
        )
        print(
            "  Run its dry report, approve the frozen JSON artifact, then "
            "execute that artifact."
        )
        raise SystemExit(2)
    if args.execute:
        from release_safety.lock import acquire_release_lock

        with acquire_release_lock(
            Path(args.lock_path) if args.lock_path else None,
            initial_step="cleanup_old_versions --execute",
        ):
            return _run_main(args)
    return _run_main(args)


def _run_main(args):
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

    # Safety: never delete a version marked is_current.
    safe_old_rows = []
    for row in old_rows:
        if row.get("is_current"):
            print(f"  [SKIP] v{row['db_version']} is marked is_current=true — will not delete.")
        else:
            safe_old_rows.append(row)

    if not safe_old_rows:
        print(
            f"Nothing to delete at the version level — {len(rows)} version(s) "
            f"exist, keep threshold is {args.keep}. Nothing deleted."
        )
    else:
        print(f"Versions to clean up: {len(safe_old_rows)}")
    print()

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

    # -----------------------------------------------------------------
    # Quarantine sweep — REPORT ONLY. Hard-deleting expired quarantine is
    # irreversible and must never ride along with catalog publishing: every
    # real release runs this path, so an automatic sweep here would fire the
    # first eligible hard-delete unattended, mid-release. The delete lives
    # exclusively in the gated maintenance command
    # (scripts/sweep_quarantine.py: dry-run -> durable approval JSON ->
    # approved execute under the release lock).
    # -----------------------------------------------------------------
    if not dry_run:
        print("\nChecking for sweep-eligible quarantine (TTL=30d, report only)...")
        try:
            sweep_report = sweep_quarantine(
                client, ttl_days=30, dry_run=True,
            )
            if sweep_report.total_eligible == 0 and sweep_report.complete:
                print("  No expired quarantine entries found.")
            else:
                print(
                    f"  Quarantine sweep: DEFERRED — "
                    f"{sweep_report.total_eligible} expired object(s) across "
                    f"{len(sweep_report.eligible_dates)} date(s) "
                    f"({', '.join(sweep_report.eligible_dates)}) are eligible "
                    "for hard-delete."
                )
                if not sweep_report.complete:
                    print(
                        f"  [WARN] eligibility scan was partial "
                        f"({len(sweep_report.listing_failures)} listing "
                        "failure(s)) — counts above are a lower bound."
                    )
                print(
                    "  Run the gated maintenance command when ready:\n"
                    "    scripts/sweep_quarantine.py            # dry run -> approval JSON\n"
                    "    scripts/sweep_quarantine.py --execute  # with the approved artifact"
                )
        except Exception as exc:  # noqa: BLE001 — report-only, never blocking.
            print(
                f"  Quarantine eligibility check failed "
                f"({type(exc).__name__}: {exc}) — sweep remains deferred."
            )

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
    print()
    if dry_run:
        print("Dry-run complete. Re-run with --execute to apply deletions.")
    else:
        blocking_failures = total_failed + total_db_failed
        if blocking_failures == 0:
            print("Cleanup complete.")
        else:
            print("Cleanup finished with errors (see above).")
            sys.exit(1)


if __name__ == "__main__":
    main()
