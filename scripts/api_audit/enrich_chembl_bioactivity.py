#!/usr/bin/env python3
from __future__ import annotations
"""
ChEMBL bioactivity enrichment tool for PharmaGuide banned/recalled ingredients.

What this script does:
  1. Reads banned_recalled_ingredients.json for pharmacologically active entries
     (drug adulterants, SARMs, steroids, stimulants, etc.).
  2. Searches ChEMBL by standard_name for known compounds.
  3. Retrieves mechanism of action and primary target data.
  4. Flags explicit prose contradictions when local notes say the mechanism is
     unknown but ChEMBL has known mechanism/target data.
  5. Enriches entries with confirmed ChEMBL target/mechanism data (optional --apply).

Operator runbook:
  1. Dry-run:
       python3 scripts/api_audit/enrich_chembl_bioactivity.py --file scripts/data/banned_recalled_ingredients.json
  2. Search a single compound:
       python3 scripts/api_audit/enrich_chembl_bioactivity.py --search "sildenafil"
  3. Apply enrichments:
       python3 scripts/api_audit/enrich_chembl_bioactivity.py --file scripts/data/banned_recalled_ingredients.json --apply
  4. Save report:
       python3 scripts/api_audit/enrich_chembl_bioactivity.py --file scripts/data/banned_recalled_ingredients.json --output /tmp/chembl_report.json

API:
  ChEMBL REST API (EMBL-EBI) -- free, no key needed.
  Rate limit: self-imposed 0.25s between requests (~4 req/s).
"""

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone, timedelta
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

BASE_URL = "https://www.ebi.ac.uk/chembl/api/data"
RATE_LIMIT_DELAY = 0.25  # ~4 req/s
DEFAULT_CACHE_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 days

# Source categories that contain pharmacologically active compounds worth looking up
ACTIVE_SOURCE_CATEGORIES = {
    "pharmaceutical_contaminant",
    "supplement_adulterant",
    "sarms_prohibited",
    "anabolic_steroid_prohormone",
    "stimulant_designer",
    "hepatotoxic_botanical",
    "nootropic_banned",
    "novel_peptide_research_chemical",
    "schedule_I_psychoactive",
    "synthetic_cannabinoid",
}

# Entity types to skip (product-level entries, not individual compounds)
SKIP_ENTITY_TYPES = {"product", "brand", "company"}

# Names that are classes/umbrellas (no single ChEMBL molecule)
SKIP_NAMES = {
    "synthetic anabolic steroids",
    "synthetic estrogens",
    "phthalates",
    "partially hydrogenated oils",
    "contaminated glp-1 compounds",
    "metal fiber contamination",
    "cannabis/thc",
    "titan sarms llc products",
}

NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def _normalize(text: str) -> str:
    return NON_ALNUM_RE.sub(" ", (text or "").lower()).strip()


def _prose_text(entry: dict) -> str:
    parts: list[str] = []
    for key in ("notes", "reason", "clinical_notes", "mechanism_of_harm"):
        value = entry.get(key)
        if isinstance(value, str):
            parts.append(value)
    return " ".join(parts)


# ---------------------------------------------------------------------------
# ChEMBL client
# ---------------------------------------------------------------------------

