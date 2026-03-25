#!/usr/bin/env python3
"""
ClinicalTrials.gov verification tool for PharmaGuide clinical studies.

What this script does:
  1. Scans backed_clinical_studies.json for NCT IDs in notable_studies, references,
     and references_structured fields.
  2. Verifies each NCT ID against the ClinicalTrials.gov API v2.
  3. Cross-checks study design (interventional / observational) against claimed study_type.
  4. Reports verified NCTs, broken NCTs, study type mismatches, and entries without NCT IDs.

Operator runbook:
  1. Dry-run:
       python3 scripts/api_audit/verify_clinical_trials.py --file scripts/data/backed_clinical_studies.json
  2. Look up a single NCT ID:
       python3 scripts/api_audit/verify_clinical_trials.py --nct NCT03675724
  3. Save report:
       python3 scripts/api_audit/verify_clinical_trials.py --file scripts/data/backed_clinical_studies.json --output /tmp/ct_verify_report.json

API:
  ClinicalTrials.gov API v2 -- free, no key needed.
  Rate limit: self-imposed 0.35s between requests (~2.8 req/s).
"""

import argparse
import json
import re
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import requests

SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_ROOT = SCRIPT_DIR.parent
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

import env_loader  # noqa: F401

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_URL = "https://clinicaltrials.gov/api/v2"
RATE_LIMIT_DELAY = 0.35  # ~2.8 req/s, conservative for public API
DEFAULT_CACHE_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 days
NCT_RE = re.compile(r"NCT\d{8}", re.I)

# Map ClinicalTrials.gov studyType → our study_type vocabulary
CT_STUDY_TYPE_MAP = {
    # Interventional studies
    "INTERVENTIONAL": {
        "RANDOMIZED": "rct",
        "NON_RANDOMIZED": "observational",
        "DEFAULT": "rct",
    },
    # Observational studies
    "OBSERVATIONAL": {
        "DEFAULT": "observational",
    },
    # Expanded access
    "EXPANDED_ACCESS": {
        "DEFAULT": "observational",
    },
}

# Our study_type strength scale (higher = stronger)
STUDY_TYPE_STRENGTH = {
    "in_vitro": 0,
    "animal_study": 1,
    "observational": 2,
    "rct_single": 3,
    "rct": 3,
    "clinical_strain": 3,
    "rct_multiple": 4,
    "meta_analysis": 5,
    "systematic_review": 6,
    "systematic_review_meta": 6,
}

# ---------------------------------------------------------------------------
# ClinicalTrials.gov client
# ---------------------------------------------------------------------------

