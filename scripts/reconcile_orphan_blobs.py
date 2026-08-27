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

    # 2. Only after a human has reviewed that report's exact count:
    scripts/reconcile_orphan_blobs.py ... --execute --expected-count N

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
        "--execute", action="store_true", default=False,
        help="Move the reported orphans to quarantine. Requires "
             "--expected-count matching a completed dry run exactly.",
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
    )

    print()
    print(report.text_report())

    if args.json_report:
        path = Path(args.json_report)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report.to_dict(), indent=2, sort_keys=True))
        print(f"\n  JSON report written to {path}")

    if report.blocked_reason:
        print("\n[refused] Nothing quarantined — the report is BLOCKED.")
        return EXIT_REFUSED if args.execute else EXIT_OK

    if not args.execute:
        print(
            "\nDry run complete. To act on this exact count, re-run with:\n"
            f"  --execute --expected-count {report.orphan_count}"
        )
        return EXIT_OK

    if args.expected_count != report.orphan_count:
        print(
            f"\n[refused] --expected-count {args.expected_count} does not match "
            f"the {report.orphan_count} orphan(s) found now.\n"
            "  Storage changed since the approved dry run, or the wrong count "
            "was supplied. Re-run the dry run and review again."
        )
        return EXIT_REFUSED

    if report.orphan_count == 0:
        print("\nNothing to quarantine.")
        return EXIT_OK

    # Every candidate must carry a proven fingerprint (size + eTag) — the
    # engine verifies each action against these frozen values, so a gap here
    # would silently weaken every downstream proof. Refuse up front instead.
    unproven = sorted(
        h for h, fp in report.candidate_fingerprints.items()
        if fp is None or fp.etag is None
    )
    if len(report.candidate_fingerprints) != report.orphan_count or unproven:
        print(
            f"\n[refused] {len(unproven) or report.orphan_count} candidate(s) "
            "lack a proven source fingerprint (missing eTag). Nothing "
            "quarantined."
        )
        return EXIT_REFUSED

    from cleanup_old_versions import quarantine_orphan_blob_batch
    from datetime import datetime, timezone
    run_date = args.run_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    print(
        f"\nQuarantining {report.orphan_count} blob(s) to "
        f"shared/quarantine/{run_date}/ (recoverable for 30 days)..."
    )
    moved, failed, failed_paths = quarantine_orphan_blob_batch(
        client, report.orphan_hashes,
        run_date=run_date,
        source_fingerprints=report.candidate_fingerprints,
        client_factory=client_factory,
        checkpoint_path=Path(args.quarantine_checkpoint),
    )
    print(f"\nQuarantine complete: {moved} moved, {failed} failed.")
    if failed_paths:
        for path in failed_paths[:10]:
            print(f"  failed: {path}")
    return EXIT_OK if failed == 0 else EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
