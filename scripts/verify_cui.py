#!/usr/bin/env python3
"""
UMLS CUI Verification & Lookup Tool for PharmaGuide data files.

Uses the NIH UMLS REST API to:
  1. Verify existing CUIs match the correct substance
  2. Look up missing CUIs by searching substance names
  3. Produce a report of mismatches, missing CUIs, and suggested fixes
  4. Optionally apply fixes directly to the JSON file

Usage:
  # Verify all CUIs in harmful_additives.json (dry run — report only)
  python3 scripts/verify_cui.py

  # Verify and apply fixes
  python3 scripts/verify_cui.py --apply

  # Verify a single CUI
  python3 scripts/verify_cui.py --cui C0037511

  # Search for a substance by name
  python3 scripts/verify_cui.py --search "calcium silicate"

  # Verify a different data file
  python3 scripts/verify_cui.py --file scripts/data/banned_recalled_ingredients.json --key-field id --cui-field cui

Environment:
  Set UMLS_API_KEY or pass --api-key. Falls back to hardcoded default.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional
from urllib.parse import quote

import env_loader  # noqa: F401 — loads .env into os.environ
import ssl
import urllib.request
import urllib.error

# macOS Python often lacks certs — probe once, use unverified context as fallback
def _make_ssl_ctx() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    try:
        req = urllib.request.Request("https://uts-ws.nlm.nih.gov", method="HEAD")
        urllib.request.urlopen(req, timeout=5, context=ctx)
        return ctx
    except (ssl.SSLCertVerificationError, urllib.error.URLError):
        return ssl._create_unverified_context()
    except Exception:
        return ctx

_SSL_CTX = _make_ssl_ctx()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DEFAULT_API_KEY = os.environ.get("UMLS_API_KEY", "")
BASE_URL = "https://uts-ws.nlm.nih.gov/rest"
VERSION = "current"
RATE_LIMIT_DELAY = 0.12  # seconds between requests (~8 req/s, well under limit)

DEFAULT_FILE = Path(__file__).parent / "data" / "harmful_additives.json"


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

class UMLSClient:
    """Thin wrapper around the UMLS REST API (stdlib only — no requests dependency)."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._request_count = 0

    def _get(self, endpoint: str, params: dict | None = None) -> dict | None:
        params = params or {}
        params["apiKey"] = self.api_key
        query = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
        url = f"{BASE_URL}{endpoint}?{query}"
        time.sleep(RATE_LIMIT_DELAY)
        self._request_count += 1
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            print(f"  API error: HTTP {e.code} — {e.reason}")
            return None
        except (urllib.error.URLError, TimeoutError) as e:
            print(f"  API error: {e}")
            return None

    def lookup_cui(self, cui: str) -> dict | None:
        """Look up a CUI and return its preferred name + semantic types."""
        data = self._get(f"/content/{VERSION}/CUI/{cui}")
        if not data or "result" not in data:
            return None
        result = data["result"]
        return {
            "cui": result.get("ui"),
            "name": result.get("name"),
            "semantic_types": [st["name"] for st in result.get("semanticTypes", [])],
            "atom_count": result.get("atomCount", 0),
            "status": result.get("status"),
        }

    def search(self, term: str, max_results: int = 5) -> list[dict]:
        """Search UMLS by name and return top matches."""
        data = self._get(f"/search/{VERSION}", params={
            "string": term,
            "pageSize": max_results,
            "searchType": "words",
        })
        if not data or "result" not in data:
            return []
        results = data["result"].get("results", [])
        # Filter out the "NO RESULTS" sentinel
        return [
            {
                "cui": r["ui"],
                "name": r["name"],
                "source": r.get("rootSource", ""),
                "semantic_types": r.get("semanticTypes", []),
            }
            for r in results
            if r.get("ui") != "NONE"
        ]

    def search_exact(self, term: str) -> dict | None:
        """Search for exact match and return top result."""
        data = self._get(f"/search/{VERSION}", params={
            "string": term,
            "pageSize": 1,
            "searchType": "exact",
        })
        if not data or "result" not in data:
            return None
        results = data["result"].get("results", [])
        if not results or results[0].get("ui") == "NONE":
            return None
        r = results[0]
        return {
            "cui": r["ui"],
            "name": r["name"],
            "source": r.get("rootSource", ""),
        }

    @property
    def request_count(self) -> int:
        return self._request_count


