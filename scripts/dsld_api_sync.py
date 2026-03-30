#!/usr/bin/env python3
"""CLI tool for syncing DSLD label data via the NIH API."""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from dsld_api_client import DSLDApiClient, load_dsld_config, normalize_api_label  # noqa: F401

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------

__version__ = "0.1.0"

# Keys excluded from parity comparison (provenance differs by design).
_PARITY_IGNORE_KEYS = frozenset({"_source", "src"})


# ---------------------------------------------------------------------------
# parity_check
# ---------------------------------------------------------------------------


def parity_check(api_label: dict, reference_label: dict) -> dict:
    """Compare *api_label* against *reference_label* and return a report.

    Keys listed in :data:`_PARITY_IGNORE_KEYS` (``_source``, ``src``) are
    excluded from the comparison because they differ by design between
    API-fetched and manually-downloaded labels.

    Returns a dict with:
      - ``keys_only_in_api``
      - ``keys_only_in_reference``
      - ``type_mismatches``
      - ``value_mismatches``
      - ``nested_diffs``
      - ``identical_keys``
      - ``parity_score`` (0.0 -- 1.0)
    """
    api_keys = set(api_label.keys()) - _PARITY_IGNORE_KEYS
    ref_keys = set(reference_label.keys()) - _PARITY_IGNORE_KEYS

    keys_only_in_api = sorted(api_keys - ref_keys)
    keys_only_in_reference = sorted(ref_keys - api_keys)
    common_keys = sorted(api_keys & ref_keys)

    type_mismatches: dict[str, dict[str, str]] = {}
    value_mismatches: dict[str, dict[str, Any]] = {}
    nested_diffs: dict[str, dict[str, Any]] = {}
    identical_keys: list[str] = []

    for key in common_keys:
        api_val = api_label[key]
        ref_val = reference_label[key]

        api_type = type(api_val).__name__
        ref_type = type(ref_val).__name__

        if api_type != ref_type:
            type_mismatches[key] = {"api": api_type, "reference": ref_type}
            continue

        # Nested structures: compare types and key sets of first element
        if isinstance(api_val, list) and isinstance(ref_val, list):
            if api_val == ref_val:
                identical_keys.append(key)
            elif api_val and ref_val and isinstance(api_val[0], dict) and isinstance(ref_val[0], dict):
                api_first_keys = sorted(api_val[0].keys())
                ref_first_keys = sorted(ref_val[0].keys())
                if api_first_keys != ref_first_keys or len(api_val) != len(ref_val):
                    nested_diffs[key] = {
                        "api_first_keys": api_first_keys,
                        "reference_first_keys": ref_first_keys,
                        "api_length": len(api_val),
                        "reference_length": len(ref_val),
                    }
                else:
                    # Same structure but possibly different values
                    if api_val == ref_val:
                        identical_keys.append(key)
                    else:
                        nested_diffs[key] = {
                            "api_first_keys": api_first_keys,
                            "reference_first_keys": ref_first_keys,
                            "api_length": len(api_val),
                            "reference_length": len(ref_val),
                            "note": "same structure, different values",
                        }
            else:
                value_mismatches[key] = {"api": api_val, "reference": ref_val}
            continue

        if isinstance(api_val, dict) and isinstance(ref_val, dict):
            if api_val == ref_val:
                identical_keys.append(key)
            else:
                api_d_keys = sorted(api_val.keys())
                ref_d_keys = sorted(ref_val.keys())
                nested_diffs[key] = {
                    "api_keys": api_d_keys,
                    "reference_keys": ref_d_keys,
                }
            continue

        # Scalar comparison
        if api_val == ref_val:
            identical_keys.append(key)
        else:
            value_mismatches[key] = {"api": api_val, "reference": ref_val}

    # Parity score: fraction of common keys that are identical
    total_keys = len(common_keys) + len(keys_only_in_api) + len(keys_only_in_reference)
    if total_keys == 0:
        score = 1.0
    else:
        score = len(identical_keys) / total_keys

    return {
        "keys_only_in_api": keys_only_in_api,
        "keys_only_in_reference": keys_only_in_reference,
        "type_mismatches": type_mismatches,
        "value_mismatches": value_mismatches,
        "nested_diffs": nested_diffs,
        "identical_keys": identical_keys,
        "parity_score": round(score, 4),
    }