class ClinicalTrialsClient:
    """Requests-based wrapper around ClinicalTrials.gov API v2.

    Uses the ``requests`` library because ClinicalTrials.gov blocks
    Python's stdlib urllib (TLS fingerprint / connection behaviour).
    """

    def __init__(
        self,
        *,
        timeout_seconds: float = 15.0,
        failure_limit: int = 3,
        cache_path: Path | None = None,
        cache_ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
    ):
        self.timeout_seconds = timeout_seconds
        self.failure_limit = max(1, failure_limit)
        self.cache_path = cache_path
        self.cache_ttl_seconds = max(0, cache_ttl_seconds)
        self._request_count = 0
        self._consecutive_failures = 0
        self.circuit_open = False
        self._cache: dict[str, dict] = {}
        if self.cache_path and self.cache_path.exists():
            try:
                self._cache = json.loads(self.cache_path.read_text())
            except (json.JSONDecodeError, OSError):
                self._cache = {}

    # -- Cache ---------------------------------------------------------------

    def _cache_get(self, key: str) -> dict | None:
        cached = self._cache.get(key)
        if not isinstance(cached, dict):
            return None
        expires_at = cached.get("expires_at")
        if isinstance(expires_at, str):
            try:
                if datetime.fromisoformat(expires_at) <= datetime.now(UTC):
                    self._cache.pop(key, None)
                    return None
            except ValueError:
                self._cache.pop(key, None)
                return None
        return cached.get("payload")

    def _cache_set(self, key: str, payload: dict) -> None:
        self._cache[key] = {
            "payload": payload,
            "expires_at": (
                datetime.now(UTC) + timedelta(seconds=self.cache_ttl_seconds)
            ).isoformat(),
        }

    def save_cache(self) -> None:
        if self.cache_path:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(json.dumps(self._cache, indent=1))

    # -- HTTP ----------------------------------------------------------------

    def _get(self, url: str) -> dict | None:
        if self.circuit_open:
            return None

        cached = self._cache_get(url)
        if cached is not None:
            return cached

        for attempt in range(1, 4):
            try:
                self._request_count += 1
                time.sleep(RATE_LIMIT_DELAY)
                resp = requests.get(
                    url,
                    headers={"Accept": "application/json"},
                    timeout=self.timeout_seconds,
                )
                if resp.status_code == 404:
                    not_found = {"_not_found": True}
                    self._cache_set(url, not_found)
                    self._consecutive_failures = 0
                    return not_found
                if resp.status_code in (429, 500, 502, 503, 504):
                    wait = RATE_LIMIT_DELAY * (2 ** attempt)
                    print(f"  [RETRY {attempt}/3] HTTP {resp.status_code}, waiting {wait:.1f}s...", file=sys.stderr)
                    time.sleep(wait)
                    continue
                if resp.status_code != 200:
                    print(f"  [ERROR] HTTP {resp.status_code} for {url}", file=sys.stderr)
                    return None
                data = resp.json()
                self._consecutive_failures = 0
                self._cache_set(url, data)
                return data
            except (requests.ConnectionError, requests.Timeout, OSError) as e:
                self._consecutive_failures += 1
                if self._consecutive_failures >= self.failure_limit:
                    print(f"  [CIRCUIT OPEN] {self._consecutive_failures} consecutive failures", file=sys.stderr)
                    self.circuit_open = True
                    return None
                wait = RATE_LIMIT_DELAY * (2 ** attempt)
                print(f"  [RETRY {attempt}/3] {e}, waiting {wait:.1f}s...", file=sys.stderr)
                time.sleep(wait)
        return None

    # -- Public API ----------------------------------------------------------

    def get_study(self, nct_id: str) -> dict | None:
        """Fetch a study by NCT ID.

        Returns:
          - the study payload when found
          - {"_not_found": True} when the NCT ID does not exist
          - None on transport / API failure
        """
        nct_id = nct_id.upper().strip()
        url = f"{BASE_URL}/studies/{nct_id}"
        data = self._get(url)
        if data is None:
            return None
        return data

    def search_studies(self, query: str, *, max_results: int = 5) -> list[dict]:
        """Search for studies by keyword. Returns list of study objects."""
        from urllib.parse import quote
        encoded = quote(query, safe="")
        url = f"{BASE_URL}/studies?query.term={encoded}&pageSize={max_results}"
        data = self._get(url)
        if data is None:
            return []
        return data.get("studies", [])


# ---------------------------------------------------------------------------
# NCT extraction from clinical study entries
# ---------------------------------------------------------------------------

def extract_nct_ids(entry: dict) -> set[str]:
    """Extract all NCT IDs from a backed_clinical_studies entry."""
    nct_ids: set[str] = set()

    # Search notable_studies text
    notable = entry.get("notable_studies", "")
    if isinstance(notable, str):
        nct_ids.update(NCT_RE.findall(notable))

    # Search references_structured
    for ref in entry.get("references_structured", []):
        url = ref.get("url", "")
        if isinstance(url, str):
            nct_ids.update(NCT_RE.findall(url))
        title = ref.get("title", "")
        if isinstance(title, str):
            nct_ids.update(NCT_RE.findall(title))
        notes = ref.get("notes", "")
        if isinstance(notes, str):
            nct_ids.update(NCT_RE.findall(notes))

    # Search scientific_references
    for ref in entry.get("scientific_references", []):
        if isinstance(ref, str):
            nct_ids.update(NCT_RE.findall(ref))

    # Search notes field
    notes = entry.get("notes", "")
    if isinstance(notes, str):
        nct_ids.update(NCT_RE.findall(notes))

    return {nct.upper() for nct in nct_ids}


