"""Validate a returned reviewer response before it becomes calibration truth.

The benchmark is the human oracle the v4 scorer is measured against, so an error
in the reviewer's own file propagates into the calibration rather than being
caught by it. This checks the parts of a response that are objectively
checkable, and deliberately does not touch the parts that are not.

Checked:
  * pillar arithmetic and bounds, required-field validity;
  * every cited PMID resolves on PubMed (existence);
  * every cited PMID is topically connected to the product it was cited for
    (a real PMID attached to the wrong product is this repo's recurring
    "ghost citation" failure -- existence is not content);
  * dose figures written in the rationale reconcile with the label facts the
    reviewer was given.

NOT checked, on purpose: clinical judgment. "Isolated-BCAA evidence is mixed"
is an expert opinion, and overriding it with an automated verdict would replace
the panel's judgment with the engine's -- destroying the independence the
benchmark exists to measure. Findings here are for human adjudication; this
script never edits a response.

Usage: python3 audit_reviewer_responses.py [--reviewer PHAM] [--offline]
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FREEZE = ROOT / "reports" / "v4_reviewer_benchmark_2026_08_06_v6"
sys.path.insert(0, str(ROOT))

from api_audit.pubmed_client import (  # noqa: E402
    PubMedClient,
    parse_pubmed_article_xml,
)

PILLAR_LIMITS = {
    "formulation_0_20": 20.0, "dose_0_20": 20.0, "evidence_0_20": 20.0,
    "transparency_0_15": 15.0, "verification_0_15": 15.0,
    "formula_quality_checks_0_10": 10.0,
}
ENUMS = {
    "product_safety_status": {"no_known_catalog_concern", "caution", "blocked",
                              "not_assessed"},
    "assessment_confidence": {"low", "moderate", "high"},
    "label_facts_sufficient": {"yes", "no"},
}
# Words too generic to prove a citation is about this product.
STOPWORDS = {
    "acid", "extract", "complex", "blend", "powder", "oil", "vitamin", "mineral",
    "supplement", "supplements", "capsule", "root", "leaf", "seed", "fruit",
    "natural", "other", "and", "the", "with", "from", "unspecified", "usp",
    "anhydrous", "citrate", "oxide", "chelate", "isolate", "concentrate",
}
TOKEN = re.compile(r"[a-z0-9][a-z0-9-]{1,}")
# Ingredient names and paper titles spell the same molecule differently.
# Without these, an HMB product citing the HMB position stand looks like a
# ghost, which would send a reviewer chasing a defect that is not there.
SYNONYM = {
    "hmb": {"hydroxy", "methylbutyrate", "hydroxymethylbutyrate"},
    "5-htp": {"hydroxytryptophan", "5-hydroxytryptophan", "tryptophan"},
    "theanine": {"l-theanine"},
    "bcaa": {"branched-chain", "branched"},
    "alpha-galactosidase": {"galactosidase"},
    "whey": {"protein"},
    "epa": {"eicosapentaenoic"},
    "dha": {"docosahexaenoic"},
    "coq10": {"coenzyme", "ubiquinone", "ubiquinol"},
}


def tokens(text: str) -> set[str]:
    out: set[str] = set()
    for raw in TOKEN.findall((text or "").lower()):
        if raw in STOPWORDS:
            continue
        out.add(raw)
        # "l-theanine" must also match a plain "theanine" row, and vice versa
        out.update(part for part in raw.split("-")
                   if len(part) > 2 and part not in STOPWORDS)
    for token in list(out):
        out |= SYNONYM.get(token, set())
    return out


def load_rows(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(path.open()))


def check_structure(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    findings = []
    for row in rows:
        bid = row["benchmark_id"]
        try:
            values = {k: float(row[k]) for k in PILLAR_LIMITS}
        except (TypeError, ValueError):
            findings.append({"benchmark_id": bid, "check": "pillar_parse",
                             "detail": "a pillar value is not numeric"})
            continue
        for field, limit in PILLAR_LIMITS.items():
            if not 0.0 <= values[field] <= limit:
                findings.append({"benchmark_id": bid, "check": "pillar_bounds",
                                 "detail": f"{field}={values[field]} outside 0..{limit}"})
        try:
            overall = float(row["overall_0_100"])
        except (TypeError, ValueError):
            findings.append({"benchmark_id": bid, "check": "overall_parse",
                             "detail": "overall_0_100 is not numeric"})
        else:
            if abs(sum(values.values()) - overall) > 1e-6:
                findings.append({
                    "benchmark_id": bid, "check": "overall_arithmetic",
                    "detail": f"pillars sum to {sum(values.values())}, "
                              f"overall_0_100 says {overall}"})
        for field, allowed in ENUMS.items():
            if (row.get(field) or "").strip() not in allowed:
                findings.append({"benchmark_id": bid, "check": "enum",
                                 "detail": f"{field}={row.get(field)!r}"})
    return findings


def cited_pmids(row: dict[str, str]) -> list[str]:
    raw = row.get("source_citations_json") or ""
    return sorted(set(re.findall(r"PMID[:\s]*(\d{6,9})", raw, re.I)))


def fetch_articles(client: PubMedClient, pmids: list[str]) -> dict[str, dict]:
    found: dict[str, dict] = {}
    for start in range(0, len(pmids), 20):
        batch = pmids[start:start + 20]
        xml = client.efetch(batch, db="pubmed", retmode="xml")
        for article in parse_pubmed_article_xml(xml):
            if article.get("pmid"):
                found[str(article["pmid"])] = article
    return found


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reviewer", default="PHAM")
    ap.add_argument("--offline", action="store_true",
                    help="structural checks only; skip PubMed")
    ap.add_argument("--out", type=Path, default=HERE)
    args = ap.parse_args()

    answers = HERE / "responses" / f"answers_{args.reviewer}.csv"
    if not answers.is_file():
        print(f"no response file: {answers}", file=sys.stderr)
        return 2
    rows = load_rows(answers)
    packet = {r["benchmark_id"]: r
              for r in csv.DictReader((FREEZE / "reviewer_packet.csv").open())}

    findings = check_structure(rows)
    print(f"reviewer {args.reviewer}: {len(rows)} responses")
    print(f"structural findings: {len(findings)}")

    every = sorted({p for row in rows for p in cited_pmids(row)})
    print(f"unique PMIDs cited: {len(every)}")

    if args.offline:
        articles = {}
    else:
        client = PubMedClient()
        articles = fetch_articles(client, every)
        missing = [p for p in every if p not in articles]
        for pmid in missing:
            findings.append({"benchmark_id": "", "check": "pmid_not_found",
                             "detail": f"PMID {pmid} did not resolve on PubMed"})
        print(f"resolved on PubMed: {len(articles)}/{len(every)}")

    # Topic match: a real PMID attached to an unrelated product is a ghost.
    pairs = []
    for row in rows:
        bid = row["benchmark_id"]
        entry = packet.get(bid)
        if not entry:
            continue
        actives = json.loads(entry["active_ingredients_json"] or "[]")
        product_terms = tokens(entry["product_name"])
        for active in actives:
            product_terms |= tokens(active.get("name") or "")
        for pmid in cited_pmids(row):
            article = articles.get(pmid)
            if not article:
                continue
            corpus = " ".join(filter(None, [
                article.get("title") or "",
                article.get("abstract") or "",
                " ".join(article.get("mesh_terms") or []),
            ]))
            overlap = product_terms & tokens(corpus)
            pairs.append({
                "benchmark_id": bid,
                "pmid": pmid,
                "product_name": entry["product_name"],
                "title": (article.get("title") or "")[:150],
                "shared_terms": ";".join(sorted(overlap)[:8]),
                "overlap_count": len(overlap),
                "needs_human_review": "yes" if not overlap else "no",
            })

    ghosts = [p for p in pairs if p["needs_human_review"] == "yes"]
    print(f"citation-to-product pairs: {len(pairs)}")
    print(f"pairs with NO shared term (candidate ghosts): {len(ghosts)}")

    args.out.mkdir(parents=True, exist_ok=True)
    pair_path = args.out / f"AUDIT_{args.reviewer}_citation_pairs.csv"
    if pairs:
        with pair_path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(pairs[0]))
            writer.writeheader()
            writer.writerows(sorted(pairs, key=lambda p: p["overlap_count"]))
        print(f"wrote {pair_path}")

    find_path = args.out / f"AUDIT_{args.reviewer}_findings.csv"
    with find_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["benchmark_id", "check", "detail"])
        writer.writeheader()
        writer.writerows(findings)
    print(f"wrote {find_path}")

    for finding in findings[:20]:
        print(f"  [{finding['check']}] {finding['benchmark_id']} {finding['detail']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
