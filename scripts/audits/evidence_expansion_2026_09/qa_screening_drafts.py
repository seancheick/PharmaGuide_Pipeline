#!/usr/bin/env python3
"""Deterministic QA over the quarantined screening drafts (read-only).

The partition-2 screening agent died during its own final verification pass, so
that pass runs here instead — deterministically, which is where it belonged: a
model checking its own quotes is the weakest link in the chain.

Checks every draft against the retrieval it was screened from:

  * every PMID cited by the draft exists in that identity's retrieved record set;
  * every quote field is an exact contiguous substring of the stored abstract,
    separating elided ("A ... B") from otherwise-absent text;
  * counts are consistent: screened versus records retrieved, kept versus records
    carried, shortlist entries drawn from kept records.

Nothing is repaired. The output is the rejection ledger that keeps these drafts
honestly labelled as untrusted input.

    python3 scripts/audits/evidence_expansion_2026_09/qa_screening_drafts.py --candidates-dir <dir>
"""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
DRAFTS = OUT / "QUARANTINE_screening_drafts"
QUOTE_FIELDS = ("dose_quote", "primary_outcome_quote", "primary_result_quote",
                "sample_size_quote", "funding_quote")


def quote_text(value):
    if isinstance(value, dict):
        value = value.get("text")
    return value if isinstance(value, str) and value.strip() else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates-dir", required=True, type=Path)
    args = parser.parse_args()

    per_identity = []
    totals = collections.Counter()
    for path in sorted(DRAFTS.glob("*.screen.json")):
        draft = json.loads(path.read_text())
        identity = draft["canonical_id"]
        retrieval_path = args.candidates_dir / f"{identity}.json"
        if not retrieval_path.exists():
            per_identity.append({"canonical_id": identity, "error": "retrieval set not available"})
            continue
        retrieval = json.loads(retrieval_path.read_text())
        stored = {r["pmid"]: r for r in retrieval["records"]}
        records = draft.get("records") or []
        shortlist = {str(p) for p in draft.get("shortlist") or []}

        unknown_pmids, elided, absent, verified = [], [], [], 0
        for record in records:
            pmid = str(record.get("pmid"))
            if pmid not in stored:
                unknown_pmids.append(pmid)
                continue
            abstract = stored[pmid].get("abstract") or ""
            for field in QUOTE_FIELDS:
                quote = quote_text(record.get(field))
                if not quote:
                    continue
                if quote in abstract:
                    verified += 1
                elif "..." in quote or "…" in quote:
                    elided.append(f"{pmid}:{field}")
                else:
                    absent.append(f"{pmid}:{field}")
        row = {
            "canonical_id": identity,
            "records_retrieved": len(stored),
            "screened_claimed": draft.get("screened"),
            "kept_claimed": draft.get("kept"),
            "records_carried": len(records),
            "rejected_listed": len(draft.get("rejected") or []),
            "shortlist": len(shortlist),
            "handoff": len(draft.get("handoff") or []),
            "quotes_verified": verified,
            "quotes_elided": len(elided),
            "quotes_absent": len(absent),
            "pmids_not_in_retrieval": unknown_pmids,
            "count_mismatch_kept_vs_records": (draft.get("kept") or 0) != len(records),
            "count_mismatch_screened_vs_retrieved": (draft.get("screened") or 0) != len(stored),
            "shortlist_not_in_records": sorted(shortlist - {str(r.get("pmid")) for r in records}),
            "elided_examples": elided[:5], "absent_examples": absent[:5],
        }
        per_identity.append(row)
        totals["identities"] += 1
        for key in ("quotes_verified", "quotes_elided", "quotes_absent"):
            totals[key] += row[key]
        totals["pmids_not_in_retrieval"] += len(unknown_pmids)
        totals["identities_with_count_mismatch"] += bool(
            row["count_mismatch_kept_vs_records"] or row["count_mismatch_screened_vs_retrieved"])
        totals["shortlist_entries_not_in_records"] += len(row["shortlist_not_in_records"])

    payload = {"_metadata": dict(totals) | {
        "purpose": "Rejection ledger for the quarantined drafts; nothing repaired.",
        "verdict": "Drafts remain untrusted input. Authored contexts re-extract every span from the live source."},
        "identities": per_identity}
    (DRAFTS / "QA_LEDGER.json").write_text(json.dumps(payload, indent=1))
    print(json.dumps(payload["_metadata"], indent=1))
    worst = sorted(per_identity, key=lambda r: -(r.get("quotes_elided", 0) + r.get("quotes_absent", 0)))[:8]
    for row in worst:
        if row.get("quotes_elided") or row.get("quotes_absent"):
            print(f"  {row['canonical_id']:<22} elided={row['quotes_elided']:<3} absent={row['quotes_absent']:<3} "
                  f"verified={row['quotes_verified']}")
    for row in per_identity:
        if row.get("pmids_not_in_retrieval") or row.get("shortlist_not_in_records"):
            print(f"  !! {row['canonical_id']}: unknown pmids={row.get('pmids_not_in_retrieval')} "
                  f"shortlist outside records={row.get('shortlist_not_in_records')}")
        if row.get("count_mismatch_kept_vs_records") or row.get("count_mismatch_screened_vs_retrieved"):
            print(f"  ?  {row['canonical_id']}: screened={row.get('screened_claimed')} vs retrieved="
                  f"{row.get('records_retrieved')}; kept={row.get('kept_claimed')} vs carried="
                  f"{row.get('records_carried')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