# ---------------------------------------------------------------------------
# write_raw_label
# ---------------------------------------------------------------------------


def write_raw_label(label: dict, output_dir: str | Path, *, snapshot: bool = False) -> Path:
    """Write a normalized label to ``{output_dir}/{dsld_id}.json``.

    Uses compact JSON (no indent, ``ensure_ascii=False``) to match manual
    download files.  When *snapshot* is True, files are written under a
    timestamped ``_snapshots/`` subdirectory.

    Returns the path to the written file.
    """
    dsld_id = label.get("id")
    if dsld_id is None:
        raise ValueError("Label is missing 'id' — cannot write")

    out = Path(output_dir)
    if snapshot:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        out = out / "_snapshots" / ts

    out.mkdir(parents=True, exist_ok=True)
    file_path = out / f"{dsld_id}.json"
    file_path.write_text(
        json.dumps(label, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    return file_path


# ---------------------------------------------------------------------------
# CLI helpers
# ---------------------------------------------------------------------------


def _print_label_summary(label: dict) -> None:
    """Print a one-line summary of a label."""
    print(f"  ID: {label.get('id')}  |  {label.get('fullName', '?')}  |  brand={label.get('brandName', '?')}")


def _print_parity_report(report: dict) -> None:
    """Pretty-print a parity report."""
    print(f"\n  Parity score: {report['parity_score']:.2%}")
    if report["keys_only_in_api"]:
        print(f"  Keys only in API:       {report['keys_only_in_api']}")
    if report["keys_only_in_reference"]:
        print(f"  Keys only in reference: {report['keys_only_in_reference']}")
    if report["type_mismatches"]:
        print(f"  Type mismatches:        {len(report['type_mismatches'])}")
        for k, v in report["type_mismatches"].items():
            print(f"    {k}: api={v['api']}  ref={v['reference']}")
    if report["value_mismatches"]:
        print(f"  Value mismatches:       {len(report['value_mismatches'])}")
        for k, v in report["value_mismatches"].items():
            api_repr = repr(v["api"])[:80]
            ref_repr = repr(v["reference"])[:80]
            print(f"    {k}: api={api_repr}  ref={ref_repr}")
    if report["nested_diffs"]:
        print(f"  Nested diffs:           {len(report['nested_diffs'])}")
        for k, v in report["nested_diffs"].items():
            print(f"    {k}: {v}")
    print(f"  Identical keys:         {len(report['identical_keys'])}")


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------


def _cmd_probe(args: argparse.Namespace) -> int:
    """Handle the ``probe`` subcommand."""
    client = DSLDApiClient()
    print(f"Fetching label {args.id} ...")
    label = client.fetch_label(args.id)
    _print_label_summary(label)

    if args.reference:
        ref_path = Path(args.reference)
        if not ref_path.exists():
            print(f"ERROR: reference file not found: {ref_path}", file=sys.stderr)
            return 1
        ref_label = json.loads(ref_path.read_text(encoding="utf-8"))
        report = parity_check(label, ref_label)
        _print_parity_report(report)
        if report["parity_score"] < 1.0:
            print("\nParity check FAILED.")
            return 1
        print("\nParity check PASSED.")
    return 0


def _cmd_sync_brand(args: argparse.Namespace) -> int:
    """Handle the ``sync-brand`` subcommand."""
    client = DSLDApiClient()
    print(f"Searching brand: {args.brand} ...")
    results = client.search_brand(args.brand)

    # The browse-labels endpoint may return a list or {"data": [...]}.
    items: list = results if isinstance(results, list) else results.get("data", results.get("list", []))
    if not items:
        print("No labels found for that brand.")
        return 0

    ids = [item["id"] for item in items if "id" in item]
    print(f"Found {len(ids)} label(s). Fetching ...")
    written = 0
    for dsld_id in ids:
        try:
            label = client.fetch_label(dsld_id)
            path = write_raw_label(label, args.output_dir, snapshot=args.snapshot)
            print(f"  wrote {path}")
            written += 1
        except Exception as exc:
            logger.warning("Failed to fetch label %s: %s", dsld_id, exc)
            print(f"  SKIP {dsld_id}: {exc}", file=sys.stderr)

    print(f"\nDone. Wrote {written}/{len(ids)} labels to {args.output_dir}")
    return 0


def _cmd_refresh_ids(args: argparse.Namespace) -> int:
    """Handle the ``refresh-ids`` subcommand."""
    client = DSLDApiClient()
    written = 0
    for dsld_id in args.ids:
        try:
            label = client.fetch_label(dsld_id)
            path = write_raw_label(label, args.output_dir, snapshot=args.snapshot)
            print(f"  wrote {path}")
            written += 1
        except Exception as exc:
            logger.warning("Failed to fetch label %s: %s", dsld_id, exc)
            print(f"  SKIP {dsld_id}: {exc}", file=sys.stderr)

    print(f"\nDone. Wrote {written}/{len(args.ids)} labels to {args.output_dir}")
    return 0


def _cmd_verify_db(args: argparse.Namespace) -> int:
    """Handle the ``verify-db`` subcommand.

    Samples *N* files from *input_dir*, fetches the same IDs from the API,
    runs :func:`parity_check` on each, and prints an aggregate report.
    **Never writes to input_dir.**
    """
    input_dir = Path(args.input_dir)
    if not input_dir.is_dir():
        print(f"ERROR: {input_dir} is not a directory", file=sys.stderr)
        return 1

    json_files = sorted(input_dir.glob("*.json"))
    if not json_files:
        print("No JSON files found in input directory.")
        return 0

    sample_size = min(args.sample_size, len(json_files))
    sampled = random.sample(json_files, sample_size)

    client = DSLDApiClient()
    scores: list[float] = []
    failures: list[str] = []

    print(f"Verifying {sample_size} labels from {input_dir} ...")
    for file_path in sampled:
        try:
            ref_label = json.loads(file_path.read_text(encoding="utf-8"))
            dsld_id = ref_label.get("id")
            if dsld_id is None:
                # Try filename
                dsld_id = file_path.stem
            api_label = client.fetch_label(dsld_id)
            report = parity_check(api_label, ref_label)
            scores.append(report["parity_score"])
            status = "PASS" if report["parity_score"] >= 1.0 else "DRIFT"
            print(f"  {file_path.name}: {status} (score={report['parity_score']:.2%})")
            if report["value_mismatches"]:
                for k in sorted(report["value_mismatches"].keys()):
                    print(f"    mismatch: {k}")
        except Exception as exc:
            failures.append(f"{file_path.name}: {exc}")
            print(f"  {file_path.name}: ERROR — {exc}", file=sys.stderr)

    print(f"\n--- Aggregate ---")
    if scores:
        avg = sum(scores) / len(scores)
        perfect = sum(1 for s in scores if s >= 1.0)
        print(f"  Checked:  {len(scores)}")
        print(f"  Perfect:  {perfect}/{len(scores)}")
        print(f"  Avg score: {avg:.2%}")
    if failures:
        print(f"  Errors:   {len(failures)}")
        for f in failures:
            print(f"    {f}")
    return 0


def _cmd_sync_query(args: argparse.Namespace) -> int:
    """Handle the ``sync-query`` subcommand."""
    client = DSLDApiClient()
    print(f"Searching: {args.query} (limit={args.limit}) ...")
    results = client.search_query(args.query, limit=args.limit)

    items: list = results if isinstance(results, list) else results.get("data", results.get("list", []))
    if not items:
        print("No labels found for that query.")
        return 0

    ids = [item["id"] for item in items if "id" in item]
    print(f"Found {len(ids)} label(s). Fetching ...")
    written = 0
    for dsld_id in ids:
        try:
            label = client.fetch_label(dsld_id)
            path = write_raw_label(label, args.output_dir, snapshot=args.snapshot)
            print(f"  wrote {path}")
            written += 1
        except Exception as exc:
            logger.warning("Failed to fetch label %s: %s", dsld_id, exc)
            print(f"  SKIP {dsld_id}: {exc}", file=sys.stderr)

    print(f"\nDone. Wrote {written}/{len(ids)} labels to {args.output_dir}")
    return 0


def _cmd_check_version(args: argparse.Namespace) -> int:
    """Handle the ``check-version`` subcommand."""
    print(f"dsld_api_sync v{__version__}")
    print("Testing DSLD API connectivity ...")
    try:
        client = DSLDApiClient()
        label = client.fetch_label(13418)
        print(f"  OK — fetched label 13418: {label.get('fullName', '?')}")
        return 0
    except Exception as exc:
        print(f"  FAILED — {exc}", file=sys.stderr)
        return 1


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser with subcommands."""
    parser = argparse.ArgumentParser(
        prog="dsld_api_sync",
        description="CLI tool for syncing DSLD label data via the NIH API.",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # -- probe ---------------------------------------------------------------
    p_probe = subparsers.add_parser("probe", help="Fetch and inspect a single label")
    p_probe.add_argument("--id", required=True, type=int, help="DSLD label ID to fetch")
    p_probe.add_argument("--reference", type=str, default=None, help="Path to reference JSON for parity check")

    # -- sync-brand ----------------------------------------------------------
    p_brand = subparsers.add_parser("sync-brand", help="Sync all labels for a brand")
    p_brand.add_argument("--brand", required=True, help="Brand name to search")
    p_brand.add_argument("--output-dir", required=True, help="Directory to write labels")
    p_brand.add_argument("--snapshot", action="store_true", help="Write to timestamped snapshot subdir")

    # -- refresh-ids ---------------------------------------------------------
    p_refresh = subparsers.add_parser("refresh-ids", help="Re-fetch specific label IDs")
    p_refresh.add_argument("--ids", required=True, nargs="+", type=int, help="DSLD label IDs to fetch")
    p_refresh.add_argument("--output-dir", required=True, help="Directory to write labels")
    p_refresh.add_argument("--snapshot", action="store_true", help="Write to timestamped snapshot subdir")

    # -- verify-db -----------------------------------------------------------
    p_verify = subparsers.add_parser("verify-db", help="Sample-verify local labels against API")
    p_verify.add_argument("--input-dir", required=True, help="Directory with local JSON labels")
    p_verify.add_argument("--sample-size", type=int, default=10, help="Number of labels to sample (default 10)")

    # -- sync-query ----------------------------------------------------------
    p_query = subparsers.add_parser("sync-query", help="Sync labels matching a query")
    p_query.add_argument("--query", required=True, help="Search query")
    p_query.add_argument("--output-dir", required=True, help="Directory to write labels")
    p_query.add_argument("--limit", type=int, default=100, help="Max results (default 100)")
    p_query.add_argument("--snapshot", action="store_true", help="Write to timestamped snapshot subdir")

    # -- check-version -------------------------------------------------------
    subparsers.add_parser("check-version", help="Print version and test API connectivity")

    return parser


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and dispatch to the correct subcommand."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(name)s: %(message)s")
    else:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    handlers = {
        "probe": _cmd_probe,
        "sync-brand": _cmd_sync_brand,
        "refresh-ids": _cmd_refresh_ids,
        "verify-db": _cmd_verify_db,
        "sync-query": _cmd_sync_query,
        "check-version": _cmd_check_version,
    }

    handler = handlers.get(args.command)
    if handler is None:
        parser.print_help()
        return 1
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