def resolve_nct_ids_from_pubmed(entries: list[dict]) -> dict[str, set[str]]:
    """Resolve NCT IDs from PubMed DataBankList for entries with PMIDs.

    Queries PubMed efetch in batches, extracts NCT IDs from the
    AccessionNumberList of each article's DataBankList.

    Returns: {entry_id: {NCT IDs}} mapping.
    """
    import xml.etree.ElementTree as ET

    try:
        from pubmed_client import PubMedClient
    except ImportError:
        print("  [WARN] pubmed_client not available — skipping PubMed NCT resolution", file=sys.stderr)
        return {}

    # Collect PMID → entry_id mapping
    pmid_to_entries: dict[str, list[str]] = {}
    for entry in entries:
        eid = entry.get("id", "")
        for ref in entry.get("references_structured", []):
            pmid = ref.get("pmid")
            if pmid:
                pmid_to_entries.setdefault(str(pmid), []).append(eid)

    if not pmid_to_entries:
        return {}

    all_pmids = list(pmid_to_entries.keys())
    print(f"  Resolving NCT IDs from {len(all_pmids)} PMIDs via PubMed...", file=sys.stderr)

    client = PubMedClient()
    entry_ncts: dict[str, set[str]] = {}

    # Batch in groups of 50
    for i in range(0, len(all_pmids), 50):
        batch = all_pmids[i:i + 50]
        try:
            xml_text = client.efetch(batch)
        except Exception:
            continue
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            continue
        for article in root.findall(".//PubmedArticle"):
            pmid = (article.findtext(".//MedlineCitation/PMID") or "").strip()
            accessions = article.findall(
                ".//DataBankList/DataBank/AccessionNumberList/AccessionNumber"
            )
            nct_ids = {a.text.upper() for a in accessions if a.text and a.text.upper().startswith("NCT")}
            if nct_ids and pmid in pmid_to_entries:
                for eid in pmid_to_entries[pmid]:
                    entry_ncts.setdefault(eid, set()).update(nct_ids)

    resolved_count = sum(len(v) for v in entry_ncts.values())
    print(f"  Resolved {resolved_count} NCT IDs for {len(entry_ncts)} entries from PubMed", file=sys.stderr)
    return entry_ncts


def _extract_study_info(study_data: dict) -> dict[str, Any]:
    """Extract relevant fields from a ClinicalTrials.gov API v2 response."""
    protocol = study_data.get("protocolSection", {})
    ident = protocol.get("identificationModule", {})
    status_mod = protocol.get("statusModule", {})
    design_mod = protocol.get("designModule", {})
    conditions_mod = protocol.get("conditionsModule", {})
    desc_mod = protocol.get("descriptionModule", {})

    study_type = design_mod.get("studyType", "UNKNOWN")
    design_info = design_mod.get("designInfo", {})
    allocation = design_info.get("allocation", "")

    # Determine our equivalent study_type
    type_map = CT_STUDY_TYPE_MAP.get(study_type, {})
    if allocation and allocation in type_map:
        our_type = type_map[allocation]
    else:
        our_type = type_map.get("DEFAULT", "observational")

    # Enrollment
    enrollment_info = design_mod.get("enrollmentInfo", {})
    enrollment = enrollment_info.get("count")

    return {
        "nct_id": ident.get("nctId", ""),
        "title": ident.get("officialTitle") or ident.get("briefTitle", ""),
        "status": status_mod.get("overallStatus", "UNKNOWN"),
        "study_type_raw": study_type,
        "allocation": allocation,
        "our_study_type": our_type,
        "phases": design_mod.get("phases", []),
        "enrollment": enrollment,
        "conditions": conditions_mod.get("conditions", []),
        "brief_summary": desc_mod.get("briefSummary", ""),
        "start_date": status_mod.get("startDateStruct", {}).get("date", ""),
        "completion_date": status_mod.get("completionDateStruct", {}).get("date", ""),
    }


# ---------------------------------------------------------------------------
# Verification logic
# ---------------------------------------------------------------------------

