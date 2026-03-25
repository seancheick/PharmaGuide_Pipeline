#!/usr/bin/env python3
"""Normalize PubMed-backed references inside backed_clinical_studies.json."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

try:
    from .pubmed_client import PubMedClient, parse_pubmed_article_xml
except ImportError:
    from pubmed_client import PubMedClient, parse_pubmed_article_xml


SCRIPTS_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FILE = SCRIPTS_ROOT / "data" / "backed_clinical_studies.json"
PMID_INLINE_RE = re.compile(r"(?:PMID|PubMed)\s*:?\s*(\d{5,8})", re.I)
PMID_BLOCK_RE = re.compile(
    r"(?:PMIDs?|PubMed(?:\s+PMIDs?)?)\s*:?\s*((?:\d{5,8}(?:\s*(?:,|;|and)\s*)?)*)",
    re.I,
)
AUTHOR_YEAR_RE = re.compile(r"([A-Z][A-Za-z'`-]+)\s+et al\.\s+\((\d{4})\)")
ECITMATCH_RE = re.compile(
    r"([A-Z][A-Za-z'`-]+),\s*([A-Z][A-Za-z.]*)\.\s*\((\d{4})\)\s*"
    r"([A-Za-z0-9 .&-]+?)\.\s*(\d+)\s*:\s*(\d+)",
    re.I,
)


def extract_pmids_from_text(text: str) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    source = text or ""

    for match in PMID_BLOCK_RE.finditer(source):
        for pmid in re.findall(r"\d{5,8}", match.group(1)):
            if pmid not in seen:
                seen.add(pmid)
                output.append(pmid)

    for match in PMID_INLINE_RE.finditer(source):
        pmid = match.group(1)
        if pmid not in seen:
            seen.add(pmid)
            output.append(pmid)
    return output


def extract_ecitmatch_candidates(text: str) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    for match in ECITMATCH_RE.finditer(text or ""):
        last_name, initials, year, journal_title, volume, first_page = match.groups()
        candidates.append(
            {
                "journal_title": " ".join(journal_title.lower().split()),
                "year": year,
                "volume": volume,
                "first_page": first_page,
                "author_name": f"{last_name.lower()} {initials.lower().replace('.', '')}",
            }
        )
    return candidates


def build_structured_reference(article: dict[str, Any]) -> dict[str, Any]:
    publication_types = article.get("publication_types") or []
    if "Systematic Review" in publication_types:
        evidence_grade = "systematic_review"
    elif "Meta-Analysis" in publication_types:
        evidence_grade = "meta_analysis"
    elif "Randomized Controlled Trial" in publication_types or any(
        "Clinical Trial" in publication_type for publication_type in publication_types
    ):
        evidence_grade = "rct"
    elif "Observational Study" in publication_types:
        evidence_grade = "observational"
    else:
        evidence_grade = "journal_article"

    return {
        "type": "pubmed",
        "authority": "NCBI PubMed",
        "pmid": article.get("pmid"),
        "doi": article.get("doi"),
        "title": article.get("title"),
        "citation": f"{article.get('journal')} ({article.get('published_date')})",
        "url": article.get("pubmed_url"),
        "published_date": article.get("published_date"),
        "publication_types": publication_types,
        "mesh_terms": article.get("mesh_terms") or [],
        "supplementary_concepts": article.get("supplementary_concepts") or [],
        "evidence_grade": evidence_grade,
        "retracted": bool(article.get("retracted")),
        "supports_claims": [],
        "verification_source": "pubmed_eutils",
    }


def build_search_suggestion(entry: dict[str, Any], text: str) -> dict[str, Any]:
    match = AUTHOR_YEAR_RE.search(text or "")
    author = match.group(1) if match else None
    year = match.group(2) if match else None
    terms = [entry.get("standard_name", "")]
    if author:
        terms.append(f"{author}[auth]")
    if year:
        terms.append(f"{year}[pdat]")
    if "systematic review" in text.lower():
        terms.append("systematic review")
    elif "meta-analysis" in text.lower() or "meta analysis" in text.lower():
        terms.append("meta-analysis")
    elif "randomized" in text.lower() or "rct" in text.lower():
        terms.append("randomized controlled trial")
    return {
        "strategy": "esearch_hint",
        "author": author,
        "year": year,
        "query": " AND ".join(term for term in terms if term),
    }


def fetch_articles_for_pmids(client: PubMedClient, pmids: list[str], batch_size: int = 100) -> list[dict[str, Any]]:
    articles: list[dict[str, Any]] = []
    for start in range(0, len(pmids), batch_size):
        batch = pmids[start:start + batch_size]
        if not batch:
            continue
        articles.extend(parse_pubmed_article_xml(client.efetch(batch)))
    return articles


def fetch_pubmed_suggestions(client: PubMedClient, query: str, limit: int = 3) -> list[dict[str, Any]]:
    if not query:
        return []
    search = client.esearch(query, retmax=limit)
    pmids = (((search or {}).get("esearchresult") or {}).get("idlist") or [])[:limit]
    if not pmids:
        return []
    articles = parse_pubmed_article_xml(client.efetch(pmids))
    suggestions = []
    for article in articles:
        suggestions.append(
            {
                "pmid": article.get("pmid"),
                "title": article.get("title"),
                "published_date": article.get("published_date"),
                "publication_types": article.get("publication_types") or [],
                "retracted": bool(article.get("retracted")),
            }
        )
    return suggestions


def _try_ecitmatch(client: PubMedClient, text: str) -> list[str]:
    candidates = extract_ecitmatch_candidates(text)
    if not candidates:
        return []
    bdata = "\r".join(
        "|".join(
            [
                candidate["journal_title"],
                candidate["year"],
                candidate["volume"],
                candidate["first_page"],
                candidate["author_name"],
                f"cand{idx}",
                "",
            ]
        )
        for idx, candidate in enumerate(candidates, start=1)
    )
    try:
        from .pubmed_client import parse_ecitmatch_rows
    except ImportError:
        from pubmed_client import parse_ecitmatch_rows
    rows = parse_ecitmatch_rows(client.ecitmatch(bdata))
    return [row["pmid"] for row in rows if row.get("pmid", "").isdigit()]


def normalize_clinical_file(file_path: Path, client: PubMedClient, apply: bool = False) -> dict[str, Any]:
    data = json.loads(file_path.read_text())
    entries = data.get("backed_clinical_studies", [])

    pmids: list[str] = []
    pmids_by_id: dict[str, list[str]] = {}
    for entry in entries:
        text = str(entry.get("notable_studies", ""))
        found = extract_pmids_from_text(text)
        if not found:
            found = _try_ecitmatch(client, text)
        pmids_by_id[entry.get("id", "UNKNOWN")] = found
        pmids.extend(found)

    unique_pmids = []
    seen: set[str] = set()
    for pmid in pmids:
        if pmid not in seen:
            seen.add(pmid)
            unique_pmids.append(pmid)

    articles = fetch_articles_for_pmids(client, unique_pmids) if unique_pmids else []
    article_by_pmid = {article["pmid"]: article for article in articles if article.get("pmid")}

    updated = 0
    missing_pmids: dict[str, list[str]] = {}
    unresolved_entries: list[dict[str, Any]] = []
    for entry in entries:
        entry_id = entry.get("id", "UNKNOWN")
        existing_refs = list(entry.get("references_structured") or [])
        existing_non_pubmed_refs = [ref for ref in existing_refs if ref.get("type") != "pubmed"]
        structured = []
        for pmid in pmids_by_id[entry_id]:
            article = article_by_pmid.get(pmid)
            if article:
                structured.append(build_structured_reference(article))
            else:
                missing_pmids.setdefault(entry_id, []).append(pmid)
        if structured:
            merged_refs = existing_non_pubmed_refs + structured
            if merged_refs != existing_refs:
                entry["references_structured"] = merged_refs
                updated += 1
        elif existing_refs:
            entry["references_structured"] = existing_refs
        else:
            recovery_candidate = build_search_suggestion(entry, str(entry.get("notable_studies", "")))
            unresolved_entries.append(
                {
                    "id": entry_id,
                    "standard_name": entry.get("standard_name"),
                    "notable_studies": entry.get("notable_studies"),
                    "recovery_candidate": recovery_candidate,
                    "recovery_suggestions": fetch_pubmed_suggestions(
                        client,
                        recovery_candidate.get("query", ""),
                    ),
                }
            )

    if apply:
        file_path.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n")

    return {
        "file": str(file_path),
        "summary": {
            "entries": len(entries),
            "entries_with_pmids": sum(1 for values in pmids_by_id.values() if values),
            "entries_updated": updated,
            "unique_pmids": len(unique_pmids),
            "missing_pmids": sum(len(values) for values in missing_pmids.values()),
            "unresolved_entries": len(unresolved_entries),
        },
        "missing_pmids": missing_pmids,
        "unresolved_entries": unresolved_entries,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", default=str(DEFAULT_FILE), help="Clinical JSON file to normalize")
    parser.add_argument("--apply", action="store_true", help="Write structured PubMed references into the file")
    parser.add_argument("--output-report", default=str(SCRIPTS_ROOT / "clinical_pubmed_normalization_report.json"))
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    report = normalize_clinical_file(Path(args.file), PubMedClient(), apply=args.apply)
    Path(args.output_report).write_text(json.dumps(report, indent=2, ensure_ascii=True))
    print(json.dumps(report["summary"], indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
