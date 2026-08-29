#!/usr/bin/env python3
"""Gated hard-delete of TTL-expired quarantine — the ONLY path allowed to.

Hard-deleting quarantine is the one irreversible storage action in this
system, so it never rides along with a catalog release (the release path only
reports eligible work). The lifecycle here mirrors the orphan drain:

    # 1. Dry run — read-only, writes the durable approval artifact.
    scripts/sweep_quarantine.py --approval-out reports/storage_cleanup/sweep_approval.json

    # 2. Only after a human has reviewed that artifact's exact numbers:
    scripts/sweep_quarantine.py --execute \
        --approval-report reports/storage_cleanup/sweep_approval.json \
        --expected-count N --expected-bytes B --fingerprint <sha256> \
        --flutter-repo PATH --dist-dir PATH

Execute re-proves everything fresh under the release lock: the candidate set
must reproduce the approved fingerprint byte-for-byte, every approved date
must still be TTL-eligible, and any protected hash whose ONLY copy sits in
quarantine refuses the whole run. Deletes go out 500 paths per request; only
what a final listing proves absent counts as deleted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import date as _date, datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import env_loader  # noqa: F401,E402

from release_safety.blob_inventory import (  # noqa: E402
    HEX_BLOB_SHARDS,
    inventory_detail_blobs,
)
from release_safety.quarantine import (  # noqa: E402
    DEFAULT_REMOVE_BATCH_SIZE,
    _remove_storage_object,
    remove_storage_batch,
)
from release_safety.quarantine_sweeper import (  # noqa: E402
    is_eligible_for_hard_delete,
    list_quarantine_dates,
)
from release_safety.transient import retry_transient  # noqa: E402

BUCKET = "pharmaguide"
QUARANTINE_ROOT = "shared/quarantine"
TTL_DAYS = 30

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_REFUSED = 2

CHECKPOINT_VERSION = 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Hard-delete TTL-expired quarantine. Dry-run by default; execute "
            "requires the reviewed approval artifact plus matching "
            "count/bytes/fingerprint."
        )
    )
    parser.add_argument(
        "--ttl-days", type=int, default=TTL_DAYS, dest="ttl_days",
        help=f"Recovery-window length (default {TTL_DAYS}).",
    )
    parser.add_argument(
        "--approval-out", default=None, dest="approval_out",
        help="Dry run: where to write the durable approval JSON.",
    )
    parser.add_argument("--execute", action="store_true", default=False)
    parser.add_argument("--approval-report", default=None, dest="approval_report")
    parser.add_argument(
        "--expected-count", type=int, default=None, dest="expected_count",
    )
    parser.add_argument(
        "--expected-bytes", type=int, default=None, dest="expected_bytes",
    )
    parser.add_argument("--fingerprint", default=None)
    parser.add_argument("--flutter-repo", default=None, dest="flutter_repo")
    parser.add_argument("--dist-dir", default=None, dest="dist_dir")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--lock-path", default=None, dest="lock_path")
    parser.add_argument(
        "--checkpoint", default="reports/storage_cleanup/sweep.checkpoint.json",
    )
    parser.add_argument("--result-out", default=None, dest="result_out")
    parser.add_argument("--max-workers", type=int, default=None, dest="max_workers")
    return parser


def _path_fingerprint(paths) -> str:
    return hashlib.sha256("\n".join(sorted(paths)).encode("ascii")).hexdigest()


def _inventory_date(client, date_str: str, *, max_workers=None):
    """Complete-or-raise inventory of one quarantine date across 256 shards."""
    inv = inventory_detail_blobs(
        client,
        prefix=f"{QUARANTINE_ROOT}/{date_str}",
        shards=HEX_BLOB_SHARDS,
        max_workers=max_workers,
    )
    return inv


def _paths_of(inv, date_str: str):
    return {
        f"{QUARANTINE_ROOT}/{date_str}/{h[:2]}/{h}.json": (
            inv.sizes[h], inv.etags.get(h),
        )
        for h in inv.hashes
    }


def _dry_run(client, args, today: _date) -> int:
    dates = [
        d for d in list_quarantine_dates(client)
        if is_eligible_for_hard_delete(d, ttl_days=args.ttl_days, now=today)
    ]
    print(f"Sweep-eligible quarantine dates (TTL={args.ttl_days}d): {dates or 'none'}")
    if not dates:
        print("Nothing eligible. No approval artifact written.")
        return EXIT_OK

    per_date = {}
    all_paths = {}
    for date_str in sorted(dates):
        inv = _inventory_date(client, date_str, max_workers=args.max_workers)
        if not inv.complete:
            print(
                f"[refused] inventory of {date_str} is INCOMPLETE "
                f"({len(inv.failures)} shard failure(s), "
                f"{len(inv.integrity_failures)} integrity violation(s)). "
                "A partial scan must never become an approval artifact."
            )
            return EXIT_ERROR
        paths = _paths_of(inv, date_str)
        all_paths.update(paths)
        per_date[date_str] = {
            "count": len(paths),
            "bytes": inv.total_bytes,
            "etag_coverage": sum(1 for _s, e in paths.values() if e),
            "paths": sorted(paths),
        }
        print(
            f"  {date_str}: {len(paths):,} object(s), {inv.total_bytes:,} bytes, "
            f"eTag coverage {per_date[date_str]['etag_coverage']:,}"
        )

    artifact = {
        "generated_utc_date": today.isoformat(),
        "ttl_days": args.ttl_days,
        "dates": sorted(dates),
        "per_date": per_date,
        "total_count": len(all_paths),
        "total_bytes": sum(s for s, _e in all_paths.values()),
        "path_fingerprint": _path_fingerprint(all_paths),
    }
    if args.approval_out:
        out = Path(args.approval_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(artifact, indent=2, sort_keys=True))
        print(f"\nApproval artifact written to {out}")
    print(
        f"\nTOTAL: {artifact['total_count']:,} object(s) / "
        f"{artifact['total_bytes']:,} bytes\n"
        f"fingerprint: {artifact['path_fingerprint']}\n\n"
        "To hard-delete this exact reviewed set:\n"
        f"  scripts/sweep_quarantine.py --execute "
        f"--approval-report {args.approval_out or '<approval.json>'} \\\n"
        f"      --expected-count {artifact['total_count']} "
        f"--expected-bytes {artifact['total_bytes']} \\\n"
        f"      --fingerprint {artifact['path_fingerprint']} \\\n"
        "      --flutter-repo PATH --dist-dir PATH"
    )
    return EXIT_OK


def _load_checkpoint(path: Path, fingerprint: str) -> set:
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return set()
    if (
        not isinstance(data, dict)
        or data.get("version") != CHECKPOINT_VERSION
        or data.get("fingerprint") != fingerprint
    ):
        return set()
    done = data.get("done_shards")
    return {tuple(x) for x in done} if isinstance(done, list) else set()


def _save_checkpoint(path: Path, fingerprint: str, done: set) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps({
        "version": CHECKPOINT_VERSION,
        "fingerprint": fingerprint,
        "done_shards": sorted(list(x) for x in done),
    }, sort_keys=True))
    tmp.replace(path)


def _execute(client, args, today: _date) -> int:
    # ---- artifact + flag validation (before anything else) ---------------
    missing = [
        flag for flag, value in (
            ("--approval-report", args.approval_report),
            ("--expected-count", args.expected_count),
            ("--expected-bytes", args.expected_bytes),
            ("--fingerprint", args.fingerprint),
            ("--flutter-repo", args.flutter_repo),
            ("--dist-dir", args.dist_dir),
        ) if value is None
    ]
    if missing:
        print(
            "\n[refused] --execute requires the reviewed approval quad plus "
            f"protection inputs: missing {', '.join(missing)}."
        )
        return EXIT_REFUSED

    try:
        artifact = json.loads(Path(args.approval_report).read_text())
    except (OSError, ValueError) as exc:
        print(f"\n[refused] cannot read approval report: {exc}")
        return EXIT_REFUSED
    for key, flag_value in (
        ("total_count", args.expected_count),
        ("total_bytes", args.expected_bytes),
        ("path_fingerprint", args.fingerprint),
    ):
        if artifact.get(key) != flag_value:
            print(
                f"\n[refused] {key} mismatch: approval says "
                f"{artifact.get(key)!r}, flags say {flag_value!r}."
            )
            return EXIT_REFUSED
    dates = artifact.get("dates") or []
    if not dates:
        print("\n[refused] approval artifact approves no dates.")
        return EXIT_REFUSED
    approved_paths = set()
    for date_str in dates:
        entry = (artifact.get("per_date") or {}).get(date_str) or {}
        raw_paths = entry.get("paths")
        if not isinstance(raw_paths, list) or not raw_paths:
            print(
                f"\n[refused] approval artifact carries no path list for "
                f"{date_str} — regenerate the dry run."
            )
            return EXIT_REFUSED
        for path in raw_paths:
            if not (
                isinstance(path, str)
                and path.startswith(f"{QUARANTINE_ROOT}/{date_str}/")
            ):
                print(
                    f"\n[refused] approval artifact contains a path outside "
                    f"the approved quarantine date: {path!r}."
                )
                return EXIT_REFUSED
            approved_paths.add(path)
    if _path_fingerprint(approved_paths) != artifact["path_fingerprint"]:
        print(
            "\n[refused] approval artifact is internally inconsistent: its "
            "path list does not reproduce its own fingerprint (edited or "
            "corrupted)."
        )
        return EXIT_REFUSED
    if len(approved_paths) != artifact["total_count"]:
        print("\n[refused] approval artifact count does not match its paths.")
        return EXIT_REFUSED
    not_eligible = [
        d for d in dates
        if not is_eligible_for_hard_delete(d, ttl_days=args.ttl_days, now=today)
    ]
    if not_eligible:
        print(
            f"\n[refused] approved date(s) {', '.join(not_eligible)} are not "
            f"TTL-eligible on {today.isoformat()}. Nothing deleted."
        )
        return EXIT_REFUSED

    from release_safety.lock import (
        CorruptLockError,
        LockContentionError,
        ReleaseLockError,
        StaleLockError,
        acquire_release_lock,
    )
    from release_safety.protected_blobs import compute_protected_blob_set

    try:
        lock_ctx = acquire_release_lock(
            Path(args.lock_path) if args.lock_path else None,
            initial_step="sweep_quarantine --execute",
        )
        lock_ctx.__enter__()
    except (LockContentionError, StaleLockError, CorruptLockError,
            ReleaseLockError) as exc:
        print(f"\n[refused] release lock unavailable: {exc}")
        return EXIT_ERROR

    deleted = 0
    residuals = []
    delete_failures = []
    already_absent = []
    try:
        # ---- fresh re-proof of the candidate set -------------------------
        fresh_paths = {}
        fresh_by_date = {}
        for date_str in sorted(dates):
            inv = _inventory_date(client, date_str, max_workers=args.max_workers)
            if not inv.complete:
                print(
                    f"\n[refused] fresh inventory of {date_str} is incomplete "
                    "— cannot prove the candidate set. Nothing deleted."
                )
                return EXIT_ERROR
            paths = _paths_of(inv, date_str)
            fresh_by_date[date_str] = inv
            fresh_paths.update(paths)
        # Frozen-set semantics (same shape as the orphan drain): the fresh
        # scan may only ever SHRINK relative to the approved set — a missing
        # approved path already reached its goal state (absence) and counts
        # as done; an EXTRA path means the candidate set changed after
        # approval, and deleting it would exceed what was reviewed. Refuse.
        extra = sorted(set(fresh_paths) - approved_paths)
        if extra:
            print(
                f"\n[refused] the candidate set has CHANGED since approval: "
                f"{len(extra)} object(s) under the approved date(s) are NOT "
                f"in the reviewed artifact (e.g. {extra[0]}). Re-run the dry "
                "run and review again. Nothing deleted."
            )
            return EXIT_REFUSED
        already_absent = sorted(approved_paths - set(fresh_paths))
        if already_absent:
            print(
                f"  resume: {len(already_absent):,} approved path(s) already "
                "absent (previously completed work)."
            )

        # ---- protected-overlap guard ------------------------------------
        # Deleting the quarantine copy of a hash that is protected AND still
        # active is safe (redundant copy). Deleting one whose ONLY copy is
        # the quarantine copy would destroy a live blob — refuse everything.
        try:
            protected = compute_protected_blob_set(
                args.flutter_repo, args.dist_dir, branch=args.branch,
                supabase_client=client,
            )
        except Exception as exc:  # noqa: BLE001
            print(
                f"\n[refused] protected-set computation failed "
                f"({type(exc).__name__}: {exc}). Nothing deleted."
            )
            return EXIT_ERROR
        if protected.degenerate:
            print(
                f"\n[refused] protected set is degenerate: "
                f"{protected.degenerate_reason}. Nothing deleted."
            )
            return EXIT_ERROR
        quarantined_hashes = {
            path.rsplit("/", 1)[-1][:-5] for path in fresh_paths
        }
        overlap = sorted(quarantined_hashes & protected.protected)
        if overlap:
            overlap_shards = tuple(sorted({h[:2] for h in overlap}))
            active_inv = inventory_detail_blobs(
                client, shards=overlap_shards, max_workers=args.max_workers,
            )
            if not active_inv.complete:
                print(
                    "\n[refused] could not verify active copies for "
                    f"{len(overlap)} protected hash(es) present in "
                    "quarantine. Nothing deleted."
                )
                return EXIT_ERROR
            orphaned_protected = [h for h in overlap if h not in active_inv.hashes]
            if orphaned_protected:
                print(
                    f"\n[refused] {len(orphaned_protected)} PROTECTED "
                    "hash(es) have their ONLY copy in quarantine — sweeping "
                    "would destroy live data. Recover them first "
                    "(release_safety.recover_blob). Nothing deleted. Sample: "
                    f"{orphaned_protected[:3]}"
                )
                return EXIT_REFUSED
            print(
                f"  protected-overlap check: {len(overlap)} hash(es) also "
                "protected — all verified present in active storage "
                "(quarantine copies are redundant)."
            )

        # ---- batched deletion, per (date, shard), checkpointed -----------
        checkpoint_path = Path(args.checkpoint)
        done_shards = _load_checkpoint(checkpoint_path, artifact["path_fingerprint"])
        by_shard = {}
        for path in set(fresh_paths) & approved_paths:
            parts = path.split("/")
            by_shard.setdefault((parts[2], parts[3]), []).append(path)

        for key in sorted(by_shard):
            date_str, shard = key
            shard_paths = sorted(by_shard[key])
            if key not in done_shards:
                for start in range(0, len(shard_paths), DEFAULT_REMOVE_BATCH_SIZE):
                    batch = shard_paths[start:start + DEFAULT_REMOVE_BATCH_SIZE]
                    try:
                        retry_transient(
                            lambda batch=batch: remove_storage_batch(
                                client, BUCKET, batch,
                            ),
                            max_attempts=4,
                        )
                    except Exception:  # noqa: BLE001 — isolate the poison.
                        for path in batch:
                            ok, err = _remove_storage_object(client, BUCKET, path)
                            if not ok:
                                delete_failures.append(f"{path} ({err})")
            # Absence proof for this shard — the listing is the authority,
            # for freshly-deleted AND checkpoint-resumed shards alike.
            prefix = f"{QUARANTINE_ROOT}/{date_str}/{shard}"
            try:
                still = retry_transient(
                    lambda prefix=prefix: client.storage.from_(BUCKET).list(
                        path=prefix, options={"limit": 1000, "offset": 0},
                    ),
                    max_attempts=4,
                )
            except Exception as exc:  # noqa: BLE001
                delete_failures.append(
                    f"{prefix} (absence proof failed: {type(exc).__name__})"
                )
                continue
            present = {
                (item or {}).get("name") for item in (still or [])
            }
            shard_residuals = [
                p for p in shard_paths if p.rsplit("/", 1)[-1] in present
            ]
            if shard_residuals:
                residuals.extend(shard_residuals)
            else:
                deleted += len(shard_paths)
                done_shards.add(key)
                _save_checkpoint(checkpoint_path, artifact["path_fingerprint"], done_shards)
    finally:
        lock_ctx.__exit__(None, None, None)

    print(
        f"\nSweep summary: {deleted:,} hard-deleted this run (proven "
        f"absent), {len(already_absent):,} already absent from prior work, "
        f"{len(residuals)} residual(s), {len(delete_failures)} failure(s) — "
        f"of {len(approved_paths):,} approved."
    )
    for path in residuals[:10]:
        print(f"  residual: {path}")
    for entry in delete_failures[:10]:
        print(f"  failed: {entry}")

    result = {
        "executed_utc_date": today.isoformat(),
        "approval_fingerprint": artifact["path_fingerprint"],
        "deleted": deleted,
        "already_absent": len(already_absent),
        "residuals": len(residuals),
        "failures": len(delete_failures),
    }
    if args.result_out:
        out = Path(args.result_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=2, sort_keys=True))
        print(f"Result written to {out}")

    if not residuals and not delete_failures:
        Path(args.checkpoint).unlink(missing_ok=True)
        return EXIT_OK
    return EXIT_ERROR


def main(argv=None, *, client=None, today=None) -> int:
    args = build_parser().parse_args(argv)
    if today is None:
        today = datetime.now(timezone.utc).date()

    if client is None:
        from supabase_client import get_supabase_client

        try:
            client = get_supabase_client()
        except ValueError as exc:
            print(f"[ERROR] Cannot connect to Supabase: {exc}")
            return EXIT_ERROR

    if args.execute:
        return _execute(client, args, today)
    return _dry_run(client, args, today)


if __name__ == "__main__":
    sys.exit(main())
