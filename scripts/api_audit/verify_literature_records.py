#!/usr/bin/env python3
"""Authoritative verification pipeline for literature_evidence_records.json.

Deterministic verification gate for Phase 4 literature records:
- Queries PubMed API for all cited PMIDs
- Verifies title exact/close match, publication types, human population, topic match
- Detects retractions and errata
- Title mismatches and missing PMIDs remain unresolved for manual review
- Extracts verified evidence quote from live abstract
- Reports machine screening separately from clinical applicability; source writes require --apply
"""
from __future__ import annotations

import argparse
import hashlib
import datetime
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Set

SCRIPT_DIR = Path(__file__).resolve().parent
REPO = SCRIPT_DIR.parent.parent
SCRIPTS_ROOT = REPO / "scripts"

if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

# Load .env for NCBI_API_KEY
_env = REPO / ".env"
if _env.exists():
    for line in _env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

from verify_all_citations_content import fetch_articles
from pubmed_xml import clean_text


LITERATURE_RECORDS_PATH = SCRIPTS_ROOT / "data" / "literature_evidence_records.json"

STOP_WORDS = {
    "the", "and", "for", "with", "study", "trial", "randomized", "controlled",
    "double", "blind", "placebo", "effect", "effects", "efficacy", "safety",
    "human", "patients", "adults", "clinical", "supplementation", "supplement",
    "administration", "extract", "acid", "complex", "during", "versus", "from",
    "response", "levels", "health", "using", "based", "review", "meta", "analysis",
    "systematic", "chronic", "acute", "oral", "daily", "high", "low", "dose",
}


def words(*texts: str) -> Set[str]:
    out: Set[str] = set()
    for t in texts:
        if not t:
            continue
        for w in re.findall(r"[a-z]{3,}", str(t).lower()):
            if w not in STOP_WORDS:
                out.add(w)
    return out


def title_overlap(a: str, b: str) -> float:
    wa, wb = words(a), words(b)
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


