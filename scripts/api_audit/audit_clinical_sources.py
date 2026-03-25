#!/usr/bin/env python3
"""Audit source explicitness and contradiction risks in backed_clinical_studies.json."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_ROOT = SCRIPT_DIR.parent
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

DATA_PATH = SCRIPTS_ROOT / "data" / "backed_clinical_studies.json"

EXPLICIT_SOURCE_PATTERNS = (
    "PMID",
    "PubMed",
    "NIH ODS",
    "NCCIH",
    "LiverTox",
    "FDA",
    "Cochrane",
    "EFSA",
    "ClinicalTrials.gov",
)


def _has_explicit_source_text(entry: Dict[str, Any]) -> bool:
    text = " ".join(
        str(entry.get(field, "")) for field in ("notes", "notable_studies")
    )
    return any(token in text for token in EXPLICIT_SOURCE_PATTERNS)


def _looks_contradictory(entry: Dict[str, Any]) -> List[str]:
    text = " ".join(
        str(entry.get(field, "")).lower() for field in ("notes", "notable_studies")
    )
    evidence_level = str(entry.get("evidence_level", "")).lower()
    study_type = str(entry.get("study_type", "")).lower()
    published = {str(item).lower() for item in entry.get("published_studies", [])}
    issues: List[str] = []

    if "no standalone rct" in text and study_type.startswith("rct"):
        issues.append("study_type_claims_rct_but_notes_deny_standalone_rct")
    if "no dedicated" in text and evidence_level == "ingredient-human":
        issues.append("ingredient_human_but_notes_deny_dedicated_human_trial")
    if "no published clinical trials" in text and "rct" in published:
        issues.append("published_studies_include_rct_but_notes_deny_trials")
    if "manufacturer-only" in text and evidence_level in {"ingredient-human", "product-human", "branded-rct"}:
        issues.append("human_evidence_level_but_notes_describe_manufacturer_only_support")

    return issues


def audit_entries(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    uncited: List[str] = []
    contradictions: List[Dict[str, Any]] = []

    for entry in entries:
        entry_id = entry.get("id", "UNKNOWN")
        if not _has_explicit_source_text(entry):
            uncited.append(entry_id)

        issues = _looks_contradictory(entry)
        if issues:
            contradictions.append({"id": entry_id, "issues": issues})

    return {
        "total_entries": len(entries),
        "entries_without_explicit_source_text": uncited,
        "entries_with_possible_contradictions": contradictions,
    }


def load_and_audit(path: Path = DATA_PATH) -> Dict[str, Any]:
    data = json.loads(path.read_text())
    entries = data.get("backed_clinical_studies", [])
    return audit_entries(entries)


def main() -> None:
    report = load_and_audit()
    print(json.dumps(report, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
