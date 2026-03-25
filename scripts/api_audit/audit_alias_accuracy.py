#!/usr/bin/env python3
"""
Alias accuracy auditor for PharmaGuide data files.

What this script does:
  1. For each ingredient with identity anchors (UNII, CAS, PubChem CID),
     fetches all known names/synonyms from the authoritative APIs.
  2. Checks whether each local alias appears in at least one authoritative
     name list. Flags aliases that don't match any external source.
  3. Detects alias collisions — the same alias appearing in multiple entries,
     which would cause false matches during scoring.
  4. Detects identity conflicts — where UNII and PubChem CID point to
     different substances (CAS mismatch).

Checks:
  - UNVERIFIED_ALIAS: alias not found in GSRS names, PubChem synonyms, or UMLS
  - ALIAS_COLLISION: same alias appears in 2+ different entries
  - IDENTITY_CONFLICT: UNII-CAS vs PubChem-CAS disagree for same entry
  - DUPLICATE_ALIAS: same alias appears twice within one entry

Operator runbook:
  python3 scripts/api_audit/audit_alias_accuracy.py --file scripts/data/ingredient_quality_map.json --mode iqm
  python3 scripts/api_audit/audit_alias_accuracy.py --file scripts/data/backed_clinical_studies.json --mode clinical
  python3 scripts/api_audit/audit_alias_accuracy.py --file scripts/data/harmful_additives.json --mode flat --list-key harmful_additives
  python3 scripts/api_audit/audit_alias_accuracy.py --file scripts/data/banned_recalled_ingredients.json --mode flat --list-key ingredients

Rate limits:
  Uses cached GSRS + PubChem data when available. Fresh lookups at ~2 req/s.
"""

import argparse
import json
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_ROOT = SCRIPT_DIR.parent

# ---------------------------------------------------------------------------
# Lightweight API helpers (use caches from existing scripts when available)
# ---------------------------------------------------------------------------

GSRS_BASE = "https://gsrs.ncats.nih.gov/ginas/app/api/v1"
PUBCHEM_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
RATE_DELAY = 0.4

_ssl_ctx = None


def _get_ssl_ctx() -> ssl.SSLContext:
    global _ssl_ctx
    if _ssl_ctx is None:
        _ssl_ctx = ssl._create_unverified_context()
    return _ssl_ctx


def _api_get_json(url: str, timeout: float = 12.0) -> dict | None:
    time.sleep(RATE_DELAY)
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout, context=_get_ssl_ctx()) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def _requests_get_json(url: str, timeout: float = 12.0) -> dict | None:
    """Use requests library for sites that block urllib (PubChem)."""
    try:
        import requests
        resp = requests.get(url, headers={"Accept": "application/json"}, timeout=timeout)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Name fetchers
# ---------------------------------------------------------------------------

def fetch_gsrs_names(unii: str) -> set[str]:
    """Get all names for a UNII from GSRS."""
    url = f"{GSRS_BASE}/substances({unii})?view=full"
    data = _api_get_json(url)
    if not data:
        return set()
    names = set()
    if data.get("_name"):
        names.add(data["_name"].lower().strip())
    for n in data.get("names", []):
        val = n.get("name", "")
        if val:
            names.add(val.lower().strip())
    return names


def fetch_pubchem_synonyms(cid: int | str) -> set[str]:
    """Get all synonyms for a PubChem CID."""
    url = f"{PUBCHEM_BASE}/compound/cid/{cid}/synonyms/JSON"
    time.sleep(RATE_DELAY)
    data = _requests_get_json(url)
    if not data:
        return set()
    info = data.get("InformationList", {}).get("Information", [])
    if info:
        return {s.lower().strip() for s in info[0].get("Synonym", [])}
    return set()


def fetch_pubchem_cas(cid: int | str) -> str | None:
    """Get primary CAS for a PubChem CID."""
    syns = fetch_pubchem_synonyms(cid)
    cas_re = re.compile(r"^\d{2,7}-\d{2}-\d$")
    for s in syns:
        if cas_re.match(s):
            return s
    return None