# ---------------------------------------------------------------------------
# Verification logic
# ---------------------------------------------------------------------------

def verify_cui_for_entry(
    client: UMLSClient,
    entry_id: str,
    standard_name: str,
    current_cui: Optional[str],
    aliases: list[str],
) -> dict:
    """Verify a single entry's CUI. Returns a report dict."""
    report = {
        "id": entry_id,
        "standard_name": standard_name,
        "current_cui": current_cui,
        "status": "unknown",
        "umls_name": None,
        "suggested_cui": None,
        "suggested_name": None,
        "action": None,
    }

    # Step 1: If CUI exists, verify it
    if current_cui:
        info = client.lookup_cui(current_cui)
        if info is None:
            report["status"] = "INVALID_CUI"
            report["action"] = f"CUI {current_cui} not found in UMLS"
        else:
            report["umls_name"] = info["name"]
            # Check if the UMLS name reasonably matches
            name_lower = standard_name.lower()
            umls_lower = info["name"].lower()
            if (name_lower in umls_lower or umls_lower in name_lower
                    or any(a.lower() in umls_lower or umls_lower in a.lower()
                           for a in aliases)):
                report["status"] = "VERIFIED"
                report["action"] = None
            else:
                report["status"] = "MISMATCH"
                report["action"] = (
                    f"CUI {current_cui} maps to '{info['name']}' "
                    f"but entry is '{standard_name}'"
                )

    # Step 2: If CUI is missing or mismatched, search for the right one
    if report["status"] in ("unknown", "INVALID_CUI", "MISMATCH") or not current_cui:
        # Try exact match on standard name first
        exact = client.search_exact(standard_name)
        if exact:
            report["suggested_cui"] = exact["cui"]
            report["suggested_name"] = exact["name"]
            if not current_cui:
                report["status"] = "MISSING_CUI"
                report["action"] = f"Suggest CUI {exact['cui']} ({exact['name']})"
        else:
            # Try word search
            results = client.search(standard_name, max_results=3)
            if results:
                top = results[0]
                report["suggested_cui"] = top["cui"]
                report["suggested_name"] = top["name"]
                if not current_cui:
                    report["status"] = "MISSING_CUI"
                    report["action"] = f"Suggest CUI {top['cui']} ({top['name']})"
            elif not current_cui:
                report["status"] = "NOT_FOUND"
                report["action"] = "No UMLS match found — may need manual lookup"

    return report


