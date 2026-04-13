#!/usr/bin/env python3
"""Content-verify every PubMed citation across all pipeline data files.

Goes beyond existence checks — fetches the actual article title and abstract
from PubMed, then checks whether the cited paper actually mentions the
ingredients/drugs/nutrients claimed in the data entry.

Usage:
    # Full content verification (hits PubMed API)
    python3 scripts/api_audit/verify_all_citations_content.py

    # Verify a single file
    python3 scripts/api_audit/verify_all_citations_content.py --file timing_rules.json

    # Output JSON report
    python3 scripts/api_audit/verify_all_citations_content.py --report scripts/reports/citation_content_audit.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import ssl
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_ROOT = SCRIPT_DIR.parent
DATA_DIR = SCRIPTS_ROOT / "data"

PMID_RE = re.compile(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d+)")
RATE_LIMIT = 0.35  # seconds between API calls

# SSL context
try:
    SSL_CTX = ssl.create_default_context()
except ssl.SSLError:
    SSL_CTX = ssl._create_unverified_context()


# ── Data file definitions ─────────────────────────────────────────────

FILE_CONFIGS = [
    {
        "file": "timing_rules.json",
        "array_key": "timing_rules",
        "id_field": "id",
        "topic_fields": ["ingredient1", "ingredient2", "advice", "mechanism"],
        "sources_field": "sources",
    },
    {
        "file": "medication_depletions.json",
        "array_key": "depletions",
        "id_field": "id",
        "topic_extractor": lambda e: [
            e.get("drug_ref", {}).get("display_name", ""),
            e.get("depleted_nutrient", {}).get("standard_name", ""),
            e.get("mechanism", ""),
        ],
        "sources_field": "sources",
    },
    {
        "file": "curated_interactions/curated_interactions_v1.json",
        "array_key": "interactions",
        "id_field": "id",
        "topic_fields": ["agent1_name", "agent2_name", "mechanism"],
        "sources_field": "source_urls",
        "source_format": "url_list",  # list of URL strings, not dicts
    },
    {
        "file": "curated_interactions/med_med_pairs_v1.json",
        "array_key": "interactions",
        "id_field": "id",
        "topic_fields": ["agent1_name", "agent2_name", "mechanism"],
        "sources_field": "source_urls",
        "source_format": "url_list",
    },
]


# ── PubMed API ─────────────────────────────────────────────────────────

def fetch_articles(pmids: list[str]) -> dict[str, dict]:
    """Fetch title + abstract for a batch of PMIDs via efetch."""
    articles = {}
    for i in range(0, len(pmids), 8):
        batch = pmids[i:i + 8]
        ids_str = ",".join(batch)
        url = (
            f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
            f"?db=pubmed&id={ids_str}&retmode=xml"
        )
        api_key = os.environ.get("NCBI_API_KEY") or os.environ.get("PUBMED_API_KEY", "")
        if api_key:
            url += f"&api_key={api_key}"

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "pharmaguide-audit/1.0"})
            with urllib.request.urlopen(req, timeout=20, context=SSL_CTX) as resp:
                root = ET.fromstring(resp.read().decode("utf-8"))

            for article in root.findall(".//PubmedArticle"):
                pmid_el = article.find(".//PMID")
                if pmid_el is None:
                    continue
                pmid = pmid_el.text.strip()

                title_el = article.find(".//ArticleTitle")
                title = title_el.text if title_el is not None and title_el.text else ""

                # Collect all abstract sections
                abstract_parts = []
                for abs_el in article.findall(".//AbstractText"):
                    if abs_el.text:
                        abstract_parts.append(abs_el.text)
                abstract = " ".join(abstract_parts)

                # Collect MeSH terms
                mesh_terms = []
                for mesh in article.findall(".//MeshHeading/DescriptorName"):
                    if mesh.text:
                        mesh_terms.append(mesh.text.lower())

                articles[pmid] = {
                    "title": title,
                    "abstract": abstract[:800],
                    "mesh_terms": mesh_terms,
                }
        except Exception as e:
            print(f"  API error batch {i}: {e}", file=sys.stderr)

        time.sleep(RATE_LIMIT)

    return articles


def search_pubmed(query: str, max_results: int = 3) -> list[dict]:
    """Search PubMed for papers matching a query. Returns [{pmid, title}]."""
    encoded = urllib.parse.quote(query)
    url = (
        f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        f"?db=pubmed&term={encoded}&retmax={max_results}&sort=relevance&retmode=xml"
    )
    api_key = os.environ.get("NCBI_API_KEY") or os.environ.get("PUBMED_API_KEY", "")
    if api_key:
        url += f"&api_key={api_key}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "pharmaguide-audit/1.0"})
        with urllib.request.urlopen(req, timeout=15, context=SSL_CTX) as resp:
            root = ET.fromstring(resp.read().decode("utf-8"))
        pmids = [el.text for el in root.findall(".//Id")]
        time.sleep(RATE_LIMIT)

        if not pmids:
            return []

        articles = fetch_articles(pmids)
        return [
            {"pmid": p, "title": articles.get(p, {}).get("title", "")}
            for p in pmids
            if p in articles
        ]
    except Exception as e:
        print(f"  Search error: {e}", file=sys.stderr)
        return []


# ── Content matching ───────────────────────────────────────────────────

def extract_topic_words(entry: dict, config: dict) -> list[str]:
    """Extract topic words from an entry for content matching."""
    texts = []
    if "topic_extractor" in config:
        texts = config["topic_extractor"](entry)
    else:
        for field in config.get("topic_fields", []):
            val = entry.get(field, "")
            if isinstance(val, str):
                texts.append(val)

    words = set()
    for text in texts:
        for word in re.split(r"[\s/,\(\)\-]+", text.lower()):
            if len(word) > 3 and word not in {
                "with", "that", "this", "from", "into", "when", "your",
                "take", "avoid", "class", "drug", "both", "risk", "does",
                "have", "been", "also", "most", "more", "used", "than",
                "some", "very", "only", "such", "each", "which", "their",
                "other", "about", "supplement", "supplements", "medication",
                "medications",
            }:
                words.add(word)
    return list(words)


def content_matches(article: dict, topic_words: list[str]) -> tuple[str, float]:
    """Check if an article's content matches the claimed topic.

    Returns (status, confidence):
    - "match" (>= 2 topic words found in title+abstract+mesh)
    - "partial" (1 topic word found)
    - "mismatch" (0 topic words found)
    """
    if not article:
        return "not_found", 0.0

    text = (
        article.get("title", "")
        + " "
        + article.get("abstract", "")
        + " "
        + " ".join(article.get("mesh_terms", []))
    ).lower()

    matches = [w for w in topic_words if w in text]
    ratio = len(matches) / max(len(topic_words), 1)

    if len(matches) >= 2:
        return "match", ratio
    elif len(matches) == 1:
        return "partial", ratio
    else:
        return "mismatch", 0.0


# ── Extract PMIDs from entries ─────────────────────────────────────────

def extract_pmids_from_entry(entry: dict, config: dict) -> list[dict]:
    """Extract PMID citations from an entry."""
    results = []
    sources_field = config.get("sources_field", "sources")
    source_format = config.get("source_format", "dict_list")

    sources = entry.get(sources_field, [])
    if not isinstance(sources, list):
        return results

    for s in sources:
        url = ""
        if source_format == "url_list":
            url = s if isinstance(s, str) else ""
        else:
            if not isinstance(s, dict):
                continue
            if s.get("source_type") != "pubmed":
                continue
            url = s.get("url", "")

        m = PMID_RE.search(url)
        if m:
            results.append({
                "pmid": m.group(1),
                "url": url,
            })

    return results


# ── Main verification ──────────────────────────────────────────────────

def verify_file(config: dict) -> dict:
    """Verify all PubMed citations in one data file."""
    filepath = DATA_DIR / config["file"]
    if not filepath.exists():
        return {"file": config["file"], "status": "not_found", "entries": []}

    with open(filepath) as f:
        data = json.load(f)

    entries = data.get(config["array_key"], [])
    results = []
    all_pmids = {}  # pmid → list of entry contexts

    # Collect all PMIDs
    for entry in entries:
        entry_id = entry.get(config["id_field"], "unknown")
        topic_words = extract_topic_words(entry, config)
        pmid_refs = extract_pmids_from_entry(entry, config)

        for ref in pmid_refs:
            pmid = ref["pmid"]
            if pmid not in all_pmids:
                all_pmids[pmid] = []
            all_pmids[pmid].append({
                "entry_id": entry_id,
                "topic_words": topic_words,
            })

    if not all_pmids:
        return {"file": config["file"], "status": "no_pubmed_citations", "entries": []}

    # Fetch all articles
    print(f"\n  {config['file']}: fetching {len(all_pmids)} unique PMIDs...")
    articles = fetch_articles(list(all_pmids.keys()))

    # Verify content match
    for pmid, contexts in all_pmids.items():
        article = articles.get(pmid)
        for ctx in contexts:
            status, confidence = content_matches(article, ctx["topic_words"])
            result = {
                "entry_id": ctx["entry_id"],
                "pmid": pmid,
                "status": status,
                "confidence": round(confidence, 2),
                "topic_words_checked": ctx["topic_words"][:10],
                "article_title": article.get("title", "NOT FOUND") if article else "NOT FOUND",
            }
            if status == "mismatch":
                result["suggestion"] = "REPLACE — paper does not mention claimed topic"
            elif status == "partial":
                result["suggestion"] = "REVIEW — only partial topic match"
            results.append(result)

    match_count = sum(1 for r in results if r["status"] == "match")
    partial_count = sum(1 for r in results if r["status"] == "partial")
    mismatch_count = sum(1 for r in results if r["status"] == "mismatch")
    notfound_count = sum(1 for r in results if r["status"] == "not_found")

    return {
        "file": config["file"],
        "total_citations": len(results),
        "match": match_count,
        "partial": partial_count,
        "mismatch": mismatch_count,
        "not_found": notfound_count,
        "pass_rate": f"{(match_count + partial_count) / max(len(results), 1):.0%}",
        "entries": results,
    }


def main():
    parser = argparse.ArgumentParser(description="Content-verify all PubMed citations")
    parser.add_argument("--file", help="Verify only this file (e.g., timing_rules.json)")
    parser.add_argument("--report", type=Path, help="Write JSON report to this path")
    args = parser.parse_args()

    # Load env
    sys.path.insert(0, str(SCRIPTS_ROOT))
    try:
        import env_loader  # noqa: F401
    except ImportError:
        pass

    configs = FILE_CONFIGS
    if args.file:
        configs = [c for c in configs if args.file in c["file"]]
        if not configs:
            print(f"ERROR: no config for file '{args.file}'", file=sys.stderr)
            return 1

    print("=" * 60)
    print("PubMed Citation Content Verification")
    print("=" * 60)

    all_results = []
    total_match = 0
    total_mismatch = 0

    for config in configs:
        result = verify_file(config)
        all_results.append(result)
        total_match += result.get("match", 0)
        total_mismatch += result.get("mismatch", 0)

        print(f"\n  {result['file']}:")
        print(f"    Citations: {result.get('total_citations', 0)}")
        print(f"    ✅ Match: {result.get('match', 0)}")
        print(f"    ⚠️  Partial: {result.get('partial', 0)}")
        print(f"    ❌ Mismatch: {result.get('mismatch', 0)}")
        print(f"    Pass rate: {result.get('pass_rate', 'N/A')}")

        # Print mismatches
        for entry in result.get("entries", []):
            if entry["status"] == "mismatch":
                print(f"    ❌ {entry['entry_id']} PMID {entry['pmid']}: {entry['article_title']}")

    print(f"\n{'=' * 60}")
    print(f"TOTAL: ✅ {total_match} match  ❌ {total_mismatch} mismatch")

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with open(args.report, "w") as f:
            json.dump(all_results, f, indent=2, ensure_ascii=False)
        print(f"Report: {args.report}")

    return 1 if total_mismatch > 0 else 0


if __name__ == "__main__":
    import urllib.parse
    sys.exit(main())
