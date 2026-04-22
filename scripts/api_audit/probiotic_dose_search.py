#!/usr/bin/env python3
"""probiotic_dose_search.py — Find and content-verify dose-anchor PMIDs for
clinically relevant probiotic strains.

Rationale: PharmaGuide's no-hallucinated-citations rule (see
critical_no_hallucinated_citations.md) requires every PMID in clinical
data to be content-verified by fetching the title+abstract and
confirming the paper is actually about the claimed strain and
indication. This helper automates the search / fetch / title-screen
loop.

Workflow per strain:
    1. esearch PubMed for `"<strain>"[TIAB] AND (dose OR "CFU" OR
       trial OR efficacy)` scoped to reviews + RCTs.
    2. efetch top N abstracts.
    3. Print title + journal + year + abstract excerpt per hit.
    4. Human reads the list, picks the dose-anchor PMID(s), and then
       manually authors cfu_thresholds in clinically_relevant_strains.json.

NEVER pick a PMID without reading its title and abstract here — that
is how hallucinated citations enter production.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPTS_ROOT))
sys.path.insert(0, str(SCRIPT_DIR))

from pubmed_client import (  # noqa: E402
    PubMedClient,
    load_pubmed_config,
    parse_pubmed_article_xml,
)


def search_and_fetch(strain_name: str, extra_terms: str = "", n: int = 10) -> list[dict]:
    """Return list of abstract dicts for top `n` PubMed hits."""
    client = PubMedClient(load_pubmed_config())

    query_bits = [f'"{strain_name}"[TIAB]']
    if extra_terms:
        query_bits.append(f"({extra_terms})")
    # favour reviews / meta-analyses / RCTs for dose anchors
    query_bits.append(
        "(Review[PT] OR Meta-Analysis[PT] OR Systematic Review[PT] OR "
        "Randomized Controlled Trial[PT])"
    )
    query = " AND ".join(query_bits)
    esearch = client.esearch(db="pubmed", term=query, retmax=n, sort="relevance")
    ids = []
    if isinstance(esearch, dict):
        esr = esearch.get("esearchresult") or {}
        ids = esr.get("idlist") or []
    if not ids:
        return []

    xml_text = client.efetch(ids=ids, db="pubmed", rettype="xml", retmode="xml")
    arts = parse_pubmed_article_xml(xml_text)

    # rate-limit politeness between strains
    time.sleep(0.2)
    return arts


def render(strain_name: str, arts: list[dict]) -> str:
    out = [f"\n=== {strain_name} — {len(arts)} hits ==="]
    for i, a in enumerate(arts, 1):
        pmid = a.get("pmid", "?")
        title = (a.get("title") or "").strip()
        journal = a.get("journal") or "?"
        year = a.get("pub_year") or "?"
        abstr = (a.get("abstract") or "").replace("\n", " ")[:300]
        out.append(f"\n[{i}] PMID {pmid} — {journal} {year}")
        out.append(f"    {title}")
        out.append(f"    {abstr}")
    return "\n".join(out)


DEFAULT_PILOT = [
    ("Lactobacillus rhamnosus GG",        "antibiotic diarrhea OR diarrhea prevention"),
    ("Lactobacillus reuteri DSM 17938",   "infant colic OR crying"),
    ("Saccharomyces boulardii",           "diarrhea OR Clostridium"),
    ("Bifidobacterium lactis HN019",      "constipation OR immune OR bowel"),
    ("Lactobacillus plantarum 299v",      "irritable bowel OR IBS"),
]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--strain", help="override: search only this strain")
    ap.add_argument("--indication", default="", help="extra search terms")
    ap.add_argument("-n", type=int, default=8, help="hits per strain")
    args = ap.parse_args()

    strains = (
        [(args.strain, args.indication)]
        if args.strain
        else DEFAULT_PILOT
    )

    for name, ind in strains:
        arts = search_and_fetch(name, ind, args.n)
        print(render(name, arts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