def load_entries(file_path: Path, list_key: str, id_field: str, cui_field: str) -> list[dict]:
    """Load entries from a JSON data file."""
    data = json.loads(file_path.read_text())

    # Try the list_key, or common alternatives
    entries = data.get(list_key)
    if entries is None:
        for key in ["harmful_additives", "ingredients", "additives"]:
            if key in data:
                entries = data[key]
                break
    if entries is None:
        print(f"ERROR: Could not find entry list in {file_path}")
        sys.exit(1)

    return entries


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_verify(args):
    """Verify all CUIs in a data file."""
    client = UMLSClient(args.api_key)
    file_path = Path(args.file)
    entries = load_entries(file_path, args.list_key, args.id_field, args.cui_field)

    print(f"Verifying {len(entries)} entries in {file_path.name}...")
    print(f"CUI field: {args.cui_field} | ID field: {args.id_field}")
    print()

    reports = []
    for i, entry in enumerate(entries):
        entry_id = entry.get(args.id_field, f"entry_{i}")
        standard_name = entry.get("standard_name", entry.get("name", ""))
        current_cui = entry.get(args.cui_field)
        aliases = entry.get("aliases", [])

        # Skip empty/null CUIs for "verify-only" mode if not looking up missing
        report = verify_cui_for_entry(client, entry_id, standard_name, current_cui, aliases)
        reports.append(report)

        # Progress indicator
        status_icon = {"VERIFIED": "✅", "MISMATCH": "❌", "MISSING_CUI": "🔍",
                       "INVALID_CUI": "⚠️", "NOT_FOUND": "—"}.get(report["status"], "?")
        print(f"  [{i+1:3d}/{len(entries)}] {status_icon} {entry_id}: {report['status']}"
              + (f" → {report['action']}" if report['action'] else ""))

    # Summary
    print(f"\n{'='*60}")
    print(f"SUMMARY — {len(entries)} entries, {client.request_count} API requests")
    print(f"{'='*60}")
    counts = {}
    for r in reports:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    for status, count in sorted(counts.items()):
        print(f"  {status}: {count}")

    # Actionable items
    actionable = [r for r in reports if r["action"]]
    if actionable:
        print(f"\n{'='*60}")
        print(f"ACTIONABLE ITEMS ({len(actionable)})")
        print(f"{'='*60}")
        for r in actionable:
            print(f"  {r['id']}:")
            print(f"    Current: cui={r['current_cui']}")
            if r["umls_name"]:
                print(f"    UMLS says: {r['umls_name']}")
            if r["suggested_cui"]:
                print(f"    Suggested: {r['suggested_cui']} ({r['suggested_name']})")
            print(f"    Action: {r['action']}")
            print()

    # Apply fixes if requested
    if args.apply and actionable:
        print(f"\nApplying {len(actionable)} fixes...")
        data = json.loads(file_path.read_text())
        entry_list = data.get(args.list_key)
        if entry_list is None:
            for key in ["harmful_additives", "ingredients", "additives"]:
                if key in data:
                    entry_list = data[key]
                    break

        applied = 0
        for entry in entry_list:
            eid = entry.get(args.id_field)
            match = next((r for r in actionable if r["id"] == eid), None)
            if not match or not match["suggested_cui"]:
                continue
            if match["status"] == "MISSING_CUI":
                entry[args.cui_field] = match["suggested_cui"]
                applied += 1
            elif match["status"] == "MISMATCH":
                # Only apply if user explicitly passed --apply
                print(f"  MISMATCH {eid}: {match['current_cui']} → {match['suggested_cui']} "
                      f"('{match['suggested_name']}')")
                entry[args.cui_field] = match["suggested_cui"]
                applied += 1

        file_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        print(f"\nApplied {applied} CUI updates to {file_path.name}")

    return reports


def cmd_lookup_cui(args):
    """Look up a single CUI."""
    client = UMLSClient(args.api_key)
    info = client.lookup_cui(args.cui)
    if info:
        print(f"CUI: {info['cui']}")
        print(f"Name: {info['name']}")
        print(f"Semantic Types: {', '.join(info['semantic_types'])}")
        print(f"Atom Count: {info['atom_count']}")
        print(f"Status: {info['status']}")
    else:
        print(f"CUI {args.cui} not found in UMLS.")


def cmd_search(args):
    """Search UMLS by substance name."""
    client = UMLSClient(args.api_key)
    results = client.search(args.search, max_results=10)
    if results:
        print(f"Top {len(results)} results for '{args.search}':\n")
        for i, r in enumerate(results, 1):
            types = ", ".join(r["semantic_types"]) if isinstance(r["semantic_types"], list) else str(r["semantic_types"])
            print(f"  {i}. {r['cui']} — {r['name']}")
            print(f"     Source: {r['source']} | Types: {types}")
            print()
    else:
        print(f"No results for '{args.search}'.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="UMLS CUI Verification & Lookup for PharmaGuide data files"
    )
    parser.add_argument("--api-key", default=DEFAULT_API_KEY,
                        help="UMLS API key (or set UMLS_API_KEY env var)")
    parser.add_argument("--file", default=str(DEFAULT_FILE),
                        help=f"JSON data file to verify (default: {DEFAULT_FILE.name})")
    parser.add_argument("--list-key", default="harmful_additives",
                        help="JSON key containing the entry list (default: harmful_additives)")
    parser.add_argument("--id-field", default="id",
                        help="Field name for entry ID (default: id)")
    parser.add_argument("--cui-field", default="cui",
                        help="Field name for CUI (default: cui)")
    parser.add_argument("--apply", action="store_true",
                        help="Apply suggested CUI fixes to the file")
    parser.add_argument("--cui", help="Look up a single CUI")
    parser.add_argument("--search", help="Search UMLS by substance name")

    args = parser.parse_args()

    if args.cui:
        cmd_lookup_cui(args)
    elif args.search:
        cmd_search(args)
    else:
        cmd_verify(args)


if __name__ == "__main__":
    main()
