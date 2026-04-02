#!/usr/bin/env python3
"""
Enrichment orchestrator for botanical_ingredients.json, other_ingredients.json,
and standardized_botanicals.json.

Runs the existing verify_cui.py, verify_unii.py, and verify_pubchem.py scripts
against these files to populate:
  - CUI (UMLS concept identifier)
  - external_ids.unii (FDA UNII)
  - external_ids.cas (CAS registry number)
  - external_ids.pubchem_cid (PubChem compound ID)
  - gsrs (FDA GSRS substance data: CFR sections, DSLD count, relationships)
  - rxcui (RxNorm identifier, where applicable)

Pre-enrichment steps:
  - For botanical_ingredients: ensures latin_name is in aliases for better API matching.
  - For standardized_botanicals: copies CUI from botanical_ingredients where overlap exists.

Usage:
  # Dry-run all three files (report only):
    python3 scripts/api_audit/enrich_botanicals.py

  # Dry-run a single file:
    python3 scripts/api_audit/enrich_botanicals.py --file botanical_ingredients

  # Apply safe fills:
    python3 scripts/api_audit/enrich_botanicals.py --apply

  # Run only CUI enrichment:
    python3 scripts/api_audit/enrich_botanicals.py --only cui

  # Run only UNII/GSRS enrichment:
    python3 scripts/api_audit/enrich_botanicals.py --only unii

  # Run only PubChem enrichment:
    python3 scripts/api_audit/enrich_botanicals.py --only pubchem

Environment:
  UMLS_API_KEY — required for CUI lookups (set in .env or pass to verify_cui.py)
  No key needed for GSRS or PubChem (free public APIs).
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
UTC = timezone.utc
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_ROOT = SCRIPT_DIR.parent
DATA_DIR = SCRIPTS_ROOT / "data"

# Target files and their list keys
TARGETS = {
    "botanical_ingredients": {
        "file": DATA_DIR / "botanical_ingredients.json",
        "list_key": "botanical_ingredients",
        "cui_field": "CUI",  # capital C in this file
    },
    "other_ingredients": {
        "file": DATA_DIR / "other_ingredients.json",
        "list_key": "other_ingredients",
        "cui_field": "CUI",  # capital C in this file
    },
    "standardized_botanicals": {
        "file": DATA_DIR / "standardized_botanicals.json",
        "list_key": "standardized_botanicals",
        "cui_field": "CUI",  # will be created
    },
}


def ensure_latin_in_aliases(data: dict, list_key: str) -> int:
    """Add latin_name to aliases where missing. Returns count of entries updated."""
    entries = data.get(list_key, [])
    updated = 0
    for entry in entries:
        latin = entry.get("latin_name")
        if not latin or not isinstance(latin, str) or not latin.strip():
            continue
        latin_clean = latin.strip()
        aliases = entry.get("aliases", [])
        aliases_lower = {a.lower().strip() for a in aliases if isinstance(a, str)}
        if latin_clean.lower() not in aliases_lower:
            aliases.append(latin_clean)
            entry["aliases"] = aliases
            updated += 1
    return updated


def copy_cuis_from_botanicals(std_data: dict, bot_data: dict) -> int:
    """Copy CUI from botanical_ingredients to standardized_botanicals where names overlap."""
    bot_entries = bot_data.get("botanical_ingredients", [])
    # Build lookup: standard_name (lower) -> CUI
    name_to_cui = {}
    latin_to_cui = {}
    for entry in bot_entries:
        cui = entry.get("CUI")
        if not cui:
            continue
        sname = (entry.get("standard_name") or "").lower().strip()
        if sname:
            name_to_cui[sname] = cui
        latin = (entry.get("latin_name") or "").lower().strip()
        if latin:
            latin_to_cui[latin] = cui

    std_entries = std_data.get("standardized_botanicals", [])
    filled = 0
    for entry in std_entries:
        if entry.get("CUI"):
            continue  # already has one
        sname = (entry.get("standard_name") or "").lower().strip()
        cui = name_to_cui.get(sname)
        if not cui:
            # Try matching via aliases
            for alias in entry.get("aliases", []):
                alias_lower = alias.lower().strip()
                cui = name_to_cui.get(alias_lower) or latin_to_cui.get(alias_lower)
                if cui:
                    break
        if cui:
            entry["CUI"] = cui
            filled += 1
    return filled


def run_enrichment_script(script_name: str, file_path: Path, list_key: str,
                          cui_field: str = "CUI", apply: bool = False) -> int:
    """Run one of the verify_*.py scripts. Returns the exit code."""
    script_path = SCRIPT_DIR / script_name

    args = [
        sys.executable, str(script_path),
        "--file", str(file_path),
        "--list-key", list_key,
    ]

    if script_name == "verify_cui.py":
        args.extend(["--cui-field", cui_field])

    if apply:
        args.append("--apply")

    print(f"\n{'='*60}")
    print(f"Running: {script_name} on {file_path.name}")
    print(f"{'='*60}")

    result = subprocess.run(args, cwd=str(SCRIPTS_ROOT))
    return result.returncode


def main():
    parser = argparse.ArgumentParser(
        description="Enrichment orchestrator for botanical/other ingredient files"
    )
    parser.add_argument(
        "--file",
        choices=list(TARGETS.keys()),
        help="Run on a single file (default: all three)",
    )
    parser.add_argument(
        "--only",
        choices=["cui", "unii", "pubchem"],
        help="Run only one enrichment type",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply safe fills (default: dry-run)",
    )
    args = parser.parse_args()

    targets = {args.file: TARGETS[args.file]} if args.file else TARGETS
    scripts = {
        "cui": "verify_cui.py",
        "unii": "verify_unii.py",
        "pubchem": "verify_pubchem.py",
    }
    if args.only:
        scripts = {args.only: scripts[args.only]}

    # --- Pre-enrichment: ensure latin_name in aliases for botanical files ---
    for name, target in targets.items():
        file_path = target["file"]
        list_key = target["list_key"]

        data = json.loads(file_path.read_text())

        changed = False

        # Add latin_name to aliases for botanical files
        if name in ("botanical_ingredients", "standardized_botanicals"):
            if "latin_name" in (data.get(list_key, [{}])[0] if data.get(list_key) else {}):
                count = ensure_latin_in_aliases(data, list_key)
                if count > 0:
                    print(f"[PRE] Added latin_name to aliases for {count} entries in {file_path.name}")
                    changed = True

        # Copy CUIs from botanical_ingredients to standardized_botanicals
        if name == "standardized_botanicals":
            bot_data = json.loads(TARGETS["botanical_ingredients"]["file"].read_text())
            filled = copy_cuis_from_botanicals(data, bot_data)
            if filled > 0:
                print(f"[PRE] Copied {filled} CUIs from botanical_ingredients → standardized_botanicals")
                changed = True

        if changed and args.apply:
            file_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    # --- Run enrichment scripts ---
    for target_name, target in targets.items():
        file_path = target["file"]
        list_key = target["list_key"]
        cui_field = target["cui_field"]

        for script_key, script_name in scripts.items():
            rc = run_enrichment_script(
                script_name, file_path, list_key,
                cui_field=cui_field, apply=args.apply,
            )
            if rc != 0:
                print(f"\n[WARN] {script_name} exited with code {rc} for {file_path.name}")

    print(f"\n{'='*60}")
    mode = "APPLIED" if args.apply else "DRY-RUN"
    print(f"Done ({mode}). Review output above for fills, rejections, and not-found entries.")
    if not args.apply:
        print("Re-run with --apply to write safe fills to the data files.")


if __name__ == "__main__":
    main()