def fetch_gsrs_cas(unii: str) -> str | None:
    """Get primary CAS from GSRS."""
    url = f"{GSRS_BASE}/substances({unii})?view=full"
    data = _api_get_json(url)
    if not data:
        return None
    for code in data.get("codes", []):
        if code.get("codeSystem") == "CAS":
            return code.get("code")
    return None


# ---------------------------------------------------------------------------
# Alias collection from entries
# ---------------------------------------------------------------------------

NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def _norm(text: str) -> str:
    return NON_ALNUM_RE.sub(" ", text.lower()).strip()


def collect_aliases_flat(entry: dict) -> list[str]:
    """Collect aliases from a flat-structure entry."""
    return [str(a) for a in entry.get("aliases", []) if a]


def collect_aliases_iqm(entry: dict, key: str) -> list[str]:
    """Collect all aliases from an IQM entry (ingredient + form level)."""
    aliases = list(entry.get("aliases", []))
    for fn, fd in entry.get("forms", {}).items():
        for a in fd.get("aliases", []):
            if a and a not in aliases:
                aliases.append(str(a))
    return aliases


def collect_aliases_clinical(entry: dict) -> list[str]:
    return [str(a) for a in entry.get("aliases", []) if a]


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def check_unverified_aliases(
    entry_id: str,
    standard_name: str,
    aliases: list[str],
    unii: str | None,
    pubchem_cid: int | str | None,
    *,
    gsrs_names_cache: dict[str, set[str]],
    pubchem_cache: dict[str, set[str]],
) -> list[dict]:
    """Check if aliases appear in authoritative name lists."""
    issues = []

    # Fetch authoritative names
    auth_names: set[str] = set()

    if unii:
        if unii not in gsrs_names_cache:
            gsrs_names_cache[unii] = fetch_gsrs_names(unii)
        auth_names.update(gsrs_names_cache[unii])

    if pubchem_cid:
        cid_str = str(pubchem_cid)
        if cid_str not in pubchem_cache:
            pubchem_cache[cid_str] = fetch_pubchem_synonyms(pubchem_cid)
        auth_names.update(pubchem_cache[cid_str])

    # If no identity anchors, skip verification (can't verify without external data)
    if not auth_names:
        return issues

    # Add standard name to auth names (it's already verified by the UNII assignment)
    auth_names.add(standard_name.lower().strip())
    auth_norms = {_norm(n) for n in auth_names}

    for alias in aliases:
        alias_lower = alias.lower().strip()
        alias_norm = _norm(alias)

        # Skip very short aliases (abbreviations are often not in synonym lists)
        if len(alias_norm.replace(" ", "")) <= 3:
            continue

        # Check exact match or normalized match
        if alias_lower in auth_names:
            continue
        if alias_norm in auth_norms:
            continue

        # Check if alias is a substring of any authoritative name (or vice versa)
        if any(alias_norm in an for an in auth_norms if len(an) > len(alias_norm)):
            continue
        if any(an in alias_norm for an in auth_norms if len(an) >= 5):
            continue

        issues.append({
            "type": "UNVERIFIED_ALIAS",
            "id": entry_id,
            "name": standard_name,
            "alias": alias,
            "detail": f"Alias not found in GSRS or PubChem synonyms for this entry's UNII/CID",
        })

    return issues


def check_alias_collisions(all_entries: list[tuple[str, str, list[str]]]) -> list[dict]:
    """Check for aliases that appear in multiple entries."""
    alias_index: dict[str, list[str]] = defaultdict(list)

    for entry_id, standard_name, aliases in all_entries:
        for alias in aliases:
            key = _norm(alias)
            if key and len(key.replace(" ", "")) > 3:
                alias_index[key].append(entry_id)
        # Also index the standard name
        key = _norm(standard_name)
        if key:
            alias_index[key].append(entry_id)

    issues = []
    seen = set()
    for alias_key, entry_ids in alias_index.items():
        unique_ids = sorted(set(entry_ids))
        if len(unique_ids) > 1:
            pair_key = tuple(unique_ids)
            if pair_key not in seen:
                seen.add(pair_key)
                issues.append({
                    "type": "ALIAS_COLLISION",
                    "alias": alias_key,
                    "entries": unique_ids,
                    "detail": f"Alias '{alias_key}' maps to {len(unique_ids)} entries: {', '.join(unique_ids[:5])}",
                })

    return issues


