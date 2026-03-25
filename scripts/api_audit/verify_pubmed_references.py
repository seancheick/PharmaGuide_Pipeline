#!/usr/bin/env python3
"""Verify and enrich DOI/PMID references across PharmaGuide JSON files."""

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

try:
    from .normalize_clinical_pubmed import fetch_articles_for_pmids
except ImportError:
    from normalize_clinical_pubmed import fetch_articles_for_pmids


SCRIPTS_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = SCRIPTS_ROOT / "pubmed_reference_audit_report.json"
DOI_RE = re.compile(r"\b(10\.\d{4,9}/[-._;()/:A-Z0-9]+)\b", re.I)
PMID_RE = re.compile(r"PMID\s*:?\s*(\d{5,8})|\b(\d{5,8})\s*\[pmid\]", re.I)


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            output.append(value)
    return output


def extract_reference_identifiers(text: str) -> dict[str, list[str]]:
    pmids = [match.group(1) or match.group(2) for match in PMID_RE.finditer(text or "")]
    dois = [match.group(1).rstrip(").,;") for match in DOI_RE.finditer(text or "")]
    return {"pmids": _unique([value for value in pmids if value]), "dois": _unique(dois)}


def _walk_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        output: list[str] = []
        for item in value:
            output.extend(_walk_strings(item))
        return output
    if isinstance(value, dict):
        output: list[str] = []
        for item in value.values():
            output.extend(_walk_strings(item))
        return output
    return []


def _collect_entry_reference_text(entry: dict[str, Any]) -> str:
    chunks: list[str] = []
    for key in ("scientific_references", "notable_studies", "notes"):
        chunks.extend(_walk_strings(entry.get(key)))
    return "\n".join(chunks)


def collect_entry_reference_identifiers(entry: dict[str, Any]) -> dict[str, list[str]]:
    pmids: list[str] = []
    dois_without_pmids: list[str] = []

    for ref in entry.get("references_structured") or []:
        if not isinstance(ref, dict):
            continue
        pmid = str(ref.get("pmid") or "").strip()
        doi = str(ref.get("doi") or "").strip()
        if pmid:
            pmids.append(pmid)
        elif doi:
            dois_without_pmids.append(doi)

    free_text_ids = extract_reference_identifiers(_collect_entry_reference_text(entry))
    pmids.extend(free_text_ids["pmids"])
    dois_without_pmids.extend(free_text_ids["dois"])

    return {"pmids": _unique([value for value in pmids if value]), "dois": _unique([value for value in dois_without_pmids if value])}


def _resolve_doi_to_pmid(client: PubMedClient, doi: str) -> str | None:
    search = client.esearch(f"{doi}[aid]", retmax=1)
    ids = (((search or {}).get("esearchresult") or {}).get("idlist") or [])
    return ids[0] if ids else None


def audit_reference_file(file_path: Path, list_key: str, client: PubMedClient) -> dict[str, Any]:
    data = json.loads(file_path.read_text())
    entries = data.get(list_key, [])
    entry_refs: dict[str, dict[str, list[str]]] = {}
    all_pmids: list[str] = []
    orphan_dois_by_entry: dict[str, list[str]] = {}

    for entry in entries:
        entry_id = entry.get("id", "UNKNOWN")
        ids = collect_entry_reference_identifiers(entry)
        entry_refs[entry_id] = {"pmids": list(ids["pmids"]), "dois": list(ids["dois"])}
        all_pmids.extend(entry_refs[entry_id]["pmids"])
        orphan_dois_by_entry[entry_id] = ids["dois"]

    doi_resolution: dict[str, str | None] = {}
    for doi in _unique([doi for values in orphan_dois_by_entry.values() for doi in values]):
        doi_resolution[doi] = _resolve_doi_to_pmid(client, doi)

    broken_dois: list[dict[str, str]] = []
    for entry_id, dois in orphan_dois_by_entry.items():
        resolved_pmids = list(entry_refs[entry_id]["pmids"])
        for doi in dois:
            pmid = doi_resolution.get(doi)
            if pmid:
                resolved_pmids.append(pmid)
            else:
                broken_dois.append({"id": entry_id, "doi": doi})
        entry_refs[entry_id]["pmids"] = _unique(resolved_pmids)
        all_pmids.extend(entry_refs[entry_id]["pmids"])

    unique_pmids = _unique(all_pmids)
    metadata_by_pmid: dict[str, dict[str, Any]] = {}
    if unique_pmids:
        articles = fetch_articles_for_pmids(client, unique_pmids)
        metadata_by_pmid = {article["pmid"]: article for article in articles if article.get("pmid")}

    broken_pmids: list[dict[str, str]] = []
    retracted_refs: list[dict[str, str]] = []
    enriched_entries: list[dict[str, Any]] = []

    for entry_id, refs in entry_refs.items():
        entry_articles = []
        for pmid in refs["pmids"]:
            article = metadata_by_pmid.get(pmid)
            if not article:
                broken_pmids.append({"id": entry_id, "pmid": pmid})
                continue
            if article["retracted"]:
                retracted_refs.append({"id": entry_id, "pmid": pmid, "title": article["title"]})
            entry_articles.append(article)
        enriched_entries.append({"id": entry_id, "references": entry_articles})

    return {
        "file": str(file_path),
        "list_key": list_key,
        "summary": {
            "entries": len(entries),
            "unique_pmids": len(unique_pmids),
            "broken_pmids": len(broken_pmids),
            "broken_dois": len(broken_dois),
            "retracted_references": len(retracted_refs),
        },
        "broken_pmids": broken_pmids,
        "broken_dois": broken_dois,
        "retracted_references": retracted_refs,
        "enriched_entries": enriched_entries,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", required=True, help="JSON file to audit")
    parser.add_argument("--list-key", required=True, help="Top-level list key")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Report output path")
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    report = audit_reference_file(Path(args.file), args.list_key, PubMedClient())
    output_path = Path(args.output)
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=True))
    print(json.dumps(report["summary"], indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
