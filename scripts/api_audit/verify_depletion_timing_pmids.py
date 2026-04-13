#!/usr/bin/env python3
"""Verify PubMed PMIDs in timing_rules.json and medication_depletions.json.

Extracts all PubMed URLs from both data files, validates each PMID exists via
NCBI E-utilities, and reports results. Uses the existing pubmed_client.py
infrastructure.

Usage:
    python3 scripts/api_audit/verify_depletion_timing_pmids.py [--live]

Without --live, runs in dry-run mode (extracts PMIDs only, no API calls).
With --live, validates each PMID against PubMed (requires NCBI_API_KEY in .env).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_ROOT = SCRIPT_DIR.parent
DATA_DIR = SCRIPTS_ROOT / "data"

sys.path.insert(0, str(SCRIPTS_ROOT))
sys.path.insert(0, str(SCRIPT_DIR))

PMID_RE = re.compile(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d+)")

TARGET_FILES = [
    ("timing_rules.json", "timing_rules"),
    ("medication_depletions.json", "depletions"),
]


def extract_pmids(data_file: Path, array_key: str) -> list[dict]:
    """Extract all PubMed PMIDs from a data file."""
    with open(data_file) as f:
        data = json.load(f)

    results = []
    for entry in data.get(array_key, []):
        entry_id = entry.get("id", "unknown")
        for source in entry.get("sources", []):
            if source.get("source_type") != "pubmed":
                continue
            url = source.get("url", "")
            match = PMID_RE.search(url)
            if match:
                results.append({
                    "file": data_file.name,
                    "entry_id": entry_id,
                    "pmid": match.group(1),
                    "url": url,
                    "label": source.get("label", ""),
                })
            else:
                results.append({
                    "file": data_file.name,
                    "entry_id": entry_id,
                    "pmid": None,
                    "url": url,
                    "label": source.get("label", ""),
                    "error": "Could not extract PMID from URL",
                })
    return results


def verify_pmids_live(pmid_records: list[dict]) -> list[dict]:
    """Validate PMIDs against PubMed E-utilities API (stdlib only)."""
    import ssl
    import time
    import urllib.request
    import xml.etree.ElementTree as ET

    # macOS SSL fallback
    try:
        ctx = ssl.create_default_context()
    except ssl.SSLError:
        ctx = ssl._create_unverified_context()

    unique_pmids = list({r["pmid"] for r in pmid_records if r.get("pmid")})
    print(f"Verifying {len(unique_pmids)} unique PMIDs against PubMed...")

    api_key = os.environ.get("NCBI_API_KEY") or os.environ.get("PUBMED_API_KEY", "")
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

    verified = {}
    # Batch in groups of 10
    for i in range(0, len(unique_pmids), 10):
        batch = unique_pmids[i:i+10]
        ids_str = ",".join(batch)
        url = f"{base_url}?db=pubmed&id={ids_str}&retmode=xml"
        if api_key:
            url += f"&api_key={api_key}"

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "pharmaguide-audit/1.0"})
            with urllib.request.urlopen(req, timeout=20, context=ctx) as resp:
                xml_data = resp.read().decode("utf-8")
            root = ET.fromstring(xml_data)

            found_ids = set()
            for docsum in root.findall(".//DocSum"):
                pmid_elem = docsum.find("Id")
                if pmid_elem is not None and pmid_elem.text:
                    found_ids.add(pmid_elem.text.strip())
                    title = ""
                    for item in docsum.findall("Item"):
                        if item.get("Name") == "Title":
                            title = item.text or ""
                            break
                    verified[pmid_elem.text.strip()] = {"valid": True, "title": title}

            for pmid in batch:
                if pmid not in found_ids:
                    verified[pmid] = {"valid": False, "error": "PMID not found in PubMed"}

        except Exception as e:
            for pmid in batch:
                if pmid not in verified:
                    verified[pmid] = {"valid": False, "error": str(e)}

        time.sleep(0.12)  # Rate limit

    # Annotate records
    for r in pmid_records:
        pmid = r.get("pmid")
        if pmid and pmid in verified:
            r["verified"] = verified[pmid]["valid"]
            if verified[pmid].get("title"):
                r["pubmed_title"] = verified[pmid]["title"]
            if verified[pmid].get("error"):
                r["verify_error"] = verified[pmid]["error"]

    return pmid_records


def main():
    parser = argparse.ArgumentParser(description="Verify PMIDs in timing/depletion data files")
    parser.add_argument("--live", action="store_true", help="Validate PMIDs against PubMed API")
    args = parser.parse_args()

    all_records = []
    for filename, array_key in TARGET_FILES:
        filepath = DATA_DIR / filename
        if not filepath.exists():
            print(f"SKIP: {filepath} not found")
            continue
        records = extract_pmids(filepath, array_key)
        all_records.extend(records)

    print(f"\n{'='*60}")
    print(f"PMID Extraction Summary")
    print(f"{'='*60}")

    by_file = {}
    for r in all_records:
        by_file.setdefault(r["file"], []).append(r)

    total_pmids = 0
    for fname, records in by_file.items():
        valid = [r for r in records if r.get("pmid")]
        invalid = [r for r in records if not r.get("pmid")]
        total_pmids += len(valid)
        print(f"\n  {fname}:")
        print(f"    PubMed sources: {len(records)}")
        print(f"    Valid PMIDs extracted: {len(valid)}")
        if invalid:
            print(f"    ⚠ Could not extract PMID: {len(invalid)}")
            for r in invalid:
                print(f"      - {r['entry_id']}: {r['url']}")

    unique_pmids = {r["pmid"] for r in all_records if r.get("pmid")}
    print(f"\n  Total PMIDs: {total_pmids} ({len(unique_pmids)} unique)")

    if args.live:
        print(f"\n{'='*60}")
        print("Live PubMed Verification")
        print(f"{'='*60}")
        all_records = verify_pmids_live(all_records)

        valid_count = sum(1 for r in all_records if r.get("verified") is True)
        invalid_count = sum(1 for r in all_records if r.get("verified") is False)
        print(f"\n  Verified valid: {valid_count}")
        print(f"  Verified invalid: {invalid_count}")

        if invalid_count:
            print("\n  Invalid PMIDs:")
            for r in all_records:
                if r.get("verified") is False:
                    print(f"    - {r['entry_id']}: PMID {r.get('pmid')} ({r.get('verify_error', 'not found')})")

    # Write report
    report_path = SCRIPTS_ROOT / "reports" / "pmid_verification_timing_depletions.json"
    report_path.parent.mkdir(exist_ok=True)
    with open(report_path, "w") as f:
        json.dump({
            "total_records": len(all_records),
            "unique_pmids": len(unique_pmids),
            "live_verified": args.live,
            "records": all_records,
        }, f, indent=2)
    print(f"\n  Report: {report_path}")


if __name__ == "__main__":
    main()