def check_duplicate_aliases(entry_id: str, aliases: list[str]) -> list[dict]:
    """Check for duplicate aliases within one entry."""
    seen: dict[str, str] = {}
    issues = []
    for alias in aliases:
        key = _norm(alias)
        if key in seen:
            issues.append({
                "type": "DUPLICATE_ALIAS",
                "id": entry_id,
                "alias": alias,
                "existing": seen[key],
                "detail": f"Duplicate alias: '{alias}' normalizes same as '{seen[key]}'",
            })
        else:
            seen[key] = alias
    return issues


def check_identity_conflict(
    entry_id: str,
    standard_name: str,
    unii: str | None,
    cas_local: str | None,
    pubchem_cid: int | str | None,
) -> list[dict]:
    """Check if UNII and PubChem CID point to the same substance via CAS."""
    issues = []
    if not unii or not pubchem_cid:
        return issues

    gsrs_cas = fetch_gsrs_cas(unii)
    pubchem_cas = fetch_pubchem_cas(pubchem_cid)

    if gsrs_cas and pubchem_cas and gsrs_cas != pubchem_cas:
        issues.append({
            "type": "IDENTITY_CONFLICT",
            "id": entry_id,
            "name": standard_name,
            "gsrs_cas": gsrs_cas,
            "pubchem_cas": pubchem_cas,
            "detail": f"GSRS CAS={gsrs_cas} vs PubChem CAS={pubchem_cas} — may be different substances",
        })

    if cas_local:
        if gsrs_cas and cas_local != gsrs_cas:
            issues.append({
                "type": "IDENTITY_CONFLICT",
                "id": entry_id,
                "name": standard_name,
                "local_cas": cas_local,
                "gsrs_cas": gsrs_cas,
                "detail": f"Local CAS={cas_local} vs GSRS CAS={gsrs_cas}",
            })

    return issues


# ---------------------------------------------------------------------------
# Main audit
# ---------------------------------------------------------------------------

