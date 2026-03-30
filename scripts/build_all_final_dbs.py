#!/usr/bin/env python3
"""
PharmaGuide Auto-Discovery Final DB Builder
============================================
Auto-discovers matching enriched/scored output folders and runs
build_final_db.py for all of them in a single export.

Usage:
    python build_all_final_dbs.py                         # scan current dir
    python build_all_final_dbs.py --scan-dir /data        # scan specific dir
    python build_all_final_dbs.py --output-dir /tmp/db    # custom output

Discovery rules:
    Enriched dirs match: output_*_enriched/enriched
    Scored dirs match:   output_*_scored/scored

The script pairs enriched/scored folders by brand prefix
(e.g. output_Thorne-2-17-26_enriched ↔ output_Thorne-2-17-26_scored).
Unpaired folders are reported but do not block the build.
"""

import argparse
import hashlib
import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).parent))

from assemble_final_db_release import discover_pair_output_dirs, merge_pair_outputs
from build_final_db import build_final_db


def extract_brand_prefix(dirname: str) -> str:
    """Extract brand prefix from output directory name.

    output_Thorne-2-17-26_enriched -> Thorne-2-17-26
    output_Nature-Made-2-17-26-L827_scored -> Nature-Made-2-17-26-L827
    """
    match = re.match(r"^output_(.+?)_(enriched|scored)$", dirname)
    return match.group(1) if match else ""


def discover_pairs(scan_dir: str):
    """Find enriched/scored folder pairs by brand prefix."""
    enriched_dirs = {}
    scored_dirs = {}

    for entry in sorted(os.listdir(scan_dir)):
        full = os.path.join(scan_dir, entry)
        if not os.path.isdir(full):
            continue

        prefix = extract_brand_prefix(entry)
        if not prefix:
            continue

        if entry.endswith("_enriched"):
            sub = os.path.join(full, "enriched")
            if os.path.isdir(sub):
                enriched_dirs[prefix] = sub
            else:
                logger.warning("Enriched dir missing 'enriched' subfolder: %s", full)
        elif entry.endswith("_scored"):
            sub = os.path.join(full, "scored")
            if os.path.isdir(sub):
                scored_dirs[prefix] = sub
            else:
                logger.warning("Scored dir missing 'scored' subfolder: %s", full)

    paired = sorted(set(enriched_dirs.keys()) & set(scored_dirs.keys()))
    enriched_only = sorted(set(enriched_dirs.keys()) - set(scored_dirs.keys()))
    scored_only = sorted(set(scored_dirs.keys()) - set(enriched_dirs.keys()))

    if enriched_only:
        logger.warning("Enriched without scored: %s", enriched_only)
    if scored_only:
        logger.warning("Scored without enriched: %s", scored_only)

    return (
        [enriched_dirs[p] for p in paired],
        [scored_dirs[p] for p in paired],
        paired,
        enriched_only,
        scored_only,
    )


def _matches_any(prefix: str, patterns) -> bool:
    normalized = prefix.lower()
    return any(pattern.lower() in normalized for pattern in patterns)


def filter_pairs(enriched_dirs, scored_dirs, paired, include_patterns, exclude_patterns):
    """Filter discovered pairs by optional include/exclude substrings."""
    selected = []
    for enriched_dir, scored_dir, prefix in zip(enriched_dirs, scored_dirs, paired):
        if include_patterns and not _matches_any(prefix, include_patterns):
            continue
        if exclude_patterns and _matches_any(prefix, exclude_patterns):
            continue
        selected.append((enriched_dir, scored_dir, prefix))

    return (
        [item[0] for item in selected],
        [item[1] for item in selected],
        [item[2] for item in selected],
    )


def filter_pairs_by_prefixes(enriched_dirs, scored_dirs, paired, prefixes):
    """Filter discovered pairs by an explicit set of pair prefixes."""
    selected = []
    for enriched_dir, scored_dir, prefix in zip(enriched_dirs, scored_dirs, paired):
        if prefix in prefixes:
            selected.append((enriched_dir, scored_dir, prefix))

    return (
        [item[0] for item in selected],
        [item[1] for item in selected],
        [item[2] for item in selected],
    )


def compute_directory_fingerprint(directory: str) -> str:
    """Hash JSON file names, sizes, and mtimes for change detection."""
    entries = []
    if not os.path.isdir(directory):
        return ""

    root = Path(directory)
    for path in sorted(root.rglob("*.json")):
        stat = path.stat()
        entries.append(f"{path.relative_to(root)}|{stat.st_size}|{stat.st_mtime_ns}")

    digest = hashlib.sha256()
    digest.update("\n".join(entries).encode("utf-8"))
    return digest.hexdigest()


def compute_pair_state(enriched_dirs, scored_dirs, paired):
    state = {}
    for enriched_dir, scored_dir, prefix in zip(enriched_dirs, scored_dirs, paired):
        enriched_fingerprint = compute_directory_fingerprint(enriched_dir)
        scored_fingerprint = compute_directory_fingerprint(scored_dir)
        combined = hashlib.sha256(
            f"{enriched_fingerprint}|{scored_fingerprint}".encode("utf-8")
        ).hexdigest()
        state[prefix] = {
            "enriched_dir": enriched_dir,
            "scored_dir": scored_dir,
            "enriched_fingerprint": enriched_fingerprint,
            "scored_fingerprint": scored_fingerprint,
            "combined_fingerprint": combined,
        }
    return state


