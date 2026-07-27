#!/usr/bin/env python3
"""Suppress known real-but-unrelated depletion PMIDs without rewriting claims.

This is deliberately a safety containment batch, not a literature repair.
Each listed PMID resolved in PubMed but its live title/abstract did not support
the medication--nutrient claim for which it was cited.  The Flutter checker
suppresses ``needs_revision`` entries, so this removes the misleading consumer
surface while each medication family receives its own evidence review.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


DATA = Path(__file__).resolve().parents[2] / "data" / "medication_depletions.json"
REVIEWED_AT = "2026-07-26"
REVIEWER = "medication_depletion_content_audit_2026_07_26"

# PMID -> entry id.  DEP_OCP_MAGNESIUM and DEP_OCP_ZINC share one unrelated
# PMID; every entry gets an independent publication decision.
KNOWN_CONTENT_MISMATCHES = {
    "DEP_OCP_MAGNESIUM": "23636014",
    "DEP_OCP_ZINC": "23636014",
    "DEP_ANTIPSYCHOTICS_VITAMIND": "25638514",
    "DEP_ANTIPSYCHOTICS_COQ10": "18316143",
    "DEP_STIMULANTS_VITAMINC": "10870150",
    "DEP_HIVPI_VITAMIND": "21694637",
    "DEP_HIVPI_ZINC": "12591569",
    "DEP_IMMUNOSUPPRESSANTS_MAGNESIUM": "16641596",
    "DEP_IMMUNOSUPPRESSANTS_VITAMIND": "19528952",
    "DEP_BENZODIAZEPINES_MELATONIN": "2733455",
    "DEP_BVITAMINS_INTERACTIONS": "2132402",
}


def _note(pmid: str) -> str:
    return (
        f"Citation content audit ({REVIEWED_AT}): PMID {pmid} resolves in PubMed "
        "but is a content mismatch — its live title/abstract does not support this "
        "medication-nutrient claim. Suppressed pending a family-specific, reviewed "
        "replacement; no clinical conclusion is made from this citation."
    )


def apply(check_only: bool = False) -> int:
    document = json.loads(DATA.read_text(encoding="utf-8"))
    by_id = {entry["id"]: entry for entry in document["depletions"]}
    changes: list[str] = []
    for entry_id, pmid in KNOWN_CONTENT_MISMATCHES.items():
        entry = by_id[entry_id]
        expected = {
            "citation_review_status": "needs_revision",
            "reviewed_at": REVIEWED_AT,
            "reviewer": REVIEWER,
            "citation_review_note": _note(pmid),
        }
        for field, value in expected.items():
            if entry.get(field) != value:
                entry[field] = value
                changes.append(f"~ {entry_id}.{field}")

    if not changes:
        print("Known ghost suppressions: already applied (no changes).")
        return 0
    print("Known ghost suppressions:")
    for change in changes:
        print(f"  {change}")
    if check_only:
        print("\n--check: nothing written.")
        return 1
    DATA.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nWrote {DATA}.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="report without writing")
    raise SystemExit(apply(check_only=parser.parse_args().check))