class ChEMBLClient:
    """Requests-based wrapper around ChEMBL REST API."""

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
                if datetime.fromisoformat(expires_at) <= datetime.now(timezone.utc):
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
                datetime.now(timezone.utc) + timedelta(seconds=self.cache_ttl_seconds)
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
                resp = _requests.get(
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
            except (_requests.ConnectionError, _requests.Timeout, OSError) as e:
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

    def search_molecule(self, name: str) -> dict | None:
        """Search for a molecule by name. Returns the best match or None."""
        from urllib.parse import quote
        encoded = quote(name, safe="")
        url = f"{BASE_URL}/molecule/search.json?q={encoded}&limit=3"
        data = self._get(url)
        if data is None or data.get("_not_found"):
            return None
        molecules = data.get("molecules", [])
        if not molecules:
            return None

        # Prefer exact pref_name match
        name_lower = name.lower().strip()
        for mol in molecules:
            pref = (mol.get("pref_name") or "").lower()
            if pref == name_lower:
                return mol

        # Accept first result if name appears in synonyms
        first = molecules[0]
        synonyms = first.get("molecule_synonyms", [])
        syn_names = {(s.get("molecule_synonym") or "").lower() for s in synonyms}
        if name_lower in syn_names or _normalize(name) in {_normalize(s) for s in syn_names}:
            return first

        # Accept if pref_name contains our query (partial match for salts)
        pref = (first.get("pref_name") or "").lower()
        if name_lower in pref or _normalize(name) in _normalize(pref):
            return first

        return None

    def get_mechanism(self, chembl_id: str) -> list[dict]:
        """Get mechanism of action for a molecule."""
        url = f"{BASE_URL}/mechanism.json?molecule_chembl_id={chembl_id}&limit=20"
        data = self._get(url)
        if data is None or data.get("_not_found"):
            return []
        return data.get("mechanisms", [])

    def get_target(self, target_chembl_id: str) -> dict | None:
        """Get target details by ChEMBL target ID."""
        url = f"{BASE_URL}/target/{target_chembl_id}.json"
        data = self._get(url)
        if data is None or data.get("_not_found"):
            return None
        return data

    def get_top_bioactivity(self, chembl_id: str, *, limit: int = 10) -> list[dict]:
        """Get top bioactivity records (IC50/EC50/Ki) for a molecule."""
        url = (
            f"{BASE_URL}/activity.json"
            f"?molecule_chembl_id={chembl_id}"
            f"&limit={limit}"
            f"&standard_type__in=IC50,EC50,Ki,Kd"
            f"&pchembl_value__isnull=false"
            f"&order_by=-pchembl_value"
        )
        data = self._get(url)
        if data is None or data.get("_not_found"):
            return []
        return data.get("activities", [])


# ---------------------------------------------------------------------------
# Enrichment helpers
# ---------------------------------------------------------------------------

def _extract_molecule_info(mol: dict) -> dict[str, Any]:
    """Extract key fields from a ChEMBL molecule record."""
    props = mol.get("molecule_properties", {}) or {}
    return {
        "chembl_id": mol.get("molecule_chembl_id"),
        "pref_name": mol.get("pref_name"),
        "molecule_type": mol.get("molecule_type"),
        "max_phase": mol.get("max_phase"),
        "first_approval": mol.get("first_approval"),
        "oral": mol.get("oral"),
        "indication_class": mol.get("indication_class"),
        "molecular_formula": props.get("full_molformula"),
        "molecular_weight": props.get("full_mwt"),
    }


def _extract_mechanism_info(mechanisms: list[dict], client: ChEMBLClient) -> list[dict]:
    """Extract mechanism of action with target details."""
    results = []
    for mech in mechanisms:
        target_id = mech.get("target_chembl_id")
        target_name = None
        target_type = None

        if target_id:
            target = client.get_target(target_id)
            if target:
                target_name = target.get("pref_name")
                target_type = target.get("target_type")

        results.append({
            "mechanism_of_action": mech.get("mechanism_of_action"),
            "action_type": mech.get("action_type"),
            "target_chembl_id": target_id,
            "target_name": target_name,
            "target_type": target_type,
            "direct_interaction": mech.get("direct_interaction"),
        })
    return results


def _extract_bioactivity_summary(activities: list[dict]) -> list[dict]:
    """Summarize top bioactivity records."""
    results = []
    seen_targets: set[str] = set()
    for act in activities:
        target_id = act.get("target_chembl_id", "")
        if target_id in seen_targets:
            continue
        seen_targets.add(target_id)
        results.append({
            "target_chembl_id": target_id,
            "target_pref_name": act.get("target_pref_name"),
            "target_organism": act.get("target_organism"),
            "standard_type": act.get("standard_type"),
            "standard_value": act.get("standard_value"),
            "standard_units": act.get("standard_units"),
            "pchembl_value": act.get("pchembl_value"),
        })
        if len(results) >= 5:
            break
    return results


# ---------------------------------------------------------------------------
# File verification
# ---------------------------------------------------------------------------

def _should_skip_entry(entry: dict) -> str | None:
    """Return skip reason or None if entry should be processed."""
    entity_type = (entry.get("entity_type") or "").lower()
    if entity_type in SKIP_ENTITY_TYPES:
        return f"entity_type={entity_type}"

    name = (entry.get("standard_name") or "").lower()
    if name in SKIP_NAMES:
        return "class/umbrella entry"

    source_cat = entry.get("source_category", "")
    if source_cat and source_cat not in ACTIVE_SOURCE_CATEGORIES:
        return f"source_category={source_cat} not pharmacologically relevant"

    match_mode = entry.get("match_mode", "")
    if match_mode == "historical":
        return "historical entry"

    return None


def _claim_review_issues(entry: dict, mechanisms: list[dict]) -> list[dict]:
    prose = _prose_text(entry)
    if not prose or not mechanisms:
        return []

    if re.search(r"\b(mechanism (?:is )?unknown|unknown mechanism of action)\b", prose, re.I):
        first_known = next(
            (m for m in mechanisms if m.get("mechanism_of_action") or m.get("target_name")),
            None,
        )
        if first_known:
            detail_bits = []
            if first_known.get("mechanism_of_action"):
                detail_bits.append(first_known["mechanism_of_action"])
            if first_known.get("target_name"):
                detail_bits.append(first_known["target_name"])
            return [{
                "type": "claim_contradiction",
                "detail": (
                    "Prose says mechanism is unknown, but ChEMBL has mechanism/target data: "
                    + " / ".join(detail_bits[:2])
                ),
            }]

    return []


def enrich_banned_recalled(
    data: dict,
    client: ChEMBLClient,
    *,
    list_key: str = "ingredients",
    apply: bool = False,
) -> dict:
    """Enrich banned_recalled_ingredients.json with ChEMBL bioactivity data."""
    entries = data.get(list_key, [])
    results: dict[str, Any] = {
        "enriched": [],         # Found in ChEMBL with mechanism/bioactivity
        "found_no_mechanism": [], # Found molecule but no mechanism data
        "claim_review_needed": [], # Explicit prose/ChEMBL contradiction
        "not_found": [],        # Not in ChEMBL
        "skipped": [],          # Not pharmacologically relevant
        "errors": [],
    }
    changes_made = 0
    total = len(entries)

    for i, entry in enumerate(entries):
        eid = entry.get("id", f"entry_{i}")
        name = entry.get("standard_name", "")

        skip_reason = _should_skip_entry(entry)
        if skip_reason:
            results["skipped"].append({"id": eid, "name": name, "reason": skip_reason})
            continue

        # Search ChEMBL
        aliases = entry.get("aliases", [])
        mol = client.search_molecule(name)

        # Try first alias if standard name fails
        if mol is None and aliases:
            for alias in aliases[:2]:
                mol = client.search_molecule(alias)
                if mol is not None:
                    break

        if mol is None:
            results["not_found"].append({"id": eid, "name": name})
            done = i + 1
            if done % 10 == 0 or done == total:
                print(f"  [{done}/{total}] {name} — not found", file=sys.stderr)
            continue

        mol_info = _extract_molecule_info(mol)
        chembl_id = mol_info["chembl_id"]

        # Get mechanism of action
        mechanisms_raw = client.get_mechanism(chembl_id)
        mechanisms = _extract_mechanism_info(mechanisms_raw, client)

        # Get top bioactivity
        activities_raw = client.get_top_bioactivity(chembl_id)
        bioactivity = _extract_bioactivity_summary(activities_raw)

        record = {
            "id": eid,
            "name": name,
            "chembl": mol_info,
            "mechanisms": mechanisms,
            "top_bioactivity": bioactivity,
        }
        claim_issues = _claim_review_issues(entry, mechanisms)
        if claim_issues:
            results["claim_review_needed"].append({**record, "issues": claim_issues})

        if mechanisms or bioactivity:
            results["enriched"].append(record)

            if apply:
                # Write ChEMBL enrichment to external_ids
                if "external_ids" not in entry:
                    entry["external_ids"] = {}
                if not entry["external_ids"].get("chembl_id"):
                    entry["external_ids"]["chembl_id"] = chembl_id
                    changes_made += 1

                # Write mechanism summary to a new chembl block
                if mechanisms and "chembl" not in entry:
                    mech_summary = [
                        {
                            "mechanism": m["mechanism_of_action"],
                            "action_type": m["action_type"],
                            "target": m["target_name"],
                        }
                        for m in mechanisms
                        if m.get("mechanism_of_action")
                    ]
                    if mech_summary:
                        entry["chembl"] = {
                            "chembl_id": chembl_id,
                            "max_phase": mol_info.get("max_phase"),
                            "mechanisms": mech_summary,
                        }
                        changes_made += 1
        else:
            results["found_no_mechanism"].append(record)

        done = i + 1
        if done % 10 == 0 or done == total:
            print(f"  [{done}/{total}] {name} → {chembl_id}", file=sys.stderr)

    results["total"] = total
    results["changes_applied"] = changes_made
    return results


# ---------------------------------------------------------------------------
# Single compound lookup
# ---------------------------------------------------------------------------

def lookup_compound(name: str, client: ChEMBLClient) -> None:
    """Look up and display ChEMBL data for a single compound."""
    mol = client.search_molecule(name)
    if mol is None:
        print(f"Not found in ChEMBL: {name}")
        return

    info = _extract_molecule_info(mol)
    chembl_id = info["chembl_id"]

    print(f"\n  ChEMBL ID:       {chembl_id}")
    print(f"  Preferred Name:  {info['pref_name']}")
    print(f"  Type:            {info['molecule_type']}")
    print(f"  Max Phase:       {info['max_phase']}")
    print(f"  First Approval:  {info['first_approval'] or 'N/A'}")
    print(f"  Indication:      {info['indication_class'] or 'N/A'}")
    print(f"  Formula:         {info['molecular_formula'] or 'N/A'}")
    print(f"  MW:              {info['molecular_weight'] or 'N/A'}")

    mechanisms = client.get_mechanism(chembl_id)
    if mechanisms:
        print(f"\n  Mechanisms of Action ({len(mechanisms)}):")
        for m in mechanisms:
            action = m.get("mechanism_of_action", "Unknown")
            target_id = m.get("target_chembl_id", "")
            action_type = m.get("action_type", "")
            print(f"    - {action} [{action_type}] → {target_id}")
    else:
        print("\n  No mechanism of action data in ChEMBL")

    activities = client.get_top_bioactivity(chembl_id)
    if activities:
        summary = _extract_bioactivity_summary(activities)
        print(f"\n  Top Bioactivity ({len(summary)} targets):")
        for a in summary:
            target = a.get("target_pref_name", "Unknown")
            val = a.get("pchembl_value", "?")
            stype = a.get("standard_type", "?")
            print(f"    - {target}: {stype} pChEMBL={val}")
    else:
        print("\n  No bioactivity data in ChEMBL")

    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print_summary(results: dict) -> None:
    print("\n" + "=" * 60)
    print("ChEMBL Bioactivity Enrichment Report")
    print("=" * 60)
    print(f"  Total entries:            {results['total']}")
    print(f"  Enriched (mech/bio):      {len(results['enriched'])}")
    print(f"  Found, no mechanism:      {len(results['found_no_mechanism'])}")
    print(f"  Claim review needed:      {len(results['claim_review_needed'])}")
    print(f"  Not found in ChEMBL:      {len(results['not_found'])}")
    print(f"  Skipped (not relevant):   {len(results['skipped'])}")
    print(f"  API errors:               {len(results['errors'])}")
    if results.get("changes_applied"):
        print(f"  Changes applied:          {results['changes_applied']}")

    if results["enriched"]:
        print(f"\n  --- Enriched ({len(results['enriched'])}) ---")
        for r in results["enriched"]:
            mechs = r.get("mechanisms", [])
            mech_str = mechs[0]["mechanism_of_action"] if mechs else "no mechanism"
            chembl_id = r["chembl"]["chembl_id"]
            print(f"    {r['id']:40s}  {chembl_id:15s}  {mech_str}")

    if results["not_found"]:
        print(f"\n  --- Not Found ({len(results['not_found'])}) ---")
        for r in results["not_found"]:
            print(f"    {r['id']:40s}  {r['name']}")

    if results["claim_review_needed"]:
        print(f"\n  --- Claim Review Needed ({len(results['claim_review_needed'])}) ---")
        for r in results["claim_review_needed"]:
            detail = r["issues"][0]["detail"] if r.get("issues") else ""
            print(f"    {r['id']:40s}  {detail[:90]}")

    print("=" * 60 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Enrich PharmaGuide banned/recalled with ChEMBL bioactivity")
    parser.add_argument("--file", type=Path, help="Path to banned_recalled_ingredients.json")
    parser.add_argument("--list-key", default="ingredients", help="Top-level list key (default: ingredients)")
    parser.add_argument("--search", type=str, help="Look up a single compound")
    parser.add_argument("--apply", action="store_true", help="Write ChEMBL enrichments to file")
    parser.add_argument("--output", type=Path, help="Save JSON report to file")
    parser.add_argument("--cache-dir", type=Path, default=SCRIPTS_ROOT / ".cache", help="Cache directory")
    args = parser.parse_args()

    cache_path = args.cache_dir / "chembl_cache.json"

    client = ChEMBLClient(
        cache_path=cache_path,
        cache_ttl_seconds=DEFAULT_CACHE_TTL_SECONDS,
    )

    try:
        if args.search:
            lookup_compound(args.search, client)
            return

        if not args.file:
            parser.error("Either --file or --search is required")

        data = json.loads(args.file.read_text())
        results = enrich_banned_recalled(data, client, list_key=args.list_key, apply=args.apply)
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
