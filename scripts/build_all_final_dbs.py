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


def main():
    parser = argparse.ArgumentParser(description="Auto-discover and build PharmaGuide final DB")
    parser.add_argument("--scan-dir", default=str(Path(__file__).parent),
                        help="Directory to scan for output_*_enriched/scored folders")
    parser.add_argument("--output-dir", default=None,
                        help="Output directory (default: <scan-dir>/final_db_<timestamp>)")
    parser.add_argument("--require-all-paired", action="store_true",
                        help="Fail if any enriched/scored folder is unpaired")
    args = parser.parse_args()

    enriched_dirs, scored_dirs, paired, enriched_only, scored_only = discover_pairs(args.scan_dir)

    if not paired:
        logger.error("No enriched/scored pairs found in %s", args.scan_dir)
        sys.exit(1)

    if args.require_all_paired and (enriched_only or scored_only):
        logger.error("Unpaired folders found and --require-all-paired is set. Aborting.")
        sys.exit(1)

    logger.info("Found %d brand pairs: %s", len(paired), paired)

    if args.output_dir:
        output_dir = args.output_dir
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = os.path.join(args.scan_dir, f"final_db_{ts}")

    script_dir = str(Path(__file__).parent)
    result = build_final_db(enriched_dirs, scored_dirs, output_dir, script_dir)

    print(f"\n{'='*60}")
    print(f"Build complete: {result['product_count']} products, {result['error_count']} errors")
    print(f"DB:     {result['db_path']} ({result['db_size_mb']} MB)")
    print(f"Audit:  {result.get('audit_path', 'N/A')}")
    print(f"Brands: {', '.join(paired)}")
    print(f"{'='*60}")

    if result["error_count"] > 0:
        logger.warning("Build completed with %d errors — check export_audit_report.json", result["error_count"])
        sys.exit(1)


if __name__ == "__main__":
    main()
