#!/usr/bin/env python3
"""Reconcile orphaned shared detail blobs — a separate maintenance step.

This is deliberately NOT part of the release. Publishing a catalog is a
user-visible event; reclaiming unreferenced blobs is housekeeping. Coupling
them meant a 6+ minute full-bucket scan sat on the release critical path, and
a maintenance failure was reported as a release-step failure.

Usage
-----
    # 1. Dry run — read-only, produces the exact counts to review.
    scripts/reconcile_orphan_blobs.py \
        --flutter-repo "/Users/seancheick/PharmaGuide ai" \
        --dist-dir scripts/dist \
        --checkpoint reports/orphan_inventory.checkpoint.json \
        --json-report reports/orphan_report.json

    # 2. Only after a human has reviewed the full frozen artifact:
    scripts/reconcile_orphan_blobs.py ... \
        --execute --approval-report reports/orphan_report.json \
        --expected-count N

``--execute`` MOVES blobs to ``shared/quarantine/{date}/`` (recoverable for 30
days via ``release_safety.recover_blob``). There is no hard-delete path in
this tool; expired quarantine is drained separately by the sweeper.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import env_loader  # noqa: F401,E402

from release_safety.blob_inventory import HEX_BLOB_SHARDS  # noqa: E402
from release_safety.orphan_reconcile import build_orphan_report  # noqa: E402

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_REFUSED = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Reconcile orphaned shared detail blobs. Dry-run by default; "
            "quarantine (recoverable) is the only destructive action."
        )
    )
    parser.add_argument("--flutter-repo", required=True, dest="flutter_repo")
    parser.add_argument("--dist-dir", required=True, dest="dist_dir")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--bucket", default="pharmaguide")
    parser.add_argument(
        "--retained-version", action="append", default=[], dest="retained_versions",
        help="db_version whose blobs must stay protected. Repeatable. "
             "Defaults to the newest --keep N export_manifest rows.",
    )
    parser.add_argument("--keep", type=int, default=2, metavar="N")
    parser.add_argument(
        "--shards", default=None,
        help="Comma-separated hex shards to scan (default: all 256).",
    )
    parser.add_argument("--max-workers", type=int, default=None, dest="max_workers")
    parser.add_argument("--max-attempts", type=int, default=None, dest="max_attempts")
    parser.add_argument(
        "--checkpoint", default=None,
        help="Path for the resumable inventory checkpoint. Only shards that "
             "were read in full are recorded.",
    )
    parser.add_argument(
        "--quarantine-checkpoint",
        default="reports/orphan_quarantine.checkpoint.json",
        help="Execution progress checkpoint. Successful moves are recorded "
             "atomically so an interrupted run resumes only unfinished blobs.",
    )
    parser.add_argument("--json-report", default=None, dest="json_report")
    parser.add_argument(
        "--verify-inventory", action="store_true", default=False,
        dest="verify_inventory",
        help="Dual-read check: run BOTH the shard walker and the inventory "
             "RPC over the same prefix and require byte-exact parity "
             "(names, sizes, eTags). Read-only; exits non-zero on any "
             "divergence or if the RPC is unavailable.",
    )
    parser.add_argument(
        "--execute", action="store_true", default=False,
        help="Move the APPROVED orphans to quarantine. Requires "
             "--approval-report (the dry run's JSON artifact) and "
             "--expected-count matching that artifact exactly.",
    )
    parser.add_argument(
        "--approval-report", default=None, dest="approval_report",
        help="Path to the dry-run JSON artifact being executed. The frozen "
             "candidate set, fingerprints, digests and quarantine date all "
             "come from THIS file — execution never re-derives the set.",
    )
    parser.add_argument(
        "--canary", type=int, default=None,
        help="Act on a deterministic shard-stratified subset of N candidates "
             "from the frozen set. --expected-count must equal N.",
    )
    parser.add_argument(
        "--lock-path", default=None, dest="lock_path",
        help="Release-lock file path (default: the pipeline's .release.lock). "
             "Held from fresh verification through the final postconditions.",
    )
    parser.add_argument(
        "--expected-count", type=int, default=None, dest="expected_count",
        help="The exact orphan count a human approved from a dry-run report.",
    )
    parser.add_argument("--run-date", default=None, dest="run_date")
    return parser


def _resolve_retained_versions(client, args) -> tuple:
    if args.retained_versions:
        return tuple(args.retained_versions)
    from cleanup_old_versions import fetch_all_versions

    rows = fetch_all_versions(client)
    return tuple(
        row["db_version"] for row in rows[: args.keep] if row.get("db_version")
    )


class ApprovalArtifactError(ValueError):
    """The approval artifact cannot authorize an execution."""


def _load_approval_artifact(path, *, expected_count, canary):
    """Validate the dry-run artifact and return its frozen contract.

    Returns ``(candidates, fingerprints, run_date, protected_digest)``.
    Raises ApprovalArtifactError with an operator-readable reason otherwise.
    """
    import re as _re

    from release_safety.blob_inventory import ObjectFingerprint
    from release_safety.orphan_reconcile import hash_set_digest

    try:
        data = json.loads(Path(path).read_text())
    except (OSError, ValueError) as exc:
        raise ApprovalArtifactError(
            f"cannot read approval report {path}: {exc}"
        ) from exc
    if not isinstance(data, dict):
        raise ApprovalArtifactError("approval report is not a JSON object")
    if data.get("blocked_reason"):
        raise ApprovalArtifactError(
            "the approval report is BLOCKED "
            f"({data['blocked_reason']!r}) — a blocked report pins nothing "
            "approvable"
        )

    raw = data.get("candidate_fingerprints")
    if not isinstance(raw, dict) or not raw:
        raise ApprovalArtifactError(
            "approval report carries no candidate_fingerprints — only the "
            "FULL dry-run JSON (written by --json-report) can authorize an "
            "execution"
        )
    fingerprints = {}
    for blob_hash, fp in raw.items():
        if not isinstance(blob_hash, str) or not _re.fullmatch(
            r"[0-9a-f]{64}", blob_hash,
        ):
            raise ApprovalArtifactError(
                f"candidate key must be a 64-char lowercase hex content "
                f"hash, got {blob_hash!r}"
            )
        if (
            not isinstance(fp, dict)
            or not isinstance(fp.get("size"), int)
            or fp["size"] <= 0
            or not isinstance(fp.get("etag"), str)
            or not fp["etag"]
        ):
            raise ApprovalArtifactError(
                f"candidate {blob_hash} has an unproven fingerprint in the "
                "approval report (positive size and non-empty eTag required)"
            )
        fingerprints[blob_hash] = ObjectFingerprint(
            size=fp["size"], etag=fp["etag"],
        )

    candidates = sorted(fingerprints)
    digest = data.get("candidate_digest")
    if digest != hash_set_digest(candidates):
        raise ApprovalArtifactError(
            "candidate_digest does not match the candidate set in the "
            "approval report — the file was edited or corrupted"
        )
    protected_digest = data.get("protected_digest")
    if not (isinstance(protected_digest, str) and len(protected_digest) == 64):
        raise ApprovalArtifactError(
            "approval report has no valid protected_digest"
        )
    run_date = data.get("quarantine_run_date")
    if not (isinstance(run_date, str) and _re.match(r"^\d{4}-\d{2}-\d{2}$", run_date)):
        raise ApprovalArtifactError(
            "approval report has no quarantine_run_date — regenerate the dry "
            "run; execution must not choose its own date"
        )

    act_count = canary if canary is not None else len(candidates)
    if canary is not None and not (0 < canary <= len(candidates)):
        raise ApprovalArtifactError(
            f"--canary {canary} exceeds the artifact's {len(candidates)} "
            "candidate(s)"
        )
    if expected_count != act_count:
        raise ApprovalArtifactError(
            f"--expected-count {expected_count} does not match the "
            f"{'canary size' if canary is not None else 'approved candidate count'} "
            f"of {act_count}"
        )
    return candidates, fingerprints, run_date, protected_digest


def _select_canary_candidates(candidates, count):
    """Choose a deterministic shard-stratified subset of a frozen set.

    Taking the lexicographically first hashes concentrates a 2,000-object
    canary in only the lowest few shards. Round-robin selection exercises
    every populated shard before taking a second object from any shard while
    remaining stable across process and input ordering.
    """
    by_shard = {}
    for blob_hash in sorted(candidates):
        by_shard.setdefault(blob_hash[:2], []).append(blob_hash)
    selected = []
    offset = 0
    while len(selected) < count:
        added = False
        for shard in sorted(by_shard):
            shard_hashes = by_shard[shard]
            if offset < len(shard_hashes):
                selected.append(shard_hashes[offset])
                added = True
                if len(selected) == count:
                    return selected
        if not added:
            break
        offset += 1
    return selected


def _execute_from_artifact(client, args, client_factory) -> int:
    """Quarantine the frozen approved set under the release lock."""
    from release_safety.lock import (
        CorruptLockError,
        LockContentionError,
        StaleLockError,
        acquire_release_lock,
    )
    from release_safety.protected_blobs import compute_protected_blob_set

    try:
        candidates, fingerprints, run_date, _protected_digest = (
            _load_approval_artifact(
                args.approval_report,
                expected_count=args.expected_count,
                canary=args.canary,
            )
        )
    except ApprovalArtifactError as exc:
        print(f"\n[refused] {exc}")
        return EXIT_REFUSED

    act_set = (
        _select_canary_candidates(candidates, args.canary)
        if args.canary is not None else candidates
    )

    lock_path = Path(args.lock_path) if args.lock_path else None
    # The lock raises on context ENTRY (same contract gates.py handles), so
    # the __enter__ must sit inside the try.
    try:
        lock_ctx = acquire_release_lock(
            lock_path, initial_step="reconcile_orphan_blobs --execute",
        )
        lock_ctx.__enter__()
    except (LockContentionError, StaleLockError, CorruptLockError) as exc:
        print(f"\n[refused] release lock unavailable: {exc}")
        return EXIT_ERROR

    try:
        # Fresh protection check INSIDE the lock: a frozen candidate that a
        # newer catalog re-references since approval has identical content
        # (identical fingerprint), so drift detection cannot catch it — the
        # protected-set intersection is the only guard.
        retained = _resolve_retained_versions(client, args)
        try:
            protected = compute_protected_blob_set(
                args.flutter_repo,
                args.dist_dir,
                branch=args.branch,
                supabase_client=client,
                registry_bucket=args.bucket,
                retained_versions=retained,
            )
        except Exception as exc:  # noqa: BLE001 — cannot prove, cannot act.
            print(
                f"\n[refused] fresh protected-set computation failed "
                f"({type(exc).__name__}: {exc}); nothing quarantined."
            )
            return EXIT_ERROR
        if protected.degenerate:
            print(
                f"\n[refused] fresh protected set is degenerate: "
                f"{protected.degenerate_reason}"
            )
            return EXIT_ERROR

        newly_protected = sorted(set(act_set) & protected.protected)
        if newly_protected:
            print(
                f"\n[BLOCKED] {len(newly_protected)} approved candidate(s) "
                "have become protected since the approval and will NOT be "
                "touched:"
            )
            for blob_hash in newly_protected[:10]:
                print(f"    {blob_hash}")
            if len(newly_protected) > 10:
                print(f"    ... and {len(newly_protected) - 10} more")
        to_act = [h for h in act_set if h not in set(newly_protected)]

        moved = failed = 0
        failed_paths = []
        if to_act:
            from cleanup_old_versions import quarantine_orphan_blob_batch

            print(
                f"\nQuarantining {len(to_act)} blob(s) to "
                f"shared/quarantine/{run_date}/ (recoverable for 30 days)..."
            )
            moved, failed, failed_paths = quarantine_orphan_blob_batch(
                client, to_act,
                run_date=run_date,
                source_fingerprints=fingerprints,
                max_workers=args.max_workers,
                max_attempts=args.max_attempts,
                client_factory=client_factory,
                checkpoint_path=Path(args.quarantine_checkpoint),
            )
    finally:
        lock_ctx.__exit__(None, None, None)

    print(
        f"\nExecution summary: {moved} moved, {failed} failed, "
        f"{len(newly_protected)} blocked-as-protected "
        f"(of {len(act_set)} approved)."
    )
    for path in failed_paths[:10]:
        print(f"  failed: {path}")
    return EXIT_OK if failed == 0 and not newly_protected else EXIT_ERROR


def _verify_inventory_parity(client, shards) -> int:
    """Read-only dual read: walker vs RPC over the same shards.

    The walker is the authority; the RPC may only ever agree with it. Any
    divergence — or an unavailable/failing RPC — is a non-zero exit so a
    scheduled parity check cannot quietly rot.
    """
    from release_safety.blob_inventory import (
        RpcInventoryError,
        inventory_detail_blobs,
        inventory_detail_blobs_via_rpc,
    )

    print("Dual-read inventory parity check (read-only)...")
    walker = inventory_detail_blobs(client, shards=shards)
    if not walker.complete:
        print("  PARITY UNPROVABLE: the walker inventory itself is incomplete.")
        return EXIT_ERROR
    try:
        via_rpc = inventory_detail_blobs_via_rpc(client, shards=shards)
    except RpcInventoryError as exc:
        print(f"  PARITY FAILED: RPC path unavailable or invalid: {exc}")
        return EXIT_ERROR

    mismatches = []
    if walker.sizes != via_rpc.sizes:
        only_walker = sorted(set(walker.sizes) - set(via_rpc.sizes))[:5]
        only_rpc = sorted(set(via_rpc.sizes) - set(walker.sizes))[:5]
        mismatches.append(
            f"sizes differ (walker {len(walker.sizes)} vs rpc "
            f"{len(via_rpc.sizes)}; walker-only sample {only_walker}; "
            f"rpc-only sample {only_rpc})"
        )
    if walker.etags != via_rpc.etags:
        mismatches.append("eTags differ")
    if walker.categories != via_rpc.categories:
        mismatches.append(
            f"categories differ ({walker.categories} vs {via_rpc.categories})"
        )
    if mismatches:
        print("  PARITY FAILED:")
        for m in mismatches:
            print(f"    - {m}")
        return EXIT_ERROR
    print(
        f"  PARITY OK: {len(walker.sizes):,} blob(s), "
        f"{walker.total_bytes:,} bytes, identical names/sizes/eTags."
    )
    return EXIT_OK


def main(argv=None, *, client=None) -> int:
    args = build_parser().parse_args(argv)

    if args.execute and args.expected_count is None:
        print(
            "\n[refused] --execute requires --expected-count N.\n"
            "  Run a dry run first, review its exact orphan count, then pass\n"
            "  that number back. This makes the blast radius an explicit,\n"
            "  reviewed decision rather than whatever the scan happened to find."
        )
        return EXIT_REFUSED
    if args.execute and not args.approval_report:
        print(
            "\n[refused] --execute requires --approval-report PATH — the "
            "dry-run JSON artifact\n  (written by --json-report) whose frozen "
            "candidate set, fingerprints and\n  quarantine date this "
            "execution will act on."
        )
        return EXIT_REFUSED

    # A caller-injected client (tests) must never be fanned out across
    # threads; only a real factory can mint one client per worker.
    client_factory = None
    if client is None:
        from supabase_client import get_supabase_client

        try:
            client = get_supabase_client()
        except ValueError as exc:
            print(f"[ERROR] Cannot connect to Supabase: {exc}")
            return EXIT_ERROR
        client_factory = get_supabase_client

    shards = (
        tuple(s.strip() for s in args.shards.split(",") if s.strip())
        if args.shards else HEX_BLOB_SHARDS
    )

    if args.verify_inventory:
        from release_safety.lock import ReleaseLockError, acquire_release_lock

        try:
            with acquire_release_lock(
                Path(args.lock_path) if args.lock_path else None,
                initial_step="verify_storage_inventory_parity",
            ):
                return _verify_inventory_parity(client, shards)
        except ReleaseLockError as exc:
            print(f"  PARITY REFUSED: release lock unavailable: {exc}")
            return EXIT_ERROR

    if args.execute:
        return _execute_from_artifact(client, args, client_factory)
    retained = _resolve_retained_versions(client, args)

    print("=" * 68)
    print("Orphan reconciliation")
    print("=" * 68)
    print(f"  mode:              {'EXECUTE (quarantine)' if args.execute else 'DRY RUN'}")
    print(f"  retained versions: {', '.join(retained) or '(none)'}")
    print(f"  shards to scan:    {len(shards)}")
    print()

    def _progress(done, total, objects):
        if done == total or done % 16 == 0:
            print(f"  inventory: {done}/{total} shard(s), {objects:,} object(s)")

    # Execution must compare the approved count against a fresh storage view.
    # Reusing the dry-run inventory checkpoint would make storage changes
    # invisible and defeat the expected-count safety gate.
    inventory_checkpoint = None
    if not args.execute and args.checkpoint:
        inventory_checkpoint = Path(args.checkpoint)
    elif args.execute and args.checkpoint:
        print("  execute inventory: fresh rescan (dry-run checkpoint ignored)")

    from datetime import datetime, timezone

    report_run_date = (
        args.run_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    )
    report = build_orphan_report(
        client,
        flutter_repo_path=args.flutter_repo,
        dist_dir=args.dist_dir,
        retained_versions=retained,
        branch=args.branch,
        bucket=args.bucket,
        shards=shards,
        max_workers=args.max_workers,
        max_attempts=args.max_attempts,
        client_factory=client_factory,
        checkpoint_path=inventory_checkpoint,
        progress=_progress,
        run_date=report_run_date,
    )

    print()
    print(report.text_report())

    if args.json_report:
        path = Path(args.json_report)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report.to_dict(), indent=2, sort_keys=True))
        print(f"\n  JSON report written to {path}")

    if report.blocked_reason:
        print("\n[refused] Nothing may be acted on — the report is BLOCKED.")
        return EXIT_OK

    print(
        "\nDry run complete. To act on this exact approved set, re-run with:\n"
        f"  --execute --approval-report {args.json_report or '<path from --json-report>'} "
        f"--expected-count {report.orphan_count}"
    )
    if not args.json_report:
        print(
            "  (re-run the dry run with --json-report PATH first — the JSON "
            "artifact IS the approval.)"
        )
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
