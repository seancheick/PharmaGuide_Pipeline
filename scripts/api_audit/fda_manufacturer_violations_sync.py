#!/usr/bin/env python3
"""Synch manufacturer violation entries from FDA openFDA recall feeds.

This script is designed to complement the existing `fda_weekly_sync.py` pipeline.
It reads the current manufacturer violations data and appends any newly detected
manufacturer recalls that implicate dietary supplements.

Usage:
    python scripts/api_audit/fda_manufacturer_violations_sync.py [--days 30] [--output <path>] [--api-key <FDA_KEY>]

Output:
    writes JSON to file (default: scripts/data/manufacturer_violations.json)

Note:
    1) It uses openFDA `food/enforcement` and `drug/enforcement` sources
       to capture dietary supplement-relevant recalls.
    2) It deduplicates by FDA recall number before adding new entries.
    3) It maintains the existing manufacturer normalization strategy for matching.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# Ensure scripts/ source module path is visible when run from repo root.
REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from api_audit.fda_weekly_sync import (
    fetch_enforcement,
    fetch_fda_rss,
    is_noise,
    classify_record,
)

WORKSPACE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = WORKSPACE_DIR / "scripts" / "data" / "manufacturer_violations.json"
DEDUCTION_EXPL_PATH = WORKSPACE_DIR / "scripts" / "data" / "manufacture_deduction_expl.json"
REPORT_DIR = WORKSPACE_DIR / "scripts" / "api_audit" / "reports"

RECENCY_BUCKETS = [
    (365, 1.0),
    (3 * 365, 0.5),
    (5 * 365, 0.25),
    (float("inf"), 0.0),
]

VIOLATION_CODE_MAP = {
    "CRI_TOXIC": -20,
    "CRI_UNDRUG": -15,
    "CRI_ALLER": -12,
    "CRI_CONTA": -15,
    "CRI_ADVERS": -20,
    "HIGH_CII": -10,
    "HIGH_CGMP_CRIT": -12,
    "MOD_CIII_SING": -3,
    "MOD_CGMP": -8,
    "MOD_BRAND": -5,
    "LOW_WARN": -2,
}

SUPPLEMENT_KEYWORDS = [
    "dietary supplement", "supplement", "nutraceutical", "vitamin", "mineral",
    "herbal", "botanical", "fat burner", "weight loss", "pre-workout",
    "sarm", "cbd", "kava", "kratom", "testosterone booster",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync manufacturer_violations.json from FDA openFDA data")
    parser.add_argument("--days", type=int, default=30, help="Lookback window in days for FDA enforcement events")
    parser.add_argument("--output", default=str(DATA_PATH), help="Output filename for manufacturer_violations.json")
    parser.add_argument("--report", default=None, help="Output report path JSON (default auto)")
    parser.add_argument("--api-key", default=os.environ.get("OPENFDA_API_KEY", ""), help="openFDA API key")
    parser.add_argument("--include-rss", action="store_true", help="Also include FDA RSS sources in candidate selection")
    parser.add_argument("--confirm", action="store_true", help="Interactive confirmation prompt before writing new entries")
    parser.add_argument("--dry-run", action="store_true", help="Do not persist file, only print summary")
    return parser.parse_args()


def is_supplement_record(record: dict) -> bool:
    relevant, _, _ = classify_record(record)
    return relevant


def extract_manufacturer_from_text(record: dict) -> str | None:
    """Extract manufacturer from RSS title or text if structured field is missing."""
    # Check RSS title for company names
    title = (record.get("title") or "").strip()
    if title:
        # Pattern: "Company Name Issues Recall..."; extract "Company Name"
        match = re.match(r"^([A-Za-z\s&.,'-]+?)\s+(?:Issues|Recalls?|Advises|Announces)", title)
        if match:
            return match.group(1).strip()
    
    # Check RSS description/reason for addresses or entity names
    reason = (record.get("reason_for_recall") or record.get("description") or "").strip()
    if reason:
        # Look for patterns like "Company Name, City, State" or "... by Company Name"
        match = re.search(r"(?:by|manufactured by|from)\s+([A-Za-z\s&.,'-]+?)(?:,|\s+(?:of|located|in|california|new york|texas))", reason, re.IGNORECASE)
        if match:
            company = match.group(1).strip()
            if len(company) > 2 and len(company) < 100:  # sanity check
                return company
    
    return None


def recency_multiplier(days_since: int) -> float:
    for max_days, multiplier in RECENCY_BUCKETS:
        if days_since <= max_days:
            return multiplier
    return 0.0


def normalize_company_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (name or "").strip().lower())


def infer_violation_code(reason: str, classification: str, status: str) -> str:
    r = (reason or "").lower()
    if any(tok in r for tok in [" aller", "allergen", "peanut", "wheat", "milk", "nuts"]):
        return "CRI_ALLER"
    if any(tok in r for tok in ["metformin", "sildenafil", "tadalafil", "diclofenac", "dexamethasone", "sibutramine", "phenolphthalein"]):
        return "CRI_UNDRUG"
    if any(tok in r for tok in ["salmonella", "listeria", "e. coli", "ecoli", "botulism"]):
        return "CRI_CONTA"
    if any(tok in r for tok in ["toxic", "poison", "death", "hospital", "serious"]):
        return "CRI_TOXIC"
    if "class i" in (classification or "").lower():
        return "CRI_TOXIC"
    if "class ii" in (classification or "").lower():
        return "HIGH_CII"
    if "class iii" in (classification or "").lower():
        return "MOD_CIII_SING"
    if status.lower() in ["ongoing", "open", "active"]:
        return "HIGH_CGMP_CRIT"
    return "LOW_WARN"


def severity_level_from_code(code: str) -> str:
    if code.startswith("CRI_"):
        return "critical"
    if code.startswith("HIGH_"):
        return "high"
    if code.startswith("MOD_"):
        return "moderate"
    return "low"


def date_from_openfda(value: str) -> str | None:
    # openFDA dates are often YYYYMMDD, or YYYY-MM-DD.
    value = (value or "").strip()
    if not value:
        return None
    try:
        if re.fullmatch(r"\d{8}", value):
            dt = datetime.strptime(value, "%Y%m%d")
            return dt.date().isoformat()
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            return value
        dt = datetime.fromisoformat(value)
        return dt.date().isoformat()
    except Exception:
        return None


def compute_total_deduction(base: int, unresolved: bool, repeat: bool, multi_line: bool, recency_mult: float) -> float:
    extra = 0
    if unresolved:
        extra -= 3
    if repeat:
        extra -= 5
    if multi_line:
        extra -= 3
    out = (base + extra) * recency_mult
    out = float(round(out, 2))
    return out


def load_deduction_expl() -> dict:
    try:
        with open(DEDUCTION_EXPL_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def main() -> int:
    args = parse_args()

    date_end = datetime.now().strftime("%Y%m%d")
    date_start = (datetime.now() - timedelta(days=args.days)).strftime("%Y%m%d")
    report_filename = args.report or f"fda_manufacturer_violations_sync_report_{date_end}.json"
    os.makedirs(REPORT_DIR, exist_ok=True)
    report_path = Path(report_filename) if args.report else REPORT_DIR / report_filename

    # Fetch data from FDAs.
    food_records = fetch_enforcement("food/enforcement", date_start, date_end, api_key=args.api_key)
    drug_records = fetch_enforcement("drug/enforcement", date_start, date_end, api_key=args.api_key)

    # Optionally include safety alert RSS as extra signal.
    rss_records = []
    if args.include_rss:
        print("[FDA Sync] Fetching FDA MedWatch safety alerts RSS...")
        rss_records.extend(fetch_fda_rss(
            "https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/medwatch/rss.xml",
            args.days,
        ))
        print(f"           {len(rss_records)} items")

        print("[FDA Sync] Fetching FDA Drugs RSS...")
        rss_drugs = fetch_fda_rss(
            "https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/drugs/rss.xml",
            args.days,
        )
        rss_records.extend(rss_drugs)
        print(f"           {len(rss_records)} items total")

    raw_candidates = list(food_records) + list(drug_records) + list(rss_records)

    existing = {
        "deprecated": [],
        "by_recall_id": {},
        "by_identifier": {},
    }
    data = {}
    try:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        for violations in data.get("manufacturer_violations", []):
            rid = str(violations.get("fda_recall_id", "")).strip().upper()
            if rid:
                existing["by_recall_id"][rid] = violations
    except FileNotFoundError:
        data = {
            "_metadata": {
                "description": "Manufacturer FDA violations and recall history",
                "purpose": "manufacturer_penalties",
                "schema_version": "5.0.0",
                "last_updated": date.today().isoformat(),
                "total_entries": 0,
                "statistics": {},
            },
            "manufacturer_violations": [],
        }
    except json.JSONDecodeError as e:
        print(f"ERROR: cannot parse existing manufacturer violations data: {e}", file=sys.stderr)
        return 1

    existing_ids = [int(re.sub(r"\D", "", item.get("id", "V0"))) for item in data.get("manufacturer_violations", []) if re.search(r"\d+", item.get("id", ""))]
    next_id = max(existing_ids, default=0) + 1

    added = []
    skipped = 0
    skip_reasons = {
        "not_supplement": 0,
        "existing_recall_id": 0,
        "noise_filtered": 0,
    }

    # if source contains 2+ recalls from same firm => repeat_violation handles 1. We derive later.
    manufacturer_event_counts = {}
    for record in raw_candidates:
        if not is_supplement_record(record):
            skipped += 1
            skip_reasons["not_supplement"] += 1
            continue

        recall_number = (record.get("recall_number") or "").strip().upper()
        if recall_number and recall_number in existing["by_recall_id"]:
            skipped += 1
            skip_reasons["existing_recall_id"] += 1
            continue

        # Try structured field first, then fall back to text extraction
        mfr = (record.get("recalling_firm") or "").strip()
        if not mfr:
            mfr = extract_manufacturer_from_text(record) or ""
        if not mfr:
            mfr = "Unknown Manufacturer"

        if any(is_noise(record) for _ in [record]):
            skipped += 1
            skip_reasons["noise_filtered"] += 1
            continue

        d = date_from_openfda(record.get("recall_initiation_date") or record.get("report_date"))
        if d is None:
            d = date.today().isoformat()
        date_obj = datetime.fromisoformat(d).date() if isinstance(d, str) else d
        days_since = (date.today() - date_obj).days
        recency = recency_multiplier(days_since)

        # Look for hint of repeated or unresolved
        key = normalize_company_name(mfr)
        manufacturer_event_counts[key] = manufacturer_event_counts.get(key, 0) + 1

        code = infer_violation_code(record.get("reason_for_recall"), record.get("classification"), record.get("status"))
        base_deduction = VIOLATION_CODE_MAP.get(code, -10)
        severity_level = severity_level_from_code(code)

        is_resolved = str(record.get("status") or "").lower() in ["terminated", "completed", "closed", "resolved"]
        # repeat inference is per manufacturer history and current batch
        repeat = manufacturer_event_counts[key] > 1
        multiple_product_lines = False

        total_deduction_applied = compute_total_deduction(base_deduction, not is_resolved, repeat, multiple_product_lines, recency)
        if total_deduction_applied < -25:
            total_deduction_applied = -25.0

        source_type = record.get("_source_type", "openfda_enforcement")
        fda_source_url = ""
        if recall_number:
            fda_source_url = (
                f"https://www.accessdata.fda.gov/scripts/ires/?action=Redirect"
                f"&recall_number={recall_number}"
            )
        elif source_type in ("fda_rss", "dea_federal_register"):
            fda_source_url = record.get("link", "")

        entry = {
            "id": f"V{next_id:03d}",
            "source_type": source_type,
            "fda_source_url": fda_source_url,
            "manufacturer": mfr,
            "manufacturer_id": key or normalize_company_name(mfr),
            "product": (record.get("product_description") or record.get("product_quantity") or "Unknown").strip(),
            "product_category": "supplement",
            "violation_type": record.get("classification") or "Recall",
            "severity_level": severity_level,
            "violation_code": code,
            "base_deduction": base_deduction,
            "reason": (record.get("reason_for_recall") or "").strip(),
            "contamination_type": code.lower(),
            "date": d,
            "days_since_violation": days_since,
            "recency_multiplier": recency,
            "illnesses_reported": int(record.get("report_date") or 0) if False else None,
            "deaths_reported": None,
            "states_affected": None,
            "product_lines_affected": 1,
            "is_resolved": is_resolved,
            "fda_action": "Recall",
            "fda_recall_id": recall_number,
            "repeat_violation": repeat,
            "multiple_product_lines": multiple_product_lines,
            "total_deduction_applied": total_deduction_applied,
            "user_facing_note": (
                f"⚠️ FDA Recall {recall_number} by {mfr} for {(record.get('product_description') or record.get('product_quantity') or 'Unknown').strip()}: "
                f"{(record.get('reason_for_recall') or '').strip()} (classification {record.get('classification') or 'Recall'}). "
                f"Penalty: {total_deduction_applied} pts."
            ),
            "internal_note": "Auto-generated by fda_manufacturer_violations_sync.py",
            "allergens": None,
            "cdc_outbreak_investigation": None,
            "cgmp_violations": None,
            "contaminants": None,
            "fda_warning_letter_id": None,
            "heavy_metals": None,
            "hospitalizations_reported": None,
            "lead_level_ppm": None,
            "related_violation_ids": None,
            "undeclared_drugs": None,
        }

        added.append(entry)
        next_id += 1

    # Append new entries and update metadata
    if added:
        data.setdefault("manufacturer_violations", []).extend(added)

    # recompute meta counters
    stats = {
        "critical_violations": 0,
        "high_violations": 0,
        "moderate_violations": 0,
        "low_violations": 0,
        "unresolved_count": 0,
        "resolved_count": 0,
        "repeat_offenders": 0,
        "active_outbreaks": 0,
    }

    manufacturer_total = {}
    for entry in data.get("manufacturer_violations", []):
        lvl = (entry.get("severity_level") or "").lower()
        if lvl in stats:
            stats[f"{lvl}_violations"] = stats.get(f"{lvl}_violations", 0) + 1
        if entry.get("is_resolved"):
            stats["resolved_count"] += 1
        else:
            stats["unresolved_count"] += 1
        mn = normalize_company_name(entry.get("manufacturer", ""))
        manufacturer_total[mn] = manufacturer_total.get(mn, 0) + 1

    stats["repeat_offenders"] = sum(1 for nm, c in manufacturer_total.items() if c > 1)

    data.setdefault("_metadata", {})["last_updated"] = date.today().isoformat()
    data["_metadata"]["total_entries"] = len(data.get("manufacturer_violations", []))
    data["_metadata"]["statistics"] = stats

    if args.confirm and added:
        print("Interactive review: the following new entries will be added:")
        for e in added:
            print(f"  - {e['id']} {e['manufacturer']} / {e['product']} / {e['fda_recall_id'] or 'no recall ID'}")
        confirm = input("Proceed and write changes? [y/N]: ").strip().lower()
        if confirm != "y":
            print("Aborted by user. No file written.")
            return 0

    if args.dry_run:
        print(f"dry-run: would add {len(added)} records, skip {skipped} existing/noise")
        report = {
            "generated_at": datetime.now().isoformat(),
            "generated_by": "fda_manufacturer_violations_sync.py",
            "lookback_days": args.days,
            "include_rss": args.include_rss,
            "data_file": str(args.output),
            "report_file": str(report_path),
            "total_candidates": len(raw_candidates),
            "added_count": len(added),
            "skipped_count": skipped,
            "skip_reasons": skip_reasons,
            "existing_total": len(existing["by_recall_id"]),
            "added_ids": [e["id"] for e in added],
            "source_counts": {
                "food_enforcement": len(food_records),
                "drug_enforcement": len(drug_records),
                "rss": len(rss_records),
            },
            "statistics": stats,
            "new_entries": added,
            "dry_run": True,
        }
        os.makedirs(REPORT_DIR, exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"Report saved: {report_path}")
        return 0

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    report = {
        "generated_at": datetime.now().isoformat(),
        "generated_by": "fda_manufacturer_violations_sync.py",
        "lookback_days": args.days,
        "include_rss": args.include_rss,
        "data_file": str(args.output),
        "report_file": str(report_path),
        "total_candidates": len(raw_candidates),
        "added_count": len(added),
        "skipped_count": skipped,
        "skip_reasons": skip_reasons,
        "existing_total": len(existing["by_recall_id"]),
        "added_ids": [e["id"] for e in added],
        "source_counts": {
            "food_enforcement": len(food_records),
            "drug_enforcement": len(drug_records),
            "rss": len(rss_records),
        },
        "statistics": stats,
        "new_entries": added,
    }

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"Wrote {args.output}: {len(added)} new entries, {skipped} skipped")
    print(f"Report saved: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
