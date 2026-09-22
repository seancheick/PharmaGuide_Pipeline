#!/usr/bin/env python3
"""Content-verify every quote in anchor_verification.json against live sources.

Run from the repo root. Each quote must appear in the PubMed title/abstract, or in
the Europe PMC open-access full text when a pmcid is given. Also checks that the
ledger covers exactly the reference entries whose notes say 'No official DRI'.
"""
from __future__ import annotations

import json
import time
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from api_audit.pubmed_xml import bound_pmc_text, source_quote_matches
LEDGER = json.loads((HERE / "anchor_verification.json").read_text())
REFERENCE = json.loads((ROOT / "scripts/data/rda_optimal_uls.json").read_text())


def get(url: str, tries: int = 4) -> bytes:
    for attempt in range(tries):
        try:
            return urllib.request.urlopen(url, timeout=90).read()
        except Exception as exc:  # noqa: BLE001 - retried, then raised
            error = exc
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"fetch failed {url}: {error}")


anchors = LEDGER["anchors"]
no_dri = {e["id"] for e in REFERENCE["nutrient_recommendations"] if "no official dri" in str(e.get("notes") or "").lower()}
ledger_ids = [a["id"] for a in anchors]
coverage_problems = sorted(set(ledger_ids) ^ no_dri) + [i for i in set(ledger_ids) if ledger_ids.count(i) > 1]

pmids = sorted({e["pmid"] for a in anchors for e in a["evidence"]})
root = ET.fromstring(get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?" + urllib.parse.urlencode(
    {"db": "pubmed", "id": ",".join(pmids), "retmode": "xml"})))
abstracts = {}
for article in root.findall(".//PubmedArticle"):
    pmid = article.findtext(".//MedlineCitation/PMID")
    node = article.find(".//Article")
    title = "".join(node.find("ArticleTitle").itertext()) if node.find("ArticleTitle") is not None else ""
    abstracts[pmid] = title + " " + " ".join("".join(x.itertext()) for x in node.findall("Abstract/AbstractText"))

full_texts: dict[str, tuple[str, str]] = {}
failures, checked, via_full = [], 0, 0
for anchor in anchors:
    for item in anchor["evidence"]:
        checked += 1
        quote = item["quote"]
        if source_quote_matches(quote, abstracts.get(item["pmid"], "")):
            continue
        pmcid = item.get("pmcid")
        if pmcid:
            if pmcid not in full_texts:
                raw = get(f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML")
                full_texts[pmcid] = (item["pmid"], bound_pmc_text(raw, item["pmid"]))
                time.sleep(0.3)
            bound_pmid, full_text = full_texts[pmcid]
            if bound_pmid == item["pmid"] and source_quote_matches(quote, full_text):
                via_full += 1
                continue
        failures.append((anchor["id"], item["pmid"], pmcid, item["quote"][:80]))

print(f"anchors {len(anchors)}; no-DRI reference entries {len(no_dri)}; coverage problems {coverage_problems}")
print(f"PMIDs {len(pmids)} (returned {len(abstracts)}); quotes checked {checked}; via full text {via_full}")
print(f"FAILURES {len(failures)}")
for failure in failures:
    print("  ", failure)
raise SystemExit(1 if failures or coverage_problems or len(abstracts) != len(pmids) else 0)
