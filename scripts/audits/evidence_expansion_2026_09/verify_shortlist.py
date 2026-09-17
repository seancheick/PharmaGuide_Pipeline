#!/usr/bin/env python3
"""Re-verify screened shortlist records against live PubMed (read-only).

Screening output is a draft. Before any of it reaches a pending context, every
shortlisted PMID is re-fetched live and checked for:

  * existence;
  * byte-exact stored-vs-live title (the check that caught nine shipped defects
    on 2026-08-06 — see verify_backed_studies_citations.py);
  * integrity: retraction, expression of concern, erratum;
  * human status signals (Humans MeSH, participant/registration text) — several
    signals, because a new record may not be indexed yet;
  * quote integrity: every verbatim quote must still be an exact substring of
    the live abstract.

Findings are reported; nothing is repaired automatically.

    python3 scripts/audits/evidence_expansion_2026_09/verify_shortlist.py \
        --screen-dir <dir> [--screen-dir <dir>] --candidates-dir <dir>
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))

import env_loader  # noqa: E402,F401
from api_audit.pubmed_client import PubMedClient, parse_pubmed_article_xml  # noqa: E402

QUOTE_FIELDS = ("dose_quote", "primary_outcome_quote", "primary_result_quote",
                "sample_size_quote", "funding_quote")
REGISTRATION = re.compile(r"\b(NCT\d{8}|ISRCTN\d+|CTRI/\d{4}/\d+/\d+|ACTRN\d+|ChiCTR[-\w]*\d+)\b", re.I)
PARTICIPANT = re.compile(r"\b(participants?|patients?|subjects?|volunteers?|men|women|adults?|children)\b", re.I)


def quote_text(value) -> str | None:
    if isinstance(value, dict):
        value = value.get("text")
    return value if isinstance(value, str) and value.strip() else None


def human_signals(article: dict) -> list[str]:
    signals = []
    if "Humans" in (article.get("mesh_terms") or []):
        signals.append("humans_mesh")
    if PARTICIPANT.search(article.get("abstract") or ""):
        signals.append("participants_in_abstract")
    if REGISTRATION.search((article.get("abstract") or "") + " " + (article.get("title") or "")):
        signals.append("trial_registration")
    return signals


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--screen-dir", action="append", required=True, type=Path)
    parser.add_argument("--candidates-dir", required=True, type=Path)
    parser.add_argument("--all-kept", action="store_true",
                        help="verify every kept record, not only the shortlist")
    args = parser.parse_args()

    screens = [json.loads(path.read_text())
               for directory in args.screen_dir for path in sorted(directory.glob("*.screen.json"))]
    wanted: dict[str, set[str]] = {}
    for screen in screens:
        pmids = {str(p) for p in screen.get("shortlist") or []}
        if args.all_kept:
            pmids |= {str(r["pmid"]) for r in screen.get("records") or []}
        wanted[screen["canonical_id"]] = pmids

    client = PubMedClient(cache_path=None)
    findings, verified = [], []
    for canonical_id, pmids in wanted.items():
        if not pmids:
            continue
        stored_path = args.candidates_dir / f"{canonical_id}.json"
        stored = {r["pmid"]: r for r in json.loads(stored_path.read_text())["records"]}
        screen = next(s for s in screens if s["canonical_id"] == canonical_id)
        screened = {str(r["pmid"]): r for r in screen.get("records") or []}
        ids = sorted(pmids, key=lambda value: int(value) if value.isdigit() else 0)
        live = {a["pmid"]: a for a in parse_pubmed_article_xml(client.efetch(ids, rettype="abstract"))}
        for pmid in ids:
            record = live.get(pmid)
            if record is None:
                findings.append({"canonical_id": canonical_id, "pmid": pmid, "finding": "PMID_NOT_FOUND_LIVE"})
                continue
            stored_title = (stored.get(pmid) or {}).get("title") or ""
            if stored_title and record["title"] != stored_title:
                findings.append({"canonical_id": canonical_id, "pmid": pmid, "finding": "TITLE_DRIFT",
                                 "stored": stored_title, "live": record["title"]})
            for flag in ("retracted", "expression_of_concern", "has_erratum"):
                if record.get(flag):
                    findings.append({"canonical_id": canonical_id, "pmid": pmid,
                                     "finding": f"INTEGRITY_{flag.upper()}"})
            signals = human_signals(record)
            if len(signals) < 2:
                findings.append({"canonical_id": canonical_id, "pmid": pmid, "finding": "HUMAN_STATUS_AMBIGUOUS",
                                 "signals": signals})
            for field in QUOTE_FIELDS:
                quote = quote_text((screened.get(pmid) or {}).get(field))
                if quote and quote not in (record.get("abstract") or ""):
                    # An elided quote ("A ... B") is two spans joined, not a quotation:
                    # separate it from a quote whose text simply is not in the source.
                    elided = "..." in quote or "\u2026" in quote
                    findings.append({"canonical_id": canonical_id, "pmid": pmid,
                                     "finding": "QUOTE_ELIDED_NOT_CONTIGUOUS" if elided
                                     else "QUOTE_NOT_IN_LIVE_ABSTRACT",
                                     "field": field, "quote": quote[:160]})
            verified.append({"canonical_id": canonical_id, "pmid": pmid, "title": record["title"],
                             "journal": record.get("journal"), "year": (record.get("published_date") or "")[:4],
                             "publication_types": record.get("publication_types"),
                             "human_signals": signals, "doi": record.get("doi"), "pmc_id": None})
        print(f"{canonical_id}: verified {len(ids)}", flush=True)

    payload = {"_metadata": {"run_date": dt.date.today().isoformat(), "source": "NCBI PubMed E-utilities (live)",
                             "verified_records": len(verified), "findings": len(findings),
                             "scope": "all kept records" if args.all_kept else "shortlisted records"},
               "findings": findings, "verified": verified}
    (OUT / "wave1_live_verification.json").write_text(json.dumps(payload, indent=1))
    print(json.dumps(payload["_metadata"], indent=1))
    for finding in findings[:40]:
        print("  ", finding.get("canonical_id"), finding.get("pmid"), finding["finding"], finding.get("field", ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