def load_state(path):
    if not path or not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_state_file(path):
    data = load_state(path)
    if not data:
        return {}
    if "pairs" in data:
        return data.get("pairs", {})
    return data


def load_change_journal(path, since_cursor=None):
    if not path or not os.path.exists(path):
        return set(), since_cursor

    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    entries = raw.get("entries", []) if isinstance(raw, dict) else raw
    changed_prefixes = set()
    latest_cursor = since_cursor

    for entry in entries:
        if not isinstance(entry, dict):
            continue

        prefix = entry.get("prefix") or entry.get("brand_prefix") or entry.get("pair_prefix")
        cursor = entry.get("changed_at") or entry.get("timestamp") or entry.get("detected_at")
        if not prefix or not cursor:
            continue

        if since_cursor and cursor <= since_cursor:
            continue

        changed_prefixes.add(prefix)
        if latest_cursor is None or cursor > latest_cursor:
            latest_cursor = cursor

    return changed_prefixes, latest_cursor


def save_state_file(path, pairs_state, metadata=None):
    if not path:
        return
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pairs": pairs_state,
    }
    if metadata:
        payload.update(metadata)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)


def filter_changed_pairs(enriched_dirs, scored_dirs, paired, current_state, previous_state):
    selected = []
    for enriched_dir, scored_dir, prefix in zip(enriched_dirs, scored_dirs, paired):
        current = current_state.get(prefix, {})
        previous = previous_state.get(prefix, {})
        if current.get("combined_fingerprint") != previous.get("combined_fingerprint"):
            selected.append((enriched_dir, scored_dir, prefix))

    return (
        [item[0] for item in selected],
        [item[1] for item in selected],
        [item[2] for item in selected],
    )


def build_pair_output_dir(output_root, prefix):
    safe_prefix = re.sub(r"[^A-Za-z0-9._-]+", "-", prefix).strip("-")
    safe_prefix = re.sub(r"-{2,}", "-", safe_prefix)
    return str(Path(output_root) / safe_prefix)


def assemble_release_artifact(per_pair_output_root: str, output_dir: str):
    input_dirs = discover_pair_output_dirs(per_pair_output_root)
    if not input_dirs:
        raise FileNotFoundError(
            f"No per-pair build outputs found under {per_pair_output_root}"
        )
    return merge_pair_outputs(input_dirs, output_dir)