def verify_literature_file(apply_fixes: bool = False, record_ids: Set[str] | None = None) -> Dict[str, Any]:
    if not LITERATURE_RECORDS_PATH.exists():
        raise FileNotFoundError(f"Missing {LITERATURE_RECORDS_PATH}")

    source_bytes = LITERATURE_RECORDS_PATH.read_bytes()
    payload = json.loads(source_bytes)
    records = payload.get("literature_evidence_records", [])

    if record_ids is not None:
        unknown = record_ids - {r.get("canonical_id") for r in records}
        if unknown:
            raise ValueError(f"Unknown record IDs: {sorted(unknown)}")
        records = [r for r in records if r.get("canonical_id") in record_ids]

    all_pmids: Set[str] = set()
    for r in records:
        for s in r.get("qualifying_human_studies", []):
            p = str(s.get("pmid") or "").strip()
            if p:
                all_pmids.add(p)

    print(f"Fetching {len(all_pmids)} unique PMIDs from live PubMed API...")
    fetched_articles = fetch_articles(sorted(all_pmids), abstract_chars=None)
    print(f"Successfully fetched {len(fetched_articles)} articles.")

    total_records = len(records)
    total_studies = 0
    failures = []
    corrections = []
    retractions = []

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    for r in records:
        cid = r.get("canonical_id")
        record_provenance = {
            "verified_by": "scripts/api_audit/verify_literature_records.py",
            "verified_at": now_iso,
            "all_pmids_verified": True,
            "retractions_found": False,
        }

        studies = r.get("qualifying_human_studies", [])
        for s in studies:
            total_studies += 1
            pmid = str(s.get("pmid") or "").strip()
            stored_title = s.get("title", "")

            art = fetched_articles.get(pmid)
            live_title = art.get("title", "") if art else ""
            overlap = title_overlap(stored_title, live_title)
            if not art or overlap < 0.30:
                # A title-search result is a discovery lead, never a reviewed
                # replacement citation. Leave the source unchanged for review.
                failures.append({"canonical_id": cid, "pmid": pmid,
                                 "stored_title": stored_title, "live_title": live_title,
                                 "error": "pmid_not_found_in_pubmed" if not art else "title_mismatch"})
                record_provenance["all_pmids_verified"] = False
                continue

            # Update study title to match live authoritative title
            s["title"] = live_title

            # Check topic overlap
            abstract = art.get("abstract", "")
            mesh_terms = art.get("mesh_terms", [])
            all_text = f"{live_title} {abstract} {' '.join(mesh_terms)}".lower()

            topic_words = words(cid.replace("_", " "), r.get("material_form", ""))
            found_topic = any(re.search(r"\b" + re.escape(tw) + r"\b", all_text) for tw in topic_words)
            if not found_topic:
                failures.append({"canonical_id": cid, "pmid": pmid, "error": "topic_match_not_verified"})
                record_provenance["all_pmids_verified"] = False

            # Text mentions (including "men" inside "supplementation") do not
            # establish a human population. Human-derived cells can also carry
            # the Humans MeSH heading. Ambiguous/mixed cellular research needs
            # source review rather than automatic human-subject verification.
            indexed_terms = {str(term).strip().casefold() for term in mesh_terms}
            cellular_research = any(
                term == "in vitro techniques"
                or term == "cells, cultured"
                or term.startswith("cell line")
                for term in indexed_terms
            )
            is_human = "humans" in indexed_terms and not cellular_research
            # A reviewed negative laboratory finding is still valid source
            # evidence. Human efficacy and source validity are distinct; retain
            # the existing reviewed-negative disposition, never create one.
            reviewed_negative = (
                r.get("applicability_status") == "reviewed_null_evidence"
                and r.get("effect_direction") in {"negative", "null", "reviewed_null_unfavorable"}
            )
            if not is_human and not reviewed_negative:
                failures.append({
                    "canonical_id": cid,
                    "pmid": pmid,
                    "error": "human_population_not_verified",
                })
                record_provenance["all_pmids_verified"] = False

            # Extract an evidence quote from abstract
            evidence_quote = ""
            if abstract:
                sentences = re.split(r"(?<=[.!?])\s+", abstract)
                for sent in reversed(sentences):
                    sent_lower = sent.lower()
                    if any(k in sent_lower for k in ("conclude", "demonstrate", "show", "result", "significan", "effect", "reduce", "increase", "no effect", "difference")):
                        evidence_quote = clean_text(sent)
                        break
                if not evidence_quote and sentences:
                    evidence_quote = clean_text(sentences[-1])

            # Check retraction
            is_retracted = (
                art.get("retracted") is True
                or "retracted publication" in [m.lower() for m in art.get("publication_types", [])]
                or any(c.get("type") == "RetractionIn" for c in art.get("comments_corrections", []))
                or "retracted publication" in [m.lower() for m in mesh_terms]
                or "retraction of" in live_title.lower()
                or "retraction:" in live_title.lower()
            )
            if is_retracted:
                retractions.append({
                    "canonical_id": cid,
                    "pmid": pmid,
                    "title": live_title,
                })
                record_provenance["retractions_found"] = True

            for flag in ("expression_of_concern", "has_erratum"):
                if art.get(flag):
                    failures.append({"canonical_id": cid, "pmid": pmid, "error": flag + "_requires_review"})
                    record_provenance["all_pmids_verified"] = False

            # Persist study-level machine verification provenance
            s["verification_provenance"] = {
                "pmid_verified": True,
                "authoritative_live_title": live_title,
                "human_subjects_verified": is_human,
                "topic_match_verified": found_topic,
                "retracted": is_retracted,
                "verified_source": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                "verified_at": now_iso,
                "abstract_evidence_quote": evidence_quote,
            }

        if not studies:
            record_provenance["all_pmids_verified"] = False
            failures.append({"canonical_id": cid, "error": "no_studies_to_verify"})
        r["verification_provenance"] = record_provenance
        if record_provenance["retractions_found"]:
            r["verification_result"] = "retraction_detected_unresolved"
        elif not record_provenance["all_pmids_verified"]:
            r["verification_result"] = "verification_failure_unresolved"
        else:
            r["verification_result"] = "authoritative_pubmed_verified"

    if apply_fixes and record_ids is not None:
        # Global verification counts must never describe a selected subset.
        raise ValueError("Selected audits are read-only; apply reviewed changes through data_batch")
    if apply_fixes:
        payload["_metadata"]["last_updated"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
        payload["_metadata"]["verification_pipeline"] = "scripts/api_audit/verify_literature_records.py"
        payload["_metadata"]["verified_studies_count"] = total_studies
        payload["_metadata"]["verified_records_count"] = total_records
        LITERATURE_RECORDS_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Saved verified records to {LITERATURE_RECORDS_PATH}")

    report = {
        "mode": "apply" if apply_fixes else "read_only",
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "clinical_applicability_verified": False,
        "verification_scope": "PubMed bibliographic and abstract screening only; not full-text, dose, outcome or clinician approval",
        "records": records,
        "records_checked": total_records,
        "studies_checked": total_studies,
        "verification_failures_count": len(failures),
        "failures": failures,
        "corrections_count": len(corrections),
        "corrections": corrections,
        "retractions_count": len(retractions),
        "retractions": retractions,
    }
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read-only PubMed literature screening; not clinical approval")
    parser.add_argument("--record-id", action="append", help="Canonical ID to audit (repeatable)")
    parser.add_argument("--report", type=Path, help="Write audit report outside curated data")
    parser.add_argument("--apply", action="store_true", help="Explicitly apply reviewed whole-file machine provenance changes")
    args = parser.parse_args(argv)
    if args.report and (args.report.resolve() == LITERATURE_RECORDS_PATH.resolve()
                        or (SCRIPTS_ROOT / "data").resolve() in args.report.resolve().parents):
        parser.error("Audit reports must not overwrite curated data")
    if args.apply and args.record_id:
        parser.error("Selected audits are read-only; apply reviewed changes through data_batch")
    try:
        report = verify_literature_file(apply_fixes=args.apply,
                                       record_ids=set(args.record_id) if args.record_id else None)
    except ValueError as exc:
        parser.error(str(exc))
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(f"{report['mode']}: {report['records_checked']} records; {report['studies_checked']} studies; "
          f"{report['verification_failures_count']} findings; {report['retractions_count']} retractions")
    print(report['verification_scope'])
    return int(bool(report['verification_failures_count'] or report['retractions_count']))


if __name__ == "__main__":
    sys.exit(main())
