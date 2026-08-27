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

BUCKET = "pharmaguide"

# Supabase storage list calls can hang in SSL reads at production scale.
# Keep page reads bounded so cleanup either progresses visibly or fails closed.
# Page timeout and list-retry budget now live in release_safety.blob_inventory
# (PG_STORAGE_LIST_PAGE_TIMEOUT_SECONDS / PG_STORAGE_LIST_MAX_RETRIES). They
# were redeclared here with a DIFFERENT default for the same env var, which is
# how two knobs that look like one drift apart.
STORAGE_LIST_PROGRESS_EVERY_SHARDS = int(
    os.environ.get("PG_STORAGE_LIST_PROGRESS_EVERY_SHARDS", "16")
)
SUPABASE_TABLE_MAX_RETRIES = int(
    os.environ.get("PG_SUPABASE_TABLE_MAX_RETRIES", "5")
)
QUARANTINE_MAX_WORKERS = int(
    os.environ.get("PG_QUARANTINE_MAX_WORKERS", "4")
)
ORPHAN_DELETE_BATCH_SIZE = int(
    os.environ.get("PG_ORPHAN_DELETE_BATCH_SIZE", "500")
)
ORPHAN_DELETE_TIMEOUT_SECONDS = int(
    os.environ.get("PG_ORPHAN_DELETE_TIMEOUT_SECONDS", "60")
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


def _remove_storage_batch(client, paths):
    bucket_proxy = client.storage.from_(BUCKET)
    if hasattr(bucket_proxy, "_request") and hasattr(bucket_proxy, "id"):
        bucket_proxy._request(
            "DELETE",
            ["object", bucket_proxy.id],
            json={"prefixes": paths},
            timeout=ORPHAN_DELETE_TIMEOUT_SECONDS,
        )
    else:
        bucket_proxy.remove(paths)


def delete_orphan_blob_batch(client, blob_hashes):
    """Hard-delete reviewed orphan hashes in storage batches.

    This path is only for large historical backlogs after release-safety gates
    pass with an explicit reviewed expected count. Quarantine remains the
    default because it is recoverable.
    """
    hashes = sorted(blob_hashes)
    total = len(hashes)
    deleted = 0
    failed = 0
    failed_paths = []
    for start in range(0, total, ORPHAN_DELETE_BATCH_SIZE):
        batch_hashes = hashes[start:start + ORPHAN_DELETE_BATCH_SIZE]
        paths = [
            f"{BLOB_STORAGE_PREFIX}/{blob_hash[:2]}/{blob_hash}.json"
            for blob_hash in batch_hashes
        ]
        try:
            _remove_storage_batch(client, paths)
            deleted += len(paths)
        except Exception as exc:  # noqa: BLE001 — report and continue.
            failed += len(paths)
            failed_paths.extend(paths[:20])
            print(
                f"  [ERROR] Failed to delete orphan batch "
                f"{start + 1}-{start + len(paths)}: "
                f"{type(exc).__name__}: {exc}"
            )
        processed = min(start + len(batch_hashes), total)
        if (
            processed == total
            or processed == len(batch_hashes)
            or processed % (ORPHAN_DELETE_BATCH_SIZE * 10) == 0
        ):
            print(
                f"  Delete progress: {processed}/{total} processed; "
                f"{deleted} deleted, {failed} failed."
            )
    return deleted, failed, failed_paths


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
    (``ORPHAN_DELETE_BATCH_SIZE`` per call); prove with one final listing that
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

    for shard, shard_hashes in sorted(hashes_by_shard.items()):
        shard_index += 1
        if shard in completed_shards:
            moved += completed_shards[shard]["count"]
            continue

        active_prefix = f"{BLOB_STORAGE_PREFIX}/{shard}"
        target_prefix = f"shared/quarantine/{run_date}/{shard}"
        bucket_proxy = client.storage.from_(BUCKET)

        def _fail_shard(reason):
            nonlocal failed
            failed += len(shard_hashes)
            failed_paths.extend(
                f"{active_prefix}/{h}.json ({reason})" for h in shard_hashes
            )
            print(f"  [ERROR] shard {shard} blocked: {reason}")

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
            _fail_shard(f"listing failed: {type(exc).__name__}: {exc}")
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
            _fail_shard(block_reason)
            continue

        bystanders = {
            leaf: fp for leaf, fp in active.items()
            if leaf.removesuffix(".json") not in set(shard_hashes)
        }

        # --- copy phase (the only per-blob requests, bounded parallel) ----
        copy_failed = {}
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
                    copy_failed[blob_hash] = err
                    failed += 1
                    failed_paths.append(
                        f"{active_prefix}/{blob_hash}.json (copy failed: {err})"
                    )

        # --- verify every needed target with ONE listing ------------------
        try:
            target_after = _list_prefix_fingerprints(
                bucket_proxy, target_prefix,
                page_limit=page_limit, max_attempts=max_attempts,
            )
        except Exception as exc:  # noqa: BLE001
            _fail_shard(
                f"target verification listing failed: "
                f"{type(exc).__name__}: {exc}"
            )
            # The shard-level failure covers the copies too; the copies that
            # succeeded are idempotently re-verified on the next run.
            failed -= len(copy_failed)  # avoid double-counting copy failures
            for blob_hash in copy_failed:
                failed_paths = [
                    fp for fp in failed_paths
                    if not fp.startswith(f"{active_prefix}/{blob_hash}.json")
                ]
            continue

        deletable = []
        for blob_hash in to_copy + delete_only:
            if blob_hash in copy_failed:
                continue
            frozen = source_fingerprints[blob_hash]
            observed = target_after.get(f"{blob_hash}.json")
            if observed != (frozen.size, frozen.etag):
                failed += 1
                failed_paths.append(
                    f"{active_prefix}/{blob_hash}.json (target verification "
                    f"failed: observed {observed})"
                )
                continue
            deletable.append(blob_hash)

        # --- batched source deletion --------------------------------------
        delete_failed = set()
        for start_idx in range(0, len(deletable), ORPHAN_DELETE_BATCH_SIZE):
            batch = deletable[start_idx:start_idx + ORPHAN_DELETE_BATCH_SIZE]
            batch_paths = [f"{active_prefix}/{h}.json" for h in batch]
            try:
                retry_transient(
                    lambda batch_paths=batch_paths: _remove_storage_batch(
                        client, batch_paths,
                    ),
                    max_attempts=max_attempts,
                )
            except Exception as exc:  # noqa: BLE001 — recoverable duplicates.
                for blob_hash in batch:
                    delete_failed.add(blob_hash)
                    failed += 1
                    failed_paths.append(
                        f"{active_prefix}/{blob_hash}.json (delete failed, "
                        f"recoverable duplicate remains: "
                        f"{type(exc).__name__}: {exc})"
                    )

        # --- absence + bystander proof with ONE listing -------------------
        try:
            active_after = _list_prefix_fingerprints(
                bucket_proxy, active_prefix,
                page_limit=page_limit, max_attempts=max_attempts,
            )
        except Exception as exc:  # noqa: BLE001
            _fail_shard(
                f"absence-proof listing failed: {type(exc).__name__}: {exc}"
            )
            continue

        shard_moved = []
        shard_clean = not copy_failed and not delete_failed
        for blob_hash in deletable:
            if blob_hash in delete_failed:
                continue
            if f"{blob_hash}.json" in active_after:
                failed += 1
                shard_clean = False
                failed_paths.append(
                    f"{active_prefix}/{blob_hash}.json (residual: delete "
                    f"reported success but the object is still listed)"
                )
                continue
            shard_moved.append(blob_hash)
        shard_moved.extend(already_complete)

        for leaf, fp in bystanders.items():
            observed = active_after.get(leaf)
            if observed != fp:
                failed += 1
                shard_clean = False
                failed_paths.append(
                    f"postcondition: non-candidate {active_prefix}/{leaf} "
                    f"changed during the shard window "
                    f"(before {fp}, after {observed})"
                )

        moved += len(shard_moved)
        if shard_clean and len(shard_moved) == len(shard_hashes):
            completed_shards[shard] = {
                "count": len(shard_moved),
                "digest": hashlib.sha256(
                    "\n".join(sorted(shard_moved)).encode("ascii")
                ).hexdigest(),
            }
            _save_checkpoint()

        print(
            f"  shard {shard} [{shard_index}/{shard_total}]: "
            f"{len(shard_moved)} moved, "
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

# One inventory brain: the shard layout, page listing, retries and
# completeness rules all live in release_safety.blob_inventory. The former
# single-version helpers here (fetch_current_detail_index, detect_orphan_blobs,
# cleanup_orphan_blobs) were removed: they protected only the CURRENT
# detail_index, so on 2026-08-26 they would have called blobs of the still
# retained 2026.08.25 catalog deletable.
from release_safety.blob_inventory import (  # noqa: E402
    BLOB_STORAGE_PREFIX,
    HEX_BLOB_SHARDS,
    inventory_detail_blobs,
)


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
    retained_versions=(),
    orphan_action="quarantine",
    quarantine_client_factory=None,
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
           - bundled∪dist∪registry protected-set computation (HR-1, HR-2)
             (P3.5: registry-backed ACTIVE+VALIDATING rows fold in too)
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
        retained_versions: db_versions intentionally kept by --keep N.
            Their version directories remain readable, so their detail blobs
            must be protected from the orphan sweep.

    Returns:
    ``(processed_count, failed_count)``. Both 0 if gates rejected.

    Never raises in normal use — gate failures and per-blob quarantine/delete
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
        DEFAULT_QUARANTINE_TTL_DAYS,
    )
    from datetime import datetime as _datetime, timezone as _timezone
    from pathlib import Path as _Path

    # One run_date per cleanup run — every quarantined blob lands under
    # the same date directory so the sweeper can drain them as a unit.
    if run_date is None:
        run_date = _datetime.now(_timezone.utc).strftime("%Y-%m-%d")
    if orphan_action not in {"quarantine", "delete"}:
        raise ValueError(
            "orphan_action must be 'quarantine' or 'delete', "
            f"got {orphan_action!r}"
        )
    if orphan_action == "delete" and expected_count is None:
        raise ValueError(
            "orphan_action='delete' requires --expected-count so the "
            "reviewed blast-radius override is explicit."
        )

    print("\n=== Gated orphan-blob cleanup (ADR-0001 P1.6 + P2.2) ===")
    print(f"  flutter_repo:     {flutter_repo_path}")
    print(f"  dist_dir:         {dist_dir}")
    print(f"  branch:           {branch}")
    print(f"  run_date:         {run_date}")
    print(f"  orphan action:    {orphan_action}")
    retained_versions = tuple(v for v in retained_versions if v)
    if retained_versions:
        print(f"  retained versions: {', '.join(retained_versions)}")

    # Step 1: list all blobs in storage (we need both the candidate set
    # and the total for blast-radius). Cheaper to do this once here than
    # twice (here + inside the gate).
    print("\nListing all blobs in Supabase storage...")

    def _progress(done, total, objects):
        if done == 1 or done == total or done % STORAGE_LIST_PROGRESS_EVERY_SHARDS == 0:
            print(
                f"  Listed {done}/{total} shard(s); "
                f"{objects} blob object(s) seen so far."
            )

    inventory = inventory_detail_blobs(
        client,
        shards=HEX_BLOB_SHARDS,
        client_factory=quarantine_client_factory,
        progress=_progress,
    )
    if not inventory.complete:
        # Fail closed WITHOUT raising: this function's contract is that gate
        # and I/O failures are reported, not thrown. An undercounted storage
        # side cannot prove what is an orphan.
        print(
            f"\n[release-safety] Storage inventory incomplete: read "
            f"{inventory.shards_completed}/{inventory.shards_total} shard(s), "
            f"{len(inventory.failures)} failed."
        )
        for failure in inventory.failures[:5]:
            print(f"    {failure.shard}: {failure.error}")
        print("  Refusing destructive cleanup. No blobs quarantined.")
        return 0, 0

    storage_hashes = set(inventory.hashes)
    storage_total = len(storage_hashes)
    print(
        f"  {storage_total} unique blobs in storage "
        f"({inventory.retries} retry/retries, "
        f"{inventory.elapsed_seconds:.1f}s)"
    )

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
        # P3.6a — registry-backed protected-set is now load-bearing in
        # production cleanup runs. Strictly additive: any ACTIVE/VALIDATING
        # catalog_releases row contributes its blob hashes to the protected
        # set before this gate decides which candidates survive.
        supabase_client=client,
        retained_versions=retained_versions,
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
    if orphan_action == "delete":
        print(
            f"\n[release-safety] Gates passed. "
            f"Hard-deleting {len(actual_orphans)} reviewed orphan blob(s) "
            f"in batches of {ORPHAN_DELETE_BATCH_SIZE} "
            f"(of {len(candidate_hashes)} pre-gate candidates; "
            f"{len(candidate_hashes) - len(actual_orphans)} protected by "
            "release-safety sources)."
        )
        deleted, failed, failed_paths = delete_orphan_blob_batch(
            client, actual_orphans
        )
        print(
            f"\n[release-safety] Batch delete complete: "
            f"{deleted} deleted, {failed} failed."
        )
        if audit_log is not None:
            audit_log.event(
                "orphan_delete_completed",
                deleted_count=deleted,
                failed_count=failed,
                failed_paths_sample=failed_paths[:20],
            )
        return deleted, failed

    print(
        f"\n[release-safety] Gates passed. "
        f"Quarantining {len(actual_orphans)} blob(s) "
        f"to shared/quarantine/{run_date}/ "
        f"(of {len(candidate_hashes)} pre-gate candidates; "
        f"{len(candidate_hashes) - len(actual_orphans)} protected by release-safety sources). "
        f"Recoverable for {DEFAULT_QUARANTINE_TTL_DAYS} days."
    )

    # The frozen identity every action is verified against comes from the
    # same inventory that produced the candidates.
    orphan_fingerprints = {
        h: inventory.fingerprint_for(h) for h in actual_orphans
    }
    quarantined, failed, failed_paths = quarantine_orphan_blob_batch(
        client,
        actual_orphans,
        run_date=run_date,
        source_fingerprints=orphan_fingerprints,
        client_factory=quarantine_client_factory,
    )

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
        help=(
            "Detect orphaned detail blobs not referenced by the current "
            "detail_index (default: false). Execute mode defaults to "
            "recoverable quarantine unless --orphan-blob-action=delete is set."
        ),
    )
    parser.add_argument(
        "--orphan-blob-action",
        choices=("quarantine", "delete"),
        default="quarantine",
        dest="orphan_blob_action",
        help=(
            "Action for gated orphan blobs in execute mode. 'quarantine' is "
            "recoverable and remains the default. 'delete' hard-deletes in "
            "batches and requires --expected-count."
        ),
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

    # Safety: never delete a version marked is_current.
    safe_old_rows = []
    for row in old_rows:
        if row.get("is_current"):
            print(f"  [SKIP] v{row['db_version']} is marked is_current=true — will not delete.")
        else:
            safe_old_rows.append(row)

    # Orphan-blob cleanup is DECOUPLED from version-directory retention.
    # Orphans accumulate independently — a backlog from prior gate-rejected
    # runs persists even at steady-state version count — so an empty
    # safe_old_rows must NOT short-circuit the orphan sweep. That early return
    # is exactly why storage grew to 84% orphans (the cleanup ran only when
    # there happened to be an old version directory to delete).
    if not safe_old_rows:
        msg = (
            f"Nothing to delete at the version level — {len(rows)} version(s) "
            f"exist, keep threshold is {args.keep}."
        )
        if not args.cleanup_orphan_blobs:
            print(msg + " Nothing deleted.")
            sys.exit(0)
        print(msg + " Proceeding to orphan-blob cleanup.")
    else:
        print(f"Versions to clean up: {len(safe_old_rows)}")
    print()

    # Delete storage objects
    total_deleted = 0
    total_failed = 0
    total_db_deleted = 0
    total_db_failed = 0
    gated_cleanup_error = False

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
                # The old dry run scanned storage against the CURRENT
                # detail_index only, so every blob kept alive solely by a
                # retained older catalog was reported as deletable. A count
                # that errs toward "delete more" is worse than no count.
                # Orphan reporting now lives in the maintenance tool, which
                # protects every retained version and states its own limits.
                print(
                    "\n[ERROR] Orphan dry-run reporting has moved to "
                    "scripts/reconcile_orphan_blobs.py."
                )
                print(
                    "        The count this path used to print protected only "
                    "the current\n        detail_index, not every retained "
                    "catalog version."
                )
                print("\n  Run instead:")
                print(
                    "    scripts/reconcile_orphan_blobs.py \\\n"
                    "        --flutter-repo PATH --dist-dir PATH \\\n"
                    "        --checkpoint reports/orphan_inventory.checkpoint.json \\\n"
                    "        --json-report reports/orphan_report.json"
                )
                sys.exit(2)
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
                            retained_versions=tuple(
                                r["db_version"] for r in keep_rows
                                if r.get("db_version")
                            ),
                            orphan_action=args.orphan_blob_action,
                            quarantine_client_factory=get_supabase_client,
                        )
                    )
                except Exception as exc:
                    gated_cleanup_error = True
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

    # -----------------------------------------------------------------
    # Quarantine sweep — hard-delete expired quarantine entries.
    # Runs after orphan quarantine so newly quarantined blobs are NOT
    # eligible (they were just created today, TTL is 30 days).
    # Non-blocking: failures here are housekeeping, not data-integrity.
    # -----------------------------------------------------------------
    sweep_deleted = 0
    sweep_failed = 0
    if not dry_run:
        print("\nSweeping expired quarantine entries (TTL=30d)...")
        try:
            sweep_result = sweep_quarantine(
                client, ttl_days=30, dry_run=False,
            )
            sweep_deleted = sweep_result.total_deleted
            sweep_failed = sweep_result.total_failed
            if not sweep_result.complete:
                # Do not report "nothing expired" when we simply could not
                # see it. Both live quarantine date roots 544 on a flat
                # listing; a shard we failed to read is unswept work.
                print(
                    f"  [WARN] Quarantine sweep saw only part of the "
                    f"quarantine — {len(sweep_result.listing_failures)} "
                    f"shard listing(s) failed. Swept {sweep_deleted}; "
                    "the rest remain for the next run."
                )
            elif sweep_result.total_eligible == 0:
                print("  No expired quarantine entries found.")
            else:
                print(
                    f"  Swept {sweep_deleted} expired blobs across "
                    f"{len(sweep_result.eligible_dates)} date(s)."
                )
                if sweep_failed:
                    print(f"  Sweep failures: {sweep_failed} (non-blocking)")
        except Exception as exc:
            print(f"  Quarantine sweep error: {type(exc).__name__}: {exc}")
            print("  Non-blocking — quarantine will be swept on next run.")

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
            if args.orphan_blob_action == "delete":
                print(f"  Orphan blobs deleted:           {total_orphans_quarantined}")
            else:
                # Execute path (P2.2): orphans were MOVED to quarantine, not
                # deleted. Recoverable for 30 days via release_safety.recover_blob.
                print(f"  Orphan blobs quarantined:       {total_orphans_quarantined}")
        if total_orphans_failed:
            verb = "delete" if dry_run else args.orphan_blob_action
            print(f"  Orphan blob {verb} failures:  {total_orphans_failed}")
    if not dry_run and (sweep_deleted or sweep_failed):
        print(f"  Quarantine swept (hard-delete): {sweep_deleted}")
        if sweep_failed:
            print(f"  Quarantine sweep failures:      {sweep_failed}")
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
            orphan_action_label = (
                "batch deletes"
                if args.orphan_blob_action == "delete"
                else "quarantine moves"
            )
            print(
                f"  Note: {total_orphans_failed}/{orphan_total} orphan-blob "
                f"{orphan_action_label} failed — typically transient HTTP/2 stream-limit "
                f"or response-parse issues. Treating as non-blocking; the "
                f"stragglers retry on the next cleanup run (idempotent)."
            )

        blocking_failures = total_failed + total_db_failed
        if gated_cleanup_error:
            blocking_failures += 1
        if blocking_failures == 0:
            print("Cleanup complete.")
        else:
            print("Cleanup finished with errors (see above).")
            sys.exit(1)


if __name__ == "__main__":
    main()