def audit_file(
    data: dict,
    mode: str,
    list_key: str | None = None,
    *,
    check_external: bool = True,
    check_identity: bool = False,
    max_external_checks: int = 0,
) -> dict:
    """Run alias accuracy audit on a data file."""

    # Collect all entries with their aliases
    all_entries: list[tuple[str, str, list[str], str | None, Any]] = []

    if mode == "iqm":
        for key in data:
            if key == "_metadata":
                continue
            entry = data[key]
            if not isinstance(entry, dict):
                continue
            eid = key
            name = entry.get("standard_name", key)
            aliases = collect_aliases_iqm(entry, key)
            unii = (entry.get("external_ids") or {}).get("unii")
            cid = None
            # IQM forms may have PubChem CID
            for fn, fd in entry.get("forms", {}).items():
                cid = cid or (fd.get("external_ids") or {}).get("pubchem_cid")
            cas = None
            for fn, fd in entry.get("forms", {}).items():
                cas = cas or (fd.get("external_ids") or {}).get("cas")
            all_entries.append((eid, name, aliases, unii, cid, cas))
    elif mode == "clinical":
        for entry in data.get("backed_clinical_studies", []):
            eid = entry.get("id", "")
            name = entry.get("standard_name", "")
            aliases = collect_aliases_clinical(entry)
            unii = (entry.get("external_ids") or {}).get("unii")
            all_entries.append((eid, name, aliases, unii, None, None))
    else:
        for entry in data.get(list_key, []):
            eid = entry.get("id", "")
            name = entry.get("standard_name", "")
            aliases = collect_aliases_flat(entry)
            ext = entry.get("external_ids", {})
            unii = ext.get("unii")
            cid = ext.get("pubchem_cid")
            cas = ext.get("cas")
            all_entries.append((eid, name, aliases, unii, cid, cas))

    results: dict[str, Any] = {
        "total_entries": len(all_entries),
        "total_aliases": sum(len(a) for _, _, a, *_ in all_entries),
        "issues": [],
        "by_type": {},
    }

    # 1. Alias collisions (fast, no API calls)
    collision_input = [(eid, name, aliases) for eid, name, aliases, *_ in all_entries]
    collisions = check_alias_collisions(collision_input)
    results["issues"].extend(collisions)

    # 2. Duplicate aliases within entries (fast, no API calls)
    for eid, name, aliases, *_ in all_entries:
        results["issues"].extend(check_duplicate_aliases(eid, aliases))

    # 3. External verification (requires API calls)
    if check_external:
        gsrs_cache: dict[str, set[str]] = {}
        pubchem_cache: dict[str, set[str]] = {}
        checked = 0
        for eid, name, aliases, unii, cid, *rest in all_entries:
            if not unii and not cid:
                continue
            if max_external_checks and checked >= max_external_checks:
                break
            issues = check_unverified_aliases(
                eid, name, aliases, unii, cid,
                gsrs_names_cache=gsrs_cache,
                pubchem_cache=pubchem_cache,
            )
            results["issues"].extend(issues)
            checked += 1
            if checked % 20 == 0:
                print(f"  [{checked}] external checks...", file=sys.stderr)

    # 4. Identity conflicts (expensive — optional)
    if check_identity:
        for eid, name, aliases, unii, cid, *rest in all_entries:
            cas = rest[0] if rest else None
            issues = check_identity_conflict(eid, name, unii, cas, cid)
            results["issues"].extend(issues)

    # Summarize
    for issue in results["issues"]:
        itype = issue["type"]
        results["by_type"][itype] = results["by_type"].get(itype, 0) + 1

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print_results(results: dict) -> None:
    print(f"\n{'=' * 60}")
    print("Alias Accuracy Audit")
    print(f"{'=' * 60}")
    print(f"  Total entries:   {results['total_entries']}")
    print(f"  Total aliases:   {results['total_aliases']}")
    print(f"  Total issues:    {len(results['issues'])}")

    if results["by_type"]:
        print(f"\n  By type:")
        for itype, count in sorted(results["by_type"].items()):
            print(f"    {itype:25s}  {count}")

    # Group by type
    by_type: dict[str, list] = defaultdict(list)
    for issue in results["issues"]:
        by_type[issue["type"]].append(issue)

    for itype in ["ALIAS_COLLISION", "IDENTITY_CONFLICT", "UNVERIFIED_ALIAS", "DUPLICATE_ALIAS"]:
        issues = by_type.get(itype, [])
        if not issues:
            continue
        print(f"\n  --- {itype} ({len(issues)}) ---")
        for issue in issues[:25]:
            detail = issue.get("detail", "")
            if len(detail) > 95:
                detail = detail[:92] + "..."
            print(f"    {detail}")
        if len(issues) > 25:
            print(f"    ... and {len(issues) - 25} more")

    print(f"{'=' * 60}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit alias accuracy across PharmaGuide data files")
    parser.add_argument("--file", type=Path, required=True, help="Path to data file")
    parser.add_argument("--mode", choices=["iqm", "clinical", "flat"], required=True)
    parser.add_argument("--list-key", type=str, help="Top-level list key (for flat mode)")
    parser.add_argument("--check-identity", action="store_true",
                        help="Also check UNII-vs-PubChem identity conflicts (slow)")
    parser.add_argument("--no-external", action="store_true",
                        help="Skip external API verification (only check collisions/duplicates)")
    parser.add_argument("--max-checks", type=int, default=0,
                        help="Max entries to check externally (0=all)")
    parser.add_argument("--output", type=Path, help="Save JSON report")
    args = parser.parse_args()

    if args.mode == "flat" and not args.list_key:
        parser.error("--list-key required for flat mode")

    data = json.loads(args.file.read_text())

    results = audit_file(
        data,
        mode=args.mode,
        list_key=args.list_key,
        check_external=not args.no_external,
        check_identity=args.check_identity,
        max_external_checks=args.max_checks,
    )

    _print_results(results)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(results, indent=2))
        print(f"  Report saved to {args.output}")


if __name__ == "__main__":
    main()
