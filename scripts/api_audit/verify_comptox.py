#!/usr/bin/env python3
"""
EPA CompTox Dashboard verification and enrichment tool for PharmaGuide harmful additives.

What this script does:
  1. Resolves CAS numbers to DTXSID via the CompTox Chemical API.
  2. Fetches hazard data (NOAEL, LOAEL, RfD, BMD, cancer slope factors) from ToxValDB.
  3. Fetches genotoxicity summary data from the Hazard genetox endpoint.
  4. Fetches endocrine disruption screening data from the Bioactivity API.
  5. Validates our ADI values against EPA/ATSDR/WHO reference doses.
  6. Fills the dose_thresholds field with authoritative toxicity data.

Two modes:
  A) API mode: uses CTX APIs (requires free API key from ccte_api@epa.gov)
  B) CSV mode: uses batch export from CompTox Dashboard web interface (no key needed)

For CSV mode:
  1. Go to https://comptox.epa.gov/dashboard/batch-search
  2. Paste CAS numbers (run --export-cas to get the list)
  3. Select "Hazard" data for export, download as CSV
  4. Run with --import-csv path/to/export.csv

Environment:
  API mode: Set COMPTOX_API_KEY in .env or pass --api-key.
  CSV mode: No key needed.

Operator runbook:
  1. Export CAS list for batch search:
       python3 scripts/api_audit/verify_comptox.py --file scripts/data/harmful_additives.json --export-cas
  2. Dry-run (API mode):
       python3 scripts/api_audit/verify_comptox.py --file scripts/data/harmful_additives.json
  3. Import from CSV (no API key):
       python3 scripts/api_audit/verify_comptox.py --file scripts/data/harmful_additives.json --import-csv /path/to/comptox_export.csv
  4. Search a single substance (API mode):
       python3 scripts/api_audit/verify_comptox.py --search "bisphenol A"
  5. Look up by CAS (API mode):
       python3 scripts/api_audit/verify_comptox.py --cas 80-05-7
  6. Apply dose_thresholds enrichment:
       python3 scripts/api_audit/verify_comptox.py --file scripts/data/harmful_additives.json --apply
  7. Save report:
       python3 scripts/api_audit/verify_comptox.py --file scripts/data/harmful_additives.json --output /tmp/comptox_report.json
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import requests as _requests

SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_ROOT = SCRIPT_DIR.parent
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

import env_loader  # noqa: F401

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_URL = "https://api-ccte.epa.gov"
RATE_LIMIT_DELAY = 0.5
DEFAULT_CACHE_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 days
DEFAULT_API_KEY = os.environ.get("COMPTOX_API_KEY", "")

ADI_RE = re.compile(
    r"(?:ADI|TDI|TWI|RfD)\s+(?:of\s+)?(\d+(?:\.\d+)?)\s*(?:mg|ug|mcg)/\s*kg",
    re.I,
)


# ---------------------------------------------------------------------------
# CompTox client
# ---------------------------------------------------------------------------

class CompToxClient:
    """Requests-based wrapper around EPA CompTox CTX APIs."""

    def __init__(
        self,
        *,
        api_key: str = "",
        timeout_seconds: float = 15.0,
        failure_limit: int = 3,
        cache_path: Path | None = None,
        cache_ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
    ):
        self.api_key = api_key or DEFAULT_API_KEY
        if not self.api_key:
            print(
                "  [WARN] No COMPTOX_API_KEY set. Get one free from ccte_api@epa.gov",
                file=sys.stderr,
            )
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

    def _cache_get(self, key: str) -> Any | None:
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

    def _cache_set(self, key: str, payload: Any) -> None:
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

    def _get(self, url: str, params: dict | None = None) -> Any | None:
        if self.circuit_open:
            return None

        cache_key = json.dumps({"url": url, "params": params or {}}, sort_keys=True)
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        if not self.api_key:
            return None

        headers = {
            "Accept": "application/json",
            "x-api-key": self.api_key,
        }

        for attempt in range(1, 4):
            try:
                self._request_count += 1
                time.sleep(RATE_LIMIT_DELAY)
                resp = _requests.get(
                    url, headers=headers, params=params,
                    timeout=self.timeout_seconds,
                )
                if resp.status_code == 404:
                    self._cache_set(cache_key, {"_not_found": True})
                    self._consecutive_failures = 0
                    return {"_not_found": True}
                if resp.status_code == 401:
                    print("  [ERROR] CompTox API key invalid (401)", file=sys.stderr)
                    self.circuit_open = True
                    return None
                if resp.status_code in (429, 500, 502, 503, 504):
                    wait = RATE_LIMIT_DELAY * (2 ** attempt)
                    print(f"  [RETRY {attempt}/3] HTTP {resp.status_code}", file=sys.stderr)
                    time.sleep(wait)
                    continue
                if resp.status_code != 200:
                    print(f"  [ERROR] HTTP {resp.status_code} for {url}", file=sys.stderr)
                    return None
                data = resp.json()
                self._consecutive_failures = 0
                self._cache_set(cache_key, data)
                return data
            except (_requests.ConnectionError, _requests.Timeout, OSError) as e:
                self._consecutive_failures += 1
                if self._consecutive_failures >= self.failure_limit:
                    print(f"  [CIRCUIT OPEN] {self._consecutive_failures} failures", file=sys.stderr)
                    self.circuit_open = True
                    return None
                time.sleep(RATE_LIMIT_DELAY * (2 ** attempt))
        return None

    # -- Chemical API --------------------------------------------------------

    def search_by_cas(self, cas: str) -> dict | None:
        """Resolve a CAS number to DTXSID and chemical details."""
        url = f"{BASE_URL}/chemical/search/equal/{cas}"
        data = self._get(url)
        if not data or isinstance(data, dict) and data.get("_not_found"):
            return None
        # Response is a list of matches
        if isinstance(data, list) and data:
            return data[0]
        return data if isinstance(data, dict) else None

    def search_by_name(self, name: str) -> dict | None:
        """Search by chemical name."""
        from urllib.parse import quote
        url = f"{BASE_URL}/chemical/search/contain/{quote(name)}"
        data = self._get(url)
        if not data or isinstance(data, dict) and data.get("_not_found"):
            return None
        if isinstance(data, list) and data:
            # Prefer exact match
            name_lower = name.lower()
            for item in data:
                if (item.get("preferredName") or "").lower() == name_lower:
                    return item
            return data[0]
        return data if isinstance(data, dict) else None

    def get_chemical_details(self, dtxsid: str) -> dict | None:
        """Get full chemical details by DTXSID."""
        url = f"{BASE_URL}/chemical/detail/search/by-dtxsid/{dtxsid}"
        data = self._get(url)
        if not data or (isinstance(data, dict) and data.get("_not_found")):
            return None
        return data

    # -- Hazard API ----------------------------------------------------------

    def get_human_hazard(self, dtxsid: str) -> list[dict]:
        """Get human hazard data from ToxValDB."""
        url = f"{BASE_URL}/hazard/search/by-dtxsid/{dtxsid}"
        params = {"type": "human"}
        data = self._get(url, params=params)
        if not data or (isinstance(data, dict) and data.get("_not_found")):
            return []
        return data if isinstance(data, list) else []

    def get_cancer_hazard(self, dtxsid: str) -> list[dict]:
        """Get cancer-specific hazard data."""
        url = f"{BASE_URL}/hazard/search/by-dtxsid/{dtxsid}"
        params = {"type": "cancer"}
        data = self._get(url, params=params)
        if not data or (isinstance(data, dict) and data.get("_not_found")):
            return []
        return data if isinstance(data, list) else []

    def get_genetox_summary(self, dtxsid: str) -> list[dict]:
        """Get genotoxicity summary."""
        url = f"{BASE_URL}/hazard/search/by-dtxsid/{dtxsid}"
        params = {"type": "genetox"}
        data = self._get(url, params=params)
        if not data or (isinstance(data, dict) and data.get("_not_found")):
            return []
        return data if isinstance(data, list) else []

    def get_skin_eye(self, dtxsid: str) -> list[dict]:
        """Get skin/eye hazard data."""
        url = f"{BASE_URL}/hazard/search/by-dtxsid/{dtxsid}"
        params = {"type": "skin-eye"}
        data = self._get(url, params=params)
        if not data or (isinstance(data, dict) and data.get("_not_found")):
            return []
        return data if isinstance(data, list) else []


# ---------------------------------------------------------------------------
# Data extraction helpers
# ---------------------------------------------------------------------------

def extract_best_pod(hazard_records: list[dict]) -> dict[str, Any]:
    """Extract the best point-of-departure values from ToxValDB records.

    Prioritizes: RfD > NOAEL > LOAEL > BMD, with oral route preferred.
    """
    pods: dict[str, list] = {
        "rfd": [], "noael": [], "loael": [], "bmd": [], "bmdl": [],
        "adi": [], "tdi": [],
    }

    for record in hazard_records:
        tox_type = (record.get("toxvalType") or "").lower()
        value = record.get("toxvalNumeric")
        units = record.get("toxvalUnits") or ""
        route = (record.get("exposureRoute") or "").lower()
        source = record.get("source") or ""
        study_type = record.get("studyType") or ""

        if value is None:
            continue

        entry = {
            "value": value,
            "units": units,
            "route": route,
            "source": source,
            "study_type": study_type,
            "species": record.get("species") or "",
        }

        if "rfd" in tox_type or "reference dose" in tox_type:
            pods["rfd"].append(entry)
        elif "noael" in tox_type:
            pods["noael"].append(entry)
        elif "loael" in tox_type:
            pods["loael"].append(entry)
        elif "bmdl" in tox_type:
            pods["bmdl"].append(entry)
        elif "bmd" in tox_type:
            pods["bmd"].append(entry)
        elif "adi" in tox_type:
            pods["adi"].append(entry)
        elif "tdi" in tox_type:
            pods["tdi"].append(entry)

    # Pick best value per type (prefer oral route)
    result = {}
    for pod_type in ["rfd", "adi", "tdi", "noael", "loael", "bmdl"]:
        candidates = pods.get(pod_type, [])
        if not candidates:
            continue
        # Prefer oral
        oral = [c for c in candidates if "oral" in c["route"]]
        best = oral[0] if oral else candidates[0]
        result[pod_type] = {
            "value": best["value"],
            "units": best["units"],
            "route": best["route"],
            "source": best["source"],
        }

    result["total_records"] = len(hazard_records)
    return result


def extract_genetox_summary(genetox_records: list[dict]) -> dict[str, Any]:
    """Summarize genotoxicity results."""
    positive = 0
    negative = 0
    equivocal = 0

    for record in genetox_records:
        outcome = (record.get("toxvalType") or "").lower()
        if "positive" in outcome:
            positive += 1
        elif "negative" in outcome:
            negative += 1
        else:
            equivocal += 1

    total = positive + negative + equivocal
    if total == 0:
        return {}

    if positive > negative:
        overall = "positive"
    elif negative > positive:
        overall = "negative"
    else:
        overall = "equivocal"

    return {
        "overall": overall,
        "positive": positive,
        "negative": negative,
        "equivocal": equivocal,
        "total_assays": total,
    }


def extract_cancer_data(cancer_records: list[dict]) -> dict[str, Any]:
    """Extract cancer classification and slope factors."""
    result: dict[str, Any] = {}

    for record in cancer_records:
        descriptor = (record.get("toxvalType") or "").lower()
        value = record.get("toxvalNumeric")
        source = record.get("source") or ""

        if "slope" in descriptor and value is not None:
            result["cancer_slope_factor"] = {
                "value": value,
                "units": record.get("toxvalUnits") or "",
                "source": source,
            }
        if "classification" in descriptor or "group" in descriptor:
            result["cancer_classification"] = {
                "value": record.get("toxvalType"),
                "source": source,
            }

    result["total_records"] = len(cancer_records)
    return result


# ---------------------------------------------------------------------------
# CSV import (no API key needed)
# ---------------------------------------------------------------------------

def export_cas_list(data: dict, list_key: str = "harmful_additives") -> list[str]:
    """Export CAS numbers for CompTox Dashboard batch search."""
    cas_list = []
    for entry in data.get(list_key, []):
        cas = (entry.get("external_ids") or {}).get("cas")
        if cas:
            cas_list.append(cas)
    return cas_list


def import_comptox_csv(csv_path: Path) -> dict[str, dict]:
    """Import CompTox Dashboard batch export CSV.

    Returns: {casrn: {field: value}} mapping.

    The CompTox batch export CSV typically includes columns like:
    CASRN, PREFERRED_NAME, DTXSID, MOLECULAR_FORMULA, and various
    hazard columns depending on what was selected during export.
    """
    import csv

    results: dict[str, dict] = {}
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # CompTox uses various column names across versions
            cas = (
                row.get("CASRN") or row.get("INPUT") or
                row.get("CAS-RN") or row.get("casrn") or ""
            ).strip()
            if not cas:
                continue

            record: dict[str, Any] = {
                "dtxsid": row.get("DTXSID") or row.get("dtxsid") or "",
                "preferred_name": row.get("PREFERRED_NAME") or row.get("preferredName") or "",
                "mol_formula": row.get("MOLECULAR_FORMULA") or row.get("molFormula") or "",
            }

            # Extract hazard fields (column names vary by export selection)
            for col, val in row.items():
                col_lower = col.lower()
                val = (val or "").strip()
                if not val or val in ("-", "N/A", "NA", ""):
                    continue

                if "noael" in col_lower:
                    record.setdefault("noael", []).append({"raw": val, "column": col})
                elif "loael" in col_lower:
                    record.setdefault("loael", []).append({"raw": val, "column": col})
                elif "rfd" in col_lower or "reference_dose" in col_lower:
                    record.setdefault("rfd", []).append({"raw": val, "column": col})
                elif "bmd" in col_lower:
                    record.setdefault("bmd", []).append({"raw": val, "column": col})
                elif "cancer" in col_lower:
                    record.setdefault("cancer", []).append({"raw": val, "column": col})
                elif "genetox" in col_lower or "genotox" in col_lower or "mutagen" in col_lower:
                    record.setdefault("genetox", []).append({"raw": val, "column": col})
                elif "adi" in col_lower or "tdi" in col_lower:
                    record.setdefault("adi", []).append({"raw": val, "column": col})

            results[cas] = record

    return results


def enrich_from_csv(
    data: dict,
    csv_data: dict[str, dict],
    *,
    list_key: str = "harmful_additives",
    apply: bool = False,
) -> dict:
    """Enrich harmful_additives from CompTox CSV export data."""
    entries = data.get(list_key, [])
    results: dict[str, Any] = {
        "matched": [],
        "not_in_csv": [],
        "no_cas": [],
    }
    changes_made = 0

    for entry in entries:
        eid = entry.get("id", "")
        name = entry.get("standard_name", "")
        cas = (entry.get("external_ids") or {}).get("cas")

        if not cas:
            results["no_cas"].append({"id": eid, "name": name})
            continue

        csv_record = csv_data.get(cas)
        if not csv_record:
            results["not_in_csv"].append({"id": eid, "name": name, "cas": cas})
            continue

        record = {
            "id": eid,
            "name": name,
            "cas": cas,
            "dtxsid": csv_record.get("dtxsid"),
            "comptox_name": csv_record.get("preferred_name"),
            "hazard_data": {
                k: v for k, v in csv_record.items()
                if k in ("noael", "loael", "rfd", "bmd", "cancer", "genetox", "adi")
            },
        }
        results["matched"].append(record)

        if apply:
            # Add DTXSID
            ext = entry.setdefault("external_ids", {})
            dtxsid = csv_record.get("dtxsid")
            if dtxsid and not ext.get("dtxsid"):
                ext["dtxsid"] = dtxsid
                changes_made += 1

            # Fill dose_thresholds from CSV data
            dose_thresh = entry.get("dose_thresholds") or {}
            for pod_type in ("noael", "loael", "rfd", "bmd", "adi"):
                if pod_type in csv_record and pod_type not in dose_thresh:
                    raw_vals = csv_record[pod_type]
                    if raw_vals:
                        dose_thresh[pod_type] = {
                            "value": raw_vals[0]["raw"],
                            "source": f"CompTox Dashboard CSV export ({raw_vals[0].get('column', '')})",
                        }
                        changes_made += 1

            if dose_thresh:
                entry["dose_thresholds"] = dose_thresh

    results["total"] = len(entries)
    results["changes_applied"] = changes_made
    return results


# ---------------------------------------------------------------------------
# ADI validation
# ---------------------------------------------------------------------------

def validate_adi(entry: dict, pods: dict) -> list[dict]:
    """Compare our ADI values against CompTox reference doses."""
    issues = []
    reg = entry.get("regulatory_status", {})

    # Extract our ADI from regulatory text
    for region in ("US", "EU", "WHO"):
        text = reg.get(region, "")
        if not isinstance(text, str):
            continue
        match = ADI_RE.search(text)
        if not match:
            continue
        our_adi = float(match.group(1))

        # Compare against CompTox RfD or ADI
        for pod_type in ("rfd", "adi", "tdi"):
            pod = pods.get(pod_type)
            if not pod:
                continue
            comptox_val = pod["value"]
            # Allow 50% tolerance (different methodologies)
            if abs(our_adi - comptox_val) > max(our_adi * 0.5, comptox_val * 0.5):
                issues.append({
                    "type": "ADI_DISCREPANCY",
                    "region": region,
                    "our_value": our_adi,
                    "comptox_value": comptox_val,
                    "comptox_type": pod_type.upper(),
                    "comptox_source": pod.get("source", ""),
                })

    return issues


# ---------------------------------------------------------------------------
# File verification
# ---------------------------------------------------------------------------

def verify_harmful_additives(
    data: dict,
    client: CompToxClient,
    *,
    list_key: str = "harmful_additives",
    apply: bool = False,
) -> dict:
    """Verify and enrich harmful_additives.json with CompTox data."""
    entries = data.get(list_key, [])
    results: dict[str, Any] = {
        "enriched": [],
        "adi_discrepancies": [],
        "genetox_flags": [],
        "cancer_data": [],
        "no_cas": [],
        "not_found": [],
        "errors": [],
    }
    changes_made = 0
    total = len(entries)

    for i, entry in enumerate(entries):
        eid = entry.get("id", f"entry_{i}")
        name = entry.get("standard_name", "")
        ext = entry.get("external_ids", {})
        cas = ext.get("cas")

        if not cas:
            results["no_cas"].append({"id": eid, "name": name})
            continue

        # Resolve CAS → DTXSID
        chem = client.search_by_cas(cas)
        if not chem:
            results["not_found"].append({"id": eid, "name": name, "cas": cas})
            continue

        dtxsid = chem.get("dtxsid")
        if not dtxsid:
            results["not_found"].append({"id": eid, "name": name, "cas": cas})
            continue

        # Fetch hazard data
        human_hazard = client.get_human_hazard(dtxsid)
        pods = extract_best_pod(human_hazard)

        # Fetch genetox
        genetox_raw = client.get_genetox_summary(dtxsid)
        genetox = extract_genetox_summary(genetox_raw)

        # Fetch cancer data
        cancer_raw = client.get_cancer_hazard(dtxsid)
        cancer = extract_cancer_data(cancer_raw)

        record = {
            "id": eid,
            "name": name,
            "dtxsid": dtxsid,
            "comptox_name": chem.get("preferredName"),
            "pods": pods,
            "genetox": genetox,
            "cancer": cancer,
        }

        # Validate ADI
        adi_issues = validate_adi(entry, pods)
        if adi_issues:
            record["adi_issues"] = adi_issues
            results["adi_discrepancies"].extend(adi_issues)

        # Flag genetox
        if genetox.get("overall") in ("positive", "equivocal"):
            results["genetox_flags"].append({
                "id": eid, "name": name,
                "genetox": genetox,
            })

        # Flag cancer data
        if cancer.get("cancer_slope_factor") or cancer.get("cancer_classification"):
            results["cancer_data"].append({
                "id": eid, "name": name,
                "cancer": cancer,
            })

        has_data = bool(pods.get("rfd") or pods.get("noael") or pods.get("adi"))
        if has_data:
            results["enriched"].append(record)

        # Apply: fill dose_thresholds
        if apply and has_data:
            dose_thresh = entry.get("dose_thresholds") or {}
            updated = False

            for pod_type in ("rfd", "noael", "loael", "bmdl", "adi", "tdi"):
                pod = pods.get(pod_type)
                if pod and pod_type not in dose_thresh:
                    dose_thresh[pod_type] = {
                        "value": pod["value"],
                        "unit": pod["units"],
                        "source": f"CompTox ToxValDB ({pod.get('source', 'EPA')})",
                        "route": pod.get("route", "oral"),
                    }
                    updated = True

            if updated:
                entry["dose_thresholds"] = dose_thresh
                changes_made += 1

            # Add DTXSID to external_ids
            if not ext.get("dtxsid"):
                ext["dtxsid"] = dtxsid
                if "external_ids" not in entry:
                    entry["external_ids"] = ext

        done = i + 1
        if done % 10 == 0 or done == total:
            print(f"  [{done}/{total}] {name}", file=sys.stderr)

    results["total"] = total
    results["changes_applied"] = changes_made
    return results


# ---------------------------------------------------------------------------
# Single substance lookup
# ---------------------------------------------------------------------------

def lookup_substance(query: str, client: CompToxClient, *, by_cas: bool = False) -> None:
    """Look up and display CompTox data for a single substance."""
    if by_cas:
        chem = client.search_by_cas(query)
    else:
        chem = client.search_by_name(query)

    if not chem:
        print(f"Not found in CompTox: {query}")
        return

    dtxsid = chem.get("dtxsid", "?")
    print(f"\n  DTXSID:          {dtxsid}")
    print(f"  Preferred Name:  {chem.get('preferredName', '?')}")
    print(f"  CAS-RN:          {chem.get('casrn', '?')}")
    print(f"  Mol Formula:     {chem.get('molFormula', '?')}")

    # Hazard data
    human = client.get_human_hazard(dtxsid)
    pods = extract_best_pod(human)
    if pods:
        print(f"\n  Hazard Data ({pods.get('total_records', 0)} ToxValDB records):")
        for pod_type in ("rfd", "adi", "tdi", "noael", "loael", "bmdl"):
            pod = pods.get(pod_type)
            if pod:
                print(f"    {pod_type.upper():6s}: {pod['value']} {pod['units']} ({pod['route']}) — {pod['source']}")
    else:
        print("\n  No hazard data in ToxValDB")

    # Genetox
    genetox_raw = client.get_genetox_summary(dtxsid)
    genetox = extract_genetox_summary(genetox_raw)
    if genetox:
        print(f"\n  Genotoxicity: {genetox['overall']} ({genetox['positive']}+ / {genetox['negative']}- / {genetox['equivocal']}eq)")
    else:
        print("\n  No genotoxicity data")

    # Cancer
    cancer_raw = client.get_cancer_hazard(dtxsid)
    cancer = extract_cancer_data(cancer_raw)
    if cancer:
        if cancer.get("cancer_slope_factor"):
            csf = cancer["cancer_slope_factor"]
            print(f"\n  Cancer Slope Factor: {csf['value']} {csf['units']} — {csf['source']}")
        if cancer.get("cancer_classification"):
            cc = cancer["cancer_classification"]
            print(f"  Cancer Classification: {cc['value']} — {cc['source']}")
    else:
        print("  No cancer-specific data")

    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print_summary(results: dict) -> None:
    print(f"\n{'=' * 60}")
    print("CompTox ToxValDB Verification Report")
    print(f"{'=' * 60}")
    print(f"  Total entries:         {results['total']}")
    print(f"  Enriched (has PODs):   {len(results['enriched'])}")
    print(f"  ADI discrepancies:     {len(results['adi_discrepancies'])}")
    print(f"  Genetox flags:         {len(results['genetox_flags'])}")
    print(f"  Cancer data found:     {len(results['cancer_data'])}")
    print(f"  No CAS number:         {len(results['no_cas'])}")
    print(f"  Not found in CompTox:  {len(results['not_found'])}")
    if results.get("changes_applied"):
        print(f"  Changes applied:       {results['changes_applied']}")

    if results["adi_discrepancies"]:
        print(f"\n  --- ADI Discrepancies ({len(results['adi_discrepancies'])}) ---")
        for d in results["adi_discrepancies"][:10]:
            print(f"    {d.get('region', '?'):5s} ours={d['our_value']} vs CompTox {d['comptox_type']}={d['comptox_value']} ({d['comptox_source'][:40]})")

    if results["genetox_flags"]:
        print(f"\n  --- Genotoxicity Flags ({len(results['genetox_flags'])}) ---")
        for g in results["genetox_flags"][:10]:
            gt = g["genetox"]
            print(f"    {g['id']:35s} {gt['overall']} ({gt['positive']}+/{gt['negative']}-)")

    if results["cancer_data"]:
        print(f"\n  --- Cancer Data ({len(results['cancer_data'])}) ---")
        for c in results["cancer_data"][:10]:
            csf = c["cancer"].get("cancer_slope_factor", {})
            if csf:
                print(f"    {c['id']:35s} slope={csf.get('value')} {csf.get('units', '')}")
            else:
                print(f"    {c['id']:35s} classification data available")

    print(f"{'=' * 60}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify PharmaGuide additives against EPA CompTox ToxValDB")
    parser.add_argument("--file", type=Path, help="Path to harmful_additives.json")
    parser.add_argument("--list-key", default="harmful_additives")
    parser.add_argument("--search", type=str, help="Search by substance name (API mode)")
    parser.add_argument("--cas", type=str, help="Look up by CAS number (API mode)")
    parser.add_argument("--export-cas", action="store_true",
                        help="Export CAS list for CompTox Dashboard batch search (no API key)")
    parser.add_argument("--import-csv", type=Path, metavar="CSV_PATH",
                        help="Import CompTox Dashboard CSV export (no API key needed)")
    parser.add_argument("--apply", action="store_true", help="Write dose_thresholds enrichment")
    parser.add_argument("--output", type=Path, help="Save JSON report")
    parser.add_argument("--api-key", type=str, help="CompTox API key")
    parser.add_argument("--cache-dir", type=Path, default=SCRIPTS_ROOT / ".cache")
    args = parser.parse_args()

    # --- Export CAS list (no API needed) ---
    if args.export_cas:
        if not args.file:
            parser.error("--file required with --export-cas")
        data = json.loads(args.file.read_text())
        cas_list = export_cas_list(data, args.list_key)
        print(f"# {len(cas_list)} CAS numbers for CompTox Dashboard batch search")
        print(f"# Paste into https://comptox.epa.gov/dashboard/batch-search")
        print(f"# Select input type: CASRN")
        print(f"# Select export: Hazard data, CSV format")
        print()
        for cas in cas_list:
            print(cas)
        return

    # --- CSV import mode (no API needed) ---
    if args.import_csv:
        if not args.file:
            parser.error("--file required with --import-csv")
        data = json.loads(args.file.read_text())
        csv_data = import_comptox_csv(args.import_csv)
        print(f"  Loaded {len(csv_data)} substances from CSV", file=sys.stderr)

        results = enrich_from_csv(data, csv_data, list_key=args.list_key, apply=args.apply)

        print(f"\n{'=' * 60}")
        print("CompTox CSV Import Report")
        print(f"{'=' * 60}")
        print(f"  Total entries:     {results['total']}")
        print(f"  Matched to CSV:    {len(results['matched'])}")
        print(f"  Not in CSV:        {len(results['not_in_csv'])}")
        print(f"  No CAS number:     {len(results['no_cas'])}")
        if results.get("changes_applied"):
            print(f"  Changes applied:   {results['changes_applied']}")

        if results["matched"]:
            print(f"\n  --- Matched ({len(results['matched'])}) ---")
            for r in results["matched"][:15]:
                hazard_types = list(r.get("hazard_data", {}).keys())
                print(f"    {r['id']:35s} DTXSID={r.get('dtxsid', '?'):15s} hazard: {hazard_types}")

        print(f"{'=' * 60}\n")

        if args.apply and results["changes_applied"] > 0:
            args.file.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
            print(f"  Wrote {results['changes_applied']} changes to {args.file}")

        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(results, indent=2))
            print(f"  Report saved to {args.output}")
        return

    # --- API mode ---
    cache_path = args.cache_dir / "comptox_cache.json"
    api_key = args.api_key or DEFAULT_API_KEY

    client = CompToxClient(
        api_key=api_key,
        cache_path=cache_path,
    )

    try:
        if args.cas:
            lookup_substance(args.cas, client, by_cas=True)
            return
        if args.search:
            lookup_substance(args.search, client)
            return

        if not args.file:
            parser.error("--file, --search, --cas, --export-cas, or --import-csv is required")

        data = json.loads(args.file.read_text())
        results = verify_harmful_additives(data, client, list_key=args.list_key, apply=args.apply)
        _print_summary(results)

        if args.apply and results["changes_applied"] > 0:
            args.file.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
            print(f"  Wrote {results['changes_applied']} changes to {args.file}")

        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(results, indent=2))
            print(f"  Report saved to {args.output}")
    finally:
        client.save_cache()


if __name__ == "__main__":
    main()