def verify_clinical_file(
    data: dict,
    client: ClinicalTrialsClient,
    *,
    list_key: str = "backed_clinical_studies",
    resolve_from_pubmed: bool = False,
) -> dict:
    """Verify NCT IDs in backed_clinical_studies.json.

    If resolve_from_pubmed is True, also queries PubMed to discover NCT IDs
    that are registered in article DataBankLists but not cited in our text.
    """
    entries = data.get(list_key, [])
    results: dict[str, Any] = {
        "verified": [],           # NCT exists and study type consistent
        "broken_nct": [],         # NCT ID not found in ClinicalTrials.gov
        "study_type_mismatch": [],  # NCT exists but study type disagrees
        "no_nct_ids": [],         # Entry has no NCT IDs (informational)
        "pubmed_resolved": [],    # NCT IDs discovered via PubMed
        "errors": [],             # API errors
    }

    # Optionally resolve NCT IDs from PubMed article metadata
    pubmed_ncts: dict[str, set[str]] = {}
    if resolve_from_pubmed:
        pubmed_ncts = resolve_nct_ids_from_pubmed(entries)

    total = len(entries)
    nct_seen: dict[str, dict] = {}  # NCT → study info (dedup API calls)

    for i, entry in enumerate(entries):
        eid = entry.get("id", f"entry_{i}")
        name = entry.get("standard_name", "")
        claimed_type = entry.get("study_type", "")

        nct_ids = extract_nct_ids(entry)

        # Merge PubMed-resolved NCT IDs
        pm_ncts = pubmed_ncts.get(eid, set())
        newly_resolved = pm_ncts - nct_ids
        if newly_resolved:
            results["pubmed_resolved"].append({
                "id": eid, "name": name, "nct_ids": sorted(newly_resolved),
            })
            nct_ids = nct_ids | pm_ncts

        if not nct_ids:
            results["no_nct_ids"].append({"id": eid, "name": name, "study_type": claimed_type})
            continue

        entry_verified = []
        entry_broken = []
        entry_mismatches = []

        for nct_id in sorted(nct_ids):
            # Dedup: reuse already-fetched study info
            if nct_id in nct_seen:
                info = nct_seen[nct_id]
            else:
                study = client.get_study(nct_id)
                if study is None:
                    results["errors"].append({"id": eid, "nct_id": nct_id, "error": "api_error"})
                    continue
                if study.get("_not_found"):
                    info = None
                else:
                    info = _extract_study_info(study)
                nct_seen[nct_id] = info

            if info is None:
                entry_broken.append(nct_id)
                continue

            # Cross-check study type
            ct_type = info["our_study_type"]
            claimed_strength = STUDY_TYPE_STRENGTH.get(claimed_type, -1)
            ct_strength = STUDY_TYPE_STRENGTH.get(ct_type, -1)

            record = {
                "nct_id": nct_id,
                "title": info["title"],
                "status": info["status"],
                "ct_study_type": ct_type,
                "ct_study_type_raw": info["study_type_raw"],
                "ct_allocation": info["allocation"],
                "ct_phases": info["phases"],
                "ct_enrollment": info["enrollment"],
                "ct_conditions": info["conditions"][:5],
            }

            # Mismatch logic:
            # - rct_multiple / systematic_review_meta entries are EXPECTED to
            #   have individual NCTs that are each single RCTs. That's not a
            #   mismatch — the aggregate study_type is correctly ranked higher.
            # - Only flag when an individual NCT's design CONTRADICTS the claim:
            #   e.g., claiming rct but the trial is observational.
            is_aggregate = claimed_type in (
                "rct_multiple", "systematic_review_meta", "systematic_review", "meta_analysis"
            )
            if is_aggregate:
                # For aggregate types, mismatch only if CT.gov says observational
                # (i.e., it's not even a trial, let alone an RCT)
                if ct_type == "observational" and claimed_type.startswith("rct"):
                    entry_mismatches.append({
                        "id": eid, "name": name,
                        "claimed_study_type": claimed_type,
                        "claimed_strength": claimed_strength,
                        "ct_strength": ct_strength,
                        **record,
                    })
                else:
                    entry_verified.append({"id": eid, "name": name, **record})
            elif claimed_strength > ct_strength and ct_strength >= 0:
                # Single-trial claim is stronger than what CT.gov says
                entry_mismatches.append({
                    "id": eid, "name": name,
                    "claimed_study_type": claimed_type,
                    "claimed_strength": claimed_strength,
                    "ct_strength": ct_strength,
                    **record,
                })
            else:
                entry_verified.append({"id": eid, "name": name, **record})

        results["verified"].extend(entry_verified)
        for nct_id in entry_broken:
            results["broken_nct"].append({"id": eid, "name": name, "nct_id": nct_id})
        results["study_type_mismatch"].extend(entry_mismatches)

        done = i + 1
        if done % 10 == 0 or done == total:
            print(f"  [{done}/{total}] {name} ({len(nct_ids)} NCTs)", file=sys.stderr)

    results["total_entries"] = total
    results["total_nct_ids"] = len(nct_seen)
    results["api_requests"] = client._request_count
    return results


# ---------------------------------------------------------------------------
# Single NCT lookup
# ---------------------------------------------------------------------------

