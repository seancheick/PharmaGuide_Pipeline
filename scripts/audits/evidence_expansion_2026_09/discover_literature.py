#!/usr/bin/env python3
"""Bounded, logged PubMed discovery for Wave 1 identities (no screening, no judgment).

For each identity: three queries (reviews/guidelines, trials, safety signals) over the label
spellings seen in the scored corpus, capped retrieval, batched efetch, parsed with
the shared ``pubmed_client.parse_pubmed_article_xml``. Output per identity:

  * search log (committed, reproducible): exact term, run date, total count,
    retrieved count, truncation flag;
  * candidate records (scratch): title, abstract, publication types, MeSH,
    integrity flags, DOI, PMC id — the input a screener reads;
  * a one-line-per-record screening index (scratch) so titles are triaged before abstracts.

The efficacy query deliberately avoids positive-outcome words, and it does not
require the Humans MeSH tag (new records are not yet indexed); it only drops
records indexed as animal-only. Human status is decided later from several signals.

Resumable: identities whose candidate file already exists are skipped.

    python3 scripts/audits/evidence_expansion_2026_09/discover_literature.py \
        --partition <partition.json> --candidates-dir <scratch dir>
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))

import env_loader  # noqa: E402,F401  (NCBI_API_KEY)
from api_audit.pubmed_client import PubMedClient, parse_pubmed_article_xml  # noqa: E402

_NOT_ANIMAL_ONLY = "NOT (animals[mh] NOT humans[mh])"
_REVIEW_TYPES = ("(meta-analysis[pt] OR systematic review[pt] OR practice guideline[pt] OR guideline[pt] "
                 "OR \"systematic review\"[ti] OR \"meta-analysis\"[ti])")
QUERY_ROLES = {
    # role: (filter, retrieval cap)
    "reviews": (f"{_REVIEW_TYPES} {_NOT_ANIMAL_ONLY}", 60),
    "trials": ("(randomized controlled trial[pt] OR controlled clinical trial[pt] OR randomized[tiab] "
               "OR randomised[tiab] OR placebo[tiab] OR crossover[tiab]) "
               f"NOT {_REVIEW_TYPES} {_NOT_ANIMAL_ONLY}", 80),
    "safety": ("(adverse effects[sh] OR toxicity[sh] OR case reports[pt] OR hepatotoxicity[tiab] "
               "OR \"adverse event\"[tiab] OR \"adverse events\"[tiab] OR poisoning[sh]) "
               f"{_NOT_ANIMAL_ONLY}", 20),
}
BATCH = 200


# Label-name fragments that are not identities. Splitting "Garcinia cambogia (Fruit)
# Extract" must never leave a bare "extract"[tiab] clause in the query.
GENERIC_NAME_PARTS = {"extract", "powder", "complex", "blend", "oil", "juice", "concentrate",
                      "root", "fruit", "leaf", "leaves", "seed", "bark", "flower", "herb", "peel",
                      "rind", "berry", "acid", "salt", "capsule", "micronized", "standardized",
                      "organic", "natural", "whole", "dried", "freeze dried", "usp", "nf"}

# Homonym traps for bare names, applied as explicit NOT clauses so the exclusion is
# visible in the committed search log rather than hidden in a hand-curated PMID list.
HOMONYM_EXCLUSIONS = {
    "l_tyrosine": '("tyrosine kinase"[tiab] OR "tyrosine phosphatase"[tiab] OR "tyrosine residue"[tiab] '
                  'OR "tyrosine hydroxylase"[tiab] OR protein-tyrosine kinases[mh])',
    "l_histidine": '("histidine kinase"[tiab] OR "histidine tag"[tiab] OR "histidine-rich"[tiab])',
    "methionine": '("methionine synthase"[tiab] OR "methionine aminopeptidase"[tiab])',
}


def name_clause(identity: dict) -> str:
    names: list[str] = []
    for raw in [identity["label_name"], *identity.get("label_spellings_seen", [])]:
        for part in re.split(r"[()]", str(raw)):
            part = re.sub(r"[,;]\s*(micronized|powder|extract)$", "", part.strip(), flags=re.I).strip()
            if (len(part) >= 3 and part.lower() not in GENERIC_NAME_PARTS
                    and part.lower() not in {n.lower() for n in names}):
                names.append(part)
    clause = "(" + " OR ".join(f'"{name}"[tiab]' for name in names[:8]) + ")"
    excluded = HOMONYM_EXCLUSIONS.get(identity["canonical_id"])
    return f"{clause} NOT {excluded}" if excluded else clause


def pmc_ids(xml_text: str) -> dict[str, str]:
    found = {}
    for article in ET.fromstring(xml_text).findall(".//PubmedArticle"):
        pmid = article.findtext(".//MedlineCitation/PMID")
        pmc = article.findtext(".//PubmedData/ArticleIdList/ArticleId[@IdType='pmc']")
        if pmid and pmc:
            found[pmid] = pmc
    return found


def run_identity(client: PubMedClient, identity: dict) -> tuple[dict, list[dict]]:
    names = name_clause(identity)
    log = {"canonical_id": identity["canonical_id"], "run_date": dt.date.today().isoformat(),
           "source": "NCBI PubMed E-utilities", "queries": []}
    pmid_roles: dict[str, set[str]] = {}
    for role, (flt, cap) in QUERY_ROLES.items():
        term = f"{names} AND {flt}"
        result = client.esearch(term, retmax=cap, sort="relevance")
        body = result.get("esearchresult") or {}
        ids = list(body.get("idlist") or [])
        total = int(body.get("count") or 0)
        log["queries"].append({"role": role, "term": term, "count": total, "retrieved": len(ids),
                               "truncated": total > len(ids), "sort": "relevance"})
        for pmid in ids:
            pmid_roles.setdefault(pmid, set()).add(role)
    records = []
    ids = sorted(pmid_roles, key=int)
    for start in range(0, len(ids), BATCH):
        xml_text = client.efetch(ids[start:start + BATCH], rettype="abstract")
        pmc = pmc_ids(xml_text)
        for article in parse_pubmed_article_xml(xml_text):
            article["pmc_id"] = pmc.get(article["pmid"])
            article["query_roles"] = sorted(pmid_roles.get(article["pmid"], ()))
            records.append(article)
    log["unique_pmids"] = len(ids)
    log["parsed_records"] = len(records)
    return log, records


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--partition", required=True, type=Path)
    parser.add_argument("--candidates-dir", required=True, type=Path)
    args = parser.parse_args()
    args.candidates_dir.mkdir(parents=True, exist_ok=True)
    log_path = OUT / "wave1_search_log.json"
    search_log = json.loads(log_path.read_text()) if log_path.exists() else {"identities": []}
    logged = {item["canonical_id"] for item in search_log["identities"]}
    # No disk cache: the shared cache rewrites one file per request, and a PMID's
    # retraction status is mutable. Resumability comes from the per-identity files.
    client = PubMedClient(cache_path=None)
    for identity in json.loads(args.partition.read_text()):
        target = args.candidates_dir / f"{identity['canonical_id']}.json"
        if target.exists() and identity["canonical_id"] in logged:
            continue
        log, records = run_identity(client, identity)
        target.write_text(json.dumps({"identity": identity, "search": log, "records": records}, indent=1))
        index_lines = [f"{r['pmid']}\t{(r.get('published_date') or '')[:4]}\t{','.join(r['query_roles'])}\t"
                       f"{'|'.join(t for t in r['publication_types'] if t != 'Journal Article')}\t"
                       f"{'HUMANS' if 'Humans' in r['mesh_terms'] else '-'}\t"
                       f"{'RETRACTED' if r['retracted'] else 'EOC' if r['expression_of_concern'] else '-'}\t{r['title']}"
                       for r in records]
        (args.candidates_dir / f"{identity['canonical_id']}.index.tsv").write_text(
            "pmid\tyear\troles\tpub_types\thumans_mesh\tintegrity\ttitle\n" + "\n".join(index_lines) + "\n")
        search_log["identities"] = [i for i in search_log["identities"] if i["canonical_id"] != identity["canonical_id"]]
        search_log["identities"].append(log)
        log_path.write_text(json.dumps(search_log, indent=1))
        print(f"{identity['canonical_id']}: " + ", ".join(
            f"{q['role']} {q['retrieved']}/{q['count']}" for q in log["queries"]) + f" -> {len(records)} records",
            flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
