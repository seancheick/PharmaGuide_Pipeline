#!/usr/bin/env python3
"""Verify PubMed PMIDs in timing_rules.json and medication_depletions.json.

Extracts every PubMed URL from both data files (regardless of the source's
``source_type`` label — the URL is the ground truth), validates each PMID
exists via NCBI E-utilities, and reports results.

Usage:
    python3 scripts/api_audit/verify_depletion_timing_pmids.py [--live]

Without --live: dry-run (extract PMIDs only, no API calls) — always exit 0.
With --live: validate each PMID against PubMed. This is a GATE and FAILS CLOSED:

    exit 0  — every extracted PMID verified to exist
    exit 1  — a PMID is genuinely absent from PubMed (a ghost reference), or a
              source labelled `pubmed` has no parseable PMID (malformed)
    exit 2  — one or more PMIDs could NOT be verified due to transient failures
              (HTTP 429 / network) after retries — we cannot declare clean

A transient rate-limit is never reported as an invalid PMID: those are two
different states (`unresolved` vs `invalid`), and both keep the gate red so a
flaky network can never masquerade as a passing verification.

Requires NCBI_API_KEY (or PUBMED_API_KEY) in .env — loaded via env_loader.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_ROOT = SCRIPT_DIR.parent
DATA_DIR = SCRIPTS_ROOT / "data"

sys.path.insert(0, str(SCRIPTS_ROOT))
sys.path.insert(0, str(SCRIPT_DIR))

import env_loader  # noqa: E402,F401 — loads .env into os.environ on import

PMID_RE = re.compile(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d+)")

TARGET_FILES = [
    ("timing_rules.json", "timing_rules"),
    ("medication_depletions.json", "depletions"),
]

ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"


# --------------------------------------------------------------------------- #
# Extraction (pure — testable without file IO)
# --------------------------------------------------------------------------- #
def _extract_from_data(data: dict, array_key: str, filename: str) -> list[dict]:
    """Extract PMID records from one already-loaded data object.

    A PubMed URL is extracted from ANY source (the `source_type` label is NOT a
    gate — a real pubmed.ncbi.nlm.nih.gov URL under `source_type: reference`
    must still be verified). A source labelled `pubmed` whose URL yields no PMID
    is flagged as malformed. Non-pubmed sources are ignored.
    """
    results: list[dict] = []
    for entry in data.get(array_key, []):
        entry_id = entry.get("id", "unknown")
        for source in entry.get("sources", []):
            url = source.get("url", "") or ""
            source_type = source.get("source_type")
            match = PMID_RE.search(url)
            if match:
                results.append({
                    "file": filename,
                    "entry_id": entry_id,
                    "pmid": match.group(1),
                    "url": url,
                    "source_type": source_type,
                    "label": source.get("label", ""),
                })
            elif source_type == "pubmed":
                # Labelled a PubMed source but the URL has no parseable PMID.
                results.append({
                    "file": filename,
                    "entry_id": entry_id,
                    "pmid": None,
                    "url": url,
                    "source_type": source_type,
                    "label": source.get("label", ""),
                    "error": "source_type=pubmed but no PMID in URL",
                })
    return results


def extract_pmids(data_file: Path, array_key: str) -> list[dict]:
    with open(data_file) as f:
        data = json.load(f)
    return _extract_from_data(data, array_key, data_file.name)


# --------------------------------------------------------------------------- #
# Network (isolated — monkeypatchable in tests)
# --------------------------------------------------------------------------- #
class TransientVerifyError(Exception):
    """A retryable failure (HTTP 429, network, timeout) — NOT a verdict."""


def _fetch_esummary(ids_str: str, api_key: str, attempts: int = 4) -> str:
    """Fetch esummary XML for a comma-joined id batch, retrying transient errors.

    Raises TransientVerifyError if all attempts fail (429/network). Any other
    exception propagates (treated as transient by the caller too, but retries
    are exhausted here for the known-retryable classes).
    """
    import ssl
    import urllib.error
    import urllib.request

    try:
        ctx = ssl.create_default_context()
    except ssl.SSLError:
        ctx = ssl._create_unverified_context()

    url = f"{ESUMMARY_URL}?db=pubmed&id={ids_str}&retmode=xml"
    if api_key:
        url += f"&api_key={api_key}"

    last_err: Exception | None = None
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "pharmaguide-audit/1.0"}
            )
            with urllib.request.urlopen(req, timeout=20, context=ctx) as resp:
                return resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code == 429:
                retry_after = e.headers.get("Retry-After") if e.headers else None
                delay = float(retry_after) if (retry_after or "").isdigit() else 2.0 * (2 ** attempt)
                time.sleep(min(delay, 30.0))
                continue
            # Non-429 HTTP errors (5xx) are also worth a couple retries.
            if 500 <= e.code < 600:
                time.sleep(2.0 * (2 ** attempt))
                continue
            raise TransientVerifyError(f"HTTP {e.code}") from e
        except Exception as e:  # URLError, socket timeout, SSL, ET issues on read
            last_err = e
            time.sleep(1.0 * (2 ** attempt))
            continue
    raise TransientVerifyError(str(last_err))


def verify_pmids_live(pmid_records: list[dict]) -> list[dict]:
    """Classify each unique PMID as valid / invalid / unresolved.

    - valid       : PubMed returned a record for it
    - invalid     : PubMed answered but the PMID was absent (a ghost reference)
    - unresolved  : we could not reach a verdict (transient 429/network)
    """
    import xml.etree.ElementTree as ET

    # Deterministic order (sorted) — sets iterate nondeterministically.
    unique_pmids = sorted({r["pmid"] for r in pmid_records if r.get("pmid")})
    print(f"Verifying {len(unique_pmids)} unique PMIDs against PubMed...")

    api_key = os.environ.get("NCBI_API_KEY") or os.environ.get("PUBMED_API_KEY", "")
    if not api_key:
        print("  ⚠ no NCBI_API_KEY/PUBMED_API_KEY in env — running keyless "
              "(lower rate limit; transient failures more likely).")

    verdict: dict[str, dict] = {}
    for i in range(0, len(unique_pmids), 10):
        batch = unique_pmids[i:i + 10]
        try:
            xml_data = _fetch_esummary(",".join(batch), api_key)
        except TransientVerifyError as e:
            for pmid in batch:
                verdict[pmid] = {"status": "unresolved", "error": str(e)}
            time.sleep(0.15)
            continue

        try:
            root = ET.fromstring(xml_data)
        except ET.ParseError as e:
            for pmid in batch:
                verdict[pmid] = {"status": "unresolved", "error": f"XML parse: {e}"}
            time.sleep(0.15)
            continue

        found = {}
        for docsum in root.findall(".//DocSum"):
            pid = docsum.find("Id")
            if pid is None or not pid.text:
                continue
            title = ""
            for item in docsum.findall("Item"):
                if item.get("Name") == "Title":
                    title = item.text or ""
                    break
            found[pid.text.strip()] = title
        for pmid in batch:
            if pmid in found:
                verdict[pmid] = {"status": "valid", "title": found[pmid]}
            else:
                verdict[pmid] = {"status": "invalid", "error": "PMID not found in PubMed"}
        time.sleep(0.15)

    for r in pmid_records:
        pmid = r.get("pmid")
        if pmid and pmid in verdict:
            v = verdict[pmid]
            r["status"] = v["status"]
            r["verified"] = (v["status"] == "valid")
            if v.get("title"):
                r["pubmed_title"] = v["title"]
            if v.get("error"):
                r["verify_error"] = v["error"]
    return pmid_records


# --------------------------------------------------------------------------- #
# Exit policy (pure — testable)
# --------------------------------------------------------------------------- #
def _decide_exit(invalid: int, unresolved: int, malformed: int) -> int:
    if invalid or malformed:
        return 1
    if unresolved:
        return 2
    return 0


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify PMIDs in timing/depletion data files")
    parser.add_argument("--live", action="store_true", help="Validate PMIDs against PubMed API (fail-closed gate)")
    args = parser.parse_args(argv)

    all_records: list[dict] = []
    for filename, array_key in TARGET_FILES:
        filepath = DATA_DIR / filename
        if not filepath.exists():
            print(f"SKIP: {filepath} not found")
            continue
        all_records.extend(extract_pmids(filepath, array_key))

    malformed = [r for r in all_records if r.get("pmid") is None]
    unique_pmids = sorted({r["pmid"] for r in all_records if r.get("pmid")})

    print(f"\n{'=' * 60}\nPMID Extraction Summary\n{'=' * 60}")
    by_file: dict[str, list] = {}
    for r in all_records:
        by_file.setdefault(r["file"], []).append(r)
    for fname, records in by_file.items():
        valid = [r for r in records if r.get("pmid")]
        bad = [r for r in records if not r.get("pmid")]
        print(f"\n  {fname}:\n    PubMed URLs: {len(records)}\n    PMIDs extracted: {len(valid)}")
        if bad:
            print(f"    ⚠ malformed pubmed source (no PMID): {len(bad)}")
            for r in bad:
                print(f"      - {r['entry_id']}: {r['url']}")
    print(f"\n  Total PMIDs: {len(unique_pmids)} unique")

    invalid_count = unresolved_count = 0
    if args.live:
        print(f"\n{'=' * 60}\nLive PubMed Verification (fail-closed)\n{'=' * 60}")
        all_records = verify_pmids_live(all_records)
        valid_count = sum(1 for r in all_records if r.get("status") == "valid")
        invalid_count = sum(1 for r in all_records if r.get("status") == "invalid")
        unresolved_count = sum(1 for r in all_records if r.get("status") == "unresolved")
        print(f"\n  valid: {valid_count}   invalid: {invalid_count}   unresolved: {unresolved_count}")
        for label, status in (("Invalid (ghost)", "invalid"), ("Unresolved (transient)", "unresolved")):
            hits = [r for r in all_records if r.get("status") == status]
            if hits:
                print(f"\n  {label}:")
                for r in hits:
                    print(f"    - {r['entry_id']}: PMID {r.get('pmid')} ({r.get('verify_error', '')})")

    report_path = SCRIPTS_ROOT / "reports" / "pmid_verification_timing_depletions.json"
    report_path.parent.mkdir(exist_ok=True)
    with open(report_path, "w") as f:
        json.dump({
            "total_records": len(all_records),
            "unique_pmids": len(unique_pmids),
            "live_verified": args.live,
            "invalid": invalid_count,
            "unresolved": unresolved_count,
            "malformed": len(malformed),
            "records": all_records,
        }, f, indent=2)
    print(f"\n  Report: {report_path}")

    if not args.live:
        return 0  # dry-run is a preview, not a gate
    code = _decide_exit(invalid_count, unresolved_count, len(malformed))
    if code == 1:
        print("\n❌ FAIL: ghost/malformed PMID(s) — data defect.")
    elif code == 2:
        print("\n❌ FAIL (fail-closed): PMID(s) could not be verified (transient). Re-run.")
    else:
        print("\n✅ PASS: all PMIDs verified.")
    return code


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()
