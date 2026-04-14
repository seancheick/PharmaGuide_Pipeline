#!/usr/bin/env python3
"""
build_unii_cache.py — Build local UNII lookup cache from OpenFDA bulk download.

Downloads the full FDA UNII substance registry (172K entries) and builds a
compact JSON cache for offline ingredient identity resolution. The enricher
and verify_unii.py can use this cache to avoid live GSRS API calls.

Usage:
    python3 scripts/api_audit/build_unii_cache.py [--refresh]

    --refresh   Re-download bulk data (default: use cached zip)

Output:
    scripts/data/fda_unii_cache.json

Source: FDA OpenFDA bulk download → /other/unii
"""

import json
import os
import sys
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data"
ZIP_PATH = DATA_DIR / "fda_unii_bulk.json.zip"
RAW_PATH = DATA_DIR / "other-unii-0001-of-0001.json"
OUTPUT_PATH = DATA_DIR / "fda_unii_cache.json"

DOWNLOAD_URL = "https://download.open.fda.gov/other/unii/other-unii-0001-of-0001.json.zip"


def download_bulk(force: bool = False):
    """Download UNII bulk data zip from OpenFDA."""
    if ZIP_PATH.exists() and not force:
        print(f"Using cached zip: {ZIP_PATH}")
        return
    print(f"Downloading UNII bulk data from {DOWNLOAD_URL}...")
    urllib.request.urlretrieve(DOWNLOAD_URL, ZIP_PATH)
    print(f"Downloaded: {ZIP_PATH.stat().st_size / 1024:.0f} KB")


def extract_zip():
    """Extract the JSON from the zip."""
    if RAW_PATH.exists():
        print(f"Already extracted: {RAW_PATH}")
        return
    print("Extracting...")
    with zipfile.ZipFile(ZIP_PATH, "r") as zf:
        zf.extractall(DATA_DIR)
    print(f"Extracted: {RAW_PATH.stat().st_size / (1024*1024):.1f} MB")


def build_cache():
    """Build the compact lookup cache from raw UNII data."""
    print("Building cache...")
    with open(RAW_PATH) as f:
        data = json.load(f)

    results = data.get("results", [])
    print(f"Total UNII records: {len(results)}")

    # name (lowercase) → UNII code
    name_to_unii = {}
    # UNII code → canonical name
    unii_to_name = {}

    for rec in results:
        name = (rec.get("substance_name") or "").strip()
        unii = (rec.get("unii") or "").strip()
        if not name or not unii:
            continue
        name_to_unii[name.lower()] = unii
        unii_to_name[unii] = name

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    output = {
        "_metadata": {
            "schema_version": "1.0.0",
            "source": "FDA OpenFDA UNII bulk download (/other/unii)",
            "source_url": DOWNLOAD_URL,
            "last_updated": now,
            "total_substances": len(name_to_unii),
            "total_uniis": len(unii_to_name),
            "description": (
                "Offline UNII substance registry. "
                "name_to_unii: lowercased substance name → UNII code. "
                "unii_to_name: UNII code → canonical substance name."
            ),
        },
        "name_to_unii": name_to_unii,
        "unii_to_name": unii_to_name,
    }

    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, separators=(",", ":"))

    size_mb = OUTPUT_PATH.stat().st_size / (1024 * 1024)
    print(f"Cache written: {OUTPUT_PATH} ({size_mb:.1f} MB)")
    print(f"Substances: {len(name_to_unii)}, UNIIs: {len(unii_to_name)}")

    # Clean up raw file (keep zip for faster refresh)
    if RAW_PATH.exists():
        RAW_PATH.unlink()
        print(f"Cleaned up: {RAW_PATH}")


def main():
    refresh = "--refresh" in sys.argv
    download_bulk(force=refresh)
    extract_zip()
    build_cache()

    # Quick validation
    with open(OUTPUT_PATH) as f:
        cache = json.load(f)
    n2u = cache["name_to_unii"]
    test_lookups = [
        ("ascorbic acid", "PQ6CK8PD0R"),
        ("cholecalciferol", "1C6V77QF41"),
        ("melatonin", "JL5DK93RCL"),
        ("caffeine", "3G6A5W338E"),
    ]
    print("\nValidation:")
    for name, expected_unii in test_lookups:
        actual = n2u.get(name)
        status = "PASS" if actual == expected_unii else f"FAIL (got {actual})"
        print(f"  {name}: {status}")


if __name__ == "__main__":
    main()