def lookup_nct(nct_id: str, client: ClinicalTrialsClient) -> None:
    """Look up and display info for a single NCT ID."""
    nct_id = nct_id.upper().strip()
    study = client.get_study(nct_id)
    if study is None or study.get("_not_found"):
        print(f"NCT ID not found: {nct_id}")
        return

    info = _extract_study_info(study)
    print(f"\n  NCT ID:      {info['nct_id']}")
    print(f"  Title:       {info['title']}")
    print(f"  Status:      {info['status']}")
    print(f"  Study Type:  {info['study_type_raw']} (→ {info['our_study_type']})")
    print(f"  Allocation:  {info['allocation'] or 'N/A'}")
    print(f"  Phases:      {', '.join(info['phases']) or 'N/A'}")
    print(f"  Enrollment:  {info['enrollment'] or 'N/A'}")
    print(f"  Conditions:  {', '.join(info['conditions'][:5]) or 'N/A'}")
    print(f"  Start:       {info['start_date'] or 'N/A'}")
    print(f"  Completion:  {info['completion_date'] or 'N/A'}")
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print_summary(results: dict) -> None:
    print("\n" + "=" * 60)
    print("ClinicalTrials.gov Verification Report")
    print("=" * 60)
    print(f"  Total entries scanned:    {results['total_entries']}")
    print(f"  Unique NCT IDs found:     {results['total_nct_ids']}")
    print(f"  API requests made:        {results['api_requests']}")
    print()
    print(f"  Verified NCT references:  {len(results['verified'])}")
    print(f"  Broken NCT IDs:           {len(results['broken_nct'])}")
    print(f"  Study type mismatches:    {len(results['study_type_mismatch'])}")
    print(f"  NCTs resolved via PubMed: {len(results.get('pubmed_resolved', []))}")
    print(f"  Entries without NCT IDs:  {len(results['no_nct_ids'])}")
    print(f"  API errors:               {len(results['errors'])}")

    if results.get("pubmed_resolved"):
        print(f"\n  --- NCT IDs Resolved via PubMed ({len(results['pubmed_resolved'])}) ---")
        for r in results["pubmed_resolved"]:
            print(f"    {r['id']:40s}  {', '.join(r['nct_ids'])}")

    if results["broken_nct"]:
        print(f"\n  --- Broken NCT IDs ({len(results['broken_nct'])}) ---")
        for r in results["broken_nct"]:
            print(f"    {r['id']:40s}  {r['nct_id']}")

    if results["study_type_mismatch"]:
        print(f"\n  --- Study Type Mismatches ({len(results['study_type_mismatch'])}) ---")
        for r in results["study_type_mismatch"]:
            print(f"    {r['id']:40s}  claimed={r['claimed_study_type']:20s}  CT.gov={r['ct_study_type']:15s}  {r['nct_id']}")

    if results["errors"]:
        print(f"\n  --- API Errors ({len(results['errors'])}) ---")
        for r in results["errors"]:
            print(f"    {r['id']:40s}  {r['nct_id']}  {r['error']}")

    print("=" * 60 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify NCT IDs in PharmaGuide clinical studies")
    parser.add_argument("--file", type=Path, help="Path to backed_clinical_studies.json")
    parser.add_argument("--list-key", default="backed_clinical_studies", help="Top-level list key (default: backed_clinical_studies)")
    parser.add_argument("--nct", type=str, help="Look up a single NCT ID")
    parser.add_argument("--resolve-from-pubmed", action="store_true",
                        help="Also resolve NCT IDs from PubMed article DataBankLists")
    parser.add_argument("--output", type=Path, help="Save JSON report to file")
    parser.add_argument("--cache-dir", type=Path, default=SCRIPTS_ROOT / ".cache", help="Cache directory")
    args = parser.parse_args()

    cache_path = args.cache_dir / "clinical_trials_cache.json"

    client = ClinicalTrialsClient(
        cache_path=cache_path,
        cache_ttl_seconds=DEFAULT_CACHE_TTL_SECONDS,
    )

    try:
        if args.nct:
            lookup_nct(args.nct, client)
            return

        if not args.file:
            parser.error("Either --file or --nct is required")

        data = json.loads(args.file.read_text())
        results = verify_clinical_file(
            data, client,
            list_key=args.list_key,
            resolve_from_pubmed=args.resolve_from_pubmed,
        )
        _print_summary(results)

        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(results, indent=2))
            print(f"  Report saved to {args.output}")
    finally:
        client.save_cache()


if __name__ == "__main__":
    main()