def main():
    parser = argparse.ArgumentParser(description="Auto-discover and build PharmaGuide final DB")
    parser.add_argument("--scan-dir", default=str(Path(__file__).parent),
                        help="Directory to scan for output_*_enriched/scored folders")
    parser.add_argument("--output-dir", default=None,
                        help="Output directory (default: <scan-dir>/final_db_<timestamp>)")
    parser.add_argument("--require-all-paired", action="store_true",
                        help="Fail if any enriched/scored folder is unpaired")
    parser.add_argument("--include-prefix", action="append", default=[],
                        help="Case-insensitive substring filter for brand prefixes to include (repeatable)")
    parser.add_argument("--exclude-prefix", action="append", default=[],
                        help="Case-insensitive substring filter for brand prefixes to exclude (repeatable)")
    parser.add_argument("--state-file", default=None,
                        help="Optional JSON state file for pair fingerprints")
    parser.add_argument("--changed-only", action="store_true",
                        help="Only build pairs whose enriched/scored fingerprints changed vs --state-file")
    parser.add_argument("--change-journal", default=None,
                        help="Optional JSON journal of changed pair prefixes from upstream ingestion")
    parser.add_argument("--journal-since", default=None,
                        help="Only consider change-journal entries after this ISO timestamp/cursor")
    parser.add_argument("--per-pair-output-root", default=None,
                        help="Build one output directory per selected brand pair under this root")
    parser.add_argument("--assemble-release-output", default=None,
                        help="After per-pair builds, assemble a full release artifact from all outputs under --per-pair-output-root")
    parser.add_argument("--plan-only", action="store_true",
                        help="Print selected pairs and exit without building")
    args = parser.parse_args()

    if args.assemble_release_output and not args.per_pair_output_root:
        logger.error("--assemble-release-output requires --per-pair-output-root.")
        sys.exit(1)
    if args.changed_only and args.change_journal:
        logger.error("--changed-only and --change-journal are mutually exclusive. Choose one change source.")
        sys.exit(1)

    enriched_dirs, scored_dirs, paired, enriched_only, scored_only = discover_pairs(args.scan_dir)

    if not paired:
        logger.error("No enriched/scored pairs found in %s", args.scan_dir)
        sys.exit(1)

    if args.require_all_paired and (enriched_only or scored_only):
        logger.error("Unpaired folders found and --require-all-paired is set. Aborting.")
        sys.exit(1)

    enriched_dirs, scored_dirs, paired = filter_pairs(
        enriched_dirs,
        scored_dirs,
        paired,
        include_patterns=args.include_prefix,
        exclude_patterns=args.exclude_prefix,
    )

    if not paired:
        logger.error("No brand pairs matched the include/exclude filters.")
        sys.exit(1)

    current_state = compute_pair_state(enriched_dirs, scored_dirs, paired)
    persisted_state = load_state(args.state_file)
    previous_state = persisted_state.get("pairs", persisted_state)
    journal_cursor = persisted_state.get("journal_cursor") if isinstance(persisted_state, dict) else None
    selected_journal_cursor = journal_cursor

    if args.changed_only:
        if not args.per_pair_output_root and not args.plan_only:
            logger.error("--changed-only requires --per-pair-output-root or --plan-only to avoid partial combined builds.")
            sys.exit(1)
        enriched_dirs, scored_dirs, paired = filter_changed_pairs(
            enriched_dirs,
            scored_dirs,
            paired,
            current_state=current_state,
            previous_state=previous_state,
        )
    elif args.change_journal:
        since_cursor = args.journal_since or journal_cursor
        changed_prefixes, selected_journal_cursor = load_change_journal(
            args.change_journal,
            since_cursor=since_cursor,
        )
        if changed_prefixes:
            enriched_dirs, scored_dirs, paired = filter_pairs_by_prefixes(
                enriched_dirs,
                scored_dirs,
                paired,
                changed_prefixes,
            )
        else:
            enriched_dirs, scored_dirs, paired = [], [], []

    if not paired:
        logger.info("No selected brand pairs require a build.")
        save_state_file(
            args.state_file,
            current_state,
            metadata={"journal_cursor": selected_journal_cursor} if selected_journal_cursor else None,
        )
        sys.exit(0)

    logger.info("Selected %d brand pairs: %s", len(paired), paired)

    if args.plan_only:
        print(json.dumps({
            "selected_pairs": paired,
            "changed_only": args.changed_only,
            "change_journal": args.change_journal,
            "journal_cursor": selected_journal_cursor,
            "state_file": args.state_file,
        }, indent=2))
        save_state_file(
            args.state_file,
            current_state,
            metadata={"journal_cursor": selected_journal_cursor} if selected_journal_cursor else None,
        )
        sys.exit(0)

    if args.output_dir:
        output_dir = args.output_dir
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = os.path.join(args.scan_dir, f"final_db_{ts}")

    script_dir = str(Path(__file__).parent)
    if args.per_pair_output_root:
        per_pair_results = []
        failed = False
        for enriched_dir, scored_dir, prefix in zip(enriched_dirs, scored_dirs, paired):
            pair_output_dir = build_pair_output_dir(args.per_pair_output_root, prefix)
            logger.info("Building pair %s -> %s", prefix, pair_output_dir)
            result = build_final_db([enriched_dir], [scored_dir], pair_output_dir, script_dir)
            per_pair_results.append({
                "prefix": prefix,
                "output_dir": pair_output_dir,
                "product_count": result["product_count"],
                "error_count": result["error_count"],
                "db_path": result["db_path"],
                "audit_path": result.get("audit_path"),
            })
            if result["error_count"] > 0:
                failed = True

        print(f"\n{'='*60}")
        print(f"Per-pair build complete: {len(per_pair_results)} outputs")
        for item in per_pair_results:
            print(f"{item['prefix']}: {item['product_count']} products, {item['error_count']} errors")
        print(f"{'='*60}")

        if failed:
            save_state_file(
                args.state_file,
                current_state,
                metadata={"journal_cursor": selected_journal_cursor} if selected_journal_cursor else None,
            )
            sys.exit(1)

        if args.assemble_release_output:
            release_result = assemble_release_artifact(
                args.per_pair_output_root,
                args.assemble_release_output,
            )
            print(f"\n{'='*60}")
            print(
                "Release assembled: "
                f"{release_result['product_count']} products, "
                f"{release_result['detail_blob_count']} detail blobs"
            )
            print(f"DB:     {release_result['db_path']}")
            print(f"Index:  {release_result['detail_index_path']}")
            print(f"Manifest: {release_result['manifest_path']}")
            print(f"{'='*60}")

        save_state_file(
            args.state_file,
            current_state,
            metadata={"journal_cursor": selected_journal_cursor} if selected_journal_cursor else None,
        )
        return

    result = build_final_db(enriched_dirs, scored_dirs, output_dir, script_dir)

    print(f"\n{'='*60}")
    print(f"Build complete: {result['product_count']} products, {result['error_count']} errors")
    print(f"DB:     {result['db_path']} ({result['db_size_mb']} MB)")
    print(f"Audit:  {result.get('audit_path', 'N/A')}")
    print(f"Brands: {', '.join(paired)}")
    print(f"{'='*60}")

    save_state_file(
        args.state_file,
        current_state,
        metadata={"journal_cursor": selected_journal_cursor} if selected_journal_cursor else None,
    )

    if result["error_count"] > 0:
        logger.warning("Build completed with %d errors — check export_audit_report.json", result["error_count"])
        sys.exit(1)


if __name__ == "__main__":
    main()
