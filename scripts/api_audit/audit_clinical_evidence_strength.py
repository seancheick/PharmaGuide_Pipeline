#!/usr/bin/env python3
"""Audit claimed clinical evidence strength against structured PubMed metadata."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCRIPTS_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FILE = SCRIPTS_ROOT / "data" / "backed_clinical_studies.json"

STUDY_TYPE_STRENGTH = {
    "retracted": -1,
    "journal_article": 0,
    "case_report": 1,
    "observational": 2,
    "rct": 3,
    "rct_single": 3,
    "rct_multiple": 4,
    "meta_analysis": 5,
    "systematic_review": 6,
    "systematic_review_meta": 6,
    "clinical_strain": 3,
}


def recommend_evidence_level(
    publication_types: list[str],
    retracted: bool,
    reference_count: int = 1,
    title: str | None = None,
) -> dict[str, str]:
    title_lc = (title or "").lower()
    if retracted:
        return {"recommended_evidence_level": "retracted", "recommended_study_type": "retracted"}
    if "Systematic Review" in publication_types or "Meta-Analysis" in publication_types:
        return {
            "recommended_evidence_level": "systematic-review-meta",
            "recommended_study_type": "systematic_review_meta",
        }
    if "systematic review" in title_lc or "meta-analysis" in title_lc or "meta analysis" in title_lc:
        return {
            "recommended_evidence_level": "systematic-review-meta",
            "recommended_study_type": "systematic_review_meta",
        }
    if "Randomized Controlled Trial" in publication_types:
        return {
            "recommended_evidence_level": "rct-multiple" if reference_count > 1 else "rct",
            "recommended_study_type": "rct_multiple" if reference_count > 1 else "rct_single",
        }
    if any("clinical trial" in publication_type.lower() for publication_type in publication_types):
        return {
            "recommended_evidence_level": "rct-multiple" if reference_count > 1 else "rct",
            "recommended_study_type": "rct_multiple" if reference_count > 1 else "rct_single",
        }
    if any(token in title_lc for token in ("randomized", "randomised", "placebo-controlled", "double-blind trial", "clinical trial")):
        return {
            "recommended_evidence_level": "rct-multiple" if reference_count > 1 else "rct",
            "recommended_study_type": "rct_multiple" if reference_count > 1 else "rct_single",
        }
    if "Observational Study" in publication_types:
        return {"recommended_evidence_level": "observational", "recommended_study_type": "observational"}
    if "Case Reports" in publication_types or "Case Report" in publication_types:
        return {"recommended_evidence_level": "case-report", "recommended_study_type": "case_report"}
    if "case report" in title_lc:
        return {"recommended_evidence_level": "case-report", "recommended_study_type": "case_report"}
    return {"recommended_evidence_level": "journal-article", "recommended_study_type": "journal_article"}


def audit_entries(entries: list[dict[str, Any]]) -> dict[str, Any]:
    mismatches = []
    issues = []

    for entry in entries:
        refs = entry.get("references_structured", []) or []
        pubmed_refs = [ref for ref in refs if ref.get("type", "pubmed") == "pubmed"]
        if not pubmed_refs:
            if refs:
                continue
            if str(entry.get("evidence_level", "")).lower() == "ingredient-human":
                issues.append(
                    {
                        "id": entry.get("id", "UNKNOWN"),
                        "issue": "missing_structured_pubmed_support",
                        "claimed_study_type": entry.get("study_type"),
                        "claimed_evidence_level": entry.get("evidence_level"),
                    }
                )
            continue

        best_recommendation = None
        best_strength = -2
        retracted_pmids = []

        for ref in pubmed_refs:
            publication_types = ref.get("publication_types") or []
            recommendation = recommend_evidence_level(
                publication_types,
                bool(ref.get("retracted")),
                reference_count=len(pubmed_refs),
                title=ref.get("title"),
            )
            strength = STUDY_TYPE_STRENGTH.get(recommendation["recommended_study_type"], 0)
            if strength > best_strength:
                best_strength = strength
                best_recommendation = recommendation
            if recommendation["recommended_study_type"] == "retracted":
                retracted_pmids.append(ref.get("pmid"))

        claimed_study_type = entry.get("study_type")
        claimed_strength = STUDY_TYPE_STRENGTH.get(str(claimed_study_type), 0)
        if best_recommendation and claimed_strength > best_strength:
            mismatches.append(
                {
                    "id": entry.get("id", "UNKNOWN"),
                    "claimed_study_type": claimed_study_type,
                    "recommended_study_type": best_recommendation["recommended_study_type"],
                    "recommended_evidence_level": best_recommendation["recommended_evidence_level"],
                }
            )
        if retracted_pmids:
            issues.append(
                {
                    "id": entry.get("id", "UNKNOWN"),
                    "issue": "retracted_pubmed_reference",
                    "pmids": retracted_pmids,
                }
            )

    return {
        "summary": {"entries": len(entries), "mismatches": len(mismatches), "issues": len(issues)},
        "mismatches": mismatches,
        "issues": issues,
    }


def audit_file(file_path: Path) -> dict[str, Any]:
    data = json.loads(file_path.read_text())
    entries = data.get("backed_clinical_studies", [])
    report = audit_entries(entries)
    report["file"] = str(file_path)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", default=str(DEFAULT_FILE))
    parser.add_argument("--output-report", default=str(SCRIPTS_ROOT / "clinical_evidence_strength_report.json"))
    args = parser.parse_args()
    report = audit_file(Path(args.file))
    Path(args.output_report).write_text(json.dumps(report, indent=2, ensure_ascii=True))
    print(json.dumps(report["summary"], indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
