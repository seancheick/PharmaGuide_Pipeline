#!/usr/bin/env python3
from __future__ import annotations
"""
EFSA OpenFoodTox validation tool for PharmaGuide harmful additives.

What this script does:
  1. Reads harmful_additives.json.
  2. Cross-references EU regulatory claims against the curated EFSA reference dataset.
  3. Validates ADI/TDI values (our file vs EFSA vs JECFA), genotoxicity status,
     and EFSA opinion references.
  4. Flags ADI mismatches, stale opinions (>8 years), missing EFSA data, and
     US/EU regulatory divergence.

EFSA has no REST API. We use a curated reference dataset:
  data/efsa_openfoodtox_reference.json
  Sourced from EFSA OpenFoodTox v9 (2024), EFSA Journal opinions, and JECFA.
  Run --update-reference to import from a downloaded OpenFoodTox CSV.

Operator runbook:
  1. Dry-run:
       python3 scripts/api_audit/verify_efsa.py --file scripts/data/harmful_additives.json
  2. Search a single substance:
       python3 scripts/api_audit/verify_efsa.py --search "aspartame"
  3. Save report:
       python3 scripts/api_audit/verify_efsa.py --file scripts/data/harmful_additives.json --output /tmp/efsa_report.json
  4. Update reference from downloaded OpenFoodTox CSV:
       python3 scripts/api_audit/verify_efsa.py --update-reference /path/to/openfoodtox.csv
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_ROOT = SCRIPT_DIR.parent
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

EFSA_REFERENCE_PATH = SCRIPTS_ROOT / "data" / "efsa_openfoodtox_reference.json"
STALE_OPINION_YEARS = 8  # Flag opinions older than this

# ADI tolerance: allow 10% float difference before flagging mismatch
ADI_TOLERANCE_FRACTION = 0.10

NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
ADI_EXTRACT_RE = re.compile(
    r"(?:ADI|TDI|TWI)\s+(?:of\s+)?(\d+(?:\.\d+)?)\s*(?:mg|ug|mcg)/\s*kg",
    re.I,
)
EFSA_OPINION_RE = re.compile(
    r"EFSA\s+(?:Journal|opinion|assessment).*?(\d{4})",
    re.I,
)


def _normalize(text: str) -> str:
    return NON_ALNUM_RE.sub(" ", (text or "").lower()).strip()


# ---------------------------------------------------------------------------
# Reference loading
# ---------------------------------------------------------------------------

def load_efsa_reference(path: Path | None = None) -> dict[str, dict]:
    """Load the curated EFSA reference dataset. Returns name → data map."""
    ref_path = path or EFSA_REFERENCE_PATH
    if not ref_path.exists():
        print(f"  [WARNING] EFSA reference not found: {ref_path}", file=sys.stderr)
        return {}

    raw = json.loads(ref_path.read_text())
    substances = raw.get("substances", {})

    # Build lookup by normalized name, CAS, and E-number (including ranges/compounds)
    lookup: dict[str, dict] = {}
    for name, data in substances.items():
        data["_ref_name"] = name
        lookup[_normalize(name)] = data
        if data.get("cas"):
            lookup[data["cas"]] = data
        e_num = data.get("e_number") or ""
        if e_num:
            lookup[_normalize(e_num)] = data
            # Handle compound E-numbers like "E150c/E150d" or "E220-E228"
            for part in re.split(r"[/,]", e_num):
                part = part.strip()
                if part:
                    lookup[_normalize(part)] = data
            # Handle ranges like "E220-E228"
            range_match = re.match(r"E(\d+)\s*-\s*E(\d+)", e_num, re.I)
            if range_match:
                start, end = int(range_match.group(1)), int(range_match.group(2))
                for n in range(start, end + 1):
                    lookup[_normalize(f"e{n}")] = data
    return lookup


# ---------------------------------------------------------------------------
# ADI extraction from our file
# ---------------------------------------------------------------------------

def _extract_adi_from_text(text: str) -> float | None:
    """Extract ADI value from a regulatory_status text string."""
    match = ADI_EXTRACT_RE.search(text)
    if match:
        try:
            return float(match.group(1))
        except (ValueError, TypeError):
            pass
    return None


def _extract_efsa_year_from_text(text: str) -> int | None:
    """Extract EFSA opinion year from EU regulatory text."""
    match = EFSA_OPINION_RE.search(text)
    if match:
        try:
            return int(match.group(1))
        except (ValueError, TypeError):
            pass
    return None


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

def _find_efsa_match(
    entry: dict,
    lookup: dict[str, dict],
) -> dict | None:
    """Try to match a harmful_additives entry to the EFSA reference."""
    name = entry.get("standard_name", "")

    # 1. Exact normalized name
    key = _normalize(name)
    if key in lookup:
        return lookup[key]

    # 2. CAS number
    ext = entry.get("external_ids", {})
    cas = ext.get("cas")
    if cas and cas in lookup:
        return lookup[cas]

    # 3. E-number from aliases (handles E150a, E452i, E471, etc.)
    for alias in entry.get("aliases", []):
        alias_str = str(alias).strip()
        if re.match(r"^[Ee]\d{3}", alias_str):
            ekey = _normalize(alias_str)
            if ekey in lookup:
                return lookup[ekey]

    # 4. Fuzzy: try all aliases by normalized name
    for alias in entry.get("aliases", []):
        akey = _normalize(str(alias))
        if akey and akey in lookup:
            return lookup[akey]

    # 5. Try name without parenthetical qualifiers
    cleaned = re.sub(r"\s*\([^)]*\)\s*", " ", name).strip()
    ckey = _normalize(cleaned)
    if ckey and ckey != key and ckey in lookup:
        return lookup[ckey]

    return None


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_harmful_additives(
    data: dict,
    efsa_lookup: dict[str, dict],
    *,
    list_key: str = "harmful_additives",
) -> dict:
    """Validate harmful_additives.json against EFSA reference data."""
    entries = data.get(list_key, [])
    results: dict[str, Any] = {
        "verified": [],           # EFSA data matches our file
        "adi_mismatch": [],       # ADI value differs
        "stale_opinion": [],      # EFSA opinion older than threshold
        "genotoxicity_flag": [],  # Genotoxicity status differs or positive
        "eu_status_diverge": [],  # US/EU regulatory status diverges
        "no_efsa_data": [],       # Not in EFSA reference
        "enrichment_available": [],  # EFSA has data we don't have
    }
    total = len(entries)

    for i, entry in enumerate(entries):
        eid = entry.get("id", f"entry_{i}")
        name = entry.get("standard_name", "")

        ref = _find_efsa_match(entry, efsa_lookup)

        if ref is None:
            # Diagnose WHY matching failed so operators can fix the root cause
            ext = entry.get("external_ids", {})
            aliases = entry.get("aliases", [])
            hints: list[str] = []
            has_cas = bool(ext.get("cas"))
            has_e_number = any(
                re.match(r"^[Ee]\d{3}", str(a)) for a in aliases
            )
            has_eu_text = bool(entry.get("regulatory_status", {}).get("EU"))

            if not has_cas and not has_e_number:
                hints.append("missing CAS and E-number — add either for better matching")
            elif not has_cas:
                hints.append("missing CAS number in external_ids")
            elif not has_e_number:
                hints.append("no E-number alias found")

            if not has_eu_text:
                hints.append("no EU regulatory_status text — may not be an EU-regulated substance")

            if not aliases:
                hints.append("no aliases — add common names or E-numbers")
            elif len(aliases) < 3:
                hints.append(f"only {len(aliases)} alias(es) — additional aliases may improve matching")

            results["no_efsa_data"].append({
                "id": eid,
                "name": name,
                "hints": hints,
                "has_cas": has_cas,
                "has_e_number": has_e_number,
                "has_eu_text": has_eu_text,
            })
            continue

        record_base = {
            "id": eid,
            "name": name,
            "efsa_ref_name": ref.get("_ref_name", ""),
            "e_number": ref.get("e_number"),
        }

        issues: list[str] = []
        enrichments: list[str] = []

        # --- ADI validation ---
        reg_status = entry.get("regulatory_status", {})
        eu_text = reg_status.get("EU", "")
        who_text = reg_status.get("WHO", "")
        us_text = reg_status.get("US", "")

        # Extract ADI from our EU text
        our_eu_adi = _extract_adi_from_text(eu_text)
        our_who_adi = _extract_adi_from_text(who_text)
        efsa_adi = ref.get("efsa_adi_mg_kg_bw")
        jecfa_adi = ref.get("jecfa_adi_mg_kg_bw")

        if efsa_adi is not None and our_eu_adi is not None:
            diff = abs(efsa_adi - our_eu_adi)
            threshold = max(efsa_adi * ADI_TOLERANCE_FRACTION, 0.01)
            if diff > threshold:
                issues.append("adi_mismatch")
                results["adi_mismatch"].append({
                    **record_base,
                    "our_eu_adi": our_eu_adi,
                    "efsa_adi": efsa_adi,
                    "jecfa_adi": jecfa_adi,
                    "source": ref.get("efsa_adi_source"),
                })
        elif efsa_adi is not None and our_eu_adi is None:
            enrichments.append(f"EFSA ADI available: {efsa_adi} mg/kg/day")

        if jecfa_adi is not None and our_who_adi is not None:
            diff = abs(jecfa_adi - our_who_adi)
            threshold = max(jecfa_adi * ADI_TOLERANCE_FRACTION, 0.01)
            if diff > threshold:
                issues.append("jecfa_adi_mismatch")
                results["adi_mismatch"].append({
                    **record_base,
                    "our_who_adi": our_who_adi,
                    "jecfa_adi": jecfa_adi,
                    "source": "JECFA",
                })

        # --- Stale opinion check ---
        efsa_year = ref.get("efsa_opinion_year")
        our_year = _extract_efsa_year_from_text(eu_text)
        current_year = datetime.now(timezone.utc).year

        if efsa_year and (current_year - efsa_year) > STALE_OPINION_YEARS:
            issues.append("stale_opinion")
            results["stale_opinion"].append({
                **record_base,
                "efsa_opinion_year": efsa_year,
                "years_old": current_year - efsa_year,
                "efsa_source": ref.get("efsa_adi_source"),
            })

        if our_year and efsa_year and our_year != efsa_year:
            # Our file references a different year than the latest EFSA opinion
            if efsa_year > our_year:
                enrichments.append(f"Newer EFSA opinion available: {efsa_year} (we cite {our_year})")

        # --- Genotoxicity flag ---
        geno = ref.get("genotoxicity", "")
        if geno in ("positive", "cannot_be_excluded", "equivocal"):
            # Check if our file mentions this
            our_notes = entry.get("notes", "").lower()
            our_mechanism = entry.get("mechanism_of_harm", "").lower()
            geno_mentioned = any(
                kw in our_notes or kw in our_mechanism
                for kw in ["genotox", "mutagen", "dna damage", "clastogen"]
            )
            if not geno_mentioned:
                issues.append("genotoxicity_flag")
                results["genotoxicity_flag"].append({
                    **record_base,
                    "efsa_genotoxicity": geno,
                    "notes": ref.get("notes", ""),
                })

        # --- IARC classification enrichment ---
        iarc_group = ref.get("iarc_group")
        if iarc_group:
            our_refs = " ".join(entry.get("scientific_references", []))
            if "iarc" not in our_refs.lower():
                enrichments.append(f"IARC Group {iarc_group}: {ref.get('iarc_source', '')}")

        # --- EU status divergence ---
        efsa_status = ref.get("efsa_status", "")
        if efsa_status in ("banned_eu", "restricted_eu"):
            us_lower = us_text.lower()
            if "approved" in us_lower or "gras" in us_lower or "fda approved" in us_lower:
                issues.append("eu_us_divergence")
                results["eu_status_diverge"].append({
                    **record_base,
                    "efsa_status": efsa_status,
                    "us_text": us_text[:120],
                })

        # --- Collect enrichments ---
        if enrichments:
            results["enrichment_available"].append({
                **record_base,
                "enrichments": enrichments,
            })

        # --- Verified if no issues ---
        if not issues:
            results["verified"].append({
                **record_base,
                "efsa_status": ref.get("efsa_status"),
                "efsa_adi": efsa_adi,
            })

        done = i + 1
        if done % 20 == 0 or done == total:
            print(f"  [{done}/{total}] {name}", file=sys.stderr)

    results["total_entries"] = total
    return results


# ---------------------------------------------------------------------------
# Update reference from OpenFoodTox CSV
# ---------------------------------------------------------------------------

def update_reference_from_csv(csv_path: Path, output_path: Path) -> None:
    """Import OpenFoodTox CSV into our JSON reference format.

    The OpenFoodTox CSV columns vary by version. This handles the v9 (2024) format.
    Download from: https://www.efsa.europa.eu/en/microstrategy/openfoodtox
    """
    import csv

    substances: dict[str, dict] = {}
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = (row.get("Substance Name") or row.get("substance_name") or "").strip()
            if not name:
                continue

            cas = (row.get("CAS Number") or row.get("cas_number") or "").strip() or None
            adi_str = (row.get("ADI (mg/kg bw/day)") or row.get("adi_value") or "").strip()
            try:
                adi = float(adi_str) if adi_str and adi_str.lower() not in ("ns", "na", "-", "") else None
            except ValueError:
                adi = None

            genotox = (row.get("Genotoxicity") or row.get("genotoxicity_conclusion") or "").strip().lower()
            if "positive" in genotox:
                genotox_val = "positive"
            elif "negative" in genotox:
                genotox_val = "negative"
            elif "equivocal" in genotox:
                genotox_val = "equivocal"
            else:
                genotox_val = "insufficient_data"

            year_str = (row.get("Year") or row.get("opinion_year") or "").strip()
            try:
                year = int(year_str) if year_str else None
            except ValueError:
                year = None

            e_number = (row.get("E Number") or row.get("e_number") or "").strip() or None

            substances[name] = {
                "e_number": e_number,
                "cas": cas,
                "efsa_adi_mg_kg_bw": adi,
                "efsa_adi_source": f"OpenFoodTox import ({year or 'unknown'})",
                "jecfa_adi_mg_kg_bw": None,
                "genotoxicity": genotox_val,
                "efsa_opinion_year": year,
                "efsa_status": "imported",
                "notes": f"Auto-imported from OpenFoodTox CSV. Verify manually.",
            }

    ref_data = {
        "_metadata": {
            "description": "EFSA OpenFoodTox reference data (auto-imported)",
            "source": f"Imported from {csv_path.name}",
            "last_updated": "2026-03-23",
            "total_entries": len(substances),
        },
        "substances": substances,
    }

    output_path.write_text(json.dumps(ref_data, indent=2, ensure_ascii=False) + "\n")
    print(f"  Imported {len(substances)} substances to {output_path}")


# ---------------------------------------------------------------------------
# Single substance lookup
# ---------------------------------------------------------------------------

def lookup_substance(name: str, efsa_lookup: dict[str, dict]) -> None:
    """Look up and display EFSA data for a single substance."""
    key = _normalize(name)
    ref = efsa_lookup.get(key)
    if ref is None:
        # Try partial match
        for k, v in efsa_lookup.items():
            if key in k or k in key:
                ref = v
                break

    if ref is None:
        print(f"Not found in EFSA reference: {name}")
        return

    print(f"\n  Name:              {ref.get('_ref_name', name)}")
    print(f"  E-Number:          {ref.get('e_number', 'N/A')}")
    print(f"  CAS:               {ref.get('cas', 'N/A')}")
    print(f"  EFSA ADI:          {ref.get('efsa_adi_mg_kg_bw', 'not specified')} mg/kg/day")
    print(f"  JECFA ADI:         {ref.get('jecfa_adi_mg_kg_bw', 'not specified')} mg/kg/day")
    print(f"  Genotoxicity:      {ref.get('genotoxicity', 'N/A')}")
    print(f"  EFSA Status:       {ref.get('efsa_status', 'N/A')}")
    print(f"  EFSA Opinion Year: {ref.get('efsa_opinion_year', 'N/A')}")
    print(f"  Source:            {ref.get('efsa_adi_source', 'N/A')}")
    iarc = ref.get("iarc_group")
    if iarc:
        print(f"  IARC Group:        {iarc} ({ref.get('iarc_source', '')})")
    print(f"  Notes:             {ref.get('notes', '')}")
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print_summary(results: dict) -> None:
    print("\n" + "=" * 60)
    print("EFSA OpenFoodTox Validation Report")
    print("=" * 60)
    print(f"  Total entries scanned:     {results['total_entries']}")
    print(f"  Verified (match):          {len(results['verified'])}")
    print(f"  ADI mismatches:            {len(results['adi_mismatch'])}")
    print(f"  Stale EFSA opinions:       {len(results['stale_opinion'])}")
    print(f"  Genotoxicity flags:        {len(results['genotoxicity_flag'])}")
    print(f"  EU/US divergence:          {len(results['eu_status_diverge'])}")
    print(f"  No EFSA reference data:    {len(results['no_efsa_data'])}")
    print(f"  Enrichment available:      {len(results['enrichment_available'])}")

    if results["adi_mismatch"]:
        print(f"\n  --- ADI Mismatches ({len(results['adi_mismatch'])}) ---")
        for r in results["adi_mismatch"]:
            our_val = r.get("our_eu_adi") or r.get("our_who_adi", "?")
            ref_val = r.get("efsa_adi") or r.get("jecfa_adi", "?")
            print(f"    {r['id']:35s}  ours={our_val}  EFSA/JECFA={ref_val}  {r.get('source', '')}")

    if results["stale_opinion"]:
        print(f"\n  --- Stale Opinions ({len(results['stale_opinion'])}) ---")
        for r in results["stale_opinion"]:
            print(f"    {r['id']:35s}  {r['efsa_opinion_year']} ({r['years_old']}y old)  {r.get('efsa_source', '')}")

    if results["genotoxicity_flag"]:
        print(f"\n  --- Genotoxicity Flags ({len(results['genotoxicity_flag'])}) ---")
        for r in results["genotoxicity_flag"]:
            print(f"    {r['id']:35s}  EFSA: {r['efsa_genotoxicity']}")

    if results["eu_status_diverge"]:
        print(f"\n  --- EU/US Divergence ({len(results['eu_status_diverge'])}) ---")
        for r in results["eu_status_diverge"]:
            print(f"    {r['id']:35s}  EU: {r['efsa_status']:15s}  US: {r['us_text'][:60]}")

    if results["enrichment_available"]:
        print(f"\n  --- Enrichments Available ({len(results['enrichment_available'])}) ---")
        for r in results["enrichment_available"]:
            for e in r["enrichments"]:
                print(f"    {r['id']:35s}  {e}")

    if results["no_efsa_data"]:
        # Split into entries with EU text (likely fixable) vs without (legitimately out of scope)
        no_eu = [r for r in results["no_efsa_data"] if not r.get("has_eu_text")]
        with_eu = [r for r in results["no_efsa_data"] if r.get("has_eu_text")]

        print(f"\n  --- No EFSA Data ({len(results['no_efsa_data'])}) ---")
        if with_eu:
            print(f"\n    Entries WITH EU regulatory text (likely fixable with aliases/CAS):")
            for r in with_eu[:15]:
                hints = "; ".join(r.get("hints", []))
                print(f"      {r['id']:35s}  {r['name'][:30]:30s}  {hints}")
            if len(with_eu) > 15:
                print(f"      ... and {len(with_eu) - 15} more")

        if no_eu:
            print(f"\n    Entries WITHOUT EU text (likely not EFSA-regulated):")
            for r in no_eu[:10]:
                print(f"      {r['id']:35s}  {r['name']}")
            if len(no_eu) > 10:
                print(f"      ... and {len(no_eu) - 10} more")

    print("=" * 60 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate PharmaGuide harmful additives against EFSA data")
    parser.add_argument("--file", type=Path, help="Path to harmful_additives.json")
    parser.add_argument("--list-key", default="harmful_additives", help="Top-level list key")
    parser.add_argument("--search", type=str, help="Look up a single substance")
    parser.add_argument("--output", type=Path, help="Save JSON report to file")
    parser.add_argument("--reference", type=Path, help="Custom EFSA reference file path")
    parser.add_argument("--update-reference", type=Path, metavar="CSV_PATH",
                        help="Import OpenFoodTox CSV into reference JSON")
    args = parser.parse_args()

    if args.update_reference:
        output_path = args.reference or EFSA_REFERENCE_PATH
        update_reference_from_csv(args.update_reference, output_path)
        return

    efsa_lookup = load_efsa_reference(args.reference)
    if not efsa_lookup:
        print("No EFSA reference data loaded. Run with --update-reference or check file path.", file=sys.stderr)
        sys.exit(1)

    if args.search:
        lookup_substance(args.search, efsa_lookup)
        return

    if not args.file:
        parser.error("Either --file, --search, or --update-reference is required")

    data = json.loads(args.file.read_text())
    results = validate_harmful_additives(data, efsa_lookup, list_key=args.list_key)
    _print_summary(results)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(results, indent=2))
        print(f"  Report saved to {args.output}")


if __name__ == "__main__":
    main()
